#!/usr/bin/env python3
"""
fluency.py — pull Handy speech-to-text takes and report spoken-fluency metrics.

Combines the transcript (from history.db) with audio analysis of the matching
.wav recording (via ffprobe + ffmpeg silencedetect) to produce the metrics that
actually predict perceived fluency: speech rate + pausing (Bosker et al. 2013) —
NOT error counts.

Usage:
  python3 scripts/fluency.py                 # the 5 most recent takes
  python3 scripts/fluency.py --since 801     # every take with id > 801
  python3 scripts/fluency.py --ids 805,806,807   # specific takes
  python3 scripts/fluency.py --last 3        # the 3 most recent
  python3 scripts/fluency.py --since 801 --json   # machine-readable

Tunables: --noise -32 (dB silence floor), --min-pause 0.3 (sec).
ffmpeg/ffprobe must be on PATH.
"""
import argparse, json, os, re, sqlite3, subprocess, sys

HANDY = os.path.expanduser("~/Library/Application Support/com.pais.handy")
DB = os.path.join(HANDY, "history.db")
RECDIR = os.path.join(HANDY, "recordings")

# Fillers that get transcribed as words (so visible in text). Silent pauses are
# measured from audio instead.
FILLERS = [
    r"\buh+\b", r"\bum+\b", r"\berm+\b", r"\bhmm+\b", r"\blike\b",
    r"\byou know\b", r"\bi mean\b", r"\bi don'?t know\b", r"\bsort of\b",
    r"\bkind of\b", r"\bbasically\b", r"\bwell\b", r"\byeah\b", r"\bso\b",
]


def ffprobe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return None


def detect_silences(path, noise_db, min_pause, duration):
    """Return list of (start, end) silent intervals."""
    res = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", path,
         "-af", f"silencedetect=noise={noise_db}dB:d={min_pause}", "-f", "null", "-"],
        capture_output=True, text=True)
    log = res.stderr
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", log)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", log)]
    intervals = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else (duration if duration else s)
        intervals.append((s, e))
    return intervals


def analyze_audio(path, words, noise_db, min_pause):
    duration = ffprobe_duration(path)
    if not duration:
        return {"audio": False}
    sil = detect_silences(path, noise_db, min_pause, duration)

    lead = sil[0][1] if sil and sil[0][0] <= 0.05 else 0.0           # silence before first word
    trail = duration - sil[-1][0] if sil and sil[-1][1] >= duration - 0.05 else 0.0
    internal = [iv for iv in sil
                if not (iv[0] <= 0.05) and not (iv[1] >= duration - 0.05)]
    n_pauses = len(internal)
    mid_pause_total = sum(e - s for s, e in internal)

    speech_span = max(duration - lead - trail, 1e-6)                 # first word → last word
    articulation_time = max(speech_span - mid_pause_total, 1e-6)     # actual phonation

    return {
        "audio": True,
        "duration_s": round(duration, 2),
        "lead_silence_s": round(lead, 2),
        "trail_silence_s": round(trail, 2),
        "speech_span_s": round(speech_span, 2),
        "articulation_time_s": round(articulation_time, 2),
        "phonation_ratio": round(articulation_time / speech_span, 2),
        "n_pauses": n_pauses,
        "pause_total_s": round(mid_pause_total, 2),
        "mean_pause_s": round(mid_pause_total / n_pauses, 2) if n_pauses else 0.0,
        "longest_pause_s": round(max((e - s for s, e in internal), default=0.0), 2),
        # words/min over the whole span (incl. pauses) vs. over phonation only
        "speech_rate_wpm": round(words / (speech_span / 60), 1),
        "articulation_rate_wpm": round(words / (articulation_time / 60), 1),
        # mean length of run: words spoken per uninterrupted stretch
        "mean_run_words": round(words / (n_pauses + 1), 1),
    }


def filler_count(text):
    low = text.lower()
    total = 0
    hits = {}
    for pat in FILLERS:
        c = len(re.findall(pat, low))
        if c:
            hits[pat.strip(r"\b").replace("'?", "'")] = c
            total += c
    return total, hits


def fetch_rows(args):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    q = "SELECT id, timestamp, file_name, transcription_text FROM transcription_history"
    if args.ids:
        ids = [int(x) for x in args.ids.split(",")]
        q += f" WHERE id IN ({','.join('?'*len(ids))}) ORDER BY id"
        rows = con.execute(q, ids).fetchall()
    elif args.since is not None:
        q += " WHERE id > ? ORDER BY id"
        rows = con.execute(q, (args.since,)).fetchall()
    else:
        q += " ORDER BY id DESC LIMIT ?"
        rows = list(reversed(con.execute(q, (args.last,)).fetchall()))
    con.close()
    return rows


def main():
    ap = argparse.ArgumentParser(description="Handy take fluency analyzer")
    ap.add_argument("--since", type=int, help="takes with id greater than this")
    ap.add_argument("--ids", help="comma-separated take ids")
    ap.add_argument("--last", type=int, default=5, help="N most recent (default 5)")
    ap.add_argument("--noise", type=float, default=-32, help="silence floor dB (default -32)")
    ap.add_argument("--min-pause", type=float, default=0.3, help="min pause sec (default 0.3)")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    if not os.path.exists(DB):
        sys.exit(f"history.db not found at {DB}")

    rows = fetch_rows(args)
    results = []
    for r in rows:
        text = r["transcription_text"] or ""
        words = len(text.split())
        wav = os.path.join(RECDIR, r["file_name"])
        audio = analyze_audio(wav, words, args.noise, args.min_pause) \
            if os.path.exists(wav) else {"audio": False}
        nfill, fhits = filler_count(text)
        results.append({
            "id": r["id"], "timestamp": r["timestamp"],
            "file": r["file_name"], "words": words,
            "fillers": nfill, "filler_breakdown": fhits,
            "text": text, **audio,
        })

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    for x in results:
        print("─" * 64)
        print(f"#{x['id']}  {x['words']} words   fillers: {x['fillers']}"
              + (f"  {x['filler_breakdown']}" if x["filler_breakdown"] else ""))
        if x.get("audio"):
            print(f"  duration {x['duration_s']}s  (lead {x['lead_silence_s']}s, "
                  f"trail {x['trail_silence_s']}s)   phonation {int(x['phonation_ratio']*100)}%")
            print(f"  speech rate {x['speech_rate_wpm']} wpm   "
                  f"articulation {x['articulation_rate_wpm']} wpm")
            print(f"  pauses {x['n_pauses']}  total {x['pause_total_s']}s  "
                  f"(mean {x['mean_pause_s']}s, longest {x['longest_pause_s']}s)")
            print(f"  mean length of run: {x['mean_run_words']} words / unbroken stretch")
        else:
            print("  [no audio recording found — text metrics only]")
        snippet = x["text"][:160] + ("…" if len(x["text"]) > 160 else "")
        print(f"  “{snippet}”")
    print("─" * 64)
    if len(results) > 1 and all(r.get("audio") for r in results):
        print("FLOW TREND (across takes — want rate ↑, pauses ↓, runs ↑):")
        for x in results:
            print(f"  #{x['id']}: {x['speech_rate_wpm']:>5} wpm | "
                  f"{x['n_pauses']:>2} pauses | {x['mean_run_words']:>4} words/run")


if __name__ == "__main__":
    main()
