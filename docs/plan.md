# FreeRock: generated zone music that follows the game

## Context

Sky plays World of Warcraft: Forever with the music turned up and wants the soundtrack replaced by
music generated with ElevenLabs: new music per zone, changing on walking into a cave, following the
in-game weather, in an instrumental "knight rock" style, with a bass line that comes in when things
get intense. It should feel close to real time and be tied to the game as tightly as the rules
allow. It is for Sky only, on Sky's two machines: this Linux box and a Windows gaming PC.

An addon alone cannot do this. Addons cannot reach the network, cannot write files while the game
runs, and cannot play audio that did not exist when the game started. So FreeRock is two parts: a
small addon that reports what is happening, and an app outside the game that makes and plays the
music.

Sky's decisions so far (2026-11-15):

- Build it with **this Linux machine as the host**, then package it to run on the Windows PC alone.
- **Instrumental only.**
- The ElevenLabs account is now on **Pro**. FreeRock uses the unrestricted key stored as
  `EL_BIG_BAD_KEY` in `.env`.
- **Good music first, with a little AC/DC in it.** The rock grows with the intensity rather than
  running flat out all the time.
- Use the **on-screen strip** to get state out of the game, knowing where it stands with Blizzard's
  rules (see "Staying within the rules").
- The strip carries **zone and coordinates** as well as the cave, weather and combat state.

Added by Sky after hearing the first clips (2026-11-15):

- **Rock during a rain storm.** Rain is not muffled; a storm brings the whole band in.
- **Planned for 100 hours of play a month.**
- **Moments without music**, as the game has, though less often.

## What I checked

**The game (Forever 1.60.1; Blizzard's generated API docs, and the client lists already in
`FreeControl/tools/sim/lab/dl-wowless-wowf-data/`):**

- Weather is official: `C_Weather.GetCurrentWeather()` returns a type (Clear, Rain, Snow, Sandstorm,
  Miscellaneous) and an intensity; `WEATHER_CHANGED` fires on change. No Blizzard code uses it, so
  its real behaviour and the intensity range have to be seen in the game.
- Day and night: `C_DateAndTime.IsDayTime()` and `DIEL_CYCLE_CHANGED`.
- Indoors and caves: `IsIndoors()` and `ZONE_CHANGED_INDOORS`.
- Zone, subzone and instance names and IDs; position within the zone; resting, swimming, submerged,
  mounted, flying, flight path, stealth, dead; combat start and end; boss encounter start and end;
  target classification. None of these is sealed.
- Sealed in combat and therefore left out entirely: health, threat, and the identity of units
  outside the group.
- `Sound_EnableMusic` exists and `C_CVar.SetCVar` is documented, so the game's own music can be
  switched off the official way.
- The world is classic Azeroth: 51 zone maps (including the six capitals) and about 1,200 named
  subzones, with zone boundaries, all published for this build on wago.tools (`UiMap`, `AreaTable`,
  `UiMapAssignment`). Every zone can have a hand-written music profile before the first note.

**ElevenLabs:**

- `.env` holds two keys. `ELEVENLABS_API_KEY` is restricted: it cannot read account details, and
  the free composition-plan call succeeded with it twice. `EL_BIG_BAD_KEY` is the unrestricted one
  Sky added after upgrading to Pro, and it is the one FreeRock uses. That it generates audio, and
  can read the credit balance, is confirmed by the first experiment.
- The current model is `music_v2_5`, and it has to be named in every request because the default
  is still the deprecated one. A request is a list of up to 30 chunks, each with its own style
  words and an enforced length of 3 s to 2 min, so part boundaries fall at known times. Tempo and
  key are given as style words. The default output is 48 kHz.
- Streaming returns audio while it is still being generated. There is no official figure for the
  delay before the first audio; one outside measurement has a full minute of music arriving in
  about 8 seconds.
- $0.15 per generated minute. Plans also cap generated minutes per month, and the two official
  pages disagree on the cap (Creator 62 or 147, Pro 304 or 660). Pro also allows uncompressed
  output. Two requests can run at once on either plan.
- Artist names are rejected in prompts, so the style is described in musical terms. Zone and game
  names stay out of prompts too.
- ElevenLabs cannot generate separate instrument layers, and its own stem separation costs extra.
  A free open-source separator (Demucs) run on this machine does the same job at no cost.

**This machine:** no WoW client, so nothing can be confirmed in the game from here. It has Python,
uv, Node, ffmpeg, Docker, Chrome and working audio output, and no firewall in the way, so
everything except the game itself can be built, run and heard here. Headless Chrome here renders
the browser audio engine offline correctly, which is how the player gets tested.

## How it fits together

```
Windows gaming PC                                   Linux host (this machine)
┌───────────────────────────────┐                  ┌──────────────────────────────────────────┐
│ WoW Forever + FreeRock addon  │                  │ FreeRock server                          │
│   draws a thin strip of       │                  │   reads the strip -> game state          │
│   squares along the top edge  │                  │   director: state -> what should play    │
│            | on screen        │   strip pixels   │   composer: ElevenLabs (key stays here)  │
│ sensor: copies that strip ----+----------------->│   library: every track kept and reused   │
│                               │                  │   web pages: player and controls         │
│ browser tab: the player  <----+-- audio + cues --+                                          │
└───────────────────────────────┘                  └──────────────────────────────────────────┘
```

### 1. The addon (`FreeRock/FreeRock/`, Lua)

- `Signals.lua` listens to the documented events and keeps one table of the current state: zone and
  subzone, map ID, position within the zone, instance, indoors, resting, swimming, submerged,
  mounted, flying, flight path, stealth, dead, in combat, boss encounter, target classification,
  weather type and intensity, day or night, game clock, cinematic, loading screen. A check five
  times a second covers the states that have no event (position, indoors, swimming, submerged,
  flying). The game withholds position inside dungeons; there the instance name stands in.
- `Beacon.lua` packs that state into a few dozen bytes with a version number and a checksum and
  draws it as the strip described below.
- `CVars.lua` turns the game's own music off while FreeRock is on and puts Sky's setting back at
  logout or on `/rock off`. Ambience and sound effects are untouched.
- `Options.lua` has `/rock on|off|status|test|skip|love|ban|volume N` and a small settings page.
  Skip, love, ban and volume travel to the app inside the strip.
- Only values that are never sealed go into the strip. Each one is checked against the flags in
  Blizzard's generated docs before it is used, and nothing sealed is read or worked around.

### 2. The strip

The format lives in one file, `protocol/beacon.md`, with test vectors both the Lua and the Python
side must pass. The squares are black or white only, start with a fixed sync pattern, and are read
by comparing each square with its neighbours, so the reading survives gamma, contrast, HDR, colour
filters and the uneven dimming the game applies when you are dead. Every frame carries the full
fast state (flags, IDs, coordinates) and a checksum, so a bad read is dropped and the last good
state is kept; names (subzone, boss) rotate through a small text field over about a second. It sits
as a thin line along the top edge, a few pixels tall, set in from the window corner because
Windows 11 rounds window corners. Position and square size are settings, and the server finds the
strip by its sync pattern rather than by a fixed position. Other tools have shown this works on
Forever with plain screen copies; FreeRock's format and code are written from scratch.

### 3. The sensor (Windows, one small Python file)

Finds the game window, copies the strip's pixels about 20 times a second, and sends the raw pixels
to the server when they change. It does no decoding, so there is little to get wrong on the one
machine where I cannot test, and the server keeps the raw strips so I can see exactly what the
gaming PC captured. It is served by the server itself: on Windows, install uv once, then
`uv run http://<music machine>:8765/sensor.py` always runs the current version. It starts with a
plain screen copy (`mss`) and can switch to two other capture methods (`dxcam`, `windows-capture`)
if that one cannot see the strip.

### 4. The server (`FreeRock/app/`, Python, on Linux for now)

- `beacon.py`: strip pixels to game state.
- `director.py`: game state to what should be heard (which track, which part, layer levels, tone),
  with the timing rules in the table below.
- `composer.py`: builds each request by hand from the zone's profile.
- `eleven.py`: the one place a paid call can be made. It checks the allowance, writes the ledger,
  streams the result and decodes it as it arrives. A rejected prompt is shown on the control page
  with ElevenLabs' suggested wording, not silently replaced.
- `stems.py` and `analysis.py`: split each track into its three layers, check tempo, beat grid,
  key and that there are no vocals, set loop points on bar lines, and even out loudness. Audio is
  stored uncompressed at the rate ElevenLabs delivers, so every part of FreeRock counts in the
  same samples.
- `library.py`: every generated track, its analysis, play history and the spend ledger.
- `atlas/`: a hand-written music profile for each of the 51 zones and the known dungeons, keyword
  rules for subzones (Mine, Cave, Ruins, Camp, Lake, Keep, Inn and so on), zone boundaries, and the
  knight-rock recipe.
- `server.py`: receives the sensor, feeds the player, and serves a control page.
- `sim.py`: plays back scripted game sessions so the whole chain runs without the game.

### 5. The player (a browser tab on the gaming PC)

A page served by the server that plays the audio through the browser's audio engine, which already
does sample-accurate scheduling, fades, filters and reverb. Nothing to install on Windows, fixes
reach it without copying files, and the same page runs in Chrome on this machine for testing.

- The server sends uncompressed audio in one-second pieces and the page schedules them on the
  audio clock, all three layers at the same instant, so they cannot drift apart. No decoding
  happens in the browser.
- The server queues what comes next and sends the target mix; the page gets there on the beat. On
  reconnect it is sent the whole target again, so a dropped connection heals itself. If the server
  goes quiet the current music keeps looping, then fades after a minute with a banner.
- Nothing in the audio path waits on timers, which browsers slow down in background windows, and
  the page uses only browser features that work on a plain local-network address.
- A track that is still being generated plays from the same pieces that become the stored copy,
  so there is no jump when the stored copy takes over.
- A launcher file served by the server opens the page in its own browser window with sound
  allowed to start without a click, and starts the sensor. Without the launcher the page shows one
  "press to start" button.
- The page keeps a log and a recording of its own output (the music only) and sends them to the
  server, so I can measure the next day what was actually played and when.

## How the music adapts

**The knight-rock recipe.** ElevenLabs rejects band names, so the AC/DC side is written out in
musical terms: late-1970s arena hard rock, riff-driven, two crunchy rhythm guitars playing
open-chord riffs with space between the hits, a bass that sits on the root in steady eighth notes,
plain hard-hitting drums with a heavy backbeat, a raw live-room sound, blues-scale lead with wide
bends. Knight colour: lute, hurdy-gurdy drone, war drums, Dorian and Mixolydian melodies. Never:
vocals, synths, electronic drums.

How much of the rock you hear follows the intensity. The Wander parts carry a little of it: the
riff played cleaner and looser, with the lute and the melody in front. Battle and Boss are the full
band at full crunch. One setting moves the whole range up or down.

Each zone's profile adds its tempo, key, colour instruments and mood: Elwynn chiming and pastoral
with lute and fiddle, Duskwood slow and minor with organ and bells, Tanaris on a frame drum with a
Phrygian lute, Dun Morogh a stomp with anvil and drone pipes.

**What gets generated: a core suite per zone, which grows while you stay.** The core suite is a
single request of just under three minutes, in one tempo and key, with every part a whole number of
bars so that parts loop and change on bar lines:

| Part | Bars | Used for |
|---|---|---|
| Arrival | 4 | The first seconds in a zone: a drone and one guitar stating the riff |
| Wander A, Wander B | 16 each | Exploring; two riffs on the same groove |
| Battle | 16 | A fight that lasts |
| Ember | 16 | Half-time and calm: inns, after a fight, as a ghost, and night until Night exists |
| Depths | 16 | Caves and buildings: low, dark, spacious |

The parts are in that order so that a first listen, straight off the stream, already makes sense.

| Added later | When | What it adds |
|---|---|---|
| Second set (about 3 min) | Ten minutes into your time in the zone | Two more Wander riffs, Night, Storm, a second Battle, Boss |
| Fresh sets (about 3 min each) | Every two hours you play there | Three more Wander riffs, a second Ember and Depths, a third Battle |

A zone holds about 15 minutes of music. Past that, a fresh set replaces the oldest one that Sky
has not marked with `/rock love`, so a zone keeps changing without growing forever.

**Three layers from every suite, made on this machine.** After download, Demucs splits the suite
into drums, bass, and everything else. The third layer is defined as the original minus the other
two, so the three always add up exactly to what ElevenLabs produced, and because they come from one
performance they are locked together. This costs no ElevenLabs minutes.

**Two controls and a set of tints:**

- **Place** moves between parts on bar lines.
- **Intensity** moves the layer levels, so the bass line enters over the music that is already
  playing. Intensity comes only from combat, target classification, boss encounters and instance
  type.
- **Weather, night, water, stealth and death** start as live changes of tone (filter, reverb,
  levels) that cost no generation and can be undone instantly. Heavy weather and night also get
  their own parts once the zone's second set exists.

**What you hear**

| In the game | At once (about a fifth of a second) | Then |
|---|---|---|
| Combat starts | The bass line fades in under what is playing, with a hit | If the fight lasts, Battle on the next bar |
| Elite | Bass and drums up at once | Battle within a couple of seconds |
| Boss pull | A boss hit, everything up | Boss on the next beat (Battle until the zone's second set exists) |
| Combat ends | Holds for 5 s in case the next pull is coming | Bass out over two bars, a few bars of Ember, back to Wander |
| Walk into a cave or building | Muffled and echoing | Depths on the next bar if you stay a few seconds |
| Under water | Heavy muffle | |
| Stealth | The band drops away to the bass line and quiet drums | |
| Mounted | Drums come up, brighter | |
| Flight path | Thin and airy, bass out | Zones passed overhead are ignored until you land |
| Rain | The drums come in once it is raining steadily. A rain storm brings the whole band in at once, harder the heavier it is. Rain is never muffled. | Storm, a hard-rocking part of its own, on the next bar once the storm has lasted ten seconds |
| Snow, sandstorm | Over a few seconds the tone follows the intensity: snow soft and wide, sandstorm narrow and gritty | |
| Night falls | A slow change: darker, drums back | Night joins the rotation |
| Moving through the zone | | The Wander riffs change with the part of the zone you are in |
| Standing still for a while | | A calmer mix; Ember favoured |
| Inn or city | Quieter, bass out | Ember |
| Dead | Winds down like a record stopping | Ember, slow and distant, until release |
| Cinematic or loading screen | Fades out, or ducks | Returns after |
| Zone border | The new zone's music on the next bar, with four seconds' grace on foot in case you step back | |
| Heading for a zone border | Nothing audible | The next zone's music is prepared ahead, so it is ready when you cross |

**A zone you have never been to:** when you spend half a minute near an edge of the map that
leads to a neighbour, that neighbour's core suite is generated in the background, so most first
visits start fully prepared. Arriving unprepared (a portal, a hearthstone), a drone in the zone's
key and a hit start at once, and the request is streamed with Arrival first, so the zone's own
music follows as soon as the first audio arrives. The layers are ready about a minute later; until
then fights are answered with tone changes, hits and the Battle part.

**Keeping it fresh:** each part is cut into four-bar cells, and the player moves through a
place's riffs in turn rather than looping one stretch. Later sets use a new seed and are told to
stay close to thirty seconds of the core suite, so they sound like the same band; a place keeps
its core suite, a second set and three fresh sets in rotation, and an older fresh set makes room
for a newer one unless it has been marked with `/rock love`.

**Rests.** After about six minutes of calm music the music fades away for about a minute, then
comes back with a fresh opening, as the game's own music does between pieces (less often than the
game). A fight, a storm, stealth or a new place brings it straight back, and nothing rests while
something is going on. Both lengths are settings; 0 switches rests off.

## Staying within the rules

- The addon calls only functions Blizzard documents, reads only values the game never seals, and
  does nothing in the game except draw the strip and switch the music setting.
- The outside program only looks at a patch of the screen. It never reads the game's memory, never
  sends keys or clicks, and never changes game files.
- Sealed values (health, threat, the identity of units outside the group) are not read, not sent,
  and not reconstructed some other way. If Blizzard seals something FreeRock uses, FreeRock drops
  it.
- Where this stands: Blizzard's licence has a broad clause against unauthorized software that
  "reads information generated by the Platform", and Blizzard has never said whether passive screen
  readers are fine. Read-only tools built this way have been public since 2015, including addons on
  CurseForge for Forever today, with no reported action. Sky chose the strip knowing this
  (2026-11-15). The alternatives are too slow by design: Blizzard delays the log files by minutes.
- ElevenLabs: prompts never name artists or songs, and the output is kept for Sky's own listening,
  which their music terms allow.

## Cost guard (planned around Pro)

- **Allowance: 300 minutes of new music a month by default**, one setting. That is under the lower
  of the two caps ElevenLabs publishes for Pro (304 and 660) and uses about $45 of the plan's
  credits at $0.15 a minute.
- **Planned for 100 hours of play a month.** With rests, that is about 85 hours of music, of which
  5 hours are new each month; the rest is the library, which keeps growing, played in a different
  order with different layers. Three fifths of the allowance goes on growing the places where time
  is spent, released as the hours are played (1.8 minutes of new music per hour, about one new set
  every two hours), so there is still new music coming in the last week of the month. The rest is
  for the first music of new places and for re-rolls. If the real cap turns out to be 660, raising
  `monthly_minutes` doubles all of this.
- What 300 minutes buys in a typical month: 15 new zones (42), a dozen second sets (38), about 30
  fresh sets (96), half a dozen dungeons (19), look-ahead for up to ten neighbours (28), and 30
  held back for re-rolls when a track fails its checks, leaving about 45 spare. The whole world
  with a core suite and a second set costs about 300 minutes once; after that nearly everything
  goes to fresh music.
- Every paid call goes through one function that checks the allowance first and writes a ledger
  (minutes, what it was for, which zone). The control page shows used, left, and where it went.
- Hard stops: the monthly allowance and 30 minutes in any one day. A place earns its second set
  after ten minutes there and a fresh set every two hours after that. Nothing is generated on a flight path, while the game is
  closed, or while the player page is not connected. One of the two request slots is kept free for
  the zone you have just walked into.
- At the cap, a new zone borrows a suite from a similar zone, and the control page says so.
- An account error (cap reached, format not available on the plan) is shown word for word on the
  control page and stops generation. It is not retried in a loop.
- The control page shows the account's real credit balance next to FreeRock's own ledger. One
  optional thing only Sky can do in the ElevenLabs dashboard: set a credit limit on the key, if
  the dashboard offers one, as a second stop outside FreeRock.

## Build order

Two things need Sky and cannot be hurried: evenings in the game and ears. The order gets both
started early.

1. **Foundations and experiments.** The paid-call function with its ledger, the analysis and layer
   splitting, the offline test rig for the player, then the experiments below (paid, under 10
   minutes of music, about $1.50). Ends with demo files Sky can judge on any device.
2. **Windows check.** The player page's one-button self-test (does sound come out, how late), and
   the link test: addon, strip, sensor, and a page showing what FreeRock sees, live. No generated
   music needed. Ends when an evening in the game shows every moment on the checklist registering.
3. **Music core.** Profiles for every zone, the director, the library, and a control page with a
   pretend-game panel (pick a zone, toggle cave, combat, weather, night). Heard on this machine or
   any browser. Ends when Sky has tuned the recipe by ear.
4. **First playable.** Link and music joined; first-visit streaming; look-ahead at zone borders;
   cost guard; session log and recording. Ends with an evening of play on generated music.
5. **Depth.** Weather tuned to the game's real values, dungeons and bosses, stingers, skip, love
   and ban from in game, fresh editions, and anything the later experiments opened up.
6. **Windows on its own.** The same Python package installed on the gaming PC with uv, server and
   sensor in one program, the player at `localhost`, and the key moved into Windows Credential
   Manager rather than a file. Layer splitting is heavy; whether it runs on the gaming PC while
   you play or stays on this machine is decided then, with timings in hand.

### The experiments (step 1)

Each is a small script in `tools/spikes/` that writes its numbers to a report and its audio to a
listening page. I cannot hear audio, so each has a measurement I can compute and something for Sky
to judge by ear. They are ordered so an early failure changes course cheaply.

| # | Question | What is generated | Passes if | Sky listens for |
|---|---|---|---|---|
| 0 | Can the key generate at all, and in which format? | Two clips of 3 s | Audio comes back; the format (uncompressed or MP3), rate and stereo are known | |
| 1 | How long until the first audio, and how fast does the rest arrive? | 30 s in two parts | First audio within 3 s; at least 3 s of music per second; tempo within 1% | First impression of the style |
| 2 | Does a core suite hold together, and do the layers split cleanly? | One core suite, kept as the first zone | Tempo within 0.5% in every part; parts start on a downbeat within 60 ms; one key throughout; no vocals; muting the bass layer removes at least 6 dB of low end; a five-minute walk through the cells has no stumbles | Is this the sound? Does the bass entrance work? Any artefacts with the bass out? |
| 3 | Does a second request for the same zone sound like the same band? | A third Wander riff and a Boss (about 1 min), new seed | Tempo within 0.5% and tuning within 10 cents of #2 | Same band or not. This decides how later sets are made. |
| 4 | Does conditioning on earlier audio work on this plan? | 30 s conditioned on #2 | Accepted, and closer to #2 than #3 is | Same zone feel |
| 5 | Can separately generated solo parts be layered? | Solo bass, solo drums, bare backing (16 s each) | Each really is solo; they line up within 15 ms | Layered version against #2 |
| 6 | Are sound-effect clips usable for drones and hits? | A drone, a power-chord hit, a drum loop | In tune within 15 cents; loop joins cleanly | Drone in tune, hit usable |
| 7 | ElevenLabs' own stem separation, only if #2's layers fail | 32 s | Same checks as #2; cost and delay | Same as #2 |

About 9 minutes of music in total including one re-roll, with a ceiling of 10. If #2's layers fail
and #7 does too, the fallback is a Tension part built around the bass line, switched to on the
beat.

### What Sky does on the gaming PC (step 2)

1. Install uv once (one line in PowerShell).
2. Run `uv run http://<music machine>:8765/sensor.py --install-addon`. It shows the Forever AddOns
   folder it found and asks before copying the addon there, then starts reading the screen.
3. Start the game, type `/rock test`, and open `http://<music machine>:8765/` on the PC or a phone.
   The page shows what FreeRock sees.

If the server cannot be reached, the sensor says so in its window and the player page shows a
banner; `/rock off` brings the game's own music back.

## Where the code goes

A new private git repository at `FreeRock/` (local only; no remote
unless Sky asks; commits carry no attribution lines). The key stays in the existing
`.env` beside the repository, never printed, never committed.

```
FreeRock/
  FreeRock/            the addon folder that goes into _forever_\Interface\AddOns\
    FreeRock.toc  Core.lua  CVars.lua  Signals.lua  Beacon.lua  Options.lua
  protocol/            beacon.md (the strip format) and vectors.json (shared test vectors)
  app/                 Python package `freerock` (uv project)
    freerock/          beacon.py  state.py  director.py  composer.py  eleven.py  stems.py
                       analysis.py  library.py  server.py  sim.py  atlas/
                       web/ (player engine, control page, sensor.py, launcher)
    tests/
  tools/
    tests/             Lua tests against a stand-in for the game client
    sim/               runs the addon beside Blizzard's real Forever interface code
    build_atlas.py     seeds zones, subzones and boundaries from wago.tools (build wowf 1.60.1)
    spikes/            the paid experiments, each writing a short report
  README.md  CHANGELOG.md  .gitignore
```

### Reused from FreeControl (Sky's own code, same workspace)

| What | From | Used for |
|---|---|---|
| `ns.Try`, `ns.On`, `ns.Print`, settings defaults and clean-up | `FreeControl/FreeControl/Core.lua` | Errors reach the game's error handler, the first is said in chat, all are listed in `/rock status`. Nothing is swallowed. |
| Console-variable backup and restore | `FreeControl/FreeControl/CVars.lua` | Turning the game's music off and putting Sky's setting back. |
| Settings page and slash-command layout | `FreeControl/FreeControl/Options.lua` | `/rock` and its settings page. |
| Stand-in game client and test runner | `FreeControl/tools/tests/` (`run.py`, `wowmock.lua`) | Lua tests; one fresh Lua state per test. |
| Simulator runner and API check | `FreeControl/tools/sim/` (`lab/run-sim.sh`, `lab/tools/api_lint.py`, image `simlab/wow-ui-sim-forever:0.1.41`) | Loading the addon beside Blizzard's real interface code; flagging any name the Forever client does not have. The simulator lacks the weather function, so tests supply it. |
| Client API, event and console-variable lists | `FreeControl/tools/sim/lab/dl-wowless-wowf-data/` | Checking every function FreeRock calls. |

## Verification

**On this machine, by me:**

1. Lua tests: each game state produces the expected strip; the music setting is backed up and put
   back; every `/rock` command; errors surface.
2. Round trip across languages: the real `Beacon.lua`, run under the stand-in client, draws a
   strip; it is rendered to an image at several square sizes and distorted (gamma, contrast,
   tint, uneven dimming, scaling blur); the real `beacon.py` must decode the same state. Random
   states, thousands of cases.
3. API check and simulator load: no name missing from the Forever client, no Lua errors, the
   settings page opens.
4. Python tests: the director against scripted sessions (what should be heard, and when); the
   composer and paid-call function against a stand-in ElevenLabs server (streaming, rejected
   prompt, rate limit, plan limit); the ledger (generation stops at the cap).
5. Track checks on every download: length, tempo, key, no vocals, layers add up to the original.
6. Player, rendered offline in headless Chrome with test signals: the three layers stay aligned to
   the sample; a change asked for on a bar lands within a millisecond of it; each tint changes the
   right frequency band within its fade time; the output never clips; the music does not gap when
   the server goes quiet; the switch from a streamed track to its stored copy is inaudible in the
   numbers.
7. End to end without the game: `freerock sim` plays a scripted session (walk through a zone, enter
   a mine, pull a mob, rain starts, night falls, cross a border) through the whole chain with real
   generated audio, and the delay from each event to the change in the output is measured.

**In the game, by Sky** (I cannot run it; each step has something to read back):

1. The player page's self-test button, which reports to the server whether sound started and how
   late it runs.
2. `/rock test` shows a test pattern; the control page shows the strip as captured, the read rate
   and the checksum failures. Target: found, about 20 reads a second, no failures.
3. A checklist of in-game moments (zone border, mine, inn, mount, swim under water, stealth, pull,
   elite, death, rain, nightfall, dungeon boss, cinematic). The control page logs every state
   change with a time, and the player's own recording shows what the music did in response.
4. `/rock status` prints what the addon sees, the weather values the game actually reports, and any
   errors, for pasting back.

## What can only be learned by trying

- **Weather in practice.** The function is documented but Blizzard's own interface never calls it.
  If the game reports nothing useful, there is no rules-clean way to see the weather, and FreeRock
  falls back to each zone's usual climate.
- **Screen copies on the gaming PC.** HDR and window mode can change what a copy sees. The strip is
  built to survive that, and two other capture methods are ready.
- **Hiding the interface.** Whether Alt-Z hides the strip is unknown. When the strip disappears,
  FreeRock keeps the last state rather than guessing.
- **How the music actually sounds.** Whether the layers split cleanly, whether the bass entrance
  lands, and whether the recipe is the sound Sky has in mind are all judged at the listening
  checkpoints in steps 1 and 3. Bringing the bass in for stealth is my guess at what a Rogue would
  like; it is one setting.
- **ElevenLabs timing.** How quickly the first audio arrives is experiment 1.
- **The real monthly cap on Pro** (304 or 660 minutes). The ledger and the first cap error will
  show which.
