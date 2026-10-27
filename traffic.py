"""Seeded synthetic rate traces; no sockets, switches or SDN controller required."""
from dataclasses import dataclass
import math
import random


@dataclass(frozen=True)
class Flow:
    name: str
    path: str
    reference: float


@dataclass(frozen=True)
class Event:
    flow: str
    start: int
    end: int  # exclusive


@dataclass
class Trace:
    paths: dict
    flows: list
    rates: dict
    events: list
    duration: int


def generate(seed=7, duration=180):
    if duration < 150:
        raise ValueError('duration must be at least 150 seconds')
    rng = random.Random(seed)
    paths = {'p0': ('s0', 's1', 's3'), 'p1': ('s0', 's2', 's3'),
             'p2': ('s1', 's2', 's3')}
    flows = [Flow(f'f{i}', f'p{i // 2}', float(10 + 5 * i)) for i in range(6)]
    events = [Event('f0', 60, 85), Event('f3', 120, 140)]
    rates = {}
    for f in flows:
        rates[f.name] = [f.reference * (1 + .04 * math.sin(t / 11 + int(f.name[1:]))
                          + rng.uniform(-.02, .02))
                         * (3 if any(e.flow == f.name and e.start <= t < e.end
                                     for e in events) else 1)
                         for t in range(duration)]
    return Trace(paths, flows, rates, events, duration)
