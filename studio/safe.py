"""Small helpers for what is safe to show a user."""
import re

_PATH = re.compile(r"(?:[A-Za-z]:)?[\\/][^\s'\"]*[\\/][^\s'\"]+")
_CTRL = re.compile(r"[\x00-\x1f\x7f]+")


def clean(v, limit: int = 200) -> str:
    """Clean untrusted text into a single safe line within `limit` characters."""
    s = _CTRL.sub(" ", str(v or "")).replace("<", "\u2039")
    return re.sub(r"\s+", " ", s).strip()[:limit]


def friendly(e, limit=600) -> str:
    """An error message for the user: trimmed, with any server file paths removed. A missing ffmpeg, which Windows
    reports only as "the system cannot find the file specified", is said in plain words with what to do."""
    from . import tools
    return tools.explain(e) or _PATH.sub("[file]", str(e)[-limit:])

