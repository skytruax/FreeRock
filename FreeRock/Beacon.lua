local _, ns = ...

-- The strip: a thin line of black and white squares along an edge of the screen that carries the
-- state gathered by Signals.lua. The FreeRock app reads it off the screen from outside the game.
-- The format is defined in protocol/beacon.md, and the same test vectors are run against this
-- file and against the app's reader.
local Beacon = {}
ns.Beacon = Beacon

---------------------------------------------------------------------------
-- The format (protocol/beacon.md)
---------------------------------------------------------------------------
local VERSION = 3              -- 2 added the speed byte and the "target can be attacked" flag;
                               -- 3 put the enemies in view and in a fight beside the command and the moment
local PAYLOAD = 40             -- bytes in a frame
local ROWS = 2
local ROW_BITS = PAYLOAD * 8 / ROWS
local QUIET = 2                -- black squares at each end of a row
local FINDER = { 1, 1, 1, 1, 0, 0 }
local CLOCK = { 1, 0, 1, 0 }
local FINISH = { 0, 0, 1, 1, 1, 1 }
local ROW_SQUARES = #FINDER + #CLOCK + 4 + 2 * ROW_BITS + #FINISH -- 340, quiet squares not counted
local ROW_WIDTH = ROW_SQUARES + 2 * QUIET                         -- 344
local TEXT_CHUNK = 6
local TEXT_MAX = 48
local UNKNOWN = 65535
local KIND_STATE, KIND_TEST = 0, 1

Beacon.ROW_WIDTH = ROW_WIDTH
Beacon.ROWS = ROWS

-- The checksum needs exclusive-or, which plain Lua 5.1 lacks. These few lines of arithmetic do it
-- for numbers up to 16 bits, so the strip does not depend on any library being present.
local XOR4 = {}
for a = 0, 15 do
	XOR4[a] = {}
	for b = 0, 15 do
		local value, place, x, y = 0, 1, a, b
		for _ = 1, 4 do
			if x % 2 ~= y % 2 then
				value = value + place
			end
			x, y, place = (x - x % 2) / 2, (y - y % 2) / 2, place * 2
		end
		XOR4[a][b] = value
	end
end

local function Xor16(a, b)
	local result, place = 0, 1
	for _ = 1, 4 do
		local x, y = a % 16, b % 16
		result = result + XOR4[x][y] * place
		a, b, place = (a - x) / 16, (b - y) / 16, place * 16
	end
	return result
end

-- CRC-16/CCITT-FALSE: polynomial 0x1021, start 0xFFFF. Its value for "123456789" is 0x29B1.
local CRC = {}
for index = 0, 255 do
	local crc = index * 256
	for _ = 1, 8 do
		if crc >= 32768 then
			crc = Xor16((crc * 2) % 65536, 0x1021)
		else
			crc = crc * 2
		end
	end
	CRC[index] = crc
end

-- bytes is a list of numbers 0 to 255; the first count of them are summed.
function Beacon.Crc16(bytes, count)
	local crc = 0xFFFF
	for i = 1, count do
		local high = (crc - crc % 256) / 256
		crc = Xor16((crc % 256) * 256, CRC[Xor16(high, bytes[i])])
	end
	return crc
end

-- The bytes of a name as they are sent: UTF-8, cut to 48 bytes without splitting a character.
function Beacon.TextBytes(text)
	local bytes = { text:byte(1, TEXT_MAX + 1) }
	if #bytes > TEXT_MAX then
		local cut = TEXT_MAX
		-- bytes[cut + 1] is the first byte left out. While that is the inside of a character,
		-- the character would be split, so back up to its start.
		while cut > 0 and bytes[cut + 1] >= 128 and bytes[cut + 1] < 192 do
			cut = cut - 1
		end
		for i = #bytes, cut + 1, -1 do
			bytes[i] = nil
		end
	end
	return bytes
end

-- The 16-bit mark of a name. 0 is kept for "no name".
function Beacon.Mark(bytes)
	if #bytes == 0 then
		return 0
	end
	local crc = Beacon.Crc16(bytes, #bytes)
	return crc == 0 and UNKNOWN or crc
end

local function Put16(bytes, at, value)
	bytes[at] = (value - value % 256) / 256
	bytes[at + 1] = value % 256
end

-- The 40 bytes of a frame. The field names are the ones protocol/vectors.json uses.
function Beacon.Pack(frame)
	local bytes = {}
	if frame.kind == KIND_TEST then
		bytes[1] = VERSION * 16 + KIND_TEST
		for i = 1, PAYLOAD - 3 do
			bytes[i + 1] = (17 * i + 3) % 256
		end
	else
		bytes[1] = VERSION * 16 + frame.kind
		bytes[2] = frame.beat
		local flags = frame.flags
		bytes[3] = math.floor(flags / 65536) % 256
		bytes[4] = math.floor(flags / 256) % 256
		bytes[5] = flags % 256
		bytes[6] = frame.instance_kind * 16 + frame.target_class
		bytes[7] = frame.pvp_kind * 16 + frame.weather_kind
		Put16(bytes, 8, frame.weather_intensity)
		Put16(bytes, 10, frame.map_id)
		Put16(bytes, 12, frame.x)
		Put16(bytes, 14, frame.y)
		Put16(bytes, 16, frame.instance_id)
		Put16(bytes, 18, frame.encounter_id)
		Put16(bytes, 20, frame.game_minutes)
		bytes[22] = frame.enemies * 16 + frame.command
		bytes[23] = frame.command_count
		bytes[24] = frame.fighting * 16 + frame.moment
		bytes[25] = frame.moment_count
		bytes[26] = frame.volume
		bytes[27] = frame.difficulty
		Put16(bytes, 28, frame.subzone_hash)
		bytes[30] = frame.speed
		bytes[31] = frame.text_field * 32 + frame.text_revision * 8 + frame.text_chunk
		bytes[32] = frame.text_length
		for i = 1, TEXT_CHUNK do
			bytes[32 + i] = frame.text_bytes[i] or 0
		end
	end
	Put16(bytes, PAYLOAD - 1, Beacon.Crc16(bytes, PAYLOAD - 2))
	return bytes
end

-- The squares of one row (0 is the top row), quiet squares included: 344 values, 1 white, 0 black.
function Beacon.Squares(bytes, row)
	local squares = {}
	local function Add(value)
		squares[#squares + 1] = value
	end
	-- A bit is two squares: 1 is white then black, 0 is black then white.
	local function AddBit(bit)
		Add(bit)
		Add(1 - bit)
	end
	for _ = 1, QUIET do Add(0) end
	for _, value in ipairs(FINDER) do Add(value) end
	for _, value in ipairs(CLOCK) do Add(value) end
	AddBit(math.floor(row / 2) % 2)
	AddBit(row % 2)
	local firstByte = row * ROW_BITS / 8
	for index = firstByte + 1, firstByte + ROW_BITS / 8 do
		local byte = bytes[index]
		local weight = 128
		for _ = 1, 8 do
			local bit = byte >= weight and 1 or 0
			AddBit(bit)
			byte = byte - bit * weight
			weight = weight / 2
		end
	end
	for _, value in ipairs(FINISH) do Add(value) end
	for _ = 1, QUIET do Add(0) end
	return squares
end

---------------------------------------------------------------------------
-- What goes into a frame
---------------------------------------------------------------------------
local beat = 0            -- goes up every half second
local testUntil           -- while set, test frames are sent
local offUntil            -- while set, FreeRock is off and the strip is saying so before it goes

-- The names that take turns in the text bytes: field number -> where Signals keeps the name.
local TEXT_SOURCES = { "zone", "subzone", "instanceName", "encounterName", "note" }
local TEXT_SUBZONE = 2
local TEXT_NOTE = 5       -- the addon's own line about itself. It waits its turn behind the names,
                          -- and each writing of it is sent once, so the names keep most of the turns.
local texts = {}
for field = 1, #TEXT_SOURCES do
	texts[field] = { text = "", bytes = {}, revision = 0 }
end
local turn = { field = 0, chunk = 0 } -- whose turn it is, and which six bytes of it

-- Moves on to the next six bytes of the name being sent, or to the next name that has any.
-- Returns true when that changed what is being sent.
local function NextText()
	local field, chunk = turn.field, turn.chunk
	local moved = false
	if field ~= 0 and (chunk + 1) * TEXT_CHUNK < #texts[field].bytes then
		turn.chunk = chunk + 1
		moved = true
	else
		if field == TEXT_NOTE then
			texts[TEXT_NOTE].pending = false       -- the note has gone out whole
		end
		turn.field, turn.chunk = 0, 0
		for step = 1, #TEXT_SOURCES do
			local candidate = (field + step - 1) % #TEXT_SOURCES + 1
			if #texts[candidate].bytes > 0 and (candidate ~= TEXT_NOTE or texts[candidate].pending) then
				turn.field = candidate
				break
			end
		end
	end
	return moved or turn.field ~= field or turn.chunk ~= chunk
end

-- Picks up names that changed. A name that just changed goes out first.
local function SyncTexts()
	local state = ns.Signals.state
	for field, key in ipairs(TEXT_SOURCES) do
		local entry = texts[field]
		local text = state[key]
		if entry.text ~= text then
			entry.text = text
			entry.bytes = Beacon.TextBytes(text)
			entry.revision = (entry.revision + 1) % 4
			if #entry.bytes > 0 and field ~= TEXT_NOTE then
				turn.field, turn.chunk = field, 0
			end
		end
	end
	-- The note is sent once for each writing of it.
	local note = texts[TEXT_NOTE]
	if note.serial ~= state.noteSerial then
		note.serial = state.noteSerial
		note.pending = #note.bytes > 0
	end
	if turn.field == 0 or #texts[turn.field].bytes == 0 then
		NextText()
	end
end

-- A value from 0 to 1 (or 0 upwards) as a whole number for the strip, or "not known".
local function Scaled(value, factor)
	if type(value) ~= "number" then
		return UNKNOWN
	end
	return math.max(0, math.min(UNKNOWN - 1, math.floor(value * factor + 0.5)))
end

local function Fits16(value)
	return value <= UNKNOWN and value or 0
end

function Beacon.BuildFrame()
	if testUntil then
		return { kind = KIND_TEST }
	end
	local db, state = ns.db, ns.Signals.state
	local flags = 0
	local function Flag(on, bit)
		if on then
			flags = flags + 2 ^ bit
		end
	end
	Flag(db.enabled, 0)
	Flag(state.indoors, 1)
	Flag(state.resting, 2)
	Flag(state.swimming, 3)
	Flag(state.submerged, 4)
	Flag(state.mounted, 5)
	Flag(state.flying, 6)
	Flag(state.taxi, 7)
	Flag(state.stealth, 8)
	Flag(state.dead, 9)
	Flag(state.combat, 10)
	Flag(state.encounter, 11)
	Flag(state.cinematic, 12)
	Flag(state.loading, 13)
	Flag(state.dayKnown and state.day, 14)
	Flag(state.dayKnown, 15)
	Flag(state.weatherKnown, 16)
	Flag(state.x ~= nil, 17)
	Flag(state.inInstance, 18)
	Flag(state.hasTarget, 19)
	Flag(state.bossPresent, 20)
	Flag(state.inGroup, 21)
	Flag(state.ghost, 22)
	Flag(state.targetHostile, 23)

	local entry = texts[turn.field]
	local chunk = {}
	if entry then
		for i = 1, TEXT_CHUNK do
			chunk[i] = entry.bytes[turn.chunk * TEXT_CHUNK + i]
		end
	end
	return {
		kind = KIND_STATE,
		beat = beat,
		flags = flags,
		instance_kind = state.instanceKind,
		target_class = state.targetClass,
		pvp_kind = state.pvpKind,
		weather_kind = state.weatherKnown and state.weatherKind or 15,
		weather_intensity = state.weatherKnown and Scaled(state.weatherIntensity, 1000) or UNKNOWN,
		map_id = Fits16(state.mapID),
		x = Scaled(state.x, UNKNOWN - 1),
		y = Scaled(state.y, UNKNOWN - 1),
		instance_id = Fits16(state.instanceID),
		encounter_id = Fits16(state.encounterID),
		game_minutes = state.minutes or UNKNOWN,
		command = db.command,
		command_count = db.commandCount,
		moment = db.moment,
		moment_count = db.momentCount,
		volume = db.volume,
		difficulty = math.min(state.difficulty, 255),
		subzone_hash = Beacon.Mark(texts[TEXT_SUBZONE].bytes),
		speed = state.speed or 255,
		enemies = state.enemies or 15,
		fighting = state.fighting or 15,
		text_field = turn.field,
		text_revision = entry and entry.revision or 0,
		text_chunk = turn.chunk,
		text_length = entry and #entry.bytes or 0,
		text_bytes = chunk,
	}
end

---------------------------------------------------------------------------
-- Drawing
---------------------------------------------------------------------------
local MARGIN = 2     -- pixels of black around the squares
local POLL = 0.2     -- seconds between reads of the things that have no event
local TEXT_TURN = 0.2
local BEAT = 0.5
local OFF_NOTICE = 3 -- seconds the strip says "off" before it is taken away

local strip                    -- the frame
local squares, showing = {}, {} -- per row: the textures of the 340 drawn squares, and what each shows
local layout = { cell = 0, fits = true }
local dirty = true
local inked                    -- the brightness the squares were last coloured with
local interfaceHidden = false  -- the player has hidden the interface (for a screenshot, say)
local ticker = CreateFrame("Frame")
ticker:Hide()

local function Draw()
	local bytes = Beacon.Pack(Beacon.BuildFrame())
	for row = 0, ROWS - 1 do
		local values = Beacon.Squares(bytes, row)
		local textures, now = squares[row], showing[row]
		for i = 1, ROW_SQUARES do
			local value = values[QUIET + i]
			if now[i] ~= value then
				now[i] = value
				textures[i]:SetShown(value == 1)
			end
		end
	end
end

-- Colours the lit squares. White is the easiest to read; drawn dark grey on the black backing
-- the strip is hard to see on screen, and the app reads it all the same.
local function Ink()
	local level = ns.db.ink
	if inked == level then
		return
	end
	inked = level
	local shade = level / 100
	for row = 0, ROWS - 1 do
		for _, texture in ipairs(squares[row]) do
			texture:SetColorTexture(shade, shade, shade, 1)
		end
	end
end

-- Whether the strip should be on screen: FreeRock is on (or saying "off" for a moment), and the
-- interface is not hidden. A hidden interface is hidden for a clean screen, and the strip goes
-- with it; the app keeps the last state until it is back.
local function Visible()
	return (ns.db.enabled or offUntil ~= nil) and not interfaceHidden
end

-- Sizes and places the strip so that one square is a whole number of screen pixels, whatever the
-- interface scale is. The interface measures in units of which the screen is 768 tall, so a frame
-- scaled by 768 / (screen height in pixels) measures in pixels.
local function Layout()
	local db = ns.db
	local width, height = GetPhysicalScreenSize()
	local anchor = strip:GetParent()
	strip:SetScale(768 / height / anchor:GetEffectiveScale())

	local room = math.floor((width - 2 * db.insetX - 2 * MARGIN) / ROW_WIDTH)
	local cell = math.max(1, math.min(db.cell, room))
	layout.cell, layout.asked, layout.fits = cell, db.cell, room >= 1
	layout.width, layout.height = ROW_WIDTH * cell + 2 * MARGIN, ROWS * cell + 2 * MARGIN
	layout.screenWidth, layout.screenHeight = width, height

	strip:SetSize(layout.width, layout.height)
	strip:ClearAllPoints()
	if db.edge == "bottom" then
		strip:SetPoint("BOTTOMLEFT", anchor, "BOTTOMLEFT", db.insetX, db.insetY)
	else
		strip:SetPoint("TOPLEFT", anchor, "TOPLEFT", db.insetX, -db.insetY)
	end
	for row = 0, ROWS - 1 do
		for i, texture in ipairs(squares[row]) do
			texture:ClearAllPoints()
			texture:SetSize(cell, cell)
			texture:SetPoint("TOPLEFT", strip, "TOPLEFT", MARGIN + (QUIET + i - 1) * cell, -(MARGIN + row * cell))
		end
	end
	Ink()
end

local function Create()
	-- A child of the world frame rather than of the interface, so it has the world frame's plain
	-- scale. Whether it also stays up when the interface is hidden is not known from here.
	strip = CreateFrame("Frame", "FreeRockStrip", WorldFrame or UIParent)
	strip:SetFrameStrata("TOOLTIP")
	strip:Hide()
	local backing = strip:CreateTexture(nil, "BACKGROUND")
	backing:SetAllPoints(strip)
	backing:SetColorTexture(0, 0, 0, 1)
	for row = 0, ROWS - 1 do
		squares[row], showing[row] = {}, {}
		for i = 1, ROW_SQUARES do
			local texture = strip:CreateTexture(nil, "ARTWORK")
			texture:SetColorTexture(1, 1, 1, 1)
			texture:Hide()
			squares[row][i] = texture
			showing[row][i] = 0
		end
	end
end

local pollTime, textTime, beatTime, polls = 0, 0, 0, 0

local function Tick(elapsed)
	pollTime, textTime, beatTime = pollTime + elapsed, textTime + elapsed, beatTime + elapsed
	if pollTime >= POLL then
		pollTime = 0
		polls = polls + 1
		ns.Signals:Poll(polls % 10 == 0)
	end
	if textTime >= TEXT_TURN then
		textTime = 0
		if NextText() then
			dirty = true
		end
	end
	if beatTime >= BEAT then
		beatTime = 0
		beat = (beat + 1) % 256
		dirty = true
	end
	local now = GetTime()
	if testUntil and now >= testUntil then
		testUntil = nil
		dirty = true
	end
	if offUntil and now >= offUntil then
		offUntil = nil
		strip:Hide()
		ticker:Hide()
		return
	end
	-- The strip goes when the interface is hidden and comes back with it. This timer belongs to
	-- no part of the interface, so it keeps running and sees the interface return.
	local hidden = not UIParent:IsShown()
	if hidden ~= interfaceHidden then
		interfaceHidden = hidden
		strip:SetShown(Visible())
		dirty = true
	end
	if dirty then
		dirty = false
		SyncTexts()
		Draw()
	end
end

ticker:SetScript("OnUpdate", function(_, elapsed)
	ns.Try(Tick, elapsed)
end)

-- Something the strip shows has changed; it is redrawn on the next frame the game draws.
function Beacon:Touch()
	dirty = true
end

-- Brings the strip in line with the settings: where it is, how big, and whether it is up at all.
function Beacon:Apply()
	if not strip then
		Create()
	end
	Layout()
	if ns.db.enabled then
		offUntil = nil
		strip:SetShown(Visible())
		ticker:Show()
		dirty = true
	elseif strip:IsShown() and not offUntil then
		-- Say "off" in the strip for a moment so the app stops at once, then take the strip away.
		offUntil = GetTime() + OFF_NOTICE
		dirty = true
	end
end

local function Relayout()
	if strip then
		Layout()
		dirty = true
	end
end
ns.On("UI_SCALE_CHANGED", Relayout)
ns.On("DISPLAY_SIZE_CHANGED", Relayout)

Beacon.COMMAND_SKIP, Beacon.COMMAND_LOVE, Beacon.COMMAND_BAN = 1, 2, 3

-- Sends a command to the app: the command and a count that goes up, so the app acts once.
function Beacon:Command(code)
	local db = ns.db
	db.command = code
	db.commandCount = (db.commandCount + 1) % 256
	dirty = true
end

-- Sends test frames for a while. Returns false when the strip is not up.
function Beacon:Test(seconds)
	if not (strip and strip:IsShown() and ns.db.enabled) then
		return false
	end
	testUntil = GetTime() + seconds
	dirty = true
	return true
end

-- For /rock status.
function Beacon:Describe()
	if not strip then
		return { "Strip: not built yet." }
	end
	local lines = {}
	lines[1] = ("Strip: %s, along the %s edge, %d px in from the left and %d px from the edge."):format(
		strip:IsShown() and (offUntil and "saying off, about to go" or "showing")
			or (interfaceHidden and ns.db.enabled) and "hidden with the interface" or "hidden",
		ns.db.edge, ns.db.insetX, ns.db.insetY)
	lines[2] = ("Squares of %d px (asked for %d), %d by %d of them, %d by %d px in all. Screen %d by %d px."):format(
		layout.cell, layout.asked, ROW_WIDTH, ROWS, layout.width, layout.height, layout.screenWidth, layout.screenHeight)
	lines[#lines + 1] = ("Brightness of the squares: %d%%."):format(ns.db.ink)
	if not layout.fits then
		lines[#lines + 1] = "The screen is too narrow for the strip at this distance from the edge; it cannot be read like this."
	elseif layout.cell < layout.asked then
		lines[#lines + 1] = "The squares were made smaller than asked so the strip fits the screen."
	end
	if testUntil then
		lines[#lines + 1] = "Sending test frames."
	end
	return lines
end
