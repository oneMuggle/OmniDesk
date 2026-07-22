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

# Install runtime library for psycopg2, libmagic for python-magic,
# and postgresql-client for pg_dump (needed by manage.py backup_db)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 libmagic1 postgresql-client && \
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

# Fix-11: ollama 传递依赖 anyio 漏在 requirements-prod.txt
# (ollama 在 prod, anyio 只在 dev.txt),file_processing 启动需要
# 同时 httpx==1.0.dev3 (prod 锁定的 pre-release)与 ollama 0.6.2 不兼容
# 强制 uninstall 再装新版(确保覆盖 wheelhouse 中的 1.0.dev3)
# 后续应通过 requirements.in + pip-compile 重新生成修复根因
RUN pip uninstall -y httpx anyio 2>&1 | tail -3 || true
RUN pip install --no-cache-dir --upgrade 'anyio>=4.0' 'httpx>=0.27,<1.0'

# Copy application source
COPY --chown=app:app omni_desk_backend/ .

# Build-time sanity check:确保关键 app 的 .py 文件存在
# 背景:v0.7.0-alpha.2 离线包镜像(v0.6.0/v0.7.0-alpha.2 SHA 相同)build context 残缺,
# paperless_proxy/file_processing 的 .py 文件未进入镜像,导致 Celery 任务注册失败 / 上传 404
# 此处硬断言防止未来构建再次回归
RUN test -f /usr/src/app/paperless_proxy/tasks.py && \
    test -f /usr/src/app/paperless_proxy/views.py && \
    test -f /usr/src/app/paperless_proxy/apps.py && \
    test -f /usr/src/app/file_processing/views.py && \
    test -f /usr/src/app/file_processing/models.py && \
    test -f /usr/src/app/file_processing/urls.py && \
    echo "✓ key apps verified (paperless_proxy + file_processing)" \
    || (echo "✗ BUILD CONTEXT BROKEN: paperless_proxy or file_processing missing .py files" && exit 1)

# Copy VERSION file so core/version.py can read the deployed version
COPY deployment/docker/VERSION deployment/docker/VERSION
# Copy CHANGELOG.md so /api/system/changelog/ can serve real content
COPY deployment/docker/CHANGELOG.md deployment/docker/CHANGELOG.md

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
