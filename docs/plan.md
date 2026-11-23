# FreeRock: music written for World of Warcraft: Forever, that follows the game

FreeRock replaces the game's soundtrack with music of its own: eight-minute pieces written and recorded
by FreeRock's studio, gathered into a library for each of three styles, and chosen and shaped live by
what is happening in the game. A small addon reports what is going on through a strip of squares at
the top of the screen; a program outside the game reads it, and a player in a browser plays the music.
It is for Sky, on Sky's own two machines: a Linux laptop that writes, records and serves the music, and
a Windows gaming PC that runs the game, the strip's reader and the player.

The details live beside this plan: how the songs are written, `docs/songwriting.md` (the handbook);
how the game's signals move the music, `docs/signals-and-channels.md`; the kinds of place and what
plays in each, `docs/places.md`; the strip's format, `protocol/beacon.md`.

## Core principles

These come from Sky, mostly while playing, and every part of FreeRock answers to them.

- **The music sheet is the golden rule** ("the music sheet should be a separate concept and asset for
  every track, and updating it should be the golden rule, you are a musician were working on music....
  the rest is plumbing", 2026-11-18). Every track has its own sheet, kept with its recordings:
  - its form and keys;
  - every part's notes, dynamics and articulation;
  - its effect marks: where a filter opens, a pedal comes in, an echo is thrown;
  - who plays each part;
  - its history of revisions, each with why.

  The writers make a sheet's first draft. The studio only performs a sheet. Making a song better
  means revising its sheet as a musician would and performing it again. The effects are written into
  the music by what the notes do ("the music itself should denote the effects it shouldnt be
  standard"), never laid on by one rule for every piece.
- **Written music with stories, not loops.** Every piece is a composition of about eight minutes ("this
  is epic world of warcraft, not top 40"): it opens, states a theme, rises to a moment, falls to a
  valley and climbs to a summit before it closes. Each is recorded as five channels (texture, lead,
  rhythm, drums, bass) so the player can bring each up or down.
- **Kinds of place, not zones.** The music follows what a place is (pastoral, highland, frozen, marsh,
  coast, jungle, haunted, mystic, regal, desert, infernal), what ground it stands on (woods, water,
  heights, ruins...), how dark it is, the time of day and the weather; and what sort of place it is
  inside the zone (an inn, a camp, a cave, a town, a battleground). Every zone has a profile of these.
- **Light and heavy take turns**, and it is never "world of fairy craft": the walking music is hard
  enough to march to, fights have war drums, and the light pieces have weight of their own.
- **Whole songs, new songs.** A song plays to its end. It changes only for a big change of place: a new
  zone, going into or out of an inn, a camp, a cave, a town or a battleground, or a storm breaking.
  Every evening brings songs not heard lately; an old one comes back only when the round comes round.
- **Fights move the song, they do not replace it.** A fight drives the song in hand to its rise; only a
  dungeon boss has music of its own.
- **Subtle and faded.** Everything fades, new songs and every change of a channel; the levels follow the
  game gently; sitting still darkens and softens the music instead of leaving one sound whining.
- **Real instruments, mixed like a record.** Real recordings and an orchestra's samples, played and mixed
  in REAPER with real effects; every instrument crafted and measured; everything kept as FLAC.
- **The numbers find what to listen to; the ear decides.** Each piece is measured against stems Sky
  liked, but what Sky hears wins: a new instrument or sound is heard as a demo before it is used, and a
  choice between two sounds is Sky's.
- **One thing at a time, proven small before it is made big.** A new character, family or change is
  written, tested, rendered once and studied; only then is the rest made with it.
- **Playing comes first.** While Sky plays, the music never waits on the studio: the library is built
  again only with the game off, and the studio keeps to its share of the processors.
- **Within the game's rules.** The addon uses only functions Blizzard documents and values the game never
  seals; the program outside only looks at a patch of the screen.
- **Nothing is bought.** Every recording and synth FreeRock plays is free and openly licensed, and its
  makers are named.

## How it fits together

```
Windows gaming PC                                   Linux laptop
┌───────────────────────────────┐                  ┌──────────────────────────────────────────────┐
│ WoW Forever + FreeRock addon  │                  │ FreeRock server                              │
│   draws a strip of squares    │                  │   beacon: strip pixels -> game state         │
│   along the top edge          │                  │   director: state -> what should be heard    │
│            | on screen        │   strip pixels   │   conductor: the place, the library to play  │
│ sensor: copies that strip ----+----------------->│   pages: the player, what FreeRock sees,     │
│                               │                  │          the listening pages                 │
│ browser tab: the player  <----+-- pieces + cues -+   libraries: one bucket of pieces per style  │
└───────────────────────────────┘                  │                                              │
                                                   │ The studio (offline, by day and by night):   │
                                                   │   writer -> MuseScore, the sampler, synths   │
                                                   │   -> REAPER -> five channels -> the bucket   │
                                                   └──────────────────────────────────────────────┘
```

### The addon (`FreeRock/`, Lua)

`Signals.lua` keeps one table of the game's state from documented events: zone and subzone, position,
instance, indoors, resting, swimming and under water, mounted, flying, flight path, stealth, dead, in
combat, boss encounter, the target's classification, weather and its strength, day or night, cinematic
and loading screen. `Beacon.lua` packs it into a few dozen bytes with a checksum and draws it as the
strip. `CVars.lua` turns the game's own music off while FreeRock is on and puts Sky's setting back on
`/rock off` or logout. `Options.lua` holds `/rock` and its settings page. Only values the game never
seals go into the strip.

### The strip and the sensor

The strip is black and white squares behind a fixed sync pattern, read by comparing each square with
its neighbours so it survives gamma, HDR, colour filters and the dimming when dead; every frame carries
the whole state and a checksum, so a bad read is dropped and the last good one kept. The sensor, one
small Python file served by the server, copies the strip's pixels about twenty times a second and
sends them on; it decodes nothing.

### The server (`app/freerock/`, Python)

`beacon.py` turns strip pixels into game state. `director.py` turns the state into what should be
heard: the kind of place and the role (walking, an inn, a cave, a camp, night, a storm, a fight, a
boss), how much is going on, and the tints (darker when sitting or at night, quieter in an inn, thin on a
flight path, muffled under water). `conductor.py` follows the zone and the place inside it, holds the
zone on a flight path, and hands the player its library. The server also shows what FreeRock sees,
and the listening pages where every piece can be heard without the game.

### The player (`app/freerock/web/player/forever.js`)

A page in a browser plays each piece's five channels together on the audio clock, so they never drift.
It chooses what comes next from the style's bucket: the piece written for this kind of place, its
role, its ground, how dark it is, the time and the weather, heard least lately (it remembers sixty days);
light and heavy in turn. It changes the song only when the place changes in a big way, lets a song run
to its end, drives a fight into the song's rise on the next bar, and brings each channel up or down as
the game asks, always fading.

### The studio (`app/freerock/studio/`)

- **The writer.** Warcraft and Knight Rock are written by `orchestra.py`: each *character* (a kind of
  piece, such as a rowdy inn, a heavy march for the hills, a frozen cavern) fixes its kinds of place,
  role, modes, tempo, instruments, grooves and hall; each *family* of a character is one set of those
  choices; each *take* of a family is a new piece from them. House is written by `house.py`, by palettes
  for each kind of place. The handbook (`docs/songwriting.md`) says how each part is written.
- **The players.** MuseScore with Muse Sounds performs the orchestra and the band's guitars (each
  performance kept, so an unchanged part is never played twice); the sfizz sampler plays real
  recordings (VSCO 2, VCSL, TinySOL, FreePats, Naked Drums, Big Rusty Drums); synths (Surge XT,
  ZynAddSubFX, Geonkick) play what they are for, House above all.
- **The desk.** REAPER puts each piece together: every instrument with its own tone and place in a hall,
  the story's levels, the kick that everything else gives way to, and the mix of the five channels
  (`build.py`, House's `club.py`, `desk.py`, `sounds.py`).
- **The ear.** `ear.py` measures each channel octave by octave against the stems Sky liked; `tools/study.py`
  studies a finished take as a musician would hear it: its swing from quiet to loud, how many play at
  once, how much of the tune repeats, how each channel stands.

### The library

Each style has one bucket of pieces, built from the staged takes by `tools/fresh_bucket.py` (beside the one
that plays, then swapped in) and played across every zone. Three styles: **Warcraft** (an orchestra, darker sometimes, war drums in fights and
on the march), **Knight Rock** (a band: two guitars, bass, a rock kit, with lutes, fiddles and pipes for
colour), and **Progressive House** (110 beats a minute, happy and chill). The player page switches
between them.

## How the music follows the game

| In the game | What is heard |
|---|---|
| Walking about | The piece for this kind of place, its ground, the time and the weather, light and heavy in turn |
| A new zone | The new zone's music once you have been there a few seconds; held while flying over |
| Into or out of an inn, a camp, a cave, a town, a battleground | Its own music, faded in on the next bar |
| A rain storm breaks | Storm music; rain alone brings the drums in |
| A fight | The song in hand goes to its rise on the next bar; the bass and drums come up |
| A dungeon boss | The boss's own piece |
| Standing, sitting | Softer and darker the longer it lasts |
| Night | Darker and further off out of doors; night pieces join the round |
| Flight path, under water, a loading screen, death | Thin, muffled, ducked, wound down |

Every signal, its timing and what it does to each channel is in `docs/signals-and-channels.md`.

## How the work runs

- **The lanes.** Lists of takes to render wait in queue folders; a lane renders one list at a time,
  each take in its own process. A scheduler gives the day lane a third of the processors (two takes
  at a time) and the night lane half of them while Sky plays, all of them once Sky is done. A render
  is never stopped: a lane ends only after the takes it has begun.
- **One pass at each take.** Every finished take is studied; what is found goes into the writer or the
  desk for the pieces still to come, and a fault that recurs becomes a change.
- **The library is built again only with the game off**, so the server is never down while Sky plays.
- **Clean as it goes.** Old assets go; the tools, the Muse sounds and every performance a kept project
  uses stay; a performance nothing uses goes.
- **Every change proven before it is kept.** The full test suite passes before each commit, and the
  repository is public at github.com/skytruax/FreeRock.

## Making the songs better every night

Until the 8 TB drive is full, the nights and days make *new* music: new takes, new families and new
characters for the places and roles that run short. A change to the writer or the desk reaches what is
made after it; every take made before it that it would change is written down in the **re-render
ledger** (`tools/rerender_ledger.py`: each change with when it came, its commit, what it does and which
pieces it touches; `--write` lists every take that lacks it). Re-rendering is the long tail, done at the
end ("good iteration, keep that up on every genre", 2026-11-18).

Once the drive is full, the work turns to making the songs better, every night, in every style.

### What gets worked on

Three things are read every morning, strongest first:

1. **What Sky says while playing.** Every remark is a target ("whiny", "too light", "the same song
   again") and goes into the handbook with what was done about it.
2. **What was played.** Which pieces played where and for how long, which came round twice in an
   evening, which were skipped, and the places, roles and weathers that ran short. The player keeps
   this already, in its own browser, to choose what comes next; it is to be sent to the server and kept
   with the evening's log (see "Still to do").
3. **The study passes**: a fault that recurs across a style or a kind of place is a target; one take's
   quirk is noted and watched.

### The nightly cycle

1. **By day**: one or two targets per style. Each is one change in the writer or the desk, so a result
   can be traced to it; it is tried on one or two takes against the same takes before (octave by
   octave, the whine of what is left when standing, the swing, bar by bar where a shape is in question)
   and kept only if it moves towards the liked stems and nothing else moves; then the suite, a commit,
   a push, and its line in the ledger.
2. **The ear decides.** When the numbers and the ear might disagree (an instrument's character: the
   bagpipe was set aside by its numbers and then chosen by ear), the two go to Sky as clips at one
   loudness.
3. **By night**: the ledger's takes are rendered again, the places Sky plays most first; then new takes
   where the library is thin.
4. **Each morning** (the game off): every take made overnight gets its pass, the buckets are built
   again, and a short report says what changed, why, and where to hear it (`tools/new_songs.py` writes
   the page of the new songs; `tools/now_page.py`, run by each build, the page of what came into the
   player, what waits for the next build, and the demos).

### When the drive is full: the last three takes, each better than the last

- Every family keeps only its last three takes (take 24, 25 and 26, say): each night's new take of a
  family replaces its oldest once it has passed its study, so the library stays the same size while
  every piece in it keeps getting better ("when the drive fills up we'll always only keep the last 3
  takes", 2026-11-18).
- **A loop that improves itself**: each take is judged (its study against the liked stems and the
  measures below, and Sky's love, skip and ban while playing); what the judging finds is fed back into
  the writer's and the desk's settings for that family's next take; several candidates can be written
  and the best by the judging rendered; and Sky's ear stays in charge, so no one number is chased.
- **The loop works on the sheets, and writes down what it learns.** A night's improvement is a revision
  of a sheet (a part re-voiced, a passage varied, an effect marked where the music asks for one), with
  why in the sheet's history. Every lesson goes into the music-writing handbook
  (`docs/songwriting.md`): what was tried, what it was for, how it measured and what Sky's ear said,
  including what did not work. The handbook grows as the loop learns, and the writers follow it ("the
  recursive loop should also update the music writing handbook as it learns more", 2026-11-18).
- **Judges that listen** ("find more music judging packages, that will rate a song", "add those to
  the recursive loop", 2026-11-18). Open models that run on this machine, with no audio sent anywhere,
  from a study of what exists (the study's own list of what it could not verify is kept with it). None
  has been proven on long instrumental game music or on stems, and most hear only 16 kHz mono. So they
  are gates, voters and pointers, never targets.
  - **Gates**:
    - Meta's Audiobox Aesthetics, production quality (CC BY 4.0, about 400 MB, a minute or so a
      track);
    - PAM, as a floor for artefacts;
    - the loudness and peak checks: one common gain for the five stems, true peak at most -1 dBTP;
    - every one of the 31 ways the game can mix the five channels (each subset) checked for clipping
      and holes.
  - **Voters** that rank a family's takes:
    - LAION-CLAP, the margin by which a take answers its brief ("a slow haunted walk with organ")
      better than a foil;
    - its distance (KAD) from the takes Sky loved;
    - Essentia's style checks (their weights are non-commercial, which suits a game soundtrack kept
      for Sky's own playing, but noted).
  - **Holdouts** that are watched but never steer: Audiobox's enjoyment score, MuQ-Eval.
  - **A critic in words**: Qwen3-Omni (Apache-2.0, about 22 GB of memory), as a fault-finder for
    sections whose hints a measurement has to confirm. It agrees with experts only weakly (about 0.3).
  - **In use since 2026-11-19, in the loop for every style**: TuneJury (a style's brief and the music:
    how much a listener would prefer it; made for instrumental music), SongEval (musicality,
    memorability, coherence, clarity of structure) and Audiobox Aesthetics, all three in
    `tools/judges.py` (`var/tools/judges`, PyTorch for the processor alone). `--watch` judges every take
    as it is made; the studies read the scores; each change to the writer is judged on its demo takes
    before and after. Since 2026-11-18 Audiobox alone (`tools/judge.py`). It did not tell an opened rise and a turned cymbal from the take
    without them (CE 6.85 and 6.83): it hears production, so it gates the sound, and the boredom meter
    and the studies judge the writing.
- **The boredom meter** (the answer to "some of the instruments get boring"): for each stem, a
  fingerprint of every bar (its shape across the octaves, its brightness, its density) and a hash of
  its notes on the sheet. It reports:
  - the longest run that does not change, alone and in the mix;
  - how much the hats dominate;
  - for each run too long, what failed to change (the sound, the part, the treatment), so the remedy
    fits.

  The evidence blames unvarying simple stems and flat section shapes, not repetition itself. Something
  must change in every channel at least every 8 or 16 bars: a filter opening, a pedal coming in, the
  part, the voicing or the instrument.
- **When a new take may replace an old one.** It must:
  - pass every gate;
  - regress nowhere;
  - win beyond the judges' measured noise;
  - not be a near-copy;
  - come from the top third of its night.

  It stays provisional until Sky agrees. Loves are kept outside the three-take window, and bans go
  at once. Renders are shared out by how likely each family is to improve, so the promising ones get
  more tries. Candidates go through a funnel: many note-level checks on sheets, a few excerpts, then a
  handful of full renders (about four full renders a family a night).
- **Sky decides.** At most one blind, loudness-matched comparison an evening. If the judges agree with
  Sky on fewer than 15 of the last 20 such pairs, replacing stops until they are mended.
- **Effects that move with the story, in every style** ("yes you need effects over time", "this
  might apply to other genres too", "guitars should have effects in the 70s bro", 2026-11-18):
  - House rides its filters: shut at the start, open at a drop, shut for the breakdown, the bass's
    bottom taken away before a drop.
  - Knight Rock's guitars go through 1970s pedals (phaser, flanger "jet", wah rocked on the beat), each
    coming in and out with the sections.
  - Warcraft gets the same treatment in its own way (its rooms and swells).
  - The studio's own REAPER effects (`studio/jsfx/pedals`, `studio/jsfx/sweep`) can move through a
    piece without a click.
- **More than MuseScore where it falls short**: better instruments, synths and mixing tools are
  weighed as the loop shows where the sound, not the writing, is the weak part.
- A place's pieces are ranked: Sky's loves and the most played first. The weakest by the study, and
  those skipped or never chosen, are written again as new takes or families of the same character.
- Nothing Sky loved is removed; banned pieces go first.
- The library keeps its shape: every kind of place, role and time of day keeps enough pieces that no
  piece comes twice in an evening and a place's round lasts days, counted from the player's log.

### Every style the same way

Warcraft, Knight Rock and House share the player's rules, the kinds of place and their ground, and the
same story shapes; each style's writer and desk get the same passes, and what is found in one is tried
in the others (as the low brass under a band, the clap's knock, the accordion). The focus follows what
Sky plays, but no style goes a week without a pass.

### How progress is measured

- Per style, every morning: each channel's median distance from the liked stems through the middle and
  at the top, the swing by role, the whine of what is left when standing, the pieces for each kind of
  place and role, and the ledger's length. The trend should move towards the liked stems and stay.
- Per evening: how many different pieces played, whether any came twice, which places ran out.
- Sky's words: the complaints get fewer, and one that comes back means its fix did not work.

## Staying within the rules

- The addon calls only functions Blizzard documents, reads only values the game never seals, and does
  nothing in the game but draw the strip and switch the music setting.
- The program outside only looks at a patch of the screen: it never reads the game's memory, never sends
  keys or clicks, never touches the game's files.
- Sealed values (health, threat, who units outside the group are) are not read, not sent and not worked
  out some other way. If Blizzard seals something FreeRock uses, FreeRock drops it.
- Blizzard's licence has a broad clause against software that "reads information generated by the
  Platform" and has never said whether passive screen readers are fine; read-only tools built this way
  have been public for years without action. Sky chose the strip knowing this.

## Where things are

```
FreeRock/
  FreeRock/            the addon (FreeRock.toc, Core, CVars, Signals, Beacon, Options)
  protocol/            beacon.md, the strip's format, and its test vectors
  app/freerock/        the server (beacon, director, conductor, server, atlas of zones) and web/ (the player)
  app/freerock/studio/ the writer (orchestra, house), the desk (build, club, desk, sounds), the players
                       (muse, samples, sfz), the ear
  app/tests/           the tests, the player's engine run in a headless browser among them
  tools/               render_some (renders takes), fresh_bucket (builds a bucket), study (a take's pass),
                       listen and new_songs (the listening pages), soak (a made-up evening through the
                       real server and player), rerender_ledger (what the takes still lack), audition
  docs/                this plan, the handbook, signals and channels, places
  var/                 links to the assets drive: staged takes, buckets, listening pages, REAPER's work and
                       the MuseScore performances, the sample sets, the tools (REAPER, MuseScore)
```

## Verification

- **Tests.** The full suite (the strip in both languages under distortion, the director and conductor
  against scripted sessions, the studio's writers, the server) passes before every commit; the player's
  engine runs in a headless browser rendering audio offline, its timing checked to the sample.
- **A made-up evening.** `tools/soak.py` plays a scripted evening (zones, a ride at full tilt, caves,
  camps, rain, fights) through the real server and player and reports every song change and why.
- **Each take's pass**, and the ear: demos and before-and-after clips for Sky.
- **In the game, by Sky**: what FreeRock sees is on its page live, the player logs what it played, and
  `/rock status` prints what the addon sees.

## Still to do

- **A sheet for every take.** Takes made before 2026-11-18 have none. Each gets its sheet when it is
  performed again (the re-render ledger lists them), so that every track in the library can be
  revised.
- **The loop's revisions of sheets**: the musical edits it makes (re-voice a part, vary a passage,
  hand a line to another instrument, mark an effect), each written into the sheet's history, heard
  against the revision before, and kept only if it is better.
- **Warcraft's effect marks**, in its own way (the orchestra's rooms and swells: a harp's echo thrown
  at a phrase's end, a valley further into the hall).
- **Keeping the sheets safe**: every revision is kept beside its take, and the sheets could also be
  kept in a version history of their own (a decision for Sky).
- **The loop's first tools** (the study's first step, about a week):
  - the player's love, skip and ban, and its play log, sent to the server;
  - a blind A/B page;
  - the loudness, true-peak and 31-subset checks;
  - the boredom meter;
  - new reference audio for every style.
- **Better performances of the same sheets**, one family at a time, demo first:
  - phrasing that breathes (phrase arches, a final slowing, timing that drifts as a player's does);
  - real drum grooves (the Groove MIDI Dataset, CC BY 4.0), played by DrumGizmo as multi-mic stems;
  - amp captures for the band's clean guitars (Neural Amp Modeler, MIT);
  - a scripted organ with its Leslie (setBfree);
  - the Accurate-Salamander piano.

  Nothing is to be bought; if anything ever is, Pianoteq first.
- **Licences to settle** (Sky's call):
  - The AVL drum kits in use are CC BY-SA 3.0, outside the CC0 and CC BY of everything else.
  - The sfizz sampler's project was archived in June 2026: sforzando's free Linux build is the fallback.
- **The player's record of what it played**, sent to the server and kept with each evening's log, so
  the mornings can count what played where, what came twice and what ran short.
- **Windows on its own.** Server, sensor and player on the gaming PC alone, with the studio's work
  staying on the laptop.
- **The 8 TB drive** (arriving 2026-11-19): the library grows into it, then the nightly improvement
  above begins.
- **Drones for the bagpipe** that can be held, and more instruments heard and chosen by ear.
- **Uniform processes in every style**: House's writer and desk brought onto the same footing as the
  orchestra's.
