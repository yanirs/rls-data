from pathlib import Path


def verify_empty_dir(dir_path: Path):
    """Verify that dir_path is an empty directory, creating it if it doesn't exist."""
    if not dir_path.is_dir():
        dir_path.mkdir(parents=True)
    if list(dir_path.glob("*")):
        raise ValueError(f"{dir_path} must be empty")
