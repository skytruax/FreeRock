"""A pretend evening, played through the real server and the real player page with no game.

    cd app && uv run --no-sync python ../tools/soak.py [style ...]

The server has to be running (freerock serve). For each style named (all three if none is), a
browser nobody sees opens the player page, and the game is pretended through a walk, a fight,
the calm after it, a border crossed into another kind of place, an inn, a boss, and a desert at
night. Every second the page says what it is playing; what changed is printed with the time,
and at the end how many parts came in late and anything the page or the server complained of.
Nothing is heard: this checks that the right music is chosen and that it plays without a hitch.
"""
from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile

import aiohttp

BASE = "http://127.0.0.1:8765"
CHROME = next((path for path in (shutil.which(name) for name in
                                 ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")) if path), None)
WALK = dict(speed=7.0, daytime=True)
EVENING = [
    (0, "a walk in Duskwood", dict(zone_name="Duskwood", **WALK)),
    (50, "a fight with two enemies", dict(zone_name="Duskwood", in_combat=True, has_target=True, target_hostile=True,
                                          enemies=2, fighting=2, daytime=True)),
    (75, "the fight is over", dict(zone_name="Duskwood", **WALK)),
    (120, "across the border into Elwynn Forest", dict(zone_name="Elwynn Forest", **WALK)),
    (170, "into an inn", dict(zone_name="Elwynn Forest", subzone_name="Lion's Pride Inn", has_subzone=True, resting=True,
                             indoors=True, daytime=True)),
    (205, "a boss", dict(zone_name="Elwynn Forest", in_combat=True, encounter=True, boss_present=True, has_target=True,
                         target_class="worldboss", target_hostile=True, daytime=True)),
    (235, "Tanaris at night", dict(zone_name="Tanaris", speed=7.0, daytime=False)),
    (280, "a cave", dict(zone_name="Tanaris", subzone_name="Gaping Chasm", has_subzone=True, indoors=True, speed=3.0, daytime=False)),
    (315, "the end", None),
]


async def evening(http: aiohttp.ClientSession, style: str) -> dict:
    async def post(path: str, body: dict) -> None:
        async with http.post(BASE + path, json=body) as response:
            text = await response.text()
            if response.status != 200:
                raise RuntimeError("%s said %d: %s" % (path, response.status, text))

    async def music() -> dict:
        async with http.get(BASE + "/api/music") as response:
            return await response.json()

    await post("/api/style", {"genre": style})
    await post("/api/pretend", EVENING[0][2])
    profile = tempfile.mkdtemp(prefix="freerock-soak-")
    chrome = await asyncio.create_subprocess_exec(
        CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--user-data-dir=" + profile,
        "--autoplay-policy=no-user-gesture-required", BASE + "/player",
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    heard, late, steps, said, silent = [], 0, list(EVENING), None, 0
    try:
        began = asyncio.get_running_loop().time()
        while steps:
            now = asyncio.get_running_loop().time() - began
            if now >= steps[0][0]:
                _, what, state = steps.pop(0)
                print("  %5.0f s  THE GAME: %s" % (now, what), flush=True)
                if state is None:
                    break
                await post("/api/pretend", state)
            status = await music()
            player = next((each for each in status["players"] if each.get("forever")), None)
            if player is not None:
                late = max(late, player.get("late", 0))
                piece = player.get("piece")
                playing = "+".join(sorted(player.get("playing", {})))
                line = ("%s [%s%s] with %s" % (piece["title"], piece.get("role"), "" if not piece.get("story") else ", " + piece["story"],
                                               playing or "nothing")
                        if piece else ("a moment of silence" if player.get("resting") else "loose phrases: %s" % (playing or "nothing")))
                if not playing and not player.get("resting"):
                    silent += 1
                if line != said:
                    said = line
                    kinds = (status.get("forever") or {}).get("kinds")
                    print("  %5.0f s  %s   (place: %s%s)" % (now, line, ", ".join(kinds or []) or "?",
                                                           ", light" if (status.get("forever") or {}).get("light") else ""), flush=True)
                    heard.append(line)
            await asyncio.sleep(1.0)
        status = await music()
    finally:
        chrome.terminate()
        await chrome.wait()
        shutil.rmtree(profile, ignore_errors=True)
    problems = [note for note in status["notes"] if "problem" in note.lower() or "could not" in note.lower()]
    return {"style": style, "changes": len(heard), "late": late, "seconds_with_nothing": silent, "problems": problems}


async def main(styles: list[str]) -> int:
    if CHROME is None:
        raise SystemExit("Chrome is not installed on this machine.")
    results = []
    async with aiohttp.ClientSession() as http:
        for style in styles:
            print("=== %s ===" % style, flush=True)
            results.append(await evening(http, style))
    bad = 0
    for result in results:
        print("%(style)s: %(changes)d changes of music, %(late)d parts late, %(seconds_with_nothing)d s with nothing playing, "
              "problems: %(problems)s" % result)
        bad += bool(result["problems"]) or result["late"] > 2
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:] or ["knight", "warcraft", "house"])))
