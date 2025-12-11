# Stage 1: Builder - Create a wheelhouse for dependencies
FROM python:3.10-slim-bullseye AS builder

# Set environment variables for pip
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PIP_NO_CACHE_DIR=off
ENV PIP_DISABLE_PIP_VERSION_CHECK=on

WORKDIR /wheelhouse

# Copy requirements file
COPY omni_desk_backend/requirements-prod.txt .

# Create wheelhouse for all dependencies. This command downloads/builds all packages and their dependencies.
RUN pip wheel --wheel-dir=/wheelhouse -r requirements-prod.txt

# Stage 2: Final - Create the lightweight production image
FROM python:3.10-slim-bullseye

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV DJANGO_ENV=production

# Create a non-root user to run the application
RUN addgroup --system app && adduser --system --group app

# Install runtime OS dependencies
# libpq5 is the runtime dependency for psycopg2-binary
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/*

# Copy the wheelhouse and requirements file from the builder stage
COPY --from=builder /wheelhouse /wheelhouse
COPY --from=builder /wheelhouse/requirements-prod.txt .

# Install Python dependencies from the local wheelhouse
# --no-index ensures pip does not access the network
RUN pip install --no-cache-dir --no-index --find-links=/wheelhouse -r requirements-prod.txt

# Set the working directory for the application
WORKDIR /usr/src/app

# Copy the application code into the image
# The .dockerignore file prevents unnecessary files from being included.
# We are copying the contents of omni_desk_backend into the WORKDIR.
COPY --chown=app:app omni_desk_backend/ .

# Collect static files as root user
RUN python manage.py collectstatic --no-input --clear

# Switch to the non-root user for security
USER app

# Expose the port Gunicorn will listen on
EXPOSE 8000

# Define the command to run the application
# This CMD is often overridden by docker-compose.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "omni_desk_backend.wsgi:application"]
