# Nginx 作为中央反向代理的架构设计

本文档旨在为使用 Nginx 作为多个项目的中央反向代理提供一个清晰的架构设计和配置指南。

## 1. Nginx 反向代理核心概念

**反向代理**（Reverse Proxy）是位于一个或多个 Web 服务器前端的代理服务器。与客户端直接访问 Web 服务器不同，客户端的请求会先发送到反向代理服务器，然后由反向代理服务器将请求转发到后端的内部服务器。

使用 Nginx 作为反向代理的核心优势包括：

*   **负载均衡**：将传入的流量分发到多个后端服务器，以提高可伸缩性和可靠性。
*   **SSL/TLS 终止**：在 Nginx 层集中处理 HTTPS 请求，解密后将未加密的请求转发到内部服务，从而简化后端服务的配置。
*   **静态内容服务**：直接从 Nginx 提供静态文件（如 HTML, CSS, JavaScript, 图片），减轻后端应用的负载。
*   **安全性增强**：隐藏后端服务器的 IP 地址和特性，提供一层额外的安全保护，抵御常见的 Web 攻击。
*   **统一访问入口**：通过单个域名或 IP 地址访问多个不同的应用程序或服务，每个服务可以通过子域名或路径进行区分。

## 2. 推荐的 Nginx 配置结构

为了保持配置的整洁、模块化和易于管理，我们推荐采用以下文件结构：

```
/etc/nginx/
├── nginx.conf          # 主配置文件
├── sites-available/    # 存放所有项目的配置文件
│   ├── project1.example.com.conf
│   └── project2.example.com.conf
└── sites-enabled/      # 存放已启用的项目的配置文件的符号链接
    ├── project1.example.com.conf -> /etc/nginx/sites-available/project1.example.com.conf
    └── project2.example.com.conf -> /etc/nginx/sites-available/project2.example.com.conf
```

### 主配置文件 (`nginx.conf`)

主配置文件 `nginx.conf` 应保持简洁，主要用于定义全局设置，并通过 `include` 指令加载其他配置文件。

一个典型的 `nginx.conf` 的 `http` 块可能如下所示：

```nginx
http {
    # ... 全局 HTTP 设置 (例如: mime types, log formats, timeouts)

    # 包含所有已启用的站点的配置
    include /etc/nginx/sites-enabled/*.conf;
}
```

这种方法的优点是：
*   **模块化**：每个项目的配置都独立存在于自己的文件中。
*   **易于管理**：要启用或禁用一个项目，只需在 `sites-enabled` 目录中创建或删除其配置文件的符号链接，然后重新加载 Nginx 即可，无需修改主配置文件。

## 3. 多项目配置示例

以下是如何为两个不同的项目（`project1.example.com` 和 `project2.example.com`）配置 `server` 块的示例。

### 项目一：`project1.example.com`

**文件路径**: `/etc/nginx/sites-available/project1.example.com.conf`

此配置监听 `project1.example.com` 的 80 端口，并将所有请求反向代理到本地的 `8001` 端口。

```nginx
server {
    listen 80;
    server_name project1.example.com;

    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 项目二：`project2.example.com`

**文件路径**: `/etc/nginx/sites-available/project2.example.com.conf`

此配置监听 `project2.example.com` 的 80 端口，并将所有请求反向代理到本地的 `8002` 端口。

```nginx
server {
    listen 80;
    server_name project2.example.com;

    location / {
        proxy_pass http://localhost:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 启用项目

要启用这两个项目，您需要创建从 `sites-available` 到 `sites-enabled` 的符号链接，然后测试并重新加载 Nginx 配置：

```bash
# 创建符号链接
sudo ln -s /etc/nginx/sites-available/project1.example.com.conf /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/project2.example.com.conf /etc/nginx/sites-enabled/

# 测试 Nginx 配置是否有语法错误
sudo nginx -t

# 如果测试成功，重新加载 Nginx 以应用更改
sudo systemctl reload nginx
```

通过这种方式，您可以轻松地扩展 Nginx 以支持任意数量的项目，同时保持配置文件的清晰和可维护性。