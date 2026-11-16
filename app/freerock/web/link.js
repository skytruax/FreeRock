// The page that shows what FreeRock sees. The server sends a full picture of things over a
// WebSocket whenever something changes; this file only draws it.
"use strict";

const byId = (id) => document.getElementById(id);
const set = (id, text) => { byId(id).textContent = text; };

const LINK_WORDS = {
  never: ["Waiting", "No strip has been read yet. Start the sensor on the gaming PC and turn FreeRock on in the game."],
  live: ["Live", "The strip is being read."],
  stale: ["Holding", "The strip cannot be read right now (a loading screen, a hidden interface, or the game not in front). The last state is being held."],
  lost: ["Lost", "The strip has not been read for a long time."],
  off: ["Off in game", "FreeRock is switched off in the game (/rock on turns it on)."],
};

const FLAGS = [
  ["indoors", "Indoors"], ["resting", "Resting"], ["in_combat", "In combat"], ["encounter", "Boss fight"],
  ["stealthed", "Stealth"], ["mounted", "Mounted"], ["flying", "Flying"], ["on_taxi", "Flight path"],
  ["swimming", "Swimming"], ["submerged", "Under water"], ["dead", "Dead"], ["ghost", "Ghost"],
  ["in_group", "In a group"], ["boss_present", "Boss present"], ["cinematic", "Cinematic"], ["loading", "Loading screen"],
];

const words = (value, unknown) => (value === null || value === undefined || value === "" ? unknown : String(value));

function drawLink(shot) {
  const [label, sentence] = LINK_WORDS[shot.link] || [shot.link, ""];
  const pill = byId("link");
  pill.textContent = label;
  pill.dataset.link = shot.link;
  let summary = sentence;
  if (!shot.sensor && shot.link !== "never") {
    summary = "No sensor is connected, so nothing new is being read. What is shown below is the last state read.";
  } else if (shot.link === "stale" && shot.seconds_since_read !== null) {
    summary += ` Last read ${shot.seconds_since_read.toFixed(1)} s ago.`;
  }
  set("summary", summary);

  const sensor = shot.sensor;
  if (!sensor) {
    set("sensor", "none connected");
    set("window", "not known");
    set("copy", "not known");
  } else {
    const what = sensor.note ? `waiting: ${sensor.note}` : (sensor.mode === "track" ? "reading the strip" : "looking for the strip");
    set("sensor", `${sensor.address}, ${what}`);
    set("window", sensor.window ? `${sensor.window[0]} x ${sensor.window[1]} px${sensor.in_front ? "" : ", not in front"}` : "not found");
    const each = sensor.copy_ms === null || sensor.copy_ms === undefined ? "" : `, ${sensor.copy_ms} ms each`;
    set("copy", sensor.copy_rate === null || sensor.copy_rate === undefined ? "not known" : `${sensor.copy_rate} a second${each}`);
  }
  set("rate", shot.read_rate.toFixed(1));
  set("reads", `${shot.counts.read} / ${shot.counts.pictures}`);
  set("checksum", String(shot.counts.checksum));
  const strip = shot.strip;
  set("strip", strip.found
    ? `at ${strip.box[0]}, ${strip.box[1]}: ${strip.box[2]} x ${strip.box[3]} px, squares of ${strip.pitch} px`
    : "not found");
  set("test", shot.test_pattern_seconds_ago === null
    ? "not seen (type /rock test in the game)"
    : `read correctly ${shot.test_pattern_seconds_ago} s ago`);
}

function drawState(game) {
  if (!game) {
    return;
  }
  set("zone", `${words(game.zone_name, "name not arrived yet")}${game.map_id ? ` (map ${game.map_id})` : ""}`);
  set("subzone", game.has_subzone ? words(game.subzone_name, "name not arrived yet") : "none");
  set("position", game.position ? `${(game.position[0] * 100).toFixed(1)}, ${(game.position[1] * 100).toFixed(1)}` : "the game gives none here");
  set("instance", game.in_instance
    ? `${words(game.instance_name, "name not arrived yet")} (${game.instance_kind}, number ${game.instance_id}, difficulty ${game.difficulty})`
    : "none");
  set("encounter", game.encounter ? `${words(game.encounter_name, "name not arrived yet")} (number ${game.encounter_id})` : "none");
  set("speed", game.speed === null || game.speed === undefined
    ? "not reported (an older addon, or the game gives none)" : `${game.speed} yards a second`);
  set("target", game.has_target
    ? `${game.target_class}${game.target_hostile ? ", can be fought" : ""}` : "none");
  const count = (value) => value >= 14 ? "14 or more" : String(value);
  set("enemies", game.enemies === null || game.enemies === undefined
    ? "not reported (an older addon, or the game does not say)"
    : `${count(game.enemies)} with a nameplate on screen, ${count(game.fighting)} in a fight`);
  set("weather", game.weather === null ? "not reported by the game"
    : `${game.weather}${game.weather_intensity === null ? "" : `, intensity ${game.weather_intensity}`}`);
  set("daylight", game.daytime === null ? "not reported by the game" : (game.daytime ? "day" : "night"));
  set("clock", game.game_minutes === null ? "not reported"
    : `${String(Math.floor(game.game_minutes / 60)).padStart(2, "0")}:${String(game.game_minutes % 60).padStart(2, "0")}`);
  set("pvp", game.pvp_kind === "unknown" ? "not reported" : game.pvp_kind);
  set("volume", `${game.volume}${game.enabled ? "" : " (FreeRock is off in the game)"}`);

  const list = byId("flags");
  list.replaceChildren(...FLAGS.map(([key, label]) => {
    const item = document.createElement("li");
    item.textContent = label;
    if (game[key]) {
      item.className = "on";
    }
    return item;
  }));
}

let lastLogLength = -1;
let lastLogStamp = "";
function drawLog(entries) {
  const stamp = entries.length ? entries[entries.length - 1].at + entries[entries.length - 1].text : "";
  if (entries.length === lastLogLength && stamp === lastLogStamp) {
    return;
  }
  lastLogLength = entries.length;
  lastLogStamp = stamp;
  byId("nolog").hidden = entries.length > 0;
  const list = byId("log");
  list.replaceChildren(...entries.slice().reverse().map((entry) => {
    const item = document.createElement("li");
    item.dataset.kind = entry.kind;
    const when = document.createElement("time");
    when.dateTime = entry.at;
    when.textContent = entry.at.slice(11, 23);
    const what = document.createElement("span");
    what.textContent = entry.text;
    item.append(when, what);
    return item;
  }));
}

let pictureStamp = "";
function drawPicture(shot) {
  // Fetch the captured strip again only when a new picture has been read or received.
  const stamp = `${shot.counts.pictures}`;
  if (stamp === pictureStamp || shot.counts.pictures === 0) {
    return;
  }
  pictureStamp = stamp;
  const picture = byId("picture");
  picture.src = `/api/strip.png?n=${stamp}`;
  picture.hidden = false;
  set("caption", shot.strip.found
    ? "The strip as the gaming PC captured it, enlarged three times."
    : "The last picture in which a strip was looked for, enlarged three times. It could not be read.");
}
byId("picture").addEventListener("error", () => {
  byId("picture").hidden = true;
  set("caption", "No strip has been captured yet.");
});

function draw(shot) {
  drawLink(shot);
  drawState(shot.state);
  drawLog(shot.log);
  drawPicture(shot);
}

let wait = 500;
function connect() {
  const socket = new WebSocket(`ws://${location.host}/ws/ui`);
  socket.addEventListener("open", () => {
    wait = 500;
    byId("offline").hidden = true;
  });
  socket.addEventListener("message", (event) => draw(JSON.parse(event.data)));
  socket.addEventListener("close", () => {
    byId("offline").hidden = false;
    setTimeout(connect, wait);
    wait = Math.min(wait * 2, 5000);
  });
}
connect();
