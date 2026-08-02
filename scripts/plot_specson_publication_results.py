#!/usr/bin/env python3
"""Generate encode, restore, and storage publication figures."""

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
DEFAULT_OUTPUT_DIR = REPO_ROOT / "experiments/specson/figures/publication"
OKABE_ITO = {"specson": "#0072B2", "jsonb": "#E69F00"}
FIGURE_WIDTH_INCHES = 3.33
FIGURE_HEIGHT_INCHES = 1.75
RASTER_DPI = 300
SCHEMA_VARIANTS = ("ordinary", "numeric")
REAL_DATASETS = (
    (1, "Yelp-Review", "yelp-review", "Yelp Review", 6_990_280),
    (2, "Yelp-Business", "yelp-business", "Yelp Business", 150_346),
    (3, "GitHub", "github", "GitHub Archive", 3_795_000),
    (4, "OpenAlex", "openalex", "OpenAlex Works", 358_387),
)


@dataclass(frozen=True)
class RealVariantResult:
    dataset_key: str
    dataset_label: str
    variant: str
    encode_specson_ms: float
    encode_jsonb_ms: float
    restore_specson_ms: float
    restore_jsonb_ms: float
    specson_table_bytes: int
    jsonb_table_bytes: int
    specson_column_bytes: int
    jsonb_column_bytes: int


def mapping(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{location}: expected an object")
    return value


def positive_float(value: Any, location: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{location}: expected a positive finite number")
    return result


def positive_int(value: Any, location: str) -> int:
    result = int(value)
    if result <= 0:
        raise ValueError(f"{location}: expected a positive integer")
    return result


def load_part(path: Path, part: str, dataset: tuple[int, str, str, str, int]) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"missing required result file: {path}")
    payload = mapping(json.loads(path.read_text(encoding="utf-8")), str(path))
    if payload.get("format") != "specson_experiment_part_result_v1":
        raise ValueError(f"{path}: unsupported result format")
    if payload.get("part") != part:
        raise ValueError(f"{path}: expected part {part!r}")
    number, name, key, label, expected_rows = dataset
    identity = mapping(payload.get("dataset"), f"{path}.dataset")
    expected_identity = {
        "id": number, "name": name, "key": key, "label": label,
        "expected_rows": expected_rows,
    }
    for field, expected in expected_identity.items():
        if identity.get(field) != expected:
            raise ValueError(f"{path}: dataset {field} mismatch")
    variants = mapping(payload.get("variants"), f"{path}.variants")
    if set(variants) != set(SCHEMA_VARIANTS):
        raise ValueError(f"{path}: expected exactly ordinary and numeric variants")
    return variants


def measurement(record: dict[str, Any], location: str) -> tuple[float, float]:
    values = mapping(record.get("measurement"), f"{location}.measurement")
    specson = positive_float(values.get("specson_median_ms"), f"{location}.specson_median_ms")
    jsonb = positive_float(values.get("jsonb_median_ms"), f"{location}.jsonb_median_ms")
    declared = values.get("speedup")
    if declared is not None and not math.isclose(
        float(declared), jsonb / specson, rel_tol=1e-9, abs_tol=1e-12
    ):
        raise ValueError(f"{location}: speedup does not match the recorded medians")
    return specson, jsonb


def storage(record: dict[str, Any], expected_rows: int, location: str) -> tuple[int, int, int, int]:
    values = record.get("storage")
    if not isinstance(values, list):
        raise ValueError(f"{location}.storage: expected an array")
    systems = {
        str(item.get("system")): mapping(item, f"{location}.storage")
        for item in values
        if isinstance(item, dict)
    }
    if set(systems) != {"specson", "jsonb"} or len(values) != 2:
        raise ValueError(f"{location}.storage: expected exactly specson and jsonb")
    for system, item in systems.items():
        if int(item.get("rows", -1)) != expected_rows:
            raise ValueError(f"{location}.storage.{system}: row count mismatch")
    return (
        positive_int(systems["specson"].get("pg_table_size_bytes"), f"{location}.specson.table"),
        positive_int(systems["jsonb"].get("pg_table_size_bytes"), f"{location}.jsonb.table"),
        positive_int(systems["specson"].get("datum_bytes"), f"{location}.specson.column"),
        positive_int(systems["jsonb"].get("datum_bytes"), f"{location}.jsonb.column"),
    )


def load_real_results() -> list[RealVariantResult]:
    results: list[RealVariantResult] = []
    for dataset in REAL_DATASETS:
        number, name, key, label, expected_rows = dataset
        stem = f"{number:03d}-{name}"
        encode_path = RESULTS_DIR / f"{stem}-encode.json"
        restore_path = RESULTS_DIR / f"{stem}-restore.json"
        encode = load_part(encode_path, "encode", dataset)
        restore = load_part(restore_path, "restore", dataset)
        for variant in SCHEMA_VARIANTS:
            encode_record = mapping(encode[variant], f"{encode_path}.variants.{variant}")
            restore_record = mapping(restore[variant], f"{restore_path}.variants.{variant}")
            encode_specson, encode_jsonb = measurement(encode_record, str(encode_path))
            restore_specson, restore_jsonb = measurement(restore_record, str(restore_path))
            table_specson, table_jsonb, column_specson, column_jsonb = storage(
                encode_record, expected_rows, str(encode_path)
            )
            results.append(RealVariantResult(
                key, label, variant, encode_specson, encode_jsonb,
                restore_specson, restore_jsonb, table_specson, table_jsonb,
                column_specson, column_jsonb,
            ))
    return results


def configure_style() -> None:
    import matplotlib as mpl

    mpl.rcParams.update({
        "figure.dpi": 150,
        "savefig.dpi": RASTER_DPI,
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
        "font.weight": "normal",
        "font.size": 7,
        "axes.labelsize": 8,
        "axes.labelweight": "normal",
        "axes.titlesize": 8,
        "axes.titleweight": "normal",
        "xtick.labelsize": 4.8,
        "ytick.labelsize": 7,
        "legend.fontsize": 7,
        "axes.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "lines.linewidth": 1.0,
        "hatch.linewidth": 0.7,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "axes.unicode_minus": False,
    })


def ordered_records(results: list[RealVariantResult]) -> list[RealVariantResult]:
    identities = {(record.dataset_key, record.variant) for record in results}
    if len(results) != 8 or len(identities) != 8:
        raise ValueError(
            "publication figures require exactly 4 real-world datasets x 2 schemas"
        )
    return results


def category_labels(records: list[RealVariantResult]) -> list[str]:
    variants = {"ordinary": "Integer", "numeric": "Numeric"}
    return [variants[record.variant] for record in records]


def legend_handles():
    from matplotlib.patches import Patch

    return [
        Patch(
            facecolor=OKABE_ITO["specson"], edgecolor="#1A1A1A",
            linewidth=0.6, label="SpecSON",
        ),
        Patch(
            facecolor=OKABE_ITO["jsonb"], edgecolor="#1A1A1A",
            linewidth=0.6, hatch="///", label="jsonb",
        ),
    ]


def draw_grouped_bars(
    axis,
    positions: list[float],
    specson_values: list[float],
    jsonb_values: list[float],
) -> None:
    width = 0.34
    axis.bar(
        [position - width / 2 for position in positions], specson_values,
        width=width, color=OKABE_ITO["specson"], edgecolor="#1A1A1A",
        linewidth=0.6, zorder=3,
    )
    axis.bar(
        [position + width / 2 for position in positions], jsonb_values,
        width=width, color=OKABE_ITO["jsonb"], edgecolor="#1A1A1A",
        linewidth=0.6, hatch="///", zorder=3,
    )


def finish_axis(
    axis, records: list[RealVariantResult], ylabel: str, maximum: float,
    show_dataset_labels: bool = True,
) -> None:
    from matplotlib.ticker import MaxNLocator

    labels = category_labels(records)
    axis.set_xlim(-0.55, len(labels) - 0.45)
    axis.set_ylim(0.0, maximum * 1.08)
    axis.set_ylabel(ylabel)
    axis.set_xticks(list(range(len(labels))))
    axis.set_xticklabels(labels, linespacing=1.15)
    for label in axis.get_xticklabels():
        label.set_fontweight("bold")
    if show_dataset_labels:
        short_labels = {
            "yelp-review": "Yelp\nReview",
            "yelp-business": "Yelp\nBusiness",
            "github": "GitHub\nArchive",
            "openalex": "OpenAlex\nWorks",
        }
        for start in range(0, len(records), 2):
            axis.text(
                start + 0.5, -0.16, short_labels[records[start].dataset_key],
                transform=axis.get_xaxis_transform(), ha="center", va="top",
                fontsize=6, fontweight="bold",
            )
    axis.yaxis.set_major_locator(MaxNLocator(nbins=5, min_n_ticks=4))
    axis.yaxis.grid(True, color="#D9D9D9", linewidth=0.45)
    axis.xaxis.grid(False)
    axis.set_axisbelow(True)
    for boundary in (1.5, 3.5, 5.5):
        axis.axvline(boundary, color="#E5E5E5", linewidth=0.55, zorder=0)


def create_time_figure(records: list[RealVariantResult], part: str):
    import matplotlib.pyplot as plt

    specson = [float(getattr(record, f"{part}_specson_ms")) / 1000.0 for record in records]
    jsonb = [float(getattr(record, f"{part}_jsonb_ms")) / 1000.0 for record in records]
    figure, axis = plt.subplots(
        figsize=(FIGURE_WIDTH_INCHES, FIGURE_HEIGHT_INCHES), layout="constrained"
    )
    positions = [float(index) for index in range(len(records))]
    draw_grouped_bars(axis, positions, specson, jsonb)
    finish_axis(axis, records, "Time (s)", max(specson + jsonb))
    axis.set_title(
        "Encode" if part == "encode" else "Full restore",
        loc="left", fontweight="normal",
    )
    axis.legend(
        handles=legend_handles(), loc="upper right", bbox_to_anchor=(1.0, 1.16),
        ncol=2, frameon=False, handletextpad=0.45, columnspacing=1.4,
        prop={"size": 7, "weight": "normal"},
    )
    return figure


def create_storage_figure(records: list[RealVariantResult]):
    import matplotlib.pyplot as plt

    gib = float(1024**3)
    specson = [record.specson_table_bytes / gib for record in records]
    jsonb = [record.jsonb_table_bytes / gib for record in records]
    figure, axis = plt.subplots(
        figsize=(FIGURE_WIDTH_INCHES, FIGURE_HEIGHT_INCHES), layout="constrained"
    )
    positions = [float(index) for index in range(len(records))]
    draw_grouped_bars(axis, positions, specson, jsonb)
    finish_axis(axis, records, "Table size (GiB)", max(specson + jsonb))
    axis.set_title("Storage", loc="left", fontweight="normal")
    axis.legend(
        handles=legend_handles(), loc="upper center", bbox_to_anchor=(0.5, 1.13),
        ncol=2, frameon=False, handletextpad=0.45, columnspacing=1.4,
        prop={"size": 7, "weight": "normal"},
    )
    return figure


def ticklabels_overlap(labels, renderer) -> bool:
    boxes = [
        label.get_window_extent(renderer)
        for label in labels
        if label.get_visible() and label.get_text().strip()
    ]
    boxes.sort(key=lambda box: box.x0)
    return any(left.x1 > right.x0 for left, right in zip(boxes, boxes[1:]))


def audit_figure(figure, name: str) -> dict[str, object]:
    import matplotlib.text as mtext

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        figure.canvas.draw()
    glyphs = [
        str(warning.message)
        for warning in caught
        if "Glyph" in str(warning.message) and "missing" in str(warning.message)
    ]
    renderer = figure.canvas.get_renderer()
    width, height = float(figure.bbox.width), float(figure.bbox.height)
    tick_ids = {
        id(label)
        for axis in figure.axes
        for label in (*axis.get_xticklabels(), *axis.get_yticklabels())
    }
    clipped: list[str] = []
    for text in figure.findobj(mtext.Text):
        if not text.get_visible() or not text.get_text().strip() or id(text) in tick_ids:
            continue
        box = text.get_window_extent(renderer)
        if box.x0 < -1 or box.y0 < -1 or box.x1 > width + 1 or box.y1 > height + 1:
            clipped.append(text.get_text().replace("\n", " ")[:40])
    overlaps = [
        index for index, axis in enumerate(figure.axes)
        if ticklabels_overlap(axis.get_xticklabels(), renderer)
    ]
    size = figure.get_size_inches()
    passed = not clipped and not overlaps and not glyphs
    return {
        "name": name,
        "width_inches": float(size[0]),
        "height_inches": float(size[1]),
        "clipped_text": list(dict.fromkeys(clipped)),
        "overlapping_tick_axes": overlaps,
        "missing_glyph_warnings": list(dict.fromkeys(glyphs)),
        "status": "PASS" if passed else "FAIL",
    }


def export_figure(figure, destination: Path) -> list[Path]:
    from PIL import Image

    destination.parent.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for extension in ("pdf", "svg", "png"):
        path = destination.with_suffix(f".{extension}")
        options: dict[str, object] = {"facecolor": "white", "transparent": False}
        if extension == "png":
            options["dpi"] = RASTER_DPI
        figure.savefig(path, **options)
        outputs.append(path)
    grayscale = destination.with_name(destination.name + "-grayscale").with_suffix(".png")
    with Image.open(destination.with_suffix(".png")) as image:
        image.convert("L").save(grayscale)
    outputs.append(grayscale)
    return outputs


def main() -> int:
    figures = []
    try:
        if len(sys.argv) > 2:
            raise ValueError(
                "usage: plot_specson_publication_results.py [OUTPUT_DIRECTORY]"
            )
        output_dir = (
            Path(sys.argv[1]).expanduser().resolve()
            if len(sys.argv) == 2
            else DEFAULT_OUTPUT_DIR
        )
        configure_style()
        records = ordered_records(load_real_results())
        figures = [
            ("encode", create_time_figure(records, "encode")),
            ("restore", create_time_figure(records, "restore")),
            ("storage", create_storage_figure(records)),
        ]
        audits = [audit_figure(figure, name) for name, figure in figures]
        output_dir.mkdir(parents=True, exist_ok=True)
        report = output_dir / "audit.json"
        report.write_text(json.dumps({
            "format": "specson_publication_figure_audit_v1",
            "source": "inspired by scipilot-figure-skill publication workflow",
            "audits": audits,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        failures = [audit for audit in audits if audit["status"] != "PASS"]
        if failures:
            raise RuntimeError(f"publication figure audit failed: {failures}")
        outputs: list[Path] = []
        for name, figure in figures:
            outputs.extend(export_figure(figure, output_dir / name))
        for path in (*outputs, report):
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
