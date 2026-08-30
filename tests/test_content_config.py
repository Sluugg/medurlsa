"""
Covers app/content_config.py's handling of content_config.json — in
particular the Docker-specific case where a missing bind-mount source gets
auto-created as an empty directory rather than a file.
"""

import json

import pytest

import app.content_config as cc


@pytest.fixture(autouse=True)
def _restore_content_config():
    """save_content_config() mutates the module-level CONTENT_CONFIG dict in
    place — restore it after each test so tests don't leak state into
    whatever runs next."""
    original = dict(cc.CONTENT_CONFIG)
    yield
    cc.CONTENT_CONFIG.clear()
    cc.CONTENT_CONFIG.update(original)


def test_load_falls_back_to_defaults_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(cc, "_CONFIG_PATH", str(tmp_path / "does_not_exist.json"))
    assert cc._load() == cc._DEFAULTS


def test_load_falls_back_to_defaults_when_path_is_a_directory(tmp_path, monkeypatch):
    # Simulates Docker auto-creating a directory for a missing bind-mount
    # source — must NOT crash trying to open() a directory as a file.
    fake_path = tmp_path / "content_config.json"
    fake_path.mkdir()
    monkeypatch.setattr(cc, "_CONFIG_PATH", str(fake_path))
    assert cc._load() == cc._DEFAULTS


def test_save_content_config_raises_a_clear_error_on_directory(tmp_path, monkeypatch):
    fake_path = tmp_path / "content_config.json"
    fake_path.mkdir()
    monkeypatch.setattr(cc, "_CONFIG_PATH", str(fake_path))
    with pytest.raises(RuntimeError, match="isn't a regular file"):
        cc.save_content_config({"site_title": "test"})


def test_save_content_config_preserves_unmanaged_keys(tmp_path, monkeypatch):
    config_path = tmp_path / "content_config.json"
    config_path.write_text(json.dumps({"custom_unmanaged_key": "keep me"}))
    monkeypatch.setattr(cc, "_CONFIG_PATH", str(config_path))

    cc.save_content_config({"site_title": "New Title"})

    result = json.loads(config_path.read_text())
    assert result["custom_unmanaged_key"] == "keep me"
    assert result["site_title"] == "New Title"
