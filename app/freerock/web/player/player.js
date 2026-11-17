// The FreeRock player page: connects the forever song's engine (forever.js) to the FreeRock server.
//
// The server says which bucket to play from and what the target is; this page fetches the
// phrases the engine asks for and shows what is going on. If the server cannot be reached the
// music that is playing carries on, and after a minute it fades out under a notice.
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  let ctx = null, engine = null, socket = null;
  let target = null;            // the last target the server sent, kept for when the engine is made
  let retry = 500;              // milliseconds until the next attempt to reconnect
  let lostAt = null;            // when the server was last lost, if it is lost now
  let gameVolume = null;        // the volume last set from inside the game
  let playing = null;           // the bucket the server last sent
  let version = null;           // the version of this page, as the server named it when it loaded
  let outdated = false;         // the server has been updated since
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
  window.addEventListener("unhandledrejection", (event) => problem(describe(event.reason)));

  // What went wrong and where. Some browsers leave the message out of the trace, so both are given.
  function describe(error) {
    if (!error) return String(error);
    const said = String(error.message || error), trace = error.stack ? String(error.stack) : "";
    return trace.includes(said) ? trace : (error.name ? error.name + ": " : "") + said + (trace ? "\n" + trace : "");
  }

  function banner(text) {
    $("banner").hidden = !text;
    $("banner").textContent = text || "";
  }

  // One whole phrase from a bucket, or one stretch of a part of a piece.
  async function phraseLoader(key, clipId) {
    const response = await fetch("/phrase/" + key + "/" + clipId);
    if (!response.ok) throw new Error("The server would not give the phrase " + clipId + " (" + response.status + "): " + await response.text());
    return response.arrayBuffer();
  }

  function volume() { return Number($("volume").value) / 100; }

  // What the player began lately, kept in this browser between visits to the page, so that a reload does not bring
  // back what was just heard. A browser that keeps nothing (a private window) is said on the page, and the music
  // goes on without it.
  const HEARD = "freerock.heard.v1";
  const heard = {
    load() {
      try {
        const text = window.localStorage.getItem(HEARD);
        return text ? JSON.parse(text) : {};
      } catch (error) {
        problem("This browser does not keep what was played between visits (" + error.message + "): a reload may bring back what was just heard.");
        return {};
      }
    },
    save(kept) {
      try {
        window.localStorage.setItem(HEARD, JSON.stringify(kept));
      } catch (error) {
        problem("This browser could not keep what was played (" + error.message + ").");
      }
    },
  };

  // The server sends the bucket the style plays from, and the five decks play from it.
  async function useBucket(message) {
    const bucket = message.bucket;
    if (!ctx) ctx = new AudioContext({ sampleRate: bucket.rate, latencyHint: "interactive" });
    if (!engine) {
      engine = new FreeRockForever(ctx, phraseLoader, { report: problem, memory: heard });
      engine.setVolume(volume());
      if (target) await engine.setTarget(target);
    }
    await engine.setBucket(bucket);
    playing = bucket;
    musicLine();
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

  // What the bucket holds: written pieces (each kept as its parts) and loose phrases.
  function musicLine() {
    if (!playing) return;
    const clips = engine && engine.bucket ? Array.from(engine.bucket.clips.values()) : playing.clips;
    const loose = clips.filter((clip) => !clip.piece).length;
    const pieces = new Set(clips.filter((clip) => clip.piece).map((clip) => clip.piece)).size;
    const style = playing.style || playing.genre;
    if (pieces) {
      $("music").textContent = "A song that never ends (" + style + "): " + pieces + " written pieces, strung together"
        + " for the kind of place you are in and what is happening there"
        + (loose ? ", with " + loose + " loose phrases (" + playing.bpm + " BPM, " + playing.tonic + ") to play between them." : ".");
      return;
    }
    $("music").textContent = "A song that never ends (" + style + ", " + playing.bpm + " BPM, "
      + playing.tonic + "), put together as it goes from " + loose + " phrases, each a verse, a build-up and a chorus"
      + " for one instrument.";
  }

  function show(message) {
    const t = message.target, where = message.where || {};
    $("where").textContent = [where.instance || where.zone, where.subzone].filter(Boolean).join(", ") || "Waiting for the game";
    $("place").textContent = t.silent ? "silence"
      : t.rest ? "a rest: no music for a little while, as in the game"
      : t.place + ((t.also || []).length ? ", taking turns with " + t.also.join(" and ") : "")
        + (t.cut === "beat" ? " (on the beat)" : "")
        // The kind of place this is, which is what written pieces are chosen by.
        + ((t.kinds || []).length ? ", in a " + t.kinds.join(" and ") + " place" + (t.light ? " (a light one)" : "") : "");
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
    if (message.type === "hello" && message.version) {
      if (version === null) version = message.version;
      else if (message.version !== version) outdated = true;
      if (outdated) banner("FreeRock has been updated. Reload this page (F5) to use the new version. The music carries on until you do.");
    }
    if (message.type === "bucket") await useBucket(message);
    else if (message.type === "retired" && engine) { engine.dropClips(message.key, message.ids); musicLine(); }
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
    else if (message.type === "moment" && engine) await engine.moment(message.name);
    // Every message is also a nudge to look at the queue, so the music never depends on a timer
    // that the browser may slow down while the game is in front.
    if (engine) await engine.tick();
  }

  function connect() {
    const scheme = location.protocol === "https:" ? "wss://" : "ws://";
    socket = new WebSocket(scheme + location.host + "/ws/player");
    socket.onopen = () => { retry = 500; lostAt = null; if (!outdated) banner(""); $("link").textContent = "Connected. Waiting for the game."; };
    socket.onmessage = (event) => { receive(JSON.parse(event.data)).catch((error) => problem(describe(error))); };
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
  $("speakerTest").addEventListener("click", () => {
    if (engine && engine.testSpeakers) engine.testSpeakers((name) => { $("speakerNow").textContent = name ? "now: " + name : ""; });
  });
  $("skip").addEventListener("click", () => {
    if (engine) engine.skip().catch((error) => problem(String(error)));
  });

  // --- the style ---------------------------------------------------------------------------------
  // Three kinds of music, each with a bucket of its own: the one in force is what is played.
  function drawStyles(styles) {
    $("styles").replaceChildren(...styles.genres.map((genre) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = genre.label;
      button.title = genre.about;
      button.className = genre.key === styles.genre ? "chosen" : "quiet";
      button.setAttribute("aria-pressed", genre.key === styles.genre ? "true" : "false");
      button.addEventListener("click", () => chooseStyle(genre.key));
      return button;
    }));
    $("pieces").checked = styles.pieces !== "off";
    const chosen = styles.genres.find((genre) => genre.key === styles.genre);
    $("styleAbout").textContent = chosen ? chosen.label + ": " + chosen.about + "." : "";
  }
  async function loadStyles() {
    const response = await fetch("/api/style");
    if (!response.ok) throw new Error("The styles could not be fetched (" + response.status + ")");
    drawStyles(await response.json());
  }
  async function chooseStyle(key) {
    const response = await fetch("/api/style", { method: "POST", headers: { "Content-Type": "application/json" },
                                                 body: JSON.stringify({ genre: key }) });
    if (!response.ok) { problem("The style was not changed: " + await response.text()); return; }
    drawStyles(await response.json());
  }
  // Written pieces on or off: the server tells every page at once what there now is to play from.
  $("pieces").addEventListener("change", async () => {
    const response = await fetch("/api/style", { method: "POST", headers: { "Content-Type": "application/json" },
                                                 body: JSON.stringify({ pieces: $("pieces").checked ? "on" : "off" }) });
    if (!response.ok) { problem("Written pieces were not switched: " + await response.text()); return; }
    drawStyles(await response.json());
  });
  loadStyles().catch((error) => problem(String(error)));

  // --- the pretend game ----------------------------------------------------------------------
  // Stands in for the game while it is not connected: every change is sent to the server as if
  // the strip had been read.
  function pretendState() {
    const on = (field) => document.querySelector('#pretend [data-field="' + field + '"]').checked;
    const targetClass = $("p-target").value, weather = $("p-weather").value;
    return {
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
    $("p-zone").replaceChildren(...(await response.json()).map((name) => {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      option.selected = name === (chosen || "Elwynn Forest");
      return option;
    }));
  }
  $("pretend").addEventListener("toggle", () => {
    if ($("pretend").open) fillZones().then(sendPretend).catch((error) => problem(String(error)));
  });
  $("pretend").addEventListener("change", sendPretend);
  $("p-strength").addEventListener("input", () => { $("p-strengthValue").textContent = $("p-strength").value; });

  setInterval(() => {
    if (!engine) return;
    engine.tick().catch((error) => problem(describe(error)));
    const status = engine.status();
    if (status.speakers) {
      // Where the music is going: said on the page, since nothing else shows it.
      $("speakersRow").hidden = false;
      $("speakers").textContent = status.speakers === 6 ? "5.1: the front pair, the centre, the sub and the rear pair"
                                                        : "two (the browser offers no more)";
    }
    // The five decks: which channels can be heard, and how hard each is playing.
    const strength = ["calm", "steady", "hard"];
    const up = Object.entries(status.playing).map(([channel, clip]) => channel + " (" + strength[clip.tier] + ")");
    // The song also rises and falls of its own accord, a turn of its form at a time.
    const wave = status.wave < 0 ? ", easing off for a turn" : status.wave > 0 ? ", leaning in for a turn" : "";
    $("section").textContent = status.resting ? "a moment of silence" : up.length ? up.length + " of 5 channels" + wave : "nothing yet";
    $("decks").textContent = up.join(", ") || "none";
    // A written piece: what it is called and how far through it the music is.
    const piece = status.resting ? null : status.piece;
    $("pieceRow").hidden = !piece;
    if (piece) {
      const clock = (seconds) => Math.floor(seconds / 60) + ":" + String(Math.floor(seconds % 60)).padStart(2, "0");
      const kind = piece.role && piece.role !== "wander" ? ", for " + piece.role : "";
      $("piece").textContent = piece.title + kind + " (" + clock(piece.of > 0 ? piece.at % piece.of : piece.at)
        + " of " + clock(piece.of) + ")";
    }
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
