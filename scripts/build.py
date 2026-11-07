#!/usr/bin/env python3
"""Embed data/matches.json into app/template.html -> dist/index.html."""
import json
from datetime import datetime, timezone
from pathlib import Path

from points import latest as latest_points, latest_player

ROOT = Path(__file__).resolve().parent.parent
matches = json.loads((ROOT / "data" / "matches.json").read_text())

POINTS_FILE, POINTS = latest_points()
PLAYER_POINTS_FILE, PLAYER_POINTS = latest_player()

rows = []
for m in matches:
    a, b = m["teams"]
    w = {None: -1, a: 0, b: 1}[m["winner"]]
    fo = {None: -1, a: 0, b: 1}[m["follow_on"]]
    # [date, ground, teamA, teamB, venueOfA, result, winnerIdx, margin, followOnIdx]
    rows.append([m["date"], m["ground"], a, b, m["venue"][a], m["result"], w, m["margin"], fo])

# Player innings, one file per team, loaded by the app when that team is picked on the Players tab.
# Each row is one Test:
# [date, opp, ground, playerIdx[], bat[[idx, runs, notOut]], bowl[[idx, wkts]], field[[idx, ctWk, ctField, st]]]
(ROOT / "dist" / "players").mkdir(parents=True, exist_ok=True)
player_teams = []
for f in sorted((ROOT / "data" / "players").glob("*.json")):
    pdata = json.loads(f.read_text())
    # Only finished Tests: a Test with no team result (still in progress) waits until it ends.
    done = {(m["date"], o) for m in matches for t, o in (m["teams"], m["teams"][::-1]) if t == pdata["team"]}
    pdata["tests"] = [t for t in pdata["tests"] if (t["date"], t["opp"]) in done]
    pids = sorted(pdata["names"], key=int)
    pix = {p: i for i, p in enumerate(pids)}
    compact = {
        "team": pdata["team"],
        "names": [pdata["names"][p] for p in pids],
        "tests": [[t["date"], t["opp"], t["ground"], [pix[p] for p in t["players"]],
                   [[pix[r[0]], r[2], r[3]] for r in t["bat"]],
                   [[pix[r[0]], r[2]] for r in t["bowl"]],
                   [[pix[r[0]], r[2], r[3], r[4]] for r in t["field"]]] for t in pdata["tests"]],
    }
    (ROOT / "dist" / "players" / f.name).write_text(json.dumps(compact, separators=(",", ":"), ensure_ascii=False))
    player_teams.append({"slug": f.stem, "team": pdata["team"], "tests": len(pdata["tests"]), "players": len(pids)})

payload = {
    "built": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    "source": "ESPNcricinfo Statsguru - Test team results",
    "matches": rows,
    "points": POINTS,
    "pointsFile": POINTS_FILE,
    "repo": "sameerumralkar/test-cricket-ratings",
    "playerTeams": player_teams,
    "playerPoints": PLAYER_POINTS,
    "playerPointsFile": PLAYER_POINTS_FILE,
    "colors": {t: v["hex"] for t, v in json.loads((ROOT / "data" / "team_colors.json").read_text()).items()},
}
tpl = (ROOT / "app" / "template.html").read_text()
out = tpl.replace('"__DATA__"', json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
(ROOT / "dist").mkdir(exist_ok=True)
(ROOT / "dist" / "index.html").write_text(out)
print(f"built dist/index.html with {len(rows)} Tests, players for {len(player_teams)} teams, points from {POINTS_FILE} ({len(out)//1024} KB)")
