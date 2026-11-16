// The forever song: the FreeRock player's engine for a bucket of single-instrument phrases.
//
// A bucket holds phrases, each one instrument alone, all on one tempo and one tonal centre:
// drums, bass, a rhythm part, a tune and a drone, each at up to three strengths (calm, steady,
// hard). This engine is five decks, one for each of those channels. Every deck loops a phrase on
// a shared bar grid, and the decks take other phrases a few at a time, the ones that have gone
// longest unheard, so the music never stops and never comes round again as a whole.
//
// A phrase is one turn of the song's form: a verse, a build-up and a chorus, the same lengths
// for every channel. The decks all turn over where the form comes round, so the whole band
// builds up together and reaches the chorus together, and each time round a couple of the
// decks have something new. (A bucket of short phrases without a form is played too: there one
// deck takes a new phrase at each four-bar line.)
//
// What the game is doing arrives as a target: how loud each channel is and how hard it plays.
// Levels move the moment the target arrives. A change of strength swaps the phrase in the middle
// of the bar, in step: on the next half beat when the music is getting harder, on the next bar
// line when it is easing off.
//
// Nothing here waits on a timer to keep the music going: every start, cut and fade is scheduled
// ahead on the audio clock. tick() only decides what comes next, and is safe to call late.
//
// The same file runs in the live page and in the offline tests.
(function (root) {
  "use strict";

  const CHANNELS = ["texture", "lead", "rhythm", "drums", "bass"];
  const BED = ["texture", "lead", "rhythm"];     // these go through the bed's own high-pass
  const OPEN_HZ = 20000;
  const NOTICE = 0.08;       // nothing is scheduled closer than this to now
  const AHEAD = 6.0;         // every deck is scheduled this far ahead
  const SEAM_IN = 0.003;     // a phrase that is cut into comes in over this long
  const SEAM_OUT = 0.020;    // every phrase goes out over this long, so its last note does not click
  const LINE_BARS = 4;       // at most one deck takes a new phrase at each line of this many bars
  // How fast a channel comes up and goes down, in seconds. Channels arrive almost at once, so
  // the music answers what the player does; they leave more slowly so that it does not flicker.
  const UP = { texture: 1.5, lead: 0.4, rhythm: 0.25, drums: 0.12, bass: 0.06 };
  const DOWN = { texture: 2.0, lead: 1.2, rhythm: 1.0, drums: 0.9, bass: 1.6 };
  // The crossfade when a deck changes strength in the middle of a phrase.
  const SWAP = { texture: 1.0, lead: 0.25, rhythm: 0.08, drums: 0.03, bass: 0.03 };
  // How long a phrase stays before the deck wants another, in passes through it (least, most).
  // Tunes and riffs are what the ear follows, so they move on soonest.
  const STAY = { texture: [2, 3], lead: [1, 2], rhythm: [2, 3], drums: [3, 5], bass: [3, 5] };
  // The same for phrases that are a whole turn of the form: a tune or a riff is heard once or
  // twice round, the drums, the bass and the drone a little longer.
  const STAY_TURNS = { texture: [2, 3], lead: [1, 2], rhythm: [1, 2], drums: [2, 3], bass: [2, 3] };
  const DRONE_SEAM = 0.4;    // the drone comes in and goes out over this long where the form comes round
  // The song's own rise and fall, a turn of the form at a time. Most turns are played as hard
  // as the game asks. Now and then a turn eases right off, to chill a minute: every channel
  // plays its calm phrases and the drums and the bass sit back. Now and then one leans in a
  // strength harder. In a fight there is none of this: the fight says how hard.
  const EASE_AFTER = 2;      // at least this many turns between two that ease off
  const EASE_BY = 5;         // and never more than this many without one
  const EASE_CHANCE = 0.4;   // how likely a turn is to ease off once one may
  const LEAN_CHANCE = 0.2;   // how likely a turn is to lean in
  const EASE_LEVEL = 0.6;    // how far the drums and the bass sit back in a turn that eases off
  const WAVE_OFF = 0.74;     // from this intensity up (a fight, a charge) the game alone decides
  // Moments of silence. After so much music (the bucket says about how much) the song comes
  // down: the last turn of the form before the silence eases off, the music fades away over its
  // last bars, and there is nothing for a while. Then it fades back in with a new verse. A
  // fight brings it straight back.
  const REST_FADE_BARS = 2;  // the music fades away over this many bars before a silence
  const BACK_IN = 3.0;       // and fades back in over this long after one
  const LAY_OUT = 0.4;       // how often the tune sits out a phrase before the next tune comes in
  const TEXTURE_OVERLAP = 1; // bars over which one pass of the drone fades into the next
  const REST_IN = 3.5;       // how long the music takes to fade back in after a rest
  const REST_IN_FAST = 0.2;  // ...unless something has just happened, a fight say
  const WIND_DOWN = 1.2;     // how long the music takes to run down, like a record stopping, at a death
  const LEAVE = 2.0;         // a place's music fades away over this long when another place's takes over
  const ARRIVE = 2.0;        // and the new place's fades in over this long
  const BETWEEN = 1.2;       // the new place's music starts this long after the old begins to leave
  const BUFFERS = 12;        // phrases kept ready to play
  const RAW = 18;            // phrases kept as they came from the server
  const LOG_LENGTH = 500;

  function gainOf(db) { return Math.pow(10, db / 20); }

  class Forever {
    // ctx:    an AudioContext, or an OfflineAudioContext in tests
    // loader: (bucketKey, clipId) -> Promise<ArrayBuffer> of 16-bit stereo, the whole phrase
    constructor(ctx, loader, options) {
      options = options || {};
      this.ctx = ctx;
      this.loader = loader;
      this.random = options.random || Math.random;
      // Where trouble that nobody is waiting on goes (a phrase that could not be fetched ahead
      // of time). The page shows it and sends it to the server. Without one it is thrown, and
      // the browser reports it.
      this.report = options.report || ((text) => { throw new Error(text); });
      this.bucket = null;        // the bucket in play: { key, bpm, bar, rate, cycle, form, changes, clips: Map }
      this.pending = null;       // another place's bucket, whose first phrases are being fetched
      this.group = null;         // the five decks playing it
      this.leaving = [];         // decks of a place that is fading away
      this.target = { place: "wander", bed: 1, drums: 0, bass: 0, bed_highpass_hz: 110, lowpass_hz: OPEN_HZ,
                      highpass_hz: 20, reverb: 0, volume: 1, silent: false, rest: false, fade_s: 0.4,
                      intensity: 0.25, channels: null };
      this.userVolume = 1;
      this.started = false;
      this.buffers = new Map();  // clip id -> AudioBuffer
      this.raw = new Map();      // clip id -> Promise of the phrase as the server sent it
      this.playedAt = new Map(); // clip id -> the turn it was last heard in
      this.planned = new Map();  // "channel:tier" -> the phrase that deck takes next at that strength
      this.turn = 0;
      this.heard = [];           // phrases that have come in since the server was last told
      this.late = 0;             // phrases that could not be loaded in time and came in late
      this.restSince = null;     // when the silence that is going on began
      this.holdUntil = 0;        // nothing new starts before this (the music is running down)
      this.silenceUntil = 0;     // a moment of silence lasts until this
      this.afterSilence = false; // the next music to start follows a silence, and fades in
      this.log = [];             // what was scheduled and when
      this._busy = Promise.resolve();

      // The graph: the decks, the bed's own high-pass, then tone, echo, volume, limiter.
      this.bus = ctx.createGain();
      this.bedHighpass = ctx.createBiquadFilter();
      this.bedHighpass.type = "highpass";
      this.bedHighpass.frequency.value = 110;
      this.bedHighpass.Q.value = 0.707;
      this.bedHighpass.connect(this.bus);
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
        // The limiter takes a moment to react. The ceiling after it is instant: untouched up to
        // nine tenths of full scale, bending over above that, never passing full scale.
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

    // One thing at a time: loading a phrase takes a moment, and two decisions made while one is
    // loading must not both act on the same "what is playing now".
    _serial(work) {
      const run = this._busy.then(work);
      this._busy = run.catch(() => {});
      return run;
    }

    // --- the bucket --------------------------------------------------------------------------

    // The bucket to play from. The same bucket again (after a reconnect) only brings its list
    // of phrases up to date. Another place's bucket takes over with a fade: the place that is
    // playing fades away while the new one comes in on its own tempo.
    setBucket(described) {
      return this._serial(async () => {
        if (described.rate !== this.ctx.sampleRate) {
          throw new Error("The phrases are at " + described.rate + " Hz and the player at " + this.ctx.sampleRate +
                          " Hz; they have to match for the decks to stay locked");
        }
        const clips = new Map(described.clips.map((clip) => [clip.id, clip]));
        if (this.bucket && this.bucket.key === described.key) {
          this.bucket.clips = clips;
          this.planned.clear();
          this.pending = null;
          return;
        }
        const fresh = { key: described.key, zone: described.zone, genre: described.genre, bpm: described.bpm,
                        tonic: described.tonic, rate: described.rate, bar: described.bar_frames / described.rate,
                        // A bucket whose phrases are each one turn of a form says how long that
                        // is, how it divides, and how many decks may change where it comes round.
                        cycle: described.cycle_bars || null, form: described.form || null,
                        changes: described.cycle_bars ? described.changes || 2 : 1,
                        // How the player shapes a turn of the form: how far the verse is held
                        // back, and how high the lows are swept away before the chorus lands.
                        arc: described.cycle_bars ? described.arc || null : null,
                        // About how much music there is between two silences, and about how
                        // long a silence is, in seconds.
                        rest: described.cycle_bars ? described.rest || null : null, clips };
        if (!this.started || this._quiet() || !this.group) {
          this.planned.clear();
          this.bucket = fresh;
          this.pending = null;
          this._release(this.group, this.ctx.currentTime, 0.05);
          this.group = null;
          return;
        }
        // A place is playing. It plays on while the first phrases of the new place are fetched,
        // and the new place takes over when they are here, so that it comes in whole.
        this.pending = fresh;
        this._first(fresh).then((plan) => this._serial(async () => {
          if (this.pending !== fresh) return;            // yet another place was asked for meanwhile
          this.pending = null;
          this.bucket = fresh;
          this.planned = plan;
          const now = this.ctx.currentTime;
          if (!this.started || this._quiet()) { this._release(this.group, now, 0.05); this.group = null; return; }
          this._release(this.group, now, LEAVE);
          this.group = this._group(now + BETWEEN, ARRIVE);
        })).catch((error) => this.report("The music for " + fresh.zone + " could not be started: " +
                                         String(error && error.stack || error)));
      });
    }

    // Fetches the phrase each deck of a bucket would start with, at the strength the game asks
    // for now, and gives back that choice, so that what was fetched is what is then played.
    async _first(bucket) {
      const plan = new Map(), loading = [];
      for (const channel of CHANNELS) {
        const use = this._tierFor(channel, this._wanted(channel).tier, bucket);
        if (use === null) continue;
        const clip = bucket === this.bucket ? this._pick(channel, use, null) : this._choose(channel, use, null, bucket);
        plan.set(channel + ":" + use, clip);
        loading.push(this._buffer(clip, bucket));
      }
      await Promise.all(loading);
      return plan;
    }

    // One more phrase for the bucket in play. A phrase for another bucket is not this engine's
    // business: that bucket's whole list comes with it when its turn comes.
    addClip(key, clip) {
      if (this.pending && this.pending.key === key) { this.pending.clips.set(clip.id, clip); return; }
      if (!this.bucket || this.bucket.key !== key) return;
      this.bucket.clips.set(clip.id, clip);
      this.planned.delete(clip.channel + ":" + clip.tier);     // what is new is what is played next
      // A channel that had nothing to play looks again on the next beat, not at the end of the
      // stretch it had already been left empty for.
      const group = this.group, deck = group ? group.decks[clip.channel] : null;
      if (deck && !deck.clip && !deck.returning) {
        const soon = Math.max(this._lineAfter(group, this.ctx.currentTime + NOTICE, 0.25), group.origin);
        if (soon < deck.until) deck.until = soon;
      }
    }

    // Phrases that have been set aside: they finish the pass they are in and are not chosen again.
    dropClips(key, ids) {
      if (this.pending && this.pending.key === key) { for (const id of ids) this.pending.clips.delete(id); return; }
      if (!this.bucket || this.bucket.key !== key) return;
      for (const id of ids) { this.bucket.clips.delete(id); this.buffers.delete(id); this.raw.delete(id); }
      this.planned.clear();
    }

    _pool(channel, tier, bucket) {
      const found = [];
      for (const clip of (bucket || this.bucket).clips.values()) {
        if (clip.channel === channel && clip.tier === tier) found.push(clip);
      }
      return found;
    }

    // The strength a deck can actually play at when `tier` is wanted: that one if the bucket has
    // a phrase for it, otherwise the nearest that it has (the calmer of two equally near), or
    // null when the channel has nothing at all yet.
    _tierFor(channel, tier, bucket) {
      for (const candidate of [tier, tier - 1, tier + 1, tier - 2, tier + 2]) {
        if (candidate >= 0 && candidate <= 2 && this._pool(channel, candidate, bucket).length) return candidate;
      }
      return null;
    }

    // The phrase of this channel and strength that has gone longest unheard. `except` is the one
    // playing; it is not chosen again while there is another. Between phrases that have never
    // been heard on this page, one nobody has ever heard comes first: it was made for now.
    //
    // The choice is kept until it is used, so that the phrase fetched ahead of time is the
    // phrase that is then played.
    _pick(channel, tier, except) {
      const use = this._tierFor(channel, tier);
      if (use === null) return null;
      const slot = channel + ":" + use, kept = this.planned.get(slot);
      if (kept && this.bucket.clips.has(kept.id) && (!except || kept.id !== except.id)) return kept;
      const chosen = this._choose(channel, use, except);
      this.planned.set(slot, chosen);
      return chosen;
    }

    _choose(channel, use, except, bucket) {
      let choices = this._pool(channel, use, bucket);
      if (except && choices.length > 1) choices = choices.filter((clip) => clip.id !== except.id);
      let oldest = Infinity, longest = [];
      for (const clip of choices) {
        const last = this.playedAt.has(clip.id) ? this.playedAt.get(clip.id) : -1;
        if (last < oldest) { oldest = last; longest = [clip]; }
        else if (last === oldest) longest.push(clip);
      }
      const fresh = longest.filter((clip) => clip.new);
      if (fresh.length) longest = fresh;
      return longest[Math.floor(this.random() * longest.length) % longest.length];
    }

    // --- loading -----------------------------------------------------------------------------

    _raw(clip, bucket) {
      if (this.raw.has(clip.id)) {
        const found = this.raw.get(clip.id);
        this.raw.delete(clip.id);
        this.raw.set(clip.id, found);          // most recently used goes to the back
        return found;
      }
      const fetched = this.loader((bucket || this.bucket).key, clip.id).then((bytes) => {
        if (bytes.byteLength !== clip.frames * 4) {
          throw new Error("The phrase " + clip.id + " should be " + clip.frames + " frames, and " + bytes.byteLength / 4 + " came");
        }
        return bytes;
      });
      // A fetch that failed is forgotten, so that whoever needs the phrase next tries again; the
      // failure itself goes to whoever was waiting for it.
      fetched.catch(() => { if (this.raw.get(clip.id) === fetched) this.raw.delete(clip.id); });
      this.raw.set(clip.id, fetched);
      while (this.raw.size > RAW) this.raw.delete(this.raw.keys().next().value);
      return fetched;
    }

    async _buffer(clip, bucket) {
      if (this.buffers.has(clip.id)) {
        const found = this.buffers.get(clip.id);
        this.buffers.delete(clip.id);
        this.buffers.set(clip.id, found);
        return found;
      }
      const samples = new Int16Array(await this._raw(clip, bucket));
      const buffer = this.ctx.createBuffer(2, clip.frames, (bucket || this.bucket).rate);
      const left = buffer.getChannelData(0), right = buffer.getChannelData(1);
      for (let i = 0, n = clip.frames; i < n; i++) {
        left[i] = samples[2 * i] / 32768;
        right[i] = samples[2 * i + 1] / 32768;
      }
      this.buffers.set(clip.id, buffer);
      while (this.buffers.size > BUFFERS) this.buffers.delete(this.buffers.keys().next().value);
      return buffer;
    }

    // Fetches, ahead of need, the phrase each deck would take next at each strength: what a
    // change in the game jumps to. Nothing waits for this. A fetch that fails is reported, and
    // tried again by whoever needs the phrase.
    _fetchAhead() {
      if (!this.bucket) return;
      for (const channel of CHANNELS) {
        const deck = this.group ? this.group.decks[channel] : null;
        for (const tier of [0, 1, 2]) {
          if (!this._pool(channel, tier).length) continue;
          const clip = this._pick(channel, tier, deck ? deck.clip : null);
          if (clip && !this.buffers.has(clip.id)) {
            this._raw(clip).catch((error) => this.report(
              "A phrase could not be fetched ahead of time: " + String(error && error.message || error)));
          }
        }
      }
    }

    // --- the decks ---------------------------------------------------------------------------

    // What a turn of the form does of its own accord: ease off, lean in, or neither. Decided
    // once for each turn, as the turn comes into view. The first two turns of any stretch of
    // music are played straight.
    _wave(group, turn) {
      if (!group.form) return 0;
      while (group.waves.length <= turn) {
        const index = group.waves.length;
        const sinceEase = index - 1 - group.waves.lastIndexOf(-1);       // turns since the last that eased off
        let next = 0;
        if (index >= 2) {
          const may = group.waves.lastIndexOf(-1) < 0 ? index >= EASE_AFTER : sinceEase >= EASE_AFTER;
          if (may && (sinceEase >= EASE_BY || this.random() < EASE_CHANCE)) next = -1;
          else if (group.waves[index - 1] === 0 && this.random() < LEAN_CHANCE) next = 1;
        }
        if (group.restTurn !== null && index === group.restTurn - 1) next = -1;     // coming down to a silence
        group.waves.push(next);
      }
      return group.waves[turn];
    }

    // The same for a moment in time; nothing in a fight, where the game alone decides.
    _waveAt(group, when) {
      if (!group || !group.form || this.target.intensity >= WAVE_OFF) return 0;
      const length = group.line * group.bar;
      return this._wave(group, Math.max(0, Math.floor((when - group.origin) / length + 1e-6)));
    }

    // How hard a channel plays at a moment: what the game asks for, moved by the song's own
    // rise and fall. The drone has one strength.
    _tierAt(group, channel, when) {
      const tier = this._wanted(channel).tier;
      if (channel === "texture") return tier;
      return Math.max(0, Math.min(2, tier + this._waveAt(group, when)));
    }

    _wanted(channel) {
      const channels = this.target.channels;
      if (channels && channels[channel]) return channels[channel];
      // A target that does not say (an older server): the three old layers stand in.
      const level = channel === "drums" ? this.target.drums : channel === "bass" ? this.target.bass : this.target.bed;
      return { level, tier: 1 };
    }

    // Five decks on a bar grid that starts at `origin`, coming in over `rise` seconds.
    _group(origin, rise) {
      const ctx = this.ctx;
      const bucket = this.bucket;
      const group = { bucket, origin, bar: bucket.bar, decks: {}, claimed: -1, claims: 0,
                      // Where decks may take a new phrase: where the form comes round, or at
                      // every four-bar line when the phrases have no form; and how many may.
                      line: bucket.cycle || LINE_BARS, changes: bucket.changes || 1, form: bucket.form,
                      bed: ctx.createGain(), rest: ctx.createGain() };
      for (const node of [group.bed, group.rest]) {
        if (rise) {
          node.gain.setValueAtTime(0, origin);
          node.gain.linearRampToValueAtTime(1, origin + rise);
        }
      }
      // The shape of a turn of the form is laid over both halves of the mix: held back in the
      // verse, rising through the build-up, full in the chorus. The drums and the bass also
      // pass a filter that can sweep their lows away just before the chorus lands.
      group.bedArc = ctx.createGain();
      group.restArc = ctx.createGain();
      group.sweep = ctx.createBiquadFilter();
      group.sweep.type = "highpass";
      group.sweep.frequency.value = 20;
      group.sweep.Q.value = 0.707;
      group.arcTurn = 0;         // the next turn of the form whose shape has not been laid down yet
      group.waves = [];          // for each turn so far: -1 eases off, 0 as the game asks, +1 leans in
      // The turn of the form that is not played: where it would begin, a silence begins.
      const rest = bucket.rest;
      group.restTurn = bucket.form && rest && rest.every_s > 0 && rest.for_s > 0
        ? Math.max(2, Math.round(rest.every_s * (0.6 + 0.8 * this.random()) / (group.line * group.bar))) : null;
      group.bed.connect(group.bedArc).connect(this.bedHighpass);
      group.rest.connect(group.restArc).connect(group.sweep).connect(this.bus);
      for (const channel of CHANNELS) {
        const level = ctx.createGain();
        level.gain.value = this._wanted(channel).level;
        level.connect(BED.includes(channel) ? group.bed : group.rest);
        group.decks[channel] = { channel, level, clip: null, passes: [], until: origin, changeAt: 0,
                                 layOutUntil: 0, returning: false, counted: false, stale: false, audible: false };
      }
      return group;
    }

    // Lets a group go: it fades away over `fall` seconds from `at` and is then forgotten.
    _release(group, at, fall) {
      if (!group) return;
      for (const node of [group.bed, group.rest]) {
        node.gain.cancelScheduledValues(at);
        node.gain.setValueAtTime(node.gain.value, at);
        node.gain.linearRampToValueAtTime(0, at + fall);
      }
      for (const deck of Object.values(group.decks)) {
        for (const pass of deck.passes) pass.source.stop(at + fall + 0.02);
      }
      group.gone = at + fall + 0.05;
      this.leaving.push(group);
    }

    // The bar line a moment falls on or after, counted from the group's start.
    _lineAfter(group, moment, bars) {
      const unit = group.bar * bars;
      return group.origin + Math.ceil((moment - group.origin) / unit - 1e-9) * unit;
    }

    // Plays a phrase on a deck from `at`. The phrase is laid on the group's grid, so a phrase
    // that comes in between its own lines comes in at the place it would have reached by then,
    // and every deck's phrases turn over on the same lines.
    _play(group, deck, clip, buffer, at, rise) {
      const ctx = this.ctx, length = clip.frames / group.bucket.rate;
      // A drone without a form has no beat to keep: it always plays from its beginning, each
      // pass laid over the end of the last. A drone that is a turn of the form swells with the
      // build-up and opens out in the chorus, so it keeps to the grid like everything else.
      const loose = deck.channel === "texture" && !group.form;
      const into = loose ? 0 : ((at - group.origin) % length + length) % length;
      const offset = into < 1e-6 || length - into < 1e-6 ? 0 : into;
      const end = at + length - offset;
      const overlap = loose ? Math.min(TEXTURE_OVERLAP * group.bar, length / 4) : 0;
      const soft = deck.channel === "texture" && !loose ? DRONE_SEAM : 0;
      const base = gainOf(clip.gain_db);
      // A phrase played from its beginning comes in whole: its first note is the downbeat, and
      // a fade would take the edge off it. One that is cut into (a change of strength in the
      // middle of the bar, a late start) or laid over the last (the drone) fades in.
      const up = Math.min(rise || overlap || soft || (offset ? SEAM_IN : 0), (end - at) / 2);
      const down = Math.min(overlap || soft || SEAM_OUT, (end - at) / 2);
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      const gain = ctx.createGain();
      if (up > 0) {
        gain.gain.setValueAtTime(0, at);
        gain.gain.linearRampToValueAtTime(base, at + up);
      } else {
        gain.gain.setValueAtTime(base, at);
      }
      gain.gain.setValueAtTime(base, end - down);
      gain.gain.linearRampToValueAtTime(0, end);
      source.connect(gain).connect(deck.level);
      source.start(at, offset);
      source.stop(end + 0.01);
      const pass = { clip, source, gain, base, start: at, end };
      deck.passes.push(pass);
      // The drone's next pass starts while this one is still fading, so that it never dips.
      deck.until = end - overlap;
      this.log.push({ at, channel: deck.channel, clip: clip.id, tier: clip.tier, offset });
      if (this.log.length > LOG_LENGTH) this.log.splice(0, this.log.length - LOG_LENGTH);
      return pass;
    }

    // Takes a phrase off a deck at `when`, fading it out over `fall`; anything that was to
    // follow it is dropped.
    _cut(deck, when, fall) {
      const kept = [];
      for (const pass of deck.passes) {
        if (pass.start >= when - 1e-6) {
          pass.source.stop(0);
          pass.source.disconnect();
          continue;
        }
        if (pass.end > when) {
          const audible = Math.min(fall, pass.end - when);
          pass.gain.gain.cancelScheduledValues(when);
          pass.gain.gain.setValueAtTime(pass.base, when);
          pass.gain.gain.linearRampToValueAtTime(0, when + audible);
          pass.source.stop(when + audible + 0.01);
          pass.end = when + audible;
        }
        kept.push(pass);
      }
      deck.passes = kept;
    }

    // A deck takes `clip` as the phrase it loops from now on.
    _take(group, deck, clip, line) {
      if (this.planned.get(clip.channel + ":" + clip.tier) === clip) this.planned.delete(clip.channel + ":" + clip.tier);
      deck.clip = clip;
      deck.counted = false;
      deck.stale = false;
      const [least, most] = (group.form ? STAY_TURNS : STAY)[deck.channel];
      const passes = least + Math.floor(this.random() * (most - least + 1));
      deck.changeAt = line + passes * clip.bars;
    }

    // Notes that a phrase is being heard: for the rotation here, and for the server's count.
    _count(deck) {
      if (deck.counted || !deck.clip || !deck.audible) return;
      deck.counted = true;
      deck.clip.new = false;
      this.turn += 1;
      this.playedAt.set(deck.clip.id, this.turn);
      this.heard.push(deck.clip.id);
    }

    // Only so many decks may take a new phrase at any line: one at a four-bar line, a couple
    // where the form comes round.
    _claim(group, bar) {
      const slot = Math.floor(bar / group.line + 1e-6);
      if (slot < group.claimed) return false;
      if (slot > group.claimed) { group.claimed = slot; group.claims = 0; }
      if (group.claims >= group.changes) return false;
      group.claims += 1;
      return true;
    }

    // Schedules a deck as far ahead as it should be: the phrase it has, again, or another when
    // its stay is over and the line is free, or when the strength the game asks for has changed.
    async _fill(group, deck) {
      while (deck.until < this.ctx.currentTime + AHEAD) {
        const at = deck.until;
        if (group.endAt !== undefined && at >= group.endAt - 1e-6) break;       // a silence begins there
        const bar = Math.round((at - group.origin) / group.bar);
        const tier = this._tierAt(group, deck.channel, at + 0.001);
        let clip = deck.clip && group.bucket.clips.has(deck.clip.id) ? deck.clip : null;
        if (deck.layOutUntil > bar) { deck.until = at + Math.min(LINE_BARS, deck.layOutUntil - bar) * group.bar; continue; }
        // The tune coming back in is a change like any other: it waits for a line nobody else has.
        if (deck.returning && !this._claim(group, bar)) { deck.until = at + LINE_BARS * group.bar; continue; }
        deck.returning = false;
        let change = !clip || clip.tier !== this._tierFor(deck.channel, tier);
        if (!change && !deck.audible && deck.stale) change = true;      // out of hearing: come back with another
        if (!change && deck.audible && bar >= deck.changeAt && this._claim(group, bar)) {
          change = true;
          // The tune does not play all the time. Now and then it sits a phrase out, and the
          // next tune has the more to say for it. Not in a fight: there the lead is the point.
          if (deck.channel === "lead" && clip && tier < 2 && this.random() < LAY_OUT) {
            if (group.form) {
              // With a form, the new tune sits out the verse and comes in with the build-up.
              const next = this._pick(deck.channel, tier, clip);
              if (next) this._take(group, deck, next, bar);
              deck.layOutUntil = bar + group.form.verse;
              deck.until = at + group.form.verse * group.bar;
              continue;
            }
            deck.layOutUntil = bar + clip.bars;
            deck.returning = true;
            deck.clip = null;
            deck.until = at + LINE_BARS * group.bar;
            continue;
          }
        }
        if (change) {
          const next = this._pick(deck.channel, tier, clip);
          if (next) { clip = next; this._take(group, deck, clip, bar); }
        }
        if (!clip) { deck.until = at + group.bar; continue; }        // nothing for this channel yet
        const buffer = await this._buffer(clip);
        if (!this.started || this.group !== group) return;             // the music moved on while it loaded
        let start = at;
        if (start < this.ctx.currentTime + 0.02) {                     // the load took too long
          start = this.ctx.currentTime + NOTICE;
          this.late += 1;
        }
        this._play(group, deck, clip, buffer, start, 0);
      }
      deck.passes = deck.passes.filter((pass) => pass.end > this.ctx.currentTime - 0.5);
    }

    // Changes gear: a deck whose phrase is not of the strength the game now asks for takes one
    // that is, in the middle of the bar and in step. Harder comes in on the next half beat;
    // easier waits for the bar line.
    async _gear() {
      const group = this.group;
      if (!group) return;
      for (const deck of Object.values(group.decks)) {
        const soon = this.ctx.currentTime + NOTICE;
        const wanted = this._tierAt(group, deck.channel, soon);
        const bar = Math.round((this.ctx.currentTime - group.origin) / group.bar);
        if (!deck.clip) {
          // A tune that is sitting a phrase out does not sit out a fight.
          if (deck.layOutUntil > bar && wanted >= 2) {
            deck.layOutUntil = 0;
            deck.returning = false;
            deck.until = Math.max(this._lineAfter(group, soon, 0.125), group.origin);
          }
          continue;
        }
        // What counts is the phrase that is sounding. The one laid down for the next turn of
        // the form may well be of another strength, and is meant to be.
        // (Of two that overlap, one fading out under the other, it is the one that came in last.)
        let sounding = null;
        for (const pass of deck.passes) {
          if (pass.start <= soon + 1e-6 && pass.end > soon && (!sounding || pass.start > sounding.start)) sounding = pass;
        }
        const sittingOut = !sounding && deck.layOutUntil > bar;          // a new tune waiting for the build-up
        if (!sounding && !(sittingOut && wanted >= 2)) continue;
        // A change of gear that is already on its way counts as made: what matters then is the
        // phrase that is coming in, not the one about to be cut.
        const changing = deck.swapAt !== undefined && soon < deck.swapAt;
        const now = sounding && !changing ? sounding.clip : deck.clip;
        const tier = this._tierFor(deck.channel, wanted);
        if (tier === null || (tier === now.tier && !sittingOut)) continue;
        const next = tier === deck.clip.tier && sittingOut ? deck.clip : this._pick(deck.channel, wanted, now);
        if (!next) continue;
        const buffer = await this._buffer(next);
        if (!this.started || this.group !== group) return;
        const when = Math.max(this._lineAfter(group, this.ctx.currentTime + NOTICE, tier > now.tier || sittingOut ? 0.125 : 1),
                              group.origin);
        const fade = SWAP[deck.channel];
        this._cut(deck, when, fade);
        this._take(group, deck, next, Math.round((when - group.origin) / group.bar));
        deck.layOutUntil = 0;
        deck.swapAt = when;
        this._play(group, deck, next, buffer, when, fade);
      }
    }

    // How far the verse is held back right now, as a gain. In a fight it is held back much
    // less: the band is meant to hit.
    _verseGain(group) {
      const fight = this.target.intensity >= 0.8;
      return gainOf(group.bucket.arc.verse_db * (fight ? 0.35 : 1));
    }

    // Lays down the shape of one turn of the form from `from` on: the verse held back, a rise
    // through the build-up, the chorus at full, and with a sweep the lows thinning out over the
    // second half of the build-up and coming back as the chorus lands.
    _shape(group, turn, from) {
      const length = group.line * group.bar;
      const start = group.origin + turn * length;
      const build = start + group.form.verse * group.bar, chorus = build + group.form.build * group.bar;
      if (from >= chorus) return;
      // In a turn that eases off, the drums and the bass sit back all the way through.
      const eased = this._waveAt(group, start + 0.001) < 0;
      for (const node of [group.bedArc, group.restArc]) {
        const top = eased && node === group.restArc ? EASE_LEVEL : 1.0;
        const low = this._verseGain(group) * top;
        if (from >= build) {
          // Caught in the build-up: carry on up from wherever it is.
          node.gain.setValueAtTime(Math.max(node.gain.value, 0.001), from);
        } else {
          if (from <= start && turn === 0) node.gain.setValueAtTime(low, start);
          else node.gain.setTargetAtTime(low, Math.max(from, start), from > start ? 0.04 : 0.12);
          node.gain.setValueAtTime(low, build);
        }
        node.gain.exponentialRampToValueAtTime(top, chorus);
      }
      const sweep = group.bucket.arc.sweep_hz || 0;
      const half = build + (chorus - build) / 2;
      if (sweep > 20 && from <= half) {
        group.sweep.frequency.setValueAtTime(20, half);
        group.sweep.frequency.exponentialRampToValueAtTime(sweep, chorus - 0.03);
        group.sweep.frequency.setTargetAtTime(20, chorus - 0.01, 0.004);
      }
    }

    // Keeps the shape of the form laid down as far ahead as the decks are.
    _arc(group) {
      if (!group.form || !group.bucket.arc) return;
      const length = group.line * group.bar;
      while (group.origin + group.arcTurn * length < this.ctx.currentTime + AHEAD) {
        this._shape(group, group.arcTurn, group.origin + group.arcTurn * length);
        group.arcTurn += 1;
      }
    }

    // A fight has begun or ended: the turn of the form that is playing is shaped again from
    // now, so that a fight in a verse is not left sitting at the verse's level.
    _reshape(group) {
      if (!group.form || !group.bucket.arc) return;
      const now = this.ctx.currentTime, length = group.line * group.bar;
      if (now <= group.origin) return;
      const turn = Math.floor((now - group.origin) / length);
      for (const param of [group.bedArc.gain, group.restArc.gain, group.sweep.frequency]) {
        if (param.cancelAndHoldAtTime) param.cancelAndHoldAtTime(now);
        else { param.cancelScheduledValues(now); param.setValueAtTime(param.value, now); }
      }
      group.sweep.frequency.setTargetAtTime(20, now, 0.01);
      this._shape(group, turn, now);
      group.arcTurn = turn + 1;          // what was laid down beyond this turn went with the rest
    }

    // Begins a moment of silence where the form next comes round, when it is time for one: the
    // music fades away over its last bars and nothing is laid down past them. In a fight the
    // silence waits another turn.
    _breath(group) {
      if (group.restTurn === null || group.endAt !== undefined) return;
      const length = group.line * group.bar, now = this.ctx.currentTime;
      const at = group.origin + group.restTurn * length;
      if (now + AHEAD < at) return;
      if (this.target.intensity >= WAVE_OFF) { group.restTurn += 1; return; }
      const fade = Math.min(REST_FADE_BARS * group.bar, 6.0);
      for (const node of [group.bed, group.rest]) {
        node.gain.setValueAtTime(1, Math.max(at - fade, now));
        node.gain.linearRampToValueAtTime(0, at);
      }
      group.endAt = at;
      this.silenceUntil = at + group.bucket.rest.for_s * (0.6 + 0.8 * this.random());
    }

    // A fight while the music is fading away to a silence: it comes straight back up and plays on.
    _unrest(group) {
      if (group.endAt === undefined) return;
      for (const node of [group.bed, group.rest]) this._ramp(node.gain, 1, 0.15);
      group.endAt = undefined;
      group.restTurn += 1;
      this.silenceUntil = 0;
    }

    _quiet() { return this.target.rest === true || this.target.silent === true; }

    // Whether a moment of silence is going on.
    _silent() { return !this.group && this.ctx.currentTime < this.silenceUntil; }

    // Decides what comes next. Call it about once a second, and whenever anything arrives.
    tick() {
      return this._serial(async () => {
        if (!this.started || !this.bucket) return;
        const now = this.ctx.currentTime;
        this.leaving = this.leaving.filter((group) => group.gone > now);
        if (this._quiet()) {
          // A rest, or a cinematic: once the fade is over what was playing is let go, and the
          // music starts afresh when it comes back.
          const since = this.restSince === null ? now : this.restSince;
          if (this.group && now > since + this.target.fade_s + 0.25) {
            this._release(this.group, now, 0.05);
            this.group = null;
          }
          if (!this.group) return;
        }
        if (this.group && this.group.endAt !== undefined && now >= this.group.endAt) {
          // The music has faded away: a moment of silence.
          this.group.gone = now + 0.1;
          this.leaving.push(this.group);
          this.group = null;
          this.afterSilence = true;
        }
        if (!this.group) {
          if (!this.bucket.clips.size) return;                         // nothing has been made yet
          const fight = this.target.intensity >= WAVE_OFF;
          if (now < this.silenceUntil && !fight) return;               // the silence holds
          this.silenceUntil = 0;
          // The phrase each deck starts with is fetched before the grid is laid down, so that
          // all of them come in together on its first beat.
          const plan = await this._first(this.bucket);
          for (const [slot, clip] of plan) this.planned.set(slot, clip);
          if (!this.started || this._quiet()) return;                  // the game went quiet while they loaded
          // Out of a silence the music fades back in, unless a fight is what ended it.
          const rise = this.afterSilence ? (this.target.intensity >= WAVE_OFF ? REST_IN_FAST : BACK_IN) : 0;
          this.afterSilence = false;
          this.group = this._group(Math.max(this.ctx.currentTime + NOTICE, this.holdUntil), rise);
        }
        const group = this.group;
        for (const deck of Object.values(group.decks)) {
          deck.audible = this._wanted(deck.channel).level > 0;
          this._count(deck);
        }
        await this._gear();
        if (this.group !== group) return;
        this._breath(group);
        // The deck that has waited longest past its time goes first for the free line.
        const decks = Object.values(group.decks).sort((a, b) => a.changeAt - b.changeAt);
        for (const deck of decks) {
          await this._fill(group, deck);
          if (this.group !== group || !this.started) return;
        }
        for (const deck of decks) this._count(deck);
        this._arc(group);
        this._fetchAhead();
      });
    }

    // --- the target --------------------------------------------------------------------------

    setTarget(target) {
      // Levels and tone move the moment the target arrives, whatever else the engine is in the
      // middle of. Only the choice of phrase waits its turn behind one that is loading.
      const before = this.target;
      this.target = Object.assign({}, before, target);
      const wasQuiet = before.rest === true || before.silent === true;
      if (this._quiet() && !wasQuiet) this.restSince = this.ctx.currentTime;
      this._levels(before, wasQuiet);
      return this._serial(async () => {
        if (!this.started || !this.bucket) return;
        if (this._quiet()) return;                       // the music fades away; tick() tidies up
        if (wasQuiet) {
          // Back from a silence: a fresh start on a new grid, not the middle of what was.
          this.restSince = null;
          if (this.group) { this._release(this.group, this.ctx.currentTime, 0.05); this.group = null; }
          return;
        }
        if (this.group) {
          for (const deck of Object.values(this.group.decks)) {
            const audible = this._wanted(deck.channel).level > 0;
            if (deck.audible && !audible) deck.stale = true;       // it has had its say: another next time
            deck.audible = audible;
            this._count(deck);
          }
          // A fight beginning or ending changes how the turn that is playing is shaped.
          const edge = (level) => (before.intensity >= level) !== (this.target.intensity >= level);
          if (this.target.intensity >= WAVE_OFF) this._unrest(this.group);
          if (edge(0.8) || edge(WAVE_OFF)) this._reshape(this.group);
          await this._gear();
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

    _levels(before, wasQuiet) {
      const t = this.target, quick = t.fade_s < 0.3;
      if (this.group) {
        for (const deck of Object.values(this.group.decks)) {
          const level = this._wanted(deck.channel).level;
          const was = deck.level.gain.value;
          if (Math.abs(level - was) < 1e-4) continue;
          const seconds = quick ? t.fade_s : level > was ? UP[deck.channel] : DOWN[deck.channel];
          this._ramp(deck.level.gain, level, seconds);
        }
      }
      this._ramp(this.bedHighpass.frequency, Math.max(t.bed_highpass_hz, 20), 0.06, true);
      this._ramp(this.toneLow.frequency, this._ceiling(t.lowpass_hz), t.fade_s, true);
      this._ramp(this.toneLow2.frequency, this._ceiling(t.lowpass_hz), t.fade_s, true);
      this._ramp(this.toneHigh.frequency, Math.max(t.highpass_hz, 20), t.fade_s, true);
      this._ramp(this.send.gain, t.reverb, t.fade_s);
      const comingBack = wasQuiet && !this._quiet();
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
        if (this.ctx.state === "suspended" && this.ctx.resume && !(this.ctx instanceof OfflineAudioContext)) {
          await this.ctx.resume();
        }
        this.started = true;
        this._ramp(this.master.gain, this._loudness(), 2.0);      // the first music fades in
      });
    }

    stop() {
      return this._serial(async () => {
        if (!this.started) return;
        this.started = false;
        const now = this.ctx.currentTime;
        this._ramp(this.master.gain, 0, 0.3);
        if (this.group) { this._release(this.group, now, 0.3); this.group = null; }
      });
    }

    // Something happened in the game that the music marks in its own way. A death runs the
    // music down like a record stopping; what follows starts when it has run down.
    moment(name) {
      return this._serial(async () => {
        if (name !== "died" || !this.started || !this.group) return;
        const now = this.ctx.currentTime;
        for (const deck of Object.values(this.group.decks)) {
          for (const pass of deck.passes) {
            if (pass.start > now) { pass.source.stop(0); continue; }
            pass.source.playbackRate.setValueAtTime(1, now);
            pass.source.playbackRate.linearRampToValueAtTime(0.3, now + WIND_DOWN);
            pass.source.stop(now + WIND_DOWN + 0.05);
            pass.gain.gain.cancelScheduledValues(now);
            pass.gain.gain.setValueAtTime(pass.base, now);
            pass.gain.gain.linearRampToValueAtTime(0, now + WIND_DOWN);
          }
        }
        this.group.gone = now + WIND_DOWN + 0.1;
        this.leaving.push(this.group);
        this.group = null;
        this.holdUntil = now + WIND_DOWN;
      });
    }

    // Leaves what is playing for other phrases, on the next bar line: every deck that can be
    // heard takes another.
    skip() {
      return this._serial(async () => {
        const group = this.group;
        if (!this.started || !group) return;
        const when = Math.max(this._lineAfter(group, this.ctx.currentTime + NOTICE, 1), group.origin);
        for (const deck of Object.values(group.decks)) {
          if (!deck.clip || !deck.audible) continue;
          const next = this._pick(deck.channel, this._tierAt(group, deck.channel, when), deck.clip);
          if (!next || next.id === deck.clip.id) continue;
          const buffer = await this._buffer(next);
          if (this.group !== group) return;
          this._cut(deck, when, SWAP[deck.channel]);
          this._take(group, deck, next, Math.round((when - group.origin) / group.bar));
          this._play(group, deck, next, buffer, when, SWAP[deck.channel]);
        }
      });
    }

    // What is going on, for the page and for the server. `heard` is the phrases that have come
    // in since the last time this was asked; asking empties it.
    status() {
      const playing = {};
      if (this.group) {
        for (const deck of Object.values(this.group.decks)) {
          if (deck.clip && deck.audible) playing[deck.channel] = { id: deck.clip.id, tier: deck.clip.tier };
        }
      }
      const heard = this.heard;
      this.heard = [];
      return {
        started: this.started, forever: true, bucket: this.bucket ? this.bucket.key : null,
        phrases: this.bucket ? this.bucket.clips.size : 0, playing, heard,
        // What the song is doing of its own accord in this turn of the form: easing off (-1),
        // leaning in (+1) or neither.
        wave: this._waveAt(this.group, this.ctx.currentTime),
        resting: this._quiet() || this._silent(), place: this.target.place, late: this.late,
        cached: this.buffers.size, time: this.ctx.currentTime,
      };
    }
  }

  Forever.CHANNELS = CHANNELS;
  Forever.SEAM_IN = SEAM_IN;
  Forever.SEAM_OUT = SEAM_OUT;
  root.FreeRockForever = Forever;
})(typeof window !== "undefined" ? window : globalThis);
