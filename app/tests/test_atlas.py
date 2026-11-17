"""The zone profiles: every zone in the game has one, and every one can be read."""
import pytest

from freerock import analysis, atlas

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


def test_every_zone_in_the_game_has_a_profile():
    missing = [name for name in GAME_ZONES if not atlas.is_known(name)]
    assert not missing, "no profile for: %s" % ", ".join(missing)
    assert len(atlas.zones()) == len(GAME_ZONES)


@pytest.mark.parametrize("name", GAME_ZONES)
def test_every_profile_can_be_read(name):
    profile = atlas.profile_for(name)
    assert profile.key == atlas.slug(name)
    assert profile.bpm in atlas.TEMPOS
    assert 2 <= len(profile.colours) <= 4 and 1 <= len(profile.mood) <= 3
    analysis.parse_tonic(profile.tonic)                                   # raises if it cannot be read
    assert (48000 * 60 * 4) % profile.bpm == 0, "a bar is not a whole number of samples"


def test_places_without_a_profile_get_one_from_their_name():
    assert "pickaxe strikes on the backbeat" in atlas.profile_for("The Deadmines").colours
    assert "war drums" in atlas.profile_for("Shadowfang Keep").colours
    assert "echoing guitar harmonics" in atlas.profile_for("Wailing Caverns").colours
    assert "church organ" in atlas.profile_for("Scarlet Monastery").colours
    assert atlas.profile_for("Warsong Gulch").bpm == 150
    assert atlas.profile_for("Somewhere Nobody Has Heard Of").key == "somewhere-nobody-has-heard-of"
    assert atlas.profile_for(None).key == "elsewhere" and atlas.profile_for("???").key == "elsewhere"
    for name in ("The Deadmines", "Warsong Gulch", "Somewhere Nobody Has Heard Of", None):
        assert atlas.profile_for(name).bpm in atlas.TEMPOS and not atlas.is_known(name)


def test_slug():
    assert atlas.slug("Un'Goro Crater") == "un-goro-crater" and atlas.slug("Shen'dralas") == "shen-dralas"
