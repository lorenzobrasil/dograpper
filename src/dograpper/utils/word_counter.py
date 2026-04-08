"""Word counting utilities."""

import os

def count_words(text: str) -> int:
    """Contagem simples de palavras."""
    return len(text.split())

def count_words_file(filepath: str) -> int:
    """Lê um arquivo do disco e retorna a contagem de palavras, tolerando erros de codificação."""
    if not os.path.isfile(filepath):
        return 0
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return count_words(content)
    except Exception:
        # Fallback for unexpected I/O errors
        return 0
