"""Word counting utilities."""

import os
from .html_stripper import strip_html
from .content_extractor import extract_content

def count_words(text: str) -> int:
    """Contagem simples de palavras."""
    return len(text.split())

def count_words_file(filepath: str, no_extract: bool = False) -> int:
    """Lê um arquivo do disco e retorna a contagem de palavras, tolerando erros de codificação."""
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
