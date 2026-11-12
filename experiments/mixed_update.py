"""Replace a mixed-table prefix with cyclic OpenAlex Work input."""
import orjson

from engines import literal, source_rows
from protocol import measure, stamp, statistics_ms

BATCH_ROWS = 1000
BATCH_BYTES = 8 * 1024**2


def replacement_batches(source, count):
    """doc_id i receives source row i % source['rows']; never cache the input pool."""
    ident = 0
    batch, size = [], 0
    while ident < count:
        stream = source_rows(source['files'], source.get('replace_nul', False))
        seen = 0
        try:
            for number, text in stream:
                if number >= source['rows']:
                    raise ValueError('OpenAlex input has more rows than its manifest')
                # OpenAlex contains duplicate keys. Every engine gets the same
                # last-key-wins document, including AsterixDB and MongoDB.
                text = orjson.dumps(orjson.loads(text))
                if batch and (len(batch) >= BATCH_ROWS or size + len(text) > BATCH_BYTES):
                    yield batch
                    batch, size = [], 0
                batch.append((ident, number, text))
                size += len(text)
                ident += 1
                seen += 1
                if ident == count:
                    break
            if ident < count and seen != source['rows']:
                raise ValueError('OpenAlex input has fewer rows than its manifest')
        finally:
            stream.close()
    if batch:
        yield batch


def update_sql(system, table, batch, source_id, schema_id):
    values = ','.join(f'({ident},{number},{literal(text.decode())})' for ident, number, text in batch)
    value = f'specson.specson_encode({schema_id},source.doc)' if system == 'specson' else 'source.doc::jsonb'
    schema = f',schema_id={schema_id}' if system == 'specson' else ''
    return (f'UPDATE {table} AS target SET doc={value},source_id={source_id},'
            f'source_no=source.source_no{schema} FROM (VALUES {values}) '
            'AS source(doc_id,source_no,doc) WHERE target.doc_id=source.doc_id '
            f'AND target.doc_id >= {batch[0][0]} AND target.doc_id <= {batch[-1][0]}')


def replace_batch(adapter, table, batch, source_id, schema_id):
    if adapter.system == 'mongodb':
        from pymongo import UpdateOne
        updates = [UpdateOne({'_id':ident}, {'$set':dict(source_id=source_id, source_no=number,
                   doc=orjson.loads(text))}, upsert=False) for ident, number, text in batch]
        return adapter.collection(table).bulk_write(updates, ordered=True).matched_count
    if adapter.system == 'asterix':
        documents = [dict(doc_id=ident, source_id=source_id, source_no=number, doc=orjson.loads(text))
                     for ident, number, text in batch]
        # The prefix is checked before writing: every primary key already exists.
        # Bind text and parse at execution: 0.9.9's structured parameter decoder
        # fails on some nested records. This also avoids compiling object literals.
        payload = orjson.dumps(documents).decode()
        response = adapter.request(f'UPSERT INTO {table} (SELECT VALUE d FROM parse_json($batch) d)',
                                   parameters={'$batch':orjson.dumps(payload).decode()})
        adapter.decode(response.content)  # synchronous success includes the writes
        return len(batch)
    return adapter.update(update_sql(adapter.system, table, batch, source_id, schema_id))


def prefix_count(adapter, table, count):
    if adapter.system == 'mongodb':
        return adapter.collection(table).count_documents({'_id':{'$gte':0,'$lt':count},
            '$expr':{'$eq':['$_id','$doc_id']}})
    if adapter.system == 'asterix':
        return adapter.command(f'SELECT VALUE count(*) FROM {table} d '
                               f'WHERE d.doc_id >= 0 AND d.doc_id < {count}')['results'][0]
    return adapter.command(f'SELECT count(*) FROM {table} WHERE doc_id >= 0 AND doc_id < {count}').fetchone()[0]


def flush_storage(adapter, table):
    if adapter.system == 'umbra':
        # This Umbra build has no CHECKPOINT command. Its buffer manager flushes
        # on orderly shutdown; restart the owned instance with identical settings.
        import json
        from umbra_runtime import activate, docker
        if adapter.command('SHOW debug.bm_flush_on_shutdown').fetchone()[0] != 'on':
            raise RuntimeError('Umbra must flush its buffer manager on shutdown')
        config, namespace = adapter.config, adapter.namespace
        cores, cpus = adapter.meta['cores'], set(adapter.meta['backend_cpus'])
        container = config['managed_container']
        adapter.close()
        docker('stop','--timeout','600',container)
        if json.loads(docker('inspect',container))[0]['State']['ExitCode'] != 0:
            raise RuntimeError('Umbra did not shut down cleanly for its storage measurement')
        config = activate(config,'mixed',cpus)
        adapter.__init__('umbra',config,namespace,cores,cpus)
        return 'orderly restart with bm_flush_on_shutdown=on'
    if adapter.system == 'mongodb':
        adapter.client.admin.command('fsync')
        return 'fsync'
    if adapter.system == 'asterix':
        # 0.9.9 ConnectorApiServlet synchronously calls FlushDatasetUtil before
        # returning file splits; this flushes without requesting compaction.
        namespace, dataset = table.split('.')
        response = adapter.session.get(adapter.config['url']+'/connector',
            params=dict(dataverseName=namespace, datasetName=dataset), timeout=3600)
        response.raise_for_status()
        result = response.json()
        if 'error' in result or not result.get('splits'):
            raise RuntimeError('AsterixDB dataset flush failed: '+str(result))
        return 'connector synchronous dataset flush'
    adapter.command('CHECKPOINT')
    return 'CHECKPOINT'


def run_update(adapter, table, datasets, state, results, storage, limit, result_system):
    if state['revision'] != 0:
        raise ValueError('Update requires the original imported table; reimport before another update run')
    source_id, source = next(((i,d) for i,d in enumerate(datasets,1) if d['name']=='openalex'), (None,None))
    if source is None:
        raise ValueError('The mixed manifest must contain the OpenAlex Work dataset (openalex)')
    count = min(limit, state['rows'])
    record = dict(system=result_system, dataset='mixed', operation='update', query='update',
        status='running', started_at=stamp(), generation=state['generation'], input_revision=state['revision'],
        warmups=0, runs=1, metadata=adapter.meta, rows=count, table_rows=state['rows'],
        target=f'0 <= doc_id < {count}', replacement_source=source['name'],
        replacement_signature=source['signature'], source_rows=source['rows'],
        mapping='OpenAlex source_no = doc_id % source_rows',
        batch_rows=BATCH_ROWS, batch_bytes=BATCH_BYTES,
        metric='source read/normalization + request serialization/transfer + lookup/encoding/update/index maintenance + commit or acknowledged writes',
        storage_metric='whole table after synchronous flush, with existing indexes; no explicit vacuum, reclaim or compaction; shared schema storage separate')
    results.checkpoint(record)
    try:
        if adapter.system not in ('mongodb','asterix'):
            # A per-batch sequential scan would repeatedly read the whole mixed
            # table. All relational systems receive the same doc_id index.
            index = table.split('.')[1]+'_update_doc_id_idx'
            record['index_setup_ms'], _ = measure(lambda: adapter.command(
                f'CREATE UNIQUE INDEX IF NOT EXISTS {index} ON {table}(doc_id)'), lambda _:None)
            record['lookup_index'] = index
        else:
            record['lookup_index'] = '_id' if adapter.system == 'mongodb' else 'doc_id primary key'
        if prefix_count(adapter, table, count) != count:
            raise RuntimeError('Update prefix must contain every doc_id exactly once')
        schema_id = None
        if adapter.system == 'specson':
            lo, hi = adapter.command(f'SELECT min(schema_id),max(schema_id) FROM {table} '
                                     f'WHERE source_id={source_id}').fetchone()
            if lo is None or lo != hi:
                raise RuntimeError('Cannot identify the imported OpenAlex schema')
            schema_id = lo
            record['replacement_schema_id'] = schema_id
        flush_storage(adapter, table)
        record['metadata'] = adapter.meta
        record['storage_before'] = storage()
        state['status'] = 'updating'
        results.save_state('mixed', state)
        results.checkpoint(record)

        def replace():
            updated = batches = 0
            for batch in replacement_batches(source, count):
                matched = replace_batch(adapter, table, batch, source_id, schema_id)
                if matched != len(batch):
                    raise RuntimeError(f'Update matched {matched} rows, expected {len(batch)}')
                updated += matched
                batches += 1
            return dict(updated_rows=updated, batches=batches)

        elapsed, info = measure(replace, lambda value:value)
        record.update(info, elapsed_ms=elapsed, statistics=statistics_ms([elapsed]))
        if info['updated_rows'] != count or prefix_count(adapter, table, count) != count:
            raise RuntimeError('Incomplete prefix update')
        state.update(status='ok', revision=state['revision']+1,
                     last_update=dict(rows=count, source='openalex', source_rows=source['rows']))
        results.save_state('mixed', state)
        record['output_revision'] = state['revision']
        results.checkpoint(record)
        record['storage_flush_ms'], record['storage_flush'] = measure(
            lambda: flush_storage(adapter, table), lambda value:value)
        record['storage_after'] = record['storage'] = storage()
        record['storage_growth_bytes'] = record['storage_after']['disk_bytes']-record['storage_before']['disk_bytes']
        record['status'] = 'ok'
        results.save(record)
    except BaseException as error:
        record.update(status='error', error=str(error))
        results.save(record)
        raise
