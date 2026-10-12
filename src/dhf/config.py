"""Local configuration. Never emit credentials."""

import os
from pathlib import Path


def load_env(path: Path = Path(".env")) -> None:
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def setting(name: str, default: str = "") -> str:
    load_env()
    return os.environ.get(name, default)
