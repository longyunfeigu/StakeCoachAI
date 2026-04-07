from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from core.i18n import set_locale


def _pick_from_accept_language(al: str) -> str:
    """Parse Accept-Language with q weights, return best lang tag.

    Examples:
      'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7' -> 'zh-CN'
    """
    try:
        items = []
        for part in al.split(","):
            p = part.strip()
            if not p:
                continue
            seg = p.split(";", 1)
            lang = seg[0].strip()
            q = 1.0
            if len(seg) == 2 and seg[1].strip().startswith("q="):
                try:
                    q = float(seg[1].strip()[2:])
                except Exception:
                    q = 1.0
            items.append((lang, q))
        if not items:
            return "en"
        # sort by q desc, keep order for ties
        items.sort(key=lambda x: x[1], reverse=True)
        return items[0][0]
    except Exception:
        return "en"


def _normalize(lang: str) -> str:
    """Map common browser tags to our locales."""
    tag = (lang or "en").replace("_", "-").lower()
    # map to zh_Hans for Simplified Chinese
    if tag in {"zh-cn", "zh-hans", "zh"}:
        return "zh_Hans"
    if tag in {"en", "en-us", "en-gb"}:
        return "en"
    return lang


class LocaleMiddleware(BaseHTTPMiddleware):
    """Parse locale from query/header and set into context.

    Priority: ?lang=xx > X-Lang > Accept-Language > default 'en'.
    """

    async def dispatch(self, request: Request, call_next):
        lang = request.query_params.get("lang") or request.headers.get("X-Lang")
        if not lang:
            al = request.headers.get("Accept-Language", "")
            lang = _pick_from_accept_language(al) if al else "en"
        set_locale(_normalize(lang))
        try:
            request.state.locale = lang
        except Exception:
            pass
        return await call_next(request)
