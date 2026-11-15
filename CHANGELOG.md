# Changelog

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
