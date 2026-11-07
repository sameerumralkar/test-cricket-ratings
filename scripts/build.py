#!/usr/bin/env python3
"""Embed data/matches.json into app/template.html -> dist/index.html."""
import json
from datetime import datetime, timezone
from pathlib import Path

from points import latest as latest_points

ROOT = Path(__file__).resolve().parent.parent
matches = json.loads((ROOT / "data" / "matches.json").read_text())

POINTS_FILE, POINTS = latest_points()

rows = []
for m in matches:
    a, b = m["teams"]
    w = {None: -1, a: 0, b: 1}[m["winner"]]
    fo = {None: -1, a: 0, b: 1}[m["follow_on"]]
    # [date, ground, teamA, teamB, venueOfA, result, winnerIdx, margin, followOnIdx]
    rows.append([m["date"], m["ground"], a, b, m["venue"][a], m["result"], w, m["margin"], fo])

# Player innings for India, one row per Test:
# [date, opp, ground, playerIdx[], bat[[idx, runs, notOut]], bowl[[idx, wkts]], field[[idx, ctWk, ctField, st]]]
pdata = json.loads((ROOT / "data" / "players_india.json").read_text())
pids = sorted(pdata["names"], key=int)
pix = {p: i for i, p in enumerate(pids)}
players = {
    "team": "India",
    "names": [pdata["names"][p] for p in pids],
    "tests": [[t["date"], t["opp"], t["ground"], [pix[p] for p in t["players"]],
               [[pix[r[0]], r[2], r[3]] for r in t["bat"]],
               [[pix[r[0]], r[2]] for r in t["bowl"]],
               [[pix[r[0]], r[2], r[3], r[4]] for r in t["field"]]] for t in pdata["tests"]],
}

payload = {
    "built": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    "source": "ESPNcricinfo Statsguru - Test team results",
    "matches": rows,
    "points": POINTS,
    "pointsFile": POINTS_FILE,
    "repo": "sameerumralkar/test-cricket-ratings",
    "players": players,
    "playerPoints": json.loads((ROOT / "data" / "player_points.json").read_text()),
    "colors": {t: v["hex"] for t, v in json.loads((ROOT / "data" / "team_colors.json").read_text()).items()},
}
tpl = (ROOT / "app" / "template.html").read_text()
out = tpl.replace('"__DATA__"', json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
(ROOT / "dist").mkdir(exist_ok=True)
(ROOT / "dist" / "index.html").write_text(out)
print(f"built dist/index.html with {len(rows)} Tests, {len(players['names'])} Indian players, points from {POINTS_FILE} ({len(out)//1024} KB)")
