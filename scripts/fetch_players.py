#!/usr/bin/env python3
"""Fetch every innings of every Test player for one team from ESPNcricinfo Statsguru.

Three player-innings lists (batting, bowling, fielding) are grouped into one record
per Test, keyed by (start date, opposition) - a team never plays two Tests at once.

Output: data/players_<team>.json  (oldest Test first)

Usage:  python3 scripts/fetch_players.py            # India
        python3 scripts/fetch_players.py 6 india    # Statsguru team id, file suffix
"""
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from fetch_results import CELL_RE, PAGES_RE, ROW_RE, get, text

TEAM_ID = sys.argv[1] if len(sys.argv) > 1 else "6"
SUFFIX = sys.argv[2] if len(sys.argv) > 2 else "india"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / f"players_{SUFFIX}.json"
URL = ("https://stats.espncricinfo.com/ci/engine/stats/index.html?"
       "class=1;team={team};template=results;type={kind};view=innings;size=200;page={page}")
PLAYER_RE = re.compile(r"/player/(\d+)\.html")
GROUND_RE = re.compile(r"/ground/(\d+)\.html")

# column layout of each list (0-based), after the player cell
LAYOUT = {
    "batting":  {"inns": 7, "opp": 9, "ground": 10, "date": 11},
    "bowling":  {"inns": 7, "opp": 9, "ground": 10, "date": 11},
    "fielding": {"inns": 6, "opp": 8, "ground": 9, "date": 10},
}


def num(s):
    s = s.strip()
    return int(s) if s.isdigit() else 0


def parse(kind, h):
    L, out = LAYOUT[kind], []
    for raw in ROW_RE.findall(h):
        c = CELL_RE.findall(raw)
        if len(c) <= L["date"]:
            continue
        pid = PLAYER_RE.search(c[0])
        g = GROUND_RE.search(c[L["ground"]])
        out.append({
            "pid": pid.group(1) if pid else text(c[0]),
            "name": text(c[0]),
            "cells": [text(x) for x in c],
            "inns": num(text(c[L["inns"]])),
            "opp": re.sub(r"^v\s+", "", text(c[L["opp"]])),
            "ground": text(c[L["ground"]]),
            "ground_id": g.group(1) if g else "",
            "date": datetime.strptime(text(c[L["date"]]), "%d %b %Y").strftime("%Y-%m-%d"),
        })
    return out


def fetch(kind):
    """All pages of one list; a few pages at a time (each page is ~850 KB and slow to serve)."""
    first = get(URL.format(team=TEAM_ID, kind=kind, page=1))
    m = PAGES_RE.search(first)
    pages = int(m.group(1)) if m else 1
    out = parse(kind, first)

    def one(page):
        time.sleep(0.5)
        return parse(kind, get(URL.format(team=TEAM_ID, kind=kind, page=page)))

    with ThreadPoolExecutor(max_workers=4) as ex:
        for page, rows in zip(range(2, pages + 1), ex.map(one, range(2, pages + 1))):
            out += rows
            print(f"  {kind}: page {page}/{pages} -> {len(out)} rows", flush=True)
    return out


def main():
    tests, names = {}, {}

    def test(r):
        key = (r["date"], r["opp"])
        t = tests.setdefault(key, {"date": r["date"], "opp": r["opp"], "ground": r["ground"],
                                   "players": set(), "bat": [], "bowl": [], "field": []})
        t["players"].add(r["pid"])
        names[r["pid"]] = r["name"]
        return t

    for r in fetch("batting"):
        t = test(r)
        runs = r["cells"][1]
        m = re.match(r"^(\d+)(\*?)$", runs)
        if m:  # batted (DNB / TDNB / absent / sub rows only mark the player as playing)
            t["bat"].append([r["pid"], r["inns"], int(m.group(1)), 1 if m.group(2) else 0])
    for r in fetch("bowling"):
        t = test(r)
        overs, wkts = r["cells"][1], r["cells"][5]
        if re.match(r"^\d", overs):  # bowled in this innings
            t["bowl"].append([r["pid"], r["inns"], num(wkts)])
    for r in fetch("fielding"):
        t = test(r)
        c = r["cells"]
        # [pid, inns, keeper catches, fielder catches, stumpings]
        t["field"].append([r["pid"], r["inns"], num(c[4]), num(c[5]), num(c[3])])

    rows = []
    for key in sorted(tests):
        t = tests[key]
        t["players"] = sorted(t["players"])
        rows.append(t)
    OUT.write_text(json.dumps({"team_id": TEAM_ID, "names": names, "tests": rows}, separators=(",", ":")))
    print(f"wrote {len(rows)} Tests, {len(names)} players -> {OUT}")


if __name__ == "__main__":
    main()
