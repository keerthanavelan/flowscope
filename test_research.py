import unittest
from dataclasses import asdict
from statistics import mean, stdev
from algorithms import Settings
from audited_hybrid import AuditedHybrid
from dashboard_app import create_app
from dashboard_data import build_trace, execute, validate, POLICIES
from experiments import experiment
from hybrid import Hybrid
from scenarios import scenario
from simulation import run
from traffic import Trace, Flow, Event


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings()
        self.flows = [Flow('a', 'p', 10), Flow('b', 'p', 15)]
        self.config = {'scenario': 'custom', 'seed': 7, 'flow_count': 6, 'policy': 'audited_hybrid',
                       'audit_interval': 8, 'custom_events': [
                           {'flow': 'f0', 'start': 10, 'duration': 10, 'multiplier': 3}]}
        self.client = create_app().test_client()

    def test_audit_detects_cancellation_without_oracle(self):
        rates = {'a': [20 if 10 <= t < 20 else 10 for t in range(40)],
                 'b': [5 if 10 <= t < 20 else 15 for t in range(40)]}
        trace = Trace({'p': ('s0', 's1')}, self.flows, rates, [Event('a', 10, 20)], 40)
        original = run(trace, Hybrid(self.flows, self.settings), self.settings)
        policy = AuditedHybrid(self.flows, self.settings)
        audited = run(trace, policy, self.settings)
        self.assertEqual(original.metrics['detected_events'], 0)
        self.assertEqual(audited.metrics['mean_detection_delay_s'], 6)
        self.assertIn({'time': 16, 'path': 'p', 'mode': 'flow', 'reason': 'audit'}, policy.transitions)
        self.assertGreater(audited.metrics['modeled_bytes'], original.metrics['modeled_bytes'])

    def test_audit_collision_and_exact_accounting(self):
        trace = Trace({'p': ('s0', 's1')}, self.flows, {'a': [10]*18, 'b': [15]*18}, [], 18)
        policy = AuditedHybrid(self.flows, self.settings)
        result = run(trace, policy, self.settings)
        self.assertEqual([(p['time'], p['group']) for p in result.polls],
                         [(0, 'p'), (8, 'p'), (16, 'audit:a'), (16, 'audit:b')])
        self.assertEqual(result.metrics['modeled_bytes'], 4*64 + 6*32)
        self.assertEqual(policy.audits[0]['source'], 'reused_batch')
        self.assertEqual(policy.audits[1]['source'], 'individual_polls')
        samples = [(p['time'], f) for p in result.polls for f in p['flows']]
        self.assertEqual(len(samples), len(set(samples)))

    def test_original_five_results_unchanged(self):
        payload = execute({'scenario': 'offsetting', 'seed': 7})
        trace = scenario('offsetting', 7)
        for cls, actual in zip(POLICIES[:5], payload['results'][:5]):
            expected = asdict(run(trace, cls(trace.flows, self.settings), self.settings))
            self.assertEqual({key: actual[key] for key in expected}, expected)

    def test_custom_trace_exact_multipliers_and_windows(self):
        config = validate(self.config)
        trace = build_trace(config)
        original = scenario('single', 7)
        for t in range(180):
            healthy = original.rates['f0'][t]
            if original.events[0].start <= t < original.events[0].end:
                healthy /= 3
            self.assertAlmostEqual(trace.rates['f0'][t], healthy * (3 if 10 <= t < 20 else 1))
        self.assertEqual(trace.events, [Event('f0', 10, 20)])
        self.assertEqual(trace, build_trace(config))

    def test_custom_multiple_flows_and_separate_windows(self):
        config = {**self.config, 'flow_count': 20, 'custom_events': [
            {'flow': 'f19', 'start': 179, 'duration': 1, 'multiplier': 2},
            {'flow': 'f0', 'start': 1, 'duration': 3, 'multiplier': 3},
            {'flow': 'f0', 'start': 4, 'duration': 2, 'multiplier': 4}]}
        result = execute(config)
        self.assertEqual(len(result['trace']['events']), 3)
        self.assertEqual(len(result['trace']['flows']), 20)
        self.assertEqual(result, execute(config))

    def test_validation_bounds_and_overlap(self):
        bad_events = [[], [{'flow': 'f0', 'start': 170, 'duration': 11, 'multiplier': 3}],
                      [{'flow': 'f6', 'start': 10, 'duration': 5, 'multiplier': 3}],
                      [{'flow': 'f0', 'start': 1.5, 'duration': 5, 'multiplier': 3}],
                      [{'flow': 'f0', 'start': 10, 'duration': 5, 'multiplier': 1}],
                      [self.config['custom_events'][0]]*2]
        for events in bad_events:
            with self.subTest(events=events):
                response = self.client.post('/api/run', json={**self.config, 'custom_events': events})
                self.assertEqual(response.status_code, 400)
        for interval in (True, 1, 33, '8'):
            self.assertEqual(self.client.post('/api/run', json={**self.config, 'audit_interval': interval}).status_code, 400)

    def test_experiment_matches_per_seed_runs(self):
        request = {'config': self.config, 'seeds': [0, 1, 2]}
        study = experiment(request)
        self.assertEqual(study, experiment(request))
        for i, aggregate in enumerate(study['aggregates']):
            values = [run['results'][i]['metrics']['modeled_bytes'] for run in study['runs']]
            self.assertEqual(aggregate['metrics']['modeled_bytes']['mean'], mean(values))
            self.assertEqual(aggregate['metrics']['modeled_bytes']['stddev'], stdev(values))
            self.assertEqual(aggregate['total_events'], 3)
        for item in study['runs']:
            direct = execute({**self.config, 'seed': item['seed']})
            self.assertEqual(item['results'][5]['metrics'], direct['results'][5]['metrics'])

    def test_all_misses_remain_undefined_delay(self):
        config = {**self.config, 'custom_events': [{'flow': 'f0', 'start': 10, 'duration': 2, 'multiplier': 1.01}]}
        study = experiment({'config': config, 'seeds': [0, 1]})
        for aggregate in study['aggregates']:
            self.assertIsNone(aggregate['metrics']['mean_detection_delay_s']['mean'])
            self.assertEqual(aggregate['metrics']['mean_detection_delay_s']['defined_runs'], 0)
            self.assertEqual(aggregate['missed_events'], 2)
            self.assertIsNone(aggregate['pooled_detection_delay_s'])

    def test_experiment_api_and_exports(self):
        body = {'config': self.config, 'seeds': [0, 1]}
        response = self.client.post('/api/experiment', json=body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.post('/api/experiment/export/json', json=body).get_json(), response.get_json())
        csv = self.client.post('/api/experiment/export/csv', json=body)
        self.assertEqual(csv.status_code, 200)
        self.assertIn('attachment', csv.headers['Content-Disposition'])
        for seeds in ([], [1], [1, 1], [True, 2], list(range(31))):
            self.assertEqual(self.client.post('/api/experiment', json={**body, 'seeds': seeds}).status_code, 400)


if __name__ == '__main__':
    unittest.main()
