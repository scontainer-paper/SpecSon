#!/usr/bin/env python3
"""Generate encode, restore, and storage figures for synthetic datasets."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from plot_specson_publication_results import (
    audit_figure,
    configure_style,
    draw_grouped_bars,
    export_figure,
    legend_handles,
    mapping,
    measurement,
    storage,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "experiments/specson/results"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "vldb/figures"
FIGURE_WIDTH_INCHES = 3.33
FIGURE_HEIGHT_INCHES = 1.75
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


@dataclass(frozen=True)
class SyntheticResult:
    label: str
    encode_specson_ms: float
    encode_jsonb_ms: float
    restore_specson_ms: float
    restore_jsonb_ms: float
    specson_table_bytes: int
    jsonb_table_bytes: int


def load_part(path: Path, part: str, dataset: tuple[int, str, str, str, int]) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"missing required result file: {path}")
    payload = mapping(json.loads(path.read_text(encoding="utf-8")), str(path))
    if payload.get("format") != "specson_experiment_part_result_v1":
        raise ValueError(f"{path}: unsupported result format")
    if payload.get("part") != part:
        raise ValueError(f"{path}: expected part {part!r}")
    number, name, key, _label, expected_rows = dataset
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
    variants = mapping(payload.get("variants"), f"{path}.variants")
    if set(variants) != {"numeric"}:
        raise ValueError(f"{path}: expected exactly the numeric variant")
    return mapping(variants["numeric"], f"{path}.variants.numeric")


def load_results() -> list[SyntheticResult]:
    results: list[SyntheticResult] = []
    for dataset in DATASETS:
        number, name, _key, label, expected_rows = dataset
        stem = f"{number:03d}-{name}"
        encode_path = RESULTS_DIR / f"{stem}-encode.json"
        restore_path = RESULTS_DIR / f"{stem}-restore.json"
        encode = load_part(encode_path, "encode", dataset)
        restore = load_part(restore_path, "restore", dataset)
        encode_specson, encode_jsonb = measurement(encode, str(encode_path))
        restore_specson, restore_jsonb = measurement(restore, str(restore_path))
        table_specson, table_jsonb, _column_specson, _column_jsonb = storage(
            encode, expected_rows, str(encode_path)
        )
        results.append(
            SyntheticResult(
                label,
                encode_specson,
                encode_jsonb,
                restore_specson,
                restore_jsonb,
                table_specson,
                table_jsonb,
            )
        )
    return results


def annotate_bars(axis, values: list[float], formatter) -> None:
    for bar, value in zip(axis.patches, values):
        axis.annotate(
            formatter(value),
            xy=(bar.get_x() + bar.get_width() / 2.0, value),
            xytext=(0, 2),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=4.8,
        )


def create_figure(records: list[SyntheticResult], metric: str):
    import matplotlib.pyplot as plt

    if metric in {"encode", "restore"}:
        specson = [getattr(record, f"{metric}_specson_ms") / 1000.0 for record in records]
        jsonb = [getattr(record, f"{metric}_jsonb_ms") / 1000.0 for record in records]
        ylabel = "Time (s, log scale)"
        title = "Encode" if metric == "encode" else "Full restore"
        formatter = (
            lambda value: f"{value:.4f}"
            if value < 0.01
            else (f"{value:.3f}" if value < 0.1 else f"{value:.2f}")
        )
    elif metric == "storage":
        mib = float(1024**2)
        specson = [record.specson_table_bytes / mib for record in records]
        jsonb = [record.jsonb_table_bytes / mib for record in records]
        ylabel = "Table size (MiB, log scale)"
        title = "Storage"
        formatter = lambda value: f"{value:.2f}" if value < 10.0 else f"{value:.1f}"
    else:
        raise ValueError(f"unsupported metric: {metric}")

    figure, axis = plt.subplots(
        figsize=(FIGURE_WIDTH_INCHES, FIGURE_HEIGHT_INCHES), layout="constrained"
    )
    positions = [float(index) for index in range(len(records))]
    draw_grouped_bars(axis, positions, specson, jsonb)
    annotate_bars(axis, [*specson, *jsonb], formatter)
    axis.set_yscale("log")
    axis.set_ylim(min(specson + jsonb) * 0.72, max(specson + jsonb) * 1.65)
    axis.set_ylabel(ylabel)
    axis.set_xticks(positions)
    axis.set_xticklabels([record.label for record in records])
    for label in axis.get_xticklabels():
        label.set_fontweight("bold")
    axis.yaxis.grid(True, which="both", color="#D9D9D9", linewidth=0.45)
    axis.xaxis.grid(False)
    axis.set_axisbelow(True)
    axis.set_title(title, loc="left", fontweight="normal")
    axis.legend(
        handles=legend_handles(),
        loc="upper center",
        bbox_to_anchor=(0.5, 1.14),
        ncol=2,
        frameon=False,
        handletextpad=0.45,
        columnspacing=1.4,
        prop={"size": 7, "weight": "normal"},
    )
    return figure


def main() -> int:
    figures = []
    try:
        if len(sys.argv) > 2:
            raise ValueError(
                "usage: plot_specson_synthetic_publication_results.py [OUTPUT_DIRECTORY]"
            )
        output_dir = (
            Path(sys.argv[1]).expanduser().resolve()
            if len(sys.argv) == 2
            else DEFAULT_OUTPUT_DIR
        )
        configure_style()
        records = load_results()
        figures = [
            ("synthetic-encode", create_figure(records, "encode")),
            ("synthetic-restore", create_figure(records, "restore")),
            ("synthetic-storage", create_figure(records, "storage")),
        ]
        audits = [audit_figure(figure, name) for name, figure in figures]
        output_dir.mkdir(parents=True, exist_ok=True)
        report = output_dir / "synthetic-publication-audit.json"
        report.write_text(
            json.dumps(
                {
                    "format": "specson_synthetic_publication_figure_audit_v1",
                    "audits": audits,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        failures = [audit for audit in audits if audit["status"] != "PASS"]
        if failures:
            raise RuntimeError(f"publication figure audit failed: {failures}")
        outputs: list[Path] = []
        for name, figure in figures:
            outputs.extend(export_figure(figure, output_dir / name))
        for path in (*outputs, report):
            print(path)
        return 0
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    finally:
        if figures:
            import matplotlib.pyplot as plt

            for _, figure in figures:
                plt.close(figure)


if __name__ == "__main__":
    raise SystemExit(main())
