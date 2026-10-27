# Hybrid extension: reproducible subject-project experiment

The original Python files, README and original `results/` are preserved. This extension adds `hybrid.py`, `scenarios.py`, `compare.py`, and `test_hybrid.py`. It uses the original simulation loop, detector, metrics and cost model without modification. No dependencies or Mininet are required. Use Python 3.10+.

## Reproduce

From this directory:

```sh
python -m unittest discover -v
python compare.py --seeds 0 1 2 3 4 5 6 7 8 9
```

If `python` is unavailable on this computer's PATH, the runtime used to verify this project can be invoked in PowerShell:

```powershell
$pythonRuntime = 'C:\Users\LENOVO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $pythonRuntime -m unittest discover -v
& $pythonRuntime compare.py --seeds 0 1 2 3 4 5 6 7 8 9
```

The default output is `comparison_results/`; `--output another_directory` selects a different destination. Existing files with matching names are overwritten. Use a fresh output directory when changing seed sets to avoid retaining old per-seed files. The original `python run.py` experiment still runs unchanged.

Outputs include 30 complete scenario/seed JSON files, `aggregate.json`, `summary.txt`, and 18 SVG comparison plots (messages, records, modeled bytes, delay, accuracy and F1 for each scenario). Each trace is generated once and supplied to all five fresh policy instances. Full traces, poll logs, alarm states, event delays, settings and hybrid mode transitions are saved. Aggregates are unweighted seed means with min/max and a count of defined runs. Delay means exclude misses; inspect the event counts too. The plot whiskers are seed ranges, not confidence intervals.

## Exact policy rules

**Fixed path baseline:** poll every path as a batch every 8 seconds, starting at t=0. This has the same sampled flow records and alarms as the original fixed flow baseline, with fewer transactions. It isolates batching benefits from adaptation.

**Hybrid path mode:** use the original path-adaptive schedule (initial interval 8 seconds, stable observations double it up to 16). Compare consecutive sampled path sums and each flow's rate with its previous sample. A relative absolute change **at least 20%** in either the path sum or any individual flow switches only that path to flow mode. The per-flow check catches changes that cancel in the aggregate. The triggering batch already returns its flow records; it is not followed by redundant individual polls at the same tick.

**Hybrid flow mode:** starting 2 seconds after the trigger, poll every member separately every 2 seconds. Each individual request incurs a full poll cost. A complete round contains one fresh observation of every flow on that path at the same tick. The round is stable only if every flow's relative absolute change is below 20% compared with the preceding complete round (the triggering batch is the first reference). An unstable round resets the stable-round count. Two consecutive stable rounds return the path to batch mode. The first resumed path poll is 8 seconds later; its interval is reset to 8 and the final individual round's sum is the reference for further adaptation. Different paths switch independently.

These choices use only sampled values. No event labels, unobserved values, periodic audits or extra path polls are used in flow mode. Switching itself is a local scheduling decision with no modeled control message; all actual sample transactions are charged by the original simulator: 2 messages per transaction, 64 framing bytes per transaction and 32 bytes per returned flow record. No per-flow records are obtained for free.

## Scenarios

The same four-switch, three-path, six-flow topology and healthy noise are reused. Original injected spikes are removed before applying the new scenario. Each seed selects an event onset uniformly from integer seconds 50 through 75; the event lasts 25 seconds. Noise and onset vary across seeds. Corresponding seeds across scenarios share healthy traffic and event timing.

| Scenario | Injected change |
|---|---|
| Single | f0 triples |
| Simultaneous | f0, f1 and f3 triple together, spanning two paths |
| Offsetting | f0 gains 10 Mb/s while f1 loses 10 Mb/s on the same path; the injected sum change is exactly zero |

The original detector targets **high-rate anomalies**, using the unchanged 1.5-times-reference threshold. Consequently, only the upward f0 anomaly is ground truth in the offsetting scenario; f1's decrease is background interference, not a target anomaly. This experiment does not evaluate detection of traffic decreases. All offsetting rates remain positive.

## Observed results

The table below records the earlier aggregate-only hybrid rule. It is retained as a historical baseline and does not measure the cancellation-aware trigger in the current code. Re-run the experiment before reporting performance for the updated rule.

Ten seeds (0–9), three scenarios and five policies give 150 simulations. All 50 annotated events across the scenario/seed traces were detected by every policy. Each policy's mean delay is 3.6 seconds for either fixed baseline and 8.4 seconds for each adaptive method, in all three scenarios.

| Scenario | Path adaptive bytes / F1 | Hybrid bytes / F1 | Fixed path bytes / F1 |
|---|---:|---:|---:|
| Single | 4,736 / 0.652 | 5,504 / 0.680 | 8,832 / 0.859 |
| Simultaneous | 4,864 / 0.652 | 6,400 / 0.680 | 8,832 / 0.859 |
| Offsetting | 4,608 / 0.685 | 4,608 / 0.685 | 8,832 / 0.859 |

These are mean simulated bytes and mean per-run F1, rounded for presentation. The full summary includes every policy and accuracy. Hybrid modestly improves F1 over path adaptation for non-cancelling spikes, at higher overhead, and does not improve first detection delay. In the offsetting scenario there are no hybrid mode transitions, so hybrid and path adaptation match exactly. The fixed path baseline gives better detection in these scenarios but spends more bytes. This is a trade-off, not a hybrid win across metrics.

## Validation and limitations

Fourteen tests cover the original functionality plus threshold entry, two complete stable rounds, streak reset under offsetting changes, no same-tick duplicate samples, independent paths, exact switching costs, fixed-baseline equivalence, reproducibility, trace immutability, and scenario ground truth. Repeated experiment outputs are also checked for byte-for-byte reproducibility.

The triggering path batch already identifies the high-rate flow, so faster individual polling cannot improve that event's initial detection. Offsetting changes can prevent switching even though the path batch's returned per-flow records may detect the upward anomaly. The prior policy deliberately triggered on aggregate change only. A steady high load becomes stable and can return to path mode; stability does not mean the anomaly ended. F1 differences depend on the resulting poll phase and stale-alarm duration, not a guaranteed benefit of individual polling.

The cancellation-aware trigger addresses the aggregate-cancellation switching case by checking sampled per-flow changes as well. Its effect on overhead, delay and F1 has not yet been measured; do not claim an improvement until fresh runs are analyzed.

This remains a synthetic rate-sampling experiment with known healthy references, zero latency and loss, fixed routes, and an assumed ingress batching service. It is not a real OpenFlow controller or SDN measurement. Ten seeds, one event duration and one threshold setting are adequate for a small demonstrator, not a general performance claim; shorter events may be missed. The experiment is a clearly specified project heuristic, not a claim of research originality.
