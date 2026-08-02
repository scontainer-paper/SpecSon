#!/usr/bin/env python3
"""Run one SpecSon VLDB dataset, one independently selected part at a time."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import platform
import statistics
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from specson_experiments.catalog import (
    FAMILY_RQ,
    Catalog,
    Dataset,
    parse_csv_selection,
    parse_schema_variant_selection,
)
from specson_experiments.protocol import PairedResult, paired_rounds, timed
from specson_experiments.results import (
    EXPERIMENT_PARTS,
    RESULT_FORMAT,
    remove_result,
    write_result,
)
from specson_experiments.sqlgen import (
    Api,
    dataset_schema_sql,
    jsonb_exists_expression,
    query_sql,
    restore_sql,
    statement_stem,
    storage_sql,
    table_names,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = REPO_ROOT / "scripts/specson_workloads.json"
DEFAULT_RESULTS = REPO_ROOT / "experiments/specson/results"
POSTGRES_UNSUPPORTED_NUL_ESCAPE = b"\\u0000"
POSTGRES_NUL_REPLACEMENT_ESCAPE = b"\\uFFFD"
ENCODE_DISPERSION_WARNING = 0.05
RESTORE_ROUNDS = 3
QUERY_ROUNDS = 10
QUERY_DISCARD_FIRST = 5
MIN_ENCODE_MAX_WAL_SIZE_MB = 32 * 1024
MIN_ENCODE_CHECKPOINT_TIMEOUT_SECONDS = 60 * 60


def import_psycopg():
    try:
        import psycopg
    except ImportError as error:
        raise RuntimeError("psycopg 3 is required for PostgreSQL execution") from error
    return psycopg


def execute_sql(cursor, sql: str) -> list[tuple[Any, ...]]:
    cursor.execute(sql)
    rows: list[tuple[Any, ...]] = []
    while True:
        if cursor.description is not None:
            rows = list(cursor.fetchall())
        if not cursor.nextset():
            return rows


def consume_rows(cursor, batch_size: int = 8192) -> dict[str, int]:
    rows = 0
    payload_bytes = 0
    while True:
        batch = cursor.fetchmany(batch_size)
        if not batch:
            break
        rows += len(batch)
        for record in batch:
            for value in record:
                if isinstance(value, str):
                    payload_bytes += len(value.encode())
                elif isinstance(value, (bytes, bytearray, memoryview)):
                    payload_bytes += len(value)
                elif value is not None:
                    payload_bytes += len(str(value).encode())
    return {"rows": rows, "payload_bytes": payload_bytes}


def raw_json_rows(paths: tuple[Path, ...]) -> Iterator[tuple[int, str]]:
    row_id = 0
    for path in paths:
        with path.open("rb") as source:
            for line_number, raw_line in enumerate(source, 1):
                line = raw_line.rstrip(b"\r\n")
                if not line:
                    continue
                line = line.replace(
                    POSTGRES_UNSUPPORTED_NUL_ESCAPE,
                    POSTGRES_NUL_REPLACEMENT_ESCAPE,
                )
                try:
                    json.loads(line)
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise RuntimeError(f"{path}:{line_number}: invalid JSON: {error}") from error
                row_id += 1
                yield row_id, line.decode("utf-8")


def pin_backend_if_requested(backend_pid: int, cpu: int | None) -> None:
    if cpu is None:
        return
    setter = getattr(os, "sched_setaffinity", None)
    if setter is None:
        raise RuntimeError("this platform does not expose process affinity through Python")
    try:
        setter(backend_pid, {cpu})
    except PermissionError:
        subprocess.run(
            ["sudo", "-n", "taskset", "-pc", str(cpu), str(backend_pid)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )


def configure_session(cursor) -> None:
    cursor.execute("SET max_parallel_workers=0")
    cursor.execute("SET max_parallel_workers_per_gather=0")
    cursor.execute("SET max_parallel_maintenance_workers=0")
    cursor.execute("SET default_toast_compression=lz4")
    cursor.execute("SET plan_cache_mode=auto")


def jit_configuration(cursor) -> dict[str, Any]:
    cursor.execute(
        "SELECT pg_jit_available(), current_setting('jit'), "
        "current_setting('jit_above_cost')::double precision, "
        "current_setting('jit_inline_above_cost')::double precision, "
        "current_setting('jit_optimize_above_cost')::double precision"
    )
    available, enabled, above, inline_above, optimize_above = cursor.fetchone()
    return {
        "available": bool(available),
        "enabled": str(enabled),
        "jit_above_cost": float(above),
        "jit_inline_above_cost": float(inline_above),
        "jit_optimize_above_cost": float(optimize_above),
    }


def prepared_plan_metadata(cursor, statement: str) -> dict[str, Any]:
    cursor.execute(f"EXPLAIN (FORMAT JSON) EXECUTE {statement}")
    document = cursor.fetchone()[0]
    if isinstance(document, str):
        document = json.loads(document)
    root = document[0]
    plan = root["Plan"]
    return {
        "total_cost": float(plan["Total Cost"]),
        "jit_planned": "JIT" in root,
        "jit": root.get("JIT"),
    }


def require_reproducible_encode_configuration(cursor) -> dict[str, Any]:
    cursor.execute(
        "SELECT name, setting::bigint, unit FROM pg_settings "
        "WHERE name IN ('max_wal_size', 'checkpoint_timeout')"
    )
    settings = {
        str(name): {"setting": int(setting), "unit": str(unit)}
        for name, setting, unit in cursor.fetchall()
    }
    max_wal_size_mb = settings["max_wal_size"]["setting"]
    checkpoint_timeout_seconds = settings["checkpoint_timeout"]["setting"]
    errors: list[str] = []
    if max_wal_size_mb < MIN_ENCODE_MAX_WAL_SIZE_MB:
        errors.append(
            f"max_wal_size is {max_wal_size_mb}MB, require at least "
            f"{MIN_ENCODE_MAX_WAL_SIZE_MB}MB"
        )
    if checkpoint_timeout_seconds < MIN_ENCODE_CHECKPOINT_TIMEOUT_SECONDS:
        errors.append(
            f"checkpoint_timeout is {checkpoint_timeout_seconds}s, require at least "
            f"{MIN_ENCODE_CHECKPOINT_TIMEOUT_SECONDS}s"
        )
    if errors:
        raise RuntimeError(
            "encode configuration is not reproducible: "
            + "; ".join(errors)
            + ". Configure PostgreSQL with max_wal_size='32GB' and "
            "checkpoint_timeout='1h', reload the configuration, and rerun encode"
        )
    return {
        "max_wal_size_mb": max_wal_size_mb,
        "checkpoint_timeout_seconds": checkpoint_timeout_seconds,
        "minimum_max_wal_size_mb": MIN_ENCODE_MAX_WAL_SIZE_MB,
        "minimum_checkpoint_timeout_seconds": MIN_ENCODE_CHECKPOINT_TIMEOUT_SECONDS,
        "timed_write_checkpoint_policy": "reject-on-overlap",
    }


def register_variant(
    cursor,
    dataset: Dataset,
    variant: str,
    api: Api,
    registered: set[str],
) -> None:
    if variant in registered:
        return
    execute_sql(cursor, dataset_schema_sql(dataset, variant, api))
    registered.add(variant)


def rebuild_raw_and_clear_encoded(
    cursor,
    dataset: Dataset,
    variants: tuple[str, ...],
) -> int:
    shared = table_names(dataset, variants[0])
    targets = [shared["raw"], shared["jsonb"]]
    targets.extend(table_names(dataset, variant)["specson"] for variant in variants)
    cursor.execute("TRUNCATE " + ", ".join(targets))
    with cursor.copy(f"COPY {shared['raw']} (row_id, json_text) FROM STDIN") as copy:
        for record in raw_json_rows(dataset.inputs):
            copy.write_row(record)
    cursor.execute(f"SELECT count(*) FROM {shared['raw']}")
    observed = int(cursor.fetchone()[0])
    if dataset.expected_rows is None:
        raise RuntimeError(
            f"{dataset.key}: expected row count is unknown; regenerate its manifest first"
        )
    if observed != dataset.expected_rows:
        raise RuntimeError(
            f"{dataset.key}: expected {dataset.expected_rows} raw rows, loaded {observed}"
        )
    cursor.execute(f"ANALYZE {shared['raw']}")
    return observed


def vacuum_encoded(
    cursor,
    dataset: Dataset,
    variants: tuple[str, ...],
) -> None:
    for variant in variants:
        table = table_names(dataset, variant)["specson"]
        cursor.execute(f"VACUUM (FREEZE, ANALYZE) {table}")
    shared_jsonb = table_names(dataset, variants[0])["jsonb"]
    cursor.execute(f"VACUUM (FREEZE, ANALYZE) {shared_jsonb}")


def prewarm_relations(cursor, roots: tuple[str, ...]) -> list[str]:
    relations: list[str] = []
    for table in roots:
        cursor.execute("SELECT pg_prewarm(%s::regclass)", (table,))
        relations.append(table)
        cursor.execute(
            "SELECT indexrelid::regclass::text FROM pg_index WHERE indrelid=%s::regclass",
            (table,),
        )
        for (index_name,) in cursor.fetchall():
            cursor.execute("SELECT pg_prewarm(%s::regclass)", (index_name,))
            relations.append(index_name)
        cursor.execute(
            "SELECT reltoastrelid::regclass::text FROM pg_class WHERE oid=%s::regclass",
            (table,),
        )
        toast = cursor.fetchone()[0]
        if toast != "-":
            cursor.execute("SELECT pg_prewarm(%s::regclass)", (toast,))
            relations.append(toast)
            cursor.execute(
                "SELECT indexrelid::regclass::text FROM pg_index WHERE indrelid=%s::regclass",
                (toast,),
            )
            for (index_name,) in cursor.fetchall():
                cursor.execute("SELECT pg_prewarm(%s::regclass)", (index_name,))
                relations.append(index_name)
    return relations


def prewarm_dataset(cursor, dataset: Dataset, variant: str) -> dict[str, Any]:
    tables = table_names(dataset, variant)
    return {
        "prewarmed": prewarm_relations(
            cursor, (tables["specson"], tables["jsonb"])
        )
    }


ENCODE_IO_FIELDS = (
    "reads",
    "read_bytes",
    "read_time",
    "writes",
    "write_bytes",
    "write_time",
    "writebacks",
    "writeback_time",
    "extends",
    "extend_bytes",
    "extend_time",
    "hits",
    "evictions",
    "reuses",
    "fsyncs",
    "fsync_time",
)


def encode_environment_snapshot(cursor) -> dict[str, int | float]:
    cursor.execute("SELECT pg_stat_force_next_flush()")
    cursor.execute(
        "SELECT num_timed, num_requested, num_done FROM pg_stat_checkpointer"
    )
    num_timed, num_requested, num_done = cursor.fetchone()
    cursor.execute(
        "SELECT wal_records, wal_fpi, wal_bytes::bigint, wal_buffers_full "
        "FROM pg_stat_wal"
    )
    wal_records, wal_fpi, wal_bytes, wal_buffers_full = cursor.fetchone()
    snapshot: dict[str, int | float] = {
        "checkpoints_timed": int(num_timed),
        "checkpoints_requested": int(num_requested),
        "checkpoints_done": int(num_done),
        "wal_records": int(wal_records),
        "wal_fpi": int(wal_fpi),
        "wal_bytes": int(wal_bytes),
        "wal_buffers_full": int(wal_buffers_full),
    }
    cursor.execute(
        "SELECT backend_type, object, context, "
        + ", ".join(ENCODE_IO_FIELDS)
        + " FROM pg_stat_io"
    )
    for row in cursor.fetchall():
        backend_type, object_name, context = (str(value) for value in row[:3])
        prefix = "io_" + "_".join(
            value.replace(" ", "_")
            for value in (backend_type, object_name, context)
        )
        for field, value in zip(ENCODE_IO_FIELDS, row[3:]):
            snapshot[f"{prefix}_{field}"] = float(value or 0)
    return snapshot


def snapshot_delta(
    before: dict[str, int | float],
    after: dict[str, int | float],
) -> dict[str, int | float]:
    delta = {
        key: after.get(key, 0) - before.get(key, 0)
        for key in before.keys() | after.keys()
    }
    return {key: value for key, value in delta.items() if value != 0}


def require_no_other_active_client(cursor) -> None:
    cursor.execute(
        "SELECT pid, left(query, 160) FROM pg_stat_activity "
        "WHERE datname=current_database() AND pid<>pg_backend_pid() "
        "AND backend_type='client backend' AND state<>'idle'"
    )
    active = cursor.fetchall()
    if active:
        raise RuntimeError(f"encode requires no other active PostgreSQL clients: {active}")


def encoded_table_state(cursor, dataset: Dataset, variant: str) -> dict[str, Any]:
    tables = table_names(dataset, variant)
    expected = dataset.expected_rows
    errors: list[str] = []
    state: dict[str, Any] = {"expected_rows": expected}
    if expected is None:
        errors.append("expected row count is unknown")
    for system in ("specson", "jsonb"):
        table = tables[system]
        cursor.execute("SELECT to_regclass(%s)", (table,))
        exists = cursor.fetchone()[0] is not None
        item: dict[str, Any] = {"table": table, "exists": exists}
        if exists:
            cursor.execute(
                "SELECT attstorage::text, attcompression::text FROM pg_attribute "
                "WHERE attrelid=%s::regclass AND attname='doc'",
                (table,),
            )
            storage_mode, compression = cursor.fetchone()
            item["storage_mode"] = str(storage_mode)
            item["compression"] = str(compression)
            if system == "specson" and storage_mode != "e":
                errors.append(
                    f"{table}.doc uses storage mode {storage_mode!r}, expected "
                    "EXTERNAL for the internal SpecSon LZ4 envelope"
                )
            if system == "jsonb" and (storage_mode != "x" or compression != "l"):
                errors.append(
                    f"{table}.doc uses storage/compression "
                    f"{storage_mode!r}/{compression!r}, expected EXTENDED/LZ4"
                )
            cursor.execute(f"SELECT count(*) FROM {table}")
            item["rows"] = int(cursor.fetchone()[0])
            if expected is not None and item["rows"] != expected:
                errors.append(f"{table} has {item['rows']} rows, expected {expected}")
        else:
            errors.append(f"{table} does not exist")
        state[system] = item
    if errors:
        raise RuntimeError(
            f"{dataset.number}/{dataset.name}/{variant}: encoded tables are not ready: "
            + "; ".join(errors)
            + ". Run the encode part first to rebuild both tables."
        )
    return state


def preflight_read_parts(cursor, dataset: Dataset, variants: tuple[str, ...]) -> dict[str, Any]:
    states: dict[str, Any] = {}
    errors: list[str] = []
    for variant in variants:
        try:
            states[variant] = encoded_table_state(cursor, dataset, variant)
        except RuntimeError as error:
            errors.append(str(error))
    if errors:
        raise RuntimeError("\n".join(errors))
    return states


def measurement_dispersion(samples: list[float]) -> dict[str, float]:
    minimum = min(samples)
    maximum = max(samples)
    median = statistics.median(samples)
    return {
        "minimum_ms": minimum,
        "maximum_ms": maximum,
        "median_ms": median,
        "maximum_over_minimum": maximum / minimum,
    }


def measure_encode_latin_square(
    cursor,
    dataset: Dataset,
    variants: tuple[str, ...],
) -> tuple[dict[str, dict[str, Any]], list[str], list[list[str]], list[str]]:
    shared = table_names(dataset, variants[0])
    systems = [f"specson:{variant}" for variant in variants] + ["jsonb"]
    conditioning_order = list(systems)
    orders = [systems[index:] + systems[:index] for index in range(len(systems))]
    records: dict[str, list[dict[str, Any]]] = {system: [] for system in systems}
    conditioning: dict[str, dict[str, Any]] = {}

    def insert(system: str) -> dict[str, int]:
        if system == "jsonb":
            cursor.execute(
                f"INSERT INTO {shared['jsonb']} (row_id, doc) "
                f"SELECT row_id, json_text::jsonb FROM {shared['raw']}"
            )
            return {"rows": cursor.rowcount}
        variant = system.split(":", 1)[1]
        table = table_names(dataset, variant)["specson"]
        cursor.execute("SELECT specson_encode_begin(%s)", (dataset.schema_id(variant),))
        try:
            cursor.execute(
                f"INSERT INTO {table} (row_id, doc) "
                f"SELECT row_id, specson_encode(json_text) FROM {shared['raw']}"
            )
            rows = cursor.rowcount
        finally:
            cursor.execute("SELECT specson_encode_end()")
        return {"rows": rows}

    def target(system: str) -> str:
        if system == "jsonb":
            return shared["jsonb"]
        return table_names(dataset, system.split(":", 1)[1])["specson"]

    def run_sample(
        phase: str,
        round_index: int,
        position: int,
        system: str,
    ) -> dict[str, Any]:
        require_no_other_active_client(cursor)
        cursor.execute(f"TRUNCATE {target(system)}")
        cursor.execute("CHECKPOINT")
        prewarm_relations(cursor, (shared["raw"],))
        before = encode_environment_snapshot(cursor)
        sample = timed(lambda: insert(system))
        after = encode_environment_snapshot(cursor)
        environment = snapshot_delta(before, after)
        if phase == "measured" and any(
            environment.get(key, 0) != 0
            for key in (
                "checkpoints_timed",
                "checkpoints_requested",
                "checkpoints_done",
            )
        ):
            raise RuntimeError(
                f"{dataset.key}/{system}/{phase}-round-{round_index}: a checkpoint "
                "overlapped the timed encode write; increase max_wal_size or "
                "checkpoint_timeout and rerun encode"
            )
        if sample.observation != {"rows": dataset.expected_rows}:
            raise RuntimeError(
                f"{dataset.key}/{system}/{phase}-round-{round_index}: "
                "encode row count changed"
            )
        return {
            "phase": phase,
            "round": round_index,
            "position": position,
            "elapsed_ms": sample.elapsed_ms,
            "observation": sample.observation,
            "environment_delta": environment,
        }

    for position, system in enumerate(conditioning_order, 1):
        conditioning[system] = run_sample(
            "conditioning",
            1,
            position,
            system,
        )

    for round_index, order in enumerate(orders, 1):
        for position, system in enumerate(order, 1):
            records[system].append(
                run_sample("measured", round_index, position, system)
            )

    jsonb_records = records["jsonb"]
    jsonb_times = [float(record["elapsed_ms"]) for record in jsonb_records]
    jsonb_median = statistics.median(jsonb_times)
    jsonb_dispersion = measurement_dispersion(jsonb_times)
    warnings: list[str] = []
    if jsonb_dispersion["maximum_over_minimum"] > 1 + ENCODE_DISPERSION_WARNING:
        warnings.append(
            f"{dataset.key}/jsonb encode dispersion is "
            f"{jsonb_dispersion['maximum_over_minimum']:.4f}x (>1.05x)"
        )

    measurements: dict[str, dict[str, Any]] = {}
    for variant in variants:
        specson_records = records[f"specson:{variant}"]
        specson_times = [float(record["elapsed_ms"]) for record in specson_records]
        specson_median = statistics.median(specson_times)
        specson_dispersion = measurement_dispersion(specson_times)
        if specson_dispersion["maximum_over_minimum"] > 1 + ENCODE_DISPERSION_WARNING:
            warnings.append(
                f"{dataset.key}/{variant}/specson encode dispersion is "
                f"{specson_dispersion['maximum_over_minimum']:.4f}x (>1.05x)"
            )
        measurements[variant] = {
            "rounds": len(orders),
            "discard_first": 0,
            "specson_all_ms": specson_times,
            "jsonb_all_ms": jsonb_times,
            "specson_retained_ms": specson_times,
            "jsonb_retained_ms": jsonb_times,
            "specson_median_ms": specson_median,
            "jsonb_median_ms": jsonb_median,
            "speedup": jsonb_median / specson_median,
            "specson_observations": [record["observation"] for record in specson_records],
            "jsonb_observations": [record["observation"] for record in jsonb_records],
            "sample_positions": {
                "specson": [
                    {"round": record["round"], "position": record["position"]}
                    for record in specson_records
                ],
                "jsonb": [
                    {"round": record["round"], "position": record["position"]}
                    for record in jsonb_records
                ],
            },
            "dispersion": {
                "specson": specson_dispersion,
                "jsonb": jsonb_dispersion,
            },
            "environment_deltas": {
                "specson": [record["environment_delta"] for record in specson_records],
                "jsonb": [record["environment_delta"] for record in jsonb_records],
            },
            "conditioning": {
                "specson": conditioning[f"specson:{variant}"],
                "jsonb": conditioning["jsonb"],
            },
        }
    return measurements, conditioning_order, orders, warnings


def measure_storage(cursor, dataset: Dataset, variant: str) -> list[dict[str, Any]]:
    rows = execute_sql(cursor, storage_sql(dataset, variant))
    return [
        {
            "system": str(system),
            "rows": int(row_count),
            "datum_bytes": int(datum_bytes),
            "heap_bytes": int(heap_bytes),
            "pg_table_size_bytes": int(pg_table_size_bytes),
            "index_bytes": int(index_bytes),
            "total_relation_bytes": int(total_relation_bytes),
        }
        for (
            system,
            row_count,
            datum_bytes,
            heap_bytes,
            pg_table_size_bytes,
            index_bytes,
            total_relation_bytes,
        ) in rows
    ]


def query_selected(dataset: Dataset, query_id: str, operation: str, selectors: str) -> bool:
    if not selectors or selectors == "all":
        return True
    identity = f"{dataset.key}/{query_id}/{operation}"
    return any(
        fnmatch.fnmatchcase(query_id, pattern.strip())
        or fnmatch.fnmatchcase(identity, pattern.strip())
        for pattern in selectors.split(",")
        if pattern.strip()
    )


def jsonb_exists_match_count(cursor, dataset: Dataset, variant: str, query) -> int:
    table = table_names(dataset, variant)["jsonb"]
    cursor.execute(
        f"SELECT count(*) FROM {table} WHERE {jsonb_exists_expression(query)}"
    )
    matched = int(cursor.fetchone()[0])
    expected = dataset.expected_rows
    if expected is None or matched <= 0 or matched >= expected:
        raise RuntimeError(
            f"{dataset.key}/{query.id}/{variant}: Exists selectivity must satisfy "
            f"0 < matched_rows < {expected}; observed {matched}. To ensure fair and "
            "transparent results, please change the JSONPath constant before running the "
            "query part."
        )
    return matched


def validate_query_measurement(payload: dict[str, Any]) -> None:
    specson = payload["specson_observations"]
    jsonb = payload["jsonb_observations"]
    if len({json.dumps(item, sort_keys=True) for item in specson}) != 1:
        raise RuntimeError("SpecSon observable row/byte count changed across query rounds")
    if len({json.dumps(item, sort_keys=True) for item in jsonb}) != 1:
        raise RuntimeError("JSONB observable row/byte count changed across query rounds")
    if specson[0] != jsonb[0]:
        raise RuntimeError("paired query systems returned different observable results")


def measure_query_table_major(
    cursor,
    dataset: Dataset,
    variant: str,
    selected: list[tuple[Any, str]],
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, Any]]:
    samples: dict[tuple[str, str], dict[str, list[Any]]] = {
        (query.id, operation): {"specson": [], "jsonb": []}
        for query, operation in selected
    }
    prewarm: dict[str, Any] = {}
    for system, prefix in (("specson", "sp"), ("jsonb", "jb")):
        table = table_names(dataset, variant)[system]
        prewarm[system] = {"prewarmed": prewarm_relations(cursor, (table,))}
        for _round in range(QUERY_ROUNDS):
            for query, operation in selected:
                name = statement_stem(dataset, query, operation, variant)

                def run(name: str = name, prefix: str = prefix) -> dict[str, int]:
                    cursor.execute(f"EXECUTE vldb_{prefix}_{name}")
                    return consume_rows(cursor)

                samples[(query.id, operation)][system].append(timed(run))

    measurements: dict[tuple[str, str], dict[str, Any]] = {}
    for identity, system_samples in samples.items():
        payload = PairedResult(
            specson=tuple(system_samples["specson"]),
            jsonb=tuple(system_samples["jsonb"]),
            discard_first=QUERY_DISCARD_FIRST,
        ).as_dict()
        validate_query_measurement(payload)
        measurements[identity] = payload
    return measurements, prewarm


def measure_restore(cursor, dataset: Dataset, variant: str) -> dict[str, Any]:
    stem = dataset.key.replace("-", "_") + "_" + variant

    def run(prefix: str) -> dict[str, int]:
        cursor.execute(f"EXECUTE vldb_restore_{prefix}_{stem}")
        return consume_rows(cursor)

    payload = paired_rounds(
        lambda: run("sp"),
        lambda: run("jb"),
        rounds=RESTORE_ROUNDS,
        discard_first=0,
    ).as_dict()
    specson_rows = {item["rows"] for item in payload["specson_observations"]}
    jsonb_rows = {item["rows"] for item in payload["jsonb_observations"]}
    if specson_rows != {dataset.expected_rows} or jsonb_rows != {dataset.expected_rows}:
        raise RuntimeError(f"{dataset.key}/{variant}: restore row count changed or differs")
    return payload


def dataset_identity(dataset: Dataset) -> dict[str, Any]:
    return {
        "id": dataset.number,
        "name": dataset.name,
        "key": dataset.key,
        "label": dataset.label,
        "kind": dataset.kind,
        "expected_rows": dataset.expected_rows,
        "family": dataset.family,
        "point": dataset.point,
    }


def result_base(dataset: Dataset, part: str, run: dict[str, Any]) -> dict[str, Any]:
    return {
        "format": RESULT_FORMAT,
        "part": part,
        "ratio_definition": "jsonb/specson",
        "dataset": dataset_identity(dataset),
        "run": run,
    }


def run_encode_part(
    cursor,
    dataset: Dataset,
    variants: tuple[str, ...],
    api: Api,
    run: dict[str, Any],
    registered: set[str],
) -> dict[str, Any]:
    result = result_base(dataset, "encode", run)
    result["capacity_ratio_definition"] = "specson/jsonb"
    result["postgresql_encode_configuration"] = (
        require_reproducible_encode_configuration(cursor)
    )
    result["variants"] = {}
    for variant in variants:
        register_variant(cursor, dataset, variant, api, registered)
    loaded_rows = rebuild_raw_and_clear_encoded(cursor, dataset, variants)
    cursor.execute(
        "SELECT current_setting('track_io_timing'), "
        "current_setting('track_wal_io_timing')"
    )
    original_track_io, original_track_wal = (str(value) for value in cursor.fetchone())
    cursor.execute("SET track_io_timing=on")
    cursor.execute("SET track_wal_io_timing=on")
    try:
        measurements, conditioning_order, orders, warnings = measure_encode_latin_square(
            cursor,
            dataset,
            variants,
        )
    finally:
        cursor.execute("SELECT set_config('track_io_timing', %s, false)", (original_track_io,))
        cursor.execute(
            "SELECT set_config('track_wal_io_timing', %s, false)",
            (original_track_wal,),
        )
    vacuum_encoded(cursor, dataset, variants)
    result["protocol"] = {
        "rounds": len(orders),
        "discard_first": 0,
        "ordering": "latin-square",
        "conditioning_rounds": 1,
        "conditioning_order": conditioning_order,
        "conditioning_recorded": True,
        "conditioning_included_in_median": False,
        "round_orders": orders,
        "shared_jsonb_baseline": True,
        "source_scan": "unsorted sequential scan",
        "dispersion_warning_threshold": 1 + ENCODE_DISPERSION_WARNING,
        "dispersion_policy": "warn-only",
        "io_timing": "session-enabled-during-measurement",
    }
    result["warnings"] = warnings
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr, flush=True)
    for variant in variants:
        measurement = measurements[variant]
        storage = measure_storage(cursor, dataset, variant)
        systems = {item["system"]: item for item in storage}
        result["variants"][variant] = {
            "raw_rows": loaded_rows,
            "measurement": measurement,
            "storage": storage,
            "capacity_ratio": {
                "definition": "specson/jsonb",
                "datum": systems["specson"]["datum_bytes"]
                / systems["jsonb"]["datum_bytes"],
                "heap": systems["specson"]["heap_bytes"]
                / systems["jsonb"]["heap_bytes"],
                "pg_table_size": systems["specson"]["pg_table_size_bytes"]
                / systems["jsonb"]["pg_table_size_bytes"],
                "indexes": systems["specson"]["index_bytes"]
                / systems["jsonb"]["index_bytes"],
                "total_relation": systems["specson"]["total_relation_bytes"]
                / systems["jsonb"]["total_relation_bytes"],
            },
        }
    return result


def run_query_part(
    cursor,
    dataset: Dataset,
    variants: tuple[str, ...],
    selectors: str,
    api: Api,
    run: dict[str, Any],
    registered: set[str],
) -> dict[str, Any]:
    table_state = preflight_read_parts(cursor, dataset, variants)
    selected = [
        (query, operation)
        for query in dataset.queries
        for operation in query.operations
        if query_selected(dataset, query.id, operation, selectors)
    ]
    if not selected:
        raise RuntimeError(f"{dataset.number}/{dataset.name}: query selector matched nothing")
    result = result_base(dataset, "query", run)
    result["protocol"] = {
        "rounds": QUERY_ROUNDS,
        "discard_first": QUERY_DISCARD_FIRST,
        "execution_order": "table-major",
        "table_order": ["specson", "jsonb"],
        "round_order_within_table": [
            f"{query.id}/{operation}" for query, operation in selected
        ],
    }
    result["table_state"] = table_state
    result["jit_configuration"] = jit_configuration(cursor)
    result["queries"] = []
    for variant in variants:
        register_variant(cursor, dataset, variant, api, registered)
        prepared: list[dict[str, Any]] = []
        for query, operation in selected:
            matched_rows = (
                jsonb_exists_match_count(cursor, dataset, variant, query)
                if operation == "exists"
                else None
            )
            rows = execute_sql(
                cursor,
                query_sql(
                    dataset,
                    variant,
                    query,
                    operation,
                    api,
                ),
            )
            if not rows or int(rows[-1][0]) != 0:
                mismatch = None if not rows else int(rows[-1][0])
                raise RuntimeError(
                    f"{dataset.key}/{query.id}/{operation}/{variant}: "
                    f"correctness mismatch_rows={mismatch}"
                )
            prepared.append({
                "query": query,
                "operation": operation,
                "matched_rows": matched_rows,
                "plans": {
                    "specson": prepared_plan_metadata(
                        cursor, f"vldb_sp_{statement_stem(dataset, query, operation, variant)}"
                    ),
                    "jsonb": prepared_plan_metadata(
                        cursor, f"vldb_jb_{statement_stem(dataset, query, operation, variant)}"
                    ),
                },
            })
        measurements, prewarm = measure_query_table_major(
            cursor, dataset, variant, selected
        )
        for item in prepared:
            query = item["query"]
            operation = item["operation"]
            rq = f"rq2-{operation}" if dataset.kind == "real" else FAMILY_RQ[dataset.family or ""]
            result["queries"].append({
                "unit": f"{rq}__{dataset.key}__{query.id}__{operation}__{variant}",
                "query_id": query.id,
                "operation": operation,
                "jsonpath": query.jsonpath,
                "variant": variant,
                "matched_rows": item["matched_rows"],
                "plans": item["plans"],
                "prewarm": prewarm,
                "measurement": measurements[(query.id, operation)],
            })
    return result


def run_restore_part(
    cursor,
    dataset: Dataset,
    variants: tuple[str, ...],
    api: Api,
    run: dict[str, Any],
    registered: set[str],
) -> dict[str, Any]:
    table_state = preflight_read_parts(cursor, dataset, variants)
    result = result_base(dataset, "restore", run)
    result["protocol"] = {"rounds": RESTORE_ROUNDS, "discard_first": 0}
    result["table_state"] = table_state
    result["variants"] = {}
    for variant in variants:
        register_variant(cursor, dataset, variant, api, registered)
        prewarm = prewarm_dataset(cursor, dataset, variant)
        execute_sql(cursor, restore_sql(dataset, variant, api))
        result["variants"][variant] = {
            "prewarm": prewarm,
            "measurement": measure_restore(cursor, dataset, variant),
        }
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-real-pg", action="store_true")
    parser.add_argument("--dataset", type=int, required=True, help="hard-coded dataset id")
    parser.add_argument(
        "--parts",
        required=True,
        help="encode,query,restore, or a comma-separated combination",
    )
    parser.add_argument("--schema-variants", default="all", help="integer,numeric,or all")
    parser.add_argument("--queries", default="all", help="query id or dataset/id/operation glob")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    parser.add_argument("--dataset-root")
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS))
    parser.add_argument(
        "--dsn",
        default="host=/var/run/postgresql port=5432 dbname=postgres",
    )
    parser.add_argument("--cpu", type=int, help="optional PostgreSQL backend CPU affinity")
    parser.add_argument("--run-id")
    parser.add_argument("--revision")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.allow_real_pg:
        print("error: refusing PostgreSQL access without --allow-real-pg", file=sys.stderr)
        return 2
    try:
        catalog = Catalog.load(
            Path(args.catalog).expanduser().resolve(),
            Path(args.dataset_root).expanduser().resolve() if args.dataset_root else None,
        )
        dataset = catalog.dataset_by_number(args.dataset)
        errors = catalog.validate_inputs(
            require_generated_data=True,
            dataset_keys=(dataset.key,),
        )
        if errors:
            raise ValueError("catalog validation failed:\n  " + "\n  ".join(errors))
        parts = parse_csv_selection(args.parts, EXPERIMENT_PARTS, "experiment parts")
        requested_variants = parse_schema_variant_selection(args.schema_variants)
        variants = (
            dataset.schema_variants
            if args.schema_variants == "all"
            else requested_variants
        )
        unsupported_variants = sorted(set(variants) - set(dataset.schema_variants))
        if unsupported_variants:
            raise ValueError(
                f"{dataset.key} does not admit schema variants: "
                + ", ".join(unsupported_variants)
            )
        results_dir = Path(args.results_dir).expanduser().resolve()
        run_id = args.run_id or (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + "-"
            + uuid.uuid4().hex[:8]
        )
        run = {
            "id": run_id,
            "revision": args.revision,
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "catalog_fingerprint": catalog.fingerprint,
            "cpu": args.cpu,
        }
        psycopg = import_psycopg()
        api = Api()
        with psycopg.connect(args.dsn, autocommit=True) as connection:
            pin_backend_if_requested(connection.info.backend_pid, args.cpu)
            with connection.cursor() as cursor:
                configure_session(cursor)
                registered: set[str] = set()
                for part in parts:
                    destination = remove_result(results_dir, dataset, part)
                    if part == "encode":
                        payload = run_encode_part(
                            cursor, dataset, variants, api, run, registered
                        )
                    elif part == "query":
                        payload = run_query_part(
                            cursor,
                            dataset,
                            variants,
                            args.queries,
                            api,
                            run,
                            registered,
                        )
                    else:
                        payload = run_restore_part(
                            cursor, dataset, variants, api, run, registered
                        )
                    payload["completed_utc"] = datetime.now(timezone.utc).isoformat()
                    write_result(destination, payload)
                    print(destination, flush=True)
        return 0
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
