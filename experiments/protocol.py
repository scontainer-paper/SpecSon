"""Runtime state, one-invocation results, and the shared timing boundary."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import json
import os
import statistics
import subprocess
import time
import uuid


def query_reference(path):
    data = json.loads(Path(path).read_text())
    if 'mixed' in data:
        reference = data['mixed']['queries']['reference']
        return dict(status=data['status'], operation='query', system='jsonb',
                    results=[dict(query=query, status='ok', result_signature=signature,
                                  warmups=reference['warmups'], runs=reference['runs'])
                             for query, signature in reference['signatures'].items()])
    return data


def stamp():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='microseconds')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    with temp.open('w') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, default=str)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    temp.replace(path)


def statistics_ms(values):
    return dict(times_ms=values, median_ms=statistics.median(values),
                mean_ms=statistics.mean(values))


class RunOutput:
    """One independent file, durably updated outside measurement intervals."""
    directory = Path(__file__).resolve().parent.parent/'results/runs'

    def __init__(self, output, system, operation):
        self.stdout = output is None
        self.path = Path(output) if output is not None else self.directory / (
            datetime.now().strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex+'-'+system+'-'+operation+'.json')
        self.value = dict(status='running',system=system,operation=operation,
                          started_at=stamp(),result_file=str(self.path.resolve()),results=[])
        self.path.parent.mkdir(parents=True,exist_ok=True)
        # Exclusive creation prevents a new invocation from overwriting history.
        with self.path.open('x') as f:
            json.dump(self.value,f,ensure_ascii=False,indent=2)
            f.write('\n'); f.flush(); os.fsync(f.fileno())

    def checkpoint(self, records, current=None):
        self.value['results'] = records
        if current is None:
            self.value.pop('current',None)
        else:
            self.value['current'] = current
        self.value['timestamp'] = stamp()
        atomic_json(self.path,self.value)

    def finish(self, status, records=None, error=None):
        self.value.update(status=status,timestamp=stamp())
        if records is not None:
            self.value['results'] = records
        if error is not None:
            self.value['error'] = error
        atomic_json(self.path,self.value)
        if self.stdout:
            emit_result(None,self.value)


class Results:
    def __init__(self, directory, system, identity, output=None):
        self.root = Path(directory) / system / identity[:16]
        self.records = []
        self.output = output

    def state_path(self, dataset):
        return self.root / dataset / 'import-state.json'

    def state(self, dataset):
        p = self.state_path(dataset)
        return json.loads(p.read_text()) if p.exists() else None

    def save_state(self, dataset, value):
        atomic_json(self.state_path(dataset), value)

    def save(self, record):
        record = dict(record, timestamp=stamp())
        self.records.append(record)
        self.checkpoint()
        return record

    def checkpoint(self, current=None):
        if self.output is not None:
            self.output.checkpoint(self.records,current)


def emit_result(output, value):
    """Write exactly one JSON object; never read or reuse earlier results."""
    if output is None:
        print(json.dumps(value, ensure_ascii=False, indent=2, default=str))
    else:
        atomic_json(output, value)


class ColdStart:
    def __init__(self, enabled, clear=None):
        self.enabled, self.done = enabled, False
        self.clear = clear or self.clear_os_cache

    @staticmethod
    def clear_os_cache():
        os.sync()
        if os.geteuid() == 0:
            Path('/proc/sys/vm/drop_caches').write_text('3\n')
        else:
            subprocess.run(['sudo', '-n', 'tee', '/proc/sys/vm/drop_caches'],
                           input=b'3\n', stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE, check=True)

    def before_first_sample(self):
        if self.enabled and not self.done:
            self.clear()  # Fail instead of silently claiming a cold run.
            self.done = True


def measure(execute, finish):
    """execute must receive ALL results, or await commit/visible UPDATE."""
    start = time.perf_counter_ns()
    result = execute()
    elapsed = (time.perf_counter_ns() - start) / 1e6
    info = finish(result)  # release buffers, inspect rows: outside the timer
    return elapsed, info


def reverse_id(ident, rows):
    base = ident // 100 * 100
    return base + min(100, rows - base) - 1 - ident % 100


def result_signature(rows):
    """Order-independent multiset check, only called after the timer stops."""
    def normalize(value):
        if isinstance(value,float):
            value=round(value,6)
            return int(value) if value.is_integer() else value
        if isinstance(value,dict):
            return {k:normalize(v) for k,v in value.items()}
        if isinstance(value,(list,tuple)):
            return [normalize(v) for v in value]
        return value
    count,total=0,0
    for row in rows:
        if isinstance(row,dict) and 'doc_id' in row:
            row=[row['doc_id'],row['result']] if 'result' in row else row['doc_id']
        encoded=json.dumps(normalize(row),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
        total=(total+int.from_bytes(hashlib.sha256(encoded).digest(),'big'))%(1<<256)
        count+=1
    return dict(rows=count,sum_sha256=f'{total:064x}',numeric_round_digits=6)
