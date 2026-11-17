local _, ns = ...

-- The settings page (Options > AddOns > FreeRock), the /rock command, and the status report.
local Options = {}
ns.Options = Options

local function Set(key, value)
	ns.db[key] = value
	ns.Refresh()
end

---------------------------------------------------------------------------
-- Widgets
---------------------------------------------------------------------------
local ROW = 26
local controls = {} -- every widget with a Sync function

local function AddTooltip(widget, title, text)
	widget:SetScript("OnEnter", function(self)
		GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
		GameTooltip:SetText(title, 1, 1, 1)
		GameTooltip:AddLine(text, nil, nil, nil, true)
		GameTooltip:Show()
	end)
	widget:SetScript("OnLeave", function()
		GameTooltip:Hide()
	end)
end

local function Heading(panel, text, x, y)
	local heading = panel:CreateFontString(nil, "ARTWORK", "GameFontNormalLarge")
	heading:SetPoint("TOPLEFT", x, y)
	heading:SetText(text)
	return y - ROW
end

local function Check(panel, x, y, label, tooltip, key)
	local check = CreateFrame("CheckButton", nil, panel, "UICheckButtonTemplate")
	check:SetSize(26, 26)
	check:SetPoint("TOPLEFT", x, y)
	check.Text:SetText(label)
	check.Text:SetFontObject("GameFontHighlight")
	AddTooltip(check, label, tooltip)
	check:SetScript("OnClick", function(self)
		Set(key, self:GetChecked() and true or false)
	end)
	check.Sync = function(self)
		self:SetChecked(ns.db[key])
	end
	controls[#controls + 1] = check
	return y - ROW
end

-- A label with - and + buttons around a whole number.
local function Stepper(panel, x, y, label, tooltip, key, minimum, maximum, step, suffix)
	local text = panel:CreateFontString(nil, "ARTWORK", "GameFontHighlight")
	text:SetPoint("TOPLEFT", x + 4, y - 6)
	text:SetText(label)

	local value = panel:CreateFontString(nil, "ARTWORK", "GameFontHighlight")
	value:SetPoint("CENTER", panel, "TOPLEFT", x + 245, y - 13)

	local function Step(direction)
		Set(key, math.max(minimum, math.min(maximum, ns.db[key] + direction * step)))
	end
	local minus = CreateFrame("Button", nil, panel, "UIPanelButtonTemplate")
	minus:SetSize(26, 22)
	minus:SetPoint("TOPLEFT", x + 160, y - 2)
	minus:SetText("-")
	minus:SetScript("OnClick", function() Step(-1) end)
	local plus = CreateFrame("Button", nil, panel, "UIPanelButtonTemplate")
	plus:SetSize(26, 22)
	plus:SetPoint("TOPLEFT", x + 304, y - 2)
	plus:SetText("+")
	plus:SetScript("OnClick", function() Step(1) end)
	AddTooltip(minus, label, tooltip)
	AddTooltip(plus, label, tooltip)

	value.Sync = function(self)
		self:SetText(tostring(ns.db[key]) .. suffix)
	end
	controls[#controls + 1] = value
	return y - ROW
end

-- A label with a button that shows the current choice and moves to the next one when clicked.
local function Choice(panel, x, y, label, tooltip, key, choices)
	local text = panel:CreateFontString(nil, "ARTWORK", "GameFontHighlight")
	text:SetPoint("TOPLEFT", x + 4, y - 6)
	text:SetText(label)

	local button = CreateFrame("Button", nil, panel, "UIPanelButtonTemplate")
	button:SetSize(170, 22)
	button:SetPoint("TOPLEFT", x + 160, y - 2)
	AddTooltip(button, label, tooltip)
	button:SetScript("OnClick", function()
		for index, choice in ipairs(choices) do
			if choice[1] == ns.db[key] then
				Set(key, choices[index % #choices + 1][1])
				return
			end
		end
		Set(key, choices[1][1])
	end)
	button.Sync = function(self)
		for _, choice in ipairs(choices) do
			if choice[1] == ns.db[key] then
				self:SetText(choice[2])
			end
		end
	end
	controls[#controls + 1] = button
	return y - ROW
end

local function Action(panel, x, y, label, tooltip, onClick)
	local button = CreateFrame("Button", nil, panel, "UIPanelButtonTemplate")
	button:SetSize(170, 22)
	button:SetPoint("TOPLEFT", x + 160, y - 2)
	button:SetText(label)
	AddTooltip(button, label, tooltip)
	button:SetScript("OnClick", onClick)
	return y - ROW
end

---------------------------------------------------------------------------
-- /rock status
---------------------------------------------------------------------------
local COMMAND_NAMES = { [0] = "none yet", "skip", "love", "ban" }
local MOMENT_NAMES = { [0] = "none yet", "level up", "boss defeated", "boss fight lost", "died", "quest handed in" }

local function PrintStatus()
	local db = ns.db
	ns.Print(("FreeRock %s is %s. Volume %d. Game restrictions on addons in this client: %s."):format(
		ns.version, db.enabled and "on" or "off", db.volume, ns.DescribeSealing()))
	for _, line in ipairs(ns.CVars:Describe()) do
		ns.Print("Game setting: " .. line)
	end
	for _, line in ipairs(ns.Beacon:Describe()) do
		ns.Print(line)
	end
	for _, line in ipairs(ns.Signals:Describe()) do
		ns.Print(line)
	end
	ns.Print(("Last command: %s (number %d). Last moment: %s (number %d)."):format(
		COMMAND_NAMES[db.command] or tostring(db.command), db.commandCount,
		MOMENT_NAMES[db.moment] or tostring(db.moment), db.momentCount))
	if #ns.missingEvents > 0 then
		ns.Print("Events this client does not have (FreeRock reads the same things on a timer instead): "
			.. table.concat(ns.missingEvents, ", ") .. ".")
	end
	local problems = ns.GetProblems()
	if #problems == 0 then
		ns.Print("No errors since login.")
	else
		for _, problem in ipairs(problems) do
			ns.Print(("|cffff4040Error|r (%d time%s): %s"):format(problem.count, problem.count == 1 and "" or "s", problem.text))
		end
	end
end
Options.PrintStatus = PrintStatus

local function Test()
	if ns.Beacon:Test(10) then
		ns.Print("Sending a test pattern for ten seconds. The FreeRock page should say it was read.")
	else
		ns.Print("FreeRock is off, so there is no strip to test. /rock on turns it on.")
	end
end

---------------------------------------------------------------------------
-- The page
---------------------------------------------------------------------------
local function Build(panel)
	local title = panel:CreateFontString(nil, "ARTWORK", "GameFontNormalHuge")
	title:SetPoint("TOPLEFT", 16, -14)
	title:SetText("FreeRock")

	local note = panel:CreateFontString(nil, "ARTWORK", "GameFontHighlightSmall")
	note:SetPoint("TOPLEFT", 18, -40)
	note:SetPoint("RIGHT", -20, 0)
	note:SetJustifyH("LEFT")
	note:SetText("Music made for where you are, played by the FreeRock app outside the game. This addon draws a thin line of squares along the edge of the screen that tells the app what is happening. It reads only what the game lets every addon read.")

	local left = 16
	local y = -84

	y = Heading(panel, "Music", left, y)
	y = Check(panel, left, y, "Enable FreeRock", "Draws the strip for the FreeRock app. Turn it off to stop the music and take the strip away.", "enabled")
	y = Check(panel, left, y, "Turn the game's own music off", "While FreeRock is on, the game's own music is switched off so the two do not play over each other. Your setting is put back when FreeRock is turned off and when you log out.", "muteGameMusic")
	y = Stepper(panel, left, y, "Volume", "How loud FreeRock plays, from 0 to 100.", "volume", 0, 100, 5, "")
	y = y - 10

	y = Heading(panel, "The strip", left, y)
	y = Choice(panel, left, y, "Edge of the screen", "Which edge the strip runs along. Move it if something of yours sits in the same place.", "edge",
		{ { "top", "Top" }, { "bottom", "Bottom" } })
	y = Stepper(panel, left, y, "Square size", "The size of one square, in screen pixels. Larger squares are easier for the app to read; smaller ones make a thinner line. One pixel only reads when the game is drawn pixel for pixel.", "cell", 1, 8, 1, " px")
	y = Stepper(panel, left, y, "Brightness", "How bright the squares are drawn. Low makes the strip hard to see: dark grey on black. If the app loses the strip, turn it up.", "ink", 10, 100, 10, "%")
	y = Stepper(panel, left, y, "In from the left", "How far the strip starts from the left edge of the screen, in pixels.", "insetX", 0, 2000, 8, " px")
	y = Stepper(panel, left, y, "In from the edge", "How far the strip sits from the top or bottom edge, in pixels.", "insetY", 0, 500, 2, " px")
	y = y - 10

	y = Heading(panel, "Checks", left, y)
	y = Action(panel, left, y, "Send a test pattern", "Sends a fixed pattern for ten seconds so the app can confirm it reads every square.", Test)
	Action(panel, left, y, "Say what FreeRock sees", "Prints the status report to chat: the same as /rock status.", PrintStatus)
end

function Options:Create()
	local panel = CreateFrame("Frame")
	panel:Hide()
	-- Built the first time the page is opened; most sessions never open it.
	panel:SetScript("OnShow", function(self)
		if not self.built then
			self.built = true
			Build(self)
		end
		Options:Sync()
	end)
	self.panel = panel
	self.category = Settings.RegisterCanvasLayoutCategory(panel, "FreeRock")
	Settings.RegisterAddOnCategory(self.category)
end

-- Brings the page in line with the saved settings.
function Options:Sync()
	if not (self.panel and self.panel.built) then
		return
	end
	for _, control in ipairs(controls) do
		control:Sync()
	end
end

function Options:Open()
	Settings.OpenToCategory(self.category:GetID())
end

---------------------------------------------------------------------------
-- /rock
---------------------------------------------------------------------------
local HELP = {
	"/rock - open the settings",
	"/rock on | off - turn FreeRock on or off (off puts the game's own music back)",
	"/rock skip - play something else",
	"/rock love - mark what is playing as one you love",
	"/rock ban - never play what is playing again",
	"/rock volume <0-100> - how loud FreeRock plays",
	"/rock gamemusic on | off - leave the game's own music playing as well (on), or switch it off while FreeRock is on (off)",
	"/rock strip top | bottom - which edge of the screen the strip runs along",
	"/rock strip size <1-8> - size of one square, in screen pixels",
	"/rock strip faint | bright - draw the squares dark grey so the strip is hard to see, or white again",
	"/rock strip ink <10-100> - how bright the squares are, in percent",
	"/rock strip inset <left> [edge] - distance from the left edge and from the top or bottom edge, in pixels",
	"/rock test - send a test pattern for ten seconds",
	"/rock status - what FreeRock sees, for bug reports",
}

local COMMANDS = {
	skip = { ns.Beacon.COMMAND_SKIP, "Asked FreeRock for something else." },
	love = { ns.Beacon.COMMAND_LOVE, "Told FreeRock you love this one." },
	ban = { ns.Beacon.COMMAND_BAN, "Told FreeRock never to play this one again." },
}

local function Whole(text)
	local number = tonumber(text)
	if number and number % 1 == 0 then
		return number
	end
	return nil
end

local function Strip(first, second, third)
	if ns.IsOneOf(first, "top", "bottom") then
		Set("edge", first)
	elseif first == "size" and Whole(second) and Whole(second) >= 1 and Whole(second) <= 8 then
		Set("cell", Whole(second))
	elseif first == "faint" then
		Set("ink", 20)
	elseif first == "bright" then
		Set("ink", 100)
	elseif first == "ink" and Whole(second) and Whole(second) >= 10 and Whole(second) <= 100 then
		Set("ink", Whole(second))
	elseif first == "inset" and Whole(second) and Whole(second) >= 0 and Whole(second) <= 2000
		and (third == nil or third == "" or (Whole(third) and Whole(third) >= 0 and Whole(third) <= 500)) then
		ns.db.insetX = Whole(second)
		if Whole(third) then
			ns.db.insetY = Whole(third)
		end
		ns.Refresh()
	else
		return false
	end
	for _, line in ipairs(ns.Beacon:Describe()) do
		ns.Print(line)
	end
	if ns.db.ink < 100 or ns.db.cell < 2 then
		ns.Print("If FreeRock loses a strip this faint or this small, the sensor's window says so. /rock strip bright and /rock strip size 3 put it back.")
	end
	return true
end

SLASH_FREEROCK1 = "/rock"
SLASH_FREEROCK2 = "/freerock"
SlashCmdList.FREEROCK = function(message)
	local command, first, second, third = strsplit(" ", strtrim(message or ""):lower())
	if command == nil or command == "" then
		Options:Open()
	elseif command == "on" then
		Set("enabled", true)
		ns.Print("On. The game's own music is off while FreeRock is on.")
	elseif command == "off" then
		Set("enabled", false)
		ns.Print("Off. The game's own music setting is back as you had it.")
	elseif COMMANDS[command] then
		if ns.db.enabled then
			ns.Beacon:Command(COMMANDS[command][1])
			ns.Print(COMMANDS[command][2])
		else
			ns.Print("FreeRock is off. /rock on turns it on.")
		end
	elseif command == "volume" and Whole(first) and Whole(first) >= 0 and Whole(first) <= 100 then
		Set("volume", Whole(first))
		ns.Print(("Volume %d."):format(ns.db.volume))
	elseif command == "gamemusic" and ns.IsOneOf(first, "on", "off") then
		Set("muteGameMusic", first == "off")
		ns.Print(first == "off" and "The game's own music is switched off while FreeRock is on."
			or "The game's own music is left as you have it.")
	elseif command == "strip" and Strip(first, second, third) then
		-- Strip has said what the strip looks like now.
	elseif command == "test" then
		Test()
	elseif command == "status" then
		PrintStatus()
	else
		for _, line in ipairs(HELP) do
			ns.Print(line)
		end
	end
end
