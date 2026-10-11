"""Application start-up and live rebuilding of the main window."""

from __future__ import annotations

import sys

from PySide6.QtCore import QLocale, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from manim_studio import APP_NAME, ORGANIZATION, __version__
from manim_studio.i18n import set_language, tr
from manim_studio.logging_setup import (
    install_exception_hook,
    install_qt_message_handler,
    log,
    quiet_qt_logging,
    setup_logging,
)


def apply_locale(language: str) -> None:
    """Set the number format (decimal comma in German)."""
    QLocale.setDefault(QLocale(QLocale.Language.German if language == "de" else QLocale.Language.English))


class StudioApplication:
    """Owns the long-lived :class:`AppContext` and the (replaceable) main window."""

    def __init__(self, app: QApplication, initial_file: str | None) -> None:
        from manim_studio.ui.context import AppContext, cache_dir
        from manim_studio.ui.settings import AppSettings

        self.app = app
        self.settings = AppSettings()
        self._image_dir = cache_dir() / "style"
        self._apply_preferences()
        self.context = AppContext(self.settings)
        self.window = None
        self._create_window()
        if initial_file:
            QTimer.singleShot(0, lambda: self.window.open_file(initial_file, ask=False))
        elif self.context.autosaver.backups():
            QTimer.singleShot(300, self._offer_recovery)
        elif self.settings.show_welcome:
            QTimer.singleShot(450, lambda: self.window.show_welcome())
        QTimer.singleShot(300, self.context.check_environment)

    def _offer_recovery(self) -> None:
        """Offer to restore unsaved work from an earlier session (e.g. after a crash)."""
        from datetime import datetime

        backups = self.context.autosaver.backups()
        if not backups:
            return
        backup = backups[0]
        when = datetime.fromtimestamp(backup.saved_at).strftime("%d.%m.%Y %H:%M")
        box = QMessageBox(self.window)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(tr("recovery.title"))
        box.setText(tr("recovery.text", name=backup.title or tr("window.untitled"), time=when))
        restore = box.addButton(tr("recovery.restore"), QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton(tr("recovery.discard"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(tr("recovery.later"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is restore:
            if self.context.autosaver.restore(backup):
                self.context.editor.reset()
                self.window.show_status(tr("recovery.restored"))
        elif box.clickedButton() is discard:
            self.context.autosaver.forget(backup)

    def _apply_preferences(self) -> None:
        from manim_studio.ui.theme import apply_theme

        set_language(self.settings.language)
        apply_locale(self.settings.language)
        apply_theme(self.app, self.settings.theme, self.settings.ui_scale, self._image_dir)

    def _create_window(self) -> None:
        from manim_studio.ui.main_window import MainWindow

        self.window = MainWindow(self.context, self.rebuild)
        self.context.set_window(self.window)
        self.window.show()

    def rebuild(self) -> None:
        """Re-create the window after language, theme or scale changed."""
        old = self.window
        if self.context.render.is_busy():
            QMessageBox.information(old, tr("settings.title"), tr("settings.rebuild_busy"))
            return
        old.close_for_rebuild()
        from manim_studio.ui.animation_preview import PreviewHover

        PreviewHover.reset()
        self._apply_preferences()
        self._create_window()
        old.deleteLater()
        log.info("Window rebuilt (language=%s, theme=%s, scale=%s)", self.settings.language, self.settings.theme, self.settings.ui_scale)


def _show_crash(text: str) -> None:
    box = QMessageBox(QApplication.activeWindow())
    box.setIcon(QMessageBox.Icon.Critical)
    box.setWindowTitle(tr("crash.title"))
    box.setText(tr("crash.text"))
    box.setDetailedText(text)
    box.exec()


def main(argv: list[str] | None = None) -> int:
    """Start Manim Studio; an optional first argument is a project file to open."""
    arguments = list(sys.argv if argv is None else argv)
    quiet_qt_logging()
    QApplication.setOrganizationName(ORGANIZATION)
    QApplication.setApplicationName(APP_NAME)
    QApplication.setApplicationVersion(__version__)
    app = QApplication.instance() or QApplication(arguments)

    from manim_studio.ui.context import data_dir
    from manim_studio.ui.icons import app_icon

    setup_logging(data_dir() / "logs")
    install_qt_message_handler()
    install_exception_hook(_show_crash)
    app.setWindowIcon(app_icon())
    initial_file = arguments[1] if len(arguments) > 1 else None
    studio = StudioApplication(app, initial_file)
    code = app.exec()
    log.info("Manim Studio closed (exit code %s)", code)
    del studio
    return code


if __name__ == "__main__":
    raise SystemExit(main())
