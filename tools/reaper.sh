#!/usr/bin/env bash
# Opens REAPER's window on this machine, with the studio's own settings, plug-ins and sounds.
#
#   tools/reaper.sh                                  REAPER by itself
#   tools/reaper.sh warcraft/haunted-requiem-1/1     the project of that track (style/family/take)
#   tools/reaper.sh /some/where/project.rpp          any project file
#
# This is the same REAPER the studio renders with (unpacked under var/tools/reaper, keeping its
# settings beside itself). Every track the studio writes has a project under
# var/reaper/projects/<style>/<family>/<take>/track.rpp: each instrument line is a track, in a
# folder for each of the player's channels, with a hall at the bottom of each folder.
#
# The first time, REAPER has no sound device: Options > Preferences > Audio > Device, choose
# PulseAudio (or ALSA), and it will play through the laptop's speakers or headphones.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
home="$here/var/tools/reaper/reaper_linux_x86_64/REAPER"
xdg="$here/var/tools/xdg"
if [ ! -x "$home/reaper" ]; then
  echo "REAPER is not unpacked at $home (see tools/stems/README.md)" >&2
  exit 1
fi
args=()
if [ $# -gt 0 ]; then
  if [ -f "$1" ]; then
    args=("$1")
  elif [ -f "$here/var/reaper/projects/$1/track.rpp" ]; then
    args=("$here/var/reaper/projects/$1/track.rpp")
  else
    echo "No project at $1 or at $here/var/reaper/projects/$1/track.rpp" >&2
    exit 1
  fi
fi
mkdir -p "$xdg/data" "$xdg/config" "$xdg/cache" "$xdg/documents"
# Tell REAPER where the plug-ins are (the studio's own and whatever has been installed since).
(cd "$here/app" && uv run --no-sync python -c "from freerock.studio import reaper; reaper.configure()")
exec env XDG_DATA_HOME="$xdg/data" XDG_CONFIG_HOME="$xdg/config" XDG_CACHE_HOME="$xdg/cache" XDG_DOCUMENTS_DIR="$xdg/documents" \
  "$home/reaper" "${args[@]}"
