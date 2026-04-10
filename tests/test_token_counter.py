"""Tests for the token counting utilities."""

import os
import tempfile
import pytest
from click.testing import CliRunner

from dograpper.utils.token_counter import (
    TokenCount,
    count_tokens,
    count_tokens_file,
    format_token_summary,
    SUPPORTED_ENCODINGS,
)
from dograpper.cli import cli


# ---------------------------------------------------------------------------
# TokenCount dataclass
# ---------------------------------------------------------------------------

class TestTokenCountDataclass:
    def test_fields(self):
        tc = TokenCount(words=100, tokens=135, encoding="cl100k_base")
        assert tc.words == 100
        assert tc.tokens == 135
        assert tc.encoding == "cl100k_base"


# ---------------------------------------------------------------------------
# count_tokens
# ---------------------------------------------------------------------------

class TestCountTokens:

    def test_empty_text(self):
        result = count_tokens("")
        assert result.words == 0
        assert result.tokens == 0

    def test_cl100k_alias(self):
        result = count_tokens("Hello world", encoding="cl100k")
        assert result.encoding == "cl100k_base"
        assert result.words == 2
        assert result.tokens > 0

    def test_o200k_alias(self):
        result = count_tokens("Hello world", encoding="o200k")
        assert result.encoding == "o200k_base"

    def test_p50k_alias(self):
        result = count_tokens("Hello world", encoding="p50k")
        assert result.encoding == "p50k_base"

    def test_full_encoding_name(self):
        result = count_tokens("Hello world", encoding="cl100k_base")
        assert result.encoding == "cl100k_base"

    def test_invalid_encoding_raises(self):
        with pytest.raises(ValueError, match="não reconhecido"):
            count_tokens("Hello", encoding="nonexistent_encoding")

    def test_longer_text_token_count(self):
        text = "The quick brown fox jumps over the lazy dog. " * 10
        result = count_tokens(text, encoding="cl100k")
        assert result.tokens > 0
        assert result.words == 90

    def test_single_word(self):
        result = count_tokens("hello")
        assert result.words == 1
        assert result.tokens > 0


# ---------------------------------------------------------------------------
# count_tokens_file
# ---------------------------------------------------------------------------

class TestCountTokensFile:

    def test_reads_file_and_counts(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("one two three four five")
            f.flush()
            try:
                result = count_tokens_file(f.name)
                assert result.words == 5
                assert result.tokens > 0
            finally:
                os.unlink(f.name)

    def test_tolerant_encoding(self):
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write(b"hello \xff\xfe world")
            f.flush()
            try:
                result = count_tokens_file(f.name)
                assert result.words > 0
            finally:
                os.unlink(f.name)

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("")
            f.flush()
            try:
                result = count_tokens_file(f.name)
                assert result.words == 0
                assert result.tokens == 0
            finally:
                os.unlink(f.name)


# ---------------------------------------------------------------------------
# format_token_summary
# ---------------------------------------------------------------------------

class TestFormatTokenSummary:

    def test_empty_list(self):
        result = format_token_summary([])
        assert "nenhum chunk" in result

    def test_single_chunk(self):
        counts = [TokenCount(words=100, tokens=135, encoding="cl100k_base")]
        result = format_token_summary(counts)
        assert "135" in result
        assert "cl100k_base" in result

    def test_multiple_chunks(self):
        counts = [
            TokenCount(words=100, tokens=130, encoding="cl100k_base"),
            TokenCount(words=200, tokens=270, encoding="cl100k_base"),
        ]
        result = format_token_summary(counts)
        assert "400" in result  # total
        assert "cl100k_base" in result

    def test_formatting_dot_separator(self):
        counts = [TokenCount(words=10000, tokens=13500, encoding="cl100k_base")]
        result = format_token_summary(counts)
        assert "13.500" in result


# ---------------------------------------------------------------------------
# CLI integration (pack --show-tokens)
# ---------------------------------------------------------------------------

class TestPackShowTokensCLI:

    def test_show_tokens_flag(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "doc.txt").write_text("word " * 100)

        output_dir = tmp_path / "output"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "pack", str(input_dir), "-o", str(output_dir), "--show-tokens"
        ])
        assert result.exit_code == 0
        assert "Tokens per chunk" in result.output or "Total tokens" in result.output

    def test_no_show_tokens_by_default(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "doc.txt").write_text("word " * 50)

        output_dir = tmp_path / "output"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "pack", str(input_dir), "-o", str(output_dir)
        ])
        assert result.exit_code == 0
        assert "Tokens per chunk" not in result.output
        assert "Total tokens" not in result.output

    def test_show_tokens_with_encoding(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "doc.txt").write_text("word " * 100)

        output_dir = tmp_path / "output"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "pack", str(input_dir), "-o", str(output_dir),
            "--show-tokens", "--token-encoding", "o200k"
        ])
        assert result.exit_code == 0

    def test_show_tokens_with_html_extraction(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "page.html").write_text("""
        <html><body>
            <nav>Nav</nav>
            <main><p>Main content with several words here.</p></main>
            <footer>Footer</footer>
        </body></html>
        """)

        output_dir = tmp_path / "output"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "pack", str(input_dir), "-o", str(output_dir), "--show-tokens"
        ])
        assert result.exit_code == 0
