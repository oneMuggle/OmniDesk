# 构建阶段
FROM python:3.9-slim-buster AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc python3-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --upgrade pip --no-cache-dir \
    && pip install --target /usr/local/lib/python3.9/site-packages -r requirements.txt \
    && pip install waitress whitenoise

# 运行阶段
FROM python:3.9-slim-buster

RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app
RUN mkdir -p /var/lib/django && chown appuser:appuser /var/lib/django
COPY --chown=appuser:appuser init_superuser.py .
COPY --chown=appuser:appuser . .
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages

# 收集静态文件
RUN mkdir -p /usr/share/nginx/html/static && chown appuser:appuser /usr/share/nginx/html/static
RUN python manage.py collectstatic --noinput --clear --settings=DRFForVue.settings

# 创建数据目录并设置权限
RUN mkdir -p /data && \
    chown appuser:appuser /data && \
    chmod 755 /data

ENV PATH="/usr/local/bin:/usr/local/lib/python3.9/site-packages/bin:${PATH}"
ENV PYTHONPATH=/app:/usr/local/lib/python3.9/site-packages:/home/appuser/.local/lib/python3.9/site-packages

# 安装运行时依赖
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 postgresql-client \
    && rm -rf /var/lib/apt/lists/*

USER appuser

EXPOSE 8000

# 使用已存在的appuser用户
USER appuser

CMD ["waitress-serve", "--port=8000", "DRFForVue.wsgi:application"]
