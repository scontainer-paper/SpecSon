#!/usr/bin/env python3
"""Compare explicit query result files after checking complete result signatures."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from protocol import emit_result


def compare(paths, replace=False):
    sources = []
    systems = {}
    for path in paths:
        raw = path.read_bytes()
        data = json.loads(raw)
        if data['status'] != 'ok' or data['operation'] != 'query':
            raise ValueError(f'Not a successful query result: {path}')
        name = data['system']
        records = {(r['dataset'], r['query']): r for r in data['results']}
        if len(records) != len(data['results']):
            raise ValueError(f'Duplicate query: {path}')
        collected = systems.setdefault(name,{})
        overlap = collected.keys() & records.keys()
        if overlap and not replace:
            raise ValueError(f'Duplicate query for {name}: {path}')
        for key in overlap:
            old, new = collected[key], records[key]
            if (old['status'] != 'ok' or new['status'] != 'ok'
                    or old['result_signature'] != new['result_signature']):
                raise ValueError(f'Replacement result mismatch: {name} {key}')
        collected.update(records)
        sources.append(dict(system=name, path=str(path.resolve()),
                            sha256=hashlib.sha256(raw).hexdigest()))
        if overlap:
            sources[-1]['replaces_queries'] = [dict(dataset=d, query=q)
                                               for d, q in sorted(overlap)]
    baseline = next(iter(systems))
    keys = systems[baseline].keys()
    if any(records.keys() != keys for records in systems.values()):
        raise ValueError('Query sets differ')
    rows = []
    for key in keys:
        reference = systems[baseline][key]
        times = {}
        for name, records in systems.items():
            record = records[key]
            if record['status'] != 'ok' or record['result_signature'] != reference['result_signature']:
                raise ValueError(f'Result mismatch: {name} {key}')
            times[name] = record['statistics']['median_ms']
        rows.append(dict(dataset=key[0], query=key[1], median_ms=times,
                         ratios_to_baseline={name: ms/times[baseline] for name, ms in times.items()}))
    summary = {}
    for name in systems:
        ratios = [r['ratios_to_baseline'][name] for r in rows]
        summary[name] = dict(sum_medians_ms=sum(r['median_ms'][name] for r in rows),
                             geometric_mean_ratio=math.exp(sum(map(math.log, ratios))/len(ratios)),
                             baseline_faster=sum(r > 1 for r in ratios))
    return dict(status='ok', baseline=baseline, queries=len(rows),
                all_results_match=True, sources=sources, summary=summary, results=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', nargs='+', type=Path, help='First file is the comparison baseline')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--replace', action='store_true',
                        help='Later files replace matching queries after verifying equal results')
    args = parser.parse_args()
    try:
        result = compare(args.results, replace=args.replace)
    except Exception as error:
        emit_result(args.output, dict(status='error', error=str(error)))
        return 1
    emit_result(args.output, result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
