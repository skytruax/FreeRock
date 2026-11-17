"""The README's pictures, drawn from the project itself: a real track's stems, the real director
and mixing desk, the real strip encoder. Nothing is mocked up.

    cd app && uv run --no-sync --with matplotlib --with pillow python ../tools/readme_pictures.py [name ...]

Writes docs/images/<name>.png (and demo.gif). Names: banner, story, signals, demo, strip, flow, ear.
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


PICTURES = {"banner": banner, "story": story, "signals": signals, "demo": demo, "strip": strip, "flow": flow, "ear": ear_picture}


def main(argv: list[str]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in argv or list(PICTURES):
        PICTURES[name]()
        print("drawn:", name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
