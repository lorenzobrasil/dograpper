"""Filter discovered URLs to the scope of the download command.

Two rules are applied against each URL:
  1. Same-netloc: URL must share `base_url`'s host (no cross-host leakage).
  2. Path-prefix / depth: URL path must live under `base_url`'s canonicalized
     path prefix; if `depth > 0`, the URL must not exceed `depth` additional
     segments beyond the base path.

Path canonicalization appends a trailing slash to BOTH sides
(`rstrip('/') + '/'`) before the startswith check, so that `/docs` does not
accidentally match `/docsextra`.
"""

from __future__ import annotations

import logging
from typing import List
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _canonical_prefix(path: str) -> str:
    """Normalize a path to a slash-terminated prefix safe for startswith()."""
    if not path:
        return "/"
    return path.rstrip("/") + "/"


def _path_segments(path: str) -> List[str]:
    return [seg for seg in path.split("/") if seg]


def filter_urls(urls: List[str], base_url: str, depth: int = 0) -> List[str]:
    """Return URLs under `base_url`'s scope, preserving order.

    Args:
        urls: candidate URLs (absolute http/https).
        base_url: scope root. URLs must share its netloc and sit under its
            (canonicalized) path prefix.
        depth: `0` means no depth limit. `>0` caps additional path segments
            beyond the base path.

    Rejected URLs are dropped silently (debug-logged) so the return value
    is safe to feed directly into `run_wget_urls`.
    """
    parsed_base = urlparse(base_url)
    if not parsed_base.scheme or not parsed_base.netloc:
        logger.warning(f"url_filter: base_url missing scheme/netloc: {base_url}")
        return []

    base_netloc = parsed_base.netloc
    base_prefix = _canonical_prefix(parsed_base.path)
    base_segments = len(_path_segments(parsed_base.path))

    kept: List[str] = []
    seen = set()
    for url in urls:
        try:
            parsed = urlparse(url)
        except ValueError:
            logger.debug(f"url_filter: skip unparseable {url!r}")
            continue
        if parsed.scheme not in ("http", "https"):
            logger.debug(f"url_filter: skip non-http scheme {url!r}")
            continue
        if parsed.netloc != base_netloc:
            logger.debug(f"url_filter: skip cross-host {url!r} (base={base_netloc})")
            continue
        url_prefix = _canonical_prefix(parsed.path)
        if not url_prefix.startswith(base_prefix):
            logger.debug(f"url_filter: skip out-of-scope path {url!r} (not under {base_prefix})")
            continue
        if depth > 0:
            url_segments = len(_path_segments(parsed.path))
            extra = url_segments - base_segments
            if extra > depth:
                logger.debug(
                    f"url_filter: skip too-deep {url!r} "
                    f"(depth={extra}, max={depth})"
                )
                continue
        if url in seen:
            continue
        seen.add(url)
        kept.append(url)
    return kept
