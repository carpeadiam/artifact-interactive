import uuid
import json
import os
import io
import base64
import qrcode
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_from_directory
from database import init_db, store_label_data, get_label_data, get_all_label_summaries, delete_label_data
from werkzeug.utils import secure_filename

# --- Configuration ---
UPLOADS_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp3', 'wav'}
 
app = Flask(__name__)
app.config['UPLOADS_FOLDER'] = UPLOADS_FOLDER
# Ensure the upload directory exists
os.makedirs(UPLOADS_FOLDER, exist_ok=True)

# Initialize the database when the app starts
init_db(app)

def allowed_file(filename):
    """Checks if the file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ----------------------------------------------------
# 1. Frontend Route (Serving the index.html form)
# ----------------------------------------------------
@app.route('/')
def home():
    """Renders the data collection form."""
    return render_template('index.html')

# ----------------------------------------------------
# 2. File Upload Handling
# ----------------------------------------------------
@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handles image and audio file uploads."""
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file and allowed_file(file.filename):
        # Use secure_filename to prevent directory traversal attacks
        filename = secure_filename(file.filename)
        # Prepend UUID to filename to ensure uniqueness
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        filepath = os.path.join(app.config['UPLOADS_FOLDER'], unique_filename)
        
        file.save(filepath)
        
        # Return the server-side file path to the frontend for use in the exhibit data
        return jsonify({
            "success": True, 
            "filename": unique_filename,
            # The URI the final label will use to access the file
            "media_uri": url_for('uploaded_file', filename=unique_filename) 
        }), 200
    else:
        return jsonify({"error": "File type not allowed"}), 400

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Route to serve the uploaded files securely."""
    return send_from_directory(app.config['UPLOADS_FOLDER'], filename)

# ----------------------------------------------------
# 3. Data Submission & Storage (Receiving JSON)
# ----------------------------------------------------
@app.route('/api/create_label', methods=['POST'])
def create_label():
    """Receives JSON data, stores it, and returns the unique URL."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided in request body."}), 400

        # Generate a unique, short ID for the exhibit label
        label_id = str(uuid.uuid4())[:8]

        # Store the data in the SQLite database
        store_label_data(label_id, data)

        label_url = url_for('unified_exhibit_site', label_id=label_id)

        print(f"--- SUCCESS: Label {label_id} created. URL: {label_url} ---")
        return jsonify({
            "message": "Exhibit label data successfully saved.",
            "label_id": label_id,
            "url": label_url
        }), 201

    except Exception as e:
        print(f"ERROR during label creation: {e}")
        return jsonify({"error": f"Internal server error: {e}"}), 500
        
# ----------------------------------------------------
# 4. Label Deletion
# ----------------------------------------------------
@app.route('/api/delete_label/<label_id>', methods=['DELETE'])
def delete_label(label_id):
    """Deletes an exhibit label from the database."""
    success = delete_label_data(label_id)
    if success:
        # Note: You might want to also delete the files in the UPLOADS_FOLDER
        return jsonify({"message": f"Label {label_id} deleted successfully."}), 200
    else:
        return jsonify({"error": f"Could not delete label {label_id}."}), 404

# ----------------------------------------------------
# 5. QR Code Generation
# ----------------------------------------------------
def generate_qrcode_base64(url):
    """Generates a QR code image as a Base64 string."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save image to an in-memory buffer
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    
    # Encode the buffer content as Base64
    img_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{img_b64}"


# ----------------------------------------------------
# 6. Unified Site Structure (The New Viewer)
# ----------------------------------------------------
@app.route('/exhibit/<label_id>')
def unified_exhibit_site(label_id):
    """
    Renders the unified site base template, populating the sidebar 
    and loading the specified exhibit content.
    """
    # 1. Fetch all exhibit summaries for the sidebar
    all_exhibits = get_all_label_summaries()
    
    # 2. Fetch the specific exhibit data
    label_data = get_label_data(label_id)

    # 3. Handle 404 if the specific exhibit doesn't exist
    if not label_data:
        return render_template('error_404.html', label_id=label_id), 404

    # 4. Generate QR Code for the current exhibit URL
    full_url = url_for('unified_exhibit_site', label_id=label_id, _external=True)
    qr_code_image = generate_qrcode_base64(full_url)

    # 5. Determine which content template to use based on the data
    template_type = label_data.get('template', 'minimalist')
    
    # Render the base template, which will automatically render the specific content template
    return render_template(
        'base_site.html',
        all_exhibits=all_exhibits,
        current_exhibit=label_data,
        current_template=f'{template_type}_label.html',
        qr_code_image=qr_code_image # Pass the Base64 image to the template
    )


##################### APK CREATOR #######################
from flask import send_file
import os, subprocess, uuid, shutil, json

WEBAPK_PATH = "/opt/webapk"

@app.route("/generate-app/<label_id>", methods=["POST"])
def generate_app():
    
    
    app_name = "Artifact"
    app_id = "001"
    mainURL = "host_replace_bro/exhibit/"+str(label_id)
    icon = None
    
    if not app_name or not app_id or not mainURL:
        return jsoify({"error": "name, id and mainURL are required"}), 400
    
    # Create build directory (unique per user request)
    build_id = str(uuid.uuid4())
    work_dir = f"{WEBAPK_PATH}/builds/{build_id}"
    os.makedirs(work_dir, exist_ok=True)

    # Generate webapk.conf dynamically
    conf_path = f"{work_dir}/webapk.conf"
    with open(conf_path, "w") as f:
        f.write(f"id = {app_id}\n")
        f.write(f"name = {app_name}\n")
        f.write(f"mainURL = {mainURL}\n")
        if icon:
            f.write(f"icon = {icon}\n")
        f.write("allowSubdomains = true\n")
        f.write("enableExternalLinks = true\n")
 
    try:
        # Run the build command
        subprocess.check_call(["bash", "-c", f"cd {WEBAPK_PATH} && ./make.sh build {conf_path}"])
        
        # The script outputs something like app-release.apk
        apk_output = f"{WEBAPK_PATH}/{app_id}.apk"

        if not os.path.exists(apk_output):
            return jsonify({"error": "APK build failed"}), 500
        
        return send_file(apk_output, as_attachment=True, download_name=f"{app_name}.apk")

    except subprocess.CalledProcessError as e:
        return jsonify({"error": "Build process failed", "details": str(e)}), 500

"""
    finally:
        # ⚠ Optional: cleanup build folders
        shutil.rmtree(work_dir, ignore_errors=True)
"""


if __name__ == "__main__":
    app.run(debug=True)












 
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error_404.html', label_id='N/A'), 404


if __name__ == '__main__':
    app.run()
