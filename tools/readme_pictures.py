"""The README's pictures, drawn from the project itself: a real track's stems, the real director
and mixing desk, the real strip encoder. Nothing is mocked up.

    cd app && uv run --no-sync --with matplotlib --with pillow python ../tools/readme_pictures.py [name ...]

Writes docs/images/<name>.png (and demo.gif). Names: banner, story, signals, demo, strip, flow, ear,
cave, water, places. The cave, water and places pictures put a real track's sound at its summit
through the player's own filters (forever.js) with the director's real numbers for each place.
The title font is FreeControl's (LifeCraft, fetched there into tools/.font-cache, never committed);
the text font is Inter. Pages that need other programs (the engraved score, the mixer page) are
made by their own tools and kept beside these: score_view.py and a headless browser.
"""
from __future__ import annotations

import dataclasses
import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from freerock import beacon, forever, studio
from freerock.director import Director
from freerock.state import GameState
from freerock.studio import ear

ROOT = Path(__file__).resolve().parents[1]
VAR = ROOT / "var"
OUT = ROOT / "docs" / "images"
TITLE_FONT = ROOT.parent / "FreeControl" / "tools" / ".font-cache" / "LifeCraft_Font.ttf"
INTER = Path.home() / ".local" / "share" / "fonts" / "Inter"
# The five channels, each with a colour of its own in every picture.
CHANNELS = ("texture", "lead", "rhythm", "drums", "bass")
COLOURS = {"texture": (72, 199, 190), "lead": (246, 201, 84), "rhythm": (240, 132, 62), "drums": (232, 72, 92), "bass": (150, 110, 240)}
NAMES = {"texture": "pads and drones", "lead": "the tune", "rhythm": "accompaniment", "drums": "the beat", "bass": "the low line"}
NIGHT = ((9, 18, 44), (33, 20, 64))         # the sky at the top and at the bottom
BANNER_TRACK = ("warcraft", "mystic-twilight-forest-1/1")


def named(meta: dict) -> str:
    """A track's title without the numeral of its take, where it has one."""
    words = meta["title"].split()
    return " ".join(words[:-1]) if len(words) > 1 and set(words[-1]) <= set("IVX") else meta["title"]


def font(size: int, weight: str = "Bold") -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(INTER / ("Inter-%s.ttf" % weight)), size)


def title_font(size: int) -> ImageFont.FreeTypeFont:
    if not TITLE_FONT.is_file():
        raise FileNotFoundError("The title font is fetched by FreeControl's tools/make_listing.py into %s" % TITLE_FONT.parent)
    return ImageFont.truetype(str(TITLE_FONT), size)


def sky(width: int, height: int, seed: int = 7) -> Image.Image:
    """A night sky: a gradient, stars, and a range of hills along the bottom."""
    top, bottom = np.array(NIGHT[0], float), np.array(NIGHT[1], float)
    rows = np.linspace(0.0, 1.0, height)[:, None]
    gradient = (top * (1 - rows) + bottom * rows).astype(np.uint8)
    image = Image.fromarray(np.repeat(gradient[:, None, :], width, axis=1).reshape(height, width, 3), "RGB")
    draw = ImageDraw.Draw(image)
    rng = random.Random(seed)
    for _ in range(width * height // 2600):
        x, y, bright = rng.randrange(width), rng.randrange(int(height * 0.75)), rng.randrange(120, 255)
        size = 1 if rng.random() < 0.85 else 2
        draw.ellipse((x, y, x + size, y + size), fill=(bright, bright, min(255, bright + 20)))
    for layer, (shade, rise) in enumerate((((26, 22, 58), 0.80), ((16, 14, 38), 0.88))):
        points, x = [(0, height)], 0
        while x <= width:
            points.append((x, int(height * rise - 40 * math.sin(x / (170 + 60 * layer) + layer) - rng.randrange(0, 30))))
            x += rng.randrange(40, 90)
        points += [(width, height)]
        draw.polygon(points, fill=shade)
    return image


def envelopes(style: str, name: str, points: int) -> tuple[dict, dict[str, np.ndarray]]:
    """A staged track's channels as loudness envelopes (0 to 1, one value for each of `points`
    stretches of the track), and what the track says of itself."""
    meta, parts = studio.read_track(VAR / "studio" / style / name)
    length = min(len(audio) for audio in parts.values())
    out = {}
    for channel in CHANNELS:
        audio = parts.get(channel)
        if audio is None:
            out[channel] = np.zeros(points)
            continue
        mono = audio[:length].mean(axis=1)
        step = length // points
        rms = np.sqrt(np.mean(mono[: step * points].reshape(points, step) ** 2, axis=1) + 1e-12)
        decibels = 20 * np.log10(rms)
        out[channel] = np.clip((decibels + 60.0) / 50.0, 0.0, 1.0)          # -60 dB to -10 dB as 0 to 1
    return meta, out


def banner() -> None:
    width, height = 1600, 600
    image = sky(width, height).convert("RGBA")
    meta, levels = envelopes(*BANNER_TRACK, points=400)
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    middle, span = int(height * 0.64), 100
    xs = np.linspace(40, width - 40, len(levels["texture"]))
    stacked = np.zeros_like(xs)
    for channel in CHANNELS:
        smooth = np.convolve(levels[channel], np.ones(5) / 5, mode="same")
        upper = middle - (stacked + smooth) * span / 2.2
        lower = middle + (stacked + smooth) * span / 2.2
        inner_up = middle - stacked * span / 2.2
        inner_down = middle + stacked * span / 2.2
        colour = COLOURS[channel]
        draw.polygon(list(zip(xs, upper)) + list(zip(xs[::-1], inner_up[::-1])), fill=colour + (150,))
        draw.polygon(list(zip(xs, inner_down)) + list(zip(xs[::-1], lower[::-1])), fill=colour + (150,))
        stacked = stacked + smooth
    glow = layer.filter(ImageFilter.GaussianBlur(10))
    image = Image.alpha_composite(image, glow)
    image = Image.alpha_composite(image, layer)
    draw = ImageDraw.Draw(image)
    title = title_font(150)
    words = "FreeRock"
    box = draw.textbbox((0, 0), words, font=title)
    x, y = (width - (box[2] - box[0])) // 2, 18
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((x + 4, y + 6), words, font=title, fill=(0, 0, 0, 200))
    image = Image.alpha_composite(image, shadow.filter(ImageFilter.GaussianBlur(6)))
    # Gold, lighter at the top, as FreeControl's title.
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).text((x, y), words, font=title, fill=255)
    gold = Image.new("RGBA", image.size)
    top, bottom = np.array((255, 240, 190)), np.array((214, 150, 52))
    rows = np.clip((np.arange(height) - y - 20) / 140.0, 0, 1)[:, None]
    gold_rows = (top * (1 - rows) + bottom * rows).astype(np.uint8)
    gold.paste(Image.fromarray(np.repeat(gold_rows[:, None, :], width, axis=1), "RGB"))
    gold.putalpha(mask)
    outline = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(outline).text((x, y), words, font=title, fill=(70, 38, 10, 255), stroke_width=5, stroke_fill=(70, 38, 10, 255))
    image = Image.alpha_composite(image, outline)
    image = Image.alpha_composite(image, gold)
    draw = ImageDraw.Draw(image)
    line = "Music that plays your game."
    tagline = font(40, "Bold")
    box = draw.textbbox((0, 0), line, font=tagline)
    draw.text(((width - (box[2] - box[0])) // 2, 196), line, font=tagline, fill=(240, 240, 250))
    caption = "The five stems of “%s”, a Warcraft piece, across its %d minutes: pads, tune, accompaniment, drums, bass." % (
        named(meta), round(sum(s["bars"] for s in meta["sections"]) * meta["bar_frames"] / studio.RATE / 60))
    small = font(18, "Medium")
    box = draw.textbbox((0, 0), caption, font=small)
    draw.text(((width - (box[2] - box[0])) // 2, height - 34), caption, font=small, fill=(200, 200, 220))
    image.convert("RGB").save(OUT / "banner.png", optimize=True)


def story() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    meta, levels = envelopes(*BANNER_TRACK, points=600)
    seconds = sum(s["bars"] for s in meta["sections"]) * meta["bar_frames"] / studio.RATE
    xs = np.linspace(0, seconds / 60, len(levels["texture"]))
    plt.style.use("dark_background")
    figure, axis = plt.subplots(figsize=(14, 5.2), dpi=110)
    figure.patch.set_facecolor("#0d1530")
    axis.set_facecolor("#0d1530")
    smooth = {channel: np.convolve(levels[channel], np.ones(9) / 9, mode="same") for channel in CHANNELS}
    axis.stackplot(xs, [smooth[c] for c in CHANNELS], colors=["#%02x%02x%02x" % COLOURS[c] for c in CHANNELS], alpha=0.85,
                   labels=["%s (%s)" % (c, NAMES[c]) for c in CHANNELS])
    edge, labels = 0.0, {"open": "opening", "theme": "theme", "rise": "rise", "moment": "moment", "close": "close"}
    words = ("open", "first theme", "second theme", "build", "arrival", "valley", "climb", "summit", "close")
    for index, section in enumerate(meta["sections"]):
        long = section["bars"] * meta["bar_frames"] / studio.RATE / 60
        if index:
            axis.axvline(edge, color="white", alpha=0.25, lw=1)
        axis.text(edge + long / 2, 4.75, words[index] if len(meta["sections"]) == 9 else labels[section["story"]], ha="center",
                  va="top", fontsize=10, color="#e8e8f0")
        edge += long
    axis.set_xlim(0, xs[-1])
    axis.set_ylim(0, 4.9)
    axis.set_yticks([])
    axis.set_xlabel("minutes", color="#c8c8d8")
    axis.set_title("“%s”: one track's story, every channel's loudness as it goes" % named(meta),
                   color="white", fontsize=14, pad=12)
    axis.legend(loc="upper left", bbox_to_anchor=(0.0, -0.13), ncol=5, frameon=False, fontsize=10)
    for side in ("top", "right", "left"):
        axis.spines[side].set_visible(False)
    figure.tight_layout()
    figure.savefig(OUT / "story.png", facecolor=figure.get_facecolor())


# --- what the game does to the channels: the real director and desk -------------------------------
SITUATIONS = (
    ("standing still", {}, 6),
    ("standing a while", {}, 20),
    ("walking", {"speed": 7.0}, 25),
    ("riding", {"speed": 14.0, "mounted": True}, 30),
    ("a foe in your sights", {"has_target": True, "target_hostile": True, "target_class": "normal"}, 4),
    ("a fight", {"in_combat": True, "has_target": True, "target_hostile": True, "target_class": "normal"}, 6),
    ("a fight with an elite", {"in_combat": True, "has_target": True, "target_hostile": True, "target_class": "elite"}, 6),
    ("a dungeon boss", {"in_combat": True, "encounter": True, "in_instance": True, "instance_kind": "party"}, 6),
    ("in a cave", {"indoors": True}, 6),
    ("in an inn", {"indoors": True, "resting": True}, 6),
    ("walking at night", {"speed": 7.0, "daytime": False}, 25),
    ("camping", {}, 50),
    ("in stealth", {"stealthed": True, "speed": 3.0}, 6),
    ("dead", {"dead": True}, 6),
)


def situation(changes: dict, seconds: float):
    """The director's target and the desk's mix after `seconds` of a situation."""
    director = Director()
    state = dataclasses.replace(GameState(daytime=True, speed=0.0), **changes)
    target = None
    for tick in range(int(seconds / 0.25) + 1):
        target = director.update(state, tick * 0.25)
    return target, forever.mix(target)


def signals() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    rows, notes = [], []
    for name, changes, seconds in SITUATIONS:
        target, mix = situation(changes, seconds)
        rows.append([mix[channel]["level"] for channel in CHANNELS])
        tone = []
        if target.lowpass_hz < 19000:
            tone.append("low-pass %.1f kHz" % (target.lowpass_hz / 1000))
        if target.highpass_hz > 40:
            tone.append("high-pass %d Hz" % target.highpass_hz)
        if target.reverb > 0.05:
            tone.append("reverb %.2f" % target.reverb)
        if target.volume < 0.99:
            tone.append("%+.0f dB" % (20 * math.log10(max(target.volume, 1e-6))))
        notes.append("%s%s" % (target.place, ("  ·  " + ", ".join(tone)) if tone else ""))
    data = np.array(rows)
    plt.style.use("dark_background")
    figure, axis = plt.subplots(figsize=(13, 7.4), dpi=110)
    figure.patch.set_facecolor("#0d1530")
    axis.set_facecolor("#0d1530")
    cmap = LinearSegmentedColormap.from_list("rock", ["#141a35", "#2e3a7a", "#7a4fd0", "#e2577a", "#f6c954"])
    axis.imshow(data, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for row in range(data.shape[0]):
        for column in range(data.shape[1]):
            value = data[row, column]
            axis.text(column, row, "%.2f" % value if value else "–", ha="center", va="center",
                      color="#0d1530" if value > 0.6 else "#e8e8f0", fontsize=11, fontweight="bold")
        axis.text(len(CHANNELS) - 0.4, row, notes[row], va="center", ha="left", fontsize=10, color="#c8c8e0")
    axis.set_xticks(range(len(CHANNELS)))
    axis.set_xticklabels(["%s\n%s" % (c, NAMES[c]) for c in CHANNELS], fontsize=11)
    axis.xaxis.tick_top()
    axis.set_yticks(range(len(SITUATIONS)))
    axis.set_yticklabels([name for name, _, _ in SITUATIONS], fontsize=11)
    axis.set_xlim(-0.5, len(CHANNELS) + 2.6)
    axis.set_title("What the game does to each channel (the director and the mixing desk, run for real)", color="white",
                   fontsize=13, pad=44)
    for side in axis.spines.values():
        side.set_visible(False)
    axis.tick_params(length=0)
    figure.tight_layout()
    figure.savefig(OUT / "signals.png", facecolor=figure.get_facecolor())


# --- an evening in the game, as the five channels hear it -------------------------------------------
SESSION = (
    (0, "standing in Elwynn Forest", {}),
    (6, "walking down the road", {"speed": 7.0}),
    (26, "a wolf in your sights", {"has_target": True, "target_hostile": True, "target_class": "normal"}),
    (29, "the fight", {"in_combat": True}),
    (41, "the fight is won", {"in_combat": False, "has_target": False, "target_hostile": False}),
    (52, "into a mine", {"indoors": True, "speed": 5.0}),
    (66, "back out, on the horse", {"indoors": False, "mounted": True, "speed": 14.0}),
    (90, "night falls", {"daytime": False}),
    (100, "at the inn", {"mounted": False, "speed": 0.0, "indoors": True, "resting": True}),
    (112, "", {}),
)


def demo() -> None:
    director = Director()
    state = GameState(daytime=True, speed=0.0)
    frames, step = [], 0.5
    script = list(SESSION)
    caption = ""
    width, height = 900, 430
    big, small, tiny = font(30, "Bold"), font(20, "Medium"), font(15, "Medium")
    shown = {channel: 0.0 for channel in CHANNELS}
    for tick in range(int(script[-1][0] / step)):
        now = tick * step
        while script and script[0][0] <= now:
            _, caption_now, changes = script.pop(0)
            caption = caption_now or caption
            state = dataclasses.replace(state, **changes)
        # The director is asked four times a second, as the server asks it.
        for sub in range(2):
            target = director.update(state, now + sub * 0.25)
        mix = forever.mix(target)
        for channel in CHANNELS:
            want = mix[channel]["level"]
            # The player's own ramps: up over about 4 s, down over about 6 s.
            shown[channel] += max(min(want - shown[channel], step / 4.0), -step / 6.0)
        image = sky(width, height, seed=3)
        draw = ImageDraw.Draw(image)
        draw.text((32, 24), caption, font=big, fill=(245, 240, 225))
        tone = "place: %s" % target.place
        if target.lowpass_hz < 19000:
            tone += "   low-pass %.1f kHz" % (target.lowpass_hz / 1000)
        if target.reverb > 0.05:
            tone += "   reverb %.2f" % target.reverb
        draw.text((32, 66), tone, font=small, fill=(190, 190, 215))
        for index, channel in enumerate(CHANNELS):
            x = 80 + index * 160
            top, bottom = 120, 360
            draw.rounded_rectangle((x, top, x + 90, bottom), radius=10, fill=(20, 24, 52), outline=(60, 66, 110))
            level = shown[channel]
            if level > 0.005:
                draw.rounded_rectangle((x + 4, bottom - 4 - (bottom - top - 8) * level, x + 86, bottom - 4), radius=8,
                                       fill=COLOURS[channel])
            label = draw.textbbox((0, 0), channel, font=small)
            draw.text((x + 45 - (label[2] - label[0]) / 2, 370), channel, font=small, fill=(235, 235, 245))
            label = draw.textbbox((0, 0), NAMES[channel], font=tiny)
            draw.text((x + 45 - (label[2] - label[0]) / 2, 396), NAMES[channel], font=tiny, fill=(170, 170, 200))
        frames.append(image.convert("P", palette=Image.ADAPTIVE, colors=128))
    frames[0].save(OUT / "demo.gif", save_all=True, append_images=frames[1:], duration=int(step * 1000 / 2.5), loop=0, optimize=True)


# --- the strip ---------------------------------------------------------------------------------
def strip() -> None:
    # Walking in Elwynn Forest at nine in the evening, in the rain, two wolves in view.
    sample = beacon.Frame(beat=42, map_id=1429, x=int(0.42 * 65534), y=int(0.65 * 65534), weather_kind=1, weather_intensity=400,
                          game_minutes=21 * 60, volume=70, speed=14, enemies=2, fighting=0)
    payload = beacon.pack(sample)
    cell = 6
    squares = beacon.render(payload, cell=cell)
    picture = np.asarray(squares, dtype=np.float32)
    if picture.ndim == 2:
        picture = np.repeat(picture[:, :, None], 3, axis=2)
    if picture.max() <= 1.0:
        picture = picture * 255.0
    strip_image = Image.fromarray(picture.astype(np.uint8), "RGB")
    width = 1600
    image = sky(width, 420, seed=11)
    draw = ImageDraw.Draw(image)
    shown = strip_image.resize((width - 80, max(int(strip_image.height * (width - 80) / strip_image.width), 6)), Image.NEAREST)
    image.paste(shown, (40, 40))
    crop = strip_image.crop((0, 0, min(strip_image.width, 64 * cell), strip_image.height))
    zoom = crop.resize((crop.width * 4, crop.height * 4), Image.NEAREST)
    image.paste(zoom, ((width - zoom.width) // 2, 150))
    text = font(24, "Bold")
    draw.text((40, 70), "The strip: the whole game state, every frame, as two rows of black and white squares along the top of the screen",
              font=font(20, "Medium"), fill=(225, 225, 240))
    draw.text(((width - zoom.width) // 2, 150 + zoom.height + 14), "Its first squares, four times larger", font=text, fill=(246, 201, 84))
    image.save(OUT / "strip.png", optimize=True)


# --- the flow from the game to the music ---------------------------------------------------------
def flow() -> None:
    width, height = 1600, 760
    image = sky(width, height, seed=5)
    draw = ImageDraw.Draw(image)
    head, body = font(26, "Bold"), font(18, "Medium")

    def box(x, y, w, h, title, lines, colour):
        draw.rounded_rectangle((x, y, x + w, y + h), radius=18, fill=(18, 22, 50), outline=colour, width=3)
        draw.text((x + 22, y + 16), title, font=head, fill=colour)
        for index, line in enumerate(lines):
            draw.text((x + 22, y + 58 + index * 28), line, font=body, fill=(222, 222, 238))

    def arrow(points, colour=(220, 220, 240), label=""):
        draw.line(points, fill=colour, width=4)
        (x0, y0), (x1, y1) = points[-2], points[-1]
        angle = math.atan2(y1 - y0, x1 - x0)
        for side in (-1, 1):
            draw.line((x1, y1, x1 - 16 * math.cos(angle + side * 0.45), y1 - 16 * math.sin(angle + side * 0.45)), fill=colour, width=4)
        if label:
            middle = ((points[0][0] + points[-1][0]) / 2, (points[0][1] + points[-1][1]) / 2)
            box_ = draw.textbbox((0, 0), label, font=body)
            w, h = box_[2] - box_[0], box_[3] - box_[1]
            x, y = middle[0] - w / 2, middle[1] - h / 2
            draw.rounded_rectangle((x - 10, y - 8, x + w + 10, y + h + 12), radius=8, fill=(12, 16, 40), outline=(90, 90, 140))
            draw.text((x, y - 2), label, font=body, fill=(246, 201, 84))

    draw.text((40, 26), "The gaming PC", font=font(22, "Bold"), fill=(170, 175, 215))
    draw.text((870, 26), "The music machine", font=font(22, "Bold"), fill=(170, 175, 215))
    box(40, 70, 420, 220, "World of Warcraft", ["the FreeRock addon reads the game", "with Blizzard's documented calls,", "five times a second, and draws",
                                                 "it as a strip of squares"], (72, 199, 190))
    box(40, 360, 420, 190, "The sensor", ["copies the strip 20 times a second", "and sends its pixels on;", "it reads nothing else"], (72, 199, 190))
    box(40, 600, 420, 130, "The player page", ["five decks in the browser,", "mixed live on one bar grid"], (246, 201, 84))
    box(870, 70, 690, 220, "The server", ["decodes the strip into the game's state", "the director: where you are, what is going on,",
                                          "how much: a place, an intensity, a tone", "the desk: each channel's level and strength"], (150, 110, 240))
    box(870, 360, 690, 190, "The buckets", ["every track cut into the pieces of its story,", "each piece as five stems, lossless",
                                             "three styles: Warcraft, Knight Rock, House"], (240, 132, 62))
    box(870, 600, 690, 130, "The studio", ["writes the music as notes and plays it with", "real instruments in REAPER, overnight"], (232, 72, 92))
    arrow([(250, 290), (250, 360)], label="")
    arrow([(460, 455), (870, 180)], label="strip pixels")
    arrow([(1215, 290), (1215, 360)])
    arrow([(1215, 600), (1215, 550)])
    arrow([(870, 250), (460, 630)], label="what to play, how loud, what tone")
    arrow([(870, 500), (460, 690)], label="the music itself")
    image.save(OUT / "flow.png", optimize=True)


# --- the ear: what the studio measures, since it cannot listen -------------------------------------
def ear_picture() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    meta, parts = studio.read_track(VAR / "studio" / BANNER_TRACK[0] / BANNER_TRACK[1])
    plt.style.use("dark_background")
    figure, axes = plt.subplots(1, 5, figsize=(16, 3.6), dpi=110, sharey=True)
    figure.patch.set_facecolor("#0d1530")
    for axis, channel in zip(axes, CHANNELS):
        axis.set_facecolor("#0d1530")
        mine = ear.profile(parts[channel], studio.RATE)
        wanted = ear.reference("", style=BANNER_TRACK[0], channel=channel)
        xs = np.arange(len(ear.CENTRES))
        axis.plot(xs, wanted.bands, color="#9aa0c8", lw=2, ls="--", label="the stems that were liked")
        axis.plot(xs, mine.bands, color="#%02x%02x%02x" % COLOURS[channel], lw=3, label="this track")
        axis.set_title(channel, color="white")
        axis.set_xticks(xs[::2])
        axis.set_xticklabels(["%.1fk" % (c / 1000) if c >= 1000 else "%d" % c for c in ear.CENTRES[::2]], fontsize=8)
        axis.set_xlabel("Hz", fontsize=8, color="#c8c8d8")
        for side in ("top", "right"):
            axis.spines[side].set_visible(False)
    axes[0].set_ylabel("share of the power, dB")
    axes[0].legend(fontsize=8, frameon=False, loc="lower left")
    figure.suptitle("The studio cannot hear, so it measures: each channel's octaves against the stems that were liked", color="white")
    figure.tight_layout()
    figure.savefig(OUT / "ear.png", facecolor=figure.get_facecolor())


# --- what a place does to the sound -----------------------------------------------------------------

FREQS = np.geomspace(30.0, 16000.0, 240)        # where the sound is looked at, in Hz


def _biquad_db(kind: str, corner: float, freqs: np.ndarray, rate: float = 48000.0) -> np.ndarray:
    """What one of the player's filters (a Web Audio biquad, `lowpass` or `highpass`, its Q set to
    0.707, which Web Audio reads in dB) passes at each frequency, in dB: the Audio EQ Cookbook's
    formulas, as the Web Audio specification gives them."""
    w0 = 2 * math.pi * min(corner, rate * 0.45) / rate
    alpha = math.sin(w0) / (2 * 10 ** (0.707 / 20))
    cos = math.cos(w0)
    b = ((1 - cos) / 2, 1 - cos, (1 - cos) / 2) if kind == "lowpass" else ((1 + cos) / 2, -(1 + cos), (1 + cos) / 2)
    a = (1 + alpha, -2 * cos, 1 - alpha)
    z = np.exp(-1j * 2 * np.pi * freqs / rate)
    response = (b[0] + b[1] * z + b[2] * z ** 2) / (a[0] + a[1] * z + a[2] * z ** 2)
    return 20 * np.log10(np.abs(response) + 1e-12)


def tone_db(target, freqs: np.ndarray = FREQS) -> np.ndarray:
    """What the player's tone does to each frequency for a target, as forever.js builds it: two
    low-passes one after the other, a high-pass, and the volume."""
    return (2 * _biquad_db("lowpass", target.lowpass_hz, freqs) + _biquad_db("highpass", max(target.highpass_hz, 20.0), freqs)
            + 20 * math.log10(max(target.volume, 1e-6)))


_SUMMIT: tuple[dict, dict[str, np.ndarray]] | None = None


def _summit() -> tuple[dict, dict[str, np.ndarray]]:
    """The banner track at its summit (its last moment): what it says of itself, and each
    channel's power in sixth-octave bands at FREQS."""
    global _SUMMIT
    if _SUMMIT is None:
        from scipy import signal
        meta, parts = studio.read_track(VAR / "studio" / BANNER_TRACK[0] / BANNER_TRACK[1])
        bars = [section["bars"] for section in meta["sections"]]
        last = max(index for index, section in enumerate(meta["sections"]) if section["story"] == "moment")
        first = int(round(sum(bars[:last]) * meta["bar_frames"]))
        until = first + int(round(bars[last] * meta["bar_frames"]))
        bands = {}
        for channel in CHANNELS:
            if channel not in parts:
                bands[channel] = np.zeros(len(FREQS))
                continue
            f, power = signal.welch(parts[channel][first:until].mean(axis=1), fs=studio.RATE, nperseg=16384)
            bands[channel] = np.array([power[(f >= c * 2 ** (-1 / 12)) & (f < c * 2 ** (1 / 12))].mean() for c in FREQS])
        _SUMMIT = meta, bands
    return _SUMMIT


def player_levels(target, meta: dict) -> dict[str, float]:
    """How loud the player plays each channel of the summit for a target, as forever.js `_level`
    does: the desk's level, raised to that of any channel it follows and to the piece's floor
    (the floor kept less at night for the drums and the bass)."""
    wanted = forever.mix(target)
    floors, follow = meta["floor"].get("moment", {}), meta.get("follow", {})
    out = {}
    for channel in CHANNELS:
        level = wanted[channel]["level"]
        for other in follow.get(channel, []):
            level = max(level, wanted[other]["level"])
        hush = target.hush if channel in ("drums", "bass") else 1.0
        if floors.get(channel, 0.0) > 0:
            level = max(level, floors[channel] * target.bed * hush)
        out[channel] = level
    return out


def heard_db(target=None) -> np.ndarray:
    """The summit as it is heard for a target, in dB against the summit with every channel up and
    nothing in the way (its loudest at 0); with no target, that open sound itself."""
    meta, bands = _summit()
    open_air = sum(bands.values())
    reference = 10 * np.log10(open_air.max())
    if target is None:
        return 10 * np.log10(open_air + 1e-20) - reference
    levels = player_levels(target, meta)
    power = sum(levels[channel] ** 2 * bands[channel] for channel in CHANNELS)
    return 10 * np.log10(power + 1e-20) - reference + tone_db(target)


def _chart(target, label: str, colour: str, corner_text: str, size=(9.0, 3.9)) -> Image.Image:
    """The track's sound in the open and in a place, as a picture to paste on a card."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.style.use("dark_background")
    figure, axis = plt.subplots(figsize=size, dpi=100)
    figure.patch.set_facecolor("#10173a")
    axis.set_facecolor("#10173a")
    open_air, here = heard_db(), heard_db(target)
    axis.fill_between(FREQS, -70, open_air, color="#9a8fd8", alpha=0.25, lw=0)
    axis.plot(FREQS, open_air, color="#b8b0f0", lw=1.4, ls="--", label="out in the open")
    axis.fill_between(FREQS, -70, here, color=colour, alpha=0.55, lw=0)
    axis.plot(FREQS, here, color=colour, lw=2.4, label=label)
    if target.lowpass_hz < 19000:
        axis.axvline(target.lowpass_hz, color="#f0f0ff", lw=1, ls=":", alpha=0.8)
        axis.text(target.lowpass_hz * 1.06, -8, corner_text, color="#f0f0ff", fontsize=11)
    axis.set_xscale("log")
    axis.set_xlim(FREQS[0], FREQS[-1])
    axis.set_ylim(-66, 4)
    axis.set_xticks([50, 100, 250, 500, 1000, 2500, 5000, 10000])
    axis.set_xticklabels(["50", "100", "250", "500", "1k", "2.5k", "5k", "10k"])
    axis.set_xlabel("Hz: low notes on the left, the shine of the top on the right", color="#c8c8e0", fontsize=10)
    axis.set_ylabel("dB", color="#c8c8e0")
    axis.legend(loc="lower left", frameon=False, fontsize=11)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    figure.tight_layout()
    figure.canvas.draw()
    image = Image.frombuffer("RGBA", figure.canvas.get_width_height(), figure.canvas.buffer_rgba()).convert("RGB")
    plt.close(figure)
    return image


def _card(image: Image.Image, box, outline) -> None:
    """A dark rounded card on the sky, for a chart and its words."""
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, radius=18, fill=(16, 23, 58, 235), outline=outline, width=2)
    image.alpha_composite(layer)


def _write(draw, xy, lines, size=20, colour=(226, 226, 240), gap=10, weight="Medium") -> None:
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=font(size, weight), fill=colour)
        y += size + gap


def _cave_scene(width: int, height: int) -> Image.Image:
    """A cave in a hillside at night, a lantern deep inside. Drawn twice as large and made smaller,
    so its edges are smooth."""
    w, h = width * 2, height * 2
    image = sky(w, h, seed=11).convert("RGBA")
    draw = ImageDraw.Draw(image)
    rng = random.Random(5)
    rock = [(0, h)] + [(x, int(h * 0.30 + 60 * math.sin(x / 210) + rng.randrange(0, 40))) for x in range(0, w + 40, 40)] + [(w, h)]
    draw.polygon(rock, fill=(44, 36, 70))
    for _ in range(26):                                                     # cracks and ledges in the stone
        x, y = rng.randrange(w), rng.randrange(int(h * 0.38), h)
        draw.line((x, y, x + rng.randrange(-60, 60), y + rng.randrange(20, 70)), fill=(30, 25, 52), width=4)
    ground, left, right, top = int(h * 0.92), int(w * 0.22), int(w * 0.78), int(h * 0.46)
    centre = (left + right) / 2

    def roof(x: float) -> float:
        """The height of the arch over the floor at `x`."""
        across = (x - centre) / ((right - left) / 2)
        return ground - (ground - top) * math.sqrt(max(1.0 - across ** 2, 0.0)) ** 0.8

    arch = [(x + rng.randrange(-5, 6), roof(x) + rng.randrange(-5, 6)) for x in range(left, right + 1, 16)]
    draw.polygon([(left, ground)] + arch + [(right, ground)], fill=(10, 8, 20))
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    cy = int(ground - 0.32 * (ground - top))
    for radius in range(230, 0, -8):                                        # the lantern's light on the walls inside
        gdraw.ellipse((centre - radius, cy - radius * 0.75, centre + radius, cy + radius * 0.75),
                      fill=(255, 150, 60, int(5 + 70 * (1 - radius / 230) ** 2)))
    image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(16)))
    draw = ImageDraw.Draw(image)
    for x in sorted(rng.sample(range(left + 90, right - 90, 10), 7)):       # stalactites hanging from the roof
        hang = roof(x) - 4
        draw.polygon([(x - 9, hang), (x + 9, hang), (x + rng.randrange(-3, 4), hang + rng.randrange(26, 64))], fill=(44, 36, 70))
    draw.polygon([(left + 40, ground), (right - 40, ground), (right + 120, h), (left - 120, h)], fill=(58, 48, 86))   # the path in
    for _ in range(9):                                                      # stones by the way
        x, size = rng.choice((rng.randrange(0, left), rng.randrange(right, w))), rng.randrange(20, 46)
        y = rng.randrange(ground - 20, h - 10)
        draw.ellipse((x - size, y - size * 0.6, x + size, y + size * 0.6), fill=(36, 30, 60))
    draw.ellipse((centre - 15, cy - 15, centre + 15, cy + 15), fill=(255, 214, 140))   # the lantern
    draw.text((60, 50), "Into a Cave", font=title_font(110), fill=(246, 201, 84), stroke_width=4, stroke_fill=(60, 30, 10))
    return image.resize((width, height), Image.LANCZOS)


def _water_scene(width: int, height: int) -> Image.Image:
    """Under the surface at night: light from above, bubbles rising, weed swaying."""
    w, h = width * 2, height * 2
    top, bottom = np.array((34, 128, 150), float), np.array((6, 16, 44), float)
    rows = np.linspace(0.0, 1.0, h)[:, None] ** 0.8
    gradient = (top * (1 - rows) + bottom * rows).astype(np.uint8)
    image = Image.fromarray(np.repeat(gradient[:, None, :], w, axis=1).reshape(h, w, 3), "RGB").convert("RGBA")
    surface = int(h * 0.16)
    night = sky(w, surface + 40, seed=13).convert("RGBA")
    image.alpha_composite(night.crop((0, 0, w, surface)), (0, 0))
    draw = ImageDraw.Draw(image)
    wave = [(x, surface + 14 * math.sin(x / 70.0) + 6 * math.sin(x / 23.0)) for x in range(0, w + 10, 10)]
    draw.polygon(wave + [(w, surface + 60), (0, surface + 60)], fill=(60, 170, 186))
    draw.line(wave, fill=(200, 245, 250), width=5)
    rays = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    rdraw = ImageDraw.Draw(rays)
    rng = random.Random(3)
    for x in (int(w * 0.18), int(w * 0.42), int(w * 0.63), int(w * 0.85)):   # light falling through the water
        spread = rng.randrange(60, 120)
        rdraw.polygon([(x - 40, surface), (x + 40, surface), (x + 180 + spread, h), (x - 120 - spread, h)],
                      fill=(190, 240, 255, 34))
    image.alpha_composite(rays.filter(ImageFilter.GaussianBlur(18)))
    draw = ImageDraw.Draw(image)
    for stem in range(9):                                                  # weed on the bottom
        x = 60 + stem * (w - 120) // 8 + rng.randrange(-30, 30)
        points = [(x + 22 * math.sin(y / 60.0 + stem), y) for y in range(h, int(h * (0.62 + 0.1 * rng.random())), -12)]
        draw.line(points, fill=(20, 70, 60), width=14)
    for _ in range(60):                                                    # bubbles going up
        x = int(w * 0.5 + rng.gauss(0, w * 0.10))
        y = rng.randrange(surface + 60, h - 40)
        radius = rng.randrange(4, 16)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=(210, 245, 255), width=3)
    draw.text((60, surface + 70), "Under Water", font=title_font(110), fill=(246, 201, 84), stroke_width=4, stroke_fill=(10, 30, 50))
    return image.resize((width, height), Image.LANCZOS)


def _place_picture(name: str, scene: Image.Image, target, colour: str, label: str, corner_text: str,
                   heading: str, lines: list[str]) -> None:
    width, height = 1600, 640
    image = sky(width, height, seed=21).convert("RGBA")
    image.alpha_composite(scene.convert("RGBA"), (0, 0))
    outline = tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
    _card(image, (650, 24, 1580, 616), outline)
    chart = _chart(target, label, colour, corner_text, size=(8.9, 3.6))
    image.paste(chart, (665, 92))
    draw = ImageDraw.Draw(image)
    draw.text((680, 40), heading, font=font(30, "Bold"), fill=(246, 246, 255))
    _write(draw, (680, 462), lines, size=19, gap=9)
    image.convert("RGB").save(OUT / ("%s.png" % name))


def cave() -> None:
    target, _ = situation({"indoors": True}, 6)
    _place_picture("cave", _cave_scene(620, 640), target, "#f0a050", "in a cave", "2.5 kHz",
                   "In a cave, the music closes in",
                   ["One second inside and the cave's own music (depths) takes its turn; two seconds out, it lets go.",
                    "Two filters close the top at 2.5 kHz, 24 dB an octave: the shine goes, the body stays.",
                    "40% of the sound goes into a stone room that rings for 1.6 seconds.",
                    "A storm outside does not reach in. (A dungeon is not a cave: it has music of its own.)"])


def water() -> None:
    target, _ = situation({"swimming": True, "submerged": True}, 2)
    _place_picture("water", _water_scene(620, 640), target, "#4fd0e0", "under water", "500 Hz",
                   "Under water, only the low notes get through",
                   ["Head under the surface and everything above 500 Hz falls away: the bass, the drums' body",
                    "and the lowest strings come through, the tune and the cymbals are a blur above you.",
                    "It happens in 0.15 s, where every other change of tone takes 0.4: you are under at once.",
                    "Swimming on the surface changes nothing. Come up for air and the music opens again."])


# A card for each kind of place: what the game says, what is heard, and a little picture of it.
PLACES = (
    ("Out walking", {"speed": 7.0}, 25, "#f6c954", "sun",
     "The walking music. The drums come in as you go, the bass after."),
    ("Night", {"speed": 7.0, "daytime": False}, 25, "#a59cf0", "moon",
     "Night's own music: darker, further off, the drums back."),
    ("A rain storm", {"speed": 7.0, "weather": "rain", "weather_intensity": 0.9}, 10, "#6fb4f0", "storm",
     "The whole band, never muffled. Storm music after 4 s."),
    ("Snow", {"speed": 7.0, "weather": "snow", "weather_intensity": 1.0}, 10, "#e8f2ff", "snow",
     "Softer at the top, wider, the drums lighter."),
    ("A sandstorm", {"speed": 7.0, "weather": "sandstorm", "weather_intensity": 1.0}, 10, "#e8b46a", "sand",
     "Narrow and gritty: the low end and the top both go."),
    ("A cave", {"indoors": True}, 6, "#f0a050", "cave",
     "The depths music, closed in, with an echo of stone."),
    ("Under water", {"swimming": True, "submerged": True}, 2, "#4fd0e0", "water",
     "Only the low notes, and at once."),
    ("An inn", {"indoors": True, "resting": True}, 6, "#f08a5d", "inn",
     "The inn's calm music, 4 dB down and closed in."),
    ("A flight path", {"on_taxi": True, "flying": True, "speed": 30.0}, 20, "#9ee6c8", "wings",
     "Thin and airy: everything under 150 Hz goes."),
    ("Camping", {}, 50, "#ff9a4a", "camp",
     "45 s still out of doors: the camp's own tunes."),
    ("Stealth", {"stealthed": True, "speed": 3.0}, 6, "#8c7cf0", "hood",
     "Only the bass line and quiet drums."),
    ("Dead", {"dead": True}, 6, "#c8d0e8", "ghost",
     "Run down like a record, then calm and far off."),
)


def _icon(draw: ImageDraw.ImageDraw, kind: str, box, colour) -> None:
    """A small picture of a place, drawn in its colour inside `box` (twice the size it is shown)."""
    x0, y0, x1, y1 = box
    cx, cy, r = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2
    dim = tuple(int(c * 0.55) for c in colour)
    if kind == "sun":
        for k in range(12):
            angle = k * math.pi / 6
            draw.line((cx + 0.62 * r * math.cos(angle), cy + 0.62 * r * math.sin(angle),
                       cx + 0.92 * r * math.cos(angle), cy + 0.92 * r * math.sin(angle)), fill=colour, width=8)
        draw.ellipse((cx - 0.48 * r, cy - 0.48 * r, cx + 0.48 * r, cy + 0.48 * r), fill=colour)
    elif kind == "moon":
        draw.ellipse((cx - 0.7 * r, cy - 0.7 * r, cx + 0.7 * r, cy + 0.7 * r), fill=colour)
        draw.ellipse((cx - 0.4 * r, cy - 0.85 * r, cx + 0.95 * r, cy + 0.5 * r), fill=(16, 23, 58))
        for sx, sy in ((0.55, -0.6), (0.75, 0.3), (0.2, 0.75)):
            draw.ellipse((cx + sx * r - 5, cy + sy * r - 5, cx + sx * r + 5, cy + sy * r + 5), fill=colour)
    elif kind == "storm":
        draw.ellipse((cx - 0.8 * r, cy - 0.55 * r, cx - 0.05 * r, cy + 0.15 * r), fill=dim)
        draw.ellipse((cx - 0.35 * r, cy - 0.85 * r, cx + 0.45 * r, cy + 0.1 * r), fill=dim)
        draw.ellipse((cx + 0.05 * r, cy - 0.5 * r, cx + 0.85 * r, cy + 0.15 * r), fill=dim)
        draw.rectangle((cx - 0.55 * r, cy - 0.2 * r, cx + 0.6 * r, cy + 0.15 * r), fill=dim)
        for k in range(5):
            x = cx - 0.6 * r + k * 0.3 * r
            draw.line((x, cy + 0.3 * r, x - 0.15 * r, cy + 0.85 * r), fill=colour, width=6)
        draw.polygon([(cx + 0.05 * r, cy + 0.1 * r), (cx - 0.2 * r, cy + 0.55 * r), (cx, cy + 0.5 * r),
                      (cx - 0.15 * r, cy + 0.95 * r), (cx + 0.3 * r, cy + 0.38 * r), (cx + 0.08 * r, cy + 0.42 * r)],
                     fill=(255, 236, 140))
    elif kind == "snow":
        for k in range(6):
            angle = k * math.pi / 3
            ex, ey = cx + 0.85 * r * math.cos(angle), cy + 0.85 * r * math.sin(angle)
            draw.line((cx, cy, ex, ey), fill=colour, width=7)
            for along in (0.45, 0.68):
                bx, by = cx + along * r * math.cos(angle), cy + along * r * math.sin(angle)
                for turn in (0.6, -0.6):
                    draw.line((bx, by, bx + 0.22 * r * math.cos(angle + turn), by + 0.22 * r * math.sin(angle + turn)),
                              fill=colour, width=5)
    elif kind == "sand":
        for row in range(4):
            y = cy - 0.6 * r + row * 0.4 * r
            draw.line([(cx - 0.9 * r + t, y + 0.12 * r * math.sin(t / (0.18 * r) + row)) for t in range(0, int(1.8 * r), 6)],
                      fill=colour if row % 2 == 0 else dim, width=7)
    elif kind == "cave":
        draw.polygon([(x0, y1), (x0 + 0.1 * r, cy - 0.3 * r), (cx - 0.4 * r, y0 + 0.2 * r), (cx + 0.5 * r, y0 + 0.1 * r),
                      (x1 - 0.05 * r, cy - 0.2 * r), (x1, y1)], fill=dim)
        draw.ellipse((cx - 0.5 * r, cy - 0.15 * r, cx + 0.5 * r, cy + 1.3 * r), fill=(10, 8, 20))
        draw.ellipse((cx - 0.12 * r, cy + 0.45 * r, cx + 0.12 * r, cy + 0.69 * r), fill=colour)
    elif kind == "water":
        for row in range(3):
            y = cy - 0.55 * r + row * 0.35 * r
            draw.line([(cx - 0.9 * r + t, y + 0.1 * r * math.sin(t / (0.14 * r))) for t in range(0, int(1.8 * r), 6)],
                      fill=colour, width=7)
        for bx, by, br in ((0.1, 0.5, 0.12), (-0.3, 0.75, 0.08), (0.45, 0.8, 0.07)):
            draw.ellipse((cx + bx * r - br * r, cy + by * r - br * r, cx + bx * r + br * r, cy + by * r + br * r), outline=colour, width=4)
    elif kind == "inn":
        draw.polygon([(cx - 0.85 * r, cy - 0.05 * r), (cx, cy - 0.85 * r), (cx + 0.85 * r, cy - 0.05 * r)], fill=dim)
        draw.rectangle((cx - 0.65 * r, cy - 0.05 * r, cx + 0.65 * r, cy + 0.85 * r), fill=dim)
        draw.rectangle((cx - 0.42 * r, cy + 0.12 * r, cx - 0.08 * r, cy + 0.42 * r), fill=(255, 200, 110))
        draw.rectangle((cx + 0.12 * r, cy + 0.3 * r, cx + 0.42 * r, cy + 0.85 * r), fill=(60, 34, 24))
    elif kind == "wings":
        for side in (-1, 1):
            draw.polygon([(cx, cy), (cx + side * 0.95 * r, cy - 0.55 * r), (cx + side * 0.7 * r, cy - 0.15 * r),
                          (cx + side * 0.9 * r, cy - 0.1 * r), (cx + side * 0.55 * r, cy + 0.15 * r)], fill=colour)
        draw.ellipse((cx - 0.12 * r, cy - 0.12 * r, cx + 0.12 * r, cy + 0.3 * r), fill=colour)
    elif kind == "camp":
        draw.polygon([(cx - 0.9 * r, cy + 0.6 * r), (cx - 0.35 * r, cy - 0.5 * r), (cx + 0.2 * r, cy + 0.6 * r)], fill=dim)
        draw.line((cx + 0.3 * r, cy + 0.85 * r, cx + 0.9 * r, cy + 0.6 * r), fill=(110, 70, 40), width=8)
        draw.line((cx + 0.3 * r, cy + 0.6 * r, cx + 0.9 * r, cy + 0.85 * r), fill=(110, 70, 40), width=8)
        draw.polygon([(cx + 0.38 * r, cy + 0.68 * r), (cx + 0.6 * r, cy - 0.1 * r), (cx + 0.82 * r, cy + 0.68 * r)], fill=colour)
        draw.polygon([(cx + 0.5 * r, cy + 0.68 * r), (cx + 0.6 * r, cy + 0.25 * r), (cx + 0.7 * r, cy + 0.68 * r)], fill=(255, 236, 140))
    elif kind == "hood":
        draw.polygon([(cx - 0.75 * r, cy + 0.9 * r), (cx - 0.6 * r, cy - 0.2 * r), (cx, cy - 0.9 * r), (cx + 0.6 * r, cy - 0.2 * r),
                      (cx + 0.75 * r, cy + 0.9 * r)], fill=dim)
        draw.ellipse((cx - 0.45 * r, cy - 0.35 * r, cx + 0.45 * r, cy + 0.55 * r), fill=(10, 8, 20))
        for ex in (-0.18, 0.18):
            draw.ellipse((cx + ex * r - 0.08 * r, cy + 0.02 * r, cx + ex * r + 0.08 * r, cy + 0.14 * r), fill=colour)
    elif kind == "ghost":
        draw.ellipse((cx - 0.55 * r, cy - 0.85 * r, cx + 0.55 * r, cy + 0.2 * r), fill=colour)
        bottom = [(cx - 0.55 * r, cy - 0.3 * r), (cx + 0.55 * r, cy - 0.3 * r), (cx + 0.55 * r, cy + 0.8 * r)]
        for k in range(6, -1, -1):
            bottom.append((cx - 0.55 * r + k * (1.1 * r / 6), cy + (0.8 if k % 2 == 0 else 0.6) * r))
        draw.polygon(bottom, fill=colour)
        for ex in (-0.2, 0.2):
            draw.ellipse((cx + ex * r - 0.09 * r, cy - 0.35 * r, cx + ex * r + 0.09 * r, cy - 0.15 * r), fill=(16, 23, 58))


def places() -> None:
    """Every kind of place on one page: a little picture, what is heard, and what the tone does."""
    columns, card_w, card_h, gap = 4, 372, 292, 18
    rows = math.ceil(len(PLACES) / columns)
    width, height = 1600, 120 + rows * (card_h + gap) + 20
    scale = 2
    image = sky(width * scale, height * scale, seed=31).convert("RGBA")
    draw = ImageDraw.Draw(image)
    heading = "How Each Place Sounds"
    size = draw.textbbox((0, 0), heading, font=title_font(96))
    draw.text(((width * scale - size[2]) / 2, 30), heading, font=title_font(96), fill=(246, 201, 84),
              stroke_width=4, stroke_fill=(60, 30, 10))
    open_air = heard_db()
    left = (width - (columns * card_w + (columns - 1) * gap)) / 2
    for index, (name, changes, seconds, colour, icon, words) in enumerate(PLACES):
        target, _ = situation(changes, seconds)
        rgb = tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))
        x = int((left + (index % columns) * (card_w + gap)) * scale)
        y = int((120 + (index // columns) * (card_h + gap)) * scale)
        w, h = card_w * scale, card_h * scale
        layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).rounded_rectangle((x, y, x + w, y + h), radius=36, fill=(16, 23, 58, 238), outline=rgb + (255,), width=4)
        image.alpha_composite(layer)
        draw = ImageDraw.Draw(image)
        _icon(draw, icon, (x + 28, y + 28, x + 28 + 150, y + 28 + 150), rgb)
        draw.text((x + 200, y + 40), name, font=font(46, "Bold"), fill=(246, 246, 255))
        said, line = [], ""
        for word in words.split():
            trial = (line + " " + word).strip()
            if draw.textlength(trial, font=font(30, "Medium")) > w - 230:
                said.append(line)
                line = word
            else:
                line = trial
        said.append(line)
        for row, text in enumerate(said[:3]):
            draw.text((x + 200, y + 104 + row * 40), text, font=font(30, "Medium"), fill=(214, 214, 232))
        # The track's sound here against the open air: a little chart along the bottom of the card.
        px0, py0, px1, py1 = x + 28, y + 236, x + w - 28, y + h - 64
        here = heard_db(target)

        def at(f_index, level):
            return (px0 + (px1 - px0) * f_index / (len(FREQS) - 1), py0 + (py1 - py0) * min(max(-level, 0.0), 66.0) / 66.0)
        draw.line([at(i, v) for i, v in enumerate(open_air)], fill=(150, 140, 200), width=3)
        draw.polygon([at(0, -66)] + [at(i, v) for i, v in enumerate(here)] + [at(len(FREQS) - 1, -66)], fill=rgb + (150,))
        draw.line([at(i, v) for i, v in enumerate(here)], fill=rgb, width=5)
        notes = []
        if target.lowpass_hz < 19000:
            notes.append("top at %s" % ("%g kHz" % round(target.lowpass_hz / 1000, 1) if target.lowpass_hz >= 1000 else "%d Hz" % target.lowpass_hz))
        if target.highpass_hz > 40:
            notes.append("lows cut at %d Hz" % target.highpass_hz)
        if target.reverb > 0.05:
            notes.append("echo %d%%" % round(target.reverb * 100))
        if target.volume < 0.99:
            notes.append("%+.0f dB" % (20 * math.log10(max(target.volume, 1e-6))))
        draw.text((x + 28, y + h - 52), "  ·  ".join(notes) or "nothing in the way", font=font(26, "Medium"), fill=rgb)
        draw.text((x + w - 28, y + h - 52), target.place, font=font(26, "Bold"), fill=(246, 246, 255), anchor="ra")
    image.resize((width, height), Image.LANCZOS).convert("RGB").save(OUT / "places.png")


PICTURES = {"banner": banner, "story": story, "signals": signals, "demo": demo, "strip": strip, "flow": flow, "ear": ear_picture,
            "cave": cave, "water": water, "places": places}


def main(argv: list[str]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in argv or list(PICTURES):
        PICTURES[name]()
        print("drawn:", name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
