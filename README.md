# SpecSON

The complete experimental results, including measurements omitted from the
paper due to space constraints, are available in
[Excel](results/reference/results.xlsx) and [JSON](results/reference/results.json).

## Contents

| Directory | Contents |
| --- | --- |
| `datasets/` | Dataset definitions and schemas; downloaded data is extracted here |
| `image/` | PostgreSQL image with SpecSON and its checksum |
| `experiments/` | Experiment scripts and queries |
| `results/reference/` | Complete experimental results |

## Setup

Requirements for running the scripts:

| Resource | Requirement |
| --- | --- |
| CPU | x86-64 processor with at least 5 available logical CPUs |
| Memory | 64 GiB available for the database, plus memory for the operating system and client |
| Operating system | Ubuntu 26.04.1 LTS; other versions and operating systems have not been tested |
| Software | Docker and Python 3.11+ |
| Access | Docker access, `sudo` privileges, and internet access for downloads |

The SpecSON PostgreSQL image is included in `image/`. Run these commands from
the package directory:

```sh
(cd image && sha256sum -c SHA256SUMS)
docker load -i image/specson-pg-18.6-release.tar.gz
python3 -m venv .venv
. .venv/bin/activate
pip install -r experiments/requirements.txt
```

## Datasets

Download [datasets.tar.gz](https://drive.google.com/file/d/1_6IA4QsLLFtshUw5X6w04C1J8H0KhNuG/view?usp=sharing)
and extract it from the package root.
After extraction, the data should be in `datasets/`:

```sh
tar -xzf /path/to/datasets.tar.gz
```

The Twitter dataset is from **2020-06-01** and is excluded for privacy reasons.
To include Twitter, provide that day's stream tar archive or UTF-8 JSONL with
one complete tweet per line. The preparation script extracts tweets, preserves
nested fields, and writes them to `datasets/twitter/data/parts/`:

```sh
python scripts/prepare_twitter.py /path/to/twitter.jsonl
python scripts/verify_artifact.py
```

## Queries

| Dataset | SpecSON / SpecSON-TOAST | JSONB | JSONB+GIN | Umbra | MongoDB | AsterixDB | ClickHouse |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GitHub | [specson.sql](experiments/sql/github/specson.sql) | [pg.sql](experiments/sql/github/pg.sql) | [pg-gin.sql](experiments/sql/github/pg-gin.sql), [pg-gin-mixed.sql](experiments/sql/github/pg-gin-mixed.sql) | [umbra.sql](experiments/sql/github/umbra.sql) | [mongodb.sql](experiments/sql/github/mongodb.sql) | [asterix.sql](experiments/sql/github/asterix.sql) | [clickhouse.sql](experiments/sql/github/clickhouse.sql) |
| Yelp Business | [specson.sql](experiments/sql/yelp-business/specson.sql) | [pg.sql](experiments/sql/yelp-business/pg.sql) | [pg-gin.sql](experiments/sql/yelp-business/pg-gin.sql), [pg-gin-mixed.sql](experiments/sql/yelp-business/pg-gin-mixed.sql) | [umbra.sql](experiments/sql/yelp-business/umbra.sql) | [mongodb.sql](experiments/sql/yelp-business/mongodb.sql) | [asterix.sql](experiments/sql/yelp-business/asterix.sql) | [clickhouse.sql](experiments/sql/yelp-business/clickhouse.sql) |
| Twitter | [specson.sql](experiments/sql/twitter/specson.sql) | [pg.sql](experiments/sql/twitter/pg.sql) | [pg-gin.sql](experiments/sql/twitter/pg-gin.sql), [pg-gin-mixed.sql](experiments/sql/twitter/pg-gin-mixed.sql) | [umbra.sql](experiments/sql/twitter/umbra.sql) | [mongodb.sql](experiments/sql/twitter/mongodb.sql) | [asterix.sql](experiments/sql/twitter/asterix.sql) | [clickhouse.sql](experiments/sql/twitter/clickhouse.sql) |
| TPC-H | [specson.sql](experiments/sql/tpch/specson.sql) | [pg.sql](experiments/sql/tpch/pg.sql) | [pg-gin.sql](experiments/sql/tpch/pg-gin.sql), [pg-gin-mixed.sql](experiments/sql/tpch/pg-gin-mixed.sql) | [umbra.sql](experiments/sql/tpch/umbra.sql) | [mongodb.sql](experiments/sql/tpch/mongodb.sql) | [asterix.sql](experiments/sql/tpch/asterix.sql) | [clickhouse.sql](experiments/sql/tpch/clickhouse.sql) |
| OpenAlex | [specson.sql](experiments/sql/openalex/specson.sql) | [pg.sql](experiments/sql/openalex/pg.sql) | [pg-gin.sql](experiments/sql/openalex/pg-gin.sql), [pg-gin-mixed.sql](experiments/sql/openalex/pg-gin-mixed.sql) | [umbra.sql](experiments/sql/openalex/umbra.sql) | [mongodb.sql](experiments/sql/openalex/mongodb.sql) | [asterix.sql](experiments/sql/openalex/asterix.sql) | [clickhouse.sql](experiments/sql/openalex/clickhouse.sql) |

For JSONB+GIN, `pg-gin.sql` is used for separate datasets and `pg-gin-mixed.sql`
for the mixed table. The memory experiment uses queries G-C1-1, G-C2-1, G-C3-1,
and G-C4-1 from the GitHub files above.

## Run

Run the complete suite, choosing an output directory that does not already exist:

```sh
python experiments/run_all.py --output-dir results/runs/reproduction
```

If you cannot provide Twitter data, skip it and obtain results for the other
datasets:

```sh
python scripts/verify_artifact.py --skip-twitter
python experiments/run_all.py --skip-twitter --output-dir results/runs/without-twitter
```

The mixed table also excludes Twitter, so its results may differ substantially
from those in the paper.

The script automatically:

1. Downloads missing Umbra, MongoDB, and ClickHouse container images and the
   AsterixDB 0.9.9 distribution. PostgreSQL uses the SpecSON image loaded above.
2. Starts the databases, imports the supplied datasets, builds indexes, and
   measures insertion, restoration, storage, and queries for both separate
   datasets and the mixed table.
3. Runs the memory experiment at 32, 16, 8, 4, 2, and 1 GiB, recording query
   times and out-of-memory outcomes.
4. Runs document updates and measures storage before updates, after updates,
   and after space reclamation.
5. Checks query results across systems and collects the measurements into
   `results/runs/reproduction/results.json`.

## Result format

The JSON files use the following sections:

| Section | Measurements |
| --- | --- |
| `single` | Separate-dataset insertion, restoration, storage, and queries |
| `mixed` | Mixed-table insertion, restoration, storage, and queries |
| `memory` | Query times at six memory limits and out-of-memory outcomes |
| `updates` | Update times and storage before and after reclamation |

Query times are in milliseconds, insertion/restoration/update times in seconds,
and storage sizes in bytes.

Given the complexity of the experiment scripts, we cannot test every hardware
and software configuration; if you encounter script issues, AI tools can help
you troubleshoot and adapt the scripts to reproduce the paper's results.
