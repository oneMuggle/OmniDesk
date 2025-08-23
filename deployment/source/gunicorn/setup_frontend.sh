#!/bin/bash

# setup_frontend.sh
# Sets up the frontend for the Omni Desk application.

set -e

# Configuration
PROJECT_DIR="/var/www/omni_desk"
FRONTEND_DIR="$PROJECT_DIR/omni_desk_frontend"
DEST_DIR="$PROJECT_DIR/frontend_build"

echo "Navigating to the frontend directory: $FRONTEND_DIR"
cd $FRONTEND_DIR

echo "Installing npm dependencies..."
npm install

echo "Building the React application..."
npm run build

echo "Creating destination directory: $DEST_DIR"
sudo mkdir -p $DEST_DIR
sudo chown $USER:$USER -R $DEST_DIR

echo "Deploying build files to $DEST_DIR..."
# Using rsync is efficient as it only copies changed files.
sudo rsync -a --delete build/ $DEST_DIR/

echo "Frontend setup is complete. The static files are located in $DEST_DIR."

exit 0