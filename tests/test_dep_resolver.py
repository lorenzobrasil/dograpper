import importlib
import os
import stat

import pytest


def test_resolve_wget_returns_user_bin_when_executable(tmp_path, monkeypatch):
    monkeypatch.setenv("DOGRAPPER_HOME", str(tmp_path))
    import dograpper.utils.dep_resolver as dep_resolver
    importlib.reload(dep_resolver)

    wget_bin = dep_resolver.USER_BIN_DIR / "wget"
    wget_bin.parent.mkdir(parents=True, exist_ok=True)
    wget_bin.write_text("#!/bin/sh\necho wget")
    wget_bin.chmod(wget_bin.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    result = dep_resolver.resolve_wget()
    assert result == str(wget_bin)


def test_resolve_wget_falls_back_to_path_wget(tmp_path, monkeypatch):
    monkeypatch.setenv("DOGRAPPER_HOME", str(tmp_path))
    import dograpper.utils.dep_resolver as dep_resolver
    importlib.reload(dep_resolver)

    system_wget = dep_resolver.shutil.which("wget")
    if system_wget is None:
        pytest.skip("wget not on PATH in this environment")

    result = dep_resolver.resolve_wget()
    assert result == system_wget


def test_resolve_wget_returns_literal_when_neither(tmp_path, monkeypatch):
    monkeypatch.setenv("DOGRAPPER_HOME", str(tmp_path))
    monkeypatch.setattr("shutil.which", lambda _: None)

    import dograpper.utils.dep_resolver as dep_resolver
    importlib.reload(dep_resolver)
    monkeypatch.setattr(dep_resolver.shutil, "which", lambda _: None)

    result = dep_resolver.resolve_wget()
    assert result == "wget"


def test_dograpper_home_env_overrides_constants(tmp_path, monkeypatch):
    custom_home = tmp_path / "foo"
    monkeypatch.setenv("DOGRAPPER_HOME", str(custom_home))

    import dograpper.utils.dep_resolver as dep_resolver
    importlib.reload(dep_resolver)

    assert dep_resolver.USER_BIN_DIR == custom_home / "bin"
    assert dep_resolver.USER_BROWSER_DIR == custom_home / "playwright-browsers"


def test_resolve_browser_dir_never_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("DOGRAPPER_HOME", str(tmp_path))
    import dograpper.utils.dep_resolver as dep_resolver
    importlib.reload(dep_resolver)

    result = dep_resolver.resolve_browser_dir()
    assert result and len(result) > 0
