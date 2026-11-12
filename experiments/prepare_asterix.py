#!/usr/bin/env python3
"""Install the official AsterixDB distribution, or stop the owned instance."""
import argparse
import hashlib
from pathlib import Path
import re
import tempfile
import zipfile

import requests
from protocol import emit_result
from run import CONNECTIONS
from umbra_runtime import docker


def prepare(action):
    config = CONNECTIONS['asterix']
    if action == 'stop':
        docker('stop', config['container'])
        return dict(status='ok', action=action, container=config['container'])
    target = Path(config['distribution'])
    if target.exists():
        raise RuntimeError('Distribution directory already exists')
    target.parent.mkdir(parents=True, exist_ok=True)
    url = ('https://archive.apache.org/dist/asterixdb/asterixdb-0.9.9/'
           'asterix-server-0.9.9-binary-assembly.zip')
    response = requests.get(url+'.sha512', timeout=60)
    response.raise_for_status()
    expected = re.search(r'\b[0-9a-fA-F]{128}\b', response.text).group().lower()
    digest = hashlib.sha512()
    with tempfile.TemporaryFile() as archive:
        with requests.get(url, stream=True, timeout=60) as response:
            response.raise_for_status()
            for chunk in response.iter_content(1024*1024):
                digest.update(chunk)
                archive.write(chunk)
        if digest.hexdigest() != expected:
            raise RuntimeError('AsterixDB archive SHA512 mismatch')
        archive.seek(0)
        with zipfile.ZipFile(archive) as package:
            for member in package.infolist():
                path = (target.parent/member.filename).resolve()
                if not path.is_relative_to(target.parent.resolve()):
                    raise RuntimeError('Archive member outside installation directory')
            package.extractall(target.parent)
            for member in package.infolist():
                mode = member.external_attr >> 16
                if mode:
                    (target.parent/member.filename).chmod(mode & 0o777)
    if not (target/'bin/asterixcc').is_file():
        raise RuntimeError('Unexpected distribution layout')
    return dict(status='ok', action=action, url=url, sha512=expected, directory=str(target))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'stop'])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        result = prepare(args.action)
    except Exception as error:
        emit_result(args.output, dict(status='error', error=str(error)))
        return 1
    emit_result(args.output, result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
