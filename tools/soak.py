"""A pretend evening, played through the real server and the real player page with no game.

    cd app && uv run --no-sync python ../tools/soak.py [style ...]
    cd app && uv run --no-sync python ../tools/soak.py --minutes 10 [--seed 7] [style ...]

The server has to be running (freerock serve). For each style named (all three if none is), a
browser nobody sees opens the player page, and the game is pretended through a walk, a fight,
the calm after it, a border crossed into another kind of place, an inn, a boss, and a desert at
night. Every second the page says what it is playing; what changed is printed with the time,
and at the end how many parts came in late and anything the page or the server complained of.
Nothing is heard: this checks that the right music is chosen and that it plays without a hitch.

With --minutes the evening is made up instead: so many minutes of walking, riding, fights of
all sizes, borders, inns, caves, nightfall, rain and deaths, in an order drawn from --seed.
"""
from __future__ import annotations

import asyncio
import random
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


ZONES = ("Duskwood", "Elwynn Forest", "Tanaris", "Dun Morogh", "Stranglethorn Vale", "Searing Gorge", "Stormwind City",
         "Teldrassil", "Westfall", "Mulgore", "Eastern Plaguelands", "Winterspring")


def made_up(minutes: float, seed: int) -> list:
    """A long evening drawn from a seed: mostly walking, with everything else that can happen."""
    rng = random.Random(seed)
    zone, night, at, steps = rng.choice(ZONES), False, 0.0, []
    def say(what: str, **state) -> None:
        steps.append((at, what, dict(zone_name=zone, daytime=not night, **state)))
    say("a walk in %s" % zone, speed=7.0)
    while at < minutes * 60.0:
        at += rng.uniform(8.0, 45.0)
        kind = rng.choices(("fight", "big fight", "boss", "border", "inn", "cave", "night", "rain", "death", "ride", "stand"),
                           (30, 8, 3, 12, 6, 6, 4, 5, 2, 6, 6))[0]
        if kind == "fight":
            enemies = rng.randint(1, 2)
            say("a fight with %d" % enemies, in_combat=True, has_target=True, target_hostile=True, enemies=enemies, fighting=enemies)
            at += rng.uniform(6.0, 30.0)
            say("the fight is over", speed=7.0)
        elif kind == "big fight":
            say("a fight with five", in_combat=True, has_target=True, target_hostile=True, target_class="elite", enemies=5, fighting=5)
            at += rng.uniform(15.0, 50.0)
            say("the fight is over", speed=7.0)
        elif kind == "boss":
            say("a boss", in_combat=True, encounter=True, boss_present=True, has_target=True, target_class="worldboss", target_hostile=True)
            at += rng.uniform(30.0, 80.0)
            say("the boss is down", speed=7.0)
        elif kind == "border":
            zone = rng.choice([name for name in ZONES if name != zone])
            say("across the border into %s" % zone, speed=7.0)
        elif kind == "inn":
            say("into an inn", subzone_name="The Inn", has_subzone=True, resting=True, indoors=True)
            at += rng.uniform(15.0, 40.0)
            say("out of the inn", speed=7.0)
        elif kind == "cave":
            say("into a cave", subzone_name="Dark Cavern", has_subzone=True, indoors=True, speed=3.0)
            at += rng.uniform(20.0, 60.0)
            say("out of the cave", speed=7.0)
        elif kind == "night":
            night = not night
            say("night falls" if night else "day breaks", speed=7.0)
        elif kind == "rain":
            say("a rain storm", speed=7.0, weather="rain", weather_intensity=0.9)
            at += rng.uniform(20.0, 50.0)
            say("the rain stops", speed=7.0)
        elif kind == "death":
            say("dead", dead=True)
            at += rng.uniform(5.0, 12.0)
            say("a ghost", ghost=True, speed=7.0)
            at += rng.uniform(8.0, 20.0)
            say("alive again", speed=7.0)
        elif kind == "ride":
            say("riding", mounted=True, speed=14.0)
        else:
            say("standing still", speed=0.0)
    steps.append((at, "the end", None))
    return steps


async def evening(http: aiohttp.ClientSession, style: str, script: list | None = None) -> dict:
    async def post(path: str, body: dict) -> None:
        async with http.post(BASE + path, json=body) as response:
            text = await response.text()
            if response.status != 200:
                raise RuntimeError("%s said %d: %s" % (path, response.status, text))

    async def music() -> dict:
        async with http.get(BASE + "/api/music") as response:
            return await response.json()

    script = script or EVENING
    await post("/api/style", {"genre": style})
    await post("/api/pretend", script[0][2])
    profile = tempfile.mkdtemp(prefix="freerock-soak-")
    chrome = await asyncio.create_subprocess_exec(
        CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--user-data-dir=" + profile,
        "--autoplay-policy=no-user-gesture-required", BASE + "/player",
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    heard, late, steps, said, silent = [], 0, list(script), None, 0
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
                if player.get("late", 0) > late:
                    print("  %5.0f s  (a part came in late: %d so far)" % (now, player["late"]), flush=True)
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


async def main(styles: list[str], minutes: float = 0.0, seed: int = 1) -> int:
    if CHROME is None:
        raise SystemExit("Chrome is not installed on this machine.")
    results = []
    async with aiohttp.ClientSession() as http:
        for number, style in enumerate(styles):
            print("=== %s ===" % style, flush=True)
            results.append(await evening(http, style, made_up(minutes, seed + number) if minutes else None))
    bad = 0
    for result in results:
        print("%(style)s: %(changes)d changes of music, %(late)d parts late, %(seconds_with_nothing)d s with nothing playing, "
              "problems: %(problems)s" % result)
        bad += bool(result["problems"]) or result["late"] > 2
    return 1 if bad else 0


if __name__ == "__main__":
    words, minutes, seed = sys.argv[1:], 0.0, 1
    for name in ("--minutes", "--seed"):
        if name in words:
            where = words.index(name)
            value = words[where + 1]
            del words[where:where + 2]
            if name == "--minutes":
                minutes = float(value)
            else:
                seed = int(value)
    sys.exit(asyncio.run(main(words or ["knight", "warcraft", "house"], minutes, seed)))
