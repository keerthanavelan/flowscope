# Current dashboard and research features

See [RESEARCH_FEATURES.md](RESEARCH_FEATURES.md) for custom scenarios, the sixth audited-hybrid policy, paired multi-seed experiments, synchronized replay, and current setup commands. The original minimal prototype documentation follows.

# Adaptive statistics collection: minimal SDN simulation

This is a synthetic discrete-time experiment, not a real controller or a measurement of an SDN deployment. No Mininet, network access, third-party Python packages, or installation is required. Use Python 3.10 or later.

## Run

From this directory:

```sh
python run.py --seed 7 --output results
python -m unittest discover -v
```

The checked-in results were generated with seed 7. Each run overwrites files with the same names in the selected output directory. `results.json` contains the full traffic trace, topology, settings, poll log, held alarms, event delays and metrics. `summary.txt` contains numerical results. Open the SVG plots in any browser. Repeating the same seed on the same Python version produces identical outputs; there are no timestamps or wall-clock measurements in the results.

## Architecture and assumptions

`traffic.py` creates four switches, three fixed paths and six flows, with two flows per path. Paths share switches but have no modeled capacity, queues, loss or routing changes. Healthy reference rates are 10, 15, 20, 25, 30 and 35 Mb/s. Small sinusoidal variation and seeded uniform noise are added. Flow f0 triples during [60,85) seconds; f3 triples during [120,140). Events are external ground-truth annotations and are never given to the policies.

`algorithms.py` contains three independent policy classes sharing scheduling machinery. At each one-second tick, every due group is selected. All groups are first polled at t=0. Fixed monitoring polls each flow every 8 seconds. Both adaptive policies start at 8 seconds, then compare the current observation with their preceding sample. Relative absolute change at least 20% halves the interval (integer division); otherwise the interval doubles. Intervals are clamped to [2,16] seconds. The first observation preserves the initial interval. The next poll is scheduled from the current tick with the updated interval. There is no oracle-triggered poll or unobserved traffic access.

Flow adaptation uses one flow's observed rate. Path adaptation uses the sum of observed rates for all flows assigned to that path, and schedules those flows together. A path request is assumed to return a batch of unique per-flow records at an ingress collector. This is a **synthetic batching abstraction**, not a claim that standard OpenFlow provides a path-statistics primitive. Intermediate switches do not each return duplicate records. The path list establishes membership; hop count does not affect this cost model. Aggregation can dilute or cancel individual changes. A sustained spike may become stable and cause intervals to grow again; the scheduler responds to change, not sustained load.

`simulation.py` samples exact instantaneous rates with zero response latency and no measurement error. This idealization differs from estimating rates using cumulative byte counters. Each observed flow is alarmed at 1.5 times its known healthy reference rate. The reference is configured from the generator, rather than learned. The last alarm state is held until the next poll, including after a spike ends. All approaches use this same detector and traffic. Fresh policy instances prevent cross-run state leakage.

## Metrics

Overhead includes poll transactions, messages (one request plus one response per transaction), returned flow records, and modeled bytes. Bytes = 64 per transaction + 32 per returned record, representing assumed combined request/response framing and record size, not real wire encoding. Path batches therefore save framing but do not get free records. Controller computation and dataplane forwarding overhead are excluded.

Delay is the first fresh positive sample during an annotated event minus its onset. A missed event has null delay; the mean includes detected events only and must be read alongside the detected-event count. Accuracy, precision, recall and F1 use a common per-flow, per-second confusion matrix over the held alarm state, so late detection and stale alarms both count as errors. Undefined metrics are null. Healthy seconds dominate accuracy; F1 and recall help expose missed anomaly time. The traffic plot displays all rates and f0's held alarms; JSON records both events and every flow's alarms.

Tests cover reproducibility and trace immutability, exact baseline cadence, interval adaptation and bounds, path batching and dilution, hand-computed confusion counts and byte accounting, and missed-event semantics. This intentionally small experiment does not establish statistical significance or general superiority. Outcomes depend on event timing, noise, thresholds, group sizes and the batch-cost assumption. A broader study should sweep these factors and add a fixed path-batch control to separate adaptation gains from batching gains.
