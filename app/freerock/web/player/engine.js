// The FreeRock player's audio engine.
//
// It plays a zone's music from the library as three layers (bed, drums, bass) that are started at
// the same instant, so they cannot drift apart. The music is cut into four-bar cells. The engine
// keeps one cell playing and the next one queued, changes section on a bar or beat line when the
// target asks for another kind of section, and moves the layer levels and the tone (muffle,
// echo, volume) as soon as the target changes.
//
// What plays next is always the section that has gone longest unheard among the kinds in
// rotation, so nothing comes round in a fixed order and no single part is left to loop.
//
// Nothing here waits on a timer to keep the music going: every start, cut and fade is scheduled
// ahead on the audio clock. tick() only decides what to queue next, and is safe to call late.
//
// The same file runs in the live page and in the offline tests, where the audio is rendered to
// memory and measured.
(function (root) {
  "use strict";

  const LAYERS = ["bed", "drums", "bass"];
  const LEAD = 0.010;        // a cell starts this long before its bar line, so a note struck early is kept
  const FADE = 0.015;        // length of the crossfade between two cells
  const NOTICE = 0.12;       // a cut is never asked for closer than this to now
  const QUEUE_AHEAD = 3.0;   // the next cell is chosen and loaded this long before it is needed
  const REST_IN = 3.5;       // how long the music takes to fade back in after a rest
  const REST_IN_FAST = 0.2;  // ...unless something has just happened, a fight say: then it is there at once
  const LOG_LENGTH = 500;    // how many scheduled cells are remembered
  const OPEN_HZ = 20000;
  const FALLBACK = { boss: "battle", battle: "wander", storm: "wander", night: "ember",
                     depths: "ember", ember: "wander", arrival: "wander" };
  // How fast a layer comes up and goes down, in seconds. Layers arrive almost at once, so the
  // music answers what the player does; they leave a little more slowly so that it does not
  // flicker. A target may ask for everything to move faster still (stealth does).
  const UP = { bed: 0.3, drums: 0.12, bass: 0.06 };
  const DOWN = { bed: 0.4, drums: 0.9, bass: 1.6 };
  const RAW_LIMIT = 48;      // cells kept as they came from the server, ready to be played at once
  const TURN_CELLS = 2;      // a section has the floor for this many cells (eight bars), then another has a turn
  const WIND_DOWN = 1.2;     // how long the music takes to run down, like a record stopping, at a death
  // Which sections are fetched ahead first: the ones a change in the game jumps to.
  const AHEAD = ["battle", "boss", "depths", "storm", "ember", "wander", "night", "arrival"];

  function gainOf(db) { return Math.pow(10, db / 20); }

  class Engine {
    // ctx:    an AudioContext, or an OfflineAudioContext in tests
    // loader: (assetId, layer, startFrame, endFrame) -> Promise<ArrayBuffer> of 16-bit stereo
    constructor(ctx, loader, options) {
      options = options || {};
      this.ctx = ctx;
      this.loader = loader;
      this.random = options.random || Math.random;
      this.asset = null;
      this.target = { place: "wander", also: [], scene: 0, scene_tag: null, cut: "bar", bed: 1, drums: 0, bass: 0,
                      bed_highpass_hz: 110, lowpass_hz: OPEN_HZ, highpass_hz: 20, reverb: 0, volume: 1,
                      silent: false, rest: false, fade_s: 0.4 };
      this.userVolume = 1;
      this.current = null;       // the cell that is playing
      this.queued = null;        // the cell that will follow it
      this.started = false;
      this.cache = new Map();    // "asset:startFrame" -> { bed, drums, bass } AudioBuffers
      this.cacheLimit = options.cacheLimit || 10;
      // The same cells as the server sent them, 16 bits a sample: a third of the size, and what
      // is fetched ahead of time so that a change of section never waits for the network.
      this.raw = new Map();      // "asset:startFrame" -> Promise of { bed, drums, bass } ArrayBuffers
      this.ahead = options.ahead !== false;
      this.late = 0;             // cells that could not be loaded in time and started late
      this.restSince = null;     // when the rest that is going on began, on the audio clock
      this.played = new Map();   // section key -> its turn number the last time it was started
      this.turn = 0;
      this.scenePending = false; // the player crossed into another part of the zone: change riff
      this.resume = new Map();   // section key -> the cell it goes on from when its turn comes round again
      this.holdUntil = 0;        // nothing new starts before this (the music is running down)
      this.log = [];             // what was scheduled and when, for the status page and the tests
      this._busy = Promise.resolve();

      // The graph: three layer levels, the bed's own high-pass, then tone, echo, volume, limiter.
      this.layerGain = {};
      this.bus = ctx.createGain();
      this.bedHighpass = ctx.createBiquadFilter();
      this.bedHighpass.type = "highpass";
      this.bedHighpass.frequency.value = 110;
      this.bedHighpass.Q.value = 0.707;
      for (const layer of LAYERS) {
        const gain = ctx.createGain();
        gain.gain.value = this.target[layer];
        this.layerGain[layer] = gain;
        if (layer === "bed") gain.connect(this.bedHighpass).connect(this.bus); else gain.connect(this.bus);
      }
      // Two low-pass filters in a row: twice as steep as one, so "muffled" is plain to hear even
      // on guitars and lute, which have little at the very top to take away.
      this.toneLow = ctx.createBiquadFilter();
      this.toneLow2 = ctx.createBiquadFilter();
      for (const filter of [this.toneLow, this.toneLow2]) {
        filter.type = "lowpass";
        filter.frequency.value = this._ceiling(OPEN_HZ);
        filter.Q.value = 0.707;
      }
      this.toneHigh = ctx.createBiquadFilter();
      this.toneHigh.type = "highpass";
      this.toneHigh.frequency.value = 20;
      this.toneHigh.Q.value = 0.707;
      this.send = ctx.createGain();
      this.send.gain.value = 0;
      this.echo = ctx.createConvolver();
      this.echo.buffer = this._room(1.6);
      this.master = ctx.createGain();
      this.master.gain.value = 0;
      this.bus.connect(this.toneLow).connect(this.toneLow2).connect(this.toneHigh);
      this.toneHigh.connect(this.master);
      this.toneHigh.connect(this.send).connect(this.echo).connect(this.master);
      if (options.limiter === false) {
        this.master.connect(ctx.destination);
      } else {
        this.limiter = ctx.createDynamicsCompressor();
        this.limiter.threshold.value = -2;
        this.limiter.knee.value = 0;
        this.limiter.ratio.value = 20;
        this.limiter.attack.value = 0.002;
        this.limiter.release.value = 0.2;
        // The limiter turns loud passages down but takes a moment to react. The ceiling after it
        // is instant: untouched up to nine tenths of full scale, bending over above that, and
        // never passing full scale whatever arrives.
        this.ceiling = ctx.createWaveShaper();
        const points = 4097, curve = new Float32Array(points);
        for (let i = 0; i < points; i++) {
          const x = (2 * i) / (points - 1) - 1, size = Math.abs(x);
          curve[i] = size <= 0.9 ? x : Math.sign(x) * (0.9 + 0.1 * Math.tanh((size - 0.9) / 0.1));
        }
        this.ceiling.curve = curve;
        this.master.connect(this.limiter).connect(this.ceiling).connect(ctx.destination);
      }
    }

    _ceiling(hz) { return Math.min(hz, this.ctx.sampleRate * 0.45); }

    // An echoing space: a burst of noise that dies away over `seconds`.
    _room(seconds) {
      const rate = this.ctx.sampleRate, length = Math.floor(seconds * rate);
      const buffer = this.ctx.createBuffer(2, length, rate);
      let seed = 12345;
      const noise = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x3fffffff - 1; };
      for (let channel = 0; channel < 2; channel++) {
        const data = buffer.getChannelData(channel);
        for (let i = 0; i < length; i++) data[i] = noise() * Math.exp(-6.9 * i / length);
      }
      return buffer;
    }

    // One thing at a time: loading a cell takes a moment, and two decisions made while one is
    // loading must not both act on the same "what is playing now".
    _serial(work) {
      const run = this._busy.then(work);
      this._busy = run.catch(() => {});
      return run;
    }

    // --- the asset ---------------------------------------------------------------------------

    // The music for a place. It may come from several requests (a core suite and later sets): each
    // section says which one its audio is in. When more music arrives for the place that is
    // already playing, nothing is cut; the new sections simply join the rotation.
    setAsset(asset) {
      return this._serial(async () => {
        if (asset.rate !== this.ctx.sampleRate) {
          throw new Error("The music is at " + asset.rate + " Hz and the player at " + this.ctx.sampleRate +
                          " Hz; they have to match for the layers to stay locked");
        }
        // Every section remembers which request its audio is in, so a cell that is playing when
        // more music arrives still knows where its own next cell comes from.
        for (const section of asset.sections) {
          section.asset_id = section.asset_id || asset.id;
          section.key = section.asset_id + ":" + section.name;
        }
        const before = this.asset;
        const changed = !before || before.id !== asset.id;
        const samePlace = before && before.zone !== undefined && before.zone === asset.zone &&
                          before.genre === asset.genre && before.bar_frames === asset.bar_frames;
        const had = new Set(before ? before.sections.map((section) => section.key) : []);
        this.asset = asset;
        if (changed && this.ahead) this._fetchAhead(asset);
        if (changed && this.started && !samePlace && !this.target.rest) {
          await this._moveTo(this._sectionFor(this.target.place, true), "bar");
        } else if (changed && this.started && samePlace && !this.target.rest) {
          // More music for the zone that is playing does not interrupt it, with one exception:
          // a piece made for the very place the player is standing in is what they are waiting
          // for, and it comes in on the next bar.
          const here = this.target.scene_tag || null;
          const fresh = asset.sections.find((section) => here && section.tag === here && !had.has(section.key));
          const playing = this.queued || this.current;
          if (fresh && playing && this._pool().includes(fresh.role) && this._pool().includes(playing.section.role)) {
            await this._moveTo(fresh, "bar");
          }
        }
      });
    }

    // Fetches the first cell of every section in the background, the ones a change in the game
    // jumps to first. Nothing waits for this; a cell that is needed before its turn comes is
    // fetched at once by whoever needs it. A fetch that fails is reported by the page (it is an
    // unhandled rejection there) and tried again when the cell is needed.
    _fetchAhead(asset) {
      const order = asset.sections.slice().sort((a, b) => AHEAD.indexOf(a.role) - AHEAD.indexOf(b.role));
      let chain = Promise.resolve();
      for (const section of order) {
        chain = chain.then(() => (this.asset === asset ? this._raw(asset, section, 0) : null));
      }
      return chain;
    }

    _roles() { return new Set(this.asset.sections.map((section) => section.role)); }

    _playable(place) {
      const roles = this._roles(), seen = new Set();
      while (!roles.has(place)) {
        if (seen.has(place) || !(place in FALLBACK)) {
          throw new Error("Nothing to play for " + place + "; this music has only " + Array.from(roles).join(", "));
        }
        seen.add(place);
        place = FALLBACK[place];
      }
      return place;
    }

    // The kinds of section in rotation right now: the kind the target asks for, and the kinds it
    // says take turns with it (the zone's riffs in a cave, the Night part at night). Kinds this
    // music does not have are left out.
    _pool() {
      const roles = this._roles(), pool = [this._playable(this.target.place)];
      for (const role of this.target.also || []) {
        if (roles.has(role) && !pool.includes(role)) pool.push(role);
      }
      return pool;
    }

    // The section of these kinds that has gone longest without being played. `except` is the one
    // playing now; it is not chosen again while there is anything else.
    // A section made for one named place inside the zone (it carries that place's tag) is in
    // the running only while the player is there.
    _pick(roles, except) {
      const here = this.target.scene_tag || null;
      let choices = this.asset.sections.filter((section) =>
        roles.includes(section.role) && (!section.tag || section.tag === here));
      if (except && choices.length > 1) choices = choices.filter((section) => section.key !== except.key);
      let oldest = Infinity, longest = [];
      for (const section of choices) {
        const last = this.played.has(section.key) ? this.played.get(section.key) : -1;
        if (last < oldest) { oldest = last; longest = [section]; }
        else if (last === oldest) longest.push(section);
      }
      return longest[Math.floor(this.random() * longest.length) % longest.length];
    }

    // The section to go to for a place. Arriving somewhere new starts with the Arrival part.
    _sectionFor(place, arriving) {
      const role = this._playable(place);
      if (arriving && role === "wander") {
        const arrival = this.asset.sections.find((section) => section.role === "arrival");
        if (arrival) return arrival;
      }
      return this._pick([role], null);
    }

    // Where a section goes on from when its turn comes round: the cell after the last one it
    // played, or its beginning.
    _resumeAt(section) {
      const index = this.resume.get(section.key) || 0;
      return index < section.cells.length ? index : 0;
    }

    // Leaves a section for another: remembers where it had got to, and fetches that cell now so
    // that it is ready when the section's turn comes round again.
    _leave(section, nextIndex) {
      const index = nextIndex < section.cells.length ? nextIndex : 0;
      this.resume.set(section.key, index);
      if (this.ahead && this.asset.sections.includes(section)) this._raw(this.asset, section, index);
    }

    // What follows a cell when nothing has changed. A section has the floor for a couple of
    // cells (eight bars), then whichever section in rotation has gone longest unheard has a turn,
    // going on from where it left off. So the riff changes often, and no pass through a riff is
    // the same stretch of it as the last. Where there is only one section to play (a fight), it
    // simply carries on.
    _following(cell) {
      const section = cell.section, pool = this._pool();
      const next = cell.index + 1, more = next < section.cells.length;
      this.scenePending = false;
      const turnOver = !more || (cell.run || 1) >= TURN_CELLS;
      if (turnOver) {
        const other = this._pick(pool, section);
        if (other.key !== section.key) {
          this._leave(section, next);
          return { section: other, index: this._resumeAt(other), run: 1 };
        }
      }
      return { section, index: more ? next : 0, run: (cell.run || 1) + 1 };
    }

    // --- loading -----------------------------------------------------------------------------

    // The three layers of one cell as the server sends them. Asked for once however many want it;
    // a fetch that failed is forgotten, so the next one to need the cell tries again.
    _raw(asset, section, index) {
      const cell = section.cells[index];
      const from = section.asset_id;                  // which request's audio this section is in
      const key = from + ":" + cell.start;
      if (this.raw.has(key)) {
        const found = this.raw.get(key);
        this.raw.delete(key);
        this.raw.set(key, found);            // most recently used goes to the back
        return found;
      }
      const rate = asset.rate;
      const first = cell.start - Math.round(LEAD * rate);
      const last = cell.end - Math.round(LEAD * rate) + Math.round(FADE * rate);
      const fetched = Promise.all(LAYERS.map(async (layer) => {
        const bytes = await this.loader(from, layer, first, last);
        if (bytes.byteLength !== (last - first) * 4) {
          throw new Error("Asked for " + (last - first) + " frames of " + layer + ", got " + bytes.byteLength / 4);
        }
        return bytes;
      })).then((layers) => ({ frames: last - first, bed: layers[0], drums: layers[1], bass: layers[2] }));
      fetched.catch(() => { if (this.raw.get(key) === fetched) this.raw.delete(key); });
      this.raw.set(key, fetched);
      while (this.raw.size > RAW_LIMIT) this.raw.delete(this.raw.keys().next().value);
      return fetched;
    }

    async _load(asset, section, index) {
      const cell = section.cells[index];
      const key = section.asset_id + ":" + cell.start;
      if (this.cache.has(key)) {
        const found = this.cache.get(key);
        this.cache.delete(key);
        this.cache.set(key, found);          // most recently used goes to the back
        return found;
      }
      const raw = await this._raw(asset, section, index);
      const loaded = {};
      for (const layer of LAYERS) {
        const samples = new Int16Array(raw[layer]);
        const buffer = this.ctx.createBuffer(2, raw.frames, asset.rate);
        const left = buffer.getChannelData(0), right = buffer.getChannelData(1);
        for (let i = 0, n = raw.frames; i < n; i++) {
          left[i] = samples[2 * i] / 32768;
          right[i] = samples[2 * i + 1] / 32768;
        }
        loaded[layer] = buffer;
      }
      this.cache.set(key, loaded);
      while (this.cache.size > this.cacheLimit) this.cache.delete(this.cache.keys().next().value);
      return loaded;
    }

    // --- scheduling --------------------------------------------------------------------------

    // Starts a cell so that its first bar line falls at `when`. All three layers start together.
    _schedule(section, index, buffers, when, fadeIn, run) {
      const ctx = this.ctx, cell = section.cells[index];
      const length = (cell.end - cell.start) / this.asset.rate;
      const base = gainOf(section.gain_db);
      // The length of a bar is kept with the cell: when the zone changes, the music that is
      // playing is still cut on its own bar line, not on the new music's. `run` counts the cells
      // this section has played in a row.
      const playing = { section, index, start: when, end: when + length, base, sources: [], gains: [],
                        bar: this.asset.bar_frames / this.asset.rate, run: run || 1 };
      for (const layer of LAYERS) {
        const source = ctx.createBufferSource();
        source.buffer = buffers[layer];
        const gain = ctx.createGain();
        if (fadeIn) {
          gain.gain.setValueAtTime(0, when - LEAD);
          gain.gain.linearRampToValueAtTime(base, when - LEAD + FADE);
        } else {
          gain.gain.setValueAtTime(base, when - LEAD);
        }
        gain.gain.setValueAtTime(base, playing.end - LEAD);
        gain.gain.linearRampToValueAtTime(0, playing.end - LEAD + FADE);
        source.connect(gain).connect(this.layerGain[layer]);
        source.start(when - LEAD);
        source.stop(playing.end - LEAD + FADE + 0.005);
        playing.sources.push(source);
        playing.gains.push(gain);
      }
      this.turn += 1;
      this.played.set(section.key, this.turn);
      if (this.ahead && index + 1 < section.cells.length) this._raw(this.asset, section, index + 1);
      this.log.push({ at: when, section: section.name, cell: index, from: section.asset_id });
      if (this.log.length > LOG_LENGTH) this.log.splice(0, this.log.length - LOG_LENGTH);
      return playing;
    }

    // Ends a cell early, at `when`, fading it out under whatever starts there.
    _cut(playing, when) {
      for (const gain of playing.gains) {
        gain.gain.cancelScheduledValues(when - LEAD);
        gain.gain.setValueAtTime(playing.base, when - LEAD);
        gain.gain.linearRampToValueAtTime(0, when - LEAD + FADE);
      }
      for (const source of playing.sources) source.stop(when - LEAD + FADE + 0.005);
      playing.end = when;
    }

    _drop(playing) {
      for (const source of playing.sources) { source.stop(0); source.disconnect(); }
    }

    // Goes to `section` on the next bar or beat line, from its beginning unless told otherwise.
    async _moveTo(section, cut, index) {
      index = index || 0;
      const buffers = await this._load(this.asset, section, index);
      const now = this.ctx.currentTime;
      if (this.queued) { this._drop(this.queued); this.queued = null; }
      let when;
      if (!this.current || this.current.end <= now) {
        when = Math.max(now + NOTICE, this.holdUntil);
        this.queued = this._schedule(section, index, buffers, when, false);
        this.current = null;
      } else {
        const unit = cut === "beat" ? this.current.bar / 4 : this.current.bar;
        const steps = Math.ceil((now + NOTICE - this.current.start) / unit - 1e-9);
        when = Math.min(this.current.start + Math.max(steps, 0) * unit, this.current.end);
        if (when < this.current.end - 1e-6) this._cut(this.current, when);
        if (this.current.section.key !== section.key) {
          const reached = this.current.index + Math.ceil((when - this.current.start) / (this.current.end - this.current.start) - 1e-9);
          this._leave(this.current.section, Math.max(reached, this.current.index + 1));
        }
        this.queued = this._schedule(section, index, buffers, when, true);
      }
      return when;
    }

    // Decides what to queue next. Call it about once a second, and whenever anything arrives.
    tick() {
      return this._serial(async () => {
        if (!this.started || !this.asset) return;
        const now = this.ctx.currentTime;
        if (this.queued && this.queued.start - LEAD <= now) { this.current = this.queued; this.queued = null; }
        if (this.target.rest) {
          // Resting: nothing new is queued, and once the fade is over what was playing is let go.
          if (this.restSince !== null && now > this.restSince + this.target.fade_s + 0.25) {
            for (const playing of [this.current, this.queued]) if (playing) this._drop(playing);
            this.current = this.queued = null;
          }
          return;
        }
        if (this.queued) return;
        if (!this.current) {
          await this._moveTo(this._sectionFor(this.target.place, true), "bar");
          return;
        }
        if (this.current.end - now > QUEUE_AHEAD) return;
        const pool = this._pool();
        const role = this.current.section.role;
        const next = pool.includes(role) || (role === "arrival" && pool.includes("wander"))
          ? this._following(this.current)
          : { section: this._sectionFor(this.target.place, false), index: 0 };
        const buffers = await this._load(this.asset, next.section, next.index);
        let when = this.current.end;
        if (when - LEAD < this.ctx.currentTime + 0.02) {      // the load took too long
          when = this.ctx.currentTime + NOTICE;
          this.late += 1;
        }
        this.queued = this._schedule(next.section, next.index, buffers, when, true, next.run);
      });
    }

    // --- the target --------------------------------------------------------------------------

    setTarget(target) {
      // The levels and the tone move the moment the target arrives, whatever else the engine is
      // in the middle of. Only the choice of section waits its turn behind a cell being loaded.
      const before = this.target;
      this.target = Object.assign({}, before, target);
      if (this.target.rest && !before.rest) this.restSince = this.ctx.currentTime;
      if (this.target.scene !== before.scene) this.scenePending = true;
      this._levels(before);
      return this._serial(async () => {
        if (!this.started || !this.asset) return;
        if (this.target.rest) return;                    // the music fades away; tick() tidies up
        if (before.rest) {
          // Back from a rest: a fresh start, the way a new piece begins, not the middle of an old one.
          this.restSince = null;
          for (const playing of [this.current, this.queued]) if (playing) this._drop(playing);
          this.current = this.queued = null;
          await this._moveTo(this._sectionFor(this.target.place, true), "bar");
          return;
        }
        const wanted = this._playable(this.target.place), pool = this._pool();
        const heading = this.queued ? this.queued.section.role : this.current ? this.current.section.role : null;
        // A change of place is answered at once, on the next bar or beat, with a section of that
        // kind. Without one, whatever is in rotation may carry on, and what has just left the
        // rotation (the calm part once the player moves again) gives way.
        const moved = this._playable(before.place) !== wanted;
        const settled = heading === wanted || (heading === "arrival" && pool.includes("wander")) ||
                        (!moved && pool.includes(heading));
        if (!settled) {
          await this._moveTo(this._sectionFor(this.target.place, false), this.target.cut);
        } else if (this.scenePending) {
          // The player has crossed into another part of the zone: another riff, on the next bar.
          this.scenePending = false;
          const playing = this.queued || this.current;
          if (playing && pool.includes(playing.section.role)) {
            const other = this._pick(pool, playing.section);
            if (other.key !== playing.section.key) await this._moveTo(other, "bar", this._resumeAt(other));
          }
        }
      });
    }

    _ramp(param, value, seconds, exponential) {
      const now = this.ctx.currentTime;
      if (param.cancelAndHoldAtTime) param.cancelAndHoldAtTime(now);
      else { param.cancelScheduledValues(now); param.setValueAtTime(param.value, now); }
      if (exponential) param.exponentialRampToValueAtTime(Math.max(value, 1), now + seconds);
      else param.linearRampToValueAtTime(value, now + seconds);
    }

    _levels(before) {
      const t = this.target, quick = t.fade_s < 0.3;
      for (const layer of LAYERS) {
        if (before[layer] === t[layer] && this.started) continue;
        const rising = t[layer] > before[layer];
        this._ramp(this.layerGain[layer].gain, t[layer], quick ? t.fade_s : rising ? UP[layer] : DOWN[layer]);
      }
      this._ramp(this.bedHighpass.frequency, Math.max(t.bed_highpass_hz, 20), 0.06, true);
      this._ramp(this.toneLow.frequency, this._ceiling(t.lowpass_hz), t.fade_s, true);
      this._ramp(this.toneLow2.frequency, this._ceiling(t.lowpass_hz), t.fade_s, true);
      this._ramp(this.toneHigh.frequency, Math.max(t.highpass_hz, 20), t.fade_s, true);
      this._ramp(this.send.gain, t.reverb, t.fade_s);
      const comingBack = before.rest && !t.rest;
      const back = t.bass > 0 ? REST_IN_FAST : REST_IN;
      if (this.started) this._ramp(this.master.gain, this._loudness(), comingBack ? back : t.fade_s);
    }

    // How loud the whole player is right now: nothing during a rest or a cinematic.
    _loudness() {
      const t = this.target;
      return t.silent || t.rest ? 0 : t.volume * this.userVolume;
    }

    setVolume(volume) {
      this.userVolume = Math.min(Math.max(volume, 0), 1);
      if (this.started) this._ramp(this.master.gain, this._loudness(), 0.1);
    }

    // --- starting and stopping ---------------------------------------------------------------

    start() {
      return this._serial(async () => {
        if (this.started) return;
        if (!this.asset) throw new Error("There is no music to play yet");
        if (this.ctx.state === "suspended" && this.ctx.resume && !(this.ctx instanceof OfflineAudioContext)) {
          await this.ctx.resume();
        }
        this.started = true;
        this._ramp(this.master.gain, this._loudness(), 2.0);      // the first music fades in
        if (!this.target.rest) await this._moveTo(this._sectionFor(this.target.place, true), "bar");
      });
    }

    stop() {
      return this._serial(async () => {
        if (!this.started) return;
        this.started = false;
        const now = this.ctx.currentTime;
        this._ramp(this.master.gain, 0, 0.3);
        for (const playing of [this.current, this.queued]) {
          if (playing) for (const source of playing.sources) source.stop(now + 0.35);
        }
        this.current = this.queued = null;
      });
    }

    // Something happened in the game that the music marks in its own way. A death runs the
    // music down like a record stopping; what follows starts when it has run down.
    moment(name) {
      return this._serial(async () => {
        if (name !== "died" || !this.started) return;
        const now = this.ctx.currentTime;
        for (const playing of [this.current, this.queued]) {
          if (!playing) continue;
          for (const source of playing.sources) {
            source.playbackRate.setValueAtTime(1, now);
            source.playbackRate.linearRampToValueAtTime(0.3, now + WIND_DOWN);
            source.stop(now + WIND_DOWN + 0.05);
          }
          for (const gain of playing.gains) {
            gain.gain.cancelScheduledValues(now);
            gain.gain.setValueAtTime(playing.base, now);
            gain.gain.linearRampToValueAtTime(0, now + WIND_DOWN);
          }
        }
        this.current = this.queued = null;
        this.holdUntil = now + WIND_DOWN;
      });
    }

    // Leaves what is playing for other music of the same kind, on the next bar line.
    skip() {
      return this._serial(async () => {
        const playing = this.queued || this.current;
        if (!this.started || !playing) return;
        const pool = this._pool();
        const roles = pool.includes(playing.section.role) ? pool : [playing.section.role];
        await this._moveTo(this._pick(roles, playing.section), "bar");
      });
    }

    status() {
      const playing = this.current || this.queued;
      return {
        started: this.started, asset: this.asset ? this.asset.id : null,
        section: playing ? playing.section.name : null, cell: playing ? playing.index : null,
        // Which request the section that is playing came from: what /rock love and ban apply to.
        asset_id: playing ? playing.section.asset_id : null,
        resting: this.target.rest === true,
        place: this.target.place, late: this.late, cached: this.cache.size, time: this.ctx.currentTime,
      };
    }
  }

  Engine.LEAD = LEAD;
  Engine.FADE = FADE;
  root.FreeRockEngine = Engine;
})(typeof window !== "undefined" ? window : globalThis);
