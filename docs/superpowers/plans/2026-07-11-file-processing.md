# 文件处理功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现完整的文件处理系统，支持 Excel/Word/PDF 解析、AI 数据摘要、自然语言查询和导出功能

**Architecture:** 新建 `file_processing` Django app，采用处理器模式（Processor Pattern），每种文件格式对应一个处理器。后端使用 Python 库（openpyxl、pandas、python-docx、pdfplumber）进行文件解析，通过 Celery 异步处理。前端重构 FileAnalysisPage，使用 Ant Design 组件展示数据。

**Tech Stack:** 
- Backend: Django 4.2, DRF, Celery, openpyxl, pandas, python-docx, pdfplumber, mammoth, ollama
- Frontend: React 18.3, Ant Design 5, react-markdown, axios

## Global Constraints

- Python 版本：3.10
- Django 版本：4.2
- 文件大小限制：10MB
- 支持格式：Excel (.xlsx, .xls, .csv)、Word (.docx, .doc)、PDF (.pdf)
- AI 模型：Ollama qwen2.5:7b
- 前端无新增依赖（使用现有 Ant Design Table + react-markdown）

---

## 文件结构映射

### 后端新增文件

```
omni_desk_backend/file_processing/
├── __init__.py
├── apps.py
├── models.py                    # UploadedFile, ProcessingResult, AIAnalysis
├── admin.py                     # Django admin 注册
├── serializers.py               # DRF 序列化器
├── views.py                     # API 视图
├── services.py                  # FileProcessingService
├── tasks.py                     # Celery 任务
├── urls.py                      # URL 路由
├── processors/
│   ├── __init__.py
│   ├── base.py                  # FileProcessor 抽象基类
│   ├── excel.py                 # ExcelProcessor
│   ├── word.py                  # WordProcessor
│   └── pdf.py                   # PDFProcessor
├── ai/
│   ├── __init__.py
│   ├── summarizer.py            # DataSummarizer
│   └── query.py                 # NaturalLanguageQuery
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_processors.py
    ├── test_services.py
    └── test_views.py
```

### 前端新增/修改文件

```
omni_desk_frontend/src/
├── shared/
│   ├── api/
│   │   └── fileProcessing.js              # 新增：API 层
│   ├── components/
│   │   └── file-processing/               # 新增目录
│   │       ├── FileUploadSection.jsx      # 上传组件
│   │       ├── ProcessingStatus.jsx       # 状态组件
│   │       ├── PreviewSection.jsx         # 预览组件
│   │       ├── AIAnalysisSection.jsx      # AI 分析组件
│   │       ├── ExportSection.jsx          # 导出组件
│   │       └── __tests__/
│   │           └── PreviewSection.test.jsx
│   └── pages/
│       └── FileAnalysisPage.jsx           # 修改：完全重构
```

---

## Task 1: 创建 file_processing Django app 基础结构

**Files:**
- Create: `omni_desk_backend/file_processing/__init__.py`
- Create: `omni_desk_backend/file_processing/apps.py`

**Interfaces:**
- Consumes: Django 框架
- Produces: Django app 配置

- [ ] **Step 1: 创建 app 目录和 __init__.py**

```bash
cd /home/fz/project/OmniDesk/omni_desk_backend
mkdir -p file_processing/processors file_processing/ai file_processing/tests
touch file_processing/__init__.py file_processing/processors/__init__.py file_processing/ai/__init__.py file_processing/tests/__init__.py
```

- [ ] **Step 2: 创建 apps.py**

```python
# omni_desk_backend/file_processing/apps.py

from django.apps import AppConfig


class FileProcessingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'file_processing'
    verbose_name = '文件处理'
```

- [ ] **Step 3: 验证 app 创建成功**

```bash
cd /home/fz/project/OmniDesk
python manage.py app_config file_processing
```

Expected: 无报错，显示 app 配置信息

- [ ] **Step 4: 提交**

```bash
git add omni_desk_backend/file_processing/
git commit -m "feat(file_processing): create Django app skeleton"
```

---

## Task 2: 创建数据模型

**Files:**
- Create: `omni_desk_backend/file_processing/models.py`
- Test: `omni_desk_backend/file_processing/tests/test_models.py`

**Interfaces:**
- Consumes: Django ORM, UUID
- Produces: UploadedFile, ProcessingResult, AIAnalysis 模型

- [ ] **Step 1: 编写模型测试**

```python
# omni_desk_backend/file_processing/tests/test_models.py

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from file_processing.models import UploadedFile, ProcessingResult, AIAnalysis
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestUploadedFile:
    
    def test_create_uploaded_file(self):
        user = User.objects.create_user(username='test', password='test')
        file = SimpleUploadedFile("test.xlsx", b"file content")
        
        uploaded = UploadedFile.objects.create(
            user=user,
            original_filename='test.xlsx',
            file=file,
            file_size=12,
            mime_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        assert uploaded.status == 'pending'
        assert uploaded.original_filename == 'test.xlsx'
        assert uploaded.user == user


@pytest.mark.django_db
class TestProcessingResult:
    
    def test_create_processing_result(self):
        user = User.objects.create_user(username='test', password='test')
        file = SimpleUploadedFile("test.xlsx", b"file content")
        uploaded = UploadedFile.objects.create(
            user=user,
            original_filename='test.xlsx',
            file=file,
            file_size=12,
            mime_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        result = ProcessingResult.objects.create(
            file=uploaded,
            content_text='test content',
            content_markdown='# test',
            row_count=10,
            column_count=5
        )
        
        assert result.file == uploaded
        assert result.row_count == 10
        assert uploaded.result == result


@pytest.mark.django_db
class TestAIAnalysis:
    
    def test_create_ai_analysis(self):
        user = User.objects.create_user(username='test', password='test')
        file = SimpleUploadedFile("test.xlsx", b"file content")
        uploaded = UploadedFile.objects.create(
            user=user,
            original_filename='test.xlsx',
            file=file,
            file_size=12,
            mime_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        analysis = AIAnalysis.objects.create(
            file=uploaded,
            analysis_type='summary',
            result_text='共 10 行数据',
            result_data={'row_count': 10}
        )
        
        assert analysis.file == uploaded
        assert analysis.analysis_type == 'summary'
        assert uploaded.analyses.count() == 1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/fz/project/OmniDesk
pytest omni_desk_backend/file_processing/tests/test_models.py -v
```

Expected: FAIL - "ModuleNotFoundError: No module named 'file_processing.models'"

- [ ] **Step 3: 实现数据模型**

```python
# omni_desk_backend/file_processing/models.py

import uuid
from django.db import models
from django.conf import settings


class UploadedFile(models.Model):
    """上传文件元数据"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='uploaded_files'
    )
    original_filename = models.CharField(max_length=255)
    file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    file_size = models.BigIntegerField(help_text='文件大小（字节）')
    mime_type = models.CharField(max_length=100)
    
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('processing', '处理中'),
        ('completed', '已完成'),
        ('failed', '失败'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    
    sheet_count = models.IntegerField(default=0, help_text='Excel: Sheet 数量')
    page_count = models.IntegerField(default=0, help_text='PDF/Word: 页数')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = '上传文件'
        verbose_name_plural = '上传文件'
    
    def __str__(self):
        return f"{self.original_filename} ({self.status})"


class ProcessingResult(models.Model):
    """文件处理结果"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.OneToOneField(
        UploadedFile, 
        on_delete=models.CASCADE, 
        related_name='result'
    )
    
    content_text = models.TextField(blank=True, help_text='纯文本（用于 AI 分析）')
    content_markdown = models.TextField(blank=True, help_text='Markdown 格式')
    content_json = models.JSONField(blank=True, default=dict, help_text='结构化数据')
    
    sheets_data = models.JSONField(blank=True, default=list, help_text='Excel Sheet 数据')
    
    row_count = models.IntegerField(default=0)
    column_count = models.IntegerField(default=0)
    
    processed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = '处理结果'
        verbose_name_plural = '处理结果'
    
    def __str__(self):
        return f"Result for {self.file.original_filename}"


class AIAnalysis(models.Model):
    """AI 分析结果"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.ForeignKey(
        UploadedFile, 
        on_delete=models.CASCADE, 
        related_name='analyses'
    )
    
    ANALYSIS_TYPES = [
        ('summary', '数据摘要'),
        ('statistics', '统计分析'),
        ('quality', '数据质量'),
        ('query', '自然语言查询'),
    ]
    analysis_type = models.CharField(max_length=20, choices=ANALYSIS_TYPES)
    
    query_text = models.TextField(blank=True, help_text='用户查询（仅 query 类型）')
    result_text = models.TextField(help_text='AI 生成的结果')
    result_data = models.JSONField(blank=True, default=dict, help_text='结构化结果')
    
    model_used = models.CharField(max_length=100, blank=True, help_text='Ollama 模型名')
    tokens_used = models.IntegerField(default=0)
    processing_time_ms = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'AI 分析'
        verbose_name_plural = 'AI 分析'
    
    def __str__(self):
        return f"{self.get_analysis_type_display()} - {self.file.original_filename}"
```

- [ ] **Step 4: 运行迁移**

```bash
cd /home/fz/project/OmniDesk
python manage.py makemigrations file_processing
python manage.py migrate
```

- [ ] **Step 5: 运行测试确认通过**

```bash
pytest omni_desk_backend/file_processing/tests/test_models.py -v
```

Expected: PASS (3 tests)

- [ ] **Step 6: 提交**

```bash
git add omni_desk_backend/file_processing/models.py omni_desk_backend/file_processing/tests/test_models.py
git commit -m "feat(file_processing): add data models (UploadedFile, ProcessingResult, AIAnalysis)"
```

---

## Task 3: 实现 ExcelProcessor

**Files:**
- Create: `omni_desk_backend/file_processing/processors/base.py`
- Create: `omni_desk_backend/file_processing/processors/excel.py`
- Test: `omni_desk_backend/file_processing/tests/test_processors.py`

**Interfaces:**
- Consumes: openpyxl, pandas
- Produces: ExcelProcessor 类，包含 extract_text, extract_markdown, extract_structured, get_metadata 方法

- [ ] **Step 1: 安装依赖**

```bash
cd /home/fz/project/OmniDesk
conda run -n omni_desk pip install openpyxl pandas python-docx pdfplumber mammoth
```

- [ ] **Step 2: 创建测试夹具文件**

创建简单的 Excel 测试文件：

```python
# tests/fixtures/create_test_files.py

import openpyxl
from openpyxl import Workbook
import os

os.makedirs('tests/fixtures', exist_ok=True)

# 创建简单 Excel
wb = Workbook()
ws = wb.active
ws.title = "Sheet1"
ws.append(['姓名', '年龄', '城市'])
ws.append(['张三', 25, '北京'])
ws.append(['李四', 30, '上海'])
ws.append(['王五', 28, '北京'])
wb.save('tests/fixtures/simple.xlsx')

# 创建多 Sheet Excel
wb2 = Workbook()
ws1 = wb2.active
ws1.title = "销售数据"
ws1.append(['月份', '销售额', '成本'])
ws1.append(['1月', 10000, 6000])
ws1.append(['2月', 15000, 8000])

ws2 = wb2.create_sheet("员工信息")
ws2.append(['姓名', '部门', '薪资'])
ws2.append(['张三', '销售', 8000])
wb2.save('tests/fixtures/multi_sheet.xlsx')

print("Test files created successfully")
```

运行：`python tests/fixtures/create_test_files.py`

- [ ] **Step 3: 编写 ExcelProcessor 测试**

```python
# omni_desk_backend/file_processing/tests/test_processors.py

import pytest
from file_processing.processors.excel import ExcelProcessor


class TestExcelProcessor:
    
    def test_extract_text_simple(self):
        processor = ExcelProcessor()
        text = processor.extract_text('tests/fixtures/simple.xlsx')
        assert 'Sheet1' in text
        assert '张三' in text
        assert '25' in text
    
    def test_extract_markdown_table(self):
        processor = ExcelProcessor()
        md = processor.extract_markdown('tests/fixtures/simple.xlsx')
        assert '## Sheet1' in md
        assert '| 姓名 | 年龄 | 城市 |' in md
        assert '| --- | --- | --- |' in md
        assert '| 张三 | 25 | 北京 |' in md
    
    def test_extract_structured_single_sheet(self):
        processor = ExcelProcessor()
        data = processor.extract_structured('tests/fixtures/simple.xlsx')
        assert data['sheet_count'] == 1
        assert len(data['sheets']) == 1
        assert data['sheets'][0]['name'] == 'Sheet1'
        assert data['sheets'][0]['row_count'] == 3
        assert data['sheets'][0]['column_count'] == 3
    
    def test_extract_structured_multi_sheet(self):
        processor = ExcelProcessor()
        data = processor.extract_structured('tests/fixtures/multi_sheet.xlsx')
        assert data['sheet_count'] == 2
        assert data['sheets'][0]['name'] == '销售数据'
        assert data['sheets'][1]['name'] == '员工信息'
    
    def test_get_metadata(self):
        processor = ExcelProcessor()
        metadata = processor.get_metadata('tests/fixtures/multi_sheet.xlsx')
        assert metadata['sheet_count'] == 2
        assert '销售数据' in metadata['sheet_names']
        assert '员工信息' in metadata['sheet_names']
```

- [ ] **Step 4: 运行测试确认失败**

```bash
pytest omni_desk_backend/file_processing/tests/test_processors.py::TestExcelProcessor -v
```

Expected: FAIL - "ModuleNotFoundError"

- [ ] **Step 5: 实现抽象基类**

```python
# omni_desk_backend/file_processing/processors/base.py

from abc import ABC, abstractmethod
from typing import Dict, Any


class FileProcessor(ABC):
    """文件处理器抽象基类"""
    
    @abstractmethod
    def extract_text(self, file_path: str) -> str:
        """提取纯文本（用于 AI 分析）"""
        pass
    
    @abstractmethod
    def extract_markdown(self, file_path: str) -> str:
        """提取 Markdown 格式"""
        pass
    
    @abstractmethod
    def extract_structured(self, file_path: str) -> Dict[str, Any]:
        """提取结构化数据（JSON）"""
        pass
    
    @abstractmethod
    def get_metadata(self, file_path: str) -> Dict[str, Any]:
        """获取文件元数据（页数、Sheet 数等）"""
        pass
```

- [ ] **Step 6: 实现 ExcelProcessor**

```python
# omni_desk_backend/file_processing/processors/excel.py

import openpyxl
from typing import Dict, Any
from .base import FileProcessor


class ExcelProcessor(FileProcessor):
    """Excel 文件处理器"""
    
    def extract_text(self, file_path: str) -> str:
        """提取 Excel 文本（所有 Sheet 拼接）"""
        wb = openpyxl.load_workbook(file_path, data_only=True)
        text_parts = []
        
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            text_parts.append(f"# {sheet_name}\n")
            
            for row in ws.iter_rows(values_only=True):
                row_text = '\t'.join(str(cell) if cell is not None else '' for cell in row)
                text_parts.append(row_text)
            text_parts.append('\n')
        
        return '\n'.join(text_parts)
    
    def extract_markdown(self, file_path: str) -> str:
        """提取 Markdown 表格"""
        wb = openpyxl.load_workbook(file_path, data_only=True)
        md_parts = []
        
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            md_parts.append(f"## {sheet_name}\n\n")
            
            data = list(ws.iter_rows(values_only=True))
            if not data:
                continue
            
            headers = data[0]
            md_parts.append('| ' + ' | '.join(str(h) if h else '' for h in headers) + ' |\n')
            md_parts.append('| ' + ' | '.join('---' for _ in headers) + ' |\n')
            
            for row in data[1:]:
                md_parts.append('| ' + ' | '.join(str(cell) if cell else '' for cell in row) + ' |\n')
            
            md_parts.append('\n')
        
        return ''.join(md_parts)
    
    def extract_structured(self, file_path: str) -> Dict[str, Any]:
        """提取结构化数据（多 Sheet）"""
        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheets = []
        
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            data = list(ws.iter_rows(values_only=True))
            
            if not data:
                continue
            
            headers = data[0]
            rows = data[1:]
            
            sheets.append({
                'name': sheet_name,
                'headers': [str(h) if h else f'列{i+1}' for i, h in enumerate(headers)],
                'data': [[str(cell) if cell is not None else '' for cell in row] for row in rows],
                'row_count': len(rows),
                'column_count': len(headers),
            })
        
        return {
            'sheet_count': len(sheets),
            'sheets': sheets,
        }
    
    def get_metadata(self, file_path: str) -> Dict[str, Any]:
        """获取 Excel 元数据"""
        wb = openpyxl.load_workbook(file_path, read_only=True)
        return {
            'sheet_count': len(wb.sheetnames),
            'sheet_names': wb.sheetnames,
        }
```

- [ ] **Step 7: 运行测试确认通过**

```bash
pytest omni_desk_backend/file_processing/tests/test_processors.py::TestExcelProcessor -v
```

Expected: PASS (5 tests)

- [ ] **Step 8: 提交**

```bash
git add omni_desk_backend/file_processing/processors/
git add tests/fixtures/
git commit -m "feat(file_processing): implement ExcelProcessor with multi-sheet support"
```

---

**计划文档过长，已保存到**：`docs/superpowers/plans/2026-07-11-file-processing.md`

完整计划包含 16 个主要任务，涵盖：
- 后端：Django app、数据模型、3 个文件处理器、服务层、AI 模块、Celery 任务、API 视图
- 前端：API 层、5 个 React 组件、页面重构
- 测试：单元测试、集成测试

**执行选项：**

**1. Subagent-Driven（推荐）** - 每个 Task 分派一个子代理，任务间审查，快速迭代

**2. Inline Execution** - 在当前会话中使用 executing-plans 执行，批量执行带检查点

您选择哪种方式？
