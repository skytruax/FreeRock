-- A stand-in for the parts of the World of Warcraft: Forever client that FreeRock touches, so the
-- addon's Lua can be run and checked without the game. It is a model written for these tests, not
-- Blizzard's code: it answers the documented functions FreeRock calls from one table (Mock.game)
-- that a test can change, keeps frames and textures as plain tables so a test can see what was
-- drawn, and moves time forward only when a test says so.
--
-- What it cannot show: whether the real client behaves the same. The names used here are checked
-- against the client's own lists by tools/sim (api_lint), and the addon is also loaded beside
-- Blizzard's real interface code there.
Mock = {}
local M = Mock

M.time = 1000          -- GetTime()
M.printed = {}         -- every line the addon printed, colour codes included
M.luaErrors = {}       -- every error handed to the game's error handler
M.sealedTouched = 0    -- how often addon code did something with a sealed value
M.screen = { 2560, 1440 }
M.uiScale = 0.71       -- the interface scale; the strip must not depend on it
M.cvars = { Sound_EnableMusic = "1", Sound_EnableAmbience = "1" }
M.refuseCVars = false  -- when true the game ignores SetCVar, as it does for a locked variable
M.secretRestrictions = true

-- What the game would answer right now.
M.game = {
	zone = "Elwynn Forest", realZone = "Elwynn Forest", subzone = "Goldshire", mapID = 1429,
	x = 0.42, y = 0.653,
	indoors = false, resting = false, swimming = false, submerged = false, mounted = false,
	flying = false, taxi = false, stealth = false, dead = false, ghost = false, combat = false,
	lockdown = false,
	inInstance = false, instanceKind = "none", instanceName = "Eastern Kingdoms", difficulty = 0, instanceID = 0,
	encounter = false,
	target = nil,          -- nil for no target, else the classification string
	boss = false, group = false,
	pvp = "friendly",      -- nil makes the function return nothing
	weather = { type = 0, intensity = 0 },  -- what C_Weather.GetCurrentWeather returns
	hasWeather = true,     -- false: the client has no C_Weather at all
	day = true,
	hasDay = true,
	hour = 14, minute = 35,
}
-- Names of answers that come back sealed, e.g. M.sealed.classification = true.
M.sealed = {}

---------------------------------------------------------------------------
-- Sealed values
---------------------------------------------------------------------------
-- A sealed value may be stored and passed on, nothing else. Whatever else is done with one is
-- counted, and a test that expects the addon to leave sealed values alone checks the count.
local SEALED = {}
local function touched()
	M.sealedTouched = M.sealedTouched + 1
	error("attempt to use a sealed value", 2)
end
for _, name in ipairs({ "__index", "__newindex", "__call", "__concat", "__add", "__sub", "__mul", "__div",
	"__mod", "__pow", "__unm", "__lt", "__le", "__tostring" }) do
	SEALED[name] = touched
end
local function Seal(value)
	return setmetatable({ hidden = value }, SEALED)
end
local function Answer(key, value)
	if M.sealed[key] then
		return Seal(value)
	end
	return value
end

local plainType = type
function issecretvalue(value)
	return plainType(value) == "table" and getmetatable(value) == SEALED
end
-- Asking what kind of thing a sealed value is counts as using it here. Code that does so goes on
-- to compare or look the value up, which the game refuses; FreeRock is meant to ask
-- issecretvalue first and drop the value.
function type(value)
	if issecretvalue(value) then
		M.sealedTouched = M.sealedTouched + 1
		return plainType(value.hidden)
	end
	return plainType(value)
end
C_Secrets = {
	HasSecretRestrictions = function() return M.secretRestrictions end,
}

---------------------------------------------------------------------------
-- Lua helpers Blizzard's interface code provides
---------------------------------------------------------------------------
function strtrim(text) return (text:gsub("^%s+", ""):gsub("%s+$", "")) end
function strsplit(separator, text)
	local parts = {}
	for part in (text .. separator):gmatch("(.-)" .. separator:gsub("%p", "%%%0")) do
		parts[#parts + 1] = part
	end
	return unpack(parts)
end
function wipe(t) for key in pairs(t) do t[key] = nil end return t end
function CopyTable(t)
	local copy = {}
	for key, value in pairs(t) do copy[key] = type(value) == "table" and CopyTable(value) or value end
	return copy
end

-- The client's xpcall passes extra arguments on to the function; plain Lua 5.1's does not.
local plainXpcall = xpcall
function xpcall(fn, handler, ...)
	local count, arguments = select("#", ...), { ... }
	return plainXpcall(function() return fn(unpack(arguments, 1, count)) end, handler)
end

local realPrint = print
function print(...)
	local parts = {}
	for i = 1, select("#", ...) do parts[i] = tostring((select(i, ...))) end
	M.printed[#M.printed + 1] = table.concat(parts, " ")
end
M.realPrint = realPrint

local errorHandler = function(message)
	M.luaErrors[#M.luaErrors + 1] = tostring(message)
end
function geterrorhandler() return errorHandler end

function GetTime() return M.time end
function GetBuildInfo() return "1.60.1", "70938", "Nov 13 2026", 16001 end
function GetPhysicalScreenSize() return M.screen[1], M.screen[2] end

C_AddOns = {
	GetAddOnMetadata = function(_, field) return field == "Version" and "0.1.0-test" or nil end,
}

C_CVar = {
	GetCVar = function(name) return M.cvars[name] end,
	SetCVar = function(name, value)
		if M.cvars[name] == nil or M.refuseCVars then
			return
		end
		M.cvars[name] = tostring(value)
		return true
	end,
}

---------------------------------------------------------------------------
-- The game's answers
---------------------------------------------------------------------------
function GetZoneText() return Answer("zone", M.game.zone) end
function GetRealZoneText() return Answer("zone", M.game.realZone) end
function GetSubZoneText() return Answer("subzone", M.game.subzone) end
function IsInInstance() return M.game.inInstance, M.game.instanceKind end
function GetInstanceInfo()
	local g = M.game
	return g.instanceName, g.instanceKind, g.difficulty, "", 5, 0, false, g.instanceID, 5, nil, false
end
function IsIndoors() return M.game.indoors end
function IsResting() return M.game.resting end
function IsSwimming() return M.game.swimming end
function IsSubmerged() return M.game.submerged end
function IsMounted() return M.game.mounted end
function IsFlying() return M.game.flying end
function IsStealthed() return M.game.stealth end
function InCombatLockdown() return M.game.lockdown end
function GetGameTime() return M.game.hour, M.game.minute end

local function OnlyPlayer(unit, what)
	if unit ~= "player" then error(what .. " asked about " .. tostring(unit), 3) end
end
function UnitOnTaxi(unit) OnlyPlayer(unit, "UnitOnTaxi") return M.game.taxi end
function UnitIsDeadOrGhost(unit) OnlyPlayer(unit, "UnitIsDeadOrGhost") return M.game.dead or M.game.ghost end
function UnitIsGhost(unit) OnlyPlayer(unit, "UnitIsGhost") return M.game.ghost end
function UnitAffectingCombat(unit) OnlyPlayer(unit, "UnitAffectingCombat") return M.game.combat end
function UnitInParty(unit) OnlyPlayer(unit, "UnitInParty") return M.game.group end
function UnitExists(unit)
	if unit == "target" then return M.game.target ~= nil end
	if unit == "boss1" then return M.game.boss end
	error("UnitExists asked about " .. tostring(unit), 2)
end
function UnitClassification(unit)
	if unit ~= "target" then error("UnitClassification asked about " .. tostring(unit), 2) end
	return Answer("classification", M.game.target)
end
-- Sealed in the real client in combat. FreeRock must never call these.
function UnitHealth() error("FreeRock asked for a unit's health", 2) end
function UnitHealthMax() error("FreeRock asked for a unit's health", 2) end
function UnitName() error("FreeRock asked for a unit's name", 2) end
function UnitGUID() error("FreeRock asked for a unit's identity", 2) end
function UnitThreatSituation() error("FreeRock asked for threat", 2) end

C_Map = {
	GetBestMapForUnit = function(unit)
		OnlyPlayer(unit, "C_Map.GetBestMapForUnit")
		return M.game.mapID
	end,
	GetPlayerMapPosition = function(mapID, unit)
		OnlyPlayer(unit, "C_Map.GetPlayerMapPosition")
		if mapID ~= M.game.mapID then error("position asked for map " .. tostring(mapID), 2) end
		if M.game.x == nil then return nil end
		local x, y = M.game.x, M.game.y
		return { x = x, y = y, GetXY = function() return x, y end }
	end,
}
C_PvP = {
	GetZonePVPInfo = function()
		if M.game.pvp == nil then return end
		return M.game.pvp, false, nil
	end,
}
C_InstanceEncounter = {
	IsEncounterInProgress = function() return M.game.encounter end,
}
C_Weather = {
	GetCurrentWeather = function() return Answer("weather", M.game.weather) end,
}
C_DateAndTime = {
	IsDayTime = function() return M.game.day end,
}
-- A test changes M.game.hasWeather / hasDay and calls this to make the functions come or go.
local weatherApi, dayApi = C_Weather, C_DateAndTime
function M.SyncApis()
	C_Weather = M.game.hasWeather and weatherApi or nil
	C_DateAndTime = M.game.hasDay and dayApi or nil
end

---------------------------------------------------------------------------
-- Frames, textures and text
---------------------------------------------------------------------------
M.frames = {}       -- every frame, in order of creation
M.events = {}       -- event -> list of frames registered for it
M.unknownEvents = {} -- events this pretend client does not have; registering one is an error, as in the game
C_EventUtils = {
	IsEventValid = function(event) return not M.unknownEvents[event] end,
}

local Region = {}
Region.__index = Region
function Region:SetPoint(point, a, b, c, d)
	local anchor
	if type(a) == "number" or a == nil and b == nil then
		anchor = { point = point, relativePoint = point, x = a or 0, y = b or 0 } -- SetPoint("TOPLEFT", x, y)
	else
		anchor = { point = point, relativeTo = a, relativePoint = b or point, x = c or 0, y = d or 0 }
	end
	self.points = self.points or {}
	self.points[#self.points + 1] = anchor
end
function Region:ClearAllPoints() self.points = {} end
function Region:SetAllPoints(target) self.points = {}; self.allPoints = target or true end
function Region:SetSize(width, height) self.width, self.height = width, height end
function Region:SetWidth(width) self.width = width end
function Region:SetHeight(height) self.height = height end
function Region:GetWidth() return self.width or 0 end
function Region:GetHeight() return self.height or 0 end
function Region:Show() self.shown = true end
function Region:Hide() self.shown = false end
function Region:SetShown(shown) self.shown = shown and true or false end
function Region:IsShown() return self.shown end
function Region:SetAlpha(alpha) self.alpha = alpha end
function Region:SetColorTexture(r, g, b, a) self.color = { r, g, b, a } end
function Region:SetText(text) self.text = text end
function Region:GetText() return self.text end
function Region:SetJustifyH() end
function Region:SetFontObject() end

local function NewRegion(kind, layer)
	return setmetatable({ kind = kind, layer = layer, shown = true }, Region)
end

local Frame = setmetatable({}, { __index = Region })
Frame.__index = Frame
function Frame:GetName() return self.name end
function Frame:GetParent() return self.parent end
function Frame:SetScale(scale) self.scale = scale end
function Frame:GetScale() return self.scale end
function Frame:GetEffectiveScale()
	return self.scale * (self.parent and self.parent:GetEffectiveScale() or 1)
end
function Frame:SetFrameStrata(strata) self.strata = strata end
function Frame:IsVisible()
	local frame = self
	while frame do
		if not frame.shown then return false end
		frame = frame.parent
	end
	return true
end
function Frame:RegisterEvent(event)
	if M.unknownEvents[event] then
		error(('Frame:RegisterEvent(): Attempt to register unknown event "%s"'):format(event), 2)
	end
	M.events[event] = M.events[event] or {}
	table.insert(M.events[event], self)
end
function Frame:SetScript(name, fn)
	self.scripts[name] = fn
end
function Frame:GetScript(name) return self.scripts[name] end
function Frame:Show()
	local was = self.shown
	self.shown = true
	if not was and self.scripts.OnShow then self.scripts.OnShow(self) end
end
function Frame:CreateTexture(_, layer)
	local texture = NewRegion("Texture", layer or "ARTWORK")
	self.textures[#self.textures + 1] = texture
	return texture
end
function Frame:CreateFontString()
	local text = NewRegion("FontString")
	self.fontStrings[#self.fontStrings + 1] = text
	return text
end
function Frame:SetChecked(checked) self.checked = checked and true or false end
function Frame:GetChecked() return self.checked end

function CreateFrame(kind, name, parent, template)
	local frame = setmetatable({
		kind = kind, name = name, parent = parent, template = template,
		scale = 1, shown = true, scripts = {}, textures = {}, fontStrings = {},
	}, Frame)
	if template == "UICheckButtonTemplate" then
		frame.Text = NewRegion("FontString")
	end
	if name then
		_G[name] = frame
	end
	M.frames[#M.frames + 1] = frame
	return frame
end

-- The root frames. The world frame has a plain scale of 1 and the interface root has the
-- interface scale; the screen is 768 units tall at scale 1.
WorldFrame = CreateFrame("Frame", "WorldFrame")
UIParent = CreateFrame("Frame", "UIParent")
UIParent.scale = M.uiScale
GameTooltip = CreateFrame("Frame", "GameTooltip")
function GameTooltip:SetOwner() end
function GameTooltip:AddLine() end

M.settings = { categories = {}, opened = nil }
Settings = {
	RegisterCanvasLayoutCategory = function(panel, name)
		local category = { panel = panel, name = name, id = #M.settings.categories + 1 }
		function category:GetID() return self.id end
		M.settings.categories[category.id] = category
		return category
	end,
	RegisterAddOnCategory = function(category) category.registered = true end,
	OpenToCategory = function(id)
		M.settings.opened = id
		M.settings.categories[id].panel:Show()
	end,
}
SlashCmdList = {}

---------------------------------------------------------------------------
-- Driving the client from a test
---------------------------------------------------------------------------
function M.Fire(event, ...)
	for _, frame in ipairs(M.events[event] or {}) do
		local handler = frame.scripts.OnEvent
		if handler then
			handler(frame, event, ...)
		end
	end
end

-- Lets seconds of game time pass, running every visible frame's OnUpdate script as the client
-- would, one drawn frame at a time (20 a second unless a test asks for another step).
function M.Advance(seconds, step)
	step = step or 0.05
	local steps = math.floor(seconds / step + 0.5)
	for _ = 1, steps do
		M.time = M.time + step
		for _, frame in ipairs(M.frames) do
			local handler = frame.scripts.OnUpdate
			if handler and frame:IsVisible() then
				handler(frame, step)
			end
		end
	end
end

function M.Slash(text)
	SlashCmdList.FREEROCK(text)
end

function M.Click(frame)
	if frame.kind == "CheckButton" then
		frame.checked = not frame.checked
	end
	frame.scripts.OnClick(frame, "LeftButton")
end

-- Where a frame's top left corner is on the screen and how big one of its units is, in screen
-- pixels. Only the anchors FreeRock uses are understood: a corner of the frame pinned to the same
-- corner of the world frame.
local function PixelsPerUnit(frame)
	return frame:GetEffectiveScale() * M.screen[2] / 768
end

function M.FrameBox(frame)
	local scale = PixelsPerUnit(frame)
	local anchor = frame.points[#frame.points]
	local width, height = frame.width * scale, frame.height * scale
	if anchor.relativeTo ~= WorldFrame then
		error("the strip is anchored to something other than the world frame", 2)
	end
	if anchor.point == "TOPLEFT" and anchor.relativePoint == "TOPLEFT" then
		return anchor.x * scale, -anchor.y * scale, width, height, scale
	elseif anchor.point == "BOTTOMLEFT" and anchor.relativePoint == "BOTTOMLEFT" then
		return anchor.x * scale, M.screen[2] - anchor.y * scale - height, width, height, scale
	end
	error("anchor " .. tostring(anchor.point) .. " is not modelled", 2)
end

-- Everything the strip frame draws, as rectangles in screen pixels with a grey level 0 to 1, in
-- drawing order (background first). Returns nil when the strip is not on screen. The numbers are
-- not rounded: a strip that is not laid out on whole pixels comes out blurred when the test
-- turns these rectangles into a picture, just as it would on a real screen.
function M.StripRects()
	local strip = _G.FreeRockStrip
	if not (strip and strip:IsVisible()) then
		return nil
	end
	local left, top, width, height, scale = M.FrameBox(strip)
	local rects = {}
	for _, layer in ipairs({ "BACKGROUND", "ARTWORK" }) do
		for _, texture in ipairs(strip.textures) do
			if texture.layer == layer and texture.shown then
				local rect
				if texture.allPoints then
					rect = { left, top, width, height }
				else
					local anchor = texture.points[#texture.points]
					if anchor.point ~= "TOPLEFT" or anchor.relativeTo ~= strip or anchor.relativePoint ~= "TOPLEFT" then
						error("a square is anchored in a way that is not modelled", 2)
					end
					rect = { left + anchor.x * scale, top - anchor.y * scale, texture.width * scale, texture.height * scale }
				end
				rect[5] = (texture.color[1] + texture.color[2] + texture.color[3]) / 3
				rects[#rects + 1] = rect
			end
		end
	end
	return rects
end
