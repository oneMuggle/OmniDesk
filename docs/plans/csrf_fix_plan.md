# 修复 Django 管理后台 CSRF 验证失败问题的计划

## 1. 问题描述

在通过 `http://<服务器IP>:8880/admin/` 访问并登录 Django 管理后台时，系统返回 403 Forbidden 错误，提示 "CSRF verification failed. Request aborted."。

## 2. 根本原因分析

经过对项目配置文件（`settings.py`, `docker-compose.yml`, `nginx.conf`）的分析，确定问题根源在于 Django 的 CSRF 防护机制。

当请求通过 Nginx 反向代理到达 Django 应用时，Django 会检查请求的 `Origin` 或 `Referer` 头，以验证请求来源的合法性。在当前部署架构中，这个来源是 `http://<服务器IP>:8880`。

然而，在后端的配置文件 `omni_desk_backend/omni_desk_backend/settings.py` 中，`CSRF_TRUSTED_ORIGINS` 列表未包含此地址，导致 Django 拒绝了该请求。

### 请求流程与问题点

```mermaid
graph TD
    A[用户浏览器] -- 1. 访问 http://<服务器IP>:8880/admin/ --> B{Nginx (frontend:80)};
    B -- 2. 代理请求 --> C{Django (backend:8000)};
    C -- 3. 检查 CSRF 来源 --> D{CSRF_TRUSTED_ORIGINS};
    D -- 4. 'http://<服务器IP>:8880' 不在列表中 --> E[X 验证失败];
    C -- 5. 返回 403 Forbidden --> A;

    subgraph "Django settings.py"
        D
    end
```

## 3. 解决方案

为了解决此问题，需要将 Nginx 代理的地址添加到 Django 的信任来源列表中。

**具体步骤如下：**

1.  **修改配置文件**: 编辑后端的 Django 配置文件 `omni_desk_backend/omni_desk_backend/settings.py`。
2.  **添加信任源**: 在 `CSRF_TRUSTED_ORIGINS` 列表中，增加服务器的访问地址。为了提高配置的灵活性和安全性，建议从环境变量中动态读取此值。
3.  **重新部署**:
    *   保存对 `settings.py` 的修改。
    *   更新 `.env` 文件。
    *   重新构建并启动 Docker 容器：`docker-compose up -d --build`。
4.  **验证**: 清除浏览器缓存后，重新访问 `http://<服务器IP>:8880/admin/`，确认可以正常登录。

## 4. 实施

此计划已获得批准。下一步将切换到 "Code" 模式以执行代码修改。