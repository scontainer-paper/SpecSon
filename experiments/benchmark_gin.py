#!/usr/bin/env python3
"""Build GIN indexes on existing formal jsonb tables; emit one result JSON."""
import argparse
import fcntl
import os
from pathlib import Path

from engines import Postgres, identifier
from protocol import ColdStart, RunOutput, measure, stamp
from run import CONNECTIONS, DATASET_DIR, STATE_DIR, dataset_manifest
from cpu_config import BACKEND_CPUS, CLIENT_CPU


def run(args):
    os.sched_setaffinity(0, {CLIENT_CPU})
    if args.mixed:
        from run_mixed import CONNECTIONS as MIXED_CONNECTIONS
        connection, namespace = MIXED_CONNECTIONS['jsonb'], 'specson_mixed_experiment'
        connection = dict(connection, connection=dict(connection['connection'], dbname=os.environ.get(
            'SPECSON_MIXED_JSONB_DATABASE', connection['connection']['dbname'])))
        tables = [('mixed', namespace+'.jsonb_mixed', 'jsonb_mixed_doc_gin')]
    else:
        connection, namespace = CONNECTIONS['pg'], 'specson_experiment'
        tables = [(ds['name'], namespace+'.pg_'+identifier(ds['name'].replace('-', '_')),
                   identifier('pg_'+ds['name'].replace('-', '_')+'_doc_gin'))
                  for ds in dataset_manifest(args.data_dir, args.skip_twitter)]
    adapter = Postgres('pg', connection, namespace, 1, {BACKEND_CPUS[0]})
    records = []
    cold = ColdStart(True)
    try:
        adapter.command("SET maintenance_work_mem='256MB'")
        for dataset, table, index in tables:
            if not adapter.exists(table):
                raise RuntimeError('Import jsonb first: ' + table)
            # Every invocation measures a fresh build; existing table data stays intact.
            adapter.command('DROP INDEX IF EXISTS '+namespace+'.'+index)
            cold.before_first_sample()
            elapsed, _ = measure(lambda: adapter.command(
                f'CREATE INDEX {index} ON {table} USING gin(doc jsonb_path_ops)'), lambda _: None)
            size, valid = adapter.c.execute(
                'SELECT pg_relation_size(indexrelid),indisvalid FROM pg_index WHERE indexrelid=%s::regclass',
                (namespace+'.'+index,)).fetchone()
            if not valid:
                raise RuntimeError('GIN index is not valid: ' + index)
            records.append(dict(dataset=dataset,table=table,index=index,build_ms=elapsed,
                index_bytes=size,metadata=adapter.meta,maintenance_work_mem='256MB',
                metric='CREATE INDEX through commit acknowledgement; index removal excluded',
                cold_os_cache_cleared=cold.done))
            args.result_output.checkpoint(records)
    finally:
        adapter.close()
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--data-dir', type=Path, default=DATASET_DIR)
    parser.add_argument('--skip-twitter', action='store_true', help='Exclude Twitter indexes')
    parser.add_argument('--mixed', action='store_true', help='Build GIN on the existing mixed jsonb table')
    args = parser.parse_args()
    output = RunOutput(args.output, 'pg-gin', 'build-gin')
    args.result_output = output
    try:
        state_dir = STATE_DIR.with_name('state-mixed') if args.mixed else STATE_DIR
        state_dir.mkdir(parents=True, exist_ok=True)
        with (state_dir/'.run.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            records = run(args)
        output.finish('ok', records)
        return 0
    except BaseException as error:
        output.finish('error', error=str(error))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
