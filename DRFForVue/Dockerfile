# 构建阶段
FROM python:3.9-slim-buster AS builder

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/root/.local/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc python3-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip --user --no-cache-dir \
    && pip install -r requirements.txt --user

# 运行阶段
FROM python:3.9-slim-buster

RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app
COPY --chown=appuser:appuser . .
COPY --from=builder /root/.local /usr/local

ENV PATH="/usr/local/bin:/root/.local/bin:${PATH}"
ENV PYTHONPATH=/app

# 安装运行时依赖
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

USER appuser

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
