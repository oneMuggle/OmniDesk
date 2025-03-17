# 使用官方Python基础镜像
FROM python:3.9-slim-buster

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 安装系统依赖
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# 复制项目文件
COPY . .

# 收集静态文件（根据Django项目需要）
RUN python manage.py collectstatic --noinput

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "DRFForVue.wsgi"]
