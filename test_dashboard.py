"""Requires requirements-dashboard.txt. Existing simulator tests stay dependency-free."""
import csv
import io
import unittest
from dataclasses import asdict

from dashboard_app import create_app
from dashboard_data import build_trace, execute, validate
from algorithms import Settings
from hybrid import Hybrid
from scenarios import scenario
from simulation import run


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()
        self.config = {'scenario': 'single', 'seed': 7, 'flow_count': 6, 'policy': 'hybrid'}

    def test_original_result_preserved(self):
        trace = scenario('single', 7)
        settings = Settings()
        expected = asdict(run(trace, Hybrid(trace.flows, settings), settings))
        response = self.client.post('/api/run', json=self.config)
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        actual = next(r for r in payload['results'] if r['name'] == 'hybrid')
        self.assertEqual({k: actual[k] for k in expected}, expected)
        self.assertEqual(len(payload['results']), 5)
        self.assertEqual(payload, self.client.post('/api/run', json=self.config).get_json())

    def test_expanded_trace_preserves_original_flows(self):
        for count in (12, 16, 20):
            for name in ('single', 'simultaneous', 'offsetting'):
                config = {**self.config, 'scenario': name, 'flow_count': count}
                trace = build_trace(config)
                original = scenario(name, 7)
                self.assertEqual(len(trace.flows), count)
                self.assertEqual(trace.events, original.events)
                for flow in original.flows:
                    self.assertEqual(trace.rates[flow.name], original.rates[flow.name])
                for flow in trace.flows[6:]:
                    self.assertTrue(all(0 < rate < 1.5 * flow.reference for rate in trace.rates[flow.name]))
                self.assertEqual(trace, build_trace(config))

    def test_all_policies_have_fair_accounting_at_scale(self):
        payload = execute({**self.config, 'flow_count': 20, 'scenario': 'simultaneous'})
        for result in payload['results']:
            metrics = result['metrics']
            self.assertEqual(metrics['poll_transactions'], len(result['polls']))
            self.assertEqual(metrics['records'], sum(len(p['flows']) for p in result['polls']))
            self.assertEqual(metrics['modeled_bytes'], 64 * len(result['polls']) + 32 * metrics['records'])
            self.assertEqual(sum(metrics[k] for k in ('tp', 'fp', 'tn', 'fn')), 180 * 20)
        self.assertEqual(payload['results'][0]['alarms'], payload['results'][1]['alarms'])

    def test_invalid_inputs_return_client_errors(self):
        for change in ({'seed': True}, {'seed': -1}, {'seed': 1.5}, {'seed': '7'},
                       {'seed': 2147483648}, {'flow_count': 7}, {'flow_count': 10000},
                       {'policy': []}, {'scenario': 'unknown'}, {'unexpected': 1}):
            with self.subTest(change=change):
                response = self.client.post('/api/run', json={**self.config, **change})
                self.assertEqual(response.status_code, 400)
                self.assertIn('error', response.get_json())
        self.assertEqual(self.client.post('/api/run', json=[]).status_code, 400)
        self.assertEqual(self.client.post('/api/run', data='{', content_type='application/json').status_code, 400)
        self.assertEqual(self.client.post('/api/run', data='text').status_code, 415)

    def test_exports_match_run_and_reconcile(self):
        payload = self.client.post('/api/run', json=self.config).get_json()
        self.assertEqual(self.client.post('/api/export/json', json=self.config).get_json(), payload)
        response = self.client.post('/api/export/metrics', json=self.config)
        self.assertIn('attachment', response.headers['Content-Disposition'])
        rows = list(csv.DictReader(io.StringIO(response.get_data(as_text=True))))
        self.assertEqual(len(rows), 5)
        for row, result in zip(rows, payload['results']):
            self.assertEqual(int(row['modeled_bytes']), result['metrics']['modeled_bytes'])
        response = self.client.post('/api/export/polls', json=self.config)
        rows = list(csv.DictReader(io.StringIO(response.get_data(as_text=True))))
        for result in payload['results']:
            subset = [row for row in rows if row['policy'] == result['name']]
            self.assertEqual(len(subset), result['metrics']['poll_transactions'])
            for metric in ('records', 'messages', 'modeled_bytes'):
                self.assertEqual(sum(int(row[metric]) for row in subset), result['metrics'][metric])
        self.assertEqual(self.client.post('/api/export/invalid', json=self.config).status_code, 404)

    def test_frontend_and_local_assets(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'FlowScope', response.data)
        for path in ('/static/style.css', '/static/app.js', '/static/vendor/chart.umd.min.js'):
            with self.client.get(path) as asset:
                self.assertEqual(asset.status_code, 200)
        self.assertEqual(len(self.client.get('/api/meta').get_json()['policies']), 5)


if __name__ == '__main__':
    unittest.main()
