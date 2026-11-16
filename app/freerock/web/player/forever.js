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
// A bucket may also hold written music: pieces, each kept as its parts (a part for a channel,
// recorded alone, in step with the piece's other parts). A piece is played whole, its parts
// together on the decks, each as loud as the game asks for that channel, so the piece keeps its
// own harmony and its own shape while the band comes and goes with the game. Pieces are strung
// together: a track is a run of pieces that tell a story (it opens, states its theme, rises,
// comes to its moment and closes), each going straight into the next; where the player is and
// what is happening decide which track, and a fight cuts in with a piece of its own, after
// which the track that was playing is picked up where it was left.
//
// What the game is doing arrives as a target: how loud each channel is and how hard it plays.
// Levels move the moment the target arrives. A change of strength swaps the phrase in the middle
// of the bar, in step: on the next half beat when the music is getting harder, on the next bar
// line when it is easing off.
//
// Nothing here waits on a timer to keep the music going: every start, cut and fade is scheduled
// ahead on the audio clock. tick() only decides what comes next, and is safe to call late.
//
// It keeps to the plainest ways of moving a level (set it, ramp it, let it settle), cancels what
// was laid down only from a moment on, and keeps its own account of where each level it moves
// is. Browsers differ in everything beyond that: one will not take a new instruction in the
// middle of a curve, another cannot be asked where a level is while it is moving.
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
  const UP = { texture: 3.0, lead: 2.0, rhythm: 1.6, drums: 1.2, bass: 1.2 };
  const DOWN = { texture: 4.0, lead: 3.5, rhythm: 3.5, drums: 3.0, bass: 3.0 };
  // The crossfade when a deck changes strength in the middle of a phrase, for a bucket of short
  // phrases without a form.
  const SWAP = { texture: 1.0, lead: 0.25, rhythm: 0.08, drums: 0.03, bass: 0.03 };
  // With a form, every change is a blend, the way a DJ brings one record in under another:
  // the phrase that is leaving plays on, fading, while the one that is arriving fades in.
  // In bars: a deck taking a new phrase where the form comes round; the whole band changing
  // for a turn that eases off or leans in; the music easing off after a fight; and, shortest,
  // a fight coming in, which is still a blend but not one that keeps the fight waiting.
  const BLEND = { texture: 4, lead: 2, rhythm: 2, drums: 2, bass: 2 };
  const BLEND_TURN = 2;
  const BLEND_EASING = 2;
  const BLEND_FIGHT = 0.5;
  const BLEND_ENTRY = 1;     // a tune coming in after sitting out a verse
  const BLEND_STEPS = 8;     // a blend's curve is laid down as this many straight pieces
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
  const BACK_IN = 5.0;       // and fades back in over this long after one
  const LAY_OUT = 0.4;       // how often the tune sits out a phrase before the next tune comes in
  const TEXTURE_OVERLAP = 1; // bars over which one pass of the drone fades into the next
  const REST_IN = 3.5;       // how long the music takes to fade back in after a rest
  const REST_IN_FAST = 0.2;  // ...unless something has just happened, a fight say
  const WIND_DOWN = 1.2;     // how long the music takes to run down, like a record stopping, at a death
  const LEAVE = 6.0;         // one style's music fades away over this long when another's takes over
  const ARRIVE = 5.0;        // and the new one fades in over this long
  const BETWEEN = 1.5;       // the new music starts this long after the old begins to leave
  const BUFFERS = 12;        // phrases kept ready to play
  const RAW = 18;            // phrases kept as they came from the server
  const LOG_LENGTH = 500;
  // Written pieces.
  const HANDOVER = 12.0;       // what follows a piece is made ready this long before the piece ends
  const RESUME_WITHIN = 900;   // a piece that a fight cut into is gone back to if the fight is over within this long
  const FIGHT_AGAIN = 600;     // a fight's own track is gone on with if the next fight comes within this long
  const FREE_SHARE = 0.25;     // how often a stretch of loose phrases follows a track, where there are enough of them
  const FREE_ENOUGH = 3;       // ...which is this many for every channel
  const RING = 2;              // bars a piece rings on under the next, when the two are in keys that sit together
  const RING_APART = 0.5;      // ...and when they are not
  const LAP_S = 40;            // a short piece on its own is played round until it has lasted about this long
  const STORY_NEXT = { open: "theme", theme: "rise", rise: "moment", moment: "close", close: "open" };

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
      this.next = null;          // the decks made ready for what follows, before their time has come
      // The pieces that were cut into, and how far each had got: the track a fight interrupted
      // (gone back to when the fight is over), and the fight's own track (gone on with at the
      // next fight, so that a fight's music gets past its opening over an evening).
      this.left = { walk: null, fight: null };
      this.standby = null;       // the piece a fight would bring in, chosen ahead so that it can be fetched ahead
      this.restDue = null;       // when the next moment of silence is due, where pieces are strung together
      this.pieceAt = new Map();  // piece id -> when it was last played here
      this.pieceTurn = 0;
      this.heavy = 0;            // how many tracks in a row have been heavy ones
      this.light = 0;            // ...and how many light ones
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
      this.moves = new WeakMap(); // for each level this engine has moved: from what, to what, and when
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
          this.bucket.pieces = described.pieces || {};
          this.bucket.index = null;
          this.standby = null;
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
                        rest: described.cycle_bars ? described.rest || null : null, clips,
                        // Written music: what each piece is (its parts are among the clips), and
                        // how often a stretch of loose phrases is played between two tracks.
                        pieces: described.pieces || {}, index: null,
                        share: described.free_share === undefined ? FREE_SHARE : described.free_share };
        this.left = { walk: null, fight: null };
        this.standby = null;
        if (!this.started || this._quiet() || !this.group) {
          this.planned.clear();
          this.bucket = fresh;
          this.pending = null;
          this._dropNext();
          this._release(this.group, this.ctx.currentTime, 0.05);
          this.group = null;
          return;
        }
        // A place is playing. It plays on while the first phrases of the new place are fetched,
        // and the new place takes over when they are here, so that it comes in whole.
        this.pending = fresh;
        const opening = this._nextItem(fresh, { fresh: true });
        this._first(fresh, opening).then((plan) => this._serial(async () => {
          if (this.pending !== fresh) return;            // yet another place was asked for meanwhile
          this.pending = null;
          this.bucket = fresh;
          this.planned = plan;
          this.restDue = null;
          const now = this.ctx.currentTime;
          this._dropNext();
          if (!this.started || this._quiet()) { this._release(this.group, now, 0.05); this.group = null; return; }
          this._release(this.group, now, LEAVE);
          this.group = this._group(now + BETWEEN, ARRIVE, opening);
        })).catch((error) => this.report("The music for " + fresh.zone + " could not be started: " +
                                         String(error && error.stack || error)));
      });
    }

    // Fetches the phrase each deck of a bucket would start with, at the strength the game asks
    // for now, and gives back that choice, so that what was fetched is what is then played.
    async _first(bucket, item) {
      const plan = new Map(), loading = [];
      if (item && item.piece) {
        // A piece: the stretch of each of its parts that it will begin with.
        const piece = item.piece, span = piece.line * piece.bar;
        const order = Math.min(Math.floor((item.from || 0) / span + 1e-6), piece.windows.length - 1);
        for (const channel of Object.keys(item.cast)) {
          const clip = this._part(item, order, channel, this._wanted(channel).tier);
          if (clip) loading.push(this._buffer(clip, bucket));
        }
        await Promise.all(loading);
        return plan;
      }
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
      if (this.pending && this.pending.key === key) { this.pending.clips.set(clip.id, clip); this.pending.index = null; return; }
      if (!this.bucket || this.bucket.key !== key) return;
      this.bucket.clips.set(clip.id, clip);
      if (clip.piece) { this.bucket.index = null; return; }    // a part of a piece: no deck takes it on its own
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
      if (this.pending && this.pending.key === key) {
        for (const id of ids) this.pending.clips.delete(id);
        this.pending.index = null;
        return;
      }
      if (!this.bucket || this.bucket.key !== key) return;
      for (const id of ids) { this.bucket.clips.delete(id); this.buffers.delete(id); this.raw.delete(id); }
      this.bucket.index = null;        // a piece that has lost a part is not played again
      this.standby = null;
      this.planned.clear();
    }

    _pool(channel, tier, bucket) {
      const found = [];
      for (const clip of (bucket || this.bucket).clips.values()) {
        if (clip.channel === channel && clip.tier === tier && !clip.piece) found.push(clip);
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
        if (bytes.byteLength !== (clip.frames + (clip.post || 0)) * 4) {
          throw new Error("The phrase " + clip.id + " should be " + (clip.frames + (clip.post || 0)) + " frames, and " +
                          bytes.byteLength / 4 + " came");
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
      const frames = clip.frames + (clip.post || 0);
      const buffer = this.ctx.createBuffer(2, frames, (bucket || this.bucket).rate);
      const left = buffer.getChannelData(0), right = buffer.getChannelData(1);
      for (let i = 0, n = frames; i < n; i++) {
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
      const ahead = (clip) => {
        if (clip && !this.buffers.has(clip.id)) {
          this._raw(clip).catch((error) => this.report(
            "A phrase could not be fetched ahead of time: " + String(error && error.message || error)));
        }
      };
      if (this._index().size) {
        // What a fight would bring in: chosen now, so that it is here when the fight is.
        const ask = this._ask();
        if (ask < 2 && !this.standby) {
          const item = this._nextItem(this.bucket, { ask: 2, peek: true, except: this.group && this.group.piece ? this.group.piece.id : null });
          this.standby = item && item.piece && item.piece.meta.serves.includes(2) ? item : { piece: null };
        }
        if (this.standby && this.standby.piece) {
          const piece = this.standby.piece;
          const order = Math.min(Math.floor((this.standby.from || 0) / (piece.line * piece.bar) + 1e-6), piece.windows.length - 1);
          for (const channel of Object.keys(this.standby.cast)) ahead(this._part(this.standby, order, channel, 2));
        }
      }
      if (this.group && this.group.piece) {
        // A piece: the stretch that follows the one playing, and the other strengths of this one.
        const group = this.group, where = this._where(group, this.ctx.currentTime);
        for (const channel of Object.keys(group.cast)) {
          const tier = this._tierAt(group, channel, this.ctx.currentTime);
          if (where.order + 1 < group.piece.windows.length) ahead(this._part(group, where.order + 1, channel, tier));
          for (const other of [0, 1, 2]) ahead(this._part(group, where.order, channel, other));
        }
        return;
      }
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

    // --- written pieces ----------------------------------------------------------------------

    // The pieces a bucket holds, by id, each with its parts laid out by stretch and by channel.
    // A piece that is missing any of its parts is left out. Pieces of one family (written over
    // the same changes, bar for bar) that stand at the same place in the story are kin: any
    // channel of one may be played with the other channels of another.
    _index(bucket) {
      bucket = bucket || this.bucket;
      if (bucket.index) return bucket.index;
      const index = new Map(), described = bucket.pieces || {};
      for (const clip of bucket.clips.values()) {
        if (!clip.piece || !described[clip.piece]) continue;
        let piece = index.get(clip.piece);
        if (!piece) {
          const meta = described[clip.piece];
          piece = { id: clip.piece, meta, bar: meta.bar_frames / bucket.rate, line: meta.bars,
                    seconds: meta.frames / bucket.rate, windows: [], channels: new Set(), plays: Infinity };
          index.set(clip.piece, piece);
        }
        const window = piece.windows[clip.order] || (piece.windows[clip.order] = {});
        (window[clip.channel] || (window[clip.channel] = [])).push(clip);
        piece.channels.add(clip.channel);
        piece.plays = Math.min(piece.plays, clip.plays || 0);
      }
      const families = new Map();
      for (const [id, piece] of index) {
        let whole = piece.windows.length === piece.meta.windows;
        for (let order = 0; whole && order < piece.meta.windows; order++) {
          for (const channel of piece.channels) if (!piece.windows[order] || !piece.windows[order][channel]) whole = false;
        }
        if (!whole) { index.delete(id); continue; }
        piece.kin = [piece];
        if (piece.meta.family) {
          const key = [piece.meta.family, piece.meta.story, piece.meta.frames, piece.meta.bar_frames, piece.meta.bars].join("|");
          if (!families.has(key)) families.set(key, []);
          families.get(key).push(piece);
          piece.kin = families.get(key);
        }
      }
      bucket.index = index;
      return index;
    }

    // Who plays what in a piece: for each channel, the piece its part is taken from. That is the
    // piece itself, or for a piece with kin any one of them, so that the same story is told by
    // another band each time. `before` is who played what in the piece this one follows
    // (channel -> track): whoever was playing goes on playing.
    _cast(piece, before) {
      const cast = {}, channels = new Set();
      for (const other of piece.kin) for (const channel of other.channels) channels.add(channel);
      for (const channel of CHANNELS) {
        if (!channels.has(channel)) continue;
        const able = piece.kin.filter((other) => other.channels.has(channel));
        const same = before && before[channel] ? able.find((other) => other.meta.track === before[channel]) : null;
        cast[channel] = same || (able.length > 1 ? able[Math.floor(this.random() * able.length) % able.length] : able[0]);
      }
      return cast;
    }

    // The stretch of a channel's part that is played at a strength: the one written for that
    // strength, or the nearest that was written (the calmer of two equally near). `group` is
    // anything with a cast: the decks playing a piece, or a piece that is about to be played.
    _part(group, order, channel, tier) {
      const from = group.cast[channel];
      const choices = from && from.windows[order] ? from.windows[order][channel] : null;
      if (!choices) return null;
      let best = choices[0];
      for (const clip of choices) {
        const near = Math.abs(clip.tier - tier), nearest = Math.abs(best.tier - tier);
        if (near < nearest || (near === nearest && clip.tier < best.tier)) best = clip;
      }
      return best;
    }

    // Which stretch of a piece is playing at a moment, and when that stretch began.
    _where(group, at) {
      const piece = group.piece, span = group.line * group.bar;
      const along = Math.max(at - group.origin, 0);
      const lap = Math.floor(along / piece.seconds + 1e-9);
      const order = Math.min(Math.floor((along - lap * piece.seconds) / span + 1e-6), piece.windows.length - 1);
      return { order, start: group.origin + lap * piece.seconds + order * span };
    }

    // How hard the game is asking the music to play, as one number: calm, steady or hard.
    _ask() { return this._wanted("rhythm").tier; }

    // Whether the loose phrases of a bucket are enough to make music of on their own.
    _freeEnough(bucket) {
      const count = {};
      for (const clip of bucket.clips.values()) if (!clip.piece) count[clip.channel] = (count[clip.channel] || 0) + 1;
      return CHANNELS.every((channel) => (count[channel] || 0) >= FREE_ENOUGH);
    }

    // Whether two keys sit together: the same notes, or all but one of them.
    _related(a, b) {
      const place = (key) => {
        const found = /^([A-G])([#b]?)\s*(.*)$/.exec(String(key || "").trim());
        if (!found) return null;
        const note = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 }[found[1]] + (found[2] === "#" ? 1 : found[2] === "b" ? -1 : 0);
        const mode = found[3].toLowerCase();
        const shift = mode.startsWith("lydian") ? 1 : mode.startsWith("mixolydian") ? -1 : mode.startsWith("dorian") ? -2
          : mode.startsWith("phrygian") ? -4 : mode.startsWith("locrian") ? -5
          : mode.startsWith("minor") || mode.startsWith("aeolian") ? -3 : 0;
        return (((note * 7) % 12) + shift + 24) % 12;          // where its notes sit on the circle of fifths
      };
      const one = place(a), other = place(b);
      if (one === null || other === null) return true;
      const apart = Math.abs(one - other);
      return Math.min(apart, 12 - apart) <= 1;
    }

    // What to play next: a piece (from where, and who plays what), or a stretch of loose phrases.
    //
    // A bucket without pieces is loose phrases without end, as it always was. Otherwise, in
    // this order: the piece a fight cut into is gone back to, at the bar it had reached; the
    // track that is playing goes on to its next piece, for as long as nothing in the bucket
    // suits the moment better; and failing both, the piece that best suits the moment is
    // chosen. What suits: first that it answers how hard the game is asking (`serves`), then
    // that it is for this kind of moment (a fight, a cave, the night: `role`), then that it
    // was written for this kind of place (`moods`), then that it is light or heavy as the
    // turn is, then that it stands at the right place in the story (a beginning after an
    // ending). Of several that suit equally, the one played least, then longest ago.
    //
    // Light and heavy take turns: after a heavy track the next is a light one, so that staying
    // in one place does not grow too intense, and after two light ones a heavy one may come.
    // A light place (the game says which) is always light.
    //
    // `options.after` is the decks whose music is ending of its own accord (`natural`) or is
    // being cut into; `except` a piece not to choose; `ask` a strength to choose for in place
    // of the one the game asks for now.
    _nextItem(bucket, options) {
      options = options || {};
      const index = this._index(bucket);
      if (!index.size) return { piece: null, turns: Infinity };
      const ask = options.ask === undefined ? this._ask() : options.ask;
      const now = this.ctx.currentTime;
      const after = options.after && options.after.piece ? options.after : null;
      const serves = (piece) => piece.meta.serves.includes(ask);
      const laps = (piece) => piece.windows.length === 1 && !piece.meta.next && piece.seconds < LAP_S
        ? Math.min(3, Math.max(1, Math.round(LAP_S / piece.seconds))) : 1;
      const slot = ask === 2 ? "fight" : "walk";
      const left = this.left[slot];
      if (left && !options.natural && left.key === bucket.key && left.piece !== options.except
          && index.has(left.piece) && serves(index.get(left.piece)) && now - left.at < (slot === "fight" ? FIGHT_AGAIN : RESUME_WITHIN)
          && (slot === "walk" || index.get(left.piece).meta.role === this.target.place)) {
        // (A fight's track is only gone on with in the same kind of moment: a fight's in a
        // fight, a boss's against a boss, a storm's in a storm.)
        const piece = index.get(left.piece);
        const from = Math.floor(left.position / piece.bar + 1e-6) * piece.bar;
        if (!options.peek) this.left[slot] = null;
        if (piece.seconds - from > 2 * piece.bar) return { piece, from, laps: 1, cast: this._cast(piece, left.casting), entry: "resume" };
        // It was all but over when the fight came: the track goes on from its next piece.
        const onward = piece.meta.next ? index.get(piece.meta.next) : null;
        if (onward && serves(onward)) return { piece: onward, from: 0, laps: 1, cast: this._cast(onward, left.casting), entry: "resume" };
      }
      const kinds = this.target.kinds || [], place = this.target.place, also = this.target.also || [];
      const off = (piece) => {
        const meta = piece.meta;
        const strength = serves(piece) ? 0 : Math.min(...meta.serves.map((tier) => Math.abs(tier - ask)));
        // The kind of moment the game names comes first; the kinds that take turns with it are
        // as good, except in a fight, where a piece written for a fight is wanted before a storm.
        const fight = place === "battle" || place === "boss";
        const role = meta.role === place ? 0 : also.includes(meta.role) ? (fight ? 0.3 : 0) : 1;
        const mood = !kinds.length || !meta.moods.length ? 0.5 : meta.moods.some((mood) => kinds.includes(mood)) ? 0 : 1;
        return strength * 100 + role * 10 + mood;
      };
      let least = Infinity;
      for (const piece of index.values()) least = Math.min(least, off(piece));
      const casting = after ? after.casting : null;
      if (after && options.natural) {
        // The track goes on into its next piece for as long as that piece answers what the
        // game asks. Two things end a track early: the player has walked into another kind of
        // place that the bucket has music of this sort for, or into a light place and the track
        // is a heavy one. (A calm moment, a cave or nightfall does not: what is written for
        // those comes when the track has ended.)
        const next = after.piece.meta.next ? index.get(after.piece.meta.next) : null;
        if (next && serves(next)) {
          const kind = (piece) => !kinds.length || !piece.meta.moods.length ? 0.5
            : piece.meta.moods.some((mood) => kinds.includes(mood)) ? 0 : 1;
          let nearer = false, lighter = false;
          for (const piece of index.values()) {
            if (!serves(piece) || piece.meta.role !== next.meta.role) continue;
            if (kind(piece) < kind(next)) nearer = true;
            if (piece.meta.light) lighter = true;
          }
          const tooHeavy = this.target.light === true && !next.meta.light && lighter;
          if (!nearer && !tooHeavy) return { piece: next, from: 0, laps: 1, cast: this._cast(next, casting), entry: "continue" };
        }
      }
      // A track has ended, or the moment has moved on from it. Now and then, where the bucket
      // has enough of them, a stretch of loose phrases comes between two tracks; and loose
      // phrases answer a fight where no piece was written for one.
      const free = this._freeEnough(bucket);
      if (free && least >= 100 && this._tierFor("drums", ask, bucket) === ask) return { piece: null, turns: 2 };
      if (free && after && options.natural && this.random() < bucket.share) {
        return { piece: null, turns: 1 + Math.floor(this.random() * 2) };
      }
      const want = after && options.natural ? STORY_NEXT[after.piece.meta.story] || "open" : "open";
      const shade = (piece) => {
        if (piece.meta.serves.includes(2) && !piece.meta.serves.includes(0)) return 0;      // a fight is a fight
        if (this.target.light === true) return piece.meta.light ? 0 : 5;
        if (this.heavy >= 1) return piece.meta.light ? 0 : 0.6;
        if (this.light >= 2) return piece.meta.light ? 0.3 : 0;
        return 0;
      };
      let best = [], bestScore = [Infinity, Infinity, Infinity];
      for (const piece of index.values()) {
        if (piece.id === options.except && index.size > 1) continue;
        const story = !piece.meta.story || piece.meta.story === want ? 0 : 0.25;
        const score = [off(piece) + shade(piece) + story, piece.plays, this.pieceAt.has(piece.id) ? this.pieceAt.get(piece.id) : -1];
        let order = 0;
        for (let i = 0; i < 3 && !order; i++) order = score[i] - bestScore[i];
        if (order < 0) { best = [piece]; bestScore = score; }
        else if (order === 0) best.push(piece);
      }
      if (!best.length) return null;
      const piece = best[Math.floor(this.random() * best.length) % best.length];
      return { piece, from: 0, laps: laps(piece), cast: this._cast(piece, null), entry: "start" };
    }

    // How loud a deck is: what the game asks of its channel, or of the channels it stands in
    // for (a band kept as one part is the tune and the drone too), and never less than the
    // piece says that channel must be for the piece to be whole.
    _level(group, channel) {
      let level = this._wanted(channel).level;
      const meta = group && group.piece ? group.piece.meta : null;
      if (meta) {
        for (const other of (meta.follow && meta.follow[channel]) || []) level = Math.max(level, this._wanted(other).level);
        const floor = meta.floor ? meta.floor[channel] : 0;
        if (floor > 0) level = Math.max(level, floor * this.target.bed);
      }
      return level;
    }

    // Lays a piece's part down on a deck as far ahead as it should be: stretch after stretch,
    // each running into the next without a seam, at the strength the game asks for.
    async _fillPiece(group, deck) {
      if (!(deck.channel in group.cast)) { deck.until = group.until; return; }      // nobody plays this channel in the piece
      while (deck.until < this.ctx.currentTime + AHEAD) {
        const at = deck.until;
        // The piece is over: what follows has decks of its own. (Its stretches are each a whole
        // number of samples, so their sum may be a sample or two off the length the piece
        // gives for itself; anything that close to the end is the end.)
        if (at >= group.until - 0.005) break;
        if (group.endAt !== undefined && at >= group.endAt - 1e-6) break;
        const where = this._where(group, at + 1e-4);
        const clip = this._part(group, where.order, deck.channel, this._tierAt(group, deck.channel, at + 0.001));
        if (!clip) { deck.until = group.until; break; }
        const buffer = await this._buffer(clip);
        if (!this.started || (this.group !== group && this.next !== group)) return;
        let start = at;
        if (start < this.ctx.currentTime + 0.02) {                     // the load took too long
          start = this.ctx.currentTime + NOTICE;
          this.late += 1;
        }
        const leaving = deck.passes.find((pass) => !pass.tail && Math.abs(pass.end - at) < 1e-3);
        let rise = 0;
        if (start === at) {
          const goesOn = leaving && leaving.clip.channel === clip.channel && leaving.clip.tier === clip.tier
            && leaving.clip.piece === clip.piece && (clip.order === leaving.clip.order + 1 || clip.id === leaving.clip.id);
          if (goesOn && leaving.clip.post) {
            rise = SEAM_OUT;                                            // the same music going on: nothing to be heard
          } else if (leaving) {
            // Another strength of the part: a blend, the old one ringing on under the new.
            rise = Math.min(BLEND_TURN * group.blend * group.bar, clip.frames / group.bucket.rate / 4);
            const old = this.buffers.get(leaving.clip.id);
            if (old) this._tail(deck, leaving.clip, old, at, rise);
          } else if (group.entry === "continue" && Math.abs(at - group.start) < 1e-3) {
            rise = SEAM_OUT;                                            // the piece before ran straight into this one
          }
        }
        if (deck.clip !== clip) { deck.clip = clip; deck.counted = false; deck.stale = false; }
        this._play(group, deck, clip, buffer, start, rise, start - where.start);
      }
      deck.passes = deck.passes.filter((pass) => pass.end > this.ctx.currentTime - 0.5);
    }

    // A piece changes gear: a part that was written at more than one strength takes the one the
    // game now asks for, at the same place in the piece. Harder on the next half beat, easier
    // on the next bar line.
    async _gearPiece(group) {
      for (const deck of Object.values(group.decks)) {
        if (!(deck.channel in group.cast)) continue;
        const soon = this.ctx.currentTime + NOTICE;
        let sounding = null;
        for (const pass of deck.passes) {
          if (pass.tail) continue;
          if (pass.start <= soon + 1e-6 && pass.end > soon && (!sounding || pass.start > sounding.start)) sounding = pass;
        }
        if (!sounding) continue;
        const changing = deck.swapAt !== undefined && soon < deck.swapAt;
        const playing = changing && deck.clip ? deck.clip : sounding.clip;
        const next = this._part(group, playing.order, deck.channel, this._tierAt(group, deck.channel, soon));
        if (!next || next.tier === playing.tier) continue;
        const harder = next.tier > playing.tier;
        const when = Math.max(this._lineAfter(group, this.ctx.currentTime + NOTICE, harder ? 0.125 : 1), group.start);
        if (when > sounding.end - 0.05) continue;                      // the stretch is turning over: the next look settles it
        const buffer = await this._buffer(next);
        if (!this.started || this.group !== group) return;
        const fade = (harder ? BLEND_FIGHT : BLEND_EASING) * group.blend * group.bar;
        this._cut(deck, when, fade);
        deck.clip = next;
        deck.counted = false;
        deck.swapAt = when;
        this._play(group, deck, next, buffer, when, fade, when - this._where(group, when + 1e-4).start);
      }
    }

    // The decks that were made ready for what follows are not wanted after all.
    _dropNext() {
      if (!this.next) return;
      for (const deck of Object.values(this.next.decks)) {
        for (const pass of deck.passes) { pass.source.stop(0); pass.source.disconnect(); }
      }
      this.next = null;
    }

    // What is ending rings on under what follows: each deck's last stretch, past its end.
    _tails(group, at, fall) {
      for (const deck of Object.values(group.decks)) {
        const pass = deck.passes.find((each) => !each.tail && Math.abs(each.end - at) < 1e-3);
        const buffer = pass ? this.buffers.get(pass.clip.id) : null;
        if (buffer) this._tail(deck, pass.clip, buffer, at, fall);
      }
    }

    // The music that is playing is coming to its end (a piece, or a stretch of loose phrases
    // between two): what follows is made ready, to come in on the beat this ends on. A track
    // goes on into its next piece without a seam. Anything else comes in whole on its first
    // beat, while what is ending rings on underneath it for a couple of bars: less when the
    // two are in keys that do not sit together. And when a moment of silence is due and a
    // track has just ended, the silence comes first.
    async _handover(group) {
      if (this.next || group.endAt !== undefined || !(group.until < Infinity)) return;
      if (group.until - this.ctx.currentTime > HANDOVER) return;
      const rest = this.bucket.rest;
      const ended = !group.piece || !group.piece.meta.next;
      if (ended && rest && rest.every_s > 0 && rest.for_s > 0 && this.restDue !== null && group.until >= this.restDue
          && this.target.intensity < WAVE_OFF) {
        this._tails(group, group.until, RING * group.bar);
        group.endAt = group.until;
        this.silenceUntil = group.until + rest.for_s * (0.6 + 0.8 * this.random());
        return;
      }
      const item = this._nextItem(this.bucket, { after: group, natural: true });
      if (!item) return;
      await this._first(this.bucket, item);
      if (!this.started || this.group !== group || this.next || this._quiet()) return;
      const at = group.until;
      if (at < this.ctx.currentTime + 0.05) return;                    // too late to do it cleanly: tick() starts afresh
      if (item.entry !== "continue") {
        const together = !group.piece || !item.piece || this._related(group.piece.meta.tonic, item.piece.meta.tonic);
        this._tails(group, at, Math.min((together ? RING : RING_APART) * group.bar, 6.0));
      }
      this.next = this._group(at, 0, item);
    }

    // The game asks for something the music that is playing was not written for: a fight, or
    // the calm after one. Another piece takes over at once (on the next beat when the music is
    // getting harder, on the next bar line when it is easing off), and what was playing is
    // remembered, to be gone back to. `force` is for moving on whatever the game asks (a skip,
    // or the piece having been banned). True if the music moved.
    async _regroup(force) {
      const group = this.group;
      const index = this.bucket ? this._index() : null;
      if (!group || !index) return false;
      const ask = this._ask();
      // (A piece that is no longer in the bucket: it was banned, or pieces were switched off.)
      const gone = Boolean(group.piece && !index.has(group.piece.id));
      if (!index.size && !gone) return false;
      const here = group.piece ? group.piece.meta.serves : [0, 1, 2];
      if (!force && !gone) {
        if (group.piece ? here.includes(ask) : ask < 2) return false;
      }
      // What was fetched ahead for a fight is what comes in, unless this is a boss and that is
      // not a boss's piece: then one is chosen now.
      const ready = this.standby && this.standby.piece && ask === 2 && !force && index.has(this.standby.piece.id);
      const standby = ready && (this.target.place !== "boss" || this.standby.piece.meta.role === "boss") ? this.standby : null;
      const item = standby || this._nextItem(this.bucket, { after: group, except: group.piece ? group.piece.id : null });
      if (standby && standby.entry === "resume") this.left.fight = null;       // the fight's track is being gone on with
      this.standby = null;
      if (!item) return false;
      if (!force && !gone) {
        // Only for something that answers the game better than what is playing.
        if (!item.piece ? Boolean(group.piece) && this._tierFor("drums", ask) !== ask : !item.piece.meta.serves.includes(ask)) return false;
        if (!item.piece && !group.piece) return false;
      }
      await this._first(this.bucket, item);
      if (!this.started || this.group !== group || this._quiet()) return false;
      const now = this.ctx.currentTime;
      const harder = !force && ask > Math.max(...here.filter((tier) => tier <= 2), 0) && (group.piece ? true : ask === 2);
      const when = Math.max(this._lineAfter(group, now + NOTICE, harder ? 0.25 : 1), group.start);
      const fade = Math.min((harder ? BLEND_FIGHT : BLEND_EASING) * group.bar, 6.0);
      if (group.piece && !gone && !force) {
        const mine = group.piece.meta.serves;
        this.left[mine.includes(0) || mine.includes(1) ? "walk" : "fight"] = {
          key: this.bucket.key, piece: group.piece.id, position: (when - group.origin) % group.piece.seconds,
          at: now, casting: group.casting };
      }
      this._dropNext();
      this._release(group, when, fade);
      this.group = this._group(when, harder ? 0 : fade, item);
      for (const deck of Object.values(this.group.decks)) {
        deck.audible = this._level(this.group, deck.channel) > 0;
        await this._fill(this.group, deck);
        if (!this.group || !this.started) return true;
      }
      return true;
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

    // Five decks that begin to play at `start`, coming in over `rise` seconds. `item` is what
    // they play: loose phrases on the bucket's bar grid (for so many turns of the form, or
    // without end), or a piece, on the piece's own bar grid, from some way into it.
    _group(start, rise, item) {
      const ctx = this.ctx;
      const bucket = this.bucket;
      const piece = item && item.piece ? item.piece : null;
      const origin = start - (piece ? item.from || 0 : 0);        // where the grid begins: the first beat of a piece
      const group = { bucket, origin, start, bar: piece ? piece.bar : bucket.bar, decks: {}, claimed: -1, claims: 0,
                      // Where decks may take a new phrase: where the form comes round, or at
                      // every four-bar line when the phrases have no form; and how many may.
                      line: piece ? piece.line : bucket.cycle || LINE_BARS, changes: bucket.changes || 1,
                      // A piece has its own shape, written into it: the player adds none.
                      form: piece ? { verse: piece.line, build: 0, chorus: 0 } : bucket.form,
                      arc: piece ? null : bucket.arc,
                      piece, cast: piece ? item.cast : null, entry: item && item.entry || "",
                      // A style may ask for longer or shorter blends than the usual.
                      blend: bucket.arc && bucket.arc.blend > 0 ? bucket.arc.blend : 1,
                      bed: ctx.createGain(), rest: ctx.createGain() };
      // When this music ends of its own accord, and something else is to follow.
      group.until = piece ? origin + piece.seconds * (item.laps || 1)
        : item && item.turns < Infinity ? origin + item.turns * group.line * group.bar : Infinity;
      if (piece) {
        group.casting = {};
        for (const channel of Object.keys(group.cast)) group.casting[channel] = group.cast[channel].meta.track;
        this.pieceTurn += 1;
        this.pieceAt.set(piece.id, this.pieceTurn);
        // A track beginning: light and heavy are counted, so that they take turns.
        if (group.entry === "start" && piece.meta.serves.includes(0)) {
          if (piece.meta.light) { this.light += 1; this.heavy = 0; } else { this.heavy += 1; this.light = 0; }
        }
      }
      for (const node of [group.bed, group.rest]) {
        if (rise) {
          node.gain.setValueAtTime(0, start);
          node.gain.linearRampToValueAtTime(1, start + rise);
          this.moves.set(node.gain, { from: 0, to: 1, t0: start, t1: start + rise });
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
      // (Music that ends of its own accord has its silences between one track and the next.)
      const rest = bucket.rest, rests = Boolean(rest && rest.every_s > 0 && rest.for_s > 0);
      const endless = !(group.until < Infinity);
      group.restTurn = endless && bucket.form && rests
        ? Math.max(2, Math.round(rest.every_s * (0.6 + 0.8 * this.random()) / (group.line * group.bar))) : null;
      if (!endless && rests && this.restDue === null) this.restDue = start + rest.every_s * (0.6 + 0.8 * this.random());
      group.bed.connect(group.bedArc).connect(this.bedHighpass);
      group.rest.connect(group.restArc).connect(group.sweep).connect(this.bus);
      for (const channel of CHANNELS) {
        const level = ctx.createGain();
        level.gain.value = this._level(group, channel);
        level.connect(BED.includes(channel) ? group.bed : group.rest);
        group.decks[channel] = { channel, level, clip: null, passes: [], until: start, changeAt: 0,
                                 layOutUntil: 0, returning: false, counted: false, stale: false, audible: false };
      }
      return group;
    }

    // Lets a group go: it fades away over `fall` seconds from `at` and is then forgotten.
    _release(group, at, fall) {
      if (!group) return;
      for (const node of [group.bed, group.rest]) {
        const from = this._valueAt(node.gain, at);
        node.gain.cancelScheduledValues(at);
        node.gain.setValueAtTime(from, at);
        node.gain.linearRampToValueAtTime(0, at + fall);
        this.moves.set(node.gain, { from, to: 0, t0: at, t1: at + fall });
      }
      for (const deck of Object.values(group.decks)) {
        for (const pass of deck.passes) {
          // A stretch of a written part that would end during the fade plays on into what
          // the music went on to, so that the fade is not cut short.
          if (!pass.tail && pass.limit > pass.end && pass.end > at && pass.end < at + fall + 0.02 && pass.end > this.ctx.currentTime + 0.01) {
            pass.gain.gain.cancelScheduledValues(pass.end - 1e-4);
            pass.end = Math.min(pass.limit, at + fall + 0.02);
          }
          pass.source.stop(Math.min(at + fall + 0.02, Math.max(pass.limit || 0, pass.end + 0.03)));
        }
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
    _play(group, deck, clip, buffer, at, rise, into) {
      const ctx = this.ctx, length = clip.frames / group.bucket.rate;
      // A drone without a form has no beat to keep: it always plays from its beginning, each
      // pass laid over the end of the last. A drone that is a turn of the form swells with the
      // build-up and opens out in the chorus, so it keeps to the grid like everything else.
      const loose = deck.channel === "texture" && !group.form;
      // (A stretch of a piece's part says itself how far into it the moment is.)
      if (into === undefined) into = loose ? 0 : ((at - group.origin) % length + length) % length;
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
      if (up > 0.1) {
        // A blend: the level follows a quarter of a sine, so that with the other phrase falling
        // along the matching curve the two together stay as loud as either alone.
        this._blend(gain.gain, base, at, up, true);
      } else if (up > 0) {
        gain.gain.setValueAtTime(0, at);
        gain.gain.linearRampToValueAtTime(base, at + up);
      } else {
        gain.gain.setValueAtTime(base, at);
      }
      // A stretch of a written part does not fade before its end: it runs on for a moment into
      // what the music went on to and fades there, so that the stretch that follows, coming in
      // over the same moment, joins it without a seam.
      const run = (clip.post || 0) >= SEAM_OUT * group.bucket.rate ? SEAM_OUT : 0;
      if (run) {
        gain.gain.setValueAtTime(base, end);
        gain.gain.linearRampToValueAtTime(0, end + run);
      } else {
        gain.gain.setValueAtTime(base, end - down);
        gain.gain.linearRampToValueAtTime(0, end);
      }
      source.connect(gain).connect(deck.level);
      source.start(at, offset);
      source.stop(end + run + 0.01);
      const pass = { clip, source, gain, base, start: at, end, up, limit: end + (clip.post || 0) / group.bucket.rate };
      deck.passes.push(pass);
      // The drone's next pass starts while this one is still fading, so that it never dips.
      deck.until = end - overlap;
      this.log.push({ at, channel: deck.channel, clip: clip.id, tier: clip.tier, offset });
      if (this.log.length > LOG_LENGTH) this.log.splice(0, this.log.length - LOG_LENGTH);
      return pass;
    }

    // One half of a blend: a level that follows a quarter of a sine from nothing up to `top`
    // over `seconds`, or from `top` down to nothing. Laid down as a run of short straight
    // ramps, which every browser lets be cut short later; a single curve it may not.
    _blend(param, top, at, seconds, rising) {
      param.setValueAtTime(rising ? 0 : top, at);
      for (let step = 1; step <= BLEND_STEPS; step++) {
        const along = (step / BLEND_STEPS) * Math.PI / 2;
        param.linearRampToValueAtTime(top * (rising ? Math.sin(along) : Math.cos(along)), at + seconds * step / BLEND_STEPS);
      }
    }

    // The phrase a deck is leaving plays on from its own beginning for `fall` seconds, fading
    // away under the phrase that takes its place: the other half of the blend where the form
    // comes round.
    _tail(deck, clip, buffer, at, fall) {
      const ctx = this.ctx, base = gainOf(clip.gain_db);
      if (clip.piece) {
        // A stretch of a written part: it rings on into what the music went on to. It comes in
        // under the last moment of the stretch itself, which is fading over that moment, so
        // the two together are the music going on unbroken; then it falls away.
        fall = Math.min(fall, (clip.post || 0) / ctx.sampleRate - 0.005);
        if (!(fall > 2 * SEAM_OUT)) return;
        const source = ctx.createBufferSource();
        source.buffer = buffer;
        const gain = ctx.createGain();
        const curve = (seconds) => base * Math.cos(Math.min(seconds / fall, 1) * Math.PI / 2);
        gain.gain.setValueAtTime(0, at);
        gain.gain.linearRampToValueAtTime(curve(SEAM_OUT), at + SEAM_OUT);
        for (let step = 1; step <= BLEND_STEPS; step++) {
          const seconds = fall * step / BLEND_STEPS;
          if (seconds > SEAM_OUT) gain.gain.linearRampToValueAtTime(curve(seconds), at + seconds);
        }
        source.connect(gain).connect(deck.level);
        source.start(at, clip.frames / ctx.sampleRate);
        source.stop(at + fall + 0.01);
        deck.passes.push({ clip, source, gain, base, start: at, end: at + fall, tail: true, fall });
        return;
      }
      fall = Math.min(fall, clip.frames / ctx.sampleRate - 0.05);
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      const gain = ctx.createGain();
      this._blend(gain.gain, base, at, fall, false);
      source.connect(gain).connect(deck.level);
      source.start(at, 0);
      source.stop(at + fall + 0.01);
      deck.passes.push({ clip, source, gain, base, start: at, end: at + fall, tail: true, fall });
    }

    // How loud a phrase is at a moment of its own envelope: on its way in, at full, or (the
    // tail of a blend) on its way out.
    _levelAt(pass, when) {
      const quarter = Math.PI / 2;
      if (pass.tail) return pass.base * Math.cos(Math.min(Math.max((when - pass.start) / pass.fall, 0), 1) * quarter);
      if (pass.up > 0 && when < pass.start + pass.up) {
        const along = Math.max(when - pass.start, 0) / pass.up;
        return pass.base * (pass.up > 0.1 ? Math.sin(along * quarter) : along);
      }
      return pass.base;
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
          const audible = Math.min(fall, Math.max(pass.limit || 0, pass.end) - when);
          const level = pass.gain.gain;
          // It falls from wherever it is at that moment: it may itself still be on its way in.
          // The fall is given its starting point outright, or it would be taken to start where
          // the phrase did and the phrase would drop away at once.
          // What was laid down from `when` on goes, and with it the rest of any rise the
          // phrase was in the middle of; the first ramp puts that rise back as far as `when`.
          const from = this._levelAt(pass, when);
          level.cancelScheduledValues(when);
          level.linearRampToValueAtTime(from, when);
          level.linearRampToValueAtTime(0, when + audible);
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
      if (group.piece) return this._fillPiece(group, deck);
      while (deck.until < this.ctx.currentTime + AHEAD) {
        const at = deck.until;
        if (group.endAt !== undefined && at >= group.endAt - 1e-6) break;       // a silence begins there
        if (at >= group.until - 1e-6) break;                                    // something else follows from there
        const bar = Math.round((at - group.origin) / group.bar);
        const tier = this._tierAt(group, deck.channel, at + 0.001);
        let clip = deck.clip && group.bucket.clips.has(deck.clip.id) ? deck.clip : null;
        // The phrase that has been sounding up to here, if one has: what a change is a blend out of.
        const leaving = group.form ? deck.passes.find((pass) => !pass.tail && Math.abs(pass.end - at) < 1e-3) : null;
        const sitting = deck.layOutUntil > 0 && deck.layOutUntil === bar;       // a tune coming in after sitting out
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
        if (!this.started || (this.group !== group && this.next !== group)) return;     // the music moved on while it loaded
        let start = at;
        if (start < this.ctx.currentTime + 0.02) {                     // the load took too long
          start = this.ctx.currentTime + NOTICE;
          this.late += 1;
        }
        let rise = 0;
        if (group.form && start === at) {
          if (leaving && leaving.clip.id !== clip.id) {
            // Another phrase takes over: the two are blended, longer when it is the whole band
            // changing for a turn of its own than when it is one deck moving on.
            const bars = leaving.clip.tier !== clip.tier ? BLEND_TURN : BLEND[deck.channel];
            rise = Math.min(bars * group.blend * group.bar, clip.frames / group.bucket.rate / 4);
            const old = this.buffers.get(leaving.clip.id);             // it was playing a moment ago
            if (old) this._tail(deck, leaving.clip, old, at, rise);
          } else if (sitting) {
            rise = BLEND_ENTRY * group.blend * group.bar;
          }
        }
        this._play(group, deck, clip, buffer, start, rise);
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
          if (pass.tail) continue;                                     // a phrase on its way out does not count
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
        const harder = tier > now.tier || sittingOut;
        const when = Math.max(this._lineAfter(group, this.ctx.currentTime + NOTICE, harder ? 0.125 : 1), group.origin);
        // With a form a change of strength is a blend: half a bar when a fight comes in, two
        // bars when the music eases off again.
        const fade = group.form ? (harder ? BLEND_FIGHT : BLEND_EASING) * group.blend * group.bar : SWAP[deck.channel];
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
      return gainOf(group.arc.verse_db * (fight ? 0.35 : 1));
    }

    // Lays down the shape of one turn of the form from `from` on: the verse held back, a rise
    // through the build-up, the chorus at full, and with a sweep the lows thinning out over the
    // second half of the build-up and coming back as the chorus lands.
    _shape(group, turn, from) {
      const length = group.line * group.bar;
      const start = group.origin + turn * length;
      const build = start + group.form.verse * group.bar, chorus = build + group.form.build * group.bar;
      if (from >= build) return;         // the rise is already under way, or over: it stands as laid down
      // In a turn that eases off, the drums and the bass sit back all the way through.
      const eased = this._waveAt(group, start + 0.001) < 0;
      for (const node of [group.bedArc, group.restArc]) {
        const top = eased && node === group.restArc ? EASE_LEVEL : 1.0;
        const low = this._verseGain(group) * top;
        if (from <= start && turn === 0) node.gain.setValueAtTime(low, start);
        else node.gain.setTargetAtTime(low, Math.max(from, start), from > start ? 0.15 : 0.6);
        node.gain.setValueAtTime(low, build);
        node.gain.exponentialRampToValueAtTime(top, chorus);
      }
      const sweep = group.arc.sweep_hz || 0;
      const half = build + (chorus - build) / 2;
      if (sweep > 20 && from <= half) {
        group.sweep.frequency.setValueAtTime(20, half);
        group.sweep.frequency.exponentialRampToValueAtTime(sweep, chorus - 0.03);
        group.sweep.frequency.setTargetAtTime(20, chorus - 0.01, 0.004);
      }
    }

    // Keeps the shape of the form laid down as far ahead as the decks are.
    _arc(group) {
      if (!group.form || !group.arc) return;
      const length = group.line * group.bar;
      while (group.origin + group.arcTurn * length < this.ctx.currentTime + AHEAD) {
        this._shape(group, group.arcTurn, group.origin + group.arcTurn * length);
        group.arcTurn += 1;
      }
    }

    // A fight has begun or ended: the turn of the form that is playing is shaped again from
    // now, so that a fight in a verse is not left sitting at the verse's level.
    _reshape(group) {
      if (!group.form || !group.arc) return;
      const now = this.ctx.currentTime, length = group.line * group.bar;
      if (now <= group.origin) return;
      const turn = Math.floor((now - group.origin) / length);
      // Only a verse is shaped again. Once the build-up has begun the rise stands as it was
      // laid down, and the chorus is at full either way.
      if (now >= group.origin + turn * length + group.form.verse * group.bar) return;
      for (const param of [group.bedArc.gain, group.restArc.gain, group.sweep.frequency]) param.cancelScheduledValues(now);
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
        const from = Math.max(at - fade, now), level = this._valueAt(node.gain, from);
        node.gain.setValueAtTime(level, from);
        node.gain.linearRampToValueAtTime(0, at);
        this.moves.set(node.gain, { from: level, to: 0, t0: from, t1: at });
      }
      group.endAt = at;
      this.silenceUntil = at + group.bucket.rest.for_s * (0.6 + 0.8 * this.random());
    }

    // A fight while the music is fading away to a silence: it comes straight back up and plays on.
    _unrest(group) {
      if (group.endAt === undefined) return;
      for (const node of [group.bed, group.rest]) this._ramp(node.gain, 1, 0.15);
      group.endAt = undefined;
      if (group.restTurn !== null) group.restTurn += 1;
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
            this._dropNext();
            this._release(this.group, now, 0.05);
            this.group = null;
          }
          if (!this.group) return;
        }
        if (this.group && this.next && now >= this.next.start - 1e-3) {
          // What was made ready has begun: its decks are the ones playing now.
          this.group.gone = Math.max(this.group.until, now) + 8;
          this.leaving.push(this.group);
          this.group = this.next;
          this.next = null;
        }
        if (this.group && this.group.endAt !== undefined && now >= this.group.endAt) {
          // The music has faded away: a moment of silence.
          this.group.gone = now + 8;
          this.leaving.push(this.group);
          this.group = null;
          this.afterSilence = true;
          this.restDue = null;
        }
        if (this.group && !this.next && now >= this.group.until) {
          // It ended with nothing made ready to follow (a part could not be fetched in time).
          this.group.gone = now + 8;
          this.leaving.push(this.group);
          this.group = null;
        }
        if (!this.group) {
          if (!this.bucket.clips.size) return;                         // nothing has been made yet
          const fight = this.target.intensity >= WAVE_OFF;
          if (now < this.silenceUntil && !fight) return;               // the silence holds
          this.silenceUntil = 0;
          // The phrase each deck starts with is fetched before the grid is laid down, so that
          // all of them come in together on its first beat.
          const item = this._nextItem(this.bucket, { fresh: true });
          if (!item) return;
          const plan = await this._first(this.bucket, item);
          for (const [slot, clip] of plan) this.planned.set(slot, clip);
          if (!this.started || this._quiet()) return;                  // the game went quiet while they loaded
          // Out of a silence the music fades back in, unless a fight is what ended it.
          const rise = this.afterSilence ? (this.target.intensity >= WAVE_OFF ? REST_IN_FAST : BACK_IN) : 0;
          this.afterSilence = false;
          this.group = this._group(Math.max(this.ctx.currentTime + NOTICE, this.holdUntil), rise, item);
        }
        // A fight, or the calm after one, may call for another piece altogether.
        await this._regroup(false);
        if (!this.group || !this.started) return;
        const group = this.group;
        for (const deck of Object.values(group.decks)) {
          deck.audible = this._level(group, deck.channel) > 0;
          this._count(deck);
        }
        if (group.piece) await this._gearPiece(group); else await this._gear();
        if (this.group !== group) return;
        this._breath(group);
        // What is playing is laid down first; then what follows it is made ready (which may
        // mean fetching it, and a short piece must not wait for that), and laid down in turn.
        for (const each of [group, null]) {
          if (each === null) {
            await this._handover(group);
            if (this.group !== group || !this.started) return;
          }
          const decks = each || this.next;
          if (!decks) continue;
          // The deck that has waited longest past its time goes first for the free line.
          for (const deck of Object.values(decks.decks).sort((a, b) => a.changeAt - b.changeAt)) {
            await this._fill(decks, deck);
            if (this.group !== group || !this.started) return;
          }
        }
        for (const deck of Object.values(group.decks)) this._count(deck);
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
          this._dropNext();
          if (this.group) { this._release(this.group, this.ctx.currentTime, 0.05); this.group = null; }
          return;
        }
        if (this.group) {
          if (before.place !== this.target.place || String(before.kinds) !== String(this.target.kinds)) this.standby = null;
          // The player has walked into another kind of place in the last seconds of a piece,
          // after the track's next piece was made ready: what follows is thought about again.
          if (this.next && this.next.entry === "continue"
              && (String(before.kinds) !== String(this.target.kinds) || before.light !== this.target.light)) this._dropNext();
          // A fight, or the calm after one, may call for another piece altogether.
          if (this.target.intensity >= WAVE_OFF) this._unrest(this.group);
          if (await this._regroup(false)) return;
          for (const deck of Object.values(this.group.decks)) {
            const audible = this._level(this.group, deck.channel) > 0;
            if (deck.audible && !audible) deck.stale = true;       // it has had its say: another next time
            deck.audible = audible;
            this._count(deck);
          }
          // A fight beginning or ending changes how the turn that is playing is shaped.
          const edge = (level) => (before.intensity >= level) !== (this.target.intensity >= level);
          if (this.target.intensity >= WAVE_OFF) this._unrest(this.group);
          if (edge(0.8) || edge(WAVE_OFF)) this._reshape(this.group);
          if (this.group.piece) await this._gearPiece(this.group); else await this._gear();
        }
      });
    }

    // Where a level this engine moves is at a moment, by the engine's own account of its last
    // move. A level that has never been moved is where it was put.
    _valueAt(param, time) {
      const move = this.moves.get(param);
      if (!move) return param.value;
      if (time >= move.t1) return move.to;
      if (time <= move.t0) return move.from;
      const along = (time - move.t0) / (move.t1 - move.t0);
      return move.exponential ? move.from * Math.pow(move.to / move.from, along)
                              : move.from + (move.to - move.from) * along;
    }

    // Moves a level to `value` over `seconds` from wherever it is now. The ramp is given its
    // starting point outright: without one, a level that has never been moved is taken to have
    // been moving since the page was opened, and jumps nearly all the way at once.
    _ramp(param, value, seconds, exponential) {
      const now = this.ctx.currentTime;
      const floor = exponential ? 1 : -Infinity;
      const from = Math.max(this._valueAt(param, now), floor), to = Math.max(value, floor);
      param.cancelScheduledValues(now);
      param.setValueAtTime(from, now);
      if (!(seconds > 0)) param.setValueAtTime(to, now);
      else if (exponential) param.exponentialRampToValueAtTime(to, now + seconds);
      else param.linearRampToValueAtTime(to, now + seconds);
      this.moves.set(param, { from, to, t0: now, t1: now + Math.max(seconds, 0), exponential: Boolean(exponential) });
    }

    _levels(before, wasQuiet) {
      const t = this.target, quick = t.fade_s < 0.3;
      for (const group of [this.group, this.next]) {
        if (!group) continue;
        for (const deck of Object.values(group.decks)) {
          const level = this._level(group, deck.channel);
          const was = this._valueAt(deck.level.gain, this.ctx.currentTime);
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
        this._dropNext();
        if (this.group) { this._release(this.group, now, 0.3); this.group = null; }
      });
    }

    // Something happened in the game that the music marks in its own way. A death runs the
    // music down like a record stopping; what follows starts when it has run down.
    moment(name) {
      return this._serial(async () => {
        if (name !== "died" || !this.started || !this.group) return;
        const now = this.ctx.currentTime;
        this._dropNext();
        this.left = { walk: null, fight: null };
        for (const deck of Object.values(this.group.decks)) {
          for (const pass of deck.passes) {
            if (pass.start > now) { pass.source.stop(0); continue; }
            pass.source.playbackRate.setValueAtTime(1, now);
            pass.source.playbackRate.linearRampToValueAtTime(0.3, now + WIND_DOWN);
            pass.source.stop(now + WIND_DOWN + 0.05);
            pass.gain.gain.cancelScheduledValues(now);
            pass.gain.gain.setValueAtTime(this._levelAt(pass, now), now);
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
        if (group.piece) {                                 // a piece: another takes its place
          this.left.walk = null;
          await this._regroup(true);
          return;
        }
        const when = Math.max(this._lineAfter(group, this.ctx.currentTime + NOTICE, 1), group.origin);
        for (const deck of Object.values(group.decks)) {
          if (!deck.clip || !deck.audible) continue;
          const next = this._pick(deck.channel, this._tierAt(group, deck.channel, when), deck.clip);
          if (!next || next.id === deck.clip.id) continue;
          const buffer = await this._buffer(next);
          if (this.group !== group) return;
          const fade = group.form ? group.blend * group.bar : SWAP[deck.channel];
          this._cut(deck, when, fade);
          this._take(group, deck, next, Math.round((when - group.origin) / group.bar));
          this._play(group, deck, next, buffer, when, fade);
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
      // The piece that is playing: what it is called, where in its story it stands, and how far through it is.
      let piece = null;
      if (this.group && this.group.piece) {
        const group = this.group, meta = group.piece.meta;
        piece = { id: group.piece.id, title: meta.title, story: meta.story, track: meta.track, role: meta.role,
                  at: Math.max(this.ctx.currentTime - group.origin, 0), of: group.piece.seconds };
      }
      return {
        started: this.started, forever: true, bucket: this.bucket ? this.bucket.key : null,
        phrases: this.bucket ? this.bucket.clips.size : 0, playing, heard, piece,
        pieces: this.bucket ? this._index().size : 0,
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
