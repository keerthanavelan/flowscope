"""Dashboard adapter. Existing generators, policies and evaluator stay untouched."""
import csv
import hashlib
import io
import json
import math
import random
from dataclasses import asdict

from algorithms import Fixed, FlowAdaptive, PathAdaptive, Settings
from hybrid import FixedPath, Hybrid
from scenarios import SCENARIOS, scenario
from simulation import run
from traffic import Flow

POLICIES = (Fixed, FixedPath, FlowAdaptive, PathAdaptive, Hybrid)
POLICY_LABELS = {'fixed': 'Fixed flow', 'fixed_path': 'Fixed path batch',
                 'flow_adaptive': 'Adaptive flow', 'path_adaptive': 'Adaptive path',
                 'hybrid': 'Hybrid path-to-flow'}
FLOW_COUNTS = [6, *range(12, 21)]


def validate(data):
    if not isinstance(data, dict):
        raise ValueError('Configuration must be a JSON object.')
    if set(data) - {'scenario', 'seed', 'flow_count', 'policy'}:
        raise ValueError('Unknown configuration field.')
    config = {'scenario': data.get('scenario', 'single'), 'seed': data.get('seed', 7),
              'flow_count': data.get('flow_count', 6), 'policy': data.get('policy', 'hybrid')}
    if config['scenario'] not in SCENARIOS:
        raise ValueError('Choose single, simultaneous or offsetting.')
    if not isinstance(config['policy'], str) or config['policy'] not in POLICY_LABELS:
        raise ValueError('Unknown policy.')
    if type(config['seed']) is not int or not 0 <= config['seed'] <= 2147483647:
        raise ValueError('Seed must be an integer between 0 and 2147483647.')
    if type(config['flow_count']) is not int or config['flow_count'] not in FLOW_COUNTS:
        raise ValueError('Flow count must be 6 or an integer from 12 to 20.')
    return config


def build_trace(config):
    trace = scenario(config['scenario'], config['seed'])
    for i in range(6, config['flow_count']):
        # Independent RNGs preserve all six original flows and event timing exactly.
        rng = random.Random(f"background:{config['seed']}:{i}")
        flow = Flow(f'f{i}', f'p{(i-6) % 3}', float(10 + 5 * (i % 6)))
        trace.flows.append(flow)
        trace.rates[flow.name] = [flow.reference * (1 + .04 * math.sin(t / 11 + i)
                                                 + rng.uniform(-.02, .02))
                                  for t in range(trace.duration)]
    return trace


def execute(data):
    config = validate(data)
    trace = build_trace(config)
    settings = Settings()
    results = []
    for cls in POLICIES:
        policy = cls(trace.flows, settings)
        result = run(trace, policy, settings)
        results.append({**asdict(result), 'transitions': getattr(policy, 'transitions', [])})
    return {'schema_version': 1,
            'run_id': hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:10],
            'config': config, 'settings': asdict(settings), 'trace': asdict(trace),
            'results': results}


def export_csv(payload, kind):
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer)
    config_columns = ['run_id', 'scenario', 'seed', 'flow_count']
    prefix = [payload['run_id'], payload['config']['scenario'], payload['config']['seed'], payload['config']['flow_count']]
    if kind == 'metrics':
        keys = list(payload['results'][0]['metrics'])
        writer.writerow(config_columns + ['policy'] + keys)
        for result in payload['results']:
            writer.writerow(prefix + [result['name']] + [result['metrics'][key] for key in keys])
    elif kind == 'polls':
        writer.writerow(config_columns + ['policy', 'transaction_id', 'time_s', 'group', 'flows', 'records', 'messages', 'modeled_bytes'])
        for result in payload['results']:
            for i, poll in enumerate(result['polls']):
                records = len(poll['flows'])
                writer.writerow(prefix + [result['name'], i, poll['time'], poll['group'],
                                          '|'.join(poll['flows']), records, 2, 64 + 32 * records])
    else:
        raise ValueError('Unknown CSV export.')
    return buffer.getvalue()
