# Docker 构建修复计划：解决 `omni_desk_worker` 启动失败问题

## 1. 问题背景

在使用 `docker compose up` 启动应用时，`omni_desk_worker` 容器在启动过程中反复崩溃并退出。日志显示以下关键错误：

```
omni_desk_worker    |   File "/usr/local/lib/python3.10/site-packages/kombu/transport/redis.py", line 271, in <module>
omni_desk_worker    |     class PrefixedStrictRedis(GlobalKeyPrefixMixin, redis.Redis):
omni_desk_worker    | AttributeError: 'NoneType' object has no attribute 'Redis'
```

## 2. 问题根源分析

通过对 `docker-compose.yml`、`Dockerfile` 和 `requirements.txt` 文件的逐步排查，确定问题根源在于 Python 依赖库之间的版本不兼容。

- **`docker-compose.yml`**: `omni_desk_worker` 服务与 `omni_desk_backend` 服务共享同一个 Docker 镜像。
- **`Dockerfile`**: 镜像是基于 `python:3.10-slim-bullseye` 构建的，并从 `omni_desk_backend/requirements.txt` 文件中安装依赖。
- **`requirements.txt`**: 文件中指定了 `celery==5.5.3` 和 `kombu==5.5.4`，但**没有固定 `redis` 库的版本**。

由于没有锁定 `redis` 的版本，`pip` 在构建镜像时会安装其最新版本（很可能是 5.x）。`redis` 库从 5.0 版本开始引入了不向后兼容的 API 变更，而项目当前使用的 `celery` 和 `kombu` 版本尚未适配这些变更，导致在初始化 Redis 连接时出现 `AttributeError`。

```mermaid
graph TD
    A[omni_desk_worker 启动失败] --> B{AttributeError: 'NoneType' object has no attribute 'Redis'};
    B --> C{原因: 依赖版本不兼容};
    C --> D[celery==5.5.3 / kombu==5.5.4];
    C --> E[redis-py 版本过高 (>=5.0)];
    E --> F[未在 requirements.txt 中固定版本];
    G[解决方案] --> H{固定 redis-py 版本};
    H --> I[在 requirements.txt 中添加 redis==4.6.0];
    I --> J[重新构建 Docker 镜像];
    J --> K[问题解决];
```

## 3. 修复方案

为了解决此问题，需要将 `redis` 库的版本固定到与当前 Celery 版本兼容的 `4.x` 版本。

**具体步骤:**

1.  在 `omni_desk_backend/requirements.txt` 文件中，添加一行 `redis==4.6.0`。
2.  停止当前运行的 Docker 容器 (`docker compose down`)。
3.  重新构建 Docker 镜像以应用新的依赖关系 (`docker compose build --no-cache`)。
4.  重新启动服务 (`docker compose up`)。

此操作将确保在构建环境中安装一个与 `celery` 和 `kombu` 兼容的 `redis` 客户端版本，从而解决启动错误。