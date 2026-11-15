local ADDON, ns = ...

-- Exposed for /run debugging and for the tests. Blizzard code never reads it.
_G.FreeRock = ns

ns.name = ADDON
ns.version = C_AddOns.GetAddOnMetadata(ADDON, "Version") or "dev"

---------------------------------------------------------------------------
-- Saved settings
---------------------------------------------------------------------------
local DEFAULTS = {
	enabled = true,       -- FreeRock is on: the strip is drawn and the game's own music is off
	muteGameMusic = true, -- turn the game's own music off while FreeRock is on
	volume = 70,          -- how loud FreeRock should play, 0 to 100; the app reads it from the strip
	cell = 3,             -- size of one square of the strip, in screen pixels
	ink = 100,            -- how bright the strip's squares are drawn, in percent; lower is harder to see
	edge = "top",         -- top | bottom: the edge of the screen the strip runs along
	insetX = 16,          -- pixels in from the left edge of the screen
	insetY = 0,           -- pixels in from the top (or bottom) edge
	-- The last skip / love / ban and the last one-off event, with how many there have been. The
	-- app acts when a count changes, so the counts are kept between sessions (they wrap at 256).
	command = 0,
	commandCount = 0,
	moment = 0,
	momentCount = 0,
	cvarBackup = {},      -- the player's own value of every console variable we changed
	cvarApplied = {},     -- the value we changed it to
	introShown = false,
}
ns.DEFAULTS = DEFAULTS

local function CopyDefaults(dst, src)
	for key, value in pairs(src) do
		if type(value) == "table" then
			if type(dst[key]) ~= "table" then
				dst[key] = {}
			end
			CopyDefaults(dst[key], value)
		elseif dst[key] == nil then
			dst[key] = value
		end
	end
	return dst
end

local function IsOneOf(value, ...)
	for i = 1, select("#", ...) do
		if value == select(i, ...) then
			return true
		end
	end
	return false
end
ns.IsOneOf = IsOneOf

local function IsWhole(value, minimum, maximum)
	return type(value) == "number" and value % 1 == 0 and value >= minimum and value <= maximum
end

-- Saved variables are plain text the player can edit, and they outlive versions of this addon,
-- so anything out of range goes back to its default instead of breaking the strip later.
local function Sanitize(db)
	local function Reset(key)
		db[key] = DEFAULTS[key]
	end
	if type(db.enabled) ~= "boolean" then Reset("enabled") end
	if type(db.muteGameMusic) ~= "boolean" then Reset("muteGameMusic") end
	if type(db.introShown) ~= "boolean" then Reset("introShown") end
	if not IsWhole(db.volume, 0, 100) then Reset("volume") end
	if not IsWhole(db.cell, 1, 8) then Reset("cell") end
	if not IsWhole(db.ink, 10, 100) then Reset("ink") end
	if not IsOneOf(db.edge, "top", "bottom") then Reset("edge") end
	if not IsWhole(db.insetX, 0, 2000) then Reset("insetX") end
	if not IsWhole(db.insetY, 0, 500) then Reset("insetY") end
	if not IsWhole(db.command, 0, 3) then Reset("command") end
	if not IsWhole(db.commandCount, 0, 255) then Reset("commandCount") end
	if not IsWhole(db.moment, 0, 6) then Reset("moment") end
	if not IsWhole(db.momentCount, 0, 255) then Reset("momentCount") end
end

---------------------------------------------------------------------------
-- Output
---------------------------------------------------------------------------
local PREFIX = "|cffff8c1aFreeRock|r: "
function ns.Print(...)
	local parts = {}
	for i = 1, select("#", ...) do
		parts[i] = tostring((select(i, ...)))
	end
	print(PREFIX .. table.concat(parts, " "))
end

---------------------------------------------------------------------------
-- Sealed values
---------------------------------------------------------------------------
-- While the game's addon restrictions are in force (in combat, among other times) some of what
-- it tells an addon comes back sealed: a "secret" value that can be stored and passed on, but not
-- compared, calculated with or handed to most game functions. Doing any of that is an error on
-- the spot. FreeRock reads only things Blizzard's interface code does not mark as sealable, and
-- anything that comes back sealed all the same is treated as "not known". Nothing sealed goes
-- into the strip.
function ns.IsSealed(value)
	return issecretvalue ~= nil and issecretvalue(value)
end

-- The value, or nil when the game sealed it.
function ns.Plain(value)
	if ns.IsSealed(value) then
		return nil
	end
	return value
end

-- For /rock status: "yes", "no", or that this client cannot say.
function ns.DescribeSealing()
	local secrets = C_Secrets
	if not (secrets and secrets.HasSecretRestrictions) then
		return "this client does not say"
	end
	return secrets.HasSecretRestrictions() and "yes" or "no"
end

---------------------------------------------------------------------------
-- Errors
---------------------------------------------------------------------------
-- The game hides addon errors unless the player has switched them on, so an error in the code
-- that draws the strip would end that update without anyone seeing why. Code run through ns.Try
-- still hands every error to the game's own error handler, exactly as an uncaught one would be;
-- on top of that the first one is said in chat and they are kept for /rock status, so a problem
-- can be reported even with errors hidden. One failing handler does not stop the next.
local MAX_PROBLEMS = 8 -- different problems kept; repeats of a kept one are only counted
local problems = {}    -- { text = "...", count = n }, in order of first appearance
local problemByText = {}

-- Notes something that went wrong without a Lua error, such as the game refusing a setting.
function ns.Report(text)
	local problem = problemByText[text]
	if problem then
		problem.count = problem.count + 1
	elseif #problems < MAX_PROBLEMS then
		problem = { text = text, count = 1 }
		problems[#problems + 1] = problem
		problemByText[text] = problem
		if #problems == 1 then
			ns.Print("|cffff4040Something went wrong inside FreeRock|r, so the music may not follow the game. Type /rock status to see what.")
		end
	end
end

local function OnError(message)
	ns.Report(tostring(message))
	geterrorhandler()(message)
	return message
end

-- Runs fn(...). Returns true and what it returned, or false after reporting what went wrong.
function ns.Try(fn, ...)
	return xpcall(fn, OnError, ...)
end

function ns.GetProblems()
	return problems
end

-- The game refuses some calls from addons. That is not an error in Lua: the call simply does
-- nothing and the game announces it with one of these events, which nobody sees. They are kept
-- with the errors.
local function OnBlocked(_, addon, what)
	if addon == ADDON then
		ns.Report(("The game refused to let FreeRock call %s."):format(tostring(what)))
	end
end

---------------------------------------------------------------------------
-- Events: modules register handlers here, Core owns the single event frame
---------------------------------------------------------------------------
local eventFrame = CreateFrame("Frame")
local handlers = {}

-- Events this client turned out not to have, for /rock status. Registering for an event the
-- client does not know is an error, and that error would stop everything set up after it. The
-- client can be asked first, so it is. Nearly everything an event tells FreeRock is also read on
-- a timer, so a missing event makes a change show a little later rather than not at all.
ns.missingEvents = {}

function ns.On(event, fn)
	if not handlers[event] then
		if C_EventUtils and C_EventUtils.IsEventValid and not C_EventUtils.IsEventValid(event) then
			ns.missingEvents[#ns.missingEvents + 1] = event
			return
		end
		handlers[event] = {}
		eventFrame:RegisterEvent(event)
	end
	table.insert(handlers[event], fn)
end

eventFrame:SetScript("OnEvent", function(_, event, ...)
	for _, fn in ipairs(handlers[event]) do
		ns.Try(fn, event, ...)
	end
end)

ns.On("ADDON_ACTION_BLOCKED", OnBlocked)
ns.On("ADDON_ACTION_FORBIDDEN", OnBlocked)

---------------------------------------------------------------------------
-- Lifecycle
---------------------------------------------------------------------------
-- Applies every setting: the game's music setting, and the strip.
function ns.Refresh()
	if ns.db.enabled then
		ns.CVars:Apply()
	else
		ns.CVars:RestoreAll()
	end
	ns.Beacon:Apply()
	if ns.Options then
		ns.Options:Sync()
	end
end

ns.On("ADDON_LOADED", function(_, name)
	if name ~= ADDON then
		return
	end
	FreeRockDB = CopyDefaults(type(FreeRockDB) == "table" and FreeRockDB or {}, DEFAULTS)
	ns.db = FreeRockDB
	Sanitize(ns.db)
end)

ns.On("PLAYER_LOGIN", function()
	ns.Options:Create()
	ns.Signals:Start()
	ns.Refresh()
	if ns.db.enabled and not ns.db.introShown then
		ns.db.introShown = true
		ns.Print("FreeRock is on. It draws a thin line of squares along the top of the screen for the FreeRock app to read, and the game's own music is off while it is on. /rock off puts the game's music back; /rock opens the settings.")
	end
end)

-- Console variables are saved by the client on the way out, so the player's own values go back first.
ns.On("PLAYER_LOGOUT", function()
	ns.CVars:RestoreAll()
end)
