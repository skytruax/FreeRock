# The instruments the studio plays

The studio (`app/freerock/studio/`) writes music as notes and needs something to play them.
Nothing here is installed in the usual way, because that needs the administrator's password:
everything is fetched and unpacked under `var/tools/`, which git does not keep. This is how to
put it back on a new machine.

## What played the first orchestra (not used now)

On 2026-11-15 and 16 the orchestra was played by FluidSynth 2.4.8 (LGPL 2.1) through the MuseScore
General and FluidR3 General MIDI SoundFonts (both MIT), unpacked from Ubuntu's archive into
`var/tools/fluid`. Its renders were turned down by ear on 2026-11-16, and the code that drove it
went on 2026-11-17. The unpacked copy is kept with the other tools.

## REAPER (the studio's desk)

REAPER 7.86 is unpacked under `var/tools/reaper` (the Linux tarball from reaper.fm) and keeps its
settings beside itself, so it is the studio's own copy. The studio runs it without a window on
a virtual display (Xvfb), either with a Lua script or as `reaper -renderproject file.rpp`
(`app/freerock/studio/reaper.py`). `tools/reaper.sh` opens the same REAPER with its window, by
itself or on a track's project. REAPER is free to try for sixty days and then needs a licence
(60 US dollars for personal use).

## The plug-ins REAPER loads

From Ubuntu's archive, installed in the usual way (this needs the administrator):

    sudo apt install dragonfly-reverb-lv2 lsp-plugins-lv2 x42-plugins calf-plugins zam-plugins \
        tap-plugins guitarix-lv2 drumgizmo avldrums.lv2 zynaddsubfx-lv2 yoshimi geonkick \
        dpf-plugins-lv2 setbfree mda-lv2 swh-lv2 ir.lv2 synthv1-lv2 padthv1-lv2 samplv1-lv2 \
        drumkv1-lv2 amsynth eq10q fil-plugins fomp rubberband-lv2

`reaper.configure()` writes the system's plug-in folders into REAPER's settings, and
`desk.catalogue()` loads every LV2 plug-in once and keeps its settings in
`var/reaper/catalogue.json`; `desk.lv2("Dragonfly Hall Reverb", decay=2.1)` writes one into a
project. Sixteen of the 669 cannot be loaded and are marked so there. The TAP plug-ins are
LADSPA only, which REAPER does not load.

| What | Used for | Licence |
|---|---|---|
| Dragonfly Reverb (hall, room, early reflections) | The hall, the drums' room, seats on the stage | GPL 3 |
| x42 (fil4 equaliser, dpl limiter) | Equalising every channel, the ceiling over the drums | GPL 2+ |
| Calf (multi chorus, tape simulator, transient designer, stereo tools, vintage delay) | Ensemble, warmth, punch, width, echoes | LGPL 2+ |
| SC4 (Steve Harris, swh) | Compression | GPL 2+ |
| ZynAddSubFX with its banks as LV2 presets | The choir | GPL 2+ |
| AVL Drumkits (Robin Gareus's plug-in; Glen MacArthur's recordings): Red Zeppelin, Black Pearl, Buskman's Holiday Percussion | The war drums, the deep stroke, the hand drums, a band's kit | plug-in GPL 2+, recordings CC BY-SA 3.0 |
| Calf compressor (with its mix part-way) | The drums' parallel compression | LGPL 2+ |
| The studio's own equaliser (`app/freerock/studio/jsfx/channel_eq`) | Every channel: low cut, bands, shelves | FreeRock's own |

Not from the archive, kept under `var/tools`:

- **Surge XT 1.3.4** (GPL 3): the Linux tarball from github.com/surge-synthesizer/releases-xt,
  unpacked to `var/tools/surge`.
- **sfizz 1.2.3** (BSD 2-clause), the sampler: built from the source tarball of
  github.com/sfztools/sfizz-ui, since nobody ships a Linux build. It has to be built in a folder
  whose path has no space in it (the linker is handed a path it does not quote), and gcc 15
  needs two warnings turned off for the window toolkit it bundles:

      sudo apt install cmake libx11-dev libx11-xcb-dev libxcb-util-dev libxcb-cursor-dev \
          libxcb-xkb-dev libxcb-keysyms1-dev libxkbcommon-dev libxkbcommon-x11-dev \
          libfontconfig-dev libcairo2-dev libfreetype-dev libpango1.0-dev libsndfile1-dev
      cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DPLUGIN_LV2=ON -DPLUGIN_VST3=ON \
          -DSFIZZ_JACK=OFF -DSFIZZ_RENDER=OFF -DSFIZZ_SHARED=OFF -DENABLE_LTO=OFF \
          -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DCMAKE_CXX_FLAGS="-Wno-template-body -fpermissive"
      cmake --build build -j 12
      cp -r build/sfizz.lv2 <repo>/var/tools/plugins/lv2/
      cp -r build/sfizz.vst3 <repo>/var/tools/plugins/vst3/

  Two things found the hard way: asked for more than its usual 64 voices it stops REAPER's
  render dead, and rendering it uses its costliest resampling unless told otherwise (the desk
  sets 3 of 10).

## MuseScore and its Muse Sounds (the orchestra)

Since the evening of 2026-11-16 the orchestra is played by MuseScore Studio 4.7.7 (GPL 3,
the AppImage from github.com/musescore/MuseScore, unpacked at `var/tools/musescore`) with
Muse Sounds: recorded instruments that MuseScore's makers give away with it. They are fetched
by the Muse Sounds Manager (`https://muse-cdn.com/Muse_Sounds_Manager_x64.deb`, installed
with `sudo apt install`) into `~/Muse Sounds`, which is a link to `musesounds` on the assets
drive: Muse Strings, Brass, Woodwinds, Percussion, Choir, Harp, Keys, Guitars Vol. 1,
Drumline, Handbells and Music Box, 117 instruments, 16 GB. The sampler itself is
`~/.local/share/MuseSampler/lib/libMuseSamplerCoreLib.so`. Muse Sounds are free of charge;
their licence terms have not been read here, which is fine for music that is only listened
to at home and has to be settled before anything is shared. The paid packs sold on MuseHub
(Spitfire and others) install only through MuseHub on Windows and macOS.

`app/freerock/studio/muse.py` says how a voice becomes a score and how a part is given a
named sound.

## The recordings the sampler plays

Under `var/samples` (on the assets drive), each fetched from GitHub as a tarball of its main branch:

| Folder | What | From | Licence |
|---|---|---|---|
| `vsco2` | Orchestra: string sections, solo violin and bass, woodwind, brass, organ, percussion | sgossner/VSCO-2-CE | CC0 |
| `vcsl` | Recorders, organs, harps, zithers, pianos, mallets, bells, timpani, world percussion | sgossner/VCSL | CC0 |
| `big-rusty-drums` | Very large drums: 24-inch kick, a 22-inch kick hung as a tom, 18-inch floor tom | sfzinstruments/karoryfer.big-rusty-drums | CC0 |
| `swirly-drums`, `black-and-green-guitars`, `pastabass`, `growlybass`, `meatbass`, `emilyguitar`, `shinyguitar` | A drum kit, electric guitars recorded clean, basses, guitars (for the band; not used yet) | sfzinstruments/karoryfer.* | CC0 |
| `salamander-piano` | A grand piano (not used yet) | sfzinstruments/SalamanderGrandPiano | CC BY 3.0 (Alexander Holm) |
| `tinysol` | Horn, trumpet, trombone, tuba, clarinet and bassoon (and flute, oboe, saxophone and solo strings, not used yet): every semitone played soft, medium and loud, one close microphone | TinySOL, zenodo.org/records/3685367 (Carmine Emanuele Cella, Daniele Ghisi, Vincent Lostanlen, Fabien Lévy, Joshua Fineberg and Yan Maresz; recorded at IRCAM) | CC BY 4.0 on the download page. IRCAM's paper on the same recordings says "free for non-commercial usage": fine for music that is only listened to at home, to be settled before anything is shared |
| `naked-drums` | A drum kit with five toms, ten takes of every stroke and a far-room microphone: its bass drum's inside, outside and room microphones are the kick (`sounds.NAKED`); the rest is not used yet | sfzinstruments/WilkinsonAudio.NakedDrums | CC BY 4.0 (Wilkinson Audio) |

`studio/samples.py` reads a folder of single notes into zones (measuring each recording's pitch),
`studio/sfz.py` writes the sampler's instrument file for it into `var/reaper/sfz`, and
`studio/sounds.py` says which of them play each instrument the writers name.

## The dance music's drums

The House tracks (`studio/club.py`) take their drums from recordings of a TR-8 drum machine,
played by sfizz: `var/tools/drums/mck/`, from github.com/MckAudio/MckSamplePacks, CC0.
(`var/tools/drums/fischer808/`, from github.com/tidalcycles/sounds-tr808-fischer, CC0, was
fetched too and is not used.) The house writer (`studio/house.py`) still runs the studio's own
synthesiser (`studio/synth.py`) while it writes, which is why House needs numba:
`uv run --no-sync --with numba ...`.

## The real scores

Public-domain orchestral scores were fetched into `var/scores/` and arranged for the General MIDI
orchestra; with that orchestra the arranging went too (2026-11-17). The scores are still read by
`tools/orchestra_study.py`, which measures how real orchestral music moves (how often the bass
repeats, how many instruments play at once) for the writers to be held against.
