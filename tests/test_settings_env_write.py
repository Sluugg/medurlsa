"""
Covers app/routes/settings.py's _write_env_file() — deliberately writes .env
in place rather than via python-dotenv's set_key() (temp-file-plus-rename),
which fails against a single-file Docker bind mount.
"""

from dotenv import dotenv_values

from app.routes.settings import _write_env_file


def test_write_env_file_is_in_place_not_a_rename(tmp_path):
    path = tmp_path / ".env"
    path.write_text("EXISTING=value\n")
    inode_before = path.stat().st_ino

    _write_env_file(str(path), {"EXISTING": "updated"})

    assert path.stat().st_ino == inode_before


def test_write_env_file_round_trips_special_characters(tmp_path):
    path = tmp_path / ".env"
    path.write_text("")
    tricky = 'value#with spaces and "quotes" and \\backslash'

    _write_env_file(str(path), {"KEY": tricky})

    assert dotenv_values(str(path))["KEY"] == tricky


def test_write_env_file_preserves_comments_and_unrelated_lines(tmp_path):
    path = tmp_path / ".env"
    path.write_text("# a comment\nKEEP_ME=untouched\nCHANGE_ME=old\n")

    _write_env_file(str(path), {"CHANGE_ME": "new"})

    content = path.read_text()
    assert "# a comment" in content
    values = dotenv_values(str(path))
    assert values["KEEP_ME"] == "untouched"
    assert values["CHANGE_ME"] == "new"


def test_write_env_file_creates_file_if_missing(tmp_path):
    path = tmp_path / ".env"
    _write_env_file(str(path), {"NEW_KEY": "value"})
    assert dotenv_values(str(path))["NEW_KEY"] == "value"
