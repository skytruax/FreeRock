local _, ns = ...

-- What is happening in the game, gathered from the game's documented functions and events into
-- one table. Beacon.lua turns that table into the strip.
--
-- Everything read here is something Blizzard's interface code does not mark as sealable. Health,
-- threat and the identity of other units are never read. If a value comes back sealed all the
-- same, ns.Plain turns it into "not known" before anything is done with it.
local Signals = {}
ns.Signals = Signals

local Plain = ns.Plain

local state = {
	mapID = 0,            -- the game's map number for the zone; 0 when it gives none
	zone = "",
	subzone = "",
	x = nil, y = nil,     -- position on the zone map, 0 to 1; nil where the game gives none (dungeons)
	speed = nil,          -- how fast the player is moving, in half yards a second; nil when not known
	inInstance = false,
	instanceKind = 0,     -- protocol number, see INSTANCE_KINDS
	instanceID = 0,
	instanceName = "",
	difficulty = 0,
	indoors = false, resting = false, swimming = false, submerged = false,
	mounted = false, flying = false, taxi = false, stealth = false,
	dead = false, ghost = false, combat = false,
	encounter = false, encounterID = 0, encounterName = "",
	hasTarget = false, targetClass = 0, targetHostile = false, bossPresent = false, inGroup = false,
	pvpKind = 0,
	weatherKnown = false, weatherKind = 15, weatherIntensity = nil,
	weatherRaw = "not read yet", -- exactly what the game answered, for /rock status
	dayKnown = false, day = false,
	minutes = nil,        -- game clock, minutes since midnight
	cinematic = false, loading = false,
}
Signals.state = state

-- The numbers the strip uses (protocol/beacon.md).
local INSTANCE_KINDS = { none = 0, party = 1, raid = 2, pvp = 3, arena = 4, scenario = 5 }
local TARGET_CLASSES = { normal = 1, elite = 2, rare = 3, rareelite = 4, worldboss = 5, trivial = 6, minus = 7 }
local PVP_KINDS = { sanctuary = 1, friendly = 2, contested = 3, hostile = 4, combat = 5, arena = 6 }
local OTHER = 15

Signals.MOMENT_LEVEL_UP = 1
Signals.MOMENT_BOSS_DEFEATED = 2
Signals.MOMENT_BOSS_LOST = 3
Signals.MOMENT_DIED = 4
Signals.MOMENT_QUEST = 5
Signals.MOMENT_ACHIEVEMENT = 6

local changed = false

local function Put(key, value)
	if state[key] ~= value then
		state[key] = value
		changed = true
	end
end

-- Tells the strip to redraw when a read changed something.
local function Flush()
	if changed then
		changed = false
		ns.Beacon:Touch()
	end
end

local function Text(value)
	value = Plain(value)
	return type(value) == "string" and value or ""
end

local function Whole(value)
	value = Plain(value)
	return type(value) == "number" and value >= 0 and value % 1 == 0 and value or 0
end

local function Flag(value)
	return Plain(value) and true or false
end

---------------------------------------------------------------------------
-- Readers
---------------------------------------------------------------------------
local function ReadZone()
	Put("mapID", Whole(C_Map.GetBestMapForUnit("player")))
	local zone = Text(GetRealZoneText())
	if zone == "" then
		zone = Text(GetZoneText())
	end
	Put("zone", zone)
	Put("subzone", Text(GetSubZoneText()))

	local inInstance, kind = IsInInstance()
	inInstance = Flag(inInstance)
	Put("inInstance", inInstance)
	if inInstance then
		local name, _, difficulty, _, _, _, _, instanceID = GetInstanceInfo()
		kind = Plain(kind)
		Put("instanceKind", type(kind) == "string" and INSTANCE_KINDS[kind] or OTHER)
		Put("instanceName", Text(name))
		Put("difficulty", Whole(difficulty))
		Put("instanceID", Whole(instanceID))
	else
		Put("instanceKind", 0)
		Put("instanceName", "")
		Put("difficulty", 0)
		Put("instanceID", 0)
	end

	local pvp = Plain((C_PvP.GetZonePVPInfo()))
	if pvp == nil then
		Put("pvpKind", 0)
	else
		Put("pvpKind", type(pvp) == "string" and PVP_KINDS[pvp] or OTHER)
	end
end

-- The strip sends position as a whole number out of 65534, so a move smaller than that is not a
-- change worth redrawing for.
local function Step(value)
	return math.floor(value * 65534 + 0.5)
end

local function ReadPosition()
	local x, y
	if state.mapID ~= 0 then
		local position = Plain(C_Map.GetPlayerMapPosition(state.mapID, "player"))
		if position ~= nil then
			x, y = position:GetXY()
			x, y = Plain(x), Plain(y)
			if type(x) ~= "number" or type(y) ~= "number" then
				x, y = nil, nil
			end
		end
	end
	if (x == nil) ~= (state.x == nil) or (x ~= nil and (Step(x) ~= Step(state.x) or Step(y) ~= Step(state.y))) then
		changed = true
	end
	state.x, state.y = x, y
end

-- How fast the player is moving: nothing standing, about 7 yards a second running, 14 on a
-- mount. The app brings the drums in with it. It is sent in half yards a second, so a change
-- smaller than that is not worth redrawing for; 254 half yards is faster than anything moves.
local function ReadSpeed()
	local speed = Plain((GetUnitSpeed("player")))
	if type(speed) == "number" and speed >= 0 then
		Put("speed", math.min(math.floor(speed * 2 + 0.5), 254))
	else
		Put("speed", nil)
	end
end

local function ReadFlags()
	Put("indoors", Flag(IsIndoors()))
	Put("resting", Flag(IsResting()))
	Put("swimming", Flag(IsSwimming()))
	Put("submerged", Flag(IsSubmerged()))
	Put("mounted", Flag(IsMounted()))
	Put("flying", Flag(IsFlying()))
	Put("taxi", Flag(UnitOnTaxi("player")))
	Put("stealth", Flag(IsStealthed()))
	Put("dead", Flag(UnitIsDeadOrGhost("player")))
	Put("ghost", Flag(UnitIsGhost("player")))
	Put("combat", Flag(InCombatLockdown()) or Flag(UnitAffectingCombat("player")))
	Put("bossPresent", Flag(UnitExists("boss1")))
	Put("inGroup", Flag(UnitInParty("player")))
end

local function ReadTarget()
	local has = Flag(UnitExists("target"))
	Put("hasTarget", has)
	if has then
		local class = Plain(UnitClassification("target"))
		Put("targetClass", type(class) == "string" and TARGET_CLASSES[class] or OTHER)
		-- Whether it is something to fight: the music leans in before the pull.
		Put("targetHostile", Flag(UnitCanAttack("player", "target")))
	else
		Put("targetClass", 0)
		Put("targetHostile", false)
	end
end

-- Boss encounters are announced by events, which carry the encounter's number and name. This
-- catches the two cases the events miss: a reload in the middle of a fight, and an end event
-- that never came.
local function ReadEncounter()
	local running = Flag(C_InstanceEncounter.IsEncounterInProgress())
	if running ~= state.encounter then
		Put("encounter", running)
		if not running then
			Put("encounterID", 0)
			Put("encounterName", "")
		end
	end
end

-- The weather function is documented but nothing in Blizzard's own interface calls it, so what it
-- really answers is only known from the game. Whatever comes back is kept word for word for
-- /rock status, and only an answer of the documented shape is sent on.
local function ReadWeather()
	local known, kind, intensity = false, OTHER, nil
	local raw
	if not (C_Weather and C_Weather.GetCurrentWeather) then
		raw = "this client has no weather function"
	else
		local info = C_Weather.GetCurrentWeather()
		if ns.IsSealed(info) then
			raw = "the game sealed the weather"
		elseif type(info) ~= "table" then
			raw = "the weather function answered " .. tostring(info)
		else
			local kindValue, amount = Plain(info.type), Plain(info.intensity)
			raw = ("type=%s intensity=%s"):format(tostring(kindValue), tostring(amount))
			if type(kindValue) == "number" and kindValue % 1 == 0 and kindValue >= 0 and kindValue < OTHER then
				known, kind = true, kindValue
				if type(amount) == "number" and amount >= 0 then
					intensity = amount
				end
			end
		end
	end
	Put("weatherKnown", known)
	Put("weatherKind", kind)
	Put("weatherIntensity", intensity)
	state.weatherRaw = raw
end

local function ReadDaylight()
	local day
	if C_DateAndTime and C_DateAndTime.IsDayTime then
		day = Plain(C_DateAndTime.IsDayTime())
	end
	if type(day) == "boolean" then
		Put("dayKnown", true)
		Put("day", day)
	else
		Put("dayKnown", false)
		Put("day", false)
	end
end

local function ReadClock()
	local hour, minute = GetGameTime()
	hour, minute = Plain(hour), Plain(minute)
	if type(hour) == "number" and type(minute) == "number" and hour >= 0 and hour < 24 and minute >= 0 and minute < 60 then
		Put("minutes", hour * 60 + minute)
	else
		Put("minutes", nil)
	end
end

local function ReadEverything()
	ReadZone()
	ReadPosition()
	ReadSpeed()
	ReadFlags()
	ReadTarget()
	ReadEncounter()
	ReadWeather()
	ReadDaylight()
	ReadClock()
end

---------------------------------------------------------------------------
-- One-off events ("moments") the app may want to mark with a sound
---------------------------------------------------------------------------
local function Moment(code)
	local db = ns.db
	db.moment = code
	db.momentCount = (db.momentCount + 1) % 256
	changed = true
end

---------------------------------------------------------------------------
-- Events
---------------------------------------------------------------------------
local function OnZone()
	ReadZone()
	ReadPosition()
	ReadFlags()
	ReadWeather()
	ReadDaylight()
	Flush()
end

local function OnFlags()
	ReadFlags()
	Flush()
end

local started = false

function Signals:Start()
	if started then
		return
	end
	started = true

	for _, event in ipairs({ "PLAYER_ENTERING_WORLD", "ZONE_CHANGED", "ZONE_CHANGED_INDOORS", "ZONE_CHANGED_NEW_AREA" }) do
		ns.On(event, OnZone)
	end
	for _, event in ipairs({ "PLAYER_UPDATE_RESTING", "UPDATE_STEALTH", "PLAYER_MOUNT_DISPLAY_CHANGED",
		"PLAYER_ALIVE", "PLAYER_UNGHOST", "GROUP_ROSTER_UPDATE", "INSTANCE_ENCOUNTER_ENGAGE_UNIT" }) do
		ns.On(event, OnFlags)
	end

	local function OnMoving()
		ReadSpeed()
		ReadPosition()
		Flush()
	end
	ns.On("PLAYER_STARTED_MOVING", OnMoving)
	ns.On("PLAYER_STOPPED_MOVING", OnMoving)

	ns.On("PLAYER_REGEN_DISABLED", function()
		Put("combat", true)
		Flush()
	end)
	ns.On("PLAYER_REGEN_ENABLED", OnFlags)

	ns.On("PLAYER_DEAD", function()
		Moment(Signals.MOMENT_DIED)
		ReadFlags()
		Flush()
	end)

	ns.On("ENCOUNTER_START", function(_, encounterID, encounterName)
		Put("encounter", true)
		Put("encounterID", Whole(encounterID))
		Put("encounterName", Text(encounterName))
		Flush()
	end)
	ns.On("ENCOUNTER_END", function(_, _, _, _, _, success)
		success = Plain(success)
		Put("encounter", false)
		Put("encounterID", 0)
		Put("encounterName", "")
		Moment((success == 1 or success == true) and Signals.MOMENT_BOSS_DEFEATED or Signals.MOMENT_BOSS_LOST)
		Flush()
	end)

	ns.On("PLAYER_TARGET_CHANGED", function()
		ReadTarget()
		Flush()
	end)
	ns.On("UNIT_CLASSIFICATION_CHANGED", function(_, unit)
		if Plain(unit) == "target" then
			ReadTarget()
			Flush()
		end
	end)

	ns.On("WEATHER_CHANGED", function()
		ReadWeather()
		Flush()
	end)
	ns.On("DIEL_CYCLE_CHANGED", function()
		ReadDaylight()
		Flush()
	end)

	local function Cinematic(on)
		return function()
			Put("cinematic", on)
			Flush()
		end
	end
	ns.On("CINEMATIC_START", Cinematic(true))
	ns.On("CINEMATIC_STOP", Cinematic(false))
	ns.On("PLAY_MOVIE", Cinematic(true))
	ns.On("STOP_MOVIE", Cinematic(false))

	ns.On("LOADING_SCREEN_ENABLED", function()
		Put("loading", true)
		Flush()
	end)
	ns.On("LOADING_SCREEN_DISABLED", function()
		Put("loading", false)
		ReadEverything()
		Flush()
	end)

	ns.On("PLAYER_LEVEL_UP", function()
		Moment(Signals.MOMENT_LEVEL_UP)
		Flush()
	end)
	ns.On("QUEST_TURNED_IN", function()
		Moment(Signals.MOMENT_QUEST)
		Flush()
	end)
	ns.On("ACHIEVEMENT_EARNED", function()
		Moment(Signals.MOMENT_ACHIEVEMENT)
		Flush()
	end)

	ReadEverything()
	Flush()
end

-- Called five times a second by the strip's timer while FreeRock is on. Several of these have no
-- event at all (position, indoors, swimming, under water, flying); the rest are read again so
-- that a missed event cannot leave the strip wrong for long. Every tenth call also reads the
-- slower things.
function Signals:Poll(everything)
	if everything then
		ReadEverything()
	else
		ReadPosition()
		ReadSpeed()
		ReadFlags()
		ReadTarget()
		ReadEncounter()
		ReadClock()
	end
	Flush()
end

---------------------------------------------------------------------------
-- /rock status
---------------------------------------------------------------------------
local WEATHER_NAMES = { [0] = "clear", "rain", "snow", "sandstorm", "miscellaneous" }

local function YesNo(value)
	return value and "yes" or "no"
end

function Signals:Describe()
	local lines = {}
	local function Add(text, ...)
		lines[#lines + 1] = text:format(...)
	end
	Add("Zone: %s (map %d). Subzone: %s.", state.zone ~= "" and state.zone or "none", state.mapID,
		state.subzone ~= "" and state.subzone or "none")
	if state.x then
		Add("Position: %.1f, %.1f.", state.x * 100, state.y * 100)
	else
		Add("Position: the game gives none here.")
	end
	if state.speed then
		Add("Speed: %.1f yards a second.", state.speed / 2)
	else
		Add("Speed: the game gives none.")
	end
	if state.inInstance then
		Add("Instance: %s (kind %d, number %d, difficulty %d).", state.instanceName, state.instanceKind,
			state.instanceID, state.difficulty)
	else
		Add("Instance: none.")
	end
	Add("Indoors %s, resting %s, swimming %s, under water %s, mounted %s, flying %s, flight path %s.",
		YesNo(state.indoors), YesNo(state.resting), YesNo(state.swimming), YesNo(state.submerged),
		YesNo(state.mounted), YesNo(state.flying), YesNo(state.taxi))
	Add("Stealth %s, dead %s, ghost %s, combat %s, group %s, cinematic %s, loading %s.",
		YesNo(state.stealth), YesNo(state.dead), YesNo(state.ghost), YesNo(state.combat),
		YesNo(state.inGroup), YesNo(state.cinematic), YesNo(state.loading))
	if state.encounter then
		Add("Boss encounter: %s (number %d). Boss unit present: %s.",
			state.encounterName ~= "" and state.encounterName or "name not given", state.encounterID,
			YesNo(state.bossPresent))
	else
		Add("Boss encounter: none. Boss unit present: %s.", YesNo(state.bossPresent))
	end
	Add("Target: %s (class %d), can be attacked: %s. Zone PvP kind %d.", YesNo(state.hasTarget), state.targetClass,
		YesNo(state.targetHostile), state.pvpKind)
	if state.weatherKnown then
		Add("Weather: %s, intensity %s. The game said: %s.", WEATHER_NAMES[state.weatherKind] or ("kind " .. state.weatherKind),
			state.weatherIntensity and ("%.3f"):format(state.weatherIntensity) or "not given", state.weatherRaw)
	else
		Add("Weather: not reported. The game said: %s.", state.weatherRaw)
	end
	Add("Daylight: %s.", state.dayKnown and (state.day and "day" or "night") or "not reported")
	if state.minutes then
		Add("Game clock: %02d:%02d.", math.floor(state.minutes / 60), state.minutes % 60)
	else
		Add("Game clock: not reported.")
	end
	return lines
end
