#!/bin/bash

APP_DIR="/home/ubuntu/flaskapp1"
REPO_URL="https://github.com/carpeadiam/artifact-interactive.git"

sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv git nginx ufw

mkdir -p $APP_DIR
cd $APP_DIR

echo "Cloning or pulling latest..."
if [ ! -d ".git" ]; then
    git clone $REPO_URL .
else
    git pull origin main
fi

echo "Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt gunicorn
deactivate
