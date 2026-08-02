from __future__ import annotations

import math
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Callable, Iterable

from .catalog import SCHEMA_VARIANTS
from .real_results import RealVariantResult


SYSTEM_COLORS = {
    "SpecSon": "#3182bd",
    "JSONB": "#9ecae1",
}


def _system_fill(system: str) -> str:
    return SYSTEM_COLORS[system] if system == "SpecSon" else "url(#jsonb-hatch)"


@dataclass(frozen=True)
class Comparison:
    label_lines: tuple[str, ...]
    specson: float
    jsonb: float


@dataclass(frozen=True)
class DatasetGroup:
    label: str
    comparisons: tuple[Comparison, ...]


def _nice_axis(maximum: float) -> tuple[float, float]:
    if not math.isfinite(maximum) or maximum <= 0.0:
        raise ValueError("plot maximum must be positive and finite")
    rough_step = maximum / 5.0
    magnitude = 10.0 ** math.floor(math.log10(rough_step))
    normalized = rough_step / magnitude
    if normalized <= 1.0:
        nice = 1.0
    elif normalized <= 2.0:
        nice = 2.0
    elif normalized <= 2.5:
        nice = 2.5
    elif normalized <= 5.0:
        nice = 5.0
    else:
        nice = 10.0
    step = nice * magnitude
    return math.ceil(maximum / step) * step, step


def _ordered_variant_records(
    results: Iterable[RealVariantResult],
) -> list[tuple[str, dict[str, RealVariantResult]]]:
    grouped: dict[str, dict[str, RealVariantResult]] = {}
    labels: dict[str, str] = {}
    order: list[str] = []
    for result in results:
        if result.dataset_key not in grouped:
            grouped[result.dataset_key] = {}
            labels[result.dataset_key] = result.dataset_label
            order.append(result.dataset_key)
        grouped[result.dataset_key][result.variant] = result
    ordered: list[tuple[str, dict[str, RealVariantResult]]] = []
    for dataset in order:
        variants = grouped[dataset]
        if set(variants) != set(SCHEMA_VARIANTS):
            raise ValueError(f"{dataset}: incomplete schema variants")
        ordered.append((labels[dataset], variants))
    return ordered


def _write_comparison_svg(
    groups: list[DatasetGroup],
    destination: Path,
    title: str,
    description: str,
    y_label: str,
    value_label: Callable[[float], str],
    tick_label: Callable[[float], str],
) -> Path:
    if not groups or any(not group.comparisons for group in groups):
        raise ValueError(f"{title}: no values to plot")
    comparisons_per_group = max(len(group.comparisons) for group in groups)
    pair_bar_width = 24.0
    pair_gap = 5.0
    comparison_gap = 18.0
    pair_width = pair_bar_width * 2 + pair_gap
    content_width = comparisons_per_group * pair_width + (
        comparisons_per_group - 1
    ) * comparison_gap
    group_width = max(168.0, content_width + 36.0)
    width = max(720, int(112 + group_width * len(groups)))
    height = 480
    left, right, top, bottom = 68, 24, 76, 100
    plot_width = width - left - right
    plot_height = height - top - bottom
    group_slot = plot_width / len(groups)
    maximum_label_lines = max(
        len(comparison.label_lines)
        for group in groups
        for comparison in group.comparisons
    )
    maximum = max(
        value
        for group in groups
        for comparison in group.comparisons
        for value in (comparison.specson, comparison.jsonb)
    )
    y_max, tick_step = _nice_axis(maximum * 1.08)

    def y(value: float) -> float:
        return top + plot_height * (1.0 - value / y_max)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{escape(title)}</title>',
        f'<desc id="desc">{escape(description)}</desc>',
        '<defs>',
        '<pattern id="jsonb-hatch" width="7" height="7" '
        'patternUnits="userSpaceOnUse">',
        f'<rect class="pattern-background" width="7" height="7" '
        f'fill="{SYSTEM_COLORS["JSONB"]}"/>',
        '<path d="M-2 2 L2 -2 M0 7 L7 0 M5 9 L9 5" '
        'stroke="#222222" stroke-width="1.2"/>',
        '</pattern>',
        '</defs>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{left}" y="24" font-family="sans-serif" font-size="15" '
        f'font-weight="600" fill="#222222">{escape(title)}</text>',
    ]
    legend_x = width - right - 272
    for index, system in enumerate(("SpecSon", "JSONB")):
        item_x = legend_x + index * 140
        texture = "solid" if system == "SpecSon" else "hatched"
        parts.extend([
            f'<rect class="legend-swatch system-{system.lower()}" x="{item_x}" '
            f'y="15" width="14" height="12" fill="{_system_fill(system)}" '
            f'stroke="#222222" stroke-width="0.9"/>',
            f'<text x="{item_x+20}" y="25" font-family="sans-serif" '
            f'font-size="10.5" fill="#222222">{system} ({texture})</text>',
        ])
    tick = 0.0
    while tick <= y_max + tick_step * 0.01:
        tick_y = y(tick)
        parts.extend([
            f'<line x1="{left}" y1="{tick_y:.2f}" x2="{width-right}" '
            f'y2="{tick_y:.2f}" stroke="#dddddd" stroke-width="1"/>',
            f'<text x="{left-8}" y="{tick_y+4:.2f}" text-anchor="end" '
            f'font-family="sans-serif" font-size="11" fill="#444444">'
            f'{escape(tick_label(tick))}</text>',
        ])
        tick += tick_step
    zero_y = y(0.0)
    for group_index, group in enumerate(groups):
        group_center = left + group_slot * (group_index + 0.5)
        group_content_width = len(group.comparisons) * pair_width + (
            len(group.comparisons) - 1
        ) * comparison_gap
        first_pair_x = group_center - group_content_width / 2
        for comparison_index, comparison in enumerate(group.comparisons):
            pair_x = first_pair_x + comparison_index * (pair_width + comparison_gap)
            pair_center = pair_x + pair_width / 2
            for system_index, (system, value) in enumerate((
                ("SpecSon", comparison.specson),
                ("JSONB", comparison.jsonb),
            )):
                bar_x = pair_x + system_index * (pair_bar_width + pair_gap)
                bar_center = bar_x + pair_bar_width / 2
                bar_y = y(value)
                parts.extend([
                    f'<rect class="data-bar system-{system.lower()}" '
                    f'x="{bar_x:.2f}" y="{bar_y:.2f}" '
                    f'width="{pair_bar_width:.2f}" height="{zero_y-bar_y:.2f}" '
                    f'fill="{_system_fill(system)}" stroke="#222222" '
                    f'stroke-width="0.9"/>',
                    f'<text x="{bar_center:.2f}" y="{max(top+10, bar_y-6):.2f}" '
                    f'text-anchor="middle" font-family="sans-serif" font-size="9.5" '
                    f'fill="#222222">{escape(value_label(value))}</text>',
                ])
            for line_index, label in enumerate(comparison.label_lines):
                parts.append(
                    f'<text x="{pair_center:.2f}" y="{zero_y+17+line_index*13:.2f}" '
                    f'text-anchor="middle" font-family="sans-serif" font-size="9.5" '
                    f'fill="#444444">{escape(label)}</text>'
                )
        parts.append(
            f'<text x="{group_center:.2f}" '
            f'y="{zero_y+30+maximum_label_lines*13:.2f}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="10.5" fill="#222222">'
            f'{escape(group.label)}</text>'
        )
    parts.extend([
        f'<text transform="translate(18 {top+plot_height/2:.2f}) rotate(-90)" '
        'text-anchor="middle" font-family="sans-serif" font-size="11.5" '
        f'fill="#222222">{escape(y_label)}</text>',
        '</svg>',
    ])
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return destination


def _time_groups(
    results: Iterable[RealVariantResult], part: str
) -> list[DatasetGroup]:
    groups: list[DatasetGroup] = []
    for label, variants in _ordered_variant_records(results):
        comparisons: list[Comparison] = []
        for variant, display in (("ordinary", "Integer"), ("numeric", "Numeric")):
            record = variants[variant]
            comparisons.append(Comparison(
                (display,),
                float(getattr(record, f"{part}_specson_ms")) / 1000.0,
                float(getattr(record, f"{part}_jsonb_ms")) / 1000.0,
            ))
        groups.append(DatasetGroup(label, tuple(comparisons)))
    return groups


def plot_encode(results: Iterable[RealVariantResult], destination: Path) -> Path:
    return _write_comparison_svg(
        _time_groups(results, "encode"),
        destination,
        "Real-World Datasets: Encode Time",
        "Encode time for SpecSon and jsonb across all real-world datasets. SpecSon bars are solid and JSONB bars are hatched.",
        "Time (s)",
        lambda value: f"{value:.2f}",
        lambda value: f"{value:g}",
    )


def plot_restore(results: Iterable[RealVariantResult], destination: Path) -> Path:
    return _write_comparison_svg(
        _time_groups(results, "restore"),
        destination,
        "Real-World Datasets: Full Restore Time",
        "Full restore time for SpecSon and jsonb across all real-world datasets. SpecSon bars are solid and JSONB bars are hatched.",
        "Time (s)",
        lambda value: f"{value:.2f}",
        lambda value: f"{value:g}",
    )


def plot_storage(results: Iterable[RealVariantResult], destination: Path) -> Path:
    gib = float(1024**3)
    groups: list[DatasetGroup] = []
    for label, variants in _ordered_variant_records(results):
        comparisons: list[Comparison] = []
        for variant, display in (("ordinary", "Integer"), ("numeric", "Numeric")):
            record = variants[variant]
            comparisons.extend((
                Comparison(
                    (display, "Table"),
                    record.specson_table_bytes / gib,
                    record.jsonb_table_bytes / gib,
                ),
                Comparison(
                    (display, "Column"),
                    record.specson_column_bytes / gib,
                    record.jsonb_column_bytes / gib,
                ),
            ))
        groups.append(DatasetGroup(label, tuple(comparisons)))
    return _write_comparison_svg(
        groups,
        destination,
        "Real-World Datasets: Storage Capacity",
        "SpecSon and jsonb storage capacity. Table is pg_table_size and column is the sum of pg_column_size. SpecSon bars are solid and JSONB bars are hatched.",
        "Capacity (GiB)",
        lambda value: f"{value:.2f}",
        lambda value: f"{value:g}",
    )
