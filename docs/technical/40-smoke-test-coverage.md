# 冒烟测试覆盖矩阵

> 最后更新:2026-07-21

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