# 使用官方 Python 镜像作为基础
FROM python:3.9-slim-buster AS builder

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

# 复制 requirements 文件并安装依赖
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# 第二阶段构建，减少镜像体积
FROM python:3.9-slim-buster
WORKDIR /app

# 从构建阶段复制已安装的包
COPY --from=builder /root/.local /root/.local
COPY . .

# 确保 Python 可以找到用户安装的包
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=DRFForVue.settings

# 安装运行时依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev python3-dev && \
    rm -rf /var/lib/apt/lists/*

# 合并数据库迁移和静态文件收集
RUN python manage.py migrate && \
    python manage.py collectstatic --noinput

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "DRFForVue.wsgi:application"]
