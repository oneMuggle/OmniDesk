# 38. LLM 服务 (llm_service app)

> 适用版本:OmniDesk v0.7+
> 关联:P1A-1(查询改走 LLMRouter)、36-file-processing.md(query 依赖本模块)

## 一、概述

`llm_service` 应用是多端点 LLM 路由器,统一所有业务模块(如 smart_assistant、office_assistant、file_processing 的 AI 分析)的模型调用。它按「数据库 `LlmAppConfig` → Ollama 本地兜底」的降级链路工作,**不再依赖环境变量**直接指定业务端点。

## 二、架构

```
业务模块(app_name 标识)
  └── get_router(app_name)  ──▶ LLMRouter 单例(按 app_name 隔离缓存)
        ├── _load_configs():LlmAppConfig.objects
        │     .select_related("endpoint")
        │     .filter(is_active=True, app_name=..., )
        │     .order_by("endpoint__priority", "endpoint__is_fallback")
        │     → 候选端点列表(priority 升序,主端点在前)
        ▼
generate() / generate_with_tools()
  └── 依次尝试每个候选端点(OpenAI 兼容 /v1/chat/completions)
        ├── 失败 → 记 warning,尝试下一个
        ├── 全部失败 → Ollama 本地兜底(localhost:11434)
        └── 最后一个仍失败 → 抛出原始异常(保留类型与完整堆栈,P0-W)
```

## 三、LLMRouter

### 3.1 类常量

| 常量 | 值 | 说明 |
|------|-----|------|
| `OLLAMA_BASE` | `http://localhost:11434` | Ollama 兜底服务地址 |
| `OLLAMA_MODEL` | `qwen2.5:7b` | 兜底模型的最终回退值;运行时优先 `settings.OLLAMA_MODEL_NAME` |
| `REQUEST_TIMEOUT` | `120`(秒) | 每次请求超时 |

### 3.2 核心方法

- **`generate(prompt, system_message, stream, options, messages)`**
  - 非流式返回 `(content, usage)` 元组;`stream=True` 返回 SSE 内容生成器。
  - `messages` 优先于 `prompt`;内部把 system_message + prompt 组装为 OpenAI messages 数组。
  - 命中的端点会通过 `_enrich_usage` 补充成本核算字段(见下)。
- **`generate_with_tools(messages, *, tools, tool_choice, endpoint_url, options)`**
  - 透传 `tools`/`tool_choice` 给 OpenAI 兼容端点,返回 `(content, usage, tool_calls)` 三元组。
  - `tool_calls` 为标准 OpenAI 结构 `[{"id", "type", "function": {"name", "arguments"}}]`,未触发工具调用时为空列表。
  - `endpoint_url` 覆盖参数直接命中指定端点(主要用于测试场景),不降级。
- **`refresh()`** 重新从数据库加载 `LlmAppConfig`。

### 3.3 usage 成本核算(_enrich_usage)

在端点返回的 usage 字典上**追加**三个字段(不改动原有 token 字段):

- `estimated_cost`:本次调用预估费用(元)。按命中端点的 `cost_per_1k_tokens` × total_tokens / 1000 计算,无配置时 0.0。
- `endpoint_id`:实际命中的 `LlmEndpoint` 主键;Ollama 兜底为 `None`。
- `model_name`:实际命中的模型名(调用方未提供时才写入)。

### 3.4 单例工厂 get_router

```python
_routers = {}

def get_router(app_name="smart_assistant") -> LLMRouter:
    if app_name not in _routers:
        _routers[app_name] = LLMRouter(app_name=app_name)
    return _routers[app_name]
```

- 按 `app_name` 隔离缓存,各应用独立持有自己的端点配置。
- 默认 `smart_assistant` 以兼容既有调用方;无专属配置的应用(如 office_assistant)自动落到 Ollama 全局兜底链。

## 四、OllamaClient

`llm_service/ollama_client.py` 提供对 Ollama **原生 API**(`/api/chat`、`/api/pull`、`/api/tags`)的轻量客户端:

- `base_url` 默认 `OLLAMA_BASE_URL` 环境变量,回退 `http://localhost:11434`。
- `model_name` 默认 `OLLAMA_MODEL_NAME` 环境变量,回退 `qwen2.5:7b`。
- `generate()`:走 `/api/chat`,支持流式;超时 120s。
- `pull_model()` / `list_models()`:模型管理。

> 与 LLMRouter 的区别:OllamaClient 直连 Ollama 原生 API,不参与 DB 端点降级;LLMRouter 走 OpenAI 兼容协议(`/v1/chat/completions`),把 Ollama 作为最终兜底。两者模型名默认值统一为 `qwen2.5:7b`。

## 五、配置与数据模型

- 端点与模型配置存在数据库:`LlmEndpoint`(地址、API Key、`cost_per_1k_tokens`、`priority`、`is_fallback`)与 `LlmAppConfig`(`app_name`、`model_name`、`is_active`)。
- 业务端无需改代码,在 Django Admin 增删端点即可调整降级链路。

## 六、测试

`llm_service/tests/` 覆盖路由降级、usage 富化、工具调用解析、OllamaClient 错误处理等。
