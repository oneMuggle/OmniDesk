# 离线部署

## 1. 概述

适用于无外网访问的内部网络（air-gapped）环境。所有镜像通过 `.tar` 文件离线传输。

## 2. 架构

```
  Port 80 ──► frontend(:80) → backend(内部)
              db(:5432)  redis(:6379)  worker
```

数据卷: postgres_data, redis_data, static_volume, media_volume, backup_volume

## 3. 部署步骤

### Phase 1: 构建镜像（有外网）
```bash
cd deployment/docker && bash build_and_export.sh
```

产物在 `deployment/docker/dist/`。

### Phase 2: 验证
```bash
bash validate_artifacts.sh
```

### Phase 3: 传输
U 盘/SCP/完整打包。

### Phase 4: 离线部署
```bash
bash deploy_offline.sh start
```

### Phase 5: 冒烟测试
健康检查(200)、未授权(401)、首页(200)、登录(200)、版本API(200)。

## 4. 升级与回滚

```bash
bash deploy_offline.sh upgrade
bash deploy_offline.sh rollback
```

## 5. 关键环境变量

| 变量 | 说明 |
|------|------|
| `POSTGRES_DB/USER/PASSWORD` | 数据库配置 |
| `REDIS_PASSWORD` | Redis 密码 |
| `DJANGO_ENV=production` | 必须为 production |
| `DEBUG=False` | 生产必须 False |

详细指南见 [部署指南](02-deployment-guide.md)。
