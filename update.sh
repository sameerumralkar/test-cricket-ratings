#!/bin/sh
# Re-download every Test result, fetch player innings for recent Tests (every team), rebuild the app.
# Run after any new Test finishes; new matches are picked up automatically.
set -e
cd "$(dirname "$0")"
python3 scripts/fetch_results.py
python3 scripts/fetch_players.py          # incremental: the last 60 days before each team's newest Test
python3 scripts/build.py
(cd scripts && python3 player_ratings.py > /dev/null)
