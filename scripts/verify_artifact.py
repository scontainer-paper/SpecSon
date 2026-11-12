#!/usr/bin/env python3
"""Check packaged dataset files and workload coverage without running experiments."""
import argparse
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root/'experiments'))
from run import dataset_manifest, load_dataset, queries
from protocol import query_reference

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-twitter', action='store_true', help='Check the package without Twitter input')
    args = parser.parse_args()
    inventory = json.loads((root/'datasets/files.json').read_text())
    if args.skip_twitter:
        inventory = [r for r in inventory if not r['path'].startswith('twitter/')]
    for record in inventory:
        path = root/'datasets'/record['path']
        if path.is_symlink() or path.stat().st_size != record['bytes']:
            raise ValueError('Missing, linked or changed dataset file: '+record['path'])
    manifest = dataset_manifest(root/'datasets', args.skip_twitter)
    if not args.skip_twitter and not list((root/'datasets/twitter/data/parts').glob('*.jsonl')):
        raise FileNotFoundError('Prepare Twitter data first: python scripts/prepare_twitter.py /path/to/twitter.jsonl')
    seen = set()
    for item in manifest:
        load_dataset(root/'datasets', item)
        variants = ['specson','pg','pg-gin','umbra','clickhouse','mongodb','asterix']
        query_ids = [set(q for q, _ in queries((root/'experiments/sql'/item['name']/(v+'.sql')).read_text())) for v in variants]
        if any(ids != query_ids[0] for ids in query_ids):
            raise ValueError('Query coverage mismatch: '+item['name'])
        seen.update(query_ids[0])
    reference = query_reference(root/'results/reference/results.json')
    expected = {r['query'] for r in reference['results']}
    if args.skip_twitter:
        expected -= {q for q,_ in queries((root/'experiments/sql/twitter/pg.sql').read_text())}
    if seen != expected:
        raise ValueError('Incomplete query coverage for the selected datasets')
    print(f'Verified {len(inventory)} dataset files; {len(seen)} queries across seven SQL variants.')

if __name__ == '__main__':
    main()
