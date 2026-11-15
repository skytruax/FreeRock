#!/usr/bin/env bash
# Loads FreeRock next to Blizzard's real Forever interface code in the wow-ui-sim simulator, runs
# tools/sim/tests against it, and takes a screenshot. First it checks every game function,
# event and console variable FreeRock names against the Forever client's own lists.
#
#   tools/sim/run.sh                 # about six seconds; logs in tools/sim/out/
#   tools/sim/run.sh --no-screenshot # any option of the lab's run-sim.sh can be passed through
#
# The simulator, its Docker image and the client lists belong to the FreeControl project next to
# this one (../FreeControl/tools/sim/lab); set FREECONTROL_LAB to use a copy somewhere else. Build
# the image once with that folder's build-image.sh. Everything runs in throw-away containers with
# no network. This script only makes a scratch copy of the addon with the test files added, so the
# folder that goes into the game stays free of them.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../.." && pwd)"
lab="${FREECONTROL_LAB:-$root/../FreeControl/tools/sim/lab}"

if [[ ! -x "$lab/run-sim.sh" ]]; then
  echo "tools/sim/run.sh: the simulator lab was not found at $lab" >&2
  echo "  (it is part of FreeControl: tools/sim/lab; set FREECONTROL_LAB to point at it)" >&2
  exit 2
fi

echo "== Names FreeRock uses, against the Forever client's lists =="
python3 -I "$lab/tools/api_lint.py" "$root/FreeRock" --all
python3 -I "$here/check_names.py" "$root/FreeRock" "$lab/dl-wowless-wowf-data"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cp -r "$root/FreeRock" "$work/FreeRock"
cp -r "$here/tests" "$work/FreeRock/tests"

out="${SIM_OUT:-$here/out}"
mkdir -p "$out"
echo "== FreeRock beside Blizzard's interface code =="
"$lab/run-sim.sh" --solo -o "$out" "$@" "$work/FreeRock"

# The screenshot is the addon's strip drawn by the simulator's renderer. Reading it back with the
# app's reader checks the drawing end to end with nothing of ours in between.
if [[ -s "$out/screenshot.png" ]]; then
  echo "== The strip in the simulator's screenshot, read by the app's reader =="
  (cd "$root/app" && uv run --no-sync freerock read "$out/screenshot.png")
fi
