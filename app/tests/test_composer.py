"""The styles, and a zone's profile as each style takes it."""
import pytest

from freerock import atlas
from freerock.composer import GENRES, ZoneProfile, for_genre, genre_of
from freerock.settings import Settings

ZONE = ZoneProfile(key="elwynn", bpm=120, tonic="G mixolydian",
                   colours=["chiming clean electric guitar arpeggios", "fiddle"], mood=["pastoral"])


def test_every_style_has_a_name_and_a_few_words_for_the_player_page():
    assert list(GENRES) == list(Settings.GENRES)
    for recipe in GENRES.values():
        assert recipe["label"] and recipe["about"]


def test_knight_rock_takes_a_zone_whole_and_the_orchestra_leaves_the_rock_band_out():
    assert for_genre(ZONE, "knight") is ZONE
    orchestra = for_genre(ZONE, "warcraft")
    assert (orchestra.bpm, orchestra.tonic, orchestra.mood) == (120, "G mixolydian", ["pastoral"])
    assert orchestra.colours == ["fiddle"], "a rock band's instruments reached the orchestra"


def test_the_house_style_is_happy_and_laid_back_wherever_the_player_is():
    for place in ("Duskwood", "Tanaris", "Stormwind City"):
        profile = for_genre(atlas.profile_for(place), "house")
        zone = atlas.profile_for(place)
        assert profile.bpm == 110 and profile.tonic == zone.tonic.split()[0] + " major"
        assert profile.mood == ["happy and carefree", "warm and laid-back"], "a gloomy zone does not make it gloomy"
        assert profile.key == zone.key and profile.colours == []


def test_an_unknown_style_is_an_error_not_knight_rock():
    with pytest.raises(ValueError, match="No style called"):
        for_genre(ZONE, "polka")
    with pytest.raises(ValueError):
        genre_of(None)
