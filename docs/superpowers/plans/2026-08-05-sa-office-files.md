# 智能助手 Office 文件操作能力（阶段 1）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让智能助手聊天流支持上传 Office 附件（docx/pdf/xlsx/pptx/txt/md/csv），直接"看文件 / 问表格 / 生成文档"，生成的 .docx 通过聊天内下载卡片交付。

**Architecture:** 在 `chat/` 与 `chat/stream/` 接口增加 multipart 附件上传；附件经 `OfficeExtractor` 抽取后以 `role="system"` 消息注入 LLM 上下文（不落库、用完即弃）。新增 3 个工具注册到 `ToolRegistry`：`OfficeReadTool`（读切片）、`OfficeGenerateTool`（write+确认，python-docx 生成）、`SpreadsheetTool`（pandas 表格问答）。生成产物写临时文件，经 `office-download/<token>/` 端点下载（签名 token，10 分钟过期）。

**Tech Stack:** Django 4.2 / DRF / Celery、python-docx / mammoth / pdfplumber / openpyxl / python-pptx / pandas、React 18 / AntD 5 / SSE。

## 与 spec 的偏差说明（实施时注意）

- **Task 10（SSE 流式确认流补全）是 spec 未明写但必要的补充**：探索发现 `process_stream`（SSE 路径）没有 confirm-replay 拦截，只有非流式 `process()` 有。若不补，`OfficeGenerateTool`（`require_confirmation=True`）在聊天主界面（SSE）下确认流不可用。此改动同时修复现有 swap 工具在 SSE 下的同类 gap（此前前端未接确认 UI，确认流仅后端框架+测试覆盖）。
- **下载 URL**：spec §4.4 示例用 `/api/smart-assistant/office-download/<token>/`，计划 Task 9 采用同路径（独立 view）。
- **附件上下文注入**：spec §2 说"附件上下文拼入 prompt"，计划实现为 `role="system"` 消息 prepend 到 history，并让 `_select_recent_messages` 保留 system 消息（否则 token 截断可能丢掉附件内容）。

## Global Constraints

- 语言：所有用户可见文案与代码注释使用**中文**（CLAUDE.md）。
- 附件大小上限：`MAX_OFFICE_UPLOAD_SIZE = 10MB`，前端 + 后端双重校验。
- 支持的格式白名单：`.docx .pdf .xlsx .pptx .txt .md .csv`；`.doc/.xls/.ppt` 明确拒绝（400）。
- 附件**临时读取**：不写任何 Django ORM 模型、无数据库迁移；生成产物落 `MEDIA_ROOT/tmp_office/`。
- 切片策略：`<50k` 字符全量注入 prompt；`>50k` 只注入前 2 片（每片 8000 字符）+ 提示 LLM 可用 `office_read` 工具读取更多。
- 新依赖：仅新增 `python-pptx>=0.6.21`（读 pptx 用），不引入 LibreOffice / xlrd。
- 工具风险等级：`office_read`/`spreadsheet_qa` 为 `read`；`office_generate` 为 `write` + `require_confirmation=True`。
- 测试运行：后端 `pytest --ds=omni_desk_backend.settings.test`（in-memory SQLite）；前端 `npm test`。覆盖率 ≥80%。
- 环境：Python 命令一律在 conda `omni_desk` 环境（`/home/fz/anaconda3/envs/omni_desk/bin/python`）或项目 venv 中执行，**禁止污染 base**（全局 python-environment.md 规则）。

---

### Task 1: 新增 python-pptx 依赖并重生成锁文件

**Files:**
- Modify: `omni_desk_backend/requirements.in`
- Modify: `omni_desk_backend/requirements.txt`、`omni_desk_backend/requirements-prod.txt`（由 pip-compile 生成，**禁止手改**）
- Test: 无（依赖变更，验证方式为 import）

**Interfaces:**
- Produces: 环境可 `import pptx`（python-pptx 包）。

- [ ] **Step 1: 在 requirements.in 追加 python-pptx**

在 `omni_desk_backend/requirements.in` 文档处理依赖块（`openpyxl` 附近）加一行：

```
python-pptx>=0.6.21
```

- [ ] **Step 2: 确认当前 conda 环境是 omni_desk**

Run: `conda info --envs | grep '*'`
Expected: 输出行含 `omni_desk` 且带 `*`。若在 `base`，先 `conda activate omni_desk` 再继续。

- [ ] **Step 3: pip-compile 重生成两个锁文件**

Run（在 `omni_desk_backend/` 目录）:
```bash
/home/fz/anaconda3/envs/omni_desk/bin/pip-compile -o requirements.txt requirements-dev.in
/home/fz/anaconda3/envs/omni_desk/bin/pip-compile -o requirements-prod.txt requirements.in
```
Expected: 两文件出现 `python-pptx==0.6.2x` 及其依赖（`Pillow` 已存在）。

- [ ] **Step 4: 安装依赖并验证 import**

Run:
```bash
/home/fz/anaconda3/envs/omni_desk/bin/pip install -r requirements.txt
/home/fz/anaconda3/envs/omni_desk/bin/python -c "import pptx; print(pptx.__version__)"
```
Expected: 打印版本号，无 ImportError。

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/requirements.in omni_desk_backend/requirements.txt omni_desk_backend/requirements-prod.txt
git commit -m "build(smart-assistant): 新增 python-pptx 依赖（读取 pptx 附件）"
```

---

### Task 2: OfficeExtractor 统一抽取器

**Files:**
- Create: `omni_desk_backend/smart_assistant/extractors/office_extractor.py`
- Create: `omni_desk_backend/smart_assistant/extractors/__init__.py`（若不存在）
- Test: `omni_desk_backend/smart_assistant/tests/test_office_extractor.py`

**Interfaces:**
- Produces: 供 Task 3/8 使用：
  ```python
  class OfficeExtractError(Exception): ...

  @dataclass
  class ExtractedDocument:
      text: str
      markdown: str = ""
      tables: list = []      # [{headers, rows}]
      sheets: list = []      # [{name, headers, data}]
      metadata: dict = field(default_factory=dict)
      format: str = ""

  class OfficeExtractor:
      MAX_UPLOAD_SIZE = 10 * 1024 * 1024
      CHUNK_SIZE = 8000
      INLINE_LIMIT = 50_000
      SUPPORTED_EXTENSIONS = {".docx", ".pdf", ".xlsx", ".pptx", ".txt", ".md", ".csv"}

      @staticmethod
      def extract(file) -> ExtractedDocument          # file 为 Django UploadedFile
      @staticmethod
      def chunk_text(text: str, size: int = CHUNK_SIZE) -> list[str]
      @staticmethod
      def format_for_prompt(doc: ExtractedDocument, filename: str) -> str  # 生成注入文本（含切片逻辑）
  ```

- [ ] **Step 1: 写失败测试**

创建 `omni_desk_backend/smart_assistant/tests/test_office_extractor.py`：

```python
import base64
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from smart_assistant.extractors.office_extractor import (
    OfficeExtractor,
    OfficeExtractError,
    ExtractedDocument,
)

# 合法最小 PDF（含文本 "Test PDF content"）
MIN_PDF_B64 = (
    "JVBERi0xLjQKMSAwIG9iajw8IC9UeXBlIC9DYXRhbG9nIC9QYWdlcyAyIDAgUiA+PmVuZG9iagoy"
    "IDAgb2JqPDwgL1R5cGUgL1BhZ2VzIC9LaWRzIFszIDAgUl0gL0NvdW50IDEgPj5lbmRvYmoKMyAw"
    "IG9iajw8IC9UeXBlIC9QYWdlIC9QYXJlbnQgMiAwIFIgL01lZGlhQm94IFswIDAgNjEyIDc5Ml0g"
    "L0NvbnRlbnRzIDQgMCBSIC9SZXNvdXJjZXMgPDwgL0ZvbnQgPDwgL0YxIDUgMCBSID4+ID4+ID4+"
    "ZW5kb2JqCjQgMCBvYmo8PCAvTGVuZ3RoIDcyID4+c3RyZWFtCniccwpR0HczVDAyUQhJUzA3UjA3"
    "MFAISVHQCEktLlEIcHFTSM7PK0nNK9FUCMlScA0BABLQDJIKZW5kc3RyZWFtZW5kb2JqCjUgMCBv"
    "Ymo8PCAvVHlwZSAvRm9udCAvU3VidHlwZSAvVHlwZTEgL0Jhc2VGb250IC9IZWx2ZXRpY2EgPj5l"
    "bmRvYmoKeHJlZgowIDYKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDA5IDAwMDAwIG4gCjAw"
    "MDAwMDAwNTggMDAwMDAgbiAKMDAwMDAwMDExNSAwMDAwMCBuIAowMDAwMDAwMzEyIDAwMDAwIG4g"
    "CjAwMDAwMDAzODggMDAwMDAgbiAKdHJhaWxlcjw8IC9TaXplIDYgL1Jvb3QgMSAwIFIgPj4Kc3Rh"
    "cnR4cmVmCjQ1NAolJUVPRg=="
)


def _make_docx_bytes() -> bytes:
    from docx import Document

    buf = io.BytesIO()
    doc = Document()
    doc.add_paragraph("测试段落一")
    doc.add_paragraph("测试段落二")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "姓名"
    table.cell(0, 1).text = "部门"
    table.cell(1, 0).text = "张三"
    table.cell(1, 1).text = "技术部"
    doc.save(buf)
    return buf.getvalue()


def _make_xlsx_bytes() -> bytes:
    from openpyxl import Workbook

    buf = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "人员表"
    ws.append(["姓名", "部门", "人数"])
    ws.append(["张三", "技术部", 3])
    ws.append(["李四", "市场部", 5])
    wb.save(buf)
    return buf.getvalue()


def _make_pptx_bytes() -> bytes:
    from pptx import Presentation

    buf = io.BytesIO()
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "项目汇报"
    body = slide.placeholders[1]
    body.text = "阶段一完成"
    prs.save(buf)
    return buf.getvalue()


def _upload(name: str, content: bytes) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content, content_type="application/octet-stream")


class TestOfficeExtractor:
    def test_docx_extracts_text_and_table(self):
        doc = OfficeExtractor.extract(_upload("合同.docx", _make_docx_bytes()))
        assert "测试段落一" in doc.text
        assert doc.tables and doc.tables[0]["headers"] == ["姓名", "部门"]
        assert "张三" in doc.markdown

    def test_pdf_extracts_text(self):
        doc = OfficeExtractor.extract(_upload("报告.pdf", base64.b64decode(MIN_PDF_B64)))
        assert "Test PDF content" in doc.text
        assert doc.format == "pdf"

    def test_xlsx_extracts_sheets(self):
        doc = OfficeExtractor.extract(_upload("名单.xlsx", _make_xlsx_bytes()))
        assert len(doc.sheets) == 1
        assert doc.sheets[0]["name"] == "人员表"
        assert "市场部" in doc.text

    def test_pptx_extracts_text(self):
        doc = OfficeExtractor.extract(_upload("汇报.pptx", _make_pptx_bytes()))
        assert "项目汇报" in doc.text

    def test_txt_extracts_text(self):
        doc = OfficeExtractor.extract(_upload("笔记.txt", "纯文本内容".encode("utf-8")))
        assert doc.text == "纯文本内容"

    def test_unsupported_extension_raises(self):
        with pytest.raises(OfficeExtractError):
            OfficeExtractor.extract(_upload("旧版.doc", b"\xd0\xcf\x11\xe0"))

    def test_corrupt_file_raises(self):
        with pytest.raises(OfficeExtractError):
            OfficeExtractor.extract(_upload("坏.docx", b"not a docx at all"))

    def test_chunk_text_splits_by_size(self):
        chunks = OfficeExtractor.chunk_text("a" * 20_000, size=8_000)
        assert len(chunks) == 3
        assert all(len(c) <= 8_000 for c in chunks)

    def test_format_for_prompt_truncates_long_docs(self):
        long_doc = ExtractedDocument(text="x" * 120_000, format="txt")
        prompt = OfficeExtractor.format_for_prompt(long_doc, "长文.txt")
        assert "长文.txt" in prompt
        assert "office_read" in prompt
        assert prompt.count("x") <= 16_000
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/smart_assistant/tests/test_office_extractor.py -v --ds=omni_desk_backend.settings.test`
Expected: FAIL — `ModuleNotFoundError: No module named 'smart_assistant.extractors.office_extractor'`

- [ ] **Step 3: 写实现**

创建 `omni_desk_backend/smart_assistant/extractors/office_extractor.py`：

```python
"""smart_assistant/extractors/office_extractor.py — 统一 Office 文件抽取器

按扩展名路由到各格式处理器（python-docx / mammoth / pdfplumber /
openpyxl / python-pptx / pandas），输出结构化文本 + 表格 + sheet 信息，
供聊天附件上下文注入与工具读取。所有抽取失败统一抛 OfficeExtractError。
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


class OfficeExtractError(Exception):
    """Office 文件抽取失败（格式不支持 / 损坏 / 超限）。"""


@dataclass
class ExtractedDocument:
    """一次抽取的产物。text 为段落合并文本；markdown 优先 docx/pdf；sheets 供 xlsx。"""

    text: str = ""
    markdown: str = ""
    tables: list = field(default_factory=list)
    sheets: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    format: str = ""


class OfficeExtractor:
    """按扩展名路由抽取，并提供切片与 prompt 注入工具。"""

    MAX_UPLOAD_SIZE = 10 * 1024 * 1024
    CHUNK_SIZE = 8000
    INLINE_LIMIT = 50_000
    SUPPORTED_EXTENSIONS = {".docx", ".pdf", ".xlsx", ".pptx", ".txt", ".md", ".csv"}

    @staticmethod
    def extract(file) -> ExtractedDocument:
        name = getattr(file, "name", "") or ""
        ext = Path(name).suffix.lower()
        if ext not in OfficeExtractor.SUPPORTED_EXTENSIONS:
            raise OfficeExtractError(
                f"暂不支持 {ext or '该'} 格式，支持 .docx/.pdf/.xlsx/.pptx/.txt/.md/.csv"
            )
        try:
            data = file.read()
        except Exception as exc:  # pragma: no cover — 依赖具体文件对象
            raise OfficeExtractError(f"读取文件失败: {exc}") from exc
        finally:
            if hasattr(file, "seek"):
                file.seek(0)

        if len(data) > OfficeExtractor.MAX_UPLOAD_SIZE:
            raise OfficeExtractError("文件超过 10MB 上限")

        handler = {
            ".docx": OfficeExtractor._extract_docx,
            ".pdf": OfficeExtractor._extract_pdf,
            ".xlsx": OfficeExtractor._extract_xlsx,
            ".pptx": OfficeExtractor._extract_pptx,
            ".txt": OfficeExtractor._extract_text,
            ".md": OfficeExtractor._extract_text,
            ".csv": OfficeExtractor._extract_csv,
        }[ext]

        try:
            doc = handler(io.BytesIO(data), name)
        except OfficeExtractError:
            raise
        except Exception as exc:
            raise OfficeExtractError("文件无法解析，请确认文件未损坏") from exc

        doc.metadata.update({"filename": name, "size": len(data), "format": ext.lstrip(".")})
        return doc

    @staticmethod
    def _extract_docx(file, name) -> ExtractedDocument:
        from docx import Document
        import mammoth

        document = Document(file)
        paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
        tables = []
        for table in document.tables:
            rows = [[cell.text for cell in row.cells] for row in table.rows]
            if rows:
                tables.append({"headers": rows[0], "rows": rows[1:]})
        file.seek(0)
        md_result = mammoth.convert_to_markdown(file)
        markdown = md_result.value
        return ExtractedDocument(
            text="\n".join(paragraphs),
            markdown=markdown,
            tables=tables,
            format="docx",
        )

    @staticmethod
    def _extract_pdf(file, name) -> ExtractedDocument:
        import pdfplumber

        tables = []
        pages_text = []
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                if page.extract_text():
                    pages_text.append(page.extract_text())
                for t in page.extract_tables() or []:
                    rows = [[cell if cell is not None else "" for cell in row] for row in t]
                    if rows:
                        tables.append({"headers": rows[0], "rows": rows[1:]})
        return ExtractedDocument(text="\n".join(pages_text), tables=tables, format="pdf")

    @staticmethod
    def _extract_xlsx(file, name) -> ExtractedDocument:
        from openpyxl import load_workbook

        wb = load_workbook(file, read_only=True, data_only=True)
        sheets, parts = [], []
        for ws in wb.worksheets:
            rows = [list(r) for r in ws.iter_rows(values_only=True) if any(r)]
            if not rows:
                continue
            headers = [str(c) if c is not None else "" for c in rows[0]]
            data = [[str(c) if c is not None else "" for c in r] for r in rows[1:]]
            sheets.append({"name": ws.title, "headers": headers, "data": data})
            parts.append(
                f"### Sheet: {ws.title}\n"
                + pd.DataFrame(data, columns=headers).to_markdown(index=False)
            )
        wb.close()
        return ExtractedDocument(
            text="\n\n".join(parts),
            markdown="\n\n".join(parts),
            sheets=sheets,
            format="xlsx",
        )

    @staticmethod
    def _extract_pptx(file, name) -> ExtractedDocument:
        from pptx import Presentation

        prs = Presentation(file)
        parts = []
        for i, slide in enumerate(prs.slides, start=1):
            texts = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    texts.append(shape.text)
                if getattr(shape, "has_table", False) and shape.has_table:
                    for row in shape.table.rows:
                        texts.append(" | ".join(cell.text for cell in row.cells))
            parts.append(f"--- 第 {i} 页 ---\n" + "\n".join(t for t in texts if t.strip()))
        return ExtractedDocument(text="\n".join(parts), format="pptx")

    @staticmethod
    def _extract_text(file, name) -> ExtractedDocument:
        raw = file.read().decode("utf-8", errors="replace")
        return ExtractedDocument(text=raw, format=Path(name).suffix.lstrip("."))

    @staticmethod
    def _extract_csv(file, name) -> ExtractedDocument:
        df = pd.read_csv(file)
        return ExtractedDocument(
            text=df.to_markdown(index=False),
            markdown=df.to_markdown(index=False),
            format="csv",
        )

    @staticmethod
    def chunk_text(text: str, size: int = CHUNK_SIZE) -> list[str]:
        """按 size 字符切片。"""
        if not text:
            return []
        return [text[i : i + size] for i in range(0, len(text), size)]

    @staticmethod
    def format_for_prompt(doc: ExtractedDocument, filename: str) -> str:
        """构造注入 LLM 上下文的附件文本。超长只注入前 2 片并提示 office_read。"""
        if len(doc.text) <= OfficeExtractor.INLINE_LIMIT:
            return (
                f"【用户上传附件：{filename}】\n"
                f"{doc.text or doc.markdown or '（未从文件中提取到文本内容，可能为纯图片扫描件）'}"
            )
        chunks = OfficeExtractor.chunk_text(doc.text)
        preview = "\n...\n".join(chunks[:2])
        return (
            f"【用户上传附件：{filename}】\n{preview}\n"
            f"\n（附件较长，以上仅展示前 {len(chunks[:2]) * OfficeExtractor.CHUNK_SIZE} 字符。"
            f"如需读取后续内容，请调用 office_read 工具按需读取。）"
        )
```

创建 `omni_desk_backend/smart_assistant/extractors/__init__.py`（若已存在则补充导出）:

```python
from .office_extractor import ExtractedDocument, OfficeExtractError, OfficeExtractor

__all__ = ["ExtractedDocument", "OfficeExtractError", "OfficeExtractor"]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/smart_assistant/tests/test_office_extractor.py -v --ds=omni_desk_backend.settings.test`
Expected: PASS（9 个用例）。

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/smart_assistant/extractors/
git add omni_desk_backend/smart_assistant/tests/test_office_extractor.py
git commit -m "feat(smart-assistant): OfficeExtractor 统一抽取 docx/pdf/xlsx/pptx/txt/csv"
```

---

### Task 3: OfficeReadTool（读附件切片）

**Files:**
- Create: `omni_desk_backend/smart_assistant/tools/office_read_tool.py`
- Test: `omni_desk_backend/smart_assistant/tests/test_office_read_tool.py`

**Interfaces:**
- Consumes: `OfficeExtractor.chunk_text`（Task 2）；附件经 `ctx.attachment` 传入（Task 8 注入）。
- Produces: `class OfficeReadTool(BaseTool)`，`name="office_read"`，`risk_level="read"`。`execute(query, context) -> dict`。

- [ ] **Step 1: 写失败测试**

创建 `omni_desk_backend/smart_assistant/tests/test_office_read_tool.py`：

```python
from smart_assistant.tools.office_read_tool import OfficeReadTool


def _ctx(**kw):
    base = {"history": [], "attachment": {"text": "a" * 20_000, "filename": "长文.txt"}}
    base.update(kw)
    return base


class TestOfficeReadTool:
    def setup_method(self):
        self.tool = OfficeReadTool()

    def test_reads_chunk_range(self):
        result = self.tool.execute("", _ctx())
        assert result["found"] is True
        assert len(result["chunks"]) == 1  # 默认读第 1 片

    def test_reads_specific_chunk(self):
        ctx = _ctx()
        ctx["attachment"]["chunk_index"] = 2
        result = self.tool.execute("", ctx)
        assert result["chunks"][0].startswith("a" * 16_000)

    def test_no_attachment_returns_not_found(self):
        result = self.tool.execute("", {"history": []})
        assert result["found"] is False
        assert "未找到附件" in result["message"]

    def test_invalid_chunk_index_returns_not_found(self):
        ctx = _ctx()
        ctx["attachment"]["chunk_index"] = 99
        result = self.tool.execute("", ctx)
        assert result["found"] is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/smart_assistant/tests/test_office_read_tool.py -v --ds=omni_desk_backend.settings.test`
Expected: FAIL — `ModuleNotFoundError: No module named 'smart_assistant.tools.office_read_tool'`

- [ ] **Step 3: 写实现**

创建 `omni_desk_backend/smart_assistant/tools/office_read_tool.py`：

```python
"""smart_assistant/tools/office_read_tool.py — 读取已上传 Office 附件切片"""

from __future__ import annotations

from ..extractors.office_extractor import OfficeExtractor
from .base import BaseTool


class OfficeReadTool(BaseTool):
    """读取本次对话已上传 Office 附件的指定切片（长文档按需读取）。"""

    name = "office_read"
    description = "读取用户上传 Office 附件的指定内容切片（当附件较长、需要更多内容时调用）"
    intent_type = "office_read"
    risk_level = "read"

    def execute(self, query=None, context=None, **kwargs) -> dict:
        ctx = context if isinstance(context, dict) else {}
        attachment = ctx.get("attachment")
        if not attachment or not attachment.get("text"):
            return {"found": False, "message": "当前对话未找到可读取的附件内容"}
        chunks = OfficeExtractor.chunk_text(attachment["text"])
        if not chunks:
            return {"found": False, "message": "附件无可读取的文本内容"}
        index = attachment.get("chunk_index", 0)
        if not isinstance(index, int) or index < 0 or index >= len(chunks):
            return {"found": False, "message": f"切片序号越界（共 {len(chunks)} 片）"}
        return {
            "found": True,
            "filename": attachment.get("filename", "附件"),
            "total_chunks": len(chunks),
            "chunks": [chunks[index]],
            "summary": f"已读取附件第 {index + 1}/{len(chunks)} 片",
        }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/smart_assistant/tests/test_office_read_tool.py -v --ds=omni_desk_backend.settings.test`
Expected: PASS（4 个用例）。

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/smart_assistant/tools/office_read_tool.py omni_desk_backend/smart_assistant/tests/test_office_read_tool.py
git commit -m "feat(smart-assistant): OfficeReadTool 读取附件切片"
```

---

### Task 4: OfficeGenerateTool（生成 .docx，require_confirmation）

**Files:**
- Create: `omni_desk_backend/smart_assistant/tools/office_generate_tool.py`
- Test: `omni_desk_backend/smart_assistant/tests/test_office_generate_tool.py`

**Interfaces:**
- Consumes: `save_tmp_office_file`、`create_download_token`（Task 7 定义，本任务先 mock）；confirm-replay 缓存 `get_confirmation_draft`（cache.py 现有）。
- Produces: `class OfficeGenerateTool(BaseTool)`，`name="office_generate"`，`risk_level="write"`，`require_confirmation=True`。`_dry_run(query, ctx) -> dict`、`_confirmed(query, ctx) -> dict`。

- [ ] **Step 1: 写失败测试**

创建 `omni_desk_backend/smart_assistant/tests/test_office_generate_tool.py`：

```python
from unittest.mock import patch

from smart_assistant.tools.office_generate_tool import OfficeGenerateTool


def _ctx(**kw):
    base = {"history": [], "user": None}
    base.update(kw)
    return base


class TestOfficeGenerateTool:
    def setup_method(self):
        self.tool = OfficeGenerateTool()

    @patch("smart_assistant.tools.office_generate_tool._plan_document_structure")
    def test_dry_run_returns_draft(self, mock_plan):
        mock_plan.return_value = {
            "structure": [
                {"type": "heading", "content": "请假单"},
                {"type": "paragraph", "content": "姓名：{name}，日期：{date}"},
            ],
            "variables": {"name": "张三", "date": "2026-08-05"},
        }
        result = self.tool.execute("生成请假单，张三，2026-08-05", _ctx(dry_run=True))
        assert result["found"] is True
        assert result["draft"]["summary"] == "确认生成文档《请假单.docx》"

    @patch("smart_assistant.tools.office_generate_tool._plan_document_structure")
    def test_dry_run_plan_failure_returns_not_found(self, mock_plan):
        mock_plan.return_value = None
        result = self.tool.execute("随便生成", _ctx(dry_run=True))
        assert result["found"] is False

    @patch("smart_assistant.tools.office_generate_tool._render_docx_to_file")
    def test_confirmed_generates_file(self, mock_render):
        mock_render.return_value = ("tmp_office/请假单.docx", b"fake-docx-bytes")
        with patch(
            "smart_assistant.tools.office_generate_tool.create_download_token",
            return_value="tok123",
        ):
            result = self.tool.execute(
                "生成请假单",
                _ctx(
                    confirmed=True,
                    draft={
                        "structure": [{"type": "paragraph", "content": "正文 {name}"}],
                        "variables": {"name": "张三"},
                    },
                ),
            )
        assert result["found"] is True
        assert result["file_download"]["filename"] == "请假单.docx"
        assert result["file_download"]["download_url"].endswith("office-download/tok123/")
        mock_render.assert_called_once()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/smart_assistant/tests/test_office_generate_tool.py -v --ds=omni_desk_backend.settings.test`
Expected: FAIL — `ModuleNotFoundError: No module named 'smart_assistant.tools.office_generate_tool'`

- [ ] **Step 3: 写实现**

创建 `omni_desk_backend/smart_assistant/tools/office_generate_tool.py`：

```python
"""smart_assistant/tools/office_generate_tool.py — 生成 .docx 文档（require_confirmation）

dry_run 阶段：LLM 规划文档结构 + 变量 → 返回 draft。
confirmed 阶段：用 python-docx 按 structure 构建标题/段落/表格 + 变量替换，
写到临时目录，返回 file_download 卡片信息。
"""

from __future__ import annotations

import json
import logging
import re

from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from llm_service.router import get_router
from ..cache import get_confirmation_draft
from .base import BaseTool

logger = logging.getLogger(__name__)

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

STRUCTURE_PROMPT = """你是文档结构规划器。根据用户描述，规划一份 .docx 文档的结构。

用户描述：{query}

请返回严格 JSON，格式：
{{
  "structure": [
    {{"type": "heading", "content": "标题文本", "level": 1}},
    {{"type": "paragraph", "content": "段落文本，可用 {{变量名}} 占位"}},
    {{"type": "table", "headers": ["列1", "列2"], "rows": [["a", "b"]]}}
  ],
  "variables": {{"变量名": "示例值"}}
}}

要求：
1. structure 每项 type 仅限 heading / paragraph / table
2. 变量用 {{name}} 占位，variables 给出示例值
3. 只输出 JSON，不要其他文字"""


def _plan_document_structure(query: str) -> dict | None:
    """调 LLM 规划文档结构。失败/非法 JSON 返回 None。"""
    try:
        answer, _usage = get_router().generate(prompt=STRUCTURE_PROMPT.format(query=query))
    except Exception as exc:
        logger.warning("文档结构规划 LLM 失败: %s", exc)
        return None
    match = re.search(r"\{.*\}", answer or "", re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data.get("structure"), list) or not isinstance(data.get("variables"), dict):
        return None
    return data


def _fill(content: str, variables: dict) -> str:
    """把 {name} 占位符替换为变量值。"""
    for key, value in variables.items():
        content = content.replace("{" + key + "}", str(value))
    return content


def _docx_bytes(doc: DocxDocument) -> bytes:
    import io

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _render_docx_to_file(structure: list, variables: dict, title: str) -> tuple[str, bytes]:
    """用 python-docx 按 structure 构建文档，返回 (相对路径, bytes)。"""
    doc = DocxDocument()
    for item in structure:
        typ = item.get("type")
        content = item.get("content", "")
        if typ == "heading":
            level = int(item.get("level", 1))
            heading = doc.add_heading(level=level)
            run = heading.add_run(_fill(content, variables))
            run.font.size = Pt(16 if level == 1 else 13)
        elif typ == "paragraph":
            doc.add_paragraph(_fill(content, variables))
        elif typ == "table":
            headers = [str(h) for h in item.get("headers", [])]
            rows = [[str(c) for c in r] for r in item.get("rows", [])]
            if headers:
                table = doc.add_table(rows=1 + len(rows), cols=len(headers))
                for j, h in enumerate(headers):
                    table.cell(0, j).text = h
                for i, row in enumerate(rows, start=1):
                    for j, cell in enumerate(row[: len(headers)]):
                        table.cell(i, j).text = cell
    if doc.paragraphs:
        doc.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    from ..tools_io import save_tmp_office_file  # 延迟导入，Task 7 实现

    relative_path = save_tmp_office_file(f"{title}.docx", _docx_bytes(doc))
    return relative_path, _docx_bytes(doc)


class OfficeGenerateTool(BaseTool):
    """根据用户描述生成 .docx 文档（需二次确认）。"""

    name = "office_generate"
    description = "根据用户描述的结构和变量生成 .docx 文档下载"
    intent_type = "office_generate"
    risk_level = "write"
    require_confirmation = True

    def execute(self, query=None, context=None, **kwargs) -> dict:
        ctx = context if isinstance(context, dict) else {}
        if ctx.get("dry_run"):
            return self._dry_run(query, ctx)
        if ctx.get("confirmed"):
            return self._confirmed(query, ctx)
        return {"found": False, "message": "工具执行异常：未进入 dry_run 或 confirmed 模式"}

    def _dry_run(self, query, ctx) -> dict:
        planned = _plan_document_structure(query or "")
        if not planned:
            return {"found": False, "message": "无法根据描述规划文档结构，请补充更明确的要求"}
        structure = planned["structure"]
        title = structure[0].get("content", "文档") if structure else "文档"
        summary = f"确认生成文档《{title}.docx》"
        return {
            "found": True,
            "draft": {
                "summary": summary,
                "fields": {"structure": structure, "variables": planned["variables"]},
            },
        }

    def _confirmed(self, query, ctx) -> dict:
        draft = ctx.get("draft")
        if not draft:
            token = ctx.get("confirm_token")
            if token:
                entry = get_confirmation_draft(token)
                if entry and isinstance(entry, dict):
                    draft = entry.get("draft", {}).get("fields")
        if not draft or not draft.get("structure"):
            return {"found": False, "message": "缺少确认时的文档结构，请重新发起生成"}
        structure = draft["structure"]
        variables = draft.get("variables", {})
        title = structure[0].get("content", "文档") if structure else "文档"
        try:
            from ..tools_io import create_download_token

            relative_path, _bytes = _render_docx_to_file(structure, variables, title)
            token = create_download_token(relative_path)
        except Exception as exc:
            logger.exception("生成 docx 失败")
            return {"found": False, "message": f"生成文档失败：{exc}"}
        return {
            "found": True,
            "summary": f"文档《{title}.docx》已生成",
            "file_download": {
                "filename": f"{title}.docx",
                "download_url": f"/api/smart-assistant/office-download/{token}/",
                "content_type": DOCX_MIME,
            },
        }
```

> 注：`..tools_io` 为 Task 7 创建的新模块 `smart_assistant/tools_io.py`（含 `save_tmp_office_file` / `create_download_token`）。Task 4 测试 mock 掉 `_render_docx_to_file` 与 `create_download_token`，不依赖 Task 7 即可通过；Task 7 落地后真实路径连通。

- [ ] **Step 4: 跑测试确认通过**

Run: `/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/smart_assistant/tests/test_office_generate_tool.py -v --ds=omni_desk_backend.settings.test`
Expected: PASS（3 个用例，均 mock LLM 与文件写入）。

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/smart_assistant/tools/office_generate_tool.py omni_desk_backend/smart_assistant/tests/test_office_generate_tool.py
git commit -m "feat(smart-assistant): OfficeGenerateTool 生成 docx（confirm-replay）"
```

---

### Task 5: SpreadsheetTool（表格问答）

**Files:**
- Create: `omni_desk_backend/smart_assistant/tools/spreadsheet_tool.py`
- Test: `omni_desk_backend/smart_assistant/tests/test_spreadsheet_tool.py`

**Interfaces:**
- Consumes: 附件 `sheets` 数据（`attachment["sheets"]`，Task 8 注入）；`NaturalLanguageQuery`（`file_processing.ai.query`）。
- Produces: `class SpreadsheetTool(BaseTool)`，`name="spreadsheet_qa"`，`risk_level="read"`。

- [ ] **Step 1: 写失败测试**

创建 `omni_desk_backend/smart_assistant/tests/test_spreadsheet_tool.py`：

```python
from unittest.mock import MagicMock, patch

from smart_assistant.tools.spreadsheet_tool import SpreadsheetTool


def _ctx_with_sheets():
    return {
        "history": [],
        "attachment": {
            "filename": "名单.xlsx",
            "sheets": [
                {
                    "name": "人员表",
                    "headers": ["姓名", "部门", "人数"],
                    "data": [["张三", "技术部", "3"], ["李四", "市场部", "5"]],
                }
            ],
        },
    }


class TestSpreadsheetTool:
    def setup_method(self):
        self.tool = SpreadsheetTool()

    def test_simple_aggregation(self):
        result = self.tool.execute("总人数", _ctx_with_sheets())
        assert result["found"] is True
        assert result["stats"]["total_rows"] == 2
        assert result["stats"]["columns"] == ["姓名", "部门", "人数"]

    @patch("smart_assistant.tools.spreadsheet_tool.NaturalLanguageQuery")
    def test_natural_language_query_falls_back_to_llm(self, mock_cls):
        mock_query = MagicMock()
        mock_query.query.return_value = "总人数为 8 人"
        mock_cls.return_value = mock_query
        result = self.tool.execute("各列人数加总", _ctx_with_sheets())
        assert result["found"] is True
        assert "8" in result["answer"]
        mock_query.query.assert_called_once()

    def test_no_sheets_returns_not_found(self):
        result = self.tool.execute("统计", {"history": []})
        assert result["found"] is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/smart_assistant/tests/test_spreadsheet_tool.py -v --ds=omni_desk_backend.settings.test`
Expected: FAIL — `ModuleNotFoundError: No module named 'smart_assistant.tools.spreadsheet_tool'`

- [ ] **Step 3: 写实现**

创建 `omni_desk_backend/smart_assistant/tools/spreadsheet_tool.py`：

```python
"""smart_assistant/tools/spreadsheet_tool.py — Excel 表格统计与自然语言问答"""

from __future__ import annotations

import re

import pandas as pd

from .base import BaseTool

# 简单统计关键词 → 直接用 pandas，不必走 LLM
_SIMPLE_STATS = re.compile(r"总人数|几行|多少行|几条|共.?多少|行数|columns|有哪些列|列名")


class SpreadsheetTool(BaseTool):
    """对上传 Excel 的指定 sheet 做统计或自然语言问答。"""

    name = "spreadsheet_qa"
    description = "对用户上传的 Excel 表格做数据统计（总行数/列名）与自然语言问答"
    intent_type = "spreadsheet_qa"
    risk_level = "read"

    def execute(self, query=None, context=None, **kwargs) -> dict:
        ctx = context if isinstance(context, dict) else {}
        attachment = ctx.get("attachment") or {}
        sheets = attachment.get("sheets") or []
        if not sheets:
            return {"found": False, "message": "当前附件没有可分析的 Excel 表格数据"}
        sheet = sheets[0]
        df = pd.DataFrame(sheet["data"], columns=sheet["headers"])

        if _SIMPLE_STATS.search(query or ""):
            return {
                "found": True,
                "stats": {
                    "sheet": sheet["name"],
                    "columns": sheet["headers"],
                    "total_rows": len(df),
                    "total_columns": len(sheet["headers"]),
                },
                "summary": f"Sheet「{sheet['name']}」共 {len(df)} 行、{len(sheet['headers'])} 列",
            }

        # 复杂自然语言问题 → 复用 file_processing 的 LLM 表格问答
        from file_processing.ai.query import NaturalLanguageQuery

        answer = NaturalLanguageQuery().query(
            query or "",
            {
                "sheets_data": [
                    {"name": sheet["name"], "headers": sheet["headers"], "data": sheet["data"]}
                ]
            },
        )
        return {"found": True, "answer": answer, "summary": answer}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/smart_assistant/tests/test_spreadsheet_tool.py -v --ds=omni_desk_backend.settings.test`
Expected: PASS（3 个用例）。

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/smart_assistant/tools/spreadsheet_tool.py omni_desk_backend/smart_assistant/tests/test_spreadsheet_tool.py
git commit -m "feat(smart-assistant): SpreadsheetTool 表格统计与自然语言问答"
```

---

### Task 6: 注册 3 个工具并更新工具数量断言

**Files:**
- Modify: `omni_desk_backend/smart_assistant/apps.py`
- Modify: `omni_desk_backend/smart_assistant/tests/test_tools.py`、`test_all_tools_scope.py`（工具数量断言）
- Test: `omni_desk_backend/smart_assistant/tests/test_tools.py`

**Interfaces:**
- Consumes: 3 个工具类（Task 3/4/5）。

- [ ] **Step 1: 跑现有测试确认当前工具数量基线**

Run: `/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/smart_assistant/tests/test_tools.py -v --ds=omni_desk_backend.settings.test`
Expected: PASS。记录测试中工具数量的断言值（记作 N）。

- [ ] **Step 2: 写失败测试（先改断言）**

在 `omni_desk_backend/smart_assistant/tests/test_tools.py` 找到工具数量断言（如 `len(ToolRegistry.get_all())` 或 `assert len(registry) == N`），把 `N` 改为 `N + 3`，并新增：

```python
def test_tool_count_after_office_tools():
    from smart_assistant.tools.registry import ToolRegistry

    schemas = ToolRegistry.get_all_schemas()
    names = {s["name"] for s in schemas}
    assert "office_read" in names
    assert "office_generate" in names
    assert "spreadsheet_qa" in names
```

Run: `/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/smart_assistant/tests/test_tools.py::test_tool_count_after_office_tools -v --ds=omni_desk_backend.settings.test`
Expected: FAIL — 断言失败（3 个工具尚未注册）。

- [ ] **Step 3: 在 apps.py 注册**

修改 `omni_desk_backend/smart_assistant/apps.py` 的 `ready()`：在 import 块追加：

```python
from .tools.office_read_tool import OfficeReadTool
from .tools.office_generate_tool import OfficeGenerateTool
from .tools.spreadsheet_tool import SpreadsheetTool
```

在 `ToolRegistry.register(...)` 块末尾追加：

```python
ToolRegistry.register(OfficeReadTool())
ToolRegistry.register(OfficeGenerateTool())
ToolRegistry.register(SpreadsheetTool())
```

- [ ] **Step 4: 跑测试确认通过 + 全量工具测试回归**

Run: `/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/smart_assistant/tests/test_tools.py omni_desk_backend/smart_assistant/tests/test_all_tools_scope.py omni_desk_backend/smart_assistant/tests/test_tool_risk_level.py -v --ds=omni_desk_backend.settings.test`
Expected: PASS。若 `test_all_tools_scope.py` / `test_tool_risk_level.py` 强制所有工具实现 `build_base_queryset`/`_scope_self` 或检查 `supports_scope_filter`，则为 3 个新工具补空实现（`build_base_queryset` 抛 `NotImplementedError` 或返回 `qs.none()`；`_scope_self` 返回 `qs.none()`），保持风险等级校验通过。

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/smart_assistant/apps.py omni_desk_backend/smart_assistant/tools/ omni_desk_backend/smart_assistant/tests/test_tools.py omni_desk_backend/smart_assistant/tests/test_all_tools_scope.py
git commit -m "feat(smart-assistant): 注册 OfficeRead/OfficeGenerate/Spreadsheet 工具"
```

---

### Task 7: 附件缓存 + 临时文件 + 签名下载 token（tools_io）

**Files:**
- Create: `omni_desk_backend/smart_assistant/tools_io.py`
- Modify: `omni_desk_backend/smart_assistant/tasks.py`（清理任务）
- Test: `omni_desk_backend/smart_assistant/tests/test_tools_io.py`

**Interfaces:**
- Produces: 供 Task 4/8/9 使用：
  ```python
  def file_sha256(data: bytes) -> str
  def attachment_cache_key(conversation_id, file_hash: str) -> str
  def cache_attachment(conversation_id, file_hash, doc: dict) -> None        # TTL 600s
  def get_attachment(conversation_id, file_hash) -> dict | None
  def save_tmp_office_file(filename: str, content: bytes) -> str            # 返回 MEDIA 相对路径
  def create_download_token(relative_path: str) -> str                      # HMAC 签名，10 分钟过期
  def resolve_download_token(token: str) -> str | None                      # 一次性，返回相对路径或 None
  def cleanup_expired_files() -> int                                        # 清 10 分钟前的 tmp_office 文件
  ```

- [ ] **Step 1: 写失败测试**

创建 `omni_desk_backend/smart_assistant/tests/test_tools_io.py`：

```python
import os
import time

import pytest
from django.conf import settings
from django.core.cache import cache

from smart_assistant.tools_io import (
    attachment_cache_key,
    cache_attachment,
    cleanup_expired_files,
    create_download_token,
    file_sha256,
    get_attachment,
    resolve_download_token,
    save_tmp_office_file,
)


@pytest.fixture(autouse=True)
def _media_root(tmp_path):
    old = settings.MEDIA_ROOT
    settings.MEDIA_ROOT = str(tmp_path)
    yield
    settings.MEDIA_ROOT = old
    cache.clear()


class TestToolsIO:
    def test_file_sha256_stable(self):
        assert file_sha256(b"abc") == file_sha256(b"abc")
        assert file_sha256(b"abc") != file_sha256(b"abd")

    def test_attachment_cache_roundtrip(self):
        cache_attachment(1, "h1", {"text": "内容", "filename": "a.docx"})
        got = get_attachment(1, "h1")
        assert got["text"] == "内容"

    def test_attachment_cache_miss(self):
        assert get_attachment(999, "nope") is None

    def test_save_and_resolve_token(self):
        rel = save_tmp_office_file("测试.docx", b"bytes")
        assert rel.startswith("tmp_office/")
        full = os.path.join(settings.MEDIA_ROOT, rel)
        assert os.path.exists(full)
        token = create_download_token(rel)
        assert resolve_download_token(token) == rel
        # 一次性
        assert resolve_download_token(token) is None

    def test_resolve_bad_token_none(self):
        assert resolve_download_token("forged.token.value") is None

    def test_cleanup_expired_files(self):
        rel = save_tmp_office_file("过期.docx", b"old")
        full = os.path.join(settings.MEDIA_ROOT, rel)
        old = time.time() - 1200  # 20 分钟前
        os.utime(full, (old, old))
        cleaned = cleanup_expired_files()
        assert not os.path.exists(full)
        assert cleaned >= 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/smart_assistant/tests/test_tools_io.py -v --ds=omni_desk_backend.settings.test`
Expected: FAIL — `ModuleNotFoundError: No module named 'smart_assistant.tools_io'`

- [ ] **Step 3: 写实现**

创建 `omni_desk_backend/smart_assistant/tools_io.py`：

```python
"""smart_assistant/tools_io.py — 附件上下文缓存 + 生成文档临时文件 + 签名下载 token

- 附件抽取结果按 (conversation_id, file_hash) 短时缓存（TTL 10 分钟），不入库。
- 生成的 .docx 写 MEDIA_ROOT/tmp_office/，返回相对路径；下载 token 为 HMAC
  签名（含过期时间），一次性使用。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
import time

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

ATTACHMENT_CACHE_TTL = 600  # 附件抽取结果缓存：10 分钟
DOWNLOAD_TOKEN_TTL = 600  # 下载 token 有效期：10 分钟
TMP_OFFICE_DIR = "tmp_office"  # 相对 MEDIA_ROOT
_CACHE_PREFIX = "smart_assistant:office:"


def file_sha256(data: bytes) -> str:
    """计算文件内容哈希（防重复抽取的缓存 key 之一）。"""
    return hashlib.sha256(data).hexdigest()[:32]  # nosec B324 — 非加密用途


def attachment_cache_key(conversation_id, file_hash: str) -> str:
    return f"{_CACHE_PREFIX}attach:{conversation_id}:{file_hash}"


def cache_attachment(conversation_id, file_hash: str, doc: dict) -> None:
    cache.set(attachment_cache_key(conversation_id, file_hash), doc, ATTACHMENT_CACHE_TTL)


def get_attachment(conversation_id, file_hash: str) -> dict | None:
    return cache.get(attachment_cache_key(conversation_id, file_hash))


def _tmp_dir() -> str:
    root = getattr(settings, "MEDIA_ROOT", "") or ""
    path = os.path.join(root, TMP_OFFICE_DIR)
    os.makedirs(path, exist_ok=True)
    return path


def save_tmp_office_file(filename: str, content: bytes) -> str:
    """写临时文件到 MEDIA_ROOT/tmp_office/，返回相对路径（防重名加时间戳）。"""
    safe = os.path.basename(filename)
    rel = os.path.join(TMP_OFFICE_DIR, f"{int(time.time())}_{secrets.token_hex(4)}_{safe}")
    full = os.path.join(settings.MEDIA_ROOT or "", rel)
    with open(full, "wb") as f:
        f.write(content)
    return rel


def create_download_token(relative_path: str) -> str:
    """生成签名下载 token：base64(payload).signature，payload 含相对路径+过期时间。"""
    expiry = int(time.time()) + DOWNLOAD_TOKEN_TTL
    payload = base64.urlsafe_b64encode(f"{relative_path}:{expiry}".encode()).decode()
    sig = _sign(payload)
    return f"{payload}.{sig}"


def _sign(payload: str) -> str:
    secret = settings.SECRET_KEY.encode()
    return hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()[:32]


def resolve_download_token(token: str) -> str | None:
    """解析并核验下载 token。一次性：成功后立即作废。返回相对路径或 None。"""
    try:
        payload, sig = token.rsplit(".", 1)
    except (ValueError, AttributeError):
        return None
    if not hmac.compare_digest(_sign(payload), sig):
        return None
    try:
        decoded = base64.urlsafe_b64decode(payload.encode()).decode()
        relative_path, expiry_str = decoded.rsplit(":", 1)
        if int(expiry_str) < int(time.time()):
            return None
    except (ValueError, UnicodeDecodeError):
        return None
    # 一次性：登记已使用，防重放
    used_key = f"{_CACHE_PREFIX}used:{payload}"
    if cache.get(used_key):
        return None
    cache.set(used_key, "1", DOWNLOAD_TOKEN_TTL)
    return relative_path


def cleanup_expired_files() -> int:
    """删除 tmp_office 下超过 10 分钟未下载的文件。返回删除数。"""
    tmp = _tmp_dir()
    if not os.path.isdir(tmp):
        return 0
    cutoff = time.time() - DOWNLOAD_TOKEN_TTL
    removed = 0
    for name in os.listdir(tmp):
        full = os.path.join(tmp, name)
        try:
            if os.path.isfile(full) and os.path.getmtime(full) < cutoff:
                os.remove(full)
                removed += 1
        except OSError as exc:  # pragma: no cover — 竞态删除
            logger.warning("清理临时文件失败 %s: %s", full, exc)
    return removed
```

在 `omni_desk_backend/smart_assistant/tasks.py` 追加 Celery 清理任务（参照该文件现有 `@shared_task` 模式）：

```python
@shared_task(name="cleanup_office_tmp_files")
def cleanup_office_tmp_files():
    """定期清理 tmp_office 过期生成文件。"""
    from .tools_io import cleanup_expired_files

    removed = cleanup_expired_files()
    logger.info("已清理过期 office 临时文件: %s", removed)
    return removed
```

- [ ] **Step 4: 跑测试确认通过**

Run: `/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/smart_assistant/tests/test_tools_io.py -v --ds=omni_desk_backend.settings.test`
Expected: PASS（6 个用例）。

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/smart_assistant/tools_io.py omni_desk_backend/smart_assistant/tasks.py omni_desk_backend/smart_assistant/tests/test_tools_io.py
git commit -m "feat(smart-assistant): 附件缓存与生成文档临时文件 + 签名下载 token"
```

---

### Task 8: chat 接口附件上传与上下文注入

**Files:**
- Modify: `omni_desk_backend/smart_assistant/serializers.py`
- Modify: `omni_desk_backend/smart_assistant/views/chat.py`
- Modify: `omni_desk_backend/smart_assistant/agent/conversation_context.py`
- Modify: `omni_desk_backend/smart_assistant/tools/tool_context.py`
- Test: `omni_desk_backend/smart_assistant/tests/test_chat_attachment.py`

**Interfaces:**
- Consumes: `OfficeExtractor`（Task 2）、`tools_io.file_sha256/cache_attachment`（Task 7）。
- Produces: `chat/` 与 `chat/stream/` 支持 `attachment` 字段；附件内容作为 `role="system"` 消息注入 `conversation_history`；`ToolContext` 增加 `attachment` 字段；`_select_recent_messages` 保留 system 消息。

- [ ] **Step 1: 写失败测试**

创建 `omni_desk_backend/smart_assistant/tests/test_chat_attachment.py`：

```python
import io
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient


def _make_docx() -> bytes:
    from docx import Document

    buf = io.BytesIO()
    doc = Document()
    doc.add_paragraph("附件里的合同条款")
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(username="tester", password="x")


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


class TestChatAttachment:
    @patch("smart_assistant.agent.orchestrator.AgentOrchestrator.process")
    def test_upload_attachment_injects_into_history(self, mock_process, client):
        mock_process.return_value = {
            "answer": "ok", "intent": "general_chat", "tool_used": None,
            "tool_result": None, "sources": None, "usage": {},
        }
        docx = SimpleUploadedFile(
            "合同.docx", _make_docx(),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        resp = client.post(
            "/api/smart-assistant/chat/",
            {"query": "合同里写了什么？", "attachment": docx},
            format="multipart",
        )
        assert resp.status_code == 200
        _, kwargs = mock_process.call_args
        history = kwargs["conversation_history"]
        assert any(
            m.get("role") == "system" and "附件里的合同条款" in m.get("content", "")
            for m in history
        )

    def test_invalid_extension_rejected(self, client):
        bad = SimpleUploadedFile("旧版.doc", b"\xd0\xcf\x11\xe0", content_type="application/msword")
        resp = client.post(
            "/api/smart-assistant/chat/",
            {"query": "x", "attachment": bad},
            format="multipart",
        )
        assert resp.status_code == 400
        assert "不支持" in resp.data["detail"]

    def test_no_attachment_still_json(self, client):
        with patch("smart_assistant.agent.orchestrator.AgentOrchestrator.process") as mock_process:
            mock_process.return_value = {
                "answer": "ok", "intent": "general_chat", "tool_used": None,
                "tool_result": None, "sources": None, "usage": {},
            }
            resp = client.post("/api/smart-assistant/chat/", {"query": "你好"}, format="json")
        assert resp.status_code == 200
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/smart_assistant/tests/test_chat_attachment.py -v --ds=omni_desk_backend.settings.test`
Expected: FAIL — 400（`attachment` 非 serializer 字段）。

- [ ] **Step 3: 写实现**

修改 `omni_desk_backend/smart_assistant/serializers.py`，`SmartChatRequestSerializer` 增加字段：

```python
class SmartChatRequestSerializer(serializers.Serializer):
    """智能聊天请求（支持附件上传）"""

    query = serializers.CharField(required=True, help_text="用户问题")
    conversation_id = serializers.IntegerField(required=False, allow_null=True, help_text="可选：关联的会话ID")
    confirm_token = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="可选:二次确认 token,带此字段走 replay 路径(跳过 orchestrator 拦截,直接执行工具)",
    )
    attachment = serializers.FileField(required=False, allow_null=True, help_text="可选：Office 附件（docx/pdf/xlsx/pptx/txt/md/csv，≤10MB）")
```

修改 `omni_desk_backend/smart_assistant/views/chat.py`：

- 顶部 import 增加：
```python
from rest_framework.parsers import FormParser, MultiPartParser

from ..extractors.office_extractor import ExtractedDocument, OfficeExtractError, OfficeExtractor
from ..tools_io import cache_attachment, file_sha256
```

- `SmartChatViewSet` 类增加 `parser_classes = [MultiPartParser, FormParser]`。

- 新增私有方法（放在 `create` 之前）：

```python
def _extract_attachment(self, request):
    """校验并抽取附件。返回 (doc_dict, None) 或 (None, error_response)。"""
    file = request.FILES.get("attachment")
    if not file:
        return None, None
    try:
        extracted = OfficeExtractor.extract(file)
    except OfficeExtractError as exc:
        return None, Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    if not extracted.text and not extracted.markdown:
        return None, Response(
            {"detail": "未从文件中提取到文本内容，可能为纯图片扫描件"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    file.seek(0)
    doc_dict = {
        "text": extracted.text,
        "markdown": extracted.markdown,
        "sheets": extracted.sheets,
        "format": extracted.format,
        "filename": file.name,
    }
    return doc_dict, None

def _inject_attachment(self, conversation_history, doc_dict, conversation_id):
    """把附件内容作为 system 消息注入历史头部，并写入附件缓存。"""
    prompt_text = OfficeExtractor.format_for_prompt(
        ExtractedDocument(text=doc_dict["text"], markdown=doc_dict["markdown"]),
        doc_dict["filename"],
    )
    attachment_msg = {"role": "system", "content": prompt_text}
    conversation_history = [attachment_msg] + (conversation_history or [])
    if conversation_id:
        file_hash = file_sha256((doc_dict["filename"] + doc_dict["text"][:200]).encode())
        cache_attachment(conversation_id, file_hash, doc_dict)
    return conversation_history
```

- `create` 方法：在 `serializer.is_valid()` 校验通过后、confirm_token 分支前插入附件抽取与注入；在 orchestrator 调用前把 `doc_dict` 挂到 `tool_context`：

```python
doc_dict, err_resp = self._extract_attachment(request)
if err_resp:
    return err_resp

# ...（confirm_token replay 分支不变，但构造 tool_context 时带上 attachment）...
tool_context = ToolContext(
    user=request.user,
    scope=resolve_scope(request.user),
    attachment=doc_dict,
)
# 附件注入（在 build_effective_history 之后）
if doc_dict:
    conversation_history = self._inject_attachment(conversation_history, doc_dict, conversation_id)
```

- `stream` 方法：同样在 serializer 校验后抽取附件；`event_stream` 闭包内 orchestrator 调用点传入注入后的 `conversation_history` 与带 `attachment` 的 `tool_context`（闭包内变量需在外层先定义并捕获）。

修改 `omni_desk_backend/smart_assistant/tools/tool_context.py` 的 `ToolContext` dataclass，新增可选字段（需先 Read 该文件确认现有字段，保持 frozen dataclass 风格）：

```python
@dataclass(frozen=True)
class ToolContext:
    user: Any
    scope: str = SmartAssistantScope.SELF
    history: list = field(default_factory=list)
    attachment: dict | None = None  # 本次请求的附件抽取结果（临时，不持久化）
```

修改 `omni_desk_backend/smart_assistant/agent/conversation_context.py` 的 `_select_recent_messages`，让 system 消息始终保留：

```python
def _select_recent_messages(history: list) -> list:
    """根据 token 限制选择要保留的历史消息。system 消息（附件上下文/摘要）始终保留。"""
    if not history:
        return []
    system_msgs = [m for m in history if m.get("role") == "system"]
    others = [m for m in history if m.get("role") != "system"]
    if not others:
        return system_msgs
    total_tokens = sum(estimate_tokens(m.get("content", "")) for m in others)
    if total_tokens <= SOFT_TOKEN_LIMIT:
        return system_msgs + others
    selected = []
    running_tokens = 0
    for msg in reversed(others):
        content = msg.get("content", "")
        clean_content = _remove_thinking_tags(content)
        token_count = estimate_tokens(clean_content)
        if running_tokens + token_count > HARD_TOKEN_LIMIT:
            break
        selected.insert(0, {"role": msg["role"], "content": clean_content})
        running_tokens += token_count
    return system_msgs + selected
```

- [ ] **Step 4: 跑测试确认通过**

Run: `/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/smart_assistant/tests/test_chat_attachment.py -v --ds=omni_desk_backend.settings.test`
Expected: PASS（3 个用例）。同时回归 `test_tool_context.py`（ToolContext 新增字段需兼容既有构造）。

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/smart_assistant/serializers.py omni_desk_backend/smart_assistant/views/chat.py omni_desk_backend/smart_assistant/agent/conversation_context.py omni_desk_backend/smart_assistant/tools/tool_context.py omni_desk_backend/smart_assistant/tests/test_chat_attachment.py
git commit -m "feat(smart-assistant): chat 接口支持附件上传并注入 LLM 上下文"
```

---

### Task 9: office-download 下载端点

**Files:**
- Create: `omni_desk_backend/smart_assistant/views/office_download.py`
- Modify: `omni_desk_backend/smart_assistant/urls.py`
- Test: `omni_desk_backend/smart_assistant/tests/test_office_download.py`

**Interfaces:**
- Consumes: `resolve_download_token`（Task 7）。
- Produces: `GET /api/smart-assistant/office-download/<token>/`，JWT 鉴权，返回 .docx blob。

- [ ] **Step 1: 写失败测试**

创建 `omni_desk_backend/smart_assistant/tests/test_office_download.py`：

```python
import os

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from smart_assistant.tools_io import create_download_token, save_tmp_office_file


@pytest.fixture(autouse=True)
def _media_root(tmp_path):
    old = settings.MEDIA_ROOT
    settings.MEDIA_ROOT = str(tmp_path)
    yield
    settings.MEDIA_ROOT = old


@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(username="dluser", password="x")


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


class TestOfficeDownload:
    def test_valid_token_returns_blob(self, client):
        rel = save_tmp_office_file("请假单.docx", b"docx-content")
        token = create_download_token(rel)
        resp = client.get(f"/api/smart-assistant/office-download/{token}/")
        assert resp.status_code == 200
        assert b"docx-content" in resp.content
        assert resp["Content-Disposition"].endswith("请假单.docx")

    def test_reused_token_rejected(self, client):
        rel = save_tmp_office_file("测试.docx", b"x")
        token = create_download_token(rel)
        client.get(f"/api/smart-assistant/office-download/{token}/")
        resp2 = client.get(f"/api/smart-assistant/office-download/{token}/")
        assert resp2.status_code == 403

    def test_forged_token_rejected(self, client):
        resp = client.get("/api/smart-assistant/office-download/forged.token/")
        assert resp.status_code == 403

    def test_requires_auth(self):
        c = APIClient()
        resp = c.get("/api/smart-assistant/office-download/anything/")
        assert resp.status_code == 401
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/smart_assistant/tests/test_office_download.py -v --ds=omni_desk_backend.settings.test`
Expected: FAIL — 404（路由不存在）。

- [ ] **Step 3: 写实现**

创建 `omni_desk_backend/smart_assistant/views/office_download.py`：

```python
"""smart_assistant/views/office_download.py — 临时生成 .docx 下载端点"""

from __future__ import annotations

import logging
import os

from django.conf import settings
from django.http import FileResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..tools_io import resolve_download_token

logger = logging.getLogger(__name__)

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class OfficeDownloadView(APIView):
    """返回临时生成的 .docx。token 一次性、10 分钟过期。"""

    permission_classes = [IsAuthenticated]

    def get(self, request, token):
        relative_path = resolve_download_token(token)
        if not relative_path:
            return Response({"detail": "链接已失效，请重新生成"}, status=403)
        full = os.path.join(settings.MEDIA_ROOT or "", relative_path)
        if not os.path.isfile(full):
            logger.warning("下载文件不存在: %s", relative_path)
            return Response({"detail": "文件不存在"}, status=404)
        try:
            f = open(full, "rb")
        except OSError as exc:
            logger.exception("打开下载文件失败: %s", full)
            return Response({"detail": "文件读取失败"}, status=500)

        def _cleanup():
            try:
                f.close()
            finally:
                try:
                    os.remove(full)  # 下载后即删
                except OSError:
                    pass

        resp = FileResponse(
            f,
            content_type=DOCX_MIME,
            as_attachment=True,
            filename=os.path.basename(relative_path),
        )
        resp.close = _cleanup
        return resp
```

修改 `omni_desk_backend/smart_assistant/urls.py`，追加：

```python
from .views.office_download import OfficeDownloadView

urlpatterns = [
    path("doctor/", DoctorView.as_view(), name="smart-doctor"),
    path("office-download/<str:token>/", OfficeDownloadView.as_view(), name="office-download"),
    path("", include(router.urls)),
]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/smart_assistant/tests/test_office_download.py -v --ds=omni_desk_backend.settings.test`
Expected: PASS（4 个用例）。

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/smart_assistant/views/office_download.py omni_desk_backend/smart_assistant/urls.py omni_desk_backend/smart_assistant/tests/test_office_download.py
git commit -m "feat(smart-assistant): office-download 临时文档下载端点"
```

---

### Task 10: SSE 流式确认流补全（process_stream confirm-replay 拦截）

**Files:**
- Modify: `omni_desk_backend/smart_assistant/agent/orchestrator.py`
- Modify: `omni_desk_backend/smart_assistant/views/chat.py`
- Test: `omni_desk_backend/smart_assistant/tests/test_orchestrator_confirm.py`（扩展）

**Interfaces:**
- Consumes: 现有 `apply_pre_execute_hooks` / `set_confirmation_draft` / `Reject`（已有）。
- Produces: `process_stream` 对 `require_confirmation=True` 工具在 dry_run 后发出 `confirmation` SSE 事件；replay 路径把 `draft` 注入工具 context。

- [ ] **Step 1: 写失败测试**

在 `omni_desk_backend/smart_assistant/tests/test_orchestrator_confirm.py` 追加：

```python
def test_stream_yields_confirmation_event_for_confirm_tool():
    """SSE 流式路径对 require_confirmation 工具应发出 confirmation 事件而非直接执行。"""
    from smart_assistant.agent.orchestrator import AgentOrchestrator
    from smart_assistant.tools.registry import ToolRegistry

    tool = ToolRegistry.get_tool("office_generate")
    assert tool is not None and tool.require_confirmation

    events = [e for e in AgentOrchestrator().process_stream("生成请假单", [], None)]
    data_blob = "\n".join(events)
    assert "awaiting_confirmation" in data_blob or "confirmation_token" in data_blob
    # 不应直接执行生成
    assert "file_download" not in data_blob
```

> 说明：确认拦截发生在 `_dry_run` 之前（`apply_pre_execute_hooks` 返回 `Reject(confirmation_required)`）。若 `_dry_run` 因 LLM 不可用返回 `found=False` 无 draft，orchestrator 会发失败 done，但**仍不会直接执行生成**——测试断言的核心是"未出现 file_download"。

- [ ] **Step 2: 跑测试确认失败**

Run: `/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/smart_assistant/tests/test_orchestrator_confirm.py::test_stream_yields_confirmation_event_for_confirm_tool -v --ds=omni_desk_backend.settings.test`
Expected: FAIL — 当前 `process_stream` 无确认拦截，直接 execute。

- [ ] **Step 3: 写实现**

修改 `omni_desk_backend/smart_assistant/agent/orchestrator.py` 的 `process_stream`，在 `if tool:` 之后、`cached_result` 之前插入与 `process()` 对称的确认拦截：

```python
        if tool:
            # === confirm-replay 流式拦截（与 process() 对称） ===
            if getattr(tool, "require_confirmation", False):
                hook_ctx = tool_context if tool_context is not None else {"history": conversation_history or []}
                hook_result = apply_pre_execute_hooks(tool, hook_ctx, {"query": user_query})
                if isinstance(hook_result, Reject) and hook_result.error_code == "confirmation_required":
                    dry_run_result = execute_guarded(
                        tool,
                        user_query,
                        context={"history": conversation_history or [], "dry_run": True},
                    )
                    draft = dry_run_result.get("draft") if isinstance(dry_run_result, dict) else None
                    if not draft:
                        done = {"type": "done", "error": True}
                        annotate_error_kind(
                            done,
                            dry_run_result.get("message", "工具未返回确认草案"),
                            tool_used=tool.name,
                            tool_result=dry_run_result,
                        )
                        yield sse_event(done)
                        return
                    token = str(uuid.uuid4())
                    set_confirmation_draft(
                        token,
                        {
                            "tool_name": tool.name,
                            "user_query": user_query,
                            "context_sig": scope_sig,
                            "draft": draft,
                        },
                    )
                    yield sse_event(
                        {"type": "meta", "intent": intent, "tool_used": tool.name, "tool_result": {"draft": draft}}
                    )
                    yield sse_event(
                        {
                            "type": "confirmation",
                            "awaiting_confirmation": True,
                            "confirmation_token": token,
                            "draft": draft,
                            "answer": draft.get("summary") or "请确认以下操作",
                        }
                    )
                    yield sse_event({"type": "done", "error": False, "awaiting_confirmation": True})
                    return
            # === confirm-replay 流式拦截结束 ===
```

确保 `orchestrator.py` 顶部已 import `Reject`、`uuid`、`apply_pre_execute_hooks`（`Reject` 来自 `..hooks.base`；若未导入则补 `from ..hooks.wiring import apply_pre_execute_hooks` 与 `from ..hooks.base import Reject`，以及 `import uuid`）。

修改 `omni_desk_backend/smart_assistant/views/chat.py` 的 replay 路径（`create` 方法 confirm_token 分支），把 draft 注入 context：

```python
tool_result = execute_guarded(
    tool,
    draft_entry["user_query"],
    context={
        "history": [],
        "confirmed": True,
        "confirm_token": confirm_token,
        "user": request.user,
        "draft": draft_entry.get("draft", {}).get("fields"),
    },
)
```

- [ ] **Step 4: 跑测试确认通过 + 回归**

Run: `/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/smart_assistant/tests/test_orchestrator_confirm.py omni_desk_backend/smart_assistant/tests/test_view_confirm_replay.py -v --ds=omni_desk_backend.settings.test`
Expected: 新用例 PASS，既有 confirm-replay 用例 0 退化。

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/smart_assistant/agent/orchestrator.py omni_desk_backend/smart_assistant/views/chat.py omni_desk_backend/smart_assistant/tests/test_orchestrator_confirm.py
git commit -m "feat(smart-assistant): SSE 流式确认流补全 + replay 注入 draft"
```

---

### Task 11: 前端 API 层（FormData / confirm_token / download）

**Files:**
- Modify: `omni_desk_frontend/src/features/smart-assistant/api/smartAssistantApi.js`
- Test: `omni_desk_frontend/src/features/smart-assistant/api/__tests__/smartAssistantApi.test.js`（若无则新建）

**Interfaces:**
- Produces:
  ```js
  sendSmartChatStream(query, conversationId = null, attachment = null, confirmToken = null) -> {bodyPromise, abort}
  sendSmartChat(query, conversationId = null, attachment = null, confirmToken = null) -> Promise
  downloadOfficeFile(token) -> Promise<Blob>
  ```

- [ ] **Step 1: 写失败测试**

创建 `omni_desk_frontend/src/features/smart-assistant/api/__tests__/smartAssistantApi.test.js`：

```js
import { sendSmartChatStream, downloadOfficeFile } from '../smartAssistantApi';

describe('smartAssistantApi attachment & confirm', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    localStorage.clear();
  });

  beforeEach(() => {
    localStorage.setItem('authTokens', JSON.stringify({ access: 'tok123' }));
  });

  test('sendSmartChatStream sends FormData when attachment present', async () => {
    const mockResponse = { status: 200, ok: true, body: 'STREAM' };
    global.fetch = jest.fn().mockResolvedValue(mockResponse);

    const fakeFile = new File(['abc'], 'a.docx', { type: 'application/octet-stream' });
    await sendSmartChatStream('问题', null, fakeFile).bodyPromise;

    const [, options] = global.fetch.mock.calls[0];
    expect(options.body).toBeInstanceOf(FormData);
    expect(options.body.get('query')).toBe('问题');
    expect(options.body.get('attachment')).toBe(fakeFile);
    expect(options.headers['Content-Type']).toBeUndefined();
  });

  test('sendSmartChatStream sends JSON when no attachment', async () => {
    const mockResponse = { status: 200, ok: true, body: 'STREAM' };
    global.fetch = jest.fn().mockResolvedValue(mockResponse);
    await sendSmartChatStream('问题').bodyPromise;
    const [, options] = global.fetch.mock.calls[0];
    expect(options.headers['Content-Type']).toBe('application/json');
    expect(JSON.parse(options.body)).toEqual({ query: '问题' });
  });

  test('sendSmartChatStream passes confirmToken', async () => {
    global.fetch = jest.fn().mockResolvedValue({ status: 200, ok: true, body: 'S' });
    await sendSmartChatStream('确认', null, null, 'tok-replay').bodyPromise;
    const [, options] = global.fetch.mock.calls[0];
    expect(JSON.parse(options.body).confirm_token).toBe('tok-replay');
  });

  test('downloadOfficeFile returns blob', async () => {
    const blob = new Blob(['x'], { type: 'application/octet-stream' });
    global.fetch = jest.fn().mockResolvedValue({ status: 200, ok: true, blob: async () => blob });
    const result = await downloadOfficeFile('tok123');
    expect(result).toBe(blob);
    expect(global.fetch.mock.calls[0][0]).toContain('/office-download/tok123/');
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run（在 `omni_desk_frontend/`）: `npm test -- --runInBand`
Expected: FAIL — `sendSmartChatStream` 仅两个参数、无 FormData 分支、无 `downloadOfficeFile`。

- [ ] **Step 3: 写实现**

修改 `omni_desk_frontend/src/features/smart-assistant/api/smartAssistantApi.js`：

```js
export function sendSmartChatStream(query, conversationId = null, attachment = null, confirmToken = null) {
  const abortController = new AbortController();

  const requestPromise = (async () => {
    const authTokens = JSON.parse(localStorage.getItem('authTokens') || sessionStorage.getItem('authTokens') || '{}');
    const token = authTokens.access;

    const useFormData = attachment != null;
    let body;
    let headers = { Authorization: `Bearer ${token}` };

    if (useFormData) {
      body = new FormData();
      body.append('query', query);
      if (conversationId) body.append('conversation_id', conversationId);
      if (confirmToken) body.append('confirm_token', confirmToken);
      body.append('attachment', attachment);
    } else {
      body = { query };
      if (conversationId) body.conversation_id = conversationId;
      if (confirmToken) body.confirm_token = confirmToken;
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(body);
    }

    try {
      const response = await fetch(`${apiClient.defaults.baseURL}${BASE_URL}/chat/stream/`, {
        method: 'POST',
        headers,
        body,
        signal: abortController.signal,
      });
      if (response.status === 401) throw new Error('AUTH_ERROR');
      if (!response.ok) throw new Error('NETWORK_ERROR');
      return response.body;
    } catch (error) {
      if (error.name === 'AbortError') return null;
      if (error.message === 'AUTH_ERROR') throw new Error('认证已过期，请重新登录');
      if (error.message === 'NETWORK_ERROR') throw new Error('网络连接失败，请检查网络');
      throw new Error('服务不可用，请稍后再试');
    }
  })();

  return { bodyPromise: requestPromise, abort: () => abortController.abort() };
}

export async function sendSmartChat(query, conversationId = null, attachment = null, confirmToken = null) {
  if (attachment != null) {
    const formData = new FormData();
    formData.append('query', query);
    if (conversationId) formData.append('conversation_id', conversationId);
    if (confirmToken) formData.append('confirm_token', confirmToken);
    formData.append('attachment', attachment);
    return apiClient.post(`${BASE_URL}/chat/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  }
  const body = { query };
  if (conversationId) body.conversation_id = conversationId;
  if (confirmToken) body.confirm_token = confirmToken;
  return apiClient.post(`${BASE_URL}/chat/`, body);
}

export async function downloadOfficeFile(token) {
  const authTokens = JSON.parse(localStorage.getItem('authTokens') || sessionStorage.getItem('authTokens') || '{}');
  const response = await fetch(`${apiClient.defaults.baseURL}${BASE_URL}/office-download/${token}/`, {
    headers: { Authorization: `Bearer ${authTokens.access}` },
  });
  if (!response.ok) throw new Error('下载失败，链接可能已过期');
  return response.blob();
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `npm test -- --runInBand`
Expected: PASS（4 个新用例）。

- [ ] **Step 5: Commit**

```bash
git add omni_desk_frontend/src/features/smart-assistant/api/smartAssistantApi.js omni_desk_frontend/src/features/smart-assistant/api/__tests__/smartAssistantApi.test.js
git commit -m "feat(smart-assistant): 前端 API 支持附件 FormData / confirm_token / 下载"
```

---

### Task 12: 前端 FileAttachmentInput 组件 + 聊天页集成

**Files:**
- Create: `omni_desk_frontend/src/shared/components/FileAttachmentInput.jsx`
- Modify: `omni_desk_frontend/src/features/smart-assistant/pages/SmartChatPage.jsx`
- Modify: `omni_desk_frontend/src/shared/components/QuickAssistant.jsx`
- Test: `omni_desk_frontend/src/shared/components/__tests__/FileAttachmentInput.test.jsx`

**Interfaces:**
- Produces: `FileAttachmentInput`（受控组件：`value` = File|null，`onChange(file|null)`，`disabled`）。导出 `validateFile({name,size}) -> {ok, reason?}` 纯函数便于测试。

- [ ] **Step 1: 写失败测试**

创建 `omni_desk_frontend/src/shared/components/__tests__/FileAttachmentInput.test.jsx`：

```jsx
import React from 'react';
import { render, fireEvent, screen } from '@testing-library/react';
import FileAttachmentInput, { validateFile } from '../FileAttachmentInput';

describe('validateFile', () => {
  test('accepts supported extension', () => {
    expect(validateFile({ name: '合同.docx', size: 100 }).ok).toBe(true);
  });
  test('rejects .doc', () => {
    expect(validateFile({ name: '旧版.doc', size: 100 }).ok).toBe(false);
  });
  test('rejects over 10MB', () => {
    expect(validateFile({ name: '大.pdf', size: 11 * 1024 * 1024 }).ok).toBe(false);
  });
});

describe('FileAttachmentInput', () => {
  test('renders selected file chip and remove button', () => {
    const file = new File(['abc'], '合同.docx', { type: 'application/octet-stream' });
    render(<FileAttachmentInput value={file} onChange={() => {}} />);
    expect(screen.getByText('合同.docx')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /移除/ }));
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `npm test -- --runInBand`
Expected: FAIL — 组件/导出函数不存在。

- [ ] **Step 3: 写实现**

创建 `omni_desk_frontend/src/shared/components/FileAttachmentInput.jsx`：

```jsx
import React from 'react';
import { Upload, Button, Space, Typography, message } from 'antd';
import { PaperClipOutlined, CloseOutlined } from '@ant-design/icons';
import PropTypes from 'prop-types';

const ALLOWED_EXTENSIONS = ['.docx', '.pdf', '.xlsx', '.pptx', '.txt', '.md', '.csv'];
const MAX_SIZE = 10 * 1024 * 1024;

/**
 * 校验附件是否合法。导出为纯函数便于单测。
 * @returns {{ok: boolean, reason?: string}}
 */
export function validateFile({ name = '', size = 0 } = {}) {
  const idx = name.toLowerCase().lastIndexOf('.');
  const ext = idx >= 0 ? name.toLowerCase().slice(idx) : '';
  if (!ALLOWED_EXTENSIONS.includes(ext)) {
    return { ok: false, reason: '仅支持 .docx/.pdf/.xlsx/.pptx/.txt/.md/.csv' };
  }
  if (size > MAX_SIZE) {
    return { ok: false, reason: '文件超过 10MB 上限' };
  }
  return { ok: true };
}

/**
 * 聊天附件选择器：白名单校验 + 缩略 chip + 移除。
 */
export default function FileAttachmentInput({ value, onChange, disabled }) {
  const handleBeforeUpload = (file) => {
    const result = validateFile(file);
    if (!result.ok) {
      message.error(result.reason);
      return false;
    }
    onChange(file);
    return false; // 阻止自动上传，交给聊天发送流程
  };

  return (
    <Space size={4}>
      <Upload
        accept={ALLOWED_EXTENSIONS.join(',')}
        beforeUpload={handleBeforeUpload}
        showUploadList={false}
        disabled={disabled}
      >
        <Button icon={<PaperClipOutlined />} size="small" disabled={disabled}>
          选择文件
        </Button>
      </Upload>
      {value && (
        <Typography.Text type="secondary" style={{ maxWidth: 200 }} ellipsis>
          {value.name}
        </Typography.Text>
      )}
      {value && (
        <Button
          type="text"
          size="small"
          icon={<CloseOutlined />}
          onClick={() => onChange(null)}
          aria-label="移除附件"
        />
      )}
    </Space>
  );
}

FileAttachmentInput.propTypes = {
  value: PropTypes.object,
  onChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
};

FileAttachmentInput.defaultProps = { value: null, disabled: false };
```

集成 `SmartChatPage.jsx`（`src/features/smart-assistant/pages/SmartChatPage.jsx`）：
- import `FileAttachmentInput`；新增 `const [attachment, setAttachment] = useState(null);`
- 发送处：`sendSmartChatStream(inputMessage, currentSessionId, attachment, null)`，发送成功后 `setAttachment(null)`
- 输入区 JSX 加 `<FileAttachmentInput value={attachment} onChange={setAttachment} />`

集成 `QuickAssistant.jsx`（`src/shared/components/QuickAssistant.jsx`）：同样加 state 与组件（`sendSmartChatStream(query, currentSessionId, attachment, null)`）。

- [ ] **Step 4: 跑测试确认通过**

Run: `npm test -- --runInBand`
Expected: PASS（新组件用例 + 既有页面用例回归；若 SmartChatPage 快照受影响则更新快照）。

- [ ] **Step 5: Commit**

```bash
git add omni_desk_frontend/src/shared/components/FileAttachmentInput.jsx omni_desk_frontend/src/shared/components/__tests__/FileAttachmentInput.test.jsx omni_desk_frontend/src/features/smart-assistant/pages/SmartChatPage.jsx omni_desk_frontend/src/shared/components/QuickAssistant.jsx
git commit -m "feat(smart-assistant): 聊天页附件上传组件与集成"
```

---

### Task 13: 前端确认弹窗 + 下载卡片渲染

**Files:**
- Modify: `omni_desk_frontend/src/features/smart-assistant/components/ToolResult.jsx`
- Modify: `omni_desk_frontend/src/features/smart-assistant/pages/SmartChatPage.jsx`（确认流事件处理）
- Test: `omni_desk_frontend/src/features/smart-assistant/components/__tests__/ToolResult.test.jsx`（新增下载卡片断言）

**Interfaces:**
- Consumes: `sendSmartChat`（confirm 二次请求，Task 11）、`downloadOfficeFile`（Task 11）。
- Produces: `ToolResult` 渲染 `file_download` 下载卡片；`SmartChatPage` 处理 SSE `confirmation` 事件 → Modal.confirm → 二次请求。

- [ ] **Step 1: 写失败测试**

创建 `omni_desk_frontend/src/features/smart-assistant/components/__tests__/ToolResult.test.jsx`：

```jsx
import React from 'react';
import { render, screen } from '@testing-library/react';
import ToolResult from '../ToolResult';

describe('ToolResult download card', () => {
  test('renders download button when file_download present', () => {
    render(
      <ToolResult
        intent="office_generate"
        result={{
          found: true,
          file_download: {
            filename: '请假单.docx',
            download_url: '/api/smart-assistant/office-download/tok/',
          },
        }}
        sources={null}
      />
    );
    expect(screen.getByText('请假单.docx')).toBeTruthy();
    expect(screen.getByRole('button', { name: /下载/ })).toBeTruthy();
  });

  test('does not render download button without file_download', () => {
    render(<ToolResult intent="schedule_query" result={{ found: true, schedules: [] }} sources={null} />);
    expect(screen.queryByRole('button', { name: /下载/ })).toBeNull();
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `npm test -- --runInBand`
Expected: FAIL — ToolResult 未渲染下载按钮。

- [ ] **Step 3: 写实现**

修改 `omni_desk_frontend/src/features/smart-assistant/components/ToolResult.jsx`：

- import 增加：
```jsx
import { DownloadOutlined } from '@ant-design/icons';
import { message, Space } from 'antd';
import { downloadOfficeFile } from '../api/smartAssistantApi';
```

- 新增子组件 `FileDownloadCard`（同文件内）：

```jsx
function FileDownloadCard({ fileDownload }) {
  const [downloading, setDownloading] = React.useState(false);

  const handleDownload = async () => {
    if (downloading) return;
    setDownloading(true);
    try {
      const token = (fileDownload.download_url || '').split('/').filter(Boolean).pop();
      const blob = await downloadOfficeFile(token);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileDownload.filename || 'document.docx';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      message.error(err.message || '下载失败');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Card size="small" style={{ marginTop: 8 }}>
      <Space>
        <span>{fileDownload.filename}</span>
        <Button icon={<DownloadOutlined />} size="small" onClick={handleDownload} loading={downloading}>
          下载
        </Button>
      </Space>
    </Card>
  );
}
```

- 在 ToolResult 渲染体收尾处（现有 intent 卡片之后），`result.file_download` 存在时渲染：

```jsx
{result.file_download && <FileDownloadCard fileDownload={result.file_download} />}
```

修改 `SmartChatPage.jsx` 处理 SSE `confirmation` 事件：

- 在 SSE 事件解析处，增加 `data.type === 'confirmation'` 分支调用：

```jsx
const handleConfirmation = async (event) => {
  const token = event.confirmation_token;
  const draft = event.draft || {};
  Modal.confirm({
    title: '请确认操作',
    content: event.answer || draft.summary || '确认执行该操作吗？',
    okText: '确认生成',
    cancelText: '取消',
    onOk: async () => {
      const resp = await sendSmartChat(inputMessage, currentSessionId, null, token);
      const data = resp.data;
      if (data && data.tool_result && data.tool_result.file_download) {
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now(),
            role: 'assistant',
            intent: data.tool_used,
            content: data.answer || '文档已生成',
            tool_result: data.tool_result,
            sources: null,
          },
        ]);
      }
    },
  });
};
```

> 说明：`sendSmartChat` 二次请求走非流式 `chat/`（已支持 confirm_token replay，Task 8 实现）。下载经 ToolResult 下载卡片触发。`Modal` / `message` 从 `antd` import（SmartChatPage 已 import Modal 则复用）。

- [ ] **Step 4: 跑测试确认通过 + 前端全量**

Run: `npm test -- --runInBand`
Expected: PASS（ToolResult 2 个新用例 + 全量回归）。若 `SmartChatPage` 既有测试受影响，同步修复。

- [ ] **Step 5: Commit**

```bash
git add omni_desk_frontend/src/features/smart-assistant/components/ToolResult.jsx omni_desk_frontend/src/features/smart-assistant/components/__tests__/ToolResult.test.jsx omni_desk_frontend/src/features/smart-assistant/pages/SmartChatPage.jsx
git commit -m "feat(smart-assistant): 下载卡片 + SSE 确认弹窗"
```

---

### Task 14: 全量验证与收尾

**Files:**
- Modify: `docs/superpowers/plans/2026-08-05-sa-office-files.md`（勾选本计划步骤 `[x]`）
- Test: 全量回归

**Interfaces:**
- Consumes: 前 13 个任务全部完成。

- [ ] **Step 1: 后端全量测试**

Run（在 `omni_desk_backend/`）:
```bash
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest --ds=omni_desk_backend.settings.test -q
```
Expected: 全绿。

- [ ] **Step 2: 覆盖率检查**

Run:
```bash
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest --ds=omni_desk_backend.settings.test --cov=smart_assistant.extractors.office_extractor --cov=smart_assistant.tools.office_read_tool --cov=smart_assistant.tools.office_generate_tool --cov=smart_assistant.tools.spreadsheet_tool --cov=smart_assistant.tools_io --cov=smart_assistant.views.office_download -q
```
Expected: 新增模块覆盖率 ≥80%（不足则补用例）。

- [ ] **Step 3: ruff + mypy**

Run:
```bash
/home/fz/anaconda3/envs/omni_desk/bin/ruff check omni_desk_backend/smart_assistant/
/home/fz/anaconda3/envs/omni_desk/bin/python -m mypy omni_desk_backend/smart_assistant/ --ignore-missing-imports
```
Expected: 0 错误。

- [ ] **Step 4: 前端全量测试 + lint + build**

Run（在 `omni_desk_frontend/`）:
```bash
npm test
npm run lint
npm run build
```
Expected: 全绿，build 通过（含 `scripts/generate-routes.js` 路由自动生成）。

- [ ] **Step 5: 清理截图/临时产物 + 勾选计划**

- 删除调试截图（若有）
- 在本文档每个已完成任务标题前加 `[x]`

- [ ] **Step 6: 提交收尾**

```bash
git add -A
git commit -m "docs(smart-assistant): 完成 Office 文件能力阶段 1 实施计划"
```

- [ ] **Step 7: 创建 feature 分支 PR（若当前在 main）**

本次改动已分 13 个 commit 落在当前分支。若直接在 main 开发，则将 commit 整理到 feature 分支并开 PR；若已在 `feat/sa-office-files` 分支，直接推送并建 PR：

```bash
git switch -c feat/sa-office-files
git push -u origin feat/sa-office-files
gh pr create --title "feat(smart-assistant): Office 文件操作能力（阶段 1）" --body "见设计 spec: docs/superpowers/specs/2026-08-05-sa-office-files-design.md"
```
