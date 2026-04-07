from __future__ import annotations

import gettext
import logging
from contextvars import ContextVar
from pathlib import Path

_current_locale: ContextVar[str] = ContextVar("current_locale", default="en")
_translators: dict[str, gettext.NullTranslations] = {}
_logger = logging.getLogger(__name__)


def set_locale(locale: str) -> None:
    """Set current request locale (fallback to 'en')."""
    _current_locale.set(locale or "en")


def get_locale() -> str:
    """Get current request locale (default 'en')."""
    return _current_locale.get()


def _get_translator(locale: str) -> gettext.NullTranslations:
    tr = _translators.get(locale)
    if tr is not None:
        return tr
    localedir = Path(__file__).resolve().parent.parent / "locales"
    try:
        tr = gettext.translation(
            domain="messages",
            localedir=str(localedir),
            languages=[locale],
            fallback=True,
        )
    except Exception:
        tr = gettext.NullTranslations()
    _translators[locale] = tr
    return tr


def t(msgid: str, **params) -> str:
    """Translate msgid using current locale and format with params.

    If translation file is missing or key not found, returns msgid itself.
    """
    text = _get_translator(get_locale()).gettext(msgid)
    if not params:
        return text
    try:
        return text.format(**params)
    except Exception as exc:
        # Log and fallback to untranslated text to avoid breaking UX
        try:
            _logger.warning(
                "i18n_format_failed", msgid=msgid, params=list(params.keys()), error=str(exc)
            )
        except Exception:
            pass
        return text
