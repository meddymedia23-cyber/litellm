from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .models import Borough

BOROUGH_ALIASES = {
    "bronx": Borough.BRONX,
    "the bronx": Borough.BRONX,
    "bx": Borough.BRONX,
    "queens": Borough.QUEENS,
    "qn": Borough.QUEENS,
    "manhattan": Borough.MANHATTAN,
    "new york": Borough.MANHATTAN,
    "mn": Borough.MANHATTAN,
    "brooklyn": Borough.BROOKLYN,
    "bk": Borough.BROOKLYN,
    "kings": Borough.BROOKLYN,
    "staten island": Borough.STATEN_ISLAND,
    "si": Borough.STATEN_ISLAND,
    "richmond": Borough.STATEN_ISLAND,
}

TRUE_VALUES = {"1", "true", "yes", "y", "available"}
FALSE_VALUES = {"0", "false", "no", "n", "unavailable"}


def normalize_borough(value: Any) -> Borough:
    if isinstance(value, Borough):
        return value
    key = str(value or "").strip().lower()
    try:
        return BOROUGH_ALIASES[key]
    except KeyError as exc:
        raise ValueError(f"unrecognized NYC borough: {value!r}") from exc


def normalize_category(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        raise ValueError("category cannot be empty")
    return text.casefold().title()


def optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def optional_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    cleaned = re.sub(r"[$,%\s,]", "", str(value))
    try:
        return float(Decimal(cleaned))
    except InvalidOperation as exc:
        raise ValueError(f"invalid number: {value!r}") from exc


def optional_int(value: Any) -> int | None:
    parsed = optional_float(value)
    if parsed is None:
        return None
    if not parsed.is_integer():
        raise ValueError(f"expected whole number, received {value!r}")
    return int(parsed)


def optional_bool(value: Any) -> bool | None:
    if value is None or str(value).strip() == "":
        return None
    key = str(value).strip().lower()
    if key in TRUE_VALUES:
        return True
    if key in FALSE_VALUES:
        return False
    raise ValueError(f"invalid boolean: {value!r}")


def parse_datetime(value: Any, *, default: datetime | None = None) -> datetime:
    if value is None or str(value).strip() == "":
        if default is None:
            raise ValueError("datetime value is required")
        return default
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"invalid ISO-8601 datetime: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def stable_id(prefix: str, *parts: Any) -> str:
    canonical = "|".join(str(part or "").strip().casefold() for part in parts)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}:{digest}"


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
