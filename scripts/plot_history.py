#!/usr/bin/env python3
"""Draw every team's rating after each Test, 1877 to date, as small multiples.

Uses the same default points system as the app (app/template.html, DEFAULTS).
Output: dist/ratings_history.svg
"""
from datetime import date
from pathlib import Path

from ratings_engine import COLORS, ROOT, compute, year

matches, hist = compute()

# ---------- layout ----------
last_date = matches[-1]["date"]
last_year = year(last_date)
teams = [t for t in hist if len(hist[t]) > 1]          # drops the one-off ICC World XI
active = lambda t: last_year - hist[t][-1][0] <= 4
teams.sort(key=lambda t: (not active(t), -hist[t][-1][1]))

COLS, PW, PH = 3, 360, 190            # panel width/height
GX, GY = 28, 64                       # gaps between panels
ML, MT, MB = 44, 150, 60              # outer margins
X0, X1 = 1877, 2027
Y0, Y1 = 60, 145
rows = (len(teams) + COLS - 1) // COLS
W = ML + COLS * PW + (COLS - 1) * GX + 24
H = MT + rows * PH + (rows - 1) * GY + MB

INK, MUTED, GRID, CTX, ACC, PEAK, BG = "#142019", "#5d6b62", "#e3e8e4", "#c9d1cb", "#1f4d36", "#b3202c", "#ffffff"
FONT = "IBM Plex Sans, Helvetica, Arial, sans-serif"


def path(points, px, py):
    """SVG path; breaks the line where a team went 5+ years without a Test."""
    d, prev = [], None
    for x, y, _ in points:
        cmd = "M" if prev is None or x - prev > 5 else "L"
        d.append(f"{cmd}{px(x):.1f},{py(y):.1f}")
        prev = x
    return "".join(d)


out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">',
       f'<rect width="{W}" height="{H}" fill="{BG}"/>',
       f'<text x="{ML}" y="44" font-size="26" font-weight="700" fill="{INK}">Test team ratings after every Test, 1877 to {date.fromisoformat(last_date).strftime("%-d %b %Y")}</text>',
       f'<text x="{ML}" y="72" font-size="14" fill="{MUTED}">{len(matches):,} Tests. Each panel highlights one team; the grey lines are every other team. Line breaks mark gaps of 5+ years without a Test.</text>',
       f'<text x="{ML}" y="92" font-size="14" fill="{MUTED}">Ordered by current rating; teams in italics have not played in 4 years. Open circle = peak rating, filled dot = now. Dashed line = 100, the starting rating.</text>']

for k, t in enumerate(teams):
    c, r = k % COLS, k // COLS
    ox, oy = ML + c * (PW + GX), MT + r * (PH + GY)
    px = lambda x, ox=ox: ox + (x - X0) / (X1 - X0) * PW
    py = lambda y, oy=oy: oy + PH - (min(max(y, Y0), Y1) - Y0) / (Y1 - Y0) * PH
    h = hist[t]
    peak = max(h, key=lambda p: p[1])
    cur = h[-1]
    style = "" if active(t) else ' font-style="italic"'
    out.append(f'<text x="{ox}" y="{oy - 26}" font-size="16" font-weight="600" fill="{INK}"{style}>{k + 1}. {t}</text>')
    out.append(f'<text x="{ox}" y="{oy - 9}" font-size="12" fill="{MUTED}">now {cur[1]:.1f} · peak {peak[1]:.1f} ({peak[2][:4]}) · {len(h)} Tests</text>')
    for gy in (80, 100, 120, 140):
        dash = ' stroke-dasharray="4 3"' if gy == 100 else ""
        col = MUTED if gy == 100 else GRID
        out.append(f'<line x1="{ox}" x2="{ox + PW}" y1="{py(gy):.1f}" y2="{py(gy):.1f}" stroke="{col}" stroke-width="1"{dash} opacity="{0.6 if gy == 100 else 1}"/>')
        if c == 0:
            out.append(f'<text x="{ox - 8}" y="{py(gy) + 4:.1f}" font-size="11" fill="{MUTED}" text-anchor="end">{gy}</text>')
    for gx in (1880, 1920, 1960, 2000):
        out.append(f'<text x="{px(gx):.1f}" y="{oy + PH + 16}" font-size="11" fill="{MUTED}" text-anchor="middle">{gx}</text>')
    out.append(f'<line x1="{ox}" x2="{ox + PW}" y1="{oy + PH}" y2="{oy + PH}" stroke="{CTX}" stroke-width="1"/>')
    for o in teams:
        if o != t:
            out.append(f'<path d="{path(hist[o], px, py)}" fill="none" stroke="{CTX}" stroke-width="0.8" opacity="0.55"/>')
    col = COLORS.get(t, ACC)
    out.append(f'<path d="{path(h, px, py)}" fill="none" stroke="{col}" stroke-width="1.8" stroke-linejoin="round"/>')
    out.append(f'<circle cx="{px(peak[0]):.1f}" cy="{py(peak[1]):.1f}" r="4.5" fill="{BG}" stroke="{INK}" stroke-width="2"/>')
    out.append(f'<circle cx="{px(cur[0]):.1f}" cy="{py(cur[1]):.1f}" r="4.5" fill="{col}" stroke="{BG}" stroke-width="2"/>')

out.append(f'<text x="{ML}" y="{H - 20}" font-size="12" fill="{MUTED}">Source: ESPNcricinfo Statsguru. Scoring: default points system of the Test Team Ratings app (α = 0.06). ICC World XI (1 Test) not shown.</text>')
out.append("</svg>")
dest = ROOT / "dist" / "ratings_history.svg"
dest.write_text("\n".join(out))
print(f"wrote {dest}")
for t in teams:
    print(f"  {t:13s} now {hist[t][-1][1]:6.1f}  peak {max(p[1] for p in hist[t]):6.1f}")
