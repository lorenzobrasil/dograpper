"""Token counting utilities for dograpper chunks.

Encoding default: cl100k_base (GPT-4, GPT-3.5-turbo).
"""

import logging
from dataclasses import dataclass

import tiktoken

logger = logging.getLogger(__name__)

# Alias curto → nome completo do encoding tiktoken.
SUPPORTED_ENCODINGS = {
    "cl100k": "cl100k_base",       # GPT-4, GPT-4-turbo, GPT-3.5-turbo
    "o200k": "o200k_base",         # GPT-4o, GPT-4o-mini
    "p50k": "p50k_base",           # Codex, text-davinci-002/003
}


@dataclass
class TokenCount:
    """Resultado de uma contagem de tokens."""
    words: int
    tokens: int
    encoding: str


def count_tokens(text: str, encoding: str = "cl100k") -> TokenCount:
    """Conta tokens do texto usando tiktoken.

    Args:
        text: texto a ser contado.
        encoding: alias do encoding (chave de SUPPORTED_ENCODINGS)
                  ou nome completo do tiktoken (ex: "cl100k_base").

    Returns:
        TokenCount com palavras, tokens e encoding usado.

    Raises:
        ValueError: se o encoding não for reconhecido pelo tiktoken.
    """
    words = len(text.split())

    if words == 0:
        return TokenCount(words=0, tokens=0, encoding=encoding)

    # Resolver alias → nome completo
    enc_name = SUPPORTED_ENCODINGS.get(encoding, encoding)

    try:
        enc = tiktoken.get_encoding(enc_name)
    except ValueError:
        raise ValueError(
            f"Encoding '{encoding}' não reconhecido. "
            f"Opções suportadas: {', '.join(SUPPORTED_ENCODINGS.keys())}"
        )

    tokens = len(enc.encode(text))
    return TokenCount(words=words, tokens=tokens, encoding=enc_name)


def count_tokens_file(filepath: str, encoding: str = "cl100k") -> TokenCount:
    """Lê arquivo com encoding tolerante e conta tokens."""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    return count_tokens(text, encoding)


def format_token_summary(counts: list) -> str:
    """Formata resumo de contagem de tokens para exibição no CLI.

    Args:
        counts: lista de TokenCount, um por chunk.

    Returns:
        String formatada com total, avg, min, max.
    """
    if not counts:
        return "  Tokens:          (nenhum chunk processado)"

    total = sum(c.tokens for c in counts)
    avg = total // len(counts)
    min_t = min(c.tokens for c in counts)
    max_t = max(c.tokens for c in counts)
    encoding = counts[0].encoding

    lines = []
    lines.append(f"  Tokens per chunk: ~{avg:,} avg (min: {min_t:,}, max: {max_t:,})".replace(",", "."))
    lines.append(f"  Total tokens:    {total:,}".replace(",", "."))
    lines.append(f"  Encoding:        {encoding}")
    return "\n".join(lines)
