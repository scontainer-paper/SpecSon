"""Release owned database files after a completed experiment stage."""
import json
from pathlib import Path
import subprocess

from umbra_runtime import docker


def release(runtime, names):
    runtime = Path(runtime).resolve()
    candidates = [runtime/name for name in names]
    paths = [p.resolve() for p in candidates]
    if any(p.is_symlink() for p in candidates) or any(not p.is_relative_to(runtime) or p==runtime for p in paths):
        raise ValueError('Invalid experiment cleanup path')
    for ident in docker('ps','-aq','--filter','name=specson-public').splitlines():
        info=json.loads(docker('inspect',ident))[0]
        mounts=[Path(m['Source']) for m in info.get('Mounts',[]) if m.get('Type')=='bind']
        if any(m.is_relative_to(p) for p in paths for m in mounts):
            if info['State']['Running']:
                raise RuntimeError('Stop the experiment instance before releasing its files')
            docker('rm',ident)
    for path in paths:
        if path.exists():
            subprocess.run(['sudo','-n','rm','-rf','--',str(path)],check=True,
                           stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
