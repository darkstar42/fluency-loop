# Teaching workspace — agent guide

This repository is a **teaching workspace** for improving spoken English. The
teaching method lives in the bundled `/teach` skill (`.claude/skills/teach/`).

## First run

When a session starts, check `MISSION.md`. If it still contains the
"_Not yet populated_" placeholder, the user is new here. Tell them to run:

```
/teach
```

`/teach` cannot be triggered automatically (it's user-invoked by design), so the
first move is to point the user at it. Once invoked, the skill will interview the
user about *why* they want to improve their spoken English, write `MISSION.md`,
and proceed exactly as described in `.claude/skills/teach/SKILL.md`.

## Start of every session (do this automatically)

A new session has no memory of the last one. So at the **start of every session**,
before anything else:

1. Read `MISSION.md`, the `learning-records/`, and `NOTES.md` (especially the
   "RESUME HERE" block).
2. Find the **last-seen take id** recorded in `NOTES.md`, then run
   `scripts/analyze.sh --since <last-seen-id>`. This sweeps in *everything* the
   user dictated into Handy since you last looked — including all the everyday
   dictation that happened between lessons, not just prompted practice.
3. Use your judgment on the results: surface what's actionable, keep it
   encouraging, don't dump raw metrics. Turn patterns into the next lesson.
4. **Update the last-seen id** in `NOTES.md` to the newest take you analyzed, so
   the next session resumes cleanly.

This watermark is what makes between-lesson usage get analyzed automatically. If
`NOTES.md` has no last-seen id yet (fresh workspace), analyze the most recent
takes (`scripts/analyze.sh --last 10`) and record the highest id you saw.

## The practice loop

1. You give a speaking prompt.
2. The user speaks the answer into the **Handy** speech-to-text app (one take,
   no editing — the natural hesitations are the signal).
3. You read the new takes from Handy's database and run the analyzer, then give
   targeted, encouraging feedback. Track flow (speed, pausing, length of unbroken
   runs), not error count.

**Not just prompted practice.** Handy's history also holds the user's everyday
dictation — messages, notes, work emails, AI prompts. That ambient usage is real
spontaneous English and is often the truest signal of how they speak under no
pressure, so analyze *all* new takes, not only answers to your prompts. When it
matters, distinguish deliberate practice rounds (e.g. same-topic monologue
repetitions) from general dictation — but mine both for patterns to teach from.

## The analyzer (`scripts/`)

Run the whole offline suite on new takes:

```
scripts/analyze.sh --since <last-seen-id>     # fluency + prosody + pronunciation
scripts/analyze.sh --ids 805,806,807
```

It reads Handy's `history.db` and the matching `.wav` recordings from
`~/Library/Application Support/com.pais.handy/` (macOS). See `README.md` for
one-time setup (Python venv + ffmpeg) and what each script reports.

> If only ~5 takes are ever available, the user likely hasn't raised Handy's
> history limit (default 5). Point them to the README setup step to increase it.

The pronunciation alignment (`pron_align.py`) flags **German→English** transfer
patterns by default. If the learner's first language isn't German, adjust the
`GER_TARGETS` map in `scripts/probe.py` / `pron_align.py` to their L1.

## Conventions

- Keep `MISSION.md`, `RESOURCES.md`, `NOTES.md`, `learning-records/`, `lessons/`,
  and `reference/` updated per the format docs in `.claude/skills/teach/`.
- Lessons are self-contained, beautiful, printable HTML in `lessons/`.
- Numbered files (`learning-records/`, `lessons/`) increment: `0001-`, `0002-`, …
