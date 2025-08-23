# Omni Desk 源代码部署指南 (Gunicorn + Nginx)

本文档将指导您如何在 Ubuntu 22.04 服务器上，使用 Gunicorn 和 Nginx 通过源代码部署 Omni Desk 应用。

## 1. 先决条件

- 一台安装了 Ubuntu 22.04 的服务器。
- 拥有 sudo 权限的用户。
- Git 已安装。
- 您的项目代码已克隆到服务器的某个位置，例如 `/home/user/omni-desk-project`。

## 2. 安装依赖

我们提供了一个脚本来自动化安装所有必需的系统和服务。

```bash
# 进入您的项目目录
cd /home/user/omni-desk-project

# 赋予脚本执行权限
chmod +x install_dependencies.sh

# 执行脚本
./install_dependencies.sh
```

## 3. 设置后端

接下来，我们将配置 PostgreSQL 数据库、Python 虚拟环境，并准备 Django 应用。

```bash
# 赋予脚本执行权限
chmod +x setup_backend.sh

# 执行脚本
# 注意：脚本会创建数据库和用户，并生成一个 .env 文件。
# 请根据脚本内的提示修改密码和域名。
sudo ./setup_backend.sh
```
**重要**: 执行完毕后，请检查并编辑 `/var/www/omni_desk/omni_desk_backend/.env` 文件，确保 `ALLOWED_HOSTS` 和 `SECRET_KEY` 等配置正确。

## 4. 设置前端

此步骤将安装前端依赖，并打包 React 应用。

```bash
# 赋予脚本执行权限
chmod +x setup_frontend.sh

# 执行脚本
./setup_frontend.sh
```

## 5. 配置和启动应用服务

### 5.1 配置 Nginx

首先，将我们提供的 Nginx 配置文件链接到 Nginx 的 `sites-enabled` 目录。

```bash
# 进入您的项目目录
cd /home/user/omni-desk-project

# 将 nginx_gunicorn.conf 复制到 Nginx 配置目录
sudo cp nginx_gunicorn.conf /etc/nginx/sites-available/omni_desk

# 创建软链接以启用该站点
sudo ln -s /etc/nginx/sites-available/omni_desk /etc/nginx/sites-enabled/

# 测试 Nginx 配置是否有语法错误
sudo nginx -t

# 如果没有错误，重启 Nginx 使配置生效
sudo systemctl restart nginx
```
**注意**: 请记得修改 `/etc/nginx/sites-available/omni_desk` 文件中的 `server_name` 为您的实际域名。

### 5.2 启动 Gunicorn 和 Celery

我们将使用 `systemd` 来管理 Gunicorn 和 Celery 服务。

```bash
# 进入您的项目目录
cd /home/user/omni-desk-project

# 将 .service 文件复制到 systemd 目录
sudo cp gunicorn.service /etc/systemd/system/
sudo cp celery.service /etc/systemd/system/

# 重新加载 systemd 管理器配置
sudo systemctl daemon-reload

# 启动并设置开机自启
sudo systemctl start gunicorn
sudo systemctl enable gunicorn
sudo systemctl start celery
sudo systemctl enable celery
```

您可以使用以下命令检查服务状态：
`sudo systemctl status gunicorn`
`sudo systemctl status celery`

## 6. 创建超级用户 (可选)

如果您需要访问 Django admin，请激活虚拟环境并创建超级用户。

```bash
source /var/www/omni_desk/venv/bin/activate
cd /var/www/omni_desk/omni_desk_backend
python manage.py createsuperuser
deactivate
```

## 7. 访问应用

部署成功后，您可以通过服务器的 IP 地址或域名在浏览器中访问 Omni Desk 应用。

---
部署完成！