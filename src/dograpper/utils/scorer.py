"""LLM Readiness scoring for chunks."""

import re
from dataclasses import dataclass


@dataclass
class ChunkScore:
    chunk_id: str
    word_count: int
    noise_ratio: float
    boundary_integrity: bool
    context_depth: int
    score: float
    grade: str


def calculate_noise_ratio(raw_words: int, extracted_words: int) -> float:
    """Proportion of words removed by extraction (boilerplate).

    Returns 0.0 if raw_words is 0 or extracted >= raw (no noise).
    """
    if raw_words <= 0:
        return 0.0
    noise = 1.0 - (extracted_words / raw_words)
    return max(0.0, min(1.0, noise))


def check_boundary_integrity(text: str) -> bool:
    """Check whether the text contains broken structural blocks.

    Detects:
    - Unbalanced ``` fences (odd count)
    - Unbalanced <pre>...</pre> tags
    """
    fence_count = len(re.findall(r'```', text))
    if fence_count % 2 != 0:
        return False

    pre_open = len(re.findall(r'<pre[\s>]', text, re.IGNORECASE))
    pre_close = len(re.findall(r'</pre>', text, re.IGNORECASE))
    if pre_open != pre_close:
        return False

    return True


def calculate_context_depth(headings_count: int, max_level: int) -> int:
    """Depth of preserved context.

    Returns max_level if headings exist, else 0.
    """
    if headings_count > 0 and max_level > 0:
        return max_level
    return 0


def calculate_grade(noise_ratio: float, boundary_ok: bool, context_depth: int) -> tuple:
    """Calculate composite score (0-1) and grade (A/B/C).

    Weights:
    - noise_ratio: 40% (lower = better -> score_noise = 1 - noise_ratio)
    - boundary_integrity: 30% (True = 1.0, False = 0.0)
    - context_depth: 30% (depth >= 2 = 1.0, depth == 1 = 0.5, depth == 0 = 0.0)
    """
    score_noise = 1.0 - noise_ratio
    score_boundary = 1.0 if boundary_ok else 0.0

    if context_depth >= 2:
        score_context = 1.0
    elif context_depth == 1:
        score_context = 0.5
    else:
        score_context = 0.0

    score = score_noise * 0.4 + score_boundary * 0.3 + score_context * 0.3

    if score >= 0.8:
        grade = "A"
    elif score >= 0.5:
        grade = "B"
    else:
        grade = "C"

    return score, grade


def score_chunk(
    chunk_id: str,
    text: str,
    raw_words: int,
    extracted_words: int,
    headings_count: int,
    max_heading_level: int,
) -> ChunkScore:
    """Main function — calculate all metrics for a chunk."""
    noise = calculate_noise_ratio(raw_words, extracted_words)
    boundary_ok = check_boundary_integrity(text)
    depth = calculate_context_depth(headings_count, max_heading_level)
    score, grade = calculate_grade(noise, boundary_ok, depth)

    return ChunkScore(
        chunk_id=chunk_id,
        word_count=len(text.split()),
        noise_ratio=noise,
        boundary_integrity=boundary_ok,
        context_depth=depth,
        score=score,
        grade=grade,
    )
