#!/usr/bin/env python3
"""Generate three standalone SVG figures: encode, restore, and storage."""

from __future__ import annotations

import json
import math
import sys
from html import escape
from pathlib import Path
from typing import Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "experiments/specson/results"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "experiments/specson/figures/real-world"
VARIANTS = (("ordinary", "Integer"), ("numeric", "Numeric"))
DATASETS = (
    (1, "Yelp-Review", "yelp-review", "Yelp Review", 6_990_280),
    (2, "Yelp-Business", "yelp-business", "Yelp Business", 150_346),
    (3, "GitHub", "github", "GitHub Archive", 3_795_000),
    (4, "OpenAlex", "openalex", "OpenAlex Works", 358_387),
)
COLORS = {"SpecSon": "#3182bd", "JSONB": "#9ecae1"}


def object_value(value: object, location: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{location}: expected an object")
    return value


def positive_number(value: object, location: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{location}: expected a positive finite number")
    return result


def read_part(
    path: Path, part: str, dataset: tuple[int, str, str, str, int]
) -> dict[str, object]:
    if not path.is_file():
        raise ValueError(f"missing required result file: {path}")
    payload = object_value(json.loads(path.read_text(encoding="utf-8")), str(path))
    if payload.get("format") != "specson_experiment_part_result_v1":
        raise ValueError(f"{path}: unsupported result format")
    if payload.get("part") != part:
        raise ValueError(f"{path}: expected part {part!r}")
    number, name, key, label, expected_rows = dataset
    identity = object_value(payload.get("dataset"), f"{path}.dataset")
    expected = {
        "id": number,
        "name": name,
        "key": key,
        "label": label,
        "expected_rows": expected_rows,
    }
    for field, value in expected.items():
        if identity.get(field) != value:
            raise ValueError(f"{path}: dataset {field} mismatch")
    variants = object_value(payload.get("variants"), f"{path}.variants")
    if set(variants) != {name for name, _ in VARIANTS}:
        raise ValueError(f"{path}: expected exactly ordinary and numeric variants")
    return variants


def measured(record: dict[str, object], location: str) -> tuple[float, float]:
    values = object_value(record.get("measurement"), f"{location}.measurement")
    specson = positive_number(values.get("specson_median_ms"), f"{location}.specson")
    jsonb = positive_number(values.get("jsonb_median_ms"), f"{location}.jsonb")
    declared = values.get("speedup")
    if declared is not None and not math.isclose(
        float(declared), jsonb / specson, rel_tol=1e-9, abs_tol=1e-12
    ):
        raise ValueError(f"{location}: speedup does not match the recorded medians")
    return specson, jsonb


def stored(
    record: dict[str, object], expected_rows: int, location: str
) -> tuple[int, int, int, int]:
    values = record.get("storage")
    if not isinstance(values, list) or len(values) != 2:
        raise ValueError(f"{location}.storage: expected two systems")
    systems: dict[str, dict[str, object]] = {}
    for index, value in enumerate(values):
        item = object_value(value, f"{location}.storage[{index}]")
        system = str(item.get("system", ""))
        if system in systems:
            raise ValueError(f"{location}.storage: duplicate system {system!r}")
        systems[system] = item
    if set(systems) != {"specson", "jsonb"}:
        raise ValueError(f"{location}.storage: expected specson and jsonb")
    for system, item in systems.items():
        if int(item.get("rows", -1)) != expected_rows:
            raise ValueError(f"{location}.storage.{system}: row count mismatch")
    return (
        int(positive_number(systems["specson"].get("pg_table_size_bytes"), location)),
        int(positive_number(systems["jsonb"].get("pg_table_size_bytes"), location)),
        int(positive_number(systems["specson"].get("datum_bytes"), location)),
        int(positive_number(systems["jsonb"].get("datum_bytes"), location)),
    )


def load_results() -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for dataset in DATASETS:
        number, name, key, label, expected_rows = dataset
        stem = f"{number:03d}-{name}"
        encode_path = RESULTS_DIR / f"{stem}-encode.json"
        restore_path = RESULTS_DIR / f"{stem}-restore.json"
        encode = read_part(encode_path, "encode", dataset)
        restore = read_part(restore_path, "restore", dataset)
        for variant, _ in VARIANTS:
            encode_record = object_value(encode[variant], f"{encode_path}.{variant}")
            restore_record = object_value(restore[variant], f"{restore_path}.{variant}")
            encode_specson, encode_jsonb = measured(encode_record, str(encode_path))
            restore_specson, restore_jsonb = measured(restore_record, str(restore_path))
            table_specson, table_jsonb, column_specson, column_jsonb = stored(
                encode_record, expected_rows, str(encode_path)
            )
            results.append({
                "dataset": key,
                "label": label,
                "variant": variant,
                "encode_specson": encode_specson / 1000.0,
                "encode_jsonb": encode_jsonb / 1000.0,
                "restore_specson": restore_specson / 1000.0,
                "restore_jsonb": restore_jsonb / 1000.0,
                "table_specson": table_specson / 1024**3,
                "table_jsonb": table_jsonb / 1024**3,
                "column_specson": column_specson / 1024**3,
                "column_jsonb": column_jsonb / 1024**3,
            })
    return results


def nice_axis(maximum: float) -> tuple[float, float]:
    rough = maximum / 5.0
    magnitude = 10.0 ** math.floor(math.log10(rough))
    normalized = rough / magnitude
    nice = next(value for value in (1.0, 2.0, 2.5, 5.0, 10.0) if normalized <= value)
    step = nice * magnitude
    return math.ceil(maximum / step) * step, step


def fill(system: str) -> str:
    return COLORS[system] if system == "SpecSon" else "url(#jsonb-hatch)"


def write_svg(
    groups: list[tuple[str, list[tuple[tuple[str, ...], float, float]]]],
    destination: Path,
    title: str,
    description: str,
    y_label: str,
    format_value: Callable[[float], str],
) -> Path:
    if not groups or any(not comparisons for _, comparisons in groups):
        raise ValueError(f"{title}: no values to plot")
    widest = max(len(comparisons) for _, comparisons in groups)
    bar_width, pair_gap, comparison_gap = 24.0, 5.0, 18.0
    pair_width = bar_width * 2 + pair_gap
    content_width = widest * pair_width + (widest - 1) * comparison_gap
    group_width = max(168.0, content_width + 36.0)
    width, height = max(720, int(112 + group_width * len(groups))), 480
    left, right, top, bottom = 68, 24, 76, 100
    plot_width, plot_height = width - left - right, height - top - bottom
    group_slot = plot_width / len(groups)
    max_lines = max(len(lines) for _, comparisons in groups for lines, _, _ in comparisons)
    maximum = max(value for _, comparisons in groups for _, a, b in comparisons for value in (a, b))
    y_max, tick_step = nice_axis(maximum * 1.08)

    def y(value: float) -> float:
        return top + plot_height * (1.0 - value / y_max)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{escape(title)}</title>',
        f'<desc id="desc">{escape(description)}</desc>',
        '<defs><pattern id="jsonb-hatch" width="7" height="7" patternUnits="userSpaceOnUse">',
        f'<rect width="7" height="7" fill="{COLORS["JSONB"]}"/>',
        '<path d="M-2 2 L2 -2 M0 7 L7 0 M5 9 L9 5" stroke="#222" stroke-width="1.2"/>',
        '</pattern></defs><rect width="100%" height="100%" fill="#fff"/>',
        f'<text x="{left}" y="24" font-family="sans-serif" font-size="15" font-weight="600">{escape(title)}</text>',
    ]
    legend_x = width - right - 220
    for index, system in enumerate(("SpecSon", "JSONB")):
        item_x = legend_x + index * 112
        parts.extend([
            f'<rect x="{item_x}" y="15" width="14" height="12" fill="{fill(system)}" stroke="#222"/>',
            f'<text x="{item_x + 20}" y="25" font-family="sans-serif" font-size="10.5">{system}</text>',
        ])
    tick = 0.0
    while tick <= y_max + tick_step * 0.01:
        tick_y = y(tick)
        parts.extend([
            f'<line x1="{left}" y1="{tick_y:.2f}" x2="{width-right}" y2="{tick_y:.2f}" stroke="#ddd"/>',
            f'<text x="{left-8}" y="{tick_y+4:.2f}" text-anchor="end" font-family="sans-serif" font-size="11">{tick:g}</text>',
        ])
        tick += tick_step
    zero_y = y(0.0)
    for group_index, (group_label, comparisons) in enumerate(groups):
        center = left + group_slot * (group_index + 0.5)
        content = len(comparisons) * pair_width + (len(comparisons) - 1) * comparison_gap
        first = center - content / 2
        for comparison_index, (lines, specson, jsonb) in enumerate(comparisons):
            pair_x = first + comparison_index * (pair_width + comparison_gap)
            pair_center = pair_x + pair_width / 2
            for system_index, (system, value) in enumerate((("SpecSon", specson), ("JSONB", jsonb))):
                bar_x = pair_x + system_index * (bar_width + pair_gap)
                bar_y = y(value)
                parts.extend([
                    f'<rect x="{bar_x:.2f}" y="{bar_y:.2f}" width="{bar_width}" height="{zero_y-bar_y:.2f}" fill="{fill(system)}" stroke="#222"/>',
                    f'<text x="{bar_x+bar_width/2:.2f}" y="{max(top+10, bar_y-6):.2f}" text-anchor="middle" font-family="sans-serif" font-size="9.5">{escape(format_value(value))}</text>',
                ])
            for line_index, label in enumerate(lines):
                parts.append(f'<text x="{pair_center:.2f}" y="{zero_y+17+line_index*13:.2f}" text-anchor="middle" font-family="sans-serif" font-size="9.5">{escape(label)}</text>')
        parts.append(f'<text x="{center:.2f}" y="{zero_y+30+max_lines*13:.2f}" text-anchor="middle" font-family="sans-serif" font-size="10.5">{escape(group_label)}</text>')
    parts.extend([
        f'<text transform="translate(18 {top+plot_height/2:.2f}) rotate(-90)" text-anchor="middle" font-family="sans-serif" font-size="11.5">{escape(y_label)}</text>',
        '</svg>',
    ])
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return destination


def grouped(results: list[dict[str, object]], part: str, storage: bool = False):
    groups = []
    for _, _, key, label, _ in DATASETS:
        records = {str(item["variant"]): item for item in results if item["dataset"] == key}
        comparisons = []
        for variant, variant_label in VARIANTS:
            item = records[variant]
            comparisons.append(((variant_label,), float(item[f"{part}_specson"]), float(item[f"{part}_jsonb"])))
            if storage:
                comparisons[-1] = ((variant_label, "Table"), float(item["table_specson"]), float(item["table_jsonb"]))
                comparisons.append(((variant_label, "Column"), float(item["column_specson"]), float(item["column_jsonb"])))
        groups.append((label, comparisons))
    return groups


def main() -> int:
    try:
        if len(sys.argv) > 2:
            raise ValueError("usage: plot_specson_results.py [OUTPUT_DIRECTORY]")
        output_dir = (
            Path(sys.argv[1]).expanduser().resolve()
            if len(sys.argv) == 2
            else DEFAULT_OUTPUT_DIR
        )
        results = load_results()
        destinations = (
            write_svg(grouped(results, "encode"), output_dir / "encode.svg", "Real-World Datasets: Encode Time", "Encode time for SpecSon and JSONB.", "Time (s)", lambda value: f"{value:.2f}"),
            write_svg(grouped(results, "restore"), output_dir / "restore.svg", "Real-World Datasets: Full Restore Time", "Full restore time for SpecSon and JSONB.", "Time (s)", lambda value: f"{value:.2f}"),
            write_svg(grouped(results, "table", storage=True), output_dir / "storage.svg", "Real-World Datasets: Storage Capacity", "Table and column capacity for SpecSon and JSONB.", "Capacity (GiB)", lambda value: f"{value:.2f}"),
        )
        for destination in destinations:
            print(destination)
        return 0
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
