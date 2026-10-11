"""Helpers for files referenced by a project (images)."""

from __future__ import annotations

from pathlib import Path


def resolve_asset_path(path: str, base_dir: str | Path | None) -> Path:
    """Return an absolute path; relative paths are resolved against ``base_dir``."""
    candidate = Path(path).expanduser()
    if candidate.is_absolute() or base_dir is None:
        return candidate
    return (Path(base_dir) / candidate).resolve()


def relative_asset_path(path: str, base_dir: str | Path | None) -> str:
    """Return ``path`` relative to ``base_dir`` when it lies inside it."""
    if base_dir is None or not path:
        return path
    try:
        return Path(path).resolve().relative_to(Path(base_dir).resolve()).as_posix()
    except ValueError:
        return path
