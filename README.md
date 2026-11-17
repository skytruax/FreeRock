# FreeRock

Music for World of Warcraft: Forever that follows the game, played as one song that never ends.

Each of the three styles (Knight Rock, Warcraft: an orchestral score in the old manner, and
Progressive House) has a bucket of music. Most of it is **written pieces**: music written and
played on this machine by FreeRock's studio (`app/freerock/studio/`) and kept as its parts, one
recording for each channel: drums, bass, a rhythm part, a tune and a drone. The player is five
decks, one for each of those channels, on one bar grid. It plays a piece's parts together, each
as loud as the game asks, so the piece keeps its own harmony and shape while the band comes and
goes. Pieces are strung into tracks that tell a story (it opens, states its theme, rises, comes
to its moment and closes). Which track plays depends on the kind of place you are in (haunted
woods, farmland, a desert: not the zone by name) and on what is happening; a dungeon's boss cuts
in with a piece of its own and the track is picked up afterwards where it was left; and light
and heavy tracks take turns, so that staying in one place does not grow too intense.

Beside its pieces a bucket keeps **loose phrases**, each one instrument alone, calm, steady or
hard, all on one tempo and key: they were made with ElevenLabs while the game was played in
FreeRock's first days. Now and then a stretch of them comes between two tracks. A phrase is one
turn of a form (a verse, a build-up and a chorus), so the whole band builds up and reaches the
chorus together, and each time round a couple of the decks have something new.

What you do in the game decides which channels are up and how hard they play: standing still is
a drone and a tune, moving brings the rhythm part and the drums, a fight brings the hard parts on
the next half beat, and more enemies in the fight bring more of them. Now and then the song eases
right off of its own accord, or leans in, and every few minutes it comes down to a moment of
silence.

FreeRock is two parts. A small addon draws what the game is doing as a thin strip of squares along
the top of the screen. A program outside the game reads that strip, decides what should be heard,
and plays it through a browser tab; its studio writes and plays the music beforehand. The first
design (music bought from ElevenLabs and played as whole songs) is in [docs/plan.md](docs/plan.md);
what the evenings in the game changed is in [CHANGELOG.md](CHANGELOG.md), and the strip is
defined in [protocol/beacon.md](protocol/beacon.md).

## Where it stands (2026-11-15)

- **Run in the game, on the gaming PC:** the addon, the strip read off a real screen, the
  sensor, the player page, the forever song in all three styles.
- **Measured here:** the player (decks locked to the sample, changes in step, no clipping), the
  rules from game state to sound, and the whole chain driven by a pretend game.
- **Judged by ear only by Sky:** how the music sounds. WoW is not installed on the development
  machine.
- **Not yet run in the game:** strip version 3 (the count of enemies in view and in a fight).

## Run it

On the Linux machine, from `app/`:

```
uv sync                        # once
uv run freerock serve          # the game link, the music and the pages, on port 8765
```

It prints the addresses to use, and plays what is in its buckets.

Open `http://localhost:8765/player` to hear it. The page has a **pretend game** panel: pick a zone,
tick cave, fight, night or weather, and the music does what it would do in the game.

## On the gaming PC

1. Install uv once. In PowerShell:
   `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
2. Put the addon in the game and start reading the screen:
   `uv run http://<linux machine>:8765/sensor.py --install-addon`
   It shows the AddOns folder it found and asks before copying.
3. Start the game and type `/rock test`. Open `http://<linux machine>:8765/` to see what FreeRock
   sees, and `http://<linux machine>:8765/player` to hear it.

After that, `http://<linux machine>:8765/FreeRock.cmd` downloads a launcher that opens the player
in its own window, with sound allowed to start by itself, and starts the sensor.

## In the game

| Command | What it does |
|---|---|
| `/rock` | Opens the settings |
| `/rock on`, `/rock off` | Turns FreeRock on or off. Off puts the game's own music back. |
| `/rock test` | Sends a test pattern for ten seconds |
| `/rock status` | Prints what the addon sees, the weather values the game reports, and any errors |
| `/rock skip`, `/rock love`, `/rock ban` | Play something else; mark this music as loved; never play it again |
| `/rock volume <0-100>` | How loud FreeRock plays |
| `/rock gamemusic on`, `off` | Leave the game's own music on as well, or off while FreeRock is on |
| `/rock strip top`, `bottom`, `size <2-8>`, `inset <left> [edge]` | Where the strip is and how big its squares are |

## The music

Each of the game's 50 zones has a profile (tempo, key, instruments, mood) in
`app/freerock/atlas/zones.json`. A place without one, such as a dungeon, gets a profile from the
words in its name. A style's bucket takes its tempo and key from the place it was begun in, and
goes with the player wherever they go: the song does not start again at a zone's border.

**Written pieces.** Tracks are written and played on this machine by the studio
(`app/freerock/studio/`): its orchestra and its band (`build`), its house writer (`house`, played
through Surge XT, Muse Sounds and the TR-8 recordings by `club`), and real public-domain scores
(`scores`). Each track is staged under `var/studio/` and put in its style's bucket with
`freerock pieces add`, cut into the pieces of its story (see `forever.Bucket.add_piece`). A piece
says what it is for: the kinds of place (pastoral, highland, haunted, desert, jungle, infernal,
regal, mystic: `app/freerock/kinds.py`), the sort of ground (woods, water, heights, fields...),
how dark or bright it is, the kind of moment, how hard it plays, and whether it is of the lighter
sort. Every zone is of one or two kinds, read from the words of its profile, and a named place
inside it adds its own; the player page says which kind of place you are in. A bucket may also
still hold pieces cut from the first design's songs (their source begins with `song/`).

**Rain and silences.** Steady rain brings the drums in, and a rain storm the whole band; rain is
never muffled. After about six minutes of music (`rest_every_minutes`) the song comes down to a
moment of silence of about a minute (`rest_seconds`), where its form comes round, and fades back
in afterwards; a fight brings it straight back.

| Command | What it does |
|---|---|
| `freerock pieces add [style]` | Puts every track the studio has staged for a style in its bucket, skipping those already there. Stop the server first. |
| `freerock pieces drop <style> <source>` | Takes every piece whose source begins with `<source>` out of the style's bucket for good: `knight/` for the studio's Knight Rock, `warcraft/real-` for the real scores, `song/` for the pieces cut from the first design's songs. Stop the server first. |
| `freerock pieces list [style]` | What written pieces a style has: how many, how long, and how they divide by kind of moment, kind of place, light and heavy |
| `uv run --no-sync python -m freerock.studio.build` | The studio's orchestra and its band: writes and plays every family of original tracks, staging the orchestra's under `var/studio/warcraft/` and Knight Rock's under `var/studio/knight/` (`--list` says what there would be, `--style knight` does only the band) |
| `uv run --no-sync --with numba python -m freerock.studio.house` | The studio's house writer and its synthesiser: stages tracks under `var/studio/house/` |
| `uv run --no-sync python -I -m freerock.studio.scores stage` | Real public-domain scores, played by family and staged (`fetch` gets them first) |
| `uv run --no-sync python ../tools/render_some.py <family/take> ...` | Writes and plays a chosen list of tracks, several at a time (`--until` begins none after that time of day) |
| `uv run --no-sync python ../tools/fresh_bucket.py <style>` | Takes a style's old studio pieces out of its bucket and puts in everything staged now. Stop the server first. |
| `uv run --no-sync python ../tools/listen.py [style]` | Every staged track as one file to listen to, under `var/listen/`, with a mixer page for its channels; the server shows them at `/listen/` |
| `uv run --no-sync python ../tools/audition.py` | Every instrument alone, on one page to listen to |
| `uv run --no-sync python ../tools/soak.py [style]` | A pretend evening played through the running server and a hidden browser: what music was chosen, and whether it played without a hitch |
| `freerock settings pieces off` | Only the loose phrases are played (`on` brings the written pieces back); the same as the tick box on the player page |
| `freerock stems [--to folder]` | Keeps every phrase and every part of every piece as a FLAC file, with `stems.csv` saying what each is |
| `freerock settings [name value]` | Shows or changes `rest_every_minutes` (6; 0 for no silences), `rest_seconds` (60), `genre` (knight, warcraft or house) and `pieces` (on or off) |
| `freerock sim <scenario>` | Plays a scripted session against a running server, drawing and reading the real strip |
| `freerock read <picture>` | Reads the strip out of a saved picture and says what it holds |

`tools/stems/README.md` says how the studio's instruments (REAPER and its plug-ins, MuseScore and
Muse Sounds, the sampled recordings) were fetched and put on this machine, and under what
licences; `tools/reaper.sh` opens the studio's REAPER with its window.

## Staying within the rules

- The addon calls only functions Blizzard documents and reads only values the game never seals.
  It does nothing in the game except draw the strip and switch the music setting.
- The program outside the game only looks at a patch of the screen, and only while the game is the
  window in front. It never reads the game's memory, never sends keys or clicks, and never changes
  game files.
- Health, threat and the identity of units outside the group are sealed in combat. They are not
  read, not sent, and not worked out some other way.
- Blizzard's licence has a broad clause against unauthorized software that "reads information
  generated by the Platform", and Blizzard has not said whether passive screen readers are fine.
  The strip was chosen knowing that. See [docs/plan.md](docs/plan.md).

## Tests

```
cd app && uv run pytest -q                 # everything in Python, including the player in headless Chrome
cd app && uv run python ../tools/tests/run.py   # the addon's Lua, against a stand-in for the game client
tools/sim/run.sh                           # the addon beside Blizzard's real interface code (needs Docker
                                           # and FreeControl's simulator lab next door)
```

## Layout

```
FreeRock/        the addon folder that goes into _forever_\Interface\AddOns\
protocol/        the strip format and its test vectors
app/freerock/    the program: game link (beacon, state, server, sim, web/sensor.py),
                 places and styles (atlas, kinds, composer), the forever song (forever,
                 stemstore, analysis, audio), written pieces (pieces, studio/), what plays
                 (director, conductor, web/player), and the commands (cli, musiccli, main)
app/tests/       Python tests
tools/           the studio's tools, the listening pages, the Lua tests, the simulator runner
docs/            the first design (plan.md) and the plan for the studio (own-stems.md)
var/             everything made at run time: buckets, the studio's tracks, logs (not in git)
```
