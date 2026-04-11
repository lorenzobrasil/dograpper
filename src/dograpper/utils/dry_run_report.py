"""Dry-run report generation for the pack command.

Receives processed pipeline data (file stats, projected chunks,
word/token counts) and produces a formatted terminal report.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FileStats:
    """Per-file statistics collected during pipeline."""
    filepath: str
    words_before_extraction: int
    words_after_extraction: int
    tokens: Optional[int] = None
    words_after_dedup: Optional[int] = None


@dataclass
class DryRunData:
    """Aggregated data for the dry-run report."""
    total_files_found: int
    total_files_excluded: int
    file_stats: list
    projected_chunks: int
    max_chunks: int
    max_words_per_chunk: int
    strategy: str
    show_tokens: bool = False
    token_encoding: str = "cl100k"
    oversize_files: int = 0
    dedup_stats: object = None  # Optional DedupStats


def _effective_words(f: FileStats) -> int:
    """Return the most-processed word count for a file."""
    if f.words_after_dedup is not None:
        return f.words_after_dedup
    return f.words_after_extraction


def generate_report(data: DryRunData) -> str:
    """Build the full dry-run report as a formatted string."""
    lines = []
    lines.append("")
    lines.append("Dry-run report (nenhum arquivo foi escrito):")
    lines.append("\u2500" * 55)

    # --- Section 1: Overview ---
    lines.append("")
    lines.append("  Arquivos encontrados:  " + str(data.total_files_found))
    lines.append("  Arquivos exclu\u00eddos:    " + str(data.total_files_excluded))
    lines.append("  Arquivos processados:  " + str(len(data.file_stats)))

    total_before = sum(f.words_before_extraction for f in data.file_stats)
    total_after = sum(f.words_after_extraction for f in data.file_stats)

    lines.append("")
    lines.append("  Palavras (bruto):      " + f"{total_before:,}")
    lines.append("  Palavras (extra\u00eddo):   " + f"{total_after:,}")

    if total_before > 0:
        reduction = (total_before - total_after) * 100 // total_before
        lines.append(f"  Redu\u00e7\u00e3o por extra\u00e7\u00e3o:  {reduction}%")

    # Dedup stats
    if data.dedup_stats is not None:
        total_after_dedup = sum(_effective_words(f) for f in data.file_stats)
        lines.append(f"  Palavras (p\u00f3s-dedup):  {total_after_dedup:,}")
        if total_after > 0:
            dedup_pct = data.dedup_stats.words_removed * 100 // total_after
        else:
            dedup_pct = 0
        lines.append(
            f"  Dedup removeu:         {data.dedup_stats.words_removed:,} palavras "
            f"({dedup_pct}%) \u2014 {data.dedup_stats.blocks_removed_exact} exact, "
            f"{data.dedup_stats.blocks_removed_fuzzy} fuzzy"
        )

    if data.show_tokens:
        total_tokens = sum(f.tokens for f in data.file_stats if f.tokens is not None)
        lines.append(f"  Total tokens:          {total_tokens:,} ({data.token_encoding})")

    # --- Section 2: Chunk projection ---
    lines.append("")
    lines.append("  Estrat\u00e9gia:            " + data.strategy)
    lines.append("  Limite por chunk:      " + f"{data.max_words_per_chunk:,} palavras")
    lines.append("  Chunks projetados:     " + f"{data.projected_chunks} / {data.max_chunks} (max)")
    if data.oversize_files > 0:
        lines.append(f"  \u26a0 Arquivos oversize:   {data.oversize_files} (excedem o limite sozinhos)")

    # --- Section 3: Top 10 files ---
    lines.append("")
    lines.append("  Top 10 arquivos por palavras (ap\u00f3s extra\u00e7\u00e3o):")
    lines.append("  " + "\u2500" * 53)

    sorted_files = sorted(data.file_stats, key=lambda f: _effective_words(f), reverse=True)
    top_n = sorted_files[:10]

    for i, f in enumerate(top_n, 1):
        name = _truncate_path(f.filepath, max_len=40)
        ew = _effective_words(f)
        words_str = f"{ew:,}"

        if data.show_tokens and f.tokens is not None:
            tokens_str = f"{f.tokens:,} tok"
            line = f"  {i:>2}. {name:<40} {words_str:>7} words  {tokens_str:>10}"
        else:
            compression = ""
            if f.words_before_extraction > 0 and f.words_before_extraction != ew:
                pct = (f.words_before_extraction - ew) * 100 // f.words_before_extraction
                compression = f"  (-{pct}%)"
            line = f"  {i:>2}. {name:<40} {words_str:>7} words{compression}"

        lines.append(line)

    # --- Section 4: Projected distribution ---
    if data.projected_chunks > 0:
        total_effective = sum(_effective_words(f) for f in data.file_stats)
        avg_words = total_effective // data.projected_chunks
        lines.append("")
        lines.append(f"  M\u00e9dia projetada:       ~{avg_words:,} palavras/chunk")

    # --- Footer ---
    lines.append("")
    lines.append("\u2500" * 55)
    lines.append("Ajuste par\u00e2metros e rode sem --dry-run para empacotar.")
    lines.append("")

    return "\n".join(lines)


def _truncate_path(path: str, max_len: int = 40) -> str:
    """Shorten long paths keeping the tail visible."""
    if len(path) <= max_len:
        return path
    return "..." + path[-(max_len - 3):]
