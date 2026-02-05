#!/bin/sh

# 收集静态文件
echo "Collecting static files..."
python manage.py collectstatic --noinput

# 执行容器的 CMD
exec "$@"