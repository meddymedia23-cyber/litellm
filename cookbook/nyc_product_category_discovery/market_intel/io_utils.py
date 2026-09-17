from __future__ import annotations

import csv
import json
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, TypeAdapter, ValidationError

T = TypeVar("T", bound=BaseModel)


def read_json(path: str | Path) -> object:
    source = Path(path)
    try:
        return json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"file not found: {source}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {source}: {exc}") from exc


def read_models(path: str | Path, model_type: type[T]) -> list[T]:
    source = Path(path)
    suffix = source.suffix.lower()
    try:
        if suffix == ".csv":
            with source.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
        elif suffix == ".jsonl":
            rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
        elif suffix == ".json":
            payload = read_json(source)
            rows = payload if isinstance(payload, list) else [payload]
        else:
            raise ValueError(f"unsupported input format {suffix}; use CSV, JSON, or JSONL")
        return TypeAdapter(list[model_type]).validate_python(rows)
    except FileNotFoundError as exc:
        raise ValueError(f"file not found: {source}") from exc
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid {model_type.__name__} data in {source}: {exc}") from exc


def write_json_atomic(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    serializable = payload
    if isinstance(payload, BaseModel):
        serializable = payload.model_dump(mode="json")
    elif isinstance(payload, list):
        serializable = [item.model_dump(mode="json") if isinstance(item, BaseModel) else item for item in payload]
    rendered = json.dumps(serializable, indent=2, ensure_ascii=False, sort_keys=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, delete=False) as handle:
        handle.write(rendered)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(target)


def write_jsonl_atomic(path: str | Path, items: Iterable[BaseModel | dict]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, delete=False) as handle:
        for item in items:
            payload = item.model_dump(mode="json") if isinstance(item, BaseModel) else item
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(target)
