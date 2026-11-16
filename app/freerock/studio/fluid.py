"""Playing a MIDI file through sampled instruments: FluidSynth and a SoundFont.

FluidSynth is not installed on this machine in the usual way (that needs the administrator). It
was fetched from Ubuntu's archive and unpacked under var/tools/fluid, with two SoundFonts:
MuseScore_General_Full.sf2 (a full General MIDI set, MIT licence) and FluidR3_GM.sf2 (MIT).
tools/stems/README says how.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import numpy as np
import soundfile

RATE = 48000
HOME = Path(__file__).resolve().parents[3] / "var" / "tools" / "fluid"
FONT = HOME / "usr" / "share" / "sounds" / "sf2" / "MuseScore_General_Full.sf2"


def render(midi: Path, wav: Path, *, gain: float = 2.0, font: Path = FONT, reverb: bool = False) -> np.ndarray:
    """Plays a MIDI file to a WAV file as fast as the machine will go, and returns the audio
    (stereo, float: it may pass full scale, and whoever asked brings it down). The instrument's
    own echo is off unless asked for: the studio adds one room to everything, so that the whole
    band stands in the same hall."""
    binary = HOME / "usr" / "bin" / "fluidsynth"
    if not binary.is_file() or not font.is_file():
        raise FileNotFoundError("FluidSynth or its SoundFont is not under %s" % HOME)
    env = dict(os.environ, LD_LIBRARY_PATH=str(HOME / "usr" / "lib" / "x86_64-linux-gnu"))
    command = [str(binary), "-ni", "-q", "-F", str(wav), "-T", "wav", "-O", "float", "-r", str(RATE), "-g", "%.3f" % gain,
               "-o", "synth.polyphony=1024", "-o", "synth.reverb.active=%d" % (1 if reverb else 0),
               "-o", "synth.chorus.active=0", "-o", "synth.cpu-cores=1", str(font), str(midi)]
    done = subprocess.run(command, env=env, capture_output=True, text=True)
    if done.returncode != 0 or not Path(wav).is_file():
        raise RuntimeError("FluidSynth could not play %s: %s" % (midi, (done.stderr or done.stdout).strip()[-600:]))
    audio, rate = soundfile.read(str(wav), dtype="float32", always_2d=True)
    if rate != RATE:
        raise RuntimeError("FluidSynth wrote %d Hz, not %d" % (rate, RATE))
    return audio
