#!/usr/bin/env python3
"""Measure diagnostic R-B1/E latency using unchanged verified normal workers.

One E round per band/case with adjacent R controls. Never freezes B_ref,
selects a band, or satisfies formal comparison/PR gates. Preserve every round.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import uuid

spec = importlib.util.spec_from_file_location('baseline', Path(__file__).with_name('run-wavefront-baseline.py'))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


def summarize_pairs(pairs, expected_bands=(64,128,256)):
    rows = []
    references = []
    for pair in pairs:
        R, E = pair['R']['scores'], pair['E']['scores']
        valid = R['valid'] and E['valid']
        if R['valid']:
            references.append(R['median_seconds'])
        rows.append({'band': pair['band'], 'rounds_valid': valid,
            'R_median_ms': R.get('median_seconds', None) * 1000 if R.get('median_seconds') is not None else None,
            'E_median_ms': E.get('median_seconds', None) * 1000 if E.get('median_seconds') is not None else None,
            'R_p95_ms': R.get('p95_seconds', None) * 1000 if R.get('p95_seconds') is not None else None,
            'E_p95_ms': E.get('p95_seconds', None) * 1000 if E.get('p95_seconds') is not None else None,
            'E_over_adjacent_R_median_ratio': E['median_seconds'] / R['median_seconds'] if valid else None,
            'R_FPS': R.get('throughput_fps'), 'E_FPS': E.get('throughput_fps'),
            'R_requests': R.get('request_count'), 'E_requests': E.get('request_count')})
    complete = sorted(pair['band'] for pair in pairs) == sorted(expected_bands)
    drift = max(references) / min(references) - 1 if complete and len(references) == len(expected_bands) and len(references)>1 else None
    return {'pairs': rows, 'R_median_range_ratio': drift,
        'R_timing_review_required': drift is None or drift > .05,
        'all_rounds_valid': complete and all(row['rounds_valid'] for row in rows),
        'B_ref_frozen': False, 'performance_acceptance': False}


def main(helper):
    p = argparse.ArgumentParser(description=__doc__)
    for n in ('reference', 'fixtures', 'verification', 'baseline-report', 'output'):
        p.add_argument('--' + n, type=Path, required=True)
    p.add_argument('--bands',default='64,128,256')
    a = p.parse_args()
    bands=tuple(map(int,a.bands.split(',')))
    if not bands or len(set(bands))!=len(bands) or any(x not in (64,128,256,512) for x in bands):
        raise ValueError('unique supported diagnostic bands required')
    c = Path(__file__).resolve().parents[1]
    r = a.reference.resolve()
    f = json.loads(a.fixtures.read_text())
    v = json.loads(a.verification.read_text())
    old = json.loads(a.baseline_report.read_text())
    if r == c or subprocess.check_output(['git', '-C', str(r), 'status', '--porcelain'], text=True).strip():
        raise ValueError('separate clean R required')
    if subprocess.check_output(['git', '-C', str(r), 'rev-parse', 'HEAD'], text=True).strip() != f['source_base']:
        raise ValueError('R base changed')
    if not v['complete'] or not v['normal_experimental_kernel_coverage'] or any(not x['comparison']['passed'] for x in v['results']):
        raise ValueError('complete normal pixel verification required')
    if v['frozen_cases_sha256'] != b.sha(a.fixtures) or v['reference_base'] != f['source_base']:
        raise ValueError('normal verification fixture/base mismatch')
    if v['common_driver_sha256'] != b.sha(c/'tools/wavefront-benchmark.mm') or f['tool_sources']['wavefront_metrics.py'] != b.sha(c/'tools/wavefront_metrics.py'):
        raise ValueError('measurement worker source or statistics changed')
    workers = {'R': r/'build/wavefront-benchmark-v2/instrumented/runner',
        **{f'E{band}': Path(v.get('C_worker_paths',{}).get(f'E_{band}',str(a.verification.resolve().parent/f'band-{band}/runner'))) for band in bands}}
    for name, worker in workers.items():
        expected = f['worker_sha256'] if name == 'R' else v['C_worker_sha256']['E_' + name[1:]]
        if b.sha(worker) != expected:
            raise ValueError('verified worker changed: ' + name)
    if v['R_worker_sha256'] != f['worker_sha256'] or len(f['cases']) != 4:
        raise ValueError('normal reference identity or primary cases changed')
    for case in f['cases']:
        for key in ('input', 'pack'):
            if b.sha(case[key]) != case[key + '_sha256']:
                raise ValueError('frozen fixture changed')
    root = a.output.resolve()/uuid.uuid4().hex[:12]
    root.mkdir(parents=True)
    report = {'scope': __doc__, 'complete': False, 'B_ref_frozen': False,
        'performance_acceptance': False, 'band_selected': None, 'Docker_shutdown_performed': False,
        'protocol': {'warmup_seconds': 5, 'measurement_seconds': 30, 'tail_seconds': 2,
            'retained_idle_seconds': 5, 'inflight_frames': 1, 'pool_MiB': 1024,
            'fresh_process_each_round': True, 'R_mode': 'B1', 'E_rounds_per_band_case': 1,
            'ring_rows':v.get('ring_rows',1024),'R_controls_per_case':len(bands),
            'pair_order': {str(band):(['R','E'] if i%2==0 else ['E','R']) for i,band in enumerate(bands)}},
        'source_base': f['source_base'], 'candidate_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=c, text=True).strip(),
        'environment': b.environment_snapshot(), 'workers': {n:{'path':str(w), 'sha256':b.sha(w)} for n,w in workers.items()},
        'sources': {n:b.sha(c/'tools'/n) for n in ('run-wavefront-latency-diagnostic.py','run-wavefront-baseline.py','wavefront-benchmark.mm','wavefront_metrics.py')},
        'source_reports': {str(path.resolve()):b.sha(path) for path in (a.fixtures,a.verification,a.baseline_report)},
        'old_baseline_usage': 'pixel hash only; old scores/epsilon not used', 'cases': {},
        'limitations': ['One E window per band/case; no E between-round reproducibility estimate.',
            'Each ratio uses its adjacent R-B1 control; R-B1 is not a frozen B_ref.',
            'Shared memory/thermal/background GPU variability remains uncontrolled; Docker remains running.',
            'Whole synchronous API includes upload/dispatch/wait/readback, excludes image decoding/file output and application display.',
            'API timing includes the same lightweight counters in R/E; resource detail observers are absent.',
            'No tuning/holdout decision or formal speed/memory/PR acceptance.']}
    def save():
        b.atomic_json(root/'report.json',report)
        b.atomic_json(a.output.resolve()/'latest.json',{'report':str(root/'report.json')})
    save()
    print('RUN',root,flush=True)
    try:
        for case in f['cases']:
            entry = {'pairs': []}
            report['cases'][case['id']] = entry
            for band_index,band in enumerate(bands):
                pair = {'band':band}
                entry['pairs'].append(pair)
                for arm in (('R','E') if band_index%2==0 else ('E','R')):
                    b.require_awake(helper)
                    if shutil.disk_usage(root).free < 2*1024**3:
                        raise RuntimeError('less than 2 GiB free; evidence saved')
                    out = root/case['id']/f'{band}-{arm}'
                    out.parent.mkdir(parents=True,exist_ok=True)
                    b.atomic_json(out.with_name(out.name+'-environment.json'),b.environment_observation(root))
                    result = b.run_round(workers['R' if arm=='R' else f'E{band}'],Path(case['pack']),Path(case['input']),
                        'B1' if arm=='R' else 'E',out,expected_band=band if arm=='E' else None,
                        expected_ring_rows=v.get('ring_rows',1024))
                    phases = [e for e in result['phase_events'] if e['type'] in ('warmup_complete','measurement_complete')]
                    if arm == 'R':
                        expected = next(e['output_sha256'] for e in old['cases'][case['id']]['arms']['B1'][0]['phase_events'] if e['type']=='measurement_complete')
                    else:
                        expected = next(x['C_output_sha256'] for x in v['results'] if x['case']==case['id'] and x['candidate']==f'E_{band}')
                    if len(phases)!=2 or any(e['output_sha256']!=expected for e in phases):
                        result['scores']['valid']=False
                        result['scores']['reasons'].append('phase output does not match frozen own-arm pixel hash')
                        result['scores']['statistics_are_diagnostic_only']=True
                        b.atomic_json(out/'round.json',result)
                    pair[arm] = b.compact(result,out/'round.json')
                    save()
                    print(json.dumps({'case':case['id'],'band':band,'arm':arm,'scores':result['scores']},ensure_ascii=False),flush=True)
                    if not result['scores']['valid']:
                        raise RuntimeError('invalid round preserved; no replacement')
                entry['assessment'] = summarize_pairs([x for x in entry['pairs'] if 'R' in x and 'E' in x],expected_bands=bands)
                save()
        report['complete']=True
    except BaseException as error:
        report['failure']=str(error)
        raise
    finally:
        save()
    print('REPORT',root/'report.json',flush=True)


if __name__ == '__main__':
    with b.awake_session() as helper:
        main(helper)
