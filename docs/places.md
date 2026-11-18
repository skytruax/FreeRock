# Places and moments: what plays where

Every place and moment the game tells FreeRock about, what the director makes of it, and what
music there is for it. Counts are families (a family is one piece's changes, key and tempo,
heard as two or three takes) in `studio/build.plan()`; "takes" are what can be rendered.
Written 2026-11-16, night, for "Dont forget caves inns pvp ect you make a list"; corrected 2026-11-17 against the
code. How each signal moves each channel is in `docs/signals-and-channels.md`.

## The places (`director.PLACES`)

| In the game | How it is told | Place | Takes turns with | Warcraft | Knight Rock | House |
|---|---|---|---|---|---|---|
| Walking about outdoors, by day | the default | wander | (in a dungeon: depths; lingering: ember) | 168 families, 420 takes | 34 / 85 | by kind of place |
| Out of doors at night | `IsDayTime()` false, not in a dungeon | night (walking music counts 0.12 against itself) | wander, and ember when lingering | 30 / 60 | 4 / 8 (night watch, midnight ride) | night palettes |
| A cave, a mine, a crypt, a building (a second inside) | `IsIndoors()`, not resting, not in a dungeon (a battleground's buildings count) | depths | wander | 28 / 56 | 6 / 12 (deep mine, glow cave, low tunnel) | depths palettes |
| An inn (resting under a roof) | resting and indoors | ember, 4 dB down, no bass | wander | 22 / 44 | 6 / 12 (tavern rock, barroom blues, dwarf hall) | ember palettes |
| A town, a city, an Alliance base (resting out of doors) | resting and not indoors | town | wander | 4 / 12 (alliance town, town square) | none: walking music | 2 (lanterns on the square, harbour lights) |
| A battleground or an arena | instance of kind battleground or arena | battleground, through its fights and deaths | wander | 4 / 12 (battleground, siege line) | none: battle music | 2 (hold the line, capture the flag) |
| A dungeon or a raid | instance of kind party, raid or scenario | wander | depths | walking and cave music of the zone's kind | same | same |
| A dungeon boss | `ENCOUNTER_START` | boss | battle | 16 / 32 | 2 / 4 | moment |
| The boss is dead, the fight is not | encounter over, still in combat | battle | storm, boss | 8 / 16 | 4 / 8 | moment |
| A fight in the open | combat (world PvP is not told apart) | the same piece: its drums and bass come up to full; its parts stay as they are (a piece has one strength) | | (every piece) | | |
| After a fight | combat over: held 3 to 13 s, then easing back | the same piece; after a boss fight of 10 s or more, 8 s of ember (the afterglow) | | ember | ember | ember |
| Camping: standing 45 s out of doors (waiting on a spawn, a rare, a friend) | still for 45 s, not on a flight path, not in a dungeon, a cave, an inn or a town, no fight | camp | wander, ember; night at night | 20 / 40 | 4 / 8 (campfire, road camp) | 3 (embers under stars, the long wait, heat haze) |
| A rain storm that has set in, out of doors (it changes the song) | weather rain at storm strength (0.6) for 4 s, over when under 0.4 for 20 s | storm | wander | 14 / 28 (tempest, blizzard, sea storm, whiteout, field storm, monsoon, witch storm) | 4 / 8 (storm rider, downpour run) | storm |
| Full tilt (a long ride, rolling from pull to pull) | the drive rule | storm | wander | storm | storm | storm |
| Dead, a ghost | dead flag | ember, filtered, slow and far | wander | ember | ember | ember |

## The tints (on top of whatever plays)

| In the game | What happens |
|---|---|
| Cave or building | low-pass 2.5 kHz, a large room |
| Under water | low-pass 500 Hz, fast fade |
| Rain | more room; drums at steady rain; a storm brings the whole band |
| Snow | low-pass 6 kHz, wide room, drums down |
| Sandstorm | narrow and gritty, by strength |
| Night | low-pass 3.8 kHz, a little room, 1 dB down, drums ×0.7, the drums and bass floors held to 75% |
| Inn | 4 dB down, no bass |
| Flight path | high-pass 150 Hz, airy, no bass |
| Stealth | the bass line alone with quiet drums |
| Mounted (moving) | the intensity rises from 0.60 to 0.75 over 25 s: drums and bass up; no change of tone |
| Standing still | the bed (pads and accompaniment) to 85%; lingering in one spot 65% |
| Loading screen, cinematic | ducked, or out |

## Ground (settings) and light (shade)

The place's ground comes from its name, the zone's name or the zone's profile (`atlas.setting_for`):
graves, sacred, fort, works, settlement, road, water, heights, woods, fields, wastes, ruins. Its
shade runs from -3 (grim) to 3 (radiant): from the zone's profile and the place's own words, 1.5
darker at night, darker in rain and under rock. A piece's shade is its mode (lydian and major
brightest, phrygian and locrian darkest), a step up for a light piece and half a step down for a
heavy one, and a lean from the kind of place it was written for.

Walking music (Warcraft), families by kind of place and ground:

```
grave sacre  fort works settl  road water heigh woods field waste ruins
pastoral     .     6     2     .    14     8    14     8     8    26     .     4
highland     2     4     4     2     4     8     8    36     6    10     2     2
haunted     12     8     .     .     4     2    12     6    14     6     4    16
desert       2     2     .     .     8     4     2     2     .     2    12     2
jungle       .     2     .     .     2     .    10     2    18     2     2     4
infernal     .     2     .     6     4     2     .     2     .     .     6     .
regal        .     8    10     4    14     4     2     2     .     2     .     2
mystic       .    16     .     .     2     .    14     4    12     .     2     6
marsh        .     .     .     .     .     .    16     .     8     2     .     6
coast        .     .     .     .     6     2    12     4     .     .     .     2
frozen       2     2     2     2     .     2     2    20     4     2     2     2
```

Walking music (Warcraft), families by kind of place and shade:

```
            -3   -2   -1    0    1    2    3
pastoral    1    4    3    8    3   17   14
highland    2   10    .   10    4    3   11
haunted     5   22    6   12    .    .    1
desert      .    6    .    4    4    4    2
jungle      2    7    3    1    .    7    2
infernal    6    4    2    1    1    .    .
regal       .    2    .    9    2    9    6
mystic      .    4    2    7    4    5   10
marsh       2    3    3    5    .    3    .
coast       .    1    .    4    1    4    2
frozen      .    8    .    4    1    .    7
```

(Both counted again 2026-11-17, evening, from `build.plan()`: a family counts under every kind and ground its
character names.)

## The marsh, the coast and the snowfields

Added 2026-11-17, evening: "tonight make more types or categories of places and thus the tracks that match them and how
they're categorized". The Wetlands, grey and damp, had been heard as a jungle; Dun Morogh's and Winterspring's snow as the
mountains round it; the harbours, bays and islands as plain country by the water.

- **How a place is told** (`kinds.py`): profile words ("swamp", "marsh", "bog", "damp", "murky", "croaking", "heavy air"
  for the marsh; "surf", "shore", "island", "harbour", "beach", "salt air", "concertina" for the coast; "snow", "frozen",
  "icy", "sleigh", "cold", "winter" for the snow), and the beginnings of a place's own name ("Marsh", "Bog", "Mud", "Reed";
  "Harbor", "Bay", "Isle", "Cove", "Dock", "Lighthouse"; "Frost", "Snow", "Ice", "Winter"). A subzone named for a swamp, a
  shore or a snowfield takes that flavour (`atlas.PLACE_WORDS`); a lake or a river stays plain water.
- **Where**: the Wetlands, Swamp of Sorrows and Dustwallow Marsh are marsh; Dun Morogh, Alterac and Winterspring are
  frozen; Zephras Isle, Darkshore and Azshara have the coast as their second kind; Menethil Harbor, Baradin Bay, Booty Bay
  and Auberdine are coast first.
- **Their own music in every moment** ("it only matters if those new categories have different families of songs"): the
  marsh's bog lights and grey fen (walking), frog chorus (night), bog inn, drowned grotto (cave), reed fire (camp) and bog
  beast (boss); the coast's sea breeze and salt road (walking), lighthouse (night), sailors rest (inn), tide cave, driftwood
  fire (camp), sea king (boss) and sea storm; the snow's ice fields and white waste (walking), aurora (night), mead hall
  (inn), ice cave, frost camp, frost wyrm (boss) and whiteout (storm). The player plays a piece written for a place's kind
  first (`forever.js`, `_mood`: 0) before one that only lists it (0.2), so these come first there.
- **Knight Rock's and House's own** ("make sure all genres got the updates around new place categories"): the band's
  bayou boogie (a swamp blues: the lead guitar over a harmonica's chords and a slide), sea dog (a rocking shanty in six-eight)
  and frost hammer (a riff hammered on a drone); House's Bullfrog Bass, Peat Smoke and Reedlight (the marsh: dub bass,
  marimba, a jawbone rattle, drips), Seaspray, Gull's Morning and Breakwater (the coast: harp, strummed strings, the sea) and
  Snowglobe, Ice Bridge and Northern Lights (the snow: bells, glass, wind), on palettes of their own. Each is heard first as
  one take and studied before the rest are made (`docs/songwriting.md`, 8.7).
- **The music besides**: every piece written for all kinds, and older ones that
  suit them: swamp fever, witch hollow, the flooded mill, the misty lake, the drowned bell, the river spirits, the jungle's
  night, the owl wood, the spider den, the glowworm grotto, the lamplit inn, the hearth, the fen fire, the wild hunt and
  the deep tide for the marsh; the sea shanty, the harbour town, the cliffside wind, the moonlit shore, the sea grotto, the
  harbour saloon, the watchfire, the warband and the drowned bell for the coast; the snowfall, the frost giant, the frozen
  lake, the snowbound pines, the frozen cavern, the frost's night, the blizzard, the drinking song, the fireside, the crows'
  rest, the moon peak, the barrow kings, the dwarven hall, the mountain pass and the unquiet dead for the snow. Knight Rock's
  jungle stomp and lantern walk, open road, and mountain stomp; House's River Drums, The Old Swamp, Drowned Halls, Morning on
  the Hill, Glade at Dusk, the High Moor, Stone and Sky and Larks over the Ridge.
- **Where there is little**: the player plays the nearest kinds' pieces there too (marsh: jungle, haunted, mystic; coast:
  pastoral, mystic, regal; frozen: highland, mystic).

## Gaps, and what is being done about them

- **Caves and inns have no ground.** A mine and a crypt chose among all the cave pieces alike.
  The cave and inn pieces now name theirs (old mine and kobold tunnels: works; crypt: graves;
  sea grotto: water; lava tube: wastes; bandit hideout: ruins and road; frozen cavern: heights;
  harbour saloon: water; caravanserai: road and wastes).
- **Night in regal places** has no piece of its own; it borrows pastoral and highland night music.
- **Knight Rock has no town or battleground music** (a decision of 2026-11-16): there its walking
  music plays. House has two families of each since the night of 2026-11-17.
- **Battle music is heard only around dungeon bosses** (a decision of 2026-11-16: no separate fight
  piece except bosses; fights in the open bring up the layers of what is playing).
- **Raids** use the dungeon rule (walking and cave music, boss music at encounters). No raid music
  of its own.
- **Under water and stealth** are tints, not pieces; swimming on the surface and flying change nothing yet.
- **Rendered so far tonight**: see `var/passes/` for each pass's list and log; the coverage queue
  (`var/passes/coverage-warcraft.txt`) renders one take of every night, cave, inn, town and
  battleground family, then walking pieces that fill the grids above.
