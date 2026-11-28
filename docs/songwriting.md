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
reaches only first drafts. A revised sheet is what the song is: a list that comes to the song again performs the
revised sheet, not a new first draft (`sheet.revised_of`, 2026-11-23; until then any re-render wrote a first draft over it).

`tools/revise.py <style/family/take> --recipe <file>` does both: the recipe is a Python file with `revise(sheet) -> (what, why)`;
`--dry` says which parts it would move and changes nothing; the take as it was is kept in `var/studio-demo/before-revise` (copied, not
linked: the performance writes over it), to be heard and judged beside the new one at one loudness; `--back` puts it back. It stays only
if the numbers and the judges agree it is better.

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
| Character: a kind of track | `orchestra.Character` in `orchestra.CHARACTERS`: 207, of which 163 Warcraft and 44 Knight Rock | none; palettes by kind of place (`house.PALETTES`) |
| Family: the changes | `orchestra.Family`, from `orchestra.family(character, seed, name, title)`: key, tempo, metre, lift, the chord under every bar, part lengths and levels | `house.Family` in `house.PLAN` (126): tonic, loop, five lengths, kick pattern, swing, drum machine, palette |
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
| every Knight Rock character a second time (`build.MORE_FAMILIES`, that night) | 2, planned after the round before |

That gives 489 Warcraft families with 1,074 takes (about 8,500 minutes) and 176 Knight Rock families
with 379 takes (about 3,050 minutes). House has 136 families of 3 takes (`house.TAKES`, about 2,000
minutes).

*More music for every scenario* (2026-11-22: "The drive is still at 11 percent tonight we need new
music following everything we learned"; "lets work on filling that drive with more music for every
scenario, following everything weve learned"). Each character has `build.MORE_FAMILIES` more families
of two takes beyond the plan's own, by style (Knight Rock two, Warcraft one: 72 Knight Rock families
and 157 Warcraft, 458 takes, about 60 hours; Knight Rock's second round that night, the music they
play, while Warcraft had 210 first takes still to make), each with its own key, pace, changes and
tunes, and written by everything the handbook has learned, as any take is. They are numbered on from
the character's own (`haunted-requiem-4`) and named after every family before them, so no family made
before changes; a family numbered ten would take the next character's seed, and `build.plan` refuses
it. Each one's first take is made and studied before its second (8.7). Their first takes go to the
night lane before the second takes of any of them.

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
finally goes back around", 2026-11-17). A song led by the instrument that led the last one costs 0.3, and by what led the
one before it 0.15 (`_ledAlike`; "make sure to switch up the instruments from song to song", 2026-11-23): which instrument that
is, `studio.lead_of` reads off the song's sheet (the lead channel's part with the most notes in the first theme, solos aside) when a
bucket is built.

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
In a company the partner is whoever has its part there, and only if that player can play the line where it is written (`DOUBLES_IN_REACH`, 2026-11-25): a lyre whose lowest note is E4, a xylophone and a kalimba had the plucked celli's doubling in seven songs and played the bass's line two and three octaves up in the bass's channel, 22 dB over the liked stems at 7 kHz in Whaler's Dole.

The line keeps within nine semitones under and eight over its centre: its instrument's home less 5,
but never above A2 (`orchestra.BASS_TOP`, `bass_centre`). An organ that plays the bass plays it on
the pedals, a harp on its low strings. (2026-11-19: Stained Glass Choir's organ, centred where it sits
as a pad, played its bass from A2 to F#4 around A3; the desk raised it 8.9 dB to its place, a tenor's
line 7 dB over the liked stems in the mids and 16 at the top, with nothing under it. The moonwell and
the elven hymn had the harp's the same way, around B3.)

*A company's tenor chair on the bass line* (2026-11-26, the studies of the songs written again, and the trace that followed them). Rush-Light Chant's bass line read 9 dB over the liked bass stems
at 3.5 kHz and Bellows-Boy's Pour's 12 to 13 over at 1.8 kHz and at the top. Both are companies whose chair for the writer's `celli` is a tenor, not a low string (`company_table`: the monastery's
choir, the iron brass's trombone), and on these takes `Character.basses` named `celli`, so the bass line itself was theirs. The register is not the fault and the cap is not broken: traced, the
centre is A2 as `bass_centre` sets it, every part's key note is C3, and the line runs C3 to B3 — a cello's own place, and what a cello has always played there. It is the timbre. A choir or a
trombone at C3 to B3 carries far more at 1.8 to 3.5 kHz than celli do, and the desk puts the whole channel at the bass's place, so the channel reads over the liked stems in the mids while the low
end is where it should be. (A guess tried on paper first and thrown away: holding each part's key note within an octave of the centre changes not one note, because they are already there.)
**The demo read, and the chair is not the fault** (2026-11-27, 01:00 to 05:08: both songs performed twice, once as they stand and once with the bass line taken off the tenor chair and given to the
basses' — the monastery's choir to its organ, the iron brass's trombone to its tuba — the tenor left in the bed, everything else the same, and four windows of each read by SongEval under
`basschair-1126`):

| | as it stands | the bass moved | |
|---|---|---|---|
| Rush-Light Chant, theme | 2.42 | 2.33 | −0.08 |
| Rush-Light Chant, summit | 2.67 | 2.64 | −0.03 |
| **Rush-Light Chant** | **2.54** | **2.49** | **−0.06** |
| Bellows-Boy's Pour, theme | 3.00 | 3.02 | +0.03 |
| Bellows-Boy's Pour, summit | 2.76 | 2.70 | −0.06 |
| **Bellows-Boy's Pour** | **2.88** | **2.86** | **−0.02** |

Flat on both songs, a shade down on both, every window inside the 0.15 that two renders of one patch move a judge. The bar was written down before the numbers landed: a gain over 0.15 on both
songs, or a large gain on one with the other not falling. Nothing of the sort. **Nothing in the writer changes, and the tenor chair joins the list of things measured and thrown away.** What the
0.50 spread across the companies is made of is still open, and the strings count above says where to look next; the demo that settles it is one no-string company, one song, its bed given real
strings beside itself.
Not this fault, though it was studied the same hour: Whaler's Dole's bass (the mead hall's war tuba) reads 9 dB UNDER the liked stems at 894 Hz, which is the thin middle of a band's bass, 8.6.

*And the judges, asked across every company, say the same thing without being asked about chairs* (2026-11-27 02:57, the newest gate reading of every staged take that has one, 31 bands and
companies with two songs or more; the demo's two songs were chosen the evening before this was counted):

| the company's chair for the writer's `celli` | companies | how their songs read |
|---|---|---|
| a cello (`cello`, `celli slow`) | highland 3.43, quartet 3.41, caravan 3.07, bronze 3.07, silk 3.01, crypt 2.99, consort 2.97 | **3.14** over seven |
| a bassoon | carnival 2.91, winds 2.65 | 2.78 |
| a trombone | iron brass 2.85, horde 2.61 | 2.73 |
| a choir | monastery 2.19 | 2.19, the lowest of all 31 |
| | | a gap of **0.50**, where two renders of one patch move a judge 0.15 |

The order is nearly monotone from a low string down to a voice, and the two companies the demo is built on are the bottom of it: the monastery, whose choir takes the `celli` chair, and the iron
brass, whose trombone does. **This is a correlation, not the finding.** A company differs in far more than that one chair — the monastery is choir and organ the whole way down its bed
(`oohs`, `choir`, `choir`, `organ`), so a reading of 2.19 could be the voices everywhere and not the bass line at all. That is the whole reason the demo changes one thing on one song beside
itself. What the table does is raise the demo from a guess to a measured hypothesis, and say what to expect: if the chair is the fault, the moved arm gains; if the voices are, it will not.

*And counted a second way the same hour, a plainer thing explains it at least as well:* **how many strings the company has at all**. Counted over every chair a company fills (high, middle, low,
bed, chord, pluck), the reading follows the strings down — quartet 7 strings reads 3.41, highland 5 reads 3.43, silk 6 reads 3.01, consort 5 reads 2.97, and at the bottom iron brass, winds and
horde have **none at all** (2.85, 2.65, 2.61) with the monastery's one (2.19) under them. Split on the bed alone: the four companies with no string in their bed read **2.58**, the eight with one
read **3.11** — a gap of 0.53, wider than the chair's 0.49, and the two splits name almost the same four companies, because a company whose `celli` chair is not a cello usually has no strings
anywhere near its bed. With twelve companies and one number each these features cannot be told apart by counting; only a demo can.

**The caveat that matters more than either table.** The companies are *built* to be different ensembles — a brass band is meant to sound like a brass band, a monastery like voices and an organ.
If what this measures is that the judges prefer strings, then "mend the companies by giving them strings" would make every company sound like the quartet, which is the exact opposite of what was
asked for (unique bands; *"too much of the same instrument sounds"*, 11-23). A judge's taste is not a fault in the music. So the next demo is not "add strings": it is one no-string company, one
song, its bed given real strings beside itself — to learn **whether the judges are reading the writing or reading the instruments**. If the strings arm gains while nothing else changes, the
reading is of the palette, and then the companies stand as they are and the judges are the wrong instrument for scoring them against one another.

*Counted over all 741 staged takes that have the desk's sub, the chair decides where the whole low end sits* (the same evening; the sheet's first history line says when a take was written, not the
file's date, which two tools rewrote in hundreds on 11-25):

| the chair the bass line is written for | takes | the line's middle | the sub over A2 |
|---|---|---|---|
| `celli` | 69 | 46 | 36 in 100 |
| `celli slow` | 17 | 45 | 0 in 100 |
| `basses`, `basses slow`, `basses pizz`, `acoustic bass`, `fretless` | 245 | 37 to 41 | 0 to 12 in 100 |

A line written for the celli chair sits a fifth over one written for a bass chair, because `bass_centre` is the instrument's home less five and the celli's home is a twelfth over the double basses'.
That is a cello's own place and it is not new: 69 takes of the liked library are written that way. It turns into the fault above only where the company's player for that chair is a tenor, and the
desk puts the whole channel at the bass's place. The desk's sub follows it (`build.perform` gives the deep synth the bass line's own pitches), so in those songs the sub is up there too: a
consequence, not a second fault, and the liked library lives with it (13 in 100 of its Warcraft takes have the sub over A2 already). So the demo tries the one thing that is wrong: the chair.

*Tried and left off: a plucked bass played to be heard* (2026-11-22, morning: in a night's studies of Warcraft's walks,
inns and camps the bass stood 7 to 12 dB thin in its middle wherever its line was plucked, never where it was bowed or
blown). The fretless struck no softer than mezzo-forte (`orchestra.FRETLESS_FIRM`, 0.55): its tone did not change (MuseScore's
fretless is dark at every strength), the judges level. A pizzicato line's key note no lower than D2
(`orchestra.PIZZICATO_FLOOR`, 38): the bass 2 to 7 dB fuller from 450 Hz up, Gull's Wind up with every judge, but White
Hearth, its line a whole octave up, lost its lowest octave and came out down: a bass's place is low. Both switches are
kept, off; a fuller pizzicato is owed another way.

*A light band's bass given presence* (`build.LIGHT_BAND_BASS`, 2026-11-22, night). The light bands' bass,
MuseScore's electric bass played softly in the walks, inns, camps and nights, stood 3.7 to 13 dB thin in its
middle in the studies of the day's new Knight families, where the heavy band's sits within 5. Its sound has
4 dB more at 800 Hz (7 over the sample in all). Judged as the whole sound's (bass1: two light songs, a heavy
band and a Warcraft fretless): the octave at 894 Hz 3 dB nearer the liked stems in all four, the mix's
loudness unmoved; the judges near level, SongEval up in sixteen of the light songs' twenty scores and
TuneJury with the brief up in three of their four windows, but the heavy band's last drop down (TuneJury
with no brief -0.18) and the fretless level. So it is the light band's alone, in an equaliser of its own
after the sound's (`build.tamed_tone`); the heavy band's and the orchestra's are as they were.

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
theme sings.

*From 2026-11-28 the solo sings over the band* (`orchestra.BRIGHT_TUNE`). When the turn comes first to a lead whose home is
under `SINGS_OVER` (G4: the clarinet's and the lead guitar's; the english horn, the horns, the trombone, the cello, the bassoon are
under it), the first lead of the same turn that sings higher takes the first theme and the low one doubles it in its own register
(`octave_of`) and may sing the second; a character with no lead that high gives it to its first strong voice that is (Warcraft),
and Knight Rock does so only in a heavy song (`BRIGHT_HEAVY` 0.85), so that the lead guitar does not take every tune. No draw of the
take's is spent on it: every note is as it was and only the singer changes. Why: the instrument demo (`instrument-1128`, the table of
things turned over, "Knight Rock's heavy songs fail for being heavy") gave six held songs' low tunes to bright voices and all six rose,
+0.22 on the mean, the heavy band songs +0.34 and +0.36. Written on paper the same morning it changes two of the night's twenty new
families; the 79 characters whose every lead and strong voice is low (the titan, the dwarven hall, the barrow kings, the house
orchestra's dark brass) are sung as they were, and only 14 of the 49 never-made orchestra families have a tune that sits high: a
high voice from each such palette's own family (a trumpet for brass, an oboe for low reeds, a violin for low strings) is the next
question, a change of the characters, not of the writer. Pads, plucks, figures, basses and grooves turn by take too. Each piece draws its Muse
Sounds from its seed (`muse.CHOICES`): six horns twice as often as one, and in one piece of three
the harp's part is a piano's.

*Who carries the tune, over every song the judges have read* (28 November; the busiest lead voice's player; each take once, by its
latest reading, and none whose sheet was revised after it was read; the bands and the characters go with the instrument, so across songs
this is a pointer, where the instrument demo is a test inside one song). Warcraft: the fiddle passes 10 of 10, the flute 13 of 13, the
whistle 6 of 6, the piano 8 of 8, the trumpet 13 of 14, the horns 28 of 31, the violins 34 of 41, the viola 16 of 20, the cello 15 of 20
— and the CHOIR 9 of 17 (mean 2.59), the brass section 7 of 12, the slow violins 2 of 8, the euphonium 3 of 6: a sung "ah" carries a
tune badly, and a low voice does not of itself (the horns, the viola and the cello, which carry most of the never-made orchestra
families' tunes on paper, pass three in four and more). Knight Rock: the lead guitar 52 of 67, the fiddle 18 of 20, the viola 5 of 6 —
and the horns 2 of 11, the english horn 2 of 8, the trombone 1 of 4, and a bright one as well, the MANDOLIN 1 of 8 (the whistle 1 of 3,
too few to say): so in Knight Rock it is not only how high the tune sits. (The bands' own leads, the fuzz 1 of 4 and the sweet lead 3 of
8, read low across songs because their bands do; inside a song they lifted the tune +0.34 and +0.36.) A first count at 09:45 took every
reading, revised sheets' too, and said the whistle 1 of 7 and the choir 9 of 19. The day's swaps test it inside songs (`revise-1128b`):
Bitter Dirge's whistle and Soot Toll's mandolin to the fiddle, the choir of Bone Rite's and Smoking Crown's second takes to the violins,
Keg Toast's horns to a trumpet and Cinder Ritual's bass clarinet to a clarinet (their families' high voices), and two liked songs' tunes,
Sentence March's english horn and Limping Shortcut's alto sax, to their bands' own lead guitars.

*Nor by a mandolin or a whistle in Knight Rock* (`WEAK_TUNE`, 28 November, noon). Where a Knight Rock take has another singer over G4 —
among its leads, or else its first strong voice that sings over and is not one of them — the mandolin and the whistle sing neither theme:
they leave the leads' order, and the second theme is not given to one of them either, unless nobody else can sing it (a character whose
only voices are a whistle and a fiddle, as Bitter Dirge's: the swap gave the fiddle both themes, but the writer keeps two singers, so the
fiddle has the first theme, the one heard most, and the whistle the second). Where the character has them besides (a strong voice at the
moments, a pad) they still play, and a character with no other singer that high is sung as it was. Why: the day's swaps gave Bitter
Dirge's whistle, D6 in the middle, to the fiddle an octave down, and it rose +0.30 on SongEval's mean and +0.37 on its memorability; and
Soot Toll's mandolin to the fiddle at its own pitch, +0.19 and +0.20, the instrument alone. On paper it moves the first theme in 190 of
Knight Rock's 3888 family-takes over fourteen characters (five had the weak voice as their only lead, so it sang every take of theirs),
and one of the ten new songs of the night of 28-29, Cutpurse Lane, whose whistle's 268 notes go to its fiddle. Warcraft keeps its whistle,
whose tunes pass 6 of 6. (Writing it turned up an older fault: a wind note held past the take's end, its last chord left ringing, was
taken up again by the breathing AT the end — lantern walk's harmonica at beat 736 of 736, in every take where the harmonica sings the
tune. The breath that reaches the end is the last now: `breathe`.)

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

**An orchestra's tune stands over its accompaniment** (`build.ORCHESTRA_OVER`, 2026-11-25). Its lead channel has its place by the summit, where it stands 4 or 5 dB over the accompaniment, and a theme is scored softly: a solo flute
or a clarinet at a third of its strength over a harp's arpeggio. Read part by part, in four songs of ten of sixty a theme's tune stood 2 to 14 dB under what accompanies it (Forgotten Lullaby's second 14, Watchful Nocturne's 11,
Dripping Tunnels' first 8), and in a valley up to 20 under its bass (Golden Run). In every part it sings in the lead is brought up to a decibel and a half under the accompaniment, by 6 dB at the most, to 5 under where who has the tune is
struck or plucked (its attack is heard through more), and the bass is no more than 4 over it (half a decibel over, by nine, split the judges: a horn's and a cello's cave up, a celesta's dance and a soft choir's nocturne down);
`tools/lift_tunes.py warcraft` gives a song staged before the same, in its lead's stem, and the track keeps the dB.

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

These are the house band's instruments; there are twenty bands beside it, with their own (4.11).

| Written name | Played by | Seat and tone |
|---|---|---|
| rhythm guitar | two Muse parts: `Electric LP - Heavy` and `Electric SC - Heavy` | LP left (−0.6, 4 dB up), SC right (+0.65, 5 dB down, 11 ms late): *two takes are never together to the sample* |
| muted guitar | the same two, played short | closed above 3.2 kHz |
| single guitar | the LP alone | a heavy band's opening riff |
| lead guitar | `Electric LP - Lead` | more at 260 Hz, less at 3.2 kHz, echo and tape |
| clean guitar | `Electric SC - Clean` | the valley's tune; a band's plain `guitar` becomes it (`build.stage`) |
| picked bass, fretless | `Electric Bass` | more at 800 Hz (a light band's 4 dB more again, `build.LIGHT_BAND_BASS`), narrowed |
| rock organ | `Hammond Organ` | less at 1.5 kHz, narrowed |
| kit rock, kit room | the AVL Red Zeppelin kit (a 26-inch bass drum), the Black Pearl kit | the kick under the bass drum, 6 dB down |

The light pieces are *the same band unplugged*: fiddle (a Muse solo violin), whistle (piccolo),
harmonica (a blues harp: VCSL's Hohner Special 20s in C and F, through a harp player's amp, below), accordion (TinySOL's, in the sampler), steel-strung guitars and mandolin
(Muse acoustic guitars), banjo (a strumstick in the sampler), ocarina and pan flute (Muse flutes).
*Tried and left off: the banjo played by MuseScore* (banjo1, 2026-11-23). The light Knight songs with a banjo scored
lower than those without with every judge, their openings, where it plays alone, most (SongEval 3.09 against 3.14, TuneJury
with no brief -0.30 against -0.03 in the open), the oasis shuffle lowest of every Knight character. The strumstick's range
covers the banjo's parts (its files are named an octave low: nothing is folded). Played by MuseScore's picked steel-string,
on two oasis shuffles and a Warcraft drinking song: the rhythm's jangle and air gone (7 to 14 kHz 4 to 5 dB down) and its
pick nearer the liked stems, an exposed opening's Audiobox up 0.6; SongEval's coherence up in five windows of six, but
TuneJury with no brief down in four and Audiobox down in two themes. The judges did not agree, and the oasis band would
lose a colour: its steel guitar is MuseScore's too. The strumstick stays.
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

Leading a band's tune or solo, the harp read 4 to 11 dB thin in its middle and 12 to 16 over the liked stems at its top in
the studies of the night of 2026-11-22's 71 harp takes, where a fiddle's or a guitar's solo reads 7 to 11 over (the
lantern walk's four takes, one song: the harp's solos +12.7 and +15.2, the fiddle's +9.3 and +10.8). A darker tone of its
own for a band's harmonica lead, closed at 4.5 kHz, 6 dB down from 2.5 kHz, 3 dB of body at 700 Hz (`build.HARP_LEAD`), is
a switch, left off (harplead1, 2026-11-23): its top came 1 to 6 dB nearer the liked stems at 7 and 14 kHz, its middle stayed as thin;
SongEval 0.02 to 0.09 down in the three windows judged of six (the rest were stopped, the storm demo waiting), TuneJury with the
brief down in two, with none up in two, enjoyment level. The liked stems have no harp in them, so the distance is not a fault
for sure. The harmonica is wanted ("i better hear harmonica and banjo"): the thin middle is the writer's and the player's to
mend, not a tone's.

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
its own chord there; on King's Oath 12 of its 80 moves. Since 2026-11-23 it listens to whoever sings (`MOVES_LISTEN_ALL`): it heard the
lead guitar alone, and in the 16 songs led by another voice 24 in 100 of the moved chords sounded an eighth note's length or more against a
note of the tune a semitone away (6 in 100 a beat or more; 10 and 2 in the 55 led by the guitar, the second singer's); now none does.

*Until 19 November every band song answered its riff with the same two runs, a walk up to the fifth
(3, 5, 6, 7 semitones over the root) at the end of every fourth bar and a run down the blues scale
(10, 7, 5, 3) at every second, about 32 times a song: "hearing that same guitar riff climb in too
many knight songs", "cant you study acdc and do different licks".* The old walk-up is in no list.
Every note of the lead guitar is moved onto the key's minor pentatonic (`orchestra.BLUES`,
`orchestra.blues`), *as the riff bands of the late seventies did*.

**A riff that is a line** (the figure `low riff`, `Take._moving_riff`, 2026-11-23, night: "make them gritty and darker", "make sure to switch
up the instruments from song to song so theres variety"). `riff` and `chug` strike one chord in one of six rhythms; the low riff is four
bars of two-note chords and single notes on steps of the scale over the chord's root, from the seventh under it to the fifth over it
(`RIFF_STEPS`; the second only in a phrygian key, where it is the half step), the shape carried over every chord. Each take draws one for
each theme: every bar begins with the same half (`RIFF_HEADS`), the first and third bars end one way, the second another, the
fourth turns round by step into the next (`RIFF_TAILS`); in four of ten it has holes in it, in under half the fourth on its way to the
third or the fifth is the blues note. The muted string fills the eighths where the band is full, and a heavy band's bass goes with it
in eighths (`Take.riffed`). A long note of it keeps off a singer's held note a semitone away, whoever sings (`Take._tune_rubs`; the
standing riff listens the same way, below). Six of the third round's characters play it; no song made before does.

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
- **A light band's summit turns by taking away** (`orchestra.LIGHT_TURNS`, 2026-11-26), the third way and the one that stayed. Solder-Smoke Embers, a camp's song in six-eight at 65: its summit's guitars the same for all 24 bars, 66 seconds, twenty strummed notes a bar on the muted string and six on the open one, under a solo sixteen bars long and after it alike: under a solo a riff band comps, and a band that strums had played on at full. Now the strummers comp too (the down-strokes on the bar's strong beats, every other note of a broken chord), and in the last bar of each eight, but not the summit's last, the band strikes the chord once and lets it ring. *Played again: the meter's 24 bars gone (twelve at the most anywhere); the judges on its summit level to a shade up (TuneJury 0.33 and 0.32, SongEval within 0.07, enjoyment 7.79 to 7.83, production 8.09 to 8.34), where the summit played harder had gone down by 0.1 to 0.3 and stop-time by 0.4.* For the characters that grow (the newer ones); the others' takes are written as they were.
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

### 4.11 The bands

"all the knight rock songs sound like the same song", "too much of the same instrument sounds" (2026-11-23, evening, played). Counted over the 402
Knight Rock sheets staged: the same two distorted guitars, recorded distorted, in two songs of three; one bass recording in 96 of 100 (the fretless is the same
Muse part as the picked bass); the rock kit in 80; the organ's pad in 55; a lead guitar's tune in 62; 4/4 in 95; one form of nine parts in all of them. The
bands answer for the first five of those.

*The auditions, read at last* (2026-11-26, the audit). Every band was to be "tested for its musicality (the same music by each, measured and judged)" before it was given many songs. The
auditions were performed on 11-24 and 11-25 (`var/studio-demo/bands`: King's Oath, heavy, and Last Call Rock, light, by the house band and by each of the twenty bands;
`var/studio-demo/companies`: Scarab Necropolis by the orchestra and by each of the thirteen companies) and measured for level and tone; no judge that listens heard one until the 26th, after
two nights of songs for all of them. Read then by SongEval alone, each take as it stands (`var/passes/audition-read.sh`, `audition-said.py`; the mean of its five scores):

| On the same notes | Reads |
|---|---|
| The house band | 3.09 (heavy), 3.62 (light) |
| Level with it or over it on both songs: baroque (+0.30, +0.10), saloon (+0.21, +0.08), chop (+0.25, +0.02), cellos (+0.18, +0.07), twang (+0.23, +0.02), tweed (+0.21, +0.01), stoner (+0.15, +0.05), jug (+0.14, +0.02), lounge (+0.02, +0.13), hammond, shanty, grit | twelve bands |
| Within the judge's noise either way: cathedral (-0.09, +0.08), doom (-0.11, +0.11) | two |
| Under on one song: garage (+0.04, -0.25), bones (-0.34, +0.11) | two |
| Under on both: the drumline (-0.21, -0.57), the brawl (-0.26, -0.32), noir (-0.08, -0.40), the skald (-0.11, -0.34) | four |
| The orchestra | 2.91 |
| Every company level with it or over it: quartet +0.76, highland +0.68, caravan +0.53, bronze +0.38, consort +0.32, mead hall +0.23, carnival +0.22, winds +0.15; monastery, silk, crypt, horde and iron brass within 0.1 | thirteen |

So a band's or a company's sound is not what reads low in the songs written for them (round thirteen's Knight Rock songs read 2.76 where the same windows of older songs read 3.19): on
notes that are liked, sixteen of twenty bands and all thirteen companies stand with the house players or over them. What reads low is what was written for them (4.12: the metres, the
retelling, and what else the gate's reading of the resting songs shows). The four bands that read under on both songs are given no new song until they are reworked and read again on
the same two; garage and bones are read again before they are given a heavy song or a light one, each the kind it fell on. House's acts have no audition of this kind yet: one is owed.

*A company by its own songs, 2026-11-28.* The audition says a company's sound stands; only its own songs say whether what is written for it does. Counted over every
Warcraft take SongEval has read, by the players its sheet names: **the monastery passes 1 of 5** (mean 2.18 full, 2.23 calm; Candlewick Vigil, the lowest of round fifteen's
old songs, is one), the horde 1 of 3 (2.61) and the winds 2 of 4 (2.65), where the quartet passes 5 of 5 (3.41), the highland 6 of 6 and the house orchestra 163 of 215.
So the monastery is given no new song until what is written for it is understood, on paper first; the horde and the winds are watched. One low song is not a company's rule:
the iron brass's Gabion Rest read 2.09 the same night (low brass alone on a soft camp piece, its lead 22 dB dark at the top) where its other songs pass 4 of 6.

A character has the instruments of a band (`Character.sounds`, a key of `orchestra.BANDS`; "" is the house band, the sound of every song before that
night). The writer writes for the instruments of 4.1 and its notes are its own; `build.write` gives each to what stands for it in the band
(`orchestra.band_of`, `sounded`), and the sheet says which (`about["sounds"]`). What a band does not name is played as written.

| Band | Guitars | Bass | Lead guitar | Kit | Organ, clean guitar | Whose |
|---|---|---|---|---|---|---|
| doom | driven hard, an octave under, closed at 3.8 kHz | fuzz | fuzz | mallets | horns; chime guitar | headsman's square, leaden sky, drowned shaft |
| stoner | fuzz | fuzz | fuzz | rusty | choir; chime guitar | cathedral ward, hollow moon |
| tweed | crunch | round | sweet | rusty, brushed where it was the room kit | as written | rogues' quarter, watch on the wall, fever swamp |
| chop | one, driven, short, its middle forward | fuzz | sweet | rusty | horns; wurly | pit fighters, drowning ride, echo forge |
| shanty | crunch | a tuba | sweet | rusty | as written | press gang |
| twang | clean, a tremolo and a spring | round | sweet | rusty, brushed | oohs; twang guitar | whetstone fire, deserters' camp, bone caravan |
| lounge | chime (a clean guitar, an ensemble, an echo) | round | sweet | brushed | as written; rhodes | last orders, smoke den, graveyard shift, black heath, spider vault, glass tide |
| cellos | two cellos, each driven, one each side; muted, plucked | fuzz | a viola, fuzzed | mallets | choir; a cello | blackwater waltz |
| cathedral | a church organ; its muted string the celli plucked | fuzz | fuzz | mallets | choir; harpsichord | five black kings |
| saloon | an upright piano | round | sweet | rusty, brushed | oohs; wurly | hearse shuffle |
| hammond | a drawbar organ, its amplifier driven | fuzz | sweet | rusty | choir; rhodes | iron market, thunderhead |
| grit | a Wurlitzer, its amplifier driven, a little tremolo | round | fuzz | rusty, brushed | oohs; wurly | alchemists' row, gin alley |
| baroque | a harpsichord; its muted string the celli plucked | round | a viola, fuzzed | mallets, brushed | choir; harpsichord | jesters' cellar, warden's lantern |
| bones | a marimba | round | a clarinet | mallets | oohs; marimba | bonemongers, bone fire |
| garage | two hollow-bodied electric guitars, on the edge, one each side | a jazz bass, its amplifier driven | one of them | sticks | a Wurlitzer; an archtop | tanners' yard, squall line, smugglers' run |
| skald | a bowed cello as a synthesiser's oscillator, driven, one each side, a tagelharpa's plucked string its stroke | a bowed double bass the same way, driven | an erhu, its amplifier driven | mallets | choir; a lyre | rainmaker's drum, scavengers' camp |
| brawl | a baritone saxophone, driven, one each side | a tuba | a trumpet | the metal kit | the brass; a saxophone's notes as an accordion's reeds | coal exchange, avalanche |
| noir | an archtop; its muted string the celli plucked | an upright, plucked | a baritone saxophone | a jazz drummer's | oohs; a vibraphone | rain alley, informer's walk, last tram |
| jug | a banjo tuned as a guitar | a double bass, plucked, no higher than E3 | a fiddle | a kit through a worn microphone | an accordion; a mandolin | moonshine hollow, blood feud, graveside picking |
| drumline | a trombone; its muted string a bassoon | a tuba | horns | a kit whose every drum is a snare | choir; a euphonium | executioner's parade, forlorn charge, black regiment |

**The guitars and the basses** are Muse's clean guitars and its electric bass through an amplifier of the studio's own (`studio/jsfx/amp`, `sounds.AMPS`):
a cut and a lift before the valve, one of five valves four times oversampled (clean, crunch, drive, fuzz, torn), an octave under (a
flip-flop that follows the string, as an octave fuzz has), the tone stack, the loudspeaker's top, a tremolo and a spring. Each was set to stand where the house
band's own does, the same riff and the same tune rendered by both: the two guitars together at −16 LUFS, muted −17, the lead −20.5, the bass −12.3.
Two guitars sit at ∓0.6, the second 11 ms behind, as the house's do; the chop's and the twang's are one guitar each, off the middle.

*Held together* (`muse.SQUEEZE`, 2026-11-23, 23:40, the first six songs). The house's guitars are recorded distorted: the same phrase at a quarter, half and four fifths of
full strength reads −16.9, −16.3 and −16.2 LUFS, and its lead −20.9, −20.6 and −20.6. A clean guitar through an amplifier falls: the crunch −34.2, −23.5, −15.7; the sweet
lead −39.6, −28.6, −19.6; the chime −46.6, −34.6, −23.2. Sentence March's valley, a chime guitar's tune, read −48 and Keel-Scarred Shove opened on a riff at −40, under
its choir. So each amplified instrument's notes go part of the way to full strength before they are played (0.6 for the crunch and the sweet lead, 0.5 for the others,
0.45 for the chime), as an amplifier does to a soft hand: a crunch falls 7 dB, a doom 4, a lead 8. What is not amplified keeps its range. (The basses are hardly held, a tenth
and a seventh of the way: the house's bass falls from −27 LUFS at a summit to −38 in the first theme and −44 in a valley, and held by a half they stood at −29 everywhere
and sang over the tune.) A band's church organ, which the sampler plays from soft stops under 0.62 and full
ones over it, 15 dB apart, is held too where it has the tune or the riff (`orchestra.HELD`): Black Spire Ward's first theme was on its soft stops, under the guitars. A
harpsichord that stands for another instrument stands 8 dB nearer (`NEARER`).

*The tune's lift* (4.1) goes to 13 dB in a band of other sounds (`build.TUNE_MOST_BANDS`), and in the house band's songs wherever somebody other than a distorted guitar has most
of the tune (`build.tune_caps`; the guitar's stays 5): a saxophone, the oohs or a viola played softly read 10 to 12 under what they are at the summit, and of 414 Knight
Rock songs the first theme's tune stood at the old limit in 9 of the 259 a lead guitar leads, 30 of 60 a fiddle does, 13 of 17 a steel guitar, 10 of 20 a harmonica, 5 of 5 an
accordion (Regicide Banquet's trombone −44 LUFS over guitars at −26): songs led by somebody else that were heard as their guitars. In the bands of other sounds it is measured
against the bass as well (`TUNE_UNDER_BASS`): in a valley with no guitars the tune sings over the bass alone
(Deposed Interdict's stood at −46 over a bass at −29). `tools/lift_tunes.py` gives both to a take staged before, in its lead's
stem alone. *And the riff gives way* (`build.riff_gives`, 2026-11-25): an amplified riff plays a valley as loud as a verse, and who sings there may be a solo cello at a quarter of its strength: Sleet-Blind Salvo's riff was at −25 over
a tune at −39, lifted by thirteen already, and Choked Level's themes 2 and 3 under theirs. What the lift leaves the tune under, the rhythm comes down by, 9 dB at the most, in that part alone, as a guitarist turns down for the singer.
The tool gives it too, in the rhythm's stem.

*A bass is a bass, whoever it is* (2026-11-25, five songs of one night with theirs 10 to 14 dB over the liked stems' in the middle). The garage's jazz bass, its roundwounds through an open amplifier, stood at -12 to -18 dB of the whole from
320 Hz to 2.5 kHz where the liked stand at -26 to -48, and 6 dB thin under 80: its amplifier is shut at 1.9 kHz, its middle let down and its bottom up (`sounds.AMPS`), and it still growls, 6 to 11 over. A tuba's fourth to eighth
overtones are nearly all of it: three bands' basses (the shanty's, the brawl's, the drumline's) have 5 dB taken out at 340 Hz and 8 at 560 (`build.tamed_tone`), an orchestra's none.

**The kits** are the Big Rusty Drums, with sticks (`kit sticks`), with brushes (`kit swept`) and with mallets (`kit felt`), the same strokes on
the same notes as the rock kit's, their levels measured as every kit's are (`levels.json`).

*Held to the house's kit* (2026-11-24). Every stroke of every kit, struck alone at four strengths through the band's drums' bus. As they first were (`kit rusty`,
`kit brushed`, `kit mallets`, kept for the sheets that name them) their bass drum stood where the house's does at the strength of a groove (−24 LUFS) and the rest
far under it: the snare 12 dB under the bass drum where the house's is 5 under, the hats 14 where they are 7, a crash 12 where it is 4, the low tom 12 where it is 4. The
first twenty songs of the bands were heard as a kick, and in their valleys, where time is kept softly, the kick alone stood over the tune (Closing Cup's
tune at −43 LUFS, its drums at −35). Now the kick that goes with them is the half the house's is (`sounds.OWN_BOOM`: these kits have a bass drum of their own), the
set stands 1 to 5 dB nearer beside it (`KIT_LEVEL`) and each stroke is brought to where the house's has it against its bass drum (`KIT_GAINS`): within 2 dB
for nearly all of them at the strength of a groove.

*Brushes.* A brush on a cymbal or a tom is ten to twenty dB under the stick on it, at every strength, so what turned to the ride or crashed was gone. The groove
"brushes" (a side stick and a hat) was written for the house's kit; a drummer with brushes plays "swept" for it (`Take.brushes`): the snare stirred on every beat (`swish`, cut
from Big Rusty's recordings of a brush going round and round, each stroke from another place in another of them: `sounds.KIT_CUTS`, `sfz.SWEEP`) and tapped on the
backbeat. Ragged Beat's second theme, at −45 LUFS under a mix of −30, has its drums.

**The other instruments**: Muse's four saxophones (level against the lead guitar's tune: the tenor and the alto 6 dB down), its suitcase piano (`rhodes`), its
Wurlitzer (`wurly`) and its upright piano. A saxophone leads smoke den and graveyard shift; the keys strum where a guitar would.

**Covers.** A family's first seven takes (0 to 6) stay as they are. From take 7 on (`COVERS_FROM`) a band song of any other character is played by a
band drawn for the take (`COVER_BANDS`: a heavy song by doom, stoner, tweed, chop, twang or shanty, a light one by lounge, twang or tweed): the family's
changes and form, its own tunes, and not the sound of the song before it.

**Fresh families.** A house band's character has families past its third that are another band's song from their first take (`orchestra.fresh`, 2026-11-24). Forty-six were planned
in the house's sounds and none made, thirty-six of them next in the day's lists: the sameness again. The place, the moment and the writer's manner stay the character's; the
band, who leads (the second of the leads: take 1's first theme), the shape, a groove and a dark mode are given out round the table, so that no two beside each other share
them.

**Warcraft's companies** (`orchestra.COMPANIES`, 2026-11-24: "make sure were using unique bands on all genres"). The orchestra is not the only set of players: eleven companies, each who sings what the
writer gives to a high, a middle and a low voice, the four parts the strings have (the violins', the violas', the celli's, the basses'), who holds chords, who plucks, and a kit: winds, iron brass,
a monastery (choirs, an organ, handbells), a quartet with a piano, a consort (recorder, viol, harpsichord), bronze (vibes, handchimes, kalimba), a caravan (shenai, sitar, koto), the highlands (fiddle,
accordion, mandolin), a carnival (an E-flat clarinet, accordion, dulcimer), a horde (choir, horns, trombone, marimba) and a crypt (bass flute, celesta, music box, an organ); then, of the instruments found that day, silk (an erhu, a lyre) and a mead hall
(a bagpipe over a tuba, a lyre and a tagelharpa). Counted before: no instrument leads
more than 11 in 100 of Warcraft's songs, but celli and violas are in four of five, a glockenspiel in three of five, and a harp accompanies the most. Every character has a fourth family,
which is a company's, in a dark mode and sung low; its first three stay the orchestra's.

**Every band is tested before it is given more songs** (Sky, 2026-11-24: "keep up the multiple band concept but make sure to test each bands musicality"). The same two songs, a heavy walk
and an inn's, written once and played by every band and by the house's, eight bars each of the first theme, the valley and the summit: so the band is the one thing that differs.
Measured: each channel against the mix in each part, the tune against the riff, how fast the riff's notes start, the riff's, the tune's and the bass's tuning, notes out of
reach, how much of the tune lies under the riff, the mud and the glare against the house's; then the three judges. A band passes, or goes back to the desk with what was found.

**Who solos.** A solo was the lead guitar's, the fiddle's and the like; a song sung low solos whoever leads its summit (`SOLOISTS_LOW`: the viola, the cello, the
clarinet, the trombone, the horns and the saxophones too), to the top each has (`SOLO_TOP`). Three in ten of the two new rounds' songs had no solo before it.

A band's instrument is given its notes within its own range (`orchestra.given`): the writer wrote for the one it names, and an organ's top chord is out of the
horns' reach, so a note past the range goes an octave or more into it.

**The balance** is each band's own too (`build.BAND_BALANCE`, dB over or under the band's places): the doom's guitars and bass 1 nearer and its drums 1 back, the chop's
drums 1 nearer and its guitar 1.5 back, the lounge's and the twang's singers 0.5 over with the rest back, the cathedral's organ 0.5 and its choir 1 nearer.

### 4.12 Shapes and metres

The same evening's other half. Every Knight Rock song told the one story (2.1): nine parts, 455 to 492 s, as loud in each as in every other, 4/4 in all but five of a
hundred. A character can name a *form* (`Character.form`, `orchestra.FORMS`): the nine parts with other lengths and levels and, for a part, another part's
writing.

| Form | Seconds | What it is |
|---|---|---|
| (none) | 455 to 505 | the story: an opening, two themes, a build, an arrival, a valley, a climb, a summit, a close |
| verses | 350 to 390 | a verse, the chorus, a verse, the chorus, a bridge, the rise, the last chorus. The second theme is the chorus, with the moment's writing each time it comes; the second verse sets out where the first left off |
| riff | 295 to 330 | the same, loud from its first bar (its opening at 0.5 of full strength, where the story's is at 0.18): the riff has the opening alone; in the verses the lead calls two bars and leaves two for the riff to answer; its middle breaks down on the bass and the drums, as a fight's does |
| jam | 410 to 455 | the head, a solo by somebody who does not take the last one, the bridge, the head, the breakdown, the rise, the last solo and the head |
| burn | 430 to 480 | one long rise: every part is over the one before it, to the summit, and there is no valley |

A `Section` says which part it is (`part`, always one of the nine, so the study, the meter, the judges and the pieces take it as they take any), whose writing the band
has there (`like`), what the lead does (`sings`: a part's, or `again`, `call`, `solo`, `rest`) and whose theme it is (`whose`); in the story all of them are the
part itself. Its story word follows what it is written as, so the player's fight finds a chorus a moment and the bridge a theme. A chorus or a summit has the
breath before it whatever came before. Nothing made before has a form, and not one of 396 songs' notes changed as the forms went in (`hash_takes.py`).

*Openings.* Every heavy song opened on one guitar's riff, the bass holding a note under it. A character can say who opens (`Character.opening`): the drummer alone, or the
bass alone on the riff, with the guitars in at the half; blank for the guitars, as before.

*Metres.* Of the 70 characters three were in anything but four. The fifth round's have 3/4, 6/8, 5/4 and 7/8, and the riff that is a line (4.2) has heads and tails
for each (`RIFF_SHAPES`): six-eight's halves, five's three and two, seven's three, two and two. The grooves name places in the bar (*pulses*, *back*, *groups*) and
are the same names in any metre.

*The fifth round's ten* (forty families): blackwater waltz (3/4, verses), gallows jig (6/8, riff), crooked mile (7/8, riff), five black kings (5/4, verses), high noon
cairn (a burn, a trumpet over tremolo guitars), hearse shuffle (6/8, a jam on a saloon's piano), engine of ruin (riff), glass tide (a burn), and for the fights, which had
two battles and two bosses, blood gallop (6/8, riff) and colossal tread (5/4).

*The sixth round's ten for Knight Rock* (the same night): three towns (alchemists' row, five; bonemongers, a waltz over a marimba; iron market, a riff song on an organ),
two storms (thunderhead, six-eight; black hail, seven, on cellos), two inns (jesters' cellar, a jam in three on a harpsichord; gin alley, a jam in five), two camps
(outrider's fire, a waltz that only rises; bone fire, six-eight) and a night (warden's lantern, the same), where its songs still come round most.

*A long moment turns* (`Character.turns`). Two of the second round's songs (Ragged Levy, Regicide Levy) kept one guitar colour through a summit of 27 and 29 bars: the
dig-in (4.5 and after) draws one of three ways, two of which play on as written, and needs 24 bars. A character that turns has the stretch from the moment's half rung or
given the other theme's figure, in every moment of sixteen bars or more.

*A theme is told another way each time it comes back* (`Character.grows`, `orchestra.retold`). Two of the first four songs of the burn's form had 62 and 76% of their tune's bars heard before
(Spur-Lit Halter, Keyholder's Round), and of the verses' Deposed Interdict 68: a form says its first theme at three or four strengths, and each was the same pair of statements, the tune and the tune with
its leaps filled. The library's middle is 46% for Knight Rock and 32% for Warcraft. Where a character grows, the next statement of a theme anywhere in the song is the next of six ways: the tune; its leaps
filled; the same question with another answer (its second half told upside down, its rhythm kept, home as before: `turned`); as a player adds to it who knows it; another question with the answer it had; that
answer and that player together. The summit has the tune as it was first heard. On nine songs made already it took 10 to 28 points off; the seventh round's twenty-six characters stand at 21 to 50%, the middle
one 32. Only families with no take have it: the new characters, the house band's and the orchestra's past their fourth, and since 2026-11-25 every family that had none that night (`build.TOLD_ONCE` names the 624 that had:
seventeen of one night's new songs, the fourth families of characters written before, had 50 to 66% of their tune's bars heard before. On 52 families still to be made the middle one goes from 48 to 33% in Knight Rock and from 37 to 26 in
Warcraft).
An old song is told so by a revision of its sheet (the lead's parts alone, over the same band: 2026-11-24, the twenty-two most repeated, 50 to 76% to 32 to 60).

*Turned down, 2026-11-26.* After an evening of these songs: "most of the music we heard last night sucked, the new bands a lot of time just sound random, it got worse not better". A tune told another way
each time, half of it upside down, is not known again when it comes back; and how much of a tune has been heard before is not a fault to bring down. Counted as the share of the lead's two-bar phrases
that are played more than once, the liked library's tunes come back in 49% in the middle for Knight Rock (the lower quartile 44, nine songs in ten over 40) and 35 for Warcraft (the lower quartile 27);
three in four of the songs this rule made lie under 38. (That count was blind to a tune told again on other voices or in another key; from 2026-11-27 study.py
counts the tune heard again by its shape, which tells the liked from these songs better still: 7.3.) Four of them written again without it go from 15 to 38% up to 43 to 77. The 120 families that were staged with it keep it (`build.GROWN`,
`studio/grown.txt`: never change a family that has takes; a family taken out of the list is written plainly the next time it is made); every other family, 912 of the plan's that had been set to grow, is
told as its first telling was, its leaps filled the second time and what a player adds the third (`varied`, `decorated`). `build.TOLD_ONCE` is gone. `tools/study.py` now says how much of a tune comes back
and marks one under the liked library's lower quartile (7.3). That afternoon the first 37 families came out of the list to be written again while they rest (none of them is in the player): Knight
Rock's six in 4/4 by bands that stood with the house band in the auditions (4.11), and Warcraft's 31 in 4/4, 6/8 and 3/4; their takes of before are kept beside
(`var/studio-demo/retold-audit-1126/resting`), and each new one is read by the judges and held to the library like any new song (8.9). 83 are left: the ones in five and in seven, which need a new
metre as well, and those of the bands that read under.
*What Sky actually heard that evening, counted* (`tools/heard.py --day 2026-11-25`): 79 songs over four and a half hours, 64 of them for the first time (75 in 100 of the time), 60 written since the
23rd. Knight Rock was 45 of the 79 hearings and 26 of those were a new band's; Warcraft 34, with 15 a company's; House 2. So more than half the evening was Knight Rock, and most of that was the new
bands' songs, which the judges pass 23 times in 100 where Warcraft's new songs pass 67. The complaint and the numbers are the same thing said twice.

*And it worked, measured the same evening.* Of Knight Rock's songs resting under `audit-1126`, the judges read 39 as they were staged and 12 written again: 23 in 100 of the first passed the
gate, 50 in 100 of the second (the judges' five in the middle 2.95 against 3.12, Memorability 2.88 against 3.00). Six of the twelve pass: Runaway Gradient 3.50, Daylight-Starved Echo 3.35,
Copper-Still Hollow 3.34, Long-Haul Bottle 3.34, Fish-Quay Slab 3.26, Twister Uproot 3.17; five of those six were in 6/8, 3/4, 5/4 or 7/8 as they were staged and are in 4/4 now. The six that are
held (Auction-Block Gavel 3.06 to Shotgun Hoedown 2.72) are the writer's next question, not the band's: four of them are the jug's, the hammond's and the cathedral's, which read level or over the
house players in the auditions (4.11).

*Of the two things a rewrite changes, the metre is the whole of it.* All 34 of Knight Rock's rewrites were read by the small hours of 27 November, and they part as cleanly as a trial could ask:

| | read | pass | the judges, in the middle |
|---|---|---|---|
| left as they were staged | 39 | 9 (23 in 100) | 2.95 |
| written again, and already in 4/4 | 6 | 1 (17 in 100) | 2.84 |
| written again, and 6/8 to 4/4 | 9 | 6 (67 in 100) | 3.26 |
| written again, and 7/8 to 4/4 | 6 | 4 (67 in 100) | 3.20 |
| written again, and 5/4 to 4/4 | 6 | 4 (67 in 100) | 3.13 |
| written again, and 3/4 to 4/4 | 7 | 4 (57 in 100) | 3.09 |
| every rewrite | 34 | 19 (56 in 100) | 3.15 |

Telling the theme plainly and leaving the metre alone passes 1 song in 6, which is no better than leaving the song as it was (23 in 100, and the judges' noise is about 0.1). Moving it to four
passes 18 of 28, and from every odd metre alike: six-eight, seven-eight, five-four and three-four all land between 57 and 67 in 100. So it is the metre, and the retelling's cost, real as it is on
the writer's own count of how much of a tune comes back, does not show in what the judges hear over two minutes. The rule of 4.12 stands for both reasons, but the one that is paying is the metre.

*What the first twelve looked like, before the rest were read:* the twelve read fall in two sixes. Six were staged in 4/4 and only their telling changed (the theme as it was first told, not
turned): one passed, Runaway Gradient 3.50, and the five held read 2.72 to 3.06. Six were staged in 6/8 and are in 4/4 as well: five passed (3.17 to 3.35) and one held, Snake-Handler's Moan 2.89.
They are not the same songs by the same bands, so it is not a trial of one thing; but it agrees with what the liked library says of itself (its seven Knight Rock songs in 6/8 read 2.79 to 2.93 where
its 114 in four read 3.21), and the two together are why Knight Rock is written in four now. What the retelling cost is still real and still worth undoing: the writer's measure of how much of a tune
comes back rose from 19-27% to 38-65% in those first six. It is simply not enough on its own to carry a song over the bar.
The same afternoon the rest of those bands' and companies' came off it, 55 families, and are written in an even metre (`studio/even.txt`, `build.EVEN`, `orchestra.EVEN_OF`): five and seven go
to four, and Knight Rock's go to four whatever they drew, its three and its six too; the family keeps the key and the tempo it drew, so it is the same song in another metre. Why Knight Rock's six
goes as well: the liked library's seven Knight Rock songs in 6/8 read 2.79 to 2.93 by SongEval's five, every one of them under the lower quartile a new song is held to (3.08), where its 114 in
four read 3.21 in the middle; of the first nineteen new band songs the judges read, the five that passed were all in four. (Warcraft's three and six read level with its four: 3.10, 2.91, 2.92; its
few in five and seven 2.37 and 2.65.) So a new Knight Rock song is in four until the band's writing in six reads as its writing in four does.
28 are left on the list: the songs of the four bands that read under and of the two to be read again (4.11).

*And the liked library itself was changed that night, in place* (2026-11-26, the same audit). In the night of 24 to 25 November the retelling was also laid on 41 takes that existed, by
revisions of their sheets (the line above, "an old song is told so by a revision of its sheet"): 27 of them were in the player on the 26th, 14 with the retold tune performed and 13 with the sheet
waiting for its next performance. On the 26th they were put back as they were before the revision (`tools/revise.py --back`; each retold take is kept beside, in `var/studio-demo/retold-audit-1126`).
The same night `tools/lift_tunes.py` brought the lead stem of 135 older takes up in place (127 of Knight Rock's; 5 dB at its most in the middle one, 8 at the most; in four it took the rhythm's
stem down as well), and `tools/open_up.py` had by then lifted the openings of 237 (210 of Warcraft's), none of them read before and after by anyone who listens; the lift had no way back
until that day (`lift_tunes.py --back` takes it back from what each track wrote down; `open_up.py --back` was there). (The 65 takes that carry "riff gives" are not all that tool's: 61 are band
songs the desk performed with the rhythm taken down already, and wrote the same words for. What the tool lays in place it now writes down as its own, "riff gives again", and takes back that alone.) Whether those stay is for the ear that plays with them. A take that is liked is
changed only beside itself: the new one is staged where the old one is not lost, the two are read by the judges and heard, and the old one stands until the new one is chosen.

*Three of them performed again, and read* (2026-11-26, the same day; `var/studio-demo/audit-plain`, the same band's instruments, the same two windows by SongEval, label `plain1126` beside
`round13`). Written plainly means here: in 4/4, each theme as it was first told, nobody sung an octave down. Red-Wind Howl (the stoner band's, from 7/8): 2.85 and 2.79 as staged, 3.13 and 3.19
written plainly, where the liked library reads about 3.2. Tally-Clerk's Ledger (the hammond band's, from 5/4): its theme 3.06 to 3.27, its summit 2.73 and 2.74. Crepe-Band Mile (the drumline's,
from 5/4): 2.34 and 2.31 to 2.32 and 2.20, no better; and the drumline is one of the four bands that read under the house band on the house band's own notes (4.11). So there were two things, and
they are apart: how the songs were written, which the plain rules mend where the band is sound; and four bands whose sound reads low whatever they are given.

*No more songs in five or in seven* (2026-11-26, the same audit). The house band's songs are in 4/4 in 95 of 100 and none is in 5/4 or 7/8. Of the Knight Rock songs begun after the evening of 11-24,
66 in 100 were not in 4/4 and a third were in 5/4 or 7/8 (of Warcraft's, three in ten, where six in a hundred were before); round thirteen's ten had not one in 4/4, and its 5/4 songs read lowest with the judges (2.62 by SongEval where the same windows of older songs
read 3.19). The 86 characters written in five or seven stay as they are; no more are added (a test holds the count). A new Knight Rock song is in 4/4, or in 6/8 or 12/8 where it is a shuffle or a jig;
a new Warcraft song in 4/4, 6/8 or 3/4.

*Three kits more* (2026-11-24, 23:10). A band is told by its drummer: fourteen had shared three kits, and fifteen snares told them apart. A Boston shop's jazz kit (six microphones to a stroke, mixed as an
engineer does, "club"), the same through the worn vintage microphone beside them ("lofi"), and a kit whose every drum is a snare, the kick and the toms too ("unruly"): each stroke's soft layers brought half way
up (a jazz drummer's softest is thirty dB under the hardest, where a groove is a third of the way), and each stroke of each kit brought to where the house's has it (`sounds.KIT_GAINS`, measured through the band's
drums' bus at four strengths). Whose they are was heard first (next).

*The eighth round's three bands* (2026-11-25), each with one of them: the noir, the jug and the drumline. The same heavy walk and the same inn's song as every band before them, eight bars of the first theme, the
valley and the summit. As they first came their plucked strings and their brass fell away in a valley as no held instrument does: the drumline's was at -40 LUFS, its tuba 10 dB under its own riff in the first theme; the
jug's inn at -34. So each player has a part of its own that is held part of the way to full strength (`muse.SQUEEZE`: 0.5 to 0.65), under a name of its own, as its instrument in an orchestra keeps the whole of its
range: the tuba came from -40 to -31 and the valley to -29. (Held near full strength it was all brass: in the drumline's first three songs, the same night, its bass stood 14 to 15 dB over the liked stems' in its middle
and 25 at its top. It is held as evenly at half strength, `muse.HELD_AT`, and shut at 1.8 kHz; the other two tubas and the garage's growl have more taken off them between 450 Hz and 1.8 kHz, `build.tamed_tone`. The other two were then shut at 900 Hz with twenty off from 500, found on their recordings; the same on the marching one, softer by then, left Casemate Fallout a thump, 13.6 dB under at 894 Hz and 23.5 at 1768. A tone is tried on a recording made as the instrument is played now, and through the desk: it has three bells, eight off from 500 Hz and is shut at 2.5 kHz. The war tuba, 7.2 and 21.7 under at the same two places in Coal-Trimmer's Dice, was performed again the same way: fourteen off from 500 Hz, shut at 1.8 kHz, and within 4 from 57 to 894 Hz. A company's brass in the bass, the horde's trombone and tubas 10 to 11 over from 894 Hz to 3.5 kHz on its reeds' tone (Beast-Pen Straw), has sixteen off from 700 Hz and is shut at 2.2 kHz (`build.BRASS_BASSES`): 6 over there, through the desk. Where a company's bass line itself is a bassoon's (the celli's part, to C4), the brass's tone does nothing for it, nor does it on the euphonium that doubles it: the carnival's stayed 8 over at 453 and 894 Hz. The reeds' own tone deeper does: twelve at 450 and five more at 900, and it stands 5 and 3 over, through the desk; the crypt's, the winds' and the silk's reeds, 4 to 6 over before, have it too.) A light song by the drumline is too soft in its riff (-39 under a mix of -28): it has heavy songs only. The noir's and the jug's lightest are right as they stand.

*The ninth round's ten for Knight Rock* (the same night) are the bands' that sound furthest from the house's, by measure (`tools/sameness.py`: of 179 songs any two are alike by 0.77, the house band's 126 by 0.80 to one
another; the fifty-three new ones by 0.75 among themselves and 0.745 to those; a song of the harpsichord's, the marimba's, the saxophones', the torn harp's or the church organ's by 0.68 to 0.71, one of the fuzz's, the crunch's or
the tuba's by 0.78): two inns (skittle alley, a jam in five on a marimba; masked supper, a waltz on a harpsichord), two storms (steeple lightning on a church organ, hull breach in seven on amplified cellos), two caves (drowned nave,
an organ's slow burn; clockwork deep, a marimba's riff in seven), a town (auction block, a saloon's verses), a camp (prizefighters' fire, a jam of saxophones) and two walks (burnt harvest, an erhu over a torn harp; harbour chain, a
drawbar organ's). *Warcraft's ten* are its companies': four towns (ship breakers, plague cloister, lampblack lane, side show), two inns (reed cutters' rest, singing bowl), two camps (silk tent, drum vigil), a storm (thunder
battery) and a walk among graves (kings' graves).

*The eleventh round's twenty* (2026-11-25) go to the bands and the companies that had two or three characters, where the music is heard most per song. Knight Rock's ten: two towns (fish quay, the shanty's in six; bear pit, the
skald's in five), two inns that are jams (coopers' cellar, the garage's in seven; revival tent, the drawbar organ's in six), two storms (dust bowl, the jug's riff in six; powder magazine, the drumline's in seven), a cave (sewer
chase, the noir's riff in five), a camp (prospectors' camp, the Wurlitzer's slow burn in three) and two walks (runaway wagon, the saloon's at a gallop; sleeping giant, the fuzz's in three). Warcraft's ten: two dark nights, which
it owed (sleepless ward, a quartet in five; hunters' moon, the consort in six), two towns (clan feud, the highland's; war chief's gate, the horde's in five), two inns (fever caravanserai; widow's parlour, a quartet's waltz), a
camp (peat wake), a storm (reef gale, the winds in seven), a cave (bell foundry, bronze in five) and a walk in the desert (waterless march, in seven).

*A tuba that is a band's bass is shut* (2026-11-25, afternoon). Three bands' bass is a tuba, and four of their songs in a row read 10 to 13 dB over the liked stems in the bass's middle after two bells on its
overtones (Split-Lip Long Count 15 at 450 Hz; Fish-Quay Slab 17 to 29 from 450 Hz to the top). A bell does not make a tuba a bass through a cabinet. Tried on the recordings themselves, no render: shut at 900 Hz, twenty
off from 500 and ten at 420, both stand within 4 dB of the liked stems in every octave (`build.tamed_tone`). The songs made before it are played again; a tuba song's family waits for that before its others. The garage's growly bass
the same way (Hoop-Iron Round, 11 over at 450 Hz): ten at 450 and eight off from 1200. A tone is found on the recording, against the liked stems, before a song is rendered to hear it; and what the recording
has in it already is counted (the tuba's first two bells were in the recordings the shutting was tried on: the tone is those and the shutting together). *A company's bass is its own reed or tuba* (the
same afternoon): the winds' contrabassoon, the horde's tuba, an orchestra's reeds and trombone where they double its line stood 7 to 10 dB over the liked stems from 450 Hz to 7 kHz in three songs, where bowed
and plucked basses stand within 3: eight at 450, ten off from 900 and shut at 3 kHz for those in the bass (`build.REED_BASSES`), and nothing for the strings.

*The twelfth round's twenty* (the same day), where Knight Rock's dark songs were one song still: of its 82 dark characters 46 play the low riff first, 59 are in minor first, 34 keep time on the brushes or the stomp, and
none had been led by a bass clarinet or a steel guitar. Ten for the bands with the fewest, each a moment its band had none for, on the patterns no dark song had kept time on (the tavern's, the toms', the anvil's, the desert's,
the ride): two inns (stokers' mess, the brawl's saxophones in three under a bass clarinet; ratcatcher's arms, the doom's slow blues in six under a baritone), two towns (stilt market, the cellos in five; flagellants' row, the
organ's hammer in six under a bassoon), two storms (lee shore, the shanty's in a fast three; levee break, the tweed's in five), a cave (the oubliette, a harpsichord tolling under a bass flute), a camp (strikers' picket, a steel
guitar in seven) and two walks (charcoal burners, the marimbas' jam in seven under a cello, who takes its first solo: a jam's two solos are two players', and a euphonium takes none; beak doctors, the Wurlitzer's in five under a trumpet). Warcraft's ten: of its 53 dark characters one was a cave's, three the
night's and four a storm's. Two caves (ossuary stair, the crypt's bass clarinet over a music box in seven; beast pens, the horde's trombone at a trudge in four), two storms (torn canvas, the carnival's waltz; moor gale, the
highland's jig), a night (night office, the monastery in three), a camp (sappers' trench, the iron brass alone), an inn (whalers' hall, the mead hall's viola over a lyre), two towns (dyers' quarter, the silk's; ferryman's
landing, the winds') and a walk (lamplighters' round, a quartet in seven). What a character names is sung by its company's own, and a name's place among its kind picks the player (`company_table`): the carnival's euphonium
is asked for as a bassoon. Five rules the suite holds a new character or family to, each broken once by these two rounds: a company belongs to the first kind of ground its character names (`COMPANY_FOR`), a song that opens on
its bass has the low riff among its figures, a hard House song goes at 118 to 132, a jam's lead is one of those who take a solo (`SOLOISTS_LOW`), and a town, an inn or a cave of weight 0.8 or more names no frame
drums (they strike its moments, and the big drums are a walk's and a fight's).

*The thirteenth round's twenty* (the same evening), by what is heard most a song and what there is least of: an inn's, a town's and a storm's songs come round 2.0 to 2.4 times each in Knight Rock, its night has five dark characters, its mystic and haunted walks the fewest songs; of 92 dark characters one each had been led by an oboe, a bass clarinet and a steel guitar, two by an accordion, a bassoon and a mandolin; and eleven bands had four dark songs. Ten of those bands, each a moment or a walk it had none for, in a metre it had not: two inns (blind tiger, the noir's slow blues in six under an alto saxophone, a jam; crimp house, the shanty's in five under a bassoon), two towns (customs house, the Hammond's hammer in five under a bass clarinet; hog market, the jug band's in seven under a mandolin), a storm (sirocco, the fuzz in seven under a trumpet), a camp (tinkers' camp, the garage's shuffle in six under an accordion), a cave (flooded archive, the cellos' chug in six under a euphonium), the night (swamper's hour, the saloon's piano in five under a subtone saxophone: a harmonica was written first, and a light band's tune is not a harmonica's, 8.7) and two walks (rune road, the skald's in three under an oboe; slow cortege, the drumline's in five under a clarinet, opened by its tuba). A groove that needs a kit is named only for a band that has it: "swept" is the brushes' on a swept kit, and the garage's sticks have no swish to play. Warcraft's ten are the nine companies that had three dark songs (the bronze two), where a town, a camp, an inn and a storm come round most and the night has few, each sung by players of its own that had not led for it (`company_table` says who plays what the writer names): two towns (gong smiths, the bronze's bass flute and ocarina in six; counting house, the consort's english horn and recorder in seven), two storms (white squall, the mead hall's bagpipe in five; monsoon gongs, the bronze's handbells in seven), two inns (garrison mess, the iron brass's horns over a tuba in three; lantern teahouse, the silk's erhu in five), a camp (pilgrims' shelter, the monastery's choir humming in six), the night (cold stars, the caravan's shakuhachi in six) and two walks (winter pier, the carnival's violin over a bassoon in five; barrow frost, the crypt's bass flute in five).

*The fourteenth round's twenty* (2026-11-26), the same way. Knight Rock: an inn's, a town's, a storm's and a cave's songs come round 2.0 to 2.3 times each, then the pastoral, the regal, the coast's, the highland and the desert walks and a camp's. Ten bands, none with more than five dark songs (a band has six at the most, the desk's test: three of the first ten written went to bands that had six, and were given to the noir, the fuzz and the skald), each a moment or a walk it had none for, in a metre it had not, led by what no dark band song had been led by: an inn (sexton's snug, the church organ's in seven under a recorder), a town (pawnbrokers' row, the chop's hammer in six under a flute), a storm (cloudburst riot, the saxophones' in five under a shenai), a cave (sump gallery, the fuzzed wurly's drip in seven under an ocarina), a camp (wreckers' cove, the noir's slow burn in seven under a soprano saxophone) and five walks: scarecrow lane (the tweed's waltz under a steel guitar, a jam), ravens' masque (the harpsichord's in five under a violin, opened by its bass), undertow (the fuzz in five under a growling saxophone), gibbet hill (the doom's in three under a bagpipe over its drone) and salt pan (the skald's slow burn under a shakuhachi). On a first take the summit is led by the second of a character's two strong players (they take turns by the take), and six of these ten first takes had no solo, a flute or a bagpipe not being one who may take it: the eight new leaders may (`SOLOISTS_LOW`; a violin two notes at once, the winds one), each to a top of its own (`SOLO_TOP`), and no song that was made has one of them among its low band's players. A band's song names no frame drums (the big drums' test): the desert walk has a taiko. Warcraft: a town, a camp and an inn come round most, then the haunted, the marsh, the regal, the mystic, the coast's and the pastoral walks and a storm. Ten of the twelve companies that have four dark songs, each a place it had none for and a metre it had not, sung by a player of its own that had not led for it: the mead hall's euphonium in a sealers' town on the ice, the caravan's cello over a shenai at a halt, the crypt's ocarina at a sin-eater's supper, the carnival's little clarinet on a ghost train, the horde's pan flute on a bog road, the monastery's full choir in a storm that rings its bell, the iron brass's trumpet on a conqueror's avenue in seven, the silk's clarinet by a water clock, the highland's fiddle among the kelp burners, the winds' oboe between hop poles. A theme's first telling is compared by its notes' names where a character grows (the test): a low character's singer goes an octave down where the middle of all its notes is at A4 or over, and a song that grows has other notes in it.

*A round bass is heard too.* The light songs of seven bands have the round bass, and it was closed at 1.8 kHz on a clean amplifier: four of one night's 8 to 10 dB thin in their middle and 32 to 36 under the liked
stems' at their top, and the lift of 4 dB at 800 Hz a light band's bass has (`LIGHT_BAND_BASS`) is the picked and the fretless one's, by name. On its crunch, with a step of middle at 850 Hz, it is 4 to 6 dB
darker than the liked bass and no more: the round one still.

*A band's string bass is heard as well as felt* (`build.BASS_HEARD_UNDER`, `bass_middle`, 2026-11-26). Nineteen staged band songs with the round bass, read octave by octave against the liked stems: eight within 5 dB at 453 and 894 Hz, eleven 5 to 18 under there, a thump with no note to it on a small loudspeaker. Neither a song's weight nor how low its line lies says which (a camp's bass at +4.5 and -2.2, a walk's of weight 0.9 at -5.6 and -10.5, an inn's at -9.8 and -18): a string bass that holds long soft notes has no middle, whoever plays it, and one that pumps has; and a tone set by the song's kind would lift the ones that have it. So the desk measures what was played: where a band's bass stem, all of it a string bass's, stands more than four under the liked stems in those two octaves, a bell at 700 Hz, two octaves wide, brings it to that at the mixdown, by eight at the most (`desk.mixdown`'s `tones`; `measured` keeps the bell as "bass middle"). Closing Cup played again: -9.8 and -18.0 to -2.7 and -6.5, the bell 2.5 of it, the rest the tones the round bass has had since it was staged. A tuba, a growling or a torn bass has the tone found for it and none of this.

*Warcraft's fifth round* (thirty families): three inns, where one song of fifty-one was heavy (cardsharps den in five, wake house a waltz that only rises, mutineers hold
in seven), three towns (quarantine gate, five, a burn; wreckage quay, six-eight; ash ward, seven), a night (hour of wolves, five) and three walks (last redoubt, a
burn; tide of teeth, five; burnt orchard, a waltz, a burn). An orchestra's verse-and-chorus has the second theme from its strong players each time it comes, the
slower line of that theme under it, and the first theme made to fit its changes at the last.

*The player* knows what plays a song: a piece carries the instrument with the most notes of each channel (`studio.sounds_of`, its `sounds`), and a song with the
last one's instruments counts up to `SOUNDS_ALIKE` (0.6) against itself, the one before that half as much and the one before that a quarter
(`forever.js` `_soundsAlike`), beside what leads it (`LED_ALIKE`). It takes each channel of a song from any take of its family, as it always has, but from takes
of one band (a piece's `band`, `studio.band_of`): a doom band's guitars are not laid over the house kit's drums.

## 5. House

`house.py` writes the notes as calls to the studio's own synthesiser; `club.py` takes those calls
down and plays them on real instruments in REAPER (5.7).

### 5.1 Tempo, keys and chord loops

Every track is 110 BPM (`house.BPM`) in four. A family names a tonic (all twelve are used;
`tests/test_studio_house.py` asks for that and for 40 or more different pairs of tonic and loop) and
a loop from `house.LOOPS`: 26 loops of four chords, each chord one or two bars, in seven modes (M1–M6
major, L1–L3 lydian, X1–X3 mixolydian, D1–D4 dorian, N1–N6 minor, P1–P2 phrygian, P3–P4 phrygian
dominant). Chord colours (`COLOURS`): triad, 7, 9, sus2, sus4, 5 and 6. Every section starts at the
top of the loop (`house.Changes.chord`). Swing delays the off sixteenths by up to 0.16 of one. 59 of
the 136 families are light. The walking, inn and night music is about as dark as it is light (49 of 89 are
light; the test keeps it between four and six in ten), and every inn, camp, night and town has a dark
one ("need some darker stuff", 2026-11-23; it was mostly light, six in ten, from the first night on).

### 5.2 The groove: kick, clap, hats

`house.Take.drums`:

- **Kick** on the family's pattern in sixteenths (`house.KICKS`): four (0, 4, 8, 12) in 65 of the 136 families,
  broken (0, 6, 10) in 21, broken2 (0, 6, 8, 14) in 20, broken3 (0, 3, 8, 10) in 13, half (0, 10) in 9, none in 8. It plays in
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
- **A long part turns every eight bars** (`house.EIGHTS_TURN`, 2026-11-26): in the last bar of each eight of a theme or a drop, but not its last, the kick rests from the bar's half, and where the take's fill is the lift the backbeat's drum plays two strokes into the next bar. (*The meter on forty first takes: in thirteen a theme's drums the same sixteen bars, Vine Cutter I's thirty. The sheets turned every eight, but the lift took the kick from a beat where a broken kick has no stroke, a four-stroke snare fill moves a bar's sound by less than the meter's line, and under them the kick and the backbeat never moved. Played again with the turn, Rat Trap I, Hush Money I and Vine Cutter I read eight bars at the most; the judges on their first themes: TuneJury with the House brief 0.69 to 0.76, 1.09 to 1.12 and level, enjoyment 6.90 to 7.02, 7.31 to 7.32 and 6.92 to 7.02, SongEval within 0.06 either way.*) A rest and a pickup, where the turns laid on the backbeat for sixteen bars (`THEME_MIDS`, `MIDS_WAY`) were not taken.
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

*A bass has its own tone at the desk* (`club.BASS_TONES`, 2026-11-26). The desk had one tone for every synthesiser's bass and one for every player's. Read octave by octave against the liked stems, from 226 Hz to 3.5 kHz, the staged basses of the newer acts stood apart from it, each the same way in every song: the square (the arcade's, the icehouse's) 7 to 9 dB over in its middle, four songs of four; the grinder 8.5 over at 1.8 kHz, five of five; the crust 5 to 10 over to 894 Hz, three; the pumphouse's round bass, played softly, 13 under at 453 Hz, three. Each has a tone of its own, found on a song of it played again through the desk: eight off the square's middle, two octaves wide (Hollow Stair I: +4.0, +3.1, +4.8, +4.8, +4.3 after it); the grinder's shelf seven deep from 650 Hz (Rendering Plant II: to within 5.2); seven off the crust's middle (Paper Trail I: to within 6.7 at 1.8 kHz, 4 to 6 under it); nine at 450 Hz and nine at 1.2 kHz for the round bass (Street Sweeper II: 13 under to 6 under: heard, where it was felt). *A bass's share in its key is noted, not judged*: Hollow Stair I's square bass read 42% and was taken for a bass that sounds its own major third; with the tone it read 40, and the same bass in Rope Walk I reads 87: a run of short low notes cannot be placed to the semitone from outside, and the number follows the line, not the sound.

*Tried and left off: the FM bass held lighter* (`sounds.FM_LIGHT`, the patch "house bass fm light", 2026-11-23). The
same note a little less modulated (0.25 for 0.27), its feedback toward a saw and the waveshaper's grit less (0.06 for
0.15, 1.5 dB of drive for 3), a design of its own with its own track template: a design reaches a render only through its
template, built once, so the first try, which set the numbers in the rendering process (fmlight1), played the old patch in
both arms (and so measured the judges' own drift between two House renders of one patch: up to 0.18 on TuneJury, 0.11 on
SongEval, 0.16 on Audiobox). Played as a player of its own (fmlight2): under the harsh twin the bass's middle came 3 to
4 dB nearer the liked stems, but alone, in a camp, it lost its top (16 dB down at 1.8 kHz, 38 at 3.5 kHz: a dull thud);
TuneJury with the House brief down in all three last drops (0.13 to 0.19) and SongEval leaning down, TuneJury with no
brief and Audiobox leaning up. The judges did not agree, and the camp's bass went dull: off.

*Tried and left off: the own bell given a body* (`club.BELL_BODY`, 2026-11-22). The FM bell designed for House, the
chords in the snowfields' and the haunted palettes, stood 36.6 to 38.0 dB over the liked stems at its top and 5.5 to 13.6
thin in its middle in all ten takes that drew it; its partials at three and a half times the note fall outside the key
(Owl Light I's chords read 64% in it). Given 4 dB at 450 Hz and its top 6 dB down from 4 kHz at the desk: SongEval up in
five windows of six, TuneJury down in four. Kept, off: the bright clang may be part of its House.

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

*Darker music* (2026-11-23: seventeen more, 126; "need some darker stuff"). Every inn and town, six camps of eight and
65 in 100 of the walking music were light. Thirteen dark walking families, at least one for each kind of place, and an inn, a camp, a
night and a town: minor and phrygian loops, the deep and dark palettes, no swing but a trace, each with a key and loop no
other has.

*Where the same songs came round most* (2026-11-23, the standing cycle's first round: ten more, 136). House's storms had been
heard 2.4 times each, its towns 2.1 and its camps 2.0. Four storms (Cannonade, Black Rain, Sandblast, Ice Fang), two towns
(Smog Quarter, Customs Wall), a camp (Dead Radio), a night (Sleepless Shift), an inn (Cellar Door) and a cave (Ossuary), all dark.

*A second of every calm moment* (2026-11-22, night: twenty more, 109; "lots of options of inns camping,
caves dungeons and just a not repetative experienxe"). The inn, the camp, the cave, the night and the
boss had one family for each group of places, three takes, where the walking music had five to eight:
an evening at one inn heard the same three songs. Each group of places now has a second of each, its
key, chord loop, kick and machine none of its sibling's (the family of the same moment for the same
places): inns Low Rafters, Hushed Parlour, Mint Tea and Mended Nets, all light; camps Bedroll Sky,
Ghostfire, Nomad Fire and Ice Fishing; caves Lodestone, Glowworm Hollow, Sandstone Hollow and Frozen
Echoes; nights Dewfall, Whispering Boughs, Desert Nocturne and Black Water; bosses Throne of Ash, The
Usurper and Drowned King; and the green lands a second town, Guildhall Steps. The caves and the bosses
are heavy; a camp or a night is light where its sibling is heavy and heavy where it is light (light
and heavy take turns). Some take a kind's palette for their colour: the desert's oud for Mint Tea and
the tomb under the sand, the coast's harp and the sea for the harbour inn, the snow's bells for the
fishing camp, the deep coast for the black water at night.

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
  *The leads made anew* (2026-11-24: "house still needs to work on that main synth lead sound"; `patches.DESIGNS` "house lead …", `sounds.HOUSE_LEADS`). Measured in the last drops of six songs
  each, the saw and the supersaw, which led 135 of 196 songs, stood within 1 dB of each other in every octave, 22 dB down by 5 to 10 kHz, nine dB under the mix, and as open on a drop's
  first bar as on its last (the writer's brightness is 1 all through a drop). A lead is now a body (two saws and a square through a driven ladder each note throws open), a width
  (saws spread far, nothing under 400 Hz) and a bite (an octave's click for seven hundredths of a second), laid at measured levels (*as first laid, by ear of the numbers alone, the width
  stood 17 dB under the body and the bite 35: a layer's level is set against the first's at one loudness*), or one of seven others: hard sync, two turning pulses, a throat's two formants, struck
  metal, an acid line, a growl, a driven pluck. Each is played with accents (the beat over the eighth over the sixteenth, `club.accented`), harder as the drop goes on, and
  its filter follows how hard it is struck, so that it opens; a mono one slides between notes that are tied. At the desk it is held in three bands (`jsfx/lift`: what is quiet in each
  brought up, what is loud held), with presence at 2.6 kHz and its top open.
  *House's acts* (`club.ACTS`, "and also should use differrent bands"): as Knight Rock's bands, whose instruments a song has: the big lead of its drops, the second synth that joins it, the soft
  lead of its themes, its chords, its bass, its pad and its drum machine. Eleven beside House's own: warehouse (acid), undercroft (the growl), foundry (metal), signal (sync), monolith (the
  ladder), vesper (the voice), velvet (the pulses), strobe (the pluck), chamber (a cello), brass (a trumpet) and bazaar (a sitar). No two have one lead. A family's first
  take is House's own act, its others and every new family's another's (`club.act_of`), given out by the moment: the calm ones to a calm song, the hard ones to a fight. A song's main
  voice, whichever the writer drew, is the act's big lead (`parts_of_the_lead`). The sheet says what plays it, and is played as it says. Two more are of the instruments found that day: cyborg
  (a cello's and a double bass's bows as a synthesiser's oscillators, all of it) and junkyard (a baritone saxophone torn by an amplifier over a jazz bass, driven; its growl, tried first, is the player's voice in the horn, two in five of it in no key).
  *The hard ones* (2026-11-24: heard as sweet still, after the dark families). The House in the player was counted: of 193 songs 76 in major, lydian or mixolydian, 102 light, maracas in 103,
  glass plucks in 74, every one at 110 beats a minute, every one a loop of four chords. Darkness of mood was not it; the writing is. A hard family (palettes "hard", "hard-broken", "hard-slow") is
  118 to 132 beats a minute (`Family.bpm`, `house.at`: the writer's and the desk's beat for as long as one song is written or played), stands on one chord and leans on another (loops H1 to H5: a
  phrygian second, a minor seventh, a fourth, or nothing), its stabs a root and a fifth and no third, low; no maracas, tambourine, chime, snap, bell, glass, harp or whistle anywhere in it, its act's own
  instruments included (what an act's keys are made of was bells until it was looked at); and its tune is a riff hammered on one note (`HAMMERS`, `Tune._hammered`): two bars of one pitch, three or
  four of its strokes the step over it, the step under it or the octave, said again, moved up a third or a fourth, and left out for the last half bar. (*Its first riff was the writer's cell of the
  chord's notes up and down: a trance lead on a hard band.*) Its act drives its drums and its bass at the desk (`Act.drive`: what rings between the strokes brought up under them, hot tape, the bass's
  harmonics), its lead stands 2 dB nearer (3 at first) and its bass 1, and its themes are held under its drops (`HELD_BACK`: 1.2 dB on the drums and the bass, 2.5 on the lead; *Riot Line's drop stood 0.8 dB over its theme,
  its drums and its lead at one level in both, so that the drop brought nothing*; counted then in all 164 staged songs that are not calm, the drop stood 0.4 to 1.4 dB over the theme, under one in 125:
  every other song's themes are held too, `HELD_BACK_SOFTER`, about a decibel). A stab of inharmonic metal reads out of the key (59% in it, at a ratio of 2.76): whole ratios.
  *How a hard song is arranged* (`house.HARD_SCENES`, 17:00 the same day, the first five read block by block by their sheets). They had one skeleton and one texture: the stabs the same bar from the first to the
  last, the groove whole from the theme's first bar, the whole tune given away in the rise before its drop could bring it, and three things of a festival's left in the build: the chords rolling into the drop in
  eighths and sixteenths, the bass's eighths opening on one note, and a third over the riff the second time round. A hard song now has one of four arrangements, taken in turns by a family's takes: *stacked* (the riff from
  the drop's first bar, a layer more every eight), *held* (the groove and its stabs for eight bars, then the riff; never a fight's or a storm's), *answered* (two bars of riff, two of stabs) and *lone* (the riff over drums
  and bass, hardly a stab). The stabs wait in the theme, leave the rise, have a second figure; the bass has a second figure; the middle of a last drop is the floor: the kick, the bass, the toms, hardly a hat and
  no riff, so that the riff comes back. The rise does not give the riff away: its one note hammered and opening, the bass going on under a closed filter, or one chord struck in threes, and then half a bar of
  nothing. The second synth says the riff an octave under or over it, never a third, never on the riff's own synth. No two hard families have the same lengths of everything.
  *A riff is even* (`club.HAMMERED`, `ACCENTS`). Read in the recordings: the strokes off the beat stood 4 to 7 dB under the beat's in every song led by a synth of House's own, which made a pulse on the kick and ghosts between
  it; the two songs led by recordings, which had no accents, were even, and drove. And the desk put what is written under six tenths of the loudest on a track of its own, so that three quarters of Riot Line's riff
  was played by another copy of the synth, 10 dB down, and nothing could slide; that track also struck the riff and its octave together on a synth that has one voice (86 strokes of it; Power Cut's lead came out
  17 cents flat). A lead of House's own plays its soft strokes itself, and only what sounds together with a louder note is a line under it (`club.voices`).
  *Its kick* (`kicks.DESIGNS` "house kick hard …", `club.HARD_KICK`, `sounds.clip`). Read alone through a hard act's drum bus, the kick every House song had was a knock and a sine: 19 dB from its loudness to its peak, its
  body 12 dB down by 170 ms, so that under a band what was left of it was a click. A hard kick is a clipped one: drawn to fall from higher with a longer knock, its 190 Hz and its 1.2 kHz brought up, driven 14
  to 26 dB into a ceiling (`jsfx/clip`), its box taken out after: 2 to 3 dB louder at a lower peak, 12 to 14 dB from loudness to peak, its body held 190 to 350 ms. One for each kind of machine, the
  909's a hammer, the 606's a boom, the 808's round; and each comes to rest on its song's root, or on its fifth where the root is out of a kick's reach (`kicks.rest`).
  *What softened them* (each channel of three songs left out in turn, by `tools/hardness.py --without`). Without its bass a song was 4 to 5 softer: the bass is the hardness, and stands a decibel up. Without its lead Blast
  Furnace was 3 harder and darker in both its parts: its lead was struck metal, two modulated sines, and rings as a bell does (a razor has its place: saws and a narrow pulse clipped hard); the acid line's was none the worse
  for being there. Without its stabs Scrap Yard was 2 harder (the plate's). And a hard act plays close (`club.CLOSE`): a third of the echo every other song's lead and chords have, a progressive record's dotted eighths from
  side to side, and a third of the hall.
  *Which lead is whose* (the same measure, thirteen of House's leads in one drop with everything else the same). Hardest first: sync -5, the anthem -6, the acid line -7, the throat -7, the ladder -9, the stack -9, the driven
  pluck -11, the growl -12, the factory's saw as it was -12.5, the two turning pulses -16.5, struck metal -18. A lead that rings like a bell is the sweetest thing a song can be led by, whatever it is called. Metal and the
  pulses lead no act now; the growl, dull and low, is a soft voice for a theme.
  *A riff is heard stroke by stroke* (`club.strokes_off`, in every song's own checks). An instrument tuned by its long notes may be out of tune on its short ones: the baritone saxophone's strokes from G sharp 3 up
  scoop from 90 to 185 cents under and are over before they arrive. The channel heard as a whole read 12 cents in one of its songs, 63% in the key in another and nothing in the third. Each stroke of the first drop's riff is
  read for itself now, the median for each pitch; of thirty-six songs three were out, all three the saxophone's (its recordings blown hardest are the ones that scoop: at a third of its strength it is in tune). It is kept for long
  notes, and for riffs no higher than G3; the junkyard has the squelch.
  *A dub chord has its third* (`club.THIRDS`, `with_thirds`; on its fifth as well, 2026-11-25: five songs' chords of a fifth, its root and its fifth again had the third of the fifth, 64 to 69% in their keys). A hard song's stabs are a root, a fifth and an octave; behind a band-pass whose peak stands on their overtones they were something else: Sump, in D phrygian, sounded 13 in
  100 of a major second (the fifth's third overtone) and 7 of a major third (the root's fifth), 63% in its key, and Cold Storage 60. The dub's are a dark minor chord, as a dub's are: the octave goes to the third the key has.
  A stab whose filter is open (the rave's, the plate's) has its overtones evenly and needs none.
  *Every act, measured* (the same short song by each, `tools/hardness.py`). The hard ones on hard music: warehouse +9 (an acid line over an acid bass), signal +2, foundry +1, junkyard +0.5, monolith 0, undercroft -1, cyborg -2; before
  their own kick. The soft ones on a dark song: strobe -13, vesper and chamber -16, bazaar -17, velvet and brass -21: as sweet as the sweetest of the old songs, though nothing in what is written is: the instruments are the sweetness.
  They play inns, camps and nights and the light songs, where softness is the place's; a dark walk, a town and a cave are the hard acts' (`club.ACTS_FOR`). (The same night: a dark calm song is four acts' that are not soft, `ACTS_FOR["after"]`: cellar, a smoking
  reed, a contrabass flute and driven tines over a tube; gallows, a foghorn, a baritone saxophone's long notes and plucked celli over a fretless bass; switchyard, a worn tape, a saxophone under its breath and dub
  chords; mortuary, a bow near the bridge, a saxophone's growl and a dry knock over a double bass. On Dead Hours their themes stand at -7 to -9 where the soft acts' do at -13 and -14; a first mortuary, with a bassoon and a
  parlour's piano, stood at -16. Their drive is the drums' and the bass's alone: a calm song's stabs keep their room.) Every act is in tune and its lead over its band.
  *What the first nineteen still do* (read by the meter the same evening). In twelve of them the drums were one groove for sixteen bars, the second half of a theme (Chain Gang's twenty-six): a hard theme's fourth eight bars, and a
  long one's last, have the toms of its drops, softer. An after-hours song's chords and bass never turned (Dead Hours' chords the same 22 bars, its bass one colour for 52): its chords take their second figure and its bass its
  other one at the half of a theme and of a moment. *The squelch*: the acid line's other voice, a square through the same ladder, is the second synth of the foundry and of cyborg.
  *A riff cut up* (`club.cut_up`, `Act.cut`, 2026-11-25: "house is a little better keep iterating"). On the records studied a hard riff's strokes are several machines', each short, one answering another; ours were one synth's
  for a whole drop. Three acts have three voices: two bars at a time, the note that is hammered is one's, the strokes that leave it and the second of two that run together are another's, and the last half bar is answered by
  the third; who is which changes every eight bars (`CUT_ROLES`), and the half bar a riff leaves out at the end of each sixteen is filled by whoever answers, an octave under. No voice sounds through another's stroke; the second
  synth goes with the hammering one alone; the two others stand a little to either side. In a drop only: a theme's hook and a rise's are the first voice's.
  *Five voices of another kind* (`patches.DESIGNS`): the talker (two formants opened by each stroke), the chip (an eight-bit ramp whose bits turn over as it is struck), the scream (a filter resonating on the note's own fourth
  overtone, broken up), the fold (a saw and a square folded over on themselves) and the reese (saws that beat, a notch going through them). Their acts: chopshop, arcade and kennel, cut up; quarry and tunnel, one voice. On one song,
  hard against sweet, drop and theme: tunnel +10 and +6 (the darkest drop of any), arcade +5 and 0, chopshop +5 and +4, kennel +5 and +2, beside warehouse's +9 and +7; not cut up arcade's drop stood at +1, chopshop's at +4 and
  kennel's at +5. (A fold of two sines rang as a bell, -1, and a saw's and a square's stood no higher over an FM bass and a pad: the quarry has the wide bass, the drone and the 808.) Every stroke of every voice is in tune.
  *A riff is not only a hammer* (`house.HOOKS_OF`, `Tune._phrased`, 2026-11-25). Read through, every hard song's riff was one note hammered, two bars of it, three or four of its strokes somewhere else: sixty songs, one
  kind of hook. Six others, each two bars said, said again with its end turned, up a third or a fourth for two, and once more with its last half bar left out: *a line*, a machine's sixteen steps drawn once (ten to
  thirteen of them sounding, the root half of them, an octave, the steps beside it, four slid into the next), two or three of them changed when it comes back, as a player turns the knobs; *a glide*, four to six long
  notes, each slid into the next; *a call*, three or four strokes low down for a bar and a bar's answer over them by the second synth; *a power riff*, a guitarist's, with its holes; *a toll*, a stroke or two to the bar
  with the floor between; *an odd cell*, three, five or seven sixteenths over the four, beginning again every two bars. A riff of few strokes has nothing to hammer a rise with, and has the machine's rise or the stab's.
  A family that has takes keeps the hammer. The second synth of these is the voice that is heard in the drops alone (`club.parts_of_the_lead`, `outside`): counted by notes, what answers and doubles a riff had been
  taken for it in four songs of thirteen.
  *A House story has five shapes* (`house.FORMS_OF`, `Family.form`, 2026-11-25). Three hundred and forty songs had one: an intro, a theme, a build, a drop, a breakdown, a build, a longer drop. Besides those two waves: *thrice*,
  a third wave, the breath between its drops eight bars, its middle drop arranged as the last one begins; *arc*, a theme three times as long, one long rise and one long drop with all of the arrangement in it, nothing that
  falls away before it; *cold*, a storm's: the riff in a drop of eight bars after four, and the theme after that; *tool*, no builds at all: the floor, what it holds, the floor taken away for a phrase and put back. A family that
  has takes keeps its two waves. And six loops more for hard songs: one that turns every bar (i, i, bII, bvii), a lament's fall to its fourth, a sixth leaned on for four bars, the dorian's fourth, the dominant's second over a
  major third, a chord and its fifth.

  *The leads are cast by a judge* (2026-11-25, "use all the different leads have tunejury decide"). Forty-two leads, each in turn the lead of six songs' drops and moments (a hard walk, a town, a storm, a calmer walk,
  a night, a camp): twenty seconds of each mix at one loudness to TuneJury, under House's brief and a hard one, at three fixed crops (its own crop is drawn by chance and moves a score a tenth). Each song is read on
  its own scale: a town's song scores twice a walk's whatever leads it. Two songs agree on the order of the leads only loosely (0.2 to 0.47 between the hard ones, 0.57 to 0.66 between the calm ones): a lead suits a
  kind of song. The jaw is first on none and never under the upper half; then the tape, the metal and the reese. The chip, the sync, the brick and the squelch each win a song and lose another, and stay with the acts
  whose songs they win. The gremlin, the shard, the slide and the chain stand at the foot of every song, the charge and the maw near it: the six acts whose drops they led have a lead from the upper half, and no two
  acts have one lead still (`club.ACTS`; the whole table is var/passes/contest-leads-summary.txt). The meter had said so of two of them before the judge did: the maw and the slide read 73 to 78% in key in four of
  the day's songs. *The twelfth round's fifteen* are cast from it: two desert walks and two regal, two caves, a storm, a town, a battle and a boss, two inns, two nights and a camp, each hard one with a riff and a
  shape of its own (of 95 hard and after-hours families 70 hammered one note and 84 kept two waves).
  *The thirteenth round's ten* (the same evening) are nine hard walks where they were fewest (the desert's four, the jungle's and the mystic's five, the coast's, the haunted's and the infernal's six) and a night, by the acts whose drops the contest's upper half leads (the jaw, the reese, the chip, the metal, the fifths, the growl, the stack, the brick, the talker; the tape for the night), on the 707 and the breaks, which four and six of 110 hard families had. A hard song's lead lies under E4 in the middle (the test's line): a glide in B was a third over it and is in E flat.

  *The fourteenth round's ten* (2026-11-26) are where House's music comes round most a song: a town, a storm and a cave, the coast's, the pastoral, the frozen and the highland walks (hard), a camp, an inn and a night (after hours). The hard ones by acts whose drops the contest's upper half leads (the talker, the jaw, the fifths, the brick, the growl, the reese, the ladder), each with a riff and a shape no song of its act has had: the storm comes in three squalls where the six before it begin cold. A hard song goes at 118 or over (the test's line): the slow ones are at 118 and 119.

  *What the day's first takes said of the players* (the same day). A table lead low in its register sounds its own major third: the sweep read 69% in key on a line written wholly in F minor (Threshing Floor I), an
  octave under the riff on which it read 85; its line is cast higher or the lead darker (owed). The acid bass is all resonance, 9 dB over the liked stems in its middle with less under 200 Hz than over (Loan Shark
  I): a sine goes under it, as under the other basses that are heard more than felt (`club.SUBBED`). And a lead's strokes are measured where they sound alone (`club.strokes_off`, `beside`): Red Rock II's riff
  read 100 cents flat at E5 and was in tune, another note of its channel sounding under half of its strokes there.
  *The heap most strokes are in* (`club.strokes_off`, 2026-11-26). Hollow Stair I's lead, a sync low down, was reported "38 by -122 cents": most of its strokes at that pitch stood within ten cents and the rest near -245, a second row of partials that the harmonic sum took for the note in some strokes, and the median of two heaps is neither of them. For each pitch the meter gives the fullest twenty cents of its strokes (two heaps as full: the one further from the note, so that a fault is not hidden).
  *Leads out of wavetables* (`patches.table`, `waves`, `_scanned`, the same day: "find more instruments!"). Seven hundred tables came with the synthesiser and none had been played; a design names one, and thirty-two of
  its waves, each brought to one loudness with nothing under it, go with the patch. Thirty-six were given one riff in one drop, the rest of the song the same. *The hardest were hardly notes*: gone all the way through by
  every stroke, a torn saxophone's table stood at +10.9 with 54% of what it sounds in the key, dragged chains +10.2 with 61%, a scraped brick +9.3 with 60%; the acid line is +11.0 with 72%, and seven notes of twelve by
  chance are 58%. Measure both. A sixth of the way through, over more of a pulse an octave under, they are notes again: a throat +10.2 and 68%, a broken glass +9.4 and 76%, chains, a formant +8.2 and 68%, a brick +8.1 and
  67%, a swept filter +8.0 and 73%, and as they were a croak +8.6 and 73%, a mouth +8.9 and 68%. Five growls drawn for a bass were the sweetest of all (+4.4 to +5.4), and two tables are not in tune in themselves. Ten acts
  are led by them (drydock, smelter, brickyard, catacomb, icehouse, faultline, powerhouse, sluice, pressroom, millrace, whose wobble goes to and fro with the beat for a glide to be held through), no two with the same stabs,
  bass and second synth; two calm ones (flophouse, a hummed "ah" with a tenor saxophone, an upright piano and an upright bass; pumphouse, a trombone that buzzes with a contrabassoon and a fuzzed electric piano); three
  stabs, three basses and a pad beside them.
  *A played bass is left open* (`club.lines`, the same day): a calm act's fretless was 6 and 13 dB thin in its middle in two songs (Cold Ashes, Bad Debt): the desk shut it at 1.8 kHz as it shuts a synthesiser's. A bass
  that is a player's is shut from 4.5 kHz, with 4 dB at 650 Hz, and held four to one: an upright's plucked notes ring into one another where they come quickly, and Cinder Block's rise stood 7 dB over its moment.
  *A stroke has a pitch.* A hard-synced lead swept 22 half-steps over half a second read 19 cents flat in two songs: in a riff's short stroke there is nothing but sweep, overtones sliding at 3.97 and 4.42 times the
  note. Swept six, from a little higher, its long notes are in tune and its short ones within 5 cents.
  *How hard it sounds, measured* (`tools/hardness.py`). The judges' model that hears audio against words (LAION-CLAP, music) scores ten seconds of a drop or a theme against three pairs of descriptions
  (hard against soft, dark against sweet, raw against cheesy), the one side less the other, the same windows always. It hears what was complained of: the sweet songs stand at -9 to -18 and the hard ones' drops at
  +1 to +11. Their themes stand at -5 to +1: a theme is where the hardness is owed.
  *The other dark ones* (`house.GRIM`, the same day): a dark palette's percussion was a light one's still (chimes in the haunted, shakers in the caves, a cowbell in the infernal, finger snaps in an inn), and
  some acts were sweet in what they are for (strobe's glass, vesper's whistle and harp, bazaar's kalimba). The twenty dark families with no take have nothing sweet struck (`house.SWEET`), and those acts
  have a pluck, a bass clarinet and a dulcimer alone in their places. Families that were made keep theirs.
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

A render that waits is a REAPER with a message open, and nobody to answer it. It is stopped at its time
limit (300 s and twelve for every second of music), its window pictured beside the project
(`reaper-waiting.png`); and since 2026-11-23 it is stopped sooner if it writes nothing for fifteen
minutes (`desk.RENDER_STALL`), and tried once more (`reaper.Stalled`): that night one met "Can't write
to REAPER configuration file" at its start, three renders having begun together, and held one of the
night's three places for its whole limit, 6,121 s.

**An opening is heard** (`build.opened`, 2026-11-24). Every song of the day's seven studied opened at -37 to -41 LUFS; counted then, 169 of Warcraft's 521 stood under -36 (Knight Rock's 16 of 425), which a
game's own sounds cover: the first minute of such a song is silence. The writer's `opens` plays the newest characters' louder; the desk now brings any opening to within 16 dB of its song's loudest
part, by 9 dB at most, and never over the theme it leads to (13 dB and 12 from the same evening: at 16 the day's thirty songs opened at -33 to -36 still). `tools/open_up.py` gives the same ride to songs already made.
Its first theme is heard too (`FIRST_UNDER`, 2026-11-25), and **so is what comes between it and a song's first arrival** (`EARLY_UNDER`, the same night): five of nine parts of Forlorn Hope, a slow burn, stood at -37 to -31 under
a moment of -22 and a summit of -19, four minutes under a game's own sounds. Each part after the first theme and before the first that comes within 8 dB of the loudest is brought half way to 10 under it, so a burn still burns, each part
under the one after it. A song that arrives with its first theme or its second has nothing between.
**A valley may be quiet and not gone** (`LOW_UNDER`, the same night): of the library's valleys 188 of Knight Rock's 453 and 190 of Warcraft's 593 stood 16 dB or more under their song's loudest part, some at -37 to -41 LUFS: a tune
sung alone for a minute under a game's own sounds. What stands more than 15 dB under, after the first arrival and before the close, is brought half way back to that: a decibel or two for most, three for the furthest.
**In a soft song an opening and a first theme have a floor of their own** (`OPEN_FLOOR`, `FIRST_FLOOR`: -32 and -30 LUFS, the same evening): fifteen of the day's first takes opened at -33 to -36, each as far under its summit as the rules say, and the summit of a cave's or a camp's song itself at -22 (Daylight-Starved Echo, Prospector's Stake). They are brought up to the floor within the same limits: never over the part after them. A valley has one too (`LOW_FLOOR`, -35, and `LOW_MOST`, 8 dB in all): half way back to fifteen under a summit that is itself at -21 left Pomander Rounds' and Tally-Clerk's Ledger's valleys at -37. An opening is brought up by fifteen at the most (`OPEN_MOST`; twelve until 2026-11-26: eight old songs, performed again from revised sheets, opened at -33.5 to -34.9 under first themes of -25 to -30, written 51 LUFS down, a lone player as softly as it can, and held there by the twelve).

**A drop stands over its theme** (`club.HELD_BACK`, `HELD_BACK_SOFTER`, the same day): House's in 5.7.
**A calm song's rise stands under its moment** (`club.CALM_RISE_UNDER`, 2026-11-25). The render's own check had said so of Cool of the Evening II on 2026-11-20 and said it of Night Bus I, the mortuary's night: its rises at -12.8 LUFS over moments of -13.8, the bass and the stabs 2.6 and 3 dB hotter in the rise than anywhere in the moment, with no kick to give way under. The build's eighths played half as loud (`house.CALM_BUILD_SOFT`) had cost the rise its lift by the judges and stays off: the notes are as written, and where a rise stands less than 0.7 dB under its moment the bass, the chords and the lead are held through it by what it is over, 4 dB at the most, eased over a bar; a rise that is under already is not touched. What was held is in the take's measurements ("calm rise held").

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
from its music sheet, how many lines play in each part, the spread of their pitches and how much of the
tune is a bar heard before; against the liked stems of its style and channel, how far its middle
(160 Hz to 1.25 kHz) and top (2.5 to 10 kHz) are off. Then the set's averages.

From 2026-11-26 it also says how much of the tune comes back: the share of the lead's two-bar phrases that are played more than once, with the liked library's lower quartile beside it
(`study.RETURNS_FLOOR`: 44% for Knight Rock, 27 for Warcraft; none yet for House, whose hooks come back in 92%), and "UNDER" where a song lies below it. "Tune bars heard before" is still printed, and is
not a fault at any height: until that day a song was marked at 55% and over, and nothing was marked for a tune that never came back. A channel that has no liked stems to be held against is named, where
it was passed over without a word.

*That count was blind, 2026-11-27.* A phrase counted as come back only when every lead voice together played it again note for note at the same pitch, so a tune told
again on other voices, beside another line, or lifted to another key was a tune that never returned. Drowned Ruins read 10%, "stated, then abandoned", and was marked for a
revision; read by ear on paper before the revision was written, its choir sings the English horn's theme note for note at the arrival while the violins play the cello's
answer two octaves over it, the cello plays its answer again in the valley, and the summit is all of it a minor third up — and the judges give it memorability 3.01 where
Warcraft's bar is 2.65. Round fifteen's two tune revisions were read the same way afterwards: Bedrock Delve's fault was real, and Merchant's Shuffle's fiddle had already
played its theme again at the arrival, which the reading of its lead guitar alone missed. So study.py now says first **the tune heard again**: the share of the tune's
two-bar spans in which some lead voice plays a phrase whose shape (where its notes fall, and each one's distance from its first) is played in another span by any lead
voice at any pitch; the same phrase in two voices at once is no return, and a phrase of fewer than three notes is left out. Over the gate's library (121 Knight Rock songs,
63 Warcraft) and the songs the retelling rule made (66 and 91), with a quarter of the liked under the floor either way, the old count caught 56 of the 66 retold Knight
Rock songs and 35 of the 91 Warcraft, the new one 63 and all 91: it hears a tune told another way each time at least as well, and does not take a tune re-voiced for one
that never came back. "UNDER" is said of it (`study.HEARD_FLOOR`: 68% for Knight Rock, the middle 72; 83 for Warcraft, the middle 88; none for House); the old count is
printed beside it as "played again note for note", with its own quartile, and marks nothing. Under the floor is a reason to look, not a fault: Drowned Ruins reads 76 by it,
because its second theme and its two rises are each heard once, and it stays as it is. Before a revision is written for a tune, its lead is read voice by voice against
the first telling, at any pitch, and the judges' memorability is looked at.

*And it predicts nothing of the judges' memorability, the same night.* Over every take SongEval has read whose sheet is staged (231 Knight Rock, 268 Warcraft), the
tune heard again goes with memorability by r = +0.07 and +0.04, and the middle memorability under the floor and over it is 3.06 against 3.10, and 2.92 against 2.94.
Among fifty-three Warcraft songs of the first weeks studied that evening, the twelve the judges had read under the floor read *higher* (3.17 in the middle) than the
twenty-nine over it (2.98); Moonlit Hour, at 74, reads 3.73. Split by the characters' `light` the liked library's quartiles are alike, so it is not the calm songs. So
the count does one thing: it tells a tune told another way each time, the fault it was built against. A song is not revised for its tune on the count alone; a tune
revision waits for the judges' memorability to be under the bar as well, and a song they have never read is read first.

The sheet read is the staged one, each note at the nearest twelfth of a beat (where the player put it), and what the desk
stacks on a moment (a kick, a sub, a bell) is not counted as one more playing. Until 2026-11-25 the writer was asked
again, which is the first draft: Keg Clamour, retold the night before to 51% of its tune's bars heard before, was read
at 69 and marked for the revision it had had. A take staged before the sheets were is still written again.

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

The meter is a pointer, never a gate and never a target (2026-11-26, the audit). It compares each bar with the first bar of its run, so it has
no notion of a phrase that comes back: a riff held through a verse reads as a fault, and so does a tune told the same way twice. With the study's
old reading of "tune bars heard before" it pushed three nights of writing towards something new in every bar, and the songs that came of it were
heard as random (4.12). A flag is followed only where the same take, changed, reads no worse with the judges against the take before it; and no
flag of the meter's keeps a song out of the player or lets one in: that is the gate's (8.9).

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
`nice` on the efficient processors only, the whole machine under a quarter by day and more by night ("i think were still using too much
CPU usage ... we want it under 25 percent", 2026-11-23), and nothing is killed to make room ("dont hard stop any renders or
tasks 9am is not a hard stop"). Never rewrite an instrument's SFZ file while a render runs: sfizz loads it again and the
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

The server keeps each bucket's list in memory and writes it back as it plays, so the bucket that plays is
written only while the server is stopped. A whole build does not touch it: the new bucket is made beside
it with the server running, and takes its place in the seconds the server is stopped for. (Until
2026-11-23 the server was down for the whole build, half an hour to two hours for a band's or the
orchestra's bucket, and a player that cannot reach it for a minute fades out.)

1. Build beside: `uv run --no-sync python ../tools/fresh_bucket.py <style> --beside`. Every staged track goes in.
   A song cut from the recordings that are staged now is taken from the bucket as it stands (its parts are
   linked, not read and written again); the rest are cut. The bucket is in `buckets-next`, next to
   `buckets`, on the same drive.
2. Read the last lines: `tracks put in; the bucket now has ...`, how many were taken as they were, and any
   `NOT put in`. A build that fails leaves the one that plays as it is.
3. Check the game is off: `curl -s http://127.0.0.1:8765/api/snapshot`; `seconds_since_read` under
   120 means it is being played.
4. Stop the server by the PID that listens on the port: `ss -ltnpH "sport = :8765"`, read its command line,
   then `kill <pid>` and wait until `kill -0 <pid>` fails. Never `pkill -f`: the pattern matches the shell
   that types it.
5. Swap: `fresh_bucket.py <style> --swap`. The bucket as it was is kept in `buckets-before` until the next build:
   a page goes on playing a song it had begun from there, and `--swap-back` puts it back.
6. Start the server again, detached, and write the pages (`tools/listen.py <style>`, `tools/now_page.py`).

A song is told by the same ids from build to build for as long as its recordings do not change: the id of a
piece and of each part is made from the track, the place and the recordings' own checksums
(`studio.stamp_of`, `forever.identity`). A page left open across a build goes on with its song; one that was
made again goes on by its track and place. `fresh_bucket.py <style>` without `--beside` builds in place, with
the server stopped (a style with no bucket yet is begun so, with `--zone`). `freerock pieces add
<style>` only adds tracks not in yet: a re-rendered take keeps its old pieces unless its source is dropped
first (`freerock pieces drop <style> <style>/<family>/<take>`).

On the music machine `var/passes/rebuild.sh <style>` does all of this; it lives outside git.

### 8.7 Add a character or a family

**What the audit of 2026-11-26 changed for a new song** (4.12, 8.9; "the new bands a lot of time just sound random, it got worse not better"). It is in 4/4 (6/8 or 12/8 for a shuffle or a jig; a Warcraft song
in 4/4, 6/8 or 3/4), never in 5/4 or 7/8. Its theme comes back as it was first told (no `grows`). It rests when it is staged and comes into the player only through the gate. Dark and gritty still, by
its key, its harmony and its sounds. Three readings of the audit's that are not tested yet, each to be tried on a pair of takes before it is a rule: a tune sung an octave down (`low`) lies inside what
accompanies it (the companies' leads at a mean of 61 where their accompaniment is at 68, the orchestra's at 71); a guitarist's riff handed to a marimba, a harpsichord or a line of trombones is not that
instrument's music; and a band is known by its own two singers song after song, where each new character has named an odd lead of its own (48 lead instruments over 137 band songs, none in more than a
quarter of them; the house band's lead guitar is in 70 of 100).


**New music is darker, gritty, and varied in its instruments** ("just new music should be darker", "make them gritty and darker",
"make sure to switch up the instruments from song to song so theres variety", 2026-11-23). A new character or family is heavy, in
minor, dorian or phrygian, with the deep sounds, unless its place or moment has no light music left; what is already made stays as
it is. It leads and strums with instruments its neighbours do not: 71 of 100 Knight Rock songs had a lead guitar, 70 a rhythm
guitar and 69 a rock organ, and two thirds of House's leads were one of two synths. A band's lead that stays in its range in every
key is the fiddle, the whistle, the mandolin, the steel guitar (and the lead guitar in most). The harmonica is wanted ("i better
hear harmonica and banjo", "Look up John Popper") and stays in its solos, its pads and the light songs that lead with it; as the
tune of the eight dark band characters it started a last note at the very end of the song or left its range in every key, so it
does not lead those until the writer's harmonica tune is mended (owed), nor does the accordion in slow ones. Songs go where they
are heard most often per song (`tools/cycle.py gaps`).

*Dark in sound, not only in key* (2026-11-23, evening, `how_dark.py` in the round's notes). The first round's six Knight Rock songs are
all in minor, dorian or phrygian (58 in 100 of 24 sampled before them were), and the ear hears nothing darker: the brightness of
the whole mix stands at 2,080 Hz against 2,051, the top over 4 kHz at −22.5 dB against −23.1, and the middle only a little denser.
Their tunes are sung at a fiddle's, a whistle's and a mandolin's height, over the same cymbals. So a dark character is led *low*
(the cello, the trombone, the bass clarinet, the horns, the viola, the euphonium), and nothing sparkles over its summit: an
orchestra's summit doubles its tune an octave up with a piccolo or a glockenspiel, and `Character.dark` leaves it out.
Twelve characters of the second round are written so, and the desk's tone for them is a separate, owed question (`how_dark.py`
measures it): the bass driven, the guitars' top eased.

*A light band's tune needs a voice with a body* (2026-11-23, evening, the first round's studies). A song for a few players (weight up to
0.6) led by a whistle or a fiddle reads 10 dB thin in its middle and more against the liked stems, its top level or over (Sewer Alley 9.9,
Hard Coin Song 11.1, Last Lament 13.6, over strings or an accordion's pads); a steel guitar (Dead Fire Watch +1.0, Cutthroat
Round +1.8) or a mandolin (Ashen Street −2.4) stands where the liked leads do, and a fiddle over a heavy band does too (Wreck Gale
+0.3). Its bass reads thin with an acoustic bass (−10.8) and a picked one (−5.5), and not with a fretless (−0.9 to +0.9). So a light
band character leads with the steel guitar, the mandolin or a low string (the viola, the cello), not with a whistle or a fiddle alone,
and its bass is the fretless. The two that failed stay as they are; round three has new ones in their places.

*The third round's twenty* (2026-11-23, night): the towns, the inns, the camps and the storms, where the same songs come round most (Knight
Rock's towns 3.1 times a song, its storms 2.8, its inns 2.5, its camps 2.2; Warcraft's towns 1.9, from ten songs). Of 383 Knight Rock
songs the lead guitar leads 250; these are led by the clarinet low, the english horn, the church organ, the viola, the bass clarinet, the
trombone, the cello, the bass flute and the horns, over four drum patterns of their own (`swamp stomp`, `train`, `gallows march`, `black
toms`) and, in six of them, the riff that is a line (4.2); Warcraft's by the low winds and brass, in three towns, two camps, two
inns and the walks with the least dark music. Seventy families, none before them changed (a hash of every note of 163 of them).

*The fourth round's ten* (the same night; Knight Rock only). Its nights had two characters behind them all, its caves three, the coast, the desert and the
mystic lands one heavy walk each, the marsh two: what comes round there is one sound in other keys. Three nights (a baritone saxophone's, a cello's, the horns'), three
caves (the bassoon, the english horn, the trombone) and four walks (a mandolin's on the coast, a viola's in the desert, a bass flute's in the mystic lands, a
clarinet's in the marsh), forty families, none before them changed, each in a band of its own (4.11).

*A band character names its band* (the same night). `Character.sounds`, a key of `BANDS`, and not the one its neighbours have: a place's
characters, and the two a song can follow in the rotation, are heard one after the other. It names a form and a metre of its own as well where its neighbours
have them (4.12).

*Sung low, not only led low* (the same night). Where the tunes of the library stand, the middle of every song's lead notes, solos aside
(395 Knight Rock and 372 Warcraft sheets): Knight Rock's heavy songs C5, its light ones F♯5, Warcraft's light ones F♯5, its heavy ones B4. The
third round's first writing named the clarinet, the viola and the bass flute and sang them at A5, D5 and D5, their tops: an instrument's `home`
is where its key note is put, and a tune climbs a fifth to an octave over its key note. A character that is `low` has whoever sings with
the middle of their notes at A4 or over (`LOW_TOP`) an octave down, where all but a few of the notes can be: the clarinet to A4, the viola
and the bass flute to D4, a fiddle at the moment from D6 to D5 (`Take.sing_low`; solos and the wired guitars stay). All twenty are.

*A bass line is bowed* (the same night). In the first round's dark towns the contrabassoon carried the bass line alone (a character's
`basses` take turns, and a contrabassoon has no one to double it): 4 to 6 dB over the liked stems in the bass's middle in five songs of the
ten, all reed and little floor. Of the 32 heavy Warcraft songs judged, the basses' lines and the celli's read 6.94 and 6.98 for
enjoyment and 2.94 and 3.09 for musicality, the tuba's 6.65 and 2.62, the bassoon's 6.40. From the third round on the line is the basses' or
the celli's, and the contrabassoon and the tuba double it at the moments, as they did. Five of the first round's songs have their line given to the
basses in their sheets, to be judged beside what they were.

*What is bright and what is thin* (the same night: the studies of 399 Knight Rock songs, each channel by who has most of it, in dB against the liked stems,
its middle and its top). Pads: the accordion's top stands 20 over, the strings' 16, the organ's 13, the pipe drone's 9, the choir's and the oohs' 5
(the harmonica's 33); all their middles 7 or 8 over. Leads: the whistle's middle 12.5 thin, the accordion's 9, the harmonica's 4.5, the fiddle's 2.5 and
its top 11 over; the lead guitar's middle level and its top 8 over, the mandolin's 2 thin and 5 over. Strummed: the rhythm guitars' top 7 over, the twelve
string's 4, the banjo's 5, the steel guitar's level, the clean guitar's 2 under. The picked bass is 3 thin in its middle. So a dark band song has the choir,
the oohs or the pipe drone for its pad and not the accordion or the strings, the steel or the clean guitar where it is soft, and a lead with a body; the
third and the fourth rounds' do. The guitars' and the leads' tops are the desk's to ease (the dark desk, owed).
House, 193 songs: the saw's and the supersaw's leads (134 of them) stand 14 over at the top, the sine's and the electric piano's 2 to 5 under; its
keys' tops 37 (the bell), 27 (the glass), 22 (the pluck) and 15 (the stab) over, the harp's, the piano's, the marimba's and the electric piano's level or under;
its pads 14 to 21 over, the strings most; its hats are the mix's own top all the same (6.1 kHz). Warcraft, 372 songs: the oohs' pad is 9 under at the top, the
strings' 2 over, the organ's 7; the choir's lead 6 under, the trombone's 3, the violins' 3 over, the accordion's 6; plucked, the vibes 10 under, the celesta 5,
the glockenspiel 10 over, the mandolin and the banjo 8; its bass lines are thin in their middles when plucked or fretless (the fretless 11, the basses plucked
6.5, the acoustic 5, the celli plucked 3) and level when bowed.

*Heard from the first bar* (the same night). Nine of Warcraft's twenty songs of the first round, ten new and ten old, opened at −36 to −43 LUFS
(Gutted Parish −39, Ramparts City −37, Iron Bridge −36, Gatehouse Square −38), where the others open at −28 to −34 and a town or an inn is
heard over. A character that `opens` plays its opening louder by 0.13 to 0.11 of full strength and its valley by 0.07 (`OPENS`), and nothing else:
the third round's Warcraft characters do, all ten. Five old songs have the same done to their sheets, to be judged beside what they were. Where the parts
stand in 770 studied songs (LUFS, the middle of each kind; the summit is at -17 to -21 everywhere): Warcraft's walks open at -39 (heavy) and -35 (light),
its towns at -35, its inns, camps, nights and caves at -30 to -34; Knight Rock's heavy walks open at -27 and fall to -37 in the valley, its
light ones at -32 and -34, its inns, camps and nights at -28 to -32; its fights and storms at -24, their valleys at -22 and their swing 5 dB, where Warcraft's are at
-28 and swing 11. The second round's first light walk (Bramble Wood, a viola over a twelve-string) opened at -42: a walk for a few players opens
on one plucked instrument at a quarter of its strength, and needs the same.

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

**Instruments that come with a program** (2026-11-24, "find more instruments!"; `studio/programs.py`). A library that is more than a folder of notes (a saxophone with five ways of playing, a lyre that rings
until it is damped, an erhu that slides) is played by its own SFZ program in the same sampler. What is set down for it: its program, which family it is on the desk with, the notes it has as they sound, how far
its keys are from them, the cents it is out, what its controllers start at, its keyswitch, and the program for a line of single notes. The studio's lines are written into a copy beside it, never into it; controller 1 is
the dynamics of nearly all of them, as it is the desk's. To add one: clone it into a folder of its own under `samples/found` with its licence; check that its recordings are whole (a repository whose attributes
rewrite line endings breaks every one of them, and a broken recording plays as noise: the black and green guitars'); play every key alone and read where it sounds and how far out
(`desk.project` puts a second before the first note, so a reading that forgets it reads the note before: every third semitone out); then a ladder through its range by the written name, its levels
(`sounds.levels`), and the same music by its band. Left alone: what will not be brought into tune (a bass voice, two notes a third of a semitone out), and shouted vocals (the music is instrumental).
A library's single notes are often the better way (guitars for an amplifier of the studio's own): cut to begin at their stroke (some have a tenth of a second before it), named "a3_f_rr2", and
read by `samples.pitched`, which tunes each one. A kit of many microphones is mixed first, as a mixer would (close, overheads, room), softest to hardest (`kit metal`).

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
octave, a bass that moves, and every channel worth hearing alone. (Until 2026-11-26 this list had "a tune that does not repeat its bars" in it. It was read as
"the less of a tune comes back the better", a rule was written to make it so (4.12, turned down), and the songs it made were heard as random. A tune is meant to come back: the study
holds it to the liked library from below.)

**Nothing new is in the player until it has been held to the liked library** (2026-11-26; `tools/heard.py`, `tools/rest.py`, `tools/windows.py`, `tools/gate.py`). A song never heard comes first in
the player ("the idea is to hear new music all the time"), so whatever was made in the night is the next evening: on 11-25, 64 of the 79 songs heard were heard for the first time and 49 had come in
that morning, none of them judged. So:

1. A new song is rested when it is staged (`rest.py`: a line in `var/studio/<style>/resting.txt`; the bucket's builder leaves it out, the listening pages keep it). `var/passes/rebuild.sh`
   does it before every build (`rest.py new`): every staged take the bucket does not have rests, a new family's and a further take of an older family alike, since a further take is written and
   mixed as the writer and the desk are that night, days on from the take that is liked. There is no exception.
2. Its two windows are cut (`windows.py`: the first theme's last 32 bars, the last moment's first 32) and given to the judges under the round's label. A window takes them four minutes, a whole song twenty:
   a night makes no more new songs than its judges can read, about sixty.
3. `gate.py check <label>` holds each song to the same windows of older, liked songs (the label `library`): it passes when the mean of SongEval's five and its Memorability are each at or over the
   library's lower quartile for its style. A song is never read against the others of its round, nor a window against whole songs.
   The quick way, and the one the library is ready for: SongEval reads a whole take by its two minutes from the first theme on, and the judges' watch read 261 whole takes of the library so until
   2026-11-23 (the label `watch`). `gate.py read <label> <style> --tag <tag>` has the resting songs of a tag read the same way, by SongEval alone (`judges.py --only songeval`: a minute or two a song,
   where the three judges take twenty over one), and `check` holds them to those 261. SongEval does not hear whether a tune comes back four minutes on: that is the sheet's to say (7.3).
4. What passes is brought back (`rest.py back <style> --tag <tag> $(gate.py check <label> --passed)`) and comes in with the next build; what does not is written again, or stays out.
   A song is brought back, and given to the judges, by its tag: one that is to stay out whatever they say rests under a word of its own (`rest.py tag`: the takes told another way each
   time rest under `retold-1126`, and one of them moves back to the tag that is read once it has been written again, `--since`). And a reading counts for the take as it is staged: one made
   before the take was performed again is left out by `check`, and `read` has the take read again (`gate.performed_since`: a take's `track.json` is the last thing a performance writes).
   Whose a song is, its sheet says (`gate.whose`): the morning brings back the house's own players' songs that passed (`gate.py check <label> --style <style> --passed --own`); a band's, a
   company's or an act's that passed (`--bands`) does not come in on the judges' word alone. `tools/gate_page.py <label> ...` writes the page the listener hears them on
   (`var/listen/gate.html`: band by band, each to play, the take of before beside a song that was written again, and the held ones by name), and they say which may come in.
   The page is of EVERY gate label the log has, whatever labels it is given, a song counting by its newest reading (2026-11-28: the day's gate copy and the night's
   each wrote it of their own labels only, one over the other, and what waited for the listener went from 82 songs to 57 and back; of all of them it is 111; `--only` for
   the labels given alone).
   What they let in is written down (`studio/<style>/admitted.txt`, by `rest.py back`): `gate.py` and the page say so (`gate.let_in`), and it is not put to them again. A song
   that is in the player and should not be is rested by name (`rest.py these`) and leaves at the next build: on 2026-11-26 fifteen further takes of older families, made the
   night before, had come in with the morning's builds unread, an hour before every take the player did not have was rested; a song never heard comes first.
5. Each morning `heard.py` says what was played the evening before, how much of it for the first time and how much of it new, before anything is said about the night's music.

The library's windows are few still (five Knight Rock songs, six Warcraft, none of House's: `gate.py library` says "THIN"): two windows of twenty-four liked songs in each style are owed, the most
played first (`gate.py pick <style>`), under the label `library`, before a song is read by its windows. Its whole takes are many: 130, 62 and 69.

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
| A theme told another way each time it comes back (`Character.grows`), for every new family; songs in 5/4 and 7/8 for a third of a style's new ones; every night's new songs into the player unjudged, read only against their own round | "most of the music we heard last night sucked, the new bands a lot of time just sound random, it got worse not better" (2026-11-26); *the judges had read the new Knight Rock songs 0.45 under the same windows of older ones, and three in four of them had less of their tune come back than nine in ten of the liked* | Themes told as they were first told (4.12); 4/4, 6/8 and 3/4; a new song rested until it passes the gate against the liked library (8.9); what came in after the evening of 11-24 rested (276 songs, tag `audit-1126`) |
| Reading "does the theme come back as it was first told?" from the parts the sheet calls `theme` | 2026-11-27, the night's 26 new Knight songs, and the test wrong twice in one hour. First a whole-row compare called all twelve staged by 02:20 a different tune: a theme's last return is written short — the first eight bars verbatim, then a four-bar tag home (`1 1 7 7 6 6 5+ 1 ‖ 6 6 5+ 1` against the 16-bar first telling). Narrowed to the shorter of the two, it then called three songs faults outright, Pitch-Black Surge, Iron Drum and Hayride Jamboree: *the tune never comes back*. Their charts say otherwise — they are A B A B A, and the A returns stand under `moment` while the second tune stands under `theme`. Measured over all 26 ignoring the labels: **every one restates its first tune two or three times, holding 21 to 42% of its bars, 29% on average**, and none fails | Test the phrase against **every part after the first telling, whatever the sheet calls it**. The story word is a hint for a reader, never a selector and never a test: a bucket's pieces are chained by `next` in the written order (`forever.py` 335), so what a listener hears is the order, not the labels |
| Reading House's `rise` as a fault because it is quieter than the theme before it | 2026-11-27 04:20, round fifteen's ten old House songs: **in all ten** the rise reads 0 to 3 dB UNDER the theme it follows (Seaspray II −2, The Deep Road I −3, By the Fire III −3). It is how club music is written — the kick and the bass come out for the build so that the drop lands — and it does land, by 1 to 2 dB into the moment, in nine of the ten. Nor is House's small story swing a fault: the three flattest (Heat Haze II 4.6 dB, Last Candle I 6.0, By the Fire III 6.2) are exactly the three marked calm, where staying calm is the design, and the seven that are not calm run 6.7 to 13.2 | Read a House rise as a strip-back, and judge it by what the moment AFTER it gains. The one that failed that test was Seaspray II, whose moment reads no louder than its theme: marked revise. Judge a calm piece's swing against calm pieces |
| Taking the render's *"the texture is only N% in the key"* on House's new acts for the known occasional | 2026-11-27 05:30, the 21 new acts' audition: **6 of the first 15 tripped it** (chopshop, drydock, foundry, kennel, powerhouse, quarry, at 62 to 65%), where the whole library's history before tonight held ten such warnings in all. Measured against the liked library rather than against the threshold: twelve liked House songs' textures read **0.77 to 0.95, median 0.876**, so the check's 0.65 is not a tight threshold — it is far under what House normally does, and those six acts really do have a texture near the noise floor (flat chroma over a seven-note scale is 0.583). Five of the six carry `house pad drone`; the three other drone acts (faultline, smelter, tunnel) came out clean, so the pad alone is not it. The one liked song that also reads low is **storm-01/1, Rain on the Roofs, at 0.578** — and that is the very song the audition is built on | Read this warning against the liked library's median, not the threshold. The six acts go to the judges at 08:30 under `acts-1126` and that reading says whether it is heard; do not change the check, which is doing its job. Rain on the Roofs' own texture at the noise floor is a separate thing, noted and not yet chased |
| Reading *"too much of the same instrument sounds"* (11-23) as a fault in the new Knight songs' bed | 2026-11-27 05:55, tonight's 26 new Knight songs counted sound by sound and set beside the 432 the player has. The bed does repeat — picked bass in 85% of them, rhythm guitar 69%, a rock organ 69%, the kit in every one — but **the liked library repeats it harder**: picked bass 93%, rhythm guitar 72%, rock organ 80%, the kit 100%. And the lead is wider tonight than it has ever been: 42 distinct leads over 26 songs where the library has 52 over 432, the commonest in 58% against 69% | Nothing tonight made this worse, so there is nothing to mend in the writer. If the sameness is still heard, it is **the recipe of Knight Rock itself** — four sounds under every song by design — and changing that is Sky's call about the style, asked in the morning report of 27 November, not a fault to be fixed quietly |
| **Knight Rock's calm songs are the weak group** (11-26: the new bands' calm ones read 2.86 over 21 where the house band's liked calm ones read 3.14 over 39) | 2026-11-27 07:20, the night's 26 new Knight songs, 14 of them read: split on the house's own `light` flag, **the light ones passed 6 of 6** at 3.17 to 3.47, and the ones that are not light passed 3 of 8. All 26 read by 07:42: **14 passed, 54 in 100, where a band on one of the house band's own characters was passing 40.** (Counted as the gate counts: a song passes on BOTH the judges' mean and its memorability. Counted on the mean alone it reads 15 and 58, which is what this row first said -- Iron Drum makes the mean exactly at 3.08 and misses memorability at 2.97 against 3.01.) On `weight`, which is the axis that divides them: **0.70 and under, 11 of 14 (79 in 100); 0.85 and over, 3 of 12 (25).** Five of the eleven held sit within a hundredth of the bar (3.07 three times, 3.06, 3.04), which is inside the move between two renders of one patch, so only six are clearly held: Gilded Rot Hall 2.67, Mountain Stomp 2.70, Storm Rider 2.83, Royal March 2.96, Hollow Deeps 2.96, Chained Row 2.99 — every one of them weight 0.85 or over. By band, the saloon took 4 of 4, baroque, cellos and tweed 1 of 1; twang 2 of 5, doom 0 of 2, shanty and stoner 0 of 1 | Turned over: it is **the heavy songs** that read badly, not the calm ones. Use `weight`, not the `light` flag — songs that are not light but carry a low weight (Sorrow Lament 0.4, Dented Oath 0.5) passed with the light ones. **And wait for the whole set before writing a row like this one**: it was written at 14 read (100 against 33), revised at 18, and moved again at 24 to 79 against 40 before settling here. The next round's question is what a heavy song does that a light one does not; loudness is where to look first |
| **An old song's revision of its form is kept when the judges agree it is better** (docs/plan.md, the standing cycle's old songs: "kept only if the numbers and judges agree") | 2026-11-28 05:40, round fifteen's four revisions, each performed beside its take of before and read under `revise-1127`: Candlewick Vigil made to travel (its opening and valley softer, its moments louder) +0.03 mean, +0.01 memorability; Merchant's Shuffle's theme told again at its arrival +0.00, +0.01; Bedrock Delve's theme told again in its valley +0.00, +0.00; Seaspray II's drop landed (what surrounds it lowered) +0.01, +0.02 — all four inside what a second performance moves alone. **The judges do not hear a song's form**: where its tune comes back, how far its story travels, how its drop lands. So a revision of that kind can never pass that test, whatever it does for a listener | Every take of before put back (`revise.py --back`); the revised takes kept in `var/studio-demo/revised-1127` for an ear. An old song's revision changes what is heard — its register, its instruments, its mix — or it waits for Sky's ear; Black-Sail Queen's travel revision was not written |
| **Knight Rock's heavy songs fail for being heavy** (11-27: on `weight`, 0.70 and under passed 11 of 14, 0.85 and over 3 of 12; the night of 27-28 the same, 5 of 7 and 0 of 3) | 2026-11-28 00:28, on paper over every take the judges have read: a heavy song passes 25 in 100 when its tune's middle (the lead channel's middle pitch) lies under F#4, 51 between F#4 and A4, and **73 from B-flat 4 up**, over the light songs' 60, which do not move with the register at all; heavy songs' tunes sit at A4 in the middle, light songs' at D5. What heavy songs lose is memorability (−0.22) and clarity (−0.14), not naturalness (−0.03). And it is not their level: the desk holds the lead 2.1 dB over the rhythm in heavy songs and 2.3 in light ones, though across all of them a lead further over the rhythm reads a little better (r = +0.24). Warcraft climbs with the register all the way, 57 to 89 in 100 from under D4 to D5 and up, most in its weakest moments (camp, depths and night: held tunes at E4, passing ones at C5) | The demo moved the register alone (`register-1128`, read 28 November 06:28: six held songs, every low lead voice an octave up inside its player's range, against the same sheet performed again, which itself moved the judges by 0.01 in the middle and 0.02 at most): the mean rose by +0.04 across the six (+0.11 Scentless Hour, +0.08 Pass-Shelter Hymn, +0.06 Crow-Pecked Fling, +0.03 Rush-Light Chant, −0.00 Sleet-Blind Salvo, −0.07 Silk-Tent Departure), and only one rose 0.10 on both scores. So register is a real lever but a small one, and it turns on the instrument: strings and voices brought up into where they sing rose (a viola and a bass clarinet, a choir), clarinets brought up into their thin top fell, a heavy song's cello did nothing. The register on paper (25 against 73 in 100) is mostly something else that goes with a high tune: which instrument carries it and how it is written. No register floor in the writer; most heavy songs could not be moved at all (their low tunes are trombones and horns near the top of their reach). What is tried next is **which instrument carries the tune**. *Tried the same morning* (`instrument-1128`, read 07:57: six held songs' tunes — each its busiest lead voice, a low instrument sitting low — given to a bright instrument their style plays, moved by octaves into its singing range, read against the studio's own take): **all six rose, +0.22 on the mean on average (the least +0.09), +0.23 memorability, +0.24 clarity** — Iron-Lung Hammer's trombone to the chop's own lead guitar +0.36/+0.39 (3.05 to 3.41, now over the bar), Titanfall Verdict's trombone to doom's own lead guitar +0.34/+0.43, Pig-Iron Gate's trombone to violins +0.30/+0.23 (now over), Sleet-Blind Salvo's cello to a fiddle +0.14/+0.16 (now over; the same cello an octave up had moved nothing), Keg Toast's horns and Tithe Bench's cello to violins +0.11 and +0.09. **The heavy songs' failure is a tune given to a trombone, horns or a low cello, under the band**; on the band's own lead it comes through. The mend for the writer keeps each song's palette — the tune to the song's own brightest singing voice, the low brass doubling or answering it, not carrying it alone — so as not to give every song the same lead (11-23: "too much of the same instrument sounds") |
| **House's 21 new acts, auditioned and read** (2026-11-27, `acts-1126`: each on a liked song's own notes beside the house's own act on the same notes — the hard acts on Rain on the Roofs, the after-hours ones on The Long Wait; 27 takes) | **Eighteen are sound and three are not.** On Rain on the Roofs the house's own reads 2.71 and sixteen of seventeen stand at or over it (powerhouse +0.26, warehouse +0.19, faultline +0.16, millrace +0.15, tunnel +0.14, catacomb alone −0.04). On The Long Wait the house's own reads 3.00: velvet +0.04 and bazaar, cellar, flophouse and mortuary within 0.07 of it, then **pumphouse −0.23, switchyard −0.42, gallows −0.43**. In ABSOLUTE terms the two groups barely differ (2.57–2.95 against 2.67–2.97): what differs is the house's own act, 3.00 on the after-hours song and 2.71 on the storm. And the in-key warning is answered — the six acts whose texture flagged at 62–65% (chopshop, drydock, foundry, kennel, powerhouse, quarry) ALL read at or over the house's own: **measured, and not heard** | Give the eighteen songs. **Gallows, switchyard and pumphouse get none** until reworked and read again, as the drumline, the brawl, noir and the skald were. And note what the audition says about the house's own act: it is an after-hours act and it is weak at hard songs, which is the gap the new hard acts fill — never judge an act against one global figure, only against the house's own on the same notes |
| **A band that reads badly can be mended by reworking it** (the five weakest Knight bands of 11-26, each given its riff on a guitar and its own instrument moved to the single-guitar part, and auditioned again on the same two songs: `auditions-1126`, 27 November 10:38) | **Once in five.** Against each band's own reading before the rework: **drumline +0.29 on both songs** (3.05 → 3.34 light, 2.88 → 3.17 heavy, where it now stands over the house band's 3.09) — mended. Brawl +0.03 and +0.14, skald −0.04 and −0.09, noir 0.00 and +0.08: inside the 0.15 two renders of one patch move a judge, so unchanged. **Bones −0.53 on the light song** (3.73 → 3.20): its light reading had been OVER the house band's 3.62, and the rework took away the thing it did best. **And the house band itself reads 3.62 on the light song and 3.09 on the heavy one** — the liked band, half a point lower on heavy | Rework is not a reliable mend: keep drumline2; put bones back as it was for light songs; the brawl, the skald and noir are where they were. The effort is better spent writing for the bands that read well than rebuilding the ones that do not. And read the night's heavy-song finding again beside the house band's own 0.53 gap: **heavy Knight Rock reads lower even when the liked band plays it**. That is at least partly the judges, not the new bands — so, as with the companies and their strings, do not chase the heavy songs' scores up by making them lighter, or every Knight song drifts toward the same calm. Ask whether heavy songs SOUND worse, which only Sky can answer |
| **An act's audition on one borrowed song says how it will do on its own songs** (the verdict of 10:15 the same morning: "gallows, switchyard and pumphouse get none until reworked") | 2026-11-27 15:26, House's 94 act songs that had been in the player ungated, all read under `gate-unheld-1127`: **47 of 94 pass, 50 in 100.** Set beside each act's audition: **gallows**, benched at −0.43 on The Long Wait, passes **4 of 5** of its own songs; **warehouse**, +0.19 and among the best at the audition, passes **3 of 10**; chopshop, arcade, kennel and tunnel all beat the house's own act at the audition and pass **0 of 2** each on their own. By place the 94 run strong for battleground 2/2, camp 7/8, night 6/8, boss 3/4, and nowhere for **infernal, marsh and mystic, 0 of 3 each**, storm 2/7, battle and frozen 1/4. The two are tangled — the hard acts write for the hard places, and the hard places read low — so act and place cannot be told apart on this set | An audition on one borrowed song is a sketch, not a verdict: **do not bench an act on it.** Gallows is NOT benched; its own songs are among House's best. Judge an act by its own songs where it has them. And the place finding stands on its own: House's act music is weakest exactly in the dark and strange settings the new music is meant to lean into — infernal, marsh, mystic — which is the question to put on paper before House writes another song for them |
| A bell in the old House songs' drums (their claps and snares stand 8 to 17 dB under the liked stems at 900 Hz and 1.8 kHz) | five old songs with the drums' middle 5 and 9 dB up, 25 November: *the themes' hardness moved by -0.8 to +0.3; one listening judge fell with the amount on four songs of five, by 0.05 to 0.25, and two rose by 0.01 to 0.14*: the judges do not agree, and a song that exists stays as it is unless they do | The old songs' drums as they are; what the meter hears in them is that nothing turns, and that is a revision of their sheets (the kick rests at each eight's end, a pickup, a shaker out every other eight), kept song by song where the judges agree |
