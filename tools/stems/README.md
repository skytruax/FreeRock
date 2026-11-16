# The instruments the studio plays

The studio (`app/freerock/studio/`) writes music as notes and needs something to play them.
Nothing here is installed in the usual way, because that needs the administrator's password:
everything is fetched and unpacked under `var/tools/`, which git does not keep. This is how to
put it back on a new machine.

## FluidSynth and its SoundFonts (the orchestra)

FluidSynth plays a MIDI file through sampled instruments. From Ubuntu's own archive, unpacked
into a folder instead of installed:

    mkdir -p var/tools/debs var/tools/fluid && cd var/tools/debs
    apt download fluidsynth=2.4.8+dfsg-1 libfluidsynth3=2.4.8+dfsg-1 \
        musescore-general-soundfont-lossless fluid-soundfont-gm
    for deb in *.deb; do dpkg -x "$deb" ../fluid; done

The version is named because without it apt chooses the Ubuntu Pro build, which this machine
may not fetch. `studio/fluid.py` runs `var/tools/fluid/usr/bin/fluidsynth` with
`LD_LIBRARY_PATH` set to the unpacked libraries, and plays
`usr/share/sounds/sf2/MuseScore_General_Full.sf2`.

| What | Licence |
|---|---|
| FluidSynth 2.4.8 | LGPL 2.1: run as a program beside FreeRock, not built into it |
| MuseScore General SoundFont (S. Christian Collins) | MIT |
| FluidR3 GM SoundFont (Frank Wen) | MIT |

How loud each instrument of the SoundFont is, and which strokes each drum kit has, was measured
on 2026-11-15 by playing each alone; the numbers are in `studio/orchestra.py` (`LOUD`, `KITS`).
The marching kit has only a handful of strokes and is not used.

## REAPER (tried, not used by the studio yet)

`reaper_try.py`, `reaper_phrase_test.lua` and `xkeys.py` are the experiment that showed REAPER
7.86 renders stems on this machine with no window: it runs on a screen nobody sees (Xvfb), a
Lua script builds a project and renders it, and `xkeys.py` answers its first-run question.
Three synth stems of 34.9 s rendered in a third of a second and passed the bucket's checks for
tempo, beat and tuning. REAPER is free to try for sixty days and then needs a licence (60 US
dollars for personal use). The studio does not depend on it: the orchestra is FluidSynth and
the dance music is our own synthesiser.

## Everything else

The house writer keeps its drum recordings under `var/tools/drums/` and the real
scores are fetched into `var/scores/`; `studio/house.py` and `studio/scores.py` say from where
and under what licence.
