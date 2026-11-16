-- Writes down every plug-in REAPER has found, one to a line: its name as REAPER shows it, a tab,
-- and how REAPER identifies it. Run by freerock.studio.desk.plugins with FREEROCK_OUT naming
-- the file to write.
local out = os.getenv("FREEROCK_OUT")
local file = assert(io.open(out, "w"))
local index = 0
while true do
  local found, name, ident = reaper.EnumInstalledFX(index)
  if not found then break end
  file:write(name .. "\t" .. ident .. "\n")
  index = index + 1
end
file:close()
local done = io.open(out .. ".done", "w")
done:write(index .. "\n")
done:close()
