# 构建阶段
FROM python:3.9-slim-buster as builder

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip --no-cache-dir \
    && pip install --user -r requirements.txt

# 运行阶段
FROM python:3.9-slim-buster

RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app
COPY --from=builder /root/.local /usr/local
COPY --chown=appuser:appuser . .

ENV PATH="/usr/local/bin:${PATH}"
ENV PYTHONPATH=/app

USER appuser

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "DRFForVue.wsgi"]
