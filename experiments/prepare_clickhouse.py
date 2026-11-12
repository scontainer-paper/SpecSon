#!/usr/bin/env python3
"""Start or stop the owned ClickHouse experiment instance."""
import argparse
import json
from pathlib import Path
import time

import requests
from protocol import atomic_json, emit_result
from run import CONNECTIONS, HERE
from cpu_config import BACKEND_CPUS
from umbra_runtime import constrain_container, docker


def prepare(args):
    config = CONNECTIONS['clickhouse']
    name = config['container']
    root = HERE/'runtime/clickhouse'
    owner = dict(system='clickhouse', container=name, directory=str(root))
    marker = root/'owner.json'
    if marker.exists() and json.loads(marker.read_text()) != owner:
        raise RuntimeError('ClickHouse directory ownership mismatch')
    existing = docker('ps', '-aq', '--filter', 'name=^/'+name+'$')
    if existing:
        info = json.loads(docker('inspect', name))[0]
        if not any(m.get('Source') == str(root/'data') and
                   m['Destination'] == '/var/lib/clickhouse' for m in info['Mounts']):
            raise RuntimeError('ClickHouse container uses a different data directory')
    if args.action == 'stop':
        if existing:
            docker('stop', name)
        return dict(status='ok', action='stop', container=name)
    root.mkdir(parents=True, exist_ok=True)
    atomic_json(marker, owner)
    (root/'data').mkdir(exist_ok=True)
    server = '''<clickhouse>
  <max_server_memory_usage>64424509440</max_server_memory_usage>
  <mark_cache_size>1073741824</mark_cache_size>
  <uncompressed_cache_size>25769803776</uncompressed_cache_size>
  <max_thread_pool_size>1024</max_thread_pool_size>
  <background_pool_size>4</background_pool_size>
  <background_schedule_pool_size>8</background_schedule_pool_size>
  <background_message_broker_schedule_pool_size>2</background_message_broker_schedule_pool_size>
  <background_distributed_schedule_pool_size>2</background_distributed_schedule_pool_size>
  <merge_tree>
    <number_of_free_entries_in_pool_to_execute_mutation>2</number_of_free_entries_in_pool_to_execute_mutation>
    <number_of_free_entries_in_pool_to_lower_max_size_of_merge>2</number_of_free_entries_in_pool_to_lower_max_size_of_merge>
    <number_of_free_entries_in_pool_to_execute_optimize_entire_partition>2</number_of_free_entries_in_pool_to_execute_optimize_entire_partition>
  </merge_tree>
  <logger><level>warning</level><console>true</console></logger>
</clickhouse>
'''
    users = '''<clickhouse><profiles><default>
  <max_threads>1</max_threads><max_insert_threads>1</max_insert_threads>
  <max_memory_usage>30064771072</max_memory_usage>
  <use_uncompressed_cache>1</use_uncompressed_cache>
  <merge_tree_max_rows_to_use_cache>20000000</merge_tree_max_rows_to_use_cache>
  <merge_tree_max_bytes_to_use_cache>68719476736</merge_tree_max_bytes_to_use_cache>
  <use_query_cache>0</use_query_cache><use_query_condition_cache>0</use_query_condition_cache>
</default></profiles></clickhouse>
'''
    if existing and info['State']['Running']:
        raise RuntimeError('Stop the experiment instance before starting it again')
    (root/'config.xml').write_text(server)
    (root/'users.xml').write_text(users)
    cpus = set(BACKEND_CPUS[:args.cores])
    if existing:
        docker('update', '--cpuset-cpus', ','.join(map(str, sorted(cpus))),
               '--cpus', str(args.cores), '--memory', '64g', '--memory-swap', '64g', name)
        docker('start', name)
    else:
        docker('run', '-d', '--name', name, '--cpuset-cpus', ','.join(map(str, sorted(cpus))),
               '--cpus', str(args.cores), '--memory', '64g', '--memory-swap', '64g',
               '-p', '127.0.0.1:56530:8123', '-e', 'CLICKHOUSE_SKIP_USER_SETUP=1',
               '-v', str(root/'data')+':/var/lib/clickhouse',
               '-v', str(root/'config.xml')+':/etc/clickhouse-server/config.d/benchmark.xml:ro',
               '-v', str(root/'users.xml')+':/etc/clickhouse-server/users.d/benchmark.xml:ro',
               'clickhouse/clickhouse-server@sha256:0152dd511befe6a2c2ef53e930726179669b08116da78500b37c51c96ff5ee77')
    deadline = time.monotonic()+60
    while True:
        try:
            response = requests.get(config['url'].rstrip('/')+'/ping', timeout=2)
            response.raise_for_status()
            break
        except requests.RequestException:
            if time.monotonic() >= deadline:
                raise RuntimeError('ClickHouse did not start within 60 seconds')
            time.sleep(.25)
    limits = constrain_container(name, cpus)
    info = json.loads(docker('inspect', name))[0]
    return dict(status='ok', action='start', image=info['Image'],
                server_config=server, user_config=users, **limits)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['start','stop'])
    p.add_argument('--cores', type=int, choices=[1,2,4], default=1)
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    try:
        result = prepare(args)
    except Exception as error:
        emit_result(args.output, dict(status='error', error=str(error)))
        return 1
    emit_result(args.output, result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
