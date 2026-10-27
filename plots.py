"""Dependency-free SVG scientific plots; explicit scales and labels."""
from html import escape


def svg(path, title, body):
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="960" height="460" '
                    'viewBox="0 0 960 460"><rect width="960" height="460" fill="white"/>'
                    '<g font-family="sans-serif" font-size="14" fill="#172438">'
                    f'<text x="45" y="30" font-size="20">{escape(title)}</text>'
                    + body + '</g></svg>', encoding='utf-8')


COLORS = ['#1769aa', '#c35b13', '#258247']


def bars(path, title, results, metric, unit):
    vals = [r.metrics[metric] for r in results]
    maximum = max([v for v in vals if v is not None] + [1]) * 1.15
    body = f'<text x="45" y="60">{escape(unit)}</text>'
    for i in range(6):
        y = 370 - i * 55
        body += f'<path d="M90 {y} H910" stroke="#ddd"/><text x="10" y="{y+5}">{maximum*i/5:.1f}</text>'
    for i, (r, value) in enumerate(zip(results, vals)):
        h = (value or 0) / maximum * 275
        x = 170 + i * 265
        label = 'N/A' if value is None else f'{value:.3g}'
        body += f'<rect x="{x}" y="{370-h}" width="120" height="{h}" fill="{COLORS[i]}"/>'
        body += f'<text x="{x}" y="{355-h}">{label}</text><text x="{x-25}" y="405">{r.name}</text>'
    svg(path, title, body)


def traffic_plot(path, trace, results):
    body = '<text x="20" y="65">Rate (Mb/s)</text>'
    for v in range(0, 121, 30):
        y = 280 - v * 1.6
        body += f'<path d="M90 {y} H910" stroke="#ddd"/><text x="40" y="{y+5}">{v}</text>'
    for i, f in enumerate(trace.flows):
        color = ['#1769aa', '#999999', '#7d4893', '#c35b13', '#258247', '#b34576'][i]
        points = ' '.join(f'{90+t/(trace.duration-1)*820:.2f},{280-v*1.6:.2f}' for t, v in enumerate(trace.rates[f.name]))
        body += f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="1.5"/>'
        body += f'<text x="{120+i*130}" y="55" fill="{color}">{f.name}</text>'
    body += '<text x="90" y="310">f0 alarm state: colored segments = alarm held active</text>'
    for i, r in enumerate(results):
        y = 335 + i * 26
        body += f'<text x="5" y="{y+4}" font-size="11">{r.name}</text>'
        for t, alarm in enumerate(r.alarms['f0']):
            if alarm:
                x = 120 + t / (trace.duration-1) * 790
                body += f'<path d="M{x} {y} h{790/(trace.duration-1)+.2}" stroke="{COLORS[i]}" stroke-width="8"/>'
    body += '<text x="400" y="445">Time (seconds); top and bottom axes</text>'
    for t in range(0, trace.duration, 30):
        body += f'<text x="{90+t/(trace.duration-1)*820}" y="298">{t}</text>'
        body += f'<text x="{120+t/(trace.duration-1)*790}" y="415">{t}</text>'
    svg(path, 'Synthetic traffic and f0 sampled alarm states', body)
