"""Puts the suite from experiment 2 into the music library as the first zone's core suite, so the
player has real music to play. Costs nothing; it only reads what the experiment stored.

    cd app && uv run --no-sync python ../tools/spikes/s2_to_library.py
"""
from common import OUT, read_report
from freerock.audio import read_audio
from freerock.composer import core_suite
from freerock.library import Library
from freerock.settings import Settings
from freerock.stems import Layers
from s2_suite import RATE, SEED, ZONE


def main() -> None:
    report = read_report("s2")
    library = Library(Settings().library_dir)
    already = [asset for asset in library.assets(ZONE.key) if asset.song_id == report["delivery"]["song_id"]]
    if already:
        print("already in the library:", already[0].id)
        return
    mix, rate = read_audio(OUT / "s2_suite.flac")
    if rate != RATE:
        raise RuntimeError("The stored suite is at %d Hz, expected %d" % (rate, RATE))
    bed, drums, bass = (read_audio(OUT / ("s2_layer_%s.flac" % name))[0] for name in ("bed", "drums", "bass"))
    layers = Layers(bed=bed, drums=drums, bass=bass, rate=RATE,
                    vocal_leak_db=report["layers"]["vocal_leak_db"],
                    seconds=report["layers"]["seconds_to_split"], model=report["layers"]["model"])
    asset = library.add(zone=ZONE.key, set_name="core", request=core_suite(ZONE, seed=SEED), mix=mix,
                        layers=layers, song_id=report["delivery"]["song_id"],
                        checks={"passes": report["passes"], "vocal_leak_db": report["layers"]["vocal_leak_db"]})
    print("added", asset.id, "to", library.root)
    for section in asset.sections:
        print("  %-9s %-7s %d cells, measured %.1f LUFS, played at %+.1f dB"
              % (section.name, section.role, len(section.cells), section.measured_lufs, section.gain_db))


if __name__ == "__main__":
    main()
