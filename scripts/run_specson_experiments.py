#!/usr/bin/env python3
"""Plan, render, and generate the canonical SpecSON VLDB experiment workload.

Dataset directories are the source of truth. This entry point reads each
jsonpaths.yaml and uses each synthetic directory's existing schema and
generate.py; it never creates a second synthetic schema tree.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from specson_experiments.catalog import (
    ALL_RQS,
    ALL_STEPS,
    Catalog,
    build_units,
    canonical_sha256,
    parse_csv_selection,
    parse_schema_variant_selection,
    select_query_identities,
)
from specson_experiments.sqlgen import (
    Api,
    dataset_metadata,
    render_dataset,
    render_unit,
    unit_metadata,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = REPO_ROOT / "scripts/specson_workloads.json"
DEFAULT_OUTPUT = REPO_ROOT / "experiments/specson"


def resolved(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def ensure_output_is_safe(output: Path, dataset_root: Path) -> None:
    try:
        output.relative_to(dataset_root)
    except ValueError:
        return
    raise ValueError(f"output root must not be inside the dataset tree: {dataset_root}")


def common_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    parser.add_argument("--dataset-root")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--rqs", default="all", help="comma-separated RQ modules")
    parser.add_argument("--datasets", default="all", help="comma-separated hard-coded dataset ids")
    parser.add_argument(
        "--schema-variants",
        default="all",
        help="integer,numeric, or all",
    )
    parser.add_argument(
        "--queries",
        default="all",
        help="query ID or dataset/query/operation glob, for example O-* or openalex/O-9/count",
    )
    parser.add_argument("--steps", default="all", help="schema,load,correctness,warm,measure")
    parser.add_argument(
        "--synthetic-points",
        help="comma-separated point or directory globs, for example 1,4,2x10000",
    )


def load_selection(args: argparse.Namespace):
    catalog = Catalog.load(
        resolved(args.catalog),
        resolved(args.dataset_root) if args.dataset_root else None,
    )
    errors = catalog.validate_inputs(require_generated_data=False)
    if errors:
        raise ValueError("catalog validation failed:\n  " + "\n  ".join(errors))
    output = resolved(args.output_root)
    ensure_output_is_safe(output, catalog.root)
    rqs = parse_csv_selection(args.rqs, ALL_RQS, "RQ modules")
    if not args.datasets or args.datasets == "all":
        datasets = tuple(catalog.datasets)
    else:
        datasets = tuple(
            catalog.dataset_by_number(int(part.strip())).key
            for part in args.datasets.split(",")
            if part.strip()
        )
    variants = parse_schema_variant_selection(args.schema_variants)
    steps = parse_csv_selection(args.steps, ALL_STEPS, "steps")
    query_identities = select_query_identities(catalog, args.queries)
    points = (
        tuple(part.strip() for part in args.synthetic_points.split(",") if part.strip())
        if args.synthetic_points
        else None
    )
    units = build_units(
        catalog, rqs, datasets, variants, query_identities, steps, points
    )
    if not units:
        raise ValueError("selection contains no experiment units")
    return catalog, output, units


def api_from_args(args: argparse.Namespace) -> Api:
    return Api(
        type_name=args.sbjson_type,
        register_schema=args.register_schema,
        encode_begin=args.encode_begin,
        encode=args.encode,
        encode_end=args.encode_end,
        exists=args.exists_function,
        count=args.count_function,
        restore=args.restore_function,
    )


def add_api_args(parser: argparse.ArgumentParser) -> None:
    defaults = Api()
    parser.add_argument("--sbjson-type", default=defaults.type_name)
    parser.add_argument("--register-schema", default=defaults.register_schema)
    parser.add_argument("--encode-begin", default=defaults.encode_begin)
    parser.add_argument("--encode", default=defaults.encode)
    parser.add_argument("--encode-end", default=defaults.encode_end)
    parser.add_argument("--exists-function", default=defaults.exists)
    parser.add_argument("--count-function", default=defaults.count)
    parser.add_argument("--restore-function", default=defaults.restore)


def plan_payload(catalog: Catalog, units) -> dict:
    setup_keys = sorted({(unit.dataset, unit.variant) for unit in units})
    payload = {
        "format": "specson_experiment_plan_v3",
        "source_catalog": str(catalog.path),
        "catalog_fingerprint": catalog.fingerprint,
        "dataset_root": str(catalog.root),
        "dataset_root_policy": "read_only_except_explicit_generate_command",
        "seed": catalog.seed,
        "formal_protocol": {
            "encode": {"rounds": 1, "discard_first": 0},
            "query": {"rounds": 10, "discard_first": 5},
            "restore": {"rounds": 3, "discard_first": 0},
            "paired_orders": ["specson,jsonb", "jsonb,specson"],
            "parallel_query": False,
            "jit": False,
            "indexes": "none",
            "timed_output": "complete client-visible result rows",
        },
        "dataset_setups": [
            dataset_metadata(catalog, catalog.datasets[dataset], variant)
            for dataset, variant in setup_keys
        ],
        "units": [unit_metadata(catalog, unit) for unit in units],
    }
    payload["plan_fingerprint"] = canonical_sha256(payload)
    return payload


def command_list(args: argparse.Namespace) -> int:
    _, _, units = load_selection(args)
    for unit in units:
        print(unit.id)
    print(f"units={len(units)}", file=sys.stderr)
    return 0


def command_datasets(args: argparse.Namespace) -> int:
    catalog = Catalog.load(
        resolved(args.catalog),
        resolved(args.dataset_root) if args.dataset_root else None,
    )
    errors = catalog.validate_inputs(require_generated_data=False)
    if errors:
        raise ValueError("catalog validation failed:\n  " + "\n  ".join(errors))
    print("ID\tName\tKey\tKind\tRows")
    for dataset in catalog.ordered_datasets:
        rows = "unknown" if dataset.expected_rows is None else str(dataset.expected_rows)
        print(
            f"{dataset.number}\t{dataset.name}\t{dataset.key}\t"
            f"{dataset.kind}\t{rows}"
        )
    return 0


def command_plan(args: argparse.Namespace) -> int:
    catalog, output, units = load_selection(args)
    payload = plan_payload(catalog, units)
    if args.stdout:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    output.mkdir(parents=True, exist_ok=True)
    path = output / "plan.json"
    if path.exists() and not args.replace:
        raise FileExistsError(f"refusing to overwrite {path}; pass --replace")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(path)
    return 0


def command_render(args: argparse.Namespace) -> int:
    catalog, output, units = load_selection(args)
    api = api_from_args(args)
    plan_path = output / "plan.json"
    managed = (output / "datasets", output / "units")
    existing = [path for path in (plan_path, *managed) if path.exists()]
    if existing and not args.replace:
        raise FileExistsError(
            "refusing to overwrite rendered artifacts; pass --replace: "
            + ", ".join(str(path) for path in existing)
        )
    output.mkdir(parents=True, exist_ok=True)
    if args.replace:
        if plan_path.exists():
            plan_path.unlink()
        for directory in managed:
            if directory.exists():
                shutil.rmtree(directory)

    setup_keys = sorted({(unit.dataset, unit.variant) for unit in units})
    for dataset_key, variant in setup_keys:
        dataset = catalog.datasets[dataset_key]
        directory = output / "datasets" / dataset.key / variant
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "dataset.json").write_text(
            json.dumps(dataset_metadata(catalog, dataset, variant), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        for name, content in render_dataset(dataset, variant, api).items():
            (directory / name).write_text(content, encoding="utf-8")

    for unit in units:
        directory = output / "units" / unit.id
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "unit.json").write_text(
            json.dumps(unit_metadata(catalog, unit), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        for name, content in render_unit(catalog, unit, api).items():
            (directory / name).write_text(content, encoding="utf-8")

    plan_path.write_text(
        json.dumps(plan_payload(catalog, units), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"rendered {len(setup_keys)} dataset setups and {len(units)} units under {output}")
    return 0


def command_generate(args: argparse.Namespace) -> int:
    catalog, _, units = load_selection(args)
    datasets = {
        unit.dataset: catalog.datasets[unit.dataset]
        for unit in units
        if catalog.datasets[unit.dataset].kind == "synthetic"
    }
    if not datasets:
        raise ValueError("selection contains no synthetic datasets")
    for dataset in datasets.values():
        command = [sys.executable, str(dataset.generator)]
        if args.rows is not None:
            command.extend(["--rows", str(args.rows)])
        if args.workers is not None:
            command.extend(["--workers", str(args.workers)])
        if args.force:
            command.append("--force")
        subprocess.run(command, check=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    datasets_parser = subparsers.add_parser(
        "datasets", help="list hard-coded dataset ids and result names"
    )
    datasets_parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    datasets_parser.add_argument("--dataset-root")
    datasets_parser.set_defaults(func=command_datasets)

    list_parser = subparsers.add_parser("list", help="list selected independent units")
    common_parser(list_parser)
    list_parser.set_defaults(func=command_list)

    plan_parser = subparsers.add_parser("plan", help="write or print a run plan; no PG access")
    common_parser(plan_parser)
    plan_parser.add_argument("--stdout", action="store_true")
    plan_parser.add_argument("--replace", action="store_true")
    plan_parser.set_defaults(func=command_plan)

    render_parser = subparsers.add_parser("render", help="render dataset and unit SQL")
    common_parser(render_parser)
    add_api_args(render_parser)
    render_parser.add_argument("--replace", action="store_true")
    render_parser.set_defaults(func=command_render)

    generate_parser = subparsers.add_parser(
        "generate", help="run the selected schema directories' canonical generate.py"
    )
    common_parser(generate_parser)
    generate_parser.add_argument("--rows", type=int)
    generate_parser.add_argument("--workers", type=int)
    generate_parser.add_argument("--force", action="store_true")
    generate_parser.set_defaults(func=command_generate)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        return int(args.func(args))
    except (FileExistsError, KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
