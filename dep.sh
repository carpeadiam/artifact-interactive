#!/bin/bash

# --- 1. SETUP & INSTALLATION ---
echo "Updating system and installing packages..."
# Ensure python3-venv is available, along with basic tools
apt-get update && apt-get install -y python3 python3-pip python3-venv git nginx ufw

APP_DIR="/home/ubuntu/flaskapp"

# Create a dedicated low-privilege user for the app
# Use 'www-data' which is standard for web services, or create a new one:
# useradd -r -s /bin/false flaskapp_user

# --- 2. CLONE & SETUP APP ---
mkdir -p $APP_DIR
cd $APP_DIR

echo "Cloning Flask application..."
# IMPORTANT: Replace with your actual GitHub repository URL
git clone https://github.com/azure-glades/artifact-interactive.git .

echo "Setting up virtual environment and installing dependencies..."
python3 -m venv venv
source venv/bin/activate
# Install Gunicorn alongside your app dependencies
pip install -r requirements.txt gunicorn

# --- 3. CONFIGURE GUNICORN (Systemd Service) ---
echo "Creating Gunicorn Systemd service file..."
cat > /etc/systemd/system/flaskapp.service << EOF
[Unit]
Description=Flask App Gunicorn Service
After=network.target

[Service]
# IMPORTANT: Use a low-privilege user (e.g., www-data or a dedicated one)
User=ubuntu
# If using a custom user, uncomment the next line and change to your custom group
Group=www-data
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
# Bind Gunicorn to the local interface (127.0.0.1) for security
ExecStart=$APP_DIR/venv/bin/gunicorn --bind 127.0.0.1:8000 app:app

[Install]
WantedBy=multi-user.target
EOF

# --- 4. CONFIGURE NGINX (Reverse Proxy) ---
echo "Setting up Nginx reverse proxy..."
NGINX_CONF="/etc/nginx/sites-available/flaskapp"

# IMPORTANT: Change 'your_domain_or_ip' to your Civo IP address or domain name
cat > $NGINX_CONF << EOF
server {
    listen 80;
    server_name _; # Use the underscore if you don't have a domain name yet

    location / {
        # Pass traffic from Nginx to Gunicorn on the internal address
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_redirect off;
    }
}
EOF

# Enable the new site and remove the default Nginx page
ln -sf $NGINX_CONF /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test configuration and restart Nginx
nginx -t && systemctl restart nginx

# --- 5. START SERVICES & FIREWALL ---
echo "Starting and enabling Flask app service..."
systemctl daemon-reload
systemctl start flaskapp
systemctl enable flaskapp

echo "Configuring firewall (ufw)..."
# IMPORTANT: Only port 80 (HTTP) and potentially 22 (SSH) are exposed publicly
ufw allow 'Nginx HTTP'
ufw allow ssh
ufw --force enable

echo "Deployment script finished successfully!"