# Changelog

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
  - With Knight Rock's 101 tracks that is 734 tracks, about 32 hours, before any two takes
    swap parts.
- **A way back.** A tick box on the player page ("Play the written pieces"; `freerock settings
  pieces off`) plays only the loose phrases, as the forever song was before.
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
