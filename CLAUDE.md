# Teaching workspace — agent guide

This repository is a **teaching workspace** for improving spoken fluency in *any*
language the user is learning. The teaching method lives in the bundled `/teach`
skill (`.claude/skills/teach/`); the speech analyzer in `scripts/` adapts to the
chosen language.

## First run

When a session starts, check `MISSION.md`. If it still contains the
"_Not yet populated_" placeholder, the user is new here. Tell them to run:

```
/teach
```

`/teach` cannot be triggered automatically (it's user-invoked by design), so the
first move is to point the user at it.

### Onboarding: establish the language first

As part of that first `/teach` session, before building any lessons, find out:

1. **Which language they want to learn to speak** (the target).
2. **Their native language(s)** — this drives which pronunciation module applies.

Then write `config.json` at the repo root (copy `config.example.json`):

```json
{ "target_language": "en", "native_language": "de" }
```

Use `en` or `ja` for the full fluency adapters (words / morae); use `generic` for
any other language (whitespace-word fluency still works). The analyzer reads this
file. Then proceed with the mission interview and lessons as described in
`.claude/skills/teach/SKILL.md`, grounding everything in the chosen language.

## Start of every session (do this automatically)

A new session has no memory of the last one. So at the **start of every session**,
before anything else:

1. Read `MISSION.md`, the `learning-records/`, and `NOTES.md` (especially the
   "RESUME HERE" block).
2. Find the **last-seen take id** recorded in `NOTES.md`, then run
   `scripts/analyze.sh --since <last-seen-id>`. It reads the target language from
   `config.json` and analyzes only takes in that language (skipping the user's
   other-language dictation in the shared Handy history). This sweeps in
   *everything* they dictated in the target language since you last looked —
   including everyday usage between lessons, not just prompted practice.
3. Use your judgment on the results: surface what's actionable, keep it
   encouraging, don't dump raw metrics. Turn patterns into the next lesson.
4. **Update the last-seen id** in `NOTES.md` to the newest take you analyzed, so
   the next session resumes cleanly.

This watermark is what makes between-lesson usage get analyzed automatically. If
`NOTES.md` has no last-seen id yet (fresh workspace), analyze the most recent
takes (`scripts/analyze.sh --last 10`) and record the highest id you saw.

5. Check `submissions/` for any ungraded lesson submissions and grade them (see
   "Interactive lessons" below) before deciding what to teach next.

## The practice loop

1. You give a speaking prompt.
2. The user speaks the answer into the **Handy** speech-to-text app (one take,
   no editing — the natural hesitations are the signal).
3. You read the new takes from Handy's database and run the analyzer, then give
   targeted, encouraging feedback. Track flow (speed, pausing, length of unbroken
   runs), not error count.

**Not just prompted practice.** Handy's history also holds the user's everyday
dictation — messages, notes, work emails, AI prompts. That ambient usage is real
spontaneous speech and is often the truest signal of how they speak under no
pressure, so analyze *all* new takes in the target language, not only answers to
your prompts. When it matters, distinguish deliberate practice rounds (e.g.
same-topic monologue repetitions) from general dictation — but mine both for
patterns to teach from.

## Interactive lessons: submit & grade

Lessons can be *submitted*, not just read. `scripts/serve.py` is a tiny local
server (stdlib only — no venv) that serves the repo and captures answers:

```
python3 scripts/serve.py --open lessons/0001-x.html
```

The user does the lesson in the browser, hits **Submit**, and their answers land
in `submissions/<lesson>__<timestamp>.json`. The server never grades — **you do**,
back here in Claude Code, with full context.

**When you create a lesson, make it submittable.** Mark each answer field with
`data-qid` (and `data-prompt`), set `data-lesson` on `<html>`, and embed this
block once (it no-ops when opened from `file://`, so the lesson still prints):

```html
<button id="submitLesson">Submit answers</button>
<p id="submitStatus"></p>
<script>
(function(){var b=document.getElementById('submitLesson'),s=document.getElementById('submitStatus');
if(location.protocol==='file:'){s.textContent='Open via scripts/serve.py to submit.';b.disabled=true;return;}
b.addEventListener('click',async function(){
 var ans=[].map.call(document.querySelectorAll('[data-qid]'),function(e){
  return{id:e.getAttribute('data-qid'),prompt:e.getAttribute('data-prompt')||'',answer:(e.value!==undefined?e.value:e.textContent).trim()};});
 b.disabled=true;s.textContent='Submitting…';
 try{var r=await fetch('/submit',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({lesson:document.documentElement.getAttribute('data-lesson')||document.title,answers:ans})});
  var j=await r.json();s.textContent=j.ok?'Submitted ✓ — switch to Claude Code and say "grade the latest submission".':'Submit failed.';
 }catch(e){s.textContent='Submit failed: '+e;b.disabled=false;}});})();
</script>
```

**Also emit a rubric** alongside each lesson — `lessons/<id>.rubric.json` — keyed
by the same `qid`s, with the expected answer / acceptance criteria per question.
Grade against it so feedback is grounded, not vibes:

```json
{ "lesson": "0001-x", "items": [
  { "qid": "q1", "expected": "…", "accept": ["…"], "criteria": "what a good answer shows" } ] }
```

**Grading flow.** When the user asks to grade (or during the session-start sweep),
read the newest ungraded file(s) in `submissions/`, compare each answer to the
rubric, give targeted encouraging feedback, update `learning-records/` where a
real insight emerges, then move the file to `submissions/graded/`. The dictation
boxes still feed Handy, so a submitted lesson gives you BOTH the written answers
(graded vs. rubric) and the audio (fluency metrics) from one action.

## The analyzer (`scripts/`)

Run the whole offline suite on new takes:

```
scripts/analyze.sh --since <last-seen-id>     # fluency (+ pronunciation if target is English)
scripts/analyze.sh --ids 805,806,807
```

It reads Handy's `history.db` and the matching `.wav` recordings from
`~/Library/Application Support/com.pais.handy/` (macOS), and picks the language
from `config.json`. See `README.md` for one-time setup (Python venv + ffmpeg) and
what each script reports.

> If only ~5 takes are ever available, the user likely hasn't raised Handy's
> history limit (default 5). Point them to the README setup step to increase it.

**Fluency** (`fluency.py`) works for every language — the audio metrics are
language-neutral and only the counting unit changes (words / morae / …, via
`scripts/lang.py`). **Pronunciation** ships per language and `analyze.sh` picks
the right one from `config.json`:
- `target=en` → `probe.py` + `pron_align.py` (English; transfer flags assume a
  German L1, `GER_TARGETS`).
- `target=ja` → `pron_align_ja.py` (Japanese: 長音 long vowels, ら-row flap, ふ /ɸ/,
  促音 geminates, and **pitch-accent** — the word's UniDic downstep vs. where the
  pitch actually dropped, with Allosaurus timestamps mapping the contour to morae.
  Directional: accent in connected speech has phrasing effects).
- other → fluency only.

Both pronunciation modules compare expected phones (CMUdict for English, a
kana→IPA rule table for Japanese) against what Allosaurus actually heard. Add a new
language by writing an adapter in `lang.py` and, optionally, a pronunciation module
modeled on these. All dictionaries/models download into the venv on first use —
none are committed.

## Conventions

- Keep `MISSION.md`, `RESOURCES.md`, `NOTES.md`, `learning-records/`, `lessons/`,
  and `reference/` updated per the format docs in `.claude/skills/teach/`.
- Lessons are self-contained, beautiful, printable HTML in `lessons/`, made
  submittable (the submit block + `data-qid` fields) with a `*.rubric.json` beside them.
- Numbered files (`learning-records/`, `lessons/`) increment: `0001-`, `0002-`, …
