"""Hybrid with periodic per-flow audits; original Hybrid is unchanged."""
from hybrid import Hybrid


class AuditedHybrid(Hybrid):
    name = 'audited_hybrid'

    def __init__(self, flows, settings, audit_interval=8):
        if type(audit_interval) is not int or not 2 <= audit_interval <= 32:
            raise ValueError('Audit interval must be an integer from 2 to 32 seconds.')
        super().__init__(flows, settings)
        self.audit_interval = audit_interval
        self.audit_due = {p: audit_interval for p in self.paths}
        self.audit_pending = {p: {} for p in self.paths}
        self.audit_paths = {}
        self.audits = []
        for path, members in self.paths.items():
            for flow in members:
                key = 'audit:' + flow
                self.groups[key] = [flow]
                self.audit_paths[key] = path

    def select(self, t):
        selected = []
        for path, members in self.paths.items():
            if self.mode[path] == 'flow':
                if t >= self.due[path]:
                    selected.extend('flow:' + f for f in members)
            elif t >= self.due[path]:
                # A due batch satisfies an audit too: never duplicate observations.
                selected.append(path)
            elif t >= self.audit_due[path]:
                selected.extend('audit:' + f for f in members)
        return selected

    def finish_audit(self, path, t, values, previous, source):
        changed = bool(previous) and any(self.changed(previous[f], values[f]) for f in values)
        self.audits.append({'time': t, 'path': path, 'source': source, 'changed': changed})
        self.audit_due[path] = t + self.audit_interval
        self.last_values[path] = dict(values)
        self.previous[path] = sum(values.values())
        if changed and self.mode[path] == 'path':
            self.mode[path] = 'flow'
            self.stable[path] = 0
            self.due[path] = t + self.settings.minimum
            self.transitions.append({'time': t, 'path': path, 'mode': 'flow', 'reason': 'audit'})

    def observe(self, key, t, values):
        if key in self.audit_paths:
            path = self.audit_paths[key]
            self.audit_pending[path].update(values)
            if len(self.audit_pending[path]) == len(self.paths[path]):
                self.finish_audit(path, t, self.audit_pending[path], self.last_values[path], 'individual_polls')
                self.audit_pending[path] = {}
            return
        if key in self.paths:
            previous = self.last_values.get(key, {}).copy()
            audit_due = t >= self.audit_due[key]
            super().observe(key, t, values)
            if audit_due:
                self.finish_audit(key, t, values, previous, 'reused_batch')
            return
        path = self.flow_path[key]
        super().observe(key, t, values)
        if self.mode[path] == 'path':
            # Audits are suspended during fast mode, then restart on return.
            self.audit_due[path] = t + self.audit_interval
