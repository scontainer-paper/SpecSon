from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .catalog import Dataset


EXPERIMENT_PARTS = ("encode", "query", "restore")
RESULT_FORMAT = "specson_experiment_part_result_v1"


def result_path(root: Path, dataset: Dataset, part: str) -> Path:
    if part not in EXPERIMENT_PARTS:
        raise ValueError(f"unsupported experiment part: {part}")
    return root / dataset.result_filename(part)


def remove_result(root: Path, dataset: Dataset, part: str) -> Path:
    path = result_path(root, dataset, part)
    path.unlink(missing_ok=True)
    return path


def write_result(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(payload, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_result(path: Path, dataset: Dataset, part: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("format") != RESULT_FORMAT:
        raise ValueError(f"{path}: unsupported result format")
    if payload.get("part") != part:
        raise ValueError(f"{path}: expected part {part!r}")
    identity = payload.get("dataset", {})
    if identity.get("id") != dataset.number or identity.get("name") != dataset.name:
        raise ValueError(f"{path}: dataset identity does not match the catalog")
    return payload
