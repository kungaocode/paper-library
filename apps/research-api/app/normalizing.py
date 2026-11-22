from __future__ import annotations

from typing import Any


def clean_text(value: Any, *, max_chars: int = 0) -> str:
    """Coerce a model field to a single-line-ish string, optionally truncated."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        text = " ".join(clean_text(item) for item in value)
    elif isinstance(value, dict):
        text = " ".join(clean_text(item) for item in value.values())
    else:
        text = str(value)
    text = text.replace("\x00", "").strip()
    if max_chars and len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "…"
    return text


def string_list(value: Any, *, limit: int = 0, max_chars: int = 0) -> list[str]:
    """Normalize the many shapes a model uses for a list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        items: list[Any] = [part for part in value.split("\n")] if "\n" in value else [value]
    elif isinstance(value, (list, tuple)):
        items = list(value)
    else:
        items = [value]

    out: list[str] = []
    for item in items:
        text = clean_text(item, max_chars=max_chars)
        if text and text not in out:
            out.append(text)
        if limit and len(out) >= limit:
            break
    return out


def clamp_float(value: Any, default: float = 0.0, *, low: float = 0.0, high: float = 1.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed != parsed:  # NaN
        return default
    return max(low, min(high, parsed))


def parse_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def pick(raw: dict[str, Any], *names: str) -> Any:
    """First present key among aliases, so model schema drift does not lose data."""
    for name in names:
        if name in raw and raw[name] not in (None, ""):
            return raw[name]
    return None
