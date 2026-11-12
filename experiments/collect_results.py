#!/usr/bin/env python3
"""Collect a complete reproduction run into one final result file."""
import argparse
import json
from pathlib import Path

from compare_queries import compare
from protocol import atomic_json
from run_memory_sweep import validate
from run import queries as parse_queries

SINGLE={'pg','specson','specson-toast','umbra','mongodb','asterix','clickhouse'}
MIXED={'jsonb','specson','specson-toast','umbra','mongodb','asterix'}
DATASETS=('github','yelp-business','twitter','tpch','openalex')


def collect(root, destination):
    configuration=root/'run-config.json'
    scope=json.loads(configuration.read_text()) if configuration.exists() else dict(datasets=list(DATASETS),skip_twitter=False)
    datasets=[d for d in DATASETS if not (scope['skip_twitter'] and d=='twitter')]
    if scope['datasets']!=datasets: raise ValueError('Invalid dataset selection')
    expected_queries={q for d in datasets for q,_ in parse_queries((Path(__file__).parent/'sql'/d/'pg.sql').read_text())}
    runs={}; queries={'single':[],'mixed':[]}
    memory_protocols=[p for p in root.rglob('protocol.json') if 'completed' in json.loads(p.read_text())]
    memory_roots=[p.parent for p in memory_protocols]
    for path in sorted(root.rglob('*.json')):
        if path.resolve()==destination.resolve(): continue
        if any(path.is_relative_to(folder) for folder in memory_roots): continue
        data=json.loads(path.read_text())
        operation=data.get('operation')
        if operation not in ('import','restore','query','update','reclaim','build-gin'): continue
        if data.get('status')!='ok': raise ValueError('Incomplete experiment: '+str(path))
        if operation=='query':
            # Memory groups are collected and validated through their protocol.
            if any(parent.name.endswith('g') and parent.name[:-1].isdigit() for parent in path.parents): continue
            kind='mixed' if {r['dataset'] for r in data['results']}=={'mixed'} else 'single'
            queries[kind].append(path);continue
        for row in data['results']:
            key=(operation,data['system'],row['dataset'])
            if key in runs: raise ValueError('Duplicate measurement: '+str(key))
            if row.get('status','ok')!='ok': raise ValueError('Incomplete measurement: '+str(key))
            runs[key]=row

    def get(op,system,dataset):
        try: return runs[(op,system,dataset)]
        except KeyError: raise ValueError(f'Missing {op}: {system}/{dataset}') from None

    def seconds(row): return row['statistics']['median_ms']/1000

    single=[]
    for dataset in datasets:
        imports={s:get('import',s,dataset) for s in SINGLE}
        restores={s:get('restore',s,dataset) for s in SINGLE}
        if len({r['rows'] for r in imports.values()})!=1: raise ValueError('Import row counts differ')
        gin=get('build-gin','pg-gin',dataset)
        single.append(dict(dataset=dataset,rows=imports['pg']['rows'],
            import_seconds={s:seconds(r) for s,r in imports.items()},
            restore_seconds={s:seconds(r) for s,r in restores.items()},
            storage_bytes={s:r['storage']['disk_bytes'] for s,r in imports.items()},
            schema_registration_seconds=imports['specson']['schema_registration_ms']/1000,
            gin_build_seconds=gin['build_ms']/1000,gin_index_bytes=gin['index_bytes']))
    imports={s:get('import',s,'mixed') for s in MIXED}
    if len({r['rows'] for r in imports.values()})!=1:
        raise ValueError('Mixed import row counts differ')
    restores={s:get('restore',s,'mixed') for s in MIXED}
    gin=get('build-gin','pg-gin','mixed')
    mixed=dict(status='ok',rows=imports['jsonb']['rows'],
        schemas=imports['specson']['registered_schemas'],
        import_seconds={s:seconds(r) for s,r in imports.items()},
        restore_seconds={s:seconds(r) for s,r in restores.items()},
        storage_bytes={s:r['storage']['disk_bytes'] for s,r in imports.items()},
        schema_storage_bytes={s:r['storage'].get('shared_schema_store',{}).get('disk_bytes',0) for s,r in imports.items()},
        schema_registration_seconds={s:imports[s]['schema_registration_ms']/1000 for s in ['specson','specson-toast']},
        gin_build_seconds=gin['build_ms']/1000,gin_index_bytes=gin['index_bytes'])
    mixed['import_seconds']['pg-gin']=mixed['import_seconds']['jsonb']+mixed['gin_build_seconds']
    mixed['storage_bytes']['pg-gin']=mixed['storage_bytes']['jsonb']+gin['index_bytes']
    mixed['restore_seconds']['pg-gin']=None
    mixed['schema_storage_bytes']['pg-gin']=0
    mixed['document_storage_bytes']=dict(mixed['storage_bytes'])
    comparisons={}
    for kind,systems in [('single',SINGLE|{'pg-gin'}),('mixed',MIXED|{'pg-gin'})]:
        result=compare(queries[kind])
        if (result['queries']!=len(expected_queries)
                or {r['query'] for r in result['results']}!=expected_queries or set(result['summary'])!=systems):
            raise ValueError('Incomplete query matrix: '+kind)
        comparisons[kind]={k:v for k,v in result.items() if k!='sources'}
        base='pg' if kind=='single' else 'jsonb'
        signatures={}
        for path in queries[kind]:
            data=json.loads(path.read_text())
            if data['system']==base:
                signatures.update({r['query']:r['result_signature'] for r in data['results']})
        comparisons[kind]['reference']=dict(system=base,warmups=1,runs=3,signatures=signatures)
    updates=[]
    labels={'specson':'SpecSON','specson-toast':'SpecSON-TOAST','jsonb':r'\texttt{jsonb}',
            'umbra':'Umbra','mongodb':'MongoDB','asterix':'AsterixDB'}
    for system in labels:
        update=get('update',system,'mixed');reclaim=get('reclaim',system,'mixed')
        if update['generation']!=imports[system]['generation']:
            raise ValueError('Update is from another import: '+system)
        if update['generation']!=reclaim['generation'] or update['output_revision']!=reclaim['input_revision']:
            raise ValueError('Reclamation is from another update: '+system)
        updates.append(dict(system=system,label=labels[system],seconds=seconds(update),before_bytes=update['storage_before']['disk_bytes'],
            after_bytes=update['storage_after']['disk_bytes'],reclaimed_bytes=reclaim['storage_after']['disk_bytes']))
    counts={get('update',s,'mixed')['updated_rows'] for s in MIXED}
    if len(counts)!=1: raise ValueError('Updated row counts differ')
    protocols=[p for p in memory_protocols if json.loads(p.read_text())['status']=='complete']
    if len(protocols)!=1: raise ValueError('Expected one complete memory sweep')
    protocol=json.loads(protocols[0].read_text())
    if protocol['status']!='complete' or set(protocol['memory_gib'])!={1,2,4,8,16,32} or set(protocol['systems'])!=MIXED|{'pg-gin'}:
        raise ValueError('Incomplete memory sweep')
    reference={}
    for path in queries['mixed']:
        data=json.loads(path.read_text())
        if data['system']=='jsonb': reference.update({r['query']:r['result_signature'] for r in data['results']})
    selected={q:reference[q] for q in ['G-C1-1','G-C2-1','G-C3-1','G-C4-1']}
    if len(protocol['completed'])!=42: raise ValueError('Incomplete memory groups')
    if {(r['memory_gib'],r['system']) for r in protocol['completed']}!={(g,s) for g in [1,2,4,8,16,32] for s in MIXED|{'pg-gin'}}:
        raise ValueError('Duplicate or missing memory groups')
    for item in protocol['completed']:
        proof=validate(Path(item['path']),item['memory_gib'],item['system'],selected)
        if proof['sha256']!=item['sha256']: raise ValueError('Changed memory measurement')
    memory={}
    for gib in [1,2,4,8,16,32]:
        d=json.loads((protocols[0].parent/f'{gib}g/comparison.json').read_text())
        memory[str(gib)]={k:v for k,v in d.items() if k not in ('sources','reference_64g')}
    totals={field:{s:sum(row[field][s] for row in single) for s in SINGLE}
            for field in ('import_seconds','restore_seconds','storage_bytes')}
    totals.update({field:sum(row[field] for row in single)
                   for field in ('schema_registration_seconds','gin_build_seconds','gin_index_bytes')})
    schema_bytes={s:sum(get('import',s,d)['storage']['shared_schema_store']['disk_bytes'] for d in datasets)
                  for s in ('specson','specson-toast')}
    totals['shared_schema_store_bytes']=schema_bytes['specson']
    return dict(status='ok',format_version=2,datasets=datasets,
        single=dict(measurements=dict(status='ok',results=single,summary=totals,
            native_toast_shared_schema_store_bytes=schema_bytes['specson-toast']),queries=comparisons['single']),
        mixed=dict(measurements=mixed,queries=comparisons['mixed']),
        memory=dict(status='complete',by_gib=memory,reference_gib=64),
        updates=dict(status='ok',updated_rows=counts.pop(),results=updates))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): raise ValueError('Output already exists')
    atomic_json(args.output,collect(args.directory,args.output))


if __name__=='__main__': main()
