from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .catalog import Catalog, Dataset, ExperimentUnit, Query, file_sha256


@dataclass(frozen=True)
class Api:
    type_name: str = "specson"
    register_schema: str = "specson_register_schema"
    encode_begin: str = "specson_encode_begin"
    encode: str = "specson_encode"
    encode_end: str = "specson_encode_end"
    exists: str = "specson_query_exists"
    count: str = "specson_query_count"
    restore: str = "specson_restore"


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def ident(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"unsafe SQL identifier: {value!r}")
    return value


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def bounded_slug(value: str, limit: int = 48) -> str:
    result = slug(value)
    if len(result) <= limit:
        return result
    digest = hashlib.sha256(result.encode()).hexdigest()[:10]
    return result[: limit - len(digest) - 1] + "_" + digest


def table_names(dataset: Dataset, variant: str) -> dict[str, str]:
    dataset_stem = slug(dataset.key)
    variant_stem = slug(variant)
    return {
        "raw": f"vldb_eval.raw_{dataset_stem}",
        "specson": f"vldb_eval.specson_{dataset_stem}_{variant_stem}",
        "jsonb": f"vldb_eval.jsonb_{dataset_stem}",
    }


def statement_stem(dataset: Dataset, query: Query, operation: str, variant: str) -> str:
    return bounded_slug(f"{dataset.key}_{query.id}_{operation}_{variant}")


def session_sql() -> str:
    return """SET max_parallel_workers = 0;
SET max_parallel_workers_per_gather = 0;
SET plan_cache_mode = auto;
"""


def dataset_schema_sql(dataset: Dataset, variant: str, api: Api) -> str:
    tables = table_names(dataset, variant)
    schema_json = dataset.schema(variant).read_text(encoding="utf-8")
    return session_sql() + f"""
CREATE SCHEMA IF NOT EXISTS vldb_eval;
CREATE EXTENSION IF NOT EXISTS pg_prewarm;

CREATE TABLE IF NOT EXISTS {tables['raw']} (
    row_id bigint PRIMARY KEY,
    json_text text NOT NULL
);
CREATE TABLE IF NOT EXISTS {tables['specson']} (
    row_id bigint PRIMARY KEY,
    doc {ident(api.type_name)} NOT NULL
) WITH (fillfactor = 100);
CREATE TABLE IF NOT EXISTS {tables['jsonb']} (
    row_id bigint PRIMARY KEY,
    doc jsonb NOT NULL
) WITH (fillfactor = 100);

ALTER TABLE {tables['raw']} SET (
    autovacuum_enabled = false,
    toast.autovacuum_enabled = false
);
ALTER TABLE {tables['specson']} SET (
    autovacuum_enabled = false,
    toast.autovacuum_enabled = false
);
ALTER TABLE {tables['jsonb']} SET (
    autovacuum_enabled = false,
    toast.autovacuum_enabled = false
);

ALTER TABLE {tables['specson']} ALTER COLUMN doc SET STORAGE EXTERNAL;
ALTER TABLE {tables['specson']} ALTER COLUMN doc SET COMPRESSION default;
ALTER TABLE {tables['jsonb']} ALTER COLUMN doc SET STORAGE EXTENDED;
ALTER TABLE {tables['jsonb']} ALTER COLUMN doc SET COMPRESSION lz4;

SELECT {ident(api.register_schema)}(
    {dataset.schema_id(variant)},
    $specson_schema${schema_json}$specson_schema$
);
"""


def dataset_load_sql(dataset: Dataset, variant: str, api: Api) -> str:
    tables = table_names(dataset, variant)
    return session_sql() + f"""
SELECT {ident(api.encode_begin)}({dataset.schema_id(variant)});
INSERT INTO {tables['specson']} (row_id, doc)
SELECT row_id, {ident(api.encode)}(json_text)
FROM {tables['raw']};
SELECT {ident(api.encode_end)}();

INSERT INTO {tables['jsonb']} (row_id, doc)
SELECT row_id, json_text::jsonb
FROM {tables['raw']};
"""


def singular_path(jsonpath: str) -> list[str] | None:
    if not re.fullmatch(r"\$\.[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*", jsonpath):
        return None
    return jsonpath[2:].split(".")


def jsonb_exists_expression(query: Query) -> str:
    fields = singular_path(query.jsonpath)
    if fields is not None:
        path = "{" + ",".join(fields) + "}"
        return f"(doc #> {sql_literal(path)}) IS NOT NULL"
    return f"jsonb_path_exists(doc, {sql_literal(query.jsonpath)}::jsonpath)"


def jsonb_count_expression(query: Query) -> str:
    match = re.fullmatch(r"\$\.([A-Za-z0-9_.]+)\[\*\]", query.jsonpath)
    if match:
        path = "{" + ",".join(match.group(1).split(".")) + "}"
        value = f"doc #> {sql_literal(path)}"
        return (
            f"CASE WHEN jsonb_typeof({value}) = 'array' "
            f"THEN jsonb_array_length({value}) ELSE 0 END::bigint"
        )
    path = sql_literal(query.jsonpath)
    return f"(SELECT count(*) FROM jsonb_path_query(doc, {path}::jsonpath))"


def query_selects(
    dataset: Dataset, variant: str, query: Query, operation: str, api: Api
) -> tuple[str, str]:
    tables = table_names(dataset, variant)
    if operation == "exists":
        specson = (
            f"SELECT row_id FROM {tables['specson']} "
            f"WHERE {ident(api.exists)}({dataset.schema_id(variant)}, doc, "
            f"{sql_literal(query.jsonpath)})"
        )
        jsonb = (
            f"SELECT row_id FROM {tables['jsonb']} "
            f"WHERE {jsonb_exists_expression(query)}"
        )
    elif operation == "count":
        specson = (
            f"SELECT row_id, {ident(api.count)}({dataset.schema_id(variant)}, doc, "
            f"{sql_literal(query.jsonpath)}) AS match_count FROM {tables['specson']}"
        )
        jsonb = (
            f"SELECT row_id, {jsonb_count_expression(query)} AS match_count "
            f"FROM {tables['jsonb']}"
        )
    else:
        raise ValueError(f"unsupported query operation: {operation}")
    return specson, jsonb


def query_sql(
    dataset: Dataset,
    variant: str,
    query: Query,
    operation: str,
    api: Api,
) -> str:
    specson_select, jsonb_select = query_selects(dataset, variant, query, operation, api)
    if operation == "exists":
        timed_specson_select = (
            f"SELECT count(*)::bigint AS matching_rows FROM ({specson_select}) AS matches"
        )
        timed_jsonb_select = (
            f"SELECT count(*)::bigint AS matching_rows FROM ({jsonb_select}) AS matches"
        )
    else:
        timed_specson_select = (
            f"SELECT coalesce(sum(match_count), 0) AS total_matches "
            f"FROM ({specson_select}) AS matches"
        )
        timed_jsonb_select = (
            f"SELECT coalesce(sum(match_count), 0) AS total_matches "
            f"FROM ({jsonb_select}) AS matches"
        )
    name = statement_stem(dataset, query, operation, variant)
    return session_sql() + f"""
PREPARE vldb_sp_{name} AS
{timed_specson_select};

PREPARE vldb_jb_{name} AS
{timed_jsonb_select};

WITH specson_result AS ({specson_select}),
     jsonb_result AS ({jsonb_select}),
     mismatch AS (
       (TABLE specson_result EXCEPT ALL TABLE jsonb_result)
       UNION ALL
       (TABLE jsonb_result EXCEPT ALL TABLE specson_result)
     )
SELECT count(*) AS mismatch_rows FROM mismatch;
"""


def warm_sql(dataset: Dataset, variant: str) -> str:
    tables = table_names(dataset, variant)
    return session_sql() + f"""
SELECT pg_prewarm({sql_literal(tables['specson'])}::regclass);
SELECT pg_prewarm({sql_literal(tables['jsonb'])}::regclass);
SELECT count(*), sum(pg_column_size(doc)) FROM {tables['specson']};
SELECT count(*), sum(pg_column_size(doc)) FROM {tables['jsonb']};
"""


def storage_sql(dataset: Dataset, variant: str) -> str:
    tables = table_names(dataset, variant)
    return session_sql() + f"""
SELECT 'specson' AS system,
       count(*) AS rows,
       sum(pg_column_size(doc)) AS datum_bytes,
       pg_relation_size({sql_literal(tables['specson'])}) AS heap_bytes,
       pg_table_size({sql_literal(tables['specson'])}) AS pg_table_size_bytes,
       pg_indexes_size({sql_literal(tables['specson'])}) AS index_bytes,
       pg_total_relation_size({sql_literal(tables['specson'])}) AS total_relation_bytes
FROM {tables['specson']}
UNION ALL
SELECT 'jsonb', count(*), sum(pg_column_size(doc)),
       pg_relation_size({sql_literal(tables['jsonb'])}),
       pg_table_size({sql_literal(tables['jsonb'])}),
       pg_indexes_size({sql_literal(tables['jsonb'])}),
       pg_total_relation_size({sql_literal(tables['jsonb'])})
FROM {tables['jsonb']};
"""


def restore_sql(dataset: Dataset, variant: str, api: Api) -> str:
    tables = table_names(dataset, variant)
    stem = slug(f"{dataset.key}_{variant}")
    return session_sql() + f"""
PREPARE vldb_restore_sp_{stem} AS
SELECT {ident(api.restore)}(doc) FROM {tables['specson']};
PREPARE vldb_restore_jb_{stem} AS
SELECT doc::text FROM {tables['jsonb']};
"""


def rq4_sql(dataset: Dataset, query: Query, api: Api) -> str:
    tables = table_names(dataset, "ordinary")
    name = statement_stem(dataset, query, "exists", "ordinary")
    return session_sql() + f"""
PREPARE vldb_rq4_sp_{name}(bigint) AS
SELECT row_id FROM {tables['specson']}
WHERE row_id <= $1
  AND {ident(api.exists)}({dataset.schema_id('ordinary')}, doc, {sql_literal(query.jsonpath)});
PREPARE vldb_rq4_jb_{name}(bigint) AS
SELECT row_id FROM {tables['jsonb']}
WHERE row_id <= $1
  AND {jsonb_exists_expression(query)};
"""


def render_dataset(dataset: Dataset, variant: str, api: Api) -> dict[str, str]:
    return {
        "schema.sql": dataset_schema_sql(dataset, variant, api),
        "load.sql": dataset_load_sql(dataset, variant, api),
        "warm.sql": warm_sql(dataset, variant),
    }


def render_unit(catalog: Catalog, unit: ExperimentUnit, api: Api) -> dict[str, str]:
    dataset = catalog.datasets[unit.dataset]
    if unit.query is not None:
        query = dataset.query(unit.query, unit.operation)
        if unit.rq == "rq4-prepare":
            return {"measure.sql": rq4_sql(dataset, query, api)}
        return {
            "query.sql": query_sql(dataset, unit.variant, query, unit.operation, api)
        }
    if unit.operation in {"storage", "capacity"}:
        return {"measure.sql": storage_sql(dataset, unit.variant)}
    if unit.operation == "restore":
        return {"measure.sql": restore_sql(dataset, unit.variant, api)}
    if unit.operation == "encode":
        return {
            "README.txt": (
                "Encoder timing is driven by the executor so parsing, structural checks, "
                "encoding, and datum allocation share one boundary.\n"
            )
        }
    return {}


def _input_signatures(paths: tuple[Path, ...]) -> list[dict[str, Any]]:
    signatures: list[dict[str, Any]] = []
    for path in paths:
        item: dict[str, Any] = {"path": str(path), "exists": path.is_file()}
        if path.is_file():
            stat = path.stat()
            item.update({"bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns})
        signatures.append(item)
    return signatures


def dataset_metadata(catalog: Catalog, dataset: Dataset, variant: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "dataset_id": dataset.number,
        "dataset_name": dataset.name,
        "dataset": dataset.key,
        "label": dataset.label,
        "kind": dataset.kind,
        "variant": variant,
        "schema_id": dataset.schema_id(variant),
        "schema": str(dataset.schema(variant)),
        "schema_sha256": file_sha256(dataset.schema(variant)),
        "query_file": str(dataset.query_file),
        "query_file_sha256": file_sha256(dataset.query_file),
        "inputs": _input_signatures(dataset.inputs),
        "expected_rows": dataset.expected_rows,
        "family": dataset.family,
        "point": dataset.point,
    }
    if dataset.generator:
        result["generator"] = str(dataset.generator)
        result["generator_sha256"] = file_sha256(dataset.generator)
    if dataset.manifest and dataset.manifest.is_file():
        result["manifest"] = str(dataset.manifest)
        result["manifest_sha256"] = file_sha256(dataset.manifest)
    return result


def unit_metadata(catalog: Catalog, unit: ExperimentUnit) -> dict[str, Any]:
    dataset = catalog.datasets[unit.dataset]
    result: dict[str, Any] = {
        "id": unit.id,
        "rq": unit.rq,
        "dataset": unit.dataset,
        "dataset_id": dataset.number,
        "dataset_name": dataset.name,
        "variant": unit.variant,
        "query": unit.query,
        "operation": unit.operation,
        "point": unit.point,
        "steps": list(unit.steps),
        "formal_rounds": 10,
        "discard_first": 5,
        "paired_orders": ["specson,jsonb", "jsonb,specson"],
        "schema_id": dataset.schema_id(unit.variant),
        "schema_sha256": file_sha256(dataset.schema(unit.variant)),
        "query_file_sha256": file_sha256(dataset.query_file),
    }
    if unit.query:
        query = dataset.query(unit.query, unit.operation)
        result.update({
            "jsonpath": query.jsonpath,
            "query_order": query.order,
        })
    return result
