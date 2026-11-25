# The instruments the studio plays

The studio (`app/freerock/studio/`) writes music as notes and needs something to play them.
Nothing here is installed in the usual way, because that needs the administrator's password:
everything is fetched and unpacked under `var/tools/`, which git does not keep. This is how to
put it back on a new machine.

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
`~/.local/share/MuseSampler/lib/libMuseSamplerCoreLib.so`. Muse Sounds are free of charge and
licensed for making music: what is made with them is its maker's (musescore.org/en/node/344132);
the sounds themselves may not be passed on, and nothing here does. The paid packs sold on MuseHub
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
| `tinysol` | Horn, trumpet, trombone, tuba, clarinet, bassoon and accordion (and flute, oboe, saxophone and solo strings, not used yet): every semitone played soft, medium and loud, one close microphone | TinySOL, zenodo.org/records/3685367 (Carmine Emanuele Cella, Daniele Ghisi, Vincent Lostanlen, Fabien Lévy, Joshua Fineberg and Yan Maresz; recorded at IRCAM) | CC BY 4.0 (zenodo.org/records/3685367; the "free for non-commercial usage" wording seen beside it belongs to IRCAM's other set, OrchideaSOL) |
| `freepats/Bagpipe` | A bagpipe in G (designed by Rémy Dubois, built by Olle Geris), its chanter from F4 to G5, two takes a note, 28 to 67 cents under A 440 (each note tuned by the sampler); plays the bagpipe's tunes since 2026-11-18 (chosen by ear; held, its upper middle stood over its body, so drones stay MuseScore's english horn: docs/songwriting.md, 8.8); the drones on G2 and G3 are not used. Recorded in 2020 by Gilles Sadowski about 80 cm from one microphone. Its LICENSE.txt and README.txt are kept beside it | freepats.zenvoid.org/Ethnic/bagpipe.html (github.com/freepats/bagpipe, cloned 2026-11-18) | CC0 |
| `naked-drums` | A drum kit with five toms, ten takes of every stroke and a far-room microphone: its bass drum's inside, outside and room microphones are the kick (`sounds.NAKED`); the rest is not used yet | sfzinstruments/WilkinsonAudio.NakedDrums | CC BY 4.0 (Wilkinson Audio) |

Found on 2026-11-24 ("find more instruments!"), each cloned from github.com/sfzinstruments into a folder of its own under
`var/samples/found` (no history, no hooks, nothing in them run; a repository whose attributes rewrite line endings is checked
out with `* -text` in `.git/info/attributes`, or every recording in it is broken: the black and green guitars' were). Their
licence files are kept beside them. Those with a program of their own are played by it (`studio/programs.py`); single notes are
cut to begin at their stroke, named by note, strength and turn, under `var/samples/merged`.

| Folder | What | Plays | Licence |
|---|---|---|---|
| `aliexpress-erhu` | A cheap erhu played by a violinist, close, in stereo | erhu, wired erhu | CC0 |
| `cithara-barbarica` | A Germanic lyre of ten metal strings: fingers, nails | lyre | CC0 |
| `Karoryfer.HorsePulse` | A bass tagelharpa plucked (Bragi's Workshop's) | tagelharpa, riff harpa | CC0 |
| `karoryfer.bear-sax` | A 1926 Conn baritone saxophone: growl, subtone, short notes | growl sax, subtone sax, riff sax | CC0 |
| `karoryfer.weresax` | An alto saxophone; its notes as an accordion's reeds | saxcordion | CC0 |
| `karoryfer.war-tuba` | A street band's tuba (Jakub Lewicki) | war tuba | CC0 |
| `karoryfer.string-cyborgs` | A cello's and a double bass's bowed notes as a synthesiser's oscillators | heart lead, pluck, stab and pad, iron bass | CC0 |
| `karoryfer.growlybass` | A jazz bass with new roundwounds | growly bass | CC0 |
| `karoryfer.black-and-green-guitars` | A Hofner Club and a Gretsch Anniversary, straight from their jacks (Brian Wood) | hollow guitar, hollow muted, hollow lead | CC0 |
| `karoryfer.shinyguitar` | An archtop guitar's magnetic pickup | archtop guitar | CC0 |
| `ganjo` | A six-string banjo (itsclipping) | guitar banjo | CC0 |
| `legato_vocal_tutorial` | A bass voice's "a", sliding from note to note (from Hadzi-Fia) | bass voice (not given to anyone yet: two of its notes are a third of a semitone out) | CC0 |
| `DrumGizmo.MuldjordKit` | Lars Muldjord's Tama Superstar, sixteen microphones to a stroke | kit metal | CC BY 4.0 (Lars Muldjord, DrumGizmo; mapped by kinwie) |
| `virtuosity_drums` | A Boston shop's jazz kit (Virtuosity Musical Instruments; Austin McMahon), six microphones to a stroke, mixed to one, and through its worn vintage microphone | kit club, kit lofi | CC0 |
| `karoryfer.unruly-drums` | A kit whose every drum is a snare, the kick too | kit unruly | CC0 |
| `karoryfer-bigcat.cello`, `karoryfer.emilyguitar`, `karoryfer.cowsynth`, `karoryfer.caveman-cosmonaut`, `karoryfer.squidpipes`, `jlearman.SteelDrum`, `body_percussion`, `zamenhof_stickmusterstuch_error`, `karoryfer.272-merry-orks`, `karoryfer.pastabass`, `karoryfer.meatbass`, `karoryfer.big-little-bass`, `karoryfer.ergo`, `dsmolken.double-bass`, `karoryfer.gogodze-phu-vol-i`, `karoryfer.gogodze-phu-vol-ii` | A cello, a clean guitar, strange synths, a squid's bagpipes, a steel drum, stomps and claps, glitches, a death metal choir, basses, Ghanaian drums | nothing yet | CC0 |

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

Public-domain orchestral scores are kept in `var/scores/`. `tools/orchestra_study.py` reads them to
measure how real orchestral music moves (how often the bass repeats, how many instruments play at
once), for the writers to be held against.
