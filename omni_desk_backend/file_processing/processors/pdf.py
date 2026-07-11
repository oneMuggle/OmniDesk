import pdfplumber
from typing import Any
from .base import FileProcessor


class PDFProcessor(FileProcessor):
    """PDF 文件处理器"""

    def extract_text(self, file_path: str) -> str:
        """提取 PDF 文本"""
        with pdfplumber.open(file_path) as pdf:
            return "\n\n".join([page.extract_text() or "" for page in pdf.pages])

    def extract_markdown(self, file_path: str) -> str:
        """PDF → Markdown（提取文本 + 表格）"""
        with pdfplumber.open(file_path) as pdf:
            md_parts = []

            for i, page in enumerate(pdf.pages, 1):
                md_parts.append(f"## 第 {i} 页\n\n")

                text = page.extract_text()
                if text:
                    md_parts.append(text + "\n\n")

                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue

                    headers = table[0]
                    md_parts.append("| " + " | ".join(str(h) or "" for h in headers) + " |\n")
                    md_parts.append("| " + " | ".join("---" for _ in headers) + " |\n")

                    for row in table[1:]:
                        md_parts.append("| " + " | ".join(str(cell) or "" for cell in row) + " |\n")

                    md_parts.append("\n")

            return "".join(md_parts)

    def extract_structured(self, file_path: str) -> dict[str, Any]:
        """提取 PDF 结构化数据"""
        with pdfplumber.open(file_path) as pdf:
            pages = []

            for i, page in enumerate(pdf.pages, 1):
                pages.append(
                    {
                        "page_number": i,
                        "text": page.extract_text() or "",
                        "tables": page.extract_tables() or [],
                    }
                )

            return {
                "page_count": len(pdf.pages),
                "pages": pages,
            }

    def get_metadata(self, file_path: str) -> dict[str, Any]:
        """获取 PDF 元数据"""
        with pdfplumber.open(file_path) as pdf:
            return {
                "page_count": len(pdf.pages),
            }
