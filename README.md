# SpecSon PostgreSQL experiment bundle

This directory contains the current SpecSon PostgreSQL release artifact, the
formal experiment harness, the experiment schemas and JSONPaths, and the four
canonical synthetic-data generators. The dataset files are distributed
separately: [download the complete dataset bundle from Google Drive](https://drive.google.com/file/d/1uap3LueGqBhA5iiS1uKOl4YxlU_f0sS6/view?usp=sharing).

## Bundle layout

```text
release/
  libpg_specson.so
  pg_specson.control
  pg_specson--0.1.0.sql
scripts/
  execute_specson_pg.py
  run_specson_experiments.py
  summarize_specson_results.py
  specson_workloads.json
  specson_experiments/
  plot_specson_*.py
datasets/
  github/
  openalex/
  yelp-business/
  yelp-review/
  synthetic-width-1/
  synthetic-rank-4/
  synthetic-array-shape-1x2000/
  synthetic-array-shape-2000x1/
```

The supplied shared library was built for PostgreSQL 18.4 and with native CPU
instructions. Install it only into a PostgreSQL installation with the same
major-version ABI on a compatible machine.

SpecSon currently supports Linux only, and the prebuilt extension in this
bundle is a Linux x86-64 binary. Windows and macOS binaries are not available
yet; we plan to provide them in future releases.

## Important safety and support limitations

> [!WARNING]
> This PostgreSQL extension is a research prototype, not production software.
> Do not install or run it in a PostgreSQL instance or cluster that contains
> valuable data. It may crash PostgreSQL, corrupt database state, or cause data
> loss. Use only an isolated, disposable experiment instance, with independent
> backups, at your own risk.
>
> We recommend experimenting by changing field names and literal values in the
> bundled test JSONPaths. Because this prototype is still rudimentary and its
> optimizer and executor are incomplete, JSONPaths with different structural
> shapes may not be optimized and may not execute at all. Many other operators
> and features such as regular-expression matching are not supported yet. We
> are actively developing a more complete extension whose JSONPath behavior
> fully conforms to PostgreSQL.

## Install the PostgreSQL extension

Set `PG_CONFIG` to the target PostgreSQL installation. The commands below copy
the library under the name expected by the extension metadata and install the
control and SQL files. They require permission to write into the PostgreSQL
installation directories.

```bash
cd ~/specson
export PG_CONFIG=/opt/postgresql-18.4-native/bin/pg_config

sudo install -m 755 release/libpg_specson.so \
  "$($PG_CONFIG --pkglibdir)/pg_specson.so"
sudo install -m 644 release/pg_specson.control \
  release/pg_specson--0.1.0.sql \
  "$($PG_CONFIG --sharedir)/extension/"
```

Restart PostgreSQL if the server has already loaded an older SpecSon library,
then create the extension in the experiment database:

```bash
psql -d postgres -c 'CREATE EXTENSION IF NOT EXISTS pg_specson;'
psql -d postgres -c \
  "SELECT extname, extversion FROM pg_extension WHERE extname = 'pg_specson';"
```

The experiment user must be able to create schemas, tables, and the
`pg_prewarm` extension in that database.

## Install Python dependencies

Python 3 and Psycopg 3 are required to run PostgreSQL experiments. Matplotlib
and Pillow are required only for the publication plotting scripts.

```bash
cd ~/specson
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install 'psycopg[binary]>=3'
python3 -m pip install -r scripts/requirements-figures.txt
```

## Prepare datasets

Download the complete dataset bundle, including the JSONL inputs and schemas,
from [Google Drive](https://drive.google.com/file/d/1uap3LueGqBhA5iiS1uKOl4YxlU_f0sS6/view?usp=sharing).
Extract it into the repository root so that the archive's `datasets/`
directory overlays `~/specson/datasets/`. For example, if your browser saved
the archive in `~/Downloads`:

```bash
tar --zstd -xf ~/Downloads/specson-test-datasets.tar.zst -C ~/specson
```

If the downloaded archive is elsewhere, replace the archive path in that
command. After extraction, the files will be under `~/specson/datasets/`.

After extraction, the real-world inputs must be present at these exact paths:

```text
datasets/yelp-review/yelp_academic_dataset_review.jsonl
datasets/yelp-business/yelp_academic_dataset_business.jsonl
datasets/github/2026-06-26-0.jsonl ... 2026-06-26-23.jsonl
datasets/openalex/2026-06-26-part-0000.jsonl
```

The catalog expects 6,990,280 Yelp Review rows, 150,346 Yelp Business rows,
3,795,000 GitHub rows, and 358,387 OpenAlex rows. Query and restore refuse to
run if either the SpecSon or JSONB table is missing or has the wrong row count.

To regenerate the retained synthetic datasets instead of using the bundled
JSONL files, use 10,000 rows and one worker:

```bash
cd ~/specson
for dataset in \
  synthetic-width-1 \
  synthetic-rank-4 \
  synthetic-array-shape-1x2000 \
  synthetic-array-shape-2000x1
do
  python3 "datasets/$dataset/generate.py" \
    --rows 10000 --workers 1 --force
done
```

Each generator writes `data.jsonl` and refreshes `manifest.json` in its own
dataset directory. Generation is deterministic for a fixed schema, seed, and
row count.

Available dataset IDs are:

| ID | Dataset | Variants |
|---:|---|---|
| 1 | Yelp Review | Integer, Numeric |
| 2 | Yelp Business | Integer, Numeric |
| 3 | GitHub Archive | Integer, Numeric |
| 4 | OpenAlex Works | Integer, Numeric |
| 201 | Synthetic Width 1 | Numeric |
| 304 | Synthetic Rank 4 | Numeric |
| 501 | Synthetic Array Shape 1x2000 | Numeric |
| 504 | Synthetic Array Shape 2000x1 | Numeric |

To inspect the catalog after placing the inputs:

```bash
python3 scripts/run_specson_experiments.py datasets
```

## Configure PostgreSQL for formal encode measurements

The formal encode runner rejects configurations that can checkpoint during a
timed bulk write. Configure these benchmark controls and reload PostgreSQL:

```sql
ALTER SYSTEM SET max_wal_size = '32GB';
ALTER SYSTEM SET checkpoint_timeout = '1h';
SELECT pg_reload_conf();
```

These settings are experiment controls, not SpecSon runtime requirements. Make
sure the PostgreSQL data directory has enough free space for the source,
SpecSon, JSONB, TOAST, and WAL data.

## Run the experiments

All examples below pin the client and PostgreSQL backend to one CPU and the
runner also disables PostgreSQL parallel workers. Replace the DSN and CPU with
values appropriate for the machine.

Encode must run first. It unconditionally clears and rebuilds the selected
dataset's raw, SpecSon, and JSONB tables. Storage measurements are recorded in
the encode result.

```bash
cd ~/specson
source .venv/bin/activate

taskset -c 11 python3 scripts/execute_specson_pg.py \
  --allow-real-pg \
  --dataset 3 \
  --parts encode \
  --schema-variants integer,numeric \
  --cpu 11 \
  --dsn 'host=/var/run/postgresql port=5432 user=YOUR_POSTGRES_USER dbname=postgres'
```

Run query and restore independently after a successful encode:

```bash
taskset -c 11 python3 scripts/execute_specson_pg.py \
  --allow-real-pg --dataset 3 --parts query \
  --schema-variants integer,numeric --cpu 11 \
  --dsn 'host=/var/run/postgresql port=5432 user=YOUR_POSTGRES_USER dbname=postgres'

taskset -c 11 python3 scripts/execute_specson_pg.py \
  --allow-real-pg --dataset 3 --parts restore \
  --schema-variants integer,numeric --cpu 11 \
  --dsn 'host=/var/run/postgresql port=5432 user=YOUR_POSTGRES_USER dbname=postgres'
```

For a synthetic dataset, select only the Numeric variant. For example:

```bash
taskset -c 11 python3 scripts/execute_specson_pg.py \
  --allow-real-pg --dataset 304 --parts encode,query,restore \
  --schema-variants numeric --cpu 11 \
  --dsn 'host=/var/run/postgresql port=5432 user=YOUR_POSTGRES_USER dbname=postgres'
```

Use `--queries` to select a query ID or glob, for example `--queries point-first`
or `--queries 'github/G-*/exists'`. Do not compare a partial query run with a
result produced from a different selector.

The formal protocol is implemented by the runner:

- encode uses a recorded conditioning pass followed by one rotating
  measurement round per selected system (three rounds for both real-world
  schema variants plus JSONB, or two for one synthetic variant plus JSONB);
- query uses table-major execution, ten rounds, and discards the first five;
- restore uses three full-data rounds;
- timed queries return the final aggregate and do not use `ORDER BY`;
- SpecSon uses PostgreSQL `STORAGE EXTERNAL` so PostgreSQL does not recompress
  its custom block-grouped LZ4 envelope; JSONB uses PostgreSQL
  `STORAGE EXTENDED` with LZ4.

Each completed part is written atomically to:

```text
experiments/specson/results/<dataset-id>-<dataset-name>-<part>.json
```

The dataset ID is zero-padded to three digits; for example, GitHub query
results are written to `experiments/specson/results/003-GitHub-query.json`.

## Summarize and plot results

Print the consolidated ASCII table. Missing parts are displayed as not run:

```bash
python3 scripts/summarize_specson_results.py
```

Generate real-world encode, restore, and storage figures:

```bash
python3 scripts/plot_specson_results.py
```

Generate real-world query figures:

```bash
python3 scripts/plot_specson_query_results.py \
  experiments/specson/figures/query
```

Generate the synthetic publication figures:

```bash
python3 scripts/plot_specson_synthetic_publication_results.py \
  experiments/specson/figures/synthetic
python3 scripts/plot_specson_synthetic_query_results.py \
  experiments/specson/figures/synthetic-query
```

Plotting scripts refuse to run when their required result files are missing.
All performance ratios are reported as `JSONB/SpecSon`; storage percentages
are reported as `SpecSon/JSONB`.
