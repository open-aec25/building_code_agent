"""Runtime configuration helpers."""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv_if_present(path: Path | None = None) -> None:
    """Load simple KEY=VALUE pairs from .env without overriding the shell."""
    env_path = path or Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        name, value = line.split("=", 1)
        name = name.strip()
        if not name or not name.replace("_", "").isalnum() or name[0].isdigit():
            continue

        os.environ.setdefault(name, value.strip().strip('"').strip("'"))
