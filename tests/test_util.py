import json
import tempfile
from pathlib import Path

import pytest

from rls.util import load_json, verify_empty_dir


def test_load_valid_json() -> None:
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
        json.dump({"key": "value"}, tmp)
        tmp_path = Path(tmp.name)
    assert load_json(tmp_path) == {"key": "value"}
    tmp_path.unlink()


def test_load_nonexistent_json() -> None:
    with pytest.raises(FileNotFoundError):
        load_json(Path("/nonexistent/path.json"))


def test_load_invalid_json() -> None:
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
        tmp.write("invalid json")
        tmp_path = Path(tmp.name)
    with pytest.raises(json.JSONDecodeError):
        load_json(tmp_path)
    tmp_path.unlink()


def test_verify_empty_dir() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        verify_empty_dir(Path(tmp_dir))


def test_verify_non_empty_dir() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        Path(tmp_dir, "file.txt").touch()
        with pytest.raises(ValueError, match="must be empty"):
            verify_empty_dir(Path(tmp_dir))


def test_verify_nonexistent_dir() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        non_existent_dir = Path(tmp_dir, "new_dir")
        verify_empty_dir(non_existent_dir)
        assert non_existent_dir.is_dir()


def test_verify_file_path_instead_of_dir() -> None:
    with tempfile.NamedTemporaryFile() as tmp_file, pytest.raises(
        OSError, match="File exists"
    ):
        verify_empty_dir(Path(tmp_file.name))
