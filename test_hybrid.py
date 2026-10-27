import unittest
from copy import deepcopy
from algorithms import Fixed, FlowAdaptive, PathAdaptive, Settings
from hybrid import FixedPath, Hybrid
from scenarios import SCENARIOS, scenario
from simulation import run
from traffic import Event, Flow, Trace


class HybridTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings()
        self.flows = [Flow('a', 'p', 10), Flow('b', 'p', 10)]

    def observe_selected(self, policy, t, values):
        selected = policy.select(t)
        for key in selected:
            policy.observe(key, t, {f: values[f] for f in policy.groups[key]})
        return selected

    def test_trigger_and_two_complete_stable_rounds(self):
        p = Hybrid(self.flows, self.settings)
        self.observe_selected(p, 0, {'a': 10, 'b': 10})
        self.observe_selected(p, 8, {'a': 14, 'b': 10})  # exactly 20%
        self.assertEqual(p.mode['p'], 'flow')
        self.assertEqual(p.select(9), [])
        self.assertEqual(p.select(10), ['flow:a', 'flow:b'])
        p.observe('flow:a', 10, {'a': 14})
        self.assertEqual(p.stable['p'], 0)  # one reply is not one stable round
        p.observe('flow:b', 10, {'b': 10})
        self.assertEqual(p.stable['p'], 1)
        self.assertEqual(p.mode['p'], 'flow')
        self.observe_selected(p, 12, {'a': 14, 'b': 10})
        self.assertEqual(p.mode['p'], 'path')
        self.assertEqual(p.due['p'], 20)
        self.assertEqual(p.select(12), [])  # no same-tick duplicate batch
        self.assertEqual(p.select(20), ['p'])

    def test_unstable_round_resets_streak_even_if_sum_stable(self):
        p = Hybrid(self.flows, self.settings)
        for t, values in [(0, {'a': 10, 'b': 10}), (8, {'a': 20, 'b': 10}),
                          (10, {'a': 20, 'b': 10}), (12, {'a': 25, 'b': 5})]:
            self.observe_selected(p, t, values)
        self.assertEqual(p.stable['p'], 0)
        self.observe_selected(p, 14, {'a': 25, 'b': 5})
        self.assertEqual(p.mode['p'], 'flow')
        self.observe_selected(p, 16, {'a': 25, 'b': 5})
        self.assertEqual(p.mode['p'], 'path')

    def test_cancellation_does_not_trigger(self):
        p = Hybrid(self.flows, self.settings)
        self.observe_selected(p, 0, {'a': 10, 'b': 10})
        self.observe_selected(p, 8, {'a': 15, 'b': 5})
        self.assertEqual(p.mode['p'], 'path')
        self.assertEqual(p.due['p'], 24)

    def test_fixed_path_is_pure_batching_control(self):
        tr = scenario('single', 7)
        a = run(tr, Fixed(tr.flows, self.settings), self.settings)
        b = run(tr, FixedPath(tr.flows, self.settings), self.settings)
        self.assertEqual(a.alarms, b.alarms)
        self.assertEqual(a.events, b.events)
        self.assertEqual(a.metrics['records'], b.metrics['records'])
        self.assertEqual(a.metrics['poll_transactions'], 2 * b.metrics['poll_transactions'])

    def test_hand_counted_switching_costs(self):
        tr = Trace({'p': ('s0', 's1')}, self.flows,
                   {'a': [10] * 8 + [30] * 6, 'b': [10] * 14}, [Event('a', 8, 14)], 14)
        p = Hybrid(self.flows, self.settings)
        result = run(tr, p, self.settings)
        # Batches at 0,8; two individual requests at each of 10,12.
        self.assertEqual(result.metrics['poll_transactions'], 6)
        self.assertEqual(result.metrics['records'], 8)
        self.assertEqual(result.metrics['messages'], 12)
        self.assertEqual(result.metrics['modeled_bytes'], 640)

    def test_scenarios_pairing_reproducibility_and_no_duplicate_samples(self):
        for name in SCENARIOS:
            tr = scenario(name, 7)
            before = deepcopy(tr)
            self.assertEqual(tr, scenario(name, 7))
            for cls in (Fixed, FixedPath, FlowAdaptive, PathAdaptive, Hybrid):
                r = run(tr, cls(tr.flows, self.settings), self.settings)
                samples = [(p['time'], f) for p in r.polls for f in p['flows']]
                self.assertEqual(len(samples), len(set(samples)))
                self.assertEqual(sum(r.metrics[k] for k in ('tp', 'fp', 'tn', 'fn')), 1080)
            self.assertEqual(tr, before)

    def test_offsetting_sum_and_high_rate_truth(self):
        tr = scenario('offsetting', 7)
        single = scenario('single', 7)
        e = tr.events[0]
        for t in range(tr.duration):
            healthy_a = single.rates['f0'][t] / (3 if e.start <= t < e.end else 1)
            expected_sum = healthy_a + single.rates['f1'][t]
            self.assertAlmostEqual(tr.rates['f0'][t] + tr.rates['f1'][t], expected_sum)
            self.assertGreater(tr.rates['f1'][t], 0)
            for flow in tr.flows:
                truth = any(event.flow == flow.name and event.start <= t < event.end for event in tr.events)
                self.assertEqual(tr.rates[flow.name][t] >= 1.5 * flow.reference, truth)

    def test_other_paths_do_not_switch(self):
        p = Hybrid(self.flows + [Flow('c', 'q', 10)], self.settings)
        self.observe_selected(p, 0, {'a': 10, 'b': 10, 'c': 10})
        self.observe_selected(p, 8, {'a': 30, 'b': 10, 'c': 10})
        self.assertEqual(p.mode, {'p': 'flow', 'q': 'path'})
        self.assertEqual(p.select(10), ['flow:a', 'flow:b'])


if __name__ == '__main__':
    unittest.main()
