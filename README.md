# FreeRock

Generated music for World of Warcraft: Forever that follows the game. Every zone gets its own
music, made with ElevenLabs in an instrumental knight-rock style. It goes muffled and echoing when
you walk into a cave, the bass line and drums come in under the same music when a fight starts,
a rain storm brings the whole band in, and now and then it rests, as the game's own music does.

FreeRock is two parts. A small addon draws what the game is doing as a thin strip of squares along
the top of the screen. A program outside the game reads that strip, decides what should be heard,
makes the music, and plays it through a browser tab. The full design is in
[docs/plan.md](docs/plan.md).

## Where it stands (2026-11-15)

- **Works here, measured:** making music (tempo, key, layers, loops), the player (layers locked to
  the sample, changes on the bar line, no clipping), the rules from game state to sound, and the
  whole chain driven by a pretend game.
- **Not yet run in the game or on Windows:** the addon, the strip on a real screen, the sensor.
  WoW is not installed on the development machine.
- **Judged by ear only by Sky:** how the music sounds.

## Run it

On the Linux machine, from `app/`:

```
uv sync --extra stems          # once
uv run freerock serve          # the game link, the music and the pages, on port 8765
```

It prints the addresses to use. The key is read from `EL_BIG_BAD_KEY` (or `ELEVENLABS_API_KEY`)
in the environment or in a `.env` file in this folder or the one above it. Without a key, or with
`--no-new-music`, it plays only what is already in its library.

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
| `/rock skip`, `/rock love`, `/rock ban` | Play something else; keep this music; never play it again |
| `/rock volume <0-100>` | How loud FreeRock plays |
| `/rock gamemusic on`, `off` | Leave the game's own music on as well, or off while FreeRock is on |
| `/rock strip top`, `bottom`, `size <2-8>`, `inset <left> [edge]` | Where the strip is and how big its squares are |

## The music

A zone's first music is a **core suite**: one request of about three minutes with six parts in one
tempo and key (Arrival, two Wander riffs, Battle, Ember, Depths). It is split on this machine into
three layers (drums, bass, and everything else) that add back up to the original exactly. The
player moves between parts on bar lines and moves the layers' levels at once, so a fight brings
the bass and drums in under the music that is already playing.

Each of the game's 50 zones has a profile (tempo, key, instruments, mood) in
`app/freerock/atlas/zones.json`. A place without one, such as a dungeon, gets a profile from the
words in its name.

**It grows where you spend time.** Ten minutes in a place earns it a second set (two more riffs,
Night, Storm, a second Battle, Boss), and every two hours after that a fresh set (three more
riffs, a second Ember and Depths, a third Battle). Later sets are told to stay close to the core
suite so they sound like the same band. A place keeps three fresh sets in rotation; an older one
makes room for a newer one unless you have marked it with `/rock love`.

**Planned for 100 hours a month.** The minutes that go on growing music are released as the hours
are played, so the month's allowance lasts the month. `freerock settings` shows the numbers.

**Rain and rests.** Steady rain brings the drums in, and a rain storm the whole band; rain is
never muffled. After about six minutes of calm music the music rests for about a minute and comes
back with a fresh opening. Anything happening brings it straight back.

| Command | What it does |
|---|---|
| `freerock make "<zone>"` | Makes a zone's first music now, instead of on the first visit. `--set second` or `--set fresh` adds a later set. |
| `freerock library` | Lists the music FreeRock has |
| `freerock ledger` | What has been spent this month and today, and the account's credit balance |
| `freerock settings [name value]` | Shows or changes `monthly_minutes` (300), `daily_minutes` (30), `hours_per_month` (100), `rock` (0.5), `rest_every_minutes` (6; 0 for no rests) and `rest_seconds` (60) |
| `freerock adopt <folder>` | Looks again at a track that failed its checks; keeps it if it now passes |
| `freerock sim <scenario>` | Plays a scripted session against a running server, drawing and reading the real strip |
| `freerock read <picture>` | Reads the strip out of a saved picture and says what it holds |

**Cost.** ElevenLabs charges about $0.15 a minute. Every paid call goes through one function
(`app/freerock/eleven.py`) that checks the monthly and daily allowance first and writes a ledger.
At the allowance FreeRock stops making music and plays what it has. A track that fails its checks
is kept in `var/rejected/` rather than thrown away.

**Tools for listening and measuring.** `tools/spikes/` holds the experiments that settled the
design, with a listening page (`var/spikes/index.html`). `tools/render_session.py walk|storm [zone]`
plays a scripted stretch of play through the real player faster than real time (a fight, a mine
and stealth; or a rain storm and a rest) and writes the clip and its measurements to `var/demos/`.

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
- Prompts never name artists, songs, the game or its places.

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
                 music (composer, eleven, ledger, stems, analysis, library, ingest, atlas),
                 what plays (director, conductor, web/player), and the commands (cli, musiccli)
app/tests/       Python tests
tools/           Lua tests, the simulator runner, the experiments, the session renderer
docs/plan.md     the plan
var/             everything made at run time: library, ledger, logs, demos (not in git)
```
