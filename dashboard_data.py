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
from traffic import Flow, Event
from audited_hybrid import AuditedHybrid

POLICIES = (Fixed, FixedPath, FlowAdaptive, PathAdaptive, Hybrid, AuditedHybrid)
POLICY_LABELS = {'fixed': 'Fixed flow', 'fixed_path': 'Fixed path batch',
                 'flow_adaptive': 'Adaptive flow', 'path_adaptive': 'Adaptive path',
                 'hybrid': 'Hybrid path-to-flow', 'audited_hybrid': 'Hybrid + periodic audit'}
FLOW_COUNTS = [6, *range(12, 21)]


def validate(data):
    if not isinstance(data, dict):
        raise ValueError('Configuration must be a JSON object.')
    if set(data) - {'scenario', 'seed', 'flow_count', 'policy', 'custom_events', 'audit_interval'}:
        raise ValueError('Unknown configuration field.')
    config = {'scenario': data.get('scenario', 'single'), 'seed': data.get('seed', 7),
              'flow_count': data.get('flow_count', 6), 'policy': data.get('policy', 'hybrid')}
    if config['scenario'] not in (*SCENARIOS, 'custom'):
        raise ValueError('Choose single, simultaneous, offsetting or custom.')
    if not isinstance(config['policy'], str) or config['policy'] not in POLICY_LABELS:
        raise ValueError('Unknown policy.')
    if type(config['seed']) is not int or not 0 <= config['seed'] <= 2147483647:
        raise ValueError('Seed must be an integer between 0 and 2147483647.')
    if type(config['flow_count']) is not int or config['flow_count'] not in FLOW_COUNTS:
        raise ValueError('Flow count must be 6 or an integer from 12 to 20.')
    interval = data.get('audit_interval', 8)
    if type(interval) is not int or not 2 <= interval <= 32:
        raise ValueError('Audit interval must be an integer from 2 to 32 seconds.')
    config['audit_interval'] = interval
    if config['scenario'] == 'custom':
        rows = data.get('custom_events', [])
        if not isinstance(rows, list) or not 1 <= len(rows) <= 20:
            raise ValueError('Custom scenarios require 1–20 events.')
        events = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != {'flow', 'start', 'duration', 'multiplier'}:
                raise ValueError('Each custom event needs flow, start, duration and multiplier.')
            if row['flow'] not in [f'f{i}' for i in range(config['flow_count'])]:
                raise ValueError('Custom event references a flow outside the workload.')
            if type(row['start']) is not int or type(row['duration']) is not int or not (0 <= row['start'] < 180 and 1 <= row['duration'] <= 180 - row['start']):
                raise ValueError('Event start/duration must be whole seconds within [0, 180).')
            multiplier = row['multiplier']
            if type(multiplier) not in (int, float) or not math.isfinite(multiplier) or not 1 < multiplier <= 8:
                raise ValueError('Spike multiplier must be greater than 1 and at most 8.')
            event = {**row, 'multiplier': float(multiplier)}
            if any(e['flow'] == event['flow'] and event['start'] < e['start'] + e['duration'] and e['start'] < event['start'] + event['duration'] for e in events):
                raise ValueError('Events on the same flow must not overlap.')
            events.append(event)
        config['custom_events'] = sorted(events, key=lambda e: (e['start'], e['flow']))
    elif data.get('custom_events'):
        raise ValueError('Custom events require the custom scenario.')
    return config


def build_trace(config):
    trace = scenario('single' if config['scenario'] == 'custom' else config['scenario'], config['seed'])
    if config['scenario'] == 'custom':
        for event in trace.events:
            for t in range(event.start, event.end):
                trace.rates[event.flow][t] /= 3
        trace.events = []
    for i in range(6, config['flow_count']):
        # Independent RNGs preserve all six original flows and event timing exactly.
        rng = random.Random(f"background:{config['seed']}:{i}")
        flow = Flow(f'f{i}', f'p{(i-6) % 3}', float(10 + 5 * (i % 6)))
        trace.flows.append(flow)
        trace.rates[flow.name] = [flow.reference * (1 + .04 * math.sin(t / 11 + i)
                                                 + rng.uniform(-.02, .02))
                                  for t in range(trace.duration)]
    if config['scenario'] == 'custom':
        for event in config['custom_events']:
            end = event['start'] + event['duration']
            trace.events.append(Event(event['flow'], event['start'], end))
            for t in range(event['start'], end):
                trace.rates[event['flow']][t] *= event['multiplier']
    return trace


def execute(data):
    config = validate(data)
    trace = build_trace(config)
    settings = Settings()
    results = []
    for cls in POLICIES:
        policy = (cls(trace.flows, settings, config['audit_interval']) if cls is AuditedHybrid
                  else cls(trace.flows, settings))
        result = run(trace, policy, settings)
        results.append({**asdict(result), 'transitions': getattr(policy, 'transitions', []),
                        'audits': getattr(policy, 'audits', [])})
    return {'schema_version': 2,
            'run_id': hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:10],
            'config': config, 'settings': asdict(settings), 'trace': asdict(trace),
            'results': results}


def export_csv(payload, kind):
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer)
    config_columns = ['run_id', 'scenario', 'seed', 'flow_count', 'audit_interval', 'custom_events_json']
    prefix = [payload['run_id'], payload['config']['scenario'], payload['config']['seed'], payload['config']['flow_count'],
              payload['config']['audit_interval'], json.dumps(payload['config'].get('custom_events', []))]
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
