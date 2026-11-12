#!/usr/bin/env python3
"""Summarize one completed memory-budget query run, retaining OOM outcomes."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean

from protocol import emit_result


def summarize(paths, reference):
    previous = json.loads(reference.read_text())
    if 'mixed' in previous:
        previous = previous['mixed']['queries']
    old = {row['query']: row['median_ms'] for row in previous['results']}
    systems, sources, conditions, query_ids = {}, [], {}, None
    for path in paths:
        raw = path.read_bytes()
        data = json.loads(raw)
        if data['status'] not in ('ok', 'completed_with_oom'):
            raise ValueError(f'Run is not complete: {path}')
        system = data['system']
        if system in systems:
            raise ValueError(f'Duplicate system: {system}')
        rows = {row['query']: row for row in data['results']}
        if query_ids is None:
            query_ids = rows.keys()
        if rows.keys() != query_ids or not rows.keys() <= old.keys() or len(data['results']) != len(rows):
            raise ValueError(f'Incomplete query coverage: {path}')
        if any(row['status'] not in ('ok', 'oom') for row in rows.values()):
            raise ValueError(f'Unexpected query failure: {path}')
        systems[system] = rows
        first = data['results'][0]
        metadata = first['metadata']
        conditions[system] = dict(warmups=first['warmups'], runs=first['runs'],
            memory_limit_bytes=metadata.get('memory_limit_bytes', metadata.get('container_memory_bytes')),
            backend_cpus=metadata['backend_cpus'])
        if 'postgres_sha256' in metadata:
            conditions[system]['postgres_sha256'] = metadata['postgres_sha256']
            conditions[system]['io_settings'] = {key: metadata['settings'][key] for key in
                ('effective_io_concurrency', 'io_combine_limit', 'io_max_combine_limit', 'io_method', 'io_workers')
                if key in metadata['settings']}
        sources.append(dict(path=str(path.resolve()), sha256=hashlib.sha256(raw).hexdigest()))
    old = {q: row for q, row in old.items() if q in query_ids}
    common = [q for q in old if all(rows[q]['status']=='ok' for rows in systems.values())]
    results, totals = [], {}
    for query, previous_times in old.items():
        times, statuses, errors = {}, {}, {}
        for system, rows in systems.items():
            row = rows[query]
            statuses[system] = row['status']
            times[system] = row['statistics']['median_ms'] if row['status']=='ok' else None
            if row['status']=='oom':
                errors[system] = row['error']
        results.append(dict(query=query, median_ms=times, status=statuses,
                            errors=errors, reference_64g_ms=previous_times))
    for system, rows in systems.items():
        complete = [q for q in old if rows[q]['status']=='ok']
        current = mean(rows[q]['statistics']['median_ms'] for q in complete) if complete else None
        former = mean(old[q][system] for q in complete) if complete else None
        totals[system] = dict(completed=len(complete), oom=[q for q in old if rows[q]['status']=='oom'],
            mean_successful_ms=current, mean_64g_same_queries_ms=former,
            slowdown_vs_64g=current/former if former else None,
            mean_common_successful_ms=mean(rows[q]['statistics']['median_ms'] for q in common) if common else None)
    return dict(status='ok', queries=len(old), common_successful_queries=common,
                summary=totals, results=results, sources=sources, conditions=conditions,
                reference_64g=str(reference.resolve()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', nargs='+', type=Path)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    emit_result(args.output, summarize(args.results, args.reference))


if __name__ == '__main__':
    main()
