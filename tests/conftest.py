"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session")
def qapp():
    """One offscreen ``QApplication`` for all tests that need Qt."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def window(tmp_path, qapp):
    """The main window with fresh settings and data folder (offscreen)."""
    from PySide6.QtCore import QEvent, QSettings, QThreadPool

    from manim_studio.i18n import set_language
    from manim_studio.ui.context import AppContext
    from manim_studio.ui.main_window import MainWindow
    from manim_studio.ui.settings import AppSettings
    from manim_studio.ui.theme import apply_theme

    app = qapp
    set_language("de")
    settings = AppSettings(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))
    settings.hidden_environment_warning = "manim,ffmpeg,latex"
    apply_theme(app, "dark", 1.0, tmp_path / "style")
    context = AppContext(settings, data_folder=tmp_path / "data")
    main = MainWindow(context, lambda: None)
    context.set_window(main)
    main.show()
    app.processEvents()
    yield main
    main.document.undo_stack.setClean()
    main.close()
    QThreadPool.globalInstance().waitForDone(60_000)
    app.processEvents()
    # Delete the window for real; closed windows would otherwise pile up and every new
    # style sheet would be applied to all of them (each test got slower than the last).
    main.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    app.processEvents()
