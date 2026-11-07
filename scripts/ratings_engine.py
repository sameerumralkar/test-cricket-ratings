"""Rating engine shared by the chart scripts: the app's default points system."""
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
matches = json.loads((ROOT / "data" / "matches.json").read_text())
# Team colours, fixed by the user: always use these for every chart and the app.
COLORS = {t: v["hex"] for t, v in json.loads((ROOT / "data" / "team_colors.json").read_text()).items()}

# The official points system (newest file in data/points/), same as the app uses.
from points import latest as _latest  # noqa: E402
POINTS_FILE, CFG = _latest()


def category(m):
    if m["follow_on"] and m["winner"] == m["follow_on"]:
        return "fo"
    g = m["margin"]
    if g.startswith("inns"):
        return "inns"
    x = re.match(r"(\d+) runs?", g)
    if x:
        n = int(x.group(1))
        return "big" if n > 300 else "close" if n < 30 else "other"
    x = re.match(r"(\d+) wickets?", g)
    if x:
        n = int(x.group(1))
        return "big" if n >= 9 else "close" if n <= 2 else "other"
    return "other"


def year(d):
    y, mo, dd = map(int, d.split("-"))
    return y + (date(y, mo, dd).timetuple().tm_yday - 1) / 365.25



def _strength(before, teams, t, band):
    """How the opponent rated against team t going into the match."""
    o = teams[1] if t == teams[0] else teams[0]
    diff = before[o] - before[t]
    return "stronger" if diff > band else "weaker" if diff < -band else "same"


def compute(mode="form", band=None):
    """Return (matches, hist) where hist[team] = [(decimal_year, rating, iso_date), ...].

    mode="form":       the app's rating; recent Tests count most (alpha = 0.06), old ones fade.
    mode="cumulative": every Test since a team's debut counts equally; the rating is the
                       average match score over all its Tests to date, so it never forgets.
    """
    band = (CFG["bandCum"] if mode == "cumulative" else CFG["band"]) if band is None else band
    rating, hist, total, played = {}, {}, {}, {}
    for m in matches:
        teams = m["teams"]
        for t in teams:
            if t not in rating:
                rating[t] = CFG["start"] if t in ("England", "Australia") else CFG["debut"]
                hist[t] = []
                total[t], played[t] = 0.0, 0
        before = {t: rating[t] for t in teams}
        # opponent strength going into the match, kept for the player ratings
        m["strength"] = {t: _strength(before, teams, t, band) for t in teams}
        if m["result"] == "abandoned":
            continue
        for t in teams:
            strength = m["strength"][t]
            venue = m["venue"][t]
            if m["result"] == "won":
                base = CFG["pts"][category(m)][0 if m["winner"] == t else 1]
            elif m["result"] == "drawn":
                base = CFG["draw"][venue]
            else:
                base = CFG["tie"]
            pos = base >= 0
            pts = base * (CFG["vpos"] if pos else CFG["vneg"])[venue] * (CFG["opos"] if pos else CFG["oneg"])[strength]
            score = CFG["start"] + CFG["scale"] * pts
            if mode == "cumulative":
                prior = CFG["start"] if t in ("England", "Australia") else CFG["debut"]
                total[t] += score
                played[t] += 1
                rating[t] = (CFG["cushion"] * prior + total[t]) / (CFG["cushion"] + played[t])
            else:
                rating[t] = before[t] + CFG["alpha"] * (score - before[t])
            hist[t].append((year(m["date"]), rating[t], m["date"]))
    return matches, hist
