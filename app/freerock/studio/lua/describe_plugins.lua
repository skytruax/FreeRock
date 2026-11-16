-- Loads each of a list of plug-ins once and writes down how REAPER keeps it in a project: its
-- name, how it is identified, and its settings with the values it starts with.
--
-- Run by freerock.studio.desk.catalogue. FREEROCK_JOB names a Lua file that returns
-- { out = "<folder>", names = { "LV2: Dragonfly Hall Reverb (Michael Willis and Rob vd Berg)", ... } }.
-- For each name, <out>/<number>.chunk is the plug-in as REAPER writes it, and <out>/describe.log
-- says which were found. A line is written BEFORE each plug-in is loaded, so that if one of them
-- brings REAPER down, the log says which.
local job = dofile(os.getenv("FREEROCK_JOB"))
local log = io.open(job.out .. "/describe.log", "a")
reaper.InsertTrackAtIndex(0, false)
local tr = reaper.GetTrack(0, 0)
for number, name in ipairs(job.names) do
  log:write("loading\t" .. number .. "\t" .. name .. "\n"); log:flush()
  local fx = reaper.TrackFX_AddByName(tr, name, false, -1)
  if fx < 0 then
    log:write("missing\t" .. number .. "\t" .. name .. "\n")
  else
    local _, chunk = reaper.GetTrackStateChunk(tr, "", false)
    local file = io.open(job.out .. "/" .. (job.first + number - 1) .. ".chunk", "w")
    file:write(chunk)
    file:close()
    log:write("done\t" .. number .. "\t" .. name .. "\n")
    reaper.TrackFX_Delete(tr, fx)
  end
  log:flush()
end
log:close()
local done = io.open(job.out .. "/describe.done", "w")
done:write("ok\n")
done:close()
