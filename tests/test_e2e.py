import os
import tempfile
import pytest
from click.testing import CliRunner

from dograpper.commands.pack import pack
from dograpper.utils.word_counter import count_words_file

# Determine test docs directory path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DOCS_DIR = os.path.join(BASE_DIR, 'test-docs', 'click.palletsprojects.com')

# Skip tests if test docs are not available
pytestmark = pytest.mark.skipif(
    not os.path.exists(TEST_DOCS_DIR), 
    reason="test-docs/click.palletsprojects.com directory not found"
)

def test_pack_real_html_docs():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as out_dir:
        result = runner.invoke(pack, [
            TEST_DOCS_DIR,
            '-o', out_dir,
            '--max-words-per-chunk', '5000'
        ])
        
        assert result.exit_code == 0
        
        # Multiple chunks should have been generated
        chunks = [f for f in os.listdir(out_dir) if f.endswith('.md')]
        assert len(chunks) > 1
        
        # Validate that chunk files do not contain HTML tags and match the expected format
        for chunk_file in chunks:
            chunk_path = os.path.join(out_dir, chunk_file)
            with open(chunk_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Exclude <script> and class attributes
                assert "<script>" not in content
                assert "class=" not in content
                assert "<nav>" not in content
                
                # Test word count heuristic (should be roughly equal)
                words = content.split()
                # Basic check, just verifying there's clean text
                assert len(words) > 0

def test_pack_real_docs_semantic():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as out_dir:
        result = runner.invoke(pack, [
            TEST_DOCS_DIR,
            '-o', out_dir,
            '--strategy', 'semantic'
        ])
        
        assert result.exit_code == 0
        chunks = [f for f in os.listdir(out_dir) if f.endswith('.md')]
        assert len(chunks) > 0
        
        # When using semantic, it groups by directories. Just verifying it runs successfully
        # with real files.

def test_pack_real_docs_with_ignore():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as out_dir:
        result = runner.invoke(pack, [
            TEST_DOCS_DIR,
            '-o', out_dir,
            '--ignore', '*.txt',
            '--ignore', '**/genindex/**' # Just an example if it existed, standard docs often have
        ])
        
        assert result.exit_code == 0
        chunks = [f for f in os.listdir(out_dir) if f.endswith('.md')]
        
        for chunk_file in chunks:
            chunk_path = os.path.join(out_dir, chunk_file)
            with open(chunk_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Ensure robots.txt is ignored
                assert "<!-- SOURCE: robots.txt -->" not in content
                assert "<!-- SOURCE: genindex/index.html -->" not in content

def test_pack_idempotency():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as out_dir1:
        with tempfile.TemporaryDirectory() as out_dir2:
            args = [TEST_DOCS_DIR, '--max-words-per-chunk', '5000']
            
            # Run 1
            res1 = runner.invoke(pack, args + ['-o', out_dir1])
            assert res1.exit_code == 0
            
            # Run 2
            res2 = runner.invoke(pack, args + ['-o', out_dir2])
            assert res2.exit_code == 0
            
            chunks1 = sorted(os.listdir(out_dir1))
            chunks2 = sorted(os.listdir(out_dir2))
            
            assert chunks1 == chunks2
            if not chunks1: # If empty for some reason, ignore
                return
                
            for c1, c2 in zip(chunks1, chunks2):
                with open(os.path.join(out_dir1, c1), 'rb') as f1:
                    with open(os.path.join(out_dir2, c2), 'rb') as f2:
                        assert f1.read() == f2.read()
