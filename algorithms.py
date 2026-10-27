"""Selection/scheduling policies. Policies only receive sampled observations."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    fixed_interval: int = 8
    minimum: int = 2
    maximum: int = 16
    change_threshold: float = .20
    alarm_multiplier: float = 1.5

    def __post_init__(self):
        if not (1 <= self.minimum <= self.fixed_interval <= self.maximum):
            raise ValueError('require 1 <= minimum <= fixed_interval <= maximum')
        if self.change_threshold <= 0 or self.alarm_multiplier <= 1:
            raise ValueError('invalid change or alarm threshold')


class Fixed:
    name = 'fixed'

    def __init__(self, flows, settings):
        self.settings = settings
        self.groups = {f.name: [f.name] for f in flows}
        self.due = {k: 0 for k in self.groups}

    def select(self, t):
        return [k for k in self.groups if t >= self.due[k]]

    def observe(self, key, t, values):
        self.due[key] = t + self.settings.fixed_interval


class FlowAdaptive(Fixed):
    name = 'flow_adaptive'

    def __init__(self, flows, settings):
        super().__init__(flows, settings)
        self.intervals = {k: settings.fixed_interval for k in self.groups}
        self.previous = {}

    def observe(self, key, t, values):
        current = sum(values.values())
        if key in self.previous:
            change = abs(current - self.previous[key]) / max(abs(self.previous[key]), 1e-12)
            interval = self.intervals[key]
            self.intervals[key] = (max(self.settings.minimum, interval // 2)
                                   if change >= self.settings.change_threshold
                                   else min(self.settings.maximum, interval * 2))
        self.previous[key] = current
        self.due[key] = t + self.intervals[key]


class PathAdaptive(FlowAdaptive):
    name = 'path_adaptive'

    def __init__(self, flows, settings):
        super().__init__(flows, settings)
        self.groups = {}
        for f in flows:
            self.groups.setdefault(f.path, []).append(f.name)
        self.due = {k: 0 for k in self.groups}
        self.intervals = {k: settings.fixed_interval for k in self.groups}
