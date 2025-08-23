# Omni Desk Docker 部署指南

本文档将指导您如何在 Ubuntu 22.04 系统上使用 Docker 和 Docker Compose 部署 Omni Desk 应用。

## 1. 先决条件

在开始之前，请确保您的服务器满足以下条件：
- 一台安装了 Ubuntu 22.04 的服务器。
- 拥有 sudo 权限的用户。
- Git 已安装 (`sudo apt update && sudo apt install git -y`)。

## 2. 安装 Docker 和 Docker Compose

首先，我们需要在服务器上安装 Docker 引擎和 Docker Compose。

### 2.1 安装 Docker

```bash
# 更新软件包列表
sudo apt-get update

# 安装必要的依赖
sudo apt-get install -y ca-certificates curl gnupg

# 添加 Docker 官方 GPG 密钥
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# 设置 Docker 仓库
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 再次更新软件包列表
sudo apt-get update

# 安装 Docker 引擎, CLI, 和 containerd
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### 2.2 将当前用户添加到 Docker 组

为了避免每次使用 `docker` 命令时都需要输入 `sudo`，可以将当前用户添加到 `docker` 组。

```bash
sudo usermod -aG docker $USER
```
**注意**: 您需要重新登录服务器或开启一个新的 shell 会话，这个改动才会生效。

## 3. 获取源代码

从您的代码仓库克隆项目。

```bash
git clone <您的项目仓库地址>
cd <项目目录>
```

## 4. 配置环境变量

我们使用 `.env` 文件来管理环境变量。您可以基于我们提供的模板创建一个生产环境的配置。

```bash
cp .env .env.production
```

然后，编辑 `.env.production` 文件，**务必修改以下配置**：

- `SECRET_KEY`: 生成一个新的、安全的 Django 密钥。
- `DEBUG`: 在生产环境中，应设置为 `False`。
- `ALLOWED_HOSTS`: 添加您的服务器域名或 IP 地址。
- `POSTGRES_PASSWORD`: 设置一个强密码。

## 5. 部署应用

我们提供了一个便捷的部署脚本 `deploy_docker.sh` 来管理应用的生命周期。

### 5.1 首次启动

要构建镜像并启动所有服务，请运行：

```bash
# 确保脚本有执行权限
chmod +x deploy_docker.sh

# 启动服务
./deploy_docker.sh up
```
这个命令会以后台模式启动所有在 `docker-compose.yml` 中定义的服务。

### 5.2 执行数据库迁移

在首次启动应用后，您需要执行数据库迁移来创建所有的数据表。

```bash
./deploy_docker.sh migrate
```

### 5.3 创建超级用户 (可选)

如果您需要访问 Django admin 后台，可以创建一个超级用户。

```bash
docker-compose exec backend python manage.py createsuperuser
```

## 6. 管理应用

`deploy_docker.sh` 脚本提供了一些有用的命令来管理您的应用：

- **停止服务**: `./deploy_docker.sh down`
- **查看日志**: `./deploy_docker.sh logs` 或 `./deploy_docker.sh logs backend`
- **重建镜像**: `./deploy_docker.sh build`

## 7. 访问应用

部署成功后，您可以通过服务器的 IP 地址或域名在浏览器中访问 Omni Desk 应用。
- **前端应用**: `http://<您的服务器IP或域名>`
- **后端 API**: `http://<您的服务器IP或域名>/api/`

---
部署完成！