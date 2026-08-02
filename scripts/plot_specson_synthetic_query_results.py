#!/usr/bin/env python3
"""Generate the synthetic-dataset query speedup figure."""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from plot_specson_query_results import (
    audit_figure,
    configure_style,
    export_figure,
    mapping,
    positive_float,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "experiments/specson/results"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "vldb/figures"
DATASETS = (
    (201, "Synthetic-Width-1", "synthetic-width-1", "Width-1", 10_000),
    (304, "Synthetic-Rank-4", "synthetic-rank-4", "Rank-4", 10_000),
    (
        501,
        "Synthetic-Array-Shape-1x2000",
        "synthetic-array-shape-1x2000",
        "1×2000",
        10_000,
    ),
    (
        504,
        "Synthetic-Array-Shape-2000x1",
        "synthetic-array-shape-2000x1",
        "2000×1",
        10_000,
    ),
)
COLORS = ("#6F9E63", "#4E79A7", "#D2B55B", "#B07AA1")


@dataclass(frozen=True)
class QueryResult:
    operation: str
    specson_ms: float
    jsonb_ms: float

    @property
    def speedup(self) -> float:
        return self.jsonb_ms / self.specson_ms


@dataclass(frozen=True)
class DatasetResult:
    label: str
    color: str
    queries: tuple[QueryResult, ...]


def load_dataset(
    dataset: tuple[int, str, str, str, int], color: str
) -> DatasetResult:
    number, name, key, label, expected_rows = dataset
    path = RESULTS_DIR / f"{number:03d}-{name}-query.json"
    if not path.is_file():
        raise ValueError(f"missing required result file: {path}")
    payload = mapping(json.loads(path.read_text(encoding="utf-8")), str(path))
    if payload.get("format") != "specson_experiment_part_result_v1":
        raise ValueError(f"{path}: unsupported result format")
    if payload.get("part") != "query":
        raise ValueError(f"{path}: expected query result")
    identity = mapping(payload.get("dataset"), f"{path}.dataset")
    expected = {
        "id": number,
        "name": name,
        "key": key,
        "expected_rows": expected_rows,
    }
    for field, value in expected.items():
        if identity.get(field) != value:
            raise ValueError(f"{path}: dataset {field} mismatch")
    raw_queries = payload.get("queries")
    if not isinstance(raw_queries, list) or not raw_queries:
        raise ValueError(f"{path}.queries: expected a non-empty array")
    queries: list[QueryResult] = []
    for index, raw_query in enumerate(raw_queries):
        location = f"{path}.queries[{index}]"
        record = mapping(raw_query, location)
        operation = str(record.get("operation", ""))
        if operation not in {"exists", "count"}:
            raise ValueError(f"{location}: invalid operation")
        if record.get("variant") != "numeric":
            raise ValueError(f"{location}: expected the numeric variant")
        measurement = mapping(record.get("measurement"), f"{location}.measurement")
        specson = positive_float(
            measurement.get("specson_median_ms"), f"{location}.specson_median_ms"
        )
        jsonb = positive_float(
            measurement.get("jsonb_median_ms"), f"{location}.jsonb_median_ms"
        )
        declared = positive_float(measurement.get("speedup"), f"{location}.speedup")
        if not math.isclose(declared, jsonb / specson, rel_tol=1e-9, abs_tol=1e-12):
            raise ValueError(f"{location}: speedup does not match recorded medians")
        queries.append(QueryResult(operation, specson, jsonb))
    return DatasetResult(label, color, tuple(queries))


def create_figure(datasets: list[DatasetResult]):
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(3.33, 2.05), layout="constrained")
    positions: list[float] = []
    labels: list[str] = []
    values: list[float] = []
    colors: list[str] = []
    groups: list[tuple[float, float, str]] = []
    boundaries: list[float] = []
    cursor = 0.0
    for dataset_index, dataset in enumerate(datasets):
        start = cursor
        for query in dataset.queries:
            positions.append(cursor)
            labels.append(query.operation.title())
            values.append(query.speedup)
            colors.append(dataset.color)
            cursor += 1.0
        groups.append((start, cursor - 1.0, dataset.label))
        if dataset_index + 1 < len(datasets):
            boundaries.append(cursor + 0.18)
            cursor += 1.35

    bars = axis.bar(
        positions,
        values,
        width=0.68,
        color=colors,
        edgecolor="#FFFFFF",
        linewidth=0.5,
        zorder=3,
    )
    for bar, value in zip(bars, values):
        axis.annotate(
            f"{value:.2f}×",
            xy=(bar.get_x() + bar.get_width() / 2.0, value),
            xytext=(0, 2),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=5.2,
        )
    axis.axhline(
        1.0,
        color="#4D4D4D",
        linewidth=0.9,
        linestyle=(0, (6, 4)),
        zorder=2,
    )
    for boundary in boundaries:
        axis.axvline(boundary, color="#D4D4D4", linewidth=0.6, zorder=1)
    for start, end, label in groups:
        axis.text(
            (start + end) / 2.0,
            -0.20,
            label,
            color="#252525",
            fontsize=5.5,
            fontweight="bold",
            ha="center",
            va="top",
            transform=axis.get_xaxis_transform(),
            clip_on=False,
        )
    axis.set_yscale("log")
    axis.set_xlim(min(positions) - 0.75, max(positions) + 0.75)
    axis.set_ylim(0.9, max(values) * 1.42)
    axis.set_ylabel("Speedup (log scale)")
    axis.set_xticks(positions)
    axis.set_xticklabels(labels)
    axis.tick_params(axis="x", pad=2)
    axis.yaxis.grid(True, which="both", color="#D9D9D9", linewidth=0.55)
    axis.xaxis.grid(False)
    axis.set_axisbelow(True)
    return figure


def main() -> int:
    figure = None
    try:
        if len(sys.argv) > 2:
            raise ValueError(
                "usage: plot_specson_synthetic_query_results.py [OUTPUT_DIRECTORY]"
            )
        output_dir = (
            Path(sys.argv[1]).expanduser().resolve()
            if len(sys.argv) == 2
            else DEFAULT_OUTPUT_DIR
        )
        configure_style()
        datasets = [
            load_dataset(dataset, color)
            for dataset, color in zip(DATASETS, COLORS)
        ]
        figure = create_figure(datasets)
        audit = audit_figure(figure, "synthetic-query")
        width, height = figure.get_size_inches()
        audit["width_inches"] = float(width)
        audit["height_inches"] = float(height)
        output_dir.mkdir(parents=True, exist_ok=True)
        audit_path = output_dir / "synthetic-query-audit.json"
        audit_path.write_text(
            json.dumps(
                {
                    "format": "specson_synthetic_query_figure_audit_v1",
                    "audits": [audit],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        if audit["status"] != "PASS":
            raise RuntimeError(f"query figure audit failed: {audit}")
        outputs = export_figure(figure, output_dir, "synthetic-query")
        for path in (*outputs, audit_path):
            print(path)
        return 0
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    finally:
        if figure is not None:
            import matplotlib.pyplot as plt

            plt.close(figure)


if __name__ == "__main__":
    raise SystemExit(main())
