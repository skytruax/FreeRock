"""The requests FreeRock writes for ElevenLabs."""
import numpy as np
import pytest

from freerock import analysis
from freerock.composer import (CORE_SUITE, FRESH_SET, NEVER, SECOND_SET, Reference, ZoneProfile,
                               bars_ms, build, core_suite, fresh_set, second_set, vocabulary)

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


def test_core_suite_layout():
    request = core_suite(ZONE, seed=5)
    assert [part.name for part in request.parts] == list(CORE_SUITE)
    assert [part.bars for part in request.parts] == [4, 16, 16, 16, 16, 16]
    assert request.minutes == pytest.approx(2.8)
    assert request.parts[0].start_ms == 0 and request.part("Wander A").start_ms == 8000
    for earlier, later in zip(request.parts, request.parts[1:]):
        assert earlier.end_ms == later.start_ms
    chunks = request.plan["chunks"]
    assert [chunk["duration_ms"] for chunk in chunks] == [8000, 32000, 32000, 32000, 32000, 32000]
    assert sum(chunk["duration_ms"] for chunk in chunks) == request.parts[-1].end_ms


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
        assert "riff-driven late-1970s arena hard rock" in first["positive_styles"]
        assert "medieval colour: lute and hurdy-gurdy" in first["positive_styles"]
        assert "fiddle" in first["positive_styles"]
        assert set(NEVER) <= set(first["negative_styles"])
    later = core_suite(ZONE).plan["chunks"][1]
    assert "riff-driven late-1970s arena hard rock" not in later["positive_styles"]


def test_no_band_or_game_names_reach_a_prompt():
    banned = ("ac/dc", "acdc", "warcraft", "azeroth", "elwynn", "stormwind", "blizzard")
    for name, spec in vocabulary(ZONE).items():
        text = " ".join(spec.styles + spec.avoid).lower()
        assert not any(word in text for word in banned), name
    whole = str(build(ZONE, CORE_SUITE + SECOND_SET + FRESH_SET).plan).lower()
    assert not any(word in whole for word in banned)


def test_more_rock_changes_the_calm_parts_only():
    gentle, hard = core_suite(ZONE, rock=0.1), core_suite(ZONE, rock=0.9)
    assert gentle.plan["chunks"][1] != hard.plan["chunks"][1]          # Wander A
    assert gentle.plan["chunks"][3] == hard.plan["chunks"][3]          # Battle
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


def test_band_profile_tells_a_dull_mix_from_a_bright_one():
    rng = np.random.default_rng(2)
    noise = rng.normal(0, 0.1, 48000 * 4).astype(np.float32)
    same = analysis.profile_difference_db(analysis.band_profile(noise, 48000),
                                          analysis.band_profile(noise * 0.3, 48000))
    assert same < 0.1, "a level change alone must not count as a difference"
    from freerock.render import lowpass
    dull = lowpass(noise[:, None], 48000, 1500.0, order=4)[:, 0]
    assert analysis.profile_difference_db(analysis.band_profile(noise, 48000),
                                          analysis.band_profile(dull, 48000)) > 6
