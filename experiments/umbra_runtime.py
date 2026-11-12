"""One owned Umbra database file per dataset, at a fixed configured port.

Isolation is necessary for honest per-dataset disk sizes and physical reimport:
Umbra's shared database has no VACUUM FULL/physical table-size SQL interface.
"""
import json
import os
from pathlib import Path
import subprocess
import time

import psycopg

from protocol import atomic_json, digest


def storage(paths, isolated):
    roots = {Path(p).resolve() for p in paths}
    output = subprocess.check_output(['sudo', '-n', 'du', '-a', '-B1',
        '--max-depth=1', '--null', '--', *map(str, sorted(roots))], stderr=subprocess.PIPE)
    total = wal = runtime = 0
    for entry in output.split(b'\0'):
        if not entry:
            continue
        size, name = entry.split(b'\t', 1)
        path, size = Path(os.fsdecode(name)), int(size)
        if path in roots:
            total += size
        elif path.name == 'umbra.db.wal' or path.name.startswith('umbra.db.wal.'):
            wal += size
        elif path.name in ('umbra.pem', 'umbra.cert', '.umbra.db.lock'):
            runtime += size
    return dict(disk_bytes=total-wal-runtime, directory_bytes=total,
        excluded_wal_bytes=wal, excluded_runtime_bytes=runtime,
        scope=('isolated dataset Umbra data/index/metadata files' if isolated else
               'shared Umbra data/index/metadata files, NOT per-table bytes')+
              '; excludes WAL, server certificate/key and lock file',
        paths=list(map(str, sorted(roots))))


def docker(*args):
    return subprocess.check_output(['sudo', '-n', 'docker', *args], stderr=subprocess.PIPE).decode().strip()


def constrain_container(name, cpus, memory_gib=64):
    docker('update', '--cpuset-cpus', ','.join(map(str, sorted(cpus))),
           '--cpus', str(len(cpus)), '--memory', f'{memory_gib}g', '--memory-swap', f'{memory_gib}g', name)
    info = json.loads(docker('inspect', name))[0]
    pid = info['State']['Pid']
    if not pid or os.sched_getaffinity(pid) != cpus:
        raise RuntimeError('Container CPU affinity verification failed: ' + name)
    limits = info['HostConfig']
    if (limits['Memory'] != memory_gib*1024**3 or limits['MemorySwap'] != memory_gib*1024**3
            or limits['NanoCpus'] != len(cpus)*10**9):
        raise RuntimeError('Container resource verification failed: ' + name)
    status = Path(f'/proc/{pid}/status').read_text()
    allowed = next(line.split(':',1)[1].strip() for line in status.splitlines()
                   if line.startswith('Cpus_allowed_list:'))
    return dict(container=name, backend_cpus=sorted(cpus),
                container_memory_bytes=limits['Memory'], swap_bytes=0,
                cpu_quota_cores=len(cpus), backend_allowed_cpus=allowed, image_id=info['Image'])


def activate(config, dataset, cpus, reset=False):
    managed = config['managed']
    memory = f"{config.get('memory_gib', 64)}g"
    root = Path(managed['directory']).resolve()
    owner = digest(str(root))[:12]
    name = f"{managed['prefix']}-{owner}-{dataset}"
    folder = root/dataset
    marker = folder/'owner.json'
    storage = folder/'data'
    identity = dict(owner=owner, dataset=dataset, container=name)
    if marker.exists() and json.loads(marker.read_text()) != identity:
        raise RuntimeError('Umbra directory ownership does not match')
    if storage.exists() and not marker.exists():
        raise RuntimeError('Refusing to use an unowned Umbra storage directory')
    if storage.is_symlink():
        raise RuntimeError('Managed Umbra storage must not be a symlink')
    # Only stop instances owned by this experiment directory to free its port.
    running = docker('ps', '-q', '--filter', 'label=specson.public.owner='+owner).splitlines()
    existing = docker('ps', '-aq', '--filter', 'name=^/'+name+'$').splitlines()
    current = existing[0] if existing else None
    for container in running:
        if container != current or reset:
            docker('stop', container)
    if reset and current:
        docker('rm', current)
        current = None
    if reset and storage.exists():
        # This is an owned, isolated dataset DB, never the historical benchmark DB.
        subprocess.run(['sudo', '-n', 'rm', '-rf', '--', str(storage)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if storage.exists():
            raise RuntimeError('Umbra physical cleanup failed')
    atomic_json(marker, identity)
    storage.mkdir(parents=True, exist_ok=True)
    storage.chmod(0o777)  # container's unprivileged umbra UID writes here
    if not current:
        docker('run', '-d', '--name', name, '--label', 'specson.public.owner='+owner,
               '--cpuset-cpus', ','.join(map(str, sorted(cpus))),
               '--cpus', str(len(cpus)), '--memory', memory, '--memory-swap', memory,
               '-p', f"127.0.0.1:{config['connection']['port']}:5432",
               '-v', str(storage)+':/var/db', managed['image'])
    else:
        docker('update', '--cpuset-cpus', ','.join(map(str, sorted(cpus))),
               '--cpus', str(len(cpus)), '--memory', memory, '--memory-swap', memory, current)
        if current not in running:
            docker('start', current)
    deadline = time.monotonic()+45
    while True:
        try:
            with psycopg.connect(**config['connection'], connect_timeout=1):
                break
        except psycopg.OperationalError:
            if time.monotonic() >= deadline:
                raise RuntimeError('Managed Umbra did not become ready within 45 seconds')
            time.sleep(.25)
    limits = constrain_container(name, cpus, config.get('memory_gib', 64))
    return dict(config, disk_paths=[str(storage)], isolated_storage=True,
                cleanup_verified=reset, managed_container=name, **limits)
