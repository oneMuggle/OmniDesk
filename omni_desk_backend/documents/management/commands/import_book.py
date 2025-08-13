import re
import markdown
import os
import shutil
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
import django
import html # Import the html module for unescaping HTML entities
from bs4 import BeautifulSoup # Import BeautifulSoup
from unidecode import unidecode # Import unidecode

# Helper to normalize heading text for robust comparison and clean display
def normalize_heading_text(text_input):
    # Ensure input is a string, handle potential None or non-string inputs gracefully
    if not isinstance(text_input, str):
        return ""
    
    text = str(text_input).strip() # Convert to string and strip initial whitespace
    
    # Decode HTML entities first, as markdown processors might convert characters to entities
    text = html.unescape(text)

    # Use BeautifulSoup to get plain text from any HTML, effectively removing all tags
    soup = BeautifulSoup(text, 'html.parser')
    text = soup.get_text()

    # Remove Markdown heading syntax (e.g., '### ')
    text = re.sub(r'^\s*#+\s*', '', text).strip()
    
    # Remove MathJax delimiters and content (more robust regex for various forms)
    # Matches $...$, \(...\), \[...\]
    text = re.sub(r'\$(.*?)\$', '', text) # Inline MathJax $...$
    text = re.sub(r'\\\((.*?)\\\)', '', text) # Escaped parens MathJax \(...\)
    text = re.sub(r'\\\[(.*?)\\\]', '', text) # Escaped brackets MathJax \[...\]
    
    # Remove common LaTeX commands and their arguments (e.g., \command, \command{arg}, \alpha)
    # This regex is more general and tries to catch various LaTeX constructs.
    # It attempts to remove \command or \command{argument} or \command*
    text = re.sub(r'\\[a-zA-Z]+\s*(\{[^}]*\})?|\\[a-zA-Z]+\*', '', text)
    
    # Remove special characters that might be part of the original heading but not useful for comparison
    # Added colon (:) to the list of characters to remove if they are not part of meaningful text
    text = re.sub(r'[．·:]', '', text) 

    # Replace multiple spaces with a single space and strip leading/trailing spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# Helper to clean text for ID generation (ASCII characters only)
def clean_text_for_id(text_input, chapter_order=None, item_index=None):
    # Ensure input is a string
    if not isinstance(text_input, str):
        text_input = ""

    # First, normalize the text to remove markdown, mathjax, and common LaTeX commands
    normalized_text = normalize_heading_text(text_input)
    
    # Convert non-ASCII characters to their closest ASCII equivalents
    ascii_text = unidecode(normalized_text)
    
    # Replace spaces with hyphens, convert to lowercase
    sanitized_id = re.sub(r'\s+', '-', ascii_text).strip()
    
    # Remove any remaining non-alphanumeric characters except hyphens
    sanitized_id = re.sub(r'[^\w-]', '', sanitized_id)
    
    # Ensure ID is not empty. If it is, create a fallback ID.
    if not sanitized_id:
        if chapter_order is not None and item_index is not None:
            # Generate a more unique fallback ID if specific indices are provided
            return f"chapter-{chapter_order}-item-{item_index}"
        elif chapter_order is not None:
            return f"chapter-{chapter_order}-heading"
        else:
            return "untitled-heading" # Generic fallback

    return sanitized_id.lower()


class Command(BaseCommand):
    help = 'Imports a book from a Markdown file, splitting it into chapters.'

    def add_arguments(self, parser):
        # Allow title to be optional if it's extracted from markdown
        parser.add_argument('--title', type=str, help='The title of the book. If not provided, attempts to extract from markdown.', default=None)
        parser.add_argument('file_path', type=str, help='The path to the markdown file.')

    def handle(self, *args, **options):
        # Ensure Django is set up before importing models
        django.setup()
        
        input_title = options['title']
        file_path = Path(options['file_path'])

        self.stdout.write(f"Importing book '{input_title or file_path.name}' from '{file_path}'...")

        if not file_path.exists():
            self.stderr.write(self.style.ERROR(f"File not found at: {file_path}"))
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e: # Catch any exception during file read
            self.stderr.write(self.style.ERROR(f"Error reading file {file_path}: {e}"))
            return

        # --- 1. Extract Metadata ---
        metadata = {
            'title': input_title,
            'author': '',
            'description': '',
            'cover_image': None,
            'publication_date': None,
            'tags': []
        }

        # Attempt to extract title from content if not provided
        if not metadata['title']:
            title_match = re.search(r'^#\s*(.+)', content, re.MULTILINE)
            if title_match:
                metadata['title'] = title_match.group(1).strip()
            else:
                self.stderr.write(self.style.ERROR("Could not determine book title. Please provide it via --title argument or ensure it's in the markdown."))
                return

        # Simple metadata extraction (can be extended with YAML parser)
        author_match = re.search(r'^- 作者：(.+)$', content, re.MULTILINE)
        if author_match:
            metadata['author'] = author_match.group(1).strip()

        desc_match = re.search(r'^- 简介：([\s\S]+?)(?=\n-|\n#|$)', content, re.MULTILINE)
        if desc_match:
            metadata['description'] = desc_match.group(1).strip()

        # Handle cover image path
        cover_image_match = re.search(r'^- 封面：(.+)$', content, re.MULTILINE)
        if cover_image_match:
            original_cover_path = file_path.parent / cover_image_match.group(1).strip()
            if original_cover_path.exists():
                media_root = Path(settings.MEDIA_ROOT)
                cover_dest_dir = media_root / 'covers'
                cover_dest_dir.mkdir(parents=True, exist_ok=True)
                
                cover_filename = original_cover_path.name
                dest_path = cover_dest_dir / cover_filename
                shutil.copy(original_cover_path, dest_path)
                metadata['cover_image'] = f"covers/{cover_filename}"
                self.stdout.write(f"  - Copied cover image to: {dest_path}")
            else:
                self.stderr.write(self.style.WARNING(f"  - Cover image not found: {original_cover_path}"))

        tags_match = re.search(r'^- 标签：(.+)$', content, re.MULTILINE)
        if tags_match:
            metadata['tags'] = [t.strip() for t in tags_match.group(1).split(',') if t.strip()]

        # --- 2. Create/Update Book Object ---
        from django.apps import apps
        Book = apps.get_model('documents', 'Book')
        Chapter = apps.get_model('documents', 'Chapter')
        Tag = apps.get_model('documents', 'Tag')
        
        book_obj, created = Book.objects.update_or_create(
            title=metadata['title'],
            defaults={
                'author': metadata['author'],
                'description': metadata['description'],
                'cover_image': metadata['cover_image'],
                'publication_date': metadata['publication_date'], # Placeholder, needs proper date parsing
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created new book: {book_obj.title}"))
        else:
            self.stdout.write(f"Updated existing book: {book_obj.title}")

        # Add tags
        book_obj.tags.clear() # Clear existing tags
        for tag_name in metadata['tags']:
            tag, _ = Tag.objects.get_or_create(name=tag_name)
            book_obj.tags.add(tag)
        self.stdout.write(f"  - Added tags: {', '.join(metadata['tags'])}")

        # Clear existing chapters for this book
        book_obj.chapters.all().delete()

        # --- 3. Markdown Extensions Configuration ---
        md_extensions = [
            'fenced_code', 'tables', 'nl2br',
            'pymdownx.arithmatex',
            'toc', # Table of Contents extension
            'attr_list',
            'pymdownx.extra',
            'pymdownx.highlight',
            'pymdownx.superfences'
        ]
        md_extension_configs = {
            'pymdownx.arithmatex': {
                'generic': True
            },
            'toc': {
                'permalink': True # Add permalinks to headers
            }
        }

        # --- 4. Define Chapters based on H1 headings ---
        chapters_data = []
        
        # Find all H1 heading positions and their content
        h1_regex = r'^(#\s*(.+))' # Capture the full H1 line and its text content
        h1_matches = list(re.finditer(h1_regex, content, re.MULTILINE))

        # Handle preamble (content before the first H1)
        first_h1_start_pos = h1_matches[0].start() if h1_matches else len(content)
        preamble_content = content[:first_h1_start_pos].strip()
        if preamble_content:
            chapters_data.append({
                'title': "前言", # Default title for preamble
                'content_md_raw': preamble_content,
                'is_preamble': True
            })
        
        # Process chapters based on H1 headings
        for i, h1_match in enumerate(h1_matches):
            chapter_start_pos = h1_match.start()
            chapter_title = h1_match.group(2).strip() # Extract only the text, not '#'
            
            chapter_end_pos = len(content)
            if i + 1 < len(h1_matches):
                chapter_end_pos = h1_matches[i+1].start()
            
            # Get the content for this chapter (from this H1 to the next H1 or end of doc)
            chapter_raw_md = content[chapter_start_pos:chapter_end_pos].strip()
            
            chapters_data.append({
                'title': chapter_title, # Use the clean text as title
                'content_md_raw': chapter_raw_md,
                'is_preamble': False
            })

        # --- 5. Process and save each chapter ---
        for chapter_order, chapter_data in enumerate(chapters_data):
            chapter_title = chapter_data['title']
            current_chapter_md_raw = chapter_data['content_md_raw']

            self.stdout.write(f"DEBUG: Processing chapter {chapter_order}: '{chapter_title}'. Raw content start: '{current_chapter_md_raw[:100]}...'")

            # Create a new Markdown instance for each chapter to get its internal TOC
            chapter_md_processor = markdown.Markdown(
                extensions=md_extensions,
                extension_configs=md_extension_configs
            )
            # Convert this chapter's raw Markdown to HTML
            chapter_content_html = chapter_md_processor.convert(current_chapter_md_raw)
            
            chapter_heading_structure = []
            if hasattr(chapter_md_processor, 'toc_tokens'):
                chapter_heading_structure = chapter_md_processor.toc_tokens
            
            # Post-process chapter_heading_structure to clean 'text' fields and ensure ID
            for i, item in enumerate(chapter_heading_structure):
                # Prefer 'name' if available, otherwise use 'text' for cleaning
                source_text = item.get('name', item.get('text', ''))
                
                # Always update 'text' field to be cleaned for display/comparison
                item['text'] = normalize_heading_text(source_text)

                # Ensure ID is also cleaned and not empty
                original_id_from_toc = item.get('id', '')
                cleaned_id = clean_text_for_id(original_id_from_toc, chapter_order, i)
                
                if not cleaned_id: # If original ID from TOC resulted in empty after cleaning, try cleaning the source text
                    cleaned_id = clean_text_for_id(source_text, chapter_order, i)
                
                item['id'] = cleaned_id

                # If after all attempts ID is still empty, use a final unique fallback
                if not item['id']:
                    item['id'] = f"chapter-{chapter_order}-heading-{item.get('level', '')}-{i}-fallback"


            # Ensure the chapter's main title is the first H1 in the heading_structure
            if not chapter_data['is_preamble']:
                found_matching_h1 = False
                normalized_chapter_title = normalize_heading_text(chapter_title)

                for item in chapter_heading_structure:
                    if item.get('level') == 1 and item.get('text') == normalized_chapter_title:
                        found_matching_h1 = True
                        break
                
                if not found_matching_h1:
                    # Filter out any existing H1s that do not match the normalized chapter title if we are inserting a new one
                    chapter_heading_structure = [item for item in chapter_heading_structure if not (item.get('level') == 1 and item.get('text') != normalized_chapter_title)]

                    # Sanitize the chapter_title for a valid ID
                    sanitized_id = clean_text_for_id(chapter_title, chapter_order) # Use clean_text_for_id for ID generation
                    
                    # Insert at the beginning to ensure it's the primary heading
                    chapter_heading_structure.insert(0, {
                        'level': 1,
                        'id': sanitized_id, # Use the simplified, clean ID
                        'text': chapter_title # Use the original chapter_title here
                    })
            elif chapter_data['is_preamble'] and not chapter_heading_structure:
                 chapter_heading_structure.append({
                        'level': 1,
                        'id': "preamble",
                        'text': "前言"
                    })


            self.stdout.write(f"DEBUG: Chapter {chapter_order} internal heading_structure: {chapter_heading_structure}")

            # --- Image Path Correction within Chapter Content ---
            image_metadata_list = [] # List to store image metadata for this chapter

            def replace_image_path(match):
                original_path = match.group(2) if match.group(2) else match.group(4)
                alt_text = match.group(1) # For markdown image, this would be ![alt_text](...)
                if alt_text:
                    alt_match = re.match(r'!\[(.*?)\]', alt_text)
                    if alt_match:
                        alt_text = alt_match.group(1)
                    else:
                        alt_text = ''
                else:
                    alt_text = ''

                if original_path.startswith(('http://', 'https://', 'data:')):
                    image_metadata_list.append({
                        'original_path': original_path,
                        'processed_url': original_path,
                        'alt_text': alt_text,
                        'type': 'external'
                    })
                    return match.group(0)

                image_abs_path = file_path.parent / original_path
                
                if image_abs_path.exists():
                    media_root_path = Path(settings.MEDIA_ROOT)
                    sanitized_book_title = re.sub(r'[^\w\-_\. ]', '_', book_obj.title)
                    book_images_dir = media_root_path / 'book_images' / sanitized_book_title
                    book_images_dir.mkdir(parents=True, exist_ok=True)
                    
                    image_filename = image_abs_path.name
                    dest_path = book_images_dir / image_filename
                    shutil.copy(image_abs_path, dest_path)
                    
                    relative_media_path = dest_path.relative_to(media_root_path).as_posix()
                    image_url = f"{settings.MEDIA_URL}{relative_media_path}"
                    
                    image_metadata_list.append({
                        'original_path': original_path,
                        'processed_url': image_url,
                        'alt_text': alt_text,
                        'type': 'local'
                    })
                    self.stdout.write(f"    - Processed image: {original_path} -> {image_url}")
                    if match.group(1): # Markdown image
                        return match.group(1).replace(match.group(2), image_url)
                    else: # HTML image
                        return match.group(0).replace(match.group(4), image_url)
                else:
                    image_metadata_list.append({
                        'original_path': original_path,
                        'processed_url': original_path,
                        'alt_text': alt_text,
                        'type': 'not_found'
                    })
                    self.stderr.write(self.style.WARNING(f"    - Image not found (keeping original path): {original_path}"))
                    return match.group(0)

            # Apply image path correction to the chapter's markdown content
            current_chapter_md = re.sub(
                r'(!\[.*?\]\((.+?)\))|(<img\s+src="([^"]+)"[^>]*>)',
                replace_image_path,
                current_chapter_md_raw, # Use raw content here
                flags=re.IGNORECASE
            )

            Chapter.objects.create(
                book=book_obj,
                title=chapter_title,
                content_md=current_chapter_md,
                content_html=chapter_content_html,
                order=chapter_order,
                image_metadata=image_metadata_list, # Save image metadata
                heading_structure=chapter_heading_structure # Save heading structure
            )
            self.stdout.write(f"  - Imported chapter {chapter_order}: '{chapter_title}' (raw content start: '{current_chapter_md_raw[:50]}...')")
        self.stdout.write(self.style.SUCCESS(f"Successfully imported {len(chapters_data)} chapters for the book '{book_obj.title}'."))