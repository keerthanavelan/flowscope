import unittest
from algorithms import Fixed, FlowAdaptive, PathAdaptive, Settings
from simulation import run
from traffic import Event, Flow, Trace, generate


class Tests(unittest.TestCase):
    def test_reproducible_shared_trace(self):
        a, b = generate(7), generate(7)
        self.assertEqual(a, b)
        self.assertNotEqual(a.rates, generate(8).rates)
        for cls in (Fixed, FlowAdaptive, PathAdaptive):
            run(a, cls(a.flows, Settings()), Settings())
        self.assertEqual(a, b)

    def test_fixed_cadence(self):
        tr = generate()
        r = run(tr, Fixed(tr.flows, Settings()), Settings())
        self.assertEqual(r.metrics['poll_transactions'], 23 * 6)
        self.assertEqual([p['time'] for p in r.polls if p['group'] == 'f0'], list(range(0, 180, 8)))

    def test_adaptation_and_path_batching(self):
        tr, s = generate(), Settings()
        p = FlowAdaptive(tr.flows, s)
        p.observe('f0', 0, {'f0': 10})
        p.observe('f0', 8, {'f0': 10})
        self.assertEqual(p.due['f0'], 24)
        p.observe('f0', 24, {'f0': 30})
        self.assertEqual(p.intervals['f0'], 8)
        for t in range(10):
            p.observe('f0', t, {'f0': 1 if t % 2 else 100})
        self.assertEqual(p.intervals['f0'], 2)
        path = PathAdaptive(tr.flows, s)
        self.assertEqual(path.groups['p0'], ['f0', 'f1'])
        path.observe('p0', 0, {'f0': 10, 'f1': 90})
        path.observe('p0', 8, {'f0': 20, 'f1': 90})
        self.assertEqual(path.intervals['p0'], 16)  # aggregate change diluted to 10%

    def test_hand_computed_metrics(self):
        tr = Trace({'p': ('s0', 's1')}, [Flow('f', 'p', 10)],
                   {'f': [10, 30, 30, 10, 10, 10]}, [Event('f', 1, 3)], 6)
        s = Settings(fixed_interval=2)
        r = run(tr, Fixed(tr.flows, s), s)
        self.assertEqual([r.metrics[k] for k in ('tp', 'fp', 'tn', 'fn')], [1, 1, 3, 1])
        self.assertEqual(r.metrics['mean_detection_delay_s'], 1)
        self.assertEqual(r.metrics['f1'], .5)
        self.assertEqual(r.metrics['modeled_bytes'], 3 * (64 + 32))

    def test_missed_event_not_zero_delay(self):
        tr = Trace({'p': ('s0',)}, [Flow('f', 'p', 10)],
                   {'f': [10, 30, 10, 10]}, [Event('f', 1, 2)], 4)
        s = Settings(fixed_interval=4)
        r = run(tr, Fixed(tr.flows, s), s)
        self.assertIsNone(r.metrics['mean_detection_delay_s'])
        self.assertEqual(r.metrics['detected_events'], 0)

    def test_accounting(self):
        tr, s = generate(), Settings()
        r = run(tr, PathAdaptive(tr.flows, s), s)
        self.assertEqual(sum(r.metrics[k] for k in ('tp', 'fp', 'tn', 'fn')), 180 * 6)
        self.assertEqual(r.metrics['records'], 2 * r.metrics['poll_transactions'])


if __name__ == '__main__':
    unittest.main()
