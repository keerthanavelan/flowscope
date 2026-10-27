"""Discrete one-second simulation and common per-flow evaluation."""
from dataclasses import dataclass


@dataclass
class Result:
    name: str
    metrics: dict
    alarms: dict
    polls: list
    events: list


def run(trace, policy, settings):
    reference = {f.name: f.reference for f in trace.flows}
    held = {f.name: False for f in trace.flows}
    alarms = {f.name: [] for f in trace.flows}
    polls = []
    tp = fp = tn = fn = 0
    for t in range(trace.duration):
        for key in policy.select(t):
            values = {f: trace.rates[f][t] for f in policy.groups[key]}
            polls.append({'time': t, 'group': key, 'flows': list(values)})
            for f, rate in values.items():
                held[f] = rate >= settings.alarm_multiplier * reference[f]
            policy.observe(key, t, values)
        for f in held:
            truth = any(e.flow == f and e.start <= t < e.end for e in trace.events)
            alarm = held[f]
            alarms[f].append(alarm)
            tp += int(truth and alarm)
            fp += int(not truth and alarm)
            tn += int(not truth and not alarm)
            fn += int(truth and not alarm)
    event_results = []
    for e in trace.events:
        # Require a fresh positive sample inside the event, not a stale alarm.
        hits = [p['time'] for p in polls if e.flow in p['flows']
                and e.start <= p['time'] < e.end
                and trace.rates[e.flow][p['time']] >= settings.alarm_multiplier * reference[e.flow]]
        delay = min(hits) - e.start if hits else None
        event_results.append({'flow': e.flow, 'start': e.start, 'end': e.end, 'delay_s': delay})
    delays = [e['delay_s'] for e in event_results if e['delay_s'] is not None]
    records = sum(len(p['flows']) for p in polls)
    ratio = lambda a, b: a / b if b else None
    metrics = {'poll_transactions': len(polls), 'messages': 2 * len(polls),
               'records': records, 'modeled_bytes': 64 * len(polls) + 32 * records,
               'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn,
               'accuracy': ratio(tp + tn, tp + fp + tn + fn),
               'precision': ratio(tp, tp + fp), 'recall': ratio(tp, tp + fn),
               'f1': ratio(2 * tp, 2 * tp + fp + fn),
               'mean_detection_delay_s': ratio(sum(delays), len(delays)),
               'detected_events': len(delays), 'total_events': len(event_results)}
    return Result(policy.name, metrics, alarms, polls, event_results)
