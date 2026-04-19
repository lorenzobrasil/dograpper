"""Integration tests for the 4-layer download cascade.

Scenarios (v2 plan § I test plan):
  1. layer-1 (llms.txt) wins → run_wget_urls is called, run_wget_mirror is not
  2. layer-2 (sitemap) wins → run_wget_urls called with sitemap URLs
  3. layer-3 (wget --mirror) wins when layers 1+2 come up empty
  4. layer-4 (playwright) fallback on SPA after layer 3
  5. layer-1 below threshold falls through to layer 2
  6. all layers fail gracefully (headless with 0 URLs → direct playwright)
"""

import os
import tempfile
from unittest.mock import patch

from click.testing import CliRunner

from dograpper.commands.download import (
    MIN_URLS_TO_CONSIDER_DISCOVERED,
    download,
)
from dograpper.lib.playwright_crawl import CrawlResult
from dograpper.lib.wget_mirror import WgetResult


def _make_outdir(d, files):
    for rel in files:
        full = os.path.join(d, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write("<html><body><p>" + "A" * 300 + "</p></body></html>")
    return [os.path.join(d, r) for r in files]


def test_cascade_layer1_llms_txt_wins():
    runner = CliRunner()
    discovered = [f"http://example.com/p{i}" for i in range(5)]

    with tempfile.TemporaryDirectory() as d:
        files = _make_outdir(d, [f"example.com/p{i}.html" for i in range(5)])
        with patch("dograpper.commands.download.fetch_llms_txt", return_value=discovered), \
             patch("dograpper.commands.download.fetch_sitemap") as mock_sitemap, \
             patch("dograpper.commands.download.run_wget_urls") as mock_wget_urls, \
             patch("dograpper.commands.download.run_wget_mirror") as mock_wget_mirror, \
             patch("dograpper.commands.download.run_playwright_crawl") as mock_pw, \
             patch("dograpper.commands.download.is_spa", return_value=False):

            mock_wget_urls.return_value = WgetResult(True, d, files, [], 0)
            res = runner.invoke(download, ["http://example.com", "-o", d])

            assert res.exit_code == 0, res.output
            assert mock_wget_urls.called
            mock_wget_mirror.assert_not_called()
            mock_sitemap.assert_not_called()  # layer-1 short-circuits layer-2
            mock_pw.assert_not_called()


def test_cascade_layer2_sitemap_wins_when_llms_empty():
    runner = CliRunner()
    sitemap_urls = [f"http://example.com/docs/p{i}" for i in range(4)]

    with tempfile.TemporaryDirectory() as d:
        files = _make_outdir(d, [f"example.com/docs/p{i}.html" for i in range(4)])
        with patch("dograpper.commands.download.fetch_llms_txt", return_value=[]), \
             patch("dograpper.commands.download.fetch_sitemap", return_value=sitemap_urls), \
             patch("dograpper.commands.download.run_wget_urls") as mock_wget_urls, \
             patch("dograpper.commands.download.run_wget_mirror") as mock_wget_mirror, \
             patch("dograpper.commands.download.is_spa", return_value=False):

            mock_wget_urls.return_value = WgetResult(True, d, files, [], 0)
            res = runner.invoke(download, ["http://example.com", "-o", d])

            assert res.exit_code == 0, res.output
            assert mock_wget_urls.called
            passed_urls = mock_wget_urls.call_args[0][0]
            assert set(passed_urls) == set(sitemap_urls)
            mock_wget_mirror.assert_not_called()


def test_cascade_layer3_wget_mirror_when_layers12_empty():
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as d:
        files = _make_outdir(d, [
            "example.com/index.html",
            "example.com/a.html",
            "example.com/b.html",
        ])
        with patch("dograpper.commands.download.fetch_llms_txt", return_value=[]), \
             patch("dograpper.commands.download.fetch_sitemap", return_value=[]), \
             patch("dograpper.commands.download.run_wget_urls") as mock_wget_urls, \
             patch("dograpper.commands.download.run_wget_mirror") as mock_wget_mirror, \
             patch("dograpper.commands.download.run_playwright_crawl") as mock_pw, \
             patch("dograpper.commands.download.is_spa", return_value=False):

            mock_wget_mirror.return_value = WgetResult(True, d, files, [], 0)
            res = runner.invoke(download, ["http://example.com", "-o", d])

            assert res.exit_code == 0, res.output
            mock_wget_urls.assert_not_called()
            assert mock_wget_mirror.called
            mock_pw.assert_not_called()


def test_cascade_layer4_playwright_fallback_after_mirror_spa(caplog):
    """Layer 3 succeeds but is_spa is True → layer 4 playwright kicks in."""
    import logging
    caplog.set_level(logging.INFO)

    runner = CliRunner()
    with tempfile.TemporaryDirectory() as d:
        mirror_files = _make_outdir(d, ["example.com/index.html"])
        pw_files = _make_outdir(d, ["example.com/fresh.html"])
        with patch("dograpper.commands.download.fetch_llms_txt", return_value=[]), \
             patch("dograpper.commands.download.fetch_sitemap", return_value=[]), \
             patch("dograpper.commands.download.run_wget_mirror") as mock_wget_mirror, \
             patch("dograpper.commands.download.run_playwright_crawl") as mock_pw, \
             patch("dograpper.commands.download.is_spa", return_value=True):

            mock_wget_mirror.return_value = WgetResult(True, d, mirror_files, [], 0)
            mock_pw.return_value = CrawlResult(True, d, pw_files, [], 0)
            res = runner.invoke(download, ["http://example.com", "-o", d])

            assert res.exit_code == 0, res.output
            assert mock_pw.called
            assert "SPA detected, falling back to playwright" in caplog.text


def test_cascade_layer3_shallow_mirror_forces_playwright(caplog):
    """wget --mirror producing <=1 HTML → force playwright.

    Covers the Mintlify-class case where is_spa() misses a lone SPA shell
    (total_files < SMALL_SAMPLE_N with only 1 file, no standard SPA id,
    but recursion obviously failed to follow any link).
    """
    import logging
    caplog.set_level(logging.INFO)

    runner = CliRunner()
    with tempfile.TemporaryDirectory() as d:
        mirror_files = _make_outdir(d, ["example.com/index.html"])
        pw_files = _make_outdir(
            d, [f"example.com/p{i}.html" for i in range(5)]
        )
        with patch("dograpper.commands.download.fetch_llms_txt", return_value=[]), \
             patch("dograpper.commands.download.fetch_sitemap", return_value=[]), \
             patch("dograpper.commands.download.run_wget_mirror") as mock_wget_mirror, \
             patch("dograpper.commands.download.run_playwright_crawl") as mock_pw, \
             patch("dograpper.commands.download.is_spa", return_value=False):

            mock_wget_mirror.return_value = WgetResult(True, d, mirror_files, [], 0)
            mock_pw.return_value = CrawlResult(True, d, pw_files, [], 0)
            res = runner.invoke(download, ["http://example.com", "-o", d])

            assert res.exit_code == 0, res.output
            assert mock_pw.called, "playwright must rescue the shallow mirror"
            assert "yielded only 1 HTML" in caplog.text


def test_cascade_layer1_below_threshold_falls_through():
    """2-URL llms.txt stub below MIN_URLS must fall through to layer 2."""
    assert MIN_URLS_TO_CONSIDER_DISCOVERED >= 3  # contract

    runner = CliRunner()
    stub = ["http://example.com/stub1", "http://example.com/stub2"]  # < 3
    sitemap_urls = [f"http://example.com/p{i}" for i in range(4)]

    with tempfile.TemporaryDirectory() as d:
        files = _make_outdir(d, [f"example.com/p{i}.html" for i in range(4)])
        with patch("dograpper.commands.download.fetch_llms_txt", return_value=stub), \
             patch("dograpper.commands.download.fetch_sitemap", return_value=sitemap_urls) as mock_sm, \
             patch("dograpper.commands.download.run_wget_urls") as mock_wget_urls, \
             patch("dograpper.commands.download.is_spa", return_value=False):

            mock_wget_urls.return_value = WgetResult(True, d, files, [], 0)
            res = runner.invoke(download, ["http://example.com", "-o", d])

            assert res.exit_code == 0, res.output
            assert mock_sm.called  # layer-2 actually reached
            passed_urls = mock_wget_urls.call_args[0][0]
            assert set(passed_urls) == set(sitemap_urls)


def test_cascade_headless_still_runs_layers_1_and_2():
    """Critic M-2: layers 1+2 must run regardless of --headless."""
    runner = CliRunner()
    discovered = [f"http://example.com/p{i}" for i in range(4)]

    with tempfile.TemporaryDirectory() as d:
        pw_files = _make_outdir(d, [f"example.com/p{i}.html" for i in range(4)])
        with patch("dograpper.commands.download.fetch_llms_txt", return_value=discovered) as mock_llms, \
             patch("dograpper.commands.download.fetch_sitemap") as mock_sm, \
             patch("dograpper.commands.download.run_wget_urls") as mock_wget_urls, \
             patch("dograpper.commands.download.run_wget_mirror") as mock_wget_mirror, \
             patch("dograpper.commands.download.run_playwright_crawl") as mock_pw:

            mock_pw.return_value = CrawlResult(True, d, pw_files, [], 0)
            res = runner.invoke(download, ["http://example.com", "-o", d, "--headless"])

            assert res.exit_code == 0, res.output
            mock_llms.assert_called()  # layer-1 ran even with --headless
            mock_wget_urls.assert_not_called()  # no wget when --headless
            mock_wget_mirror.assert_not_called()
            assert mock_pw.called

            call_kwargs = mock_pw.call_args.kwargs
            seed = call_kwargs.get("seed_urls")
            assert seed is not None
            assert set(seed) == set(discovered)


def test_cascade_post_wget_i_spa_falls_through_to_playwright(caplog):
    """Layer-1 "wins" but fetched pages are empty shells → playwright re-hydrates."""
    import logging
    caplog.set_level(logging.INFO)

    runner = CliRunner()
    discovered = [f"http://example.com/p{i}" for i in range(5)]

    with tempfile.TemporaryDirectory() as d:
        wget_files = _make_outdir(d, [f"example.com/p{i}.html" for i in range(5)])
        pw_files = _make_outdir(d, [f"example.com/p{i}-fresh.html" for i in range(5)])
        with patch("dograpper.commands.download.fetch_llms_txt", return_value=discovered), \
             patch("dograpper.commands.download.fetch_sitemap", return_value=[]), \
             patch("dograpper.commands.download.run_wget_urls") as mock_wget_urls, \
             patch("dograpper.commands.download.run_playwright_crawl") as mock_pw, \
             patch("dograpper.commands.download.is_spa", return_value=True):

            mock_wget_urls.return_value = WgetResult(True, d, wget_files, [], 0)
            mock_pw.return_value = CrawlResult(True, d, pw_files, [], 0)
            res = runner.invoke(download, ["http://example.com", "-o", d])

            assert res.exit_code == 0, res.output
            assert mock_pw.called
            seed = mock_pw.call_args.kwargs.get("seed_urls")
            assert set(seed) == set(discovered)
            assert "SPA detected" in caplog.text


def test_e2e_pack_delta_after_cascade_run():
    """Run the cascade end-to-end against a mocked layer-1 win, then pack the output.

    Ensures the downloaded layout remains compatible with `pack --delta`.
    """
    from dograpper.commands.pack import pack as pack_cmd

    runner = CliRunner()
    discovered = [f"http://example.com/docs/p{i}" for i in range(4)]

    with tempfile.TemporaryDirectory() as d:
        files = _make_outdir(d, [f"example.com/docs/p{i}.html" for i in range(4)])
        with patch("dograpper.commands.download.fetch_llms_txt", return_value=discovered), \
             patch("dograpper.commands.download.fetch_sitemap", return_value=[]), \
             patch("dograpper.commands.download.run_wget_urls") as mock_wget_urls, \
             patch("dograpper.commands.download.is_spa", return_value=False):

            mock_wget_urls.return_value = WgetResult(True, d, files, [], 0)
            dl_res = runner.invoke(download, ["http://example.com", "-o", d])
            assert dl_res.exit_code == 0, dl_res.output

        # Pack the output tree — should produce at least one chunk.
        with tempfile.TemporaryDirectory() as out_dir:
            pack_res = runner.invoke(pack_cmd, [d, "-o", out_dir, "--max-words-per-chunk", "5000"])
            assert pack_res.exit_code == 0, pack_res.output
            chunks = [f for f in os.listdir(out_dir) if f.endswith(".md")]
            assert len(chunks) >= 1


def test_cascade_emits_observability_log_lines(caplog):
    import logging
    caplog.set_level(logging.INFO)

    runner = CliRunner()
    with tempfile.TemporaryDirectory() as d:
        files = _make_outdir(d, ["example.com/index.html"])
        with patch("dograpper.commands.download.fetch_llms_txt", return_value=[]), \
             patch("dograpper.commands.download.fetch_sitemap", return_value=[]), \
             patch("dograpper.commands.download.run_wget_mirror") as mock_wget_mirror, \
             patch("dograpper.commands.download.is_spa", return_value=False):
            mock_wget_mirror.return_value = WgetResult(True, d, files, [], 0)
            runner.invoke(download, ["http://example.com", "-o", d])

    text = caplog.text
    assert "[cascade] layer-1 llms.txt: probing" in text
    assert "[cascade] layer-2 sitemap.xml: probing" in text
    assert "[cascade] layer-3 wget --mirror" in text
