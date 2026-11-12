"""Measure physical storage after the paper's reclamation operations."""
from collections import Counter
import re
import time

from mixed_update import flush_storage, prefix_count
from protocol import measure, result_signature
from umbra_runtime import docker


def snapshot(adapter, table, ids):
    if adapter.system == 'mongodb':
        rows = list(adapter.collection(table).find({'doc_id': {'$in': ids}}))
    elif adapter.system == 'asterix':
        rows = adapter.command(f'SELECT VALUE d FROM {table} d WHERE d.doc_id IN '
                               + str(ids))['results']
    else:
        doc = 'doc::text' if adapter.system == 'specson' else 'doc'
        rows = adapter.command(f'SELECT doc_id,source_id,source_no,{doc} FROM {table} '
                               'WHERE doc_id IN ('+','.join(map(str, ids))+')').fetchall()
    signature = result_signature([[row] for row in rows])
    if signature['rows'] != len(ids):
        raise RuntimeError('Reclamation sample is incomplete')
    return signature


def wait_merge(adapter, table, timeout=600):
    deadline = time.monotonic()+timeout
    while True:
        files = [p for p in adapter.dataset_paths(table) if re.fullmatch(r'\d+_\d+_b', p.name)]
        counts = Counter(p.parent for p in files)
        if counts and all(n == 1 for n in counts.values()):
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('AsterixDB full merge did not complete')
        time.sleep(.2)


def run_reclaim(adapter, table, state, results, storage, system):
    if state['revision'] != 1 or state.get('reclaimed'):
        raise ValueError('Reclamation requires one completed update and no previous reclamation')
    count = state['rows']
    edge = state['last_update']['rows']
    ids = sorted({i for i in [0, 700, edge-1, edge, count-1] if 0 <= i < count})
    flush_storage(adapter, table)
    before = snapshot(adapter, table, ids)
    record = dict(system=system, dataset='mixed', operation='reclaim', status='running',
                  generation=state['generation'], input_revision=state['revision'],
                  metadata=adapter.meta, storage_before=storage(), steps=[])
    results.checkpoint(record)
    if adapter.system in ('specson','pg','jsonb','umbra'):
        methods = ['VACUUM FULL'] if system.startswith('specson') else ['VACUUM','VACUUM FULL']
        for method in methods:
            elapsed, _ = measure(lambda: adapter.command(method+' '+table), lambda _: None)
            record['steps'].append(dict(method=method, elapsed_ms=elapsed))
    elif adapter.system == 'mongodb':
        col = adapter.collection(table)
        elapsed, value = measure(lambda: col.database.command('compact', col.name), lambda x: x)
        record['steps'].append(dict(method='compact', elapsed_ms=elapsed, return_value=value))
    else:
        elapsed, _ = measure(lambda: adapter.command('COMPACT DATASET '+table), lambda _: None)
        wait_merge(adapter, table)
        record['steps'].append(dict(method='COMPACT DATASET', submission_ms=elapsed))
    flush_storage(adapter, table)
    if adapter.system == 'asterix':
        wait_merge(adapter, table)
    if snapshot(adapter, table, ids) != before or prefix_count(adapter, table, count) != count:
        raise RuntimeError('Reclamation changed documents or row count')
    if adapter.system == 'asterix':
        docker('stop', adapter.config['container'])
    record.update(status='ok', storage_after=storage(), verified_rows=count, verified_doc_ids=ids)
    record['released_bytes'] = record['storage_before']['disk_bytes']-record['storage_after']['disk_bytes']
    state['reclaimed'] = True
    results.save_state('mixed', state)
    results.save(record)
