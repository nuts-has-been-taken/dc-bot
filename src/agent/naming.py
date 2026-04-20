"""Helpers for turning Discord display names into filesystem-safe identifiers."""

import re
import unicodedata

# Allow CJK, ASCII letters/digits, dash, underscore, space → converted to `_`
_INVALID = re.compile(r"[^\w\-]", re.UNICODE)


def sanitize_user_name(raw: str) -> str:
    """Return a filesystem-safe version of a Discord display name.

    - Strips leading/trailing whitespace
    - NFC-normalizes unicode
    - Replaces any char that isn't a word char or dash with underscore
    - Collapses repeated underscores
    - Rejects empty / '.' / '..' with a fallback to 'unnamed'
    - Truncates to 64 chars to stay comfortably under filesystem limits
    """
    s = unicodedata.normalize("NFC", (raw or "").strip())
    s = _INVALID.sub("_", s)
    s = re.sub(r"_{2,}", "_", s).strip("._")
    if not s or s in (".", ".."):
        return "unnamed"
    return s[:64]
