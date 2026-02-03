from __future__ import annotations

from pathlib import Path


def data_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "data"


def resolve_data_file(path: str) -> Path:
    base = data_dir().resolve()
    candidate = Path(path)
    resolved = (base / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    if base not in resolved.parents and resolved != base:
        raise ValueError("file_path_must_be_within_data_dir")
    if not resolved.exists() or not resolved.is_file():
        raise FileNotFoundError("file_not_found")
    return resolved

