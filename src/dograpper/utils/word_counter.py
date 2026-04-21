"""Word counting utilities."""

import os
from .html_stripper import strip_html
from .content_extractor import extract_content

def count_words(text: str) -> int:
    """Simple word count."""
    return len(text.split())

def count_words_file(filepath: str, no_extract: bool = False) -> int:
    """Read a file from disk and return its word count, tolerating encoding errors."""
    if not os.path.isfile(filepath):
        return 0
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        if filepath.lower().endswith(('.html', '.htm')):
            if not no_extract:
                content = extract_content(content)
            content = strip_html(content)
        return count_words(content)
    except Exception:
        # Fallback for unexpected I/O errors
        return 0
