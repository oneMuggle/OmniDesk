# omni_desk_backend/documents/file_processing.py

import os
from pathlib import Path
import requests
from django.conf import settings
import PyPDF2
from docx import Document as DocxDocument
from PIL import Image

# Mineru OCR API 配置
MINERU_API_URL = getattr(settings, 'MINERU_API_URL', None)
MINERU_API_KEY = getattr(settings, 'MINERU_API_KEY', None)

def call_mineru_ocr(image_path):
    """
    调用 Mineru OCR 服务对图片进行文本识别。
    """
    if not MINERU_API_URL or not MINERU_API_KEY:
        raise ValueError("Mineru API URL or Key not configured in settings.")

    headers = {
        "Authorization": f"Bearer {MINERU_API_KEY}"
    }
    with open(image_path, 'rb') as f:
        files = {'image': f}
        response = requests.post(MINERU_API_URL, headers=headers, files=files)
        response.raise_for_status()  # 抛出 HTTP 错误
        return response.json().get('text', '')

def convert_pdf_to_images(pdf_path, output_folder):
    """
    将 PDF 每一页转换为图片。需要 Poppler 和 Pillow。
    目前简化处理，实际可能需要外部工具如 `pdftoppm` 或 `pdf2image`。
    此处仅为占位符，表示需要将 PDF 转换为图片以便 OCR。
    """
    # 这是一个简化版本，实际生产环境需要更健壮的 PDF 转图片方案
    # 例如：使用 pdf2image 库 (依赖 Poppler)
    # from pdf2image import convert_from_path
    # images = convert_from_path(pdf_path)
    # image_paths = []
    # for i, image in enumerate(images):
    #     image_path = os.path.join(output_folder, f"page_{i+1}.png")
    #     image.save(image_path, "PNG")
    #     image_paths.append(image_path)
    # return image_paths
    
    # 模拟生成一个图片路径
    print(f"Warning: PDF to image conversion is a placeholder. For '{pdf_path}'.")
    dummy_image_path = os.path.join(output_folder, "dummy_pdf_page.png")
    # 创建一个空的占位符图片文件
    try:
        Image.new('RGB', (10, 10)).save(dummy_image_path)
    except Exception as e:
        print(f"Could not create dummy image: {e}")
    return [dummy_image_path]


def extract_text_from_pdf(file_path):
    """
    从 PDF 文件中提取文本。
    """
    text = ""
    try:
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() or ""
        return text
    except PyPDF2.errors.PdfReadError:
        print(f"PDFReadError: Could not read text directly from {file_path}. Will try OCR.")
        return None
    except Exception as e:
        print(f"Error extracting text from PDF {file_path}: {e}")
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
        print(f"Error extracting text from DOCX {file_path}: {e}")
        return None

def extract_text_from_image(file_path, temp_dir):
    """
    从图片文件中提取文本，优先使用 Mineru OCR。
    """
    try:
        return call_mineru_ocr(file_path)
    except Exception as e:
        print(f"Error calling Mineru OCR for image {file_path}: {e}")
        return ""

def process_uploaded_file(file_obj, temp_dir):
    """
    处理上传的文件，提取文本。根据文件类型选择合适的提取方式。
    如果直接提取失败，尝试通过 Mineru OCR 提取。
    """
    file_extension = Path(file_obj.name).suffix.lower()
    temp_file_path = os.path.join(temp_dir, file_obj.name)

    # 将上传的文件保存到临时目录
    with open(temp_file_path, 'wb+') as destination:
        for chunk in file_obj.chunks():
            destination.write(chunk)

    extracted_text = ""

    if file_extension == '.pdf':
        extracted_text = extract_text_from_pdf(temp_file_path)
        if not extracted_text: # 如果直接提取失败，尝试 OCR
            image_paths = convert_pdf_to_images(temp_file_path, temp_dir)
            for img_path in image_paths:
                extracted_text += extract_text_from_image(img_path, temp_dir) + "\n"
    elif file_extension in ['.doc', '.docx']:
        extracted_text = extract_text_from_docx(temp_file_path)
    elif file_extension in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']:
        extracted_text = extract_text_from_image(temp_file_path, temp_dir)
    else:
        # 对于其他未知类型，可以尝试直接读取文本或返回空
        try:
            extracted_text = Path(temp_file_path).read_text(encoding='utf-8')
        except UnicodeDecodeError:
            print(f"Warning: Could not decode text from {file_obj.name}. Returning empty string.")
            extracted_text = ""
        except Exception as e:
            print(f"Error processing unknown file type {file_obj.name}: {e}")
            extracted_text = ""

    return extracted_text