#!/usr/bin/env python3
"""Run the complete paper experiment sequence and collect its final results."""
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import psycopg

from collect_results import collect
from compare_queries import compare
from protocol import atomic_json
from prepare_postgres import prepare
from types import SimpleNamespace
from run import CONNECTIONS, dataset_manifest, load_dataset
from run_memory_sweep import stop_databases
from runtime_cleanup import release

HERE=Path(__file__).resolve().parent


def run(args):
    manifest=dataset_manifest(args.data_dir,args.skip_twitter)
    datasets=[d['name'] for d in manifest]
    expected={'github','yelp-business','tpch','openalex'} | (set() if args.skip_twitter else {'twitter'})
    if set(datasets)!=expected or len(datasets)!=len(expected):
        raise ValueError('Dataset manifest does not match the selected experiment suite')
    for item in manifest:load_dataset(args.data_dir,item)
    selection=['--skip-twitter'] if args.skip_twitter else []
    if any((HERE/'runtime').glob('state*/**/import-state.json')):
        raise ValueError('Run the complete sequence from fresh database state')
    root=args.output_dir.resolve()
    root.mkdir(parents=True,exist_ok=False)
    atomic_json(root/'run-config.json',dict(datasets=datasets,skip_twitter=args.skip_twitter))
    prefix='repro_'+hashlib.sha256(str(root).encode()).hexdigest()[:10]
    mixed_databases={system:prefix+'_mixed_'+system.replace('-','_')
                     for system in ('jsonb','specson','specson-toast')}
    for system,database in mixed_databases.items():
        key='TOAST' if system=='specson-toast' else system.upper()
        os.environ['SPECSON_MIXED_'+key+'_DATABASE']=database
    records=root/'measurements';records.mkdir()
    counter=0

    def execute(script, label, *options, database=None):
        output=records/(label+'.json')
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
        if database: env['SPECSON_SINGLE_DATABASE']=database
        command=[sys.executable,str(HERE/script),*map(str,options),'--output',str(output)]
        if script in ('run.py','run_mixed.py','benchmark_gin.py'):
            command+=selection
        result=subprocess.run(command,env=env,capture_output=True,text=True)
        if result.returncode:
            data=json.loads(output.read_text()) if output.exists() else {}
            raise RuntimeError(label+': '+data.get('error',result.stderr[-3000:]))
        print(label,flush=True)
        return output

    def pg(action, cores, mixed=False):
        nonlocal counter
        counter+=1
        port=56539 if mixed else 56529
        runtime=HERE/'runtime'/('postgres-mixed' if mixed else 'postgres')
        execute('prepare_postgres.py',f'setup-{counter}',action,'--cores',cores,
                '--port',port,'--runtime-dir',runtime,'--memory-gib',64)

    def create(database, port=56529):
        with psycopg.connect(host='/tmp',port=port,user=getpass.getuser(),dbname='postgres',autocommit=True) as c:
            c.execute('CREATE DATABASE '+database)

    queries={'single':[],'mixed':[]}
    try:
        stop_databases()
        if not Path(CONNECTIONS['asterix']['distribution']).exists():
            execute('prepare_asterix.py','asterix-install','install')
        for system in ['pg','specson','specson-toast']:
            options=['--system','pg' if system=='pg' else 'specson']
            if system=='specson-toast':options+=['--specson-storage','toast']
            pg('start',1)
            common=prefix+'_pg'
            if system=='pg':create(common)
            for dataset in datasets:
                database=common if system=='pg' else prefix+'_'+system.replace('-','_')+'_'+dataset.replace('-','_')
                if system!='pg':create(database)
                for operation in ['import','restore','query']:
                    if operation!='import':
                        pg('stop',1);pg('start',4 if operation=='query' else 1)
                    path=execute('run.py',f'single-{system}-{dataset}-{operation}',*options,operation,
                        '--dataset',dataset,'--data-dir',args.data_dir,
                        *(['--verify-results'] if operation=='query' else []),database=database)
                    if operation=='query':queries['single'].append(path)
                pg('stop',1);pg('start',1)
            if system=='pg':
                execute('benchmark_gin.py','single-gin-build','--data-dir',args.data_dir,database=common)
                pg('stop',1);pg('start',4)
                queries['single'].append(execute('run.py','single-pg-gin-query','--system','pg','--gin','--reuse-pg',
                    'query','--verify-results','--data-dir',args.data_dir,database=common))
            pg('stop',1)
        for system in ['umbra','mongodb','asterix','clickhouse']:
            stop_databases()
            if system=='clickhouse':execute('prepare_clickhouse.py','clickhouse-start','start')
            for operation in ['import','restore','query']:
                path=execute('run.py',f'single-{system}-{operation}','--system',system,operation,
                    '--data-dir',args.data_dir,*(['--verify-results'] if operation=='query' else []))
                if operation=='query':queries['single'].append(path)
            if system=='clickhouse':execute('prepare_clickhouse.py','clickhouse-stop','stop')
        stop_databases()
        atomic_json(root/'single-comparison.json',compare(queries['single']))
        release(HERE/'runtime',['postgres','umbra','clickhouse','mongodb/data','asterix/data','state'])
        mixed_reference=None
        for system in ['jsonb','specson','specson-toast','umbra','mongodb','asterix']:
            stop_databases()
            pg_system=system in ('jsonb','specson','specson-toast')
            if pg_system:
                pg('start',1,True)
                create(mixed_databases[system],56539)
            options=['--system','specson' if system=='specson-toast' else system]
            if system=='specson-toast':options+=['--specson-storage','toast']
            for operation in ['import','restore','query']:
                if pg_system and operation=='query':pg('stop',1,True);pg('start',4,True)
                extra=['--restart-postgres'] if pg_system and operation=='restore' else []
                if operation=='query':
                    extra+=['--verify-results']
                    if mixed_reference:extra+=['--reference-results',mixed_reference]
                path=execute('run_mixed.py',f'mixed-{system}-{operation}',*options,operation,
                    '--data-dir',args.data_dir,'--synthetic-dir',args.data_dir/'synthetic',*extra)
                if operation=='query':
                    queries['mixed'].append(path)
                    if system=='jsonb':mixed_reference=path
            if pg_system:pg('stop',1,True)
        stop_databases();pg('start',1,True)
        execute('benchmark_gin.py','mixed-gin-build','--mixed')
        pg('stop',1,True);pg('start',4,True)
        queries['mixed'].append(execute('run_mixed.py','mixed-pg-gin-query','--system','jsonb','--gin','query',
            '--verify-results','--reference-results',mixed_reference,'--data-dir',args.data_dir,
            '--synthetic-dir',args.data_dir/'synthetic'))
        pg('stop',1,True)
        for kind in queries:atomic_json(root/(kind+'-comparison.json'),compare(queries[kind]))
        subprocess.run([sys.executable,str(HERE/'run_memory_sweep.py'),'--output-dir',str(root/'memory'),
            '--reference-results',str(mixed_reference),'--comparison-results',str(root/'mixed-comparison.json'),
            '--data-dir',str(args.data_dir),*selection,'--query','G-C1-1','--query','G-C2-1','--query','G-C3-1','--query','G-C4-1'],check=True)
        for system in ['jsonb','specson','specson-toast','umbra','mongodb','asterix']:
            stop_databases()
            pg_system=system in ('jsonb','specson','specson-toast')
            if pg_system:pg('start',4,True)
            if system=='jsonb':
                with psycopg.connect(host='/tmp',port=56539,user=getpass.getuser(),dbname=mixed_databases['jsonb'],autocommit=True) as c:
                    c.execute('DROP INDEX specson_mixed_experiment.jsonb_mixed_doc_gin')
            options=['--system','specson' if system=='specson-toast' else system]
            if system=='specson-toast':options+=['--specson-storage','toast']
            for operation in ['update','reclaim']:
                execute('run_mixed.py',f'mixed-{system}-{operation}',*options,operation,
                    '--data-dir',args.data_dir,'--synthetic-dir',args.data_dir/'synthetic',
                    '--memory-gib',64,'--update-rows',args.update_rows)
            if pg_system:pg('stop',1,True)
        stop_databases()
        release(HERE/'runtime',['postgres-mixed','umbra-mixed','mongodb/data','asterix/data','state-mixed'])
        atomic_json(root/'results.json',collect(root,root/'results.json'))
    finally:
        stop_databases()
        prepare(SimpleNamespace(action='stop',port=56529,runtime_dir=HERE/'runtime/postgres'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--data-dir',type=Path,default=HERE.parent/'datasets')
    parser.add_argument('--skip-twitter',action='store_true',help='Run the suite without Twitter data')
    parser.add_argument('--update-rows',type=int,default=1000000)
    args=parser.parse_args()
    args.data_dir=args.data_dir.resolve()
    run(args)


if __name__=='__main__':main()
