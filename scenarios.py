"""Three paired scenarios using the original topology and seeded healthy noise."""
import random
from traffic import Event, generate

SCENARIOS = ('single', 'simultaneous', 'offsetting')


def scenario(name, seed):
    if name not in SCENARIOS:
        raise ValueError(f'unknown scenario: {name}')
    trace = generate(seed)
    # Undo only the original injected events, retaining the original healthy trace.
    for event in trace.events:
        for t in range(event.start, event.end):
            trace.rates[event.flow][t] /= 3
    start = random.Random(seed + 10000).randint(50, 75)
    end = start + 25
    targets = ['f0', 'f1', 'f3'] if name == 'simultaneous' else ['f0']
    trace.events = [Event(f, start, end) for f in targets]
    for t in range(start, end):
        if name == 'offsetting':
            # Exactly cancel the injected change in p0's sum; rates stay positive.
            trace.rates['f0'][t] += 10
            trace.rates['f1'][t] -= 10
        else:
            for flow in targets:
                trace.rates[flow][t] *= 3
    return trace
