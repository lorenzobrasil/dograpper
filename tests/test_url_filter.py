"""Tests for dograpper.lib.url_filter."""

from dograpper.lib.url_filter import filter_urls


def test_filter_same_netloc_only():
    urls = [
        "https://site.io/docs/a",
        "https://other.io/docs/a",
        "http://site.io/docs/b",  # different scheme, same netloc → kept
    ]
    kept = filter_urls(urls, "https://site.io/docs/")
    assert "https://site.io/docs/a" in kept
    assert "http://site.io/docs/b" in kept
    assert "https://other.io/docs/a" not in kept


def test_filter_path_prefix_canonicalization():
    """Regression: `/docs` must NOT match `/docsextra` (v1 Critic C-3)."""
    urls = [
        "https://site.io/docs/intro",
        "https://site.io/docs/api/ref",
        "https://site.io/docsextra/should-not-match",
        "https://site.io/docs-beta/nope",
        "https://site.io/other",
    ]
    kept = filter_urls(urls, "https://site.io/docs")
    assert "https://site.io/docs/intro" in kept
    assert "https://site.io/docs/api/ref" in kept
    assert "https://site.io/docsextra/should-not-match" not in kept
    assert "https://site.io/docs-beta/nope" not in kept
    assert "https://site.io/other" not in kept


def test_filter_depth_zero_no_limit():
    urls = [
        "https://site.io/docs/a",
        "https://site.io/docs/a/b/c/d/e",
    ]
    kept = filter_urls(urls, "https://site.io/docs/", depth=0)
    assert kept == urls


def test_filter_depth_bounded():
    urls = [
        "https://site.io/docs/a",          # depth 1
        "https://site.io/docs/a/b",        # depth 2
        "https://site.io/docs/a/b/c",      # depth 3 -- rejected at depth=2
    ]
    kept = filter_urls(urls, "https://site.io/docs/", depth=2)
    assert "https://site.io/docs/a" in kept
    assert "https://site.io/docs/a/b" in kept
    assert "https://site.io/docs/a/b/c" not in kept


def test_filter_dedupes_preserves_order():
    urls = [
        "https://site.io/docs/a",
        "https://site.io/docs/a",
        "https://site.io/docs/b",
        "https://site.io/docs/a",
    ]
    kept = filter_urls(urls, "https://site.io/docs/")
    assert kept == ["https://site.io/docs/a", "https://site.io/docs/b"]


def test_filter_rejects_base_url_missing_scheme():
    assert filter_urls(["https://site.io/x"], "site.io/docs") == []


def test_filter_accepts_root_base_url():
    urls = [
        "https://site.io/",
        "https://site.io/anything",
        "https://other.io/x",
    ]
    kept = filter_urls(urls, "https://site.io/")
    assert "https://site.io/" in kept
    assert "https://site.io/anything" in kept
    assert "https://other.io/x" not in kept
