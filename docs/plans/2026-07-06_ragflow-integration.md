# OmniDesk 真正接入 RAGFlow 方案

> **状态**: 待审批
> **创建日期**: 2026-07-06
> **优先级**: 高

---

## 1. 背景与目标

### 1.1 当前状态

OmniDesk 已有 `ragflow_service` 和 `smart_assistant` 两个 Django app，代码骨架基本完整，但存在以下问题：

| 问题 | 现状 | 影响 |
|------|------|------|
| **RAGFlow 服务未部署** | docker-compose 中无 ragflow 容器 | 无法实际调用 |
| **API 路径错误** | `views.py` 用 `/v1/chat/completions`（OpenAI 兼容格式），不是 ragflow 原生 API | 查询必然失败 |
| **Dataset 管理缺失** | 无 UI/API 在 ragflow 服务器上创建/列出 dataset | 管理员无法管理知识库 |
| **Chat API 未实现** | 只有 retrieval API（取 chunks），没有 chat API（直接返回答案） | 前端聊天页只能用 retrieval + 自行拼装 |
| **连接健康检查缺失** | 无法验证 ragflow 服务是否可达、API Key 是否有效 | 部署后无法确认配置正确 |
| **前端 Demo 模式** | 前端 `demoMocks.js` 返回假数据，生产环境未打通 | 用户体验不到真实功能 |
| **多 Dataset 路由** | `KnowledgeDataset` 模型已定义，但无管理 UI | 无法利用多知识库智能路由 |

### 1.2 目标

让 OmniDesk 能够：
1. **部署时自带 RAGFlow 服务**（docker-compose 一键启动）
2. **管理员可在 OmniDesk 内管理 RAGFlow 的 Dataset 和 Chat Assistant**
3. **前端聊天页面真正调用 RAGFlow 获取答案**（非 mock）
4. **智能助手的 RAGTool 能正确检索知识库**
5. **部署后可通过健康检查确认 RAGFlow 可用**

---

## 2. RAGFlow API 梳理

RAGFlow 提供以下核心 API（基于官方文档 https://ragflow.io/docs/dev/）：

### 2.1 认证方式
```
Authorization: Bearer <API_KEY>
```

### 2.2 核心 API 端点

| 功能 | 方法 | 路径 | 说明 |
|------|------|------|------|
| **创建 Dataset** | POST | `/api/v1/datasets` | 创建知识库数据集 |
| **列出 Dataset** | GET | `/api/v1/datasets` | 列出所有数据集 |
| **删除 Dataset** | DELETE | `/api/v1/datasets/{id}` | 删除数据集 |
| **上传文档** | POST | `/api/v1/datasets/{dataset_id}/documents` | 上传文件到数据集 |
| **列出文档** | GET | `/api/v1/datasets/{dataset_id}/documents` | 列出数据集内文档 |
| **删除文档** | DELETE | `/api/v1/datasets/{dataset_id}/documents` | 删除文档 |
| **触发解析** | POST | `/api/v1/datasets/{dataset_id}/chunks` | 解析 dataset 下的文档 |
| **检索 chunks** | POST | `/api/v1/retrieval` | 从指定 dataset 检索文本块 |
| **创建 Chat Assistant** | POST | `/api/v1/chats` | 创建聊天助手（绑定 dataset） |
| **Chat 对话** | POST | `/api/v1/chats/{chat_id}/completions` | 与 chat assistant 对话 |
| **列出 Chat** | GET | `/api/v1/chats` | 列出所有 chat assistant |

### 2.3 Chat vs Retrieval 的区别

- **Retrieval API**：只返回检索到的 chunks（文本块），不做 LLM 总结。适合"拿到原始资料后自行处理"的场景。
- **Chat API**：基于 dataset 检索 + LLM 总结，直接返回答案。适合"用户提问 → 得到答案"的场景。

**建议**：
- `RagflowChatPage`（前端聊天页）→ 使用 **Chat API**
- `RAGTool`（智能助手知识库查询）→ 使用 **Retrieval API**（因为需要拿到 chunks 作为上下文传给 LLM 编排器）

---

## 3. 实施方案

### Phase 1: RAGFlow 服务部署（基础设施）

**目标**：让 RAGFlow 能随 OmniDesk 一起部署。

#### 1.1 新增 docker-compose 服务

在 `deployment/docker/docker-compose.prod.yml` 中添加 ragflow 服务：

```yaml
  ragflow:
    image: infiniflow/ragflow:v0.16.0  # 固定版本，不用 latest
    container_name: omnidesk-ragflow
    restart: unless-stopped
    environment:
      - MYSQL_PASSWORD=ragflow123
      - MYSQL_HOST=ragflow-mysql
      - MYSQL_PORT=3306
    volumes:
      - ragflow_data:/ragflow/data
    ports:
      - "9380:80"  # RAGFlow Web UI
    depends_on:
      - ragflow-mysql
    networks:
      - omnidesk-net

  ragflow-mysql:
    image: mysql:8.0
    container_name: omnidesk-ragflow-mysql
    restart: unless-stopped
    environment:
      - MYSQL_ROOT_PASSWORD=ragflow123
      - MYSQL_DATABASE=ragflow
      - MYSQL_USER=ragflow
      - MYSQL_PASSWORD=ragflow123
    volumes:
      - ragflow_mysql_data:/var/lib/mysql
    networks:
      - omnidesk-net

volumes:
  ragflow_data:
  ragflow_mysql_data:
```

#### 1.2 环境变量

在 `.env` 文件中添加：
```bash
RAGFLOW_API_ENDPOINT=http://ragflow:80
RAGFLOW_API_KEY=  # 部署后在 RAGFlow Web UI 中生成
SMART_ASSISTANT_DATASET_ID=  # 部署后在 RAGFlow 中创建 dataset 后填入
```

#### 1.3 Nginx 反向代理（可选）

如果需要通过 OmniDesk 域名访问 RAGFlow Web UI：
```nginx
location /ragflow/ {
    proxy_pass http://ragflow:80/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

**交付物**：
- [ ] 修改 `docker-compose.prod.yml`
- [ ] 修改 `deployment/docker/.env.example`
- [ ] 更新 `docs/technical/` 部署文档

---

### Phase 2: 后端 API 修正与增强

**目标**：修正错误的 API 路径，补全缺失的 API。

#### 2.1 修正 `ragflow_service/views.py` 的 query action

当前代码 POST 到 `/v1/chat/completions`（OpenAI 兼容路径），但 RAGFlow 原生 API 路径是 `/api/v1/chats/{chat_id}/completions`。

**方案**：
- `RagflowConfig` 模型新增 `chat_id` 字段（对应在 RAGFlow 中创建的 chat assistant ID）
- `query` action 改为调用 `/api/v1/chats/{chat_id}/completions`

```python
# ragflow_service/models.py 新增字段
chat_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="Chat Assistant ID")

# ragflow_service/views.py 修正 query action
def query(self, request, pk=None):
    config = self.get_object()
    if not config.chat_id:
        return Response({"detail": "未配置 Chat Assistant ID"}, status=400)
    
    url = f"{config.api_endpoint}/api/v1/chats/{config.chat_id}/completions"
    # ... 调用 RAGFlow Chat API
```

#### 2.2 新增 Dataset 管理 API

新增 `RagflowDatasetViewSet`，代理 RAGFlow 的 dataset 管理 API：

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/ragflow-service/datasets/` | GET | 列出 RAGFlow 上所有 dataset |
| `/api/ragflow-service/datasets/` | POST | 在 RAGFlow 上创建新 dataset |
| `/api/ragflow-service/datasets/{id}/` | DELETE | 删除 RAGFlow 上的 dataset |
| `/api/ragflow-service/datasets/{id}/documents/` | GET | 列出 dataset 内的文档 |
| `/api/ragflow-service/datasets/{id}/documents/` | POST | 上传文档到 dataset |

#### 2.3 新增连接测试 API

```python
# ragflow_service/views.py
@action(detail=True, methods=["get"])
def health_check(self, request, pk=None):
    """测试 RAGFlow 连接是否正常"""
    config = self.get_object()
    try:
        resp = requests.get(
            f"{config.api_endpoint}/api/v1/datasets",
            headers={"Authorization": f"Bearer {config.api_key}"},
            timeout=5,
        )
        if resp.status_code == 200:
            return Response({"status": "ok", "message": "连接成功"})
        else:
            return Response({"status": "error", "message": f"HTTP {resp.status_code}"}, status=500)
    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=500)
```

#### 2.4 新增 RAGFlow Client 封装

创建 `ragflow_service/client.py`，统一封装 RAGFlow API 调用：

```python
class RagflowClient:
    def __init__(self, api_endpoint: str, api_key: str):
        self.base_url = api_endpoint.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    
    def list_datasets(self) -> list: ...
    def create_dataset(self, name: str, **kwargs) -> dict: ...
    def upload_document(self, dataset_id: str, file) -> dict: ...
    def parse_documents(self, dataset_id: str, document_ids: list) -> dict: ...
    def retrieval(self, dataset_ids: list, query: str, top_k: int = 5) -> list: ...
    def chat_completion(self, chat_id: str, question: str, **kwargs) -> dict: ...
    def health_check(self) -> bool: ...
```

**交付物**：
- [ ] 修正 `ragflow_service/models.py`（新增 chat_id 字段）
- [ ] 创建 `ragflow_service/client.py`
- [ ] 修正 `ragflow_service/views.py`（query action + health_check）
- [ ] 新增 `ragflow_service/dataset_views.py`（Dataset 管理 API）
- [ ] 更新 `ragflow_service/urls.py`
- [ ] 补充测试

---

### Phase 3: 前端管理界面

**目标**：管理员可在 OmniDesk 内配置 RAGFlow 连接、管理 Dataset、创建 Chat Assistant。

#### 3.1 Ragflow 配置管理页面

新建 `RagflowSettingsPage.jsx`，功能：
- 列出所有 RagflowConfig（已有 API）
- 新增/编辑配置（api_endpoint, api_key, chat_id）
- **测试连接**按钮（调用 health_check API）
- 显示连接状态（成功/失败 + 错误信息）

#### 3.2 Dataset 管理页面

新建 `KnowledgeDatasetPage.jsx`，功能：
- 列出 OmniDesk 中注册的 KnowledgeDataset
- 从 RAGFlow 拉取 dataset 列表，选择关联
- 上传文档到指定 dataset
- 查看文档解析状态
- 删除文档/dataset

#### 3.3 修正 RagflowChatPage

当前问题：
- `response.data.answer` 字段不对（RAGFlow Chat API 返回格式是 `{choices: [{message: {content: "..."}}]}`，类似 OpenAI）
- 需要处理流式响应（RAGFlow Chat API 支持 SSE）

**修正**：
- 修正响应解析逻辑
- 可选：支持流式显示（SSE）

**交付物**：
- [ ] 新建 `RagflowSettingsPage.jsx` + CSS
- [ ] 新建 `KnowledgeDatasetPage.jsx` + CSS
- [ ] 修正 `RagflowChatPage.jsx` 响应解析
- [ ] 注册路由和侧边栏入口
- [ ] 更新 `demoInterceptor.js` 支持新 API

---

### Phase 4: 智能助手 RAGTool 修正

**目标**：让 `RAGTool` 能正确调用 RAGFlow Retrieval API。

#### 4.1 修正 `rag_router.py`

当前 `search_dataset` 调用 `/api/v1/retrieval`，请求体是 `{"dataset_id": ..., "query": ..., "top_k": ...}`。

需要确认 RAGFlow Retrieval API 的实际请求格式：
```json
POST /api/v1/retrieval
{
  "question": "xxx",
  "dataset_ids": ["dataset_id_1", "dataset_id_2"],
  "top_k": 5,
  "similarity_threshold": 0.2,
  "vector_similarity_weight": 0.3
}
```

**修正点**：
- `dataset_id` → `dataset_ids`（数组）
- `query` → `question`
- 支持 `similarity_threshold` 和 `vector_similarity_weight` 配置

#### 4.2 修正 `tasks.py` 文档上传

当前上传和解析 API 路径基本正确，但需要：
- 使用 `RagflowClient` 统一封装
- 增加解析状态轮询（RAGFlow 解析是异步的，需要轮询文档状态直到完成）

**交付物**：
- [ ] 修正 `smart_assistant/agent/rag_router.py`
- [ ] 修正 `smart_assistant/tasks.py`（使用 RagflowClient）
- [ ] 补充测试

---

### Phase 5: 部署验证与文档

#### 5.1 端到端测试清单

1. 启动 docker-compose → ragflow 容器正常运行
2. 访问 RAGFlow Web UI（:9380）→ 创建管理员账号
3. 在 RAGFlow 中创建 dataset → 上传测试文档 → 等待解析完成
4. 在 OmniDesk 中配置 RagflowConfig → 测试连接成功
5. 使用 RagflowChatPage 提问 → 得到基于文档的回答
6. 使用智能助手提问 → RAGTool 正确检索知识库
7. 上传文档到知识库 → Celery 异步解析 → 状态变为 completed

#### 5.2 文档更新

- `docs/technical/` 新增 RAGFlow 部署与配置文档
- `docs/user-manual/` 更新知识库管理操作手册
- `deployment/docker/README.md` 补充 RAGFlow 部署说明

**交付物**：
- [ ] 端到端测试通过
- [ ] 文档更新完成

---

## 4. 实施顺序与依赖

```
Phase 1 (部署)
    ↓
Phase 2 (后端 API) ←── Phase 4 (RAGTool 修正可并行)
    ↓
Phase 3 (前端 UI)
    ↓
Phase 5 (验证与文档)
```

**预计工作量**：
- Phase 1: 0.5 天
- Phase 2: 1 天
- Phase 3: 1 天
- Phase 4: 0.5 天
- Phase 5: 0.5 天
- **总计**: 3.5 天

---

## 5. 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| RAGFlow 版本 API 变化 | API 路径/格式不兼容 | 固定 RAGFlow 版本（v0.16.0），升级时先查 changelog |
| RAGFlow 依赖 MySQL | 增加部署复杂度 | docker-compose 自带 MySQL，无需额外配置 |
| RAGFlow 资源消耗大 | 影响 OmniDesk 性能 | RAGFlow 独立容器，可限制资源（CPU/内存） |
| API Key 泄露 | 安全风险 | api_key 字段使用 `EncryptedCharField`（参考 personnel app） |
| 文档解析耗时 | 用户上传后等待时间长 | Celery 异步处理 + 前端状态轮询 |

---

## 6. 决策点（需用户确认）

### 6.1 RAGFlow 版本

建议使用 **v0.16.0**（当前稳定版）。是否需要用最新版本？

### 6.2 API Key 加密存储

`RagflowConfig.api_key` 当前是普通 `CharField`。是否改用 `EncryptedCharField`（参考 `personnel.models.EncryptedCharField`）？

### 6.3 Chat API vs Retrieval API

- **RagflowChatPage**：使用 Chat API（直接返回答案）还是 Retrieval API（返回 chunks + 自行调用 LLM）？
  - 推荐：Chat API（简单，RAGFlow 内置 LLM 总结）
- **RAGTool（智能助手）**：使用 Retrieval API（拿到 chunks 传给编排器）还是 Chat API？
  - 推荐：Retrieval API（需要 chunks 做来源引用）

### 6.4 RAGFlow Web UI 访问方式

- **方案 A**：通过 Nginx 反向代理，在 OmniDesk 域名下访问（`https://omnidesk.example.com/ragflow/`）
- **方案 B**：直接暴露端口（`http://server-ip:9380`），仅管理员可访问
- 推荐方案 B（简单，RAGFlow Web UI 有自己的登录认证）

### 6.5 实施范围

是否全部 5 个 Phase 都做？还是先做 Phase 1-2（部署 + 后端 API），前端后续再做？

---

## 7. 参考资源

- RAGFlow 官方文档：https://ragflow.io/docs/dev/
- RAGFlow API 参考：https://ragflow.io/docs/dev/http_api_reference
- RAGFlow Docker 部署：https://ragflow.io/docs/dev/launch_ragflow_from_docker
- RAGFlow GitHub：https://github.com/infiniflow/ragflow
