#!/usr/bin/env python3
"""Checks the event names and console variables FreeRock uses against the Forever client's lists.

    python3 -I tools/sim/check_names.py FreeRock <folder with events.yaml and cvars.yaml>

The lab's api_lint.py checks function names, and event names where they are written as
RegisterEvent("NAME"). FreeRock registers its events through ns.On("NAME", ...) and through lists
of names, which that check does not see, so this one reads them straight out of the Lua. An event
the client does not have would never fire, and nothing in the game would say so.
Exit status is 1 when a name is missing.
"""
import pathlib
import re
import sys


def top_keys(path: pathlib.Path) -> set[str]:
    return {match.group(1) for match in re.finditer(r"^([A-Za-z_][A-Za-z0-9_.]*):\s*$", path.read_text(encoding="utf-8"), re.M)}


def strip_comments(source: str) -> str:
    return re.sub(r"--[^\n]*", "", source)


def main() -> int:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    addon, lists = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    events = top_keys(lists / "events.yaml")
    cvars = {name.lower() for name in top_keys(lists / "cvars.yaml")}
    used_events: dict[str, str] = {}
    used_cvars: dict[str, str] = {}
    for path in sorted(addon.glob("*.lua")):
        source = strip_comments(path.read_text(encoding="utf-8"))
        # Events are named in two ways: ns.On("NAME", ...) and lists walked with
        # `for _, event in ipairs({ "NAME", ... })`.
        names = re.findall(r'ns\.On\(\s*"([A-Z0-9_]+)"', source)
        for listed in re.findall(r"for _, event in ipairs\(\{(.*?)\}\)", source, re.S):
            names += re.findall(r'"([A-Z0-9_]+)"', listed)
        for name in names:
            used_events.setdefault(name, path.name)
        for name in re.findall(r'"((?:Sound|sound)_[A-Za-z_]+)"', source):
            used_cvars.setdefault(name, path.name)
    missing = [f"event {name} ({where})" for name, where in sorted(used_events.items()) if name not in events]
    missing += [f"console variable {name} ({where})" for name, where in sorted(used_cvars.items()) if name.lower() not in cvars]
    print(f"check_names: {len(used_events)} events and {len(used_cvars)} console variables named in {addon.name}")
    for line in missing:
        print("  NOT IN CLIENT: " + line)
    if not missing:
        print("  all of them are in the Forever client's lists")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
