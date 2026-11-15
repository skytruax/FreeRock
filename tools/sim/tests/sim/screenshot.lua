-- Runs in the simulator after login, just before the screenshot is taken (tools/sim/run.sh).
--
-- The simulator draws one interface unit as about two thirds of a screenshot pixel where the game
-- draws FreeRock's strip pixel for pixel, so at the usual 3 px the squares in the screenshot are
-- too small to read. With the largest squares that fit they come out near 4 px, and
-- tools/sim/run.sh then reads the strip back out of the screenshot with the app's own reader: the
-- addon's drawing, rendered by code that is not ours, read by the reader.
A_Admin.SetZone("Westfall", 40)
A_Admin.SetSubZone("Sentinel Hill")
A_Admin.FireEvent("ZONE_CHANGED_NEW_AREA")
A_Admin.SetResting(true)
A_Admin.FireEvent("PLAYER_UPDATE_RESTING")
SlashCmdList.FREEROCK("strip size 6")
SlashCmdList.FREEROCK("volume 55")
