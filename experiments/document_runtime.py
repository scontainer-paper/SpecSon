"""Owned local document database services with verified CPU/memory limits."""
import json
import os
from pathlib import Path
import time

import requests
from protocol import atomic_json
from umbra_runtime import docker


def activate(system, config, cpus):
    root=Path(config['directory']).resolve()
    root.mkdir(parents=True,exist_ok=True)
    name=config['container']
    owner={'system':system,'container':name,'directory':str(root)}
    marker=root/'owner.json'
    if marker.exists() and json.loads(marker.read_text())!=owner:
        raise RuntimeError('Document service ownership mismatch')
    data=root/'data'
    if data.exists() and not marker.exists():
        raise RuntimeError('Refusing an unowned document database directory')
    atomic_json(marker,owner)
    data.mkdir(exist_ok=True);data.chmod(0o777)
    for other in docker('ps','-q','--filter','label=specson.public.documents=1').splitlines():
        info=json.loads(docker('inspect',other))[0]
        if info['Name']!='/'+name:
            docker('stop',other)
    flags=['--network','host','--memory',str(config['memory_gib'])+'g',
           '--memory-swap',str(config['memory_gib'])+'g','--cpuset-cpus',','.join(map(str,sorted(cpus))),
           '--cpus',str(len(cpus))]
    command=[]
    if system=='mongodb':
        command=['mongod','--port',str(config['port']),'--bind_ip','127.0.0.1',
                 '--dbpath','/data','--directoryperdb','--wiredTigerCacheSizeGB',str(config['cache_gib']),
                 '--wiredTigerCollectionBlockCompressor',config.get('block_compressor','snappy')]
    else:
        settings=f'''[nc/formal_nc]
txn.log.dir=/data/txnlog
core.dump.dir=/data/coredump
iodevices=/data/p0,/data/p1,/data/p2,/data/p3
nc.api.port=56534

[nc]
address=127.0.0.1
command=asterixnc
jvm.args=-Xms{config.get('nc_initial_mib', 4096)}m -Xmx{config.get('nc_heap_mib', 49152)}m -XX:+UseG1GC -XX:ActiveProcessorCount={len(cpus)}
storage.buffercache.size={int(config['cache_gib']*1024**3)}
storage.memorycomponent.globalbudget={config.get('memory_component_bytes', 2147483648)}
# Avoid 0.9.9 result-page eviction lock inversion with concurrent partitions.
# Zero uses the native file-backed result path instead of ResultMemoryManager.
result.manager.memory=0

[cc]
address=127.0.0.1
api.port={config['port']}
console.listen.address=127.0.0.1

[common]
storage.partitions.count=4
compiler.parallelism={len(cpus)}
compiler.sortmemory={config.get('work_mem_mib', 256)*1024**2}
compiler.joinmemory={config.get('work_mem_mib', 256)*1024**2}
compiler.groupmemory={config.get('work_mem_mib', 256)*1024**2}
log.dir=/data/logs
log.level=WARN
'''
        (root/'asterix.conf').write_text(settings)
        (root/'start.sh').write_text(f'''#!/bin/bash
set -euo pipefail
cd /opt/asterix
mkdir -p /data/logs
export JAVA_OPTS='-Xms{config.get('service_initial_mib', 256)}m -Xmx{config.get('service_heap_mib', 1024)}m'
bin/asterixncservice -logdir /data/logs > /data/ncservice.log 2>&1 &
exec bin/asterixcc -config-file /setup/asterix.conf > /data/cc.log 2>&1
''')
        flags+=['-v',str(Path(config['distribution']).resolve())+':/opt/asterix:ro',
                '-v',str(root)+':/setup:ro']
        command=['bash','/setup/start.sh']
    desired={'image':config['image'],'cpus':sorted(cpus),'cache_gib':config['cache_gib'],
             'memory_gib':config['memory_gib'],'port':config['port']}
    if system=='asterix':
        desired['result_manager_memory']=0
        desired['memory_profile']={k:config[k] for k in
            ('nc_heap_mib','nc_initial_mib','service_heap_mib','service_initial_mib',
             'memory_component_bytes','work_mem_mib') if k in config}
    if system=='mongodb':desired['block_compressor']=config.get('block_compressor','snappy')
    saved=root/'service.json'
    existing=docker('ps','-aq','--filter','name=^/'+name+'$')
    if existing:
        info=json.loads(docker('inspect',name))[0]
        if info['Config'].get('Labels',{}).get('specson.public.directory')!=str(root):
            raise RuntimeError('Refusing to replace an unrelated container')
        if not saved.exists() or json.loads(saved.read_text())!=desired:
            docker('rm','-f',name);existing=''
    if not existing:
        docker('run','-d','--name',name,'--label','specson.public.documents=1',
               '--label','specson.public.directory='+str(root),*flags,
               '-v',str(data)+':/data',config['image'],*command)
        atomic_json(saved,desired)
    else:
        docker('start',name)
    deadline=time.monotonic()+180
    while True:
        try:
            if system=='mongodb':
                from pymongo import MongoClient
                with MongoClient(config['url'],serverSelectionTimeoutMS=1000) as client:
                    client.admin.command('ping')
            else:
                response=requests.get(config['url']+'/admin/cluster',timeout=2)
                response.raise_for_status()
                if response.json().get('state')!='ACTIVE':
                    raise RuntimeError('AsterixDB cluster is not active')
            break
        except Exception:
            if time.monotonic()>=deadline:
                raise RuntimeError('Document service startup timed out; inspect '+str(data))
            time.sleep(.5)
    info=json.loads(docker('inspect',name))[0]
    if os.sched_getaffinity(info['State']['Pid'])!=cpus:
        raise RuntimeError('Document service CPU affinity mismatch')
    if info['HostConfig']['Memory']!=config['memory_gib']*1024**3:
        raise RuntimeError('Document service memory limit mismatch')
    limits=info['HostConfig']
    if limits['MemorySwap']!=limits['Memory'] or limits['NanoCpus']!=len(cpus)*10**9:
        raise RuntimeError('Document service swap/CPU quota mismatch')
    status=Path(f"/proc/{info['State']['Pid']}/status").read_text()
    allowed=next(line.split(':',1)[1].strip() for line in status.splitlines()
                 if line.startswith('Cpus_allowed_list:'))
    return {'container':name,'backend_cpus':sorted(cpus),'cores':len(cpus),
            'container_memory_bytes':limits['Memory'],'cache_bytes':config['cache_gib']*1024**3,
            'swap_bytes':0,'cpu_quota_cores':len(cpus),'backend_allowed_cpus':allowed,
            'image_id':info['Image']}
