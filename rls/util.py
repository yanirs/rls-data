"""Various utilities."""
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    """Read and parse the JSON file at path."""
    with path.open() as fp:
        return json.load(fp)


def verify_empty_dir(dir_path: Path) -> None:
    """Verify that dir_path is an empty directory, creating it if it doesn't exist."""
    if not dir_path.is_dir():
        dir_path.mkdir(parents=True)
    if list(dir_path.glob("*")):
        raise ValueError(f"{dir_path} must be empty")
