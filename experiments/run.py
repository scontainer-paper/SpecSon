#!/usr/bin/env python3
"""Formal single-system experiments. Edit CONNECTIONS and paths here, or use path flags."""
import argparse
import getpass
import fcntl
import glob
import json
import os
from pathlib import Path
import re
import sys
import uuid

from engines import Postgres, ClickHouse, identifier
from cpu_config import BACKEND_CPUS, CLIENT_CPU
from protocol import ColdStart, Results, RunOutput, digest, emit_result, measure, stamp, statistics_ms

HERE = Path(__file__).resolve().parent
DATASET_DIR = HERE.parent / 'datasets'
SQL_DIR = HERE / 'sql'
STATE_DIR = HERE / 'runtime/state'

# Deliberately separate connection dictionaries, even on the same PostgreSQL.
# Do not import connection settings from the old benchmark scripts.
CONNECTIONS = {
    'specson': {'connection': {'host': '/tmp', 'port': 56529, 'dbname': os.environ.get('SPECSON_SINGLE_DATABASE', 'postgres'), 'user': getpass.getuser()}},
    'pg': {'connection': {'host': '/tmp', 'port': 56529, 'dbname': os.environ.get('SPECSON_SINGLE_DATABASE', 'postgres'), 'user': getpass.getuser()}},
    'umbra': {
        'connection': {'host': '127.0.0.1', 'port': 56620, 'dbname': 'postgres',
                       'user': 'postgres', 'password': 'postgres'},
        # Dedicated per-dataset files; same configured connection/port each time.
        # Needed because physical reimport cannot compact a shared Umbra DB.
        'managed': {'directory': str(HERE/'runtime/umbra'), 'prefix': 'specson-public-umbra',
                    'image': 'umbradb/umbra@sha256:3ce071bced83b4a58cc4aa1c2f1cc628353277dc5d4538018fb5e910e879346c'},
    },
    'clickhouse': {'url': 'http://127.0.0.1:56530/', 'user': 'default', 'password': '',
                   'container': 'specson-public-clickhouse'},
    'asterix': {'url':'http://127.0.0.1:56531','port':56531,
                'container':'specson-public-asterix','image':'eclipse-temurin@sha256:207ecae0b2b104dfc6dfa763d1e9cd2041cb344800a180e24cb1a28ed533ff90',
                'directory':str(HERE/'runtime/asterix'),'cache_gib':32,'memory_gib':64,
                'distribution':str(HERE/'runtime/asterix/apache-asterixdb-0.9.9')},
    'mongodb': {'url':'mongodb://127.0.0.1:56528','port':56528,
                'container':'specson-public-mongodb','image':'mongo@sha256:1f995ad6fdb93244a1addab1b58f934a0bc2f5643c38e02f5e9d7f0c7d227a7b',
                'directory':str(HERE/'runtime/mongodb'),'cache_gib':32,'memory_gib':64,
                'block_compressor':'snappy'},
}


def cpuset(text):
    result = set()
    for piece in text.split(','):
        if '-' in piece:
            first, last = map(int, piece.split('-'))
            result.update(range(first, last+1))
        else:
            result.add(int(piece))
    if not result:
        raise ValueError('Empty CPU set')
    return result


class ExperimentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def parser():
    p = ExperimentParser(description=__doc__, add_help=False,
        epilog='Examples: --system specson import --dataset github; --system pg query --warmups 2 --runs 5; '
               '--system specson --specson-storage toast import --dataset github; '
               '--system specson import --reimport; --system pg --gin query --warmups 0. '
               'Coldstart clears only OS page cache ONCE, not database buffers. '
               'Reimport deletes only the selected experiment datasets. '
               'The final short block is reversed within its actual length; each update repetition reverses again. '
               'Umbra uses a dedicated Docker database per dataset, configured in CONNECTIONS.')
    p.add_argument('operation', nargs='?', choices=['import', 'query', 'restore', 'update', 'size'])
    p.add_argument('--system', choices=list(CONNECTIONS))
    p.add_argument('--dataset', action='append', help='Repeat to select datasets; default: all in datasets.json')
    p.add_argument('--query', action='append', help='Only these query IDs (query operation only)')
    p.add_argument('--data-dir', type=Path, default=DATASET_DIR)
    p.add_argument('--skip-twitter', action='store_true', help='Exclude Twitter data and queries')
    p.add_argument('--sql-dir', type=Path, default=SQL_DIR)
    p.add_argument('--state-dir', type=Path, default=STATE_DIR, help='Imported-table metadata; not historical results')
    p.add_argument('--output', type=Path, help='One JSON result file; default: stdout')
    p.add_argument('--warmups', type=int, help='Default: import/restore 0, others 1')
    p.add_argument('--runs', type=int, help='Default: import/restore 1, others 3')
    p.add_argument('--cores', type=int, choices=range(1, 5), default=4,
                   help='Query/update CPU budget (1-4); import/restore always use 1 core')
    p.add_argument('--client-cpus', default=str(CLIENT_CPU))
    p.add_argument('--namespace', default='specson_experiment', help='Dedicated SQL schema/database')
    p.add_argument('--gin', action='store_true', help='PG only: GIN(jsonb_path_ops) and GIN-capable SQL')
    p.add_argument('--specson-storage', choices=['custom', 'toast'], default='custom',
                   help='SpecSON table storage; toast uses the jsonb compression/externalization policy '
                        'and separate specson-toast tables, state, and results for every operation')
    p.add_argument('--reuse-pg', action='store_true', help='GIN query only: use the existing pg tables after benchmark_gin.py builds their indexes')
    p.add_argument('--verify-results', action='store_true', help='Record an order-independent query result signature outside timing')
    p.add_argument('--analyze-plans', action='store_true', help='PG/SpecSON queries: execute EXPLAIN ANALYZE outside timing to record actual workers')
    p.add_argument('--reimport', action='store_true', help='Import only: delete old table AND its physical storage before reloading')
    p.add_argument('--help', '-h', action='store_true')
    return p


def dataset_manifest(root, skip_twitter=False):
    manifest = json.loads((root/'datasets.json').read_text())
    return [d for d in manifest if not (skip_twitter and d['name'] == 'twitter')]


def load_dataset(root, config):
    if not isinstance(config['rows'], int) or config['rows'] < 1:
        raise ValueError('Dataset rows must be a positive integer')
    folder = root / config['name']
    files = []
    for pattern in config['files']:
        matches = sorted(glob.glob(str(folder/pattern)))
        if not matches:
            raise FileNotFoundError(f'No input files: {folder/pattern}')
        files.extend(Path(p) for p in matches)
    if len(files) != len(set(files)):
        raise ValueError('Overlapping dataset file patterns')
    schema = json.loads((folder/'schema.json').read_text())
    source = [(str(p.resolve()), p.stat().st_size, p.stat().st_mtime_ns) for p in files]
    signature = dict(schema=schema, sources=source, rows=config['rows'])
    if config.get('replace_nul'):
        signature['input_normalization'] = 'JSON U+0000 escapes to U+FFFD; literal escapes preserved'
    return dict(config, files=files, schema=schema,
                signature=digest(signature))


def render_sql(text, variables):
    def replace(match):
        key = match[1]
        if key not in variables:
            raise ValueError('Unknown SQL placeholder: ' + key)
        return str(variables[key])
    return re.sub(r'\{\{([a-z_]+)\}\}', replace, text).strip().removesuffix(';')


def queries(text):
    parts = re.split(r'^-- query: (\S+)(?: \|[^\n]*)?\n', text, flags=re.M)
    result = [(parts[i], parts[i+1].strip().removesuffix(';')) for i in range(1, len(parts), 2)]
    if not result or len({q for q, _ in result}) != len(result):
        raise ValueError('Query file must contain unique -- query: ID | title markers')
    return result


def query_sql(system, text, variables):
    """Apply the relational condition before the document query on every engine."""
    if system == 'mongodb':
        request = json.loads(render_sql(text, variables))
        request['pipeline'].insert(0, {'$match': {'doc_id': {'$gt': 0}}})
        return json.dumps(request, separators=(',', ':'))
    if system == 'clickhouse':
        # A SELECT * subquery prevents JSON subcolumn pruning in ClickHouse.
        if '{{relational_filter}}' not in text:
            raise ValueError('ClickHouse query template requires {{relational_filter}}')
        return render_sql(text, dict(variables, relational_filter='doc_id > 0'))
    table = variables['table']
    source = (f'(SELECT VALUE query_input FROM {table} query_input WHERE query_input.doc_id > 0)'
              if system == 'asterix' else f'(SELECT * FROM {table} WHERE doc_id > 0)')
    return render_sql(text, dict(variables, table=source))


def sql_file(args, path, variables):
    return render_sql((args.sql_dir/path).read_text(), variables)


def execution_cores(args):
    # Import is always single-core, independent of the query CPU budget.
    return 1 if args.operation in ('import', 'restore') else args.cores


def result_variant(args):
    if args.system == 'specson' and args.specson_storage == 'toast':
        return 'specson-toast'
    return 'pg-gin' if getattr(args, 'gin', False) else args.system


def run(args):
    cores = execution_cores(args)
    backend_cpus = set(BACKEND_CPUS[:cores])
    os.sched_setaffinity(0, cpuset(args.client_cpus))
    config = dict(CONNECTIONS[args.system])
    if args.system == 'specson' and args.specson_storage == 'toast':
        config['specson_storage'] = args.specson_storage
    public = {k: v for k, v in config.items() if k not in ('password', 'container')}
    if 'connection' in public:
        public['connection'] = {k:v for k,v in public['connection'].items() if k != 'password'}
    variant = result_variant(args)
    sql_variant = 'specson' if args.system == 'specson' else variant
    create_path = Path(args.system) / ('create-toast.sql' if variant == 'specson-toast' else 'create.sql')
    storage_variant = 'pg' if args.reuse_pg else variant
    identity = digest(dict(connection=public, namespace=args.namespace))
    results = Results(args.state_dir, storage_variant, identity, getattr(args,'result_output',None))
    manifest = dataset_manifest(args.data_dir, args.skip_twitter)
    names = [c['name'] for c in manifest]
    if args.dataset and not set(args.dataset).issubset(names):
        raise ValueError('Unknown datasets: ' + str(set(args.dataset)-set(names)))
    selected = [c for c in manifest if not args.dataset or c['name'] in args.dataset]
    if args.operation != 'import':
        for ds in selected:
            state = results.state(ds['name'])
            if not state or state.get('status') != 'ok':
                raise RuntimeError(f"{ds['name']}: no successful import; execute import first")
    if args.query:
        known = set()
        for ds in selected:
            known.update(q for q,_ in queries((args.sql_dir/ds['name']/(sql_variant+'.sql')).read_text()))
        if not set(args.query).issubset(known):
            raise ValueError('Unknown query IDs: '+str(set(args.query)-known))
    if args.system in ('asterix','mongodb'):
        from document_engines import Asterix, MongoDB
        adapter_class={'asterix':Asterix,'mongodb':MongoDB}[args.system]
    else:
        adapter_class=ClickHouse if args.system=='clickhouse' else Postgres
    adapter = None if args.system == 'umbra' and config.get('managed') else adapter_class(
            args.system, config, identifier(args.namespace), cores, backend_cpus)
    cold = ColdStart(args.warmups == 0)
    try:
        for config_ds in selected:
            ds = load_dataset(args.data_dir, config_ds)
            name = ds['name']
            stem = identifier(name.replace('-', '_'))
            table = args.namespace + '.' + identifier(storage_variant.replace('-', '_')+'_'+stem)
            state = results.state(name)
            if args.system == 'umbra' and config.get('managed'):
                from umbra_runtime import activate
                if adapter:
                    adapter.close()
                if args.reimport:
                    results.save_state(name, dict(status='incomplete', table=table))
                local_config = activate(config, stem, backend_cpus, reset=args.reimport)
                adapter = Postgres(args.system, local_config, identifier(args.namespace), cores, backend_cpus)
            variables = dict(table=table, rows=ds['rows'], schema_id=state.get('schema_id') if state else 0,
                             snapshot=table+'_update_source',
                             batch_start='{{batch_start}}', batch_end='{{batch_end}}')
            def storage():
                info = adapter.storage(table)
                if args.system == 'specson':
                    shared = adapter.storage('specson.schema_store')
                    shared['scope'] = 'database-wide schema store, reported separately from document storage'
                    info['shared_schema_store'] = shared
                return info
            type_path = args.sql_dir/name/'clickhouse-type.sql'
            if args.system == 'clickhouse':
                variables['doc_type'] = type_path.read_text().strip().removesuffix(';')
            signature = digest(dict(data=ds['signature'], table=table, variant=storage_variant,
                ddl=(args.sql_dir/create_path).read_text(), doc_type=variables.get('doc_type'),
                **({'duplicate_keys':'last-wins'} if args.system=='asterix' and ds.get('duplicate_keys') else {})))
            if args.operation != 'import':
                if not state or state.get('status') != 'ok' or state['signature'] != signature:
                    raise RuntimeError(f'{name}: no successful matching import; execute import first')
                if not adapter.exists(table):
                    raise RuntimeError(f'{name}: imported table is missing; import again')
                if args.reuse_pg and not adapter.c.execute(
                    "SELECT 1 FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid "
                    "JOIN pg_am a ON a.oid=c.relam JOIN pg_opclass o ON o.oid=i.indclass[0] "
                    "WHERE i.indrelid=%s::regclass AND i.indisvalid AND a.amname='gin' "
                    "AND o.opcname='jsonb_path_ops'", (table,)).fetchone():
                    raise RuntimeError(f'{name}: build the GIN index with benchmark_gin.py first')
            if args.operation == 'import':
                if adapter.exists(table) and not args.reimport:
                    raise RuntimeError(f'{name}: table exists; use import --reimport to acknowledge physical deletion')
                # Invalidate completion BEFORE any destructive change.
                results.save_state(name, dict(status='incomplete', signature=signature, table=table))
                def drop_import_table():
                    if args.system in ('specson', 'pg'):
                        return adapter.drop(table, journal=results.root/name/'cleanup-pending.json')
                    return adapter.drop(table) if adapter.exists(table) else dict(cleaned=True,
                        isolated_database_reset=bool(args.system == 'umbra' and args.reimport))
                cleanup = drop_import_table()
                if args.system == 'clickhouse' and adapter.exists(variables['snapshot']):
                    adapter.drop(variables['snapshot'])
                registration_ms, variables['schema_id'] = measure(
                    lambda: adapter.register(ds['schema']), lambda value: value)
                create = sql_file(args, create_path, variables)
                adapter.command(create)
                if args.system == 'asterix' and not adapter.exists(table):
                    raise RuntimeError('AsterixDB dataset missing after creation')
                generation = uuid.uuid4().hex
                times = []
                def ingest():
                    adapter.ingest(table, ds['files'], variables['schema_id'], replace_nul=ds.get('replace_nul', False),
                        **({'normalize_duplicate_keys':True} if args.system=='asterix' and ds.get('duplicate_keys') else {}))
                    if args.gin:
                        # Bulk-load then build: include index readiness in PG+GIN import.
                        adapter.command(f'CREATE INDEX ON {table} USING gin(doc jsonb_path_ops)')
                try:
                    for i in range(args.warmups+args.runs):
                        if i:
                            # Repeated import trials must also reclaim SpecSon storage.
                            if args.system == 'umbra':
                                adapter.command(f'DROP TABLE {table}')
                                adapter.command(create)
                            else:
                                drop_import_table()
                                adapter.command(create)
                        # Finish work inherited from setup or the preceding import.
                        # Checkpoints caused by this import remain inside its timer.
                        if args.system in ('specson', 'pg'):
                            adapter.command('CHECKPOINT')
                        if i >= args.warmups:
                            cold.before_first_sample()
                        elapsed, _ = measure(ingest, lambda _: None)
                        if i >= args.warmups:
                            times.append(elapsed)
                        results.checkpoint(dict(system=variant,dataset=name,operation='import',
                            times_ms=times,completed_executions=i+1,
                            schema_registration_ms=registration_ms))
                        adapter.validate(table, ds['rows'])
                    adapter.maintain(table)
                    storage_info = storage()
                    record = dict(status='ok', system=variant, dataset=name, operation='import',
                        statistics=statistics_ms(times), storage=storage_info, cleanup=cleanup,
                        warmups=args.warmups, runs=args.runs, rows=ds['rows'], metadata=adapter.meta,
                        schema_registration_ms=registration_ms if args.system == 'specson' else None,
                        checkpoint_before_import=args.system in ('specson', 'pg'),
                        input_normalization='JSON U+0000 to U+FFFD' if ds.get('replace_nul') else 'none',
                        duplicate_key_normalization='last-wins via native orjson, included in import timing'
                            if args.system=='asterix' and ds.get('duplicate_keys') else 'none',
                        metric='source JSONL read through COPY/INSERT and commit acknowledgement; PG+GIN includes index build; schema/table DDL excluded',
                cold_os_cache_cleared=cold.done, generation=generation)
                    results.save(record)
                    results.save_state(name, dict(status='ok', signature=signature, table=table,
                        schema_id=variables['schema_id'], generation=generation, rows=ds['rows'],
                        update_parity=0, revision=0))
                except BaseException as error:
                    results.save_state(name, dict(status='incomplete', signature=signature, table=table))
                    results.save(dict(status='error', error=str(error),
                        times_ms=times, system=variant, dataset=name, operation='import'))
                    raise
                continue
            if args.operation == 'query':
                statements = [(qid, query_sql(args.system, text, variables)) for qid, text in
                              queries((args.sql_dir/name/(sql_variant+'.sql')).read_text())]
                if args.query:
                    statements = [(q,s) for q,s in statements if q in args.query]
            elif args.operation == 'size':
                statements = [('size', '')]
            else:
                statements = [(args.operation, sql_file(args, Path(args.system)/(args.operation+'.sql'), variables))]
            for qid, sql in statements:
                snapshot_sql = (sql_file(args, Path('clickhouse/update-source.sql'), variables)
                                if args.operation == 'update' and args.system == 'clickhouse' else '')
                record = dict(system=variant, dataset=name, query=qid, operation=args.operation,
                    sql=sql, warmups=args.warmups, runs=args.runs, metadata=adapter.meta,
                    generation=state['generation'], input_revision=state['revision'], started_at=stamp())
                if args.operation == 'query':
                    record['relational_filter'] = 'doc_id > 0'
                results.checkpoint(record)
                try:
                    if args.operation == 'size':
                        record.update(status='ok', storage=storage())
                    else:
                        times = []
                        record['times_ms'] = times
                        prepared = adapter.prepare(sql, streaming=args.operation == 'restore') if args.operation in ('query', 'restore') else None
                        expected_rows = None
                        for i in range(args.warmups+args.runs):
                            adapter.verify_results=args.verify_results and args.operation=='query' and i>=args.warmups
                            if i >= args.warmups:
                                cold.before_first_sample()
                            if args.operation == 'update':
                                state['status'] = 'updating'
                                results.save_state(name, state)
                                elapsed, _ = measure(lambda: adapter.update(sql, snapshot_sql=snapshot_sql,
                                    snapshot=variables['snapshot'], rows=ds['rows']), lambda _: None)
                                if args.system == 'clickhouse':
                                    adapter.drop(variables['snapshot'])
                                adapter.validate(table, ds['rows'])
                                state['update_parity'] = 1-state.get('update_parity', 0)
                                state['revision'] += 1
                                state['status'] = 'ok'
                                results.save_state(name, state)
                            else:
                                elapsed, info = measure(lambda: adapter.receive(prepared), adapter.finish)
                                count = info['result_rows']
                                if expected_rows is not None and count != expected_rows:
                                    raise RuntimeError('Result row count changed between repetitions')
                                expected_rows = count
                                if info.get('result_signature'):
                                    if record.get('result_signature',info['result_signature'])!=info['result_signature']:
                                        raise RuntimeError('Query results changed between executions')
                                    record['result_signature']=info['result_signature']
                                if args.operation == 'restore' and count != ds['rows']:
                                    raise RuntimeError('Restore did not return every document')
                            if i >= args.warmups:
                                times.append(elapsed)
                            record['completed_executions'] = i+1
                            results.checkpoint(record)
                        record.update(status='ok', statistics=statistics_ms(times), result_rows=expected_rows,
                            output_revision=state['revision'],
                            cold_os_cache_cleared=cold.done,
                            metric='snapshot serialization/reverse UPDATE through commit/visible acknowledgement' if args.operation == 'update'
                            else 'query submission through complete raw result reception; restore streams bounded chunks; Python decoding excluded')
                        if args.system=='mongodb' and args.operation=='restore':
                            record['metric']='complete BSON reception and native libbson conversion of every document to JSON text; bounded memory; no content validation'
                    if args.operation == 'query' and args.system in ('specson', 'pg'):
                        # Plan inspection is outside all timed executions.
                        record['plan_nodes'] = adapter.query_plan(sql)
                        if args.analyze_plans:
                            record['executed_plan'] = adapter.command(
                                'EXPLAIN (ANALYZE, VERBOSE, TIMING OFF, FORMAT JSON) EXECUTE '+
                                prepared[0].decode()).fetchone()[0]
                    results.save(record)
                except BaseException as error:
                    record.update(status='error', error=str(error))
                    results.save(record)
                    raise
    finally:
        if adapter:
            adapter.close()
    return results.records


def main(argv=None):
    p = parser()
    args = None
    output = None
    try:
        args = p.parse_args(argv)
        if args.help:
            print(p.format_help())
            return 0
        if not args.operation or not args.system:
            raise ValueError('Specify exactly one --system and one operation')
        if args.warmups is None:
            args.warmups = 0 if args.operation in ('import', 'restore') else 1
        if args.runs is None:
            args.runs = 1 if args.operation in ('import', 'restore') else 3
        if args.runs < 1 or args.warmups < 0:
            raise ValueError('--runs must be positive; --warmups must be nonnegative')
        if args.gin and args.system != 'pg':
            raise ValueError('--gin is only valid for --system pg')
        if args.specson_storage != 'custom' and args.system != 'specson':
            raise ValueError('--specson-storage requires --system specson')
        if args.reuse_pg and not (args.gin and args.system == 'pg' and args.operation == 'query'):
            raise ValueError('--reuse-pg requires query --system pg --gin')
        if args.reimport and args.operation != 'import':
            raise ValueError('--reimport is only valid for import')
        if args.query and args.operation != 'query':
            raise ValueError('--query is only valid for query')
        if args.analyze_plans and (args.operation != 'query' or args.system not in ('pg','specson')):
            raise ValueError('--analyze-plans requires query --system pg/specson')
        if args.system in ('asterix','mongodb') and args.operation=='update':
            raise ValueError('AsterixDB/MongoDB adapters currently support import, query, restore and size')
        output = args.result_output = RunOutput(args.output,result_variant(args),args.operation)
        args.state_dir.mkdir(parents=True, exist_ok=True)
        with (args.state_dir/'.run.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            records = run(args)
        output.finish('ok',records=records)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        if output is not None:
            output.finish('interrupted' if isinstance(error,KeyboardInterrupt) else 'error',
                          error=str(error) or 'Interrupted')
        else:
            emit_result(None,dict(status='error',error=str(error) or 'Interrupted',timestamp=stamp()))
        return 1


if __name__ == '__main__':
    sys.exit(main())
