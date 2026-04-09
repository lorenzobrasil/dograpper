import os
import json
import tempfile
from unittest.mock import patch
import click

from dograpper.lib.wget_mirror import run_wget_mirror
from dograpper.lib.spa_detector import is_spa
from dograpper.lib.manifest import Manifest, ManifestEntry, load_manifest, save_manifest, merge_manifests
from dograpper.lib.config_loader import load_config

def test_merge_manifests_basic():
    old = Manifest("http://localhost", "2020", {
        "A.md": ManifestEntry("a/b", 100, etag="e1"),
        "B.md": ManifestEntry("b/b", 200, etag="e2")
    })
    new = Manifest("http://localhost", "2021", {
        "B.md": ManifestEntry("b/b", 999), # changed size
        "C.md": ManifestEntry("c/c", 300)
    })
    
    merged = merge_manifests(old, new)
    
    assert "A.md" not in merged.files
    assert "B.md" in merged.files
    assert "C.md" in merged.files
    
    assert merged.files["B.md"].etag is None # Size changed, etag lost
    assert merged.files["B.md"].size_bytes == 999
    assert merged.last_run == "2021"

def test_merge_manifests_preserves_etag():
    old = Manifest("http://localhost", "2020", {
        "A.md": ManifestEntry("a/b", 100, etag="e1", last_modified="lm")
    })
    new = Manifest("http://localhost", "2021", {
        "A.md": ManifestEntry("a/b", 100) # same size
    })
    
    merged = merge_manifests(old, new)
    assert merged.files["A.md"].etag == "e1"
    assert merged.files["A.md"].last_modified == "lm"

def test_merge_manifests_none_old():
    new = Manifest("http://localhost", "2021", {"A.md": ManifestEntry("a/b", 100)})
    merged = merge_manifests(None, new)
    assert "A.md" in merged.files

def test_wget_mirror_command_build():
    with patch('subprocess.run') as mock_run:
        # Mock successful wget
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""
        
        run_wget_mirror('http://example.com', './out', depth=2, delay=1500, include_extensions="html,md")
        
        args = mock_run.call_args[0][0]
        assert "wget" in args
        assert "--mirror" in args
        assert "--timestamping" not in args
        assert "--convert-links" in args
        assert "--level=2" in args
        assert "--wait=1.5" in args
        assert "--accept=html,md" in args
        assert "--directory-prefix=./out" in args
        assert "http://example.com" in args

def test_wget_incremental_flag():
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.returncode = 0
        
        run_wget_mirror('http://example.com', './out', incremental=True)
        args = mock_run.call_args[0][0]
        
        assert "wget" in args
        assert "--timestamping" in args
        assert "--mirror" not in args
        assert "--recursive" in args
        assert "--page-requisites" in args
        assert "--convert-links" in args

def test_wget_non_incremental():
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.returncode = 0
        
        run_wget_mirror('http://example.com', './out', incremental=False)
        args = mock_run.call_args[0][0]
        
        assert "--mirror" in args
        assert "--timestamping" not in args

def test_spa_detector_empty_shells():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create an empty shell HTML
        with open(os.path.join(temp_dir, 'index.html'), 'w') as f:
            f.write('<html><body><div id="root"></div></body></html>')
            
        assert is_spa(temp_dir) is True

def test_spa_detector_real_content():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create HTML with real content (> 200 chars to bypass minimum)
        with open(os.path.join(temp_dir, 'about.html'), 'w') as f:
            content = "A" * 250
            f.write(f'<html><body><p>{content}</p></body></html>')
            
        assert is_spa(temp_dir) is False

def test_manifest_roundtrip():
    with tempfile.TemporaryDirectory() as temp_dir:
        manifest_path = os.path.join(temp_dir, 'manifest.json')
        original = Manifest(
            base_url="http://example.com",
            last_run="2025-01-01T00:00:00Z",
            files={
                "index.html": ManifestEntry(url="http://example.com/", size_bytes=100)
            }
        )
        save_manifest(original, manifest_path)
        loaded = load_manifest(manifest_path)
        
        assert loaded is not None
        assert loaded.base_url == original.base_url
        assert loaded.last_run == original.last_run
        assert "index.html" in loaded.files
        assert loaded.files["index.html"].size_bytes == 100

def test_manifest_missing_file():
    loaded = load_manifest("/path/that/does/not/exist.json")
    assert loaded is None

def test_config_loader_precedence():
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, 'config.json')
        with open(config_path, 'w') as f:
            json.dump({
                "download": {
                    "depth": 5,
                    "delay": 200
                }
            }, f)
            
        cli_params = {
            "depth": 2, # explicit CLI flag
            "delay": 0, # implicit default
            "output": "./out"
        }
        
        class FakeSource:
            def __init__(self, name):
                self.name = name

        class FakeContext:
            def __init__(self):
                self.params = cli_params
            
            def get_parameter_source(self, param_name):
                if param_name == "depth":
                    return FakeSource("COMMANDLINE")
                return FakeSource("DEFAULT")

        fake_ctx = FakeContext()
        merged = load_config(config_path, 'download', cli_params, fake_ctx)
        
        assert merged["depth"] == 2 # CLI explicit beat JSON
        assert merged["delay"] == 200 # JSON beat default
        assert merged["output"] == "./out" # default preserved if not in JSON

def test_playwright_skips_cached():
    import sys
    from unittest.mock import MagicMock
    
    mock_playwright = MagicMock()
    mock_sync_api = MagicMock()
    mock_sync = mock_sync_api.sync_playwright
    mock_p = mock_sync.return_value.__enter__.return_value
    mock_page = mock_p.chromium.launch.return_value.new_context.return_value.new_page.return_value
    
    sys.modules['playwright'] = mock_playwright
    sys.modules['playwright.sync_api'] = mock_sync_api
    
    try:
        # Manifest mapping http://target.com to index.html
        m = Manifest("http://target.com", "", {
            "index.html": ManifestEntry("http://target.com", 100)
        })
        
        with tempfile.TemporaryDirectory() as d:
            # File exists on disk
            with open(os.path.join(d, "index.html"), "w") as f:
                f.write("content")
                
            from dograpper.lib.playwright_crawl import run_playwright_crawl
            res = run_playwright_crawl("http://target.com", d, manifest_data=m)
            
            # Assert goto was not called
            mock_page.goto.assert_not_called()
            assert res.files_skipped == 1
    finally:
        del sys.modules['playwright']
        del sys.modules['playwright.sync_api']

def test_playwright_redownloads_missing():
    import sys
    from unittest.mock import MagicMock
    
    mock_playwright = MagicMock()
    mock_sync_api = MagicMock()
    mock_sync = mock_sync_api.sync_playwright
    mock_p = mock_sync.return_value.__enter__.return_value
    mock_page = mock_p.chromium.launch.return_value.new_context.return_value.new_page.return_value
    mock_page.content.return_value = "<html><body>content</body></html>"
    mock_page.evaluate.return_value = []
    
    sys.modules['playwright'] = mock_playwright
    sys.modules['playwright.sync_api'] = mock_sync_api
    
    try:
        m = Manifest("http://target.com", "", {
            "index.html": ManifestEntry("http://target.com", 100)
        })
        
        with tempfile.TemporaryDirectory() as d:
            # DO NOT create index.html
            from dograpper.lib.playwright_crawl import run_playwright_crawl
            res = run_playwright_crawl("http://target.com", d, manifest_data=m)
            
            # Assert goto WAS called because file is missing
            mock_page.goto.assert_called_with("http://target.com", wait_until="networkidle")
            assert res.files_skipped == 0
    finally:
        del sys.modules['playwright']
        del sys.modules['playwright.sync_api']

from click.testing import CliRunner
from dograpper.commands.download import download

def test_download_wget_success():
    runner = CliRunner()
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.returncode = 0
        
        with tempfile.TemporaryDirectory() as d:
            from dograpper.lib.wget_mirror import WgetResult
            with patch('dograpper.commands.download.run_wget_mirror') as mock_wget:
                mock_wget.return_value = WgetResult(True, d, [os.path.join(d, "index.html")], [], 0)
                
                # Mock is_spa
                with patch('dograpper.commands.download.is_spa') as mock_is_spa:
                    mock_is_spa.return_value = False
                    
                    with open(os.path.join(d, "index.html"), "w") as f:
                        f.write("content")
                        
                    res = runner.invoke(download, ['http://example.com', '-o', d])
                    assert res.exit_code == 0
                    assert "Download complete" in res.output
                    assert "Files downloaded: 1" in res.output
                    assert mock_wget.called

def test_download_spa_fallback(caplog):
    import logging
    caplog.set_level(logging.INFO)
    runner = CliRunner()
    
    with tempfile.TemporaryDirectory() as d:
        from dograpper.lib.wget_mirror import WgetResult
        from dograpper.lib.playwright_crawl import CrawlResult
        with patch('dograpper.commands.download.run_wget_mirror') as mock_wget:
            mock_wget.return_value = WgetResult(True, d, [], [], 0)
            
            with patch('dograpper.commands.download.is_spa') as mock_is_spa:
                mock_is_spa.return_value = True
                
                with patch('dograpper.commands.download.run_playwright_crawl') as mock_pw:
                    mock_pw.return_value = CrawlResult(True, d, [os.path.join(d, "index.html")], [], 0)
                    
                    with open(os.path.join(d, "index.html"), "w") as f:
                        f.write("content fallback")
                        
                    res = runner.invoke(download, ['http://example.com', '-o', d])
                    assert res.exit_code == 0
                    assert "SPA detected, falling back to playwright" in caplog.text
                    mock_pw.assert_called()

def test_download_headless_skips_wget():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as d:
        from dograpper.lib.playwright_crawl import CrawlResult
        
        with patch('dograpper.commands.download.run_wget_mirror') as mock_wget:
            with patch('dograpper.commands.download.run_playwright_crawl') as mock_pw:
                mock_pw.return_value = CrawlResult(True, d, [os.path.join(d, "index.html")], [], 0)
                
                with open(os.path.join(d, "index.html"), "w") as f:
                    f.write("content")
                    
                res = runner.invoke(download, ['http://example.com', '-o', d, '--headless'])
                assert res.exit_code == 0
                mock_wget.assert_not_called()
                mock_pw.assert_called()

def test_download_incremental_second_run():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as d:
        manifest_path = os.path.join(d, ".dograpper-manifest.json")
        
        from dograpper.lib.wget_mirror import WgetResult
        with patch('dograpper.commands.download.run_wget_mirror') as mock_wget:
            mock_wget.return_value = WgetResult(True, d, [os.path.join(d, "index.html")], [], 0)
            with patch('dograpper.commands.download.is_spa') as mock_is_spa:
                mock_is_spa.return_value = False
                
                with open(os.path.join(d, "index.html"), "w") as f: f.write("1")
                
                # First run
                runner.invoke(download, ['http://example.com', '-o', d, '--manifest', manifest_path])
                args1 = mock_wget.call_args[1]
                assert args1.get('incremental', False) is False
                
                # Second run
                runner.invoke(download, ['http://example.com', '-o', d, '--manifest', manifest_path])
                args2 = mock_wget.call_args[1]
                assert args2.get('incremental', False) is True

def test_download_wget_not_installed():
    runner = CliRunner()
    from dograpper.lib.wget_mirror import run_wget_mirror
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = FileNotFoundError()
        
        with tempfile.TemporaryDirectory() as d:
            res = runner.invoke(download, ['http://example.com', '-o', d])
            assert res.exit_code != 0
            assert "wget is required" in res.output
