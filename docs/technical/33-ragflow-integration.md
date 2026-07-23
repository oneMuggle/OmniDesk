# 33. RAGFlow 集成

> **状态**：✅ 已实现（v0.6.0-alpha.2，PR #49 — `feat/ragflow`）
> **代码位置**：`omni_desk_backend/ragflow_service/` + `omni_desk_backend/conftest.py`（fixture）
> **部署位置**：`deployment/docker/docker-compose.prod.yml` 含 ragflow 服务

## 1. 设计动机

`ragflow_service` 与 `smart_assistant` 两 app 已有代码骨架，但实际落地时存在：
- 无 ragflow 容器（部署缺失）
- 用 OpenAI 兼容路径 `/v1/chat/completions`，非 RAGFlow 原生 API
- 无 Dataset / Chat Assistant 管理 UI
- 无健康检查
- 前端聊天用 mock 数据

本次接入修复全部上述问题。

## 2. RAGFlow API 路径

| 功能 | 方法 | 路径 |
|---|---|---|
| 认证 | Header | `Authorization: Bearer <API_KEY>` |
| 列出 Dataset | GET | `/api/v1/datasets` |
| 创建 Dataset | POST | `/api/v1/datasets` |
| 删除 Dataset | DELETE | `/api/v1/datasets/{id}` |
| 列出文档 | GET | `/api/v1/datasets/{dataset_id}/documents` |
| 上传文档 | POST | `/api/v1/datasets/{dataset_id}/documents` |
| 删除文档 | DELETE | `/api/v1/datasets/{dataset_id}/documents` |
| 触发解析 | POST | `/api/v1/datasets/{dataset_id}/chunks` |
| 检索 chunks | POST | `/api/v1/retrieval` |
| 创建 Chat Assistant | POST | `/api/v1/chats` |
| Chat 对话 | POST | `/api/v1/chats/{chat_id}/completions` |
| 健康检查 | GET | `/api/v1/health` |

**Chat vs Retrieval 区别**：
- **Chat API** — 内置 RAG + LLM 总结，直接返回最终答案（用户提问场景）
- **Retrieval API** — 仅返回原始 chunks，由调用方自行处理（智能助手 `RAGTool` 编排场景）

## 3. 服务端模块（`ragflow_service/`）

| 文件 | 职责 |
|---|---|
| `client.py` | `RagflowClient`：完整 RAGFlow API 客户端（同步阻塞 HTTP） |
| `models.py` | `RagflowConfig` (Django 模型) + 内部 ORM 模型 |
| `serializers.py` | DRF 序列化器 |
| `views.py` | `RagflowConfigViewSet` + 管理端点 |
| `urls.py` | 路由（包含 `/configs/` 简版） |
| `tests.py` + `tests/` | 单元 + 集成测试 |

`RagflowClient` 公开方法（节选）：

```python
list_datasets(page, page_size) -> list[dict]
create_dataset(name, **kwargs) -> dict
delete_dataset(dataset_id) -> bool
list_documents(dataset_id, page, page_size)
upload_document(dataset_id, file_name, file_content)
parse_documents(dataset_id, document_ids) -> bool   # 触发解析
retrieval(dataset_ids, question, top_k, ...)        # 仅 chunks
list_chats(page, page_size)
create_chat(name, dataset_ids, system_prompt, ...)
chat_completion(chat_id, messages, stream=False)    # RAG + LLM 答案
health_check() -> dict
```

## 4. 前端集成

| 路径 | 模块 | 说明 |
|---|---|---|
| `/knowledge/ragflow` | `RagflowChatPage` | 管理员配置 + 测试聊天界面，**调用 Chat API** |
| 智能助手 RAG 工具 | `RAGTool` | 单 Agent 管道中检索，**调用 Retrieval API** 拿 chunks，传给 LLM 编排器 |

**消除 mock**：`omni_desk_frontend/src/shared/mocks/` 下 `ragflowDemoMocks.js` 已退出生产路径，仅开发模式 fallback。

## 5. 部署

`docker-compose.prod.yml` 新增：

```yaml
ragflow:
  image: infiniflow/ragflow:latest
  container_name: omni-desk-ragflow
  ports: ["9380:9380"]
  volumes:
    - ragflow_data:/ragflow/data
  environment:
    - RAGFLOW_API_KEY=${RAGFLOW_API_KEY:-change_me}
```

健康检查：

```bash
curl http://<ragflow-host>:9380/api/v1/health
```

部署后管理员可在 `/api/smart-assistant/ragflow/configs/` 创建 `RagflowConfig` 记录，填入 `api_endpoint` + `api_key`。

## 6. 关键设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| Chat vs Retrieval 路由 | Chat 页 → Chat API；RAGTool → Retrieval | Chat 给最终用户；Retrieval 给 LLM 编排更灵活 |
| Dataset 多路管理 | 后台 ORM + RAGFlow 双向同步 | 管理员可拖拽管理而不必登 ragflow UI |
| 健康检查 | 启动 + 定期 | 配置错误早暴露 |
| 同步 vs 异步客户端 | 同步（`requests`） + Celery 异步任务 | 客户端简洁，调用方决定是否上 Celery |
| 前端 mock | 仅开发模式保留 | 生产路径必须打通 |

## 7. 关联参考

- 关联计划：`docs/plans/2026-07-06_ragflow-integration.md`（**已归档，删档**）
- 上层架构：`docs/technical/16-smart-assistant.md` + `18-external-integration.md`
- 前端 Demo：`omni_desk_frontend/src/shared/pages/RagflowChatPage.jsx`

---

> 📅 最近更新：2026-07-16 — 文档归档，从 docs/plans/2026-07-06_ragflow-integration.md 提取。
