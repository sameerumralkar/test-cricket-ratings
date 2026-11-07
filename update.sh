#!/bin/sh
# Re-download every Test result and Indian player innings from Statsguru and rebuild the app.
# Run after any new Test finishes; new matches are picked up automatically.
set -e
cd "$(dirname "$0")"
python3 scripts/fetch_results.py
python3 scripts/fetch_players.py
python3 scripts/build.py
(cd scripts && python3 player_ratings.py > /dev/null)
