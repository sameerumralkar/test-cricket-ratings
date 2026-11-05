#!/usr/bin/env python3
"""Embed data/matches.json into app/template.html -> dist/index.html."""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
matches = json.loads((ROOT / "data" / "matches.json").read_text())

rows = []
for m in matches:
    a, b = m["teams"]
    w = {None: -1, a: 0, b: 1}[m["winner"]]
    fo = {None: -1, a: 0, b: 1}[m["follow_on"]]
    # [date, ground, teamA, teamB, venueOfA, result, winnerIdx, margin, followOnIdx]
    rows.append([m["date"], m["ground"], a, b, m["venue"][a], m["result"], w, m["margin"], fo])

payload = {
    "built": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    "source": "ESPNcricinfo Statsguru - Test team results",
    "matches": rows,
    "colors": {t: v["hex"] for t, v in json.loads((ROOT / "data" / "team_colors.json").read_text()).items()},
}
tpl = (ROOT / "app" / "template.html").read_text()
out = tpl.replace('"__DATA__"', json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
(ROOT / "dist").mkdir(exist_ok=True)
(ROOT / "dist" / "index.html").write_text(out)
print(f"built dist/index.html with {len(rows)} Tests ({len(out)//1024} KB)")
