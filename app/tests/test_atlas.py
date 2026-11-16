"""The zone profiles: every zone in the game has one, and every one makes a valid request."""
import pytest

from freerock import analysis, atlas, forever
from freerock.composer import NEVER, bars_ms, core_suite, fresh_set, second_set

# The zone maps of Forever 1.60.1, from the game's own map table (wago.tools, UiMap, build wowf).
GAME_ZONES = [
    "Durotar", "Mulgore", "The Barrens", "Alterac Mountains", "Arathi Highlands", "Badlands",
    "Blasted Lands", "Tirisfal Glades", "Silverpine Forest", "Western Plaguelands",
    "Eastern Plaguelands", "Hillsbrad Foothills", "The Hinterlands", "Dun Morogh", "Searing Gorge",
    "Burning Steppes", "Elwynn Forest", "Deadwind Pass", "Duskwood", "Loch Modan",
    "Redridge Mountains", "Stranglethorn Vale", "Swamp of Sorrows", "Westfall", "Wetlands",
    "Teldrassil", "Darkshore", "Ashenvale", "Thousand Needles", "Stonetalon Mountains", "Desolace",
    "Feralas", "Dustwallow Marsh", "Tanaris", "Azshara", "Felwood", "Un'Goro Crater", "Moonglade",
    "Silithus", "Winterspring", "Stormwind City", "Orgrimmar", "Ironforge", "Thunder Bluff",
    "Darnassus", "Undercity", "Mount Hyjal", "Zephras Isle", "Riverglades", "Shen'dralas",
]
# Words that are ordinary English and may appear in a prompt even though a zone name has them.
ORDINARY = {"the", "of", "forest", "mountains", "mountain", "highlands", "foothills", "lands", "gorge",
            "steppes", "pass", "vale", "swamp", "sorrows", "city", "thunder", "bluff", "mount", "isle",
            "crater", "marsh", "needles", "thousand", "glades", "burning", "searing", "blasted",
            "eastern", "western", "loch", "dun"}
PLACE_WORDS = {word for name in GAME_ZONES for word in atlas.slug(name).split("-")
               if len(word) > 3 and word not in ORDINARY}
OTHER_NAMES = {"warcraft", "azeroth", "kalimdor", "blizzard", "horde", "alliance", "acdc", "ac/dc"}


def test_every_zone_in_the_game_has_a_profile():
    missing = [name for name in GAME_ZONES if not atlas.is_known(name)]
    assert not missing, "no profile for: %s" % ", ".join(missing)
    assert len(atlas.zones()) == len(GAME_ZONES)


@pytest.mark.parametrize("name", GAME_ZONES)
def test_a_profile_makes_valid_requests(name):
    profile = atlas.profile_for(name)
    assert profile.key == atlas.slug(name)
    assert profile.bpm in atlas.TEMPOS
    assert 2 <= len(profile.colours) <= 4 and 1 <= len(profile.mood) <= 3
    analysis.parse_tonic(profile.tonic)                                   # raises if it cannot be read
    assert (48000 * 60 * 4) % profile.bpm == 0, "a bar is not a whole number of samples"
    bars = atlas.part_bars(profile.bpm)
    request = core_suite(profile, seed=1, part_bars=bars)
    assert 2.0 <= request.minutes <= 4.0, "%s: a %.2f minute suite" % (name, request.minutes)
    for part in request.parts:
        assert part.bars % 4 == 0 and bars_ms(profile.bpm, part.bars) == part.end_ms - part.start_ms
    for later in (second_set(profile, part_bars=bars), fresh_set(profile, part_bars=bars)):
        assert 2.0 <= later.minutes <= 4.0, "%s: a %.2f minute set" % (name, later.minutes)
        assert all(3000 <= chunk["duration_ms"] <= 120000 for chunk in later.plan["chunks"])


@pytest.mark.parametrize("name", GAME_ZONES)
def test_a_profile_says_nothing_a_prompt_must_not(name):
    profile = atlas.profile_for(name)
    text = " ".join(profile.colours + profile.mood + [profile.tonic]).lower()
    for word in NEVER:
        assert word not in text, "%s asks for %r, which every request also forbids" % (name, word)
    for word in PLACE_WORDS | OTHER_NAMES:
        assert word not in text.replace("-", " ").split() and word not in text, \
            "%s puts the name %r into a prompt" % (name, word)


def test_places_without_a_profile_get_one_from_their_name():
    assert "pickaxe strikes on the backbeat" in atlas.profile_for("The Deadmines").colours
    assert "war drums" in atlas.profile_for("Shadowfang Keep").colours
    assert "echoing guitar harmonics" in atlas.profile_for("Wailing Caverns").colours
    assert "church organ" in atlas.profile_for("Scarlet Monastery").colours
    assert atlas.profile_for("Warsong Gulch").bpm == 150
    assert atlas.profile_for("Somewhere Nobody Has Heard Of").key == "somewhere-nobody-has-heard-of"
    assert atlas.profile_for(None).key == "elsewhere" and atlas.profile_for("???").key == "elsewhere"
    for name in ("The Deadmines", "Warsong Gulch", "Somewhere Nobody Has Heard Of", None):
        profile = atlas.profile_for(name)
        # A song with its fight part comes in under five minutes at any tempo, and a phrase
        # of the forever song, which is one turn of its form, at about a minute or under.
        assert core_suite(profile, part_bars=atlas.part_bars(profile.bpm)).minutes <= 5.0
        assert 0.6 <= forever.ask(profile, "knight", "drums", 1, 0, seed=1).minutes <= 1.1
        assert not atlas.is_known(name)


def test_slug():
    assert atlas.slug("Un'Goro Crater") == "un-goro-crater" and atlas.slug("Shen'dralas") == "shen-dralas"
