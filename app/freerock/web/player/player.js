// The FreeRock player page: connects the audio engine (engine.js) to the FreeRock server.
//
// The server says which music to play and what the target is; this page fetches the audio the
// engine asks for and shows what is going on. If the server cannot be reached the music that is
// playing carries on, and after a minute it fades out under a notice.
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  let ctx = null, engine = null, socket = null;
  let target = null;            // the last target the server sent, kept for when the engine is made
  let retry = 500;              // milliseconds until the next attempt to reconnect
  let lostAt = null;            // when the server was last lost, if it is lost now
  let gameVolume = null;        // the volume last set from inside the game
  let playing = null;           // the music the server last sent
  const problems = [];

  // Anything that goes wrong is shown on the page and sent to the server, never dropped.
  function problem(text) {
    problems.push(new Date().toLocaleTimeString() + "  " + text);
    $("problems").hidden = false;
    $("problems").textContent = problems.slice(-6).join("\n");
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "problem", message: text }));
    }
  }
  window.addEventListener("error", (event) => problem(event.message + " (" + event.filename + ":" + event.lineno + ")"));
  window.addEventListener("unhandledrejection", (event) => problem(String(event.reason && event.reason.stack || event.reason)));

  function banner(text) {
    $("banner").hidden = !text;
    $("banner").textContent = text || "";
  }

  async function loader(assetId, layer, start, end) {
    const response = await fetch("/audio/" + assetId + "/" + layer + "?start=" + start + "&end=" + end);
    if (!response.ok) throw new Error("The server would not give audio (" + response.status + "): " + await response.text());
    return response.arrayBuffer();
  }

  function volume() { return Number($("volume").value) / 100; }

  async function useAsset(message) {
    const asset = message.asset;
    if (!ctx) {
      // The player runs at the music's own sample rate, so nothing is resampled and the three
      // layers stay locked.
      ctx = new AudioContext({ sampleRate: asset.rate, latencyHint: "playback" });
      engine = new FreeRockEngine(ctx, loader);
      engine.setVolume(volume());
      if (target) await engine.setTarget(target);
    }
    await engine.setAsset(asset);
    playing = asset;
    musicLine(message.borrowed);
    await begin();
  }

  // Browsers only let a page make sound after a click, unless they were started with sound
  // allowed (the FreeRock launcher does that). Until then the Start button is shown.
  async function begin() {
    if (!engine || engine.started) return;
    if (ctx.state !== "running") { $("gate").hidden = false; return; }
    $("gate").hidden = true;
    await engine.start();
  }

  // Whose music is playing, and whether this place is only borrowing it.
  function musicLine(borrowed) {
    if (!playing) return;
    $("music").textContent = (borrowed ? "This place has no music of its own yet. Playing music made for " : "Music for ")
      + playing.zone + " (" + playing.set + " set, " + playing.bpm + " BPM, " + playing.tonic + ").";
  }

  function show(message) {
    const t = message.target, where = message.where || {};
    if (message.music) musicLine(message.music.borrowed);
    $("where").textContent = [where.instance || where.zone, where.subzone].filter(Boolean).join(", ") || "Waiting for the game";
    $("place").textContent = t.silent ? "silence"
      : t.rest ? "a rest: no music for a little while, as in the game"
      : t.place + (t.cut === "beat" ? " (on the beat)" : "");
    for (const name of ["intensity", "bed", "drums", "bass"]) $(name).style.width = Math.round(100 * t[name]) + "%";
    const tone = [];
    if (t.lowpass_hz < 19000) tone.push("muffled above " + Math.round(t.lowpass_hz) + " Hz");
    if (t.highpass_hz > 30) tone.push("thinned below " + Math.round(t.highpass_hz) + " Hz");
    if (t.reverb > 0) tone.push("echo " + Math.round(100 * t.reverb) + "%");
    if (t.volume < 1) tone.push("volume " + Math.round(100 * t.volume) + "%");
    $("tone").textContent = tone.join(", ") || "open";
    $("why").textContent = (t.why || []).join("; ") || "nothing is happening";
    $("link").textContent = message.link === "live" ? "Following the game." : "Game link: " + message.link + ".";
  }

  async function receive(message) {
    if (message.type === "asset") await useAsset(message);
    else if (message.type === "target") {
      target = message.target;
      if (engine) await engine.setTarget(target);
      // /rock volume in the game moves this page's volume control.
      if (message.game_volume !== null && message.game_volume !== gameVolume) {
        gameVolume = message.game_volume;
        $("volume").value = gameVolume;
        $("volumeValue").textContent = gameVolume;
        if (engine) engine.setVolume(volume());
      }
      show(message);
    } else if (message.type === "skip" && engine) await engine.skip();
    // Every message is also a nudge to look at the queue, so the music never depends on a timer
    // that the browser may slow down while the game is in front.
    if (engine) await engine.tick();
  }

  function connect() {
    const scheme = location.protocol === "https:" ? "wss://" : "ws://";
    socket = new WebSocket(scheme + location.host + "/ws/player");
    socket.onopen = () => { retry = 500; lostAt = null; banner(""); $("link").textContent = "Connected. Waiting for the game."; };
    socket.onmessage = (event) => { receive(JSON.parse(event.data)).catch((error) => problem(String(error && error.stack || error))); };
    socket.onclose = () => {
      if (lostAt === null) lostAt = Date.now();
      banner("The FreeRock server cannot be reached. The music carries on for a minute; trying again…");
      setTimeout(connect, retry);
      retry = Math.min(retry * 2, 5000);
    };
  }

  $("start").addEventListener("click", () => {
    ctx.resume().then(begin).catch((error) => problem(String(error)));
  });
  $("volume").addEventListener("input", () => {
    $("volumeValue").textContent = $("volume").value;
    if (engine) engine.setVolume(volume());
  });
  $("skip").addEventListener("click", () => {
    if (engine) engine.skip().catch((error) => problem(String(error)));
  });

  // --- the pretend game ----------------------------------------------------------------------
  // Stands in for the game while it is not connected: every change is sent to the server as if
  // the strip had been read.
  function pretendState() {
    const on = (field) => document.querySelector('#pretend [data-field="' + field + '"]').checked;
    const targetClass = $("p-target").value, weather = $("p-weather").value;
    return {
      make_new_music: $("p-make").checked,
      zone_name: $("p-zone").value, indoors: on("indoors"), resting: on("resting"),
      swimming: on("submerged"), submerged: on("submerged"), mounted: on("mounted"),
      on_taxi: on("on_taxi"), flying: on("on_taxi"), stealthed: on("stealthed"),
      in_combat: on("in_combat"), encounter: on("encounter"), dead: on("dead"),
      daytime: !on("night"), cinematic: on("cinematic"),
      has_target: targetClass !== "none", target_class: targetClass,
      weather: weather, weather_intensity: weather === "clear" ? 0 : Number($("p-strength").value) / 100,
    };
  }
  function sendPretend() {
    fetch("/api/pretend", { method: "POST", headers: { "Content-Type": "application/json" },
                            body: JSON.stringify(pretendState()) })
      .then(async (response) => { if (!response.ok) problem("The pretend game was refused: " + await response.text()); })
      .catch((error) => problem("The pretend game could not reach the server: " + error));
  }
  async function fillZones() {
    const response = await fetch("/api/zones");
    if (!response.ok) throw new Error("The list of zones could not be fetched (" + response.status + ")");
    const chosen = $("p-zone").value;
    $("p-zone").replaceChildren(...(await response.json()).map((zone) => {
      const option = document.createElement("option");
      option.value = zone.name;
      option.textContent = zone.name + (zone.has_music ? "" : "  (no music yet)");
      option.selected = zone.name === (chosen || "Elwynn Forest");
      return option;
    }));
  }
  $("pretend").addEventListener("toggle", () => {
    if ($("pretend").open) fillZones().then(sendPretend).catch((error) => problem(String(error)));
  });
  $("pretend").addEventListener("change", sendPretend);
  $("p-strength").addEventListener("input", () => { $("p-strengthValue").textContent = $("p-strength").value; });

  setInterval(() => {
    if ($("pretend").open && Date.now() % 15000 < 1000) fillZones().catch((error) => problem(String(error)));
    if (!engine) return;
    engine.tick().catch((error) => problem(String(error && error.stack || error)));
    const status = engine.status();
    $("section").textContent = status.section ? status.section + ", cell " + (status.cell + 1) : "nothing";
    if (lostAt !== null && Date.now() - lostAt > 60000 && !engine.target.silent) {
      banner("The FreeRock server has been out of reach for a minute. The music has faded out and returns when the server does.");
      engine.setTarget({ silent: true, fade_s: 2 }).catch((error) => problem(String(error)));
    }
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(Object.assign({ type: "status", context: ctx.state }, status)));
    }
  }, 1000);

  connect();
})();
