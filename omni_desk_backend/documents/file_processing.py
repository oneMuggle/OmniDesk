# omni_desk_backend/documents/file_processing.py

import logging
import mimetypes
import os
from pathlib import Path

import pypdf
import requests
from django.conf import settings
from docx import Document as DocxDocument

logger = logging.getLogger(__name__)

# Mineru OCR API 配置
MINERU_API_URL = getattr(settings, "MINERU_API_URL", None)
MINERU_API_KEY = getattr(settings, "MINERU_API_KEY", None)


def call_mineru_ocr(file_path):
    """
    调用 Mineru OCR 服务对文件进行文本识别。
    尝试支持图片和 PDF。
    """
    if not MINERU_API_URL or not MINERU_API_KEY:
        raise ValueError("Mineru API URL or Key not configured in settings.")

    headers = {"Authorization": f"Bearer {MINERU_API_KEY}"}

    # 尝试根据文件扩展名猜测 MIME 类型
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "application/octet-stream"  # 默认二进制流

    with open(file_path, "rb") as f:
        # 使用更通用的参数名，并包含文件名和 MIME 类型
        files = {"document": (Path(file_path).name, f, mime_type)}
        response = requests.post(MINERU_API_URL, headers=headers, files=files, timeout=30)
        response.raise_for_status()
        return response.json().get("text", "")


def extract_text_from_pdf(file_path):
    """
    从 PDF 文件中提取文本。
    """
    text = ""
    try:
        with open(file_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() or ""
        return text
    except pypdf.errors.PdfReadError:
        logger.warning("Could not read text directly from %s. Will try Mineru OCR.", file_path)
        return None
    except Exception as e:
        logger.error("Error extracting text from PDF %s: %s", file_path, e)
        return None


def extract_text_from_docx(file_path):
    """
    从 DOCX 文件中提取文本。
    """
    text = ""
    try:
        doc = DocxDocument(file_path)
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except Exception as e:
        logger.error("Error extracting text from DOCX %s: %s", file_path, e)
        return None


def process_uploaded_file(file_obj, temp_dir):
    """
    处理上传的文件，提取文本。根据文件类型选择合适的提取方式。
    如果直接提取失败，尝试通过 Mineru OCR 提取。
    """
    file_extension = Path(file_obj.name).suffix.lower()
    temp_file_path = os.path.join(temp_dir, file_obj.name)

    # 将上传的文件保存到临时目录
    with open(temp_file_path, "wb+") as destination:
        for chunk in file_obj.chunks():
            destination.write(chunk)

    extracted_text = ""

    if file_extension == ".pdf":
        extracted_text = extract_text_from_pdf(temp_file_path)
        if not extracted_text:  # 如果直接提取失败，尝试 Mineru OCR
            try:
                extracted_text = call_mineru_ocr(temp_file_path)
                logger.info("Text extracted from PDF via Mineru OCR: %d characters", len(extracted_text))
            except Exception as e:
                logger.error("Error calling Mineru OCR for PDF %s: %s", file_obj.name, e)
                extracted_text = ""
    elif file_extension in [".doc", ".docx"]:
        extracted_text = extract_text_from_docx(temp_file_path)
        # 对于 Word 文档，如果直接提取失败，也可以考虑 Mineru OCR
        if not extracted_text:
            try:
                extracted_text = call_mineru_ocr(temp_file_path)
                logger.info("Text extracted from DOCX via Mineru OCR: %d characters", len(extracted_text))
            except Exception as e:
                logger.error("Error calling Mineru OCR for DOCX %s: %s", file_obj.name, e)
                extracted_text = ""
    elif file_extension in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"]:
        extracted_text = call_mineru_ocr(temp_file_path)
    else:
        # 对于其他未知类型，可以尝试直接读取文本或返回空
        try:
            extracted_text = Path(temp_file_path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            logger.warning("Could not decode text from %s. Returning empty string.", file_obj.name)
            extracted_text = ""
        except Exception as e:
            logger.error("Error processing unknown file type %s: %s", file_obj.name, e)
            extracted_text = ""

    return extracted_text
