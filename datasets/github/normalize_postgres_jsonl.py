#!/usr/bin/env python3
"""Normalize GitHub JSONL for PostgreSQL JSONB without reserializing it.

PostgreSQL JSONB cannot represent the JSON string escape ``\u0000``.  Replacing
that escape with an empty string is unsafe because an adjacent backslash can
then change how the following quote is parsed.  This script replaces it with
``\uFFFD`` instead, validates every resulting JSON line, and writes normalized
copies while preserving every other input byte.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


BAD_ESCAPE = b"\\u0000"
REPLACEMENT_ESCAPE = b"\\uFFFD"


def normalize_file(source: Path, destination: Path) -> tuple[int, int]:
    rows = 0
    repaired_rows = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as input_file, destination.open("wb") as output_file:
        for line_number, line in enumerate(input_file, 1):
            rows += 1
            normalized = line.replace(BAD_ESCAPE, REPLACEMENT_ESCAPE)
            repaired_rows += normalized != line
            try:
                json.loads(normalized)
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise SystemExit(
                    f"{source}:{line_number}: invalid JSON after normalization: "
                    f"{error}"
                ) from error
            output_file.write(normalized)
    return rows, repaired_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        help="JSONL files; defaults to every 2026-*.jsonl beside this script",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "postgres-normalized",
        help="destination directory (default: ./postgres-normalized)",
    )
    args = parser.parse_args()

    dataset_dir = Path(__file__).resolve().parent
    inputs = args.inputs or sorted(dataset_dir.glob("2026-*.jsonl"))
    if not inputs:
        raise SystemExit("no input JSONL files found")

    total_rows = 0
    total_repaired_rows = 0
    for source in inputs:
        destination = args.output_dir / source.name
        rows, repaired_rows = normalize_file(source, destination)
        total_rows += rows
        total_repaired_rows += repaired_rows
        print(
            f"{source.name}: rows={rows} repaired_rows={repaired_rows} "
            f"output={destination}"
        )
    print(
        f"total_rows={total_rows} total_repaired_rows={total_repaired_rows}"
    )


if __name__ == "__main__":
    main()
