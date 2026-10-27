"""Reproduce a six-policy paired study without opening the dashboard."""
import argparse
import json
from pathlib import Path
from experiments import experiment, experiment_csv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', choices=['single', 'simultaneous', 'offsetting'], default='offsetting')
    parser.add_argument('--seeds', nargs='+', type=int, default=list(range(10)))
    parser.add_argument('--flows', type=int, default=6)
    parser.add_argument('--audit-interval', type=int, default=8)
    parser.add_argument('--config', type=Path, help='Optional configuration JSON, including custom events.')
    parser.add_argument('--output', type=Path, default=Path(__file__).parent / 'research_results')
    args = parser.parse_args()
    config = (json.loads(args.config.read_text(encoding='utf-8')) if args.config else
              {'scenario': args.scenario, 'flow_count': args.flows, 'audit_interval': args.audit_interval,
               'policy': 'audited_hybrid'})
    study = experiment({'config': config, 'seeds': args.seeds})
    args.output.mkdir(parents=True, exist_ok=True)
    stem = study['config']['scenario']
    (args.output / f'{stem}.json').write_text(json.dumps(study, indent=2), encoding='utf-8')
    (args.output / f'{stem}.csv').write_text(experiment_csv(study), encoding='utf-8')
    lines = ['SYNTHETIC paired study — not real SDN measurements',
             f"Config: {study['config']}", f'Seeds: {args.seeds}',
             'policy                mean_bytes   mean_F1   mean_delay_s  missed/total']
    for aggregate in study['aggregates']:
        m = aggregate['metrics']
        delay = m['mean_detection_delay_s']['mean']
        delay_label = f'{delay:.3f}' if delay is not None else 'N/A'
        f1 = m['f1']['mean']
        f1_label = f'{f1:.3f}' if f1 is not None else 'N/A'
        lines.append(f"{aggregate['name']:22} {m['modeled_bytes']['mean']:10.1f} {f1_label:>9} "
                     f"{delay_label:>14}  {aggregate['missed_events']}/{aggregate['total_events']}")
    lines.append(study['notes'])
    summary = '\n'.join(lines) + '\n'
    (args.output / f'{stem}_summary.txt').write_text(summary, encoding='utf-8')
    print(summary)


if __name__ == '__main__':
    main()
