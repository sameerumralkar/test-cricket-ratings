"""The official points system: the newest file in data/points/.

Each saved change is a new file named points-YYYYMMDD-HHMMSS.json (UTC), so the
folder doubles as a history of every change. The site admin creates these from
the app's #admin view; GitHub only lets the repository owner commit them.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POINTS_DIR = ROOT / "data" / "points"

SHAPE = {
    "pts": {k: 2 for k in ("fo", "inns", "big", "close", "other")},
    "draw": ("home", "neutral", "away"), "vpos": ("home", "neutral", "away"), "vneg": ("home", "neutral", "away"),
    "opos": ("stronger", "same", "weaker"), "oneg": ("stronger", "same", "weaker"),
    "tie": None, "band": None, "alpha": None, "scale": None, "start": None, "debut": None,
    "active": None, "bandCum": None, "cushion": None,
}


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def validate(cfg):
    """Raise ValueError if the points file is missing a value or has a bad one."""
    for key, shape in SHAPE.items():
        if key not in cfg:
            raise ValueError(f"missing '{key}'")
        v = cfg[key]
        if shape is None:
            if not _num(v):
                raise ValueError(f"'{key}' must be a number")
        elif isinstance(shape, dict):
            for sub, n in shape.items():
                if not (isinstance(v.get(sub), list) and len(v[sub]) == n and all(map(_num, v[sub]))):
                    raise ValueError(f"'{key}.{sub}' must be [win, loss] numbers")
        else:
            for sub in shape:
                if not _num(v.get(sub)):
                    raise ValueError(f"'{key}.{sub}' must be a number")
    if not 0 < cfg["alpha"] <= 1:
        raise ValueError("'alpha' must be above 0 and at most 1")
    if cfg["cushion"] < 0 or cfg["active"] <= 0:
        raise ValueError("'cushion' must be 0 or more and 'active' above 0")
    return cfg


def latest():
    """Return (filename, config) for the newest points file."""
    files = sorted(POINTS_DIR.glob("points-*.json"))
    if not files:
        raise FileNotFoundError(f"no points-*.json in {POINTS_DIR}")
    f = files[-1]
    try:
        return f.name, validate(json.loads(f.read_text()))
    except (ValueError, json.JSONDecodeError) as e:
        raise SystemExit(f"{f.name} is not a valid points file: {e}")


# ---------- player points: the newest file in data/player_points/ ----------
PLAYER_DIR = ROOT / "data" / "player_points"


def _pairs(v, name, n):
    if not (isinstance(v, list) and len(v) == n and all(isinstance(p, list) and len(p) == 2 and all(map(_num, p)) for p in v)):
        raise ValueError(f"'{name}' must be {n} [at, points] pairs")
    if [p[0] for p in v] != sorted(p[0] for p in v):
        raise ValueError(f"'{name}' thresholds must go up")


def validate_player(cfg):
    """Raise ValueError if the player points file is missing a value or has a bad one."""
    try:
        b, w, f, L, c = cfg["bat"], cfg["bowl"], cfg["field"], cfg["longevity"], cfg["context"]
        nums = [b["run"], b["twin"], w["wkt"], f["keeperCatch"], f["stumping"], f["catch"],
                L["below"], L["first"], L["upto"], L["step"], L["every"]]
        nums += [c["venue"][k] for k in ("home", "neutral", "away")]
        nums += [c["opp"][k] for k in ("stronger", "same", "weaker")]
        nums += [c["result"][k] for k in ("won", "drawn", "tied", "lost", "abandoned")]
    except (KeyError, TypeError) as e:
        raise ValueError(f"missing {e}")
    if not all(map(_num, nums)):
        raise ValueError("every value must be a number")
    _pairs(b["milestones"], "bat.milestones", 8)
    _pairs(w["hauls"], "bowl.hauls", 3)
    _pairs(w["match"], "bowl.match", 4)
    if L["every"] <= 0 or L["upto"] < L["below"]:
        raise ValueError("'longevity.every' must be above 0 and 'upto' at least 'below'")
    return cfg


def latest_player():
    """Return (filename, config) for the newest player points file."""
    files = sorted(PLAYER_DIR.glob("player-points-*.json"))
    if not files:
        raise FileNotFoundError(f"no player-points-*.json in {PLAYER_DIR}")
    f = files[-1]
    try:
        return f.name, validate_player(json.loads(f.read_text()))
    except (ValueError, json.JSONDecodeError) as e:
        raise SystemExit(f"{f.name} is not a valid player points file: {e}")
