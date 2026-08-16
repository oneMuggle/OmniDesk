# 36. 文件处理 (file_processing app)

> 适用版本:OmniDesk v0.7+
> 关联:PR 文件处理模块、P1A-1(查询改走 LLMRouter)

## 一、概述

`file_processing` 应用提供 Office / PDF 文件的上传、异步解析与 AI 分析能力。用户上传 Excel / Word / PDF 文件后,系统通过 Celery 异步任务解析出纯文本、Markdown 与结构化数据,并可对结果做 AI 摘要、自然语言查询与导出。

## 二、架构

```
POST /api/file/upload/  ──▶ UploadedFile 落库
        │  process_file_task.delay(file_id)  (Celery 异步)
        ▼
FileProcessingService.process_file()
  └── 按 MIME 类型选择 Processor(策略模式)
        ├── ExcelProcessor   (.xlsx / .xls / csv)
        ├── WordProcessor    (.docx / .doc)
        └── PDFProcessor     (.pdf)
        ├── extract_text()      → content_text
        ├── extract_markdown()  → content_markdown
        ├── extract_structured()→ content_json / sheets_data
        └── get_metadata()      → sheet_count / page_count
        ▼
ProcessingResult 落库 + UploadedFile.status = "completed"
```

## 三、数据模型

### 3.1 UploadedFile(上传文件元数据)

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID(主键) | 自动生成 |
| `user` | FK → CustomUser | 属主(related_name=`uploaded_files`) |
| `original_filename` | CharField(255) | 原始文件名 |
| `file` | FileField | 存储路径 `uploads/%Y/%m/%d/` |
| `file_size` | BigIntegerField | 字节数 |
| `mime_type` | CharField(100) | 检测到的真实 MIME(内容检测) |
| `status` | CharField | `pending` / `processing` / `completed` / `failed` |
| `error_message` | TextField | 失败原因(不暴露内部细节) |
| `sheet_count` / `page_count` | IntegerField | Excel Sheet 数 / PDF/Word 页数 |
| `created_at` / `updated_at` | DateTimeField | 自动时间戳 |

### 3.2 ProcessingResult(处理结果,与 UploadedFile 一对一)

- `content_text`:纯文本(供 AI 分析)
- `content_markdown`:Markdown 格式
- `content_json`:结构化数据
- `sheets_data`:Excel Sheet 数据列表
- `row_count` / `column_count`:行列统计
- `processed_at`:处理时间

### 3.3 AIAnalysis(AI 分析记录)

- `analysis_type`:`summary`(数据摘要) / `statistics`(统计分析) / `quality`(数据质量) / `query`(自然语言查询)
- `query_text`:用户查询(仅 query 类型)
- `result_text` / `result_data`:AI 生成的结果
- `model_used` / `tokens_used` / `processing_time_ms`:模型与用量信息

## 四、API 端点

路由:`/api/file/`(DefaultRouter 注册 `FileProcessingViewSet`),全部要求登录(`IsAuthenticated`),且 `get_queryset()` 只返回当前用户文件。

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/file/` | GET | 当前用户文件列表 |
| `/api/file/{id}/` | GET / PUT / PATCH / DELETE | 单个文件 CRUD |
| `/api/file/upload/` | POST | 上传文件(见下) |
| `/api/file/{id}/preview/` | GET | 预览数据(sheets / markdown) |
| `/api/file/{id}/analyze/` | POST | AI 数据摘要 |
| `/api/file/{id}/query/` | POST | 自然语言查询 |
| `/api/file/{id}/export/{csv\|markdown}/` | GET | 导出 CSV / Markdown |

### 4.1 upload 流程与安全检查

1. **大小限制**:超过 `FILE_UPLOAD_MAX_MEMORY_SIZE`(默认 10MB)返回 400。
2. **真实 MIME 检测**:用 `python-magic` 读前 2KB 内容判断真实类型(不信文件名);xlsx/docx 在 magic 中检测为 `application/zip`,结合扩展名做映射还原。
3. **白名单校验**:仅接受 5 种 MIME(xlsx / xls / docx / doc / pdf),否则 400。
4. 落库后 `process_file_task.delay(file_id)` 触发异步解析。

### 4.2 query 的输入防护

- 文件必须 `completed` 状态。
- 问题长度上限 2000 字符(防资源耗尽与 prompt 注入)。
- P1A-1 起底层走 `LLMRouter`(见 [38-llm-service.md](38-llm-service.md)),返回 `(answer, usage)` 元组,usage 暴露给前端。

### 4.3 export 的 CSV 公式注入防护

导出 CSV 时对以 `=`、`+`、`-`、`@` 开头的字段添加前导单引号,防止电子表格公式注入。

## 五、异步任务

`tasks.py::process_file_task`(`celery.shared_task`):

- `max_retries=3`,指数退避 `60s → 120s → 240s`
- 硬超时 `task_time_limit=300`(5 分钟)、软超时 `task_soft_time_limit=240`,防止 OCR/PDF 处理粘死 worker
- 不可重试错误(`ValueError`:不支持的文件类型/格式错误)直接失败;可重试错误(IO/临时服务不可用)重试并统一写 `error_message`(不暴露内部细节)

## 六、AI 分析

- `DataSummarizer`(`ai/summarizer.py`):对 `sheets_data` 生成数据摘要(sheet 数、总行数)。
- `NaturalLanguageQuery`(`ai/query.py`):自然语言查询,走 `LLMRouter` 降级链路。

## 七、测试

`file_processing/tests/` 覆盖 processors、services、views、tasks、query、summarizer 与模型。
