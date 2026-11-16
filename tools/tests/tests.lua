-- Scenarios for FreeRock, run against tools/tests/wowmock.lua. Each test gets a fresh Lua state.
local M = Mock
local ns

local function eq(actual, expected, what)
	if actual ~= expected then
		error(("%s: expected %s, got %s"):format(what or "value", tostring(expected), tostring(actual)), 2)
	end
end

local function truthy(value, what)
	if not value then error((what or "value") .. ": expected something true, got " .. tostring(value), 2) end
end

-- The addon runs in an environment that passes everything through to the real globals but notes
-- each name it reads or writes, so `run.py --globals` can list every client API it depends on.
GLOBAL_READS, GLOBAL_WRITES = {}, {}
TRACKED = setmetatable({}, {
	__index = function(_, key)
		GLOBAL_READS[key] = true
		return _G[key]
	end,
	__newindex = function(_, key, value)
		GLOBAL_WRITES[key] = true
		_G[key] = value
	end,
})

-- Loads the addon the way the client does: every file in the .toc, in order, sharing one table.
local function Load(saved)
	FreeRockDB = saved
	ns = {}
	for line in ReadFile("FreeRock/FreeRock.toc"):gmatch("[^\r\n]+") do
		if line ~= "" and not line:match("^#") then
			local chunk = assert(loadstring(ReadFile("FreeRock/" .. line), "@FreeRock/" .. line))
			setfenv(chunk, TRACKED)
			chunk("FreeRock", ns)
		end
	end
	M.Fire("ADDON_LOADED", "FreeRock")
	M.Fire("PLAYER_LOGIN")
	M.Fire("PLAYER_ENTERING_WORLD", true, false)
	return ns
end

local function Printed(pattern)
	for _, line in ipairs(M.printed) do
		if line:find(pattern) then return true end
	end
	return false
end

local function AllPrinted()
	return table.concat(M.printed, "\n")
end

-- Lets the strip's timer run: one poll of the game, and a redraw.
local function Settle()
	M.Advance(0.25)
end

-- The frame the strip is showing now.
local function Frame()
	Settle()
	return ns.Beacon.BuildFrame()
end

local function Flag(frame, bit)
	return math.floor(frame.flags / 2 ^ bit) % 2 == 1
end

-- The squares on screen right now, read back from the textures: per row a list of 0 and 1 for the
-- 340 drawn squares.
local function Drawn()
	local strip = FreeRockStrip
	local rows = { [0] = {}, [1] = {} }
	local index = 1 -- textures[1] is the black backing
	for row = 0, 1 do
		for i = 1, 340 do
			index = index + 1
			rows[row][i] = strip.textures[index].shown and 1 or 0
		end
	end
	return rows
end

TESTS = {}
local function test(name, fn)
	TESTS[#TESTS + 1] = {
		name = name,
		fn = function()
			fn()
			-- A test that expects errors says so; anywhere else an error is a failure.
			if not M.expectErrors and #M.luaErrors > 0 then
				error("the addon raised: " .. M.luaErrors[1], 0)
			end
			if not M.expectErrors and ns and #ns.GetProblems() > 0 then
				error("the addon reported: " .. ns.GetProblems()[1].text, 0)
			end
			eq(M.sealedTouched, 0, "times a sealed value was used")
		end,
	}
end

---------------------------------------------------------------------------
-- Format: the same vectors the Python reader is tested with
---------------------------------------------------------------------------
test("the checksum is CRC-16/CCITT-FALSE", function()
	Load()
	local bytes = { ("123456789"):byte(1, -1) }
	eq(ns.Beacon.Crc16(bytes, #bytes), VECTORS.crc_check.crc16, "check value")
	eq(VECTORS.crc_check.crc16, 0x29B1, "the published check value")
end)

test("every vector frame packs to the bytes in protocol/vectors.json", function()
	Load()
	truthy(#VECTORS.frames >= 5, "vectors loaded")
	for _, case in ipairs(VECTORS.frames) do
		local bytes = ns.Beacon.Pack(case.frame)
		eq(#bytes, VECTORS.payload_bytes, case.name .. ": length")
		for i = 1, #bytes do
			eq(bytes[i], case.payload[i], case.name .. ": byte " .. (i - 1))
		end
	end
end)

test("every vector frame lays out as the squares in protocol/vectors.json", function()
	Load()
	for _, case in ipairs(VECTORS.frames) do
		for row = 0, VECTORS.rows - 1 do
			local squares = ns.Beacon.Squares(case.payload, row)
			eq(#squares, VECTORS.row_squares, case.name .. ": squares in row " .. row)
			local drawn = {}
			for i, value in ipairs(squares) do drawn[i] = value == 1 and "#" or "." end
			eq(table.concat(drawn), case.squares[row + 1], case.name .. ": row " .. row)
		end
	end
end)

test("names are cut to 48 bytes without splitting a character, and marked as in the vectors", function()
	Load()
	for _, case in ipairs(VECTORS.names) do
		local bytes = ns.Beacon.TextBytes(case.text)
		eq(#bytes, #case.sent, "bytes sent for " .. case.text)
		for i = 1, #bytes do
			eq(bytes[i], case.sent[i], "byte " .. i .. " of " .. case.text)
		end
		eq(ns.Beacon.Mark(bytes), case.mark, "mark of " .. case.text)
	end
end)

---------------------------------------------------------------------------
-- Settings and the game's music
---------------------------------------------------------------------------
test("first login: on, strip up, game music off, one line of introduction", function()
	Load()
	eq(ns.db.enabled, true, "enabled")
	eq(M.cvars.Sound_EnableMusic, "0", "game music")
	eq(ns.db.cvarBackup.Sound_EnableMusic, "1", "the player's own value is kept")
	truthy(FreeRockStrip:IsVisible(), "strip visible")
	truthy(Printed("FreeRock is on"), "introduction")
	local lines = #M.printed
	-- The introduction is said once.
	M.printed = {}
	M.Fire("PLAYER_LOGIN")
	eq(#M.printed, 0, "lines at a second login")
	truthy(lines >= 1)
end)

test("/rock off puts the game's music back, says off in the strip, then takes the strip away", function()
	Load()
	M.Slash("off")
	eq(M.cvars.Sound_EnableMusic, "1", "game music after off")
	eq(ns.db.cvarBackup.Sound_EnableMusic, nil, "backup cleared")
	local frame = Frame()
	eq(Flag(frame, 0), false, "the strip says off")
	truthy(FreeRockStrip:IsVisible(), "still up to say so")
	M.Advance(3.5)
	eq(FreeRockStrip:IsVisible(), false, "strip gone")
	M.Slash("on")
	truthy(FreeRockStrip:IsVisible(), "strip back")
	eq(M.cvars.Sound_EnableMusic, "0", "game music off again")
	eq(Flag(Frame(), 0), true, "the strip says on")
end)

test("logging out puts the player's own music setting back", function()
	Load()
	eq(M.cvars.Sound_EnableMusic, "0")
	M.Fire("PLAYER_LOGOUT")
	eq(M.cvars.Sound_EnableMusic, "1", "game music at logout")
end)

test("if the player turns the game's music on themselves, their choice stands", function()
	Load()
	M.cvars.Sound_EnableMusic = "1" -- the player, in the sound options
	M.Slash("off")
	eq(M.cvars.Sound_EnableMusic, "1", "left as the player set it")
end)

test("a player who already had the game's music off keeps it off after FreeRock is turned off", function()
	M.cvars.Sound_EnableMusic = "0"
	Load()
	eq(ns.db.cvarBackup.Sound_EnableMusic, nil, "nothing to remember")
	M.Slash("off")
	eq(M.cvars.Sound_EnableMusic, "0", "still off")
end)

test("/rock gamemusic on leaves the game's music alone", function()
	Load()
	M.Slash("gamemusic on")
	eq(M.cvars.Sound_EnableMusic, "1", "game music")
	M.Slash("gamemusic off")
	eq(M.cvars.Sound_EnableMusic, "0", "game music")
end)

test("a game that refuses the music setting is reported, not ignored", function()
	M.expectErrors = true
	M.refuseCVars = true
	Load()
	eq(M.cvars.Sound_EnableMusic, "1", "the game kept its value")
	eq(#ns.GetProblems(), 1, "problems")
	truthy(ns.GetProblems()[1].text:find("did not accept Sound_EnableMusic"), "what was reported")
	truthy(Printed("Something went wrong inside FreeRock"), "said in chat")
	eq(ns.db.cvarBackup.Sound_EnableMusic, nil, "no backup of a change that did not happen")
end)

test("saved settings that are out of range go back to their defaults", function()
	Load({ enabled = "yes", volume = 400, cell = 0, ink = 5, edge = "left", insetX = -5, insetY = 9999,
		command = 9, commandCount = 300, moment = 2.5, momentCount = -1, muteGameMusic = 0 })
	eq(ns.db.enabled, true)
	eq(ns.db.volume, 70)
	eq(ns.db.cell, 3)
	eq(ns.db.ink, 100)
	eq(ns.db.edge, "top")
	eq(ns.db.insetX, 16)
	eq(ns.db.insetY, 0)
	eq(ns.db.command, 0)
	eq(ns.db.commandCount, 0)
	eq(ns.db.moment, 0)
	eq(ns.db.momentCount, 0)
	eq(ns.db.muteGameMusic, true)
end)

test("a setup saved as off stays off: no strip, game music untouched", function()
	Load({ enabled = false })
	eq(M.cvars.Sound_EnableMusic, "1", "game music")
	eq(FreeRockStrip:IsVisible(), false, "strip")
	eq(Printed("FreeRock is on"), false, "no introduction while off")
end)

---------------------------------------------------------------------------
-- The strip on screen
---------------------------------------------------------------------------
test("one square is a whole number of screen pixels whatever the interface scale", function()
	Load()
	local left, top, width, height, scale = M.FrameBox(FreeRockStrip)
	eq(scale, 1, "screen pixels per strip unit")
	eq(left, 16, "left edge")
	eq(top, 0, "top edge")
	eq(width, 344 * 3 + 4, "width in pixels")
	eq(height, 2 * 3 + 4, "height in pixels")
	-- A different screen and interface scale: still pixel for pixel.
	M.screen = { 3840, 2160 }
	UIParent.scale = 1.3
	M.Fire("DISPLAY_SIZE_CHANGED")
	left, top, width, height, scale = M.FrameBox(FreeRockStrip)
	eq(scale, 1, "screen pixels per strip unit at 2160p")
	eq(width, 344 * 3 + 4, "width in pixels at 2160p")
end)

test("the squares drawn are the squares of the frame", function()
	Load()
	M.game.indoors = true
	Settle()
	local bytes = ns.Beacon.Pack(ns.Beacon.BuildFrame())
	local drawn = Drawn()
	for row = 0, 1 do
		local squares = ns.Beacon.Squares(bytes, row)
		for i = 1, 340 do
			eq(drawn[row][i], squares[2 + i], "row " .. row .. " square " .. i)
		end
	end
	-- The finder, clock and end mark are there.
	eq(table.concat(drawn[0], "", 1, 10), "1111001010", "start of row 0")
	eq(table.concat(drawn[1], "", 335, 340), "001111", "end of row 1")
end)

test("/rock strip moves and resizes the strip", function()
	Load()
	M.Slash("strip bottom")
	local left, top, width, height = M.FrameBox(FreeRockStrip)
	eq(top, 1440 - height, "top when along the bottom")
	M.Slash("strip size 5")
	left, top, width, height = M.FrameBox(FreeRockStrip)
	eq(width, 344 * 5 + 4, "width at 5 px")
	eq(top, 1440 - height, "still along the bottom")
	M.Slash("strip inset 40 6")
	left, top, width, height = M.FrameBox(FreeRockStrip)
	eq(left, 40, "left")
	eq(top, 1440 - 6 - height, "top")
	M.Slash("strip top")
	left, top = M.FrameBox(FreeRockStrip)
	eq(top, 6, "top when along the top")
	truthy(Printed("Squares of 5 px"), "the strip is described after a change")
end)

test("the strip goes with the interface and comes back with it", function()
	Load()
	truthy(FreeRockStrip:IsVisible(), "strip up")
	UIParent:Hide()                -- what a hide-the-interface macro or Alt-Z does
	Settle()
	eq(FreeRockStrip:IsShown(), false, "hidden with the interface")
	M.Slash("status")
	truthy(Printed("Strip: hidden with the interface"), "status says why")
	M.Slash("strip size 4")        -- a setting changed meanwhile must not bring it back
	eq(FreeRockStrip:IsShown(), false, "still hidden after a setting changed")
	M.game.indoors = true          -- the game goes on while the interface is hidden
	Settle()
	UIParent:Show()
	Settle()
	truthy(FreeRockStrip:IsShown(), "back with the interface")
	eq(Flag(Frame(), 1), true, "and showing what happened meanwhile")
end)

test("a strip that is off stays away when the interface comes back", function()
	Load({ enabled = false })
	UIParent:Hide()
	Settle()
	UIParent:Show()
	Settle()
	eq(FreeRockStrip:IsVisible(), false, "still off")
end)

test("/rock strip faint draws the squares dark grey, and bright puts white back", function()
	Load()
	local function Shade()
		return FreeRockStrip.textures[2].color[1], FreeRockStrip.textures[681].color[1]
	end
	local first, last = Shade()
	eq(first, 1, "white to begin with")
	eq(last, 1, "every square")
	M.Slash("strip faint")
	eq(ns.db.ink, 20)
	first, last = Shade()
	eq(first, 0.2, "dark grey")
	eq(last, 0.2, "every square")
	eq(FreeRockStrip.textures[1].color[1], 0, "the backing stays black")
	truthy(Printed("Brightness of the squares: 20%%"), "described")
	truthy(Printed("/rock strip bright"), "says how to get it back")
	M.Slash("strip ink 55")
	eq((Shade()), 0.55, "any brightness from 10 to 100")
	M.Slash("strip ink 5")
	eq(ns.db.ink, 55, "out of range is refused")
	M.Slash("strip bright")
	eq((Shade()), 1, "white again")
	M.Slash("status")
	truthy(Printed("Brightness of the squares: 100%%"), "in the status report")
end)

test("a faint strip is remembered", function()
	Load({ ink = 30, cell = 1 })
	eq(FreeRockStrip.textures[2].color[1], 0.3, "drawn faint from the start")
	local _, _, width, height = M.FrameBox(FreeRockStrip)
	eq(width, 344 + 4, "one pixel a square")
	eq(height, 2 + 4, "two rows of one pixel")
end)

test("speed, a target that can be fought, and an achievement reach the strip", function()
	Load()
	local frame = Frame()
	eq(frame.speed, 0, "standing")
	eq(Flag(frame, 23), false, "no target")
	eq(ns.Beacon.Pack(frame)[1], 3 * 16, "strip version 3, a state frame")
	eq(ns.Beacon.Pack(frame)[30], 0, "the speed is byte 30")
	M.game.speed = 7
	M.game.target, M.game.canAttack = "normal", true
	M.Fire("PLAYER_TARGET_CHANGED")
	frame = Frame()
	eq(frame.speed, 14, "running: seven yards a second, in half yards")
	eq(Flag(frame, 23), true, "the target can be fought")
	M.game.canAttack = false
	M.Fire("PLAYER_TARGET_CHANGED")
	eq(Flag(Frame(), 23), false, "a friendly target")
	M.game.canAttack = true
	M.sealed.canAttack = true
	M.Fire("PLAYER_TARGET_CHANGED")
	eq(Flag(Frame(), 23), false, "sealed: not sent")
	M.game.speed = 400
	eq(Frame().speed, 254, "faster than the strip can say")
	M.sealed.speed = true
	eq(Frame().speed, 255, "sealed: not known")
	M.sealed.speed = nil
	M.game.speed = 14
	M.Fire("PLAYER_STARTED_MOVING")
	eq(ns.Beacon.BuildFrame().speed, 28, "read at once when the player starts moving")
	local before = ns.db.momentCount
	M.Fire("ACHIEVEMENT_EARNED", 1234)
	eq(ns.db.moment, 6, "achievement")
	eq(ns.db.momentCount, before + 1)
	M.Slash("status")
	truthy(Printed("Speed: 14%.0 yards a second"), "speed in the status report")
	truthy(Printed("can be attacked: no"), "target in the status report")
end)

test("enemies with a nameplate on screen are counted, and how many are in a fight", function()
	-- One enemy's nameplate is already up when the addon loads, and no event announces it.
	M.game.plates.nameplate5 = { enemy = true, fighting = true }
	Load()
	local frame = Frame()
	eq(frame.enemies, 1, "a nameplate that was there before the addon was is counted")
	eq(frame.fighting, 1)
	M.game.plates.nameplate5 = nil
	frame = Frame()
	eq(frame.enemies, 0, "nobody about")
	eq(frame.fighting, 0)
	-- Three nameplates come on screen: two enemies, one of them fighting, and a friendly guard.
	M.game.plates.nameplate1 = { enemy = true, fighting = true }
	M.game.plates.nameplate2 = { enemy = true }
	M.game.plates.nameplate7 = { enemy = false, fighting = true }
	M.Fire("NAME_PLATE_UNIT_ADDED", "nameplate1")
	frame = ns.Beacon.BuildFrame()
	eq(frame.enemies, 2, "counted at once when the game announces a nameplate, without waiting for the timer")
	eq(frame.fighting, 1)
	-- The counts share their bytes with the command and the moment: the upper four bits.
	ns.db.command, ns.db.moment = 2, 5
	local bytes = ns.Beacon.Pack(ns.Beacon.BuildFrame())
	eq(bytes[22], 2 * 16 + 2, "enemies in view beside the command")
	eq(bytes[24], 1 * 16 + 5, "enemies fighting beside the moment")
	-- The second enemy joins the fight; no event says so, the timer finds it.
	M.game.plates.nameplate2.fighting = true
	eq(Frame().fighting, 2)
	-- One dies: a dead enemy is not an enemy in view.
	M.game.plates.nameplate1.dead = true
	frame = Frame()
	eq(frame.enemies, 1)
	eq(frame.fighting, 1)
	-- A nameplate that goes with an event, and one that goes without.
	M.game.plates.nameplate1 = nil
	M.Fire("NAME_PLATE_UNIT_REMOVED", "nameplate1")
	eq(ns.Beacon.BuildFrame().enemies, 1, "counted again at once")
	M.game.plates.nameplate2 = nil
	frame = Frame()
	eq(frame.enemies, 0)
	eq(frame.fighting, 0)
	-- More than the strip can count, up to the last token the game hands out.
	for i = 10, 40 do
		M.game.plates["nameplate" .. i] = { enemy = true, fighting = i % 3 == 0 }
	end
	frame = Frame()
	eq(frame.enemies, 14, "fourteen stands for fourteen or more")
	eq(frame.fighting, 10)
	M.Slash("status")
	truthy(Printed("Enemies with a nameplate on screen: 14 or more, in a fight: 10"), "the counts in the status report")
	truthy(Printed("Nameplates of any kind the game has up: 32"), "the game's own count in the status report")
end)

test("if the game seals anything about a nameplate, the counts are not sent", function()
	Load()
	M.game.plates.nameplate1 = { enemy = true, fighting = true }
	eq(Frame().enemies, 1)
	for _, answer in ipairs({ "plateExists", "plateEnemy", "plateDead", "plateFighting" }) do
		M.sealed[answer] = true
		local frame = Frame()
		eq(frame.enemies, 15, answer .. " sealed: not known")
		eq(frame.fighting, 15, answer .. " sealed: not known")
		M.sealed[answer] = nil
		eq(Frame().enemies, 1, "known again")
	end
	-- What a nameplate event carries is never looked at, sealed or not.
	M.game.plates.nameplate2 = { enemy = true }
	M.Fire("NAME_PLATE_UNIT_ADDED", M.SealedValue("nameplate2"))
	eq(ns.Beacon.BuildFrame().enemies, 2)
	-- The game's own list of nameplates is only for the status report, and may be withheld too.
	M.sealed.plateList = true
	M.Slash("status")
	truthy(Printed("Enemies with a nameplate on screen: 2, in a fight: 1"))
	truthy(Printed("Nameplates of any kind the game has up: it does not say"))
end)

test("the addon sends a note about itself: its version and what it counted", function()
	M.game.plates.nameplate1 = { enemy = true, fighting = true }
	M.game.plates.nameplate2 = { enemy = true, dead = true }
	M.game.plates.nameplate3 = { enemy = false }
	Load()
	Frame()
	local state = ns.Signals.state
	eq(state.note, "", "nothing in the first seconds: the names go out first")
	-- It goes out in the text bytes as name number five, six bytes at a time, in its turn, and
	-- once for each writing: the rest of the time the names have the text bytes to themselves.
	local function Listen(seconds)
		local seen, times = {}, 0
		for _ = 1, math.floor(seconds / 0.2 + 0.5) do
			M.Advance(0.2)
			local frame = ns.Beacon.BuildFrame()
			if frame.text_field == 5 then
				if frame.text_chunk == 0 then times = times + 1 end
				for i = 1, 6 do
					seen[frame.text_chunk * 6 + i] = frame.text_bytes[i]
				end
				eq(frame.text_length, #state.note)
			end
		end
		local sent = {}
		for i = 1, #state.note do
			sent[i] = string.char(seen[i] or 63)
		end
		return table.concat(sent), times
	end
	local sent, times = Listen(9)
	eq(state.note, "v" .. ns.version .. " up=3 un=3 en=1 fi=1 dead=1", "the dead enemy is left out, and said to be")
	eq(sent, state.note, "the whole note was sent")
	eq(times, 1, "once")
	-- It is not written afresh at every count: it has to have time to go out whole.
	M.game.plates.nameplate4 = { enemy = true }
	M.Advance(0.4)
	eq(state.enemies, 2, "the count itself is up to date")
	eq(state.note, "v" .. ns.version .. " up=3 un=3 en=1 fi=1 dead=1", "the note waits")
	sent, times = Listen(6)
	eq(state.note, "v" .. ns.version .. " up=4 un=4 en=2 fi=1 dead=1")
	eq(sent, state.note)
	eq(times, 1)
	sent, times = Listen(6)
	eq(times, 1, "sent again unchanged, for an app that has only just started listening")
	-- A change of name still goes out first, and comes through whole with a note waiting.
	M.Advance(4.6)
	M.game.subzone = "Fargodeep Mine"
	M.Fire("ZONE_CHANGED")
	M.Advance(0.05)
	local frame = ns.Beacon.BuildFrame()
	eq(frame.text_field, 2, "a name that changes goes out first")
	eq(frame.text_chunk, 0)
end)

test("with no nameplates up, status says there is nothing to count", function()
	Load()
	M.Slash("status")
	truthy(Printed("Enemies with a nameplate on screen: 0, in a fight: 0"))
	truthy(Printed("Nameplates of any kind the game has up: none"))
	truthy(Printed("the V key"), "and says where to switch them on")
end)

test("squares shrink to fit a narrow screen, and status says so", function()
	M.screen = { 1920, 1080 }
	Load({ cell = 8 })
	local _, _, width = M.FrameBox(FreeRockStrip)
	eq(width, 344 * 5 + 4, "largest whole square that fits 1920")
	M.Slash("status")
	truthy(Printed("made smaller than asked"), "status mentions it")
end)

test("the beat goes up twice a second", function()
	Load()
	local before = Frame().beat
	M.Advance(1.0)
	eq(ns.Beacon.BuildFrame().beat, (before + 2) % 256, "beat after a second")
end)

test("/rock test sends the test pattern for ten seconds", function()
	Load()
	M.Slash("test")
	local frame = Frame()
	eq(frame.kind, 1, "kind while testing")
	local bytes = ns.Beacon.Pack(frame)
	eq(bytes[1], 0x31, "first byte: version 3, a test frame")
	eq(bytes[2], (17 * 1 + 3) % 256, "second byte")
	M.Advance(10.5)
	eq(ns.Beacon.BuildFrame().kind, 0, "kind afterwards")
	truthy(Printed("test pattern"), "said in chat")
end)

test("/rock test while off says so", function()
	Load({ enabled = false })
	M.Slash("test")
	truthy(Printed("FreeRock is off"), "said in chat")
end)

---------------------------------------------------------------------------
-- Signals
---------------------------------------------------------------------------
test("zone, map and position reach the frame", function()
	Load()
	local frame = Frame()
	eq(frame.map_id, 1429, "map")
	eq(frame.x, math.floor(0.42 * 65534 + 0.5), "x")
	eq(frame.y, math.floor(0.653 * 65534 + 0.5), "y")
	eq(Flag(frame, 17), true, "position known")
	eq(ns.Signals.state.zone, "Elwynn Forest")
	eq(ns.Signals.state.subzone, "Goldshire")
	eq(frame.subzone_hash, ns.Beacon.Mark(ns.Beacon.TextBytes("Goldshire")), "subzone mark")
	eq(frame.pvp_kind, 2, "friendly territory")
end)

test("a new zone shows at once on the zone event", function()
	Load()
	Settle()
	M.game.zone, M.game.realZone, M.game.subzone, M.game.mapID = "Westfall", "Westfall", "Sentinel Hill", 1436
	M.game.pvp = "contested"
	M.Fire("ZONE_CHANGED_NEW_AREA")
	local frame = ns.Beacon.BuildFrame() -- no time has passed
	eq(frame.map_id, 1436, "map")
	eq(frame.pvp_kind, 3, "contested")
	eq(ns.Signals.state.zone, "Westfall")
end)

test("every yes/no state is picked up within a fifth of a second and sets its own bit", function()
	Load()
	local cases = {
		{ "indoors", 1 }, { "resting", 2 }, { "swimming", 3 }, { "submerged", 4 }, { "mounted", 5 },
		{ "flying", 6 }, { "taxi", 7 }, { "stealth", 8 }, { "combat", 10 }, { "boss", 20 }, { "group", 21 },
	}
	local quiet = Frame().flags
	for _, case in ipairs(cases) do
		M.game[case[1]] = true
		local frame = Frame()
		eq(frame.flags, quiet + 2 ^ case[2], case[1])
		M.game[case[1]] = false
		eq(Frame().flags, quiet, case[1] .. " cleared")
	end
end)

test("dead and ghost", function()
	Load()
	M.game.dead = true
	M.Fire("PLAYER_DEAD")
	local frame = ns.Beacon.BuildFrame()
	eq(Flag(frame, 9), true, "dead")
	eq(Flag(frame, 22), false, "not yet a ghost")
	eq(frame.moment, 4, "moment: died")
	M.game.dead, M.game.ghost = false, true
	M.Fire("PLAYER_ALIVE")
	frame = ns.Beacon.BuildFrame()
	eq(Flag(frame, 9), true, "a ghost counts as dead")
	eq(Flag(frame, 22), true, "ghost")
	M.game.ghost = false
	M.Fire("PLAYER_UNGHOST")
	frame = ns.Beacon.BuildFrame()
	eq(Flag(frame, 9), false, "alive")
end)

test("combat starts on the event, before the next poll", function()
	Load()
	Settle()
	M.Fire("PLAYER_REGEN_DISABLED")
	eq(Flag(ns.Beacon.BuildFrame(), 10), true, "combat on the event")
	M.game.combat = true
	Settle()
	M.game.combat = false
	M.Fire("PLAYER_REGEN_ENABLED")
	eq(Flag(ns.Beacon.BuildFrame(), 10), false, "combat over on the event")
end)

test("target classification", function()
	Load()
	local numbers = { normal = 1, elite = 2, rare = 3, rareelite = 4, worldboss = 5, trivial = 6, minus = 7 }
	eq(Frame().target_class, 0, "no target")
	eq(Flag(ns.Beacon.BuildFrame(), 19), false, "no target bit")
	for class, number in pairs(numbers) do
		M.game.target = class
		M.Fire("PLAYER_TARGET_CHANGED")
		local frame = ns.Beacon.BuildFrame()
		eq(frame.target_class, number, class)
		eq(Flag(frame, 19), true, "target bit")
	end
	M.game.target = "something new"
	M.Fire("PLAYER_TARGET_CHANGED")
	eq(ns.Beacon.BuildFrame().target_class, 15, "a class this version does not know")
end)

test("a sealed answer is treated as not known and never touched", function()
	Load()
	M.game.target = "elite"
	M.sealed.classification = true
	M.Fire("PLAYER_TARGET_CHANGED")
	local frame = Frame()
	eq(frame.target_class, 15, "sealed class is sent as not readable")
	eq(Flag(frame, 19), true, "that there is a target is not sealed")
	M.sealed.weather = true
	M.Fire("WEATHER_CHANGED")
	frame = Frame()
	eq(Flag(frame, 16), false, "sealed weather is not reported")
	eq(frame.weather_kind, 15)
	M.sealed.zone, M.sealed.subzone = true, true
	M.Fire("ZONE_CHANGED")
	eq(ns.Signals.state.subzone, "", "sealed name is no name")
	M.Fire("UNIT_CLASSIFICATION_CHANGED", "target")
	M.Slash("status") -- must not try to print a sealed value
	eq(M.sealedTouched, 0, "sealed values used")
end)

test("a dungeon: instance kind, number, name and difficulty; no position", function()
	Load()
	local g = M.game
	g.inInstance, g.instanceKind, g.instanceName, g.difficulty, g.instanceID = true, "party", "The Deadmines", 1, 36
	g.zone, g.realZone, g.subzone, g.mapID, g.x, g.y, g.indoors = "The Deadmines", "The Deadmines", "", 0, nil, nil, true
	g.pvp = nil
	M.Fire("PLAYER_ENTERING_WORLD", false, false)
	local frame = ns.Beacon.BuildFrame()
	eq(Flag(frame, 18), true, "in instance")
	eq(frame.instance_kind, 1, "party")
	eq(frame.instance_id, 36)
	eq(frame.difficulty, 1)
	eq(frame.map_id, 0, "no map")
	eq(Flag(frame, 17), false, "no position")
	eq(frame.x, 65535)
	eq(frame.y, 65535)
	eq(frame.pvp_kind, 0, "PvP kind not reported")
	eq(frame.subzone_hash, 0, "no subzone")
	eq(ns.Signals.state.instanceName, "The Deadmines")
	g.instanceKind = "delve"
	M.Fire("ZONE_CHANGED")
	eq(ns.Beacon.BuildFrame().instance_kind, 15, "an instance kind this version does not know")
end)

test("a boss encounter: start, the name, and how it ended", function()
	Load()
	M.game.encounter = true
	M.Fire("ENCOUNTER_START", 1144, "Edwin VanCleef", 1, 5)
	local frame = ns.Beacon.BuildFrame()
	eq(Flag(frame, 11), true, "encounter running")
	eq(frame.encounter_id, 1144)
	eq(ns.Signals.state.encounterName, "Edwin VanCleef")
	local count = frame.moment_count
	M.game.encounter = false
	M.Fire("ENCOUNTER_END", 1144, "Edwin VanCleef", 1, 5, 1)
	frame = ns.Beacon.BuildFrame()
	eq(Flag(frame, 11), false, "encounter over")
	eq(frame.encounter_id, 0)
	eq(frame.moment, 2, "moment: boss defeated")
	eq(frame.moment_count, (count + 1) % 256)
	M.Fire("ENCOUNTER_START", 1144, "Edwin VanCleef", 1, 5)
	M.Fire("ENCOUNTER_END", 1144, "Edwin VanCleef", 1, 5, 0)
	frame = ns.Beacon.BuildFrame()
	eq(frame.moment, 3, "moment: boss fight lost")
	eq(frame.moment_count, (count + 2) % 256)
end)

test("an encounter already running at login is noticed, and one whose end never came is cleared", function()
	M.game.encounter = true
	Load()
	eq(Flag(Frame(), 11), true, "running at login")
	M.game.encounter = false
	eq(Flag(Frame(), 11), false, "cleared by the poll")
end)

test("weather: kind and intensity, on the event and without it", function()
	Load()
	local frame = Frame()
	eq(Flag(frame, 16), true, "weather known")
	eq(frame.weather_kind, 0, "clear")
	eq(frame.weather_intensity, 0)
	M.game.weather = { type = 1, intensity = 0.45 }
	M.Fire("WEATHER_CHANGED")
	frame = ns.Beacon.BuildFrame()
	eq(frame.weather_kind, 1, "rain")
	eq(frame.weather_intensity, 450)
	-- Without the event it is still picked up, within two seconds.
	M.game.weather = { type = 2, intensity = 3 }
	M.Advance(2.2)
	frame = ns.Beacon.BuildFrame()
	eq(frame.weather_kind, 2, "snow")
	eq(frame.weather_intensity, 3000, "an intensity above 1 is sent as given")
	M.game.weather = { type = 3, intensity = 99 }
	M.Fire("WEATHER_CHANGED")
	eq(ns.Beacon.BuildFrame().weather_intensity, 65534, "capped")
end)

test("weather the game does not report leaves the weather fields saying so", function()
	Load()
	local function NotReported(what)
		M.Fire("WEATHER_CHANGED")
		local frame = ns.Beacon.BuildFrame()
		eq(Flag(frame, 16), false, what .. ": flag")
		eq(frame.weather_kind, 15, what .. ": kind")
		eq(frame.weather_intensity, 65535, what .. ": intensity")
	end
	M.game.weather = nil
	NotReported("the function answers nothing")
	M.game.weather = { }
	NotReported("an empty answer")
	M.game.weather = { type = "rain", intensity = 1 }
	NotReported("a kind that is not a number")
	M.game.weather = { type = 2 }
	M.Fire("WEATHER_CHANGED")
	local frame = ns.Beacon.BuildFrame()
	eq(frame.weather_kind, 2, "a kind without an intensity is still a kind")
	eq(frame.weather_intensity, 65535, "intensity not given")
	M.game.hasWeather = false
	M.SyncApis()
	NotReported("no weather function at all")
	M.Slash("status")
	truthy(Printed("this client has no weather function"), "status says why")
end)

test("day and night", function()
	Load()
	local frame = Frame()
	eq(Flag(frame, 15), true, "known")
	eq(Flag(frame, 14), true, "day")
	M.game.day = false
	M.Fire("DIEL_CYCLE_CHANGED", false)
	frame = ns.Beacon.BuildFrame()
	eq(Flag(frame, 15), true, "known")
	eq(Flag(frame, 14), false, "night")
	M.game.hasDay = false
	M.SyncApis()
	M.Fire("DIEL_CYCLE_CHANGED", true)
	frame = ns.Beacon.BuildFrame()
	eq(Flag(frame, 15), false, "not reported")
	eq(Flag(frame, 14), false, "no claim of day")
end)

test("the game clock", function()
	Load()
	eq(Frame().game_minutes, 14 * 60 + 35)
	M.game.hour, M.game.minute = 0, 5
	eq(Frame().game_minutes, 5)
end)

test("cinematics, movies and loading screens", function()
	Load()
	M.Fire("CINEMATIC_START", true)
	eq(Flag(ns.Beacon.BuildFrame(), 12), true, "cinematic")
	M.Fire("CINEMATIC_STOP")
	eq(Flag(ns.Beacon.BuildFrame(), 12), false, "cinematic over")
	M.Fire("PLAY_MOVIE", 5)
	eq(Flag(ns.Beacon.BuildFrame(), 12), true, "movie")
	M.Fire("STOP_MOVIE")
	eq(Flag(ns.Beacon.BuildFrame(), 12), false, "movie over")
	M.Fire("LOADING_SCREEN_ENABLED")
	eq(Flag(ns.Beacon.BuildFrame(), 13), true, "loading")
	M.game.zone, M.game.realZone, M.game.mapID = "Duskwood", "Duskwood", 1431
	M.Fire("LOADING_SCREEN_DISABLED")
	local frame = ns.Beacon.BuildFrame()
	eq(Flag(frame, 13), false, "loading over")
	eq(frame.map_id, 1431, "everything is read again after a loading screen")
end)

test("level up and quest hand-in are moments", function()
	Load()
	local count = ns.db.momentCount
	M.Fire("PLAYER_LEVEL_UP", 12)
	local frame = ns.Beacon.BuildFrame()
	eq(frame.moment, 1, "level up")
	eq(frame.moment_count, (count + 1) % 256)
	M.Fire("QUEST_TURNED_IN", 123, 400, 0)
	frame = ns.Beacon.BuildFrame()
	eq(frame.moment, 5, "quest")
	eq(frame.moment_count, (count + 2) % 256)
end)

---------------------------------------------------------------------------
-- Names
---------------------------------------------------------------------------
-- Collects what the text bytes carry over some seconds: field -> name, put together from chunks.
local function Names(seconds)
	local got, parts = {}, {}
	local steps = math.floor(seconds / 0.05 + 0.5)
	for _ = 1, steps do
		M.Advance(0.05)
		local frame = ns.Beacon.BuildFrame()
		local field = frame.text_field
		if field ~= 0 then
			parts[field] = parts[field] or {}
			local chars = {}
			for i = 1, 6 do
				if frame.text_bytes[i] then chars[#chars + 1] = string.char(frame.text_bytes[i]) end
			end
			parts[field][frame.text_chunk] = table.concat(chars)
			local whole, complete = {}, true
			for chunk = 0, math.ceil(frame.text_length / 6) - 1 do
				if not parts[field][chunk] then complete = false break end
				whole[#whole + 1] = parts[field][chunk]
			end
			if complete then got[field] = table.concat(whole):sub(1, frame.text_length) end
		end
	end
	return got
end

test("zone and subzone names take turns in the text bytes and come through whole", function()
	Load()
	local got = Names(1.5)
	eq(got[1], "Elwynn Forest", "zone")
	eq(got[2], "Goldshire", "subzone")
	eq(got[3], nil, "no instance name")
	eq(got[4], nil, "no boss name")
end)

test("a name that changes is sent first, with a new revision", function()
	Load()
	Settle()
	local before = ns.Beacon.BuildFrame()
	-- The subzone's revision before the change, taken from a frame in which it has its turn.
	local revision
	for _ = 1, 40 do
		M.Advance(0.05)
		local frame = ns.Beacon.BuildFrame()
		if frame.text_field == 2 then revision = frame.text_revision break end
	end
	truthy(revision, "the subzone had a turn")
	M.game.subzone = "Fargodeep Mine"
	M.Fire("ZONE_CHANGED")
	M.Advance(0.05) -- one drawn frame
	local frame = ns.Beacon.BuildFrame()
	eq(frame.text_field, 2, "the subzone goes first")
	eq(frame.text_chunk, 0, "from its start")
	eq(frame.text_length, 14)
	eq(frame.text_revision, (revision + 1) % 4, "the revision moves on, so the reader drops the old name's chunks")
	eq(string.char(unpack(frame.text_bytes)), "Fargod", "first six bytes")
	eq(frame.subzone_hash, ns.Beacon.Mark(ns.Beacon.TextBytes("Fargodeep Mine")), "mark changes in the same frame")
	truthy(frame.subzone_hash ~= before.subzone_hash, "mark differs from the old one")
	local got = Names(1.5)
	eq(got[2], "Fargodeep Mine")
end)

test("the boss's name is sent while the fight runs and dropped after", function()
	Load()
	M.game.encounter = true
	M.Fire("ENCOUNTER_START", 1144, "Edwin VanCleef", 1, 5)
	eq(Names(1.5)[4], "Edwin VanCleef", "boss name")
	M.game.encounter = false
	M.Fire("ENCOUNTER_END", 1144, "Edwin VanCleef", 1, 5, 1)
	eq(Names(1.5)[4], nil, "no boss name after the fight")
end)

test("with no names at all the text bytes are empty", function()
	M.game.zone, M.game.realZone, M.game.subzone = "", "", ""
	Load()
	local frame = Frame()
	eq(frame.text_field, 0)
	eq(frame.text_length, 0)
	eq(#frame.text_bytes, 0)
	eq(#ns.Beacon.Pack(frame), 40, "still packs")
end)

---------------------------------------------------------------------------
-- Commands
---------------------------------------------------------------------------
test("skip, love and ban each send their number and raise the count; the count is kept", function()
	Load({ commandCount = 254 })
	M.Slash("skip")
	local frame = ns.Beacon.BuildFrame()
	eq(frame.command, 1, "skip")
	eq(frame.command_count, 255)
	M.Slash("love")
	frame = ns.Beacon.BuildFrame()
	eq(frame.command, 2, "love")
	eq(frame.command_count, 0, "wraps at 256")
	M.Slash("ban")
	frame = ns.Beacon.BuildFrame()
	eq(frame.command, 3, "ban")
	eq(frame.command_count, 1)
	eq(FreeRockDB.commandCount, 1, "kept in the saved settings")
	truthy(Printed("never to play this one again"), "said in chat")
end)

test("commands while off are refused in words", function()
	Load({ enabled = false })
	M.Slash("skip")
	eq(ns.db.commandCount, 0, "count unchanged")
	truthy(Printed("FreeRock is off"), "said in chat")
end)

test("/rock volume", function()
	Load()
	M.Slash("volume 35")
	eq(Frame().volume, 35)
	M.printed = {}
	M.Slash("volume 150")
	eq(ns.db.volume, 35, "out of range is not taken")
	truthy(Printed("/rock volume"), "the help is shown instead")
end)

---------------------------------------------------------------------------
-- Settings page, status and errors
---------------------------------------------------------------------------
test("/rock opens the settings page, and its controls change the settings", function()
	Load()
	M.Slash("")
	eq(M.settings.opened, 1, "page opened")
	local panel = ns.Options.panel
	truthy(panel.built, "page built")
	local checks, buttons = {}, {}
	for _, frame in ipairs(M.frames) do
		if frame.parent == panel and frame.kind == "CheckButton" then checks[#checks + 1] = frame end
		if frame.parent == panel and frame.kind == "Button" then buttons[#buttons + 1] = frame end
	end
	eq(#checks, 2, "check boxes")
	eq(checks[1]:GetChecked(), true, "enabled box shows the setting")
	M.Click(checks[1])
	eq(ns.db.enabled, false, "unticking turns FreeRock off")
	M.Click(checks[1])
	eq(ns.db.enabled, true)
	-- Buttons in order: volume - +, edge, size - +, brightness - +, inset - +, inset - +, test, status.
	M.Click(buttons[1])
	eq(ns.db.volume, 65, "volume down")
	M.Click(buttons[3])
	eq(ns.db.edge, "bottom", "edge button moves to the next choice")
	eq(buttons[3]:GetText(), "Bottom", "and says so")
	M.Click(buttons[5])
	eq(ns.db.cell, 4, "square size up")
	M.printed = {}
	M.Click(buttons[#buttons])
	truthy(Printed("Zone: Elwynn Forest"), "status button prints the report")
end)

test("/rock status says what FreeRock sees", function()
	Load()
	M.game.weather = { type = 1, intensity = 0.45 }
	M.game.indoors = true
	Settle()
	M.Fire("WEATHER_CHANGED")
	M.printed = {}
	M.Slash("status")
	local all = AllPrinted()
	truthy(all:find("FreeRock 0.1.0%-test is on"), "version and state")
	truthy(all:find("Sound_EnableMusic = 0 %(yours: 1%)"), "game setting")
	truthy(all:find("Squares of 3 px"), "strip")
	truthy(all:find("Zone: Elwynn Forest %(map 1429%)%. Subzone: Goldshire"), "zone")
	truthy(all:find("Position: 42%.0, 65%.3"), "position")
	truthy(all:find("Indoors yes"), "flags")
	truthy(all:find("Weather: rain, intensity 0%.450%. The game said: type=1 intensity=0%.45"), "weather with the raw answer")
	truthy(all:find("Daylight: day"), "daylight")
	truthy(all:find("Game clock: 14:35"), "clock")
	truthy(all:find("No errors since login"), "errors")
	truthy(all:find("restrictions on addons in this client: yes"), "sealing")
end)

test("an error inside FreeRock reaches the game's error handler, is said once in chat, and is listed in status", function()
	M.expectErrors = true
	Load()
	M.game.weather = setmetatable({}, { __index = function() error("the weather broke") end })
	M.Fire("WEATHER_CHANGED")
	M.Fire("WEATHER_CHANGED")
	eq(#M.luaErrors, 2, "both errors reached the game's handler")
	truthy(M.luaErrors[1]:find("the weather broke"), "the error itself")
	eq(#ns.GetProblems(), 1, "kept once")
	eq(ns.GetProblems()[1].count, 2, "and counted")
	local said = 0
	for _, line in ipairs(M.printed) do
		if line:find("Something went wrong inside FreeRock") then said = said + 1 end
	end
	eq(said, 1, "said once")
	-- The strip keeps working.
	M.game.weather = { type = 0, intensity = 0 }
	M.game.indoors = true
	eq(Flag(Frame(), 1), true, "the strip still follows the game")
	M.printed = {}
	M.Slash("status")
	truthy(Printed("Error|r %(2 times%)"), "listed in status")
end)

test("a call the game refuses is kept with the errors", function()
	M.expectErrors = true
	Load()
	M.Fire("ADDON_ACTION_BLOCKED", "FreeRock", "SomeProtectedFunction()")
	M.Fire("ADDON_ACTION_BLOCKED", "AnotherAddon", "Whatever()")
	eq(#ns.GetProblems(), 1, "only our own")
	truthy(ns.GetProblems()[1].text:find("refused to let FreeRock call SomeProtectedFunction"), "what was refused")
end)

test("an event this client does not have is skipped and listed, and the timer covers for it", function()
	M.unknownEvents.WEATHER_CHANGED = true
	M.unknownEvents.UPDATE_STEALTH = true
	Load()
	eq(#ns.missingEvents, 2, "missing events noted")
	-- Everything after the missing registrations was still set up.
	M.game.target = "elite"
	M.Fire("PLAYER_TARGET_CHANGED")
	eq(ns.Beacon.BuildFrame().target_class, 2, "later events still work")
	-- What the missing events would have said is picked up by the timer.
	M.game.stealth = true
	M.game.weather = { type = 2, intensity = 1 }
	M.Advance(2.2)
	local frame = ns.Beacon.BuildFrame()
	eq(Flag(frame, 8), true, "stealth, without its event")
	eq(frame.weather_kind, 2, "weather, without its event")
	M.printed = {}
	M.Slash("status")
	truthy(Printed("Events this client does not have.*UPDATE_STEALTH, WEATHER_CHANGED"), "listed in status")
	truthy(Printed("No errors since login"), "and it is not an error")
end)

test("a client that cannot be asked about events gets them registered as before", function()
	C_EventUtils = nil
	Load()
	eq(#ns.missingEvents, 0)
	M.game.indoors = true
	M.Fire("ZONE_CHANGED_INDOORS")
	eq(Flag(ns.Beacon.BuildFrame(), 1), true, "events arrive")
end)

test("an unknown command prints the help", function()
	Load()
	M.printed = {}
	M.Slash("dance")
	truthy(Printed("/rock skip"), "help")
	truthy(Printed("/rock status"), "help")
end)

test("nothing is read while FreeRock is off", function()
	Load({ enabled = false })
	M.game.indoors = true
	M.Advance(1)
	eq(ns.Signals.state.indoors, false, "the timer is stopped")
	M.Slash("on")
	eq(Flag(Frame(), 1), true, "and starts again when turned on")
end)
