"""Application start-up."""

from __future__ import annotations

import sys

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication

from manim_studio import APP_NAME, ORGANIZATION, __version__
from manim_studio.i18n import set_language


def _apply_locale(language: str) -> None:
    locale = QLocale(QLocale.Language.German if language == "de" else QLocale.Language.English)
    QLocale.setDefault(locale)


def main(argv: list[str] | None = None) -> int:
    """Start Manim Studio; an optional first argument is a project file to open."""
    arguments = list(sys.argv if argv is None else argv)
    QApplication.setOrganizationName(ORGANIZATION)
    QApplication.setApplicationName(APP_NAME)
    QApplication.setApplicationVersion(__version__)
    app = QApplication.instance() or QApplication(arguments)

    from manim_studio.ui.icons import app_icon
    from manim_studio.ui.main_window import MainWindow
    from manim_studio.ui.settings import AppSettings

    settings = AppSettings()
    set_language(settings.language)
    _apply_locale(settings.language)
    app.setWindowIcon(app_icon())
    initial_file = arguments[1] if len(arguments) > 1 else None
    window = MainWindow(settings, initial_file)
    app.aboutToQuit.connect(window.controller.release_clipboard)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
