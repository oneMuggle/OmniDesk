# Design: 智能助手 Office 文件操作能力（阶段 1）

**Date**: 2026-08-05
**Status**: Draft (awaiting user review)
**Author**: Claude (via brainstorming)
**Branch**: main

## 1. 背景 & 目标

### 1.1 背景

分析确认：OmniDesk 智能助手（`smart_assistant`）当前**没有任何工具直接读写 Office 二进制文件**：

- `DocumentTool` 只查 `DocumentTemplate` / `GeneratedDocument` 的**元数据**，不读文件内容
- `RAGTool` 通过 RAGFlow 只拿到外部解析后的文本片段，不能读全文/结构
- `SmartChatRequestSerializer` 只接 `query / conversation_id / confirm_token`，**chat 接口完全不支持附件**
- 依赖层（`python-docx` / `mammoth` / `pdfplumber` / `openpyxl` / `pandas` / `docxtpl` / `docxcompose`）已安装但 smart_assistant 内**零调用**
- 真正能拆 Office 的代码散落在 `file_processing` / `documents` / `office_assistant` 三个独立模块，与智能助手完全脱钩

### 1.2 目标

让用户**直接在智能助手聊天流中**完成"看文件、问表格、生成文档"三类操作：

1. **Chat 附件上传**：`chat/` 与 `chat/stream/` 支持 multipart 附件上传
2. **OfficeExtractor 统一抽取**：docx/pdf/xlsx/pptx/txt/md/csv → 文本/表格/Markdown
3. **3 个新工具注册**：`OfficeReadTool` / `OfficeGenerateTool` / `SpreadsheetTool`
4. **聊天内下载卡片**：生成的 .docx 通过下载卡片交付
5. **附件临时读取**：不入库、不落盘（生成产物除外），用完即弃

### 1.3 不在范围（YAGNI，阶段 2+ 再做）

- `.doc` / `.xls` / `.ppt` 老格式（需 LibreOffice 系统依赖）
- `DocumentTemplate.file` / `GeneratedDocument.generated_file` 模型字段
- PPT 生成工具（python-pptx 仅用于读取 .pptx）
- OCR 兜底（Mineru 扫描件识别）
- 附件持久化到知识库 / RAGFlow
- 三套文档管线（file_processing / documents / office_assistant）的合并重构

## 2. 架构

```
┌─ 前端 ─────────────────────────────────────┐
│ SmartChatPage / QuickAssistant             │
│  ├─ 输入框旁: Upload 按钮（附件选择）        │
│  └─ 消息流: ToolResult 渲染下载卡片         │
└──────────────┬─────────────────────────────┘
               │ POST chat/stream/ (multipart: query + attachment)
               ▼
┌─ 后端 ─────────────────────────────────────┐
│ chat.py (MultiPartParser)                  │
│  → 附件 → magic MIME 校验 → 大小校验(10MB)  │
│  → OfficeExtractor 抽取 (docx/pdf/xlsx/     │
│     pptx/txt/md/csv)                       │
│  → 切片策略: <50k 字符全量注入, >50k 注入    │
│    前 2 片 + 提示 LLM 可用 ReadTool 按需读   │
│  → 附件上下文拼入 prompt                    │
│  → LLM: 直接回答 / 调工具                   │
│                                            │
│ ToolRegistry 新增:                         │
│  ├─ OfficeReadTool  (read)                 │
│  ├─ OfficeGenerateTool (write+确认)         │
│  └─ SpreadsheetTool (read)                 │
│                                            │
│ 生成结果 → 临时 .docx 文件 + 短期签名 token  │
│  → GET /office-download/<token>/ 返回 blob │
└────────────────────────────────────────────┘
```

**关键约束**：

- 附件上下文与历史消息**隔离**：抽取内容只存在于本次请求内存，不写 `ChatMessage`
- 工具层薄：复用 `BaseTool` / `ToolRegistry` / confirm-replay 基础设施
- Extractor 独立：可单测、可替换格式处理器
- 零模型改动：不新增持久化字段，无数据库迁移

## 3. 数据流

### 3.1 读文件问答

```
1. 用户上传 .docx + 提问 "这份合同的有效期是？"
2. chat/stream 接收 multipart → magic 校验 → OfficeExtractor 抽取
3. 抽取文本 < 50k 字符 → 全量注入 attachment_context
4. LLM 基于附件上下文直接回答（SSE 流式返回）
5. 附件随请求结束释放
```

### 3.2 表格问答

```
1. 用户上传 .xlsx + 提问 "帮我统计各部门人数"
2. 抽取注入上下文（sheet markdown 预览）
3. LLM 判断需要统计 → 调 SpreadsheetTool(sheet_index, query)
4. SpreadsheetTool: openpyxl → pandas DataFrame → 统计/自然语言问答
5. 返回统计结果 → LLM 组织成答案
```

### 3.3 生成文档

```
1. 用户描述 "基于换班制度生成一份请假单" + 选模板/描述结构
2. LLM 规划文档结构 + 变量 → OfficeGenerateTool.execute(dry_run=True)
3. 返回 {structure, variables, confirm_token} → 前端 ConfirmModal 展示变量
4. 用户确认 → POST chat {query, confirm_token}
5. OfficeGenerateTool.execute(confirmed=True) → python-docx 生成 .docx
6. 写入 MEDIA_ROOT/tmp_office/ → 返回 {filename, download_url, token}
7. ToolResult 渲染下载卡片 → 用户点击下载
```

## 4. 组件

### 4.1 后端新增文件（`omni_desk_backend/smart_assistant/`）

#### 4.1.1 `extractors/office_extractor.py`

```python
# 统一 Office 抽取器：按扩展名路由到格式处理器
@dataclass
class ExtractedDocument:
    text: str                 # 纯文本（段落合并）
    markdown: str             # Markdown 渲染（docx/pdf/xlsx 优先）
    tables: list[dict]        # 表格列表 [{headers, rows}]
    sheets: list[dict]        # xlsx sheet 列表 [{name, markdown, rows}]
    metadata: dict            # {format, filename, size, page_count?, sheet_count?}
    format: str               # "docx" | "pdf" | "xlsx" | "pptx" | "txt" | "md" | "csv"

class OfficeExtractor:
    @staticmethod
    def extract(file: UploadedFile) -> ExtractedDocument:
        """按 file.name 扩展名路由，抽取失败抛 OfficeExtractError"""
    @staticmethod
    def chunk_text(text: str, size: int = 8000) -> list[str]:
        """按 ~8000 字符切片，供长文档按需读取"""
```

格式路由：

| 格式 | 处理器 | 关键库 |
|---|---|---|
| `.docx` | python-docx 抽段落+表格 + mammoth 转 Markdown | `python-docx`, `mammoth` |
| `.pdf` | pdfplumber 抽文本 + 表格 | `pdfplumber` |
| `.xlsx` | openpyxl 遍历 sheet → markdown/json | `openpyxl` |
| `.pptx` | python-pptx 抽文本 + 备注 + 表格 | `python-pptx`（新依赖） |
| `.txt` / `.md` | 直接 decode utf-8 | — |
| `.csv` | 读取 + pandas 转 markdown | `pandas` |

#### 4.1.2 `tools/office_read_tool.py`

```python
class OfficeReadTool(BaseTool):
    name = "office_read"
    description = "读取已上传 Office 附件的指定切片内容（长文档按需读取）"
    risk_level = "read"
    parameters = {
        "file_index": {"type": "integer", "description": "附件序号（本次对话第几个附件）"},
        "chunk_range": {"type": "array", "items": {"type": "integer"}, "description": "[start, end] 切片区间"},
    }
    # execute(ctx): 从附件上下文缓存读取指定切片返回
```

#### 4.1.3 `tools/office_generate_tool.py`

```python
class OfficeGenerateTool(BaseTool):
    name = "office_generate"
    description = "根据用户描述的结构和变量生成 .docx 文档"
    risk_level = "write"
    require_confirmation = True
    # _dry_run: LLM 规划 structure + variables → 返回 {structure, variables} draft
    # _confirmed: python-docx 按 structure 构建标题/段落/表格 + 变量替换
    #            → 写临时文件 → 返回 {filename, download_url, token}
```

**生成策略（阶段 1 MVP）**：用 python-docx 从零构建（标题 + 段落 + 表格 + 变量），不依赖 docxtpl 模板文件（docxtpl 需 .docx 模板，模板文件化属阶段 2）。变量用 `{name}` 占位符替换。

#### 4.1.4 `tools/spreadsheet_tool.py`

```python
class SpreadsheetTool(BaseTool):
    name = "spreadsheet_qa"
    description = "对上传的 Excel 做数据统计与自然语言问答"
    risk_level = "read"
    parameters = {
        "sheet_index": {"type": "integer"},
        "query": {"type": "string", "description": "自然语言统计问题"},
    }
    # execute(ctx): openpyxl → pandas DataFrame
    #   → 简单聚合（sum/mean/count/groupby）直接用 pandas
    #   → 复杂自然语言查询复用 file_processing.ai.NaturalLanguageQuery
```

#### 4.1.5 `views/office_download.py`

```python
@action(detail=False, methods=["get"])
def office_download(self, request, token=None):
    """返回临时生成的 .docx 文件，下载后删除。token 有效 10 分钟。"""
```

### 4.2 后端修改文件

| 文件 | 改动 |
|---|---|
| `serializers.py` | `SmartChatRequestSerializer` 增加 `attachment = FileField(required=False, allow_null=True)` |
| `views/chat.py` | `create` / `stream` 加 `parser_classes = [MultiPartParser, FormParser]`；附件接收 → 校验 → 抽取 → 注入 prompt |
| `apps.py` | `ready()` 注册 3 个新工具 |
| `urls.py` | 增加 `office-download/<str:token>/` 路由 |
| `cache.py` 或新增 `office_attachment.py` | 附件内容按 `conversation_id + file_hash` 短时缓存（TTL 10 分钟）；生成临时文件注册清理 |
| `requirements.in` / `.txt` / `-prod.txt` | 新增 `python-pptx>=0.6.21` |

### 4.3 前端修改文件（`omni_desk_frontend/src/`）

| 文件 | 改动 |
|---|---|
| `shared/components/FileAttachmentInput.jsx`（新） | 通用附件选择：类型白名单校验、大小校验、缩略 chip、移除、错误 toast |
| `features/smart-assistant/pages/SmartChatPage.jsx` | 输入区加 `FileAttachmentInput`；附件随消息发送；消息流显示附件气泡 |
| `shared/components/QuickAssistant.jsx` | 同样加 `FileAttachmentInput` |
| `features/smart-assistant/api/smartAssistantApi.js` | `sendSmartChat` / `sendSmartChatStream` 支持 FormData（有附件时） |
| `features/smart-assistant/components/ToolResult.jsx` | 渲染下载卡片（`tool_result.file_download`）；生成确认按钮（复用 ConfirmModal） |

### 4.4 SSE 契约扩展

`chat/stream/` 的 SSE 事件中，`tool_result` 新增可选字段：

```json
{
  "intent": "office_generate",
  "tool_result": {
    "file_download": {
      "filename": "请假单.docx",
      "download_url": "/api/smart-assistant/office-download/<token>/",
      "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }
  }
}
```

### 4.5 性能与缓存

- **附件抽取**：`conversation_id + file_hash` 作 key 缓存抽取结果，TTL 10 分钟；重复提问同一附件不重复抽取
- **附件内容**：注入 prompt 时控制总量（<50k 字符全量，>50k 只注入前 2 片约 16k 字符 + 提示 LLM 可调 `OfficeReadTool`）
- **确认流**：复用现有 confirm-replay 缓存（`set_confirmation_draft`），`_confirmed` 优先用 `ctx.draft_fields` 避免二次 LLM 规划

## 5. 错误处理

| 场景 | 行为 |
|---|---|
| 不支持的格式（.doc/.xls/.ppt） | 前端拦截 + 后端 magic 校验兜底 → 400「暂不支持该格式，支持 .docx/.pdf/.xlsx/.pptx/.txt/.md/.csv」 |
| 文件过大（>10MB） | 前端 + 后端双重校验 → 400 |
| MIME 伪装 | python-magic 检测真实类型不符 → 400 |
| 损坏文件 / 抽取失败 | `OfficeExtractError` → 400「文件无法解析，请确认文件未损坏」 |
| 空文件 / 无可抽取内容 | 提示「未从文件中提取到文本内容，可能为纯图片扫描件」 |
| 生成确认超时 | confirm_token 过期 → 400「确认已过期，请重新发起」 |
| 下载 token 过期 / 已使用 | 403「链接已失效，请重新生成」 |
| LLM 无有效输出 | 按现有 chat 兜底逻辑处理 |

## 6. 安全

- **鉴权**：`office-download` 端点仍要求 JWT 鉴权（token 仅防 URL 猜测，不替代登录）
- **附件大小**：`MAX_OFFICE_UPLOAD_SIZE = 10MB` 常量，前端 + 后端一致
- **签名 token**：`secrets.token_urlsafe(32)` + 过期时间戳 + HMAC 签名（`settings.SECRET_KEY`），存入短时缓存
- **敏感信息**：抽取文本注入 LLM 前过现有 `PiiMaskingHook`（`smart_assistant/hooks/`）
- **临时文件**：下载后即删；未被下载的由 Celery 定时清理（TTL 10 分钟）
- **无模型改动**：不新增持久化字段，无数据库迁移，降低风险面

## 7. 测试

| 文件 | 类型 | 数量 | 内容 |
|---|---|---|---|
| `smart_assistant/tests/test_office_extractor.py` | 新 | ~20 | 每格式一个 fixture（docx/pdf/xlsx/pptx/txt/csv）；损坏/空/不支持格式各 1 |
| `smart_assistant/tests/test_office_read_tool.py` | 新 | ~6 | 切片读取、无附件、越界 |
| `smart_assistant/tests/test_office_generate_tool.py` | 新 | ~10 | dry_run 规划 / confirmed 生成 / 变量替换 / 临时文件 |
| `smart_assistant/tests/test_spreadsheet_tool.py` | 新 | ~8 | pandas 聚合、mock `NaturalLanguageQuery` |
| `smart_assistant/tests/test_chat_attachment.py` | 新 | ~8 | multipart 上传 → 抽取注入 prompt；无附件保持原 JSON；大小/格式/MIME 校验失败 |
| `smart_assistant/tests/test_office_download.py` | 新 | ~5 | token 过期 403、有效 token 返回 blob、下载后删除 |
| 前端 `FileAttachmentInput.test.jsx` | 新 | ~6 | 类型/大小白名单、chip、错误 toast |
| 前端 `ToolResult.test.jsx` | 改 | +4 | 下载卡片有/无 `file_download` 字段 |
| 前端 `smartAssistantApi.test.js` | 改 | +4 | FormData vs JSON 分支 |

**Mock 策略**：

- 各格式处理器：fixture 二进制文件放 `smart_assistant/tests/fixtures/`
- LLM：patch `NaturalLanguageQuery` / LLM 客户端
- magic：patch `magic.from_buffer`

**覆盖率目标**：80%+（项目标准）。新增代码随测试一起提交。

## 8. 迁移 / 兼容性

| 改动 | 兼容情况 |
|---|---|
| `SmartChatRequestSerializer` 加 attachment 字段 | 向后兼容（`required=False`），无附件请求行为不变 |
| chat 接口加 parser_classes | 原 JSON 请求不受影响 |
| SSE 事件新增 `file_download` 字段 | 可选字段，旧前端忽略 |
| 新增 3 个工具 | 全新增，不影响现有 14 个工具 |
| 新增依赖 python-pptx | 需重新 `pip-compile` + 重新生成锁文件 |
| 无模型改动 / 无迁移 | 数据库零影响 |

## 9. 风险

| 风险 | 缓解 |
|---|---|
| 长文档全文塞 LLM 上下文爆掉 | 切片 + 注入前 2 片 + `OfficeReadTool` 按需读取 |
| 生成复杂版式效果差 | 阶段 1 明确"简单模板"定位，复杂版式留待 docxtpl + 模板文件化（阶段 2） |
| multipart + SSE 混用兼容性 | 前端 FormData 上传（文件流），SSE 只做文本流，两者分离 |
| python-pptx 读取兼容性 | fixture 覆盖标准 pptx；损坏文件走统一 400 |
| 附件抽取延迟影响响应 | 抽取在请求内同步执行，10MB 上限 + 内存缓冲控制；大文件抽取 <2s 预期 |
| Win7/IE11 兼容（下载卡片） | `URL.createObjectURL` + `<a download>`，AntD 5 现有能力 |

## 10. 实施步骤

| # | 步骤 | 验证 |
|---|---|---|
| 1 | `requirements.in` 加 python-pptx + pip-compile 重生成锁文件 | `pip-compile -o requirements.txt requirements-dev.in`（在 conda omni_desk 环境） |
| 2 | 创建 `extractors/office_extractor.py` + fixture 文件 | `pytest test_office_extractor.py -v` |
| 3 | 创建 3 个工具 + 注册到 `apps.py` | `pytest test_office_read_tool.py / test_office_generate_tool.py / test_spreadsheet_tool.py` |
| 4 | 改 `serializers.py` + `views/chat.py` 附件上传 | `pytest test_chat_attachment.py -v` |
| 5 | 创建 `views/office_download.py` + urls | `pytest test_office_download.py -v` |
| 6 | 附件内容缓存 + 临时文件清理任务 | `pytest` 相关用例 |
| 7 | 前端 `FileAttachmentInput` + API FormData 分支 | `npm test` |
| 8 | 前端 `SmartChatPage` / `QuickAssistant` 集成 | `npm test` |
| 9 | 前端 `ToolResult` 下载卡片 | `npm test` |
| 10 | 全套 backend `pytest` + 前端 `npm test` | 全绿 |
| 11 | coverage 检查 + ruff + mypy | ≥80% / 0 错误 |
| 12 | 提交 + PR | feature 分支 `feat/sa-office-files` |

## 11. 附录：文件清单

| 路径 | 操作 | 估行数 |
|---|---|---|
| `omni_desk_backend/smart_assistant/extractors/office_extractor.py` | 新 | ~200 |
| `omni_desk_backend/smart_assistant/tools/office_read_tool.py` | 新 | ~60 |
| `omni_desk_backend/smart_assistant/tools/office_generate_tool.py` | 新 | ~150 |
| `omni_desk_backend/smart_assistant/tools/spreadsheet_tool.py` | 新 | ~120 |
| `omni_desk_backend/smart_assistant/views/office_download.py` | 新 | ~80 |
| `omni_desk_backend/smart_assistant/serializers.py` | 改 | +5 |
| `omni_desk_backend/smart_assistant/views/chat.py` | 改 | +60 |
| `omni_desk_backend/smart_assistant/apps.py` | 改 | +3 |
| `omni_desk_backend/smart_assistant/urls.py` | 改 | +1 |
| `omni_desk_backend/smart_assistant/cache.py`（或 office_attachment.py） | 改/新 | +60 |
| `omni_desk_backend/requirements.in` + 锁文件 | 改 | +1 |
| `omni_desk_backend/smart_assistant/tests/fixtures/*` | 新 | 6 文件 |
| `omni_desk_backend/smart_assistant/tests/test_office_extractor.py` | 新 | ~300 |
| `omni_desk_backend/smart_assistant/tests/test_office_read_tool.py` | 新 | ~80 |
| `omni_desk_backend/smart_assistant/tests/test_office_generate_tool.py` | 新 | ~150 |
| `omni_desk_backend/smart_assistant/tests/test_spreadsheet_tool.py` | 新 | ~120 |
| `omni_desk_backend/smart_assistant/tests/test_chat_attachment.py` | 新 | ~120 |
| `omni_desk_backend/smart_assistant/tests/test_office_download.py` | 新 | ~80 |
| `omni_desk_frontend/src/shared/components/FileAttachmentInput.jsx` | 新 | ~120 |
| `omni_desk_frontend/src/features/smart-assistant/pages/SmartChatPage.jsx` | 改 | +60 |
| `omni_desk_frontend/src/shared/components/QuickAssistant.jsx` | 改 | +30 |
| `omni_desk_frontend/src/features/smart-assistant/api/smartAssistantApi.js` | 改 | +20 |
| `omni_desk_frontend/src/features/smart-assistant/components/ToolResult.jsx` | 改 | +40 |
| 前端对应测试 | 新/改 | ~200 |
