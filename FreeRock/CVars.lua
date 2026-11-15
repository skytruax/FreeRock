local _, ns = ...

-- The one console variable FreeRock changes: the game's own music is switched off while FreeRock
-- is on, because the FreeRock app plays the music instead. Ambience and sound effects are left
-- alone. The player's own value is remembered the first time the variable is changed and put back
-- at logout or when FreeRock is turned off, so removing the addon leaves the game as it was.
local CVars = {}
ns.CVars = CVars

-- { name, function(db) returning the value wanted, or nil to leave the variable alone }
local MANAGED = {
	{ "Sound_EnableMusic", function(db) return db.muteGameMusic and "0" or nil end },
}

-- Names this client does not have, kept for the status report.
CVars.missing = {}

-- Some variables are stored as "1.000000"; the same number is not a change.
local function Same(a, b)
	if a == b then
		return true
	end
	local x, y = tonumber(a), tonumber(b)
	return x ~= nil and x == y
end

-- Changes a variable and checks that the game took the change. The game can refuse (a locked or
-- protected variable) without raising an error, which would otherwise pass unnoticed.
local function Write(name, value)
	C_CVar.SetCVar(name, value)
	if not Same(C_CVar.GetCVar(name), value) then
		ns.Report(("The game did not accept %s = %s."):format(name, tostring(value)))
		return false
	end
	return true
end

local function Set(name, value)
	local current = C_CVar.GetCVar(name)
	if current == nil then
		CVars.missing[name] = true
		return
	end
	local db = ns.db
	if not Same(current, value) then
		if db.cvarBackup[name] == nil then
			db.cvarBackup[name] = current
		end
		if not Write(name, value) then
			db.cvarBackup[name] = nil
			return
		end
	end
	db.cvarApplied[name] = value
end

local function Release(name)
	local db = ns.db
	local backup, applied = db.cvarBackup[name], db.cvarApplied[name]
	db.cvarBackup[name], db.cvarApplied[name] = nil, nil
	-- If the player changed it again after we did, their newer choice stands.
	if backup ~= nil and Same(C_CVar.GetCVar(name), applied) then
		Write(name, backup)
	end
end

function CVars:Apply()
	wipe(self.missing)
	for _, entry in ipairs(MANAGED) do
		local name, wanted = entry[1], entry[2](ns.db)
		if wanted then
			Set(name, wanted)
		else
			Release(name)
		end
	end
end

function CVars:RestoreAll()
	for _, entry in ipairs(MANAGED) do
		Release(entry[1])
	end
end

-- For the status report: name, current value, and the player's own value where we changed it.
function CVars:Describe()
	local lines = {}
	for _, entry in ipairs(MANAGED) do
		local name = entry[1]
		local current = C_CVar.GetCVar(name)
		local note = ""
		if current == nil then
			note = " (not in this client)"
		elseif ns.db.cvarBackup[name] ~= nil then
			note = (" (yours: %s)"):format(ns.db.cvarBackup[name])
		end
		lines[#lines + 1] = ("%s = %s%s"):format(name, tostring(current), note)
	end
	return lines
end
