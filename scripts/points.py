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
