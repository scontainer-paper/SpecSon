#!/usr/bin/env python3
"""Run the packaged PostgreSQL image with the formal CPU and memory settings."""
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import psycopg
from protocol import emit_result
from cpu_config import BACKEND_CPUS
from memory_budget import PG_IO_COMBINE_KIB, PG_IO_CONCURRENCY, PG_IO_METHOD, PG_IO_WORKERS, profile, verify

ROOT = Path(__file__).resolve().parent.parent


def command(*args, cwd=None):
    result = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:] or result.stdout[-4000:])
    return result.stdout.strip()


def prepare(args):
    name = f'specson-public-pg-{args.port}'
    runtime = args.runtime_dir.resolve()
    existing = command('docker', 'ps', '-aq', '--filter', f'name=^/{name}$')
    if existing:
        info = json.loads(command('docker', 'inspect', name))[0]
        if info['Config'].get('Labels', {}).get('specson.public.runtime') != str(runtime):
            raise RuntimeError('Container belongs to another runtime directory: '+name)
        if args.action == 'stop':
            command('docker', 'stop', '-t', '120', name)
            return dict(status='ok', action='stop', container=name)
        if info['State']['Running']:
            raise RuntimeError('Stop the existing instance before changing its resource limits')
        command('docker', 'rm', name)
    elif args.action == 'stop':
        return dict(status='ok', action='stop', container=name)
    image = getattr(args, 'image', None) or os.environ.get('SPECSON_IMAGE', 'specson-pg:18.6-release')
    runtime.mkdir(parents=True, exist_ok=True)
    data = runtime/'pgdata'
    user = getpass.getuser()
    mounts = ['--user', f'{os.getuid()}:{os.getgid()}', '-v', f'{runtime}:{runtime}',
              '-v', '/etc/passwd:/etc/passwd:ro', '-v', '/etc/group:/etc/group:ro']
    if not (data/'PG_VERSION').exists():
        command('docker', 'run', '--rm', *mounts, '--entrypoint', 'initdb', image,
                '-D', data, '-U', user, '-A', 'trust', '--no-locale', '--encoding=UTF8')
    memory = getattr(args, 'memory_gib', None) or 64
    budget = profile(memory)
    combine = getattr(args, 'io_combine_kib', None) or PG_IO_COMBINE_KIB
    settings = dict(port=str(args.port), listen_addresses="''", unix_socket_directories="'/tmp'",
        shared_buffers=f"'{budget['buffer_mib']}MB'", work_mem=f"'{budget['work_mem_mib']}MB'",
        effective_cache_size=f"'{budget['effective_cache_mib']}MB'", huge_pages='off',
        max_parallel_workers='8', max_worker_processes='8',
        max_parallel_workers_per_gather=str(args.cores-1), max_parallel_maintenance_workers='0',
        jit='off', plan_cache_mode='force_generic_plan', fsync='on', synchronous_commit='on',
        full_page_writes='on', checkpoint_timeout="'1h'", max_wal_size="'256GB'",
        default_toast_compression='lz4', io_method=f"'{PG_IO_METHOD}'", io_workers=str(PG_IO_WORKERS),
        effective_io_concurrency=str(PG_IO_CONCURRENCY), io_max_combine_limit=f"'{combine}kB'",
        io_combine_limit=f"'{combine}kB'")
    settings['specson.schema_root_cache_size'] = f"'{budget['schema_root_cache_mib']}MB'"
    config = runtime/'experiment.conf'
    config.write_text(''.join(f'{k} = {v}\n' for k, v in settings.items()))
    cpus = set(BACKEND_CPUS[:args.cores])
    # Host PIDs and identical data paths preserve the formal affinity, binary,
    # cgroup and physical-size checks performed by the client on the host.
    command('docker', 'run', '-d', '--name', name, *mounts, '-v', '/tmp:/tmp',
        '--pid=host', '--network=host', '--cpuset-cpus', ','.join(map(str, sorted(cpus))),
        '--cpus', args.cores, '--memory', f'{memory}g', '--memory-swap', f'{memory}g',
        '--shm-size', f'{memory}g', '--label', f'specson.public.runtime={runtime}',
        '--entrypoint', 'postgres', image, '-D', data, '-c', f'config_file={config}')
    deadline = time.monotonic()+60
    while True:
        try:
            connection = psycopg.connect(host='/tmp', port=args.port, dbname='postgres', user=user,
                                         connect_timeout=2, autocommit=True)
            break
        except psycopg.OperationalError:
            if time.monotonic() >= deadline:
                raise RuntimeError(command('docker', 'logs', '--tail', '30', name))
            time.sleep(.5)
    with connection as c:
        pid = c.info.backend_pid
        limits = verify(pid, memory)
        if os.sched_getaffinity(pid) != cpus:
            raise RuntimeError('Backend affinity mismatch')
        actual = dict(c.execute('SELECT name,setting FROM pg_settings').fetchall())
        version = c.execute('SELECT version()').fetchone()[0]
        binary_hash = hashlib.sha256(Path(f'/proc/{pid}/exe').read_bytes()).hexdigest()
    info = json.loads(command('docker', 'inspect', name))[0]
    return dict(status='ok', action='start', container=name, image_id=info['Image'],
                data_directory=str(data), version=version, postgres_sha256=binary_hash,
                settings={k:actual[k] for k in settings}, resource_limits=limits)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start','stop'])
    parser.add_argument('--cores', type=int, choices=[1,2,3,4], default=1)
    parser.add_argument('--port', type=int, default=56529)
    parser.add_argument('--runtime-dir', type=Path, default=ROOT/'experiments/runtime/postgres')
    parser.add_argument('--memory-gib', type=int, default=64)
    parser.add_argument('--io-combine-kib', type=int)
    parser.add_argument('--image', default=os.environ.get('SPECSON_IMAGE', 'specson-pg:18.6-release'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        result = prepare(args)
    except Exception as error:
        emit_result(args.output, dict(status='error', error=str(error)))
        return 1
    emit_result(args.output, result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
