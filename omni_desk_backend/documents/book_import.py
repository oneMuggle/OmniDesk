"""电子书导入服务模块。

将 ZIP/Markdown 文件导入为电子书的核心逻辑从 BookImportView 中分离。
"""

import posixpath
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import unquote

import markdown
from django.conf import settings
from django.db import transaction

from taggit.models import Tag

from .models import Book, Chapter


def extract_headings(markdown_content):
    """从 markdown 内容中提取标题结构。（原 views.py 中的实现）"""
    heading_pattern = re.compile(r"^(#{1,6})\s+(.+)", re.MULTILINE)
    headings = []
    for match in heading_pattern.finditer(markdown_content):
        level = len(match.group(1))
        text = match.group(2).strip()
        headings.append({"level": level, "text": text})
    return headings


def import_book_from_file(
    uploaded_file, cover_image_file=None, title=None, author="", description="", publication_date=None, tags_str=""
):
    """从上传的 .md 或 .zip 文件导入电子书。

    返回 Book 实例。
    """
    if uploaded_file.name.endswith(".zip"):
        content, base_path, temp_dir_obj = _extract_zip(uploaded_file)
    elif uploaded_file.name.endswith(".md"):
        content = uploaded_file.read().decode("utf-8")
        base_path = None
    else:
        raise ValueError("Unsupported file type. Please upload a .md or .zip file.")

    if not title:
        title_match = re.search(r"^#\s*(.+)", content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()
        else:
            title = Path(uploaded_file.name).stem

    if not title:
        raise ValueError("Book title is required.")

    with transaction.atomic():
        cover_image_path = _save_cover_image(cover_image_file) if cover_image_file else None

        book_obj, _ = Book.objects.update_or_create(
            title=title,
            defaults={
                "author": author,
                "description": description,
                "cover_image": cover_image_path,
                "publication_date": publication_date,
            },
        )

        _apply_tags(book_obj, tags_str)

        if base_path:
            content = _migrate_image_paths(content, base_path, title)

        _create_chapters(book_obj, content)

    return book_obj


def _extract_zip(uploaded_file):
    """解压 ZIP 文件并返回 markdown 内容、图片目录和临时目录对象。"""
    temp_dir_obj = tempfile.TemporaryDirectory()
    temp_dir = Path(temp_dir_obj.name)

    zip_path = temp_dir / uploaded_file.name
    with open(zip_path, "wb+") as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(temp_dir)

    md_files = list(temp_dir.glob("**/*.md"))
    if not md_files:
        raise ValueError("No markdown file found in the zip archive.")

    markdown_file_path = md_files[0]
    content = markdown_file_path.read_text(encoding="utf-8")
    return content, markdown_file_path.parent, temp_dir_obj


def _save_cover_image(cover_image_file):
    """保存封面图片到 MEDIA_ROOT/covers/，返回相对路径。"""
    media_root = Path(settings.MEDIA_ROOT)
    cover_dest_dir = media_root / "covers"
    cover_dest_dir.mkdir(parents=True, exist_ok=True)

    cover_filename = cover_image_file.name
    dest_path = cover_dest_dir / cover_filename

    with open(dest_path, "wb+") as destination:
        for chunk in cover_image_file.chunks():
            destination.write(chunk)

    return f"covers/{cover_filename}"


def _apply_tags(book_obj, tags_str):
    """应用标签到电子书。"""
    tags_list = [t.strip() for t in tags_str.split(",") if t.strip()]
    book_obj.tags.clear()
    for tag_name in tags_list:
        tag, _ = Tag.objects.get_or_create(name=tag_name)
        book_obj.tags.add(tag)


def _migrate_image_paths(content, base_path, book_title):
    """将本地图片路径迁移到 MEDIA_URL 下的标准路径。"""

    def replace_image_path(match):
        alt_text = match.group(1)
        original_path_str = unquote(match.group(2))

        if original_path_str.startswith(("http://", "https://", "data:")):
            return match.group(0)

        try:
            original_path_str = original_path_str.replace("\\", "/")
            src_image_path = (base_path / original_path_str).resolve(strict=True)

            if not str(src_image_path).startswith(str(base_path.resolve())):
                return match.group(0)

            sanitized_title = re.sub(r"[^\w\-_\.]", "_", book_title)
            image_filename = src_image_path.name
            image_dest_dir = Path(settings.MEDIA_ROOT) / "book_images" / sanitized_title
            image_dest_dir.mkdir(parents=True, exist_ok=True)
            dest_image_path = image_dest_dir / image_filename

            shutil.move(str(src_image_path), str(dest_image_path))

            new_path = posixpath.join(settings.MEDIA_URL, "book_images", sanitized_title, image_filename)
            return f"![{alt_text}]({new_path})"
        except (FileNotFoundError, ValueError):
            return match.group(0)
        except Exception:
            return match.group(0)

    return re.sub(r"!\[(.*?)\]\((.*?)\)", replace_image_path, content)


def _create_chapters(book_obj, content):
    """将 markdown 内容拆分为章节并保存到数据库。"""
    md_extensions = ["fenced_code", "tables", "nl2br", "pymdownx.arithmatex"]
    md_extension_configs = {"pymdownx.arithmatex": {"generic": True}}

    book_obj.chapters.all().delete()
    chapters_md = re.split(r"(?m)^# (?!#)", content)

    chapter_order = 0
    preamble = chapters_md[0].strip()
    if preamble and not re.fullmatch(r"\s*", preamble):
        Chapter.objects.create(
            book=book_obj,
            title="前言",
            content_md=preamble,
            content_html=markdown.markdown(preamble, extensions=md_extensions, extension_configs=md_extension_configs),
            order=chapter_order,
        )
        chapter_order += 1

    for i in range(1, len(chapters_md)):
        chapter_full_content = chapters_md[i]
        if not chapter_full_content.strip():
            continue
        parts = chapter_full_content.split("\n", 1)
        chapter_title = parts[0].strip()
        chapter_content_md = "# " + chapter_full_content.strip()

        Chapter.objects.create(
            book=book_obj,
            title=chapter_title,
            content_md=chapter_content_md,
            content_html=markdown.markdown(
                chapter_content_md, extensions=md_extensions, extension_configs=md_extension_configs
            ),
            heading_structure=extract_headings(chapter_content_md),
            order=chapter_order,
        )
        chapter_order += 1
