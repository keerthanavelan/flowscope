"""Additive policies: the original policy implementations are unchanged."""
from algorithms import Fixed, PathAdaptive


class FixedPath(Fixed):
    name = 'fixed_path'

    def __init__(self, flows, settings):
        super().__init__(flows, settings)
        self.groups = {}
        for flow in flows:
            self.groups.setdefault(flow.path, []).append(flow.name)
        self.due = {path: 0 for path in self.groups}


class Hybrid(PathAdaptive):
    name = 'hybrid'

    def __init__(self, flows, settings):
        super().__init__(flows, settings)
        self.paths = dict(self.groups)
        self.mode = {p: 'path' for p in self.paths}
        self.stable = {p: 0 for p in self.paths}
        self.last_values = {}
        self.pending = {p: {} for p in self.paths}
        self.flow_path = {}
        self.transitions = []
        for path, members in self.paths.items():
            for flow in members:
                key = 'flow:' + flow
                self.groups[key] = [flow]
                self.flow_path[key] = path

    def select(self, t):
        selected = []
        for path, members in self.paths.items():
            if t >= self.due[path]:
                selected.extend([path] if self.mode[path] == 'path'
                                else ['flow:' + f for f in members])
        return selected

    def changed(self, previous, current):
        return abs(current - previous) / max(abs(previous), 1e-12) >= self.settings.change_threshold

    def observe(self, key, t, values):
        if key in self.paths:
            total = sum(values.values())
            trigger = key in self.previous and self.changed(self.previous[key], total)
            super().observe(key, t, values)
            self.last_values[key] = dict(values)
            if trigger:
                self.mode[key] = 'flow'
                self.stable[key] = 0
                self.due[key] = t + self.settings.minimum
                self.transitions.append({'time': t, 'path': key, 'mode': 'flow'})
            return

        path = self.flow_path[key]
        self.pending[path].update(values)
        # One observation is a complete synchronous round, not a single reply.
        if len(self.pending[path]) != len(self.paths[path]):
            return
        current = self.pending[path]
        stable = all(not self.changed(self.last_values[path][f], current[f])
                     for f in self.paths[path])
        self.stable[path] = self.stable[path] + 1 if stable else 0
        self.last_values[path] = dict(current)
        self.previous[path] = sum(current.values())
        self.pending[path] = {}
        if self.stable[path] >= 2:
            self.mode[path] = 'path'
            self.intervals[path] = self.settings.fixed_interval
            self.due[path] = t + self.settings.fixed_interval
            self.transitions.append({'time': t, 'path': path, 'mode': 'path'})
        else:
            self.due[path] = t + self.settings.minimum
