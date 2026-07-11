from .processors.excel import ExcelProcessor
from .processors.word import WordProcessor
from .processors.pdf import PDFProcessor
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

        # 提取内容
        text = processor.extract_text(file_path)
        markdown = processor.extract_markdown(file_path)
        structured = processor.extract_structured(file_path)
        metadata = processor.get_metadata(file_path)

        # 创建处理结果
        result = ProcessingResult.objects.create(
            file=uploaded_file,
            content_text=text,
            content_markdown=markdown,
            content_json=structured,
            sheets_data=structured.get('sheets', []),
            row_count=sum(sheet.get('row_count', 0) for sheet in structured.get('sheets', [])),
            column_count=max((sheet.get('column_count', 0) for sheet in structured.get('sheets', [])), default=0),
        )

        # 更新文件状态
        uploaded_file.status = 'completed'
        uploaded_file.sheet_count = metadata.get('sheet_count', 0)
        uploaded_file.page_count = metadata.get('page_count', 0)
        uploaded_file.save()

        return result
