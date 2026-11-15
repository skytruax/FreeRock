-- FreeRock against Blizzard's real Forever interface code, in the wow-ui-sim simulator.
-- Run with tools/sim/run.sh (it copies this folder into a scratch copy of the addon).
--
-- Unlike tools/tests, nothing here is a model written for FreeRock: frames, textures, scaling, the
-- settings panel and the console variables are the simulator's and Blizzard's own. What the
-- simulator cannot show is the game itself: whether the real client reports weather, and what a
-- screen copy of the strip looks like.
local ns = FreeRock

-- The simulator has no C_Weather; the Forever client does. This stands in for it. The addon looks
-- the function up each time it reads the weather, so defining it after load is enough.
local weather = { type = 1, intensity = 0.5 }
C_Weather = { GetCurrentWeather = function() return weather end }

-- Every protected call the client refused while a test ran.
local refused = {}
local watcher = CreateFrame("Frame")
watcher:RegisterEvent("ADDON_ACTION_BLOCKED")
watcher:RegisterEvent("ADDON_ACTION_FORBIDDEN")
watcher:SetScript("OnEvent", function(_, event, addon, what)
	refused[#refused + 1] = event .. ": " .. tostring(addon) .. " " .. tostring(what)
end)

local function NothingWrong()
	assertEquals("", table.concat(refused, " | "))
	local problems = {}
	for _, problem in ipairs(ns.GetProblems()) do
		problems[#problems + 1] = problem.text
	end
	assertEquals("", table.concat(problems, " | "))
end

local function Flag(frame, bit)
	return math.floor(frame.flags / 2 ^ bit) % 2 == 1
end

-- Lets the strip's timer run: a poll of the game and a redraw. The simulator's clock only moves
-- when told to.
local clockIsOurs = false
local function Pass(seconds)
	if not clockIsOurs then
		A_Admin.SetManualClock(GetTime())
		clockIsOurs = true
	end
	for _ = 1, math.floor(seconds * 10 + 0.5) do
		A_Admin.AdvanceTime(0.1)
	end
end

local function Settle()
	Pass(0.4)
end

test("FreeRock loaded, is on, and nothing was refused or went wrong at login", function()
	assertNotNil(ns)
	assertTrue(FreeRockDB.enabled)
	assertNotNil(FreeRockStrip)
	assertTrue(FreeRockStrip:IsShown())
	NothingWrong()
	-- The simulator lacks one event the Forever client has. It is skipped, not an error, and every
	-- other event FreeRock listens for was registered with Blizzard's own event system.
	assertEquals("WEATHER_CHANGED", table.concat(ns.missingEvents, ", "))
end)

test("the strip is laid out pixel for pixel on the real frame system", function()
	local width, height = GetPhysicalScreenSize()
	-- One unit of the strip frame, in screen pixels.
	local pixels = FreeRockStrip:GetEffectiveScale() * height / 768
	assertAlmostEquals(1, pixels, 0.0001)
	assertAlmostEquals(344 * 3 + 4, FreeRockStrip:GetWidth(), 0.001)
	assertAlmostEquals(2 * 3 + 4, FreeRockStrip:GetHeight(), 0.001)
	assertEquals("TOOLTIP", FreeRockStrip:GetFrameStrata())
	local point, relativeTo, relativePoint, x, y = FreeRockStrip:GetPoint(1)
	assertEquals("TOPLEFT", point)
	assertEquals("TOPLEFT", relativePoint)
	assertAlmostEquals(16, x, 0.001)
	assertAlmostEquals(0, y, 0.001)
	-- The strip does not hang off the interface root, whose scale the player can change.
	assertTrue(FreeRockStrip:GetParent() ~= UIParent)
	assertTrue(width >= 344 * 3 + 4 + 16)
	NothingWrong()
end)

test("the squares on screen are the squares of the frame, on real textures", function()
	Settle()
	local bytes = ns.Beacon.Pack(ns.Beacon.BuildFrame())
	local regions = { FreeRockStrip:GetRegions() }
	assertEquals(1 + 2 * 340, #regions)
	local index = 1 -- the first region is the black backing
	for row = 0, 1 do
		local squares = ns.Beacon.Squares(bytes, row)
		for i = 1, 340 do
			index = index + 1
			assertEquals(squares[2 + i] == 1, regions[index]:IsShown())
		end
	end
	local first = regions[2]
	assertAlmostEquals(3, first:GetWidth(), 0.001)
	assertAlmostEquals(3, first:GetHeight(), 0.001)
	NothingWrong()
end)

test("a frame is 40 bytes and its checksum holds", function()
	local bytes = ns.Beacon.Pack(ns.Beacon.BuildFrame())
	assertEquals(40, #bytes)
	assertEquals(bytes[39] * 256 + bytes[40], ns.Beacon.Crc16(bytes, 38))
	assertEquals(0x20, bytes[1]) -- strip version 2, a state frame
	local check = { ("123456789"):byte(1, -1) }
	assertEquals(0x29B1, ns.Beacon.Crc16(check, #check))
end)

test("the game's own music is switched off while FreeRock is on, and put back when it is turned off", function()
	local mine = FreeRockDB.cvarBackup.Sound_EnableMusic
	assertEquals("0", C_CVar.GetCVar("Sound_EnableMusic"))
	SlashCmdList.FREEROCK("off")
	assertEquals(mine or "0", C_CVar.GetCVar("Sound_EnableMusic"))
	assertFalse(FreeRockDB.enabled)
	SlashCmdList.FREEROCK("on")
	assertEquals("0", C_CVar.GetCVar("Sound_EnableMusic"))
	assertTrue(FreeRockStrip:IsShown())
	NothingWrong()
end)

test("what the simulator's game says is what the frame carries", function()
	A_Admin.SetZone("Westfall", 40)
	A_Admin.SetSubZone("Sentinel Hill")
	A_Admin.FireEvent("ZONE_CHANGED_NEW_AREA")
	local state = ns.Signals.state
	assertEquals(GetRealZoneText(), state.zone)
	assertEquals(GetSubZoneText(), state.subzone)
	assertEquals("Westfall", state.zone)
	assertEquals("Sentinel Hill", state.subzone)
	assertEquals(C_Map.GetBestMapForUnit("player") or 0, state.mapID)

	A_Admin.SetResting(true)
	A_Admin.FireEvent("PLAYER_UPDATE_RESTING")
	assertTrue(Flag(ns.Beacon.BuildFrame(), 2))
	A_Admin.SetResting(false)
	A_Admin.FireEvent("PLAYER_UPDATE_RESTING")
	assertFalse(Flag(ns.Beacon.BuildFrame(), 2))

	-- Swimming has no event: the five-times-a-second poll has to find it.
	A_Admin.SetSwimming(true)
	Settle()
	assertEquals(IsSwimming() and true or false, Flag(ns.Beacon.BuildFrame(), 3))
	assertTrue(Flag(ns.Beacon.BuildFrame(), 3))
	A_Admin.SetSwimming(false)
	Settle()
	assertFalse(Flag(ns.Beacon.BuildFrame(), 3))

	local hour, minute = GetGameTime()
	assertEquals(hour * 60 + minute, ns.Beacon.BuildFrame().game_minutes)
	NothingWrong()
end)

test("combat shows on the event and clears afterwards", function()
	A_Admin.SetInCombat(true)
	Settle()
	assertTrue(Flag(ns.Beacon.BuildFrame(), 10))
	A_Admin.SetInCombat(false)
	Settle()
	assertFalse(Flag(ns.Beacon.BuildFrame(), 10))
	NothingWrong()
end)

test("weather is read when the client has the function, here a stand-in", function()
	-- The simulator has no WEATHER_CHANGED event either, so this goes by the two-second timer,
	-- which is also what covers for the event in the game should it never fire.
	Pass(2.2)
	local frame = ns.Beacon.BuildFrame()
	assertTrue(Flag(frame, 16))
	assertEquals(1, frame.weather_kind)
	assertEquals(500, frame.weather_intensity)
	weather = nil
	Pass(2.2)
	frame = ns.Beacon.BuildFrame()
	assertFalse(Flag(frame, 16))
	assertEquals(15, frame.weather_kind)
	weather = { type = 1, intensity = 0.5 }
	NothingWrong()
end)

test("day or night comes from the client's own function", function()
	local frame = ns.Beacon.BuildFrame()
	if C_DateAndTime and C_DateAndTime.IsDayTime then
		assertTrue(Flag(frame, 15))
		assertEquals(C_DateAndTime.IsDayTime() and true or false, Flag(frame, 14))
	else
		assertFalse(Flag(frame, 15))
	end
end)

test("the settings page opens on Blizzard's settings panel and its controls work", function()
	SlashCmdList.FREEROCK("")
	local panel = ns.Options.panel
	assertTrue(panel.built)
	assertTrue(panel:IsShown())
	HideUIPanel(SettingsPanel)
	SlashCmdList.FREEROCK("volume 40")
	assertEquals(40, FreeRockDB.volume)
	assertEquals(40, ns.Beacon.BuildFrame().volume)
	SlashCmdList.FREEROCK("strip size 4")
	assertAlmostEquals(344 * 4 + 4, FreeRockStrip:GetWidth(), 0.001)
	SlashCmdList.FREEROCK("strip bottom")
	local point = FreeRockStrip:GetPoint(1)
	assertEquals("BOTTOMLEFT", point)
	SlashCmdList.FREEROCK("strip top")
	SlashCmdList.FREEROCK("strip size 3")
	NothingWrong()
end)

test("/rock status, /rock test and the commands run without error", function()
	SlashCmdList.FREEROCK("status")
	SlashCmdList.FREEROCK("test")
	Settle()
	assertEquals(1, ns.Beacon.BuildFrame().kind)
	local count = FreeRockDB.commandCount
	SlashCmdList.FREEROCK("skip")
	assertEquals((count + 1) % 256, FreeRockDB.commandCount)
	NothingWrong()
end)

test("the strip goes when the interface is hidden and comes back with it, on the real interface root", function()
	Settle()
	assertTrue(FreeRockStrip:IsShown())
	UIParent:Hide() -- what Alt-Z and SetUIVisibility(false) do
	Settle()
	assertFalse(FreeRockStrip:IsShown())
	UIParent:Show()
	Settle()
	assertTrue(FreeRockStrip:IsShown())
	NothingWrong()
end)

test("a faint strip of one-pixel squares is drawn on real textures", function()
	SlashCmdList.FREEROCK("strip faint")
	SlashCmdList.FREEROCK("strip size 1")
	Settle()
	local regions = { FreeRockStrip:GetRegions() }
	local first = regions[2]
	assertAlmostEquals(1, first:GetWidth(), 0.001)
	local r, g, b = first:GetVertexColor()
	assertEquals(20, FreeRockDB.ink)
	assertEquals(1, FreeRockDB.cell)
	local scale = FreeRockStrip:GetEffectiveScale()
	local _, screenHeight = GetPhysicalScreenSize()
	assertAlmostEquals(344 + 4, FreeRockStrip:GetWidth() * scale * screenHeight / 768, 0.01)
	SlashCmdList.FREEROCK("strip bright")
	SlashCmdList.FREEROCK("strip size 3")
	assertEquals(100, FreeRockDB.ink)
	NothingWrong()
end)

test("speed and the target come from the client's own functions without error", function()
	Pass(11) -- past the ten seconds of test pattern an earlier test asked for
	local frame = ns.Beacon.BuildFrame()
	assertEquals(0, frame.kind)
	local speed = GetUnitSpeed("player")
	assertEquals(math.min(math.floor(speed * 2 + 0.5), 254), frame.speed)
	assertEquals(UnitExists("target") and UnitCanAttack("player", "target") or false, Flag(frame, 23))
	SlashCmdList.FREEROCK("status")
	NothingWrong()
end)
