"""Adapters. Connections are supplied explicitly by run.py, never discovered."""
from pathlib import Path
import hashlib
import itertools
import json
import os
import re
import struct
import subprocess

import psycopg
from psycopg import pq
import requests
from protocol import atomic_json, result_signature
from memory_budget import PG_IO_COMBINE_KIB, PG_IO_CONCURRENCY, PG_IO_METHOD, PG_IO_WORKERS


def identifier(value):
    if not re.fullmatch(r'[a-z][a-z0-9_]*', value):
        raise ValueError('Unsafe SQL identifier: ' + value)
    return value


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


NUL_ESCAPE = re.compile(rb'(\\+)u0000')

# Installed Umbra rejects binary COPY input. CSV preserves JSON backslashes verbatim.
# RS cannot occur unescaped in valid JSON; quoting also permits JSON whitespace.
UMBRA_COPY_OPTIONS = " (FORMAT csv, DELIMITER '\x1f', QUOTE '\x1e', ESCAPE '\x1e')"
UMBRA_COPY_BATCH_ROWS = 100_000


def append_umbra_json(buf, text):
    if b'\x1e' in text:
        raise ValueError('JSON contains an unescaped record-separator control character')
    buf.extend(b'\x1e')
    buf.extend(text)
    buf.extend(b'\x1e')


def normalize_nul(text):
    # Only an odd number of backslashes introduces an actual JSON escape.
    # A literal string containing \\u0000 must stay unchanged.
    if b'\\u0000' not in text:
        return text
    return NUL_ESCAPE.sub(lambda m: m[1]+b'uFFFD' if len(m[1]) % 2 else m[0], text)


def source_rows(files, replace_nul=False):
    ident = 0
    for file in files:
        with Path(file).open('rb') as f:
            for line in f:
                if line.strip():
                    text = line.rstrip(b'\r\n')
                    yield ident, normalize_nul(text) if replace_nul else text
                    ident += 1


def copy_chunks(files, binary, replace_nul=False):
    yield from copy_row_chunks(source_rows(files, replace_nul), binary)


def copy_row_chunks(rows, binary):
    buf = bytearray(b'PGCOPY\n\xff\r\n\0' + struct.pack('!ii', 0, 0) if binary else b'')
    for ident, text in rows:
        if binary:
            buf.extend(struct.pack('!hiii', 2, 4, ident, len(text) + 1))
            buf.extend(b'\x01' + text)
        else:
            buf.extend(str(ident).encode()+b'\x1f')
            append_umbra_json(buf,text)
            buf.extend(b'\n')
        if len(buf) >= 1024 * 1024:
            yield bytes(buf)
            buf.clear()
    if binary:
        buf.extend(struct.pack('!h', -1))
    if buf:
        yield bytes(buf)


class Postgres:
    def __init__(self, system, config, namespace, threads, cpus):
        self.system, self.config, self.namespace = system, config, identifier(namespace)
        self.c = psycopg.connect(**config['connection'], autocommit=True, prepare_threshold=5)
        self.postmaster_affinity = None
        self.prepared = set()
        self.meta = dict(version=self.c.execute('SELECT version()').fetchone()[0])
        if config.get('container'):
            self.meta['container'] = config['container']
        if system == 'umbra':
            # Native WAL limits: numeric wal_max_size SET uses MiB; SHOW uses bytes.
            # Umbra has no time-based checkpoint interval.
            self.c.execute("SET debug.wal_max_size=262144; "
                           "SET debug.wal_flush_epoch_interval='274877906944B'")
            wal_max = self.c.execute('SHOW debug.wal_max_size').fetchone()[0]
            flush_epoch = self.c.execute('SHOW debug.wal_flush_epoch_interval').fetchone()[0]
            if int(wal_max) != 256 * 1024**3 or flush_epoch != '274877906944B':
                self.c.close()
                raise RuntimeError('Umbra native checkpoint thresholds do not match')
        if system=='specson':
            self.c.execute('SET specson.experimental_storage=off; SET specson.compact_storage=off')
            self.meta['storage_layout']='A: accepted adaptive4096 indexed directory, directory compressed with payload'
            self.meta['specson_storage']=config.get('specson_storage','custom')
            if self.meta['specson_storage']=='toast':
                self.meta['storage_layout']='PostgreSQL TOAST, EXTENDED, LZ4 body with uncompressed schema ID prefix'
            self.meta['sql_function_costs'] = dict(self.c.execute(
                "SELECT proname,procost FROM pg_catalog.pg_proc "
                "WHERE pronamespace='pg_catalog'::regnamespace AND proname IN "
                "('specson_sql_exists','specson_sql_scalar','specson_sql_rows','specson_sql_possible')"
            ).fetchall())
        self.c.execute(f'CREATE SCHEMA IF NOT EXISTS {namespace}')
        if system == 'umbra':
            # Umbra SET accepts MiB, while SHOW reports bytes. Leave room for
            # query state and process overhead inside the 64 GiB instance cap.
            buffer_mib = config.get('buffer_mib', 32768)
            query_mib = config.get('query_memory_mib', 16384)
            self.c.execute(f'SET debug.buffersize={buffer_mib}; SET debug.database.querymemorysize={query_mib}')
            self.c.execute(f"SET debug.parallel={threads}; SET debug.compilationmode='o'")
            self.meta.update({k: config[k] for k in
                ('container', 'backend_cpus', 'container_memory_bytes', 'swap_bytes', 'cpu_quota_cores',
                 'backend_allowed_cpus', 'image_id') if k in config})
            self.meta['cores'] = threads
        else:
            work_mib = config.get('work_mem_mib', 256)
            self.c.execute(f"SET jit=off; SET plan_cache_mode=force_generic_plan; SET work_mem='{work_mib}MB'")
            io_concurrency = config.get('io_concurrency', PG_IO_CONCURRENCY)
            io_combine_kib = config.get('io_combine_kib', PG_IO_COMBINE_KIB)
            self.c.execute(f"SET effective_io_concurrency={io_concurrency}; SET io_combine_limit='{io_combine_kib}kB'")
            actual_io = self.c.execute("SELECT current_setting('effective_io_concurrency')::int, "
                "pg_size_bytes(current_setting('io_combine_limit')), "
                "current_setting('io_method'), current_setting('io_workers')::int").fetchone()
            if actual_io != (io_concurrency, io_combine_kib * 1024, PG_IO_METHOD, PG_IO_WORKERS):
                self.c.close()
                raise RuntimeError('PostgreSQL I/O settings differ; restart with prepare_postgres.py')
            if 'effective_cache_mib' in config:
                self.c.execute(f"SET effective_cache_size='{config['effective_cache_mib']}MB'")
            # The leader can participate; the remaining cores are worker slots.
            self.c.execute(f'SET max_parallel_workers_per_gather={threads-1}; SET parallel_leader_participation=on')
            if threads == 1:
                self.c.execute('SET max_parallel_maintenance_workers=0')
            if threads > 1:
                # Match the established multi-core benchmark policy for both
                # SpecSon and jsonb; retain all scan alternatives.
                self.c.execute('SET parallel_setup_cost=0; SET parallel_tuple_cost=0; SET min_parallel_table_scan_size=0')
            pid = self.c.info.backend_pid
            if 'buffer_mib' in config:
                from memory_budget import verify
                self.meta.update(verify(pid, config['memory_gib']))
                actual = self.c.execute("SELECT pg_size_bytes(current_setting('shared_buffers'))").fetchone()[0]
                if actual != config['buffer_mib'] * 1024**2:
                    raise RuntimeError('PostgreSQL shared_buffers does not match the memory profile')
                actual_root = self.c.execute("SELECT pg_size_bytes(current_setting('specson.schema_root_cache_size'))").fetchone()[0]
                if actual_root != config['memory_gib'] * 1024**3 // 8:
                    raise RuntimeError('Schema root cache does not match one eighth of the memory limit')
            os.sched_setaffinity(pid, cpus)
            if os.sched_getaffinity(pid) != cpus:
                raise RuntimeError('Backend affinity verification failed')
            status = Path(f'/proc/{pid}/status').read_text()
            allowed = next(line.split(':', 1)[1].strip() for line in status.splitlines()
                           if line.startswith('Cpus_allowed_list:'))
            self.meta.update(backend_pid=pid, backend_cpus=sorted(cpus), cores=threads,
                backend_allowed_cpus=allowed,
                postgres_sha256=hashlib.sha256(Path(f'/proc/{pid}/exe').read_bytes()).hexdigest())
            self.data_dir = Path(self.c.execute('SHOW data_directory').fetchone()[0])
            pm = int((self.data_dir/'postmaster.pid').read_text().splitlines()[0])
            previous = os.sched_getaffinity(pm)
            os.sched_setaffinity(pm, cpus)
            self.postmaster_affinity = (pm, previous)
            if os.sched_getaffinity(pm) != cpus:
                self.close()
                raise RuntimeError('Postmaster CPU affinity verification failed')
        self.meta['settings'] = dict(self.c.execute("SELECT name,setting FROM pg_settings WHERE name IN "
            "('jit','plan_cache_mode','max_parallel_workers_per_gather','parallel_leader_participation',"
            "'parallel_setup_cost','parallel_tuple_cost','min_parallel_table_scan_size',"
            "'max_parallel_workers','max_worker_processes','max_parallel_maintenance_workers','work_mem','shared_buffers','effective_cache_size','hash_mem_multiplier',"
            "'fsync','synchronous_commit','full_page_writes','wal_sync_method','wal_buffers',"
            "'wal_writer_delay','wal_init_zero','wal_recycle','checkpoint_timeout','max_wal_size',"
            "'effective_io_concurrency','io_combine_limit','io_max_combine_limit','io_method','io_workers',"
            "'specson.schema_root_cache_size','debug.parallel','debug.buffersize',"
            "'debug.database.querymemorysize','debug.wal_sync_method','debug.wal_sync_interval',"
            "'debug.wal_max_size','debug.wal_flush_epoch_interval','debug.bm_flush_on_shutdown')").fetchall())
        self.meta['copy_flush'] = 'Drain pending libpq output after each input batch'
        if system == 'umbra':
            self.meta['copy_protocol'] = 'csv-us-rs-v1'
            self.meta['copy_batch_rows'] = UMBRA_COPY_BATCH_ROWS

    def close(self):
        try:
            self.c.close()
        finally:
            if self.postmaster_affinity is not None:
                pid, previous = self.postmaster_affinity
                try:
                    os.sched_setaffinity(pid, previous)
                except ProcessLookupError:
                    pass  # The postmaster may have been killed by the memory limit.
                self.postmaster_affinity = None

    def command(self, sql):
        return self.c.execute(sql, prepare=False)

    def query_plan(self, sql):
        plan = self.command('EXPLAIN (FORMAT JSON) ' + sql).fetchone()[0][0]['Plan']
        nodes = []
        def collect(node):
            nodes.append({k: node[k] for k in ('Node Type', 'Parallel Aware', 'Workers Planned',
                                             'Custom Plan Provider', 'Index Name', 'Index Cond') if k in node})
            for child in node.get('Plans', []):
                collect(child)
        collect(plan)
        return nodes

    def exists(self, table):
        return bool(self.c.execute('SELECT 1 FROM information_schema.tables WHERE table_schema=%s AND table_name=%s',
                                  tuple(table.split('.'))).fetchone())

    def prepare(self, sql, streaming=False):
        name = ('formal_' + hashlib.sha256(sql.encode()).hexdigest()[:24]).encode()
        if name in self.prepared:
            return name, streaming
        # Parse once without executing: cold-start has NO hidden query warmup.
        result = self.c.pgconn.prepare(name, sql.encode())
        self.check(result)
        result.clear()
        self.prepared.add(name)
        return name, streaming

    @staticmethod
    def check(result):
        if result.status not in (pq.ExecStatus.TUPLES_OK, pq.ExecStatus.COMMAND_OK):
            error = RuntimeError(result.error_message.decode(errors='replace'))
            code = result.error_field(pq.DiagnosticField.SQLSTATE)
            error.sqlstate = code.decode() if code else None
            raise error

    def receive(self, prepared):
        name, streaming = prepared
        if not streaming:
            return self.c.pgconn.exec_prepared(name, [])
        conn = self.c.pgconn
        conn.send_query_prepared(name, [])
        conn.set_chunked_rows_mode(1024)
        rows, error = 0, None
        while (result := conn.get_result()) is not None:
            try:
                if result.status == pq.ExecStatus.TUPLES_CHUNK:
                    rows += result.ntuples
                else:
                    self.check(result)
                    rows += result.ntuples
            except Exception as exc:
                error = exc
            finally:
                result.clear()
        if error:
            raise error
        return dict(result_rows=rows)

    def finish(self, result):
        if isinstance(result, dict):
            return result
        try:
            self.check(result)
            info=dict(result_rows=result.ntuples)
            if getattr(self,'verify_results',False):
                def rows():
                    for i in range(result.ntuples):
                        ident=int(result.get_value(i,0))
                        yield ident if result.nfields==1 else [ident,json.loads(result.get_value(i,1))]
                info['result_signature']=result_signature(rows())
            return info
        finally:
            result.clear()

    def update(self, sql, **_):
        # The timer includes the transaction's commit acknowledgement.
        with self.c.transaction():
            cur = self.c.execute(sql, prepare=True)
            rows = cur.rowcount
        return rows  # COMMIT has completed

    def register(self, schema):
        if self.system != 'specson':
            return None
        return self.c.execute('INSERT INTO specson.schemas(schema) VALUES(%s::json) RETURNING schema_id',
                              (json.dumps(schema),)).fetchone()[0]

    def ingest(self, table, files, schema_id, replace_nul=False):
        if self.system == 'umbra':
            # Keep native COPY transactions bounded; IDs continue across batches.
            rows = source_rows(files, replace_nul)
            for first in rows:
                batch = itertools.chain((first,), itertools.islice(rows, UMBRA_COPY_BATCH_ROWS - 1))
                with self.c.transaction():
                    with self.c.cursor().copy(f'COPY {table}(doc_id,doc) FROM STDIN' +
                                              UMBRA_COPY_OPTIONS) as stream:
                        for chunk in copy_row_chunks(batch, False):
                            stream.write(chunk)
                            self.c.wait(psycopg.generators.send(self.c.pgconn))
            return
        try:
            self.command(f'BEGIN IMPORT SCHEMA {int(schema_id)}' if self.system == 'specson' else 'BEGIN')
            with self.c.cursor().copy(f'COPY {table}(doc_id,doc) FROM STDIN (FORMAT binary)') as stream:
                for chunk in copy_chunks(files, True, replace_nul):
                    stream.write(chunk)
                    # Bound pending output; otherwise libpq repeatedly moves an
                    # accumulating COPY buffer when the backend consumes slowly.
                    self.c.wait(psycopg.generators.send(self.c.pgconn))
            self.command('END IMPORT' if self.system == 'specson' else 'COMMIT')
        except BaseException:
            if not self.c.closed:
                self.command('ROLLBACK')
            raise

    def validate(self, table, expected):
        row = self.c.execute(f'SELECT count(*),min(doc_id),max(doc_id) FROM {table}').fetchone()
        if tuple(row) != (expected, 0, expected - 1):
            raise RuntimeError(f'Row/doc_id validation failed: {row}')

    def maintain(self, table):
        self.command(f'ANALYZE {table}' if self.system == 'umbra' else f'VACUUM ANALYZE {table}')

    def relation_oids(self, table):
        oid = self.c.execute('SELECT %s::regclass::oid', (table,)).fetchone()[0]
        pending, found = [oid], set()
        while pending:
            oid = pending.pop()
            if not oid or oid in found:
                continue
            found.add(oid)
            toast = self.c.execute('SELECT reltoastrelid FROM pg_class WHERE oid=%s', (oid,)).fetchone()[0]
            pending.append(toast)
            pending.extend(r[0] for r in self.c.execute('SELECT indexrelid FROM pg_index WHERE indrelid=%s', (oid,)))
            if self.system == 'specson':
                pending.extend(self.c.execute('SELECT relspecsonmap,relspecsondata FROM pg_class WHERE oid=%s', (oid,)).fetchone())
        return sorted(found)

    def verify_removed(self, paths):
        self.command('CHECKPOINT')  # flush deferred unlink of relation segment 0
        remaining = []
        for path in paths:
            base = Path(path)
            pattern = re.compile(re.escape(base.name) + r'(?:_(?:fsm|vm|init))?(?:\.\d+)?$')
            remaining.extend(str(p) for p in base.parent.glob(base.name+'*') if pattern.fullmatch(p.name))
        if remaining:
            raise RuntimeError('Old relation files remain: ' + ', '.join(remaining))

    def drop(self, table, journal=None):
        previous_paths = json.loads(journal.read_text()) if journal and journal.exists() else []
        if not self.exists(table):
            if previous_paths:
                self.verify_removed(previous_paths)
                journal.unlink()
            return dict(cleaned=True, verified_relation_paths=previous_paths)
        if self.system == 'umbra':
            # Umbra stores multiple tables in a shared file. A configured hook
            # must provide physical reclamation; do not claim DROP shrinks it.
            hook = self.config.get('reimport_cleanup_command')
            if not hook:
                raise RuntimeError('Umbra physical reimport cleanup is not configured; set reimport_cleanup_command for an isolated experiment database. Refusing to claim disk reclamation after DROP alone.')
            self.command(f'DROP TABLE {table}')
            subprocess.run(hook, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return dict(cleaned=True, method='configured Umbra physical cleanup hook')
        paths = [self.data_dir / self.c.execute('SELECT pg_relation_filepath(%s)', (oid,)).fetchone()[0]
                 for oid in self.relation_oids(table)]
        paths = sorted(set(previous_paths + [str(p) for p in paths]))
        if journal:
            # Keep the physical cleanup obligation even if DROP succeeds and
            # the process fails before verification or before saving results.
            atomic_json(journal, paths)
        self.command(f'DROP TABLE {table}')
        self.verify_removed(paths)
        if journal:
            journal.unlink()
        return dict(cleaned=True, verified_relation_paths=paths)

    def storage(self, table):
        if self.system == 'umbra':
            from umbra_runtime import storage
            return storage(self.config['disk_paths'], self.config.get('isolated_storage', False))
        rows = self.c.execute('SELECT c.oid,c.relname,pg_relation_size(c.oid),'
                              "pg_relation_size(c.oid,'fsm')+pg_relation_size(c.oid,'vm')+pg_relation_size(c.oid,'init'),a.amname "
                              'FROM pg_class c LEFT JOIN pg_am a ON a.oid=c.relam '
                              'WHERE c.oid=ANY(%s)', (self.relation_oids(table),)).fetchall()
        return dict(disk_bytes=sum(r[2]+r[3] for r in rows),
                    gin_index_bytes=sum(r[2]+r[3] for r in rows if r[4]=='gin'),
                    scope='table + TOAST + indexes + SpecSon map/data forks',
                    relations=[dict(oid=r[0], name=r[1], main_bytes=r[2], other_fork_bytes=r[3],
                                    access_method=r[4]) for r in rows])


class ClickHouse:
    update_batch_rows = 100000  # Whole groups of 100; bound Join snapshot memory.

    def __init__(self, system, config, namespace, threads, cpus):
        self.system, self.config, self.namespace = system, config, identifier(namespace)
        from umbra_runtime import constrain_container
        affinity = constrain_container(config['container'], cpus)
        self.http = requests.Session()
        self.settings = dict(max_threads=threads, max_insert_threads=threads, max_query_size=1048576,
            use_query_cache=0, use_query_condition_cache=0, async_insert=0, mutations_sync=2,
            input_format_parallel_parsing=0, json_type_escape_dots_in_keys=1,
            type_json_skip_duplicated_paths=1, input_format_json_read_numbers_as_strings=0,
            enable_named_columns_in_function_tuple=1, output_format_json_quote_64bit_integers=0)
        self.command(f'CREATE DATABASE IF NOT EXISTS {namespace}')
        self.meta = dict(version=self.command('SELECT version()').text.strip(), settings=self.settings,
                        cores=threads, **affinity,
                        restoration='Native JSON value, not lossless: typed paths add defaults; nulls and empty objects may be lost',
                        update_batch_rows=self.update_batch_rows)

    def close(self):
        self.http.close()

    def command(self, sql, data=None, stream=False):
        params = dict(self.settings)
        if data is not None:
            params['query'] = sql
        response = self.http.post(self.config['url'], params=params,
            auth=(self.config['user'], self.config['password']),
            data=sql.encode() if data is None else data, timeout=3600, stream=stream)
        if (response.status_code != 200 or response.headers.get('X-ClickHouse-Exception-Code')
                or (not stream and re.search(rb'(?:^|\n)Code: \d+\. .*DB::Exception', response.content[-8192:]))):
            raise RuntimeError(response.text[:2000])
        return response

    def exists(self, table):
        return self.command('EXISTS TABLE ' + table).text.strip() == '1'

    def prepare(self, sql, streaming=False):
        return sql, streaming  # HTTP has no equivalent prepared-statement protocol

    def receive(self, prepared):
        sql, streaming = prepared
        if not streaming:
            return self.command(sql).content
        rows, size, tail = 0, 0, b''
        with self.command(sql, stream=True) as response:
            for chunk in response.iter_content(1024*1024):
                rows += chunk.count(b'\n')
                size += len(chunk)
                tail = (tail + chunk)[-8192:]
            if re.search(rb'(?:^|\n)Code: \d+\. .*DB::Exception', tail):
                raise RuntimeError(tail.decode(errors='replace'))
        return dict(result_rows=rows, received_bytes=size)

    def finish(self, result):
        if isinstance(result, dict):
            return result
        if getattr(self, 'verify_results', False):
            def rows():
                for line in result.splitlines():
                    row = json.loads(line)
                    ident = int(row[0])
                    if len(row) == 1:
                        yield ident
                    else:
                        value = json.loads(row[1]) if isinstance(row[1], str) else row[1]
                        yield [ident, value]
            signature = result_signature(rows())
            return dict(result_rows=signature['rows'], received_bytes=len(result),
                        result_signature=signature)
        return dict(result_rows=result.count(b'\n'), received_bytes=len(result))

    def ingest(self, table, files, schema_id, replace_nul=False):
        def chunks():
            buf = bytearray()
            for ident, text in source_rows(files, replace_nul):
                buf.extend(b'{"doc_id":'+str(ident).encode()+b',"doc":'+text+b'}\n')
                if len(buf) >= 1024*1024:
                    yield bytes(buf)
                    buf.clear()
            if buf:
                yield bytes(buf)
        self.command(f'INSERT INTO {table} FORMAT JSONEachRow', chunks())

    def register(self, schema):
        return None

    def validate(self, table, expected):
        row = json.loads(self.command(f'SELECT count(),min(doc_id),max(doc_id) '
            f'FROM {table} FORMAT JSONCompactEachRow').text)
        if row != [expected, 0, expected-1]:
            raise RuntimeError(f'Row/doc_id validation failed: {row}')

    def maintain(self, table):
        pass

    def drop(self, table):
        if not self.exists(table):
            return dict(cleaned=True)
        # SYNC bypasses Atomic's delayed-drop grace period and waits for removal.
        self.command(f'DROP TABLE {table} SYNC')
        if self.exists(table):
            raise RuntimeError('ClickHouse table still exists after synchronous DROP')
        return dict(cleaned=True, method='DROP TABLE SYNC')

    def update(self, sql, snapshot_sql, snapshot, rows, **_):
        # Groups are independent: snapshot only complete groups in this batch.
        # Earlier batches cannot change a source value used by a later batch.
        # Snapshot creation, serialization, updates and intermediate cleanup
        # are all timed. The final snapshot is dropped by the caller afterwards.
        assert self.update_batch_rows > 0 and self.update_batch_rows % 100 == 0
        for start in range(0, rows, self.update_batch_rows):
            if start:
                self.drop(snapshot)
            def bind(statement):
                return statement.replace('{{batch_start}}', str(start)).replace(
                    '{{batch_end}}', str(min(start+self.update_batch_rows, rows)))
            self.command(bind(snapshot_sql))
            self.command(bind(sql))
        return None

    def storage(self, table):
        db, name = table.split('.')
        row = json.loads(self.command('SELECT sum(bytes_on_disk),sumIf(bytes_on_disk,active),'
            'sumIf(data_uncompressed_bytes,active) FROM system.parts WHERE database='+literal(db)+
            ' AND table='+literal(name)+' FORMAT JSONCompactEachRow').text)
        return dict(disk_bytes=row[0], active_bytes=row[1], uncompressed_bytes=row[2],
                    scope='MergeTree parts on disk, active and inactive')
