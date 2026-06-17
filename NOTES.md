# Working Notes

> Scratchpad for your teacher: your stated preferences, what to remember between
> sessions, and where to resume. Empty until your first `/teach` session fills it in.

## ▶ NEXT SESSION — RESUME HERE
_Start here next time: what's done and what's open._

- **Last-seen Handy take id:** _none yet_ — the highest take id already analyzed.
  At session start, run `scripts/analyze.sh --since <this id>` to sweep in
  everything dictated since (including everyday usage between lessons), then bump
  this number to the newest take you looked at.

## About the learner
_Native language, level, relevant background, tools you use — captured as it comes up._

## Teaching preferences
_How you want to be taught: spoken practice vs. written drills, how hard to push, how bluntly to correct._

## The practice loop (core engine)
1. Teacher gives a speaking prompt.
2. You speak the answer into the **Handy** speech-to-text app (no editing — speak it as one take; natural hesitations are the signal we work on).
3. Teacher reads the new rows from Handy's `history.db` and runs the analyzer, then gives targeted feedback.

See the README for how the analyzer reads Handy's database and audio.
