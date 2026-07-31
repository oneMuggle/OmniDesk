# 冒烟测试覆盖矩阵

> 最后更新:2026-07-27

## 阶段清单

| 阶段 | 目标 | 关键命令 | 失败时定位 |
|------|------|----------|------------|
| 1 | 容器状态 | `docker inspect .State.Status` | 服务未启动 |
| 2 | 前端可访问 | `curl /` | Nginx 502/前端 build 挂 |
| 3 | 后端 API | `/api/health/`, `/api/system/version/` | Django 启动失败 |
| 4 | Redis | `redis-cli ping` | Celery broker 不可用 |
| 5 | Celery worker + 真任务 | `cleanup_paperless_cache.delay()` | task 未注册/broker 断 |
| 6 | 迁移 + CHANGELOG 端点 | `/api/system/{migrations,changelog}/` | 迁移未跑/版本错 |
| 7 | 离线包元数据 | `validate_artifacts.sh` | 离线包损坏 |
| 8.1 | backend media 卷 | write→restart→read | 卷未挂载 |
| 8.2 | postgres data 卷 | INSERT→restart→SELECT | 卷未挂载 |
| 8.3 | 文件上传链路 | `/api/file/upload/` | Celery dispatch 挂 |
| 9 | 业务 happy-path (memos) | POST→GET→DELETE | memos view/serializer 挂 |
| **10** | **业务广度 (5 app GET)** | **events/news/documents/projects/ragflow** | **某 app URL/view 挂** |
| **11** | **PG 备份可恢复性 (shadow DB)** | **`backup_db` → base64 → 容器内落地 → `CREATE DATABASE` → `gunzip \| psql` → 4 核心表 SELECT** | **pg_dump 失败 / restore 报错 / 核心表大量缺失** |

> 阶段 12/13/14/15 已规划但尚未实现(后续 PR 落地),见下方"已知缺口"段。

## Task 8: 升级集成测试与环境变量校验 (2026-07-27)

### 环境变量校验

`smoke_tests.sh` 现在在启动时设置并校验以下环境变量,确保与升级/备份脚本使用一致的运行时路径:

| 变量 | 默认值 | 来源 | 用途 |
|------|--------|------|------|
| `COMPOSE_PROJECT_NAME` | `omnidesk` | `.env.production` 或环境变量 | Docker Compose 项目名,确保卷身份一致 |
| `OMNIDESK_BACKUP_ROOT` | `/opt/omnidesk/backups` | `.env.production` 或环境变量 | 批次备份根目录 |
| `OMNIDESK_RUNTIME_ROOT` | `/opt/omnidesk/runtime` | `.env.production` 或环境变量 | 升级状态/日志持久化目录 |

若变量为空,脚本以非零退出并报错。

### 升级集成测试矩阵

新增 `deployment/docker/tests/test_upgrade_integration.sh`,覆盖 7 个升级/恢复场景:

| 场景 | 目标 | 验证点 |
|------|------|--------|
| S1: upgrade_success | 正常升级成功路径 | dry-run 模式不写状态文件,渠道参数正确传递 |
| S2: migration_failure_restores_source | 迁移失败自动恢复源版本 | 升级失败(非零退出),SAFE_STOPPED 被记录 |
| S3: health_failure_restores_source | 健康检查失败自动恢复源版本 | 升级失败,状态文件记录失败 |
| S4: backup_checksum_failure_blocks_upgrade | 备份校验失败阻断升级 | 升级被阻断,状态文件记录 INIT |
| S5: media_restore_failure_enters_safe_stop | 媒体恢复失败进入 SAFE_STOPPED | rollback 失败,SAFE_STOPPED 可能被记录 |
| S6: bundle_directory_change_reuses_volumes | 不同 bundle 目录复用生产卷 | COMPOSE_PROJECT_NAME 一致,状态文件共享 |
| S7: interrupted_upgrade_enters_recovery | 中断升级进入恢复流程 | 升级被中断,锁残留或 SAFE_STOPPED 记录 |

**测试设计:**
- 使用临时目录模拟 `OMNIDESK_RUNTIME_ROOT`/`OMNIDESK_BACKUP_ROOT`
- 通过 PATH 前置 mock bin 目录替换 docker/compose(不依赖真实 Docker)
- 每个场景独立,trap EXIT 清理临时目录
- 验证 state.json 状态转移/锁目录/备份路径/源版本保留

**运行方式:**
```bash
# 运行全部场景
bash deployment/docker/tests/test_upgrade_integration.sh --all

# 运行单个场景
bash deployment/docker/tests/test_upgrade_integration.sh S1
bash deployment/docker/tests/test_upgrade_integration.sh --scenario=upgrade_success
```

**CI 集成:**
`.github/workflows/deploy-test.yml` 新增 `shell-and-django-tests` job,在专用测试 job 中运行:
- Django 单元测试 (`pytest`)
- Shell 单元测试 (`tests/test_*.sh`)
- 升级集成测试 (`test_upgrade_integration.sh --all`)

生产凭证保护:CI job 使用临时测试凭证,不引用生产 `.env.production`,测试脚本使用 mock 而非真实 Docker。

## app 端点覆盖(GET-only 探针)

| app | 端点 | view | 数据风险 |
|-----|------|------|----------|
| memos | `/api/memos/` | `MemoViewSet` | POST 已含完整 CRUD 链路 |
| events | `/api/events/trials/` | `TrialViewSet` | GET-only,无写入 |
| news | `/api/news-articles/` | `NewsArticleViewSet` | GET-only |
| documents | `/api/documents/books/` | `BookViewSet` | GET-only |
| projects | `/api/projects/` | `ProjectViewSet` | GET-only |
| ragflow-service | `/api/ragflow-service/configs/` | `RagflowConfigViewSet` | GET-only,需网络可达 |

## 已知缺口(后续阶段)

- 阶段 12:外部依赖降级(paperless/llm 502/503 行为,降级路径是 stack trace)
- 阶段 13:HTTP 安全头 + bundle(X-CTO/X-FO/HSTS + bundle.js,Nginx 配置缺头/资源 404)
- 阶段 14:资源基线(CPU/mem/disk 阈值)
- 阶段 15:rollback 闭环(独立脚本 `test_smoke_rollback_loop.sh`)
- API 响应时间基线:需先建立生产 P95(后续 sprint)