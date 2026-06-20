---
description: Grade the newest ungraded lesson submission (audio + written) with flow-first feedback
---

Grade the latest lesson submission. Follow this exactly — it is the same workflow as
"grade the latest submission" in CLAUDE.md, just triggered by `/grade`.

## Steps

1. **Find the submission.** Read the newest file in `submissions/` (NOT
   `submissions/graded/`). If there are several ungraded files, grade the newest;
   mention the others exist. If `submissions/` has no ungraded `*.json`, say so and stop.

2. **Analyze the audio.** Find the last-seen take id in `NOTES.md` and run
   `scripts/analyze.sh --since <id>` to sweep in this submission's takes *and* any
   ambient dictation since. (Fresh workspace / no id → `scripts/analyze.sh --last 10`.)
   - **Trust the audio metrics (pauses, phonation, duration) over the transcript.**
     Whisper-family ASR hallucinates repeated text over silence; a physically
     implausible rate (e.g. far above a human speaking rate in the target's counting
     unit) means a transcription artifact, not a finding — say so, don't grade it as
     real speech. Defer to the learner's lived experience over the transcript.

3. **Grade against the rubric.** Open `lessons/<lesson>.rubric.json` and compare each
   answer to its `qid`. Honor the rubric's `focus`/`criteria`.
   - **Flow over correctness.** Lead with what flowed (unbroken-run length, fewer/
     shorter silent pauses, filler use, words/morae per the target's counting unit). Do
     NOT headline error counts.
   - Be encouraging but **honest** — name real caveats plainly; never flatter. The
     learner is fragile about "still can't," so ground every win in a concrete metric
     or quote, and reframe deficit self-talk against the data.
   - Compare to the previous session's numbers to show trend.

4. **Capture insight.** If a genuinely new pattern emerges, add/update a
   `learning-records/000N-*.md`. Drain at most one item from any running fix-list in
   `NOTES.md` if the submission included a review round.

5. **File it.** Move the graded file to `submissions/graded/`. Update the **last-seen
   take id** in `NOTES.md` to the newest take you analyzed, and refresh the
   "RESUME HERE" block (what's done, what's next).

6. **Propose the next lesson** in one or two lines, tied to the mission and the zone
   of proximal development — then offer to build it.

Keep the tone warm and specific. If the target language uses a script the learner is
still acquiring, add the appropriate reading aid (e.g. furigana on kanji) in anything
you show.
