"""Bounded mixed-table input and adapters shared by the formal mixed runner."""
from array import array
import heapq
import itertools
import json
from pathlib import Path
import random
import struct

import psycopg

from engines import Postgres, source_rows, UMBRA_COPY_OPTIONS, UMBRA_COPY_BATCH_ROWS, append_umbra_json

CHUNK_BYTES = 1024 * 1024
BLOCK_ROWS = 100
MIXED_SEED = 20261105
MIXED_ORDER = 'merge (ordinal + seeded schema phase) / schema document count'


def mixed_schedule(counts, seed=MIXED_SEED):
    """Merge equally spaced schema positions without retaining the full order."""
    rng = random.Random(seed)
    phases = [rng.random() for _ in counts]
    heap = [(phases[i]/count, i, 0) for i,count in enumerate(counts) if count]
    heapq.heapify(heap)
    while heap:
        _, index, ordinal = heap[0]
        yield index, ordinal
        ordinal += 1
        if ordinal < counts[index]:
            heapq.heapreplace(heap, ((ordinal+phases[index])/counts[index], index, ordinal))
        else:
            heapq.heappop(heap)


def mixed_rows(datasets, synthetic_file, synthetic_count, schema_ids=None):
    """Yield doc_id, source_id, source_no, schema_id, JSON bytes.

    Preserve the original population and merge each schema's equally spaced
    positions. Synthetic counts retain the old pool-cycle multiplicities;
    source_no identifies the original row even after interleaving changes.
    Real documents stream from disk; the one-document-per-schema synthetic
    pool is retained in memory for reuse.
    """
    streams = [source_rows(d['files'], d.get('replace_nul', False)) for d in datasets]
    counts = [d['rows'] for d in datasets] + [0] * synthetic_count
    payloads = [None] * synthetic_count
    pool_positions = [0] * synthetic_count
    try:
        if synthetic_count:
            total = max((d['rows']+BLOCK_ROWS-1)//BLOCK_ROWS for d in datasets) * BLOCK_ROWS
            cycles, remainder = divmod(total, synthetic_count)
            with Path(synthetic_file).open('rb') as synthetic:
                for pool_index in range(synthetic_count):
                    line = synthetic.readline()
                    if not line:
                        raise ValueError('Synthetic file has fewer rows than declared')
                    item = json.loads(line)
                    if not 1 <= item['schema_no'] <= synthetic_count:
                        raise ValueError('Synthetic schema number out of range')
                    index = item['schema_no'] - 1
                    if payloads[index] is not None:
                        raise ValueError('Duplicate synthetic schema number')
                    payloads[index] = json.dumps(item['doc'], ensure_ascii=False, separators=(',', ':')).encode()
                    pool_positions[index] = pool_index
                    counts[len(datasets)+index] = cycles + (pool_index < remainder)
                if synthetic.readline():
                    raise ValueError('Synthetic file has more rows than declared')
        for ident, (index, ordinal) in enumerate(mixed_schedule(counts)):
            logical = index + 1
            if index < len(datasets):
                row = next(streams[index], None)
                if row is None:
                    raise ValueError('Source row count mismatch: '+datasets[index]['name'])
                source_no, text = row
                source = logical
            else:
                pool_index = index - len(datasets)
                source_no = ordinal * synthetic_count + pool_positions[pool_index]
                text = payloads[pool_index]
                source = 0
            yield (ident, source, source_no,
                   schema_ids[logical] if schema_ids is not None else logical, text)
        for index, stream in enumerate(streams):
            if next(stream, None) is not None:
                raise ValueError('Too many source rows: '+datasets[index]['name'])
    finally:
        for stream in streams:
            stream.close()


def copy_chunks(rows, binary, limit=CHUNK_BYTES, specson=False):
    buf = bytearray(b'PGCOPY\n\xff\r\n\0' + struct.pack('!ii', 0, 0) if binary else b'')
    for ident, source, source_no, schema, text in rows:
        if binary:
            buf.extend(struct.pack('!h', 5 if specson else 4))
            for fmt, value in [('q', ident), ('i', source), ('q', source_no)]:
                value = struct.pack('!'+fmt, value)
                buf.extend(struct.pack('!i', len(value)))
                buf.extend(value)
            if specson:
                buf.extend(struct.pack('!ii',4,schema))
            buf.extend(struct.pack('!i', len(text)+(5 if specson else 1)))
            buf.extend(b'\x02'+struct.pack('!i',schema) if specson else b'\x01')
            buf.extend(text)
        else:
            buf.extend(f'{ident}\x1f{source}\x1f{source_no}\x1f'.encode())
            append_umbra_json(buf,text)
            buf.extend(b'\n')
        if len(buf) >= limit:
            yield bytes(buf)
            buf.clear()
    if binary:
        buf.extend(struct.pack('!h', -1))
    if buf:
        yield bytes(buf)


class MixedPostgres(Postgres):
    def ingest_mixed(self, table, rows):
        if self.system == 'umbra':
            for first in rows:
                batch = itertools.chain((first,), itertools.islice(rows, UMBRA_COPY_BATCH_ROWS - 1))
                self._copy_mixed(table,batch)
        else:
            self._copy_mixed(table,rows)

    def _copy_mixed(self, table, rows):
        with self.c.transaction():
            binary = self.system != 'umbra'
            columns='doc_id,source_id,source_no,'+('schema_id,' if self.system=='specson' else '')+'doc'
            with self.c.cursor().copy(f'COPY {table}({columns}) FROM STDIN'
                                      + (' (FORMAT binary)' if binary else UMBRA_COPY_OPTIONS)) as stream:
                for chunk in copy_chunks(rows, binary, specson=self.system=='specson'):
                    stream.write(chunk)
                    # PQputCopyData may accept a chunk into libpq without sending
                    # it. Wait for PQflush==0 before requesting the next chunk.
                    self.c.wait(psycopg.generators.send(self.c.pgconn))

    def validate_mixed(self, table, datasets, synthetic_rows):
        rows = self.command(f'''SELECT source_id,count(*),min(source_no),max(source_no)
            FROM {table} GROUP BY source_id ORDER BY source_id''').fetchall()
        expected = [(0, synthetic_rows, 0, synthetic_rows-1)] if synthetic_rows else []
        expected += [(i, d['rows'], 0, d['rows']-1) for i,d in enumerate(datasets, 1)]
        if rows != expected:
            raise RuntimeError('Mixed source/sequence validation failed: '+str(rows))
        count = sum(d['rows'] for d in datasets)+synthetic_rows
        actual = self.command(f'SELECT count(*),count(DISTINCT doc_id),min(doc_id),max(doc_id) FROM {table}').fetchone()
        if tuple(actual) != (count, count, 0, count-1):
            raise RuntimeError('Mixed doc_id validation failed: '+str(actual))


def mongo_ingest(adapter, table, rows):
    from bson.raw_bson import RawBSONDocument
    col = adapter.collection(table)
    batch, size = [], 0
    for ident, source, source_no, schema, text in rows:
        envelope = (f'{{"_id":{ident},"doc_id":{ident},"source_id":{source},'
                    f'"source_no":{source_no},"doc":').encode()+text+b'}'
        raw = adapter.bsonjs.loads(envelope)
        if batch and size + len(raw) > 8*1024**2:
            col.insert_many(batch, ordered=True)
            batch, size = [], 0
        batch.append(RawBSONDocument(raw))
        size += len(raw)
        if size >= 8*1024**2 or len(batch) >= 10000:
            col.insert_many(batch, ordered=True)
            batch, size = [], 0
    if batch:
        col.insert_many(batch, ordered=True)
    # Each call waits for the adapter's acknowledged journaled write concern.


def mongo_validate(adapter, table, datasets, synthetic_rows):
    col = adapter.collection(table)
    expected = {i: d['rows'] for i,d in enumerate(datasets, 1)}
    if synthetic_rows:
        expected[0] = synthetic_rows
    groups = list(col.aggregate([{'$group': {'_id':'$source_id', 'n':{'$sum':1},
        'lo':{'$min':'$source_no'},'hi':{'$max':'$source_no'}}}]))
    if len(groups) != len(expected) or any(g != dict(_id=g['_id'], n=expected.get(g['_id']), lo=0,
            hi=expected.get(g['_id'],0)-1) for g in groups):
        raise RuntimeError('Mixed MongoDB source validation failed: '+str(groups))
    # _id is the same monotonic doc_id and has a unique index.
    count = sum(expected.values())
    bad = col.count_documents({'$expr': {'$ne':['$_id','$doc_id']}})
    lo = col.find_one(sort=[('_id',1)])['_id']
    hi = col.find_one(sort=[('_id',-1)])['_id']
    if bad or (lo, hi) != (0,count-1):
        raise RuntimeError('Mixed MongoDB doc_id validation failed')


def asterix_ingest(adapter, table, rows, datasets):
    normalize = {i for i,d in enumerate(datasets,1) if d.get('duplicate_keys')}
    if normalize:
        import orjson

    def documents():
        for ident,source,source_no,schema,text in rows:
            if source in normalize:
                text = orjson.dumps(orjson.loads(text))
            yield (f'{{"doc_id":{ident},"source_id":{source},'
                   f'"source_no":{source_no},"doc":').encode()+text+b'}\n'
    adapter.load_json(table,documents())


def asterix_validate(adapter, table, datasets, synthetic_rows):
    expected = {i:d['rows'] for i,d in enumerate(datasets,1)}
    if synthetic_rows:
        expected[0] = synthetic_rows
    groups = adapter.command(f'''SELECT source_id, count(*) AS n,
        min(d.source_no) AS lo, max(d.source_no) AS hi
        FROM {table} d GROUP BY d.source_id AS source_id''')['results']
    if len(groups) != len(expected) or any(g != dict(source_id=g['source_id'],
            n=expected.get(g['source_id']),lo=0,hi=expected.get(g['source_id'],0)-1)
            for g in groups):
        raise RuntimeError('Mixed AsterixDB source validation failed: '+str(groups))
    count = sum(expected.values())
    summary = adapter.command(f'SELECT count(*) AS n,min(d.doc_id) AS lo,max(d.doc_id) AS hi '
                              f'FROM {table} d')['results']
    # doc_id is the dataset's primary key.
    if summary != [dict(n=count,lo=0,hi=count-1)]:
        raise RuntimeError('Mixed AsterixDB doc_id validation failed: '+str(summary))


def reuse_schema_ids(adapter, table, datasets, synthetic_dir, count):
    """Reuse the schema mapping of an existing stream with the same source rows."""
    from engines import identifier
    table = '.'.join(identifier(part) for part in table.split('.'))
    mapping = array('I', [0]) * (len(datasets) + count + 1)
    pool = []
    if count:
        with (Path(synthetic_dir)/'mixed.jsonl').open() as stream:
            pool = [json.loads(line)['schema_no'] for line in stream]
        if sorted(pool) != list(range(1, count + 1)):
            raise ValueError('Synthetic pool does not cover each schema exactly once')
    rows = adapter.command(f'''SELECT source_id,
        CASE WHEN source_id=0 THEN source_no % {max(count, 1)} ELSE 0 END AS pool_index,
        min(schema_id),max(schema_id) FROM {table} GROUP BY 1,2''').fetchall()
    for source, position, first, last in rows:
        if first != last or first is None or first <= 0:
            raise ValueError('Source rows do not share one registered schema')
        logical = source if source else len(datasets) + pool[position]
        if not 0 < logical < len(mapping) or mapping[logical]:
            raise ValueError('Unexpected or duplicate source schema')
        mapping[logical] = first
    if len(rows) != len(mapping)-1 or not all(mapping[1:]):
        raise ValueError('Source table does not cover the expected schemas')
    return mapping


def register_schemas(adapter, datasets, synthetic_dir, count):
    """Register every schema for this import and return its document ID mapping."""
    ids = array('I', [0])
    if adapter.system != 'specson':
        return None

    def definitions():
        for ds in datasets:
            yield json.dumps(ds['schema'])
        if not count:
            return
        with (Path(synthetic_dir)/'schemas.jsonl').open() as f:
            index = -1
            for index,line in enumerate(f):
                if index >= count:
                    raise ValueError('Too many synthetic schemas')
                yield line
            if index+1 != count:
                raise ValueError('Too few synthetic schemas')

    with adapter.c.transaction():
        for definition in definitions():
            physical = adapter.c.execute('SELECT specson.specson_register_schema(%s::text)',
                                         (definition,)).fetchone()[0]
            ids.append(physical)
    return ids
