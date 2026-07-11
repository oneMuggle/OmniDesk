# 文件处理功能设计文档

**创建日期**：2026-07-11  
**状态**：设计完成，待实现  
**作者**：AI Assistant + User

---

## 1. 概述

### 1.1 背景与目标

OmniDesk 项目需要从 AionUi 项目移植完整的文档处理和表格处理功能。现有文件处理功能（`documents/file_processing.py`、`office_assistant`）暂不使用，可以进行大规模重构。

**核心目标**：
- 完整移植 AionUi 的文档/表格处理能力
- 后端 Python/Django 实现（服务端处理）
- 服务端转换 + 前端渲染
- 扩展现有功能（重构 FileAnalysisPage）
- AI 数据摘要 + 自然语言查询
- 仅查看 + 导出（无编辑功能）
- 创建统一的文件处理服务层，完全替代现有分散实现

### 1.2 支持的文件格式

| 格式 | MIME 类型 | 处理能力 |
|------|----------|---------|
| Excel (.xlsx) | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet | 多 Sheet、表格数据提取、统计 |
| Excel (.xls) | application/vnd.ms-excel | 同上 |
| CSV (.csv) | text/csv | 单 Sheet、表格数据提取 |
| Word (.docx) | application/vnd.openxmlformats-officedocument.wordprocessingml.document | 文本提取、Markdown 转换 |
| Word (.doc) | application/msword | 同上 |
| PDF (.pdf) | application/pdf | 文本提取、表格提取、Markdown 转换 |

### 1.3 核心功能

1. **文件上传**：拖拽上传，支持多格式
2. **文件解析**：提取文本、表格、元数据
3. **格式转换**：Word/Excel/PDF ↔ Markdown
4. **数据预览**：多 Sheet 切换、表格展示、Markdown 渲染
5. **AI 分析**：数据摘要、统计信息、自然语言查询
6. **数据导出**：CSV、Excel、Markdown

---

## 2. 整体架构

### 2.1 系统架构图

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                      │
├─────────────────────────────────────────────────────────┤
│  FileAnalysisPage (重构)                                 │
│  ├─ FileUploadSection (拖拽上传)                         │
│  ├─ ProcessingStatus (处理状态)                          │
│  ├─ PreviewSection (数据预览)                            │
│  │  ├─ SheetTabs (多 Sheet 切换)                         │
│  │  ├─ DataTable (Ant Design Table)                      │
│  │  └─ MarkdownPreview (Markdown 渲染)                   │
│  ├─ AIAnalysisSection (AI 分析)                          │
│  │  ├─ SummaryPanel (数据摘要)                           │
│  │  └─ QueryPanel (自然语言查询)                         │
│  └─ ExportSection (导出功能)                             │
└─────────────────────────────────────────────────────────┘
                           ↓ API Calls
┌─────────────────────────────────────────────────────────┐
│              Backend (Django + Celery)                   │
├─────────────────────────────────────────────────────────┤
│  file_processing app (新建)                              │
│  ├─ Views (API 端点)                                     │
│  │  ├─ POST /api/file/upload/                           │
│  │  ├─ GET  /api/file/{id}/preview/                     │
│  │  ├─ POST /api/file/{id}/analyze/                     │
│  │  ├─ POST /api/file/{id}/query/                       │
│  │  └─ GET  /api/file/{id}/export/{format}/             │
│  ├─ Services (业务逻辑)                                  │
│  │  ├─ FileProcessingService                             │
│  │  └─ ConversionService                                 │
│  ├─ Processors (文件解析)                                │
│  │  ├─ ExcelProcessor (openpyxl + pandas)               │
│  │  ├─ WordProcessor (python-docx + mammoth)            │
│  │  ├─ PDFProcessor (pdfplumber + pypdf)                │
│  │  └─ MarkdownProcessor                                │
│  ├─ Converters (格式转换)                                │
│  │  ├─ WordMarkdownConverter (Word ↔ Markdown)          │
│  │  ├─ ExcelMarkdownConverter (Excel ↔ Markdown)        │
│  │  └─ PDFMarkdownConverter (PDF → Markdown)            │
│  ├─ AI Module (AI 分析)                                  │
│  │  ├─ DataSummarizer (数据统计)                         │
│  │  ├─ NaturalLanguageQuery (NL 查询)                   │
│  │  └─ DataQualityAnalyzer (数据质量)                   │
│  └─ Models (数据模型)                                    │
│     ├─ UploadedFile (文件元数据)                         │
│     ├─ ProcessingResult (处理结果)                       │
│     └─ AIAnalysis (AI 分析结果)                          │
├─────────────────────────────────────────────────────────┤
│  Celery Tasks (异步处理)                                 │
│  ├─ process_file_task (文件解析)                          │
│  ├─ convert_file_task (格式转换)                          │
│  └─ analyze_file_task (AI 分析)                           │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│              Storage & External Services                 │
├─────────────────────────────────────────────────────────┤
│  Media Storage: media/uploads/{yyyy}/{mm}/{uuid}/        │
│  Database: PostgreSQL (文件元数据、处理结果)              │
│  Cache: Redis (处理进度、临时数据)                        │
│  LLM: Ollama (AI 分析)                                  │
└─────────────────────────────────────────────────────────┘
```

### 2.2 核心设计原则

1. **单一职责**：每个 Processor 只负责一种文件类型的解析
2. **开闭原则**：添加新格式只需新增 Processor，不修改现有代码
3. **依赖倒置**：上层服务依赖抽象接口，不依赖具体实现
4. **异步处理**：大文件处理通过 Celery 异步执行
5. **错误隔离**：文件处理失败不影响其他功能

### 2.3 技术栈

**后端新增依赖**：
```python
# requirements.in
openpyxl==3.1.2          # Excel 读写
pandas==2.1.4            # 数据分析
python-docx==1.1.0       # Word 文档处理
pdfplumber==0.10.3       # PDF 文本提取
mammoth==1.6.0           # Word → HTML → Markdown
markdown==3.5.1          # Markdown 生成
```

**前端**：无新增依赖（使用现有 Ant Design Table + react-markdown）

---

## 3. 后端详细设计

### 3.1 数据模型

#### UploadedFile（上传文件元数据）

```python
class UploadedFile(models.Model):
    """上传文件元数据"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    original_filename = models.CharField(max_length=255)
    file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    file_size = models.BigIntegerField()  # bytes
    mime_type = models.CharField(max_length=100)
    
    # 处理状态
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('processing', '处理中'),
        ('completed', '已完成'),
        ('failed', '失败'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    
    # 文件元信息
    sheet_count = models.IntegerField(default=0)  # Excel: Sheet 数量
    page_count = models.IntegerField(default=0)   # PDF/Word: 页数
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
```

#### ProcessingResult（处理结果）

```python
class ProcessingResult(models.Model):
    """文件处理结果"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    file = models.OneToOneField(UploadedFile, on_delete=models.CASCADE, related_name='result')
    
    # 提取的内容
    content_text = models.TextField(blank=True)      # 纯文本（用于 AI 分析）
    content_markdown = models.TextField(blank=True)  # Markdown 格式
    content_json = models.JSONField(blank=True)      # 结构化数据（表格用）
    
    # Excel 特有
    sheets_data = models.JSONField(blank=True)  # [{name, data, headers}]
    
    # 统计信息
    row_count = models.IntegerField(default=0)
    column_count = models.IntegerField(default=0)
    
    processed_at = models.DateTimeField(auto_now_add=True)
```

#### AIAnalysis（AI 分析结果）

```python
class AIAnalysis(models.Model):
    """AI 分析结果"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    file = models.ForeignKey(UploadedFile, on_delete=models.CASCADE, related_name='analyses')
    
    # 分析类型
    ANALYSIS_TYPES = [
        ('summary', '数据摘要'),
        ('statistics', '统计分析'),
        ('quality', '数据质量'),
        ('query', '自然语言查询'),
    ]
    analysis_type = models.CharField(max_length=20, choices=ANALYSIS_TYPES)
    
    # 输入和输出
    query_text = models.TextField(blank=True)      # 用户查询（仅 query 类型）
    result_text = models.TextField()                # AI 生成的结果
    result_data = models.JSONField(blank=True)      # 结构化结果（统计数据等）
    
    # 元信息
    model_used = models.CharField(max_length=100)   # Ollama 模型名
    tokens_used = models.IntegerField(default=0)
    processing_time_ms = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
```

### 3.2 文件处理器 (Processors)

#### 抽象基类

```python
# file_processing/processors/base.py

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

#### ExcelProcessor

```python
# file_processing/processors/excel.py

import openpyxl
import pandas as pd
from typing import Dict, Any, List

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
                'headers': list(headers),
                'data': [list(row) for row in rows],
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

#### WordProcessor

```python
# file_processing/processors/word.py

from docx import Document
import mammoth

class WordProcessor(FileProcessor):
    """Word 文档处理器"""
    
    def extract_text(self, file_path: str) -> str:
        """提取 Word 文本"""
        doc = Document(file_path)
        return '\n\n'.join([p.text for p in doc.paragraphs if p.text.strip()])
    
    def extract_markdown(self, file_path: str) -> str:
        """Word → Markdown（使用 mammoth）"""
        with open(file_path, 'rb') as f:
            result = mammoth.convert_to_markdown(f)
            return result.value
    
    def extract_structured(self, file_path: str) -> Dict[str, Any]:
        """提取 Word 结构化数据"""
        doc = Document(file_path)
        return {
            'paragraphs': [p.text for p in doc.paragraphs if p.text.strip()],
            'tables': [
                [[cell.text for cell in row.cells] for row in table.rows]
                for table in doc.tables
            ],
        }
    
    def get_metadata(self, file_path: str) -> Dict[str, Any]:
        """获取 Word 元数据"""
        doc = Document(file_path)
        return {
            'page_count': len(doc.sections),
            'paragraph_count': len(doc.paragraphs),
        }
```

#### PDFProcessor

```python
# file_processing/processors/pdf.py

import pdfplumber

class PDFProcessor(FileProcessor):
    """PDF 文件处理器"""
    
    def extract_text(self, file_path: str) -> str:
        """提取 PDF 文本"""
        with pdfplumber.open(file_path) as pdf:
            return '\n\n'.join([page.extract_text() or '' for page in pdf.pages])
    
    def extract_markdown(self, file_path: str) -> str:
        """PDF → Markdown（提取文本 + 表格）"""
        with pdfplumber.open(file_path) as pdf:
            md_parts = []
            
            for i, page in enumerate(pdf.pages, 1):
                md_parts.append(f"## 第 {i} 页\n\n")
                
                text = page.extract_text()
                if text:
                    md_parts.append(text + '\n\n')
                
                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue
                    
                    headers = table[0]
                    md_parts.append('| ' + ' | '.join(str(h) or '' for h in headers) + ' |\n')
                    md_parts.append('| ' + ' | '.join('---' for _ in headers) + ' |\n')
                    
                    for row in table[1:]:
                        md_parts.append('| ' + ' | '.join(str(cell) or '' for cell in row) + ' |\n')
                    
                    md_parts.append('\n')
            
            return ''.join(md_parts)
    
    def extract_structured(self, file_path: str) -> Dict[str, Any]:
        """提取 PDF 结构化数据"""
        with pdfplumber.open(file_path) as pdf:
            pages = []
            
            for i, page in enumerate(pdf.pages, 1):
                pages.append({
                    'page_number': i,
                    'text': page.extract_text() or '',
                    'tables': page.extract_tables() or [],
                })
            
            return {
                'page_count': len(pdf.pages),
                'pages': pages,
            }
    
    def get_metadata(self, file_path: str) -> Dict[str, Any]:
        """获取 PDF 元数据"""
        with pdfplumber.open(file_path) as pdf:
            return {
                'page_count': len(pdf.pages),
            }
```

### 3.3 业务服务层

```python
# file_processing/services.py

from .processors import ExcelProcessor, WordProcessor, PDFProcessor
from .models import UploadedFile, ProcessingResult

class FileProcessingService:
    """文件处理业务逻辑"""
    
    PROCESSORS = {
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ExcelProcessor,
        'application/vnd.ms-excel': ExcelProcessor,
        'text/csv': ExcelProcessor,
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': WordProcessor,
        'application/msword': WordProcessor,
        'application/pdf': PDFProcessor,
    }
    
    def __init__(self):
        self.processors = {}
    
    def get_processor(self, mime_type: str):
        """获取对应的文件处理器"""
        processor_class = self.PROCESSORS.get(mime_type)
        if not processor_class:
            raise ValueError(f"不支持的文件类型: {mime_type}")
        
        if mime_type not in self.processors:
            self.processors[mime_type] = processor_class()
        
        return self.processors[mime_type]
    
    def process_file(self, uploaded_file: UploadedFile) -> ProcessingResult:
        """处理上传的文件"""
        processor = self.get_processor(uploaded_file.mime_type)
        file_path = uploaded_file.file.path
        
        text = processor.extract_text(file_path)
        markdown = processor.extract_markdown(file_path)
        structured = processor.extract_structured(file_path)
        metadata = processor.get_metadata(file_path)
        
        result = ProcessingResult.objects.create(
            file=uploaded_file,
            content_text=text,
            content_markdown=markdown,
            content_json=structured,
            sheets_data=structured.get('sheets', []),
            row_count=sum(sheet.get('row_count', 0) for sheet in structured.get('sheets', [])),
            column_count=max((sheet.get('column_count', 0) for sheet in structured.get('sheets', [])), default=0),
        )
        
        uploaded_file.status = 'completed'
        uploaded_file.sheet_count = metadata.get('sheet_count', 0)
        uploaded_file.page_count = metadata.get('page_count', 0)
        uploaded_file.save()
        
        return result
```

### 3.4 AI 分析模块

#### DataSummarizer

```python
# file_processing/ai/summarizer.py

import pandas as pd
from typing import Dict, Any, List

class DataSummarizer:
    """数据摘要生成器"""
    
    def summarize_table(self, sheets_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成表格数据摘要"""
        summaries = []
        
        for sheet in sheets_data:
            df = pd.DataFrame(sheet['data'], columns=sheet['headers'])
            
            summary = {
                'sheet_name': sheet['name'],
                'row_count': len(df),
                'column_count': len(df.columns),
                'columns': [],
            }
            
            for col in df.columns:
                col_info = {
                    'name': col,
                    'type': str(df[col].dtype),
                    'null_count': int(df[col].isnull().sum()),
                    'unique_count': int(df[col].nunique()),
                }
                
                if pd.api.types.is_numeric_dtype(df[col]):
                    col_info.update({
                        'min': float(df[col].min()) if not df[col].empty else None,
                        'max': float(df[col].max()) if not df[col].empty else None,
                        'mean': float(df[col].mean()) if not df[col].empty else None,
                        'sum': float(df[col].sum()) if not df[col].empty else None,
                    })
                
                summary['columns'].append(col_info)
            
            summaries.append(summary)
        
        return {
            'sheet_count': len(sheets_data),
            'total_rows': sum(s['row_count'] for s in summaries),
            'summaries': summaries,
        }
```

#### NaturalLanguageQuery

```python
# file_processing/ai/query.py

from ollama import Client
import pandas as pd
from typing import Dict, Any

class NaturalLanguageQuery:
    """自然语言查询"""
    
    def __init__(self):
        self.client = Client(host='http://localhost:11434')
    
    def query(self, question: str, context: Dict[str, Any]) -> str:
        """用自然语言查询表格数据"""
        prompt = self._build_prompt(question, context)
        
        response = self.client.chat(
            model='qwen2.5:7b',
            messages=[{'role': 'user', 'content': prompt}]
        )
        
        return response['message']['content']
    
    def _build_prompt(self, question: str, context: Dict[str, Any]) -> str:
        """构建 LLM 提示"""
        sheets = context.get('sheets_data', [])
        if not sheets:
            return "没有表格数据可供分析。"
        
        sheet = sheets[0]
        df = pd.DataFrame(sheet['data'][:100], columns=sheet['headers'])
        markdown_table = df.to_markdown(index=False)
        
        prompt = f"""你是一个数据分析助手。请根据以下表格数据回答用户的问题。

表格数据（Sheet: {sheet['name']}）:
{markdown_table}

用户问题: {question}

请用中文回答，简洁明了。如果数据不足以回答问题，请说明。"""
        
        return prompt
```

### 3.5 API 视图

```python
# file_processing/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import UploadedFile
from .services import FileProcessingService
from .ai.summarizer import DataSummarizer
from .ai.query import NaturalLanguageQuery
import mimetypes

class FileProcessingViewSet(viewsets.ModelViewSet):
    """文件处理 API"""
    
    queryset = UploadedFile.objects.all()
    
    @action(detail=False, methods=['post'])
    def upload(self, request):
        """上传文件"""
        file = request.FILES.get('file')
        if not file:
            return Response({'error': '未提供文件'}, status=status.HTTP_400_BAD_REQUEST)
        
        mime_type, _ = mimetypes.guess_type(file.name)
        if not mime_type:
            mime_type = 'application/octet-stream'
        
        uploaded_file = UploadedFile.objects.create(
            user=request.user,
            original_filename=file.name,
            file=file,
            file_size=file.size,
            mime_type=mime_type,
        )
        
        from .tasks import process_file_task
        process_file_task.delay(str(uploaded_file.id))
        
        return Response({
            'id': str(uploaded_file.id),
            'status': uploaded_file.status,
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """获取文件预览数据"""
        uploaded_file = self.get_object()
        
        if uploaded_file.status != 'completed':
            return Response({
                'status': uploaded_file.status,
                'error': uploaded_file.error_message,
            })
        
        result = uploaded_file.result
        
        return Response({
            'file_id': str(uploaded_file.id),
            'filename': uploaded_file.original_filename,
            'mime_type': uploaded_file.mime_type,
            'sheet_count': uploaded_file.sheet_count,
            'sheets': result.sheets_data,
            'markdown': result.content_markdown,
        })
    
    @action(detail=True, methods=['post'])
    def analyze(self, request, pk=None):
        """AI 数据分析"""
        uploaded_file = self.get_object()
        
        if uploaded_file.status != 'completed':
            return Response({'error': '文件尚未处理完成'}, status=status.HTTP_400_BAD_REQUEST)
        
        result = uploaded_file.result
        summarizer = DataSummarizer()
        summary = summarizer.summarize_table(result.sheets_data)
        
        from .models import AIAnalysis
        analysis = AIAnalysis.objects.create(
            file=uploaded_file,
            analysis_type='summary',
            result_text=f"共 {summary['sheet_count']} 个 Sheet，{summary['total_rows']} 行数据",
            result_data=summary,
        )
        
        return Response({
            'analysis_id': str(analysis.id),
            'summary': summary,
        })
    
    @action(detail=True, methods=['post'])
    def query(self, request, pk=None):
        """自然语言查询"""
        uploaded_file = self.get_object()
        
        if uploaded_file.status != 'completed':
            return Response({'error': '文件尚未处理完成'}, status=status.HTTP_400_BAD_REQUEST)
        
        question = request.data.get('question')
        if not question:
            return Response({'error': '未提供问题'}, status=status.HTTP_400_BAD_REQUEST)
        
        result = uploaded_file.result
        nl_query = NaturalLanguageQuery()
        answer = nl_query.query(question, {'sheets_data': result.sheets_data})
        
        from .models import AIAnalysis
        analysis = AIAnalysis.objects.create(
            file=uploaded_file,
            analysis_type='query',
            query_text=question,
            result_text=answer,
        )
        
        return Response({
            'analysis_id': str(analysis.id),
            'question': question,
            'answer': answer,
        })
    
    @action(detail=True, methods=['get'])
    def export(self, request, pk=None, format=None):
        """导出文件"""
        uploaded_file = self.get_object()
        
        if uploaded_file.status != 'completed':
            return Response({'error': '文件尚未处理完成'}, status=status.HTTP_400_BAD_REQUEST)
        
        result = uploaded_file.result
        
        if format == 'csv':
            content = result.content_text
            return HttpResponse(content, content_type='text/csv')
        elif format == 'markdown':
            content = result.content_markdown
            return HttpResponse(content, content_type='text/markdown')
        elif format == 'excel':
            # TODO: 使用 openpyxl 生成 Excel
            return Response({'error': 'Excel 导出尚未实现'}, status=status.HTTP_501_NOT_IMPLEMENTED)
        
        return Response({'error': f'不支持的导出格式: {format}'}, status=status.HTTP_400_BAD_REQUEST)
```

### 3.6 Celery 任务

```python
# file_processing/tasks.py

from celery import shared_task
from .services import FileProcessingService
from .models import UploadedFile

@shared_task(bind=True, max_retries=3)
def process_file_task(self, file_id):
    """异步处理文件"""
    try:
        uploaded_file = UploadedFile.objects.get(id=file_id)
        uploaded_file.status = 'processing'
        uploaded_file.save()
        
        service = FileProcessingService()
        service.process_file(uploaded_file)
        
    except Exception as exc:
        uploaded_file.status = 'failed'
        uploaded_file.error_message = str(exc)
        uploaded_file.save()
        
        raise self.retry(exc=exc, countdown=60)
```

---

## 4. 前端详细设计

### 4.1 页面结构

**路由**：`/file-analysis`（保留现有路由，完全重构组件）

**组件树**：
```
FileAnalysisPage
├─ FileUploadSection (上传区域)
│  ├─ DragDropZone (拖拽上传)
│  ├─ FileInput (点击上传)
│  └─ SupportedFormats (支持的格式提示)
│
├─ ProcessingStatus (处理状态)
│  ├─ ProgressBar (进度条)
│  └─ ErrorMessage (错误信息)
│
├─ PreviewSection (预览区域)
│  ├─ SheetTabs (多 Sheet 切换，仅 Excel)
│  ├─ DataTable (Ant Design Table)
│  └─ MarkdownPreview (Markdown 渲染，Word/PDF)
│
├─ AIAnalysisSection (AI 分析区域)
│  ├─ SummaryPanel (数据摘要)
│  └─ QueryPanel (自然语言查询)
│
└─ ExportSection (导出区域)
   ├─ ExportCSV
   ├─ ExportExcel
   └─ ExportMarkdown
```

### 4.2 核心组件

#### FileAnalysisPage 主组件

```jsx
// omni_desk_frontend/src/shared/pages/FileAnalysisPage.jsx

import React, { useState, useCallback } from 'react';
import { Card, message } from 'antd';
import FileUploadSection from '../components/file-processing/FileUploadSection';
import ProcessingStatus from '../components/file-processing/ProcessingStatus';
import PreviewSection from '../components/file-processing/PreviewSection';
import AIAnalysisSection from '../components/file-processing/AIAnalysisSection';
import ExportSection from '../components/file-processing/ExportSection';
import { fileProcessingApi } from '../api/fileProcessing';

const FileAnalysisPage = () => {
  const [uploadedFile, setUploadedFile] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleFileUpload = useCallback(async (file) => {
    setLoading(true);
    setError(null);
    
    try {
      const uploadResult = await fileProcessingApi.upload(file);
      setUploadedFile(uploadResult);
      
      const preview = await pollProcessingStatus(uploadResult.id);
      setPreviewData(preview);
      
      const analysis = await fileProcessingApi.analyze(uploadResult.id);
      setAnalysisResult(analysis);
      
      message.success('文件处理成功');
    } catch (err) {
      setError(err.message);
      message.error('文件处理失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const pollProcessingStatus = async (fileId) => {
    const maxAttempts = 30;
    const interval = 1000;
    
    for (let i = 0; i < maxAttempts; i++) {
      const result = await fileProcessingApi.getPreview(fileId);
      
      if (result.status === 'completed') {
        return result;
      } else if (result.status === 'failed') {
        throw new Error(result.error || '处理失败');
      }
      
      await new Promise(resolve => setTimeout(resolve, interval));
    }
    
    throw new Error('处理超时');
  };

  const handleQuery = useCallback(async (question) => {
    if (!uploadedFile) return;
    
    try {
      const result = await fileProcessingApi.query(uploadedFile.id, question);
      return result.answer;
    } catch (err) {
      message.error('查询失败');
      throw err;
    }
  }, [uploadedFile]);

  return (
    <div className="file-analysis-page">
      <Card title="文件分析" style={{ marginBottom: 16 }}>
        <FileUploadSection 
          onFileUpload={handleFileUpload}
          disabled={loading}
        />
        
        <ProcessingStatus 
          file={uploadedFile}
          loading={loading}
          error={error}
        />
      </Card>

      {previewData && (
        <>
          <Card title="数据预览" style={{ marginBottom: 16 }}>
            <PreviewSection 
              data={previewData}
              mimeType={uploadedFile?.mime_type}
            />
          </Card>

          <Card title="AI 分析" style={{ marginBottom: 16 }}>
            <AIAnalysisSection 
              summary={analysisResult}
              onQuery={handleQuery}
            />
          </Card>

          <Card title="导出数据">
            <ExportSection 
              fileId={uploadedFile?.id}
              filename={uploadedFile?.original_filename}
            />
          </Card>
        </>
      )}
    </div>
  );
};

export default FileAnalysisPage;
```

#### FileUploadSection 组件

```jsx
// omni_desk_frontend/src/shared/components/file-processing/FileUploadSection.jsx

import React from 'react';
import { Upload, message, Typography } from 'antd';
import { InboxOutlined, FileExcelOutlined, FileWordOutlined, FilePdfOutlined } from '@ant-design/icons';

const { Dragger } = Upload;
const { Text } = Typography;

const SUPPORTED_FORMATS = [
  { ext: '.xlsx, .xls, .csv', icon: <FileExcelOutlined />, label: 'Excel 表格' },
  { ext: '.docx, .doc', icon: <FileWordOutlined />, label: 'Word 文档' },
  { ext: '.pdf', icon: <FilePdfOutlined />, label: 'PDF 文档' },
];

const FileUploadSection = ({ onFileUpload, disabled }) => {
  const uploadProps = {
    name: 'file',
    multiple: false,
    maxCount: 1,
    accept: '.xlsx,.xls,.csv,.docx,.doc,.pdf',
    showUploadList: false,
    disabled,
    beforeUpload: (file) => {
      const maxSize = 10 * 1024 * 1024;
      if (file.size > maxSize) {
        message.error('文件大小不能超过 10MB');
        return Upload.LIST_IGNORE;
      }
      
      onFileUpload(file);
      return false;
    },
  };

  return (
    <div className="file-upload-section">
      <Dragger {...uploadProps}>
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
        <p className="ant-upload-hint">
          支持格式：Excel (.xlsx, .xls, .csv)、Word (.docx, .doc)、PDF (.pdf)
        </p>
      </Dragger>

      <div style={{ marginTop: 16 }}>
        <Text type="secondary">支持的文件类型：</Text>
        <div style={{ marginTop: 8, display: 'flex', gap: 16 }}>
          {SUPPORTED_FORMATS.map((format, index) => (
            <div key={index}>
              {format.icon} <Text>{format.label}</Text>
              <br />
              <Text type="secondary" style={{ fontSize: 12 }}>{format.ext}</Text>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default FileUploadSection;
```

#### PreviewSection 组件

```jsx
// omni_desk_frontend/src/shared/components/file-processing/PreviewSection.jsx

import React, { useState } from 'react';
import { Tabs, Table, Typography } from 'antd';
import ReactMarkdown from 'react-markdown';

const { TabPane } = Tabs;
const { Text } = Typography;

const PreviewSection = ({ data, mimeType }) => {
  const [activeSheet, setActiveSheet] = useState(0);

  if (mimeType.includes('spreadsheet') || mimeType.includes('csv')) {
    const sheets = data.sheets || [];
    
    if (sheets.length === 0) {
      return <Text type="secondary">无数据</Text>;
    }

    const currentSheet = sheets[activeSheet];
    const columns = currentSheet.headers.map((header, index) => ({
      title: header || `列 ${index + 1}`,
      dataIndex: `col_${index}`,
      key: `col_${index}`,
      ellipsis: true,
    }));

    const dataSource = currentSheet.data.map((row, rowIndex) => {
      const record = { key: rowIndex };
      row.forEach((cell, colIndex) => {
        record[`col_${colIndex}`] = cell;
      });
      return record;
    });

    return (
      <div className="preview-section">
        {sheets.length > 1 && (
          <Tabs 
            activeKey={String(activeSheet)} 
            onChange={(key) => setActiveSheet(Number(key))}
          >
            {sheets.map((sheet, index) => (
              <TabPane tab={sheet.name} key={index} />
            ))}
          </Tabs>
        )}

        <Table
          columns={columns}
          dataSource={dataSource}
          pagination={{ 
            pageSize: 50,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 行`,
          }}
          scroll={{ x: 'max-content' }}
          size="small"
        />

        <div style={{ marginTop: 8 }}>
          <Text type="secondary">
            共 {currentSheet.row_count} 行，{currentSheet.column_count} 列
          </Text>
        </div>
      </div>
    );
  }

  if (mimeType.includes('word') || mimeType.includes('pdf')) {
    return (
      <div className="preview-section markdown-preview">
        <ReactMarkdown>{data.markdown}</ReactMarkdown>
      </div>
    );
  }

  return <Text type="secondary">不支持的文件类型</Text>;
};

export default PreviewSection;
```

#### AIAnalysisSection 组件

```jsx
// omni_desk_frontend/src/shared/components/file-processing/AIAnalysisSection.jsx

import React, { useState } from 'react';
import { Card, Statistic, Row, Col, Input, Button, List, Typography, Space } from 'antd';
import { BarChartOutlined, SearchOutlined } from '@ant-design/icons';

const { TextArea } = Input;
const { Text, Title } = Typography;

const AIAnalysisSection = ({ summary, onQuery }) => {
  const [queryText, setQueryText] = useState('');
  const [queryResult, setQueryResult] = useState(null);
  const [queryLoading, setQueryLoading] = useState(false);

  const handleQuery = async () => {
    if (!queryText.trim()) return;
    
    setQueryLoading(true);
    try {
      const answer = await onQuery(queryText);
      setQueryResult(answer);
    } catch (err) {
      console.error('Query failed:', err);
    } finally {
      setQueryLoading(false);
    }
  };

  return (
    <div className="ai-analysis-section">
      {summary && (
        <div style={{ marginBottom: 24 }}>
          <Title level={5}>
            <BarChartOutlined /> 数据摘要
          </Title>
          
          <Row gutter={16}>
            <Col span={8}>
              <Statistic title="Sheet 数量" value={summary.sheet_count} />
            </Col>
            <Col span={8}>
              <Statistic title="总行数" value={summary.total_rows} />
            </Col>
          </Row>

          {summary.summaries.map((sheetSummary, index) => (
            <Card 
              key={index} 
              size="small" 
              title={sheetSummary.sheet_name}
              style={{ marginTop: 16 }}
            >
              <Row gutter={16}>
                <Col span={8}>
                  <Statistic title="行数" value={sheetSummary.row_count} />
                </Col>
                <Col span={8}>
                  <Statistic title="列数" value={sheetSummary.column_count} />
                </Col>
              </Row>

              <div style={{ marginTop: 16 }}>
                <Text strong>列详情：</Text>
                <List
                  size="small"
                  dataSource={sheetSummary.columns}
                  renderItem={(col) => (
                    <List.Item>
                      <Text>{col.name}</Text>
                      <Text type="secondary">
                        ({col.type}, {col.null_count} 空值, {col.unique_count} 唯一值)
                      </Text>
                      {col.mean !== undefined && (
                        <Text type="secondary">
                          ，平均: {col.mean.toFixed(2)}, 总和: {col.sum?.toFixed(2)}
                        </Text>
                      )}
                    </List.Item>
                  )}
                />
              </div>
            </Card>
          ))}
        </div>
      )}

      <div>
        <Title level={5}>
          <SearchOutlined /> 自然语言查询
        </Title>
        
        <Space direction="vertical" style={{ width: '100%' }}>
          <TextArea
            rows={3}
            value={queryText}
            onChange={(e) => setQueryText(e.target.value)}
            placeholder="输入您的问题，例如：哪个月份的销售额最高？"
            onPressEnter={(e) => e.ctrlKey && handleQuery()}
          />
          
          <Button 
            type="primary" 
            icon={<SearchOutlined />}
            loading={queryLoading}
            onClick={handleQuery}
          >
            查询 (Ctrl+Enter)
          </Button>

          {queryResult && (
            <Card size="small" title="查询结果">
              <Text>{queryResult}</Text>
            </Card>
          )}
        </Space>
      </div>
    </div>
  );
};

export default AIAnalysisSection;
```

#### ExportSection 组件

```jsx
// omni_desk_frontend/src/shared/components/file-processing/ExportSection.jsx

import React from 'react';
import { Button, Space, message } from 'antd';
import { FileExcelOutlined, FileTextOutlined } from '@ant-design/icons';
import { fileProcessingApi } from '../../api/fileProcessing';

const ExportSection = ({ fileId, filename }) => {
  const handleExport = async (format) => {
    try {
      const blob = await fileProcessingApi.export(fileId, format);
      
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${filename.replace(/\.[^/.]+$/, '')}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      message.success('导出成功');
    } catch (err) {
      message.error('导出失败');
    }
  };

  return (
    <Space>
      <Button 
        icon={<FileExcelOutlined />} 
        onClick={() => handleExport('csv')}
      >
        导出 CSV
      </Button>
      
      <Button 
        icon={<FileExcelOutlined />} 
        onClick={() => handleExport('excel')}
      >
        导出 Excel
      </Button>
      
      <Button 
        icon={<FileTextOutlined />} 
        onClick={() => handleExport('markdown')}
      >
        导出 Markdown
      </Button>
    </Space>
  );
};

export default ExportSection;
```

### 4.3 API 层

```javascript
// omni_desk_frontend/src/shared/api/fileProcessing.js

import axios from 'axios';

const API_BASE = '/api/file';

export const fileProcessingApi = {
  upload: async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await axios.post(`${API_BASE}/upload/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    
    return response.data;
  },

  getPreview: async (fileId) => {
    const response = await axios.get(`${API_BASE}/${fileId}/preview/`);
    return response.data;
  },

  analyze: async (fileId) => {
    const response = await axios.post(`${API_BASE}/${fileId}/analyze/`);
    return response.data;
  },

  query: async (fileId, question) => {
    const response = await axios.post(`${API_BASE}/${fileId}/query/`, { question });
    return response.data;
  },

  export: async (fileId, format) => {
    const response = await axios.get(`${API_BASE}/${fileId}/export/${format}/`, {
      responseType: 'blob',
    });
    return response.data;
  },
};
```

---

## 5. 数据流与错误处理

### 5.1 完整数据流

```
用户上传文件
    ↓
[1] POST /api/file/upload/
    ├─ 保存文件到 media/uploads/
    ├─ 创建 UploadedFile 记录 (status=pending)
    ├─ 触发 Celery 任务: process_file_task
    └─ 返回 {id, status}
    ↓
[2] 前端轮询 GET /api/file/{id}/preview/
    ├─ Celery 任务执行:
    │   ├─ 选择 Processor (Excel/Word/PDF)
    │   ├─ extract_text() → content_text
    │   ├─ extract_markdown() → content_markdown
    │   ├─ extract_structured() → content_json
    │   ├─ get_metadata() → sheet_count, page_count
    │   └─ 创建 ProcessingResult
    ├─ status: pending → processing → completed
    └─ 返回预览数据
    ↓
[3] 自动触发 POST /api/file/{id}/analyze/
    ├─ DataSummarizer 分析表格数据
    ├─ 生成统计信息（行数、列数、数值统计）
    ├─ 创建 AIAnalysis 记录
    └─ 返回摘要数据
    ↓
[4] 用户可选操作:
    ├─ 自然语言查询: POST /api/file/{id}/query/
    │   ├─ NaturalLanguageQuery 调用 Ollama
    │   ├─ 创建 AIAnalysis 记录 (type=query)
    │   └─ 返回 AI 回答
    └─ 导出: GET /api/file/{id}/export/{format}/
        ├─ CSV: content_text → text/csv
        ├─ Excel: sheets_data → xlsx
        └─ Markdown: content_markdown → text/markdown
```

### 5.2 错误处理策略

| 错误场景 | 处理方式 | 用户提示 |
|---------|---------|---------|
| 不支持的文件类型 | 上传时立即拒绝 | "不支持的文件格式，请上传 Excel/Word/PDF" |
| 文件过大 (>10MB) | 前端验证拦截 | "文件大小不能超过 10MB" |
| 文件解析失败 | Celery 任务捕获异常，status=failed | "文件解析失败：[具体原因]" |
| AI 分析超时 | 30 秒超时，返回降级结果 | "AI 分析超时，请重试" |
| Ollama 不可用 | 捕获连接错误 | "AI 服务不可用，请稍后重试" |
| 导出失败 | 返回 HTTP 500 | "导出失败，请重试" |

### 5.3 前端错误处理

```javascript
try {
  // API 调用
} catch (error) {
  if (error.response?.status === 413) {
    message.error('文件过大');
  } else if (error.response?.status === 415) {
    message.error('不支持的文件格式');
  } else if (error.code === 'ECONNABORTED') {
    message.error('请求超时，请重试');
  } else {
    message.error(error.response?.data?.error || '操作失败');
  }
}
```

---

## 6. 测试策略

### 6.1 后端测试

**单元测试**：

```python
# file_processing/tests/test_processors.py

import pytest
from file_processing.processors import ExcelProcessor, WordProcessor, PDFProcessor

class TestExcelProcessor:
    
    def test_extract_text_simple(self):
        processor = ExcelProcessor()
        text = processor.extract_text('tests/fixtures/simple.xlsx')
        assert 'Sheet1' in text
    
    def test_extract_markdown_table(self):
        processor = ExcelProcessor()
        md = processor.extract_markdown('tests/fixtures/simple.xlsx')
        assert '| 列1 | 列2 |' in md
    
    def test_extract_structured_multi_sheet(self):
        processor = ExcelProcessor()
        data = processor.extract_structured('tests/fixtures/multi_sheet.xlsx')
        assert data['sheet_count'] == 3


class TestWordProcessor:
    
    def test_extract_text(self):
        processor = WordProcessor()
        text = processor.extract_text('tests/fixtures/sample.docx')
        assert len(text) > 0


class TestPDFProcessor:
    
    def test_extract_text(self):
        processor = PDFProcessor()
        text = processor.extract_text('tests/fixtures/sample.pdf')
        assert len(text) > 0
```

**测试覆盖率目标**：
- Processors: 90%+
- Services: 85%+
- AI Module: 80%+
- Views: 85%+

### 6.2 前端测试

```javascript
// omni_desk_frontend/src/shared/components/file-processing/__tests__/PreviewSection.test.jsx

import { render, screen } from '@testing-library/react';
import PreviewSection from '../PreviewSection';

describe('PreviewSection', () => {
  
  it('renders Excel data as table', () => {
    const data = {
      sheets: [
        {
          name: 'Sheet1',
          headers: ['姓名', '年龄'],
          data: [['张三', 25]],
          row_count: 1,
          column_count: 2,
        }
      ]
    };
    
    render(<PreviewSection data={data} mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" />);
    
    expect(screen.getByText('姓名')).toBeInTheDocument();
    expect(screen.getByText('张三')).toBeInTheDocument();
  });
  
  it('renders multiple sheets as tabs', () => {
    const data = {
      sheets: [
        { name: 'Sheet1', headers: [], data: [], row_count: 0, column_count: 0 },
        { name: 'Sheet2', headers: [], data: [], row_count: 0, column_count: 0 },
      ]
    };
    
    render(<PreviewSection data={data} mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" />);
    
    expect(screen.getByText('Sheet1')).toBeInTheDocument();
    expect(screen.getByText('Sheet2')).toBeInTheDocument();
  });
});
```

---

## 7. 实施计划

### 7.1 时间线

| 阶段 | 内容 | 时间 | 交付物 |
|------|------|------|--------|
| **Phase 1** | 架构搭建 | 2-3 天 | file_processing app、数据模型、4 个 Processor |
| **Phase 2** | 转换引擎 | 2-3 天 | Word/Excel ↔ Markdown 转换、单元测试 |
| **Phase 3** | AI 集成 | 3-4 天 | DataSummarizer、NaturalLanguageQuery |
| **Phase 4** | 前端重构 | 2-3 天 | FileAnalysisPage 重构、5 个组件 |
| **Phase 5** | 清理旧代码 | 1-2 天 | 移除旧代码、更新文档 |
| **Phase 6** | 测试与优化 | 2-3 天 | 集成测试、性能优化、Bug 修复 |

**总时间**：12-18 天

### 7.2 里程碑

1. **M1**（Day 3）：能上传 Excel 文件并在前端展示表格数据
2. **M2**（Day 6）：Word/PDF 也能正常解析和展示
3. **M3**（Day 10）：AI 数据摘要功能可用
4. **M4**（Day 14）：自然语言查询功能可用
5. **M5**（Day 16）：导出功能完成
6. **M6**（Day 18）：测试通过、文档完成

### 7.3 风险与依赖

**风险**：
- PDF 表格提取准确率可能不高（pdfplumber 对复杂表格支持有限）
- Ollama 模型响应时间可能较长（需要优化提示词）
- 大文件处理可能超时（需要优化 Celery 任务）

**依赖**：
- Ollama 服务必须运行（用于 AI 分析）
- Redis 服务必须运行（用于 Celery）
- PostgreSQL 数据库（生产环境）

---

## 8. 附录

### 8.1 参考资料

- AionUi 项目：`/home/fz/project/AionUi`
- OmniDesk 项目：`/home/fz/project/OmniDesk`
- openpyxl 文档：https://openpyxl.readthedocs.io/
- pandas 文档：https://pandas.pydata.org/docs/
- python-docx 文档：https://python-docx.readthedocs.io/
- pdfplumber 文档：https://github.com/jsvine/pdfplumber
- mammoth 文档：https://github.com/mwilliamson/mammoth

### 8.2 术语表

| 术语 | 说明 |
|------|------|
| Processor | 文件处理器，负责解析特定格式的文件 |
| Converter | 格式转换器，负责在不同格式间转换 |
| Sheet | Excel 工作表 |
| Markdown | 轻量级标记语言 |
| NL Query | Natural Language Query，自然语言查询 |

---

**文档版本**：1.0  
**最后更新**：2026-07-11
