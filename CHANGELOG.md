# Changelog

Newest first. Words in quotation marks are what was said while listening or playing, as typed or
dictated, where it drove the change.

## 2026-11-18, afternoon: the pedals on; drums, rises and basses that move

"k keep going"; "some of the instruments get boring figure out how to get more especially in house";
"Rain on the Roofs I is okay i wish i could hear more of that saw synths top end".

- **The band's 1970s pedals and the orchestra's moving effects are on** in every new take (the demos
  were heard). Each is still a switch (`orchestra.BAND_PEDALS`, `ORCHESTRA_MARKS`).
- **House's saw lead keeps its top**: only its very top is eased now (2 dB above 7 kHz), and the
  tune's filter opens further than the band's.
- **A band's long rise opens**: the rhythm guitar's wah is held at the heel as a rise of 16 bars or
  more begins and is brought by hand to the toe by its end, then let go so the moment comes in open.
- **A band's drummer turns the cymbal** every sixteen bars of a theme: the hat, then the ride. A groove
  on the toms takes the ride softly over it. At a heavy band's long moment the drummer rides out its
  second sixteen bars on the ride's bell.
- **House's bass grows harsher through a long drop**: halfway through every drop of 32 bars or more, a
  harsher twin plays the bass's own notes, coming in over eight bars (deadmau5's "Turning Point").
- **A judge that listens** ("find more music judging packages, that will rate a song"): Meta's
  Audiobox Aesthetics scores a take's enjoyment and production quality, whole and part by part
  (`tools/judge.py`), on this machine. It is a gate and a pointer for the sound, not a target.
- All found by the boredom meter (`tools/boredom.py`): a battle piece's rhythm guitar had one colour
  through a 36-bar rise, its drums one groove through a 40-bar theme and 18 bars of its last moment,
  and Moonwell's bass one colour through 44 bars of its last drop. The handbook has the lesson that a
  part can change its notes and still sound the same.

## 2026-11-18, midday: House's lead a riff, its synths bigger; no reed whining in a valley

"still some boring sounds in house, somethings got better the lead is still lame"; "the sounds just need
to be bigger somehow it sounds hollow and generic in the synths".

- **House's lead is a riff**: cells of three sixteenths resolved by two eighths, every note on the chord,
  as a progressive house hook is written. It's a pluck where the track is quiet and a big synth at the
  drops, chosen by each take. Its echo is thrown up on the last note of every four-bar phrase, and in a
  drop's second half a phaser turns on it and a second synth joins an octave up. The calm moments still
  sing their melodies.
- **Bigger synths**: the pads, chords and leads keep their body (cut from 110, 80 and 85 Hz, where they
  had been cut from 200, 110 and 120) and are spread wider: the lead has 2.5 dB more body and about 6 dB
  more width. Bigger Surge XT patches are on a page to choose from by ear.
- **A tape echo among the pedals** (`studio/jsfx/pedals`), its send thrown up by the sheet's marks.
- **No reed whining in a valley.** A valley's drone is no longer held by a reed (the english horn, a
  bagpipe, an accordion, a harmonica): it goes to the organ or the strings, and the english horn's pipe
  drone plays as low as the instrument does. King's Oath's valley drone went from 9 dB over the tune to
  2 under, with 17 dB less whine ("sometimes when one synth stays in when youre sitting its whiny").
- The plan has the study of judges and the rules of the nightly loop (gates, voters, the boredom meter,
  when a take may replace another, Sky's blind comparison), the better performances to come, and two
  licences for Sky to settle.

## 2026-11-18, late morning: every track gets its own music sheet; effects the music asks for

"the music sheet should be a separate concept and asset for every track, and updating it should be the
golden rule, you are a musician were working on music.... the rest is plumbing"; "the music itself
should denote the effects it shouldnt be standard"; "guitars should have effects in the 70s bro".

- **The music sheet** (`score.Sheet`).
  - Every new take is written down whole and kept beside its recordings as `sheet.json`: its form and
    keys, every part's notes, swells and effect marks, who plays each part, and its history of
    revisions with why. The revisions it replaces stay beside it.
  - The writers make the first draft (`build.write`, `club.write`); the desk only performs a sheet
    (`build.perform`, `club.perform`). Making a song better means revising its sheet and performing it
    again.
  - Performed from its sheet, a take makes exactly the REAPER project it did before (shown on three
    takes of both styles, and read back from the file).
  - `python -m freerock.studio.sheet show` lays a sheet out as a part chart, and `perform` plays it
    again.
- **Effects marked by the music.** A part's effect marks are where its own notes ask for them, never
  one rule for every piece.
  - The band's guitars, as a 1970s player works his pedals: a jet flanged by hand across a chord held
    into an arrival, a wah rocked at the pace of a running solo, a cry across a long held note, a vibe
    on a clean guitar ringing in the valley, a phaser on strummed chords where a passage comes back.
    Riffs and chugs stay dry, as on the records. Waiting on the ear before the lanes use them.
  - The studio's own REAPER effects play the marks (`studio/jsfx/pedals`: wah, phaser and flanger, in
    time with the song or swept by hand; `studio/jsfx/sweep`: a resonant low-pass and a high-pass).
    REAPER's bundled phaser starts its sweep again whenever a setting moves.
- **House, from a study of how the records are made** ("too much high hat and not enough dynamic
  sound", "study top dj techniques like deadmau5 and daft punk", "this is boring generic crap"):
  - Each part's filter follows its own notes' brightness, where four fixed cuts had stood: the theme
    darker than the drop, and the breakdown shut down dark. The chords' fixed top, which kept a drop
    as dark as its theme, gave way to it.
  - The sub leaves for each rise and the breakdown (26 dB down there, was 9), the last seven beats of
    a rise are thinned from the bottom, and everything comes back on the drop's first beat.
  - The hats are off the clap's bright chain and on a line of their own: high-passed, dry, 3 dB further
    under the kick, with the sixteenths between the eighths only at a drop.
  - The pump is deeper at a drop (the sub 14 dB, the pads 9) and swells back into the off-beat.
  - Held until its demo passes.
- **The songwriting handbook** opens with the sheet: what it is, how to read, revise and perform one,
  how effects are marked, and what was learned. The nightly loop works on sheets and writes what it
  learns there.

## 2026-11-18, morning: every style on the same ground, a real accordion, a bagpipe chosen by ear

"make sure all our new location, song switch, signal stuff, persists across all genres"; "new horn
sounds better"; "move re-rendering to the end when the drives are full".

- **Ground for every piece.** The player prefers the piece written for the ground underfoot (woods,
  water, heights, ruins...), but 23 Knight Rock characters, 24 Warcraft ones and every House family
  named none. Now all of them do (`orchestra.SETTINGS_OF`, `house.ground`), and the tests hold it.
- **A real accordion**: TinySOL's, every semitone from A1 at three strengths, where a harmonica had
  stood in, stretched below its range. In the Warcraft tavern its pad, 10 to 19 dB over the liked
  stems from 1.8 to 7 kHz, came to between 3 over and 7 under, and the reedy whine went.
- **The bagpipe, by ear.** FreePats' chanter was set aside by its numbers, then heard against
  MuseScore's english horn at one loudness, and the ear chose it: it plays the highland reel's and
  the stone circle's tunes, while a held drone stays the english horn.
- **House's clap and snare knock harder**: 3 dB more at 900 Hz, where each take was 3 to 6 dB short.
- **Effects over time** ("yes you need effects over time"): the desk can move any effect's setting
  through a piece (`desk.automated`, `desk.sweep`), a filter opening into a drop or closing in a
  breakdown; a resonant low-pass opened over ten seconds took a string chord from 680 to 2160 Hz.
- **Knight Rock's towns, a second boss and a battleground**: market square (a light shuffle for any
  town), royal march (for the great cities), warlord (the orc and troll lords) and banner war.
- **Soft war drums for the slower light walks** ("i hope you have been working on those war drums"):
  lighter walking music busy from 0.35 (a snowfall, a mirage, a frozen lake, a desert shrine, the ice
  fields) has them too; dances and the most delicate pieces still go without.
- **New music first, re-renders last.** Until the drive is full the nights make new takes, and each
  change to the writer or the desk goes into the re-render ledger (`tools/rerender_ledger.py`: when
  it came, what it does, which pieces it touches, and every take that still lacks it).
- `tools/new_songs.py` puts the newest songs on one page ("show me the listener with new house
  songs"), and `docs/plan.md` is written again, with how every style is to get better night by night
  once the drive is full ("good iteration, keep that up on every genre").

## 2026-11-18, small hours: more for the moments, rowdy inns, the new rules on a made-up evening

- **More for Knight Rock's moments and Warcraft's storms.** Now that inns, camps, caves and storms
  change the song, Knight Rock's one character for each would have come round and round: barroom
  blues, dwarf hall, road camp, glow cave, low tunnel, midnight ride and downpour run join them.
  Warcraft's fields, jungles, marshes, deserts and haunted woods get storms of their own (field
  storm, monsoon, witch storm). New characters are named last, so no family already made changes.
- **A rowdy inn walks**: a busy inn's music (the tavern, the drinking song, dwarf hall...) keeps its
  opening and middle present, as walking music does; a drinking hall's demo had opened at -38 dB.
- **The new rules on a made-up evening** (`tools/soak.py`): a long ride at full tilt no longer
  changes the song, only a rain storm that has set in does; a song that ends early is followed by
  another from its opening; a cave's song no longer follows you out.
- **No tuba under a rock band**: the low brass the desk lays under an orchestra's moments had
  doubled the band's bass, 8 to 15 dB over the liked stems. The sub at the moments stays.
- **The snow's accompaniment given a middle**: all celesta and glockenspiel, it was 21 dB short
  through the middle, so the ice and snow pieces play pizzicato for the glockenspiel and the frost
  camp a guitar. The celesta stays, for the sparkle.
- **Hillsbrad Foothills is a contested border**, not a gentle place; a test pins the light zones.

## 2026-11-17, evening: whole songs, changed only by big changes of place; harder and darker

"fights shouldnt start new songs"; "for the whole songs to play, for the best song to be chosen
based on the place, and for major place changes to shift the songs"; "the warcraft songs are too
light go a lil darker sometimes"; "go a little harder this is not world of fairy craft".

- **A song plays whole.** Only a new zone (after 15 s; held on a flight path), going into or out of
  an inn, a camp, a cave, a town or a battleground, a storm setting in, or a dungeon's boss changes
  it; a subzone, nightfall or the ground never does. A fight drives the song on to its own rise.
- **Which song comes next**: the moment's own music first, then the kind of land, light and heavy
  one for one, then the round ("for us to hear new songs every night and it not go back to those old
  ones until it finally goes back around"): never heard first, then the one heard longest ago,
  remembered for 60 days. The hour, the weather and the ground choose among those.
- **Sitting is soft and dark, not whiny** ("sometimes when one synth stays in when youre sitting its
  whiny and annoying mix better"): standing still closes the top of the music, more after 15 s; the
  quiet middle's pad goes under the tune, where a band's drone had stood 9 to 11 dB over everything;
  House keeps its bass and some drums under the synths.
- **Heavier, in every style** ("just a bit light and wimpy in general", "dont hear much war drums"):
  a light place hears the nearest heavy piece every other track; lively lighter walking music has
  soft war drums; every desk brings the drums and bass nearer; light pads sit three semitones up,
  not five; four country pieces trade celesta and glockenspiel for mandolin and guitar.
- **More Knight Rock for the hills and fields** ("feel like i hear the same knight rock one over and
  over"): hill country and harvest boogie, light; iron vow and free company, heavy.

## 2026-11-17, afternoon: House's sounds made again, more camps and bosses, three new kinds of place

"your house sounds cheesy bro more effects or something"; "keep cranking on warcraft we want lots of
options of inns camping, caves dungeons and just a not repetative experienxe"; "tonight make more
types or categories of places".

- **House's sounds.** A third pass against the liked stems closed the tops of the pads, risers,
  chords and bass, with a darker hall than the orchestra's; then 38 Surge XT patches were auditioned
  alone: new leads (Oberheim Dreams, Prophet VS, Moogy Saw, Crisp PWM), plucks and pads, synths for
  the tunes the pan flute and marimba sang, tape, chorus, slow phasers, longer echoes.
- **More camps and dungeon bosses**: a camp for each sort of country, one line over a drone
  (shepherds rest, fen fire, oasis embers, crows rest), and two bosses (deep tide, fallen crusade)
  for the kinds that had only the titan's.
- **Tops taken down where they were bright**: brass stabs, tubular bells, xylophone, harpsichord, a
  tavern's banjo. Knight Rock's texture and lead fall away at the top as a guitar's cabinet does
  (the liked band stems are dark), keeping the guitar's bite at 1 to 3 kHz.
- **One pass at each take** ("just do one adversarial pass instead of 3"): every take is studied
  once, and what is found goes into the writer or the desk for the pieces still to come.
- **Three new kinds of place**, each with music of its own: the marsh (the Wetlands, Swamp of
  Sorrows, Dustwallow), the coast (harbours, bays, isles) and the frozen snowfields (Dun Morogh,
  Alterac, Winterspring). Warcraft has 23 new characters for them (bog lights, sea breeze, the
  lighthouse, frog chorus, aurora, sailors rest, tide cave, frost wyrm, whiteout...), Knight Rock
  three (bayou boogie, sea dog, frost hammer), House nine families.

## 2026-11-17, morning: camping, the signals put right, lossless, a handbook, public

"camping should get its own tunes"; "switch it all back to flac"; "make sure we can play tonight
even without re-renders".

- **Camping has music of its own.** 45 s still out of doors, not in a fight, a town or a dungeon,
  nor on a flight path, is a camp: waiting on a spawn, a rare or a friend. Written for all three
  styles (the watchfire, still hunt and uneasy vigil; a campfire band; three House camps).
- **The signals put right**: a flight path never lingers; a rare is an elite in a fight too; a
  smaller moment no longer cuts a bigger one short; a storm ends after 20 s of light rain; snow,
  sandstorm and night are for out of doors; a death in a battleground no longer runs its music down.
- **House plays as loud as it is written.** Surge's patches play a note alike however hard it is
  struck, so each synth voice rides its level four bars at a time, by its loudest note. The tunes go
  a fifth lower (a house hook sits in the middle), and a sine sub plays the basses' notes.
- **Knight Rock's fights break down in their valley**: the riff rests under the clean guitar, the
  drummer keeps time on the cymbal, and the groove comes back with a fill into the climb.
- **Everything lossless.** After one night of MP3, staged takes are 24-bit FLAC, buckets and
  listening pages 16-bit FLAC, and MuseScore's performances 24-bit FLAC (`tools/muse_flac.py`).
- **Playing comes first**: a bucket is rebuilt only with the game off, so the music never waits.
- **The papers**: `docs/signals-and-channels.md` (how the game's signals move the five channels),
  the songwriting handbook (`docs/songwriting.md`), a README that tells FreeRock whole with pictures
  drawn from the real code and four short samples, the MIT licence, and the repository public.

## 2026-11-17, small hours: an orchestra that moves, the band's craft, House in two waves, the mix

"get everything out of muse"; "make sure the individual stem tracks are interesting enough";
"remember to use reaper and plugins for effects and mixing".

- **The orchestra moves as one does**, held against 72 movements of the public-domain repertoire
  (`tools/orchestra_study.py`): the bass moves through the chords, the pad's inner voices move, the
  first theme's third statement is a question from one player and an answer from another, and the
  theme's third time round at the moments is decorated.
- **The rest of Muse Sounds**: Muse Percussion (taikos, tam-tam, mark tree, field drum, rolls) with
  pickups and fills; the contrabassoon under grim music, the contrabass flute in glowing caves, the
  E-flat clarinet in dances, handchimes and the dream piano at night, the full choir for bosses.
- **The band**: the riff answers its chords with licks; the bass leads into each change; the drums
  fill every other phrase. A heavy band opens on one guitar alone and its valley's tune is the clean
  guitar's, so its pieces swing 17 to 20 dB from quietest to loudest, where they swung 8.
- **House in two waves**: open, theme, rise, drop; a breakdown (no kick, the bass one long note to a
  bar), a rise, the last drop, the close. House has towns and battlegrounds too, and its air
  (sweeps, wind, sea, rain, fire, crickets) is played in REAPER by the studio's own instrument.
- **The last of the mix in REAPER** (`mix.rpp`): each channel's stem on its own track, its fader
  where it was measured to go and the story's ride as its volume envelope; no channel so far up that
  another part goes more than 3 dB over it; every instrument measured before anything renders.

## 2026-11-16, night: more Warcraft, fuller pieces, towns, battlegrounds, caves, inns and the night

"need more variety in warcraft first"; "not enough instruments in each track"; "like whenever in an
alliance base should be a family of songs"; "night should feel like night".

- **Fourteen new kinds of Warcraft piece** (a shadowed wood, a border keep, barrow kings, a night
  market...), with new voices: piano, bass flute, bass clarinet, handbells and euphonium.
- **Fuller writing**: both themes' figures where the music grows, a slower line under the theme, the
  bass doubled an octave away, a second strong player at the moments. The opening, valley and close
  stay bare, so a piece swells from three players at the opening to eight to eighteen at the
  moments, each crowned by its kind of place.
- **Heard by family** ("been hearing the same thing over and over"): the player had counted each
  take of a family as a song of its own. Now a family counts as one, and the page keeps the count.
- **Towns and battlegrounds have music of their own**, a battleground's held through fights and
  deaths; nine new caves, five new inns, two more bosses.
- **Ground** ("granularity in locations on all the kinds"): woods, water, heights, fields, wastes,
  ruins, road, settlement, fort, sacred, graves or works, read from a place's name or its zone's;
  seventeen new characters fill the gaps of kind, ground and light.
- **Night is a place of its own**, darker, softer and hushed, with nine more night pieces; standing
  still quiets every channel, more after a while.
- **More dynamic** ("rewrite all music to be more dynamic"): pianissimo to fortissimo, and gentler
  buses. `tools/study.py` measures a set's swing and `tools/score_view.py` engraves a take's score.
- **Knight Rock's lead plays the blues**, and a heavy band's big moments open on a stop.
- **House gets a desk** (`studio/club.py`; "figure out how to make house music not suck"): its notes
  played in REAPER on Surge XT, Muse Sounds and a TR-8's recordings, all ducking the kick.

## 2026-11-16, evening: played for an evening; one song through a fight, fades on everything

"make sure our location changes CHANGE SONGS based on tone ect"; "in normal fights dont play a
separate battle piece dungeon bosses ONLY"; "you gotta fade in and out of everything, new songs, but
even channel changes".

- **The music follows the player**: into another kind of place, a cave or an inn (or out of one),
  the piece written for it takes over on the next bar line, four seconds on.
- **One song through a fight**: a fight brings up the drums and bass of the song that is playing,
  and only a dungeon's boss has music of its own.
- **Subtle and faded** ("it should only be a subtle difference like before"): the afternoon's
  drastic hand is taken back, the drums and bass standing at 55 to 100%; a channel comes up over 4 s
  and goes down over 5 to 6, and a new song is crossfaded in under the last bar of the old.
- **Fewer repeats**: a track heard lately counts against being chosen, and each kind of place has
  neighbours whose music is reached for first.
- **A band for Knight Rock**: Muse's Les Paul and Stratocaster double the riff, one each side; the
  Les Paul's lead tone, electric bass, Hammond and a 1970s rock kit, each set by the liked stems.
- **Players that breathe**: a long bowed, blown or sung note leans in, is fullest past its middle
  and falls away, and the pads follow the writer's swells.
- **A shade from grim to radiant** ("in a dark misty place and music is too light"): -3 to 3 for
  places and pieces, and a place's own name is read before its zone's.

## 2026-11-16, afternoon: an ear, each instrument by itself, and an orchestra given a score

"sounds very low quality", "drums are not good"; "still sounds like a 90s windows demo"; "the music
is well written we just need a good renderer".

- **An ear** (`studio/ear.py`). The studio cannot hear, so it measures each recording octave by
  octave against the stems that were liked: it found the orchestra 10 to 18 dB short above 2.5 kHz
  and the war drums tuned too low. It cannot tell whether an instrument sounds played; ears do that.
- **Each instrument by itself**: recordings played as they were made, slurred lines, war drums from
  the AVL kits and the Big Rusty Drums at their own pitch, a page of every instrument alone
  (`tools/audition.py`), and a real kick ("missing a kickdrum") with a Geonkick sub under it.
- **MuseScore plays the orchestra** (`studio/muse.py`): each voice written out as a score (dynamics,
  slurs, accents, tremolo, pizz.), performed with Muse Sounds and laid on a REAPER track. A part can
  have any of the 117 Muse Sounds by name, and each piece draws its own from its seed.
- **Then, as the first pieces came out** ("sounds much better", "more bass and kick in the intense
  parts", "i better hear harmonica and banjo"): every pitched instrument a Muse Sound, a harmonica,
  a strumstick; at the moments a kick on every bar, a sub and low brass under the bass, a bell, a
  choir; and a drastic hand for the game, no drums when calm ("we want more ... drasticness").
- **A mixing desk** ("can the player show the multiple channels like a mixer"): a take's five
  channels with meters, faders, mute and solo; and 5.1 where there are six loudspeakers.

## 2026-11-16, morning: eight minutes in two waves, played in REAPER

"rewrite all the music using the same concepts, but to 8 minutes"; "Then rerender with reaper".

- **Eight minutes, nine parts, two waves**: an opening, a first theme and a second, a build and an
  arrival; then a valley, where the broader theme is sung by one player over very little, a climb, a
  summit (the first theme from everyone, the second under it) and a close.
- **Written for real instruments**: string chords as a line for each section, the brass resting
  until the arrival, the celli and basses an octave apart with the low brass at the big moments.
- **REAPER plays every take**: a folder for each of the five channels, a track for every line, a
  concert hall at the foot of each folder; recordings in the sfizz sampler, Surge XT and
  ZynAddSubFX, effects by instrument family. The project is kept, to open and change by hand.
- **War drums**: nearly all through a fight and in each rise of heavy walking music; before an
  arrival the tune rests, the drums roll, a cymbal swells, and a deep stroke lands.

## 2026-11-15, night: the first written pieces

"real music, with stories, that rise and come to a moment"; "duskwood is a type of place".

- **Pieces**: music written as a whole and kept as five channels (texture, lead, rhythm, drums,
  bass), played together, each as loud as the game asks, so a piece keeps its own harmony and shape
  while the band comes and goes with the game.
- **A track tells a story**: it opens, states its theme, rises, comes to its moment and closes, each
  piece running into the next without a seam.
- **Kinds of place, not zones**: pastoral, highland, haunted, desert, jungle, infernal, regal and
  mystic, read from the words of each zone's profile. Light and heavy take turns.
- **The writer** (`studio/orchestra.py`): characters (music for each kind of place and for the
  night, an inn, a cave, a storm, a fight, a boss), families (key, tempo, metre, changes) and takes
  (a tune, its accompaniment, bass, drums and players). By morning, 58 characters and 223 takes.
- **Knight Rock and House**: eighteen band characters from the same writer (riffs with room between
  the chords, a lead in thirds at the moment, the bass on the root in eighths), and progressive
  house at 110 beats a minute from `studio/house.py`.
- **The tools**: `freerock pieces add|list|drop`, `tools/listen.py` (every staged take at
  `/listen/`) and `tools/soak.py` (a pretend evening through the real server and a browser nobody
  sees).
