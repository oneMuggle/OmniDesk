import os
import re
from pathlib import Path

import markdown
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from documents.models import Book, Chapter


class Command(BaseCommand):
    help = "Imports books and chapters from Markdown files in the specified directories."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting book import from filesystem..."))

        # Define the directories to scan for Markdown files
        # We'll use BASE_DIR to construct absolute paths
        base_dir = Path(settings.BASE_DIR).parent  # Assuming BASE_DIR is in omni_desk_backend
        scan_dirs = [
            base_dir / "docs",
            base_dir / "calendar_with_react" / "docs",
        ]

        with transaction.atomic():
            self.import_books(scan_dirs, base_dir)

        self.stdout.write(self.style.SUCCESS("Successfully imported books and chapters."))

    def import_books(self, scan_dirs, base_dir):
        """
        Scans directories, maps folders to Books and .md files to Chapters.
        """
        for dir_path in scan_dirs:
            if not dir_path.is_dir():
                self.stdout.write(self.style.WARNING(f"Directory not found, skipping: {dir_path}"))
                continue

            self.stdout.write(f"Scanning directory: {dir_path}")
            for root, dirs, files in os.walk(dir_path):
                # Use a more unique title for the book, e.g., based on relative path
                relative_path = Path(root).relative_to(base_dir)
                book_title = str(relative_path).replace(os.path.sep, " - ")

                # Create or update the book using the unique title
                book, created = Book.objects.update_or_create(
                    title=book_title, defaults={"description": f"Book imported from {relative_path}"}
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f"  Created book: '{book.title}'"))
                else:
                    self.stdout.write(f"  Found existing book: '{book.title}'")

                # Process markdown files in the current directory
                for filename in files:
                    if filename.endswith(".md"):
                        file_path = Path(root) / filename
                        self.process_markdown_file(file_path, book)

    def process_markdown_file(self, file_path, book):
        """
        Processes a single Markdown file to create or update a Chapter.
        This will include heading extraction and image path handling.
        """
        self.stdout.write(f"    Processing file: {file_path.name}")
        try:
            with open(file_path, encoding="utf-8") as f:
                content_md = f.read()

            # Extract headings
            headings = self.extract_headings(content_md)

            # Handle images and update content
            # book.title can be used to create a unique folder for images
            sanitized_book_title = re.sub(r"[^\w\-_\. ]", "_", book.title)
            content_md_with_updated_images = self.handle_images(content_md, sanitized_book_title, file_path.parent)

            # Convert Markdown to HTML
            html_content = markdown.markdown(
                content_md_with_updated_images, extensions=["fenced_code", "tables", "nl2br", "pymdownx.arithmatex"]
            )

            # Create or update chapter
            chapter_title = file_path.stem  # Use filename without extension as title
            Chapter.objects.update_or_create(
                book=book,
                title=chapter_title,  # Assuming one md file is one chapter
                defaults={
                    "content_md": content_md,
                    "content_html": html_content,
                    "heading_structure": headings,
                    "order": 0,  # We can define a better ordering later
                },
            )

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"    Error processing file {file_path}: {e}"))

    def extract_headings(self, markdown_content):
        """
        Extracts H1-H6 headings and builds a nested structure.
        """
        headings = []
        # Find all markdown headings
        lines = markdown_content.split("\n")
        for line in lines:
            match = re.match(r"^(#+)\s+(.*)", line)
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()
                # Simple slugify for id
                slug = re.sub(r"[^\w\s-]", "", title).strip().lower()
                slug = re.sub(r"[-\s]+", "-", slug)
                headings.append({"level": level, "title": title, "id": slug, "children": []})

        # Build the nested structure
        if not headings:
            return []

        root_nodes = []
        stack = []  # A stack to keep track of parent nodes

        for heading in headings:
            level = heading["level"]

            # Go up the stack to find the correct parent
            while stack and stack[-1]["level"] >= level:
                stack.pop()

            if not stack:
                # This is a root node (or the first node)
                root_nodes.append(heading)
            else:
                # This is a child of the node at the top of the stack
                stack[-1]["children"].append(heading)

            # Push the current heading onto the stack
            stack.append(heading)

        return root_nodes

    def handle_images(self, markdown_content, book_slug, base_file_path):
        """
        Finds image paths, copies them to media, and updates the content.
        """
        import shutil

        media_root = Path(settings.MEDIA_ROOT)
        image_dest_dir = media_root / "book_images" / book_slug
        image_dest_dir.mkdir(parents=True, exist_ok=True)

        # Regex to find markdown image syntax
        # ![alt text](path/to/image.jpg)
        img_pattern = re.compile(r"!\[(.*?)\]\((.*?)\)")

        def replace_path(match):
            alt_text = match.group(1)
            original_path = match.group(2)

            # Skip absolute URLs
            if original_path.startswith(("http://", "https://", "/")):
                return match.group(0)

            src_image_path = base_file_path / original_path

            if not src_image_path.is_file():
                self.stderr.write(self.style.WARNING(f"      Image not found: {src_image_path}"))
                return match.group(0)  # Keep original if not found

            # Copy image to media directory
            dest_image_path = image_dest_dir / src_image_path.name
            try:
                shutil.copy(src_image_path, dest_image_path)

                # New path for markdown content (URL path)
                new_path = f"{settings.MEDIA_URL}book_images/{book_slug}/{src_image_path.name}"
                self.stdout.write(f"      Copied image to: {new_path}")
                return f"![{alt_text}]({new_path})"

            except Exception as e:
                self.stderr.write(self.style.ERROR(f"      Error copying image {src_image_path}: {e}"))
                return match.group(0)  # Keep original on error

        return img_pattern.sub(replace_path, markdown_content)
