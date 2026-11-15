"""Builds the listening page for the experiments: var/spikes/index.html.

It puts every clip next to what to listen for and the numbers that were measured, so the parts
only an ear can judge are easy to get through. Costs nothing; it only reads the reports.

    cd app && uv run --no-sync python ../tools/spikes/build_page.py
"""
import html
import time

from common import OUT, read_report
from freerock.ledger import Ledger, month_start
from freerock.settings import Settings

STYLE = """
:root { --bg:#f6f4ef; --card:#fffdf8; --ink:#22201c; --soft:#6b665d; --line:#ded8cb; --accent:#a4441c;
        --good:#2d6a3e; --bad:#a3301f; --chip:#ece7dc; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#17161a; --card:#211f25; --ink:#ece8e1; --soft:#a39d93; --line:#37343c; --accent:#f08a54;
          --good:#7fca92; --bad:#f08a7a; --chip:#2c2a31; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:16px/1.55 system-ui, sans-serif; }
main { max-width: 860px; margin: 0 auto; padding: 28px 16px 64px; }
h1 { font-size: 1.7rem; margin: 0 0 4px; } h2 { font-size: 1.2rem; margin: 36px 0 10px; }
p { margin: 8px 0; } .soft { color: var(--soft); }
.card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px 18px; margin:12px 0; }
.card h3 { margin:0 0 6px; font-size:1.02rem; }
audio { width:100%; margin:10px 0 4px; }
.ask { border-left:3px solid var(--accent); padding:2px 0 2px 12px; margin:10px 0 2px; }
table { border-collapse:collapse; width:100%; font-size:.9rem; margin:8px 0; }
th, td { text-align:left; padding:5px 8px; border-bottom:1px solid var(--line); vertical-align:top; }
th { color:var(--soft); font-weight:600; } td.n { font-variant-numeric: tabular-nums; white-space:nowrap; }
.scroll { overflow-x:auto; }
.chip { display:inline-block; background:var(--chip); border-radius:999px; padding:1px 10px; font-size:.82rem; margin:2px 4px 2px 0; }
.pass { color:var(--good); font-weight:600; } .fail { color:var(--bad); font-weight:600; }
ul.checks { list-style:none; padding:0; margin:8px 0; } ul.checks li { padding:2px 0; }
"""


def esc(value) -> str:
    return html.escape(str(value))


def clip(title: str, files: dict, what: str = "", ask: str = "") -> str:
    parts = ['<div class="card"><h3>%s</h3>' % esc(title)]
    if what:
        parts.append('<p class="soft">%s</p>' % esc(what))
    parts.append('<audio controls preload="none" src="%s"></audio>' % esc(files["mp3"]))
    if ask:
        parts.append('<p class="ask"><strong>Listen for:</strong> %s</p>' % esc(ask))
    parts.append("</div>")
    return "".join(parts)


def checks(passes: dict) -> str:
    rows = ['<li><span class="%s">%s</span> %s</li>' % (
        "pass" if ok else "fail", "Pass" if ok else "Fail", esc(line)) for line, ok in passes.items()]
    return '<ul class="checks">%s</ul>' % "".join(rows)


def main() -> None:
    s0, s1, s2, s3, s5 = (read_report(name) for name in ("s0", "s1", "s2", "s3", "s5"))
    ledger = Ledger(Settings().ledger_path)
    spent = ledger.minutes_since(month_start(time.time()))
    out = ['<!doctype html><html lang="en"><head><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width, initial-scale=1">'
           "<title>FreeRock experiments</title><style>%s</style></head><body><main>" % STYLE]
    out.append("<h1>FreeRock experiments</h1>")
    out.append('<p class="soft">Built %s. %.1f minutes of the monthly allowance used so far '
               "(about $%.2f). Everything here was measured; how it sounds is yours to judge.</p>"
               % (esc(time.strftime("%Y-%m-%d %H:%M")), spent, spent * 0.15))

    # --- the three clips that matter most -----------------------------------------------------
    demos = s2["demos"]
    out.append("<h2>Start here</h2>")
    out.append(clip("1. The whole first suite, as it came off the stream", s2["delivery"] and {"mp3": "s2_suite.mp3"},
                    "One request, 2 minutes 48. Arrival 0:00, Wander A 0:08, Wander B 0:40, Battle 1:12, "
                    "Ember 1:44, Depths 2:16.",
                    "Is this the sound? Is there enough rock in the Wander parts, or too much? "
                    "Does Battle hit hard enough, and do Ember and Depths feel different enough from Wander?"))
    out.append(clip("2. The bass line coming in", demos["bass_entrance"]["files"], demos["bass_entrance"]["what"],
                    "At 0:16 a fight starts. Does the bass and drums arriving under the same music work? "
                    "Does the first 16 seconds stand up on its own as calm zone music?"))
    out.append(clip("3. Walking into a cave", demos["cave"]["files"], demos["cave"]["what"],
                    "Does the change at 0:08 read as going indoors, and is the move to Depths at 0:12 natural?"))

    # --- layers ---------------------------------------------------------------------------------
    out.append("<h2>The three layers of Wander A</h2>")
    out.append('<p class="soft">Split on this machine in %s seconds. They add back up to the original exactly.</p>'
               % esc(s2["layers"]["seconds_to_split"]))
    for key, title, ask in (
            ("wander_a_bed", "Bed: everything except drums and bass", "This is what plays when nothing is happening. "
             "Any watery or hollow artefacts?"),
            ("wander_a_no_bass", "Bed and drums, bass muted", "Is the missing bass obvious, or does it sound like a mix choice?"),
            ("wander_a_bass", "Bass alone", "Is it a clean bass line?"),
            ("wander_a_drums", "Drums alone", "")):
        out.append(clip(title, demos[key]["files"], "", ask))

    out.append("<h2>Five minutes of moving between cells</h2>")
    walk = s2["cell_walk"]
    out.append(clip("Wander A and B, four bars at a time, in random order", walk["files"],
                    "%d cuts. Measured tempo %s, %d of %d beats off the grid."
                    % (walk["cells"] - 1, walk["measured_bpm"], walk["outliers"], walk["beats_checked"]),
                    "Do any of the cuts stumble or sound like an edit? Does it hold up as five minutes of music?"))

    # --- same band ------------------------------------------------------------------------------
    out.append("<h2>A second request for the same zone</h2>")
    out.append('<p class="soft">Later sets are separate requests. Each clip cuts between the first suite '
               "and the new riff every four bars.</p>")
    out.append(clip("Without a reference", s3["s3"]["splice"]["files"],
                    "Tone differs from the first suite by %s dB (two parts of the first suite differ by %s)."
                    % (s3["s3"]["tone_difference_db"], s3["s3"]["tone_difference_between_two_parts_of_the_core_suite_db"]),
                    "Same band, or two different records?"))
    if s3["s4"].get("accepted"):
        out.append(clip("Told to stay close to 30 seconds of the first suite", s3["s4"]["splice"]["files"],
                        "Tone differs by %s dB; tuning gap %s cents." % (
                            s3["s4"]["tone_difference_db"], s3["s4"]["tuning_gap_cents"]),
                        "Same band? This is how later sets would be made."))
    out.append(clip("The Boss part from the second request", {"mp3": "s3_unconditioned.mp3"},
                    "Boss starts at 0:32 (the first 32 seconds are the new Wander riff).",
                    "Is this what a boss fight should sound like?"))

    # --- kit --------------------------------------------------------------------------------------
    out.append("<h2>Solo parts and the kit</h2>")
    for name in ("bass", "drums"):
        solo = s5["s5_solos"][name]
        out.append(clip("Solo %s from the music endpoint" % name, solo["files"],
                        "Other layers are %s dB below it; tempo off by %s%%." % (
                            solo["loudest_other_layer_below_own_db"], solo["tempo"]["off_percent"])))
    fx = s5["s6_effects"]
    if "refused" not in fx["drone"]:
        out.append(clip("Drone from the sound-effects endpoint", fx["drone"]["files"],
                        "Asked for a drone on G. Its strongest note is %s, with G %s; %s cents from concert pitch."
                        % (fx["drone"]["strongest_note"],
                           "second" if fx["drone"]["rank_of_G"] == 2 else "at rank %d" % fx["drone"]["rank_of_G"],
                           fx["drone"]["tuning_cents"]),
                        "Does it sit under the suite as a G drone? It plays for the first seconds in a new zone."))
    if "refused" not in fx["hit"]:
        out.append(clip("Hit from the sound-effects endpoint", fx["hit"]["files"], "", "Usable for a boss pull?"))
    if "refused" not in fx["drum_loop"]:
        out.append(clip("Drum loop from the sound-effects endpoint", fx["drum_loop"]["files"],
                        "Exactly %s bars at %s BPM." % (fx["drum_loop"]["bars_at_120"], fx["drum_loop"]["tempo"]["measured_bpm"])))

    # --- numbers ----------------------------------------------------------------------------------
    out.append("<h2>The numbers</h2>")
    out.append('<div class="card"><h3>Speed</h3><table><tr><th>Request</th><th>First audio</th><th>All of it</th></tr>')
    clip0 = next(c for c in s0["clips"] if "refused" not in c)
    out.append('<tr><td>3 seconds</td><td class="n">%.1f s</td><td class="n">%.1f s</td></tr>' % (clip0["first_audio_s"], clip0["total_s"]))
    out.append('<tr><td>30 seconds, two parts</td><td class="n">%s s</td><td class="n">%s s</td></tr>' % (s1["first_audio_s"], s1["total_s"]))
    out.append('<tr><td>2 min 48, six parts</td><td class="n">%s s</td><td class="n">%s s</td></tr></table>' % (
        s2["delivery"]["first_audio_s"], s2["delivery"]["total_s"]))
    out.append('<p class="soft">Format: %s, stereo. Account: %s, %s of %s credits used when the experiments began.</p></div>' % (
        esc(s0["chosen"]["format"]), esc(s0["account"]["tier"]), esc(s0["account"]["credits_used"]), esc(s0["account"]["credits_limit"])))

    out.append('<div class="card"><h3>The first suite, part by part</h3><div class="scroll"><table><tr><th>Part</th><th>Tempo off</th>'
               "<th>Start to nearest beat</th><th>Heard as</th><th>Tuning</th><th>Loudness</th><th>Bass left in bed</th><th>Drum timing</th></tr>")
    for name, part in s2["parts"].items():
        out.append('<tr><td>%s</td><td class="n">%+.3f%%</td><td class="n">%+.1f ms</td><td>%s</td><td class="n">%+.1f cents</td>'
                   '<td class="n">%.1f LUFS</td><td class="n">%.1f dB</td><td class="n">%.1f ms</td></tr>' % (
                       esc(name), part["tempo"]["off_percent"], part["start_to_nearest_beat_ms"], esc(part["key"]["heard_as"]),
                       part["key"]["tuning_cents"], part["loudness_lufs"], part["bass_left_in_bed_db"], part["drums"]["jitter_ms"]))
    out.append("</table></div>%s<p class=\"soft\">%s Asked for 120 BPM in G Mixolydian; a key finder hears that as G major or E minor.</p></div>"
               % (checks(s2["passes"]), esc(s2["note_on_bass_check"])))

    out.append('<div class="card"><h3>Other checks</h3>%s%s%s</div>' % (checks(s1["passes"]), checks(s3["passes"]), checks(s5["passes"])))
    out.append("</main></body></html>")
    path = OUT / "index.html"
    path.write_text("".join(out), encoding="utf-8")
    print("listening page:", path)


if __name__ == "__main__":
    main()
