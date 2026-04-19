"""Regression tests for `dograpper sync` flag pass-through."""

from unittest.mock import patch

from click.testing import CliRunner

from dograpper.cli import cli
from dograpper.commands.download import download as download_cmd
from dograpper.commands.pack import pack as pack_cmd


def _capture_calls():
    """Build stub callbacks for download and pack that record their kwargs."""
    captured = {"download": None, "pack": None}

    def _dl(**kwargs):
        captured["download"] = kwargs

    def _pk(**kwargs):
        captured["pack"] = kwargs

    return captured, _dl, _pk


def _run_sync(args):
    captured, dl_stub, pk_stub = _capture_calls()
    with patch.object(download_cmd, 'callback', dl_stub), \
         patch.object(pack_cmd, 'callback', pk_stub):
        result = CliRunner().invoke(cli, ['sync'] + args)
    return result, captured


def test_sync_accepts_pack_flags_without_error():
    """Sync must accept all pack-related flags promised by the README.

    Regression: users reported `--context-header` raising 'No such option'
    because sync was a thin wrapper that only forwarded a subset of pack flags.
    """
    result, captured = _run_sync([
        'https://example.com',
        '-o', './out',
        '--context-header',
        '--score',
        '--cross-refs',
        '--format', 'md',
        '--bundle', 'notebooklm',
    ])
    assert result.exit_code == 0, f"sync rejected flags: {result.output}"
    pk = captured["pack"]
    assert pk is not None
    assert pk["context_header"] is True
    assert pk["score"] is True
    assert pk["cross_refs"] is True
    assert pk["bundle"] == "notebooklm"
    assert pk["delta"] is True


def test_sync_forwards_download_flags():
    """Sync must forward download-specific flags (--headless, --depth, --delay)."""
    result, captured = _run_sync([
        'https://spa.example.com',
        '-o', './out',
        '--headless',
        '--depth', '2',
        '--delay', '500',
    ])
    assert result.exit_code == 0, f"sync rejected download flags: {result.output}"
    dl = captured["download"]
    assert dl is not None
    assert dl["headless"] is True
    assert dl["depth"] == 2
    assert dl["delay"] == 500


def test_sync_forwards_pack_flags():
    """Sync must forward pack-specific flags (dedup, show-tokens, strategy)."""
    result, captured = _run_sync([
        'https://example.com',
        '-o', './out',
        '--strategy', 'semantic',
        '--dedup', 'both',
        '--show-tokens',
        '--max-chunks', '30',
    ])
    assert result.exit_code == 0, f"sync rejected pack flags: {result.output}"
    pk = captured["pack"]
    assert pk is not None
    assert pk["strategy"] == "semantic"
    assert pk["dedup"] == "both"
    assert pk["show_tokens"] is True
    assert pk["max_chunks"] == 30
