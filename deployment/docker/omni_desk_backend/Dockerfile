# 1. 构建阶段 - 安装依赖
FROM python:3.10-slim-bullseye AS builder

# 设置环境变量，防止生成 .pyc 文件并允许日志直接输出
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PYTHONPATH=/home/app

# 安装编译 psycopg2 所需的系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 仅复制依赖文件并安装，以利用 Docker 的层缓存
COPY omni_desk_backend/requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# 2. 生产阶段 - 运行应用
FROM python:3.10-slim-bullseye

# 创建一个非 root 用户来运行应用
RUN addgroup --system app && adduser --system --group app

# 安装在构建阶段编译好的包
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache /wheels/*

# 将应用代码复制到容器中
WORKDIR /home/app
COPY omni_desk_backend .

# 更改文件所有权为新创建的非 root 用户
RUN chown -R app:app /home/app

# 切换到非 root 用户
USER app

# 暴露 Gunicorn 将要监听的端口
EXPOSE 8000

# 运行 Gunicorn 服务器
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "omni_desk_backend.wsgi:application"]
