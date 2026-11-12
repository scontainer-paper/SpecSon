#!/usr/bin/env python3
"""Formal mixed-table counterpart of run.py. One system and one operation per run.

Each schema's documents are evenly spaced over a normalized insertion timeline,
with a seeded phase per schema; a heap merges these positions. Source counts
are unchanged, including the synthetic pool's original cycle multiplicities
(omit synthetic documents and schemas with --no-synthetic). doc_id starts at
zero globally.
source_id/source_no identify each document's current input source; only
SpecSon stores schema_id. Queries select doc_id > 0 across the mixed
table without adding a dataset predicate. Updates replace the first 1,000,000
doc_ids with cyclic OpenAlex Work input, recording elapsed time and final size.
Schema registration is timed separately on every import. AsterixDB uses row
storage and the native socket-client bulk loader.
"""
import fcntl
import getpass
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import uuid

from run import ExperimentParser, cpuset, load_dataset, queries, render_sql, query_sql, execution_cores, result_variant
from engines import identifier
from cpu_config import BACKEND_CPUS, CLIENT_CPU
from run import dataset_manifest
from mixed import BLOCK_ROWS, MIXED_ORDER, MIXED_SEED, MixedPostgres, mixed_rows, mongo_ingest, mongo_validate, asterix_ingest, asterix_validate, register_schemas, reuse_schema_ids
from protocol import ColdStart, Results, RunOutput, digest, emit_result, measure, stamp, statistics_ms, query_reference

HERE = Path(__file__).resolve().parent
# Deliberately explicit and separate, including SpecSon/jsonb on the same PG.
CONNECTIONS = {
    'specson': {'connection': {'host':'/tmp','port':56539,'dbname':'postgres','user':getpass.getuser()}},
    'jsonb': {'connection': {'host':'/tmp','port':56539,'dbname':'postgres','user':getpass.getuser()}},
    'umbra': {'connection': {'host':'127.0.0.1','port':56620,'dbname':'postgres',
                            'user':'postgres','password':'postgres'},
              'managed': {'directory':str(HERE/'runtime/umbra-mixed'), 'prefix':'specson-public-mixed-umbra',
                          'image':'umbradb/umbra@sha256:3ce071bced83b4a58cc4aa1c2f1cc628353277dc5d4538018fb5e910e879346c'}},
    'mongodb': {'url':'mongodb://127.0.0.1:56528','port':56528,
                'container':'specson-public-mongodb','image':'mongo@sha256:1f995ad6fdb93244a1addab1b58f934a0bc2f5643c38e02f5e9d7f0c7d227a7b',
                'directory':str(HERE/'runtime/mongodb'),'cache_gib':32,'memory_gib':64,
                'block_compressor':'snappy'},
    'asterix': {'url':'http://127.0.0.1:56531','port':56531,
                'container':'specson-public-asterix','image':'eclipse-temurin@sha256:207ecae0b2b104dfc6dfa763d1e9cd2041cb344800a180e24cb1a28ed533ff90',
                'directory':str(HERE/'runtime/asterix'),'cache_gib':32,'memory_gib':64,
                'distribution':str(HERE/'runtime/asterix/apache-asterixdb-0.9.9')},
}


def parser():
    p = ExperimentParser(description=__doc__, add_help=False,
        epilog='Examples: --system specson import --warmups 1 --runs 1; '
               '--system jsonb query --warmups 1 --runs 1; '
               '--system umbra query --dataset github; '
               '--system mongodb restore --warmups 1 --runs 1; '
               '--system specson restore --restart-postgres; '
               '--system specson import --reimport. '
               '--system specson update --cores 4; update runs once from the original import.')
    p.add_argument('operation', nargs='?', choices=['import','query','restore','update','size','reclaim'])
    p.add_argument('--system', choices=list(CONNECTIONS))
    p.add_argument('--specson-storage', choices=['custom', 'toast'], default='custom')
    p.add_argument('--gin', action='store_true',
                   help='Query or measure the existing jsonb mixed table with a jsonb_path_ops GIN index')
    p.add_argument('--reuse-schemas-from',
                   help='SpecSON import: reuse registered schema IDs from an existing mixed table')
    p.add_argument('--data-dir', type=Path, default=HERE.parent/'datasets')
    p.add_argument('--skip-twitter', action='store_true', help='Exclude Twitter from the mixed table and queries')
    p.add_argument('--synthetic-dir', type=Path, default=HERE.parent/'datasets/synthetic')
    p.add_argument('--no-synthetic', action='store_true',
                   help='Import only real datasets; do not read/register synthetic schemas or insert synthetic documents')
    p.add_argument('--sql-dir', type=Path, default=HERE/'sql')
    p.add_argument('--state-dir', type=Path, default=HERE/'runtime/state-mixed')
    p.add_argument('--output', type=Path, help='One JSON result file; default: stdout')
    p.add_argument('--dataset', action='append', help='Query selection only; imports always mix every manifest dataset')
    p.add_argument('--query', action='append', help='Select query IDs')
    p.add_argument('--update-rows', type=int, default=1_000_000,
                   help='Update the first N doc_ids with cyclic OpenAlex Work input (default: 1000000)')
    p.add_argument('--namespace', default='specson_mixed_experiment')
    p.add_argument('--cores', type=int, choices=range(1,5), default=4,
                   help='Query/update CPU budget; import/restore always use 1 core')
    p.add_argument('--client-cpus', default=str(CLIENT_CPU))
    p.add_argument('--memory-gib', type=int, help='Query/update instance limit; PG must be started with the same profile')
    p.add_argument('--continue-on-oom', action='store_true', help='Record an OOM query and continue with a fresh connection')
    p.add_argument('--clear-os-cache', action='store_true', help='Clear OS page cache before the first warmup')
    p.add_argument('--mongodb-compressor', choices=['none','snappy','zlib','zstd'],
                   help='Override MongoDB collection block compression; use a separate namespace to keep both copies')
    p.add_argument('--warmups', type=int, help='Default: import/restore/update 0, others 1; update never clears caches implicitly')
    p.add_argument('--runs', type=int, help='Default: import/restore/update 1, others 3')
    p.add_argument('--restart-postgres', action='store_true',
                   help='Full PG/SpecSON restoration: rebuild and restart the mixed instance before a cold single-core run')
    p.add_argument('--verify-results', action='store_true')
    p.add_argument('--reference-results', type=Path,
                   help='Check each query against a completed reference run; requires --verify-results')
    p.add_argument('--analyze-plans', action='store_true',
                   help='PG/SpecSON: record actual workers outside query timing')
    p.add_argument('--reimport', action='store_true', help='Replace the mixed table and register schemas for the new import')
    p.add_argument('--help','-h', action='store_true')
    return p


def inputs(args):
    manifest = dataset_manifest(args.data_dir, args.skip_twitter)
    datasets = [load_dataset(args.data_dir, d) for d in manifest]
    if not datasets or len({d['name'] for d in datasets}) != len(datasets):
        raise ValueError('Dataset manifest must be nonempty with unique names')
    if args.no_synthetic:
        signature = digest(dict(format=4, datasets=[d['signature'] for d in datasets],
                                synthetic_count=0, order=MIXED_ORDER, seed=MIXED_SEED))
        return datasets, {'schemas':0, 'documents':0}, 0, signature
    synthetic = json.loads((args.synthetic_dir/'manifest.json').read_text())
    if synthetic['schemas'] < 1 or synthetic['documents'] != synthetic['schemas']:
        raise ValueError('Synthetic pool needs one document per schema')
    sources = []
    for name in ['schemas.jsonl','mixed.jsonl']:
        path = args.synthetic_dir/name
        stat = path.stat()
        if stat.st_size != synthetic['files'][name]:
            raise ValueError('Synthetic file size mismatch: '+name)
        sources.append((str(path.resolve()), stat.st_size, stat.st_mtime_ns))
    rounds = max((d['rows']+BLOCK_ROWS-1)//BLOCK_ROWS for d in datasets)
    signature = digest(dict(format=4, datasets=[d['signature'] for d in datasets],
                            synthetic=sources, synthetic_count=synthetic['schemas'],
                            order=MIXED_ORDER, seed=MIXED_SEED))
    return datasets, synthetic, rounds, signature


def create_sql(system, table, specson_storage='custom'):
    if system == 'mongodb':
        return json.dumps({'create':table})
    if system == 'asterix':
        return (f'CREATE TYPE {table}_type AS OPEN {{doc_id: bigint,'
                f'source_id: bigint,source_no: bigint}}; '
                f'CREATE DATASET {table}({table}_type) PRIMARY KEY doc_id '
                'WITH {"storage-format":{"format":"row"}}')
    doc = 'specson.specson' if system == 'specson' else 'jsonb'
    if system == 'jsonb' or (system == 'specson' and specson_storage == 'toast'):
        doc += ' COMPRESSION lz4'
    options = '' if system == 'umbra' else ' WITH (autovacuum_enabled=false)'
    if system == 'specson' and specson_storage == 'toast':
        options = ' WITH (autovacuum_enabled=false, specson_storage=toast)'
    schema_column = 'schema_id integer,' if system == 'specson' else ''
    return (f'CREATE TABLE {table}(doc_id bigint,source_id integer,'
            f'source_no bigint,{schema_column}doc {doc})'+options)


def mixed_query(system, statement, table):
    return query_sql('pg' if system == 'jsonb' else system, statement, {'table': table})


def run(args):
    os.sched_setaffinity(0, cpuset(args.client_cpus))
    cores = execution_cores(args)
    cpus = set(BACKEND_CPUS[:cores])
    datasets, synthetic, rounds, input_signature = inputs(args)
    names = {d['name'] for d in datasets}
    if args.dataset and not set(args.dataset) <= names:
        raise ValueError('Unknown query dataset')
    variant = 'pg' if args.system == 'jsonb' else args.system
    result_system = result_variant(args)
    storage_system = args.system if args.gin else result_system
    sql_variant = 'pg-gin-mixed' if args.gin else variant
    table = identifier(args.namespace)+'.'+identifier(storage_system.replace('-', '_')+'_mixed')
    ddl = create_sql(args.system, table, args.specson_storage)
    config = dict(CONNECTIONS[args.system])
    if args.system in ('specson','jsonb'):
        key = 'TOAST' if result_system=='specson-toast' else args.system.upper()
        config['connection'] = dict(config['connection'], dbname=os.environ.get(
            'SPECSON_MIXED_'+key+'_DATABASE', config['connection']['dbname']))
        config['container'] = f"specson-public-pg-{config['connection']['port']}"
    if args.system == 'specson' and args.specson_storage == 'toast':
        config['specson_storage'] = args.specson_storage
    if args.mongodb_compressor is not None:
        config['block_compressor'] = args.mongodb_compressor
    public = {k:v for k,v in config.items() if k not in ('password','container')}
    if 'connection' in public:
        public['connection'] = {k:v for k,v in public['connection'].items() if k != 'password'}
    results = Results(args.state_dir, storage_system, digest(dict(connection=public,table=table)),
                      getattr(args,'result_output',None))
    signature = digest(dict(input=input_signature, table=table, ddl=ddl))
    state = results.state('mixed')
    if args.memory_gib is not None:
        from memory_budget import profile
        config.update(profile(args.memory_gib))
    synthetic_rows = rounds * BLOCK_ROWS
    rows = sum(d['rows'] for d in datasets)+synthetic_rows
    selected_queries = []
    reference = {}
    if args.operation == 'query':
        for d in datasets:
            if not args.dataset or d['name'] in args.dataset:
                selected_queries.extend((qid,mixed_query(args.system,statement,table))
                    for qid,statement in queries((args.sql_dir/d['name']/(sql_variant+'.sql')).read_text()))
        if args.query:
            if not set(args.query) <= {q for q,s in selected_queries}:
                raise ValueError('Unknown selected query IDs')
            selected_queries = [(q,s) for q,s in selected_queries if q in args.query]
        if args.reference_results:
            data = query_reference(args.reference_results)
            if data['status'] != 'ok' or data['operation'] != 'query':
                raise ValueError('Reference must be a completed query run')
            reference = {r['query']:r['result_signature'] for r in data['results'] if r['status']=='ok'}
            if not {q for q,_ in selected_queries} <= reference.keys():
                raise ValueError('Reference does not cover every selected query')
    if args.operation != 'import' and (not state or state.get('status') != 'ok' or state['signature'] != signature):
        raise RuntimeError('No successful matching mixed import; execute import first')
    if args.reimport:
        results.save_state('mixed', dict(status='incomplete',signature=signature,table=table))
    adapter = None
    cold = ColdStart(args.warmups == 0 and args.operation != 'update')
    try:
        def storage():
            info = adapter.storage(table)
            if args.system == 'specson':
                shared = adapter.storage('specson.schema_store')
                shared['scope'] = '全库共享 schema 目录和镜像，包含其他表及未引用 schema；不归入本表独占空间'
                info['shared_schema_store'] = shared
            return info

        def connect(reset=False):
            if args.system in ('mongodb','asterix'):
                from document_engines import Asterix, MongoDB
                cls = {'mongodb':MongoDB,'asterix':Asterix}[args.system]
                return cls(args.system,config,args.namespace,cores,cpus)
            local = config
            if args.system == 'umbra' and config.get('managed'):
                from umbra_runtime import activate
                local = activate(config,'mixed',cpus,reset=reset)
            return MixedPostgres(variant,local,args.namespace,cores,cpus)
        adapter = connect(reset=args.reimport)
        if args.operation == 'import':
            if adapter.exists(table) and not args.reimport:
                raise RuntimeError('Mixed table exists; use import --reimport to replace its physical storage')
            results.save_state('mixed', dict(status='incomplete',signature=signature,table=table))

            def drop():
                if args.system in ('specson','jsonb'):
                    return adapter.drop(table,journal=results.root/'mixed/cleanup-pending.json')
                return adapter.drop(table) if adapter.exists(table) else dict(cleaned=True)

            cleanup = drop()
            reuse_ms = None
            if args.reuse_schemas_from:
                reuse_ms, mapping = measure(lambda: reuse_schema_ids(
                    adapter,args.reuse_schemas_from,datasets,args.synthetic_dir,synthetic['schemas']),
                    lambda value: value)
                registration_ms = 0
            else:
                registration_ms, mapping = measure(lambda: register_schemas(
                    adapter,datasets,args.synthetic_dir,synthetic['schemas']), lambda value: value)
            adapter.command(ddl)
            generation = uuid.uuid4().hex
            times = []
            try:
                for i in range(args.warmups+args.runs):
                    if i:
                        if args.system == 'umbra' and config.get('managed'):
                            adapter.close()
                            adapter = None
                            adapter = connect(reset=True)
                        else:
                            drop()
                        adapter.command(ddl)
                    if args.system=='asterix' and not adapter.exists(table):
                        raise RuntimeError('AsterixDB row dataset was not created')
                    if args.system in ('specson','jsonb'):
                        adapter.command('CHECKPOINT')
                    if i >= args.warmups:
                        cold.before_first_sample()
                    def ingest():
                        stream = mixed_rows(datasets,args.synthetic_dir/'mixed.jsonl',synthetic['schemas'],mapping)
                        try:
                            if args.system == 'mongodb':
                                mongo_ingest(adapter,table,stream)
                            elif args.system == 'asterix':
                                asterix_ingest(adapter,table,stream,datasets)
                            else:
                                adapter.ingest_mixed(table,stream)
                        finally:
                            stream.close()
                    elapsed,_ = measure(ingest, lambda _: None)
                    if i >= args.warmups:
                        times.append(elapsed)
                    results.checkpoint(dict(system=result_system,dataset='mixed',operation='import',
                        times_ms=times,completed_executions=i+1,schema_registration_ms=registration_ms))
                    if args.system == 'mongodb':
                        mongo_validate(adapter,table,datasets,synthetic_rows)
                    elif args.system == 'asterix':
                        asterix_validate(adapter,table,datasets,synthetic_rows)
                    else:
                        adapter.validate_mixed(table,datasets,synthetic_rows)
                adapter.maintain(table)
                record = dict(status='ok',system=result_system,dataset='mixed',operation='import',
                    statistics=statistics_ms(times),storage=storage(),cleanup=cleanup,
                    rows=rows,source_rows={d['name']:d['rows'] for d in datasets},synthetic_rows=synthetic_rows,
                    synthetic_pool=synthetic['schemas'],
                    registered_schemas=len(mapping)-1 if mapping and not args.reuse_schemas_from else 0,
                    reused_schemas=len(mapping)-1 if args.reuse_schemas_from else 0,
                    schema_reuse_ms=reuse_ms,reused_schemas_from=args.reuse_schemas_from,
                    interleaving=dict(order=MIXED_ORDER,seed=MIXED_SEED),
                    warmups=args.warmups,runs=args.runs,metadata=adapter.meta,generation=generation,
                    cold_os_cache_cleared=cold.done,
                    checkpoint_before_import=args.system in ('specson','jsonb'),
                    schema_registration_ms=registration_ms if args.system == 'specson' else None,
                    input_normalization='last-key-wins within timed stream for '+', '.join(
                        d['name'] for d in datasets if d.get('duplicate_keys')) if args.system=='asterix' else 'none',
                    metric='source reads + interleaving + client serialization + server encoding/writes + commit or journaled batch acknowledgement; DDL/schema registration/validation/maintenance/storage inspection excluded',
                    input_protocol='binary COPY v2 (schema ID + JSON), PQflush after each 1MiB chunk' if args.system=='specson' else
                        'native socket-client LOAD, bounded 1MiB stream; completion acknowledged' if args.system=='asterix' else
                        'ordered acknowledged MongoDB batches, 8MiB/10000 rows' if args.system=='mongodb' else
                        'CSV COPY (US delimiter / RS quote), 100000-row transactions, PQflush after each 1MiB chunk; all commits timed' if args.system=='umbra' else
                        'binary COPY, PQflush after each 1MiB chunk')
                results.save(record)
                results.save_state('mixed',dict(status='ok',signature=signature,table=table,rows=rows,
                    generation=generation,revision=0))
            except BaseException as error:
                results.save(dict(status='error',system=result_system,operation='import',error=str(error),times_ms=times))
                raise
            return results.records
        if not adapter.exists(table):
            raise RuntimeError('Imported mixed table is missing; import again')
        if args.gin and not adapter.c.execute(
                "SELECT 1 FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid "
                "JOIN pg_am a ON a.oid=c.relam JOIN pg_opclass o ON o.oid=i.indclass[0] "
                "WHERE i.indrelid=%s::regclass AND i.indisvalid AND a.amname='gin' "
                "AND o.opcname='jsonb_path_ops'", (table,)).fetchone():
            raise RuntimeError('Build the mixed-table GIN index with benchmark_gin.py --mixed first')
        if args.operation == 'reclaim':
            from mixed_reclaim import run_reclaim
            run_reclaim(adapter, table, state, results, storage, result_system)
            return results.records
        if args.operation == 'update':
            if args.system == 'jsonb' and adapter.c.execute(
                    "SELECT 1 FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid "
                    "JOIN pg_am a ON a.oid=c.relam "
                    "WHERE i.indrelid=%s::regclass AND a.amname='gin'", (table,)).fetchone():
                raise RuntimeError('Update excludes GIN: use an independent jsonb table without a GIN index')
            from mixed_update import run_update
            run_update(adapter, table, datasets, state, results, storage, args.update_rows, result_system)
            return results.records
        if args.operation == 'query':
            statements = selected_queries
        elif args.operation == 'size':
            statements = [('size','')]
        else:
            statements = [('restore',render_sql((args.sql_dir/variant/'restore.sql').read_text(),{'table':table}))]
        if args.clear_os_cache:
            ColdStart.clear_os_cache()
        for position,(qid,statement) in enumerate(statements):
            record = dict(system=result_system,dataset='mixed',query=qid,operation=args.operation,sql=statement,
                warmups=args.warmups,runs=args.runs,metadata=adapter.meta,generation=state['generation'],
                input_revision=state['revision'],started_at=stamp())
            if args.operation == 'query':
                record['relational_filter'] = 'doc_id > 0'
                if args.reference_results:
                    record['reference_results'] = str(args.reference_results.resolve())
            results.checkpoint(record)
            phase = 'prepare'
            from memory_budget import memory_events
            events_before = memory_events(adapter.meta) if args.continue_on_oom else None
            try:
                if args.operation == 'size':
                    record.update(status='ok',storage=storage())
                else:
                    prepared = adapter.prepare(statement,streaming=args.operation=='restore')
                    times, expected = [], None
                    record['times_ms'] = times
                    for i in range(args.warmups+args.runs):
                        phase = 'warmup' if i < args.warmups else 'measurement'
                        adapter.verify_results = args.verify_results and args.operation=='query' and i>=args.warmups
                        if i >= args.warmups:
                            cold.before_first_sample()
                        elapsed,info = measure(lambda: adapter.receive(prepared),adapter.finish)
                        if args.operation == 'query' and i == 0:
                            record['first_execution_ms'] = elapsed
                        if expected is not None and expected != info['result_rows']:
                            raise RuntimeError('Result row count changed between repetitions')
                        expected = info['result_rows']
                        if args.operation == 'restore' and expected != rows:
                            raise RuntimeError('Restore did not receive every document')
                        if info.get('result_signature'):
                            if qid in reference and reference[qid] != info['result_signature']:
                                raise RuntimeError('Query result differs from reference: '+qid)
                            if record.get('result_signature',info['result_signature']) != info['result_signature']:
                                raise RuntimeError('Query results changed between executions')
                            record['result_signature'] = info['result_signature']
                        if i >= args.warmups:
                            times.append(elapsed)
                        record['completed_executions'] = i+1
                        results.checkpoint(record)
                    record.update(status='ok',statistics=statistics_ms(times),result_rows=expected,
                                  output_revision=state['revision'],cold_os_cache_cleared=cold.done)
                if args.operation=='query' and args.system in ('specson','jsonb'):
                    record['plan_nodes'] = adapter.query_plan(statement)
                    if args.analyze_plans:
                        record['executed_plan'] = adapter.command(
                            'EXPLAIN (ANALYZE, VERBOSE, TIMING OFF, FORMAT JSON) EXECUTE '+
                            prepared[0].decode()).fetchone()[0]
                results.save(record)
            except BaseException as error:
                if args.continue_on_oom and isinstance(error, Exception):
                    from memory_budget import oom_failure
                    failure = oom_failure(error, adapter.meta, events_before)
                    if failure is not None:
                        record.update(status='oom', failed_phase=phase, **failure)
                        results.save(record)
                        failed_container = adapter.meta.get('container')
                        adapter.close()
                        adapter = None
                        if position+1 < len(statements):
                            # An OOM can kill a database worker while its container
                            # remains running. Restart all processes before reconnecting.
                            if failed_container and args.system not in ('specson','jsonb'):
                                from umbra_runtime import docker
                                docker('stop', failed_container)
                            if args.system in ('specson','jsonb'):
                                from prepare_postgres import prepare
                                setup=SimpleNamespace(action='stop',cores=cores,
                                    port=config['connection']['port'],
                                    runtime_dir=HERE/'runtime/postgres-mixed',
                                    memory_gib=args.memory_gib or 64)
                                prepare(setup)
                                setup.action='start'
                                prepare(setup)
                            adapter = connect()
                        continue
                record.update(status='error',error=str(error))
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
            raise ValueError('Specify one --system and one operation')
        if args.mongodb_compressor is not None and args.system!='mongodb':
            raise ValueError('--mongodb-compressor requires --system mongodb')
        if args.specson_storage != 'custom' and args.system != 'specson':
            raise ValueError('--specson-storage requires --system specson')
        if args.gin and (args.system != 'jsonb' or args.operation not in ('query','size')):
            raise ValueError('--gin requires query or size --system jsonb')
        if args.memory_gib is not None and args.operation not in ('query','update','reclaim'):
            raise ValueError('--memory-gib requires query, update or reclaim')
        if (args.continue_on_oom or args.clear_os_cache) and args.operation != 'query':
            raise ValueError('OOM/cache-clear options require query')
        if args.reuse_schemas_from and (args.system != 'specson' or args.operation != 'import'):
            raise ValueError('--reuse-schemas-from requires import --system specson')
        if args.warmups is None:
            args.warmups = 0 if args.operation in ('import','restore','update','reclaim') else 1
        if args.runs is None:
            args.runs = 1 if args.operation in ('import','restore','update','reclaim') else 3
        if args.warmups < 0 or args.runs < 1:
            raise ValueError('Invalid warmup/run count')
        if args.operation == 'reclaim' and (args.warmups != 0 or args.runs != 1):
            raise ValueError('Reclamation runs once: use --warmups 0 --runs 1')
        if args.reimport and args.operation!='import':
            raise ValueError('--reimport requires import')
        if args.reference_results and (args.operation!='query' or not args.verify_results):
            raise ValueError('--reference-results requires query --verify-results')
        if (args.dataset or args.query) and args.operation!='query':
            raise ValueError('--dataset/--query select queries; import always mixes the complete manifest')
        if args.update_rows < 1:
            raise ValueError('--update-rows must be positive')
        if args.operation == 'update' and (args.warmups != 0 or args.runs != 1):
            raise ValueError('Update replaces each selected row once: use --warmups 0 --runs 1')
        if args.restart_postgres and (args.operation!='restore' or
                args.system not in ('specson','jsonb') or args.warmups!=0 or args.runs!=1):
            raise ValueError('--restart-postgres requires PG/SpecSON restore with --warmups 0 --runs 1')
        output = args.result_output = RunOutput(args.output,result_variant(args),args.operation)
        args.state_dir.mkdir(parents=True,exist_ok=True)
        with (args.state_dir/'.run.lock').open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if args.restart_postgres:
                from prepare_postgres import prepare
                setup=SimpleNamespace(action='stop',cores=1,
                    port=CONNECTIONS[args.system]['connection']['port'],
                    runtime_dir=HERE/'runtime/postgres-mixed')
                output.value['setup']={'status':'running','database_buffers_reset':True}
                output.checkpoint([])
                prepare(setup)
                setup.action='start'
                output.value['setup']=prepare(setup)
                output.value['setup']['database_buffers_reset']=True
                output.checkpoint([])
            records = run(args)
        output.finish('completed_with_oom' if any(r.get('status')=='oom' for r in records) else 'ok',records=records)
        return 0
    except (Exception,KeyboardInterrupt) as error:
        if output is not None:
            output.finish('interrupted' if isinstance(error,KeyboardInterrupt) else 'error',
                          error=str(error) or 'Interrupted')
        else:
            emit_result(None,dict(status='error',error=str(error) or 'Interrupted',timestamp=stamp()))
        return 1


if __name__=='__main__':
    sys.exit(main())
