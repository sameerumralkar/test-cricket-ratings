#!/usr/bin/env python3
"""All Test teams' ratings on one chart, 1877 to date.

One point per team per calendar year it played (its rating after its last Test
that year), so 12 lines stay readable. Identity = colour x line style, plus a
name label at the end of every line.
Output: dist/ratings_combined.svg (current form) or, with the argument
"cumulative", dist/ratings_cumulative.svg (every Test to date counts equally).
"""
import sys
from datetime import date

from ratings_engine import COLORS, ROOT, compute, year

MODE = sys.argv[1] if len(sys.argv) > 1 else "form"
CUM = MODE == "cumulative"
# Cumulative ratings sit closer together, so the same-strength band is halved to +/-4.
matches, hist = compute("cumulative") if CUM else compute()

# Colours come from data/team_colors.json. Line style separates the six
# longest-standing teams (solid) from the rest (dashed), which also keeps
# similar colours apart (e.g. South Africa vs Ireland).
DASHED = {"Sri Lanka", "Pakistan", "Bangladesh", "Zimbabwe", "Afghanistan", "Ireland"}
STYLE = {t: (c, t in DASHED) for t, c in COLORS.items() if t != "ICC World XI"}

# end-of-year series
series = {}
for t, h in hist.items():
    if t not in STYLE:
        continue  # ICC World XI, one Test
    by_year = {}
    for x, r, d in h:
        by_year[int(d[:4])] = r
    series[t] = sorted(by_year.items())

last_date = matches[-1]["date"]
order = sorted(series, key=lambda t: -series[t][-1][1])
_lo = min(r for v in series.values() for _, r in v)
_hi = max(r for v in series.values() for _, r in v)
Y0, Y1 = int(_lo // 5 * 5), int(-(-_hi // 5) * 5)

SUB = ("Average match score over every Test a team has played to date, with no fading of old results. " if CUM else "")
FOOT = ("cumulative average; each team starts with 10 Tests at its starting rating; same-strength band ±4" if CUM else "α = 0.06")
W, H = 1400, 800
ML, MR, MT, MB = 64, 150, 170, 70
X0, X1 = 1876, 2027
INK, MUTED, GRID, BG = "#142019", "#5d6b62", "#e6ebe7", "#ffffff"
DASH, REFDASH = ' stroke-dasharray="6 4"', ' stroke-dasharray="5 4"'
FONT = "IBM Plex Sans, Helvetica, Arial, sans-serif"
px = lambda x: ML + (x - X0) / (X1 - X0) * (W - ML - MR)
py = lambda y: MT + (Y1 - min(max(y, Y0), Y1)) / (Y1 - Y0) * (H - MT - MB)


def path(pts):
    d, prev = [], None
    for x, y in pts:
        d.append(f"{'M' if prev is None else 'L'}{px(x + 0.5):.1f},{py(y):.1f}")
        prev = x
    return "".join(d)


o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">',
     f'<rect width="{W}" height="{H}" fill="{BG}"/>',
     f'<text x="{ML}" y="44" font-size="26" font-weight="700" fill="{INK}">{"Cumulative" if CUM else ""} Test team ratings{" (every Test counts)" if CUM else ""}, 1877 to {date.fromisoformat(last_date).strftime("%-d %b %Y")}</text>',
     f'<text x="{ML}" y="70" font-size="14" fill="{MUTED}">{SUB}</text>',
     f'<text x="{ML}" y="{90 if SUB else 70}" font-size="14" fill="{MUTED}">Each team\'s rating at the end of every year it played Tests ({len(matches):,} Tests in all). Lines run straight across years with no Tests. Dashed grey line = 100, the starting rating.</text>']

# legend, in current-rating order: two rows of six
for i, t in enumerate(order):
    c, dash = STYLE[t]
    lx, ly = ML + (i % 6) * 190, (122 if SUB else 102) + (i // 6) * 24
    o.append(f'<line x1="{lx}" x2="{lx + 28}" y1="{ly}" y2="{ly}" stroke="{c}" stroke-width="3"{DASH if dash else ""}/>')
    o.append(f'<text x="{lx + 36}" y="{ly + 5}" font-size="14" fill="{INK}">{i + 1}. {t} <tspan fill="{MUTED}">{series[t][-1][1]:.1f}</tspan></text>')

# grid
for gy in range(Y0 + (-Y0) % 5, Y1 + 1, 5 if CUM else 10):
    ref = gy == 100
    o.append(f'<line x1="{ML}" x2="{W - MR}" y1="{py(gy):.1f}" y2="{py(gy):.1f}" stroke="{MUTED if ref else GRID}" stroke-width="1"{REFDASH if ref else ""}/>')
    o.append(f'<text x="{ML - 10}" y="{py(gy) + 4:.1f}" font-size="12" fill="{MUTED}" text-anchor="end">{gy}</text>')
for gx in range(1880, 2021, 20):
    o.append(f'<line x1="{px(gx):.1f}" x2="{px(gx):.1f}" y1="{MT}" y2="{H - MB}" stroke="{GRID}" stroke-width="1"/>')
    o.append(f'<text x="{px(gx):.1f}" y="{H - MB + 20}" font-size="12" fill="{MUTED}" text-anchor="middle">{gx}</text>')
o.append(f'<text x="{ML - 48}" y="{(MT + H - MB) / 2}" font-size="12" fill="{MUTED}" transform="rotate(-90 {ML - 48} {(MT + H - MB) / 2})" text-anchor="middle">Rating</text>')

# lines: dashed (newer) first so the long-standing teams sit on top
for t in sorted(series, key=lambda t: (not STYLE[t][1], -len(series[t]))):
    c, dash = STYLE[t]
    o.append(f'<path d="{path(series[t])}" fill="none" stroke="{c}" stroke-width="{1.8 if dash else 2.2}" stroke-linejoin="round" stroke-linecap="round"{DASH if dash else ""}/>')

# end labels, nudged apart (min 15px), with a leader line to each end point
ends = sorted(((py(series[t][-1][1]), t) for t in series), key=lambda e: e[0])
placed, gap = [], 15
for y, t in ends:
    placed.append(max(y, placed[-1] + gap) if placed else y)
over = placed[-1] - (H - MB)
if over > 0:
    placed = [p - over for p in placed]
    for i in range(len(placed) - 2, -1, -1):
        placed[i] = min(placed[i], placed[i + 1] - gap)
for (y, t), ly in zip(ends, placed):
    c, dash = STYLE[t]
    ex = px(series[t][-1][0] + 0.5)
    o.append(f'<circle cx="{ex:.1f}" cy="{y:.1f}" r="4" fill="{c}" stroke="{BG}" stroke-width="2"/>')
    o.append(f'<path d="M{ex + 6:.1f},{y:.1f} L{W - MR + 10:.1f},{ly:.1f}" stroke="{c}" stroke-width="1" fill="none"/>')
    o.append(f'<text x="{W - MR + 14}" y="{ly + 4:.1f}" font-size="13" fill="{INK}">{t}</text>')

o.append(f'<text x="{ML}" y="{H - 22}" font-size="12" fill="{MUTED}">Source: ESPNcricinfo Statsguru. Scoring: default points system of the Test Team Ratings app ({FOOT}). ICC World XI (1 Test) not shown.</text>')
o.append("</svg>")
dest = ROOT / "dist" / ("ratings_cumulative.svg" if CUM else "ratings_combined.svg")
dest.write_text("\n".join(o))
print(f"wrote {dest}")
