"""Experiment 0: can the key generate music at all, and in which format?

Reads the account's plan (free), then asks for two clips of three seconds: uncompressed at 48 kHz,
and if that is refused, uncompressed at 44.1 kHz. From the number of bytes that come back it works
out whether the audio is mono or stereo. Cost: 0.05 minutes per clip.
"""
import asyncio

from common import describe, gateway, save, write_report
from freerock.audio import decode_bytes, pcm16_to_float
from freerock.eleven import ElevenError

PROMPT = ("Instrumental hard rock riff: crunchy overdriven rhythm guitars, driving eighth-note bass, "
          "plain hard-hitting drums. 120 BPM, A minor.")
SECONDS = 3


async def main() -> None:
    gate = gateway()
    report: dict = {"clips": []}
    try:
        account = await gate.subscription()
        report["account"] = {
            "tier": account.get("tier"), "status": account.get("status"),
            "credits_used": account.get("character_count"), "credits_limit": account.get("character_limit"),
            "resets_unix": account.get("next_character_count_reset_unix"),
        }
        print("account:", report["account"])

        chosen = None
        for fmt, rate in (("pcm_48000", 48000), ("pcm_44100", 44100), ("mp3_48000_192", 48000)):
            try:
                data, delivery = await gate.music(
                    purpose="experiment 0: format", prompt=PROMPT, music_length_ms=SECONDS * 1000,
                    force_instrumental=True, output_format=fmt)
            except ElevenError as error:
                print("%s refused: %s" % (fmt, error))
                report["clips"].append({"format": fmt, "refused": str(error), "status": error.status})
                continue
            entry = {"format": fmt, "bytes": len(data), "first_audio_s": delivery.first_audio_s,
                     "total_s": delivery.total_s, "headers": delivery.headers}
            if fmt.startswith("pcm"):
                # 16-bit samples: bytes / 2 / rate is seconds times the number of channels.
                channel_seconds = len(data) / 2 / rate
                channels = round(channel_seconds / SECONDS)
                entry.update(channel_seconds=round(channel_seconds, 3), channels=channels)
                if channels not in (1, 2):
                    raise RuntimeError("%s: %d bytes does not look like mono or stereo for %d s"
                                       % (fmt, len(data), SECONDS))
                usable = len(data) - len(data) % (2 * channels)
                audio = pcm16_to_float(data[:usable], channels)
            else:
                audio, rate = decode_bytes(data)
                entry.update(channels=audio.shape[1])
            entry["rate"] = rate
            entry["measured"] = describe(audio, rate)
            entry["files"] = save("s0_" + fmt, audio, rate)
            report["clips"].append(entry)
            print(fmt, "->", {k: entry[k] for k in ("bytes", "channels", "rate", "first_audio_s", "total_s")})
            if entry["channels"] == 2 and chosen is None:
                chosen = {"format": fmt, "rate": rate, "channels": 2}
                break  # stereo and accepted: this is the format to use
        report["chosen"] = chosen
        if chosen is None:
            raise RuntimeError("No format gave stereo audio; see the report for what each one returned")
    finally:
        print("report:", write_report("s0", report))
        await gate.aclose()


if __name__ == "__main__":
    asyncio.run(main())
