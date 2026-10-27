"""Run the additive experiment: python compare.py --seeds 0 1 2 3 4 5 6 7 8 9."""
import argparse
import json
from pathlib import Path
from statistics import mean
from algorithms import Fixed, FlowAdaptive, PathAdaptive, Settings
from hybrid import FixedPath, Hybrid
from scenarios import SCENARIOS, scenario
from simulation import run
from plots import svg

POLICIES = (Fixed, FixedPath, FlowAdaptive, PathAdaptive, Hybrid)
LABELS = ('Fixed flow', 'Fixed path', 'Adaptive flow', 'Adaptive path', 'Hybrid')
COLORS = ('#61758a', '#9966aa', '#c35b13', '#258247', '#1769aa')


def chart(path, name, aggregates, metric, unit):
    stats = [aggregates[cls.name][metric] for cls in POLICIES]
    upper = 1 if metric in ('accuracy', 'f1') else max([s['max'] or 0 for s in stats] + [1]) * 1.2
    body = f'<text x="45" y="60">{unit}; bars = seed means; whiskers = min/max</text>'
    for i in range(6):
        y = 365 - 275 * i / 5
        body += f'<path d="M90 {y} H920" stroke="#ddd"/><text x="15" y="{y+5}">{upper*i/5:.2g}</text>'
    for i, (label, stat) in enumerate(zip(LABELS, stats)):
        x = 125 + i * 162
        value = stat['mean']
        if value is not None:
            y = 365 - value / upper * 275
            low, high = (365 - stat[k] / upper * 275 for k in ('min', 'max'))
            body += f'<rect x="{x}" y="{y}" width="90" height="{365-y}" fill="{COLORS[i]}"/>'
            body += f'<path d="M{x+45} {low} V{high} M{x+35} {low} h20 M{x+35} {high} h20" stroke="#172438"/>'
            body += f'<text x="{x+45}" y="{high-12}" text-anchor="middle">{value:.3g}</text>'
        else:
            body += f'<text x="{x}" y="350">N/A</text>'
        body += f'<text x="{x+45}" y="395" text-anchor="middle" font-size="12">{label}</text>'
    body += '<text x="90" y="435">Synthetic simulation; delay excludes misses (see summary for event counts).</text>'
    svg(path, f'{name}: {metric}', body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seeds', nargs='+', type=int, default=list(range(10)))
    parser.add_argument('--output', type=Path, default=Path(__file__).parent / 'comparison_results')
    args = parser.parse_args()
    if len(set(args.seeds)) != len(args.seeds):
        parser.error('seeds must be distinct')
    args.output.mkdir(parents=True, exist_ok=True)
    settings = Settings()
    aggregate = {}
    lines = ['SYNTHETIC SDN COMPARISON (not real measurements)',
             f'Seeds: {args.seeds}; 180 seconds per trace.',
             'Values are means over seeds. Delay excludes missed events.',
             'Each policy receives the identical trace for a scenario/seed.', '']
    for name in SCENARIOS:
        collected = {cls.name: [] for cls in POLICIES}
        for seed in args.seeds:
            trace = scenario(name, seed)
            results = []
            for cls in POLICIES:
                policy = cls(trace.flows, settings)
                result = run(trace, policy, settings)
                collected[cls.name].append(result.metrics)
                results.append({**vars(result), 'transitions': getattr(policy, 'transitions', [])})
            payload = {'scenario': name, 'seed': seed, 'settings': vars(settings),
                       'duration': trace.duration, 'paths': trace.paths,
                       'flows': [vars(f) for f in trace.flows], 'traffic_mbps': trace.rates,
                       'events': [vars(e) for e in trace.events], 'results': results}
            (args.output / f'{name}_{seed}.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
        aggregate[name] = {}
        lines += [name, 'policy             polls  records    bytes  delay_s  accuracy     F1  events']
        for cls in POLICIES:
            rows = collected[cls.name]
            stats = {}
            for metric in rows[0]:
                values = [row[metric] for row in rows if row[metric] is not None]
                stats[metric] = {'mean': mean(values) if values else None,
                                 'min': min(values) if values else None,
                                 'max': max(values) if values else None,
                                 'defined_runs': len(values)}
            aggregate[name][cls.name] = stats
            m = {k: v['mean'] for k, v in stats.items()}
            delay = f"{m['mean_detection_delay_s']:.2f}" if m['mean_detection_delay_s'] is not None else 'N/A'
            detected = sum(r['detected_events'] for r in rows)
            total = sum(r['total_events'] for r in rows)
            lines.append(f"{cls.name:18} {m['poll_transactions']:5.1f} {m['records']:8.1f} "
                         f"{m['modeled_bytes']:8.1f} {delay:>8} {m['accuracy']:9.4f} "
                         f"{m['f1']:6.3f} {detected}/{total}")
        lines.append('')
        for metric, unit in [('messages', 'messages'), ('records', 'records'),
                             ('modeled_bytes', 'modeled bytes'),
                             ('mean_detection_delay_s', 'seconds'),
                             ('accuracy', 'accuracy'), ('f1', 'F1')]:
            chart(args.output / f'{name}_{metric}.svg', name, aggregate[name], metric, unit)
    (args.output / 'aggregate.json').write_text(json.dumps({'seeds': args.seeds, 'scenarios': aggregate}, indent=2), encoding='utf-8')
    lines += ['Cost: 2 messages/poll; 64 bytes/poll + 32 bytes/returned record.',
              'Offsetting labels only the upward f0 anomaly; downward f1 change is not a target of the unchanged high-rate detector.',
              'Hybrid mode switches are local decisions, not extra network messages. All actual polls are counted.',
              'Ranges in plots show variation across seeds, not confidence intervals.',
              'Hybrid cannot improve initial detection before its triggering path observation.',
              'Exact cancellation may prevent flow-mode entry. No periodic audit was added.',
              'Synthetic batching, known references, instantaneous samples and zero latency remain assumptions.']
    summary = '\n'.join(lines) + '\n'
    (args.output / 'summary.txt').write_text(summary, encoding='utf-8')
    print(summary)


if __name__ == '__main__':
    main()
