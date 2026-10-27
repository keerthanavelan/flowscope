# FlowScope — local SDN monitoring dashboard

Flask + HTML/CSS/vanilla JavaScript, with Chart.js 4.5.1 served locally and an interactive SVG topology. No frontend build, Node runtime, CDN connection, or Mininet is needed to run the dashboard. Existing policy code, simulation code, original CLI tools and saved experiment results are untouched.

## Setup and run

Use Python 3.10+ and run these commands from the `sdn_sim` project folder:

```sh
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dashboard.txt
.\.venv\Scripts\python.exe dashboard_app.py
```

macOS/Linux:

```sh
.venv/bin/python -m pip install -r requirements-dashboard.txt
.venv/bin/python dashboard_app.py
```

Open **http://127.0.0.1:5050**. If `python` is not on PATH, use `py` on Windows or the full path to a Python executable. Flask must be installed in the same interpreter used to start the server. To change ports, use `python dashboard_app.py --port 5051`. Stop with Ctrl+C. The server binds to localhost with debug disabled; this is a local demo, not a public production deployment.

On the computer used for this project, a bundled Python executable is available at `C:\Users\LENOVO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`. In PowerShell, use `& 'that-full-path' -m venv .venv` for the first command if neither `python` nor `py` is available. Afterward, use the `.venv` commands above.

Chart.js and its MIT license are included in `dashboard/static/vendor/`. Once Python dependencies are installed, the app works offline. The UI uses system fonts, with no external font or image requests.

## Demo guide

1. Open the dashboard. The initial load actually runs all five policies using the single-spike scenario, seed 7 and the original six flows. Summary cards refer to the selected policy; comparison data always contains all five.
2. In **Topology**, move the replay slider to 72 seconds to see the default hybrid in fast individual mode. Play advances through the recorded trace, not a wall-clock network simulation. Select paths, switches or flow markers. Orange means a ground-truth high-rate anomaly; a purple ring means the monitor's held alarm. The inventory separately shows actual rates, alarms and last-sample times.
3. In **Simulation**, choose a flow. View its actual rate, the shared detection threshold, actual poll samples, held alarm state and polling transaction/record counts. Hybrid mode strips are reconstructed from logged transitions, with textual switch times and matching vertical markers in the traffic chart. Chart legends toggle datasets and tooltips expose values.
4. In **Comparison**, compare overhead, transactions, records, messages, recall, F1 and delay for the exact same generated trace. The table also shows event detection counts. Changing a chart metric changes real values, not display placeholders. The selected policy is highlighted; no policy is labeled a universal winner.
5. In **Experiments & Logs**, inspect the loaded configuration and selected policy's event outcomes. Filter transaction logs by flow and paginate them. Export the complete run as JSON, all five policies' metrics as CSV, or all five policies' transactions as CSV.
6. Try **offsetting changes** to see aggregate cancellation, or select 12–20 flows to increase background load. Press **Run simulation** to apply configuration changes. Until then, an explicit message says that views still show the previous loaded run. Exports always use the loaded run's configuration, not unsaved controls.

All five policies are computed in one request to prevent comparisons between mismatched traces. The interface exposes a single seed per run. Previous ten-seed results remain in `comparison_results/`; the dashboard does not misrepresent a single run as a multi-seed average. Runs are not stored on the server; download JSON to retain a run. The run ID is a deterministic configuration hash, not a timestamp or a unique execution ID.

## Additive architecture

- `dashboard_app.py`: Flask app factory, static UI, configuration metadata, simulation and export endpoints.
- `dashboard_data.py`: validates inputs, calls the existing generators and policies, and serializes the existing evaluator's results. No changes to metric definitions or polling costs.
- `dashboard/templates/index.html`: four responsive views.
- `dashboard/static/style.css`: layout, responsive breakpoints, focus styles and visual states.
- `dashboard/static/app.js`: fetches real results, renders charts and SVG, replays logged state, filters logs and downloads exports.
- `test_dashboard.py`: API, validation, original-output equivalence, expanded-workload invariants, accounting and exports.

`POST /api/run` accepts:

```json
{"policy":"hybrid","scenario":"single","seed":7,"flow_count":6}
```

Policy values: `fixed`, `fixed_path`, `flow_adaptive`, `path_adaptive`, `hybrid`. Scenario values: `single`, `simultaneous`, `offsetting`. Flow count is 6 or any integer from 12 through 20. Seed is an integer from 0 through 2147483647. Unsupported values receive JSON errors. `POST /api/export/json`, `/api/export/metrics`, and `/api/export/polls` accept the same configuration and deterministically reproduce the corresponding export. `GET /api/meta` provides policy labels and supported flow counts.

The JSON contains configuration, settings, the full trace, all five policies' metrics, polls, alarms, event outcomes and hybrid transitions. Poll CSV has one row per transaction, including its returned-flow list. Its records, messages and modeled bytes sum directly to each policy's metrics; batch replies are not accidentally counted as multiple transactions. The CSV also includes scenario, seed, flow count and run ID. Undefined metrics export as blank CSV cells and null JSON values.

## Workload and interpretation

The default six-flow trace is identical to the existing scenario generator. Larger workloads append healthy flows round-robin across the existing three paths, using independent deterministic noise streams. Original flow values and event timing remain identical. Extra references repeat the original 10–35 Mb/s range. They are background flows only; the simultaneous scenario still spikes f0, f1 and f3. Extra traffic can dilute the path-relative change and alter hybrid switching. This is a workload-size experiment, not a larger switch topology.

Topology switch highlights show membership in the selected route. Orange markers represent annotated upward anomalies, not link failure or congestion. In the offsetting scenario, the f1 decrease is not a target of the existing high-rate detector. Rate plots and topology rates expose simulator ground truth for explanation; policies still see only their original sampled observations.

The dashboard retains synthetic ingress batching, known healthy references, instantaneous sampling, fixed routes and zero latency. Delay excludes missed events; the event count must be considered alongside it. Mode transitions are local decisions and incur no extra network cost. All real polls use the existing cost model: 64 bytes per transaction + 32 per record; two messages per transaction. Nothing here represents real SDN measurements.

## Tests

After installing dashboard requirements, run with the same Python environment:

```sh
python -m unittest discover -v
```

For just the dependency-free original tests:

```sh
python -m unittest test_simulation test_hybrid -v
```

Library references: [Flask quickstart](https://flask.palletsprojects.com/en/stable/quickstart/), [Flask testing](https://flask.palletsprojects.com/en/stable/testing/), and [Chart.js script-tag integration](https://www.chartjs.org/docs/latest/getting-started/integration.html). Chart.js is pinned locally at 4.5.1; its license is preserved alongside the library.
