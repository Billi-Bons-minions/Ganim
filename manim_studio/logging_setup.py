"""Application log file, uncaught exceptions and Qt message routing."""

from __future__ import annotations

import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType
from typing import Callable

LOGGER_NAME = "manim_studio"
LOG_FILE_NAME = "manim_studio.log"
MAX_LOG_BYTES = 2_000_000

#: Qt logging categories that only produce noise on the terminal.
QUIET_QT_RULES = "qt.multimedia*=false;qt.qpa.wayland*=false;qt.qpa.xcb*=false"

log = logging.getLogger(LOGGER_NAME)


def quiet_qt_logging() -> None:
    """Silence noisy Qt categories (must run before ``QApplication`` exists)."""
    if os.environ.get("MANIM_STUDIO_DEBUG"):
        return
    existing = os.environ.get("QT_LOGGING_RULES", "")
    os.environ["QT_LOGGING_RULES"] = ";".join(rule for rule in (existing, QUIET_QT_RULES) if rule)


def setup_logging(folder: Path) -> Path:
    """Write the application log to ``folder`` and return the file path."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / LOG_FILE_NAME
    handler = RotatingFileHandler(path, maxBytes=MAX_LOG_BYTES, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    log.setLevel(logging.DEBUG if os.environ.get("MANIM_STUDIO_DEBUG") else logging.INFO)
    log.handlers = [handler]
    log.propagate = False
    log.info("Manim Studio started (Python %s, %s)", sys.version.split()[0], sys.platform)
    return path


def install_qt_message_handler() -> None:
    """Route Qt warnings into the log file instead of the terminal."""
    from PySide6.QtCore import QtMsgType, qInstallMessageHandler

    levels = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }

    def handler(kind: QtMsgType, context: object, message: str) -> None:
        category = getattr(context, "category", "") or "qt"
        log.log(levels.get(kind, logging.WARNING), "[%s] %s", category, message)

    qInstallMessageHandler(handler)


def install_exception_hook(show: Callable[[str], None]) -> None:
    """Log uncaught exceptions and report them to the user via ``show``."""

    def hook(kind: type[BaseException], value: BaseException, tb: TracebackType | None) -> None:
        text = "".join(traceback.format_exception(kind, value, tb))
        log.error("Uncaught exception:\n%s", text)
        sys.__stderr__.write(text)
        try:
            show(text)
        except Exception:  # noqa: BLE001 - reporting must never raise
            log.exception("Could not show the error dialog")

    sys.excepthook = hook
