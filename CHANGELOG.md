# Changelog

## More Warcraft, and more of the band in each piece (2026-11-16, night)

Said while playing: "need more variety in warcraft first before you actually print house", "write
the most dynamic interesting music you can, look at where we are", "not enough instruments in
each track", "prioritize warcraft for 3 hours then shift".

- **Fourteen new kinds of Warcraft piece** (`studio/orchestra.py`, at the end of `CHARACTERS` so
  every family made before keeps its seed): a shadowed wood, a fallen farmstead, a border keep,
  rain on the roof, a forsaken parlour, a witch's hollow, a spirit grove, barrow kings, a
  windswept cliff, a dark ritual, a savanna, temple steps, a night market and a high pasture.
  They bring voices Warcraft had not had: a piano, a bass flute, a bass clarinet, handbells
  and a euphonium (Muse Sounds, each played alone and checked for pitch first; the euphonium
  is kept above C3, where Muse's sounds an octave up).
- **The heavy music for walking about has a second family** (`studio/build.py` `plan`): a dark
  wood had three pieces of its own. Second families are named after all the others, so no
  title changed.
- **Fuller writing.** The second theme's figure plays with the first one's where the music
  grows (at the moments, from each theme's second statement, through the second half of each
  rise); a slower line goes under a theme from its second statement; the bass is doubled an
  octave away by its neighbour (`PARTNERS`); the second strong instrument joins the tune from
  the first statement of a moment; the moment's small percussion joins a theme the second
  time round. The opening, the valley and the close are left as bare as they were, so a piece
  swells and falls further than before: three instruments at the opening, six to nine in the
  themes, eight to eighteen at the moments.
- **Moments that differ by place** (`studio/build.py` `CROWNS`): every heavy piece used to end
  its moments with the same choir and bell. Now the haunted, mystic and regal places have the
  choir and the bell, infernal ones the choir, the open country and the hills the horns, the
  desert and the jungle neither; light pieces have a soft horn or voice chord at their moments.
- **High ground is read from a place's name** (`kinds.py`): "Shen'dar Highlands" was heard as the
  plain country round it. Highland, mountain, peak, ridge, summit, cliff, height, crest,
  pinnacle and moor now say highland.

## Played for an evening: one song through a fight, fades on everything, no repeats, nothing bought (2026-11-16, late)

The first evening on the new pieces, with the game. What was said while playing, and what was
changed while they played:

- **"feels like its playing the same songs over and over and maybe playing a different song in
  battles"; "in normal fights dont play a separate battle piece dungeon bosses ONLY".** Every
  pull used to cut to a piece written for fights, on the beat, and back again: a different song
  every half minute, from a handful of battle tracks (26 plays of four that evening). Now a
  fight is answered by the song that is playing, with its drums and bass brought up. Only a
  dungeon's boss (the game says when its encounter begins and ends) has music of its own; an
  elite, a crowd, a long fight and a world boss do not (`director.py`: `place` is "boss" for an
  encounter and nothing else names a fight's piece; `forever.js`: `_ask`).
- **"the abruptness between fighting and not, its way too much now, it should only be a subtle
  difference like before".** The afternoon's "drastic" hand is taken back: the drums and the
  bass stand at 55 to 100% whatever the game does (`studio/build.py` FLOOR, and written into
  the pieces already in the buckets without rendering them again), twenty seconds on foot
  bring the drums to about 73%, and a fight adds the last quarter.
- **"you gotta fade in and out of everything, new songs, but even channel changes".** A channel
  now comes up over three and a half to four seconds and goes down over five to six (it was
  1.2 for the drums and the bass). A new song is crossfaded in under the last bar of the one
  that is ending, and is whole on the beat that one ends on; a boss's piece comes in over a
  bar; the music comes in over three seconds when it starts from nothing.
- **The same tracks round and round.** The best-suited track was chosen every time, so a place
  of one kind with three tracks written for it heard those three all night. Now each time a
  track has begun in the last three quarters of an hour counts against choosing it again,
  measured among light tracks and among heavy ones separately so that they go on taking turns;
  and the kinds of place have neighbours (pastoral: highland, regal, mystic; jungle: mystic,
  haunted, desert; and so on), whose music is reached for before a track is heard a third time.
- **"stop buying eleven labs were making music now".** The server used to buy phrases from
  ElevenLabs the whole time the game was played (147 minutes that evening). `freerock serve`
  now buys nothing; `--buy-from-elevenlabs` is how it is asked for.
- **Restarts.** A server that was told to stop held on to the game's sensor for two minutes
  (and wrote its old bucket lists over new ones): it now closes every connection at once. A
  page that was playing is left to play for half a minute after a start, while the sensor finds
  the new server, and the sensor tries again every three seconds at most, not fifteen.
- Kept from a review that was begun and stopped: a place change that arrives in the middle of
  a fight is no longer lost (the look is taken again when the fight is over); the calm after a
  fight inside a cave no longer takes the cave's track away; and looking for a better track
  no longer forgets the one that was left.

## A band, players that breathe, and music that goes where the player goes (2026-11-16, night)

Said while the evening's music was being rendered: "make sure our location changes CHANGE
SONGS based on tone ect", "start rocking make sure tonight you print enough of these for
every type of situation", "get working on some of our acdc knight rock ones too", "it still
seems like the instruments are a little bland".

- **The music follows the player (`forever.js`, `director.py`).** A walk into another kind of
  place used to change the music only where the piece that was playing ended (up to a
  minute on), and a cave or an inn only when the whole eight-minute track had ended. Now,
  four seconds after the player has gone into another kind of place, into a cave or an inn,
  or out of one, the track written for it takes over on the next bar line, the old one giving
  way over two bars. A step over a border and back within those seconds changes nothing; the
  music does not move twice within twenty seconds; and going back picks the old track up at
  the bar it had reached. The director says when the kind of moment comes from where the
  player stands (`sited`: a cave, an inn) and not from what is going on: the calm after a
  fight is not a place, and the walking track still goes on through it. A place's first kind
  now counts for more than its second (Stormwind is regal before it is pastoral), so a city
  brings the city's music. In a fight nothing moves for a place.
- **A band (`studio/muse.py`, `studio/sounds.py`).** The knight rock pieces had no players in
  the new studio. Now: the riff is played twice, as a record is made, by Muse's Les Paul on
  the left and its Stratocaster on the right, each through its own amplifier, the second a
  hundredth of a second behind the first; muted notes are the same two playing short with
  the top taken off; the tune is the Les Paul's lead tone with an echo; the bass is Muse's
  electric bass, made narrow; the organ is its Hammond; a band's plain guitar is the
  Stratocaster played clean; the kit is the 1970s rock kit with the kick under its bass
  drum. Each sound was measured alone against the rock stems that were liked and set by
  that: the two guitars brought level (they were 8 dB apart), the Les Paul's fizz taken off,
  the Stratocaster's honk at 450 Hz down, the lead given a body and its top taken down (it
  was 5 dB bright and thin), the kit given more stroke and less box.
- **A held note is never still.** MuseScore's players follow a hairpin under a held note, and
  written without one they held every long note at one level; and the pads (strings, choir,
  organ) were written at one strength for all eight minutes, the story's rise and fall
  being in the writer's swells, which were not being passed on. Now a long note of a bowed,
  blown or sung part begins a mark under its strength, is fullest past its middle and falls
  away, further at the end of a phrase; a line of long notes that run into each other is one
  breath; and a pad goes with the writer's swell from note to note and inside each note.
- **Adding to a bucket no longer reads what is already in it** (four minutes for 28 tracks
  became seconds), and `tools/fresh_bucket.py <style> --keep-style` makes a second style
  ready without changing the one in force.

## An orchestra that is given a score (2026-11-16, evening)

The reworked sample instruments were heard and turned down too: "still sounds like a 90s
windows demo", "the lead synth sounds cheezy", and then the decision: "the music is well
written we just need a good renderer", "we should be using plugins and effects for most
instruments". So the orchestra is no longer played from the studio's own recordings.

- **MuseScore plays the orchestra (`studio/muse.py`).** MuseScore Studio comes with Muse
  Sounds: recorded instruments that are given a score, not notes to trigger, and play it as
  players would. Each written voice is written out as a score (MusicXML): a dynamic mark
  where the strength changes, a slur over notes that follow at once on each other, a dot on a
  short note, an accent on one struck harder than those about it, tremolo strokes, "pizz.".
  MuseScore performs it with no window and the recording is laid on a REAPER track, in time
  with what REAPER itself plays to within two thousandths of a second. The drums (the kit
  plug-ins, the kick) and whatever MuseScore has no instrument for stay with REAPER, and the
  mix, the hall and the five channels are as before.
- **Many sounds, and not the same ones in every piece.** There are 117 Muse Sounds on the
  drive. A part can be given any of them by name (six horns or one, four trumpets or one,
  first or second violins, the choir as women and men or voice by voice, a grand, a soft or
  an upright piano), and each piece draws its own from its seed.
- **A check that it is really Muse Sounds.** Told a profile name or an instrument it does not
  know, MuseScore says nothing and plays its plain built-in sounds. A performance with
  nothing at all above 16 kHz is taken to be that, and stops the piece.
- **A real kick.** A recorded studio kick's inside and outside microphones with a designed
  sub from the Geonkick drum synthesiser under it, a fifth of a second long, in place of a
  26-inch drum that rang for seven tenths; the other channels give way under each stroke by
  a drawn volume curve.
- **5.1 on the mixing-desk page**, where the browser has six loudspeakers: the tune in front
  with some in the centre, the pad round the room, the drums and the bass to the sub.

Heard that evening as the first pieces came out ("sounds much better", then "still sounds a
little generic add more depth", "more bass and kick in the intense parts", "theres not much
difference between quet and full, we want more ... drasticness"), and changed before the
evening's music was rendered:

- **The game's hand is drastic now.** The drums and the bass used to stand at 55 to 100%
  whatever the game did. Now a calm game has no drums and about a third of the bass; a rise
  lets a quarter of the drums in, a moment half; a fight brings everything.
- **Layers the desk stacks on what the writer wrote** (`studio/build.py`): a kick on every bar
  of each moment and of the end of each rise; a deep sub and low brass doubling the bass
  through the moments; a bell on each moment's first beat; a choir singing the pad's chords
  there; a wide synth pad far under the string pad, all the way through.
- **Depth.** A hall a third longer with more of everything sent to it; air on the tune
  (an exciter), the bottom lifted and made audible on small loudspeakers (a bass enhancer),
  tape on every channel, the pad widened, plucked parts answering themselves a dotted eighth
  later; the drums and the bass placed higher, the kick five decibels up in all.
- **More instruments.** Every pitched instrument is a Muse Sound: guitars, harpsichord, music
  box, bells and the folk winds by name; in one piece out of three the harp's part is a
  piano's. The accordion's parts are a recorded chromatic harmonica's ("i better hear
  harmonica and banjo"); the banjo's are a strumstick's, since there is no banjo recording.
- **A light piece's percussion** (a few taps of a triangle) is no longer turned up sixteen
  decibels to reach the drums' place.
- **5.1 in the game's player** (`web/player/forever.js`): with six loudspeakers the music is
  laid round the room (the front pair as it is, a little in the centre, the low end to the sub
  as well, a soft copy a moment late behind); if six cannot be had it plays on two and the
  page says why.
- `tools/render_some.py` renders a chosen list of tracks several at a time and past a failure;
  `tools/fresh_bucket.py` takes a style's old written pieces out of its bucket and puts the
  staged ones in. The Warcraft bucket's 474 tracks rendered with the General MIDI sound set
  were taken out that evening.

## The instruments, one at a time (2026-11-16, afternoon)

The second try in REAPER was heard and turned down: "sounds very low quality", "instruments
still shitty", "drums are not good". The studio cannot hear, so it was given an ear of a kind
and each instrument was gone through by itself.

- **An ear (`studio/ear.py`).** A recording is measured the way an engineer holds a mix against
  a record they trust: how its power is spread over the octaves, how far its peaks stand above
  its body, how wide it is. The records it is held against are the stems that were listened
  to and liked (`var/stems`), each by the instrument it was asked for. What it found in the
  second try: every instrument ten to eighteen decibels short above 2.5 kHz (the sampler's
  filter followed the note and stood half shut), war drums with nearly all their power under
  160 Hz (the drums were tuned five to fifteen semitones down), and twelve decibels of rumble
  under 40 Hz. It judges none of what makes an instrument sound played; ears do that.
- **Every instrument is its recording.** The filter no longer follows the note and is past
  9 kHz by the middle of an instrument's strength. A section that was recorded as a section
  is played as it is: no second and third copies a few cents apart, and no chorus. The synth
  pad under the strings is gone.
- **Brass that can play loud.** The horn, trumpet, trombone and tuba are TinySOL's (IRCAM):
  every semitone played soft, medium and loud, with no vibrato. A horn played loud is twenty
  decibels louder than one played soft and has twenty-five more above 2.5 kHz, and the three
  recordings fade into each other as the players swell. Three horns, two trumpets and two
  trombones are made of the neighbouring semitones, each a different recording a little apart
  in time and place. The clarinet and the bassoon are TinySOL's as well.
- **Slurs.** In a line of single notes, a note that follows at once on a different one is
  slurred to it: it comes in over the note before without a start of its own, as the next
  note under one bow or in one breath does. A note after a gap, or the same note again,
  starts afresh. Chords are left alone.
- **A long note is not still.** It leans in, is fullest past its middle and eases off, by a
  different amount each time, and the last note of a phrase falls away.
- **War drums from drum-kit plug-ins.** Two drummers at two kits (the AVL kits Red Zeppelin
  and Black Pearl: both floor toms, both toms, the 26-inch bass drum) and a third at the big
  rusty drums, every drum at the pitch it was recorded at; the stroke brought out, the skin
  and the room brought up under it by a compressor laid beside the sound. The deep stroke on
  an arrival is both kits' bass drums, the deep floor tom, a concert bass drum and a sub at
  65 Hz. The frame drums have a cajon with them (Buskman's Holiday). A band's kit, when the
  band is next played, is the Red Zeppelin kit itself. Measured against the drums that were
  liked, the drum channel of a whole piece is now within about two decibels in every octave.
- **The bottom belongs to one thing.** Each channel loses what is under 28 Hz. Where the
  double basses play out, a plain sub sits under them at their own pitch (a recorded double
  bass has little of its bottom octave), in the middle.
- **A second of silence before every project.** The kit plug-ins fetch their recordings when
  the first stretch of sound is asked of them and play nothing in it. The second is cut from
  what REAPER renders.
- **Each instrument alone, to listen to.** `tools/audition.py` writes
  `var/listen/instruments/`: every instrument playing a phrase by itself, as the bare
  recording, as it was before, and as it is now, with the ear's numbers beside in
  `measured.json`.
- **A track on a mixing desk.** Asked for the same afternoon: "can the player show the multiple
  channels like a mixer so i know its made up of multiple channels that are going to be signal
  dependent". On the listening pages every track has a "channels" link (`tools/mixer.html`,
  written out by `tools/listen.py`): its five channels side by side, each with a meter, a
  fader, mute and solo; the story's parts along the top, to click on; and a slider that does
  to the drums and the bass what the game does, down to the least each part of the story
  will play them at. The channels are kept as twelve-second pieces and laid end to end on the
  audio clock, all five at once, so they cannot drift apart.
- A whole eight-minute piece now renders in under seven minutes (it took fifteen): the
  equaliser on every channel is the studio's own (`studio/jsfx/channel_eq`), and there are
  far fewer effects.

## Written pieces (2026-11-15, the night after the first evening)

The phrases of the forever song share a key and nothing else: each is one instrument alone, and
nothing in them goes anywhere together. And the ElevenLabs credits ran out the same evening.
What was added that night:

- **Pieces.** A bucket now holds written music beside its loose phrases. A piece is music
  written as a whole and kept as its parts: one recording for each channel that plays in it,
  in step with the others. The five decks play the parts together, each as loud as the game
  asks for its channel, so a piece keeps its own harmony and its own shape while the band comes
  and goes with the game. A piece keeps its own time: its tempo and key need not be the
  bucket's. A piece can say that one channel stands in for others (a whole band kept as one
  part is the tune and the drone as well) and how little of each channel it can do with, so
  that the moment a story comes to is whole whatever the game is doing.
- **A track tells a story.** A track is a run of pieces: it opens, states its theme, rises,
  comes to its moment and closes, each piece going into the next without a seam. When a track
  ends, another begins on that beat while the first rings on under it for a couple of bars
  (less when the two are in keys that do not sit together), and now and then a moment of
  silence comes between two tracks.
- **A fight cuts in with a piece of its own** on the next beat, and when it is over the track
  that was playing is picked up at the bar it had reached.
- **Kinds of place.** Music is written for a kind of place, not for a zone: pastoral, highland,
  haunted, desert, jungle, infernal, regal or mystic. Every zone is of one or two kinds, read
  from the words of its music profile, so a place nobody has listed gets music of the right
  kind from the words in its name; a named place inside a zone (an inn, a hall, a crypt) adds
  what its own name says. The player is told the kind of place with everything else it is
  told, and chooses pieces by it: first what answers how hard the game is asking, then the
  kind of moment (a fight, a cave, the night), then the kind of place.
- **Light and heavy take turns.** After a heavy track the next is a light one, so that staying
  in one place does not grow too intense. A light place (sunny farmland, an inn) is always light.
- **Pieces written over the same changes lend each other their parts**: the tune of one take
  with the drums of another and the bass of a third, so one story is told by another band each
  time it comes round.
- **Knight Rock from the songs on disk.** Every Knight Rock song made before the forever song
  (32 of them, in five keys and three tempos) is now in the Knight Rock bucket as pieces: 101
  tracks, 208 pieces, 88 minutes. A song proper, from its Intro to its Outro, is one track with
  a piece for each section; its Fight, Boss, Storm, Night, Ember and Depths parts are short
  tracks for those moments. The band, the drums and the bass of each section are the three
  parts, exactly as they are on disk. `freerock pieces songs` does it, and does nothing the
  second time.
- **Tracks from the studio.** Music written and played on this machine is staged under
  `var/studio/` (a folder for each track: a recording for each channel and a file saying what
  the track is; see `app/freerock/studio/__init__.py`). `freerock pieces add <style>` cuts the
  staged tracks into the pieces of their stories and puts them in the style's bucket;
  `freerock pieces list <style>` says what a style has. Both are for while the server is
  stopped, and say so if it is running.
- **Love and ban are for the whole piece**: `/rock ban` while a piece is playing takes every
  part of it out of play.
- The player page shows the piece that is playing and how far through it is, and how many
  written pieces the bucket has. The stems folder has every part of every piece in a folder
  for its piece. A page that connects is told where the player is before it is given the
  music, so that the first piece it plays is one for that place.

- **The studio and what it wrote that night** (`app/freerock/studio/`). Nothing in it asks
  anyone outside this machine for anything.
  - *The orchestra* (`orchestra.py`, `build.py`): original music written as notes and played
    through a sampled orchestra (FluidSynth and the MuseScore General SoundFont, unpacked under
    `var/tools/`: `tools/stems/README.md`). 58 characters: light and heavy music for each kind
    of place (a village dance in six-eight, a requiem, a caravan, troll drums in five-four, a
    dwarven hall...), and for the night, an inn, a cave, a storm, a fight and a boss. Each
    family has its own key, tempo, metre and changes; each take its own tune (a motif of two
    bars, answered, repeated higher and brought home), accompaniment, bass, drums and players.
    90 families, 223 tracks, 643 minutes.
  - *Real scores* (`scores.py`): public-domain orchestral works with clean licences, read from
    MusicXML and MIDI, each family of the orchestra played alone, every movement cut into
    tracks of about three minutes with the story found from its own loudness. All nine
    Beethoven symphonies, Brahms's four, Bruckner's Fifth, Dvořák's Ninth, William Tell,
    Egmont, Coriolan and more: 251 tracks, 743 minutes, each credited with its source.
  - *House* (`house.py`, `synth.py`): progressive house at 110 beats a minute on a synthesiser
    of our own, drums from CC0 recordings of a drum machine. 53 families, 159 tracks, 438 minutes.
  - *Knight Rock's band* (the same writer, with a band's instruments): riffs with room between
    the chords and the muted string chugging, a lead guitar that doubles in thirds at the
    moment, the bass on the root in eighths, a rock kit, a drone as of a hurdy-gurdy; the
    light ones are the band unplugged. The guitars are the SoundFont's clean ones played
    through an amplifier of our own (`amp.py`), so that a power chord's two notes beat against
    each other as they do in a real one. 32 families, 74 tracks, 211 minutes, for every kind
    of place and moment; the songs on disk cover only three kinds of place.
  - With the 101 tracks cut from Knight Rock's songs that is 808 tracks, about 35 hours,
    before any two takes swap parts.
- **A fight's own track goes on at the next fight** from the bar it had reached, so that over
  an evening of short fights the fight music gets past its opening; a boss still gets a boss's
  piece and a storm a storm's. After a fight the track that was playing goes on, from its next
  piece if the fight came in its last bars.
- **A way back.** A tick box on the player page ("Play the written pieces"; `freerock settings
  pieces off`) plays only the loose phrases, as the forever song was before. And `freerock
  pieces drop <style> <source>` takes every piece from one source out of a bucket for good
  (`knight/` is the studio's Knight Rock, `warcraft/real-` the real scores, `song/` the
  songs); what they were made from stays on disk, so they can be put back.
- **Listening without the game.** `tools/listen.py` writes every staged track as one file with
  a page to play them from; the server shows them at `/listen/`. `tools/soak.py` plays a
  pretend evening (a walk, a fight, a border, an inn, a boss, a desert at night, a cave) through
  the real server and a browser nobody sees, and prints what was chosen and when.
- The parts of pieces are kept as FLAC, half the size of the raw samples the loose phrases use.

Heard by nobody yet: the player has been measured with pieces (its parts locked together, no
seam where two stretches or two pieces join, the fight's piece in on the beat and the track
picked up after), and has played the real Knight Rock bucket in a browser here without a
problem, but what it sounds like is for the next evening in the game.

## The forever song (2026-11-15, the first evening in the game)

The first evening with the real game changed what FreeRock is. Whole songs made a few minutes
at a time turned out to repeat, and to answer the game too slowly. What replaced them:

- **A bucket of phrases, and five decks.** The music for a place in a style is a bucket of
  phrases, each one instrument alone (drums, bass, a rhythm part, a tune, a drone) at up to
  three strengths (calm, steady, hard), all on the place's tempo and tonal centre. The player
  keeps one phrase of each going on a shared bar grid. `settings.mode` is `forever` for this
  (the default) and `songs` for the songs of before.
- **A phrase is one turn of a form**: a verse, a build-up and a chorus, about three quarters of
  a minute, the same lengths for every channel, so the whole band builds up together and
  reaches the chorus together. The player shapes each turn as well (the verse held back, a rise
  through the build-up, the chorus at full; in Trance the lows are swept away before the
  chorus lands). Each time the form comes round, two of the decks may take a new phrase.
- **It follows the game channel by channel.** Standing still is the drone and the tune; moving
  brings the rhythm part and soft drums; a ride or a long walk the steady drums and the bass; a
  fight the hard drums and riff on the next half beat, in step, at that place in the form.
- **It counts the enemies in a fight** (strip version 3, see `protocol/beacon.md`): a second
  enemy brings the hard lead at once, a third the hard bass line, more than that everything.
  Enemies in view out of a fight keep the music from sitting right back.
- **It rises and falls of its own accord.** Now and then a turn of the form eases right off (to
  chill a minute), now and then one leans in. After about `rest_every_minutes` of music it
  comes down to a moment of silence (the last turn eased off, a fade over its last bars, about
  `rest_seconds` of nothing) and fades back in with a new verse. A fight overrides all of it.
- **The bucket is filled while the game is played.** A new place gets phrases two at a time
  until every channel has three at every strength, then one at a time up to eight, then
  wherever the music is running out of phrases nobody has heard. Each phrase is checked part by
  part for tempo, beat and tuning and asked for again in other words if it fails. The
  allowances are wide open by the player's choice; when ElevenLabs has nothing left, the song
  plays on from the bucket. `Bucket.add` takes any audio, so phrases made some other way can
  fill the same bucket.
- **Three styles**: Knight Rock, Warcraft (an orchestral score in the old manner) and
  Progressive House (uplifting, 110 beats a minute, a major key, happy and laid back; it took
  the place of Trance the same evening), chosen on the player page. A style has one bucket,
  which goes on growing wherever the player goes; phrases are asked for in the colours of the
  place the player is in.
- **Every change is a blend**, the way a DJ brings one record in under another: two bars for a
  deck taking a new phrase, half a bar for a fight coming in, seconds for a channel coming up
  or going down.
- **Stems kept for study**: every phrase is also written as a FLAC file under `var/stems/`,
  with `stems.csv` saying what each is and what it was asked for with. `freerock stems` brings
  the folder up to date.
- **The addon says what it found**: with the names it sends a line about itself (its version,
  the nameplates the game has up, the units that answered, living enemies, those fighting,
  dead ones left out), shown on the link page.
- Also from that evening: the strip can be drawn faint and small and hides with the interface
  (version 2 added the player's speed and whether the target can be fought); the reader finds a
  faint strip beside a bright sky; a building the game names as a zone is treated as a place
  inside its zone.

Not yet brought up to date: the tests of the songs mode's library, requests, track-making and
conductor.

## After the first listen (2026-11-15)

- **Rock during a rain storm.** Rain used to darken and soften the music. Now steady rain brings
  the drums in and a rain storm brings the whole band in at once, with nothing muffled, and the
  Storm part is hard rock of its own.
- **Rests.** After about six minutes of calm music the music fades away for about a minute and
  comes back with a fresh opening, as the game's music does between pieces. A fight, a storm,
  stealth or a new place ends a rest at once. `rest_every_minutes` and `rest_seconds` set it.
- **Planned for 100 hours a month.** Hours played are counted. A place's music grows with the time
  spent there (a second set after ten minutes, a fresh set every two hours, three fresh sets in
  rotation), and the minutes that go on that are released as the hours are played. The daily
  stop is now 30 minutes.
- The player plays a place's core suite and later sets as one body of music, and more music
  arriving for the place that is playing does not interrupt it.
- `freerock make "<zone>" --set second|fresh`; `tools/render_session.py storm`.

## 0.1.0 (2026-11-15)

First working version. Built and measured on Linux; not yet run in the game or on Windows.

**The game link**
- The addon: reads zone, subzone, position, instance, indoors, resting, swimming, mounted, flight
  path, stealth, dead, combat, boss encounter, target classification, weather, day or night; draws
  it as a strip; switches the game's own music off and puts it back; `/rock` commands.
- The strip format (`protocol/beacon.md`), a reader that survives gamma, contrast, tint, uneven
  dimming and scaling, and a sensor for Windows served by the server itself.
- A server with a live page showing what FreeRock sees, and a scripted pretend game.

**The music**
- One function for every paid ElevenLabs call, with monthly and daily allowances and a ledger.
- A zone's core suite: six parts in one tempo and key, written from a profile for each of the
  game's 50 zones.
- Layers split on this machine (drums, bass, everything else) that add up to the original.
- Checks on every track (length, tempo, starts on the beat, the notes of its key, no vocals). A
  track that fails is kept for inspection, not thrown away.

**What plays**
- The rules from game state to sound: which part, the layers' levels, and tone for caves,
  weather, night, water, stealth and death.
- A player in the browser that keeps the three layers locked to the sample, changes part on the
  bar or beat line, and never passes full scale.
- Music is made for a zone the first time you stay in it; until then it borrows another zone's.

**Found by measuring**
- ElevenLabs holds a stated tempo to within about 0.1%. In two of the three suites made so far
  every part started within about 10 ms of a beat; the third was 0.3 s late throughout and was
  turned away by the checks. A three-minute suite arrives in about twelve seconds.
- A second request told to stay close to thirty seconds of the first sounds like the same band by
  every measure taken.
- A 6 kHz muffle changed nothing measurable on guitars and lute; the cave, weather and night
  effects were moved lower and made steeper.
- The first key check read a low note's energy into its neighbours and rejected a good track. It
  now measures spectral peaks and asks whether the track uses the notes of its key.
