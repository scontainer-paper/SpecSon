#!/usr/bin/env python3
"""Prepare user-supplied Twitter stream records for the experiments."""
import argparse
import bz2
import gzip
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
from contextlib import ExitStack


ROOT = Path(__file__).resolve().parent.parent
PART_ROWS = 100_000


def lines(path):
    """Read JSONL files or compressed stream members without extracting a tar."""
    with ExitStack() as stack:
        if path.name.endswith(('.tar', '.tar.gz', '.tgz', '.tar.bz2')):
            archive = stack.enter_context(tarfile.open(path, 'r:*'))
            members = sorted((m for m in archive if m.isfile() and m.name.endswith(
                ('.json', '.jsonl', '.json.bz2', '.jsonl.bz2', '.json.gz', '.jsonl.gz'))),
                key=lambda m: m.name)
            for member in members:
                with ExitStack() as member_stack:
                    stream = member_stack.enter_context(archive.extractfile(member))
                    if member.name.endswith('.bz2'):
                        stream = member_stack.enter_context(bz2.BZ2File(stream))
                    elif member.name.endswith('.gz'):
                        stream = member_stack.enter_context(gzip.GzipFile(fileobj=stream))
                    for number, line in enumerate(stream, 1):
                        yield member.name, number, line
        else:
            opener = bz2.open if path.suffix == '.bz2' else gzip.open if path.suffix == '.gz' else open
            stream = stack.enter_context(opener(path, 'rb'))
            for number, line in enumerate(stream, 1):
                yield path.name, number, line


def prepare(inputs, data_dir):
    manifest_path = data_dir/'datasets.json'
    manifest = json.loads(manifest_path.read_text())
    config = next(d for d in manifest if d['name'] == 'twitter')
    target = data_dir/'twitter/data/parts'
    if target.exists():
        raise ValueError(f'Twitter output already exists: {target}')
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = skipped = 0
    output = None
    with tempfile.TemporaryDirectory(prefix='.prepare-', dir=target.parent) as temporary:
        parts = Path(temporary)/'parts'
        parts.mkdir()
        try:
            for path in inputs:
                for source, number, line in lines(path):
                    if not line.strip():
                        continue
                    try:
                        value = json.loads(line.decode('utf-8'))
                    except (ValueError, UnicodeError) as error:
                        raise ValueError(f'Invalid UTF-8 JSON: {source}:{number}') from error
                    if not (isinstance(value, dict) and type(value.get('id')) is int
                            and isinstance(value.get('text'), str) and isinstance(value.get('user'), dict)):
                        skipped += 1
                        continue
                    if rows % PART_ROWS == 0:
                        if output is not None:
                            output.close()
                        output = (parts/f'{rows // PART_ROWS:06d}.jsonl').open('wb')
                    output.write(line.rstrip(b'\r\n') + b'\n')
                    rows += 1
        finally:
            if output is not None:
                output.close()
        if not rows:
            raise ValueError('No tweet objects with integer id, string text, and object user were found')
        config.update(rows=rows, files=['data/parts/*.jsonl'])
        updated = Path(temporary)/'datasets.json'
        updated.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        parts.rename(target)
        try:
            updated.replace(manifest_path)
        except BaseException:
            shutil.rmtree(target)
            raise
    return rows, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='+', type=Path, help='JSONL, JSONL.gz, JSONL.bz2, or stream tar archives')
    parser.add_argument('--data-dir', type=Path, default=ROOT/'datasets')
    args = parser.parse_args()
    rows, skipped = prepare([p.expanduser().resolve() for p in args.inputs], args.data_dir.resolve())
    print(f'Prepared {rows} tweets; skipped {skipped} other records. Updated datasets.json.')


if __name__ == '__main__':
    main()
