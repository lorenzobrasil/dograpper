"""Smoke tests for CLI."""

import pytest
from click.testing import CliRunner
from dograpper.cli import cli
import os

def test_help_main():
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'download' in result.output
    assert 'pack' in result.output

def test_help_download():
    runner = CliRunner()
    result = runner.invoke(cli, ['download', '--help'])
    assert result.exit_code == 0
    assert '--output' in result.output
    assert '--headless' in result.output

def test_help_pack():
    runner = CliRunner()
    result = runner.invoke(cli, ['pack', '--help'])
    assert result.exit_code == 0
    assert '--max-words-per-chunk' in result.output
    assert '--strategy' in result.output

def test_download_missing_url():
    runner = CliRunner()
    result = runner.invoke(cli, ['download', '-o', './out'])
    assert result.exit_code != 0
    assert 'Missing argument' in result.output

def test_pack_missing_input_dir():
    runner = CliRunner()
    result = runner.invoke(cli, ['pack', '-o', './out'])
    assert result.exit_code != 0
    assert 'Missing argument' in result.output

def test_mutually_exclusive_flags():
    runner = CliRunner()
    # It should error out before actually processing commands if verbose and quiet are together
    result = runner.invoke(cli, ['-v', '-q', 'download', 'https://example.com', '-o', './out'])
    assert result.exit_code != 0
    assert 'mutually exclusive' in result.output
