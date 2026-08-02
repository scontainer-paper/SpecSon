#!/usr/bin/env python3
"""Summarize every hard-coded SpecSon dataset in a readable ASCII table."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

from specson_experiments.catalog import SCHEMA_VARIANTS, Catalog
from specson_experiments.results import EXPERIMENT_PARTS, read_result, result_path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = REPO_ROOT / "scripts/specson_workloads.json"
DEFAULT_RESULTS = REPO_ROOT / "experiments/specson/results"


def measurement_summary(measurement: dict[str, Any]) -> dict[str, float]:
    return {
        "specson_median_ms": float(measurement["specson_median_ms"]),
        "jsonb_median_ms": float(measurement["jsonb_median_ms"]),
        "speedup": float(measurement["jsonb_median_ms"])
        / float(measurement["specson_median_ms"]),
    }


def summarize_encode(payload: dict[str, Any]) -> dict[str, Any]:
    variants: dict[str, Any] = {}
    for variant, record in payload.get("variants", {}).items():
        systems = {item["system"]: item for item in record["storage"]}
        summary = measurement_summary(record["measurement"])
        summary["table_capacity_specson_over_jsonb"] = (
            float(systems["specson"]["pg_table_size_bytes"])
            / float(systems["jsonb"]["pg_table_size_bytes"])
        )
        summary["datum_capacity_specson_over_jsonb"] = (
            float(systems["specson"]["datum_bytes"])
            / float(systems["jsonb"]["datum_bytes"])
        )
        variants[variant] = summary
    return {"status": "COMPLETED", "variants": variants}


def summarize_query(payload: dict[str, Any], expected_per_variant: int) -> dict[str, Any]:
    variants: dict[str, Any] = {}
    for variant in SCHEMA_VARIANTS:
        records = [item for item in payload.get("queries", []) if item["variant"] == variant]
        if not records:
            continue
        speedups = [float(item["measurement"]["speedup"]) for item in records]
        variants[variant] = {
            "completed": len(records),
            "expected": expected_per_variant,
            "median_speedup": statistics.median(speedups),
            "min_speedup": min(speedups),
            "max_speedup": max(speedups),
        }
    return {"status": "COMPLETED", "variants": variants}


def summarize_restore(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "COMPLETED",
        "variants": {
            variant: measurement_summary(record["measurement"])
            for variant, record in payload.get("variants", {}).items()
        },
    }


def summarize(catalog: Catalog, results_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dataset in catalog.ordered_datasets:
        row: dict[str, Any] = {
            "id": dataset.number,
            "name": dataset.name,
            "key": dataset.key,
            "variants": dataset.schema_variants,
        }
        expected_queries = sum(len(query.operations) for query in dataset.queries)
        for part in EXPERIMENT_PARTS:
            path = result_path(results_dir, dataset, part)
            payload = read_result(path, dataset, part)
            if payload is None:
                row[part] = {"status": "NOT RUN"}
            elif part == "encode":
                row[part] = summarize_encode(payload)
            elif part == "query":
                row[part] = summarize_query(payload, expected_queries)
            else:
                row[part] = summarize_restore(payload)
        rows.append(row)
    return rows


def variant_result(part: dict[str, Any], variant: str) -> dict[str, Any] | None:
    if part["status"] == "NOT RUN":
        return None
    return part.get("variants", {}).get(variant)


def encode_text(part: dict[str, Any], variant: str) -> str:
    value = variant_result(part, variant)
    if value is None:
        return "NOT RUN"
    return f"{value['speedup']:.2f}x"


def table_capacity_text(part: dict[str, Any], variant: str) -> str:
    value = variant_result(part, variant)
    if value is None:
        return "NOT RUN"
    return f"{value['table_capacity_specson_over_jsonb'] * 100.0:.2f}%"


def datum_capacity_text(part: dict[str, Any], variant: str) -> str:
    value = variant_result(part, variant)
    if value is None:
        return "NOT RUN"
    return f"{value['datum_capacity_specson_over_jsonb'] * 100.0:.2f}%"


def query_text(part: dict[str, Any], variant: str) -> str:
    value = variant_result(part, variant)
    if value is None:
        return "NOT RUN"
    return (
        f"{value['completed']}/{value['expected']} | median {value['median_speedup']:.2f}x "
        f"| [{value['min_speedup']:.2f}, {value['max_speedup']:.2f}]"
    )


def restore_text(part: dict[str, Any], variant: str) -> str:
    value = variant_result(part, variant)
    if value is None:
        return "NOT RUN"
    return f"perf {value['speedup']:.2f}x"


def ascii_table(headers: tuple[str, ...], records: list[tuple[str, ...]]) -> str:
    widths = [
        max(len(headers[index]), *(len(record[index]) for record in records))
        for index in range(len(headers))
    ]
    border = "+-" + "-+-".join("-" * width for width in widths) + "-+"

    def row(values: tuple[str, ...]) -> str:
        return "| " + " | ".join(
            value.ljust(widths[index]) for index, value in enumerate(values)
        ) + " |"

    lines = [border, row(headers), border]
    for index, record in enumerate(records):
        lines.append(row(record))
        if index + 1 == len(records) or records[index + 1][0] != record[0]:
            lines.append(border)
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    parser.add_argument("--dataset-root")
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS))
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        catalog = Catalog.load(
            Path(args.catalog).expanduser().resolve(),
            Path(args.dataset_root).expanduser().resolve() if args.dataset_root else None,
        )
        errors = catalog.validate_inputs(require_generated_data=False)
        if errors:
            raise ValueError("catalog validation failed:\n  " + "\n  ".join(errors))
        rows = summarize(catalog, Path(args.results_dir).expanduser().resolve())
        if args.json:
            print(json.dumps(rows, indent=2, ensure_ascii=False, sort_keys=True))
            return 0
        table_rows: list[tuple[str, ...]] = []
        for row in rows:
            for variant in row["variants"]:
                table_rows.append((
                    str(row["id"]),
                    row["name"],
                    variant,
                    encode_text(row["encode"], variant),
                    table_capacity_text(row["encode"], variant),
                    datum_capacity_text(row["encode"], variant),
                    query_text(row["query"], variant),
                    restore_text(row["restore"], variant),
                ))
        print(ascii_table(
            ("ID", "Dataset", "Variant", "Encode (JSONB/SpecSon)",
             "Table Size (SpecSon/JSONB %)",
             "Column Size (SpecSon/JSONB %)", "Query (JSONB/SpecSon)",
             "Restore (JSONB/SpecSon)"),
            table_rows,
        ))
        return 0
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
