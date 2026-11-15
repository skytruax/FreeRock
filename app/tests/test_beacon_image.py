"""Reading the strip out of a picture: clean, and spoiled in the ways a real screen spoils it."""
import time

import numpy as np
import pytest
from hypothesis import assume, given, settings, strategies as st

from freerock import beacon
import link_helpers as lh
from link_helpers import SAMPLE, frames

PAYLOAD = beacon.pack(SAMPLE)
SIZES = (2, 3, 4, 5, 6)


def band(cell=3, **options):
    return lh.screen_band(beacon.render(PAYLOAD, cell=cell).astype(np.float32), **options)


def reads_sample(picture) -> bool:
    reading = beacon.read(lh.as_picture(picture))
    # Whatever happens, a frame that is read must be the frame that was drawn.
    assert reading.frame in (None, SAMPLE), "a wrong frame was read"
    return reading.ok


@pytest.mark.parametrize("cell", SIZES)
def test_clean_strip_is_read_and_measured(cell):
    picture = lh.as_picture(band(cell, at=(3, 21)))
    reading = beacon.read(picture)
    assert reading.frame == SAMPLE
    assert reading.problem is None
    assert reading.pitch == pytest.approx(cell, abs=0.01)
    x, y, width, height = reading.box
    assert x == 21 + 2                       # the quiet squares start after the 2 px backing
    assert width == 344 * cell
    assert 3 + 2 <= y and y + height <= 3 + 2 + 2 * cell


@pytest.mark.parametrize("cell", SIZES)
def test_strip_is_found_anywhere(cell):
    for at in ((0, 0), (9, 137), (25, 60)):
        assert reads_sample(band(cell, at=at, height=44)), at


def test_colour_pictures_in_either_channel_order():
    grey = lh.as_picture(band(3))
    rgb = np.stack([grey, grey, grey], axis=2)
    bgra = np.dstack([rgb[:, :, ::-1], np.full(grey.shape, 255, np.uint8)])
    assert beacon.read(rgb).frame == SAMPLE
    assert beacon.read(bgra).frame == SAMPLE


SPOILERS = {
    "gamma 0.45": lambda p, c: lh.gamma(p, 0.45),
    "gamma 2.4": lambda p, c: lh.gamma(p, 2.4),
    "low contrast": lambda p, c: lh.levels(p, 70, 135),
    "dimmed to 30%": lambda p, c: lh.levels(p, 0, 76),
    "raised black": lambda p, c: lh.levels(p, 95, 255),
    "dimming across, 1.0 to 0.35": lambda p, c: lh.dim_across(p, 1.0, 0.35),
    "dimming across with a grey veil": lambda p, c: lh.dim_across(p, 0.3, 1.0, lift=60),
    "warm tint": lambda p, c: lh.tint(p),
    "blue cast with raised blacks": lambda p, c: lh.tint(p, gains=(0.5, 0.7, 1.0), lifts=(10, 10, 60)),
    "blur, 0.35 of a square": lambda p, c: lh.blur(p, 0.35 * c),
    "noise": lambda p, c: lh.noise(p, 20),
    "jpeg quality 40": lambda p, c: lh.jpeg(p, 40),
    "gamma, dimming and noise together": lambda p, c: lh.noise(lh.dim_across(lh.gamma(p, 1.8), 0.5, 1.0, lift=30), 10),
}


@pytest.mark.parametrize("name", SPOILERS)
@pytest.mark.parametrize("cell", SIZES)
def test_spoiled_pictures_are_still_read(name, cell):
    assert reads_sample(SPOILERS[name](band(cell), cell)), f"{name} at {cell} px"


@pytest.mark.parametrize("cell", (3, 4, 5, 6))
@pytest.mark.parametrize("factor", (0.8, 0.9, 1.1, 1.25, 1.5))
def test_a_strip_that_is_not_pixel_exact_is_still_read(cell, factor):
    """Scaling blur: from 3 px squares up, a resampled strip reads."""
    assert reads_sample(lh.rescale(band(cell), factor)), f"{cell} px at x{factor}"


@pytest.mark.parametrize("cell", (3, 4, 5, 6))
def test_half_a_pixel_off_the_grid(cell):
    from scipy import ndimage

    assert reads_sample(ndimage.shift(band(cell), (0.5, 0.5), order=1, mode="nearest"))


def test_the_smallest_squares_have_a_limit_and_it_fails_safe():
    """The limit, stated: squares of 2 px read when drawn pixel for pixel, and stop reading when
    the picture is shrunk so that they are a pixel and a half wide. 3 px is the default for that
    reason. Nothing wrong is ever read."""
    assert reads_sample(band(2))
    assert not reads_sample(lh.rescale(band(2), 0.75))


def test_no_strip():
    picture = lh.as_picture(lh.screen_band(np.zeros((0, 0), np.float32), height=40, extra=1400, seed=3))
    reading = beacon.read(picture)
    assert not reading.ok
    assert reading.problem == "no strip"
    assert reading.box is None


def test_flat_pictures_and_tiny_pictures_do_not_trip_the_reader():
    for picture in (np.zeros((30, 1500), np.uint8), np.full((30, 1500), 255, np.uint8), np.zeros((5, 20), np.uint8)):
        assert beacon.read(picture).problem == "no strip"


def test_half_a_strip_says_so():
    picture = band(4, at=(0, 16), busy=False)
    picture[2 + 4:2 + 8, :] = 128.0  # the second row of squares is covered
    reading = beacon.read(lh.as_picture(picture))
    assert not reading.ok
    assert reading.problem == "half a strip"
    assert reading.rows_seen == (0,)


def test_a_damaged_strip_fails_the_checksum_instead_of_reading_wrong():
    picture = band(4, at=(0, 16), busy=False)
    # Swap one bit's two squares in the top row: still a valid pair, but a different bit.
    left = 16 + 2 + (2 + 6 + 4 + 4 + 40) * 4
    pair = picture[2:6, left:left + 8].copy()
    picture[2:6, left:left + 4], picture[2:6, left + 4:left + 8] = pair[:, 4:8], pair[:, 0:4]
    reading = beacon.read(lh.as_picture(picture))
    assert not reading.ok
    assert reading.problem == "checksum"
    assert reading.rows_seen == (0, 1)


def test_a_search_band_from_a_4k_screen_is_read_quickly():
    picture = lh.as_picture(lh.screen_band(beacon.render(PAYLOAD, cell=3).astype(np.float32), height=64, extra=2788, seed=9))
    assert picture.shape == (64, 3840)
    beacon.read(picture)  # warm up
    started = time.perf_counter()
    reading = beacon.read(picture)
    elapsed = time.perf_counter() - started
    assert reading.frame == SAMPLE
    assert elapsed < 0.25, f"reading a 64 x 3840 band took {elapsed * 1000:.0f} ms"


distortion = st.sampled_from(["gamma", "levels", "dim", "tint", "blur", "noise", "rescale"])


@given(frame=frames(), cell=st.sampled_from((3, 4, 5, 6)), kinds=st.lists(distortion, max_size=3, unique=True),
       seed=st.integers(0, 10_000), data=st.data())
@settings(max_examples=120, deadline=None)
def test_any_frame_under_any_mix_of_ordinary_distortions(frame, cell, kinds, seed, data):
    """Inside the envelope a real screen stays in, every frame reads exactly.

    The envelope: squares of 3 px or more; white at least 45 levels (of 255) brighter than black
    everywhere after gamma, contrast, dimming and tint; blur up to 0.3 of a square; noise up to
    12 levels; the picture resampled by 0.9 to 1.3.
    """
    payload = beacon.pack(frame)
    picture = lh.screen_band(beacon.render(payload, cell=cell).astype(np.float32),
                             at=(data.draw(st.integers(0, 12)), data.draw(st.integers(0, 60))), seed=seed)
    # The same brightness changes applied to plain white and plain black, to know the contrast left.
    white, black = np.full((1, 64), 255.0, np.float32), np.zeros((1, 64), np.float32)

    def everywhere(change):
        nonlocal picture, white, black
        picture, white, black = change(picture), change(white), change(black)

    for kind in kinds:
        if kind == "gamma":
            power = data.draw(st.floats(0.5, 2.2))
            everywhere(lambda p: lh.gamma(p, power))
        elif kind == "levels":
            low = data.draw(st.floats(0, 90))
            high = low + data.draw(st.floats(70, 165))
            everywhere(lambda p: lh.levels(p, low, high))
        elif kind == "dim":
            left, right, lift = data.draw(st.floats(0.4, 1.0)), data.draw(st.floats(0.4, 1.0)), data.draw(st.floats(0, 50))
            everywhere(lambda p: lh.dim_across(p, left, right, lift=lift))
        elif kind == "tint":
            gains = tuple(data.draw(st.floats(0.6, 1.0)) for _ in range(3))
            lifts = tuple(data.draw(st.floats(0, 30)) for _ in range(3))
            everywhere(lambda p: lh.tint(p, gains=gains, lifts=lifts).mean(axis=2))
        elif kind == "blur":
            picture = lh.blur(picture, data.draw(st.floats(0.0, 0.3)) * cell)
        elif kind == "noise":
            picture = lh.noise(picture, data.draw(st.floats(0, 12)), seed=seed)
        elif kind == "rescale":
            picture = lh.rescale(picture, data.draw(st.floats(0.9, 1.3)))
    assume(float((np.clip(white, 0, 255) - np.clip(black, 0, 255)).min()) >= 45.0)
    reading = beacon.read(lh.as_picture(picture))
    assert reading.frame == frame, reading.problem


@given(frame=frames(), cell=st.sampled_from(SIZES), seed=st.integers(0, 10_000), data=st.data())
@settings(max_examples=120, deadline=None)
def test_heavy_damage_never_produces_a_wrong_frame(frame, cell, seed, data):
    """Outside that envelope a reading may fail, but it must never come back as something else."""
    payload = beacon.pack(frame)
    picture = lh.screen_band(beacon.render(payload, cell=cell).astype(np.float32), seed=seed)
    picture = lh.blur(picture, data.draw(st.floats(0.0, 1.5)) * cell)
    picture = lh.noise(picture, data.draw(st.floats(0, 70)), seed=seed)
    picture = lh.rescale(picture, data.draw(st.floats(0.5, 1.6)))
    rng = np.random.default_rng(seed)
    for _ in range(data.draw(st.integers(0, 6))):  # blotches over parts of the strip
        x = int(rng.integers(0, picture.shape[1] - 12))
        picture[:, x:x + int(rng.integers(2, 12))] = rng.integers(0, 256)
    reading = beacon.read(lh.as_picture(picture))
    assert reading.frame in (None, frame)
