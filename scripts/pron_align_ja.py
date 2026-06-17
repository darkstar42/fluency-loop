#!/usr/bin/env python3
"""
pron_align_ja.py — Japanese pronunciation feedback, fully offline.

The Japanese sibling of pron_align.py. Same shape (expected vs. actual phones,
aligned, then flagged), but built for Japanese:

  1. EXPECTED phones  — the transcript's kana reading (pykakasi) → IPA via a
     rule-based table. Japanese orthography→sound is very regular, so this is
     more reliable than the English CMUdict path.
  2. ACTUAL phones    — from the .wav via Allosaurus, constrained to Japanese.
  3. ALIGN            — Needleman-Wunsch on a Japanese-tuned phone inventory.
  4. FLAG             — the learner tells that matter for Japanese:
        • 長音   long vowels shortened (おばあさん→おばさん)
        • ら行   flap /ɾ/ realized as English/German l or ɹ
        • ふ     /ɸ/ realized as labiodental f
        • 促音   geminate っ dropped
     plus prosody (pitch range / monotone). True pitch-ACCENT correctness needs
     an accent dictionary and is out of scope — we report the contour, not a grade.

DIRECTIONAL, not clinical: Allosaurus is imperfect — read rates/trends, not single
hits. Pronunciation is a secondary track behind fluency for most learners.

  scripts/.venv/bin/python scripts/pron_align_ja.py --ids 793
  scripts/.venv/bin/python scripts/pron_align_ja.py --since 800 --json
"""
import argparse, json, os, re, sqlite3, sys, unicodedata

import lang as L

HANDY = os.path.expanduser("~/Library/Application Support/com.pais.handy")
DB = os.path.join(HANDY, "history.db")
RECDIR = os.path.join(HANDY, "recordings")

VOWELS = set("aiueo")

# ── kana → normalized Japanese phones ──────────────────────────────────────
# Working inventory: k g s z ʃ ʒ t d ts tʃ dʒ n h ɸ b p m j r w  N(moraic ん)
# Q(geminate っ)  +  vowels a i u e o.  ら-row → 'r'; ふ → 'ɸ' (kept distinct
# from 'f' so a labiodental substitution shows up).
KANA = {
    "あ": ["a"], "い": ["i"], "う": ["u"], "え": ["e"], "お": ["o"],
    "か": ["k", "a"], "き": ["k", "i"], "く": ["k", "u"], "け": ["k", "e"], "こ": ["k", "o"],
    "が": ["g", "a"], "ぎ": ["g", "i"], "ぐ": ["g", "u"], "げ": ["g", "e"], "ご": ["g", "o"],
    "さ": ["s", "a"], "し": ["ʃ", "i"], "す": ["s", "u"], "せ": ["s", "e"], "そ": ["s", "o"],
    "ざ": ["z", "a"], "じ": ["dʒ", "i"], "ず": ["z", "u"], "ぜ": ["z", "e"], "ぞ": ["z", "o"],
    "た": ["t", "a"], "ち": ["tʃ", "i"], "つ": ["ts", "u"], "て": ["t", "e"], "と": ["t", "o"],
    "だ": ["d", "a"], "ぢ": ["dʒ", "i"], "づ": ["z", "u"], "で": ["d", "e"], "ど": ["d", "o"],
    "な": ["n", "a"], "に": ["n", "i"], "ぬ": ["n", "u"], "ね": ["n", "e"], "の": ["n", "o"],
    "は": ["h", "a"], "ひ": ["h", "i"], "ふ": ["ɸ", "u"], "へ": ["h", "e"], "ほ": ["h", "o"],
    "ば": ["b", "a"], "び": ["b", "i"], "ぶ": ["b", "u"], "べ": ["b", "e"], "ぼ": ["b", "o"],
    "ぱ": ["p", "a"], "ぴ": ["p", "i"], "ぷ": ["p", "u"], "ぺ": ["p", "e"], "ぽ": ["p", "o"],
    "ま": ["m", "a"], "み": ["m", "i"], "む": ["m", "u"], "め": ["m", "e"], "も": ["m", "o"],
    "や": ["j", "a"], "ゆ": ["j", "u"], "よ": ["j", "o"],
    "ら": ["r", "a"], "り": ["r", "i"], "る": ["r", "u"], "れ": ["r", "e"], "ろ": ["r", "o"],
    "わ": ["w", "a"], "ゐ": ["w", "i"], "ゑ": ["w", "e"], "を": ["o"],
    "ぁ": ["a"], "ぃ": ["i"], "ぅ": ["u"], "ぇ": ["e"], "ぉ": ["o"],
}
YOON = {  # consonant + small ゃゅょ (palatalization dropped — it's stripped on both sides)
    "きゃ": ["k", "a"], "きゅ": ["k", "u"], "きょ": ["k", "o"],
    "ぎゃ": ["g", "a"], "ぎゅ": ["g", "u"], "ぎょ": ["g", "o"],
    "しゃ": ["ʃ", "a"], "しゅ": ["ʃ", "u"], "しょ": ["ʃ", "o"],
    "じゃ": ["dʒ", "a"], "じゅ": ["dʒ", "u"], "じょ": ["dʒ", "o"],
    "ちゃ": ["tʃ", "a"], "ちゅ": ["tʃ", "u"], "ちょ": ["tʃ", "o"],
    "にゃ": ["n", "a"], "にゅ": ["n", "u"], "にょ": ["n", "o"],
    "ひゃ": ["h", "a"], "ひゅ": ["h", "u"], "ひょ": ["h", "o"],
    "びゃ": ["b", "a"], "びゅ": ["b", "u"], "びょ": ["b", "o"],
    "ぴゃ": ["p", "a"], "ぴゅ": ["p", "u"], "ぴょ": ["p", "o"],
    "みゃ": ["m", "a"], "みゅ": ["m", "u"], "みょ": ["m", "o"],
    "りゃ": ["r", "a"], "りゅ": ["r", "u"], "りょ": ["r", "o"],
}


def to_hira(text):
    import pykakasi
    return "".join(i["hira"] for i in pykakasi.kakasi().convert(text))


def expected_phones(text):
    """kana reading → list of {p, mora, vowel, role}. role ∈ rrow|fu|geminate|long2|''."""
    try:
        hira = to_hira(text)
    except Exception:
        return None
    raw = []  # (phone, source-kana)
    i = 0
    while i < len(hira):
        c = hira[i]
        pair = hira[i:i + 2]
        if len(pair) == 2 and pair in YOON:
            for p in YOON[pair]:
                raw.append((p, pair))
            i += 2
        elif c == "っ":
            raw.append(("Q", c)); i += 1
        elif c == "ー":
            if raw and raw[-1][0] in VOWELS:
                raw.append((raw[-1][0], c))     # lengthen previous vowel
            i += 1
        elif c == "ん":
            raw.append(("N", c)); i += 1
        elif c in KANA:
            for p in KANA[c]:
                raw.append((p, c))
            i += 1
        else:
            i += 1  # punctuation, latin, spaces — skip

    seq = []
    for idx, (p, mora) in enumerate(raw):
        vowel = p in VOWELS
        role = ""
        if p == "Q":
            role = "geminate"
        elif p == "ɸ":
            role = "fu"
        elif p == "r":
            role = "rrow"
        elif vowel and seq and seq[-1]["vowel"] and seq[-1]["p"] == p:
            role = "long2"                       # second half of a long vowel
        seq.append({"p": p, "mora": mora, "vowel": vowel, "role": role})
    return seq


# ── normalize Allosaurus output into the same inventory ────────────────────
MODIFIERS = set("ʰʲʷːˑ˞ʼˀˤ͡ⁿˠˡ̚ʱ̥̃ ")
JA_VARIANTS = {
    "ɾ": "r", "ɺ": "r", "l": "r", "ɫ": "r", "ɭ": "r", "ɹ": "r", "ɻ": "r", "r": "r", "ɽ": "r",
    "ɯ": "u", "ʉ": "u", "ɨ": "u",
    "ɕ": "ʃ", "ʂ": "ʃ", "ʃ": "ʃ", "s": "s",
    "ʑ": "ʒ", "ʐ": "ʒ", "ʒ": "ʒ", "z": "z", "dz": "z",
    "tɕ": "tʃ", "tʂ": "tʃ", "tʃ": "tʃ", "ts": "ts",
    "dʑ": "dʒ", "dʐ": "dʒ", "dʒ": "dʒ",
    "ɸ": "ɸ", "f": "f", "ʋ": "f", "v": "f",
    "ŋ": "N", "ɴ": "N", "ɲ": "n", "ɱ": "m",
    "ç": "h", "x": "h", "h": "h", "ɦ": "h", "β": "b", "ɟ": "g", "ɡ": "g", "c": "k", "ʔ": "",
    "ə": "a", "ɐ": "a", "ʌ": "a", "ɑ": "a", "æ": "a", "ä": "a",
    "ɛ": "e", "e": "e", "ɪ": "i", "i": "i", "ʊ": "u", "u": "u", "o": "o", "ɔ": "o", "ø": "e",
    "a": "a",
}


def strip_dia(tok):
    tok = "".join(c for c in tok if c not in MODIFIERS)
    return "".join(c for c in tok if not unicodedata.combining(c))


def norm(tok):
    if tok in JA_VARIANTS:
        return JA_VARIANTS[tok]
    t = strip_dia(tok)
    if t in JA_VARIANTS:
        return JA_VARIANTS[t]
    if t in ("tʃ", "dʒ", "ts"):
        return t
    return t[:1] if len(t) > 1 else t


def actual_phones(path):
    from allosaurus.app import read_recognizer
    m = read_recognizer()
    try:
        raw = m.recognize(path, lang_id="jpn").split()
    except Exception:
        raw = m.recognize(path).split()
    return [{"p": norm(t), "raw": t} for t in raw]


def align(exp, act):
    """Needleman-Wunsch on normalized phones → list of (e_or_None, a_or_None)."""
    n, m = len(exp), len(act)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = i
    for j in range(1, m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if exp[i - 1]["p"] == act[j - 1]["p"] else 1
            dp[i][j] = min(dp[i - 1][j - 1] + cost, dp[i - 1][j] + 1, dp[i][j - 1] + 1)
    i, j, out = n, m, []
    while i > 0 or j > 0:
        if i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + (0 if exp[i - 1]["p"] == act[j - 1]["p"] else 1):
            out.append((exp[i - 1], act[j - 1])); i -= 1; j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            out.append((exp[i - 1], None)); i -= 1
        else:
            out.append((None, act[j - 1])); j -= 1
    return list(reversed(out))


def rrow_realization(raw):
    b = strip_dia(raw)
    if b in ("l", "ɫ", "ɭ"):
        return "l"            # lateral — common English/German substitution
    if b in ("ɹ", "ɻ"):
        return "ɹ"            # English bunched/retroflex r
    if b in ("ɾ", "r", "ɽ", "ɺ"):
        return "flap"         # native-like
    return "other"


def fu_realization(raw):
    b = strip_dia(raw)
    if b in ("f", "v", "ʋ"):
        return "f"            # labiodental — the German/English substitution
    if b in ("ɸ", "h", "ç", "x", "β"):
        return "ok"
    return "other"


def prosody(path):
    try:
        import parselmouth, numpy as np
    except Exception as e:
        return {"prosody": False, "err": str(e)}
    snd = parselmouth.Sound(path)
    f0 = snd.to_pitch().selected_array["frequency"]
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
        "intensity_sd_db": round(float(np.std(iv)), 1) if iv.size else None,
        "monotone_flag": range_st < 4.0,   # JA pitch-accent uses a smaller range than EN intonation
    }


def analyze(text, path):
    exp = expected_phones(text)
    if exp is None:
        return {"err": "pykakasi not installed"}
    if not exp:
        return {"err": "no Japanese in transcript"}
    act = actual_phones(path)
    pairs = align(exp, act)
    ea = [(e, a) for e, a in pairs if e is not None]

    matched = sum(1 for e, a in ea if a and e["p"] == a["p"])

    # 長音 — long vowels shortened (second half of a long vowel deleted)
    long2 = [(e, a) for e, a in ea if e["role"] == "long2"]
    long_short = [e["mora"] for e, a in long2 if a is None]

    # ら行 — flap realized as l / English ɹ
    rrow = [(e, a) for e, a in ea if e["role"] == "rrow"]
    r_subs = []
    for e, a in rrow:
        kind = rrow_realization(a["raw"]) if a else "drop"
        if kind in ("l", "ɹ"):
            r_subs.append((e["mora"], kind))

    # ふ — /ɸ/ realized as labiodental f
    fu = [(e, a) for e, a in ea if e["role"] == "fu"]
    fu_subs = [(e["mora"], "f") for e, a in fu if a and fu_realization(a["raw"]) == "f"]

    # 促音 — geminate っ dropped
    gem = [(e, a) for e, a in ea if e["role"] == "geminate"]
    gem_drop = sum(1 for e, a in gem if a is None)

    return {
        "n_expected": len(exp), "n_actual": len(act), "n_aligned": len(ea),
        "segment_match_pct": round(100 * matched / max(len(ea), 1)),
        "long_vowels": {"expected": len(long2), "shortened": len(long_short), "examples": long_short[:6]},
        "ra_row": {"expected": len(rrow), "substituted": len(r_subs), "examples": r_subs[:6]},
        "fu": {"expected": len(fu), "substituted": len(fu_subs), "examples": fu_subs[:6]},
        "geminate": {"expected": len(gem), "dropped": gem_drop},
        "prosody": prosody(path),
    }


def fetch(args):
    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
    if args.ids:
        ids = [int(x) for x in args.ids.split(",")]
        rows = con.execute(
            f"SELECT id,file_name,transcription_text FROM transcription_history "
            f"WHERE id IN ({','.join('?'*len(ids))}) ORDER BY id", ids).fetchall()
    elif args.since is not None:
        rows = con.execute("SELECT id,file_name,transcription_text FROM transcription_history "
                           "WHERE id > ? ORDER BY id", (args.since,)).fetchall()
    else:
        rows = list(reversed(con.execute(
            "SELECT id,file_name,transcription_text FROM transcription_history "
            "ORDER BY id DESC LIMIT ?", (args.last,)).fetchall()))
    con.close(); return rows


def main():
    ap = argparse.ArgumentParser(description="Japanese pronunciation alignment")
    ap.add_argument("--since", type=int); ap.add_argument("--ids")
    ap.add_argument("--last", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--force", action="store_true", help="run even if the workspace language isn't Japanese")
    args = ap.parse_args()
    if not os.path.exists(DB):
        sys.exit("no db")

    target = L.load_config().get("target_language")
    if target not in (None, "ja") and not args.force:
        print(f"Japanese pronunciation: this module is for Japanese; workspace target is '{target}'.")
        return

    results = []
    for r in fetch(args):
        wav = os.path.join(RECDIR, r["file_name"])
        if not os.path.exists(wav):
            continue
        a = analyze(r["transcription_text"] or "", wav)
        a["id"] = r["id"]
        results.append(a)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False)); return

    for x in results:
        print("─" * 64)
        if x.get("err"):
            print(f"#{x['id']}  [{x['err']}]"); continue
        print(f"#{x['id']}  ({x['n_aligned']} phones aligned of {x['n_expected']} expected, "
              f"{x['segment_match_pct']}% segment match)")
        lv, ra, fu, gem = x["long_vowels"], x["ra_row"], x["fu"], x["geminate"]
        if lv["expected"]:
            ex = "  e.g. " + " ".join(lv["examples"][:4]) if lv["examples"] else ""
            print(f"  長音 long vowels:  {lv['shortened']}/{lv['expected']} shortened{ex}")
        if ra["expected"]:
            ex = "  e.g. " + ", ".join(f"{m}→{k}" for m, k in ra["examples"][:4]) if ra["examples"] else ""
            print(f"  ら行 flap /ɾ/:    {ra['substituted']}/{ra['expected']} as l or ɹ{ex}")
        if fu["expected"]:
            ex = "  e.g. " + ", ".join(m for m, _ in fu["examples"][:4]) if fu["examples"] else ""
            print(f"  ふ /ɸ/→f:         {fu['substituted']}/{fu['expected']} labiodental{ex}")
        if gem["expected"]:
            print(f"  促音 geminate っ:  {gem['dropped']}/{gem['expected']} dropped")
        pr = x["prosody"]
        if pr.get("prosody") and "pitch_range_semitones" in pr:
            flat = "  ⚑ flat — work on pitch-accent movement" if pr["monotone_flag"] else ""
            print(f"  prosody: pitch range {pr['pitch_range_semitones']} st, "
                  f"median {pr['mean_f0_hz']} Hz{flat}")
    print("─" * 64)
    print("Directional only — Allosaurus is imperfect; read trends, not single hits.")
    print("Pitch-ACCENT correctness needs an accent dictionary (not graded here) — "
          "the pitch range is descriptive.")


if __name__ == "__main__":
    main()
