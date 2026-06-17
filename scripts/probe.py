#!/usr/bin/env python3
"""
probe.py — EXPERIMENTAL local analysis of Handy takes, beyond fluency.

A "try-it-and-decide" probe. Runs three extra, fully-offline analyses so we can
see what each is actually worth:

  1. DISFLUENCY typing  — repetitions / restarts / repair markers (from transcript)
  2. PROSODY            — pitch range, monotone-ness, voicing (parselmouth/Praat)
  3. PRONUNCIATION      — phone recognition + German→English target-sound flags
                          (Allosaurus; only runs if installed)

Run with the workspace venv:
  scripts/.venv/bin/python scripts/probe.py --ids 805,806,807,808
  scripts/.venv/bin/python scripts/probe.py --since 801 --json

Nothing here talks to a remote service.
"""
import argparse, json, os, re, sqlite3, sys

HANDY = os.path.expanduser("~/Library/Application Support/com.pais.handy")
DB = os.path.join(HANDY, "history.db")
RECDIR = os.path.join(HANDY, "recordings")

REPAIR_MARKERS = [
    "or rather", "i mean", "what i mean", "let me", "sorry", "actually",
    "no wait", "hang on", "let me put", "to be clear", "let me back up",
]

# Classic German→English pronunciation transfers, keyed to the English phones
# (IPA-ish, as Allosaurus emits) that signal them.
GER_TARGETS = {
    "θ / ð (th)": ["θ", "ð"],          # often → s/z/t/d
    "w vs v":     ["w", "v"],          # often swapped
    "ŋ (-ng)":    ["ŋ"],               # often → ŋk
    "æ (cat)":    ["æ"],               # often → ɛ
    "r (English)": ["ɹ", "r"],
}


def tokens(text):
    return re.findall(r"[a-z']+", text.lower())


def disfluency(text):
    toks = tokens(text)
    repeats = [toks[i] for i in range(len(toks) - 1) if toks[i] == toks[i + 1]]
    low = text.lower()
    markers = {m: low.count(m) for m in REPAIR_MARKERS if low.count(m)}
    return {
        "immediate_repeats": len(repeats),
        "repeated_words": repeats,
        "repair_markers": markers,
        "n_repair_markers": sum(markers.values()),
    }


def prosody(path):
    try:
        import parselmouth, numpy as np
    except Exception as e:
        return {"prosody": False, "err": str(e)}
    snd = parselmouth.Sound(path)
    pitch = snd.to_pitch()
    f0 = pitch.selected_array["frequency"]
    voiced = f0[f0 > 0]
    if voiced.size < 5:
        return {"prosody": True, "note": "too little voiced audio"}
    p10, p90 = np.percentile(voiced, [10, 90])
    range_st = float(12 * np.log2(p90 / p10)) if p10 > 0 else 0.0
    inten = snd.to_intensity()
    iv = inten.values[inten.values > 0]
    return {
        "prosody": True,
        "mean_f0_hz": round(float(np.median(voiced)), 1),
        "pitch_range_semitones": round(range_st, 1),
        "pct_voiced": round(float(voiced.size / f0.size), 2),
        "intensity_sd_db": round(float(np.std(iv)), 1) if iv.size else None,
        "monotone_flag": range_st < 6.0,   # rough: natural expressive speech ~8-14 st
    }


def pronunciation(path):
    try:
        from allosaurus.app import read_recognizer
    except Exception as e:
        return {"pron": False, "err": "allosaurus not installed yet"}
    try:
        model = read_recognizer()
        phones = model.recognize(path).split()
    except Exception as e:
        return {"pron": False, "err": str(e)}
    present = {}
    for label, ps in GER_TARGETS.items():
        present[label] = sum(phones.count(p) for p in ps)
    return {
        "pron": True,
        "n_phones": len(phones),
        "phone_sample": " ".join(phones[:40]) + ("…" if len(phones) > 40 else ""),
        "ger_target_phones_found": present,
    }


def fetch(args):
    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
    if args.ids:
        ids = [int(x) for x in args.ids.split(",")]
        rows = con.execute(
            f"SELECT id,timestamp,file_name,transcription_text FROM transcription_history "
            f"WHERE id IN ({','.join('?'*len(ids))}) ORDER BY id", ids).fetchall()
    elif args.since is not None:
        rows = con.execute(
            "SELECT id,timestamp,file_name,transcription_text FROM transcription_history "
            "WHERE id > ? ORDER BY id", (args.since,)).fetchall()
    else:
        rows = list(reversed(con.execute(
            "SELECT id,timestamp,file_name,transcription_text FROM transcription_history "
            "ORDER BY id DESC LIMIT ?", (args.last,)).fetchall()))
    con.close(); return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=int); ap.add_argument("--ids")
    ap.add_argument("--last", type=int, default=5)
    ap.add_argument("--no-pron", action="store_true", help="skip pronunciation")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if not os.path.exists(DB):
        sys.exit(f"no db at {DB}")

    out = []
    for r in fetch(args):
        wav = os.path.join(RECDIR, r["file_name"])
        rec = {"id": r["id"], "text": r["transcription_text"],
               "disfluency": disfluency(r["transcription_text"] or "")}
        if os.path.exists(wav):
            rec["prosody"] = prosody(wav)
            rec["pronunciation"] = ({"pron": False, "err": "skipped"}
                                    if args.no_pron else pronunciation(wav))
        out.append(rec)

    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False)); return

    for x in out:
        d = x["disfluency"]; p = x.get("prosody", {}); pr = x.get("pronunciation", {})
        print("─" * 64)
        print(f"#{x['id']}")
        print(f"  DISFLUENCY: {d['immediate_repeats']} word-repeats "
              f"{d['repeated_words'] or ''}; {d['n_repair_markers']} repair markers "
              f"{d['repair_markers'] or ''}")
        if p.get("prosody"):
            mono = "  ⚠ flat/monotone" if p.get("monotone_flag") else ""
            print(f"  PROSODY: median pitch {p.get('mean_f0_hz')}Hz, "
                  f"range {p.get('pitch_range_semitones')} semitones{mono}; "
                  f"voiced {int(p.get('pct_voiced',0)*100)}%")
        if pr.get("pron"):
            print(f"  PRONUNCIATION: {pr['n_phones']} phones; "
                  f"German-target sounds {pr['ger_target_phones_found']}")
            print(f"    phones: {pr['phone_sample']}")
        elif pr:
            print(f"  PRONUNCIATION: [{pr.get('err','n/a')}]")
    print("─" * 64)


if __name__ == "__main__":
    main()
