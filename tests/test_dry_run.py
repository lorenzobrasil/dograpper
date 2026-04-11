"""Tests for --dry-run mode in the pack command."""

import os
import tempfile

from click.testing import CliRunner

from dograpper.commands.pack import pack
from dograpper.utils.dry_run_report import (
    DryRunData,
    FileStats,
    generate_report,
    _truncate_path,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _create_html_files(tmp_path):
    """Create a directory with test HTML files."""
    input_dir = os.path.join(tmp_path, "input")
    os.makedirs(input_dir)
    with open(os.path.join(input_dir, "big.html"), "w") as f:
        f.write(
            "<html><body><main>"
            + "<p>Word </p>" * 3000
            + "</main></body></html>"
        )
    with open(os.path.join(input_dir, "small.html"), "w") as f:
        f.write(
            "<html><body><main>"
            + "<p>Word </p>" * 200
            + "</main></body></html>"
        )
    return input_dir


def _make_data(**overrides) -> DryRunData:
    """Create DryRunData with reasonable defaults."""
    defaults = dict(
        total_files_found=10,
        total_files_excluded=2,
        file_stats=[
            FileStats("docs/api.html", words_before_extraction=1000,
                      words_after_extraction=700),
            FileStats("docs/guide.html", words_before_extraction=500,
                      words_after_extraction=450),
            FileStats("docs/faq.html", words_before_extraction=200,
                      words_after_extraction=180),
        ],
        projected_chunks=3,
        max_chunks=50,
        max_words_per_chunk=5000,
        strategy="size",
        show_tokens=False,
        oversize_files=0,
    )
    defaults.update(overrides)
    return DryRunData(**defaults)


# ---------------------------------------------------------------------------
# Unit tests: generate_report
# ---------------------------------------------------------------------------

class TestGenerateReport:

    def test_report_contains_file_counts(self):
        data = _make_data()
        report = generate_report(data)
        assert "10" in report
        assert "2" in report

    def test_report_contains_word_counts(self):
        data = _make_data()
        report = generate_report(data)
        assert "1,700" in report   # total bruto: 1000+500+200
        assert "1,330" in report   # total extraido: 700+450+180

    def test_report_contains_reduction_percentage(self):
        data = _make_data()
        report = generate_report(data)
        # (1700-1330)/1700 = ~21%
        assert "21%" in report or "22%" in report

    def test_report_contains_chunk_projection(self):
        data = _make_data(projected_chunks=8, max_chunks=50)
        report = generate_report(data)
        assert "8 / 50" in report
        assert "5,000" in report

    def test_report_contains_strategy(self):
        data = _make_data(strategy="semantic")
        report = generate_report(data)
        assert "semantic" in report

    def test_report_shows_oversize_warning(self):
        data = _make_data(oversize_files=3)
        report = generate_report(data)
        assert "3" in report
        assert "oversize" in report.lower() or "excedem" in report.lower()

    def test_report_no_oversize_warning_when_zero(self):
        data = _make_data(oversize_files=0)
        report = generate_report(data)
        assert "oversize" not in report.lower()

    def test_report_top_10_sorted_by_words(self):
        data = _make_data()
        report = generate_report(data)
        lines = report.split("\n")
        ranking_lines = [l for l in lines if l.strip().startswith(("1.", "2.", "3."))]
        assert len(ranking_lines) == 3
        assert "api.html" in ranking_lines[0]

    def test_report_top_10_caps_at_10(self):
        stats = [
            FileStats(f"file_{i}.html",
                      words_before_extraction=100 + i * 10,
                      words_after_extraction=80 + i * 10)
            for i in range(15)
        ]
        data = _make_data(file_stats=stats)
        report = generate_report(data)
        # Count numbered lines (e.g. "  1. ...")
        import re
        ranking_lines = re.findall(r'^\s+\d+\.', report, re.MULTILINE)
        assert len(ranking_lines) == 10

    def test_report_with_tokens(self):
        stats = [
            FileStats("doc.html", words_before_extraction=1000,
                      words_after_extraction=700, tokens=945),
        ]
        data = _make_data(
            file_stats=stats,
            show_tokens=True,
            token_encoding="cl100k_base",
        )
        report = generate_report(data)
        assert "945" in report
        assert "cl100k_base" in report

    def test_report_without_tokens(self):
        data = _make_data(show_tokens=False)
        report = generate_report(data)
        assert "tok" not in report.lower() or "extração" in report.lower()

    def test_report_shows_projected_average(self):
        stats = [
            FileStats("a.html", 1000, 600),
            FileStats("b.html", 800, 400),
        ]
        data = _make_data(file_stats=stats, projected_chunks=2)
        report = generate_report(data)
        assert "500" in report

    def test_report_zero_chunks(self):
        data = _make_data(file_stats=[], projected_chunks=0)
        report = generate_report(data)
        assert "0" in report

    def test_report_dry_run_header(self):
        data = _make_data()
        report = generate_report(data)
        assert "dry-run" in report.lower() or "Dry-run" in report

    def test_report_footer_hint(self):
        data = _make_data()
        report = generate_report(data)
        assert "--dry-run" in report


# ---------------------------------------------------------------------------
# Unit tests: _truncate_path
# ---------------------------------------------------------------------------

class TestTruncatePath:

    def test_short_path_unchanged(self):
        assert _truncate_path("docs/api.html", max_len=40) == "docs/api.html"

    def test_long_path_truncated(self):
        path = "click.palletsprojects.com/en/stable/api/index.html"
        result = _truncate_path(path, max_len=30)
        assert result.startswith("...")
        assert result.endswith("index.html")
        assert len(result) == 30

    def test_exact_length_unchanged(self):
        path = "a" * 40
        assert _truncate_path(path, max_len=40) == path


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------

class TestDryRunCLI:

    def test_dry_run_does_not_create_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = _create_html_files(tmp)
            output_dir = os.path.join(tmp, "output")

            runner = CliRunner()
            result = runner.invoke(pack, [
                input_dir, "-o", output_dir, "--dry-run",
            ])

            assert result.exit_code == 0
            assert not os.path.exists(output_dir)

    def test_dry_run_does_not_write_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = _create_html_files(tmp)
            output_dir = os.path.join(tmp, "output")

            runner = CliRunner()
            result = runner.invoke(pack, [
                input_dir, "-o", output_dir, "--dry-run",
            ])

            assert result.exit_code == 0
            if os.path.exists(output_dir):
                assert len(list(os.listdir(output_dir))) == 0

    def test_dry_run_outputs_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = _create_html_files(tmp)
            output_dir = os.path.join(tmp, "output")

            runner = CliRunner()
            result = runner.invoke(pack, [
                input_dir, "-o", output_dir, "--dry-run",
            ])

            assert result.exit_code == 0
            output = result.output
            assert "dry-run" in output.lower() or "Dry-run" in output
            assert "big.html" in output or "small.html" in output

    def test_dry_run_with_show_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = _create_html_files(tmp)
            output_dir = os.path.join(tmp, "output")

            runner = CliRunner()
            result = runner.invoke(pack, [
                input_dir, "-o", output_dir, "--dry-run", "--show-tokens",
            ])

            assert result.exit_code == 0
            output = result.output
            assert "tok" in output.lower() or "token" in output.lower()

    def test_dry_run_without_show_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = _create_html_files(tmp)
            output_dir = os.path.join(tmp, "output")

            runner = CliRunner()
            result = runner.invoke(pack, [
                input_dir, "-o", output_dir, "--dry-run",
            ])

            assert result.exit_code == 0
            assert "encoding" not in result.output.lower()

    def test_dry_run_shows_oversize_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = _create_html_files(tmp)
            output_dir = os.path.join(tmp, "output")

            runner = CliRunner()
            result = runner.invoke(pack, [
                input_dir, "-o", output_dir,
                "--dry-run", "--max-words-per-chunk", "100",
            ])

            assert result.exit_code == 0
            assert "oversize" in result.output.lower() or "excedem" in result.output.lower()

    def test_dry_run_exit_code_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = _create_html_files(tmp)

            runner = CliRunner()
            result = runner.invoke(pack, [
                input_dir, "-o", os.path.join(tmp, "out"), "--dry-run",
            ])

            assert result.exit_code == 0

    def test_normal_pack_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = _create_html_files(tmp)
            output_dir = os.path.join(tmp, "output")

            runner = CliRunner()
            result = runner.invoke(pack, [
                input_dir, "-o", output_dir,
            ])

            assert result.exit_code == 0
            assert os.path.exists(output_dir)
            assert len(os.listdir(output_dir)) > 0

    def test_dry_run_shows_extraction_reduction(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = os.path.join(tmp, "input")
            os.makedirs(input_dir)
            with open(os.path.join(input_dir, "page.html"), "w") as f:
                f.write(
                    "<html><body>"
                    "<nav>" + "<a href='#'>Link</a> " * 50 + "</nav>"
                    "<main><p>" + "Conteudo real. " * 200 + "</p></main>"
                    "<footer>" + "Footer text. " * 30 + "</footer>"
                    "</body></html>"
                )

            runner = CliRunner()
            result = runner.invoke(pack, [
                input_dir, "-o", os.path.join(tmp, "out"), "--dry-run",
            ])

            assert result.exit_code == 0
            assert "%" in result.output

    def test_dry_run_empty_input_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = os.path.join(tmp, "empty")
            os.makedirs(input_dir)

            runner = CliRunner()
            result = runner.invoke(pack, [
                input_dir, "-o", os.path.join(tmp, "out"), "--dry-run",
            ])

            # Empty dir triggers ClickException before dry-run, that's fine
            assert "Traceback" not in result.output
