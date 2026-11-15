// The FreeRock player's audio engine.
//
// It plays a zone's music from the library as three layers (bed, drums, bass) that are started at
// the same instant, so they cannot drift apart. The music is cut into four-bar cells. The engine
// keeps one cell playing and the next one queued, changes section on a bar or beat line when the
// target asks for another kind of section, and moves the layer levels and the tone (muffle,
// echo, volume) as soon as the target changes.
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
  const OPEN_HZ = 20000;
  const FALLBACK = { boss: "battle", battle: "wander", storm: "wander", night: "ember",
                     depths: "ember", ember: "wander", arrival: "wander" };
  // How fast a layer comes up and goes down, in seconds. The bass arrives almost at once and
  // leaves over two bars; a target may ask for everything to move faster (stealth does).
  const UP = { bed: 0.4, drums: 0.5, bass: 0.06 };
  const DOWN = { bed: 0.4, drums: 2.0, bass: 4.0 };

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
      this.target = { place: "wander", cut: "bar", bed: 1, drums: 0, bass: 0, bed_highpass_hz: 110,
                      lowpass_hz: OPEN_HZ, highpass_hz: 20, reverb: 0, volume: 1, silent: false, fade_s: 0.4 };
      this.userVolume = 1;
      this.current = null;       // the cell that is playing
      this.queued = null;        // the cell that will follow it
      this.started = false;
      this.cache = new Map();    // "asset:startFrame" -> { bed, drums, bass } AudioBuffers
      this.cacheLimit = options.cacheLimit || 10;
      this.late = 0;             // cells that could not be loaded in time and started late
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

    setAsset(asset) {
      return this._serial(async () => {
        const changed = !this.asset || this.asset.id !== asset.id;
        this.asset = asset;
        this.bar = asset.bar_frames / asset.rate;
        if (asset.rate !== this.ctx.sampleRate) {
          throw new Error("The music is at " + asset.rate + " Hz and the player at " + this.ctx.sampleRate +
                          " Hz; they have to match for the layers to stay locked");
        }
        if (changed && this.started) await this._moveTo(this._sectionFor(this.target.place, true), "bar");
      });
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

    // The section to go to for a place. Arriving somewhere new starts with the Arrival part.
    _sectionFor(place, arriving) {
      const role = this._playable(place);
      if (arriving && role === "wander") {
        const arrival = this.asset.sections.find((section) => section.role === "arrival");
        if (arrival) return arrival;
      }
      const choices = this.asset.sections.filter((section) => section.role === role);
      return choices[Math.floor(this.random() * choices.length) % choices.length];
    }

    // What follows a cell when nothing has changed: the next cell of its section, and after the
    // last one, the next section of the same kind (Wander A, then Wander B, then A again).
    _following(cell) {
      const section = cell.section;
      if (cell.index + 1 < section.cells.length) return { section, index: cell.index + 1 };
      const role = section.role === "arrival" ? "wander" : section.role;
      const same = this.asset.sections.filter((other) => other.role === this._playable(role));
      const at = same.indexOf(section);
      return { section: same[(at + 1) % same.length], index: 0 };
    }

    // --- loading -----------------------------------------------------------------------------

    async _load(asset, section, index) {
      const cell = section.cells[index];
      const key = asset.id + ":" + cell.start;
      if (this.cache.has(key)) {
        const found = this.cache.get(key);
        this.cache.delete(key);
        this.cache.set(key, found);          // most recently used goes to the back
        return found;
      }
      const rate = asset.rate;
      const first = cell.start - Math.round(LEAD * rate);
      const last = cell.end - Math.round(LEAD * rate) + Math.round(FADE * rate);
      const loaded = {};
      await Promise.all(LAYERS.map(async (layer) => {
        const bytes = await this.loader(asset.id, layer, first, last);
        const samples = new Int16Array(bytes);
        if (samples.length !== (last - first) * 2) {
          throw new Error("Asked for " + (last - first) + " frames of " + layer + ", got " + samples.length / 2);
        }
        const buffer = this.ctx.createBuffer(2, last - first, rate);
        const left = buffer.getChannelData(0), right = buffer.getChannelData(1);
        for (let i = 0, n = last - first; i < n; i++) {
          left[i] = samples[2 * i] / 32768;
          right[i] = samples[2 * i + 1] / 32768;
        }
        loaded[layer] = buffer;
      }));
      this.cache.set(key, loaded);
      while (this.cache.size > this.cacheLimit) this.cache.delete(this.cache.keys().next().value);
      return loaded;
    }

    // --- scheduling --------------------------------------------------------------------------

    // Starts a cell so that its first bar line falls at `when`. All three layers start together.
    _schedule(section, index, buffers, when, fadeIn) {
      const ctx = this.ctx, cell = section.cells[index];
      const length = (cell.end - cell.start) / this.asset.rate;
      const base = gainOf(section.gain_db);
      const playing = { section, index, start: when, end: when + length, base, sources: [], gains: [] };
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
      this.log.push({ at: when, section: section.name, cell: index });
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

    // Goes to `section` on the next bar or beat line.
    async _moveTo(section, cut) {
      const buffers = await this._load(this.asset, section, 0);
      const now = this.ctx.currentTime;
      if (this.queued) { this._drop(this.queued); this.queued = null; }
      let when;
      if (!this.current || this.current.end <= now) {
        when = now + NOTICE;
        this.queued = this._schedule(section, 0, buffers, when, false);
        this.current = null;
      } else {
        const unit = cut === "beat" ? this.bar / 4 : this.bar;
        const steps = Math.ceil((now + NOTICE - this.current.start) / unit - 1e-9);
        when = Math.min(this.current.start + Math.max(steps, 0) * unit, this.current.end);
        if (when < this.current.end - 1e-6) this._cut(this.current, when);
        this.queued = this._schedule(section, 0, buffers, when, true);
      }
      return when;
    }

    // Decides what to queue next. Call it about once a second, and whenever anything arrives.
    tick() {
      return this._serial(async () => {
        if (!this.started || !this.asset) return;
        const now = this.ctx.currentTime;
        if (this.queued && this.queued.start - LEAD <= now) { this.current = this.queued; this.queued = null; }
        if (this.queued) return;
        if (!this.current) {
          await this._moveTo(this._sectionFor(this.target.place, true), "bar");
          return;
        }
        if (this.current.end - now > QUEUE_AHEAD) return;
        const wanted = this._playable(this.target.place);
        const role = this.current.section.role;
        const next = role === wanted || (role === "arrival" && wanted === "wander")
          ? this._following(this.current)
          : { section: this._sectionFor(this.target.place, false), index: 0 };
        const buffers = await this._load(this.asset, next.section, next.index);
        let when = this.current.end;
        if (when - LEAD < this.ctx.currentTime + 0.02) {      // the load took too long
          when = this.ctx.currentTime + NOTICE;
          this.late += 1;
        }
        this.queued = this._schedule(next.section, next.index, buffers, when, true);
      });
    }

    // --- the target --------------------------------------------------------------------------

    setTarget(target) {
      return this._serial(async () => {
        const before = this.target;
        this.target = Object.assign({}, before, target);
        this._levels(before);
        if (!this.started || !this.asset) return;
        const wanted = this._playable(this.target.place);
        const heading = this.queued ? this.queued.section.role : this.current ? this.current.section.role : null;
        const settled = heading === wanted || (heading === "arrival" && wanted === "wander");
        if (!settled) await this._moveTo(this._sectionFor(this.target.place, false), this.target.cut);
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
      if (this.started) this._ramp(this.master.gain, t.silent ? 0 : t.volume * this.userVolume, t.fade_s);
    }

    setVolume(volume) {
      this.userVolume = Math.min(Math.max(volume, 0), 1);
      if (this.started) this._ramp(this.master.gain, this.target.silent ? 0 : this.target.volume * this.userVolume, 0.1);
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
        this._ramp(this.master.gain, this.target.silent ? 0 : this.target.volume * this.userVolume, 0.3);
        await this._moveTo(this._sectionFor(this.target.place, true), "bar");
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

    // Leaves what is playing for other music of the same kind, on the next bar line.
    skip() {
      return this._serial(async () => {
        const playing = this.queued || this.current;
        if (!this.started || !playing) return;
        const same = this.asset.sections.filter((section) => section.role === playing.section.role);
        const next = same[(same.indexOf(playing.section) + 1) % same.length];
        const section = same.length > 1 ? next : this._sectionFor(this.target.place, false);
        await this._moveTo(section, "bar");
      });
    }

    status() {
      const playing = this.current || this.queued;
      return {
        started: this.started, asset: this.asset ? this.asset.id : null,
        section: playing ? playing.section.name : null, cell: playing ? playing.index : null,
        place: this.target.place, late: this.late, cached: this.cache.size, time: this.ctx.currentTime,
      };
    }
  }

  Engine.LEAD = LEAD;
  Engine.FADE = FADE;
  root.FreeRockEngine = Engine;
})(typeof window !== "undefined" ? window : globalThis);
