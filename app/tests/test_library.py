"""The library: storing a track, finding it again, and handing stretches of it to the player."""
import numpy as np
import pytest

from freerock.audio import pcm16_to_float
from freerock.composer import ZoneProfile, core_suite
from freerock.composer import fresh_set, second_set
from freerock.library import LAYERS, TARGET_LUFS, Library, merged, role_of
from freerock.stems import Layers

RATE = 48000
ZONE = ZoneProfile(key="elwynn", bpm=120, tonic="G mixolydian", colours=["fiddle"])


def made_up_track(request, seed=4):
    """Noise standing in for music, already split into layers that add up to the mix. Each part is
    a little louder than the last, so the loudness matching has something to do."""
    rng = np.random.default_rng(seed)
    frames = request.parts[-1].end_ms * RATE // 1000
    parts = {}
    for name in LAYERS:
        layer = rng.normal(0, 0.05, (frames, 2)).astype(np.float32)
        for index, part in enumerate(request.parts):
            start, end = part.start_ms * RATE // 1000, part.end_ms * RATE // 1000
            layer[start:end] *= 1.0 + 0.3 * index
        parts[name] = layer
    layers = Layers(bed=parts["bed"], drums=parts["drums"], bass=parts["bass"], rate=RATE,
                    vocal_leak_db=-40.0, seconds=1.0, model="test")
    return layers.mix(), layers


@pytest.fixture
def stored(tmp_path):
    request = core_suite(ZONE, seed=11)
    mix, layers = made_up_track(request)
    library = Library(tmp_path / "library")
    asset = library.add(zone="elwynn", set_name="core", request=request, mix=mix, layers=layers,
                        song_id="song1", checks={"vocal_leak_db": -40.0})
    return library, asset, mix, layers


def test_roles():
    assert [role_of(n) for n in ("Wander A", "Wander G", "Battle", "Battle B", "Ember B", "Depths", "Boss", "Night", "Storm", "Arrival")] \
        == ["wander", "wander", "battle", "battle", "ember", "depths", "boss", "night", "storm", "arrival"]
    with pytest.raises(ValueError):
        role_of("Interlude")


def test_sections_and_cells_sit_on_bar_lines(stored):
    library, asset, mix, _ = stored
    assert asset.bar_frames == 96000 and asset.frames == len(mix) and asset.minutes == pytest.approx(2.8)
    assert [s.name for s in asset.sections] == ["Arrival", "Wander A", "Wander B", "Battle", "Ember", "Depths"]
    assert [len(s.cells) for s in asset.sections] == [1, 4, 4, 4, 4, 4]
    for section in asset.sections:
        assert section.start % asset.bar_frames == 0
        assert section.cells[0].start == section.start and section.cells[-1].end == section.end
        for cell in section.cells:
            assert cell.end - cell.start == 4 * asset.bar_frames
    assert [s.name for s in asset.sections_for("wander")] == ["Wander A", "Wander B"]


def test_each_section_is_brought_to_its_own_loudness(stored):
    _, asset, _, _ = stored
    for section in asset.sections:
        assert section.measured_lufs + section.gain_db == pytest.approx(TARGET_LUFS[section.role], abs=0.02)
    assert asset.section("Battle").measured_lufs > asset.section("Wander A").measured_lufs


def test_it_can_be_found_again_and_marked(stored):
    library, asset, _, _ = stored
    again = Library(library.root)                       # a fresh start reads what is on disk
    assert [a.id for a in again.assets("elwynn")] == [asset.id] and again.assets("westfall") == []
    found = again.get(asset.id)
    assert found.to_json() == asset.to_json() and found.song_id == "song1" and found.seed == 11
    assert again.mark(asset.id, loved=True).loved and Library(library.root).get(asset.id).loved
    with pytest.raises(KeyError):
        again.get("nope")


def test_stored_layers_add_up_to_the_stored_mix(stored):
    library, asset, mix, _ = stored
    cell = asset.section("Wander B").cells[2]
    parts = [np.frombuffer(library.samples(asset, layer, cell.start, cell.end), dtype="<i2").astype(np.int32)
             for layer in LAYERS]
    expected = np.round(np.clip(mix[cell.start:cell.end], -1, 32767 / 32768) * 32768).astype(np.int32).reshape(-1)
    assert np.array_equal(sum(parts), expected)


def test_samples_are_what_was_stored_and_silence_outside(stored):
    library, asset, _, layers = stored
    data = library.samples(asset, "drums", 96000, 96000 + 480)
    assert len(data) == 480 * 2 * 2
    assert np.allclose(pcm16_to_float(data, 2), layers.drums[96000:96000 + 480], atol=1 / 32768)
    before = np.frombuffer(library.samples(asset, "bed", -100, 50), dtype="<i2").reshape(-1, 2)
    assert not before[:100].any() and before[100:].any()
    after = np.frombuffer(library.samples(asset, "bed", asset.frames - 10, asset.frames + 90), dtype="<i2").reshape(-1, 2)
    assert after[:10].any() and not after[10:].any()
    with pytest.raises(KeyError):
        library.samples(asset, "vocals", 0, 10)
    with pytest.raises(ValueError):
        library.samples(asset, "bed", 10, 10)


def test_a_track_of_the_wrong_length_is_refused(tmp_path):
    request = core_suite(ZONE)
    mix, layers = made_up_track(request)
    short = Layers(bed=layers.bed[:-RATE], drums=layers.drums[:-RATE], bass=layers.bass[:-RATE], rate=RATE,
                   vocal_leak_db=-40.0, seconds=1.0, model="test")
    with pytest.raises(ValueError):
        Library(tmp_path).add(zone="elwynn", set_name="core", request=request, mix=mix[:-RATE], layers=short)


def test_a_places_music_is_described_as_one_body_from_several_requests(tmp_path):
    library = Library(tmp_path)
    made = {}
    for name, request in (("fresh", fresh_set(ZONE, seed=3)), ("core", core_suite(ZONE, seed=1)),
                          ("second", second_set(ZONE, seed=2))):
        mix, layers = made_up_track(request)
        made[name] = library.add(zone="elwynn", set_name=name, request=request, mix=mix, layers=layers)
    usable = library.usable("elwynn")
    assert [asset.set for asset in usable] == ["core", "second", "fresh"]     # whatever order they were made in
    view = merged(usable)
    assert view["id"] == "+".join(made[name].id for name in ("core", "second", "fresh"))
    assert view["zone"] == "elwynn" and view["set"] == "core + second + fresh" and view["bar_frames"] == 96000
    assert view["minutes"] == pytest.approx(2.8 + 3.2 + 3.2)
    names = [section["name"] for section in view["sections"]]
    assert names[:6] == ["Arrival", "Wander A", "Wander B", "Battle", "Ember", "Depths"] and "Storm" in names and "Wander G" in names
    by_name = {section["name"]: section for section in view["sections"]}
    assert by_name["Wander A"]["asset_id"] == made["core"].id and by_name["Boss"]["asset_id"] == made["second"].id
    assert by_name["Boss"]["cells"][0] == {"start": by_name["Boss"]["start"], "end": by_name["Boss"]["start"] + 4 * 96000}
    with pytest.raises(ValueError):
        merged([])


def test_banned_and_retired_music_is_kept_but_not_played(stored):
    library, asset, _, _ = stored
    assert [a.id for a in library.usable()] == [asset.id]
    assert not library.mark(asset.id, retired=True).usable and library.usable() == []
    assert [a.id for a in library.assets()] == [asset.id] and Library(library.root).get(asset.id).retired
    library.mark(asset.id, retired=False, banned=True)
    assert library.usable() == [] and library.get(asset.id).banned and not library.get(asset.id).retired
