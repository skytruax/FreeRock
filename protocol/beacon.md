# The strip (version 1)

The strip is how the FreeRock addon tells the outside world what is happening in the game. An
addon cannot open a connection or write a file while the game runs, but it can draw. So it draws
its state as a thin line of black and white squares, and a program outside the game reads that
line off the screen.

This file is the one definition of the format. `FreeRock/Beacon.lua` draws it and
`app/freerock/beacon.py` reads it. Both must pass the test vectors in `vectors.json`, which
`tools/tests/make_vectors.py` writes from the cases listed inside that script.

Only values the game never seals go into the strip. See "What is never sent" at the end.

## Shape on screen

- Two rows of squares, one directly above the other. Every square is the same size, a whole number
  of screen pixels (the addon's setting, 3 by default, 2 to 8 allowed). A row is 344 squares wide,
  so at 3 pixels the strip is 1032 by 6 pixels.
- Black is the background and white squares are drawn on it. The black backing reaches 2 pixels
  past the squares on every side.
- By default the strip sits along the top edge of the game window, 16 pixels in from the left
  edge. Windows rounds the corners of windows, and a corner would eat the first squares. It can
  be moved to the bottom edge and the distances changed.
- The reader does not rely on any of those numbers. It finds the strip by its finder pattern and
  measures the square size from the strip itself.

## One row of squares

Left to right, `#` white and `.` black:

| Squares | Count | What |
|---|---|---|
| `..` | 2 | Quiet: always black |
| `####..` | 6 | Finder. Four white squares in a row occur nowhere else at the start of anything. |
| `#.#.` | 4 | Clock: single squares, which give the square size |
| 4 squares | 4 | Row number, two bits, most significant first (row 0 is the top row) |
| 320 squares | 320 | Data: 160 bits |
| `..####` | 6 | End mark |
| `..` | 2 | Quiet |

**Bits are pairs of squares.** A 1 is white then black. A 0 is black then white. The reader decides
each bit by asking which square of the pair is brighter, so it needs no idea of how bright "white"
is, and gamma, contrast, tints and uneven dimming do not disturb it. A side effect is that the
data never holds more than two squares of one colour in a row, which is what makes the finder
stand out and gives the reader an edge to measure from at least every second square.

## The payload

40 bytes. Row 0 carries bytes 0 to 19 and row 1 carries bytes 20 to 39, each byte most significant
bit first. Numbers of more than one byte are big-endian.

| Offset | Bytes | Field | Meaning |
|---|---|---|---|
| 0 | 1 | version and kind | High four bits: format version, 1. Low four bits: 0 a state frame, 1 a test frame. |
| 1 | 1 | beat | Goes up by one every half second and wraps at 256. Proves the strip is live. |
| 2 | 3 | flags | 24 yes/no values, listed below |
| 5 | 1 | instance kind, target class | High four bits and low four bits; values below |
| 6 | 1 | PvP kind, weather kind | High four bits and low four bits; values below |
| 7 | 2 | weather intensity | What the game reports, times 1000, capped at 65534. 65535: not reported. |
| 9 | 2 | map | The game's map number for the zone (uiMapID). 0: not known. |
| 11 | 2 | x | Position across the zone map, 0 to 65534 for left edge to right edge. 65535: not known. |
| 13 | 2 | y | Position down the zone map, same scale |
| 15 | 2 | instance | The game's instance number while in a dungeon, raid or battleground, else 0 |
| 17 | 2 | encounter | The boss encounter's number while one is running, else 0 |
| 19 | 2 | game clock | Minutes since midnight, game time. 65535: not known. |
| 21 | 1 | command | The last thing the player asked for: 0 nothing yet, 1 skip, 2 love, 3 ban |
| 22 | 1 | command count | Goes up by one with every command and wraps at 256 |
| 23 | 1 | moment | The last one-off event: 0 none yet, 1 level up, 2 boss defeated, 3 boss fight lost, 4 died, 5 quest handed in |
| 24 | 1 | moment count | Goes up by one with every moment and wraps at 256 |
| 25 | 1 | volume | The player's FreeRock volume, 0 to 100 |
| 26 | 1 | difficulty | The game's difficulty number while in an instance, else 0 |
| 27 | 2 | subzone mark | A 16-bit mark of the subzone name (see "Names"). 0: no subzone name. |
| 29 | 1 | reserved | 0 |
| 30 | 1 | text header | High three bits: which name. Next two bits: revision. Low three bits: chunk number. |
| 31 | 1 | text length | Length of the whole name in bytes, 0 to 48 |
| 32 | 6 | text chunk | Six bytes of the name, padded with zero bytes |
| 38 | 2 | checksum | CRC-16/CCITT-FALSE of bytes 0 to 37 |

The checksum is the common CRC-16 with polynomial 0x1021, starting value 0xFFFF, no reflection and
no final XOR. Its value for the nine characters `123456789` is 0x29B1.

A command or a moment is acted on when its count changes, not when it is seen, since the last one
stays in the strip. The counts are kept in the addon's saved settings so they do not start again
from zero at each login.

### Flags

Bit 0 is the least significant bit of the three bytes read as one number.

| Bit | Set when |
|---|---|
| 0 | FreeRock is switched on |
| 1 | Indoors (caves and buildings) |
| 2 | Resting (inns and cities) |
| 3 | Swimming |
| 4 | Under water |
| 5 | Mounted |
| 6 | Flying |
| 7 | On a flight path |
| 8 | Stealthed |
| 9 | Dead or a ghost |
| 10 | In combat |
| 11 | A boss encounter is running |
| 12 | A cinematic or movie is playing |
| 13 | A loading screen is up |
| 14 | It is day. Only meaningful when bit 15 is set. |
| 15 | The game reported day or night |
| 16 | The game reported weather |
| 17 | The position (x and y) is known |
| 18 | In an instance |
| 19 | The player has a target |
| 20 | A boss unit is present |
| 21 | In a group |
| 22 | A ghost |
| 23 | Reserved, 0 |

### Kinds

| Field | Values |
|---|---|
| Instance kind | 0 none, 1 party, 2 raid, 3 battleground, 4 arena, 5 scenario, 15 something else |
| Target class | 0 no target, 1 normal, 2 elite, 3 rare, 4 rare elite, 5 world boss, 6 trivial, 7 minus, 15 not readable |
| PvP kind | 0 not reported, 1 sanctuary, 2 friendly, 3 contested, 4 hostile, 5 combat zone, 6 arena, 15 something else |
| Weather kind | 0 clear, 1 rain, 2 snow, 3 sandstorm, 4 miscellaneous (the game's own numbers), 15 not reported |

Room is left on purpose. If the game turns out to report nothing useful for weather, the weather
flag stays clear and the two weather fields say "not reported"; nothing else moves.

### Names

Zone, subzone, instance and boss names are too long to send whole in every frame, so they take
turns in the eight text bytes, six bytes of name at a time. The addon moves to the next chunk
every fifth of a second and goes round all the names it has.

- Which name: 1 zone, 2 subzone, 3 instance, 4 boss encounter. 0 means the text bytes are empty.
- A name is sent as UTF-8, cut to 48 bytes without splitting a character.
- The revision goes up by one (wrapping at 4) each time that name changes, so the reader knows to
  throw away chunks of the old one.
- The subzone mark in every frame is the CRC-16 of the subzone name as sent, with 0 kept for "no
  name" (a name whose CRC is 0 is marked 0xFFFF). It changes in the same frame as the subzone does,
  before the name itself has arrived, and the reader checks the assembled name against it.

### Test frames

`/rock test` makes the addon send test frames for ten seconds. Byte 0 is 0x11, bytes 1 to 37 are
`(17 * i + 3) mod 256` for byte number `i`, and the checksum follows as usual. A reader that
decodes one knows every bit position works.

## What is never sent

Health, threat, and the name or identity of units outside the player's group are sealed by the
game in combat. FreeRock does not read them, does not send them, and does not work them out some
other way. Target class is read through `UnitClassification`, which the game does not seal; if a
value ever comes back sealed it is sent as "not readable".
