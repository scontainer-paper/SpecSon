# SpecSon experiment harness

The workload catalog assigns every dataset a stable numeric ID and display
name. Schemas, JSONPaths, manifests, and source JSON remain under the external
dataset root; the catalog does not duplicate them.

Real-world datasets retain Integer and Numeric schema variants. Synthetic
experiments use only the Numeric variant. The array-size family is excluded;
array topology experiments use only the array-shape family. Depth retains only
1 and 8, width retains only 1 and 128, and every synthetic dataset contains
10,000 rows. Rank retains only 4, array shape retains only 1x2000 and 2000x1,
and normalized alternatives retain only 7. The external dataset root contains
only these nine synthetic dataset directories.

## PostgreSQL requirements

The full logged encode benchmark requires a checkpoint-free timed write. Use
these settings and reload PostgreSQL before running encode:

```sql
ALTER SYSTEM SET max_wal_size = '32GB';
ALTER SYSTEM SET checkpoint_timeout = '1h';
SELECT pg_reload_conf();
```

The executor checks both settings and refuses encode when either is smaller.
It issues a checkpoint and prewarms the raw heap, TOAST relation, and indexes
before each single timed write. Any checkpoint that overlaps the timed write
invalidates the part. The measured values and required minima are stored in
the encode result.

These settings are benchmark controls, not SpecSon runtime requirements.
Query and restore do not generate the corresponding bulk-write WAL, but all
parts should use one documented PostgreSQL configuration.

## Running one dataset

List the hard-coded dataset IDs:

```text
python3 scripts/run_specson_experiments.py datasets
```

Run any independent combination of encode, query, and restore for one ID:

```text
taskset -c 11 python3 scripts/execute_specson_pg.py \
  --allow-real-pg \
  --dataset 3 \
  --parts encode,query,restore \
  --schema-variants ordinary,numeric \
  --cpu 11
```

Encode truncates and rebuilds one shared raw table, one shared JSONB table, and
one SpecSon table per selected schema variant. Query and restore refuse to run
unless both encoded systems exist and contain the catalog row count.

With both schema variants selected, encode first runs one complete, explicitly
recorded conditioning round in `SpecSon Ordinary, SpecSon Numeric, JSONB`
order. Conditioning populates each exact target and exercises its backend,
JIT, relation, filesystem, and WAL path, but its times are excluded from the
reported medians. Encode then measures three Latin-square rounds: `SpecSon
Ordinary, SpecSon Numeric, JSONB`; `SpecSon Numeric, JSONB, SpecSon Ordinary`;
and `JSONB, SpecSon Ordinary, SpecSon Numeric`. The JSONB samples are one shared
baseline for both SpecSon variants. Each sample starts from a truncated target
table, an explicit checkpoint, and a prewarmed shared raw table. A
maximum/minimum time ratio above 1.05 is recorded and printed as a warning; it
does not reject the run or remove the final encoded data. Conditioning and raw
measured rounds, medians, sample positions, WAL/IO deltas, and warnings are
retained in the result JSON. A checkpoint overlapping a measured write remains
an invalid measurement.

Query runs ten rounds, discards the first five, and uses table-major order: one
physical table executes the complete ordered query list for every round before
execution switches tables. Restore runs three full-data rounds. Every timed
query returns its final aggregate without an `ORDER BY`.

SpecSon columns use PostgreSQL `STORAGE EXTERNAL`: the SpecSon envelope owns
block-group LZ4 compression, while PostgreSQL may move the datum to TOAST but
must not compress it again. JSONB columns use `STORAGE EXTENDED` with LZ4.
Query and restore preflight reject any other storage configuration.

Performance is reported as `JSONB/SpecSon`. Capacity is displayed as the
percentage `SpecSon/JSONB`, so a value below 100% means SpecSon uses less space.
The summary displays both `pg_table_size` (main table, TOAST, free-space map,
and visibility map, excluding indexes) and `sum(pg_column_size(doc))`. Result
JSON also retains main-fork, index, and total-relation sizes as diagnostics.

## Results

Each dataset part has one atomic result file under
`experiments/specson/results`. A failed or interrupted part has no current
result file. Print the complete ASCII summary with:

```text
python3 scripts/summarize_specson_results.py
```

Generate the three real-world dataset figures after every real-world dataset has both an
encode and restore result file:

```text
python3 scripts/plot_specson_results.py
```

The command takes no arguments and writes independent `encode.svg`,
`restore.svg`, and `storage.svg` figures under
`experiments/specson/figures/real-world`. It refuses to generate any figure when a
required real-world dataset result file or schema variant is missing. Encode and
restore plot the recorded SpecSon and JSONB times in seconds; storage plots the
recorded `pg_table_size` and column sizes in GiB. Colors identify systems, not
datasets or schema variants. System identity does not depend on color alone:
SpecSon bars are solid and JSONB bars use diagonal hatching, with dark outlines
on both for grayscale printing and color-vision accessibility.

An independent Matplotlib publication pipeline is also available. It keeps the
direct SVG command and its outputs intact:

```text
python3 -m pip install -r scripts/requirements-figures.txt
python3 scripts/plot_specson_publication_results.py
```

The zero-argument publication command follows the workflow described by
`Haojae/scipilot-figure-skill`: grouped bars at a zero baseline, final-size rendering,
the same Okabe-Ito color pair used by its bar recipe, JSONB hatch redundancy,
PDF/SVG/PNG export, grayscale
previews, and deterministic clipping/tick/glyph audits. Outputs are written to
`experiments/specson/figures/publication` without replacing the direct SVG set.

Generate the independent real-world query figure after all four query result
files exist:

```text
python3 scripts/plot_specson_query_results.py [OUTPUT_DIRECTORY]
```

The command creates separate wide Integer and Numeric figures covering every
recorded query. Each bar is the recorded `JSONB/SpecSon` speedup. Dataset groups
use coordinated green, yellow, blue, and purple hues, visible gaps, and direct
group labels below the bars; no detached legend is required. Each figure is
exported as PDF, SVG, PNG, and a grayscale preview, with one shared audit report.
The command refuses to run when any required query result or ordinary/numeric
matrix entry is missing.
