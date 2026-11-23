"""Local configuration. Never emit credentials or mutate the process environment."""

import os
from functools import cache
from pathlib import Path


@cache
def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.exists():
        # utf-8-sig: Windows editors may save a byte-order mark, which would hide the first key.
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def setting(name: str, default: str = "") -> str:
    values = load_env(Path(os.environ.get("DHF_ENV_FILE", ".env")))
    return os.environ.get(name, values.get(name, default))
