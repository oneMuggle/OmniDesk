#!/bin/bash

# --- Exit Handler ---
# Function to be executed on script exit
function on_exit {
    echo "" # Add a newline for better formatting
    read -n 1 -s -r -p "Press any key to exit..."
}

# Register the exit handler
trap on_exit EXIT

# Usage: ./build_and_export.sh <version> <docker_user> [export_dir]
#
# This script builds Docker images using build.sh and then exports them
# using export_images.sh.
#
# Arguments:
#   version       The version tag for the Docker images (e.g., 1.0.0).
#   docker_user   The Docker username or organization.
#   export_dir    (Optional) The directory to export the images to.
#                 Defaults to the current directory.
#
# Example:
#   ./build_and_export.sh 1.0.0 mydockeruser
#   ./build_and_export.sh 1.0.0 mydockeruser /tmp/docker_images

# --- Argument Parsing ---
VERSION=$1
DOCKER_USER=$2
EXPORT_DIR=${3:-.} # Default to current directory if not provided

# --- Input Validation ---
if [ -z "$VERSION" ] || [ -z "$DOCKER_USER" ]; then
  echo "Error: Version and Docker user are required."
  echo "Usage: $0 <version> <docker_user> [export_dir]"
  exit 1
fi

# --- Step 1: Build Docker Images ---
echo "--- Running build.sh ---"
./build.sh "$VERSION" "$DOCKER_USER"

# Check if the build script succeeded
if [ $? -ne 0 ]; then
  echo "Error: build.sh failed. Aborting."
  exit 1
fi

echo "--- build.sh completed successfully ---"

# --- Step 2: Export Docker Images ---
echo "--- Running export_images.sh ---"
./export_images.sh "$VERSION" "$DOCKER_USER" "$EXPORT_DIR"

# Check if the export script succeeded
if [ $? -ne 0 ]; then
  echo "Error: export_images.sh failed. Aborting."
  exit 1
fi

echo "--- export_images.sh completed successfully ---"
echo "Build and export process finished successfully."