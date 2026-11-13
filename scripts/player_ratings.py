#!/usr/bin/env python3
"""Player ratings, computed Test by Test, using the team ratings for match context.

Each Test a player plays earns batting, bowling and fielding points (newest file in data/player_points/).
Those match points are scaled by the match context taken from the team ratings: where the
Test was played, the result for the player's team, and whether the opponent was stronger,
the same or weaker going into the match. A player's rating after any Test is

    batting total x batting longevity + bowling total x bowling longevity
    + fielding total x fielding longevity

where each longevity multiplier depends on that discipline's innings count so far.

Usage:  python3 scripts/player_ratings.py [all|india|england|...] [top N]
        -> prints the top players and writes dist/players/<team>.csv
"""
import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from points import latest_player  # noqa: E402
PLAYER_POINTS_FILE, P = latest_player()  # newest file in data/player_points/


def longevity(n, L=P["longevity"]):
    if n < L["below"]:
        return 1.0
    if n <= L["upto"]:
        return L["first"]
    return round(L["first"] + L["step"] * math.ceil((n - L["upto"]) / L["every"]), 6)


def innings_bat(runs, B=P["bat"]):
    """Points for one innings: runs plus the bonus for the highest milestone reached."""
    bonus = 0
    for at, pts in B["milestones"]:
        if runs >= at:
            bonus = pts
    return runs * B["run"] + bonus


def innings_bowl(w, B=P["bowl"]):
    bonus = 0
    for at, pts in B["hauls"]:
        if w >= at:
            bonus = pts
    return w * B["wkt"] + bonus


def band(x, lst):
    """Index of the highest threshold x reaches, or -1: each haul counts once, in the band that scored it."""
    k = -1
    for j, (at, _) in enumerate(lst):
        if x >= at:
            k = j
    return k


def labels(lst, open_end):
    out = []
    for j, (at, _) in enumerate(lst):
        nx = lst[j + 1][0] if j + 1 < len(lst) else None
        out.append(f"{at}-{nx - 1}" if nx and nx - 1 > at else f"{at}" if nx or not open_end else f"{at}+")
    return out


def match_bowl_bonus(w, B=P["bowl"]):
    bonus = 0
    for at, pts in B["match"]:
        if w >= at:
            bonus = pts
    return bonus


def context(m, team):
    """Context multiplier for team's players in match m (from data/matches.json)."""
    C = P["context"]
    if m is None:
        return 1.0, {}
    res = m["result"]
    if res == "won":
        res = "won" if m["winner"] == team else "lost"
    venue, opp = m["venue"][team], m["strength"][team]
    return C["venue"][venue] * C["opp"][opp] * C["result"][res], {"venue": venue, "opp": opp, "result": res}


_TEAM_MATCHES = None


def compute(slug="india"):
    global _TEAM_MATCHES
    from ratings_engine import compute as team_compute
    data = json.loads((ROOT / "data" / "players" / f"{slug}.json").read_text())
    team = data["team"]
    if _TEAM_MATCHES is None:
        _TEAM_MATCHES, _ = team_compute()
    matches = _TEAM_MATCHES
    by_key = {}
    for m in matches:
        if team in m["teams"]:
            opp = m["teams"][1] if m["teams"][0] == team else m["teams"][0]
            by_key[(m["date"], opp)] = m

    S = {}  # per-player career state
    missing = 0

    def st(pid):
        return S.setdefault(pid, {
            "name": data["names"][pid], "tests": 0, "bi": 0, "no": 0, "runs": 0, "hs": 0,
            "ms": {at: 0 for at, _ in P["bat"]["milestones"]}, "twins": 0, "twin5": 0,
            "wi": 0, "wkts": 0, "best": 0, "hb": [0] * len(P["bowl"]["hauls"]), "mb": [0] * len(P["bowl"]["match"]),
            "fi": 0, "ctwk": 0, "ctfi": 0, "st": 0,
            "bat": 0.0, "bowl": 0.0, "field": 0.0, "first": None, "last": None, "hist": []})

    for t in data["tests"]:
        m = by_key.get((t["date"], t["opp"]))
        if m is None:  # no team result yet: the Test is still in progress
            missing += 1
            continue
        mult, ctx = context(m, team)
        bat, bowl, field = {}, {}, {}
        for pid, inns, runs, notout in t["bat"]:
            bat.setdefault(pid, []).append((runs, notout))
        for pid, inns, w in t["bowl"]:
            bowl.setdefault(pid, []).append(w)
        for pid, inns, ctwk, ctfi, stp in t["field"]:
            field.setdefault(pid, []).append((ctwk, ctfi, stp))
        for pid in t["players"]:
            s = st(pid)
            s["tests"] += 1
            s["first"] = s["first"] or t["date"]
            s["last"] = t["date"]
            # batting
            inns = bat.get(pid, [])
            pts = sum(innings_bat(r) for r, _ in inns)
            hundreds = sum(1 for r, _ in inns if r >= 100)
            if hundreds >= 2:
                pts *= P["bat"]["twin"]
                s["twins"] += 1
            for r, no in inns:
                s["bi"] += 1
                s["no"] += no
                s["runs"] += r
                s["hs"] = max(s["hs"], r)
                top = [at for at, _ in P["bat"]["milestones"] if r >= at]
                if top:
                    s["ms"][top[-1]] += 1
            s["bat"] += pts * mult
            # bowling
            ws = bowl.get(pid, [])
            pts = sum(innings_bowl(w) for w in ws) + match_bowl_bonus(sum(ws))
            if sum(1 for w in ws if w >= P["bowl"]["hauls"][0][0]) >= 2:  # 5+ wickets in each innings
                pts *= P["bowl"]["twin"]
                s["twin5"] += 1
            for w in ws:
                s["wi"] += 1
                s["wkts"] += w
                k = band(w, P["bowl"]["hauls"])
                if k >= 0:
                    s["hb"][k] += 1
            s["best"] = max(s["best"], sum(ws))
            k = band(sum(ws), P["bowl"]["match"])
            if k >= 0:
                s["mb"][k] += 1
            s["bowl"] += pts * mult
            # fielding
            fs = field.get(pid, [])
            F = P["field"]
            pts = sum(a * F["keeperCatch"] + b * F["catch"] + c * F["stumping"] for a, b, c in fs)
            for a, b, c in fs:
                s["fi"] += 1
                s["ctwk"] += a
                s["ctfi"] += b
                s["st"] += c
            s["field"] += pts * mult
            s["hist"].append((t["date"], rating(s)))
        _ = ctx
    return S, missing, len(data["tests"]) - missing


def rating(s):
    return (s["bat"] * longevity(s["bi"]) + s["bowl"] * longevity(s["wi"])
            + s["field"] * longevity(s["fi"]))


def per_innings(s):
    """Points per innings for batting, bowling and fielding, and their sum."""
    pi = [s[k] * longevity(s[n]) / s[n] if s[n] else 0 for k, n in (("bat", "bi"), ("bowl", "wi"), ("field", "fi"))]
    return [round(x, 1) for x in pi + [sum(pi)]]


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    slugs = sorted(f.stem for f in (ROOT / "data" / "players").glob("*.json")) if arg == "all" else [arg]
    top = int(sys.argv[2]) if len(sys.argv) > 2 else (25 if len(slugs) == 1 else 5)
    for slug in slugs:
        report(slug, top)


def report(suffix, top):
    S, missing, n = compute(suffix)
    rows = sorted(S.values(), key=lambda s: -rating(s))
    print(f"{suffix}: {n} Tests, {len(S)} players, {missing} in progress (left out)")
    for i, s in enumerate(rows[:top], 1):
        print(f"{i:>3}. {s['name']:<22} {rating(s):8.0f}  bat {s['bat'] * longevity(s['bi']):7.0f} "
              f"bowl {s['bowl'] * longevity(s['wi']):7.0f} field {s['field'] * longevity(s['fi']):5.0f}  "
              f"T{s['tests']} R{s['runs']} W{s['wkts']}")
    (ROOT / "dist" / "players").mkdir(parents=True, exist_ok=True)
    out = ROOT / "dist" / "players" / f"{suffix}.csv"
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        ms = [at for at, _ in P["bat"]["milestones"]]
        w.writerow(["rank", "player", "first", "last", "tests", "bat_inns", "not_outs", "runs", "highest"]
                   + [f"{a}s" for a in ms] + ["twin_100s", "bowl_inns", "wkts", "best_match"]
                   + [f"{l}wi" for l in labels(P["bowl"]["hauls"], False)]
                   + [f"{l}wm" for l in labels(P["bowl"]["match"], True)] + ["twin_5wi", "field_inns", "ct_wk", "ct_field", "st", "bat_pts", "bowl_pts",
                   "field_pts", "rating", "bat_pts_per_inns", "bowl_pts_per_inns", "field_pts_per_inns",
                   "points_per_innings"])
        for i, s in enumerate(rows, 1):
            w.writerow([i, s["name"], s["first"], s["last"], s["tests"], s["bi"], s["no"], s["runs"], s["hs"]]
                       + [s["ms"][a] for a in ms] + [s["twins"], s["wi"], s["wkts"], s["best"]] + s["hb"] + s["mb"] + [s["twin5"], s["fi"], s["ctwk"], s["ctfi"], s["st"],
                       round(s["bat"] * longevity(s["bi"]), 1), round(s["bowl"] * longevity(s["wi"]), 1),
                       round(s["field"] * longevity(s["fi"]), 1), round(rating(s), 1)] + per_innings(s))
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
