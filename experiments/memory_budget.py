"""Instance memory profiles for the mixed-table query experiment."""
from pathlib import Path
import json
import re

# Shared by all PostgreSQL systems. Bulk-read windows adapt inside read_stream;
# these settings define the asynchronous I/O capacity, not a fixed scan window.
PG_IO_METHOD = 'worker'
PG_IO_WORKERS = 3
PG_IO_CONCURRENCY = 64
PG_IO_COMBINE_KIB = 1024


def profile(gib):
    if gib < 1:
        raise ValueError('Memory limit must be at least 1 GiB')
    return dict(memory_gib=gib, cache_gib=gib / 2,
                buffer_mib=gib * 512, work_mem_mib=gib * 4,
                schema_root_cache_mib=gib * 128,
                effective_cache_mib=gib * 768, query_memory_mib=gib * 256,
                nc_heap_mib=gib * 768, nc_initial_mib=gib * 64,
                service_heap_mib=max(256, gib * 16),
                service_initial_mib=max(64, gib * 4),
                memory_component_bytes=gib * 32 * 1024**2)


def cgroup(pid):
    group = next(line.split(':', 2)[2] for line in
                 Path(f'/proc/{pid}/cgroup').read_text().splitlines()
                 if line.startswith('0::'))
    return Path('/sys/fs/cgroup') / group.lstrip('/')


def verify(pid, gib):
    path = cgroup(pid)
    values = {name: (path / name).read_text().strip()
              for name in ('memory.max', 'memory.swap.max')}
    if values != {'memory.max': str(gib * 1024**3), 'memory.swap.max': '0'}:
        raise RuntimeError(f'Unexpected database memory limits: {values}')
    return dict(memory_limit_bytes=gib * 1024**3, swap_limit_bytes=0,
                cgroup=str(path))


def memory_events(metadata):
    if not metadata.get('cgroup'):
        return {}
    path = Path(metadata['cgroup']) / 'memory.events'
    if not path.exists():
        return {}
    return {key: int(value) for key, value in
            (line.split() for line in path.read_text().splitlines())}


def oom_failure(error, metadata, before=None):
    """Recognize memory errors; other query failures must still stop the run."""
    message = str(error)
    state = getattr(error, 'sqlstate', None)
    details = dict(error=message, sqlstate=state)
    detected = state == '53200' or bool(re.search(
        r'out[ -]of[ -]memory|bad_alloc|cannot allocate memory|memory (?:limit|budget).*exceed|'
        r'exceed\w*.*memory (?:limit|budget)|insufficient memory|OutOfMemoryError',
        message, re.I))
    if metadata.get('container'):
        from umbra_runtime import docker
        status = json.loads(docker('inspect', metadata['container']))[0]['State']
        details['container_state'] = {k: status.get(k) for k in
                                      ('Running', 'OOMKilled', 'ExitCode', 'Error')}
        detected |= status.get('OOMKilled', False)
    if metadata.get('cgroup'):
        after = memory_events(metadata)
        details['memory_events'] = after
        if before is not None:
            details['memory_events_before'] = before
            detected |= after.get('oom_kill', 0) > before.get('oom_kill', 0)
    return details if detected else None
