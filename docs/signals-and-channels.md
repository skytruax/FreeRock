# Game signals and the five channels

How what happens in the game becomes what each of a track's five channels does. Written on
2026-11-17 from the code, not from memory; line numbers are as of that day. Every number below
is a knob, and the last section says where each one lives. The numbered problems near the end
(P1, P2, ...) are there to be argued over and changed.

## The five channels

| Channel | What it is in a track | Warcraft | Knight Rock | House |
|---|---|---|---|---|
| texture | the bed: pads, drones, held chords; in House also the risers and the weather | strings, organ, choir | Hammond, pads | Surge pads, the air instrument |
| lead | the tune | the solo instruments | lead guitar, clean guitar | lead synths, Muse keys and winds |
| rhythm | the accompaniment: figures, riffs, arpeggios | harp, plucked strings, ostinati | the riff guitars | plucks, stabs, keys |
| drums | the percussion | war drums, timpani, orchestral percussion | the rock kit | the TR-8 kit |
| bass | the low line | cellos and basses, contrabassoon | electric bass | sub and growl, bass synths |

The game moves three numbers and a tone:

- **bed** sets texture, lead and rhythm together;
- **drums** and **bass** each have their own number;
- filters, reverb and the overall volume shape the tone.

A written piece can also hold a channel up by itself: its **floors** (see "What a piece adds").

## From the game to the speakers, and how fast

1. **The addon** (`FreeRock/Signals.lua`) reads the game every 0.2 s. Zone, weather and daylight are read every 2 s; game events are read the moment they fire.
2. **The strip** (`Beacon.lua`) is redrawn on the next frame after any change, and at least every 0.5 s. Names are sent six letters at a time, so a long subzone name takes up to 1.6 s to arrive.
3. **The sensor** on the gaming PC copies the strip 20 times a second while the game is the window in front.
4. **The server** decodes the strip (`state.py`). If frames stop arriving, it holds the last good state (the link is "stale" after 1.5 s). After 120 s without a frame, the link counts as lost and the music fades to silence.
5. **The director** (`director.py`) runs at least 4 times a second and answers with a target: place, intensity, bed, drums, bass, filters, reverb, volume.
6. **The mixing desk** (`forever.mix`, in `forever.py`) gives each channel a level and a strength: calm, steady or hard.
7. **The player** (`web/player/forever.js`, `setTarget`) moves the channels at once. A channel comes up over 3.5-4 s and goes down over 5-6 s. Filters and reverb move over the target's fade time: 0.4 s usually, 0.15 s under water, 0.25 s into stealth.

So a fight that starts is heard beginning to come up about a quarter of a second later, and is fully up after about 4 s.

## What the game tells us

| Signal | From | Used by the music for |
|---|---|---|
| zone, subzone | `GetRealZoneText`, `GetSubZoneText` | the kind of place, its light and shade, its ground (graves, woods, ...) |
| instance kind | `IsInInstance` | dungeon (party, raid, scenario), battleground (pvp, arena) |
| position, speed | `C_Map.GetPlayerMapPosition`, `GetUnitSpeed` | moving, standing still, lingering, how long you have been going |
| indoors, resting | `IsIndoors`, `IsResting` | cave, inn, town |
| mounted, flight path | `IsMounted`, `UnitOnTaxi` | riding; a flight path |
| submerged | `IsSubmerged` | under water |
| stealth | `IsStealthed` | stealth |
| dead, ghost | `UnitIsDeadOrGhost` | dead |
| combat | `InCombatLockdown`, `UnitAffectingCombat` | a fight |
| target | `UnitExists`, `UnitClassification`, `UnitCanAttack` | sizing up a foe; elites, rares, world bosses |
| enemies, fighting | nameplates with `UnitExists`, `UnitCanAttack`, `UnitIsDead`, `UnitAffectingCombat` (counts only, up to 14) | company (3 or more foes in view), a crowd in a fight |
| boss encounter | `ENCOUNTER_START/END`, `C_InstanceEncounter.IsEncounterInProgress` | boss music |
| weather | `C_Weather.GetCurrentWeather` (kind and strength) | rain, storm, snow, sandstorm |
| day or night | `C_DateAndTime.IsDayTime` | night |
| moments | level up, boss beaten, boss lost, died, quest handed in, achievement | a swell (or, on dying, the music winding down) |
| loading screen, cinematic | their events | ducking, silence |
| `/rock skip, love, ban, volume, on, off` | slash commands | the player's buttons, the volume, switching off |

Read but not used by the music yet: swimming on the surface, flying, a boss unit present, being in a group, the zone's PvP kind, instance difficulty, the game clock (see P18).

## How much is going on: the intensity

Everything hangs on one number between 0 and 1. Without a fight it sits on a **floor** that follows what you are doing (`director.py:303-348`). The rules apply in this order:

| What you are doing | Floor |
|---|---|
| lingering (still for 15 s or more) | 0.10 |
| standing (still for 1.5 s or more) | 0.25 |
| on a flight path (a journey, not a wait: it never lingers) | 0.25 |
| on foot | 0.40, growing to 0.57 over 20 s of going |
| riding | 0.60, growing to 0.75 over 25 s |
| in a dungeon | 0.15 more than the above |
| a hostile target in your sights (after 0.2 s) | at least 0.57; 0.68 for an elite, rare or world boss |
| 3 or more foes in view | at least 0.44 + 0.03 per foe, up to 0.62 |
| in an inn | at most 0.30 |

When there is no word on movement at all, the floor is 0.25 (0.40 in a dungeon), and 0.60 once you have been mounted for 1 s.

**In a fight** (`director.py:351-402`):

- intensity jumps to 0.80 and then climbs 0.006 a second, up to 0.90;
- at least 0.85 with 2 foes fighting you, 0.90 with 3, 0.93 with 4, 0.96 with 5 or more;
- at least 0.92 against an elite or a rare;
- 1.0 against a boss or a world boss.

**After a fight:** the music holds for 3 s, or up to 13 s when fights come one after another (the "roll"). Then the intensity falls 0.12 a second back to the floor. Fights in a row also raise the floor itself, by up to 0.32.

**Moments and weather:**

- A level gained holds the intensity at 1.0 for 10 s, a boss beaten at 0.9 for 10 s, a quest handed in at 0.7 for 5 s, an achievement at 0.8 for 6 s. A smaller moment while a bigger one is being answered is part of it; one as big or bigger takes over, for the longer of the two.
- Rain at storm strength (0.6 and over) lifts the intensity to between 0.6 and 0.8.

**Full tilt** (place "storm"): the intensity's floor plus the roll reaches 0.70, out of a fight. A 17-second ride gets there, and so do fights close together. A dungeon's extra 0.15 is left out of it (P12).

## Which kind of music: the place

The first match wins (`director.py:465-526`). Ordinary fights do not change the place: the piece playing stays, and its channels come up.

| # | When | Place | Also allowed |
|---|---|---|---|
| 1 | a boss encounter | boss | battle |
| 2 | still fighting after a boss's encounter | battle | storm, boss |
| 3 | a battleground or arena (through fights and deaths) | battleground | wander |
| 4 | dead or a ghost | ember | wander |
| 5 | the afterglow of a boss fight that lasted 10 s or more (8 s after the hold) | ember | |
| 6 | the hold after a boss fight | battle | storm |
| 7 | in a cave, or under a roof whose place's name does not say a building (`atlas.building_of`: a hall, a keep, a tower, a harbor, a shire...), for 1 s (released 2 s after leaving) | depths | wander |
| 8 | in an inn (resting, indoors) | ember | wander |
| 9 | in a town (resting, out of doors) | town | wander |
| 10 | a rain storm for 4 s, out of doors (it ends once the rain has been under 0.4, or turned to other weather, for 20 s together) | storm | wander |
| 11 | full tilt | storm | wander |
| 11a | camping: still for 45 s out of doors, not in a town (a settlement by its own name, 2026-11-23), on a flight path, in a dungeon or a fight (added 2026-11-17) | camp | wander, ember; night at night |
| 12 | night, out of doors and not in a dungeon | night | wander; ember when lingering |
| 13 | anything else | wander | depths in a dungeon; ember when lingering |

"Also allowed" pieces can be chosen too, at a small cost (0.12 for walking music at night).
Places 3, 7, 8, 9 and 11a are "sited": the player follows a change into or out of them even in the middle of a piece.

## The mixing desk: from the director to each channel

`forever.mix` (in `forever.py`):

| Channel | Level | Strength (calm / steady / hard) |
|---|---|---|
| texture | bed, but 0.6 of it from intensity 0.80 (room for the band) | always calm |
| lead | bed | steady from 0.52, hard from 0.83 |
| rhythm | bed from intensity 0.30; nothing below (it goes out again below 0.285) | steady from 0.52, hard from 0.74 |
| drums | 0 below intensity 0.33; then 0.45 rising to 1.0 by 0.80 | steady from 0.52, hard from 0.74 |
| bass | 0 until intensity 0.55 (and out again below 0.47); then 0.70 rising to 1.0 by 0.80 | steady from 0.50, hard from 0.88 |

In ember (an inn, death, the afterglow) every channel is calm. A written piece has one strength, so
only the levels move; the rhythm's strength still says which pieces serve the moment (see P2).

The intensity ladder, worked out (the bass as it comes up):

| Moment | Intensity | Drums | Bass | Rhythm | Texture |
|---|---|---|---|---|---|
| lingering / standing | 0.10 / 0.25 | 0 | 0 | off | bed |
| inn | 0.30 | 0 | 0 | on | bed |
| walking / standing in a dungeon | 0.40 | 0.55 | 0 | on | bed |
| 20 s on foot, or a target in sights | 0.57 | 0.75 | 0.70 | on | bed |
| riding | 0.60 | 0.75 | 0.75 | on | bed |
| big game in sights | 0.68 | 0.85 | 0.85 | on | bed |
| 25 s riding | 0.75 | 0.95 | 0.95 | on | bed |
| a fight | 0.80-1.0 | 1.0 | 1.0 | on | 0.6 of bed |

## The tone and the channel overrides

The lowest low-pass, the highest high-pass and the largest reverb win; volumes multiply (`director.py:533-587`).

| When | Low-pass | High-pass | Reverb | Volume | Channels |
|---|---|---|---|---|---|
| cave, and inns (P7) | 2500 Hz | | 0.40 | | |
| under water | 500 Hz | | | | everything moves in 0.15 s |
| rain, out of doors, strength s | | | 0.08 + 0.12 s | | drums at least 0.6 from strength 0.3 |
| snow, out of doors | 6000 Hz | | 0.20 + 0.25 s | | drums × (1 − 0.3 s) |
| sandstorm, out of doors | 3000 + 5000 (1 − s) Hz | 300 s Hz | | | |
| night, out of doors and not in a dungeon (nor in a storm) | 3800 Hz | | 0.15 | 0.89 (1 dB down) | drums × 0.7; the drums' and bass's floors × 0.75 |
| inn | | | | 0.63 (4 dB down) | bass 0 |
| flight path | | 150 Hz | 0.30 | | bass 0 |
| loading screen | 800 Hz | | | 0.5 | |
| stealth, out of a fight | | | | | bed 0, drums 0.35, bass 0.7 (the bass line alone), in 0.25 s |
| dead | at most 1200 Hz | | at least 0.6 | × 0.4 | bed 1.0, drums 0, bass 0 |

Standing still (not in a fight, a storm, an inn or on a flight path): the bed is 0.85 after 1.5 s, and 0.65 once you have lingered 15 s. The drums and bass are not turned down by this rule. They fall away because the intensity drops to 0.25. The music is also darker, as a band playing softly loses its edge: the top comes down to 6500 Hz on stopping and to 3400 Hz once you have stood (or sat) 15 s, over 3 s, and opens again at once when you move or a fight starts; not with something to fight in your sights, under water or on a loading screen ("sometimes when one synth stays in when youre sitting its whiny and annoying mix better", 2026-11-17).

When the bass is 0, the bed (texture, lead, rhythm) is also cut below 110 Hz.

## What a piece adds: floors and follows

A written piece carries its own minimums, so that it never falls apart under the game's levels
(`_level`, `forever.js:958-969`). Floors and follows only ever raise a channel, never lower it:

```
level = what the desk gives the channel
for each channel it follows: level = max(level, that channel's level)
level = max(level, floor × bed × hush)          (hush: 0.75 at night for drums and bass, else 1)
```

What the writers stage:

| | open | theme | rise | moment | close | follow |
|---|---|---|---|---|---|---|
| Warcraft and Knight Rock (`build.py:56`) | rhythm 1.0, bass 0.85, drums 0.6 | rhythm 1.0, bass 0.85, drums 0.55 | rhythm 1.0, bass 0.9, drums 0.75 | rhythm 1.0, bass 1.0, drums 0.9 | rhythm 1.0, bass 0.85, drums 0.55 | rhythm and texture follow the lead |
| House, walking (`house.Take.meta`) | drums 0.36, bass 0.4 | drums 0.6, bass 0.5 | drums 0.36, bass 0.4 | drums 0.6, bass 0.5 | drums 0.36, bass 0.4 | rhythm follows the lead |
| House, fights and battlegrounds | drums 0.9, bass 0.85 in every part | | | | | |
| House, inns and camps | drums 0.3, bass 0.32 | drums 0.5, bass 0.4 | drums 0.3, bass 0.32 | drums 0.5, bass 0.4 | drums 0.3, bass 0.32 | |

House's open, rise and close had no floor until 2026-11-17: standing still, the director takes the drums and the bass
out, and there that left the synths all but alone ("sometimes when one synth stays in when youre sitting its whiny and
annoying mix better"). Now the bass stays under them, and a little of the drums (60% of the theme's drums, 80% of its bass).

The Warcraft and Knight floors are deliberate. On the evening of 2026-11-16 you said, while
playing, "the abruptness between fighting and not, its way too much now, it should only be a
subtle difference like before". So the drums and bass stand at 55-100% whatever the game does,
and a fight adds the rest. The cost is P1.

## Signal by signal

"bed" is the director's bed number; the floors above come on top for written pieces.

| In the game | Intensity / place | Texture | Lead | Rhythm | Drums | Bass | Tone |
|---|---|---|---|---|---|---|---|
| a fight | 0.80 → 0.90, place unchanged | 0.6 (House; Warcraft and Knight follow the lead) | 1.0 | 1.0 | 1.0 | 1.0 | up over 4 s; held 3-13 s after, then down 0.12/s |
| elite, world boss | 0.92 / 1.0 | 0.6 | 1.0 | 1.0 | 1.0 | 1.0 | |
| dungeon boss | 1.0, boss piece | 0.6 | 1.0 | 1.0 | 1.0 | 1.0 | the piece changes on the next beat |
| a hostile target in sights | 0.57 (0.68 big) | bed | bed | bed | 0.75 (0.85) | 0.70 (0.85) | after 0.2 s |
| 3+ foes in view | 0.53-0.62 | bed | bed | bed | 0.70-0.80 | 0-0.80 | |
| walking | 0.40 → 0.57 over 20 s | bed | bed | bed | 0.55 → 0.75 | 0, then 0.70 after about 18 s | |
| riding | 0.60 → 0.75 over 25 s; full tilt at 0.70 | bed | bed | bed | 0.75 → 0.95 | 0.75 → 0.95 | |
| standing still | 0.25 | 0.85 | 0.85 | off | 0 | 0 | down over 5-6 s; low-pass 6500 Hz, over 3 s |
| lingering | 0.10; ember allowed | 0.65 | 0.65 | off | 0 | 0 | low-pass 3400 Hz, over 3 s |
| camping (45 s still, out of doors) | 0.10; camp music, every strength calm | 0.65 | 0.65 | off | 0 | 0 | |
| dungeon | floor +0.15 | | | | 0.55 standing | 0.70-0.90 walking | depths allowed |
| cave | depths after 1 s | | | | | | low-pass 2500 Hz, reverb 0.40 |
| inn | at most 0.30, ember | 1.0 | 1.0 | only when walking | 0 | 0 | 4 dB down, plus the cave tint |
| town | town | as usual | | | | | |
| battleground, arena | battleground | as usual | | | | | |
| night | night, out of doors | | | | × 0.7 | floors × 0.75 | low-pass 3800 Hz, reverb 0.15, 1 dB down |
| rain | storm after 4 s at strength 0.6 | | | | at least 0.6 from 0.3 | | more reverb; at storm strength the night tint is off |
| snow | | | | | × (1 − 0.3 s) | | low-pass 6000 Hz, wide reverb |
| sandstorm | | | | | | | narrow and gritty by strength |
| under water | | | | | | | low-pass 500 Hz; everything in 0.15 s |
| flight path | counts as standing still | 0.85 → 0.65 | 0.85 → 0.65 | off | 0 | 0 | high-pass 150 Hz, reverb 0.30 |
| stealth | | 0 | 0 | 0 | 0.35 | 0.7 | in 0.25 s |
| dead | 0, ember | 1.0 | 1.0 | off | 0 | 0 | low-pass 1200 Hz, reverb 0.6, 8 dB down; the music winds down like a record over 1.2 s |
| loading screen | | | | | | | low-pass 800 Hz, 6 dB down |
| cinematic, FreeRock off, link lost | silence | | | | | | fades of 0.3, 1.0 and 2.0 s |

## Moving between pieces: when a song changes, and which comes

Rethought from the ground on the evening of 2026-11-17, after playing, in your words: "fights shouldnt start new
songs"; "the idea is to hear new music all the time, for the whole songs to play, for the best song to be chosen based
on the place, and for major place changes to shift the songs"; "for songs to match locations, but for us to hear new
songs every night and it not go back to those old ones until it finally goes back around"; "but major place changes,
inns, camps, or abrupt storms should change the song"; "entering a new place the song should be based on the time and
weather and place"; "but this should only happen in like zone changes, not every subzone"; "need to do a better job
dynamically to match the mood in general".

### The rules

1. **A song plays whole.** A track runs its pieces in order (open, theme, rise, moment, then the second wave: the quiet
   middle, the climb, the summit, the close). The next piece is ready 12 s before the end and starts exactly on it.
2. **Only these change the song that is playing**, on the next bar line over two bars:
   - **a new zone** (or a dungeon), once you have been in it 15 s (a corner cut across a border changes nothing; on a
     flight path the zone you left stands until you land);
   - **going into a place with music of its own**: an inn, a camp, a cave or mine, a town, a battleground (4 s after);
   - **a storm setting in** (heavy rain for 4 s, then 4 s more; not a long ride at full tilt, which the game also
     calls a storm: its hard rock waits for the next song);
   - **a dungeon's boss** (on the next beat over one bar).
   Going **out** of an inn, camp, cave, town or battleground ends that place's song too; a storm's song ends where its
   part ends once the storm is over. Back in the zone the walking song was playing in, within 5 minutes and less than
   8 minutes after it began, it is picked up at the bar it reached; otherwise a new one comes. Only walking music is
   gone back to: a cave's, an inn's, a camp's or a storm's song belongs to where it was. A new song always begins at
   its opening.
3. **Nothing else changes it**: not a subzone (whatever kind of land, shade or ground its name says), not nightfall, not
   the weather short of a storm, not a fight, not standing or sitting, not the calm after a fight.
4. **Which song comes** (when one ends, or after a change), in this order: the moment (an inn's, a camp's, a cave's, a
   storm's, the night's own music before the walking music that takes turns with it, which counts 2.5 against it); the
   kind of land (the zone's, with the subzone's colouring: written for it first, then one that lists it, then the
   zone's second kind; a neighbouring kind's counts 0.6, a far one's 5, so it comes only where nothing else will do);
   light and heavy in turn, one for one; then the round of what has been heard: never heard first, then the one heard
   longest ago (a track heard costs 1.2, and up to 1.0 more for each of its last three hearings, falling away over some
   six hours; a sister tune of the same character heard in the last two hours 0.8). The page remembers this for 60
   days, so each night starts with what the last did not play. A song led by the instrument that led the last one counts
   0.3 against it, by what led the one before 0.15 (a piece knows its lead, `studio.lead_of`, from its music sheet; a
   fight's does not count). Among those the hour and the weather choose by shade
   (night darker by 1.5 steps, rain by 0.5 to 1) and the ground underfoot by its setting. The calm after a fight is no
   place: a song that begins in it is walking music.
5. **Inside a song, the music follows the mood as it changes**: a fight brings the drums and the bass up, and **drives
   the song on to its own rise** (where it is in its opening, a theme or the quiet middle, its next rise comes in on the
   next bar line: the same song, further on, and the moment after it); standing still and sitting make it softer and
   darker; night darker and further off; rain wetter; a storm brings the whole band; snow softens; a cave muffles;
   something to fight in sight leans in. See the tables above.
6. **Silences:** every `rest_every_minutes` (3 in the settings now) a silence is due, at the next end of a whole track,
   unless intensity is 0.74 or over. It lasts about `rest_seconds` (40 now). A fight ends it early.
7. **Dying:** the music slows to a stop over 1.2 s, then the ember music comes in over 3 s.

### What the audit found (2026-11-17)

- **Subzones moved the song.** The player looked again whenever the kinds of land, the light, the shade (night falling
  counted) or the ground changed, and a subzone's name changes all of them; then on the way back the old song was
  picked up again: "the same knight rock one over and over then something else maybe then it comes back". Now only a
  new zone, a place with music of its own, a storm or a boss.
- **The heavy turn was cut short.** In a light place a heavy track that came on its turn was ended after its opening.
- **Wear lasted an hour and a half**, so there was no round from night to night, and a place with two light tracks
  heard those two all evening. Now the round above, kept for 60 days.
- **The moment's own music lost to walking music** once the round was in: a never-heard walking song beat the storm's.
  Now what takes turns with the moment counts 2.5 against it.
- **A fight's prepared piece went stale**: chosen ahead after one pull and kept however long the calm lasted.
- **Loch Modan was heard as sunny farmland** (its profile said "cheerful", mandolin, tin whistle): it is dwarven hill
  country, highland first, and not a light place. The next morning **Hillsbrad Foothills** was found light for the
  word "peace" in "uneasy peace": a contested border, now "uneasy truce" and "watchful". Which zones are light is
  pinned by a test (`test_atlas.py`): Elwynn, Mulgore, Teldrassil, Moonglade, Thunder Bluff, Darnassus, Zephras Isle and
  the Riverglades.
- **Camps and storms did not change the song**, and a camp's or a storm's song played on after it.
- **Found by a made-up evening the next night** (`tools/soak.py`, Knight Rock): a long ride at full tilt changed the
  song (it is a "storm" to the game); a song that ended early was followed by another song's middle; a cave's song
  came back outdoors after the cave. All three mended.
- **Still thin**: a kind of place in Knight Rock or House has few tracks of its own (Knight's light walking music for
  the hills and fields was two tunes of one character), so the round comes back sooner there; more are being written.

## Problems, to iterate on

P1. **Floors beat the director's silences.** For Warcraft and Knight pieces in a theme:

- in an inn the bass still plays at 0.85 and the drums at 0.55 (the inn's "no bass" never happens);
- dead: drums 0.55, bass 0.85, where the rule says none;
- standing still: drums 0.47, bass 0.72.

And with the bass 0 in the director's numbers, the bed is cut below 110 Hz while the floor keeps the bass playing, which thins the sound. Only stealth removes the floors. A way through: the director says when it means silence (inn, dead, flight path), and floors give way then. Elsewhere they stay, for the subtle difference you asked for. The bed's cut should follow what is really heard from the bass, not the director's number. Left as it is on 2026-11-17 until it has been heard: whether an inn's or a ghost's own piece should keep its bass and drums is for the ear.

P2. **A fight only turns things up.** A piece has one strength, so one foe, five foes, an elite and a world boss sound the same once the intensity reaches 0.80. The strengths (calm, steady, hard) only choose which pieces serve; within a piece nothing changes. A way through: hard versions of the moment pieces' drums and rhythm (a busier groove, the doubled riff), or extra layers that come in above 0.85.

P3. **Standing still is only half quieter.** The bed drops to 0.85 and then 0.65, but the floors hold the drums and bass up (P1). ("standing still should quiet the tracks", 2026-11-16.)

P4. **Cinematics can't be seen.** The game hides the whole interface for a cinematic, so the strip vanishes; the music plays on and only fades when the link is lost, 120 s later. A way through: a strip gone for more than 3 s while the game is still the window in front means "duck".

P5. ~~Every death in a battleground winds the music down and starts it again.~~ Fixed 2026-11-17: in a battleground the death is not passed on to the player, and its music plays on, far off, until the spirit healer.

P6. **The texture's dip in fights (0.6) happens only in House:** in Warcraft and Knight Rock the texture follows the lead and stays at 1.0.

P7. **Inns get the cave's muffle** (low-pass 2500 Hz, reverb 0.40), and so do caves' own pieces. A test keeps the inn's on purpose: a building sounded like inside when a zone had one loop. Now the inn's and the cave's pieces are written for them, and the muffle takes their top off. For the ear: keep it, soften it, or drop it for a place's own music.

P8. ~~Snow, sandstorm and night tints apply indoors and in dungeons.~~ Fixed 2026-11-17: out of doors only (a sandstorm's 300 Hz cut took the bass out of a cave), and no night pieces in dungeons either.

P9. **Under water and in stealth every change is fast**, including a fight starting under water (0.15 s).

P10. **The player takes intensity 0.74 and over as a fight.** A 25 s ride (0.75), heavy rain, a level gained, a boss beaten and an achievement also hold off silences and place changes.

P11. **A silence after every track.** With 8-minute tracks and a silence due every 3 minutes, one always follows a track: 24 to 56 s of nothing after each.

P12. ~~Full tilt is easy to reach.~~ Fixed 2026-11-17: 17 s of walking in a dungeon got there (the dungeon's +0.15 plus walking) and played storm music. Full tilt is now judged without the dungeon's 0.15.

P13. ~~A flight path counts as standing still~~, and ember music joined after 15 s on it. Fixed 2026-11-17: a flight path stays at 0.25, at full level, with no lingering.

P14. **"Boss" is any encounter in progress**, with no check that you are in a dungeon.

P15. ~~A plain rare counts as big game in your sights but not as an elite in the fight.~~ Fixed 2026-11-17: a rare is an elite in the fight too (0.92).

P16. ~~A smaller moment can cut a bigger one short~~: a quest handed in 6 s after a level gained dropped the swell from 1.0 to 0.7. Fixed 2026-11-17.

P17. ~~A storm ends only after rain under 0.4 for 20 s; rain between 0.4 and 0.6 neither keeps it nor ends it.~~ Fixed 2026-11-17: rain between the two keeps the storm and starts the 20 s again, and snow or a sandstorm after rain counts as no rain.

P18. **Signals not used yet:** swimming on the surface, flying, a boss unit present, being in a group, the zone's PvP kind (world PvP), instance difficulty, the game clock. Each could become a rule: open water, a raid's weight, a contested zone's edge, dawn and dusk.

P19. **With enemy nameplates switched off**, the foe counts read 0, so "company" and "a crowd in the fight" never happen.

P20. **`docs/places.md` was out of date** in places, corrected on 2026-11-17:

- a storm sets in after 4 s, not 10;
- the afterglow (ember) follows only boss fights of 10 s or more;
- mounting brightens nothing;
- swimming and flying have no tints;
- caves are "not in a dungeon", so a battleground's buildings get the cave tint.

Still to be seen in the game:

- what range the weather's strength really takes (the rules assume 0 to 1);
- whether the strip can be read on a loading screen;
- whether `IsEncounterInProgress` is ever true outside instances;
- whether `IsDayTime` answers inside them.

## Where to change things

| Knob | Value | Where |
|---|---|---|
| moving after / still after / lingering after / camping after | 0.2 s / 1.5 s / 15 s / 45 s | `director.py` rules (`moving_after_s`, `still_after_s`, `linger_after_s`, `camp_after_s`) |
| floors: lingering, standing, on foot, riding, dungeon | 0.10, 0.25, 0.40 (+0.17 over 20 s), 0.60 (+0.15 over 25 s), +0.15 | `director.py:303-348` |
| sizing up, company, inn ceiling | 0.57 / 0.68, 0.44 + 0.03 per foe (up to 0.62), 0.30 | same |
| fight: start, climb, crowd, elite, boss | 0.80 (+0.08 roll), 0.006/s to 0.90, 0.85-0.96, 0.92, 1.0 | `director.py:351-402` |
| hold after a fight, fall | 3 s + 10 s × roll, 0.12/s | `hold_after_combat_s`, `roll_hold_s` |
| drums on, drums least | 0.33, 0.45 | `drums_on`, `drums_least` |
| bass on / off, bass least | 0.55 / 0.47, 0.70 | `bass_on`, `bass_off`, `bass_least` |
| full tilt on / off | 0.70 / 0.62 | `charge_at`, `charge_off` |
| storm at / after / release | 0.6 / 4 s / under 0.4 for 20 s | `storm_at`, `storm_after_s`, `storm_release_at`, `storm_release_s` |
| standing still, lingering (bed) | 0.85, 0.65 | `still_bed`, `linger_bed` |
| night: low-pass, volume, drums, floors | 3800 Hz, 0.89, × 0.7, × 0.75 | `NIGHT_TOP`, `NIGHT_GAIN`, `NIGHT_HUSH` |
| the tints | the table above | `director.py:533-587` |
| texture's fight dip, rhythm from | 0.6 from 0.80, 0.30 | `forever.mix`, `RHYTHM_FROM` |
| strengths | lead 0.52/0.83, rhythm and drums 0.52/0.74, bass 0.50/0.88 | `forever.GEARS` |
| channel ramps up / down | 3.5-4 s / 5-6 s | `forever.js` `UP`, `DOWN` |
| piece floors and follows | the table above | `studio/build.py` `FLOOR`, `studio/house.py` `meta()` |
| silences | every 3 min, 40 s | `var/settings.json` `rest_every_minutes`, `rest_seconds` |
