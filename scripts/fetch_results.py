#!/usr/bin/env python3
"""Fetch every men's Test result from ESPNcricinfo Statsguru (team results view).

Runs three queries - home (1), away (2), neutral (3) - so each team-row carries
its venue type, then pairs the rows into one record per match.

Output: data/matches.json  (oldest first)

Usage:  python3 scripts/fetch_results.py
"""
import html
import json
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = ("https://stats.espncricinfo.com/ci/engine/stats/index.html?"
        "class=1;home_or_away={hoa};page={page};size=200;"
        "template=results;type=team;view=results")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) TestRatingsBot/1.0"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "matches.json"
VENUE = {1: "home", 2: "away", 3: "neutral"}

ROW_RE = re.compile(r'<tr class="data1">(.*?)</tr>', re.S)
CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
TAG_RE = re.compile(r"<[^>]+>")
PAGES_RE = re.compile(r"Page <b>\d+</b> of <b>(\d+)</b>")
GROUND_RE = re.compile(r"/ground/(\d+)\.html")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            print(f"  retry {attempt + 1}: {e}", file=sys.stderr)
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"failed: {url}")


def text(cell):
    return html.unescape(TAG_RE.sub("", cell)).strip()


def fetch_rows(hoa):
    rows, page, pages = [], 1, 1
    while page <= pages:
        h = get(BASE.format(hoa=hoa, page=page))
        m = PAGES_RE.search(h)
        pages = int(m.group(1)) if m else 1
        for raw in ROW_RE.findall(h):
            c = CELL_RE.findall(raw)
            if len(c) < 9:
                continue
            g = GROUND_RE.search(c[7])
            rows.append({
                "team": text(c[0]),
                "result": text(c[1]),
                "margin": text(c[2]),
                "toss": text(c[3]),
                "bat": text(c[4]),
                "opp": re.sub(r"^v\s+", "", text(c[6])),
                "ground": text(c[7]),
                "ground_id": g.group(1) if g else text(c[7]),
                "date": datetime.strptime(text(c[8]), "%d %b %Y").strftime("%Y-%m-%d"),
                "venue": VENUE[hoa],
            })
        print(f"  {VENUE[hoa]}: page {page}/{pages} -> {len(rows)} rows")
        page += 1
        time.sleep(1.0)
    return rows


INNS_URL = ("https://stats.espncricinfo.com/ci/engine/stats/index.html?"
            "class=1;page={page};size=200;template=results;type=team;view=innings")


def fetch_follow_ons():
    """Return {match_key: team} for every match in which a team followed on.

    A team followed on when it batted in both the 2nd and 3rd innings.
    """
    batted, page, pages = {}, 1, 1
    while page <= pages:
        h = get(INNS_URL.format(page=page))
        m = PAGES_RE.search(h)
        pages = int(m.group(1)) if m else 1
        for raw in ROW_RE.findall(h):
            c = CELL_RE.findall(raw)
            if len(c) < 11:
                continue
            inns = text(c[5])
            if inns not in ("2", "3"):
                continue
            team = text(c[0])
            opp = re.sub(r"^v\s+", "", text(c[8]))
            g = GROUND_RE.search(c[9])
            date = datetime.strptime(text(c[10]), "%d %b %Y").strftime("%Y-%m-%d")
            key = (date, g.group(1) if g else text(c[9]), tuple(sorted([team, opp])))
            batted.setdefault(key, {}).setdefault(team, set()).add(inns)
        print(f"  innings: page {page}/{pages}")
        page += 1
        time.sleep(1.0)
    return {k: t for k, teams in batted.items() for t, s in teams.items() if s == {"2", "3"}}


RESULT_MAP = {"won": "won", "lost": "won", "draw": "drawn", "tied": "tied",
              "aban": "abandoned", "canc": "abandoned"}


def main():
    all_rows = []
    for hoa in (1, 2, 3):
        all_rows += fetch_rows(hoa)
    follow_ons = fetch_follow_ons()

    # Pair the two team-rows of each match
    by_key = {}
    for r in all_rows:
        key = (r["date"], r["ground_id"], tuple(sorted([r["team"], r["opp"]])))
        by_key.setdefault(key, {})[r["team"]] = r

    matches = []
    for key, sides in by_key.items():
        date, gid, (a, b) = key
        ra, rb = sides.get(a), sides.get(b)
        base = ra or rb
        res_a = ra["result"] if ra else mirror(rb["result"])
        result = RESULT_MAP.get(res_a)
        if result is None:          # "-" = match in progress / not yet decided
            continue
        winner = a if res_a == "won" else b if res_a == "lost" else None
        matches.append({
            "date": date,
            "ground": base["ground"],
            "teams": [a, b],
            "venue": {a: ra["venue"] if ra else flip(rb["venue"]),
                      b: rb["venue"] if rb else flip(ra["venue"])},
            "result": result,
            "winner": winner,
            "margin": base["margin"] if base["margin"] not in ("-", "") else "",
            "follow_on": follow_ons.get(key),
        })
    matches.sort(key=lambda m: (m["date"], m["ground"]))
    for i, m in enumerate(matches, 1):
        m["no"] = i
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(matches, separators=(",", ":")))
    print(f"wrote {len(matches)} matches -> {OUT}")


def mirror(res):
    return {"won": "lost", "lost": "won"}.get(res, res)


def flip(v):
    return {"home": "away", "away": "home"}.get(v, v)


if __name__ == "__main__":
    main()
