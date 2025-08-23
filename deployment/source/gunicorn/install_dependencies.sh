#!/bin/bash

# install_dependencies.sh
# Installs all necessary dependencies for the Omni Desk application
# on a fresh Ubuntu 22.04 server for the Gunicorn + Nginx setup.

# Exit immediately if a command exits with a non-zero status.
set -e

# Update package list and upgrade existing packages
echo "Updating system packages..."
sudo apt-get update -y && sudo apt-get upgrade -y

# Install system-level dependencies
echo "Installing system dependencies..."
sudo apt-get install -y python3.10 python3.10-venv python3-pip postgresql postgresql-contrib nginx curl

# Install Node.js and npm for frontend builds
# Using NodeSource repository for a specific Node.js version
echo "Installing Node.js and npm..."

# Remove conflicting Node.js packages and old NodeSource repositories if they exist
echo "Cleaning up existing Node.js installations..."
sudo rm -f /etc/apt/sources.list.d/nodesource.list
sudo apt-get purge -y nodejs npm libnode-dev || true
sudo apt-get autoremove -y
sudo apt-get clean
sudo apt-get remove --purge -y libnode-dev || true

echo "Installing Node.js and npm..."
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install Redis for Celery message broker
echo "Installing Redis server..."
sudo apt-get install -y redis-server

# Enable and start services
echo "Enabling and starting services..."
sudo systemctl enable nginx
sudo systemctl start nginx
sudo systemctl enable redis-server
sudo systemctl start redis-server
sudo systemctl enable postgresql
sudo systemctl start postgresql

echo "All dependencies have been installed successfully."
exit 0