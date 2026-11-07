#!/usr/bin/env python3
"""Fetch every innings of every Test player, team by team, from ESPNcricinfo Statsguru.

Three player-innings lists (batting, bowling, fielding) are grouped into one record
per Test, keyed by (start date, opposition) - a team never plays two Tests at once.

Output: data/players/<team>.json  (oldest Test first)

Usage:  python3 scripts/fetch_players.py               # every team, only Tests since each file's last one
        python3 scripts/fetch_players.py india         # one team
        python3 scripts/fetch_players.py all --full    # re-download everything (slow: ~2 hours)
An update re-fetches the last 60 days before each file's newest Test and replaces those Tests,
so corrections and Tests that were in progress get picked up.
"""
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

from fetch_results import CELL_RE, PAGES_RE, ROW_RE, get, text

# file slug -> (Statsguru team id, team name as in data/matches.json)
TEAMS = {
    "england": (1, "England"), "australia": (2, "Australia"), "south-africa": (3, "South Africa"),
    "west-indies": (4, "West Indies"), "new-zealand": (5, "New Zealand"), "india": (6, "India"),
    "pakistan": (7, "Pakistan"), "sri-lanka": (8, "Sri Lanka"), "zimbabwe": (9, "Zimbabwe"),
    "bangladesh": (25, "Bangladesh"), "ireland": (29, "Ireland"), "afghanistan": (40, "Afghanistan"),
}
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "players"
URL = ("https://stats.espncricinfo.com/ci/engine/stats/index.html?"
       "class=1;team={team};template=results;type={kind};view=innings;size=200;page={page}{since}")
PLAYER_RE = re.compile(r"/player/(\d+)\.html")
GROUND_RE = re.compile(r"/ground/(\d+)\.html")

# Columns are found by their headings on every page: Statsguru drops some (e.g. BPO, balls per
# over) when no row in the result needs them, so fixed positions would shift.
TH_RE = re.compile(r"<th[^>]*>(.*?)</th>", re.S)
NEED = {"batting": ("Runs",), "bowling": ("Overs", "Wkts"), "fielding": ("Ct", "St", "Ct Wk", "Ct Fi")}


def columns(h, kind):
    i = h.find('<tr class="data1">')
    head = h.rfind("<thead", 0, i)
    names = [text(x) for x in TH_RE.findall(h[head:i])] if head >= 0 else []
    col = {}
    for j, n in enumerate(names):
        col.setdefault(n, j)
    for n in ("Player", "Inns", "Opposition", "Ground", "Start Date") + NEED[kind]:
        if n not in col:
            raise SystemExit(f"Statsguru {kind} list has no '{n}' column (headings: {names}); the page format changed")
    return col


def num(s):
    s = s.strip()
    return int(s) if s.isdigit() else 0


def parse(kind, h):
    out = []
    if '<tr class="data1">' not in h:
        return out
    C = columns(h, kind)
    for raw in ROW_RE.findall(h):
        c = CELL_RE.findall(raw)
        if len(c) <= C["Start Date"] or not re.match(r"^\d{1,2} \w{3} \d{4}$", text(c[C["Start Date"]])):
            continue  # "No records available" and similar rows
        pid = PLAYER_RE.search(c[C["Player"]])
        g = GROUND_RE.search(c[C["Ground"]])
        cell = {n: text(c[j]) for n, j in C.items() if j < len(c)}
        out.append({
            "pid": pid.group(1) if pid else cell["Player"],
            "name": cell["Player"],
            "cell": cell,
            "inns": num(cell["Inns"]),
            "opp": re.sub(r"^v\s+", "", cell["Opposition"]),
            "ground": cell["Ground"],
            "ground_id": g.group(1) if g else "",
            "date": datetime.strptime(cell["Start Date"], "%d %b %Y").strftime("%Y-%m-%d"),
        })
    return out


def fetch(team_id, kind, since=""):
    """All pages of one list; a few pages at a time (each page is ~850 KB and slow to serve)."""
    url = lambda page: URL.format(team=team_id, kind=kind, page=page, since=since)
    first = get(url(1))
    m = PAGES_RE.search(first)
    pages = int(m.group(1)) if m else 1
    out = parse(kind, first)

    def one(page):
        time.sleep(0.5)
        return parse(kind, get(url(page)))

    with ThreadPoolExecutor(max_workers=4) as ex:
        for page, rows in zip(range(2, pages + 1), ex.map(one, range(2, pages + 1))):
            out += rows
            print(f"  team {team_id} {kind}: page {page}/{pages} -> {len(out)} rows", flush=True)
    return out


def fetch_team(slug, full=False):
    team_id, team = TEAMS[slug]
    out = OUT_DIR / f"{slug}.json"
    old = json.loads(out.read_text()) if out.exists() and not full else None
    since, cutoff = "", None
    if old and old["tests"]:
        cutoff = (date.fromisoformat(old["tests"][-1]["date"]) - timedelta(days=60)).isoformat()
        since = ";spanmin1=" + date.fromisoformat(cutoff).strftime("%d+%b+%Y") + ";spanval1=span"
    tests, names = {}, dict(old["names"]) if old else {}

    def test(r):
        key = (r["date"], r["opp"])
        t = tests.setdefault(key, {"date": r["date"], "opp": r["opp"], "ground": r["ground"],
                                   "players": set(), "bat": [], "bowl": [], "field": []})
        t["players"].add(r["pid"])
        names[r["pid"]] = r["name"]
        return t

    for r in fetch(team_id, "batting", since):
        t = test(r)
        m = re.match(r"^(\d+)(\*?)$", r["cell"]["Runs"])
        if m:  # batted (DNB / TDNB / absent / sub rows only mark the player as playing)
            t["bat"].append([r["pid"], r["inns"], int(m.group(1)), 1 if m.group(2) else 0])
    for r in fetch(team_id, "bowling", since):
        t = test(r)
        if re.match(r"^\d", r["cell"]["Overs"]):  # bowled in this innings
            t["bowl"].append([r["pid"], r["inns"], num(r["cell"]["Wkts"])])
    for r in fetch(team_id, "fielding", since):
        t = test(r)
        c = r["cell"]
        # [pid, inns, keeper catches, fielder catches, stumpings]
        t["field"].append([r["pid"], r["inns"], num(c["Ct Wk"]), num(c["Ct Fi"]), num(c["St"])])

    rows = [t for t in (old["tests"] if old else []) if not cutoff or t["date"] < cutoff]
    for key in sorted(tests):
        t = tests[key]
        t["players"] = sorted(t["players"])
        rows.append(t)
    rows.sort(key=lambda t: t["date"])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"team": team, "team_id": team_id, "names": names, "tests": rows}, separators=(",", ":")))
    print(f"{team}: {len(rows)} Tests ({len(tests)} fetched{' since ' + cutoff if cutoff else ''}), {len(names)} players -> {out.name}", flush=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    full = "--full" in sys.argv
    slugs = list(TEAMS) if not args or args[0] == "all" else args
    for slug in slugs:
        fetch_team(slug, full)


if __name__ == "__main__":
    main()
