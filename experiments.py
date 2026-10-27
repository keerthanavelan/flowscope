"""Paired multi-seed evaluation; bounded synchronous jobs for a local demo."""
import csv
import io
import json
from statistics import mean, stdev
from dashboard_data import execute, validate, POLICIES


def experiment(data):
    if not isinstance(data, dict) or set(data) != {'config', 'seeds'}:
        raise ValueError('Experiment requires config and seeds.')
    config = validate(data['config'])
    seeds = data['seeds']
    if not isinstance(seeds, list) or not 2 <= len(seeds) <= 30:
        raise ValueError('Provide 2–30 distinct seeds.')
    if any(type(s) is not int or not 0 <= s <= 2147483647 for s in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError('Seeds must be distinct integers from 0 to 2147483647.')
    runs = []
    for seed in seeds:
        payload = execute({**config, 'seed': seed})
        runs.append({'seed': seed, 'run_id': payload['run_id'],
                     'results': [{'name': r['name'], 'metrics': r['metrics'], 'events': r['events']}
                                 for r in payload['results']]})
    aggregates = []
    for cls in POLICIES:
        results = [next(r for r in run['results'] if r['name'] == cls.name) for run in runs]
        stats = {}
        for key in results[0]['metrics']:
            values = [r['metrics'][key] for r in results if r['metrics'][key] is not None]
            stats[key] = {'mean': mean(values) if values else None,
                          'stddev': stdev(values) if len(values) > 1 else (0 if values else None),
                          'min': min(values) if values else None, 'max': max(values) if values else None,
                          'defined_runs': len(values)}
        delays = [e['delay_s'] for r in results for e in r['events'] if e['delay_s'] is not None]
        total = sum(r['metrics']['total_events'] for r in results)
        aggregates.append({'name': cls.name, 'metrics': stats, 'total_events': total,
                           'detected_events': len(delays), 'missed_events': total - len(delays),
                           'pooled_detection_delay_s': mean(delays) if delays else None})
    return {'schema_version': 1, 'config': config, 'seeds': seeds, 'runs': runs, 'aggregates': aggregates,
            'notes': 'Per-seed macro means; sample standard deviation (not confidence intervals). Undefined values excluded with counts. Pooled delay uses detected events only. Preset onset varies with seed; custom onset is fixed.'}


def experiment_csv(payload):
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer)
    writer.writerow(['seed', 'run_id', 'policy', 'metric', 'value', 'config_json'])
    for run in payload['runs']:
        for result in run['results']:
            for key, value in result['metrics'].items():
                writer.writerow([run['seed'], run['run_id'], result['name'], key, value,
                                 json.dumps({**payload['config'], 'seed': run['seed']}, sort_keys=True)])
    return buffer.getvalue()
