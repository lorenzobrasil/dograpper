from pathlib import Path
from click.testing import CliRunner
from dograpper.cli import cli

FIXTURE = Path(__file__).parent / "fixtures" / "help_baseline.txt"


def test_help_baseline_stable():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"], prog_name="dograpper")
    assert result.exit_code == 0
    baseline = FIXTURE.read_text(encoding="utf-8")
    assert result.output == baseline, (
        "dograpper --help drifted from baseline. "
        "If intentional, regenerate: uv run dograpper --help > tests/fixtures/help_baseline.txt"
    )


def test_help_lists_all_subcommands():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"], prog_name="dograpper")
    assert result.exit_code == 0
    for sub in ("download", "pack", "sync", "doctor"):
        assert sub in result.output, f"subcommand {sub!r} missing from help"
