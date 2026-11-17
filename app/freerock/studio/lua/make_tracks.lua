-- Builds instruments as REAPER tracks and saves each as a track template.
--
-- Run by freerock.studio.desk with REAPER on a virtual display. FREEROCK_JOB names a Lua file
-- that returns what to build:
--
--   return { out = "<folder>", tracks = {
--     { name = "violins long", fx = {
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

local function plugin(tr, spec)
  local fx = reaper.TrackFX_AddByName(tr, spec.name, false, -1)
  if fx < 0 then error("no plug-in called " .. spec.name) end
  if spec.preset then
    if not reaper.TrackFX_SetPreset(tr, fx, spec.preset) then error(spec.name .. " has no preset called " .. spec.preset) end
  end
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
      plugin(tr, each)
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
