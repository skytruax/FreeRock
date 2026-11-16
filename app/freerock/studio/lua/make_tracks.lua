-- Builds instruments as REAPER tracks and saves each as a track template.
--
-- Run by freerock.studio.desk with REAPER on a virtual display. FREEROCK_JOB names a Lua file
-- that returns what to build:
--
--   return { out = "<folder>", tracks = {
--     { name = "violins long", fx = {
--         { kind = "sampler", files = { "<wav>", ... }, low = 55, high = 58, root = 57, soft = 1, hard = 64,
--           tune = -2.0, gain = 0.0, attack = 30, release = 250, held = true, floor = -6.0 },
--         { kind = "clap", name = "CLAPi: Surge XT", chunk = "<base64 of the plug-in's own state>" },
--         { kind = "fx", name = "ReaEQ", params = { [0] = 0.5 }, named = { { "BANDTYPE0", "1" } } },
--     } },
--   } }
--
-- Each track is written to <out>/<name>.RTrackTemplate: the same file REAPER writes for "Save
-- track as template", so an instrument can be put into any project by hand as well.
local job = dofile(os.getenv("FREEROCK_JOB"))
local log = io.open(job.out .. "/make_tracks.log", "w")
local function say(text) log:write(tostring(text) .. "\n"); log:flush() end
local failed = 0

local function sampler(tr, spec)
  local fx = reaper.TrackFX_AddByName(tr, "ReaSamplOmatic5000", false, -1)
  if fx < 0 then error("REAPER's sampler could not be added") end
  for index, file in ipairs(spec.files) do
    reaper.TrackFX_SetNamedConfigParm(tr, fx, "FILE" .. (index - 1), file)
  end
  reaper.TrackFX_SetNamedConfigParm(tr, fx, "DONE", "")
  -- 2: the recording follows the note in semitones. 1: it plays as it is, whatever the note.
  reaper.TrackFX_SetNamedConfigParm(tr, fx, "MODE", spec.follow == false and "1" or "2")
  local function set(index, value) reaper.TrackFX_SetParamNormalized(tr, fx, index, math.max(0, math.min(1, value))) end
  set(0, 10 ^ ((spec.gain or 0) / 20) / 2)                 -- volume: 1.0 is +6 dB
  set(2, 10 ^ ((spec.floor or -12) / 20) / 2)              -- how loud the softest strike is
  set(3, spec.low / 127)
  set(4, spec.high / 127)
  set(5, (spec.low - spec.root + 80) / 160)                -- the pitch of the lowest note, in semitones from the recording
  set(6, (spec.high - spec.root + 80) / 160)
  set(15, ((spec.tune or 0) / 100 + 80) / 160)             -- fine tuning
  set(8, ((spec.voices or 12) - 1) / 16 / 4)
  set(9, (spec.attack or 1) / 2000)
  set(10, (spec.release or 100) / 2000)
  set(11, spec.held and 1 or 0)                            -- a held note ends when it is let go
  set(17, spec.soft / 127)
  set(18, spec.hard / 127)
  set(20, #spec.files > 1 and 1 or 0)                      -- several recordings take turns
  if spec.loop then
    set(12, 1)                                             -- a held note goes round a stretch of the recording
    set(23, spec.loop / 30000)                             -- from here, in milliseconds
    set(14, spec["until"] or 1)                            -- to here, as a part of the whole recording
    set(22, (spec.cross or 60) / 1000)                     -- blending this long where it joins
  end
  return fx
end

local function plugin(tr, spec)
  local fx = reaper.TrackFX_AddByName(tr, spec.name, false, -1)
  if fx < 0 then error("no plug-in called " .. spec.name) end
  if spec.chunk then
    local key = spec.kind == "clap" and "clap_chunk" or "vst_chunk"
    if not reaper.TrackFX_SetNamedConfigParm(tr, fx, key, spec.chunk) then error("could not set the state of " .. spec.name) end
  end
  for _, each in ipairs(spec.named or {}) do               -- in the order given: some effects are told things step by step
    if not reaper.TrackFX_SetNamedConfigParm(tr, fx, each[1], tostring(each[2])) then
      error(spec.name .. " would not take the setting " .. each[1] .. " = " .. tostring(each[2]))
    end
  end
  for index, value in pairs(spec.params or {}) do
    reaper.TrackFX_SetParamNormalized(tr, fx, index, value)
  end
  for index, value in pairs(spec.values or {}) do
    reaper.TrackFX_SetParam(tr, fx, index, value)
  end
  return fx
end

for _, spec in ipairs(job.tracks) do
  local ok, problem = pcall(function()
    local index = reaper.CountTracks(0)
    reaper.InsertTrackAtIndex(index, false)
    local tr = reaper.GetTrack(0, index)
    reaper.GetSetMediaTrackInfo_String(tr, "P_NAME", spec.name, true)
    for _, each in ipairs(spec.fx) do
      if each.kind == "sampler" then sampler(tr, each) else plugin(tr, each) end
    end
    if spec.describe then
      -- For finding out what a plug-in's settings are called.
      for fx = 0, reaper.TrackFX_GetCount(tr) - 1 do
        local _, name = reaper.TrackFX_GetFXName(tr, fx, "")
        say("  [" .. spec.name .. "] fx " .. fx .. ": " .. name)
        for param = 0, math.min(reaper.TrackFX_GetNumParams(tr, fx), spec.describe) - 1 do
          local _, label = reaper.TrackFX_GetParamName(tr, fx, param, "")
          local value, low, high = reaper.TrackFX_GetParam(tr, fx, param)
          local _, shown = reaper.TrackFX_GetFormattedParamValue(tr, fx, param, "")
          say(string.format("     %3d %-34s %.5f [%.3f..%.3f] '%s'", param, label, value, low, high, shown))
        end
      end
    end
    local got, chunk = reaper.GetTrackStateChunk(tr, "", false)
    if not got then error("the track's state could not be read") end
    local file = assert(io.open(job.out .. "/" .. spec.name .. ".RTrackTemplate", "w"))
    file:write(chunk)
    file:close()
    say("built " .. spec.name .. " (" .. #spec.fx .. " effects)")
    reaper.DeleteTrack(tr)
  end)
  if not ok then
    failed = failed + 1
    say("FAILED " .. spec.name .. ": " .. tostring(problem))
  end
end
say(failed == 0 and "all built" or (failed .. " failed"))
log:close()
local done = io.open(job.out .. "/make_tracks.done", "w")
done:write(failed == 0 and "ok\n" or "failed\n")
done:close()
