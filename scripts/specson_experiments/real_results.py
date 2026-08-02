from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .catalog import SCHEMA_VARIANTS, Catalog, Dataset
from .results import read_result, result_path


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

    @property
    def encode_speedup(self) -> float:
        return self.encode_jsonb_ms / self.encode_specson_ms

    @property
    def restore_speedup(self) -> float:
        return self.restore_jsonb_ms / self.restore_specson_ms

    @property
    def table_ratio(self) -> float:
        return self.specson_table_bytes / self.jsonb_table_bytes

    @property
    def column_ratio(self) -> float:
        return self.specson_column_bytes / self.jsonb_column_bytes


def _mapping(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{location}: expected an object")
    return value


def _positive_float(value: Any, location: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{location}: expected a positive finite number")
    return result


def _positive_int(value: Any, location: str) -> int:
    result = int(value)
    if result <= 0:
        raise ValueError(f"{location}: expected a positive integer")
    return result


def _measurement(record: dict[str, Any], location: str) -> tuple[float, float]:
    measurement = _mapping(record.get("measurement"), f"{location}.measurement")
    specson_ms = _positive_float(
        measurement.get("specson_median_ms"), f"{location}.specson_median_ms"
    )
    jsonb_ms = _positive_float(
        measurement.get("jsonb_median_ms"), f"{location}.jsonb_median_ms"
    )
    declared = measurement.get("speedup")
    if declared is not None and not math.isclose(
        float(declared), jsonb_ms / specson_ms, rel_tol=1e-9, abs_tol=1e-12
    ):
        raise ValueError(f"{location}: speedup does not match the recorded medians")
    return specson_ms, jsonb_ms


def _storage(
    record: dict[str, Any], dataset: Dataset, location: str
) -> tuple[int, int, int, int]:
    storage = record.get("storage")
    if not isinstance(storage, list):
        raise ValueError(f"{location}.storage: expected an array")
    systems: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(storage):
        system_record = _mapping(item, f"{location}.storage[{index}]")
        system = str(system_record.get("system", ""))
        if system in systems:
            raise ValueError(f"{location}.storage: duplicate system {system!r}")
        systems[system] = system_record
    if set(systems) != {"specson", "jsonb"}:
        raise ValueError(f"{location}.storage: expected exactly specson and jsonb")
    expected_rows = dataset.expected_rows
    for system, system_record in systems.items():
        if expected_rows is None or int(system_record.get("rows", -1)) != expected_rows:
            raise ValueError(f"{location}.storage.{system}: row count mismatch")
    specson_table = _positive_int(
        systems["specson"].get("pg_table_size_bytes"),
        f"{location}.storage.specson.pg_table_size_bytes",
    )
    jsonb_table = _positive_int(
        systems["jsonb"].get("pg_table_size_bytes"),
        f"{location}.storage.jsonb.pg_table_size_bytes",
    )
    specson_column = _positive_int(
        systems["specson"].get("datum_bytes"),
        f"{location}.storage.specson.datum_bytes",
    )
    jsonb_column = _positive_int(
        systems["jsonb"].get("datum_bytes"),
        f"{location}.storage.jsonb.datum_bytes",
    )
    return specson_table, jsonb_table, specson_column, jsonb_column


def _require_variants(payload: dict[str, Any], path: Path) -> dict[str, Any]:
    variants = _mapping(payload.get("variants"), f"{path}.variants")
    if set(variants) != set(SCHEMA_VARIANTS):
        expected = ", ".join(SCHEMA_VARIANTS)
        raise ValueError(f"{path}: expected exactly these schema variants: {expected}")
    return variants


def load_real_results(catalog: Catalog, results_dir: Path) -> list[RealVariantResult]:
    datasets = tuple(sorted(catalog.real_datasets, key=lambda item: item.number))
    required = [
        result_path(results_dir, dataset, part)
        for dataset in datasets
        for part in ("encode", "restore")
    ]
    missing = [path for path in required if not path.is_file()]
    if missing:
        rendered = "\n  ".join(str(path) for path in missing)
        raise ValueError(f"missing required real-world dataset result files:\n  {rendered}")

    results: list[RealVariantResult] = []
    for dataset in datasets:
        encode_path = result_path(results_dir, dataset, "encode")
        restore_path = result_path(results_dir, dataset, "restore")
        encode = read_result(encode_path, dataset, "encode")
        restore = read_result(restore_path, dataset, "restore")
        if encode is None or restore is None:
            raise AssertionError("required result disappeared after the preflight check")
        encode_variants = _require_variants(encode, encode_path)
        restore_variants = _require_variants(restore, restore_path)
        for variant in SCHEMA_VARIANTS:
            encode_record = _mapping(
                encode_variants[variant], f"{encode_path}.variants.{variant}"
            )
            restore_record = _mapping(
                restore_variants[variant], f"{restore_path}.variants.{variant}"
            )
            encode_specson, encode_jsonb = _measurement(
                encode_record, f"{encode_path}.variants.{variant}"
            )
            restore_specson, restore_jsonb = _measurement(
                restore_record, f"{restore_path}.variants.{variant}"
            )
            table_specson, table_jsonb, column_specson, column_jsonb = _storage(
                encode_record, dataset, f"{encode_path}.variants.{variant}"
            )
            results.append(RealVariantResult(
                dataset_key=dataset.key,
                dataset_label=dataset.label,
                variant=variant,
                encode_specson_ms=encode_specson,
                encode_jsonb_ms=encode_jsonb,
                restore_specson_ms=restore_specson,
                restore_jsonb_ms=restore_jsonb,
                specson_table_bytes=table_specson,
                jsonb_table_bytes=table_jsonb,
                specson_column_bytes=column_specson,
                jsonb_column_bytes=column_jsonb,
            ))
    return results
