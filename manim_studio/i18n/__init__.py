"""Central collection of all user-visible texts (German and English).

Use :func:`tr` with a key; the texts live in :mod:`.de` and :mod:`.en`.
Adding a language means adding one more module with the same keys.
"""

from __future__ import annotations

from manim_studio.i18n import de, en

LANGUAGES: dict[str, str] = {"de": "Deutsch", "en": "English"}
DEFAULT_LANGUAGE = "de"

_CATALOGS: dict[str, dict[str, str]] = {"de": de.STRINGS, "en": en.STRINGS}
_current = DEFAULT_LANGUAGE


def set_language(code: str) -> None:
    """Switch the active language (unknown codes fall back to German)."""
    global _current
    _current = code if code in _CATALOGS else DEFAULT_LANGUAGE


def language() -> str:
    """Return the active language code."""
    return _current


def catalog(code: str) -> dict[str, str]:
    """Return the text catalog of a language."""
    return _CATALOGS[code]


def has(key: str) -> bool:
    """Return ``True`` if a text exists for ``key``."""
    return key in _CATALOGS[_current] or key in _CATALOGS[DEFAULT_LANGUAGE]


def tr(key: str, **values: object) -> str:
    """Return the translated text for ``key``, formatted with ``values``."""
    text = _CATALOGS[_current].get(key) or _CATALOGS[DEFAULT_LANGUAGE].get(key) or key
    if values:
        try:
            return text.format(**values)
        except (KeyError, IndexError, ValueError):
            return text
    return text
