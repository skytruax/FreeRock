"""The page of what is new (tools/now_page.py), written again at every build of a bucket: what came into the player with
the build, what was made again, what waits for the next build, and the demos as they were written."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

CHROME = next(filter(None, (shutil.which(name) for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"))), None)
REPO = Path(__file__).resolve().parents[2]
HOUR = 3600.0
BUILT = 1_800_000_000.0             # when the first build stood


def _tool():
    spec = importlib.util.spec_from_file_location("now_page", REPO / "tools" / "now_page.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stage(var: Path, track: str, title: str, at: float, heard: bool = True) -> None:
    """A staged song (its track.json, made at a time) and, if heard, its whole-track file for listening."""
    style, family, take = track.split("/")
    folder = var / "studio" / style / family / take
    folder.mkdir(parents=True, exist_ok=True)
    meta = {"title": title, "family": family, "take": int(take), "role": "wander", "moods": ["pastoral"], "light": False}
    (folder / "track.json").write_text(json.dumps(meta), encoding="utf-8")
    os.utime(folder / "track.json", (at, at))
    if heard:
        listen = var / "listen" / style
        listen.mkdir(parents=True, exist_ok=True)
        (listen / ("%s - take %s (%s).flac" % (title, take, family))).write_bytes(b"fLaC")


def _build(var: Path, style: str, tracks: list[str], at: float) -> None:
    folder = var / "buckets" / style / "all"
    folder.mkdir(parents=True, exist_ok=True)
    pieces = {"p%d%s" % (n, story): {"track": track, "story": story} for n, track in enumerate(tracks) for story in ("open", "close")}
    (folder / "bucket.json").write_text(json.dumps({"pieces": pieces, "clips": []}), encoding="utf-8")
    os.utime(folder / "bucket.json", (at, at))


def _built(var: Path, style: str, made: dict[str, float]) -> None:
    """A bucket whose pieces say when they were put in (as a real one's do), by song."""
    folder = var / "buckets" / style / "all"
    folder.mkdir(parents=True, exist_ok=True)
    pieces = {"p%d%s" % (n, story): {"track": track, "story": story, "created": at}
              for n, (track, at) in enumerate(made.items()) for story in ("open", "close")}
    (folder / "bucket.json").write_text(json.dumps({"pieces": pieces, "clips": []}), encoding="utf-8")


def _section(page: str, heading: str, until: str) -> str:
    start = page.index(heading)
    return page[start:page.index(until, start)]


def test_a_first_build_shows_the_songs_of_the_day_before_it_and_what_waits(tmp_path):
    now_page = _tool()
    var = tmp_path / "var"
    _stage(var, "knight/old-road-1/1", "Old Road", BUILT - 3 * 24 * HOUR)
    _stage(var, "knight/fresh-gate-1/1", "Fresh Gate", BUILT - 2 * HOUR)
    _stage(var, "knight/later-hill-1/1", "Later Hill", BUILT + HOUR, heard=False)
    _build(var, "knight", ["knight/old-road-1/1", "knight/fresh-gate-1/1"], BUILT)
    (var / "listen" / "now-demos.html").write_text("<h2>A demo written by hand</h2>", encoding="utf-8")

    assert now_page.main(["--var", str(var)]) == 0

    page = (var / "listen" / "now.html").read_text(encoding="utf-8")
    player = _section(page, "<h2>In the player</h2>", "</body>")
    assert "Fresh Gate" in player and "Old Road" not in player          # the day before the build, not older
    assert "src='knight/Fresh%20Gate%20-%20take%201%20%28fresh-gate-1%29.flac'" in player
    waiting = _section(page, "<h2>For the next build</h2>", "<h2>Demos and changes</h2>")
    assert page.index("<h2>For the next build</h2>") < page.index("<h2>Demos and changes</h2>") < page.index("<h2>In the player</h2>")     # what is new first
    assert "Later Hill" in waiting and "its file is being written" in waiting
    assert "1 new, 0 made again" in waiting
    assert "<h2>A demo written by hand</h2>" in page
    state = json.loads((var / "listen" / "now-state.json").read_text(encoding="utf-8"))
    assert state["knight"]["came"] == ["knight/fresh-gate-1/1"] and state["knight"]["since"] is None


def test_a_song_says_who_plays_it(tmp_path):
    """(2026-11-25: the page said where a song is heard, at length, and not whose it is.)"""
    now_page = _tool()
    var = tmp_path / "var"
    for track, about in (("knight/fresh-gate-1/1", {"sounds": "garage", "metre": "3/4", "shape": "riff", "tonic": "D minor"}), ("warcraft/old-hall-1/1", {"sounds": "", "metre": "4/4", "tonic": "E dorian"}),
                         ("house/pit-1/1", {"sounds": "kennel", "meta": {"tonic": "C# phrygian"}})):
        _stage(var, track, track.split("/")[1], BUILT + HOUR)
        (var / "studio" / track / "sheet.json").write_text(json.dumps({"about": about}), encoding="utf-8")
    _stage(var, "knight/no-sheet-1/1", "No Sheet", BUILT + HOUR)
    _build(var, "knight", [], BUILT)
    _build(var, "warcraft", [], BUILT)
    _build(var, "house", [], BUILT)
    path = var / "studio" / "knight" / "fresh-gate-1" / "1" / "track.json"
    path.write_text(json.dumps(dict(json.loads(path.read_text(encoding="utf-8")), moods=list("abcdefghij"))), encoding="utf-8")
    os.utime(path, (BUILT + HOUR, BUILT + HOUR))
    now_page.main(["--var", str(var)])
    page = (var / "listen" / "now.html").read_text(encoding="utf-8")
    assert "by the garage, D minor, in 3/4, a riff song" in page and "by the orchestra, E dorian<" in page and "by the kennel, C# phrygian" in page
    assert "fresh-gate-1, take 1: wander, anywhere" in page and "old-hall-1, take 1: wander, pastoral" in page
    assert now_page.who(var, "knight/no-sheet-1/1", {}) == ""


def test_a_long_list_of_what_came_in_is_closed_and_a_short_one_is_open(tmp_path):
    now_page = _tool()
    var = tmp_path / "var"
    many = ["knight/many-%d/1" % n for n in range(now_page.LONG_LIST + 1)]
    for n, track in enumerate(many):
        _stage(var, track, "Song %d" % n, BUILT - HOUR)
    _build(var, "knight", many, BUILT)
    _stage(var, "house/few-1/1", "Few", BUILT - HOUR)
    _build(var, "house", ["house/few-1/1"], BUILT)
    now_page.main(["--var", str(var)])
    page = (var / "listen" / "now.html").read_text(encoding="utf-8")
    player = _section(page, "<h2>In the player</h2>", "</body>")
    assert "<summary>the %d that came in</summary>" % (now_page.LONG_LIST + 1) in player and "Song 3" in player
    assert "<summary>the 1 that came in</summary>" not in player and "Few" in player


def test_the_next_build_is_read_against_the_one_before_it(tmp_path):
    now_page = _tool()
    var = tmp_path / "var"
    _stage(var, "knight/old-road-1/1", "Old Road", BUILT - 3 * 24 * HOUR)
    _stage(var, "knight/fresh-gate-1/1", "Fresh Gate", BUILT - 2 * HOUR)
    _build(var, "knight", ["knight/old-road-1/1", "knight/fresh-gate-1/1"], BUILT)
    now_page.main(["--var", str(var)])

    # The night after: a new song, and an old one made again; then the bucket is built again.
    _stage(var, "knight/later-hill-1/1", "Later Hill", BUILT + HOUR)
    _stage(var, "knight/old-road-1/1", "Old Road", BUILT + 2 * HOUR)
    _build(var, "knight", ["knight/old-road-1/1", "knight/fresh-gate-1/1", "knight/later-hill-1/1"], BUILT + 3 * HOUR)
    now_page.main(["--var", str(var)])

    state = json.loads((var / "listen" / "now-state.json").read_text(encoding="utf-8"))["knight"]
    assert state["came"] == ["knight/later-hill-1/1"]
    assert state["again"] == ["knight/old-road-1/1"]
    assert state["since"] == BUILT
    page = (var / "listen" / "now.html").read_text(encoding="utf-8")
    player = _section(page, "<h2>In the player</h2>", "</body>")
    assert "1 came in with this build, 1 made again" in player
    assert player.index("Later Hill") < player.index("the 1 made again") < player.index("Old Road")
    assert "Fresh Gate" not in player
    assert "0 new, 0 made again" in _section(page, "<h2>For the next build</h2>", "<h2>Demos and changes</h2>")


def test_the_page_written_twice_on_one_build_keeps_what_came_in_with_it(tmp_path):
    now_page = _tool()
    var = tmp_path / "var"
    _stage(var, "house/ember-01/1", "Low Rafters", BUILT - 3 * 24 * HOUR)
    _build(var, "house", ["house/ember-01/1"], BUILT)
    now_page.main(["--var", str(var)])
    _stage(var, "house/ember-02/1", "Second Hearth", BUILT + HOUR)
    _build(var, "house", ["house/ember-01/1", "house/ember-02/1"], BUILT + 2 * HOUR)
    now_page.main(["--var", str(var)])
    now_page.main(["--var", str(var)])          # nothing built since: the same build, read again

    state = json.loads((var / "listen" / "now-state.json").read_text(encoding="utf-8"))["house"]
    assert state["came"] == ["house/ember-02/1"]
    page = (var / "listen" / "now.html").read_text(encoding="utf-8")
    assert "Second Hearth" in _section(page, "<h2>In the player</h2>", "</body>")
    assert "no bucket" in page                  # the styles with no bucket say so


def test_a_bucket_the_server_writes_again_as_it_plays_is_the_same_build(tmp_path):
    """(2026-11-23: the server keeps what is heard in the bucket's file, and the page took the file's time for the build's: 104 new songs
    stood as none an hour after they came in.)"""
    now_page = _tool()
    var = tmp_path / "var"
    _stage(var, "knight/old-road-1/1", "Old Road", BUILT - 3 * 24 * HOUR)
    _built(var, "knight", {"knight/old-road-1/1": BUILT})
    now_page.main(["--var", str(var)])
    _stage(var, "knight/later-hill-1/1", "Later Hill", BUILT + HOUR)
    _built(var, "knight", {"knight/old-road-1/1": BUILT, "knight/later-hill-1/1": BUILT + 2 * HOUR})
    now_page.main(["--var", str(var)])
    path = var / "buckets" / "knight" / "all" / "bucket.json"
    os.utime(path, (BUILT + 5 * HOUR, BUILT + 5 * HOUR))         # ...the player plays, and the file is written again
    now_page.main(["--var", str(var)])
    state = json.loads((var / "listen" / "now-state.json").read_text(encoding="utf-8"))["knight"]
    assert state["came"] == ["knight/later-hill-1/1"] and state["built"] == BUILT + 2 * HOUR and state["since"] == BUILT

    # A state kept by the old rule (the file's time for the build's) is kept too, until a piece newer than it comes in.
    path = var / "listen" / "now-state.json"
    old = json.loads(path.read_text(encoding="utf-8"))
    old["knight"]["built"] = BUILT + 4 * HOUR
    path.write_text(json.dumps(old), encoding="utf-8")
    now_page.main(["--var", str(var)])
    assert json.loads(path.read_text(encoding="utf-8"))["knight"]["came"] == ["knight/later-hill-1/1"]


def _drawn(page: Path, width: int, tmp_path: Path) -> list[int]:
    """How wide a browser's window of that width draws each play button on the page."""
    looked = page.with_name("looked.html")
    looked.write_text(page.read_text(encoding="utf-8").replace("<details>", "<details open>").replace("</body>", (
        "<pre id='drawn'></pre><script>document.getElementById('drawn').textContent = 'DRAWN ' + "
        "[...document.querySelectorAll('audio')].map(a => Math.round(a.getBoundingClientRect().width)).join(',') + "
        "' WIDER ' + (document.documentElement.scrollWidth > innerWidth) + ' END';</script></body>")), encoding="utf-8")
    out = subprocess.run([CHROME, "--headless=new", "--mute-audio", "--disable-gpu", "--no-first-run", "--user-data-dir=%s" % (tmp_path / "chrome"),
                          "--window-size=%d,900" % width, "--virtual-time-budget=3000", "--dump-dom", "file://%s" % looked],
                         capture_output=True, text=True, timeout=120, check=True).stdout
    found = re.search(r">DRAWN ([0-9,]*) WIDER (true|false) END<", out)
    assert found, "the page was not drawn: %s" % out[-300:]
    assert found[2] == "false", "the page is wider than its window of %d" % width
    return [int(each) for each in found[1].split(",")]


@pytest.mark.skipif(CHROME is None, reason="no Chrome to draw the page with")
@pytest.mark.parametrize("width", [1400, 980, 500])
def test_every_play_button_is_drawn_wide_enough_to_press(tmp_path, width):
    """(2026-11-23: "no play buttons on most": a song for a long list of places left its play button no width, and a demo in
    many versions shrank its own.)"""
    now_page = _tool()
    var = tmp_path / "var"
    for number, title in enumerate(("Warsong Run", "Fresh Gate")):
        track = "knight/long-list-%d/1" % number
        _stage(var, track, title, BUILT - HOUR)
        path = var / "studio" / track / "track.json"
        meta = json.loads(path.read_text(encoding="utf-8"))
        meta["moods"] = ["pastoral", "highland", "haunted", "desert", "jungle", "infernal", "regal", "mystic", "marsh", "coast", "frozen"]
        path.write_text(json.dumps(meta), encoding="utf-8")
        os.utime(path, (BUILT - HOUR, BUILT - HOUR))
    _build(var, "knight", ["knight/long-list-0/1", "knight/long-list-1/1"], BUILT)
    versions = "".join("<td><audio controls preload='none' src='demo/%d.flac'></audio><br><span class='sub'>a version said at some "
                       "length, as they are</span></td>" % n for n in range(6))
    (var / "listen" / "now-demos.html").write_text(
        "<h2>A demo</h2><table><tr><td><b>Night Prowl I, the whole song: everything of House's own, the kick too, and more to say "
        "about it than a cell should have to hold</b></td>%s</tr></table>" % versions, encoding="utf-8")

    now_page.main(["--var", str(var)])

    drawn = _drawn(var / "listen" / "now.html", width, tmp_path)
    assert len(drawn) == 8 and min(drawn) >= 180, drawn
