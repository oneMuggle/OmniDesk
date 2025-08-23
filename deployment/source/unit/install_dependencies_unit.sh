#!/bin/bash

# install_dependencies_unit.sh
# Installs all necessary dependencies for the Omni Desk application
# on a fresh Ubuntu 22.04 server for the Nginx Unit setup.

set -e

echo "Updating system packages..."
sudo apt-get update -y && sudo apt-get upgrade -y

echo "Installing common dependencies..."
sudo apt-get install -y python3.10 python3.10-venv python3-pip postgresql postgresql-contrib curl

# Install Node.js and npm
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

# Install Redis
echo "Installing Redis server..."
sudo apt-get install -y redis-server

# Install Nginx Unit
echo "Installing Nginx Unit..."
sudo apt-get install -y unit unit-python3.10

# Enable and start services
echo "Enabling and starting services..."
sudo systemctl enable unit
sudo systemctl start unit
sudo systemctl enable redis-server
sudo systemctl start redis-server
sudo systemctl enable postgresql
sudo systemctl start postgresql

echo "All dependencies for Nginx Unit setup have been installed successfully."
exit 0