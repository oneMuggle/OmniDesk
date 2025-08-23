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
# Remove NodeSource apt source list to prevent conflicts
sudo rm -f /etc/apt/sources.list.d/nodesource.list
# Purge all nodejs related packages
sudo apt-get purge -y nodejs npm libnode-dev || true
# Clean up any leftover dependencies
sudo apt-get autoremove -y
sudo apt-get clean
# Attempt to forcibly remove libnode-dev before installing new nodejs
# This command forcefully removes the package and ignores dependency issues
sudo dpkg --remove --force-remove-reinstreq libnode-dev || true
# Remove any remaining Node.js related files and directories
sudo find /usr/local -name "node*" -exec rm -rf {} + || true
sudo rm -rf /usr/local/bin/npm /usr/local/share/man/man1/node* /usr/local/lib/dtrace/node.d || true
sudo rm -rf /opt/nodejs || true
# Remove any remaining nodesource apt sources
sudo rm -f /etc/apt/sources.list.d/nodesource.list
# Update package list after cleanup
sudo apt-get update

# Ensure all previous nodesource list files are removed
sudo rm -f /etc/apt/sources.list.d/nodesource.list

# Re-add NodeSource repository for Node.js 18.x
curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.d/nodesource.gpg | sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_18.x nodistro main" | sudo tee /etc/apt/sources.list.d/nodesource.list
sudo apt-get update

# Re-add NodeSource repository for Node.js 18.x
curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.d/nodesource.gpg | sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_18.x nodistro main" | sudo tee /etc/apt/sources.list.d/nodesource.list
sudo apt-get update

echo "Installing Node.js and npm..."
# Remove old NodeSource keys if they exist
sudo rm -f /etc/apt/keyrings/nodesource.gpg

# Add NodeSource repository for Node.js 18.x
curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.d/nodesource.gpg | sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_18.x nodistro main" | sudo tee /etc/apt/sources.list.d/nodesource.list

sudo apt-get update
sudo apt-get --fix-broken install -y # Add this line to fix broken dependencies
# Install Node.js
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