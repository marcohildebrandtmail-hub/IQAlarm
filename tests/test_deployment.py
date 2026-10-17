"""Packaging and replacement must be reproducible, scoped and recoverable."""

import ast
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from scripts.bind_repository import bind
from scripts.deploy import inside, install
from scripts.package_release import package


def test_release_zip_contains_entire_buildless_integration(tmp_path):
    archive = package(tmp_path / "first")
    repeat = package(tmp_path / "second")
    assert (
        hashlib.sha256(archive.read_bytes()).digest()
        == hashlib.sha256(repeat.read_bytes()).digest()
    )
    with zipfile.ZipFile(archive) as contents:
        assert "custom_components/iqalarm/frontend/iqalarm-panel.js" in contents.namelist()
        assert "custom_components/iqalarm/translations/de.json" in contents.namelist()
        assert all(
            n.startswith("custom_components/iqalarm/") and "__pycache__" not in n
            for n in contents.namelist()
        )


def test_deployment_backs_up_existing_integration(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.deploy.shutil.which", lambda _: None)
    config, source = tmp_path / "config", tmp_path / "source"
    config.mkdir()
    (config / "configuration.yaml").write_text("default_config:\n")
    old = config / "custom_components" / "iqalarm"
    old.mkdir(parents=True)
    (old / "version.txt").write_text("old")
    source.mkdir()
    (source / "version.txt").write_text("new")
    result = install(source, config)
    assert (old / "version.txt").read_text() == "new"
    assert (Path(result["backup"]) / "version.txt").read_text() == "old"
    assert not list((config / "custom_components").glob(".iqalarm-stage-*"))


def test_failed_restart_rolls_back_without_ha_cli(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.deploy.shutil.which", lambda _: None)
    config, source = tmp_path / "config", tmp_path / "source"
    config.mkdir()
    (config / "configuration.yaml").write_text("default_config:\n")
    old = config / "custom_components" / "iqalarm"
    old.mkdir(parents=True)
    (old / "version.txt").write_text("old")
    source.mkdir()
    (source / "version.txt").write_text("new")
    with pytest.raises(ValueError, match="ha-CLI"):
        install(source, config, restart=True)
    assert (old / "version.txt").read_text() == "old"


def test_deployment_rejects_non_ha_directory(tmp_path):
    with pytest.raises(ValueError, match="Home-Assistant"):
        install(tmp_path, tmp_path)


def test_paths_cannot_escape_config(tmp_path):
    with pytest.raises(ValueError):
        inside(tmp_path / ".." / "outside", tmp_path)
    with pytest.raises(ValueError):
        inside(tmp_path, tmp_path)


def test_no_unimplemented_production_functions():
    root = Path(__file__).resolve().parents[1] / "custom_components" / "iqalarm"
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert not any(isinstance(node, ast.Pass) for node in ast.walk(tree)), path
        assert not any(
            isinstance(node, ast.Constant) and node.value is Ellipsis for node in ast.walk(tree)
        ), path


def test_binding_repository_keeps_manifest_order(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.bind_repository.ROOT", tmp_path)
    manifest_path = tmp_path / "custom_components" / "iqalarm" / "manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({"domain": "iqalarm", "name": "IQAlarm", "version": "1.0.0"})
    )
    assert (
        bind("https://github.com/marcohildebrandtmail-hub/IQAlarm")
        == "https://github.com/marcohildebrandtmail-hub/IQAlarm"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert list(manifest)[:2] == ["domain", "name"]
    assert list(manifest)[2:] == sorted(list(manifest)[2:])
    assert manifest["issue_tracker"].endswith("/IQAlarm/issues")
