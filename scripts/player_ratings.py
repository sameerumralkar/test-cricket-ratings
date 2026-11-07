#!/usr/bin/env python3
"""Player ratings, computed Test by Test, using the team ratings for match context.

Each Test a player plays earns batting, bowling and fielding points (data/player_points.json).
Those match points are scaled by the match context taken from the team ratings: where the
Test was played, the result for the player's team, and whether the opponent was stronger,
the same or weaker going into the match. A player's rating after any Test is

    batting total x batting longevity + bowling total x bowling longevity
    + fielding total x fielding longevity

where each longevity multiplier depends on that discipline's innings count so far.

Usage:  python3 scripts/player_ratings.py [india]   -> prints the top 25, writes dist/players_<team>.csv
"""
import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = json.loads((ROOT / "data" / "player_points.json").read_text())
TEAM_NAME = {"india": "India"}


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


def compute(suffix="india"):
    from ratings_engine import compute as team_compute
    team = TEAM_NAME[suffix]
    data = json.loads((ROOT / "data" / f"players_{suffix}.json").read_text())
    matches, _ = team_compute()
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
            "ms": {at: 0 for at, _ in P["bat"]["milestones"]}, "twins": 0,
            "wi": 0, "wkts": 0, "best": 0, "w5": 0, "w8": 0, "w10i": 0, "w10m": 0,
            "fi": 0, "ctwk": 0, "ctfi": 0, "st": 0,
            "bat": 0.0, "bowl": 0.0, "field": 0.0, "first": None, "last": None, "hist": []})

    for t in data["tests"]:
        m = by_key.get((t["date"], t["opp"]))
        missing += m is None
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
            for w in ws:
                s["wi"] += 1
                s["wkts"] += w
                s["w5"] += 5 <= w < 8
                s["w8"] += 8 <= w < 10
                s["w10i"] += w >= 10
            s["best"] = max(s["best"], sum(ws))
            s["w10m"] += sum(ws) >= 10
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
    return S, missing, len(data["tests"])


def rating(s):
    return (s["bat"] * longevity(s["bi"]) + s["bowl"] * longevity(s["wi"])
            + s["field"] * longevity(s["fi"]))


def main():
    suffix = sys.argv[1] if len(sys.argv) > 1 else "india"
    S, missing, n = compute(suffix)
    rows = sorted(S.values(), key=lambda s: -rating(s))
    print(f"{n} Tests, {len(S)} players, {missing} Tests not matched to team results")
    for i, s in enumerate(rows[:25], 1):
        print(f"{i:>3}. {s['name']:<22} {rating(s):8.0f}  bat {s['bat'] * longevity(s['bi']):7.0f} "
              f"bowl {s['bowl'] * longevity(s['wi']):7.0f} field {s['field'] * longevity(s['fi']):5.0f}  "
              f"T{s['tests']} R{s['runs']} W{s['wkts']}")
    out = ROOT / "dist" / f"players_{suffix}.csv"
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        ms = [at for at, _ in P["bat"]["milestones"]]
        w.writerow(["rank", "player", "first", "last", "tests", "bat_inns", "not_outs", "runs", "highest"]
                   + [f"{a}s" for a in ms] + ["twin_100s", "bowl_inns", "wkts", "best_match", "5wi", "8wi",
                   "10wi", "10wm", "field_inns", "ct_wk", "ct_field", "st", "bat_pts", "bowl_pts",
                   "field_pts", "rating"])
        for i, s in enumerate(rows, 1):
            w.writerow([i, s["name"], s["first"], s["last"], s["tests"], s["bi"], s["no"], s["runs"], s["hs"]]
                       + [s["ms"][a] for a in ms] + [s["twins"], s["wi"], s["wkts"], s["best"], s["w5"],
                       s["w8"], s["w10i"], s["w10m"], s["fi"], s["ctwk"], s["ctfi"], s["st"],
                       round(s["bat"] * longevity(s["bi"]), 1), round(s["bowl"] * longevity(s["wi"]), 1),
                       round(s["field"] * longevity(s["fi"]), 1), round(rating(s), 1)])
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
