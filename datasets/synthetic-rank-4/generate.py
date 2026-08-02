#!/usr/bin/env python3
"""Generate deterministic wide-range floating-point synthetic JSONL."""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


DEFAULT_ROWS = 10_000
DEFAULT_WORKERS = 4
DEFAULT_SEED = 20_260_801
MISSING = object()
MASK64 = (1 << 64) - 1
BACKGROUND_LIMIT = 400_000_000_000.0
MATCH_THRESHOLD = 500_000_000_000.0
MATCH_FLOOR = 600_000_000_000.0
MATCH_SPAN = 300_000_000_000.0


@dataclass(frozen=True)
class RawNumeric:
    lexeme: str


_WORKER_SPEC: dict[str, Any] | None = None


def _positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return value


def _metadata(schema: dict[str, Any]) -> dict[str, Any]:
    keys = [key for key in schema if key.startswith("x-vldb-")]
    if len(keys) != 1 or not isinstance(schema[keys[0]], dict):
        raise SystemExit("schema must contain exactly one x-vldb-* object")
    return schema[keys[0]]


def _profile(row_index: int, seed: int) -> tuple[str, bool]:
    return "present", (row_index + seed) % 2 == 0


def _mix64(value: int) -> int:
    value = (value + 0x9E3779B97F4A7C15) & MASK64
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK64
    return value ^ (value >> 31)


def _fraction(seed: int, row_index: int, position: int, salt: int) -> float:
    key = (
        seed
        ^ ((row_index + 1) * 0xD6E8FEB86659FD93)
        ^ ((position + 1) * 0xA5A3564E27F8862B)
        ^ salt
    ) & MASK64
    return (_mix64(key) >> 11) * (1.0 / (1 << 53))


def _background_float(
    seed: int, row_index: int, position: int, salt: int = 0
) -> float:
    value = (2.0 * _fraction(seed, row_index, position, salt) - 1.0) * BACKGROUND_LIMIT
    return value if abs(value) >= 1.0 else value + 1.125


def _match_float(seed: int, row_index: int, position: int, salt: int = 0) -> float:
    return MATCH_FLOOR + _fraction(seed, row_index, position, salt) * MATCH_SPAN


def _negative_match_float(
    seed: int, row_index: int, position: int, salt: int = 0
) -> float:
    return -_match_float(seed, row_index, position, salt)


def _nested_next(depth: int, value: float) -> Any:
    result: Any = value
    for _ in range(depth - 1):
        result = {"next": result}
    return result


def _random_tensor(
    shape: tuple[int, ...],
    seed: int,
    row_index: int,
    salt: int,
    start: int = 0,
) -> Any:
    if len(shape) == 1:
        return [
            _background_float(seed, row_index, start + index, salt)
            for index in range(shape[0])
        ]
    stride = 1
    for extent in shape[1:]:
        stride *= extent
    return [
        _random_tensor(
            shape[1:], seed, row_index, salt, start + index * stride
        )
        for index in range(shape[0])
    ]


def _set_at(value: Any, position: tuple[int, ...], replacement: Any) -> None:
    current = value
    for index in position[:-1]:
        current = current[index]
    current[position[-1]] = replacement


def _rank_shape(rank: int) -> tuple[int, ...]:
    return {
        1: (1024,),
        2: (32, 32),
        3: (8, 8, 16),
        4: (4, 4, 8, 8),
    }[rank]


def _rank_points(rank: int) -> tuple[tuple[int, ...], ...]:
    return {
        1: ((0,), (512,), (1023,)),
        2: ((0, 0), (16, 0), (31, 31)),
        3: ((0, 0, 0), (4, 0, 0), (7, 7, 15)),
        4: ((0, 0, 0, 0), (2, 2, 2, 2), (3, 3, 7, 7)),
    }[rank]


def _alternative_value(
    kind: str, row_index: int, hit: bool, seed: int, position: int
) -> Any:
    if kind == "boolean":
        return bool(row_index & 1)
    if kind == "integer":
        return _background_float(seed, row_index, position, 0x101)
    if kind == "number":
        return _background_float(seed, row_index, position, 0x102)
    if kind == "numeric":
        value = _background_float(seed, row_index, position, 0x103)
        return RawNumeric(f"{value:.9f}")
    if kind == "string":
        return "scalar" if hit else "other"
    if kind == "object":
        return {
            "code": _background_float(seed, row_index, position, 0x104),
            "kind": "object",
            "value": f"value-{row_index}",
        }
    if kind == "array":
        return [
            _background_float(seed, row_index, position * 2, 0x105),
            _background_float(seed, row_index, position * 2 + 1, 0x105),
        ]
    raise ValueError(f"unsupported alternative kind: {kind}")


def _inventory(
    product: dict[str, Any],
    available: bool,
    seed: int,
    row_index: int,
    occurrence: int,
) -> None:
    product["price"] = _negative_match_float(
        seed, row_index, occurrence, 0x201
    )
    product["inventory"] = {"available": available}


def _object_array(
    metadata: dict[str, Any], row_index: int, hit: bool, seed: int
) -> Any:
    warehouses = int(metadata["warehouses"])
    aisles = int(metadata["aisles_per_warehouse"])
    products = int(metadata["products_per_aisle"])
    result = []
    for warehouse_index in range(warehouses):
        aisle_values = []
        for aisle_index in range(aisles):
            product_values = []
            for product_index in range(products):
                occurrence = (
                    warehouse_index * aisles * products
                    + aisle_index * products
                    + product_index
                    + row_index
                )
                product: dict[str, Any] = {
                    "price": _background_float(
                        seed, row_index, occurrence, 0x202
                    )
                }
                if occurrence % 2 == 0:
                    product["inventory"] = {"available": False}
                product_values.append(product)
            aisle_values.append({"category": "grocery", "products": product_values})
        result.append({"region": "EU", "aisles": aisle_values})

    if hit:
        for warehouse_index, aisle_index, product_index in (
            (0, 0, 0),
            (warehouses // 2, 0, 0),
            (warehouses - 1, aisles - 1, products - 1),
        ):
            warehouse = result[warehouse_index]
            warehouse["region"] = "APAC"
            aisle = warehouse["aisles"][aisle_index]
            aisle["category"] = "electronics"
            occurrence = (
                warehouse_index * aisles * products
                + aisle_index * products
                + product_index
            )
            _inventory(
                aisle["products"][product_index],
                True,
                seed,
                row_index,
                occurrence,
            )
    else:
        # Both halves of the predicate occur, but never under one warehouse.
        result[0]["region"] = "APAC"
        trap = result[1]["aisles"][0]
        trap["category"] = "electronics"
        _inventory(trap["products"][0], True, seed, row_index, products)
    return result


def _row_for(spec: dict[str, Any], row_index: int) -> dict[str, Any]:
    metadata = spec["metadata"]
    family = metadata["family"]
    seed = int(spec["seed"])
    state, hit = _profile(row_index, spec["seed"])
    document: dict[str, Any] = {
        "id": _background_float(seed, row_index, 0, 0x301)
    }
    if state == "missing":
        return document
    if state == "null":
        document["target"] = None
        return document

    if family == "depth":
        terminal = (
            _match_float(seed, row_index, 0, 0x302)
            if hit
            else _background_float(seed, row_index, 0, 0x302)
        )
        document["target"] = _nested_next(int(metadata["depth"]), terminal)
    elif family == "object-width":
        width = int(metadata["declaredFields"])
        document["target"] = {
            f"field_{index:03}": (
                _match_float(seed, row_index, index, 0x303)
                if hit and index == width // 2
                else _background_float(seed, row_index, index, 0x303)
            )
            for index in range(width)
        }
    elif family == "rank":
        rank = int(metadata["rank"])
        shape = _rank_shape(rank)
        tensor = _random_tensor(shape, seed, row_index, 0x304)
        if hit:
            for point in _rank_points(rank):
                linear = 0
                for coordinate, extent in zip(point, shape):
                    linear = linear * extent + coordinate
                _set_at(
                    tensor,
                    point,
                    _match_float(seed, row_index, linear, 0x304),
                )
        document["target"] = tensor
    elif family == "array-size":
        length = int(metadata["length"])
        values = [
            _background_float(seed, row_index, index, 0x305)
            for index in range(length)
        ]
        if hit:
            values[-1] = _match_float(seed, row_index, length - 1, 0x305)
        document["target"] = values
    elif family == "array-shape":
        outer, inner = (int(value) for value in metadata["shape"])
        matrix = [
            [
                _background_float(
                    seed, row_index, outer_index * inner + inner_index, 0x306
                )
                for inner_index in range(inner)
            ]
            for outer_index in range(outer)
        ]
        if hit:
            matrix[-1][-1] = _match_float(
                seed, row_index, outer * inner - 1, 0x306
            )
        document["target"] = matrix
    elif family == "normalized-alternative":
        document["target"] = [
            _alternative_value(kind, row_index, hit, seed, position)
            for position, kind in enumerate(metadata["kinds"])
        ]
    elif family == "array-object-elemmatch":
        document["target"] = _object_array(metadata, row_index, hit, seed)
    else:
        raise ValueError(f"unsupported synthetic family: {family}")
    return document


def _encode_row(document: dict[str, Any], row_index: int) -> str:
    replacements: dict[str, str] = {}

    def prepare(value: Any) -> Any:
        if isinstance(value, RawNumeric):
            marker = f"__RAW_NUMERIC_{row_index}_{len(replacements)}__"
            replacements[marker] = value.lexeme
            return marker
        if isinstance(value, list):
            return [prepare(item) for item in value]
        if isinstance(value, dict):
            return {name: prepare(child) for name, child in value.items()}
        return value

    text = json.dumps(prepare(document), ensure_ascii=False, separators=(",", ":"))
    for marker, lexeme in replacements.items():
        text = text.replace(json.dumps(marker), lexeme)
    return text


def _init_worker(spec: dict[str, Any]) -> None:
    global _WORKER_SPEC
    _WORKER_SPEC = spec


def _generate_batch(bounds: tuple[int, int]) -> bytes:
    if _WORKER_SPEC is None:
        raise RuntimeError("worker was not initialized")
    start, end = bounds
    lines = [
        _encode_row(_row_for(_WORKER_SPEC, row_index), row_index)
        for row_index in range(start, end)
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _ranges(rows: int, batch_rows: int) -> Iterator[tuple[int, int]]:
    for start in range(0, rows, batch_rows):
        yield start, min(rows, start + batch_rows)


def _terminal_count(metadata: dict[str, Any]) -> int:
    family = metadata["family"]
    if family == "object-width":
        return int(metadata["declaredFields"])
    if family == "rank":
        count = 1
        for extent in _rank_shape(int(metadata["rank"])):
            count *= extent
        return count
    if family == "array-size":
        return int(metadata["length"])
    if family == "array-shape":
        return int(metadata["leafCount"])
    if family == "array-object-elemmatch":
        return int(metadata["terminal_objects"])
    if family == "normalized-alternative":
        return len(metadata["kinds"])
    return 1


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=_positive_int, default=DEFAULT_ROWS)
    parser.add_argument("--workers", type=_positive_int, default=DEFAULT_WORKERS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--batch-rows",
        type=_positive_int,
        help="rows generated per worker task; chosen from schema size by default",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data.jsonl"),
        help="output JSONL path, relative to this schema directory by default",
    )
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    schema_directory = Path(__file__).resolve().parent
    schema_path = schema_directory / "schema-numeric.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    metadata = _metadata(schema)
    dataset_seed = int.from_bytes(
        hashlib.sha256(schema_directory.name.encode("utf-8")).digest()[:8],
        "little",
    )
    effective_seed = args.seed ^ dataset_seed
    output = args.output.expanduser()
    if not output.is_absolute():
        output = schema_directory / output
    manifest = output.with_name("manifest.json")
    if (output.exists() or manifest.exists()) and not args.force:
        raise SystemExit(f"{output} or {manifest} already exists; pass --force")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp.{os.getpid()}")
    workers = min(args.workers, args.rows)
    batch_rows = args.batch_rows or max(
        1, min(4096, 8192 // max(1, _terminal_count(metadata)))
    )
    spec = {"metadata": metadata, "seed": effective_seed}

    try:
        with temporary.open("wb", buffering=1024 * 1024) as stream:
            if workers == 1:
                _init_worker(spec)
                for bounds in _ranges(args.rows, batch_rows):
                    stream.write(_generate_batch(bounds))
            else:
                context = multiprocessing.get_context("spawn")
                with context.Pool(
                    processes=workers,
                    initializer=_init_worker,
                    initargs=(spec,),
                ) as pool:
                    for block in pool.imap(
                        _generate_batch,
                        _ranges(args.rows, batch_rows),
                        chunksize=1,
                    ):
                        stream.write(block)
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()

    manifest.write_text(
        json.dumps(
            {
                "dataset": schema_directory.name,
                "format": "specson-vldb-synthetic-data-v2",
                "generator": Path(__file__).name,
                "output": output.name,
                "rows": args.rows,
                "schemas": ["schema-numeric.json"],
                "seed": args.seed,
                "effective_seed": effective_seed,
                "workers": workers,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"{schema_directory.name}: {args.rows} rows -> {output}")


if __name__ == "__main__":
    main()
