#!/usr/bin/env python3
"""Generate real-world query speedup figures for both schema variants."""

from __future__ import annotations

import json
import math
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "experiments/specson/results"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "experiments/specson/figures/query"
FIGURE_WIDTH_INCHES = 3.33
FIGURE_HEIGHT_INCHES = 2.35
RASTER_DPI = 300
VARIANTS = (("ordinary", "Integer"), ("numeric", "Numeric"))
DATASETS = (
    (1, "Yelp-Review", "yelp-review", "Yelp Review", 6_990_280),
    (2, "Yelp-Business", "yelp-business", "Yelp Business", 150_346),
    (3, "GitHub", "github", "GitHub Archive", 3_795_000),
    (4, "OpenAlex", "openalex", "OpenAlex Works", 358_387),
)
DATASET_COLORS = {
    "yelp-review": "#6F9E63",
    "yelp-business": "#D2B55B",
    "github": "#4E79A7",
    "openalex": "#B07AA1",
}


@dataclass(frozen=True)
class QueryResult:
    query_id: str
    operation: str
    variant: str
    specson_ms: float
    jsonb_ms: float

    @property
    def speedup(self) -> float:
        return self.jsonb_ms / self.specson_ms


@dataclass(frozen=True)
class DatasetResult:
    key: str
    label: str
    queries: tuple[QueryResult, ...]


def mapping(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{location}: expected an object")
    return value


def positive_float(value: Any, location: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{location}: expected a positive finite number")
    return result


def load_dataset_result(
    dataset: tuple[int, str, str, str, int],
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
    expected_identity = {
        "id": number,
        "name": name,
        "key": key,
        "label": label,
        "expected_rows": expected_rows,
    }
    for field, expected in expected_identity.items():
        if identity.get(field) != expected:
            raise ValueError(f"{path}: dataset {field} mismatch")
    raw_queries = payload.get("queries")
    if not isinstance(raw_queries, list) or not raw_queries:
        raise ValueError(f"{path}.queries: expected a non-empty array")
    queries: list[QueryResult] = []
    identities: set[tuple[str, str, str]] = set()
    for index, raw_query in enumerate(raw_queries):
        location = f"{path}.queries[{index}]"
        record = mapping(raw_query, location)
        query_id = str(record.get("query_id", ""))
        operation = str(record.get("operation", ""))
        variant = str(record.get("variant", ""))
        if not query_id or operation not in {"exists", "count"}:
            raise ValueError(f"{location}: invalid query identity")
        if variant not in {value for value, _ in VARIANTS}:
            raise ValueError(f"{location}: invalid schema variant")
        query_identity = (query_id, operation, variant)
        if query_identity in identities:
            raise ValueError(f"{location}: duplicate query identity")
        identities.add(query_identity)
        measurement = mapping(record.get("measurement"), f"{location}.measurement")
        specson = positive_float(
            measurement.get("specson_median_ms"),
            f"{location}.specson_median_ms",
        )
        jsonb = positive_float(
            measurement.get("jsonb_median_ms"),
            f"{location}.jsonb_median_ms",
        )
        declared = positive_float(measurement.get("speedup"), f"{location}.speedup")
        if not math.isclose(declared, jsonb / specson, rel_tol=1e-9, abs_tol=1e-12):
            raise ValueError(f"{location}: speedup does not match recorded medians")
        queries.append(QueryResult(query_id, operation, variant, specson, jsonb))
    query_order = list(dict.fromkeys((item.query_id, item.operation) for item in queries))
    expected_identities = {
        (query_id, operation, variant)
        for query_id, operation in query_order
        for variant, _ in VARIANTS
    }
    if identities != expected_identities:
        raise ValueError(f"{path}: incomplete ordinary/numeric query matrix")
    return DatasetResult(key, label, tuple(queries))


def configure_style() -> None:
    import matplotlib as mpl

    mpl.rcParams.update({
        "figure.dpi": 150,
        "savefig.dpi": RASTER_DPI,
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "font.size": 7,
        "axes.labelsize": 8,
        "axes.titlesize": 8,
        "axes.titleweight": "normal",
        "xtick.labelsize": 5.2,
        "ytick.labelsize": 7,
        "legend.fontsize": 7,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.major.width": 0.7,
        "ytick.major.width": 0.7,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "axes.unicode_minus": False,
    })


def create_variant_figure(
    datasets: list[DatasetResult],
    variant: str,
    variant_label: str,
):
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MultipleLocator

    figure, axis = plt.subplots(
        figsize=(FIGURE_WIDTH_INCHES, FIGURE_HEIGHT_INCHES),
        layout="constrained",
    )
    positions: list[float] = []
    labels: list[str] = []
    values: list[float] = []
    colors: list[str] = []
    boundaries: list[float] = []
    groups: list[tuple[float, float, str]] = []
    cursor = 0.0
    group_gap = 1.35
    for dataset_index, dataset in enumerate(datasets):
        records = [query for query in dataset.queries if query.variant == variant]
        if not records:
            raise ValueError(f"{dataset.key}: missing {variant} query records")
        group_start = cursor
        for record in records:
            positions.append(cursor)
            labels.append(record.query_id)
            values.append(record.speedup)
            colors.append(DATASET_COLORS[dataset.key])
            cursor += 1.0
        group_end = cursor - 1.0
        groups.append((
            group_start,
            group_end,
            dataset.label,
        ))
        if dataset_index + 1 < len(datasets):
            boundaries.append(cursor + (group_gap - 1.0) / 2.0)
            cursor += group_gap
    maximum = max(values)
    y_max = max(2.0, math.ceil(maximum * 1.12 * 2.0) / 2.0)
    axis.bar(
        positions,
        values,
        width=0.68,
        color=colors,
        edgecolor="#FFFFFF",
        linewidth=0.5,
        zorder=3,
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
    for group_start, group_end, group_label in groups:
        axis.text(
            (group_start + group_end) / 2.0,
            -0.19,
            group_label.replace(" ", "\n"),
            color="#252525",
            fontsize=5.5,
            fontweight="bold",
            ha="center",
            va="top",
            transform=axis.get_xaxis_transform(),
            clip_on=False,
        )
    axis.set_xlim(min(positions) - 0.8, max(positions) + 0.8)
    axis.set_ylim(0.0, y_max)
    axis.set_ylabel("Speedup over JSONB")
    axis.set_xticks(positions)
    axis.set_xticklabels(labels, rotation=90, ha="center", va="top")
    axis.tick_params(axis="x", pad=2)
    axis.yaxis.set_major_locator(MultipleLocator(0.5))
    axis.yaxis.grid(True, color="#D9D9D9", linewidth=0.55)
    axis.xaxis.grid(False)
    axis.set_axisbelow(True)
    axis.annotate(
        "",
        xy=(1.012, 0.0),
        xytext=(1.0, 0.0),
        xycoords="axes fraction",
        arrowprops={"arrowstyle": "->", "color": "#1A1A1A", "lw": 0.8},
        annotation_clip=False,
    )
    axis.annotate(
        "",
        xy=(0.0, 1.018),
        xytext=(0.0, 1.0),
        xycoords="axes fraction",
        arrowprops={"arrowstyle": "->", "color": "#1A1A1A", "lw": 0.8},
        annotation_clip=False,
    )
    return figure


def ticklabels_overlap(labels: list[Any], renderer: Any) -> bool:
    boxes = [
        label.get_window_extent(renderer)
        for label in labels
        if label.get_visible() and label.get_text().strip()
    ]
    boxes.sort(key=lambda box: box.x0)
    return any(left.x1 > right.x0 for left, right in zip(boxes, boxes[1:]))


def audit_figure(figure: Any, name: str) -> dict[str, Any]:
    import matplotlib.text as mtext

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    width, height = float(figure.bbox.width), float(figure.bbox.height)
    tick_ids = {
        id(label)
        for axis in figure.axes
        for label in (*axis.get_xticklabels(), *axis.get_yticklabels())
    }
    clipped: list[str] = []
    for item in figure.findobj(mtext.Text):
        if not item.get_visible() or not item.get_text().strip() or id(item) in tick_ids:
            continue
        box = item.get_window_extent(renderer)
        if box.x0 < -1 or box.y0 < -1 or box.x1 > width + 1 or box.y1 > height + 1:
            clipped.append(item.get_text().replace("\n", " ")[:48])
    overlaps = [
        index
        for index, axis in enumerate(figure.axes)
        if ticklabels_overlap(list(axis.get_xticklabels()), renderer)
    ]
    glyphs = [
        str(item.message)
        for item in caught
        if "Glyph" in str(item.message) and "missing" in str(item.message)
    ]
    passed = not clipped and not overlaps and not glyphs
    return {
        "name": name,
        "width_inches": FIGURE_WIDTH_INCHES,
        "height_inches": FIGURE_HEIGHT_INCHES,
        "clipped_text": list(dict.fromkeys(clipped)),
        "overlapping_tick_axes": overlaps,
        "missing_glyph_warnings": list(dict.fromkeys(glyphs)),
        "status": "PASS" if passed else "FAIL",
    }


def export_figure(figure: Any, output_dir: Path, stem: str) -> list[Path]:
    from PIL import Image

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for extension in ("pdf", "svg", "png"):
        path = output_dir / f"{stem}.{extension}"
        options: dict[str, Any] = {"facecolor": "white", "transparent": False}
        if extension == "png":
            options["dpi"] = RASTER_DPI
        figure.savefig(path, **options)
        outputs.append(path)
    grayscale = output_dir / f"{stem}-grayscale.png"
    with Image.open(output_dir / f"{stem}.png") as image:
        image.convert("L").save(grayscale)
    outputs.append(grayscale)
    return outputs


def main() -> int:
    figures: list[tuple[str, Any]] = []
    try:
        if len(sys.argv) > 2:
            raise ValueError(
                "usage: plot_specson_query_results.py [OUTPUT_DIRECTORY]"
            )
        output_dir = (
            Path(sys.argv[1]).expanduser().resolve()
            if len(sys.argv) == 2
            else DEFAULT_OUTPUT_DIR
        )
        configure_style()
        datasets = [load_dataset_result(dataset) for dataset in DATASETS]
        figures = [
            (
                f"query-{variant}",
                create_variant_figure(datasets, variant, variant_label),
            )
            for variant, variant_label in VARIANTS
        ]
        audits = [audit_figure(figure, name) for name, figure in figures]
        output_dir.mkdir(parents=True, exist_ok=True)
        audit_path = output_dir / "query-audit.json"
        audit_path.write_text(
            json.dumps({
                "format": "specson_query_figure_audit_v2",
                "audits": audits,
            }, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        failures = [audit for audit in audits if audit["status"] != "PASS"]
        if failures:
            raise RuntimeError(f"query figure audit failed: {failures}")
        outputs: list[Path] = []
        for name, figure in figures:
            outputs.extend(export_figure(figure, output_dir, name))
        for path in (*outputs, audit_path):
            print(path)
        return 0
    except ModuleNotFoundError as error:
        print(
            "error: install plotting dependencies with "
            "python3 -m pip install -r scripts/requirements-figures.txt "
            f"({error})",
            file=sys.stderr,
        )
        return 2
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    finally:
        if figures:
            try:
                import matplotlib.pyplot as plt

                for _, figure in figures:
                    plt.close(figure)
            except ModuleNotFoundError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
