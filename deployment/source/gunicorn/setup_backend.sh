#!/bin/bash

# setup_backend.sh
# Sets up the backend for the Omni Desk application.

set -e

# Configuration
PROJECT_DIR="/var/www/omni_desk"
BACKEND_DIR="$PROJECT_DIR/omni_desk_backend"
VENV_DIR="$PROJECT_DIR/venv"
DB_NAME="omni_desk"
DB_USER="omni_desk_user"
DB_PASSWORD="a_strong_and_secure_password" # Please change this!

# 1. Create project directory
echo "Creating project directory at $PROJECT_DIR..."
sudo mkdir -p $PROJECT_DIR
sudo chown $USER:$USER -R $PROJECT_DIR

# 2. Setup PostgreSQL Database
echo "Setting up PostgreSQL database and user..."
# Create a user and database, grant privileges. Using --password to prompt for a password securely.
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME;" || echo "Database $DB_NAME already exists."
sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';" || echo "User $DB_USER already exists."
sudo -u postgres psql -c "ALTER ROLE $DB_USER SET client_encoding TO 'utf8';"
sudo -u postgres psql -c "ALTER ROLE $DB_USER SET default_transaction_isolation TO 'read committed';"
sudo -u postgres psql -c "ALTER ROLE $DB_USER SET timezone TO 'UTC';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"

# 3. Setup Python Virtual Environment
echo "Setting up Python virtual environment at $VENV_DIR..."
python3 -m venv $VENV_DIR
source $VENV_DIR/bin/activate

# 4. Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r $BACKEND_DIR/requirements.txt

# 5. Create .env file for the backend
echo "Creating .env file..."
cat > $BACKEND_DIR/.env << EOL
# Backend Environment Variables
SECRET_KEY='$(openssl rand -hex 32)'
DEBUG=False
ALLOWED_HOSTS=your_domain.com,www.your_domain.com,localhost
DATABASE_URL=postgres://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
EOL

# 6. Run Django migrations and collect static files
echo "Running Django migrations and collecting static files..."
python $BACKEND_DIR/manage.py migrate
python $BACKEND_DIR/manage.py collectstatic --no-input

echo "Backend setup is complete. Please review the .env file in $BACKEND_DIR."
echo "IMPORTANT: Remember to replace 'your_domain.com' in the .env file with your actual domain name."

deactivate
exit 0