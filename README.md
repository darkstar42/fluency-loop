# AI Language Fluency Loop

An AI speaking coach that runs in [Claude Code](https://claude.com/claude-code),
for **any language you're learning**. It interviews you about *why* you want to
speak the language, then builds short, beautiful, printable lessons grounded in
that goal — and measures your real spontaneous speech with a fully offline audio
analyzer. Speak → measure → lesson → repeat: the fluency loop.

This is a **blank starter you make your own**: on GitHub, click **Use this
template** to create your own private copy (or clone it), run the onboarding, pick
your language, and your first session builds everything from your own mission. No
lessons or learner data ship with it.

---

## Why this exists

You can understand a language well — read it, follow a podcast, get the gist of a
fast conversation — and still freeze the moment it's your turn to *speak*. Under
real-time pressure the sentence you meant to say falls apart: you hesitate,
restart, reach for your native-language phrasing. Lessons help (conversation
practice on something like [italki](https://www.italki.com) is invaluable), but
they happen once or twice a week, and most of the feedback is gone the moment it's
spoken.

This project came out of wanting something to close that gap: a coach that listens
to the speech you *actually* produce — not only in drills, but in the everyday
dictation you do anyway — and gives objective, low-stakes feedback on how you're
really doing. Are your sentences getting longer? Fewer freezes and restarts? Is a
sound starting to drift? The point is to turn the time *between* lessons into
practice too, and to make producing speech feel less like a test. It's built to
sit **alongside** real conversation practice, not replace it.

## How it works

You practice by **speaking**, not typing. The teacher gives you a prompt; you
speak your answer (one take, no editing) into a speech-to-text app called
**[Handy](https://github.com/cjpais/Handy)**. The teacher then reads your real
transcripts *and* analyzes the audio — speech rate, pauses, length of unbroken
runs (and pronunciation, for English) — and turns the patterns into your next
lesson. Progress is tracked as **flow**, not error count, so it stays low-stress.

Crucially, this isn't limited to deliberate practice. If you use Handy as your
everyday speech-to-text — dictating messages, notes, prompts, work emails — then
**every one of those takes is real spontaneous speech**, and the analyzer can
mine all of it, not just prompted exercises. That ambient daily usage is often
the truest signal of how you actually speak under no pressure to "perform." It's
also why you raise Handy's history limit (below): so days of real interactions
accumulate into a corpus the teacher can learn from, instead of just your last
few recordings.

Everything is local: lessons are HTML files in `lessons/`, your mission and notes
are markdown at the repo root, and the analyzer never sends audio anywhere.

## Languages

| Language | Fluency metrics | Pronunciation feedback |
|---|---|---|
| **English** | ✅ words | ✅ th, w/v, ŋ, æ, final-devoicing (assumes a German L1) |
| **Japanese** | ✅ morae | ✅ 長音 long vowels, ら行 flap, ふ /ɸ/, 促音 geminate, **pitch-accent** (vs. UniDic) |
| **Any other** (`generic`) | ✅ whitespace words | — fluency only |

**Fluency works for every language** — the audio metrics (pauses, phonation,
length of runs) are language-neutral; only the counting unit changes. Adding a
new language is a small adapter in [`scripts/lang.py`](scripts/lang.py).
**Pronunciation** ships for English (← German) and Japanese; each is a module that
compares expected phones to what Allosaurus actually heard and flags the transfer
errors that matter for that language. Add a new one by modeling it on these.

## Quick start

0. **Get your own copy.** On GitHub, click **Use this template → Create a new
   repository** (make it **private** — your lessons and notes will live in it).
   Then clone your copy locally.
1. **Open this folder in Claude Code.**
2. **Run the teacher:**
   ```
   /teach
   ```
   On a fresh clone it first asks which language you want to speak and your native
   language (saving them to `config.json`), then — since `MISSION.md` is empty —
   interviews you about your goal and writes it. From there, follow along: it
   builds your first lesson and opens it in your browser.

That's all you need to begin lessons. Set up the analyzer below when you're ready
to practice with spoken feedback.

## Setting up the speech analyzer (optional but recommended)

The analyzer reads spoken takes recorded by Handy and reports the metrics that
actually predict perceived fluency.

**Prerequisites (macOS):**
- [Handy](https://github.com/cjpais/Handy) — the speech-to-text app. It stores a
  history database and `.wav` recordings under
  `~/Library/Application Support/com.pais.handy/`, which the scripts read.
  - **Raise the history limit first.** Handy keeps only the **last 5** takes by
    default, so the analyzer would never see more than your 5 most recent
    recordings. In Handy's settings, increase the history size to something large
    (1000 works well) so your everyday dictation *and* practice takes accumulate
    over days — giving the teacher a real corpus of your spontaneous speech to
    analyze and compare across, not just a handful of recent clips.
  - Handy holds takes in **every** language you dictate; the analyzer filters to
    your `config.json` target language, so your other-language dictation is left
    out of the metrics automatically.
- `ffmpeg` / `ffprobe` — `brew install ffmpeg`
- Python 3.12

**One-time install:**
```bash
scripts/setup.sh          # creates scripts/.venv and installs dependencies
```
The first run of the pronunciation tools downloads the Allosaurus model once,
then everything works offline.

**Run it** (the teacher does this for you each session, but you can too):
```bash
scripts/analyze.sh --last 3            # the 3 most recent takes
scripts/analyze.sh --since 120         # everything newer than take id 120
scripts/analyze.sh --ids 121,122,123   # specific takes
```
`analyze.sh` reads your language from `config.json`. Override per run with
`LANG_CODE=ja scripts/analyze.sh ...`, or call a script directly with `--lang`.

### What each script reports
| Script | What it gives you |
|---|---|
| `fluency.py` | units (words/morae), fillers, duration, **phonation ratio**, **speech rate**, pause count/length, **mean length of run** — plus a flow-trend table across takes. Works for any language. |
| `probe.py` | disfluency typing, **prosody** (pitch range / monotone via Praat), raw phone recognition. *English module* (prosody is language-neutral and a candidate to generalize). |
| `pron_align.py` | expected (CMUdict) vs. actual (Allosaurus) phones aligned → **L1-transfer flags**. *English-from-German module.* |
| `pron_align_ja.py` | expected (fugashi+UniDic → kana→IPA) vs. actual (Allosaurus, timestamped) → **Japanese tells**: long vowels, ら-row flap, ふ, geminates, and **pitch-accent** (UniDic downstep vs. the measured contour, mapped to morae by the timestamps). |
| `analyze.sh` | the standing per-session command — runs fluency for your language, plus the matching pronunciation module (English or Japanese). |

### Adding a language or pronunciation module
- **New fluency language:** add an adapter to `scripts/lang.py` — a unit counter,
  a filler list, and a script-detection rule. That's the whole job; the audio
  pipeline is shared. Until then, `generic` gives whitespace-word fluency.
- **New pronunciation pair:** the English scripts (`probe.py`, `pron_align.py`)
  are the reference. Their transfer flags assume German→English (`GER_TARGETS`);
  model a new module on them for another target language or native L1.

## Interactive lessons (submit & grade)

Lessons aren't just to read — you can **submit** them and get evaluated. A tiny
local server (stdlib Python, no venv) serves the lesson and captures your answers:

```bash
python3 scripts/serve.py --open lessons/0001-your-lesson.html
```

Do the lesson in your browser, hit **Submit**, and your answers are saved to
`submissions/`. Then back in Claude Code say *"grade the latest submission"* — the
teacher evaluates your answers against the lesson's rubric, with full context
(your mission, your past takes, your learning records), gives feedback, and
updates your records. Because you dictate answers with Handy, one submitted lesson
gives you **both** a graded written answer *and* fluency metrics from the audio.

The server is localhost-only and never grades or sends anything anywhere — it's
just the bridge that lets a browser page save your answers to disk.

## What's in here

```
config.json         Your target + native language (created during onboarding)
config.example.json Template for the above
MISSION.md          Why you're learning — the compass for every lesson (start empty)
RESOURCES.md        Trusted sources the teacher curates (start empty)
NOTES.md            Teacher's scratchpad + where to resume (start empty)
learning-records/   Decision-grade insights about your progress (ADR-style)
lessons/            Your lessons — self-contained printable HTML (+ *.rubric.json)
submissions/        Answers you submit from a lesson (graded ones move to graded/)
reference/          Cheat-sheets distilled from lessons
scripts/            The offline analyzer (lang.py = language adapters), serve.py + setup
.claude/skills/teach/   The teaching method (the /teach skill), bundled in
```

## Credits & license

This project is released under the [MIT License](LICENSE).

The `/teach` skill bundled in `.claude/skills/teach/` is adapted from
**[mattpocock/skills](https://github.com/mattpocock/skills)** by Matt Pocock, also
MIT licensed. The teaching workspace around it — the offline speech analyzer in
`scripts/`, the templates, and these docs — is original to this repository.

## Privacy

**Your clone is your own private workspace.** As you use it, your mission, notes,
lessons, and learning records are written into the repo — committing them is fine
and lets you track your progress over time. Just don't push that personal content
to a **public or shared** repo: keep your own copy private (e.g.
`gh repo create my-fluency --private`). The analyzer reads Handy's local database
and audio on your machine and sends nothing to any server.
