"""The requests FreeRock writes for ElevenLabs."""
import numpy as np
import pytest

from freerock import analysis
from freerock.composer import (CORE_SUITE, FRESH_SET, GENRES, NEVER, PLACE_PIECE, SECOND_SET, Reference, ZoneProfile,
                               bars_ms, build, core_suite, for_genre, fresh_set, genre_of, second_set, vocabulary)

ZONE = ZoneProfile(key="elwynn", bpm=120, tonic="G mixolydian",
                   colours=["chiming clean electric guitar arpeggios", "fiddle"], mood=["pastoral"])


def test_bars_are_exact_or_refused():
    assert bars_ms(120, 16) == 32000
    assert bars_ms(96, 4) == 10000
    assert bars_ms(128, 16) == 30000
    assert bars_ms(90, 3) == 8000            # 2666.67 ms a bar, whole only every third bar
    with pytest.raises(ValueError):
        bars_ms(90, 4)
    with pytest.raises(ValueError):
        bars_ms(112, 16)


def test_a_piece_can_be_sixteen_bars_where_eight_would_be_too_short():
    request = core_suite(ZONE, part_bars=16)
    assert [part.bars for part in request.parts] == [4] + [16] * 9


def test_each_fresh_set_goes_further_down_the_feels():
    first, later = fresh_set(ZONE, turn=0), fresh_set(ZONE, turn=1)
    assert [part.name for part in first.parts] == [part.name for part in later.parts] == list(FRESH_SET)
    words = lambda request: request.plan["chunks"][0]["positive_styles"]
    assert words(first) != words(later), "a second fresh set was asked for in the words of the first"
    assert words(first) != second_set(ZONE).plan["chunks"][0]["positive_styles"]


def test_every_part_states_tempo_key_and_instrumental():
    for request in (core_suite(ZONE), second_set(ZONE), fresh_set(ZONE)):
        for chunk in request.plan["chunks"]:
            styles = chunk["positive_styles"]
            assert styles[0] == "120 BPM" and styles[1] == "G mixolydian"
            assert "instrumental" in styles and "vocals" in chunk["negative_styles"]
            assert len(styles) == len(set(styles)), "a style word is said twice"
            assert 3000 <= chunk["duration_ms"] <= 120000


def test_the_first_part_carries_the_whole_style_whichever_part_it_is():
    for names in (CORE_SUITE, SECOND_SET, FRESH_SET, ("Boss",)):
        first = build(ZONE, names).plan["chunks"][0]
        assert "riff-driven late-1970s arena hard rock, loud and simple" in first["positive_styles"]
        assert "medieval colour: lute and hurdy-gurdy" in first["positive_styles"]
        assert "fiddle" in first["positive_styles"]
        assert set(NEVER) <= set(first["negative_styles"])
    later = core_suite(ZONE).plan["chunks"][1]
    assert "riff-driven late-1970s arena hard rock, loud and simple" not in later["positive_styles"]


def test_no_band_or_game_names_reach_a_prompt():
    banned = ("ac/dc", "acdc", "warcraft", "azeroth", "elwynn", "stormwind", "blizzard")
    for genre in GENRES:
        for name, spec in vocabulary(for_genre(ZONE, genre), genre=genre).items():
            text = " ".join(spec.styles + spec.avoid).lower()
            assert not any(word in text for word in banned), (genre, name)
        whole = str(build(ZONE, CORE_SUITE + SECOND_SET + FRESH_SET + PLACE_PIECE, genre=genre).plan).lower()
        assert not any(word in whole for word in banned), genre


def test_more_rock_changes_the_calm_parts_only():
    gentle, hard = core_suite(ZONE, rock=0.1), core_suite(ZONE, rock=0.9)
    assert gentle.plan["chunks"][1] != hard.plan["chunks"][1]          # Wander A
    assert gentle.plan["chunks"][5] == hard.plan["chunks"][5]          # Battle
    with pytest.raises(ValueError):
        core_suite(ZONE, rock=1.5)


def test_a_reference_is_attached_to_every_part():
    reference = Reference("song123", 8000, 38000, strength="high")
    request = second_set(ZONE, seed=9, reference=reference)
    for chunk in request.plan["chunks"]:
        assert chunk["conditioning_ref"] == {"song_id": "song123", "range": {"start_ms": 8000, "end_ms": 38000}}
        assert chunk["condition_strength"] == "high"
    assert "conditioning_ref" not in core_suite(ZONE).plan["chunks"][0]
    with pytest.raises(ValueError):
        Reference("song123", 0, 31000)


def test_first_cuts_a_request_down():
    short = core_suite(ZONE, bars={"Wander A": 11}).first(2)
    assert [part.name for part in short.parts] == ["Arrival", "Wander A"]
    assert short.minutes == pytest.approx(0.5) and len(short.plan["chunks"]) == 2
    assert short.parts[1].bars == 11, "a part's length can be set by name"


def test_band_profile_tells_a_dull_mix_from_a_bright_one():
    rng = np.random.default_rng(2)
    noise = rng.normal(0, 0.1, 48000 * 4).astype(np.float32)
    same = analysis.profile_difference_db(analysis.band_profile(noise, 48000),
                                          analysis.band_profile(noise * 0.3, 48000))
    assert same < 0.1, "a level change alone must not count as a difference"
    from scipy.signal import butter, sosfilt
    dull = sosfilt(butter(4, 1500.0, "low", fs=48000, output="sos"), noise).astype(np.float32)
    assert analysis.profile_difference_db(analysis.band_profile(noise, 48000),
                                          analysis.band_profile(dull, 48000)) > 6


# --- the three styles ------------------------------------------------------------------------------

def test_the_same_ladder_of_pieces_in_every_style():
    """Whatever the style, a zone's first request has the same ten pieces in the same order, so
    the player and the rules need know nothing about styles."""
    for genre in GENRES:
        request = core_suite(ZONE, genre=genre)
        assert [part.name for part in request.parts] == list(CORE_SUITE), genre
        assert [part.bars for part in request.parts] == [4] + [8] * 9
        first = request.plan["chunks"][0]
        assert first["positive_styles"][3] == "instrumental" and "vocals" in first["negative_styles"]
        assert GENRES[genre]["base"][0] in first["positive_styles"]
        for chunk in request.plan["chunks"]:
            assert len(chunk["positive_styles"]) == len(set(chunk["positive_styles"]))
            assert 3000 <= chunk["duration_ms"] <= 120000


def test_knight_rock_is_the_band_and_the_orchestra_and_trance_are_not():
    knight = " ".join(str(chunk) for chunk in core_suite(ZONE, genre="knight").plan["chunks"])
    orchestra = core_suite(ZONE, genre="warcraft")
    trance = core_suite(ZONE, genre="trance")
    assert "rhythm guitars" in knight and "hurdy-gurdy" in knight
    said = " ".join(" ".join(chunk["positive_styles"]) for chunk in orchestra.plan["chunks"])
    assert "symphony orchestra" in said and "guitar" not in said, "a rock band's instruments reached the orchestra"
    assert "fiddle" in said, "the zone's own acoustic colour is kept"
    assert {"electric guitar", "drum kit", "synthesizer"} <= set(orchestra.plan["chunks"][0]["negative_styles"])
    said = " ".join(" ".join(chunk["positive_styles"]) for chunk in trance.plan["chunks"])
    assert "uplifting trance" in said and "four-on-the-floor" in said and "fiddle" not in said
    assert "pastoral" in said, "the zone's mood is kept"
    assert "synthesizer" not in trance.plan["chunks"][0]["negative_styles"]


def test_trance_plays_a_zone_at_a_dance_tempo_in_a_minor_key():
    slow = ZoneProfile(key="duskwood", bpm=80, tonic="D minor", colours=["organ"], mood=["haunted"])
    fast = ZoneProfile(key="gulch", bpm=160, tonic="E minor", colours=["war drums"], mood=["urgent"])
    assert (for_genre(ZONE, "trance").bpm, for_genre(ZONE, "trance").tonic) == (128, "G minor")
    assert for_genre(slow, "trance").bpm == 128 and for_genre(fast, "trance").bpm == 150
    request = core_suite(slow, genre="trance")
    assert request.bpm == 128 and request.tonic == "D minor"
    assert request.plan["chunks"][0]["positive_styles"][:2] == ["128 BPM", "D minor"]
    assert request.parts[1].end_ms - request.parts[1].start_ms == 15000, "eight bars at 128"
    assert for_genre(slow, "knight") is slow and for_genre(slow, "warcraft").bpm == 80


def test_an_unknown_style_is_an_error_not_knight_rock():
    with pytest.raises(ValueError, match="No style called"):
        core_suite(ZONE, genre="polka")
    with pytest.raises(ValueError):
        genre_of(None)
