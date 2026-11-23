# FreeRock songwriting handbook

How FreeRock's studio writes, plays, mixes and checks its music, and how to make more of it.
Written from the code as it stood on 2026-11-17. Read the README first.
`docs/signals-and-channels.md` says how the game moves each channel, and `docs/places.md` what
plays where.

**Conventions.**

- Modules are under `app/freerock/studio/` unless a path says otherwise; tools are under `tools/`.
  Run every command from `app/`.
- `var/` is made at run time and is not in git. On the music machine most of its folders are
  links to an assets drive: without the drive, nothing plays or renders.
- Numbers are the code's. (unconfirmed) marks what the code could not settle.
- Words in quotation marks are the owner's, as typed or dictated, from the project's notes and
  the code's comments. *Italic* quotations are the code's own comments. `[...]` marks words left
  out: the names of artists and services, and a few oaths. Names of sounds, titles and settings are
  in `code` style.

---

## 0. The music sheet: the golden rule

"The music sheet should be a separate concept and asset for every track, and updating it should be
the golden rule, you are a musician were working on music.... the rest is plumbing"; "remember your
music sheets are your core principal and most important asset" (2026-11-18).

### 0.1 What a sheet is

Every take has its own sheet (`score.Sheet`), kept beside its recordings as
`var/studio/<style>/<family>/<take>/sheet.json`. When a sheet is saved over, the revision it replaces
stays beside it as `sheet.r<N>.json`. A sheet holds:

- **the form**: each section's story word and part, its first bar and length, its key and chords, and
  how hard it is played from start to end (House: which theme is the breakdown);
- **every part**, by channel: who plays it (`instrument`), its notes, its swells (the expression
  pedal), its **effect marks** (what moves, beat by beat) and their settings;
- **about**: what the desk needs to perform it and the player to choose it (the character, the room,
  band or orchestra, light or heavy, the strokes the others duck under);
- **airs** (House): the risers, wind and weather;
- **history**: every revision, with what, why, by whom and when.

The writers (`orchestra.Take` with `build.write`, `house.Take` with `club.write`) make only the first
draft. The desk (`build.perform`, `club.perform`) only performs a sheet. Every number is kept exactly:
a note rounded off by a hundred-thousandth of a beat moved a MIDI tick and sent a part back to
MuseScore to be performed again.

### 0.2 Reading, revising and performing one

    uv run --no-sync --with numba python -m freerock.studio.sheet show knight/infernal-forge-anthem-1/3
    uv run --no-sync --with numba python -m freerock.studio.sheet perform knight/infernal-forge-anthem-1/3

`show` lays the sheet out like a part chart: a row for each part, a column for each section, how many
notes a bar it plays there, and its marks (w wah, p phaser, f flanger, l the low-pass closed, h the
high-pass in). Then the history.

A revision is a change to the music, made as a musician would: a part re-voiced, a passage varied, a
line handed to another instrument, an effect marked where the music asks for one. It is written into
the history with why (`Sheet.revised`), saved, and performed again. Changing the writers' code
reaches only first drafts.

### 0.3 Effects are marked by the music

"The music itself should denote the effects it shouldnt be standard." An effect is marked on the part
that plays it, where that take's own notes ask for it, never laid on by one rule for every piece. The
marks the desk plays (`score.EFFECTS`):

- the pedals (`studio/jsfx/pedals`): wah, wah depth and position, phaser, flanger, flanger depth
  and position;
- the filters (`studio/jsfx/sweep`): low-pass and high-pass.

Their settings that stay put are in `score.SETTINGS`. Both effects are the studio's own, so they can
move through a piece without a click. REAPER's bundled phaser starts its sweep again whenever a
setting moves.

**Knight Rock, a band's guitars** (`orchestra.Take.effects`), as a player of the 1970s works his pedals
("guitars should have effects in the 70s bro"):

- A rhythm guitar that sounds most of the time (strummed chords, 60% or more) is coloured where a
  passage comes back. The first time a passage is heard it is dry. The colour is a phaser that sweeps
  once per chord, or in some takes a slow flanger.
- A chord held two beats or more into an arrival is flanged by hand across exactly that chord (the
  jet), and is dry when the arrival lands.
- A long rise (16 bars or more) opens: the rhythm guitar's wah is held at the heel as the rise
  begins, dark, and brought forward by hand to the toe by its last bars, slowly at first. It is let go
  where the jet begins or the arrival lands, so the moment comes in open and dry. Half in, the guitar
  keeps its body.
- The lead's wah at the moments:
  - rocked at the pace of its own notes where it runs (at the first arrival only where it runs hard,
    at the summit wherever it is busy);
  - opened slowly from heel to toe across a long held note (the cry).
- A second guitar playing the harmony stays dry: the harmony is its colour.
- A clean guitar's ringing broken chords get a vibe in the quiet valley.
- A long opening (16 bars or more) opens the same way on the guitar that carries its riff (a heavy
  band's lone guitar, or the rhythm guitar where the band opens together): dry for the first half,
  then the wah brought by hand from heel to toe, let go as the band comes in. A guitar that only
  counts the band in at the end stays dry.
- Where the clean guitar is the band's whole accompaniment (a light band with no rhythm guitar), it is
  dry through the first theme. The vibe comes in with the second theme and stays through the moments,
  where a light band's arpeggios want the shimmer that a heavy band's arrival, struck dry, does not.
  The rises are left as they are.
- Chugs and riffs with air between their hits stay dry, as on the records they come from.

**House** (`club.write`):

- **The low-pass.** Each part's low-pass follows its own notes' brightness (`club.cutoff`): a drop
  wide open, a theme half an octave to an octave darker, opening across it, and the breakdown shut
  under 1.5 kHz.
- **The high-pass**, by the form (`club.thinning`):
  - the sub leaves for the whole of each rise;
  - over a rise's last seven beats the bass, chords and pads are thinned from the bottom;
  - the bass is lifted out over the breakdown's first four bars;
  - everything returns on the drop's first beat.
- **Calm pieces** (an inn, a camp, the night) keep their bottom.

### 0.4 What was learned (2026-11-18)

- **One rule for every piece sounds standard.** The first pedal demo put a phaser in every theme and
  a jet in every rise, by rule. Marks taken from the notes land in different places in each take, and
  only where a player would use them.
- **A filter can only open as far as the part's fixed tone lets it.** House's chords had a fixed top
  (cut at 6 kHz, 16 dB down from 2.5 kHz), measured against the liked stems on average. A drop was as
  dark as its theme until that top gave way to the moving low-pass.
- **House: level is not where the contrast lives.** The records studied swing little in loudness
  ("Strobe": 5.8 LU). Their contrast is in brightness, density, the sub and the pump: the sub came out
  of the breakdown by 26 dB, where before it held on at -9.
- **The hats**: off the clap's bright chain, onto a line of their own (high-passed at 500 Hz, dry, no
  tape), 3 dB further under the kick ("too much high hat").
- **A house lead is a riff** ("the lead is still lame"). The singing hooks, two-bar melodies with long notes
  on a thin whistle, became riffs: cells of three sixteenths resolved by eighths, every note on the
  chord, a pluck where it is quiet and a big synth at the drops, the echo thrown at each phrase's end.
  The calm moments still sing.
- **Hollow came from the cuts** ("it sounds hollow and generic in the synths"). Measured against the
  liked stems on average, House's pads had been cut below 200 Hz, its chords below 110, its leads
  below 120: the body of a synth lives there. Eased (110, 80, 85) and spread wider, the lead gained
  2.5 dB of body and about 6 dB of width. Bigger patches are heard by Sky, not chosen by number
  (`var/listen/house-sounds.html`), and a held C4 can mislead about a patch's octave: a strong sub reads
  as the note, so every candidate's pitch is checked again in its own music.
- **The boredom meter** (`tools/boredom.py`) found what the ear calls boring in House: the drums the same
  for 40 bars of a theme, the maracas' sixteenths running under everything, and in a 48-bar last drop the
  lead's colour held 23 bars and the chords' all 48. A groove now changes every sixteen bars (the hats
  turn, the percussion figures take turns), a drop builds block by block, and its last sixteen bars
  change again. The meter reads a groove's figure as well as its octaves: a hat that turns from eighths
  to off-beats hardly moves any octave's energy.
- **A synth is chosen by the music it plays.** Nine leads played Breakwater's own riff through House's
  chain; Argitoth's Trance Lead 1 stood 4 dB from the liked house leads across the octaves, the leads in
  use 12 to 14 (16 to 34 dB short from 80 to 160 Hz). In the track its lead went from 17.9 dB off the
  liked to 9.1. But it played 22 cents flat as it comes, and the second choice, Anthemish 1, 42 sharp:
  a patch is heard for its tuning in its own music too, not only its shape (`analysis.estimate_key` on
  the audition clip). Trance Lead 1 is tuned up in its own state (`desk.surge`, "@+22") and plays at
  +4; Anthemish 2, in tune, is the second synth.
- **The ear over the average** ("Rain on the Roofs I is okay i wish i could hear more of that saw synths
  top end"). The saw lead's chain still carried cuts measured against the liked stems' average (5 dB at
  2.5 kHz, 8 dB from 3.5 kHz), and its moving filter sat at 3.2 kHz in a theme: the hook's edge was
  gone. Now only its very top is eased (2 dB above 7 kHz), with a little air, and the tune's filter
  opens further than the band's (a theme's lead about 6 kHz). A liked stem's average is a guide to
  where a part sits, not a ceiling on what makes it sing.
- **A reed does not hold the valley's drone.** King's Oath's valley drone was the english horn, held
  24 bars under a soft guitar. Pushed up into its upper register by the old bagpipe's floor it whined,
  and MuseScore's english horn hardly follows its dynamics (as loud at pianissimo as at piano): it
  stood 9 dB over the tune. Handed to the organ, which goes down 20 dB there as written, it sits 2 dB
  under the tune and whines 17 dB less. A reed's harmonics read louder than its note (its peaks at
  twice, three and four times the note): read a reed's spectrum by its pattern, not its top peak.

- **A part can change its notes and still sound the same** (the boredom meter on Bridge Charge, a
  battleground take). Its rhythm guitar went 19 bars of a 36-bar rise without a change the meter
  could hear. On the sheet its chords moved a half step and its figure thinned, but in one colour, and
  its drums kept one groove on the toms through a whole 40-bar theme. Moving the notes is not enough.
  What moves is the colour: the long rise is now opened on a wah, and the drummer turns to the ride
  every other sixteen bars. Read the meter's flag against the sheet before deciding what is wrong.

- **A patch's loudest partial is not always its note.** Banners I's organ chords stood 28.8 dB over the
  liked house chords at the top. Surge's House Organ is loudest at its fourth harmonic, two octaves
  over its note, like an organ with its two-foot drawbar pulled all the way. The octave was right; the
  colour was wrong for chords. Ten organs played Banners I's own chords through the chord chain, and
  the LinnStrument set's Drawbar Organ 1 came 4.5 dB from the liked, in tune. In the song its chords
  went from 23 to 34 dB over the liked in the top three octaves to within 7, centred at 590 Hz against
  the liked 514 (1,658 before).
- **An audition strikes its notes as the desk does** (`club._loud`: a voice's hardest note at 0.9).
  Struck at the sheet's soft levels, Smooth Stabs read 6 dB darker than the liked chords at the top;
  struck as the desk strikes, 19 to 27 dB brighter, as in the songs. A synth's filter follows how hard
  it is struck.
- **An edge asked for one part stays on that part.** The open top asked for the saw ("i wish i could
  hear more of that saw synths top end") had reached every synth lead, and an inn's sung melody stood
  20 dB over the liked leads at the top. Only the drop's big synths keep it now (`club.OPEN_TOP`).

- **House's chords against the liked stems at the top are not a target.** Struck as the desk strikes
  them, every synth tried for the chords stood 15 to 28 dB over the liked chords from 2.5 to 10 kHz,
  under the old fixed top too (cut at 6 kHz, 16 dB down from 2.5): no EQ brought them near. As with
  Knight Rock's texture, the liked chords' top is likely a separated stem's leftovers. The chords keep
  their top and are judged by ear. The organ was another matter: its whole shape was off, centred at
  1,658 Hz against the liked 514.
- **A calm piece has no roll into its moment**, as its design says (Cold Stars I's bell had rolled in
  sixteenths into its drop, ringing 6 dB over it). In the other pieces the chords' roll climbs to the
  drop and no higher: each stroke softer as they come faster, swelling across the bar.

- **The weather sits under the band where the band is full.** A storm's rain at 0.4 all the way through
  sat under Rain on the Roofs' warm pad, which was heard and liked, but over Thunderhead I's bright pad
  it covered the music: the texture centred at 4.8 kHz against the liked 422 Hz, and the render's check
  found it only 61% in its key. The rain now falls at 0.4 in the opening, the rises and the close and
  at 0.25 under the themes and drops: centred at 1.8 kHz, 5 dB less at the top, 7 to 9 dB more middle.
  The rest of the gap is the bright pad's own top; what pad a storm wants is for the ear.

- **The boredom meter over the whole Knight Rock library** (206 takes, 2026-11-18): 16 bars or more
  without a change in the rhythm guitar of 22 takes, 15 of them in a rise; in the drums of 8, 6 in a
  moment; in the texture of 7; in the bass of 5. The rises and moments are what the opened wah and
  the drummer's ride and bell were written for. The flat textures were 21 to 40 bars of a tavern's,
  an open road's or a bayou band's accordion and harmonica. The open road's and the tavern's new
  takes change every couple of bars. But the bayou band's new take still held its harmonica on one
  chord for a minute (Moonshine Blues: notes 16 and 24 bars long, as an organ would), so a wind
  player now breathes (4.8). Results in `var/passes/boredom-knight.json`.

The nightly loop works on sheets and writes every lesson here: what was tried, what it was for, how
it measured, what Sky's ear said, and what did not work ("the recursive loop should also update the
music writing handbook as it learns more").

---

## 1. What the music is for, and the brief

### 1.1 What it is for

The music sits behind hours of play and follows it. Each track is written for a kind of place
(pastoral, highland, haunted, desert, jungle, infernal, regal, mystic, and since 2026-11-17 the marsh, the coast and
the frozen snowfields) and a kind of moment
(`studio.ROLES`: wander, night, ember, depths, storm, battle, boss, town, battleground, camp). It
is recorded as five channels (texture, lead, rhythm, drums, bass) that the game turns up and
down. So a track must tell its story whole, still make sense with channels missing, and not wear
out over an evening.

### 1.2 The brief, in the owner's words

- **Style.** "do good music, add a lil [...] style in there too" (2026-11-15). Knight Rock: "a
  little more toward [...]". Warcraft: "traditional recreations of the zone music", written as an
  original orchestral score in that manner, since nothing may copy the game's own music. House:
  "change the trance to uplifting progressive house, like 110 bpm not 128", "we want that mode to
  be happy and chill".
- **A song that never ends.** "use the song stems like its ableton, switching on channels based on
  whats true in the game", "your a dj making a forver song".
- **Stories.** "real music, with stories, that rise and come to a moment", "make it sound UNIQUE AND
  DIFFERENT", then "rewrite all the music using the same concepts, but to 8 minutes (since this is
  epic world of warcraft, not [...] top 40)".
- **Places.** "Its not about duskwood... duskwood is a type of place so it will construct that type
  of music"; "make sure our location changes CHANGE SONGS based on tone ect"; "in a dark misty place
  and music is too light we need lots of different granularity"; "our grim to bright scale"; "night
  should feel like night"; "like whenever in an alliance base should be a family of songs", "or in a
  battleground, a family"; "camping should get its own tunes".
- **Light and heavy.** "remember sometimes it calls for light moods"; "it always should shift to
  light mood after some time in the same place it gets a bit too intense"; "just shift around, or in
  light places always be light".
- **Fights, weather, fades, silence.** "Rock during a rain storm"; "in normal fights dont play a
  separate battle piece dungeon bosses ONLY"; "the abruptness between fighting and not, its way too
  much now, it should only be a subtle difference like before"; "you gotta fade in and out of
  everything, new songs, but even channel changes"; "Make it so that there are moments without music,
  just like the real game, maybe not as often as the real game".
- **Fullness and movement.** "not enough instruments in each track"; "write the most dynamic
  interesting music you can"; "rewrite all music to be more dynamic"; "make sure the individual stem
  tracks are interesting enough"; "more depth more instruments .... more bass and kick in the intense
  parts".
- **The sound.** "the music is well written we just need a good renderer"; "we should be using
  plugins and effects for most instruments"; "be meticulous on every instrument, and every
  arrangement"; "you're a musician not a coder"; "dont forget to try out lots of instruments i better
  hear harmonica and banjo"; "make sure no default sounds are left"; "remember to use reaper and
  plugins for effects and mixing".
- **The method.** "look at principals of orchestra music, [...] for house, [...] for knight rock";
  "i want real music, thats dfiferent and unique"; "not a bunch of schlack"; "make 10 of each genre
  listen to it with musescore, make it better and do that 3 times for each set of 10"; "let me see a
  song demo when youve figured it out"; "make sure all genres use uniform processes eventually".
- **Keeping it.** "were going to get an 8tb drive for this project so switch it all back to flac";
  "make sure we can play tonight even without re-renders".

### 1.3 The influences

**Warcraft: orchestral principles.** *The tunes are built the way tunes are: a motif of a bar,
answered, repeated a step higher, and brought home; long notes on the notes of the chord, steps
between them; the highest note late in the phrase* (the `orchestra` module). Themes are stated,
varied and handed between players; inner voices move; the bass moves through the chords. The
writer is held against 72 movements of the public-domain orchestral repertoire (the OpenScore
orchestra, `tools/orchestra_study.py`).

**Knight Rock: riff rock in the late-seventies arena tradition.** Power-chord riffs with room
between the chords, licks that answer them, a lead on the minor pentatonic over major chords, a
bass on the root in eighths that leads into each change, a plain hard kit, twin guitars a third
apart, a stop on the first beat of a big moment, and a riff that opens on one guitar.

**House: progressive house.** The project's open-work notes record a study of one producer's
method: keys of G# or B minor; add9 and sus chords; loops of three to five chords; the bass on the
roots first; a kick 1/8 to 1/16 long; a sidechain release of about a quarter beat; everything but
the kick and the bass high-passed; something changing every eight bars; one wide element. Research
notes of the same day add a short kick that is only a transient, the low end owned by one thing at
a time, ducking drawn as volume curves, and arranging by adding and removing. The code follows most
of this: four-chord loops with 9 and sus colours, plain roots first, drawn ducking with the bass
back in a third of a beat, low cuts from 110 to 200 Hz on everything but the kick and the bass,
eight-bar phrases. It does not follow the keys: the House plan uses all twelve tonics, and its test
asks for them. Whether the TR-8 kicks are that short is (unconfirmed).

---

## 2. A track's shape

### 2.1 The five story words

The player knows five words for where a piece stands (`forever.STORY`). Long tracks use three of
them more than once.

| Word | Warcraft and Knight Rock (`orchestra.WORD`) | House (`house.Family.story`) |
|---|---|---|
| open | open | open |
| theme | first, second, valley | theme (the groove), theme (the breakdown) |
| rise | build, climb | rise, rise |
| moment | arrival, summit | moment (first drop), moment (last drop) |
| close | close | close |

### 2.2 Warcraft and Knight Rock: nine parts in two waves

`orchestra.family` writes the parts of `orchestra.PARTS`. A track is about 480 s (`LONG`); every
family in the plan comes to between 455 and 505 s.

| Part | Word | Share (in a fight) | What happens |
|---|---|---|---|
| open | open | 8.5% (4.5%) | The key chord, a pad or drone. One player hints at the first theme's first two bars, then another. From its middle the chord stirs to the mode's colour chord every fourth bar. |
| first | theme | 12.5% (13.5%) | The first theme, stated and stated again. From the second statement a slower line goes under it, the other figure joins and the bass moves more. |
| second | theme | 12% (13%) | A second theme that begins away from home, from another singer, over another figure, pad and groove. |
| build | rise | 10% (12%) | The first theme's first bars, higher each time, more players, closer together. The drums go over to the moment's groove and roll; a run up the scale; a breath. |
| arrival | moment | 11.5% (13.5%) | The first theme from the strongest players, a second joining, a slower line under. In bigger music a cymbal swells into it and a deep stroke lands. |
| valley | theme | 10% (10%) | The broader theme from one player who has not stated it, over very little. |
| climb | rise | 12.5% (13.5%) | The second theme's opening handed between two players, then the first theme's first bar climbing, to the chord before home, held. |
| summit | moment | 13.5% (14%) | The first theme from everyone strong, the second sung under it; in some families a key higher. |
| close | close | 9.5% (6%) | The opening again, a memory of the second theme, the first theme's last two bars, the key note (or its fifth) held. |

**How bars are counted** (`orchestra._lengths`). A theme's period is eight bars, or sixteen where
eight bars would pass in under 17 s. A part that sings a theme is whole periods, with room for the
second half once more. Other parts go in fours (twos where a bar lasts 3 s or more). A sung part is
kept under 66 s where it can be (`MINUTE`). Then a step at a time is added or taken until the
whole fits; a fight's opening and close are the last to grow. Two real families, worked out by
running `orchestra.family` with the seeds `build.plan` gives them:

| Family | Key, tempo | Bars: open, first, second, build, arrival, valley, climb, summit, close | Length |
|---|---|---|---|
| `pastoral-morning-fields-1` (`Dew Lane`) | F# major, 79 BPM, period 8 | 14, 20, 20, 16, 20, 16, 20, 20, 16 | 492 s |
| `anywhere-tempest-1` (`Howling Gale`, a storm) | F minor, 141 BPM, period 16 | 12, 32, 32, 36, 32, 32, 36, 40, 16 | 456 s |

**How levels are drawn** (`orchestra._levels`). Each part has a level at its start and at its end,
0 to 1, and runs straight between them (`Take.level`). `w` is the character's weight.

| Part | Walking music | Night, inn, cave, camp | Fights (battle, boss, storm, battleground) |
|---|---|---|---|
| open | 0.18 to 0.34 | 0.14 to 0.26 | 0.60 to 0.72 |
| first | 0.42 to 0.60 | 0.34 to 0.44 | 0.70 to 0.80 |
| second | 0.38 to 0.56 | 0.30 to 0.42 | 0.66 to 0.78 |
| build | 0.46 to 0.5 + 0.38w | 0.36 to 0.38 + 0.2w | 0.75 to 0.95 |
| arrival | 0.56 + 0.26w | 0.4 + 0.26w | 0.90 |
| valley | 0.24 to 0.20 | 0.18 to 0.16 | 0.58 to 0.66 |
| climb | 0.32 to 0.55 + 0.42w | 0.26 to 0.42 + 0.3w | 0.68 to 1.00 |
| summit | 0.68 + 0.32w | 0.45 + 0.4w | 1.00 |
| close | 0.48 to 0.12 | 0.36 to 0.10 | 0.90 to 0.65 |

*Walking music was made a little harder on 2026-11-17 ("go a little harder this is not world of fairy
craft"): its quiet parts less faint and a light piece's top higher (it was open 0.14 to 0.30, valley
0.20 to 0.16, summit 0.6 + 0.4w). A rowdy inn (an inn's character busy 0.6 or more: tavern, drinking
song, harbour saloon, sailors rest, tavern rock, dwarf hall) is shaped as walking music, not as a quiet
room: a dwarven drinking hall's demo opened at -38 dB and its middle fell to -41 (2026-11-18).*

A note's strength is `Take.hard(level, weight)` = 0.16 + 0.8 × level × weight, kept between 0.05
and 1. `tests/test_studio.py` holds the shape: the summit is the top, the arrival at least 0.05
under it, the valley quieter than both themes and the arrival. After the render `build.stage`
lifts each part 15% of the way to the loudest (`build.RIDE`, at most 12 dB, easing over 3 s at each
join). It was 0.42, *which took most of the written dynamics away*.

### 2.3 House: eight sections in two waves

A House family gives five lengths (open, theme, rise, moment, close). `house.Family.story` makes
two waves of them: open, the theme twice as long, rise, moment, the breakdown (a theme), rise, the
last drop twice as long, close. Tracks run 124 to 192 bars at 110 BPM, 271 to 419 s. The shape
`E5` (16 bars each) gives 16, 32, 16, 16, 16, 16, 32, 16 bars: 349 s.

| Section | What happens |
|---|---|
| open | Pads and a filtered chord figure, no kick. In two takes of three a shaker or other small percussion creeps in over the second half. The end of the tune's idea, far off. |
| theme | The groove: kick, backbeat, hats, percussion, bass, the chord figure. The hook in its second half. |
| rise | The groove drops out but for the kick, which stays on the floor until the build's last eight bars (`house.RISE_KICK`), and the closed hat ticking the eighths, soft and growing (`house.RISE_CLOSED_HAT`). The tune whole, soft then full; a roll and a riser over the last eight bars, the kick gone for them. A calm rise (an inn, a camp, a night) has neither: the tune over a shaker stirring. (The full hats and percussion, `house.RISE_PULSE`, were tried and left off: 5.5.) |
| moment | The drop: everything, the tune at its brightest; every second time round a line above it. |
| theme (breakdown) | No kick, no groove, the bass one long note to a bar. Fights do not break down. |
| close | The band leaves; the kick goes four bars before the end. |

**Energy** (`house.ARCS`, `Take.energy`) sets levels and brightness. The arc comes from the role
(`house.ARC_OF`): wander, night, depths and town use the wander arc, ember and camp the ember arc,
storm its own, and battle, boss and battleground the battle arc. In a rise energy grows as
along^1.8: *it holds back, then goes*. The breakdown runs 0.3 to 0.5 (`house.BREAKDOWN`), *from
little and growing*.

| Arc | open | theme | rise | moment | close |
|---|---|---|---|---|---|
| wander | 0.2 to 0.5 | 0.6 to 0.72 | 0.4 to 0.95 | 1.0 | 0.72 to 0.2 |
| ember | 0.2 to 0.4 | 0.5 to 0.6 | 0.4 to 0.66 | 0.78 | 0.55 to 0.2 |
| storm | 0.45 to 0.65 | 0.75 to 0.8 | 0.5 to 1.0 | 1.0 | 0.8 to 0.4 |
| battle | 0.8 to 0.88 | 0.86 to 0.9 | 0.6 to 1.0 | 1.0 | 0.9 to 0.7 |

### 2.4 Light and heavy

Two things share these words.

- **The label** (`Character.light`, `house.Family.light`, `light` in a piece). The player makes
  light and heavy take turns (`web/player/forever.js`, `_nextItem`): after a heavy track a heavy one
  costs 1.0 (`TURN`); after a light one a light one does, so they go one for one; in a light place a
  heavy track costs 5, except that after a light track (two until "go a little harder", 2026-11-17) it costs nothing and a light one
  1.0: one track in two, the nearest heavy one in shade ("the warcraft songs are too light go a lil
  darker sometimes", "just a bit light and wimpy in general", "in all genres", 2026-11-17; light and
  heavy had gone two to one, and light places had heard nothing heavy). Turns are counted as a track
  for calm play begins, and a track plays whole whichever it is ("for the whole songs to play").
- **Heavy writing** (`Take.heavy`: weight 0.8 or more): brass stabs and two lines above the pad at
  the moments, the whole low end together, war drums in walking music, a gong, a piccolo on top of
  the summit (a glockenspiel otherwise); in a band, the lone opening guitar and the stop.

A light piece is written lighter: its pad three semitones higher (five until "go a little harder this
is not world of fairy craft", 2026-11-17: high airy pads were half the fairy sound, and high pasture,
harvest home, harbour town and lakeside reverie gave up their celesta, glockenspiel and vibraphone
for mandolin and guitar; and the snow's accompaniment, all celesta and glockenspiel, read 21 dB short in the
middle and 16 dB over at the top, so frozen cavern, frozen lake, ice fields, aurora and ice cave play pizzicato
where they had the glockenspiel, and the frost camp a guitar, 2026-11-18), its arrival's second player a
third above the tune, the desk's kick only on the bar and at 0.6, and no sub, low brass or bell at
its moments (`build.stage`). Drums and
bass sit further back where the weight is under 0.7 (`build.LIGHT`, `build.BAND_LIGHT`). Light
walking characters, and every band walking character, get a second family, *since light places
hear little else* (`build.plan`). The tests ask both writers for light and heavy walking music in
every kind of place.

### 2.5 Characters, families and takes

| | Warcraft and Knight Rock | House |
|---|---|---|
| Character: a kind of track | `orchestra.Character` in `orchestra.CHARACTERS`: 149, of which 131 Warcraft and 18 Knight Rock | none; palettes by kind of place (`house.PALETTES`) |
| Family: the changes | `orchestra.Family`, from `orchestra.family(character, seed, name, title)`: key, tempo, metre, lift, the chord under every bar, part lengths and levels | `house.Family` in `house.PLAN` (89): tonic, loop, five lengths, kick pattern, swing, drum machine, palette |
| Take: one band playing it | `orchestra.Take(fam, take)`: tunes, figures, bass, drums and players, from its own seed | `house.Take(fam, take)`: sounds and ways chosen in turn (`Take.pick`) |

A character's fields: `kinds`, `role`, `light`, `serves` (what it is for, 2.6); `modes`, `bpm`,
`metres` (what a family draws from); `busy` (how many notes its tunes have); `weight` (how big its
moment is, 0.5 a handful of players, 1 everyone); `leads`, `strong`, `under` (who states the
theme, who carries it at the moment, who answers underneath); `pads` and `pad_ways` (pad, tremolo,
arp, drone); `plucks` and `figures` (the accompaniment); `basses`, `kit`, `drums` (pitched drums
that join the hits), `grooves`; `hall` (seconds of ring, and how much); `lift` (how likely the
second wave is a key higher); `titles` (two word lists); `style` and `band`.

**The plan** (`build.plan`):

| Role | Families and takes |
|---|---|
| wander, heavy orchestra | 3 takes, and later a second family of 2 |
| wander, light or band | 3, then 2 |
| town, battleground | 3, then 3 |
| battle, ember, storm, boss | 2, then 2 |
| depths, night | 2, and later 2 |
| camp | 2 and 2, planned after all the above |
| added after the camps (`build.LAST_ADDED`: the bosses deep tide and fallen crusade) | 2 and 2, planned last |
| every character once more (`build.MORE_FAMILIES`, 2026-11-22) | 2, planned after everything: Knight Rock's, then Warcraft's |

That gives 471 Warcraft families with 1,034 takes (about 8,200 minutes) and 108 Knight Rock families
with 239 takes (about 1,900 minutes). House has 89 families of 3 takes (`house.TAKES`, about 1,300
minutes).

*More music for every scenario* (2026-11-22: "The drive is still at 11 percent tonight we need new music
following everything we learned"; "lets work on filling that drive with more music for every scenario,
following everything weve learned"). Each character has `build.MORE_FAMILIES` more families of two
takes beyond the plan's own (one so far: 36 Knight Rock families and 157 Warcraft, 386 takes, about 50
hours), each with its own key, pace, changes and tunes, and written by everything the handbook has
learned, as any take is. They are numbered on from the character's own (`haunted-requiem-4`) and named
after every family before them, so no family made before changes; a family numbered ten would take the
next character's seed, and `build.plan` refuses it. Each one's first take is made and studied before
its second (8.7). Their first takes go to the night lane before the second takes of any of them.

**Seeds and names.** A family's seed is 20261115 × 100 + its character's index × 10 + its number,
0 for the first (`build.MASTER`). Its name is the character's first kind (or `anywhere`, for a
character of five kinds or more), the character and the number: `haunted-requiem-1`. Its title is
drawn from the two word lists and is unique. A take writes from `Random(seed × 9973 + take × 7919
+ 5)`. A House family's seed is the CRC-32 of its name, a take's `seed × 7 + take`. The same family
and take always write the same notes.

**Kin.** In the player, pieces of one family at the same place in the story, of the same length and
bar, are kin (`forever.js`, `_index`). `_cast` takes each channel from any of them, keeping whoever
played that channel in the piece before: the same story, told by another band. So a family's
changes, key and tempo must never change once a take of it exists (`orchestra.family`). What has
been heard counts by family and goes round (`_rotation`): a family never heard comes first, one
heard costs 1.2 and up to 1.0 more for each of its last three hearings (falling away over some six
hours), remembered for 60 days; a sister family (the same name but its number) heard in the last two
hours costs 0.8 ("for us to hear new songs every night and it not go back to those old ones until it
finally goes back around", 2026-11-17).

### 2.6 From a staged track to pieces

`studio.import_track`, run by `freerock pieces add` and `tools/fresh_bucket.py`:

- gives the whole track one gain: its loudest section to −12 LUFS (`forever.PIECE_LEVEL` −13 plus
  `studio.LIFT` 1), its peak no higher than −1 dBFS, then `level_db` (House: ember −4, camp −3,
  night −2 dB; the comment in `house.Take.meta` saying the import does not read it is out of date);
- makes one piece per section, each pointing to the one before, so the player runs on;
- leaves a channel out of a piece where its peak stays under −72 dB (`studio.QUIET`);
- gives each part 6 s of what follows (`forever.POST_S`), to fade under the next piece;
- keeps parts in stretches of about 52 s at most (`forever.WINDOW_S`), as 16-bit FLAC;
- skips a track whose source (`style/family/take`) is in the bucket already.

| Field | From | What the player does with it |
|---|---|---|
| `role` | the role | the kind of moment; a mismatch weighs 10 (`_off`) |
| `moods` | `kinds` | the kind of place: 0 the place's first kind, 0.3 another of its kinds, 0.6 a neighbouring kind, 1 none (`_mood`) |
| `settings` | `orchestra.SETTINGS_OF`; none in House | the ground (woods, water, heights...): 0.35 against other ground, half that for none (`_setting`) |
| `light` | `light` | the turns of 2.4 |
| `floor` | `build.FLOOR`, `house.Take.meta` | the least a channel plays at: level = max(level, floor × bed × hush) (`_level`) |
| `follow` | `{"rhythm": ["lead"], "texture": ["lead"]}`; House `{"rhythm": ["lead"]}` | a channel kept as loud as the loudest of those |
| `serves` | `serves` | the strengths it answers, 0 calm, 1 steady, 2 hard; a mismatch weighs 100 |
| `tonic` | the section's key | its shade, −3 grim to 3 radiant, from mode, light and kind (`_shade`) |

`serves` is (0, 1) for walking, night, ember, depths, town and camp music; (2) for battle and boss;
(1, 2) for Warcraft and Knight Rock storms; (0, 1) for House storms; (0, 1, 2) for battlegrounds.

| Floors | open | theme | rise | moment | close |
|---|---|---|---|---|---|
| Warcraft and Knight Rock (`build.FLOOR`) | rhythm 1.0, bass 0.85, drums 0.6 | rhythm 1.0, bass 0.85, drums 0.55 | rhythm 1.0, bass 0.9, drums 0.75 | rhythm 1.0, bass 1.0, drums 0.9 | rhythm 1.0, bass 0.85, drums 0.55 |
| House, most roles | | drums 0.6, bass 0.5 | | drums 0.6, bass 0.5 | |
| House, ember and camp | | drums 0.5, bass 0.4 | | drums 0.5, bass 0.4 | |
| House, fights | drums 0.9, bass 0.85 | the same | the same | the same | the same |

---

## 3. Warcraft, as orchestra.py writes it

`Take.__init__` runs `cast`, then `lead`, `texture`, `rhythm`, `bass`, `drums`, `war_drums` and
`marks` (which ends with `colours`). Everything is written in steps of the scale (`theory.Line`)
and becomes pitches only when an instrument plays it (`Take.sing`, `theory.Key.pitch`), so a tune
fits any chord and a whole wave can move up a key.

### 3.1 A theme, and how it repeats and varies

`orchestra.theme` writes eight bars, or sixteen: a question of eight that ends away from home, and
an answer that begins as it did and climbs home.

- **Rhythm.** `orchestra._cell` fills a bar from `_SPLITS`, with more notes the busier the
  character. A motif has two notes at least. A second theme's motif puts its longest note first, a
  `broad` one joins its first two notes, and `unlike` keeps it from the first theme's rhythm.
- **Order.** Motif, answer, motif, answer, a busier cell, the motif or that cell, answer, a
  whole-bar end.
- **Shape.** `orchestra._shape`: rise, fall, arch, dip, turn, leap, wave or thirds.
- **The spine.** Each bar begins on a chord note aimed at a height from `_HEIGHTS`; the highest
  comes in the sixth bar. The fourth bar and a question's last land on the second or the fifth, an
  answer's last on the key note. No three bars begin on one note; a leap of over four steps costs.
- **Inside the bar.** In a bar of three notes or more the last leads by step into the next bar. A
  long note sits on the chord. Strength is 0.62 + 0.3 × height, 0.08 more on the bar's first note.
- **Tidying.** `orchestra._smoothed` moves a note heard three times running and brings in any leap
  over an octave; `orchestra._singable` keeps a tune within two octaves.

**Variation.** `orchestra.varied` is the theme the second time round: thirds filled with passing
notes, turns on some long notes. `orchestra.decorated` is the third time round, at the moments: the
next note anticipated, a turn round the longest note, passing notes (*at the moments the theme and
its first variation took turns, so that the third time round was the first again, note for note*).
The second theme begins high and comes down before it climbs, and is broad where the first is busy
and busy where it is broad.

**Through the story** (`Take.lead`). The first theme's statements take turns: the solo; another
player with `again`; the conversation (3.3); the solo doubled an octave away. The second theme: its
singer; a partner with `again_b` while the singer holds a slower line; both an octave apart. The
build and the climb use fragments, each moved onto a chord note (`Take.fit`) and aimed higher; a run
up the scale ends each rise short of the bar line. The arrival and the summit cycle through `tune`,
`again` and `adorned`, keeping their strength between accents. Fights and regal music end on the key
note; half of the other takes end on the fifth, *so that its mood carries into the quiet after it*.

### 3.2 Harmony and modes by kind of place

A family draws its mode from `Character.modes`. How many Warcraft characters offer each mode, by
the first kind each is written for:

| Kind | Modes offered |
|---|---|
| pastoral | major 21, dorian 18, mixolydian 18, lydian 11, minor 9, phrygian 4 |
| highland | dorian 15, minor 9, mixolydian 8, lydian 4, major 4, phrygian 3 |
| haunted | minor 20, dorian 9, phrygian 8, major 1 |
| desert | phrygian dominant 13, dorian 8, mixolydian 5, minor 3, phrygian 3, major 2, lydian 1 |
| jungle | dorian 11, minor 8, lydian 2, major 2, mixolydian 2, phrygian 2, phrygian dominant 2 |
| infernal | minor 8, phrygian 7, dorian 2, mixolydian 1 |
| regal | major 7, dorian 4, lydian 4, mixolydian 4, minor 2, phrygian 1, phrygian dominant 1 |
| mystic | dorian 10, lydian 8, minor 5, major 3, phrygian 3, mixolydian 1 |
| marsh | dorian 2, lydian 1, minor 1, mixolydian 1, phrygian 1 |
| coast | dorian 3, mixolydian 2, lydian 1, major 1, minor 1 |
| frozen | dorian 2, lydian 1, major 1, minor 1, phrygian 1 |

(The characters written for every kind of place, `KINDS_ALL`, are counted under pastoral, their first. The marsh, the
coast and the snowfields have few of their own so far; the pieces of the kinds nearest them (`forever.js`, `NEAR`) are
played there too, and many older characters were given the new kinds besides their own.)

The changes (`orchestra.family`):

- **First theme**: four chords of two bars (or eight of one) from `THEMES[mode]`; a key chord in the
  fourth bar is moved away from home, and the last two bars are the mode's way home (`HOME`): major
  5–1, lydian 2–1, mixolydian 7–1, dorian 4–1, minor 5+–1 (the dominant with its third raised),
  phrygian and phrygian dominant 2–1.
- **Second theme**: three chords of two bars from `SECONDS[mode]`, *on the mode's other side (the
  relative key of a minor one, the fourth or the sixth of a major one)*, then home. It is drawn again
  if it comes to the first theme's eight bars.
- **Rises** come from `RISES[mode]`. The climb is a rise, then two chords swinging, then the chord
  before home, held.
- **Opening and close** sit on the key chord and stir to the colour chord (`COLOUR`): major and
  dorian 4, lydian and both phrygians 2, mixolydian 7, minor 6.
- **Tried and left off: Warcraft's opening walking** (`OPEN_WALKS`, 2026-11-20). After a bar or two of
  the key chord where bars are over, it went through the first theme's changes slowed to fill it (each
  bar of the theme one, two, three or four bars), from the key chord to the chord before home; Crooked
  Round's 32 bars fell i, VII, VI, V eight bars each, Deep Hall Hearth's 16 went i, III, VII, IV. *The
  judges had the open the weakest of Warcraft's nine parts (TuneJury 0.43 against 0.70, enjoyment 6.31
  against 7.29), the meter its pads one colour 16 to 18 bars.* Heard before and after on five takes, the
  open went a little up on the Warcraft brief, a little down with none, its enjoyment level on average:
  Old Corpse Road up on all three (+0.93 enjoyment), Crooked Round down on all three (-0.97). The meter
  heard the pads move. It is kept for the ear to decide (the listening page has the pairs).
- **The lift**: with chance `Character.lift`, the climb, summit and close are 2 or 3 semitones up.

Chord figures follow `theory.Key.chord`: `1` to `7`, `+` or `-` to raise or lower the third, `7`
after the step for a seventh, `s` for a fourth in place of the third, `o` for a bare fifth.

### 3.3 Counter-melody and the conversation

- `orchestra.answer` writes a slower line under a tune: a note or two a bar, on the chord, moving
  against the tune, never on its note, about an octave below. From a theme's second statement an
  instrument of `Character.under` sings it (*it is stated alone once, then the band fills in*);
  at the arrival `under[0]` has it.
- `orchestra.recast` fits the second theme to the first theme's chords, each bar moved at most a
  step, and the summit sings it under the first theme. Where the theme comes round more than once,
  the first round has only the slower line, *so that the two themes together are the last thing
  to arrive*.
- **The conversation.** In the first theme's third statement one player asks (the first half) and
  another answers (the second). *In the orchestral scores studied, who is playing changes every two
  bars or so; here it changed only from one statement of a theme to the next.*

### 3.4 Accompaniment figures and ostinati

`Take.rhythm` plays one figure under the first theme and another under the second theme and the
valley; if both are the same on the same instrument, the second is a fourth higher.

| Figure | What it plays |
|---|---|
| pulse | repeated chord notes on the eighths (sixteenths when full and slow); the outer notes on strong beats |
| arp | a broken chord on the eighths, in another order for the second theme |
| strum | down-strokes on the strong beats, up-strokes between, 0.012 of a beat between strings |
| oompah | the chord off the strong beats |
| rock | a rocking broken chord on the pulse |
| toll | the chord's lowest note an octave up on the bar, its top note on the second group, every other bar |
| gallop | a gallop on each beat (on it, a half and three quarters after) |
| hammer | the whole chord on 1, the and of 2, and 4, the lowest note an octave down under it |
| pattern | a take's own walk through the chord, on the eighths |
| riff, chug | the band's power chords (section 4) |

How full it is: open 0.15, first 0.5, second 0.45, build 0.5 to 1.0, arrival 0.9, valley 0.2
(fights 0.5), climb 0.35 to 1.0, summit 1.0, close 0.4 to 0. Under 0.45 it thins out. In the opening,
and in a valley outside a fight, the orchestra plays only a toll, rock or arp, every other bar, and
nothing against a harp's valley. `fuller` adds the other theme's figure at 0.72 on its own
instrument: at the moments, from each theme's second statement and through the second half of each
rise. At heavy moments the trombones, horns and trumpets mark the chord, on the bar at the arrival
and on every strong beat at the summit: *until then the heavy brass has rested, so that it means
something*.

**The breath.** For the last beat or two of each rise (`Take.breath`: at least 0.45 s, at most
half a bar) the tune rests and the accompaniment stops striking, so the arrival's downbeat lands.
The big drums' ostinati are in 3.7.

**A long moment goes up a gear every second phrase** (`orchestra.GEARS`, `Take.geared`, 2026-11-19).
In an arrival or a summit of sixteen bars or more, every second eight-bar phrase has the
accompaniment's figure an octave up, the two lines over the pad given to the horns an octave lower (a
warm call the second time round), and the drums a step busier (`BUSIER_STROKES`: a stroke on the bar goes to the strong
beats, the strong beats to every beat, every beat to the eighths) with the cymbal twice as often;
the next phrase comes back down. *The boredom meter had heard Warcraft's summits keep one colour for
16 to 24 bars in the drums, the accompaniment and the texture (Withered Circle, Elder Boughs, Quiet
Nave, Twilight Song): an orchestra's climax that plays its eight bars the same way three times.* The
two lines over the pad were raised as well, first an octave, then a fifth: either way they put 8 to 13
dB on the texture's top between 5 and 10 kHz in those bars (Withered Circle), the texture 7 dB over
the liked stems at 7 kHz across the whole take; the horns, an octave under, brought the texture
toward the liked stems instead (226 Hz from -3.2 to -0.2 dB) with its top within 0.5 dB. Measured on
the demos, the accompaniment's octave moved toward the liked stems and the drums stayed within 0.2 dB;
the meter's runs in Withered Circle's summit went from 20-23 bars to 7-15 in every channel. A band's moments go their own way (4.9).

### 3.5 Pads with moving inner voices

`Take.texture` lays a chord in every bar for two to four players, centred between MIDI 53 (open)
and 62 (moments), five higher in light music; under a second theme sung high the pad sits low, and
the other way about. `theory.voiced` moves each player to the nearest note of the next chord. For
strings each player is a section (`DESKS`, `Take.desk`): celli, violas, second and first violins.
The way is `pad`, `tremolo` (in the open and the rises), `arp` (the harp, outside the rises and
moments) or `drone` (root and fifth, not at the moments).

*In the scores studied an inner voice holds one note through a bar one time in fourteen; this pad
held every note until the chord took it away.* So one voice that must move does it as an
orchestra's does: a step down is held into the bar and let fall (a suspension); a third is filled
with the note between at the end of the bar (a passing note); on a repeated chord an upper voice
moves to another chord note halfway through. How often, by part: open 0.5, themes 0.6, build 0.4,
arrival 0.3, valley 0.7, climb 0.4, summit 0.25, close 0.7. Each pad voice carries a swell, 0.3 +
0.62 × level every half bar, which becomes MuseScore's hairpins or the sampler's controller 1; in
the valley it is 0.55 of that (`VALLEY_PAD`), under the tune: its floor of 0.3 kept the pad at
mezzo-piano while the tune went down to pianissimo, and a band's drone stood 9 to 11 dB over
everything else there, a bagpipe or an organ held all but alone ("sometimes when one synth stays
in when youre sitting its whiny and annoying mix better", 2026-11-17, played). At
heavy moments two lines sit an octave above the pad (the violins, or oboe and flute when the
violins are busy), and the summit adds the choir where the palette has one.

### 3.6 The bass line

`Take.line` picks a note for each bar: the root on a phrase's first and last bars; between them the
root, the third (cost 0.8) or the fifth (cost 2.2), whichever moves by step. A repeated note costs
1.6, a step nothing, a third 0.7, a fourth 1.0, a tritone 3.0. *A real bass repeats its note one
time in four and moves by step two times in five; this bass repeated its note one time in two and
sat on the root nine times in ten.* The opening and the moments of heavy music keep to the root.
`Take.between` finds a note on the way: the scale note inside a third, a chord note inside a wider
leap, or a third aside for a step.

| Way (`Take.bass`) | What it plays |
|---|---|
| long | the bar's note held; in a grim valley a contrabassoon an octave under |
| two | the bar's note, then a passing note or another chord note on each group |
| walk | notes on the way, the last a step from the next bar's note |
| oct | the note and its octave on the pulse |
| pulse | the root on every pulse: the drive at the top of a climb |
| eight | eighths on the root that lead into changes (4.7) |

The first theme, build, arrival and summit take one way, the second theme and the first half of the
climb another, the valley (outside fights) and the close `long`, the open the key note held (the chord's root
under a walking open, where `OPEN_WALKS` has it walk). The
second time round a theme the way gets busier (`BUSIER`). From each theme's second statement,
through the second half of each rise and at the moments of music that is not heavy, the neighbour
doubles the line an octave away at 0.8 (`PARTNERS`). At heavy moments bowed celli and basses play
the root an octave apart, with the contrabassoon in grim music and, at the summit, the tuba and
trombones where the palette has them.

The line keeps within nine semitones under and eight over its centre: its instrument's home less 5,
but never above A2 (`orchestra.BASS_TOP`, `bass_centre`). An organ that plays the bass plays it on
the pedals, a harp on its low strings. (2026-11-19: Stained Glass Choir's organ, centred where it sits
as a pad, played its bass from A2 to F#4 around A3; the desk raised it 8.9 dB to its place, a tenor's
line 7 dB over the liked stems in the mids and 16 at the top, with nothing under it. The moonwell and
the elven hymn had the harp's the same way, around B3.)

*Tried and left off: a plucked bass played to be heard* (2026-11-22, morning: in a night's studies of Warcraft's walks,
inns and camps the bass stood 7 to 12 dB thin in its middle wherever its line was plucked, never where it was bowed or
blown). The fretless struck no softer than mezzo-forte (`orchestra.FRETLESS_FIRM`, 0.55): its tone did not change (MuseScore's
fretless is dark at every strength), the judges level. A pizzicato line's key note no lower than D2
(`orchestra.PIZZICATO_FLOOR`, 38): the bass 2 to 7 dB fuller from 450 Hz up, Gull's Wind up with every judge, but White
Hearth, its line a whole octave up, lost its lowest octave and came out down: a bass's place is low. Both switches are
kept, off; a fuller pizzicato is owed another way.

*The bass follows the key* (`orchestra.BASS_FOLLOWS_KEY`, `bass_tonics`, 2026-11-20). Each part's key
note for the bass is the one nearest the part before's, moved by octaves into the instrument's range
with room for the scale over it, and the part's line is centred on it: a key lifted for the summit
lifts the bass with it. The key note had been the one nearest the line's centre in every part, so in
18 of Knight's 71 parts that go up a key the bass went *down* about a seventh (Frost Hammer's climb,
C# phrygian to E, from C#2 to E1), and in Eb, whose key note nearest the centre is under a bass's
low E, the key note alone was lifted an octave: Blood Machine I played its key note on Eb2 and its
bII on E1, a major seventh under it, where the phrygian half step should be. The judges heard
Glacier Hammer III's climb and summit level (TuneJury 0.468 to 0.480 with the Knight brief, 0.563
to 0.587 with none, enjoyment 7.00 to 6.98): a register is not a thing they hear, and a bass that
goes up with its band is.

### 3.7 Percussion phrasing and fills

A groove (`GROOVES`) has layers for the theme and for the moment, a roll and a hit; a layer is a
stroke, a place in the bar (`Take.spots`: down, groups, pulses, back, offs, halves, ands, gallop,
last, kick, kick busy, three, mid), a strength and every how many bars. `KITS` maps strokes to
notes for the orchestra, march, folk, hands, wood, rock and room kits.

`Take.drums`, part by part:

- **Themes**: the groove's theme layers; the second time round the moment's small percussion
  (`SMALL`) joins at 0.55. The second theme has its own groove, or the first less its last layer.
- **Phrasing**: each phrase's last bar ends with a pickup on the roll (three sixteenths, or two
  eighths in compound time), rising, and the next opens on the light hit (a triangle for a crash,
  unless the music is heavy).
- **Rises**: the theme's groove, then the moment's at 0.7 (from half the build, 60% of the climb);
  a roll of sixteenths over the last bar (two in heavy music, doubled in the climb), from 0.2 to 0.9.
- **Moments**: the moment's groove (0.85 at the arrival), the hit on the first beat (with the
  character's pitched drums in heavy music), a four-stroke fill every eighth bar.
- **Open and close**: the theme's groove on every other bar of the first half, at 0.7.
- Where the big drums play, the orchestra's own low drums leave the low end to them and the timpani
  only mark the bar. Timpani take the key note or the fourth below, whichever is in the chord.

**The big drums** (`Take.big`, `Take.hands`, `Take.war_drums`). A fight has war drums nearly all the
way; heavy walking music has them in each rise and its moment; lighter walking music of the desert,
jungle and highlands (weight 0.6 or more) has frame drums. Lively lighter walking music (weight 0.6 or
more and busy 0.55 or more, or weight 0.5 and busy 0.45 where its grooves are not all delicate ones:
sparkle, tick, rain, drip, bog, brushes, none; and never a dance: no jig, reel, waltz or courtly groove)
has them too, softer (`Take.soft_war`, since "just a bit light and wimpy in general", "dont hear much war
drums", then "go a little harder this is not world of fairy craft", 2026-11-17): from 40% of a rise at 90%,
under the arrival at 0.8 rather than on it, the deep stroke at the summit only (0.92), and frame drums
with them; a hymn, a morning, a music box or a dance has none. Night, inn, cave and camp music has none.
In walking music they come in low at 30% of a rise, play the whole ostinato from 60 to 65%, and grow;
every drum strikes together on the bar at the moments; the close lets them fall away. A fight
begins with every drum at once. `Take.war_cycle` writes the take's own ostinato of two or four bars:
the biggest drum (36) on the bar, the next (38) on the other strong beats, a smaller drum's pickup
into them, and between them eighths, a gallop or a sparse stroke; every fourth bar ends with a run
down the drums (47, 45, 43, 41). A rise ends in a roll on two drums, never under seven strokes a
second, up to the arrival.

**What marks a moment** (`Take.marks`, `Take.colours`):

| Mark | Where |
|---|---|
| cymbal swell | ends on the moment's first beat, from 2.5 + 2w s before the arrival and 4 + 3w s before the summit |
| deep stroke | each moment's first beat and each round of the theme there, where there are war drums |
| gong | the summit of heavy orchestral music with war drums (weight 0.9 or more), unless the tam-tam has it |
| anvil | fire music with war drums and no forge: every fourth bar of the arrival, every second of the summit |
| tam-tam | the summit of grim heavy music, a boss's arrival, softly as a dark cave's music opens |
| mark tree | into each moment of light and mystic music |
| soft cymbal roll | into the moments of quieter music that has no swell |
| field drum | a roll into the moments of regal and battleground music; at the summit a march on the off-beats |
| taikos | four rising strokes into the moments of heavy jungle, fire and desert music and fights; the summit's strong beats |
| concert bass drum | a rumble under a storm's rises |

### 3.8 Orchestration

**Who plays.** `Take.cast` turns `leads` by take into the solo, mate and third. The second theme
goes to `other`: one of the other leads, `under`, `strong` or the pads that can sing (`SINGERS`),
at least five semitones from the solo's register. In the valley a player who has not stated that
theme sings. Pads, plucks, figures, basses and grooves turn by take too. Each piece draws its Muse
Sounds from its seed (`muse.CHOICES`): six horns twice as often as one, and in one piece of three
the harp's part is a piano's.

**Registers.** Each instrument has a range and a home (`orchestra.INSTRUMENTS`): flute 60–96 round
79, violins 55–96 round 74, celli 36–72 round 50, basses 28–52 round 38, horns 41–74 round 58,
trumpet 55–82 round 70, tuba 28–55 round 40. `Take.sing` places a line round the home and moves it
by octaves to fit; `Take.put` folds stray notes in. Some ranges were set by ear: *Muse's euphonium
under C3 was found to sound an octave up and 18 dB soft*, so it stays above.

**Doubling.** A second player doubles in its own register, an octave off where the two sit far
apart; high woodwinds and bells go an octave above (`octave_of`, `HIGH`). The summit is crowned by
a piccolo an octave up in heavy music, a glockenspiel otherwise. Pad lines and bass partners are in
3.5 and 3.6.

**What the desk stacks on** (`build.stage`; "stack on top of this for interesting layers"):

| Layer | Where |
|---|---|
| a wide synth pad (ZynAddSubFX `Full Strings`, −13 dB) | under the string pad, all the way |
| a kick on the bar, and on the half bar at the moments of music that is not light | through each moment and the last 40% of each rise; not in night music |
| a sub (Surge XT `Sub 1`) on the bass's notes | the moments of music that is not light |
| low brass on the bass's notes | the same, where no tuba or trombone plays already; never under a band (a tuba had doubled the rock bass, 8 to 15 dB over the liked stems from 450 Hz to 1.8 kHz, 2026-11-18) |
| a bell on the moment's first beat | where the crown has one |
| the crown | the moments: choir, horns or oohs by kind of place (`build.CROWNS`, `CROWNS_LIGHT`); the full choir for bosses and battlegrounds |

**Seating.** The studio's own players sit where `sounds.SOUNDS` puts them (violins −0.4, violas
0.12, celli 0.3, basses 0.45, horns −0.28, trumpet 0.2, trombone 0.32, tuba 0.38, harp −0.45), and as
far back as `sounds.DEPTHS` says (strings 0, woodwinds 0.45, horns 0.6, trumpets and trombones 0.65,
percussion 0.85 to 0.95), by early reflections (`sounds.row`). `Take.voice` gives each voice a pan
within ±0.35, used only where a player has no seat. MuseScore's recordings are laid in at the centre,
except the band's heavy guitars; any placement the Muse Sounds carry themselves is (unconfirmed).

*Tried and left off: a calm arrival keeps its rise's singers* (`orchestra.CALM_ARRIVAL_JOINS`, 2026-11-22: three caves in
one night's studies came to their arrival no louder than their rise; one cave in nine and one night in eight of all those
studied). The rise is sung by its soloist, its partner joining at two fifths of the way and the strongest player at seven
tenths; the arrival is the strong players'. Where those are soft (slow violins, a glockenspiel) and the rise's bright (a
high flute, the vibes), the moment came in under the rise. With the rise's two singers on through the arrival's first
statement the moment came in over its rise in all three caves, by 0.6 to 1.9 dB, but the judges did not agree (enjoyment
up on two, TuneJury with no brief down on the same two, the rest level), and the switch would change every calm piece for
a flaw in one cave in nine: kept, off. A calm arrival is a release more than a climax; a cave whose arrival does not
arrive is owed a narrower fix.

### 3.9 Dynamics and articulation

- Strength comes from `Take.hard` (2.2). `Take.put` gives a held note 0.97 of its written length,
  a tied one all but its last 0.05 s, and never less than 0.11 s; a bowed note in a figure stays a
  short stroke (0.2 s at most).
- `muse.score` writes each part as a player would get it: marks pp to ff at strengths 0.30, 0.42,
  0.54, 0.66 and 0.80 (`muse.MARKS`), a new mark only when the strength truly moves; an accent on a
  jump of 0.13; staccato under 0.28 s; slurs over a single line whose notes follow within 0.09 s;
  tremolo strokes or `pizz.` where the part says. A note of 2.5 s or more (`LONG_S`) gets a hairpin:
  leaned into, fullest past its middle, eased off, further at a phrase's end. The writer's swells
  become hairpins. Struck instruments get no dots or slurs; the lead guitar's long notes are left to
  die away.
- The studio's own sampler draws controller 1 under each held line (`sounds._dynamics`): each note's
  strength, a lean into notes of a second or more, a fall at a phrase's end. A line of single notes
  is slurred (`sounds._slurred`).

### 3.10 Humanising

`build.stage` runs `score.humanise` on every voice: each note moved by a normal spread of 4 ms
(drums) or 7 ms (the rest), and its strength by 6%. The sampler's instruments vary each note by a
few milliseconds, cents and fractions of a dB, and take turns between recordings made more than
once (the `sfz` module). MuseScore's players perform as players. All of it is seeded: a take is the
same every time.

---

## 4. Knight Rock

Knight Rock is written by the same `orchestra.Take` with `Character.band` set. It keeps the nine
parts and their levels. This is what differs.

### 4.1 The band

| Written name | Played by | Seat and tone |
|---|---|---|
| rhythm guitar | two Muse parts: `Electric LP - Heavy` and `Electric SC - Heavy` | LP left (−0.6, 4 dB up), SC right (+0.65, 5 dB down, 11 ms late): *two takes are never together to the sample* |
| muted guitar | the same two, played short | closed above 3.2 kHz |
| single guitar | the LP alone | a heavy band's opening riff |
| lead guitar | `Electric LP - Lead` | more at 260 Hz, less at 3.2 kHz, echo and tape |
| clean guitar | `Electric SC - Clean` | the valley's tune; a band's plain `guitar` becomes it (`build.stage`) |
| picked bass, fretless | `Electric Bass` | more at 800 Hz, narrowed |
| rock organ | `Hammond Organ` | less at 1.5 kHz, narrowed |
| kit rock, kit room | the AVL Red Zeppelin kit (a 26-inch bass drum), the Black Pearl kit | the kick under the bass drum, 6 dB down |

The light pieces are *the same band unplugged*: fiddle (a Muse solo violin), whistle (piccolo),
harmonica (a blues harp: VCSL's Hohner Special 20s in C and F, through a harp player's amp, below), accordion (TinySOL's, in the sampler), steel-strung guitars and mandolin
(Muse acoustic guitars), banjo (a strumstick in the sampler), ocarina and pan flute (Muse flutes).
Hall sends are small: rhythm guitars −19 dB, muted −22, lead −11, bass −26, organ −14
(`sounds.MUSE_SENDS`). Channel places at the summit (`build.BAND`): lead −17, rhythm −18.5, drums
−17.5, bass −19.5, texture −24 LUFS; lighter pieces (`BAND_LIGHT`) drums −18.5, bass −19.5, rhythm −18.5.

**The harmonica is a blues harp** (2026-11-21: "You gotta work on your fucking harmonica. Look up John Popper";
`sounds.BLUES_HARP`). It was VCSL's chromatic Super 64, smooth and even, a canned vibrato on every held note: the
wrong instrument for a rock band's harp player. Now VCSL's Hohner Special 20s, the diatonic harp of the blues and of
Popper's first records, a C harp and an F harp together (three notes an octave each, so no note is stretched more
than a tone; `samples/merged/blues-harp`, links to their recordings): held straight for the long notes, the staccato
takes for the quick ones, the hand vibrato's cupped wah for the wails. Through a harp player's amp (`sounds.harp_amp`,
Calf's saturator): the bullet microphone's band (250 Hz to 5.5 kHz), the tubes warmed, the reed's honk lifted at
1.4 kHz, the speaker's top rolled off, a slapback a sixteenth behind. *The judges, against the chromatic harp on
three songs: SongEval up in five windows of six (Whiskey Groove's solo end +0.27 on every score), TuneJury with the
brief level, with none down on two songs.* Driven 18 dB harder into the tubes, as a harp cupped round a bullet
microphone can push an amp, it was tried and left off: SongEval 0.11 to 0.14 down where the harp carries the tune
(Whiskey Groove's theme), the rest level. Its playing is a harp player's (4.10).

**The tune stands over the guitars wherever it sings** (`build.TUNE_LIFT`, `build.tune_lift`, 2026-11-19). The
lead's place is set at the summit, where the twin guitars play the theme together; one guitar or a fiddle singing it
alone in a theme was left there, and across all 144 Knight takes the tune sat level with the rhythm guitars in the
first theme (median −0.4 dB, half of them under). In every part of the story but the open (the riff alone) and the
solo (lifted by its own measure), the lead is brought up until it stands `TUNE_OVER` (2 dB) over the rhythm
guitars, at most `TUNE_MOST` (5 dB), eased over a beat from part to part, on the lead's stem and its envelope in the
mix; each take keeps what it was given (`measured`, "tune lift"). King's Oath: 2.3 dB in the first theme, 3.8 at the
arrival, 5 in the valley. *The tune is the band's singer.*

### 4.2 Riffs

A riff is power chords with room between them (`Take.rhythm`, figures `riff` and `chug`). `riff()`
picks the bar's rhythm from six for 4/4 (for example hits at 0, 1½ and 2½ beats) or three for 6/8,
and another for the second theme. Each hit is root, fifth and octave, the root kept between E2 and
E3: *the third is left to the tune*. `chug` fills every free eighth with a muted root and fifth, and
so does `riff` where the music is fullest.

### 4.3 Licks

*The riff answers its chords, with fills of the take's own* (`orchestra.OWN_LICKS`, `Take._fills`,
`Take._fill`). Where the riff is not thin, the second bar of each four ends with the take's answer and
the fourth with a turn; a take has two turns and uses them in turn, so the same fill comes every eight
bars, not every four. They are drawn once for the take, on a generator of their own, from what the
lessons on Malcolm's and Angus's playing teach (Premier Guitar, MusicRadar, Guitar World, 2026-11-19):

| Fill | What is played | As the answer | As a turn |
|---|---|---|---|
| a run | single picked notes to the bar line, sixteenths (eighths over 150 BPM), from `FILL_RUNS`: the minor pentatonic with the blues note, mostly falling into the chord | 0.3 | 0.4 (0.3 in a major key) |
| a bright run | the same from `BRIGHT_RUNS`, the major pentatonic, only in a major, mixolydian or lydian key (Angus mixes the two) | | 0.1 |
| the curl | the minor third hammered to the major, then the root or the fifth (`CURLS`) | | 0.15 |
| double stops | two notes at once on the last two offbeats (`DOUBLE_STOPS`: fifth and octave, third and fifth, fourth and sixth) | 0.2 | 0.15 |
| stabs | the riff's chord struck on the last two offbeats | 0.2 | 0.1 |
| the turn chord | the flat seventh's power chord on the last beat, back to the root on the bar | | 0.2 |
| ring | no fill: the last chord struck before the last beat rings to the bar line ("let a held chord ring") | 0.3 | |

**The riff moves, its own way** (`orchestra.RIFF_MOVES`, `Take.riff_move`, 2026-11-19: "still need more
complex leads and riffs"). Each band take draws one way its riff moves inside the bar, for the whole
take, so the riff is the song's own: *rock* (the chord struck in the second half of the bar is the
fourth's, over the same root, and back: I to IV), *drop* (the last chord of the bar is the flat
seventh's, leading back to the root), *pedal* (the low root alone, palm-muted, on every eighth between
the chords), or *push* (a stab on the last off-beat). **The second turn is a variation of the first**
(`Take._varied`): the same run a step of the scale away, the other curl, the double stops the other way
round, the turn chord answered by stabs. *SongEval's coherence had fallen on King's Oath with two
unrelated turns.* **The riff listens to the lead** (`orchestra.MOVES_LISTEN`, `Take._rubs`, 2026-11-19,
13:20): the rhythm guitar is written after the lead, and where the lead sounds a note a semitone or a
tritone from the chord the move would strike (its major third under the IV's chord), the riff stays on
its own chord there; on King's Oath 12 of its 80 moves.

*Until 19 November every band song answered its riff with the same two runs, a walk up to the fifth
(3, 5, 6, 7 semitones over the root) at the end of every fourth bar and a run down the blues scale
(10, 7, 5, 3) at every second, about 32 times a song: "hearing that same guitar riff climb in too
many knight songs", "cant you study acdc and do different licks".* The old walk-up is in no list.
Every note of the lead guitar is moved onto the key's minor pentatonic (`orchestra.BLUES`,
`orchestra.blues`), *as the riff bands of the late seventies did*.

### 4.4 The lone opening guitar

*A riff band opens on one guitar alone, and the second guitar, the chugs and the band come in
together with the first theme.* In heavy band music the opening's riff is the LP alone (`single
guitar`), thin, without chugs or licks. The bass holds the key note under it, and in an opening of
16 bars or more goes with the chord where the harmony leaves home (the riff's fourth, a flat
seventh) and comes back with it: the boredom meter had found one held note 27 bars long. The drums play the
groove on every other bar of the opening's first half, and on its last bar the sticks count the
band in. The reason was measured: *distorted guitars hardly grow softer when played softly*, and the
band's pieces swung 8 dB from quietest to loudest where the orchestra's swung 18.

### 4.5 The clean-guitar valley

*A band's valley is quiet only if its tune is: a distorted guitar is as loud played softly.* In a
heavy band's valley the clean guitar sings the broader theme and answers itself; in a lighter band's
it stands in for the distorted lead only (`Take.lead`). The riff guitars rest through a walking
piece's valley. With the lone opening, this took the heavy pieces *from 8 dB between their quietest
and loudest parts to 17 to 20*.

Under a walking band's valley the drummer keeps time softly (`orchestra.VALLEY_KEEPS_TIME`,
2026-11-19): the closed hat on the beat and the bass drum on the bar, and from the valley's second half
the side stick on the backbeat, the band gathering itself before the climb. *The judges scored Knight's
valleys TuneJury 0.36 with no brief, against 0.9 for its first theme and arrival, and Audiobox's
enjoyment lowest there (6.34): the drummer had stopped for the whole valley, under one player, a pad
and held roots.*

*A band's valley's pad goes under pianissimo* (`orchestra.VALLEY_SOFT`, 2026-11-20): its swell goes to
`VALLEY_PAD_SOFT` (0.35) of the part's level where it went to 0.55, so that MuseScore marks it ppp (the
softest of `muse.MARKS` now), and its held notes are struck at 0.48 where they were 0.60, the church
organ on its soft stops (its two recordings split at 0.62). A held pad written pp still stood over a
single soft tune: Midnight Mass II's church organ 13 dB over its guitar, Thunder Lizard Stomp II's rock
organ and Throne Parade IV's organ and choir 3 to 10 dB over theirs. *The judges heard the valleys go
up: Midnight Mass II's TuneJury 0.27 to 1.01 with the Knight brief and -0.61 to 1.71 with none,
enjoyment 7.08 to 7.54; Throne Parade IV's 0.33 to 0.48, enjoyment 6.88 to 7.32; Thunder Lizard Stomp
II's level; Warcraft's Bone Rite I's TuneJury rose there too (0.19 to 0.54) but its enjoyment fell a
whole point (5.58 to 4.57), so an orchestra's valley, its tune a single soft player over its pad, keeps
the pad as it was: this is the band's.*

### 4.6 The fight valley breakdown

A band's fight valley is short, and *its fight pieces went only 4 to 5 dB between their quietest
part and their loudest*. So it breaks down. In its first half the riff rests under the clean
guitar's theme, the bass holds its roots, and the drummer keeps time on the hats or ride with the
bass drum on the bar. In its second half the groove comes back at 0.65 with the riff and the bass's
second way, and a four-stroke fill takes it into the climb. The test
`test_a_bands_fight_breaks_down_in_its_valley_and_comes_back_before_the_climb` holds it.

### 4.7 The bass leading into changes

A band's bass keeps to the root; in heavy music it plays eighths (`eight`). *Into a new chord the
last eighth is a step away from its root*: a semitone or a tone from the next root, on the side the
line comes from (*the band's bass played one note 85% of the time; the riff bands' bass players lead
into each change like this*).

### 4.8 Drum patterns and fills

| Groove | Theme | Moment | Roll | Characters |
|---|---|---|---|---|
| rock | kick on 1 and 3, snare on 2 and 4, eighth hats | busy kick, open hats, crash every 4 bars | snare | open road, banner ride, battle cry |
| half rock | kick on 1, snare on 3, hats | busy kick, ride, crash, low tom on the last beat | tom | black chapel, mountain stomp, dragon |
| rock ride | kick on every beat, backbeat, hats | the same harder, ride, crash every 2 bars | snare | banner ride, sand rider, storm rider, battle cry, war machine |
| tom rock | kick, low-tom eighths, backbeat | busy kick, toms, crash | low tom (its fills the snare) | jungle stomp, war machine, frost hammer, low tunnel, downpour run, warlord, banner war, bayou boogie |
| anvil rock | kick, backbeat, a struck `ting`, hats | the same harder, open hats, crash | snare | forge anthem, mountain stomp, deep mine |
| desert rock | kick, backbeat, bongo off-beats, jingles | busy kick, open hats, crash | high bongo | sand rider |
| tavern rock | kick, side stick, tambourine | busy kick, snare, tambourine, open hats | tambourine | open road, tavern rock |
| shuffle | kick, side stick, hats | busy kick, snare, open hats, crash | snare | oasis shuffle |
| brushes | side stick, soft hats | side stick, hats, a soft kick | none | lantern walk, moon glade, night watch, campfire |

`kick busy` is 1, the and of 2, 3 and the and of 4. The fills: a pickup into each phrase (each
second phrase in heavy music), a roll at the end of each rise, four strokes every eighth bar of a
moment.

*A drummer fills with what is not keeping time* (`orchestra.TOM_FILLS_ON_SNARE`, `Take.fill_of`,
2026-11-20). A groove names its `fill` where its roll is a drum already playing the beat: on a
groove of the toms the pickups and the moment's fills go on the snare, and the long roll up to the
summit stays on the low tom, the thunder. *Downpour Surge II's summit read the same 19 bars on the
meter: its groove the mid tom on the eighths and the low tom on the beat, and its fill every eight
bars four sixteenths of the low tom, so the fill vanished into the groove and the phrases went
unmarked.*

The cymbal turns (`Take.cymbal`). In a theme, a drummer keeps time on the hat for sixteen bars and
on the ride for the next sixteen, the same figure a little softer. On a groove of the toms, with no
cymbal keeping time, the ride joins softly for those sixteen bars and leaves again. A groove that keeps
time on the ride turns to the closed hat for its second sixteen, tighter after the wash (`orchestra.TURNS_TO_HAT`,
2026-11-19: it had had nowhere to turn). A tavern's
tambourine and side stick, and a theme the drums sit out, stay as they are. At a heavy band's moment
the drummer rides it out the same way: the open hat or the ride goes over to the ride's bell for the
second sixteen bars, or the bell joins a groove of the toms. A light band's moment is left alone.

**A wind player breathes** (`Take.breathe`, 2026-11-18). A harmonica, the English horn's drone or an
accordion holding a pad would hold a chord as long as an organ does, a whole section, which no player
can. A note held longer than a breath (`BREATH`: a harmonica about 5 seconds, the English horn about
6, an accordion's bellows about 9) is played as breaths of whole bars. Each is let go half a beat
before the bar line it reaches and taken up again on it. A bagpipe's bag holds its drone on.

### 4.9 The rest of the band's story

- At the arrival and summit of heavy band music the first bar is a stop: one chord struck together
  and left to ring, the bass on one note, the kit's hit alone. Then the riff.
- At the summit the lead is doubled a third above: twin guitars, after the lead guitar's solo where it
  takes one (4.10).
- In heavy band music the second theme goes to a pad that can sing: the Hammond, a bagpipe, a
  shenai, a pan flute or the choir. Lighter bands pass it between their leads.
- *Under it the band opens out*: the rhythm guitar strikes each chord once and lets it ring through
  the bar (the lick still answers every second bar), with no chugs, and the riff comes back with the
  rise (`orchestra.RING_SECOND`). The boredom meter had found a heavy band's rhythm guitar one colour
  through both themes, 42 to 64 bars: a riff and then a strum or a chug are different notes on one
  distorted sound, and the ear hears the sound.
- *A heavy band's long rise climbs, drives or plays on* (`orchestra.CLIMBS`, `Take.climbs`, `Take.rise_way`):
  each take draws one of the three ways (since 19 November, 08:20, so the climb is not every song's).
  Where a rise holds one chord
  nine bars or more (`LONG_HOLD`; a fight's 36-bar build has two or three chords, each nine to
  eighteen bars), the second half of that chord climbs: the riff's power chords and licks go an
  octave up the neck while the muted string chugs on low, and the bass pumps its octaves (root and
  octave in turn; the octave under where the one over is past its top). A take that drives keeps the
  riff low with the muted string on every eighth under it and the bass's octaves, and no run. In a
  climbing take's chord's last bar the
  bass runs by step, two eighths a note, into the next bar's note: up from under it where the chords
  rise, down from over it where they step down (Warlord Fury's build goes Bb, Ab, Gb and lands on
  F), or where there is no room under it. The next chord brings the riff down again, so a long build
  climbs in terraces and the arrival lands on the low riff. *The boredom meter had found a fight's
  bass on one note and its rhythm guitar on one riff for 17 bars of a build.* The chords themselves
  are not touched: a family's takes are played channel by channel together.
- *Under the second theme the drummer opens out too* (`orchestra.OPENS_OUT`): a heavy band keeps time on
  the open hat for the second theme's first sixteen bars, as its guitars ring, then on the ride. *The
  meter had heard King's Oath's and Banner Oath's drums one colour for 34 to 68 bars across both
  themes: the turn from the hat to the ride sits too far under the kick and the snare to be heard.*
- *A long moment digs in at its half* (`orchestra.DIGS_IN`, `Take.digs_in`): in a heavy band's arrival
  or summit of 24 bars or more, from the first eight-bar line at or after its middle (bar 16 of 32),
  the crash comes every other bar over the ride's bell and the bass pumps its octaves, the way a band
  plays its chorus harder the second time round. *The meter had found the bass and the drums of a
  32-bar arrival or summit one colour all through.*
- *Its guitars ring as it digs in* (`orchestra.HEAVY_DIG_TURNS`, `Take.dig_way`, `Take.dig_turn`,
  2026-11-21): in a third of the heavy bands' takes, each drawn its own way as a rise's is, the rhythm
  guitars leave their chords ringing over the drums for the first half of the dig-in, a chord pushed an
  eighth early now and then, and the riff comes back for the second half to land the moment. *Lightning
  Runner II's rhythm guitar was one colour all 32 bars of its arrival, the drums and the bass digging
  in at its half and the guitars playing on as they were. The judges heard it level (TuneJury 0.389 to
  0.394, enjoyment 7.08 both), the meter's run 32 bars to 16.* The riff going up the neck an octave
  there (`DIG_UP`) was tried on 20 November and left off: a take drawn that way plays as written.
- *A light band's long arrival goes up a gear* (`orchestra.LIGHT_GEARS`, `Take.band_geared`,
  2026-11-19): every second eight-bar phrase of an arrival of sixteen bars or more the riff goes up the
  neck an octave, the muted string chugging where it was, and the other figure (a mandolin, a banjo) an
  octave up, as a band plays a chorus higher the second time round. *Sea Raiders V's mandolin, rhythm
  guitar and muted guitar played the same 160, 78 and 32 notes in every eight bars of its 40-bar
  arrival, the meter's colour unchanged all 40.* A geared phrase is voiced on its own, led from the last
  geared bar, and over a long stretch it walks back down toward the ungeared voicing, each voice going to the
  nearest note of the next chord anywhere within 14 semitones (Lazy River Sway I's banjo, from a chord spread over
  21 semitones). `orchestra.GEARED_SHAPE` (2026-11-20, off) makes a geared bar the shape the bar would have had, an
  octave up the neck; it waits to be heard on its own, before and after.
- *Tried and left off: a light band's summit coming back harder after its solo* (`orchestra.LIGHT_SUMMIT_TURNS`,
  `Take.after_solo`, 2026-11-20). From the solo's last bar the rhythm went up a gear, the drummer from the hats to the
  ride, and the bass one step more drive (`LAST_CHORUS`). *Anchor Dog V's mandolin, rhythm guitar, muted guitar, kit
  and bass had played the same 32 bars through its summit's fiddle solo and the twin theme after it.* The meter heard
  the turn (38 bars of one colour, 22 after), but the judges did not like it on the banjo band: Anchor Dog V's summit
  level, Lazy River Sway I's down (TuneJury -0.16 with the brief, -0.46 with none), and with its octave bass kept as
  octaves still down (-0.11, -0.31). The light band's summit after its solo is still owed a turn of its own.
- *Tried and left off: a light band plays stop-time after its solo* (`orchestra.STOP_TIME`, `STOP_BARS`, `Take.stop_time`,
  `Take.lay_out`, 2026-11-21): a blues or a country band's way back from a solo. For three bars the band strikes the chord together
  on the bar's first beat, short, and lays out: the rhythm, the bass on the root, the texture cut to the chord, the
  crash and the bass drum on the stroke, the hat on two and four keeping the time; the tune carries on alone. In the
  fourth bar the same stroke and the drummer's fill, and the band is back in on a crash. Only where the summit has
  STOP_BARS + 4 bars after the solo, so the band has four bars back before the close. *The study: a light band's
  rhythm one colour 20 to 31 bars through its summit after the solo (Whiskey Groove II and IV, Ridge Rover III,
  Sunny Wheels I), where the last chorus played harder had been judged level and down. The judges on
  Whiskey Groove's sixteen bars from four before the solo's end: TuneJury with the band brief 0.79 to
  0.38, with none 1.48 to -0.93, Audiobox's enjoyment 7.44 to 6.76, SongEval level: three bars of the
  tune alone over the band's stabs heard as a hole, not a breath; Midnight Vigil's level (0.37 to 0.31,
  enjoyment 7.39 to 7.49).* The light band's summit after its
  solo is still owed a turn of its own.
- *A heavy band's close ends as a rock band ends* (`orchestra.ROCK_ENDING`, `Take.ending`, 2026-11-19):
  through the close the riff drives on (its density 0.8, at least 0.6 of the way up), the bass in
  eighths and the groove every bar, with a fill into the stop; then the last four bars (two in a short
  close): the stop, one chord struck with the crash and the kick and left to ring; the chord struck
  again and held while the drummer rolls around the toms, high to low to the snare, growing; and the
  last chord with the crash and the kick, together, held. *The judges heard the close as the weakest
  of the nine parts in every band song (TuneJury 0.20 against 0.67 for the second theme, Audiobox's
  enjoyment 6.6 against 7.4): it had died away as an orchestra's does, its riff thinning to nothing.*
  The family's form and levels are not touched (its takes play channel by channel together); the
  tune and the pads still wind down over the band.
- *A heavy close breaks down before its ending* (`orchestra.HEAVY_CLOSE_BREAK`, `Take.break_span`,
  2026-11-22: five heavy songs in one night's studies drove the summit's riff on through the close,
  the rhythm one colour for 43 to 56 bars: Sand Fever I, Hammer Thunder I, II, IV and V). In a close
  of sixteen bars or more the four bars before its last eight are the bass's break, as after the
  valley (below): its riff alone over the drummer keeping time, the guitars and the lead resting;
  then the band crashes back in and drives into the stop, as a rock band lays out before its last
  chorus. The meter: the rhythm's one colour from 56 bars to 35 in Sand Fever I, 43 to 35 in Hammer
  Thunder IV. *The judges on each close's last sixteen bars, before and after: Sand Fever I's SongEval up 0.13 to 0.27 on all four of its scores and Audiobox's enjoyment 7.06 to 7.40, TuneJury level; Hammer Thunder IV's TuneJury with the band brief 0.61 to 0.85, its clarity up 0.13, the rest level; nothing down in either.*
- *The bass leads the band back in after the valley* (`orchestra.BASS_SOLO`, `Take.bass_break`,
  2026-11-19: "do bass solos too"). The first four bars of a heavy band's climb (eight in a climb of
  24 bars or more) are the bass's: its riff over each bar's root (one of `BASS_RIFFS`, drawn for the
  take: the blues climb, up the octave and down, the shuffle, the pedal), the second time with a leap
  to the octave, the octave pumped with passing notes in the third bar of four, and in the break's last
  bar a run up the blues scale into the band's entry. The guitars and the lead rest (`make_room`), the
  drummer keeps time lightly (hat, kick, backbeat) with a fill into the band.
- *A band's riff guitars are the band's whole accompaniment*: heavy band music has no second figure;
  lighter bands do.
- War drums play only in a band's rises (and in a fight, as it opens and in its valley).
- Knight Rock has no town or battleground music; its walking music plays there.

### 4.10 The guitar solo

*A band whose lead is the lead guitar takes a solo at the summit* ("i want fucking guitar solos in my
knight rock, study eddie vedder and pearl jam", 2026-11-18). Where the summit states its theme more
than once, the first time round is the lead guitar alone over the band (the riff, the bass and the
drums as written), and the theme comes back after it with the twin guitars.

*Most songs have one, each its own, and it moves* (2026-11-19, 13:15: "most songs should have
solos", "and they should be original each time", "i think you need the solos to do some flange shit
like move a little"; `orchestra.MOST_SOLOS`, `ORIGINAL_SOLOS`, `SOLO_FLANGER`). Whoever leads the
band's summit takes it (`orchestra.SOLOISTS`): the fiddle, the mandolin, the harmonica and the whistle
as well as the lead guitar, so the fiddle bands and the whistle's and harmonica's songs have solos of
their own; a whistle sounds one note at a time, so its solo has no double stops, octaves or doubled
notes. A summit of the theme and half of it again has room for one (the half after it), and where the
theme is eight bars and the summit states it three times or more, the solo takes two of them: sixteen
bars. Of the plan's band takes 142 in 144 have one (two Tavern Rock takes state the summit's theme
once). Each solo draws its own: three figures out of ten (one of them at least a riff of quick notes),
where they fall among its sentences (after the call and its answer; first of all; between the call and
its answer; or with the call carried higher between them), its own way through each figure, and its
call's rhythm; no two of the plan's 142 are the same. Under it a flanger sweeps in time, a little:
in from its first bar, a half again more at its peak, out as it ends; its own sweep (a bar, two or
four) and its own bite. It moves; it is never rocked by hand nor laid on every note.

*A solo is sung, not shredded.* The first one was runs and bends from end to end, every bend a grace
note a step below its note, under a wah rocked at the pace of the notes through the whole summit,
and every long note made to cry. Heard in the game: "all wammy no chill", "thats not a guitar solo
thats a solo effect track". A bend written as two sampled notes is a chirp, not a bend, and a pedal
that never stops is the thing you hear instead of the tune. `orchestra.guitar_solo` now writes it
the way Mike McCready plays a slow Pearl Jam song ("Yellow Ledbetter", after Hendrix's "Little
Wing") and the way a singer phrases:

- **Sentences of two bars**, each ending on a note held over its chord and a breath (a beat or
  more) before the next. Knight Rock has no singer, so the solo is the voice.
- **Its first words are the tune's own opening**, on the band's stop chord; then answered and
  turned upwards; then carried higher in eighths.
- **A held note doubled a third below** now and then, as McCready and Hendrix voice them.
- **Outside the solo the lead answers itself** (`orchestra.LEAD_ANSWERS`, `Take.answer`, 2026-11-19):
  where the tune holds a note two and a half beats or more and its next phrase begins within two and a
  half beats, the breath takes a run of four quick notes of the blues scale into the next phrase's
  first note, every other long note, so the tune still sings. Since 13:20 that day the run is the
  first theme's opening played quick (`orchestra.ANSWERS_SING_THE_THEME`, `Take._theme_head`): its
  shape on the blues scale's ladder, ending on the step beside the next phrase's first note, turned
  upside down where the phrase begins on the other side of the held note; a scale run only where it
  would leap more than a sixth or leave the range. The song's own idea answers it, not a stock run
  (the judges scored it the same or a little over the scale runs on King's Oath).
- **It builds**: one short figure (da-da-DUM) a note higher each time, then **one quick run** (six
  notes) to just under the top.
- **Its middle riffs, the way Angus Young plays** (`orchestra.ANGUS`, 2026-11-19: "couldnt you do more
  complex riffs in the solo part like angus"). In a sixteen-bar solo two of his figures are drawn for
  each solo, with a sung sentence between them, before the quick run: *the repeated note* (a high
  note of the chord picked against the note under it, fast, held, then again a note higher); *the run
  down in threes* (a note and the two under it, then the same from the next note down, a bar of it,
  onto a chord tone held); *the trill* (hammered on and pulled off between a note and the one over it,
  then a fall by step); *Chuck Berry's double stops* (two notes struck together on every beat and
  off-beat, a note higher every two, the top pair held with its third under it). Since 12:10 that day
  ("angus solo sounds pretty good iterate on those") a sixteen-bar solo's middle is three of his figures
  in a row, then the run, out of six: those four and *the cascade* (a run down from the top in
  triplets, a note of the chord and the two under it, then the same a note lower) and *the pedal
  lick* (a high note of the chord picked again and again with a line falling under it, Chuck Berry's
  and Angus's). An eight-bar solo trades its answer for one. Since 13:15 the ten figures are those six, each
  with its own way (the run in threes or fours, down or up; the trill a step or a third; the pedal over
  the line or under it; the cascade falling or climbing; the double stops climbing or falling; the
  repeated note against the note under it or over it), and four more: *octaves* (the tune's opening
  with the note an octave under each, as Wes Montgomery and Hendrix play a line), *the echo* (quick
  notes about a note of the chord, the same a step lower each beat), *the push* (one note picked in
  threes against the beat, 3+3+2 or 3+2+3) and *the slide* (two long notes, each slid onto from three
  quick notes under it, a fiddler's or a slide guitar's). The call, the peak and the way home stay sung, every sentence still ends
  on a held note and a breath, and the notes stay in the key's five: fast notes are now about half,
  where the sung solo of 18 November kept them under a fifth (two thirds since the three riffs) ("it shreds" was about the pedal and the
  chirping bends, not about speed).
- **The peak is the highest note of the chord under it, held two bars' worth of beats, and nothing
  before it goes as high**; then down by step, and the tune's opening once more, slower, to the
  key note held.
- **Notes on strong beats are notes of the chord**; everything is in the key's own five notes: the
  major pentatonic in a major key or mixolydian (sweet), the minor in a minor key or dorian (blue).
  It is not moved onto the blues scale as the lead's other lines are.
- **It sits high on the neck**: the octave is chosen so that the peak comes nearest the top of the
  guitar's reach, and the peak is the chord's note nearest that top, up to two steps over it where the
  guitar reaches (`orchestra.SOLO_PEAK_NEAR_TOP`, 2026-11-20). *It had been looked for only in the octave
  under the top: over Sand Fever's flat-two chord the one note of the five there was six steps down, so
  the peak was C5 and the whole solo sat G3 to C5 under it, a rhythm guitar's register. Now D4 to C6. 32
  of 165 band solos had peaked lower than they could.*
- **No pedal rocked on it.** It is a voice of its own (`lead guitar solo`, `fiddle solo`...) with a tape
  echo a dotted eighth behind it, so the held notes sing on into the room, and a flanger sweeping in
  time under it, a little, since 13:15; the summit has no wah on the lead at all.
- **It stands over the band**: 5 dB over the lead's usual level (`orchestra.SOLO_LIFT`, the part's
  `gain db`). Played at the lead's own level it was 2 dB under the rhythm guitars and 4 under the
  twin guitars' theme after it. The desk measures the lead's place over the summit after the solo
  (`build.perform`): measured over the solo, the lift had turned the whole lead channel down. And
  where the solo plays it is measured against the rhythm guitars and brought up until it stands
  1.5 dB over them (`build.solo_lift`, at most 8 dB, eased in and out over a beat), on the lead stem's
  own volume envelope in the mix: a light band's theme after the solo has a fiddle and the twin
  guitars on it, and the channel set by that had left Barnyard Jamboree's solo under the guitars.
  `tools/lift_solos.py` does the same to a staged take without making it again.
- **Under it the rhythm guitar comps** (`orchestra.SOLO_COMP`, 2026-11-19, 16:15): the chord struck on the
  bar's first beat and left to ring half the bar, the muted string chugging the eighths after it, no fills
  (they would talk over the solo), a little softer; the take's push stays. The riff comes back with the theme
  after the solo. *The boredom meter had the rhythm guitar one colour 34 to 50 bars from the summit through the
  close in three of the day's four new heavy takes: the riff played on under the solo as everywhere else.*
- **Never the same twice**: each take draws its own solo from the family's seed and the take: its
  figures, its form and each figure's way (above).
- **More Angus** (`orchestra.ANGUS_MORE`, 2026-11-19, 23:00: "gimme a better angus", "lets go"): the solo's figures
  are only his own (the repeated note, the trill, the pedal lick, the cascade, the run in threes, Chuck Berry's double
  stops; `ANGUS_FIGURES`), four of a sixteen-bar solo's eight sentences riff, and each riff is played again a note higher
  through the first half of its second bar, landing on a note of the chord held a beat with a beat's breath after it.
  The tune's call, the run, the peak and the way home are still sung. Lightning Runner's solo: 71 notes and 5 trills
  before, 116 and 24 after, 12 double stops where it had none.
- **A fiddle's, a mandolin's or a whistle's solo sings below its top** (`orchestra.SOLO_TOP`, 2026-11-19): a solo
  climbs an octave and a note over where the tune begins, and a fiddle's tune begins high; its reach had
  been the instrument's whole written range, and Lazy River Swing V's fiddle solo sat F5 to C7. Now the
  highest note is E6 on a fiddle and D6 on a mandolin (across nine oasis shuffle and sea dog takes the
  fiddles' peaks went from G6-B6 to G5-E6); the lead guitar's D6 and the harmonica's C6 are their
  written tops already. A whistle's is A6 (2026-11-21): *its solos sang to its very top, all in its
  shrill second octave (Silver Glade II A5 to D7, Dreaming Ballad II C#6 to C#7, Sunny Wheels I and III
  E5 to C#7)*, and a player keeps the top of a whistle for a note or two.
- **A harmonica's solo is a harp player's** (2026-11-21, evening: "You gotta work on your fucking harmonica.
  Look up John Popper"; `orchestra.SOLOISTS`, `HARP_FLURRIES`, `HARP_BENDS`). It had taken the guitar's figures,
  double stops and all (Campfire Ballad's solo two notes a third apart on every eighth). Now single notes, as
  Popper plays; its trill the warble between two holes a third apart; its quick figures flurries of
  thirty-seconds where the song is slow (at most 110 to the minute), the way his runs pour out; its notes of a
  second and a half or more on the hand vibrato's wail (`sounds.Sound.held`, the blues harp's "wail" player).
  And it is bent, as a blues harp is: half of its sung notes (an eighth or longer, not the flurries) on the
  key note, the third or the fifth are taken from under and let go up onto their pitch over 90 ms (a whole
  tone into the key note, the flat seventh's pull; a half tone into the major third and the fifth, the blue
  notes; a quarter tone into a minor third), and a third of the long notes that end a sentence fall a half
  tone over their last eighth (`orchestra.harp_bends`, written on the sheet as the solo's `bend` marks after
  the take is played in, so each lines up with its note as played; the desk plays them on the sampler's
  pitch wheel, `desk.PITCH`, two semitones each way, on every track of the harp). Campfire Ballad's solo
  bends 7 notes of 140, Lantern Walk's 8: a harp player's, not a whammy's. *The judges on both solos, bent
  against straight: level (TuneJury within 0.06, SongEval 0.00 to 0.07 up on both, enjoyment within 0.02).*
- `orchestra.SOLOS = False` takes it away and gives the summit back to the twins.

---

## 5. House

`house.py` writes the notes as calls to the studio's own synthesiser; `club.py` takes those calls
down and plays them on real instruments in REAPER (5.7).

### 5.1 Tempo, keys and chord loops

Every track is 110 BPM (`house.BPM`) in four. A family names a tonic (all twelve are used;
`tests/test_studio_house.py` asks for that and for 40 or more different pairs of tonic and loop) and
a loop from `house.LOOPS`: 26 loops of four chords, each chord one or two bars, in seven modes (M1–M6
major, L1–L3 lydian, X1–X3 mixolydian, D1–D4 dorian, N1–N6 minor, P1–P2 phrygian, P3–P4 phrygian
dominant). Chord colours (`COLOURS`): triad, 7, 9, sus2, sus4, 5 and 6. Every section starts at the
top of the loop (`house.Changes.chord`). Swing delays the off sixteenths by up to 0.16 of one. 49 of
the 89 families are light: *the house is meant to be mostly light* (the test).

### 5.2 The groove: kick, clap, hats

`house.Take.drums`:

- **Kick** on the family's pattern in sixteenths (`house.KICKS`): four (0, 4, 8, 12) in 36 families,
  broken (0, 6, 10), broken2 (0, 6, 8, 14), broken3 (0, 3, 8, 10), half (0, 10), none. It plays in
  the theme and the drops, and in the close until four bars from the end; in fights everywhere but
  the second half of each rise, on the `punch` sound. *Everything but the drums ducks under the kick,
  so the kick is part of the changes*: every take of a family keeps it. *The kick itself is House's
  own* (`studio/kicks.py`, `club.OWN_KICK`, 2026-11-21: "and design yourself"), struck on Geonkick in
  the machine's sample's place: a sine falling from 240 Hz to 52 Hz (105 Hz at 25 ms, 72 at 45, held
  low a moment), a triangle on the same fall for the punch a small loudspeaker plays, a burst of
  noise high-passed at 1.8 kHz for 10 ms for the click, and drive; down 12 dB by 142 ms, so the bass
  has the back of each beat. Measured against the TR-8's 909: within 3 dB in every octave to 2 kHz,
  turned up 5.1 dB (`club.KICK_TRIM`) to the 909's weight in the mix. *Each machine its own kick was tried
  and left off* (`club.MACHINE_KICKS`, `kicks.DESIGNS`, 2026-11-22): the 808's deeper body falling only from
  85 Hz, the 707's short knock with a band-passed burst round 2 kHz, the 606's long dark boom at 55 Hz, each
  drawn after the TR-8's within 3 to 4 dB in every band. *The judges on Drowned Halls I (808), Morning on the
  Hill I (707) and Mill Stream I (606): TuneJury with the House brief down 0.36 to 0.39 in four windows of six,
  Audiobox's enjoyment down in all six (to -0.66 with the 808's drop), SongEval up on the 808*: a progressive
  house drop wants the punchy kick, whatever machine the rest of the kit is.
- **Backbeat**: clap, clap and snare, or a second snare, on 2 and 4 (on 3 in half time), from bar 0,
  4 or 8 of the theme. Half-time grooves, inns and camps use a snap, a rim or a clap.
- **Hats** from the palette (`house.HATS`): off-beat opens, eighths, sixteenths, shuffle or sparse.
- **Percussion** (`house.PERCUSSION`): one figure from bar 0, 4 or 8, a second at the drops.
- **Fills** every eighth bar: a snare run, three toms, or a lift (the kick leaves the last beat).
- **The roll** over a rise's last four bars (two in short rises): *slow, then twice as fast, then
  twice as fast again, climbing*; in two takes of three its last beat is left empty, *the breath
  before the drop*. The calm roles stir a shaker, a rim or the hats instead.
- **Crashes** at the start of each theme and drop, and every eight bars of a drop.
- **A theme after a drop begins on the other figure**: its hats turned and the other percussion, so
  the groove changes where the drop ends (each section had counted its sixteen bars from its own
  start, and Ambush III's drums stayed the same 32 bars from its drop through the theme after it).
- **The close lets the band go one at a time, the hats first**: at its first bar they thin to two
  strokes and an open hat, the clap leaves halfway, the kick two bars from the end. (The drop's groove
  had run on into the close for 20 bars: Mirage I and III.)
- **A theme's percussion turns eight bars after its hats** (`house.THEME_STAGGERS`, 2026-11-20): the
  hats at a theme's seventeenth bar, the other figure at its twenty-fifth, so the drums change every
  eight bars (*a theme's drums had been the same sixteen bars from each turn, the hats and the
  percussion turning on one bar: The Deep Road III, Drowned Halls III, Thunderhead II*). Not in a calm
  piece. *The judges on The Deep Road III's theme: TuneJury 0.69 to 0.78, enjoyment 6.96 to 7.17,
  SongEval a shade down, within its noise.* Every such turn is in the top, a high percussion for
  another under the same kick and backbeat, and the meter read Breakwater I's theme the same 40 bars
  through them; but it was deaf to the hats' ring, which an ear is not (7.7), and with it the theme
  reads 16 at the most. A turn in the mids every second sixteen bars was tried on 21 November and left
  off, each behind its switch: House's backbeat is the groove's anchor. *A snare under the clap, or the
  clap and snare thinned to the clap (`house.THEME_MIDS`): TuneJury with the House brief 1.07 to 0.85,
  the judges hearing less house. A finger snap laid on the backbeat (`house.MIDS_WAY = "snap"`): level,
  1.02 to 1.08. A second clap laid on it (`"clap2"`): down, 1.02 to 0.86 with no brief, SongEval down on
  every axis.* A ghost kick on the bar's last sixteenth (`"ghost"`) is written and not yet heard.
- **A fight's drums grow** (`house.FIGHT_DRUMS_GROW`, 2026-11-20): its open is the kick, the backbeat
  and its roll, with no hats and no percussion; the hats come in with the theme, the first figure at
  its ninth bar (*a fight's open had played the theme's whole groove, the clap and the percussion in
  from the first bar: Ambush III's drums the same 20 bars from it, Capture the Flag III's 20*). *The
  judges liked the bare open better: Ambush III's open TuneJury 0.98 to 1.31, 0.94 to 1.43 with no
  brief, enjoyment 6.89 to 7.36; its theme 0.66 to 0.73.*

At the desk (`club.lines`) the kick is struck dry and everything else into a small room, whose
equaliser lifts the clap's, the snare's and the hats' presence at 2 kHz (*4 to 10 dB short from 900
Hz to 3.5 kHz against the liked stems*, 2026-11-17) and their knock at 900 Hz (*still 3 to 6 dB short
there in every take*, 2026-11-18: 3 dB more brought that octave about 2 dB nearer and left the rest,
the level and the punch as they were).

### 5.3 Bass, sub and growl

`house.Take.bass` plays a figure from `house.BASSES` (offbeat, offbeat with octaves, rolling,
driving, syncopated, tresillo, long, dub), between G1 and F#2 (`Take.bass_note`): *where the liked
house basses have their weight (40 to 80 Hz)*. The theme starts plain: the busier figures begin as
off-beat roots for four bars, and no figure has octaves or fifths for eight. The breakdown, and the
close once the kick has gone, hold one long note to a bar, *8 to 10 dB under the groove*. In two
takes of three, eighths on one note open up through the end of a rise. The desk adds the sub and the
growl (5.7). *A long theme's bass lifting at its half was tried and left off* (`house.THEME_BASS_TURNS`,
`house.lifted`, 2026-11-21: in a theme of 32 bars or more, the roots on its off-beats of two and four up an octave
from its half, as a house bassline climbs toward the drop): *the judges level on Moonwell I and Hollow Road III
(TuneJury +0.11 and +0.01 on their themes, SongEval within 0.04; their drops, where nothing changed, moved as
much), and the meter read both basses' colour 4 to 6 bars either way.*

*A sub with nothing over it is heard* (`club.SUB_ALONE_GROWL`, 2026-11-22). The sub is a sine, felt and not heard; its
growl, a saw on the same notes closed above 900 Hz at 0.45 of the bass, is the part that is heard. Where the sub played a
camp's or an inn's bass alone it stood 5.9 to 7.5 dB thin in its middle against the liked stems (six calm takes of six),
and under only its harsh twin in walking music 3.4 on average (fourteen takes), where every other bass was level or
heavier. Where the sub is the bass with nothing over it but its twin (`club.TWINS`), its growl is 0.8 of the bass: in
three camps the bass 4.1 to 4.4 dB fuller from 226 Hz to 1.8 kHz, its lowest octaves unmoved; *the judges level in all
six windows, SongEval a shade up in four*: in for its musical reason.

*The own FM bass's middle eased* (`club.FM_MIDDLE`, 2026-11-22). The FM bass designed for House has a middle of its own,
its sidebands: 3 to 8 dB heavy against the liked stems at 450 to 900 Hz in every take that drew it that day, sixteen.
At the desk it is cut 4 dB an octave wide at 600 Hz, in the bass's own equaliser: the middle 1.5 to 2.4 dB lighter, *TuneJury
with the House brief up in all six windows of three songs, the rest level*. It is still 4.6 to 7.9 over there, its weight
spread from 226 Hz to 3.5 kHz: a broader easing, or a lighter modulation in the patch, is owed.

**The bass grows harsher through a long drop** (`club.harsher`, on the sheet as the part `bass
harsh`). Halfway through every drop of 32 bars or more, a second bass plays the bass's own notes and
leaves with the drop. It is the detuned saws of the wide bass, or a sawtooth where the bass is already
the wide one. It comes in over eight bars in the desk's four-bar volume steps (under half way, most of
the way, in), up to about half the bass's level. This is the move of deadmau5's "Turning Point", where
a harsher bass fades in under the same notes and the timbre seems to change, and of "Phantoms Can't
Hang", whose bass turns harsher before a core's midpoint. The boredom meter had heard Moonwell's bass
keep one colour through 44 bars of its last drop. Calm pieces keep one bass. *With House's own
instruments the twin is a sound of its own* (`"house bass harsh"`, `club.HARSH_OWN`, 2026-11-21):
three detuned saws and a square driven hard, opened to 2.4 kHz and high-passed at 180 Hz, so it adds
the grit and leaves the low end to the bass and the sub; it comes in at 0.85 of the bass's strength.
*The wide bass it had been added 0.0 to 0.4 dB to the bass in five long drops of six, never heard,
and at 0.95 of the bass's strength only 0.6; the high-passed twin at 0.55 lifted the bass's 300 Hz to
3 kHz by about 1 dB, and is brought nearer.*

### 5.4 Plucks, stabs and arps; leads; pads

**Chords** (`Take.rhythm`) are voiced from G3 to E5 (`Changes.voicing`), moving as little as they
can, with an octave added at the drops. Ways of playing: stabs (one of the six rhythms of
`house.STABS`), strum (14 ms between strings), pumped chords on 1 and 3, a dub chord thrown into
the echo, or an arp of sixteenths or broken chord of eighths (up, down, up and down, pedal, skip).
Brightness climbs through each section: open 0.12 to 0.62, theme 0.55 to 0.75, rise 0.4 to 1.0,
drops 1.0, close 0.85 to 0.25. In two takes of three the figure plays through the rise; otherwise
only at its end, where it becomes repeated chords.

**The tune** (`house.Tune`) is sixteen bars from a two-bar idea: stated, answered by itself fitted
to the next chord, left for a phrase of another rhythm that climbs, and brought to rest; the second
eight bars say it again with turns and the climb a third higher. Strong and long notes sit on the
chord, the rest move by step, a leap turns back. It is centred on G4: *a house hook sits in the warm
middle, not over the band*. Nothing goes above A6.

**A riff is a cell** (`house.RIFF_CELLS`, `Tune._riff_cell`, 2026-11-19, 14:15: "your house suck", "study house on
the loop with the same scrutiny"). Two takes in three have a riff for a hook. It had followed the same slow curve
with a note coming again for nothing, and settled on the chord's third and fifth: F F F F A A A A A (The Forge at
Rest I), G G G D D D D (Canopy I); in the staged takes half the riff's notes were the note before, on three or four
pitches, and SongEval heard House's memorability at 2.4 to 2.8 against Knight Rock's 2.9 to 3.0. Now a riff is a cell
of three or four notes of the chord in an order drawn for the tune (no note twice running, three of them at least,
within about an octave): F5 F4 D4, an octave down and a step (The Forge); G5 B4 G5 D4, a pedal over two that move
(Canopy); D4 A4 C5, up through a minor seventh. It is said over the riff's rhythm again and again, and over each chord
the same cell is on that chord's own notes, so the hook keeps its shape as the chords change, the way an arpeggiated
house hook does. The cell's first note is leaned on.

| Section | The tune |
|---|---|
| open | the idea's last notes, far off, in the soft voice |
| theme | the tune's opening phrases every four bars from the fifth, softly (`house.THEME_SINGS`, 2026-11-19: eight bars of tune in thirty-two had left the theme a groove waiting for one; not a fight's or a calm piece's), then the hook every four bars from halfway, in the soft voice (a fight's in the main one from the first bar) |
| rise | the whole tune, soft then main, growing; its last bar left empty before the drop |
| moment | the whole tune in the main voice at full brightness; every second time a line an octave or a third above (not in calm music) |
| close | the idea every four bars, fading |

The soft voice is the palette's next lead after the chosen one. **Pads** (`Take.texture`) hold each
loop slot's chord, voiced from C3 to A4, brightest at the drops (0.92).

**The lead is ridden at the desk, not turned down** (`club.ridden`): it stands at its place at the
drop, and a part of the story that would stand more than 3 dB over that is brought down to it on the
lead's own volume envelope, as a mixer rides a fader. (Set as the other channels are, by the drop but
never letting another part over, a lead loud in its rises was turned down whole: Blades III's riff 15
dB under its rises.) The chords and stabs are ridden the same way (`club.RIDDEN`).

**The bigger of a lead's two voices plays the drops** (`house.LEAD_WEIGHT`): the saws and the brass
carry a drop; a plucked or struck voice sits between; a hollow square, a pipe or a whistle is the
gentle one for the quiet places. (A take that drew the hollow square had played the seven-saw super
in its themes and the square at its drops: Hammerfall III, the lead 12 dB louder outside the drop.)

### 5.5 Waves, drops and breakdowns; risers and air

The waves and the breakdown are in 2.3. The air (`Take.airs`):

| Sound | Where |
|---|---|
| sweep up (noise, 250 Hz to 9 kHz) | the last eight bars of each rise (four in short ones) |
| climb (a sawtooth from the key note, two octaves up) | with it, in two takes of three |
| thud | each drop's first beat |
| sweep down (9 kHz to 400 Hz) | the drop's first two bars |
| small sweeps | at the turn into each theme and the close (not in fights) |
| weather (`atmos`: wind, sea, rain, fire, drips, crickets) | the opening, the close and long rises; all the way in a storm |

In the calm roles the risers, thud and falling sweep are at 0.4: *an inn does not have a drop*.

**The rise, as the judges hear it** (2026-11-19). In all thirteen House takes judged the rises scored
TuneJury 0.22 on the House brief and −0.30 on none, against 1.1 to 1.3 for the grooves either side: twelve
bars of the tune over nothing, then a four-bar roll under an eight-bar sweep. A pulse was tried
(`house.RISE_PULSE`): the hats going on through the rise with the first percussion figure until the build,
and the roll, the bass's eighths and the late chords coming in with the sweep (`RISE_LONG_BUILD`,
`Take.build_bars`). Heard on The Long Watch II and Harbour Lights II, eight rises: the House brief edged up
in every one (+0.04 to +0.09) and SongEval rose on one take (musicality 2.64 to 2.88, all four scores up
0.15 to 0.24), but Audiobox's enjoyment fell in all eight (−0.28 on average) and the score with no brief
fell on one take (−0.23 to −0.39) and rose on the other (−0.16 to +0.10). With the four-bar build of before
it was worse, so the hats were what the judges liked less, the open hats and the ride of The Long Watch the
most. It is left off. The quieter pulse, the closed hat alone on the eighths with no percussion and the
eight-bar build (`house.RISE_CLOSED_HAT`, 2026-11-20), the judges liked: the House brief up in all four
rises of The Long Watch II and Harbour Lights II (+0.07 to +0.17), the score with none up on Harbour Lights
and level on The Long Watch, Audiobox's enjoyment within its noise. It is in.

The rises were still House's lowest part (TuneJury -0.25 with no brief over sixteen takes, its themes 0.76 and
its drops 1.13): a rise had no kick from its first bar, where a house record keeps the four on the floor through
its build-up and takes it away only for the last bars before the drop. A rise now keeps the kick until its build
(`house.RISE_KICK`, 2026-11-20), everything but the drums ducking under it as in a groove, and the build goes
without it, so the drop's kick lands after its absence. On Harbour Lights II both rises rose, TuneJury with the
House brief 0.23 to 0.50 and 0.22 to 0.50, with none 0.05 to 0.67 and 0.06 to 0.58, Audiobox's enjoyment level
(7.28 to 7.31, 7.35 to 7.38); on The Long Watch II further, 0.33 to 0.97 and 0.30 to 0.77 with the brief, -0.33 to
0.91 and -0.25 to 0.75 with none, enjoyment level (7.29 to 7.33, 7.28 to 7.25). A calm rise keeps neither the kick nor, now, the closed hat: House's calm takes
made again with the hat had their rises up to their moments (Embers under Stars I level with it, Cool of the
Evening II a dB over it, the render's own check), so an inn's rise is the tune over a shaker stirring, as it was.
Its bass building at half the level (`house.CALM_BUILD_SOFT`, 2026-11-20: Cool of the Evening II's rise still over
its moment without the hat, its bass -15.3 dB there against -20.3 at the moment) passed the render's check but the
judges heard less lift (TuneJury 0.93 to 0.79, 1.20 to 0.89 with no brief): it is left off; that bass was an organ,
which House no longer has.

*A long drop drops out for a bar before its last eight* (`house.DROP_OUT`, 2026-11-20): in a drop of thirty-two
bars or more the kick, the bass, the chords, the tune and the percussion stop for a bar; the clap and the hats go
on with a snare pickup under a bar of rising air, and everything lands again on a full crash and the drop's thud,
the pads swelling in the gap with no kick to duck under. A long drop's last sixteen bars had been one groove to
the meter (Mirage I, Hollow Road III, River Drums III, The Old Swamp III), and its third block louder
(`house.DROP_PEAK`, left off) moved its drums 0.3 dB. *The judges up on both songs heard: The Old Swamp III's last
sixteen bars TuneJury 0.80 to 0.93, 0.94 to 1.10 with no brief, enjoyment 6.84 to 7.11; Mirage I's 0.56 to 0.65,
musicality and memorability up; the meter's run at Mirage I's drop end gone.* Not in a calm piece, which has no drop.

*A long drop opens up at its second block* (`house.LONG_DROP_GROWS`, 2026-11-21): in a drop of thirty-two bars or
more a ride comes in on the beat at the seventeenth bar, a wash over the top you can hear, as a long house drop
brings in a layer after its first sixteen bars; not where the palette's percussion is a ride already, nor in a calm
piece. The drop-out breaks a long drop's end only: Mill Stream II's last drop read the same 39 bars from its first
to the meter, The Old Swamp III's 23, the turn of the hats and the figures at its second block under the kick and
the clap. (Its percussion turning eight bars after its hats, as a theme's does, was written and taken back before
it was heard: in a drop it would have moved the figures' one audible turn later.) *The meter: Mill Stream II's 39
bars broken by the ride. The judges on its bars 8 to 24: TuneJury 0.64 to 0.71 with the House brief, 0.69 to 0.66
with none, enjoyment 7.20 to 7.24, SongEval up a shade on every axis.* Still owed: every one of these changes is in
the top, and a drop's colour stays one to the meter (a change in the mids every sixteen bars, after Thunderhead
III's finding).

### 5.6 Palettes and the calm roles

A palette (`house.PALETTES`) lists the sounds and ways a take may draw on for each channel; the
three takes of a family take different ones (`Take.pick`). There are 27: a light and a dark one for
each of the eleven kinds of place, and ember, night, depths, storm and battle.

*Every kind of place has music for every moment* (2026-11-22, twenty families more: 89). Each of the
eleven kinds of place has five to eight families for walking about (a new one each: Hay Bale Sunset,
Cairn Wind, Gaslight, Salt Caravan, Monsoon Drums, Cinder Bloom, Gilded Halls, Moth Wings, Willow
Lanterns, Tidepools, Hoarfrost) and at least one for the town, the inn, the camp, the night, the cave,
the storm, the fight and the boss; the marsh, the coast and the snowfields, which had borrowed those
from the kinds nearest them, have their own (Fishmarket, Driftwood Hearth, Tide Camp, Moonlit Ebb,
Sunken Grotto, Squall, Breakers, The Leviathan), and the battleground a third (Siege Bells). Each new
family has a key and chord loop (tonic and loop) no other family has.

| Palette | Bass | Chords | Lead | Pad | Weather |
|---|---|---|---|---|---|
| pastoral | pluck, square, sub, FM | string, keys, pluck, harp, piano | whistle, keys, string, flute | warm, strings, hollow, glass | none |
| highland | sub, square, pluck | harp, pluck, piano, string | pipe, whistle, flute, hollow | warm, hollow, strings, glass | wind |
| haunted-light | sub, FM, square | bell, keys, marimba, glass | glass, whistle, keys, bell | glass, strings, warm, hollow | wind |
| desert | pluck, FM, square | oud, string, marimba, pluck | oud, flute, hollow, pipe | warm, hollow, glass | wind |
| jungle | pluck, square, FM | marimba, pluck, string, piano | flute, marimba, whistle, pluck | warm, glass, strings | none |
| infernal-light | saw, square, pluck | brass, stab, piano, pluck | saw, brass, hollow, super | super, hollow, strings | fire |
| regal | saw, FM, pluck | brass, piano, stab, harp | super, brass, saw, keys | strings, super, warm | none |
| mystic | sub, FM, pluck | harp, glass, bell, keys | glass, whistle, harp, bell | glass, strings, warm, hollow | sea |
| the dark ones | mostly reese and saw | stab, pluck, brass and the kind's own | saw, hollow, super and the kind's own | hollow, super | as their kind |
| ember | sub, square, FM | keys, string, harp, glass | whistle, keys, glass, flute | warm, strings, glass | fire |
| night | sub, FM, pluck | bell, glass, keys, harp | glass, flute, whistle, keys | glass, warm, hollow | crickets |
| depths | sub, reese, FM | stab, pluck, bell, glass | hollow, glass, bell, saw | hollow, warm, glass | drips |
| storm, battle | reese, saw, square or pluck | stab, pluck, brass | saw, hollow, super | super, hollow, strings | rain in a storm |

*House has no organ* (2026-11-20, playing House: "No organs in the house music"): not as its bass, its
chords or its pad. Each palette's organ became a sound of its own world in the same place among its
choices, so that only the takes that had drawn it changed (39 of 163): a square or FM bass; a piano,
an electric piano, a stab, a pluck or a harp for the chords; strings, a warm, hollow or glass pad. The
desk's organ patches are left to the other styles.

**The calm roles** (`house.CALM_ROLES`: ember, night, camp) *have no drop to speak of, no roll into
one and no line doubled over the tune, and they play under the usual level*. Ember and camp take the
ember arc and half time or no kick; the night takes the walking arc. At the desk their drums, bass
and lead sit at −18 LUFS and their pad at −20 (`club.CALM`), and the bucket takes them 4 (ember), 3
(camp) or 2 dB (night) further down (`level_db`).

### 5.7 How club.py plays the notes

*That synthesiser is what was turned down by ear ("figure out how to make house music not suck",
2026-11-16); the notes are not.* `club.listen` stands in for the synthesiser's `play`, `hit` and
`drum` while a `house.Take` writes, and takes down every note (time, length, pitch, level, pan,
brightness) and every stroke. The writer's echo, chorus and hall do nothing then: *the echo, the
chorus and the hall are the desk's now*.

- **Sounds** (`club.PLAYED`). Synth names go to Surge XT factory patches (`sounds.HOUSE`), each at
  the octave it was measured to need (`sounds.HOUSE_OCTAVE`). On 2026-11-17 the House sounds were
  heard as cheesy ("your house sounds cheesy bro"; asked which: the synth sounds, and the tunes'
  instruments), and 38 patches were auditioned alone through House's desk, measured against the
  liked stems and for tuning. Now: leads Oberheim Dreams, Prophet VS, Moogy Saw and Crisp PWM;
  plucks Saw Pluck, Fat Curtis and Delay Dancer; pads Legacy, Verb Pad, Winter Warmer and Sparkly;
  stabs Smooth Stabs. The tunes the pan flute, the flute and the marimba sang are sung by synths.
  Real instruments still go to Muse Sounds for chords and colour: the piano, the Suitcase Piano for
  `keys` chords and the Wurly 200A for a `keys` lead, marimba chords, harp, nylon guitar for the oud
  and for plucked-string chords, trumpet, brass, and slow strings for the strings pad. Surge is not
  sent controller 1: each patch puts it on something of its own, and one new lead went 49 cents out
  of tune in the drops on it.
- **House's own instruments** (`studio/patches.py`, `sounds.OWN_HOUSE`, 2026-11-21: "why does my
  house sound like generic shit", "i think mainly your instruments suck for house", "and design
  yourself"). Every guide to the genre names stock presets used as they come first among what makes
  a track generic, and House had leaned on five: the saw bass, the pluck, the super pad, the saw lead
  and the chord stab. Each is now designed in code on Surge's empty saw, its effects the desk's:
  - *the rolling bass*: a saw and a square a few cents apart through a 24 dB ladder low-pass that
    opens on each note and closes within a sixteenth or two (the sub under it on its own track);
  - *the pluck*: three detuned saws and one an octave up through a driven 24 dB low-pass shut low
    and thrown open by an envelope gone in a quarter of a second, harder notes brighter: the sound
    the dotted-eighth echo is written for;
  - *the pad*: a seven-voice supersaw over a five-voice one an octave down and a triangle an octave
    up, through a 12 dB low-pass that a scene LFO opens and closes by an octave each way in about
    twelve seconds, slow in and slow out;
  - *the lead*: a nine-voice supersaw over a square an octave down, a glide of 40 ms and a vibrato
    that waits a third of a second;
  - *the chord stab*: three saws and a square through the ladder, struck and gone in under half a
    second.
  The second five, by how much House plays them: *the drop's big lead* (sixteen saws spread wide,
  seven an octave up, a square an octave down); *the glass pluck* (a narrow pulse and a triangle an
  octave up, thrown open and shut in a sixth of a second); *the warm pad* (saws over a triangle under
  a kilohertz, opening half an octave each way in seventeen seconds); *the hollow pad* (squares whose
  width a slow triangle moves); *the glass pad* (triangles and narrow pulses an octave up, high-passed,
  its filter turning slowly); and the harsh twin (5.3).
  The desk no longer cuts their tops (its 2.5 kHz shelves and 4-6 kHz closings were made to match
  the liked stems, which were separated from whole mixes and are dull up there): each keeps its top
  and loses only the lows its part does not need; a lead gets 2 dB of presence at 1.2 kHz and its top
  eased 4 dB from 6 kHz. *Opened to 2.5 and 3.2 kHz, the leads came out 5.5 dB quieter in the mix and
  7 to 10 dB short at 1.25 to 2.5 kHz, the loudness's weighting taking a very bright sound down whole:
  they are shut lower now and opened by the envelope at each note.* The drop's big lead is lifted
  4 dB at the desk (`club.OWN_LIFT`): *the factory one it replaced had measured quiet on the level's
  three short notes and been turned up 5.5 dB, so the drops had been heard with their hook that much
  over the studio's level, and the own lead, measured true, sat 5 dB under it where Audiobox's
  enjoyment fell (Mirage I, Hollow Road III).* They are in tune within a few
  cents (measured by each note's detuned cluster, not its loudest voice). *The judges on five takes'
  last drops against the factory patches: TuneJury with the House brief up in four (Mirage I 0.62 to
  1.18, Hollow Road III 0.72 to 1.09) and level in one, SongEval up or level.*
  *Until that afternoon the designs were not quite what is written here.* Surge's classic oscillator
  makes a square at its Shape −1 (Surge's own "Init Square") and a double saw at +1, an octave over
  its note at the default widths, and the designs had read −1 as a triangle and +1 as a square:
  *played alone and their harmonics read, the "squares" had only the even harmonics (the leads' body
  under them a saw at the note, the hollow pad saws) and the "triangles" only the odd ones, squares
  (the glass pad buzzing where it should shimmer); the first takes on them stood 17 to 32 dB over the
  liked stems at the top in their chords and pads.* Each is drawn as written now (`patches.SAW`,
  `PULSE`; a triangle is the modern oscillator's, `triangle`), and an oscillator of another kind takes
  its settings' kinds from a patch that has it (`patches.KINDS`). *With the patches as designed
  alone, Glade at Dusk III's drop: TuneJury 1.16 to 1.39.*
  The third set, that evening, the rest of what House played as the factory made it, the sub aside
  (a sine, whose whole job is to be one): *the FM bass*, one sine modulated by two at its note and an
  octave over it, the filter envelope throwing both up at each note and letting them settle, bright
  and woody and then round (*the factory's had sounded an octave under its written note, 17 to 30 dB
  short of the liked stems from 450 Hz up; the own one is 10 to 12 dB fuller from 320 Hz to 1.25 kHz:
  Moonwell I's drop TuneJury 1.13 to 1.48, SongEval up 0.2 to 0.34*); *the reese*, two pairs of saws
  24 and 14 cents apart through a driven low-pass that a slow LFO turns; *the square bass*, two
  squares through a low-pass each note opens two octaves; *the whistle's lead* (for the whistle and
  the flute), a sine with a breath of noise and a quiet triangle an octave up, a slide and a late
  vibrato; and *the bell*, a sine modulated at three and a half times its note, clanging and then
  singing. *Against the factory patches, with everything of House's own: TuneJury with the House brief
  up in every window of four songs (Larks over the Ridge II's drop 1.12 to 1.50, Night Prowl III's 1.06
  to 1.45, Snowmelt II's theme 1.48 to 1.87, Hollow Road III's drop with the bell 0.63 to 1.24),
  Audiobox's production up in all and its enjoyment in five of eight (6.81 to 7.24, 6.91 to 7.32);
  SongEval down 0.1 to 0.5 in most. The whistle's lead is nearly a sine, 25 to 55 dB under the factory
  lead from 2.5 kHz up: a breath more is owed.* *The whistle with its edge* (`patches` "house lead whistle",
  `sounds.WHISTLE_EDGE`, 2026-11-22: a fifth of House's songs lead with it): the sine leaned toward a saw, the
  octave's triangle nearly twice as loud, more breath, a soft saturation for the odd harmonics a real whistle's edge
  tone has, the filter opened to 6 kHz; a template of its own. Measured alone, 31 dB more in its top and the same
  middle; in Morning on the Hill III the lead within 5 dB of the liked stems in every octave from 450 Hz up (it had
  been 15 to 30 under from 3.5 kHz). *The judges on Morning on the Hill III and Larks over the Ridge II, both ways: SongEval up in all four windows on every score (0.05 to 0.31), TuneJury with the House brief mixed (+0.18 and +0.07, -0.06 and -0.31), with none level, Audiobox's enjoyment level.* The plucked bass and the hollow lead were designed too
  and stay the factory's (their designs kept in `patches.DESIGNS`): *the judges heard Reedlight I's
  theme down on every judge with the hollow lead (TuneJury 1.64 to 1.40, enjoyment 7.69 to 7.35), and
  its drop level to down with the plucked bass.*
- **Effects.** Tape on the chords, the lead and the drum room; a light chorus on synth leads; slow
  phasers on the chords (about eight bars a turn) and the pads (slower); a longer echo from side to
  side on the lead and the chords; more of the (darker) hall on everything but the bass. *A longer,
  cleaner hall was tried and left off* (`club.ROOM`, 2026-11-21): 2.8 seconds, nothing in it under
  300 Hz or over 8 kHz, its lows ringing 0.8 of the rest, against the hall as it was set the first night
  (1.5 seconds, 80 Hz to 6 kHz, its lows 1.2). *On Glade at Dusk III, Night Prowl III and Hollow Road
  III, six windows: TuneJury with the House brief down in four (-0.11 to -0.26) and level in two, with
  none down in five (-0.10 to -0.17); SongEval and Audiobox within their noise.*
- **Brightness as a moving filter** (`club.cutoff`, since 2026-11-18). Each part's brightness is its
  low-pass, an effect mark on its sheet that moves with the music (see 0.3). Until then a voice was
  split over up to four tracks closed at fixed points (900 Hz, 2.2 kHz, 5 kHz or open), so its tone
  moved in steps and a drop was the colour of its theme.
- **Four-bar rides** (`club._spans`, `club._ride`). *Surge XT's patches play a note alike however hard
  it is struck*, so a synth voice's level rides its track's volume four bars at a time (`SPAN`), read
  from the loudest note there, its loudest four bars at full. *Not their mean: the drop's second time
  round has a quieter line over the tune, and with it a mean took the whole drop 5 dB down.* Muse
  voices keep velocities instead: 0.9 × √(level ÷ loudest).
- **The under line.** In a synth voice, notes written under 0.6 of their four bars' loudest (`UNDER`)
  go to a track of their own, as far under as they were written.
- **Sub and growl.** Under the plucked and sawtooth basses (`SUBBED`) a sine sub plays their own notes
  at 0.8 (0.7 until the third pass: the liked basses had 3 to 7 dB more at 28 to 57 Hz): *an octave
  under, tried the same morning, put the sub at 25 to 45 Hz*. Beside the sub and
  the FM bass a sawtooth growl closed at 900 Hz plays at 0.45: *the part of the bass that is heard;
  the sub is the part that is felt*. Not beside House's own FM bass (`club.FM_GROWL`, 2026-11-22), which has a
  middle of its own: taken away in three songs, the bass moved 1 dB or less in every octave and the judges stayed
  level; *Sunlit Fields II's bass, 7 dB over the liked stems at 450 to 900 Hz, is the FM bass's own middle.*
- **The kit** (`club.kit_file`). The TR-8 recordings the writer used become an SFZ instrument for
  sfizz, one key per drum. The kick has its own dry track (its stroke brought out, under 30 Hz cut,
  parallel compression, no hall). The hats, shakers, tambourine and ride have a line of their own
  (`club.HATS_SOUNDS`, since 2026-11-18, "too much high hat"): high-passed at 500 Hz, the top eased
  3 dB above 11 kHz, dry, no tape, at 0.42. Everything else is a `room` track, 3 dB more present at
  900 Hz and 2 kHz, with 0.22 of it sent to the hall.
- **Ducking** (`club.DUCK`, `club.RECOVER`, `club.PUMP`). Under every kick each channel dips and comes
  back over its own time, slowly at first so that it swells into the off-beat. At a drop: the bass to
  0.2 (14 dB down), back in a third of a beat (*about 150 ms at 110 BPM, where the records studied put
  it*); the pad to 0.35 over 0.85 of a beat, *the pump that is heard*; the chords to 0.45 over 0.7; the
  lead to 0.85 over 0.5. The depth follows the story (`PUMP`): all of it at a drop, 0.7 of it in a theme
  and the close, 0.5 in a rise, 0.4 in the open; none in the breakdown, which has no kick. (Until
  2026-11-18 the bass went only to 0.5 and the chords to 0.72 everywhere: "not enough dynamic sound".)
- **Tone.** Bass closed above 1.8 kHz with its top shelved down from 800 Hz, narrowed, dry. Chords
  cut under 110 Hz and shelved down 10 dB from 2.5 kHz (16 dB and closed from 6 kHz until the moving
  low-pass took over, 2026-11-18), with an echo of three and four sixteenths. Lead cut under 120 Hz with the same echo, Surge's taken down at 2.5 kHz and
  shelved 8 dB from 3.5 kHz, MuseScore's lifted at 1.2 kHz. Pads cut under 200 Hz, shelved 12 dB
  down and closed at 3.5 kHz (Surge) or 4.5 kHz (Muse), with a chorus; the air closed at 5 kHz.
  House's hall is darker than the orchestra's (nothing above 6 kHz). Each setting is dated in the
  code with what the ear measured: three passes so far, each bringing the tops nearer the liked
  stems (the third, 4 to 9 dB nearer in the pads).
- **The air** (`club.air_lines`) is played by the studio's own JSFX instrument (`studio/jsfx/air`):
  each sound a note, its sweep on controller 1 and its swell on controller 11.
- **Levels.** Each voice is set against the others of its channel by where each is loudest (its
  `taste`, at least 0.35). Muse voices are measured to −30 LUFS where they play firmest, as the
  studio's own players are. Each channel goes to its place at the last drop (`club.PLACE`: drums −12.5, bass −15 since "light and wimpy" and "a little harder", rhythm
  −20, lead −19, texture −22 LUFS; drums −27 with no kick), never so far up that another section is
  more than 3 dB over it. The last drop goes to −13 LUFS with its peaks held under 0.89
  (`house.master_gains`), and the last 2 s fade out.

---

## 6. The sound

### 6.1 From a written name to a sound

`sounds.lines(voice, ...)` turns one written voice into REAPER tracks.

1. **MuseScore**, if the name is in `muse.PARTS` and `muse.available()`. `muse.shared` shares the
   notes among parts by register (`strings`: basses to B2, celli to B3, violas to B4, first violins
   above; `brass`: trombone, horn, trumpet; `choir`: men below middle C, women from it). `muse.score`
   writes MusicXML and `muse.perform` has MuseScore play it with no window (`--sound-profile
   MuseSounds`). A named Muse Sound is written into the score's `audiosettings.json` (`muse._given`).
   Performances are kept by a hash of what was in them (`var/reaper/muse`), so an unchanged part is
   never performed twice. A recording with nothing above 16 kHz is MuseScore's plain built-in set,
   and stops the render (`muse._plain`).
2. **Drums.** A kit's strokes go to a drum plug-in where it has them (`sounds.KIT_PLUGS`: rock to
   AVL Red Zeppelin, room to Black Pearl, hands and folk to Buskman's Holiday), the rest to an SFZ
   kit of recorded strokes; in the kits of `sounds.KICKED` every bass-drum stroke also plays the kick.
3. **The studio's own players** (`sounds.SOUNDS`): recordings in sfizz (`sfz` module), Surge XT and
   ZynAddSubFX patches, the AVL and Geonkick plug-ins. A name can have several: long and short notes
   split at 0.26 s (0.2 s for winds), registers split among sections, soft and loud recordings.

With MuseScore there, it plays every pitched instrument but the pipe organ, the harmonica, the
accordion, the bagpipe's tunes (FreePats' chanter) and the banjo (a strumstick). The studio's own players have those,
all the drums (war drums, frame drums, taiko, great drum, melodic tom, the deep stroke, gong, anvil,
cymbal swells and the kits) and the desk's layers: the Zyn pad, the Surge sub, and the kick, Naked
Drums' bass drum through three microphones with a Geonkick sub under it, *short on purpose: a kick is
a stroke, and the bass owns what rings*.

### 6.2 How levels are measured

- **Each instrument alone** (`sounds.levels`): every player plays a few firm notes alone in REAPER,
  twice. `before` is the dB that brings its bare sound to −30 LUFS (`sounds.LEVEL`); `after`, with
  its effects on, is its fader. Both are kept in `var/reaper/templates/levels.json`.
  `tools/render_some.py` refuses to start while any instrument is unmeasured.
- **MuseScore**: in Warcraft and Knight Rock its recordings are laid in 6 dB up (`MUSE_LEVEL`), with
  a trim for the two heavy guitars (`MUSE_TRIM`), keeping Muse's balance among its own sounds. In
  House each is measured to −30 LUFS where it is played firmest (`sounds.firm_loudness`: the notes
  struck at 0.8 of its hardest or more), because *a channel that had one of each had no level between
  them*. This is one place where the desks differ, against "uniform processes eventually".
- **Each channel** goes to its place by its loudness at the summit (`build.PLACE`: lead −17, texture
  −21, rhythm −21.5, bass −18, drums −20 LUFS, or −15.5 with war drums, −18 with soft ones; a light piece's drums
  −20.5 and bass −19, 3.5 and 2.5 dB nearer than they were at first, and a light band's drums −18.5, bass −19.5, rhythm
  −18.5: "just a bit light and wimpy in general", then "go a little harder", 2026-11-17), never so far up that another
  part goes more than 3 dB over it, within ±18 dB, and drums never more than 6 dB up (`DRUMS_UP`:
  a light piece's taps had come out *16 dB up*).
- `sounds.lines` also takes a `taste`, a turn of a whole voice. House sets it per voice (5.7). For
  Warcraft and Knight Rock `build.stage` reads it from each instrument's `level` in
  `orchestra.INSTRUMENTS` (taikos 0.4, handbells 0.6, contrabassoon 1.6, a cymbal roll 1.5...).

### 6.3 Tone per source

Each player's track gets the studio's own equaliser (`studio/jsfx/channel_eq`, `sounds.equalise`)
and little more (`sounds.chain`): *each further box used to be there on principle, and together they
made the orchestra dull and wide and unlike itself*.

| Source | Chain |
|---|---|
| strings, woodwinds | a low cut by instrument (`LOW_CUT`: violins 170 Hz, flute 230, celli 58, basses 30) and a top set by the ear (`voicing.json`, 7.1); brass adds tape |
| bells, plucked | low cut and the ear's top, an echo for bells and zithers |
| war drums, deep stroke | stroke brought out, box at 280 Hz down, stick at 3.2 kHz up, parallel compression, tape |
| band kit | more stroke, box at 480 Hz down, shell at 200 Hz up, a little tape |
| kick | stroke up, box at 350 Hz down, beater at 3.8 kHz up; its sub left as designed |
| Muse parts | a low cut by part (`MUSE_CUT`), tone for the guitars, bass and organ (`MUSE_TONE`), echo on plucked and struck parts, tape on brass |
| choir and pad synths | low cut, then ensemble (choir) or width and echo (the Zyn pad) |

A voice that still comes out bright against the liked stems has its top taken down by name or by
instrument (`build.tamed_tone`, 2026-11-17, each measured on rendered tracks and noted beside it):
brass stabs and the bell at the moments shelved 9 dB from 3 kHz; the accordion closed at 5.5 kHz and shelved 14 dB from 2 kHz
(set for the harmonica that played it until 2026-11-18, and kept for TinySOL's accordion: see below); xylophone, glock and harpsichord shelved
7 dB from 4 kHz; banjo and mandolin 6 dB from 4 kHz, keeping the twang under it; a trombone doubling
a battle's bass shelved 6 dB from 1.5 kHz; in the band only (`band=True`), the church organ and the rock
organ closed at 6 kHz and shelved 10 dB from 3 kHz (the black chapel's had its texture 24 to 28 dB over
the liked band stems; the orchestra's organ sits about 5 dB over its own and is left as it is). The rest of the
band's texture and lead (the lead guitar, the reeds and pipes, the fiddle, the choir at the moments) fall away as a
guitar's cabinet and a keyboard's speaker do, and leave the top to the cymbals: the texture closed at 5 kHz and shelved
8 dB from 2.5 kHz, the lead closed at 6 kHz and shelved 6 dB from 3.5 kHz. The liked band stems are dark (their texture
falls away from 900 Hz, 35 to 41 dB down at the top; their lead is a guitar through a cabinet, gone above 5 kHz); the
band's had been 12 to 46 dB over, and a first cut at 7.5 kHz brought them only 4 to 5 dB nearer.

### 6.4 Buses

Each channel is a folder with a bus (`sounds.bus(channel, style)`). The drums get the equaliser, a
Dragonfly room, a compressor (SC4, −12 dB, 2.5:1), tape and a ceiling at −1.5 dB pushed 1 dB. The
others get a gentle compressor (−14 dB, 2:1) *that only takes the edge off the loudest notes*, tape
and a ceiling pushed 0.5 to 1 dB. *The compressors began 6 dB lower and every ceiling was pushed 3
dB, which flattened what the writer wrote between pianissimo and fortissimo.* The orchestra's buses
follow the ear (the pad shelved down above 4 kHz, the tune lifted at 600 Hz, the bass with a low
shelf, a bass enhancer and its top down); Knight Rock's follow the band stems (the lead lifted at
900 Hz, the pad down at 500 Hz, every top down). House's drums have their own bus: no room, no tape,
the box at 250 Hz down and *a compressor slow enough to let every stroke through*.

### 6.5 Halls, rooms and seats

- Every folder ends with a hall of its own (`desk.project`, `sounds.hall`: Dragonfly Hall Reverb,
  larger the longer it rings), so each channel carries its own share of the room. A Warcraft or
  Knight Rock hall rings 1.3 times its character's `hall` seconds, at most 3.8 s; House's 1.5 s.
- Lines send to it by family (`sounds.SENDS`: strings −10 dB, woodwinds −13, brass −9, war drums −8;
  Muse −12 unless `MUSE_SENDS` says otherwise), scaled by the character's amount.
- The studio's own players are seated front to back by early reflections (`sounds.row`); recordings
  made close (TinySOL) get more of the stage.

### 6.6 The mixdown

`desk.project` writes each track's REAPER project, `track.rpp`: a folder per channel, a track per
instrument line, the hall last. Each project begins with 1 s of silence (`desk.LEAD`), since some drum
plug-ins play nothing in the first block; it is cut off again. REAPER renders the five folders as
32-bit float WAV at 48 kHz. `desk.mixdown` then lays each stem on its own track in a second project,
`mix.rpp`, with its fader where it was measured to go and the story's ride (in House, the peak hold
and the end fade) as one volume envelope. `desk.ride_points` makes each envelope point the lowest of
the curve either side, so no held peak slips through. REAPER renders again. Both projects are kept;
`tools/reaper.sh <style>/<family>/<take>` opens one in REAPER's window.

### 6.7 File formats

| What | Format | Where |
|---|---|---|
| REAPER's renders | WAV, 32-bit float, 48 kHz; deleted once staged | `var/reaper/projects/...` |
| MuseScore's performances | FLAC, 24-bit, at MuseScore's 44.1 kHz | `var/reaper/muse/` |
| staged tracks | FLAC, 24-bit, 48 kHz stereo, one file per channel that plays | `var/studio/<style>/<family>/<take>/` |
| bucket pieces | FLAC, 16-bit, in stretches | `var/buckets/<style>/<bucket>/` |
| listening tracks and the mixer's 12 s pieces | FLAC, 16-bit | `var/listen/` |

Nothing writes MP3. `studio.read_track` still reads an MP3 left from the night of 2026-11-17.

---

## 7. Checking it

The studio cannot hear, so it measures. The owner's ears stay the judge.

### 7.1 The ear

`ear.profile` measures a recording: each of ten octaves' share of its power, 20 Hz to 20 kHz
(`ear.EDGES`, centres 28 Hz to 14 kHz), how wide each octave is, the crest, how fast its loud notes
start, how far its level wanders, how long it rings, and the centre of its spectrum. `ear.reference`
averages the profiles of stems the owner had heard and liked, kept in `var/reaper/ear.json` (the
recordings are gone): 875 of them, 384 Warcraft, 334 Knight Rock, 20 House and 137 of the faster
dance style House replaced, each labelled with its instrument. `ear.differs` prints the octave
gaps (plus is more than the reference). `ear.top` turns the gap in the top, against the body from
320 Hz to 2.5 kHz, into a bell at 3.5 kHz and a shelf from 7.5 kHz; `sounds.levels` keeps them in
`voicing.json` for violins, solo violin, horns, trumpets and harp (`HEARD_AS`).

    uv run --no-sync python -m freerock.studio.ear "violins in" path/to/mine.flac
    uv run --no-sync python -m freerock.studio.ear --list knight

*The numbers are no judge of whether an instrument sounds real. They do catch the faults that make a
mix sound cheap whatever is in it: no top, a boom nobody can hear but every loudspeaker has to carry,
peaks with no body under them, a bass that is not there.*

That file is all there is of the liked stems: `ear._references` stops with an error if it is
missing, and nothing is ever added to it (*the studio's own recordings must never be*).

### 7.2 Checks inside the render

- `build.stage` stops when a channel with 24 notes or more written comes out under −65 LUFS: *the Muse
  performances were laid into REAPER as the wrong kind of file, and three channels came out silent*.
  A channel quieter than that with fewer notes is left out of the take.
- `house.measure` checks every House track and writes `measured.json` beside it. A problem is: a
  section louder than the drops (by 0.5 dB); clipping (over 0.98); a part 5 dB louder outside the
  drops than in them; drums off the beat; chords or tune over 12 cents out of tune; chords, tune or
  pad under 65% in the key; a bass with more above 200 Hz than below; drums with no top. The bass's
  tuning is *noted, not judged*.
- `muse._plain` (6.1) and the level check in `render_some.py` (6.2).

### 7.3 tools/study.py

For each staged track: the loudness of each part and the story's swing (loudest minus quietest);
from the writer, how many lines play in each part, the spread of their pitches and how much of the
tune is a bar heard before; against the liked stems of its style and channel, how far its middle
(160 Hz to 1.25 kHz) and top (2.5 to 10 kHz) are off. Then the set's averages.

    uv run --no-sync python ../tools/study.py warcraft pastoral-morning-fields-1/1 haunted-requiem-1/1

### 7.4 tools/stem_interest.py and tools/orchestra_study.py

`stem_interest.py` asks whether each channel is worth hearing alone, *since the game brings channels
in and out*: notes to the bar, silent bars, different bars, rhythms, players, and for the bass its
average move, its repeats and how often it is off the root (Warcraft and Knight Rock only).
`orchestra_study.py` reads the OpenScore orchestra (`var/scores/openscore/*/score.mxl`) and writes
`var/passes/orchestra-study.json`: across its 72 movements the bass repeats a note 24% of the time
and moves by step 40%, the scoring stays the same for a median of 1.8 bars, and percussion plays in
31% of bars.

    uv run --no-sync python ../tools/stem_interest.py knight pastoral-battle-cry-1/1
    uv run --no-sync python ../tools/orchestra_study.py 80

### 7.5 The engraved score

`tools/score_view.py` lays a track's written parts out as a full score in the orchestra's order
(drums left out) and has MuseScore engrave it at 150 dpi into `var/passes/scores/`, by default the
first eight bars of the arrival (in House, of the drop). It shows where the tune is, what doubles it,
how the chords are spaced and what moves under them.

    uv run --no-sync python ../tools/score_view.py warcraft pastoral-morning-fields-1/1 --part summit --bars 8

### 7.6 The listening pages and the mixer

`tools/listen.py [style ...]` writes every staged track as one FLAC and a page for each style,
`var/listen/<style>/index.html`, served at `http://<music machine>:8765/listen/`. Each row's
`channels` link opens `mixer.html`: the five channels side by side with meters, faders, mute and
solo, and *the game's hand*, a slider from quiet to a fight that moves the drums and the bass but
never takes them under the part's floor. A 5.1 button appears when the browser reports six
loudspeakers. `tools/audition.py [--only <name>] [--keep]` writes `var/listen/instruments/`: each
instrument alone, as the bare recording, as it was and as it is now, with the ear's octave gaps.

---

### 7.7 The boredom meter and the judge

`tools/boredom.py` gives each channel of a take a fingerprint for every bar: its shape across the
octaves, its loudness and the figure its top strikes in sixteen steps. Its colour (a cepstrum of the
bar) has a top band of its own since 2026-11-19: the share of the bar above 4 kHz, which moving by
more than 3 dB ends a run; a drummer's turn from the hat to the ride under a kick on every beat had
hardly moved the cepstrum (House's Moonwell I: 44 bars of one colour before, 16 after). A heavy
band's cymbal turns still moved its top under 3 dB, too quiet in the mix to tell apart; since 19 November, 13:10,
the band kits' top is opened 3.5 dB from 5 kHz (`sounds.chain`; the study had the drums 3.7 dB under the liked
stems there). Since 20 November the top has its air too: the share of the top above 16 kHz, which moving by more than
6 dB ends a run. The kit's closed hat, its open hat and its ride sit within 1 dB in the top's share, but a closed hat keeps
a fifth to a hundredth of its top over 16 kHz, an open hat about a thousandth and a ride a three-thousandth: Downpour Run's
turn from the hat to the ride is 13 to 15 dB there, one cymbal's bars within 2 to 6 dB of each other. Cobra Fever III's drums
read one colour 47 bars across their turn from the open hat to the ride before, 22 after; pads, basses and House's
synths read as they did. Since 21 November the drums have their ring too: how far the quiet quarter of the kit's sound
over 6 kHz sits under its strokes, which moving by more than 4.5 dB ends a run. An open hat's sizzle fills the gaps
between the strokes that a closed hat leaves dry. Breakwater I's theme turns from one to the other every eight bars, 10
to 15 dB apart in its ring, the bars inside a block within 2.2 dB; under its clap and snare the strokes had stood within
1 to 3 dB of each other in every sixteenth and in the air, and the meter had read its drums the same 40 bars. It is
measured on the drums alone. It reports the longest
stretch that does not move, and flags 16 bars or more. Read a flag against the sheet: a close that
peels its groove away a quiet layer at a time reads as unchanged, and a part can change its notes
and still sound the same (0.4).

`tools/judge.py` runs Meta's Audiobox Aesthetics on a take, whole and part by part (`--parts`), in an
environment of its own (`var/tools/judges`). It scores enjoyment (CE), usefulness (CU), production
complexity (PC) and production quality (PQ), about 1 to 10, from 16 kHz mono in ten-second windows.
It is a gate and a pointer, not a target. Its first readings (2026-11-18): Bridge Charge scored the
same before and after its rise was opened on a wah and its drummer turned to the ride (CE 6.85 and
6.83, PQ 7.28 and 7.29). It hears production, not arrangement. The reworked House take Larks over the
Ridge scored PQ 7.83. Under a full load of renders it takes about six minutes a take.

    "var/tools/judges/.venv/bin/python" -I tools/judge.py knight/anywhere-banner-war-2/1 --parts

**The three judges** (2026-11-19: "find out if there are packages python or otherwise that are somehow
subjective about music sounding good for a genre", "use the best 3 and use the output to improve the
songs", "add it to the recursive loop for all genres"). `tools/judges.py` scores a take with three
models, in the same environment:

| Judge | What it says | Learned from | Hears |
|---|---|---|---|
| TuneJury (2026) | how much a listener would prefer it, as music of the brief it is given | 17,500 choices between two pieces (Music Arena, MusicPrefs, AIME, SongEval); made for instrumental music | LAION-CLAP-Music and MERT-v1-330M, 20 s of each part |
| SongEval (2025) | coherence, musicality, memorability, clarity of structure (and a singer's breathing, which means nothing here) | professional listeners' ratings of 2,399 whole songs | MuQ, two minutes from the first theme on |
| Audiobox Aesthetics (2025) | enjoyment (CE), usefulness (CU), production complexity (PC) and quality (PQ) | Meta's rated speech, sound and music | 20 s of each part, 16 kHz mono |

Each style has its brief (`judges.BRIEFS`), so TuneJury hears a Knight Rock take as hard rock and a
Warcraft one as a fantasy soundtrack; the empty brief is scored beside it, the authors' safe reading
where a brief is far from what it learned. Every excerpt is set to one level first, so that loudness
does not sway a judge. Read them as voters and pointers: rank a family's takes, find the part of a
take that scores under the rest, and judge a change to the writer on the same takes before and after
(the demos). None was made for long instrumental game music or for stems, and their numbers are not
targets: a change is kept for what the ear and the studies say, with the judges as one voice more.

    "var/tools/judges/.venv/bin/python" -I tools/judges.py knight/pastoral-banner-ride-1/5 --folder <a demo's folder> --label after
    "var/tools/judges/.venv/bin/python" -I tools/judges.py --watch --since "2026-11-19 08:30"     (the loop)

**Working on each score, every pass** (2026-11-19: "looks like your scores went down in some places
put into the loop ways to work on each score with each pass"). `tools/judges_report.py` reads the
records and says, for each style, which score and which part of the story fall lowest across its
takes, and which scores fell after each change (a demo's before and after, by more than the judge's
noise: TuneJury 0.05, SongEval 0.08, Audiobox 0.15). Each pass takes the first of those as its target
and tries the lever that answers it (the table in the README, "How the songs are judged"): a
take's riff, fills and lead for memorability and coherence; the tune and the chords for musicality;
the stops, fills and contrast between parts for clarity; the ending and each part's energy for
TuneJury; the desk for Audiobox. One or two takes are made with the change and judged against
themselves before; the change is kept if its score rises and nothing else falls beyond its noise.

**A before and after is one take only if nothing else moves** (2026-11-19, 13:00). The judges give
the same scores to the same audio (King's Oath's morning take judged twice: SongEval identical to the
hundredth). But the orchestra's writers drew from one generator, the lead first and the rest after
it, and each instrument's place in the stereo field was drawn from it too as it first played: a
change to the close, or a part brought in anywhere, drew every later riff, bass line and groove of
the take anew. Two demos of King's Oath with the same first two minutes on paper came back with
other drums and another bass there, and SongEval 0.08 apart. Since then the cast and the lead keep
the take's generator (its tunes are drawn first and stay as they were), each instrument's place is
drawn from its own name, and the rhythm guitar and the drum cycles have their own (`Take.own`): a
switch turned in one part changes that part alone (ROCK_ENDING the close, LEAD_ANSWERS the lead).
A change still has to move a score by more than its noise on two takes before it counts; a fall
within the noise is not a target.

The records go to `var/passes/judged3.jsonl`, one a take. On this laptop's processors it takes a few
minutes a take; a GPU would take seconds (an RX 5700 XT is RDNA1, which ROCm does not support).

## 8. How to make and change music

### 8.1 Before you start

The studio needs REAPER, MuseScore Studio and Surge XT under `var/tools/`, the sfizz plug-in built
into `var/tools/plugins/`, the LV2 plug-ins from the system's packages, Muse Sounds from the Muse
Sounds Manager, and the sample sets under `var/samples/`. `tools/stems/README.md` says how to fetch
each and under what licence. Renders are heavy; on the music machine they run under `taskset` and
`nice` on a share of the processors ("continue to make tracks in the bg at half cpu so the player
still works"), and nothing is killed to make room ("dont hard stop any renders or tasks 9am is not a
hard stop"). Never rewrite an instrument's SFZ file while a render runs: sfizz loads it again and the
render stops dead. `render_some.py` writes every instrument out before it begins for that reason.

### 8.2 List what there is

    uv run --no-sync python -m freerock.studio.build --list
    uv run --no-sync python -m freerock.studio.build --list --style knight --only stomp
    uv run --no-sync --with numba python -m freerock.studio.club --list
    uv run --no-sync freerock pieces list warcraft

Staged tracks are the folders under `var/studio/<style>/`; the listening pages list them too.

### 8.3 Render chosen tracks

Warcraft and Knight Rock, a family and a take each:

    uv run --no-sync python ../tools/render_some.py --workers 3 --until 23:00 pastoral-morning-fields-1/1 pastoral-battle-cry-1/2
    uv run --no-sync python -m freerock.studio.build --only requiem --workers 3

House, through its desk:

    uv run --no-sync --with numba python ../tools/render_some.py --workers 2 regal-01/1 mystic-01/2
    uv run --no-sync --with numba python -m freerock.studio.club pastoral-01/1

`render_some.py` begins nothing after `--until` (the next time the clock shows it) or once its
`--stop-file` exists; tracks in hand are finished and saved, and a failure does not stop the rest.
`build` skips takes already staged.

### 8.4 Where staged tracks go

| What | Where |
|---|---|
| the track | `var/studio/<style>/<family>/<take>/track.json` and `<channel>.flac` |
| House's checks | `measured.json` beside them |
| the REAPER projects | `var/reaper/projects/<style>/<family>/<take>/track.rpp` and `mix.rpp` |
| MuseScore's performances | `var/reaper/muse/`, a cache by what was in each part |
| instruments, levels, tone | `var/reaper/sfz/`, `var/reaper/templates/levels.json`, `voicing.json` |

A new render of a take rewrites its folder's files, and a channel that falls silent loses its old
recording (`studio.write_track`); to keep the old take for comparing, copy the folder to
`var/rejected/` first.

### 8.5 Listen and measure

    uv run --no-sync python ../tools/listen.py warcraft
    uv run --no-sync python ../tools/study.py warcraft pastoral-morning-fields-1/1
    uv run --no-sync python ../tools/stem_interest.py warcraft pastoral-morning-fields-1/1
    uv run --no-sync python ../tools/score_view.py warcraft pastoral-morning-fields-1/1 --part valley

Then open `http://<music machine>:8765/listen/`. "let me see a song demo when youve figured it out":
one or two tracks are heard before a set is rendered in bulk.

### 8.6 Put tracks into a bucket safely

The server keeps each bucket's list in memory and writes it back as it plays, so a bucket is written
only while the server is stopped; `freerock pieces add|drop` and `fresh_bucket.py` refuse while
anything answers on port 8765. A bucket is rebuilt only with the game off, and never left half-built.

1. Check the game is off: `curl -s http://127.0.0.1:8765/api/snapshot`; `seconds_since_read` under
   120 means it is being played.
2. Keep the bucket as it is: `cp -al var/buckets/<style>/<bucket> var/rejected/bucket-<style>-<date>`
   (hard links: instant, no room taken). A style has one bucket, `all`: its song goes wherever the player
   goes. (Until 2026-11-20 a bucket was named after the zone it was begun in, which said nothing true about it.)
3. Stop the server by the PID that listens on the port: `ss -ltnpH "sport = :8765"`, then `kill
   <pid>`; wait until `kill -0 <pid>` fails, and `kill -9` after 3 s. Never `pkill -f`: the pattern
   matches the shell that types it.
4. Build: `uv run --no-sync python ../tools/fresh_bucket.py <style> --keep-style`. It takes out every
   piece whose source begins with `<style>/` and puts every staged track in. Without `--keep-style`
   it also makes this style the one in force. `freerock pieces add <style>` only adds tracks not in
   yet: a re-rendered take keeps its old pieces unless its source is dropped first (`freerock pieces
   drop <style> <style>/<family>/<take>`).
5. Read the last lines: `tracks put in; the bucket now has ...` and any `NOT put in`. If the build did
   not finish, put the kept copy back.
6. Write the pages (`tools/listen.py <style>`), start the server again detached (`setsid nohup uv run
   --no-sync freerock serve ... &`) and reload the player page.

On the music machine `var/passes/rebuild.sh <style>` does all of this; it lives outside git.

### 8.7 Add a character or a family

**Warcraft or Knight Rock.**

1. Add a `C(...)` at the end of `orchestra.CHARACTERS`. A family's seed comes from its character's
   index, so a character put in earlier would change every family after it: *new ones go at the end,
   so that the families already written keep the numbers they were written from*. Give it title
   words of its own: titles are drawn in plan order and must be unique. The plan names the camps
   after everything else, so a new character that is not a camp also goes into `build.LAST_ADDED`,
   which names it after the camps: otherwise it could take a title a camp already has. Its name
   becomes a folder name: letters and spaces only, no apostrophes (`shepherds rest`).
2. Fill its fields (2.5): `kinds` from `kinds.KINDS` (or `KINDS_ALL`), `role` from `studio.ROLES`,
   `serves` as in 2.6, `modes` that `THEMES` has, instruments from `orchestra.INSTRUMENTS`, grooves
   from `GROOVES`; `style="knight", band=True` for the band.
3. Give walking, night, cave, inn and camp music its ground in `orchestra.SETTINGS_OF`.
4. Run `uv run --no-sync --with numba pytest -q tests/test_studio.py`: it checks that the instruments
   and grooves exist, that every kind of place has light and heavy walking music, that every role has
   music, and that the families are 450 to 510 s with the right shape.
5. `build --list --only <name>` shows its families. Render one take, listen and study, then the rest.

**House.** Add a `house.Family(...)` to `house.PLAN`: name, title, moods, role, serves, light, tonic,
loop, the five lengths (eight-bar phrases; four for a fight's opening), kick pattern, swing, machine
(909, 808, 707, 606) and palette. Its seed is the CRC-32 of its name, so its place in the list does
not matter, but a family with takes is never renamed. A palette's sounds must exist in `house.BASS`,
`KEYS`, `LEADS` and `PADS` and have a player in `club.PLAYED`. Run `uv run --no-sync --with numba
pytest -q tests/test_studio_house.py`.

**A new kind of moment** is a change to the director (`director.PLACES`) and to `studio.ROLES`, and
every style needs music for it. Camping (2026-11-17) is the pattern: one role, written for all three
styles the same way: watchfire, still hunt and uneasy vigil (Warcraft), campfire (Knight Rock), three
camp families (House). The same afternoon a second camp was written for each sort of country
(shepherds rest, fen fire, oasis embers, crows rest), each with winds, plucks and a ground of its own.
A camp is one line over a drone. Give it a pad of one voice (oohs, celli slow, basses slow, organ):
`strings slow` splits into four string parts even as a drone, and the first marsh camp, written that
way, had 13 to 17 players at once where the other camps have 9 to 13.

**Never change a family that has takes.** Its changes, key and tempo are shared with its kin in the
bucket. Write a new family.

### 8.8 Add or replace an instrument, and measure it

**Played by MuseScore.**

1. `orchestra.INSTRUMENTS`: its range (`low`, `high`), its `home`, whether it sustains (`held`), how
   early it must speak (`early`), and `wired` for an electric guitar.
2. `muse.PARTS`: the MuseScore part (a name in `muse.KINDS`, or a drum staff in `muse.PERCUSSION`), the
   notes it takes, how it is played (`""`, `"trem"`, `"pizz"`) and, as a fifth item, the Muse Sound by
   pack and name (`Muse Woodwinds/Bass Flute`). Per-piece choices go in `muse.CHOICES`.
3. At the desk: its low cut (`sounds.MUSE_CUT`), hall send (`MUSE_SENDS`), echo (`ECHOED`), tone
   (`MUSE_TONE`), width (`MUSE_NARROW`), seat (`MUSE_SEATS`).
4. Hear it alone before a piece uses it (*each heard played alone first*). Known traps: a part name
   MuseScore does not know plays its plain sounds (`muse._plain` stops that render); a sound can sit an
   octave off at the foot of its range (the euphonium); some carry more than others at the same
   written strength (*handbells carry far more than the glockenspiel*; *the mark tree was at 2.0 at
   first: a night piece's drums, nearly all mark tree, came out 14 dB bright*); and MuseScore 4 can
   crash on a note at one particular moment of a recording (*a tubular bell 5:56 into frost hammer's
   track at 116 beats a minute, every time; a beat either side it played*): `muse.perform` then has
   the part played a bar later and cuts that bar off, so every note sounds where it was written.

**Played by the studio.** Put the recordings under `var/samples/` (and their licence in
`tools/stems/README.md`), add the folder and how it is played to `sounds.RECORDED` (`LONG`, `SLOW`,
`WIND`, `SHORT`, `RINGS`, `DAMPED`), and a `Sound` of `Player`s to `sounds.SOUNDS`. Give it a depth in
`sounds.DEPTHS` (the desk refuses a player without one) and, if it is a new family of instrument, a
place in `sounds.family`. A Surge patch is `Player("surge:patches_factory/<folder>/<patch>.fxp",
octave=...)`: play C3, C4 and C5 on it alone and read the pitch that comes out, as
`sounds.HOUSE_OCTAVE` was found. A House sound is mapped in `club.PLAYED`. Then measure it, and hear it
on the audition page (after adding a row to `audition.rows`):

    uv run --no-sync python -m freerock.studio.sounds --only <name>
    uv run --no-sync python ../tools/audition.py --only <name>

*While the lanes run, measure before the `Sound` points at the new players* (2026-11-18, TinySOL's
accordion for the harmonica that had played its parts): `tools/render_some.py` will not begin while a
player the plan uses has no measured level, so every list begun between the switch and the measuring
is refused (night.sh puts a refused list back to wait and stops its lane by its stop file). The
`--only` line finds only players a `Sound` already uses, so measure them straight from
`sounds.levels([...], display=...)` inside `reaper.Display()`, then make the switch. The accordion
was then heard against the harmonica on one inn of each style: in the Warcraft tavern its pad came
from +9.5, +10.2 and +18.6 dB over the liked stems at 1.8, 3.5 and 7 kHz to +2.7, -2.0 and -7.2, and
its upper middle from 6.5 to 18 dB under its body (the reedy whine gone).

The bagpipe was tried the same way and set aside, which taught the other half: *a held high reed is
a whine, and a bagpipe's tune is one too*. FreePats' chanter (CC0, F4 to G5, its scale its own: 28 to
67 cents under A 440, so `samples.pitched` is told to believe a measured pitch up to 80 cents off,
`cents_within`, where its two takes of a note agree) holding a drone pad's long notes had the band's
texture 30 to 34 dB over the liked stems from 1.8 to 7 kHz and its upper middle 1.5 dB *over* its
body, where MuseScore's english horn had it 21.7 under; as the highland reel's tune its upper middle
stood 7.6 dB over its body, where the tavern's and the drinking song's leads stand 5 to 6 under. It is
on the drive and measured (`sounds.RECORDED`, "bagpipe long" and "short"). Then it was *heard*: the
reel's tune on the english horn and on the chanter, at one loudness, and the ear chose the chanter
("new horn sounds better", 2026-11-18). So the chanter plays the bagpipe's tunes (`bagpipe`: the
highland reel, the stone circle) and a held drone is `pipe drone`, MuseScore's english horn at the old
range, until drones that can be held are found (the set's own G2 drone is 2.4 s, too short to go
round). *The numbers find what to listen to; the ear decides.* And keep an instrument's range
when the writing should not change: who sings the second theme is chosen by how far an instrument's
home note sits from the first singer's, and the chanter's narrower range had moved the bagpipe into
the band's leads.

### 8.9 Work in passes

The night of 2026-11-16 set the first method: "make 10 of each genre listen to it with musescore,
make it better and do that 3 times for each set of 10". The next afternoon, with the writer better,
it became one pass: "just do one adversarial pass instead of 3", "re render everything only at
night".

1. Write a list of `family/take` (the lists live in `var/passes/`, a queue folder per lane). By day the
   lanes render new pieces only, ordered by where the owner plays (the server's `var/log/link-*.jsonl`
   names the zones; `atlas.kinds_for` gives their kinds of place).
2. When a list is finished, study it once: `study.py` for the swing, the octaves against the liked
   stems and the tune's repeated bars; `boredom.py` for a channel that does not move; the three judges
   (7.7, `judges.py --watch` scores every take as it is made, in every style) for how a listener would
   take it as music of its kind, part by part; `stem_interest.py` for each channel alone;
   `score_view.py` for the writing; the ear for one instrument. Listen for what a musician would hear: a place that
   repeats, a tune that does not sing, a channel wrong for its place, too many players for a quiet one.
3. Change the writer or the desk where the study points, with what was measured, dated, in the
   comment beside the change: the comments in this code are its history. A change is heard first on
   one or two takes against the same takes before (a demo), by the studies and by the judges; the
   judges' part-by-part scores across a style's takes point at what to change next (the parts and the
   kinds of take that score lowest). The change goes into the
   pieces still to come. Nothing is rendered again by day.
4. At night (`var/passes/lane-tonight`, from 23:00) every staged track rendered with code older than
   its style's latest change is rendered again, once. A `render_some` run keeps the code it started
   with, so a track belongs to the time its run began, not the time it was staged. Unchanged Muse parts
   come from the cache.
5. Rebuild a bucket (8.6) only with the game off.

The passes so far looked for more swing between quietest and loudest (the orchestra's pieces reached
18 dB; the heavy band's went from 8 to 17–20), channels within a few dB of the liked stems octave by
octave, a bass that moves, a tune that does not repeat its bars, and every channel worth hearing alone.

---

## 9. What was tried and turned down

| Tried | Why it went | What replaced it |
|---|---|---|
| A bucket per zone | "we moved from duskwood but it should just keep the bucket growing", then "Its not about duskwood... duskwood is a type of place" | One bucket per style; music by kind of place (`kinds.py`) |
| Trance at 128 BPM | "change the trance to uplifting progressive house, like 110 bpm not 128" | House at 110 BPM |
| Cuts | "crossfades are too sharp"; "you gotta fade in and out of everything" | Slow blends; channels move over 3.5 to 6 s |
| Three-minute tracks | "rewrite all the music using the same concepts, but to 8 minutes" | Nine parts in two waves, about 480 s |
| A render engine of the studio's own | the owner chose REAPER: "reaper", "Then rerender with reaper i can buy it or whatever" | Everything rendered and mixed in REAPER |
| Bare samples, then hand-built sampled instruments | "the actual music is good", but "make the instruments sound less like a 90s piano", "still sounds like a 90s windows demo"; measured: filters that followed the note left the orchestra 10 to 18 dB short above 2.5 kHz, war drums tuned 5 to 15 semitones down, a chorus on the strings | Recordings as they are, then MuseScore with Muse Sounds: "the music is well written we just need a good renderer", then "sounds much better" |
| House's own synthesiser | "figure out how to make house music not suck" | `club.py`: Surge XT, Muse Sounds and the TR-8 kit in REAPER |
| A trumpet lead, and the SC's lead tone | "the lead synth sounds cheezy" (it was a trumpet); *two straight trumpets a few cents apart were heard as "a cheesy synth"*; the SC lead *has four times the power between 2.5 and 5 kHz that it has anywhere else* | One trumpet with a late vibrato (`sounds.VIBRATO`); the LP's lead tone |
| A soft 26-inch kick | "missing a kickdrum"; *a 26-inch drum whose body lay at 28 Hz and rang for seven tenths of a second* | Naked Drums' kick and a Geonkick sub; "think we need a little more kick drum": 3 dB more |
| Drastic floors (no drums when calm) | "the abruptness between fighting and not, its way too much now" | The floors of 2.6: drums and bass at 55 to 100% |
| A separate battle piece for every fight | "in normal fights dont play a separate battle piece dungeon bosses ONLY" | The playing piece's drums and bass come up; only dungeon bosses have their own |
| MP3 | "save stems to mp3 so theres more room" (one night); *encoding them as MP3 a second time changed what is above 2 kHz at only 19 to 24 dB under the music*, and the encoder's padding played as gaps | "switch it all back to flac": 24-bit staged, 16-bit in the buckets |
| A strong story ride, pushed buses | `RIDE` at 0.42 *took most of the written dynamics away*; lower compressors and pushed ceilings *flattened* the writing | `RIDE` 0.15 and gentle buses: "rewrite all music to be more dynamic" |
| House rides by the mean; a sub an octave under | the mean *took the whole drop 5 dB down*; the low sub sat *at 25 to 45 Hz: 12 dB over the liked there* | rides by the loudest note; the sub on the bass's own notes |
| One crown for every heavy moment | *every heavy piece had a choir and a bell at its moments, so every moment sounded alike* | Crowns by kind of place (`build.CROWNS`) |
| Hairpins from 1.5 s | *nearly every note of a slow piece swelled, which read as pumping, not phrasing* | From 2.5 s (`muse.LONG_S`) |
| Streams from music shops and services | their published terms forbid capturing or altering streams, or using them with games | The studio's own music |
