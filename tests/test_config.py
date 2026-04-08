import os
import json
import pytest
import click
from click.testing import CliRunner
import tempfile

from dograpper.lib.config_loader import load_config

def test_config_loader_missing_file():
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, "does_not_exist.json")
        
        # Mock click ctx
        @click.command()
        @click.option('--foo', default="default_foo")
        def dummy(foo):
            pass
            
        runner = CliRunner()
        # Create a mock context to test
        ctx = click.Context(dummy)
        ctx.params = {'foo': 'cli_foo'}
        
        # Missing file should not raise an error, just return defaults and cli overrides
        cli_params = {'foo': 'cli_foo'}
        
        final_params = load_config(config_path, "dummy_cmd", cli_params, ctx)
        assert final_params['foo'] == 'cli_foo'

def test_config_loader_invalid_json():
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, "bad.json")
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write("{ bad json formatting")
            
        @click.command()
        def dummy():
            pass
            
        ctx = click.Context(dummy)
        
        with pytest.raises(click.ClickException) as excinfo:
            load_config(config_path, "dummy_cmd", {}, ctx)
            
        assert "Invalid JSON in config file" in str(excinfo.value)
