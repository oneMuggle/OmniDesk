# =====================================================================
# Base Stage
# =====================================================================
FROM python:3.10-slim-bookworm AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
# SECURITY/PERFORMANCE (Phase 8): Disable pip cache in Docker to reduce image size
# (Previous value 'off' actually meant cache ON, defeating the purpose)
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=on

# Install runtime library for psycopg2 and libmagic for python-magic
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 libmagic1 && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /usr/src/app

# =====================================================================
# Builder Stage
# =====================================================================
FROM base AS builder

# Install build dependencies (only in builder)
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /wheelhouse

# Copy only the production requirements file
COPY omni_desk_backend/requirements-prod.txt .

# Build the wheelhouse for production dependencies
RUN pip wheel --wheel-dir=/wheelhouse -r requirements-prod.txt

# =====================================================================
# Development Stage
# =====================================================================
# This stage is for local development and testing
FROM base AS development

# Copy all requirements files
COPY omni_desk_backend/requirements.txt omni_desk_backend/requirements-prod.txt ./

# Install all dependencies (dev + prod)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY omni_desk_backend/ .

# The default command for development will be to run the dev server
# This can be overridden in docker-compose.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# =====================================================================
# Production Stage
# =====================================================================
# This is the final, lean production image
FROM base AS production

# Set production environment
ENV DJANGO_ENV=production

# Create a non-root user to run the application
# 显式创建 HOME 目录,避免 gunicorn 等工具回退到 /root(切到 app 用户后无权限)
RUN addgroup --system app && adduser --system --group app --home /home/app \
    && mkdir -p /home/app && chown app:app /home/app

# Copy the wheelhouse from the builder stage
COPY --from=builder /wheelhouse /wheelhouse

# Copy the production requirements file
COPY omni_desk_backend/requirements-prod.txt .

# Install Python dependencies from the local wheelhouse
RUN pip install --no-cache-dir --no-index --find-links=/wheelhouse -r requirements-prod.txt

# Copy application source
COPY --chown=app:app omni_desk_backend/ .

# Copy VERSION file so core/version.py can read the deployed version
COPY deployment/docker/VERSION deployment/docker/VERSION

# Ensure the entrypoint script has correct line endings and is executable
RUN sed -i 's/\r$//' ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

# Create staticfiles directory and set permissions
RUN mkdir -p /usr/src/app/staticfiles && chown -R app:app /usr/src/app/staticfiles

# Copy frontend routes.json so sync_routes management command can find it
# (sync_routes 优先从 /usr/src/app/staticfiles/routes.json 读)
COPY --chown=app:app omni_desk_frontend/public/routes.json /usr/src/app/staticfiles/routes.json

# Note: Container runs as root for volume setup, then drops to 'app' user
# for the main process (handled by entrypoint.sh)

# Expose the port Gunicorn will listen on
EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]

# Run Gunicorn WSGI server
CMD ["sh", "-c", "gunicorn omni_desk_backend.wsgi:application --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-3} --timeout 120"]
