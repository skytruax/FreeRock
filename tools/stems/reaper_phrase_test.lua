-- Experiment: one house phrase for four instruments, written as notes, rendered by REAPER as
-- four stems with no one at the controls.
--
-- Run by tools/stems/reaper_try.py, which starts REAPER on a screen nobody sees and passes the
-- folder to write to in FREEROCK_OUT. Uses only the instruments that come with REAPER, so what
-- it proves is the route (notes in, stems out, exact to the sample), not the sound.
local out = os.getenv("FREEROCK_OUT")
local log = io.open(out .. "/log.txt", "w")
local function say(text)
  log:write(text .. "\n")
  log:flush()
end

local BPM = 110
local BAR = 240 / BPM                       -- seconds
local VERSE, BUILD, CHORUS = 4, 4, 8        -- bars: one turn of the form
local BARS = VERSE + BUILD + CHORUS
local LENGTH = BARS * BAR

say("REAPER " .. reaper.GetAppVersion())
reaper.SetCurrentBPM(0, BPM, false)

-- The changes: one chord a bar, the same four round and round. D major: D, A, B minor, G.
local ROOTS = { 50, 45, 47, 43 }            -- D3 A2 B2 G2
local THIRDS = { 4, 4, 3, 4 }               -- major, major, minor, major
local function chord(bar)
  local index = (bar % 4) + 1
  return ROOTS[index], THIRDS[index]
end
-- How much is going on in each bar: held back in the verse, rising, full in the chorus.
local function part(bar)
  if bar < VERSE then return "verse" elseif bar < VERSE + BUILD then return "build" end
  return "chorus"
end

local function track(name, instrument)
  local index = reaper.CountTracks(0)
  reaper.InsertTrackAtIndex(index, false)
  local tr = reaper.GetTrack(0, index)
  reaper.GetSetMediaTrackInfo_String(tr, "P_NAME", name, true)
  local fx = reaper.TrackFX_AddByName(tr, instrument, false, -1)
  say(name .. ": " .. instrument .. " loaded as fx " .. tostring(fx))
  local item = reaper.CreateNewMIDIItemInProj(tr, 0, LENGTH, false)
  return tr, reaper.GetActiveTake(item)
end

-- A note at `beat` beats into `bar` (both from 0), `beats` long.
local function note(take, bar, beat, beats, pitch, velocity)
  local from = bar * BAR + beat * BAR / 4
  local to = from + beats * BAR / 4
  reaper.MIDI_InsertNote(take, false, false, reaper.MIDI_GetPPQPosFromProjTime(take, from),
    reaper.MIDI_GetPPQPosFromProjTime(take, to), 0, pitch, velocity, true)
end

-- Drums: ReaSynDr has four voices on notes 36 to 39 (kick, snare, hat, tom).
local _, drums = track("drums", "ReaSynDr")
for bar = 0, BARS - 1 do
  local where = part(bar)
  for beat = 0, 3 do
    if where ~= "verse" or beat % 2 == 0 then note(drums, bar, beat, 0.25, 36, 110) end   -- four on the floor from the build-up on
    if where == "chorus" and beat % 2 == 1 then note(drums, bar, beat, 0.25, 37, 100) end
    note(drums, bar, beat + 0.5, 0.25, 38, where == "verse" and 60 or 90)                 -- off-beat hat
  end
  if where == "build" then                                                               -- a roll that gets busier
    local hits = 2 ^ (bar - VERSE + 1)
    for hit = 0, hits - 1 do note(drums, bar, 2 + 2 * hit / hits, 0.1, 37, 60 + 10 * (bar - VERSE)) end
  end
end
reaper.MIDI_Sort(drums)

-- Bass: the root on every off-beat; in the chorus it also jumps the octave.
local _, bass = track("bass", "ReaSynth")
for bar = 0, BARS - 1 do
  local root = chord(bar) - 12
  for beat = 0, 3 do
    if part(bar) ~= "verse" or beat % 2 == 0 then note(bass, bar, beat + 0.5, 0.45, root, 100) end
    if part(bar) == "chorus" and beat == 3 then note(bass, bar, beat, 0.25, root + 12, 90) end
  end
end
reaper.MIDI_Sort(bass)

-- Chords: stabs on the off-beats, held longer through the build-up.
local _, chords = track("rhythm", "ReaSynth")
for bar = 0, BARS - 1 do
  local root, third = chord(bar)
  local long = part(bar) == "build" and 0.9 or 0.4
  for beat = 0, 3 do
    if part(bar) ~= "verse" or beat == 1 or beat == 3 then
      for _, step in ipairs({ 12, 12 + third, 19 }) do note(chords, bar, beat + 0.5, long, root + step, 80) end
    end
  end
end
reaper.MIDI_Sort(chords)

-- Tune: a few notes in the verse, a line that climbs through the build-up, a hook in the chorus.
local _, lead = track("lead", "ReaSynth")
local SCALE = { 0, 2, 4, 7, 9, 12, 14, 16 }    -- D major pentatonic, from D5
local HOOK = { 5, 4, 5, 7, 5, 4, 3, 1 }
for bar = 0, BARS - 1 do
  local where = part(bar)
  if where == "verse" then
    note(lead, bar, 0, 1.5, 74 + SCALE[(bar % 3) + 1], 70)
  elseif where == "build" then
    for step = 0, 3 do note(lead, bar, step, 0.9, 74 + SCALE[math.min(bar - VERSE + step + 1, 8)], 80) end
  else
    for step = 0, 7 do note(lead, bar, step / 2, 0.45, 74 + SCALE[HOOK[((step + bar) % 8) + 1]], 95) end
  end
end
reaper.MIDI_Sort(lead)

-- Render every track as its own file: exactly one turn of the form, 48 kHz, 16 bit, no tail.
for index = 0, reaper.CountTracks(0) - 1 do
  reaper.SetTrackSelected(reaper.GetTrack(0, index), true)
end
reaper.GetSetProjectInfo(0, "RENDER_SETTINGS", 3, true)        -- stems of the selected tracks only
reaper.GetSetProjectInfo(0, "RENDER_BOUNDSFLAG", 0, true)      -- the stretch given below
reaper.GetSetProjectInfo(0, "RENDER_STARTPOS", 0, true)
reaper.GetSetProjectInfo(0, "RENDER_ENDPOS", LENGTH, true)
reaper.GetSetProjectInfo(0, "RENDER_TAILFLAG", 0, true)
reaper.GetSetProjectInfo(0, "RENDER_SRATE", 48000, true)
reaper.GetSetProjectInfo(0, "RENDER_CHANNELS", 2, true)
reaper.GetSetProjectInfo_String(0, "RENDER_FILE", out, true)
reaper.GetSetProjectInfo_String(0, "RENDER_PATTERN", "$track", true)
reaper.GetSetProjectInfo_String(0, "RENDER_FORMAT", "ZXZhdxAAAA==", true)   -- WAV, 16 bit
reaper.Main_SaveProjectEx(0, out .. "/phrase.rpp", 0)
say("project saved; rendering")
local began = reaper.time_precise()
reaper.Main_OnCommand(41824, 0)            -- File: Render project, using the most recent render settings
say(string.format("render returned after %.2f s", reaper.time_precise() - began))
reaper.Main_SaveProjectEx(0, out .. "/phrase.rpp", 0)
say("done")
log:close()
reaper.Main_OnCommand(40004, 0)            -- File: Quit REAPER
