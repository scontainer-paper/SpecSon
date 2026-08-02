from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VARIANTS = ("ordinary", "numeric")
PUBLIC_SCHEMA_VARIANTS = ("integer", "numeric")
ALL_RQS = (
    "rq1-storage",
    "rq1-encode",
    "rq1-restore",
    "rq2-exists",
    "rq2-count",
    "rq3-depth",
    "rq3-width",
    "rq3-rank",
    "rq3-array-shape",
    "rq3-elemmatch",
    "rq3-alternative",
    "rq4-prepare",
)
ALL_STEPS = ("schema", "load", "correctness", "warm", "measure")

FAMILY_RQ = {
    "depth": "rq3-depth",
    "object-width": "rq3-width",
    "rank": "rq3-rank",
    "array-shape": "rq3-array-shape",
    "array-object-elemmatch": "rq3-elemmatch",
    "normalized-alternative": "rq3-alternative",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def natural_path_key(path: Path) -> tuple[Any, ...]:
    return tuple(
        int(part) if part.isdigit() else part
        for part in re.split(r"([0-9]+)", path.name)
    )


def _yaml_scalar(text: str, path: Path, line_number: int) -> str:
    try:
        value = ast.literal_eval(text)
    except (SyntaxError, ValueError) as error:
        raise ValueError(f"{path}:{line_number}: invalid quoted scalar") from error
    if not isinstance(value, str):
        raise ValueError(f"{path}:{line_number}: expected a quoted string")
    return value


@dataclass(frozen=True)
class Query:
    id: str
    dataset: str
    operations: tuple[str, ...]
    jsonpath: str
    order: int

    @property
    def identities(self) -> tuple[tuple[str, str, str], ...]:
        return tuple((self.dataset, self.id, operation) for operation in self.operations)


def load_query_yaml(path: Path, dataset: str) -> tuple[Query, ...]:
    """Read the deliberately small YAML subset used by dataset jsonpaths.yaml."""
    records: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or stripped == "queries:":
            continue
        if stripped.startswith("- id:"):
            if current is not None:
                records.append(current)
            current = {"id": stripped.split(":", 1)[1].strip(), "line": line_number}
            continue
        if current is None or ":" not in stripped:
            raise ValueError(f"{path}:{line_number}: malformed query YAML")
        key, value = (part.strip() for part in stripped.split(":", 1))
        if key == "operations":
            if not (value.startswith("[") and value.endswith("]")):
                raise ValueError(f"{path}:{line_number}: operations must be an inline list")
            current[key] = tuple(
                part.strip() for part in value[1:-1].split(",") if part.strip()
            )
        elif key == "path":
            current[key] = _yaml_scalar(value, path, line_number)
        else:
            raise ValueError(f"{path}:{line_number}: unsupported key {key!r}")
    if current is not None:
        records.append(current)
    queries: list[Query] = []
    for order, item in enumerate(records):
        query_id = str(item.get("id", "")).strip()
        operations = tuple(item.get("operations", ()))
        jsonpath = item.get("path")
        if not query_id or not operations or not isinstance(jsonpath, str):
            raise ValueError(f"{path}:{item.get('line', 1)}: incomplete query")
        unknown = sorted(set(operations) - {"exists", "count"})
        if unknown:
            raise ValueError(f"{path}: unsupported operations: {', '.join(unknown)}")
        if len(set(operations)) != len(operations):
            raise ValueError(f"{path}: duplicate operation in {query_id}")
        queries.append(Query(query_id, dataset, operations, jsonpath, order))
    if not queries:
        raise ValueError(f"{path}: no queries")
    return tuple(queries)


@dataclass(frozen=True)
class Dataset:
    number: int
    name: str
    key: str
    label: str
    kind: str
    schemas: dict[str, Path]
    schema_ids: dict[str, int]
    query_file: Path
    queries: tuple[Query, ...]
    inputs: tuple[Path, ...]
    expected_rows: int | None
    family: str | None = None
    point: str | None = None
    generator: Path | None = None
    manifest: Path | None = None
    metadata: dict[str, Any] | None = None

    def schema(self, variant: str) -> Path:
        return self.schemas[variant]

    @property
    def schema_variants(self) -> tuple[str, ...]:
        return tuple(self.schemas)

    def schema_id(self, variant: str) -> int:
        return self.schema_ids[variant]

    def query(self, query_id: str, operation: str) -> Query:
        for query in self.queries:
            if query.id == query_id and operation in query.operations:
                return query
        raise KeyError((self.key, query_id, operation))

    def result_filename(self, part: str) -> str:
        return f"{self.number:03d}-{self.name}-{part}.json"


@dataclass(frozen=True)
class ExperimentUnit:
    id: str
    rq: str
    dataset: str
    variant: str
    query: str | None
    operation: str
    point: str | None
    steps: tuple[str, ...]


@dataclass(frozen=True)
class Catalog:
    path: Path
    root: Path
    seed: int
    datasets: dict[str, Dataset]
    preparation_queries: tuple[tuple[str, str, str], ...]
    source_payload: dict[str, Any]

    @classmethod
    def load(cls, path: Path, dataset_root: Path | None = None) -> "Catalog":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("format") != "specson_experiment_workloads_v3":
            raise ValueError(f"unsupported workload catalog: {payload.get('format')!r}")
        root = (dataset_root or Path(payload["dataset_root"])).expanduser().resolve()
        datasets: dict[str, Dataset] = {}
        identities = payload["dataset_identities"]

        for key, item in payload["real_datasets"].items():
            schemas = {
                variant: (root / item["schemas"][variant]).resolve()
                for variant in SCHEMA_VARIANTS
            }
            query_file = (root / item["queries"]).resolve()
            inputs: list[Path] = []
            for pattern in item["inputs"]:
                matches = sorted(root.glob(pattern), key=natural_path_key)
                inputs.extend(match.resolve() for match in matches)
                if not matches:
                    inputs.append((root / pattern).resolve())
            datasets[key] = Dataset(
                number=int(identities[key]["id"]),
                name=str(identities[key]["name"]),
                key=key,
                label=item["label"],
                kind="real",
                schemas=schemas,
                schema_ids={variant: int(item["schema_ids"][variant]) for variant in SCHEMA_VARIANTS},
                query_file=query_file,
                queries=load_query_yaml(query_file, key),
                inputs=tuple(inputs),
                expected_rows=int(item["expected_rows"]),
            )

        synthetic_directories = sorted(
            path for path in root.glob("synthetic-*") if path.is_dir()
        )
        synthetic_variants = tuple(payload["synthetic_schema_variants"])
        if not synthetic_variants or not set(synthetic_variants) <= set(SCHEMA_VARIANTS):
            raise ValueError("synthetic_schema_variants must select known variants")
        schema_id_base = int(payload["synthetic_schema_id_base"])
        for ordinal, directory in enumerate(synthetic_directories):
            metadata_schema_path = directory / (
                "schema.json"
                if "ordinary" in synthetic_variants
                else "schema-numeric.json"
            )
            schema_payload = json.loads(
                metadata_schema_path.read_text(encoding="utf-8")
            )
            metadata_keys = [key for key in schema_payload if key.startswith("x-vldb-")]
            if len(metadata_keys) != 1 or not isinstance(schema_payload[metadata_keys[0]], dict):
                raise ValueError(
                    f"{metadata_schema_path}: expected one x-vldb-* metadata object"
                )
            metadata = dict(schema_payload[metadata_keys[0]])
            family = str(metadata.get("family", ""))
            if family not in FAMILY_RQ:
                raise ValueError(
                    f"{metadata_schema_path}: unsupported synthetic family {family!r}"
                )
            point = _synthetic_point(directory.name, family, metadata)
            manifest = directory / "manifest.json"
            expected_rows = None
            if manifest.is_file():
                manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
                expected_rows = int(manifest_payload["rows"])
            schema_id = schema_id_base + ordinal * len(SCHEMA_VARIANTS)
            query_file = directory / "jsonpaths.yaml"
            datasets[directory.name] = Dataset(
                number=int(identities[directory.name]["id"]),
                name=str(identities[directory.name]["name"]),
                key=directory.name,
                label=directory.name,
                kind="synthetic",
                schemas={
                    variant: (
                        directory / "schema.json"
                        if variant == "ordinary"
                        else directory / "schema-numeric.json"
                    )
                    for variant in synthetic_variants
                },
                schema_ids={
                    variant: schema_id + SCHEMA_VARIANTS.index(variant)
                    for variant in synthetic_variants
                },
                query_file=query_file,
                queries=load_query_yaml(query_file, directory.name),
                inputs=(directory / "data.jsonl",),
                expected_rows=expected_rows,
                family=family,
                point=point,
                generator=directory / "generate.py",
                manifest=manifest,
                metadata=metadata,
            )

        preparation_queries = tuple(
            (str(item["dataset"]), str(item["id"]), str(item["operation"]))
            for item in payload["preparation_queries"]
        )
        return cls(path.resolve(), root, int(payload["seed"]), datasets, preparation_queries, payload)

    @property
    def real_datasets(self) -> tuple[Dataset, ...]:
        return tuple(dataset for dataset in self.datasets.values() if dataset.kind == "real")

    @property
    def synthetic_datasets(self) -> tuple[Dataset, ...]:
        return tuple(dataset for dataset in self.datasets.values() if dataset.kind == "synthetic")

    @property
    def ordered_datasets(self) -> tuple[Dataset, ...]:
        return tuple(sorted(self.datasets.values(), key=lambda dataset: dataset.number))

    def dataset_by_number(self, number: int) -> Dataset:
        matches = [dataset for dataset in self.datasets.values() if dataset.number == number]
        if len(matches) != 1:
            raise KeyError(f"unknown dataset number: {number}")
        return matches[0]

    @property
    def fingerprint(self) -> str:
        sources: dict[str, Any] = {"catalog": file_sha256(self.path), "datasets": {}}
        for dataset in self.datasets.values():
            sources["datasets"][dataset.key] = {
                "schemas": {
                    variant: file_sha256(dataset.schema(variant))
                    for variant in dataset.schema_variants
                },
                "queries": file_sha256(dataset.query_file),
                "generator": file_sha256(dataset.generator) if dataset.generator else None,
            }
        return canonical_sha256(sources)

    def validate_inputs(
        self,
        *,
        require_generated_data: bool = False,
        dataset_keys: Iterable[str] | None = None,
    ) -> list[str]:
        errors: list[str] = []
        declared_identities = set(self.source_payload["dataset_identities"])
        discovered = set(self.datasets)
        if declared_identities != discovered:
            missing = sorted(discovered - declared_identities)
            stale = sorted(declared_identities - discovered)
            errors.append(
                f"dataset identities differ from discovered datasets; missing={missing}, stale={stale}"
            )
        numbers = [dataset.number for dataset in self.datasets.values()]
        names = [dataset.name for dataset in self.datasets.values()]
        if len(set(numbers)) != len(numbers):
            errors.append("dataset ids must be unique")
        if len(set(names)) != len(names):
            errors.append("dataset names must be unique")
        for dataset in self.datasets.values():
            if dataset.number <= 0:
                errors.append(f"invalid dataset id for {dataset.key}: {dataset.number}")
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", dataset.name):
                errors.append(f"invalid dataset result name for {dataset.key}: {dataset.name!r}")
        selected = (
            tuple(self.datasets.values())
            if dataset_keys is None
            else tuple(self.datasets[key] for key in dataset_keys)
        )
        identities: list[tuple[str, str, str]] = []
        for dataset in selected:
            for variant in dataset.schema_variants:
                if not dataset.schema(variant).is_file():
                    errors.append(f"missing {variant} schema: {dataset.schema(variant)}")
            if not dataset.query_file.is_file():
                errors.append(f"missing query YAML: {dataset.query_file}")
            if dataset.generator and not dataset.generator.is_file():
                errors.append(f"missing generator: {dataset.generator}")
            if dataset.kind == "real" or require_generated_data:
                for input_path in dataset.inputs:
                    if not input_path.is_file():
                        errors.append(f"missing input: {input_path}")
            for query in dataset.queries:
                identities.extend(query.identities)
        duplicates = sorted({identity for identity in identities if identities.count(identity) > 1})
        if duplicates:
            errors.append("duplicate query operations: " + ", ".join("/".join(item) for item in duplicates))
        real_exists = sum(
            "exists" in query.operations
            for dataset in self.real_datasets
            for query in dataset.queries
        )
        real_count = sum(
            "count" in query.operations
            for dataset in self.real_datasets
            for query in dataset.queries
        )
        if (real_exists, real_count) != (22, 4):
            errors.append(f"expected 22 real Exists and 4 Count operations, found {real_exists} and {real_count}")
        expected_synthetic = int(self.source_payload["expected_synthetic_datasets"])
        if len(self.synthetic_datasets) != expected_synthetic:
            errors.append(
                f"expected {expected_synthetic} synthetic schema directories, "
                f"found {len(self.synthetic_datasets)}"
            )
        for identity in self.preparation_queries:
            try:
                self.query(*identity)
            except KeyError:
                errors.append(f"unknown preparation query: {'/'.join(identity)}")
        return errors

    def query(self, dataset: str, query_id: str, operation: str) -> Query:
        return self.datasets[dataset].query(query_id, operation)


def _synthetic_point(directory: str, family: str, metadata: dict[str, Any]) -> str:
    if family == "depth":
        return str(metadata["depth"])
    if family == "object-width":
        return str(metadata["declaredFields"])
    if family == "rank":
        return str(metadata["rank"])
    if family == "array-size":
        return str(metadata["length"])
    if family in {"array-shape", "array-object-elemmatch"}:
        return "x".join(str(value) for value in metadata["shape"])
    if family == "normalized-alternative":
        return str(metadata["normalizedNonNullBranches"])
    return directory


def parse_csv_selection(value: str | None, allowed: Iterable[str], label: str) -> tuple[str, ...]:
    allowed_values = tuple(allowed)
    if not value or value == "all":
        return allowed_values
    requested = tuple(part.strip() for part in value.split(",") if part.strip())
    unknown = sorted(set(requested) - set(allowed_values))
    if unknown:
        raise ValueError(f"unknown {label}: {', '.join(unknown)}")
    return requested


def parse_schema_variant_selection(value: str | None) -> tuple[str, ...]:
    selected = parse_csv_selection(value, PUBLIC_SCHEMA_VARIANTS, "schema variants")
    return tuple("ordinary" if variant == "integer" else variant for variant in selected)


def select_query_identities(catalog: Catalog, patterns: str | None) -> set[tuple[str, str, str]] | None:
    if not patterns or patterns == "all":
        return None
    all_identities = [
        identity
        for dataset in catalog.datasets.values()
        for query in dataset.queries
        for identity in query.identities
    ]
    selected: set[tuple[str, str, str]] = set()
    for pattern in (part.strip() for part in patterns.split(",") if part.strip()):
        matches = [
            identity
            for identity in all_identities
            if fnmatch.fnmatchcase(identity[1], pattern)
            or fnmatch.fnmatchcase("/".join(identity), pattern)
        ]
        if not matches:
            raise ValueError(f"query selector matched nothing: {pattern}")
        selected.update(matches)
    return selected


def _point_selected(dataset: Dataset, patterns: tuple[str, ...] | None) -> bool:
    if patterns is None:
        return True
    return any(
        fnmatch.fnmatchcase(dataset.point or "", pattern)
        or fnmatch.fnmatchcase(dataset.key, pattern)
        for pattern in patterns
    )


def build_units(
    catalog: Catalog,
    rqs: tuple[str, ...],
    datasets: tuple[str, ...],
    variants: tuple[str, ...],
    query_identities: set[tuple[str, str, str]] | None,
    steps: tuple[str, ...],
    synthetic_points: tuple[str, ...] | None,
) -> list[ExperimentUnit]:
    selected = set(datasets)
    units: list[ExperimentUnit] = []
    for rq in rqs:
        if rq.startswith("rq1-"):
            for dataset in catalog.real_datasets:
                if dataset.key not in selected:
                    continue
                for variant in variants:
                    units.append(ExperimentUnit(
                        f"{rq}__{dataset.key}__{variant}", rq, dataset.key, variant,
                        None, rq.removeprefix("rq1-"), None, steps,
                    ))
        elif rq in {"rq2-exists", "rq2-count"}:
            operation = rq.removeprefix("rq2-")
            for dataset in catalog.real_datasets:
                if dataset.key not in selected:
                    continue
                for query in dataset.queries:
                    identity = (dataset.key, query.id, operation)
                    if operation not in query.operations or (
                        query_identities is not None and identity not in query_identities
                    ):
                        continue
                    for variant in variants:
                        units.append(ExperimentUnit(
                            f"{rq}__{dataset.key}__{query.id}__{variant}", rq,
                            dataset.key, variant, query.id, operation, None, steps,
                        ))
        elif rq.startswith("rq3-"):
            for dataset in catalog.synthetic_datasets:
                if dataset.key not in selected or FAMILY_RQ[dataset.family or ""] != rq:
                    continue
                if not _point_selected(dataset, synthetic_points):
                    continue
                for variant in variants:
                    if variant not in dataset.schema_variants:
                        continue
                    units.append(ExperimentUnit(
                        f"{rq}__{dataset.key}__capacity__{variant}", rq, dataset.key,
                        variant, None, "capacity", dataset.point, steps,
                    ))
                    for query in dataset.queries:
                        for operation in query.operations:
                            identity = (dataset.key, query.id, operation)
                            if query_identities is not None and identity not in query_identities:
                                continue
                            units.append(ExperimentUnit(
                                f"{rq}__{dataset.key}__{query.id}__{operation}__{variant}",
                                rq, dataset.key, variant, query.id, operation,
                                dataset.point, steps,
                            ))
        elif rq == "rq4-prepare":
            if "ordinary" not in variants:
                continue
            for dataset_key, query_id, operation in catalog.preparation_queries:
                identity = (dataset_key, query_id, operation)
                if dataset_key not in selected or (
                    query_identities is not None and identity not in query_identities
                ):
                    continue
                units.append(ExperimentUnit(
                    f"{rq}__{dataset_key}__{query_id}", rq, dataset_key,
                    "ordinary", query_id, operation, None, steps,
                ))
        else:
            raise ValueError(f"unsupported RQ: {rq}")
    return units
