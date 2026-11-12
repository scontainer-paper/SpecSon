#!/usr/bin/env python3
"""Run the formal mixed query workload sequentially under memory limits."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from protocol import atomic_json, stamp, query_reference
from memory_budget import PG_IO_COMBINE_KIB, PG_IO_CONCURRENCY, PG_IO_METHOD, PG_IO_WORKERS
from summarize_memory_queries import summarize
from umbra_runtime import docker
from cpu_config import CLIENT_CPU
from run import dataset_manifest, queries

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RESULTS = ROOT/'results'
REFERENCE = RESULTS/'reference/results.json'
COMPARISON = RESULTS/'reference/results.json'
SYSTEMS = ('specson', 'specson-toast', 'jsonb', 'pg-gin', 'umbra', 'mongodb', 'asterix')
BUDGETS = (32, 16, 8, 4, 2, 1)


def validate(path, memory, system, reference):
    data = json.loads(path.read_text())
    if data['status'] not in ('ok', 'completed_with_oom') or data['system'] != system:
        raise ValueError(f'Incomplete run: {path}')
    rows = data['results']
    if len(rows) != len(reference) or {r['query'] for r in rows} != reference.keys():
        raise ValueError(f'Incomplete query coverage: {path}')
    cpus = rows[0]['metadata']['backend_cpus']
    if len(cpus) != 4 or len(set(cpus)) != 4:
        raise ValueError(f'Expected four database CPUs: {path}')
    for row in rows:
        meta = row['metadata']
        limit = meta.get('memory_limit_bytes', meta.get('container_memory_bytes'))
        swap = meta.get('swap_limit_bytes', meta.get('swap_bytes'))
        if (row['warmups'], row['runs'], limit, swap, meta['backend_cpus']) != (
                1, 3, memory*1024**3, 0, cpus):
            raise ValueError(f'Wrong measurement conditions: {path}: {row["query"]}')
        if row['status'] == 'ok':
            if len(row['times_ms']) != 3 or row['completed_executions'] != 4:
                raise ValueError(f'Missing repetitions: {path}: {row["query"]}')
            if row['result_signature'] != reference[row['query']]:
                raise ValueError(f'Result mismatch: {path}: {row["query"]}')
        elif row['status'] != 'oom' or not row.get('error') or not row.get('failed_phase'):
            raise ValueError(f'Unclassified failure: {path}: {row["query"]}')
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                queries=len(rows), successful=sum(r['status']=='ok' for r in rows),
                oom=[r['query'] for r in rows if r['status']=='oom'])


def stop_databases():
    from prepare_postgres import prepare
    from types import SimpleNamespace
    prepare(SimpleNamespace(action='stop', port=56539, runtime_dir=HERE/'runtime/postgres-mixed'))
    for label in ('specson.public.owner', 'specson.public.documents=1'):
        for name in docker('ps', '-q', '--filter', 'label='+label).splitlines():
            docker('stop', name)


def main():
    global REFERENCE, COMPARISON
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--memory-gib', nargs='+', type=int, default=list(BUDGETS))
    parser.add_argument('--reference-results', type=Path, default=REFERENCE)
    parser.add_argument('--comparison-results', type=Path, default=COMPARISON)
    parser.add_argument('--data-dir', type=Path, default=ROOT/'datasets')
    parser.add_argument('--skip-twitter', action='store_true', help='Use a mixed table without Twitter')
    parser.add_argument('--systems', nargs='+', choices=SYSTEMS, default=list(SYSTEMS))
    parser.add_argument('--github-only', action='store_true',
                        help='Run only the 16 GitHub Archive queries')
    parser.add_argument('--query', action='append', help='Select query IDs; repeat for multiple queries')
    parser.add_argument('--rerun-systems', nargs='+', choices=SYSTEMS, default=[],
                        help='Always rerun these systems instead of retaining prior results')
    parser.add_argument('--resume-from', type=Path,
                        help='Explicitly retain verified completed groups from a prior sweep')
    args = parser.parse_args()
    REFERENCE = args.reference_results.resolve()
    COMPARISON = args.comparison_results.resolve()
    root = args.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {CLIENT_CPU})
    ref = query_reference(REFERENCE)
    reference = {r['query']:r['result_signature'] for r in ref['results']}
    expected = {qid for d in dataset_manifest(args.data_dir, args.skip_twitter)
                for qid, _ in queries((HERE/'sql'/d['name']/'pg.sql').read_text())}
    if set(reference) != expected or {(r['warmups'], r['runs']) for r in ref['results']} != {(1, 3)}:
        raise ValueError('Unexpected 64 GiB reference workload')
    if args.github_only:
        reference = {q: value for q, value in reference.items() if q.startswith('G-')}
        if len(reference) != 16:
            raise ValueError('Unexpected GitHub query coverage')
    if args.query:
        if len(set(args.query)) != len(args.query) or not set(args.query) <= reference.keys():
            parser.error('Query IDs must be distinct members of the selected workload')
        reference = {q: value for q, value in reference.items() if q in args.query}
    state = dict(status='running', started_at=stamp(), pid=os.getpid(),
                 memory_gib=args.memory_gib, systems=args.systems, queries=len(reference),
                 github_only=args.github_only,
                 skip_twitter=args.skip_twitter,
                 selected_queries=list(reference), rerun_systems=args.rerun_systems,
                 warmups=1, runs=3, reference=str(REFERENCE), comparison=str(COMPARISON),
                 postgres_io_concurrency=PG_IO_CONCURRENCY, postgres_io_combine_kib=PG_IO_COMBINE_KIB,
                 postgres_io_method=PG_IO_METHOD, postgres_io_workers=PG_IO_WORKERS,
                 commands=[], completed=[])
    manifest = root/'protocol.json'
    atomic_json(manifest, state)
    retained = {}
    partial = {}
    if args.resume_from:
        previous = json.loads((args.resume_from/'protocol.json').read_text())
        candidates = list(previous['completed'])
        current = previous.get('current')
        if (args.github_only or args.query) and current:
            source = args.resume_from/f"{current['memory_gib']}g"/f"{current['system']}-query.json"
            if source.exists():
                candidates.append(dict(memory_gib=current['memory_gib'],
                                       system=current['system'], path=str(source)))
        candidates.extend(previous.get('retained_sources', []))
        seen = set()
        for item in candidates:
            key = (item['memory_gib'], item['system'])
            if key in seen:
                continue
            seen.add(key)
            if item['memory_gib'] not in args.memory_gib or item['system'] not in args.systems:
                continue
            if item['system'] in args.rerun_systems:
                continue
            if args.github_only or args.query:
                source = Path(item['path'])
                raw = source.read_bytes()
                if item.get('sha256') and hashlib.sha256(raw).hexdigest() != item['sha256']:
                    raise ValueError('Previously completed result has changed')
                selected = json.loads(raw)
                selected['results'] = [r for r in selected['results']
                    if r['query'] in reference and r['status'] in ('ok', 'oom')]
                if not selected['results']:
                    continue
                selected_reference = {r['query']: reference[r['query']] for r in selected['results']}
                selected['status'] = ('completed_with_oom' if any(
                    r['status']=='oom' for r in selected['results']) else 'ok')
                selected.pop('current', None)
                selected.pop('error', None)
                selected['selected_from'] = dict(path=str(source),
                    sha256=hashlib.sha256(raw).hexdigest())
                destination = root/'retained'/f"{item['memory_gib']}g-{item['system']}.json"
                destination.parent.mkdir(exist_ok=True)
                atomic_json(destination, selected)
                proof = validate(destination, item['memory_gib'], item['system'], selected_reference)
                item = dict(memory_gib=item['memory_gib'], system=item['system'], **proof)
                if selected_reference.keys() != reference.keys():
                    key = (item['memory_gib'], item['system'])
                    if key in partial or key in retained:
                        raise ValueError('Duplicate previously completed group')
                    partial[key] = dict(item, retained_from=str(args.resume_from.resolve()))
                    continue
            proof = validate(Path(item['path']), item['memory_gib'], item['system'], reference)
            if proof['sha256'] != item['sha256']:
                raise ValueError('Previously completed result has changed')
            key = (item['memory_gib'], item['system'])
            if key in retained:
                raise ValueError('Duplicate previously completed group')
            retained[key] = dict(item, retained_from=str(args.resume_from.resolve()))
        state['resume_from'] = str(args.resume_from.resolve())
        # Preserve groups not yet reached by this run if another resume is needed.
        state['retained_sources'] = list(retained.values()) + list(partial.values())
        atomic_json(manifest, state)

    def execute(command, name):
        event = dict(command=list(map(str, command)), started_at=stamp())
        state['commands'].append(event)
        error_path = root/(name+'.stderr')
        with error_path.open('x') as error:
            process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=error)
            event['pid'] = process.pid
            atomic_json(manifest, state)
            code = process.wait()
        event.update(returncode=code, finished_at=stamp())
        atomic_json(manifest, state)
        if code:
            raise RuntimeError(f'{name} exited {code}: {error_path.read_text()[-3000:]}')
        if error_path.stat().st_size == 0:
            error_path.unlink()

    try:
        for memory in args.memory_gib:
            folder = root/f'{memory}g'
            folder.mkdir()
            paths = []
            for system in args.systems:
                if (memory, system) in retained:
                    item = retained[(memory, system)]
                    state['completed'].append(item)
                    paths.append(Path(item['path']))
                    atomic_json(manifest, state)
                    continue
                state['current'] = dict(memory_gib=memory, system=system, started_at=stamp())
                atomic_json(manifest, state)
                stop_databases()
                if system in ('specson', 'specson-toast', 'jsonb', 'pg-gin'):
                    execute([sys.executable, HERE/'prepare_postgres.py', 'start', '--cores', '4',
                        '--port', '56539', '--runtime-dir', HERE/'runtime/postgres-mixed',
                        '--memory-gib', str(memory),
                        '--output', folder/f'{system}-setup.json'], f'{memory}g-{system}-setup')
                base = 'jsonb' if system=='pg-gin' else 'specson' if system=='specson-toast' else system
                result = folder/f'{system}-query.json'
                prior = partial.get((memory, system))
                prior_rows = {}
                if prior:
                    source = Path(prior['path'])
                    raw = source.read_bytes()
                    if hashlib.sha256(raw).hexdigest() != prior['sha256']:
                        raise ValueError('Previously retained queries changed')
                    prior_rows = {r['query']: r for r in json.loads(raw)['results']}
                remaining = {q: value for q, value in reference.items() if q not in prior_rows}
                measured = folder/f'{system}-query-new.json' if prior else result
                command = [sys.executable, HERE/'run_mixed.py', 'query', '--system', base,
                    '--data-dir', args.data_dir, '--synthetic-dir', args.data_dir/'synthetic',
                    '--cores', '4', '--memory-gib', str(memory), '--clear-os-cache',
                    '--continue-on-oom', '--warmups', '1', '--runs', '3', '--verify-results',
                    '--reference-results', REFERENCE, '--output', measured]
                if args.skip_twitter:
                    command += ['--skip-twitter']
                if system=='pg-gin':
                    command += ['--gin']
                if system=='specson-toast':
                    command += ['--specson-storage', 'toast']
                if args.github_only or args.query or prior:
                    for query in remaining:
                        command += ['--query', query]
                execute(command, f'{memory}g-{system}-query')
                if prior:
                    validate(measured, memory, system, remaining)
                    combined = json.loads(measured.read_text())
                    all_rows = dict(prior_rows, **{r['query']: r for r in combined['results']})
                    combined['results'] = [all_rows[q] for q in reference]
                    combined['status'] = ('completed_with_oom' if any(
                        r['status']=='oom' for r in combined['results']) else 'ok')
                    combined['retained_queries'] = dict(source=prior, queries=list(prior_rows))
                    combined['new_queries'] = dict(path=str(measured),
                        sha256=hashlib.sha256(measured.read_bytes()).hexdigest())
                    atomic_json(result, combined)
                proof = validate(result, memory, system, reference)
                state['completed'].append(dict(memory_gib=memory, system=system, **proof))
                paths.append(result)
                atomic_json(manifest, state)
                stop_databases()
            atomic_json(folder/'comparison.json', summarize(paths, COMPARISON))
        # Reopen every result after all runs; successful exit alone is insufficient.
        for item in state['completed']:
            proof = validate(Path(item['path']), item['memory_gib'], item['system'], reference)
            if proof['sha256'] != item['sha256']:
                raise ValueError('A completed result changed during the experiment')
        if len(state['completed']) != len(args.memory_gib)*len(args.systems):
            raise ValueError('Incomplete memory/system matrix')
        state.update(status='complete', finished_at=stamp())
        state.pop('current', None)
        atomic_json(manifest, state)
        os.sync()
    except BaseException as error:
        state.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'error',
                     error=str(error), finished_at=stamp())
        atomic_json(manifest, state)
        stop_databases()
        raise


if __name__ == '__main__':
    main()
