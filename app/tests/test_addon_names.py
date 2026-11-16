"""Every game function, event and console variable the addon names exists in the Forever client.

The client's own lists live in the FreeControl project next to this one (its simulator lab). A
name the client does not have is nil in the game: a function call would be an error and an event
would simply never fire, and nothing in these tests' stand-in client would notice. When the lists
are not on this machine the checks are skipped, and say so.
"""
import importlib.util
import subprocess
import sys

import pytest

from link_helpers import CLIENT_LISTS, REPO

LAB = CLIENT_LISTS.parent
needs_lists = pytest.mark.skipif(not (CLIENT_LISTS / "events.yaml").is_file(),
                                 reason=f"the Forever client lists are not at {CLIENT_LISTS}")


@needs_lists
def test_every_event_and_console_variable_is_in_the_client(capsys):
    spec = importlib.util.spec_from_file_location("check_names", REPO / "tools" / "sim" / "check_names.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys_argv = sys.argv
    sys.argv = ["check_names.py", str(REPO / "FreeRock"), str(CLIENT_LISTS)]
    try:
        status = module.main()
    finally:
        sys.argv = sys_argv
    out = capsys.readouterr().out
    assert status == 0, out
    assert "40 events and 1 console variables" in out, "the check found the registrations it is meant to read"


@needs_lists
def test_every_game_function_is_in_the_client():
    result = subprocess.run([sys.executable, "-I", str(LAB / "tools" / "api_lint.py"), str(REPO / "FreeRock"), "--all"],
                            capture_output=True, text=True, check=True)
    assert "NOT IN CLIENT" not in result.stdout, result.stdout
    assert "SIM ONLY" not in result.stdout, result.stdout
    assert "5 Lua file(s)" in result.stdout


def test_the_addon_never_names_a_sealed_function():
    """Health, threat and other units' identity are sealed by the game. FreeRock must not ask."""
    sealed = ["UnitHealth", "UnitHealthMax", "UnitHealthPercent", "UnitPower", "UnitThreatSituation",
              "UnitDetailedThreatSituation", "UnitName", "UnitGUID", "UnitAura", "C_UnitAuras",
              "CombatLogGetCurrentEventInfo", "COMBAT_LOG_EVENT_UNFILTERED", "UNIT_HEALTH", "UNIT_AURA", "UNIT_SPELLCAST"]
    for path in sorted((REPO / "FreeRock").glob("*.lua")):
        source = path.read_text(encoding="utf-8")
        for name in sealed:
            assert name not in source, f"{path.name} mentions {name}"


def test_the_toc_lists_every_lua_file_and_nothing_else():
    toc = (REPO / "FreeRock" / "FreeRock.toc").read_text(encoding="utf-8").splitlines()
    listed = [line.strip() for line in toc if line.strip() and not line.startswith("#")]
    on_disk = sorted(path.name for path in (REPO / "FreeRock").glob("*.lua"))
    assert sorted(listed) == on_disk
    assert listed[0] == "Core.lua" and listed[-1] == "Options.lua"
    assert "## Interface: 16001" in toc and "## SavedVariables: FreeRockDB" in toc and "## Author: Sky Truax" in toc
