"""Automatic backups of unsaved work and recovery after a crash."""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QTimer

from manim_studio.logging_setup import log
from manim_studio.model.serialization import FILE_SUFFIX, ProjectFormatError, dumps_project, load_project
from manim_studio.ui.document import ProjectDocument

INTERVAL_MS = 60_000


@dataclass(frozen=True)
class Backup:
    """One recoverable autosave."""

    project_file: Path
    meta_file: Path
    original: str
    saved_at: float
    title: str


class AutoSaver(QObject):
    """Writes the project to a backup folder every minute while it has unsaved changes."""

    def __init__(self, document: ProjectDocument, folder: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.document = document
        self.folder = folder
        self._session = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self._timer = QTimer(self, interval=INTERVAL_MS)
        self._timer.timeout.connect(self.save_now)
        self._timer.start()
        self._key = self._make_key()
        document.pathChanged.connect(self._on_path_changed)
        document.dirtyChanged.connect(self._on_dirty_changed)

    def _make_key(self) -> str:
        source = str(self.document.path) if self.document.path else f"untitled-{self._session}"
        return hashlib.sha1(source.encode("utf-8")).hexdigest()[:16]

    def _files(self, key: str | None = None) -> tuple[Path, Path]:
        key = key or self._key
        return self.folder / f"{key}{FILE_SUFFIX}", self.folder / f"{key}.json"

    def _on_path_changed(self) -> None:
        self.discard()
        self._key = self._make_key()

    def _on_dirty_changed(self, dirty: bool) -> None:
        if not dirty:
            self.discard()

    def save_now(self) -> bool:
        """Back up the project if it has unsaved changes."""
        if not self.document.is_dirty:
            return False
        project_file, meta_file = self._files()
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            project_file.write_text(dumps_project(self.document.project), encoding="utf-8")
            meta = {"original": str(self.document.path or ""), "saved_at": time.time(), "session": self._session}
            meta_file.write_text(json.dumps(meta), encoding="utf-8")
        except OSError:
            log.exception("Autosave failed")
            return False
        return True

    def discard(self) -> None:
        """Remove the backup of the current document (after saving or discarding)."""
        for path in self._files():
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    def stop(self) -> None:
        """Stop backing up (the application closes normally)."""
        self._timer.stop()

    def backups(self) -> list[Backup]:
        """Backups left over from earlier sessions, newest first."""
        result = []
        for meta_file in self.folder.glob("*.json"):
            project_file = meta_file.with_suffix(FILE_SUFFIX)
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if meta.get("session") == self._session or not project_file.exists():
                continue
            original = str(meta.get("original", ""))
            title = Path(original).stem if original else ""
            result.append(Backup(project_file, meta_file, original, float(meta.get("saved_at", 0.0)), title))
        return sorted(result, key=lambda backup: backup.saved_at, reverse=True)

    def restore(self, backup: Backup) -> bool:
        """Load a backup into the document (unsaved, but with its original file name)."""
        try:
            project = load_project(backup.project_file)
        except (OSError, ProjectFormatError):
            log.exception("Could not restore %s", backup.project_file)
            return False
        self.document.restore(project, Path(backup.original) if backup.original else None)
        self.forget(backup)
        self.save_now()
        return True

    @staticmethod
    def forget(backup: Backup) -> None:
        """Delete a backup."""
        for path in (backup.project_file, backup.meta_file):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
