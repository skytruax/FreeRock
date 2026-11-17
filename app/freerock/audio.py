"""Audio in and out: decoding what ElevenLabs sends, reading and writing files, resampling.

Inside FreeRock audio is a NumPy array of float32, shaped (frames, channels), with a sample rate
carried beside it. Stored tracks are FLAC, which is lossless, so every part of FreeRock counts in
the same samples.
"""
from __future__ import annotations

import io
from math import gcd
from pathlib import Path

import av
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


def pcm16_to_float(data: bytes, channels: int) -> np.ndarray:
    """Raw 16-bit little-endian samples, as ElevenLabs sends for its pcm_ formats."""
    if len(data) % (2 * channels):
        raise ValueError("%d bytes is not a whole number of %d-channel 16-bit frames" % (len(data), channels))
    samples = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
    return samples.reshape(-1, channels)


def float_to_pcm16(audio: np.ndarray) -> bytes:
    clipped = np.clip(audio, -1.0, 32767.0 / 32768.0)
    return np.round(clipped * 32768.0).astype("<i2").tobytes()


class PcmStream:
    """Raw 16-bit audio arriving in pieces of any size; hands back whole frames as they complete."""

    def __init__(self, channels: int):
        self.channels = channels
        self._rest = b""

    def feed(self, data: bytes) -> np.ndarray:
        data = self._rest + data
        frame_bytes = 2 * self.channels
        usable = len(data) - len(data) % frame_bytes
        self._rest = data[usable:]
        return pcm16_to_float(data[:usable], self.channels)

    @property
    def leftover_bytes(self) -> int:
        return len(self._rest)


def _frames_to_array(frames: list[np.ndarray]) -> np.ndarray:
    if not frames:
        return np.zeros((0, 2), dtype=np.float32)
    return np.concatenate(frames, axis=1).T.astype(np.float32, copy=False)


class CompressedStream:
    """Compressed audio (MP3 by default) arriving in pieces; hands back decoded audio as it can.

    Decoding in pieces keeps the encoder's lead-in and tail (a few hundredths of a second of
    near-silence) that decoding a finished file trims off. FreeRock stores what this decoder
    produced, so a track played while it streams and the stored copy are the same samples.
    """

    def __init__(self, codec: str = "mp3"):
        self._codec = av.CodecContext.create(codec, "r")
        self._resampler: av.AudioResampler | None = None
        self.sample_rate: int | None = None
        # An MP3 file may open with an ID3 tag (title, artist and so on). It is not audio, and the
        # decoder rejects it, so it is measured and stepped over before anything is decoded.
        self._head = b""
        self._head_done = codec != "mp3"
        self._skip = 0

    def _without_tag(self, data: bytes) -> bytes:
        if self._skip:
            dropped = min(self._skip, len(data))
            self._skip -= dropped
            return data[dropped:]
        if self._head_done:
            return data
        self._head += data
        if len(self._head) < 10:
            return b""
        head, self._head, self._head_done = self._head, b"", True
        if head[:3] != b"ID3":
            return head
        # The tag's length is stored as four 7-bit numbers; ten more bytes follow if it has a footer.
        size = (head[6] << 21) | (head[7] << 14) | (head[8] << 7) | head[9]
        total = 10 + size + (10 if head[5] & 0x10 else 0)
        if total >= len(head):
            self._skip = total - len(head)
            return b""
        return head[total:]

    def _convert(self, frame: av.AudioFrame) -> list[np.ndarray]:
        if self._resampler is None:
            self.sample_rate = frame.sample_rate
            self._resampler = av.AudioResampler(format="fltp", layout=frame.layout.name,
                                                rate=frame.sample_rate)
        return [out.to_ndarray() for out in self._resampler.resample(frame)]

    def feed(self, data: bytes) -> np.ndarray:
        pieces: list[np.ndarray] = []
        data = self._without_tag(data)
        if not data:
            return _frames_to_array(pieces)
        for packet in self._codec.parse(data):
            for frame in self._codec.decode(packet):
                pieces.extend(self._convert(frame))
        return _frames_to_array(pieces)

    def finish(self) -> np.ndarray:
        """Call once after the last piece: returns whatever the decoder was still holding."""
        pieces: list[np.ndarray] = []
        for frame in self._codec.decode(None):
            pieces.extend(self._convert(frame))
        return _frames_to_array(pieces)


def decode_bytes(data: bytes) -> tuple[np.ndarray, int]:
    """Decodes a whole file held in memory (MP3, Opus, FLAC, WAV). Returns (audio, sample rate)."""
    pieces: list[np.ndarray] = []
    with av.open(io.BytesIO(data)) as container:
        stream = container.streams.audio[0]
        resampler = None
        rate = None
        for frame in container.decode(stream):
            if resampler is None:
                rate = frame.sample_rate
                resampler = av.AudioResampler(format="fltp", layout=frame.layout.name, rate=rate)
            pieces.extend(out.to_ndarray() for out in resampler.resample(frame))
    if rate is None:
        raise ValueError("No audio could be decoded from %d bytes" % len(data))
    return _frames_to_array(pieces), rate


def to_stereo(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        audio = audio[:, None]
    if audio.shape[1] == 2:
        return audio
    if audio.shape[1] == 1:
        return np.repeat(audio, 2, axis=1)
    raise ValueError("Expected one or two channels, got %d" % audio.shape[1])


def to_mono(audio: np.ndarray) -> np.ndarray:
    return audio if audio.ndim == 1 else audio.mean(axis=1)


def resample(audio: np.ndarray, rate_from: int, rate_to: int) -> np.ndarray:
    if rate_from == rate_to:
        return audio
    divisor = gcd(rate_from, rate_to)
    return resample_poly(audio, rate_to // divisor, rate_from // divisor, axis=0).astype(np.float32)


def write_flac(path: Path, audio: np.ndarray, rate: int) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, rate, format="FLAC", subtype="PCM_24")


# Music that is kept (the studio's tracks, the buckets' parts, the listening pages) is kept as MP3 at the encoder's
# best variable rate: about a quarter of the room of FLAC for a full part, much less for a sparse one ("save stems to
# mp3 so theres more room", "do great quality", 2026-11-16). This machine's encoder and decoder give back exactly as
# many samples as went in, each where it was (tried that night: a click came back on the same sample), so the parts
# of a piece stay in step and its stretches join without a seam.
def write_mp3(path: Path, audio: np.ndarray, rate: int) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.clip(audio, -1.0, 1.0), rate, format="MP3", subtype="MPEG_LAYER_III", compression_level=0.0,
             bitrate_mode="VARIABLE")


def write_wav(path: Path, audio: np.ndarray, rate: int) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, rate, format="WAV", subtype="PCM_16")


def read_audio(path: Path) -> tuple[np.ndarray, int]:
    audio, rate = sf.read(str(path), dtype="float32", always_2d=True)
    return audio, rate


def encode_mp3(audio: np.ndarray, rate: int, bitrate: int = 192_000) -> bytes:
    """An MP3 of `audio`, for listening pages and for sending a clip to another device."""
    stereo = to_stereo(audio)
    buffer = io.BytesIO()
    with av.open(buffer, "w", format="mp3") as container:
        stream = container.add_stream("libmp3lame", rate=rate)
        stream.bit_rate = bitrate
        stream.layout = "stereo"
        frame = av.AudioFrame.from_ndarray(
            np.ascontiguousarray(stereo.T, dtype=np.float32), format="fltp", layout="stereo")
        frame.sample_rate = rate
        for packet in stream.encode(frame):
            container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)
    return buffer.getvalue()


def db(value: float) -> float:
    """A linear amplitude ratio in decibels; silence is reported as -200 rather than minus infinity."""
    return 20.0 * float(np.log10(max(value, 1e-10)))


def rms(audio: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(audio, dtype=np.float64)))) if audio.size else 0.0
