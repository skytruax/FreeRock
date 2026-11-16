"""Written pieces cut from the songs on disk, and the `freerock pieces` commands."""
import numpy as np
import pytest
import soundfile

from freerock import cli, composer, forever, musiccli, pieces, songstems, studio
from freerock.composer import ZoneProfile
from freerock.library import Library
from freerock.settings import Settings
from freerock.stems import Layers
from test_library import made_up_track

RATE = forever.RATE
BAR = 72000                    # a bar at 160 beats a minute
DUSKWOOD = ZoneProfile(key="duskwood", bpm=160, tonic="D minor", colours=["organ"])
ELWYNN = ZoneProfile(key="elwynn-forest", bpm=160, tonic="G mixolydian", colours=["fiddle"])
SONG = composer.SONG + ("Fight", "Ember")
SUITE = ("Arrival", "Wander A", "Wander B", "Battle E", "Battle F", "Boss", "Storm", "Night", "Depths")


def add(library, profile, names, *, genre="knight", subzone=None, seed=1, level=0.3, set_name="core"):
    """A made-up song of four-bar sections in the library: noise, split into three layers."""
    request = composer.build(profile, names, seed=seed, bars={name: 4 for name in names}, part_bars=4)
    _, layers = made_up_track(request, seed=seed)
    quiet = Layers(bed=layers.bed * level, drums=layers.drums * level, bass=layers.bass * level, rate=RATE,
                   vocal_leak_db=-40.0, seconds=1.0, model="test")
    return library.add(zone=profile.key, set_name=set_name, request=request, mix=quiet.mix(), layers=quiet,
                       genre=genre, subzone=subzone)


@pytest.fixture
def home(tmp_path):
    library = Library(tmp_path / "library")
    bucket = forever.Bucket(tmp_path / "buckets", "duskwood", "knight", 80, "D minor")
    return library, bucket


def by_source(bucket):
    return {piece["source"]: (piece_id, piece) for piece_id, piece in bucket.pieces.items()}


def test_a_song_is_one_track_and_the_parts_made_for_a_moment_are_tracks_of_their_own(home):
    library, bucket = home
    asset = add(library, DUSKWOOD, SONG)
    made = songstems.from_songs(library, bucket)
    assert [(track.title, track.role, track.pieces, track.added) for track in made] == [
        ("Duskwood 1: Intro to Outro", "wander", 9, 9), ("Duskwood 1: Fight", "battle", 1, 1),
        ("Duskwood 1: Ember", "ember", 1, 1)]
    assert made[0].seconds == pytest.approx(9 * 4 * 1.5)
    found = by_source(bucket)
    # The song proper: a piece for each section, each going on into the next.
    song = [found["song/%s/%d" % (asset.id, bar)] for bar in range(0, 36, 4)]
    assert [piece["title"] for _, piece in song] == ["Duskwood 1: " + name for name in composer.SONG]
    assert [piece["story"] for _, piece in song] == ["open", "theme", "moment", "theme", "moment", "rise", "moment",
                                                     "moment", "close"]
    assert [piece["next"] for _, piece in song] == [piece_id for piece_id, _ in song[1:]] + [""]
    assert {piece["track"] for _, piece in song} == {"song/%s/0" % asset.id}
    for _, piece in song:
        assert (piece["role"], piece["serves"], piece["moods"], piece["light"]) == ("wander", [0, 1], ["haunted"], False)
        assert piece["follow"] == {"rhythm": ["texture", "lead"]}, "the band stands in for the tune and the drone"
        assert (piece["bar_frames"], piece["frames"], piece["windows"], piece["tonic"]) == (BAR, 4 * BAR, 1, "D minor")
    assert song[2][1]["floor"] == {"drums": 0.6, "bass": 0.5} and song[1][1]["floor"] == {"drums": 0.3}
    assert song[0][1]["floor"] == {} and song[5][1]["floor"] == {} and song[8][1]["floor"] == {}
    # The fight and the calm part are short tracks of their own, for their own moments.
    _, fight = found["song/%s/36" % asset.id]
    assert (fight["role"], fight["serves"], fight["story"], fight["next"]) == ("battle", [2], "", "")
    assert fight["floor"] == {"drums": 1.0, "bass": 1.0} and fight["track"] == "song/%s/36" % asset.id
    _, ember = found["song/%s/40" % asset.id]
    assert (ember["role"], ember["serves"], ember["light"], ember["floor"]) == ("ember", [0, 1], True, {})


def test_riffs_themes_and_fights_that_follow_each_other_are_tracks(home):
    library, bucket = home
    asset = add(library, DUSKWOOD, SUITE)
    made = songstems.from_songs(library, bucket)
    assert [(track.title, track.role, track.pieces) for track in made] == [
        ("Duskwood 1: Arrival to Wander B", "wander", 3), ("Duskwood 1: Battle E to Battle F", "battle", 2),
        ("Duskwood 1: Boss", "boss", 1), ("Duskwood 1: Storm", "storm", 1), ("Duskwood 1: Night", "night", 1),
        ("Duskwood 1: Depths", "depths", 1)]
    found = by_source(bucket)
    stories = [found["song/%s/%d" % (asset.id, bar)][1]["story"] for bar in (0, 4, 8)]
    assert stories == ["open", "theme", "theme"]
    assert found["song/%s/12" % asset.id][1]["next"] == found["song/%s/16" % asset.id][0], "two fights in a row are one track"
    assert [found["song/%s/%d" % (asset.id, bar)][1]["serves"] for bar in (12, 20, 24, 28, 32)] == [[2], [2], [1, 2], [0, 1], [0, 1]]
    assert found["song/%s/24" % asset.id][1]["floor"] == {"drums": 0.6, "bass": 0.5}, "a storm brings the band in"
    # Riffs with no opening of their own: the first is a story in itself, so the track can be begun with it.
    later = add(library, DUSKWOOD, ("Wander C", "Wander D"), seed=2, set_name="second")
    songstems.from_songs(library, bucket)
    found = by_source(bucket)
    assert [found["song/%s/%d" % (later.id, bar)][1]["story"] for bar in (0, 4)] == ["", "theme"]
    assert found["song/%s/0" % later.id][1]["title"] == "Duskwood 2: Wander C"


def test_the_parts_are_the_songs_layers_as_they_are_with_what_the_song_went_on_to(home, monkeypatch):
    monkeypatch.setattr(forever, "POST_S", 2.0)
    library, bucket = home
    asset = add(library, DUSKWOOD, SONG)
    songstems.from_songs(library, bucket)
    piece_id, piece = by_source(bucket)["song/%s/4" % asset.id]               # the Verse: bars 4 to 8
    parts = {clip.channel: clip for clip in bucket.clips if clip.piece == piece_id}
    assert set(parts) == {"rhythm", "drums", "bass"} and {clip.tier for clip in parts.values()} == {1}
    for layer, channel in songstems.CHANNEL.items():
        clip = parts[channel]
        assert (clip.frames, clip.post, clip.bars, clip.order) == (4 * BAR, 2 * RATE, 4, 0)
        kept = np.frombuffer(bucket.samples(clip.id), dtype="<i2")
        assert len(kept) == (clip.frames + clip.post) * 2, "the file holds the stretch and what the song went on to"
        assert kept.tobytes() == library.samples(asset, layer, 4 * BAR, 8 * BAR + 2 * RATE), "the layer exactly as it is on disk"
    # The last section of the song has nothing after it.
    last_id, _ = by_source(bucket)["song/%s/40" % asset.id]
    assert {clip.post for clip in bucket.clips if clip.piece == last_id} == {0}
    # One gain for the whole song: its loudest section, the three layers together, is a little
    # over the bucket's usual level, and the quiet sections stay as much quieter as they were.
    gains = {clip.gain_db for clip in bucket.clips if clip.piece}
    assert len(gains) == 1
    layers = [np.frombuffer(library.samples(asset, layer, 0, asset.frames), dtype="<i2").reshape(-1, 2) / 32768.0
              for layer in songstems.CHANNEL]
    mix = sum(layers)
    from freerock import analysis
    loudest = max(analysis.loudness_lufs(mix[section.start:section.end], RATE) for section in asset.sections)
    assert loudest + gains.pop() == pytest.approx(forever.PIECE_LEVEL + 1.0, abs=0.02)
    described = bucket.describe()
    assert set(described["pieces"]) == set(bucket.pieces) and described["pieces"][piece_id]["story"] == "theme"
    told = next(clip for clip in described["clips"] if clip["id"] == parts["drums"].id)
    assert (told["piece"], told["order"], told["post"], told["frames"]) == (piece_id, 0, 2 * RATE, 4 * BAR)


def test_a_loud_song_is_never_taken_past_full_scale(home):
    library, bucket = home
    add(library, DUSKWOOD, ("Wander C", "Wander D"), level=1.0)               # as loud as noise gets: its peaks are clipped
    songstems.from_songs(library, bucket)
    gain = {clip.gain_db for clip in bucket.clips if clip.piece}.pop()
    loudest = 0.0
    for piece_id in bucket.pieces:
        whole = sum(np.frombuffer(bucket.samples(clip.id), dtype="<i2").reshape(-1, 2) / 32768.0
                    for clip in bucket.clips if clip.piece == piece_id)
        loudest = max(loudest, float(np.abs(whole).max()))
    assert loudest * 10 ** (gain / 20.0) <= 10 ** (-1.0 / 20.0) + 1e-3


def test_a_long_section_is_kept_in_stretches_of_whole_bars(home, monkeypatch):
    monkeypatch.setattr(forever, "WINDOW_S", 4.0)                              # two bars and a bit at this tempo
    library, bucket = home
    asset = add(library, DUSKWOOD, ("Wander C", "Wander D"))
    songstems.from_songs(library, bucket)
    piece_id, piece = by_source(bucket)["song/%s/0" % asset.id]
    assert (piece["bars"], piece["windows"]) == (2, 2), "the largest whole number of bars that is not over the limit"
    drums = sorted((clip for clip in bucket.clips if clip.piece == piece_id and clip.channel == "drums"), key=lambda c: c.order)
    assert [(clip.order, clip.frames, clip.bars) for clip in drums] == [(0, 2 * BAR, 2), (1, 2 * BAR, 2)]


def test_only_the_buckets_style_is_cut_bans_stick_and_a_second_run_adds_nothing(home):
    library, bucket = home
    add(library, DUSKWOOD, ("Wander C", "Wander D"))
    banned = add(library, DUSKWOOD, ("Wander E", "Wander F"), seed=2)
    library.mark(banned.id, banned=True)
    add(library, DUSKWOOD, ("Wander G", "Wander H"), genre="warcraft", seed=3)
    made = songstems.from_songs(library, bucket)
    assert [(track.title, track.added) for track in made] == [("Duskwood 1: Wander C to Wander D", 2)]
    assert len(bucket.pieces) == 2
    # Again: nothing new. And a piece that has been banned since is not put back.
    piece_id = next(iter(bucket.pieces))
    bucket.mark([next(clip.id for clip in bucket.clips if clip.piece == piece_id)], banned=True)
    again = songstems.from_songs(library, forever.Bucket(bucket.root, "duskwood", "knight", 80, "D minor"))
    assert [(track.pieces, track.added) for track in again] == [(2, 0)]
    fresh = forever.Bucket(bucket.root, "duskwood", "knight", 80, "D minor")
    assert len(fresh.pieces) == 2 and len(fresh.live_pieces()) == 1


def test_the_kinds_of_place_come_from_where_a_song_was_made(home):
    library, bucket = home
    add(library, ELWYNN, ("Wander C", "Wander D"))
    add(library, ELWYNN, ("Theme A", "Theme B"), subzone="fargodeep-mine", seed=2, set_name="place")
    tavern = ZoneProfile(key="scarlet-raven-tavern", bpm=160, tonic="A minor", colours=["fiddle reel"])
    add(library, tavern, ("Wander C", "Fight"), seed=3)
    made = {track.title: track for track in songstems.from_songs(library, bucket)}
    assert (made["Elwynn Forest 1: Wander C to Wander D"].moods, made["Elwynn Forest 1: Wander C to Wander D"].light) == (["pastoral"], True)
    mine = made["Fargodeep Mine 1: Theme A to Theme B"]
    assert mine.moods[0] == "infernal" and mine.light is False, "a mine is not a light place, whatever the country round it"
    assert (made["Scarlet Raven Tavern 1: Wander C"].moods, made["Scarlet Raven Tavern 1: Wander C"].light) == (["pastoral"], True)
    # A piece keeps its own key, whatever the bucket's is.
    assert {piece["tonic"] for piece in bucket.pieces.values()} == {"G mixolydian", "A minor"}


# --- the commands ---------------------------------------------------------------------------------

@pytest.fixture
def var(tmp_path, monkeypatch):
    monkeypatch.setattr(musiccli, "_settings", lambda: Settings.load(tmp_path))
    monkeypatch.setattr(pieces, "server_is_up", lambda port: False)
    return tmp_path


def staged_track(var, family="haunted-01", take=1, *, bars=(2, 3), post_s=1.0, hz=220.0, quiet_drums_in=None):
    """A tiny staged track: two parts of a story at two-second bars, a tone for each channel."""
    bar = 2 * RATE
    frames = sum(bars) * bar + int(post_s * RATE)
    time = np.arange(frames) / RATE
    parts = {}
    for index, channel in enumerate(("texture", "lead", "drums")):
        tone = 0.2 * np.sin(2 * np.pi * hz * (index + 1) * time).astype(np.float32)
        if channel == "drums" and quiet_drums_in == 0:
            tone[:bars[0] * bar] = 0.0
        parts[channel] = np.stack([tone, tone], axis=1)
    meta = {"style": "warcraft", "family": family, "take": take, "title": "The Long Dark", "tempo": 120, "beats": 4,
            "bar_frames": bar, "tonic": "D minor", "moods": ["haunted"], "role": "wander", "serves": [0, 1], "light": False,
            "sections": [{"story": "open", "bars": bars[0]}, {"story": "moment", "bars": bars[1]}],
            "floor": {"moment": {"drums": 0.7}}, "follow": {}, "post_s": post_s, "credit": "written here", "seed": 5}
    studio.write_track(studio.stage_root(var, "warcraft") / family / str(take), meta, parts)
    return meta, parts


def test_staged_tracks_are_put_in_the_styles_bucket_once(var, capsys):
    staged_track(var, "haunted-01", 1, quiet_drums_in=0)
    staged_track(var, "haunted-01", 2, hz=330.0)
    # The style has no bucket yet, so one is begun in a place; after that the style has its bucket.
    assert cli.main(["pieces", "add", "warcraft"]) == 1 and "has no bucket yet" in capsys.readouterr().err
    assert cli.main(["pieces", "add", "warcraft", "--zone", "Duskwood"]) == 0
    out = capsys.readouterr().out
    assert "added     haunted-01/1" in out and "added     haunted-01/2" in out
    assert "2 staged tracks for Warcraft: 2 put in warcraft/duskwood now, 0 were there already." in out
    assert "4 written pieces in 2 tracks" in out and "haunted 4" in out and "1 families" in out
    bucket = forever.Bucket(var / "buckets", "duskwood", "warcraft", 80, "D minor")
    first = [piece for piece in bucket.pieces.values() if piece["track"] == "warcraft/haunted-01/1"]
    opening, moment = sorted(first, key=lambda piece: piece["story"] != "open")
    assert (opening["story"], moment["story"], moment["floor"], opening["floor"]) == ("open", "moment", {"drums": 0.7}, {})
    assert opening["next"] in bucket.pieces and bucket.pieces[opening["next"]] is moment
    assert opening["family"] == moment["family"] == "warcraft/haunted-01"
    # The drums are silent in the opening of the first take, so they have no part in that piece.
    channels = lambda piece: {clip.channel for clip in bucket.clips if bucket.pieces[clip.piece] is piece}
    assert channels(opening) == {"texture", "lead"} and channels(moment) == {"texture", "lead", "drums"}
    # One gain for the track, and each piece's recording is followed by what the track went on to.
    assert len({clip.gain_db for clip in bucket.clips if bucket.pieces[clip.piece] in first}) == 1
    lead = next(clip for clip in bucket.clips if bucket.pieces[clip.piece] is opening and clip.channel == "lead")
    assert (lead.frames, lead.post) == (2 * 2 * RATE, int(forever.POST_S * RATE)), "six seconds of the seven that follow"
    # A second time, nothing is added.
    assert cli.main(["pieces", "add", "warcraft"]) == 0
    assert "0 put in warcraft/duskwood now, 2 were there already" in capsys.readouterr().out
    assert len(forever.Bucket(var / "buckets", "duskwood", "warcraft", 80, "D minor").pieces) == 4


def test_a_staged_track_that_is_not_fit_is_named_and_the_rest_go_in(var, capsys):
    staged_track(var, "haunted-01", 1)
    staged_track(var, "haunted-02", 1)
    folder = studio.stage_root(var, "warcraft") / "haunted-01" / "1"
    audio, _ = soundfile.read(str(folder / "lead.flac"), dtype="float32", always_2d=True)
    soundfile.write(str(folder / "lead.flac"), audio, 44100, format="FLAC", subtype="PCM_16")      # the wrong rate
    assert cli.main(["pieces", "add", "warcraft", "--zone", "Duskwood"]) == 1
    said = capsys.readouterr()
    assert "NOT PUT IN haunted-01/1" in said.err and "44100" in said.err
    assert "1 put in warcraft/duskwood now" in said.out and "1 could not be put in" in said.out


def test_the_songs_command_cuts_the_style_in_force_and_lists_what_it_made(var, capsys):
    library = Library(var / "library")
    add(library, DUSKWOOD, SONG)
    assert cli.main(["pieces", "songs", "--zone", "Duskwood"]) == 0
    out = capsys.readouterr().out
    assert "added     Duskwood 1: Intro to Outro" in out and "9 pieces" in out and "wander" in out and "haunted" in out
    assert "3 tracks cut from the Knight Rock songs on disk: 11 pieces put in knight/duskwood now, 0 were there already." in out
    assert "Knight Rock (knight/duskwood): 11 written pieces in 3 tracks" in out
    assert "battle 1" in out and "ember 1" in out and "wander 9" in out and "light 1, heavy 10" in out
    assert cli.main(["pieces", "songs", "knight"]) == 0
    assert "0 pieces put in knight/duskwood now, 11 were there already" in capsys.readouterr().out
    assert cli.main(["pieces", "list", "knight"]) == 0
    assert "11 written pieces in 3 tracks" in capsys.readouterr().out


def test_nothing_is_written_while_the_server_runs_and_a_style_needs_a_bucket(var, monkeypatch, capsys):
    assert cli.main(["pieces", "list", "house"]) == 1
    assert "has no bucket yet" in capsys.readouterr().err
    monkeypatch.setattr(pieces, "server_is_up", lambda port: True)
    assert cli.main(["pieces", "songs", "knight", "--zone", "Duskwood"]) == 1
    assert cli.main(["pieces", "add", "knight", "--zone", "Duskwood"]) == 1
    assert capsys.readouterr().err.count("Stop it first") == 2
    assert cli.main(["pieces", "list", "knight", "--zone", "Duskwood"]) == 0, "listing writes nothing, so it may be done at any time"
    # A style with no bucket can be given one, begun in a place.
    monkeypatch.setattr(pieces, "server_is_up", lambda port: False)
    assert cli.main(["pieces", "add", "house", "--zone", "Elwynn Forest"]) == 0
    assert "0 staged tracks for Progressive House" in capsys.readouterr().out


def test_a_place_is_named_as_it_is_spelt():
    assert songstems.place_name("duskwood") == "Duskwood"
    assert songstems.place_name("un-goro-crater") == "Un'Goro Crater", "a zone the atlas knows keeps its own spelling"
    assert songstems.place_name("the-hall-of-thanes") == "The Hall of Thanes"
    assert songstems.place_name("anvilmar-s-rest") == "Anvilmar's Rest"
