# Places and moments: what plays where

Every place and moment the game tells FreeRock about, what the director makes of it, and what
music there is for it. Counts are families (a family is one piece's changes, key and tempo,
heard as two or three takes) in `studio/build.plan()`; "takes" are what can be rendered.
Written 2026-11-16, night, for "Dont forget caves inns pvp ect you make a list"; corrected 2026-11-17 against the
code. How each signal moves each channel is in `docs/signals-and-channels.md`.

## The places (`director.PLACES`)

| In the game | How it is told | Place | Takes turns with | Warcraft | Knight Rock | House |
|---|---|---|---|---|---|---|
| Walking about outdoors, by day | the default | wander | (in a dungeon: depths; lingering: ember) | 156 families, 390 takes | 20 / 50 | by kind of place |
| Out of doors at night | `IsDayTime()` false, not in a dungeon | night (walking music counts 0.12 against itself) | wander, and ember when lingering | 24 / 48 | 2 / 4 | night palettes |
| A cave, a mine, a crypt, a building (a second inside) | `IsIndoors()`, not resting, not in a dungeon (a battleground's buildings count) | depths | wander | 22 / 44 | 2 / 4 | depths palettes |
| An inn (resting under a roof) | resting and indoors | ember, 4 dB down, no bass | wander | 16 / 32 | 2 / 4 | ember palettes |
| A town, a city, an Alliance base (resting out of doors) | resting and not indoors | town | wander | 4 / 12 (alliance town, town square) | none: walking music | 2 (lanterns on the square, harbour lights) |
| A battleground or an arena | instance of kind battleground or arena | battleground, through its fights and deaths | wander | 4 / 12 (battleground, siege line) | none: battle music | 2 (hold the line, capture the flag) |
| A dungeon or a raid | instance of kind party, raid or scenario | wander | depths | walking and cave music of the zone's kind | same | same |
| A dungeon boss | `ENCOUNTER_START` | boss | battle | 6 / 12 | 2 / 4 | moment |
| The boss is dead, the fight is not | encounter over, still in combat | battle | storm, boss | 8 / 16 | 4 / 8 | moment |
| A fight in the open | combat (world PvP is not told apart) | the same piece: its drums and bass come up to full; its parts stay as they are (a piece has one strength) | | (every piece) | | |
| After a fight | combat over: held 3 to 13 s, then easing back | the same piece; after a boss fight of 10 s or more, 8 s of ember (the afterglow) | | ember | ember | ember |
| Camping: standing 45 s out of doors (waiting on a spawn, a rare, a friend) | still for 45 s, not on a flight path, not in a dungeon, a cave, an inn or a town, no fight | camp | wander, ember; night at night | 6 / 12 (watchfire, still hunt, uneasy vigil) | 2 / 4 (campfire) | 3 (embers under stars, the long wait, heat haze) |
| A rain storm that has set in, out of doors | weather rain at storm strength (0.6) for 4 s, over when under 0.4 for 20 s | storm | wander | 4 / 8 (tempest, blizzard) | 2 / 4 | storm |
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
pastoral      .     .     2     .     8     6     8     2     .    20     .     4
highland      2     2     2     2     2     4     4    24     4     4     .     2
haunted       8     2     .     .     4     2     4     .     8     2     .     6
desert        2     2     .     .     6     4     2     2     .     2    12     2
jungle        .     2     .     .     2     .     6     2    14     .     .     4
infernal      .     2     .     6     4     2     .     2     .     .     6     .
regal         .     8     6     .     8     .     2     .     .     2     .     .
mystic        .    10     .     .     .     .     6     2    12     .     .     4
```

Walking music (Warcraft), families by kind of place and shade:

```
            -3   -2   -1    0    1    2    3
pastoral     .    .    1    5    2   12    8
highland     .    8    .    8    2    3    3
haunted      3   11    3    5    .    .    .
desert       .    6    .    3    4    3    2
jungle       1    6    3    1    .    5    .
infernal     6    4    2    1    1    .    .
regal        .    .    .    4    .    6    6
mystic       .    3    .    5    1    .    9
```

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
