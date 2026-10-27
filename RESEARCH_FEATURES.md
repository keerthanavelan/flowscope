# FlowScope research extension

Four additions are now available in the existing four-tab dashboard. The five original policies and evaluator are unchanged; the audited hybrid is a sixth policy. The original `run.py`, `compare.py`, `results/` and `comparison_results/` remain the original experiments.

## Run from this folder

The old `.venv` points to an unavailable Python installation on this computer. A separate `.venv-research` was created; the old environment was not removed.

```powershell
cd "C:\Users\LENOVO\OneDrive\Desktop\College\SEM5\ACN\flowscope"
.\.venv-research\Scripts\python.exe dashboard_app.py
```

Open http://127.0.0.1:5050. If another server uses that port, add `--port 5051` and use http://127.0.0.1:5051. Restart a running server after code changes. Keep PowerShell open; Ctrl+C stops it.

On another machine, create the environment first:

```powershell
python -m venv .venv-research
.\.venv-research\Scripts\python.exe -m pip install -r requirements-dashboard.txt
```

Use Python 3.10+. If `python` is not on PATH on this computer, invoke `C:\Users\LENOVO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe` with PowerShell's `&` operator. No new frontend or Python package requirements were added.

## 1. Custom scenario builder

Select **Custom spikes** in the global scenario selector. Add up to 20 event rows, each specifying a flow, start second, duration and multiplier. Choose the workload first to expose flows f0 through f19. Use **Run simulation** to apply the draft. JSON exports retain the full configuration; CSV exports include custom events and audit interval too.

Windows are half-open [start, start + duration), inside the 180-second trace. Events on one flow must not overlap; different flows may spike together. The multiplier must be greater than 1 and at most 8. Each spike multiplies that flow's healthy noisy rate. Preset spikes are removed before custom events are injected; original presets themselves are unchanged.

Ground truth marks the injected event window, regardless of whether the multiplier crosses the detector's 1.5-times-reference threshold. Small spikes can therefore legitimately be missed. This builder models upward spikes, not drops or arbitrary traffic functions. Custom timing stays fixed across seeds; seeded healthy noise changes. Preset onset and noise still vary with seed.

## 2. Hybrid with periodic audits

Choose **Hybrid + periodic audit**. Set the audit interval between 2 and 32 seconds (default 8). This setting affects only the sixth policy; every comparison includes it alongside the original five.

`audited_hybrid.py` extends `Hybrid` without editing its code. Each path begins in path mode, with the original adaptive path schedule. When a scheduled audit is due:

- If a path batch is also due, use that batch's already-returned flow records. The audit inspection adds no transaction.
- Otherwise, request each flow on the path individually. These requests pass through the original simulator and each incurs 2 messages, 64 framing bytes and 32 record bytes.
- Compare every flow with its preceding sampled value, including samples returned by path batches. At least 20% absolute relative change in any flow switches that path to fast individual mode. Aggregate triggers remain available as before.
- Audits pause in fast mode. The original two-complete-stable-round rule returns the path to batch mode; its audit deadline then resets to current time + audit interval.

A stable independent audit updates the most recent observations but does not postpone the next normal path batch. Its next audit is scheduled from the current sample time. A triggering audit schedules the next fast poll two seconds later. No flow is sampled twice at the same tick. Audit decisions inspect only sampled data, never event labels or unobserved rates.

The JSON audit log records time, path, source (`reused_batch` or `individual_polls`) and whether a per-flow change was detected. Extra audit transactions have `audit:fN` group keys in the normal poll log. Mode transitions triggered specifically by an audit carry `reason: audit`. Simulation mode captions and side-by-side replay expose these distinctions.

Audits do not guarantee better results. They can catch aggregate cancellation earlier but increase cost, and bursts between polls can still be missed. Since batches already return individual records, another possible design is inspecting every batch's per-flow changes; this implementation instead performs scheduled audits, as a separately measurable heuristic.

## 3. Paired multi-seed studies

In **Experiments & Logs**, enter 2–30 distinct comma-separated seeds and choose **Run experiment**. This uses the currently loaded run's configuration, not unsaved controls. All six policies receive the identical trace for each seed, with fresh policy instances. No scheduler state leaks between runs.

Charts and tables show per-seed means and sample standard deviations. Whiskers are mean ± one sample SD, not confidence intervals or a claim of statistical significance. Undefined metrics are excluded, with a defined-run count. Delays exclude missed events; missed/total events are displayed explicitly. JSON also includes the event-weighted pooled delay, per-seed raw metrics, event outcomes, seeds and full configuration. CSV contains per-seed metric rows and configuration JSON. If every event is missed, mean delay remains null/N/A, not zero.

The study remains loaded until replaced, even if the single-run configuration changes. The study's own status caption records its scenario, workload, seeds and audit interval. Study downloads use that retained request. Single-run exports remain separate. Runs are bounded synchronous jobs for a local demo, not a production task queue.

Reproduce without the browser:

```powershell
.\.venv-research\Scripts\python.exe run_research.py --scenario offsetting --seeds 0 1 2 3 4 5 6 7 8 9
.\.venv-research\Scripts\python.exe run_research.py --scenario single
.\.venv-research\Scripts\python.exe run_research.py --scenario simultaneous
```

For a custom study, pass `--config config.json`, where the file contains a configuration object, for example:

```json
{"scenario":"custom","flow_count":6,"seed":7,"policy":"audited_hybrid","audit_interval":8,"custom_events":[{"flow":"f0","start":10,"duration":12,"multiplier":3},{"flow":"f3","start":30,"duration":20,"multiplier":2.5}]}
```

Output defaults to `research_results/`; use `--output` for another location. Matching scenario filenames are overwritten. Existing historical results are never overwritten. Studies generated with the same code, configuration and seeds are reproducible.

## 4. Side-by-side policy replay

The **Comparison** tab contains two policy selectors, a flow selector and one shared time slider/play control. At each second, both panels show the selected flow's alarm, latest sample time/value, its path's mode, current transaction groups, cumulative transactions and cumulative modeled bytes. Costs include all flows, not just the inspected flow.

The cumulative-cost chart displays the complete logged histories with a cursor at the replay time. Playback advances through stored simulation output; it does not run a real network or inject extra polls. Ground truth is shared, while alarms and sample times come from each policy. Changing tabs or loading a new run pauses playback.

## Validation and scope

Ten-seed preset results (seeds 0–9, six flows, 8-second audits) are saved in `research_results/`:

| Scenario | Original hybrid bytes / F1 | Audited hybrid bytes / F1 | Fixed path bytes / F1 |
|---|---:|---:|---:|
| Single | 5,504 / 0.680 | 11,494.4 / 0.846 | 8,832 / 0.859 |
| Simultaneous | 6,400 / 0.680 | 12,044.8 / 0.846 | 8,832 / 0.859 |
| Offsetting | 4,608 / 0.685 | 11,494.4 / 0.846 | 8,832 / 0.859 |

Audits reduce the original hybrid's mean detection delay from 8.4 to 3.6 seconds in all three presets. All policies detect all preset events. The fixed path baseline also achieves 3.6 seconds, with lower bytes and higher F1 than the audited hybrid in these presets. Thus audits improve the original hybrid's responsiveness here but do not beat the fixed path baseline. Short custom bursts can reveal missed-event differences; see tests for one controlled cancellation case. These results cover 180 simulations, not a claim of general superiority.

```powershell
.\.venv-research\Scripts\python.exe -m unittest discover -v
```

Tests cover the original behavior plus original-five equivalence, custom windows/multipliers, bounds and overlaps, reproducibility, independent audit cost accounting, reuse at coincident deadlines, cancellation detection, paired study aggregation, all-missed delay semantics and exports. Browser validation covers custom controls, replay-cost reconciliation, experiments, downloads, invalid-input handling and mobile layouts.

This remains a synthetic simulation with fixed routes, exact instantaneous samples, known healthy references and zero response latency. There is no claim of research originality or general superiority. The work divides naturally into traffic/scenarios, monitoring, evaluation and visualization; actual team contributions should be documented honestly.
