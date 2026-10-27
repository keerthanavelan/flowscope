"""Run with: python run.py --seed 7 --output results"""
import argparse
import json
from pathlib import Path
from algorithms import Fixed, FlowAdaptive, PathAdaptive, Settings
from traffic import generate
from simulation import run
from plots import bars, traffic_plot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--output', type=Path, default=Path(__file__).parent / 'results')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    settings = Settings()
    trace = generate(args.seed)
    results = [run(trace, cls(trace.flows, settings), settings)
               for cls in (Fixed, FlowAdaptive, PathAdaptive)]
    payload = {'seed': args.seed, 'settings': vars(settings), 'paths': trace.paths,
               'flows': [vars(f) for f in trace.flows], 'traffic_mbps': trace.rates,
               'events': [vars(e) for e in trace.events],
               'results': [vars(r) for r in results]}
    (args.output / 'results.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
    traffic_plot(args.output / 'traffic.svg', trace, results)
    for metric, title, unit in [('messages', 'Monitoring messages', 'request + response count'),
                                ('records', 'Returned flow records', 'record count'),
                                ('modeled_bytes', 'Modeled monitoring traffic', 'bytes'),
                                ('mean_detection_delay_s', 'Mean delay among detected events', 'seconds'),
                                ('f1', 'Per-flow, per-second detection F1', 'F1 (0 to 1)')]:
        bars(args.output / f'{metric}.svg', title, results, metric, unit)
    lines = ['SIMULATED RESULTS — not real SDN measurements', f'Seed: {args.seed}; duration: {trace.duration}s',
             'Same immutable generated traffic used for all three policies.', '']
    for r in results:
        lines.append(r.name)
        lines.extend(f'  {k}: {v}' for k, v in r.metrics.items())
        lines.append('  Event delays: ' + str(r.events))
    lines += ['', 'Interpretation: fewer messages can reflect batching, not better sampling.',
              'Compare returned records and modeled bytes as well as messages.',
              'Mean delay excludes missed events; always inspect detected_events too.',
              'Accuracy is dominated by healthy seconds; F1, precision and recall are also reported.',
              'A single seeded scenario is a demonstration, not evidence of general superiority.']
    summary = '\n'.join(lines) + '\n'
    (args.output / 'summary.txt').write_text(summary, encoding='utf-8')
    print(summary)


if __name__ == '__main__':
    main()
