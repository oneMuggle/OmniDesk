# Omni Desk 源代码部署指南 (Nginx Unit)

本文档将指导您如何在 Ubuntu 22.04 服务器上，使用 Nginx Unit 通过源代码部署 Omni Desk 应用。Nginx Unit 提供了一个一体化的解决方案，可以同时作为 Web 服务器和应用服务器。

## 1. 先决条件

- 一台安装了 Ubuntu 22.04 的服务器。
- 拥有 sudo 权限的用户。
- Git 已安装。
- 您的项目代码已克隆到服务器的某个位置，例如 `/home/user/omni-desk-project`。

## 2. 安装依赖

我们提供了一个专门为 Nginx Unit 准备的依赖安装脚本。

```bash
# 进入您的项目目录
cd /home/user/omni-desk-project

# 赋予脚本执行权限
chmod +x install_dependencies_unit.sh

# 执行脚本
./install_dependencies_unit.sh
```

## 3. 设置后端

此步骤与 Gunicorn 方案完全相同，它将配置数据库、Python 虚拟环境并准备 Django 应用。

```bash
# 赋予脚本执行权限
chmod +x setup_backend.sh

# 执行脚本
sudo ./setup_backend.sh
```
**重要**: 执行完毕后，请检查并编辑 `/var/www/omni_desk/omni_desk_backend/.env` 文件。

## 4. 设置前端

此步骤也与 Gunicorn 方案完全相同，它将打包 React 应用。

```bash
# 赋予脚本执行权限
chmod +x setup_frontend.sh

# 执行脚本
./setup_frontend.sh
```

## 5. 配置和启动应用服务

### 5.1 配置 Nginx Unit

Nginx Unit 使用一个 JSON 文件进行配置，并通过 REST API 加载。

```bash
# 进入您的项目目录
cd /home/user/omni-desk-project

# 使用 curl 命令将我们的配置上传到 Nginx Unit
# 这会将整个配置应用到 /config/ 路径下
sudo curl -X PUT --data-binary @unit.json --unix-socket /var/run/control.unit.sock http://localhost/config/
```
配置会立即生效，无需重启服务。您可以随时修改 `unit.json` 文件并重新运行上述命令来更新配置。

### 5.2 启动 Celery

我们仍然需要使用 `systemd` 来管理 Celery 服务。

```bash
# 进入您的项目目录
cd /home/user/omni-desk-project

# 将 celery.service 文件复制到 systemd 目录
sudo cp celery.service /etc/systemd/system/

# 重新加载 systemd 管理器配置
sudo systemctl daemon-reload

# 启动并设置开机自启
sudo systemctl start celery
sudo systemctl enable celery
```
使用 `sudo systemctl status celery` 来检查服务状态。

## 6. 创建超级用户 (可选)

此步骤与 Gunicorn 方案相同。

```bash
source /var/www/omni_desk/venv/bin/activate
cd /var/www/omni_desk/omni_desk_backend
python manage.py createsuperuser
deactivate
```

## 7. 访问应用

部署成功后，您可以通过服务器的 IP 地址或域名在浏览器中访问 Omni Desk 应用。Nginx Unit 会处理所有请求。

---
部署完成！