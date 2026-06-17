#!/usr/bin/env python3
"""
pron_align_ja.py — Japanese pronunciation feedback, fully offline.

The Japanese sibling of pron_align.py. Same shape (expected vs. actual phones,
aligned, then flagged), built for Japanese:

  1. EXPECTED phones  — the transcript tokenized with fugashi + UniDic, each
     token's pronunciation reading → IPA via a rule-based table. UniDic also
     gives each word's ACCENT TYPE (downstep position), used below.
  2. ACTUAL phones    — from the .wav via Allosaurus (Japanese), WITH timestamps.
  3. ALIGN            — Needleman-Wunsch on a Japanese-tuned phone inventory.
  4. FLAG             — the learner tells that matter for Japanese:
        • 長音   long vowels shortened (おばあさん→おばさん)
        • ら行   flap /ɾ/ realized as English/German l or ɹ
        • ふ     /ɸ/ realized as labiodental f
        • 促音   geminate っ dropped
        • アクセント  pitch-accent: the dictionary downstep position vs. where the
                 pitch actually dropped (timestamps map the pitch contour to morae)
     plus an overall pitch-range / monotone read.

DIRECTIONAL, not clinical: Allosaurus is imperfect and connected-speech accent has
phrasing effects, so read rates/trends, not single hits. The accent dictionary is
UniDic (free, via the `unidic-lite` package) — downloaded with the deps into the
venv, never committed.

  scripts/.venv/bin/python scripts/pron_align_ja.py --ids 793
  scripts/.venv/bin/python scripts/pron_align_ja.py --since 800 --json
"""
import argparse, json, math, os, re, sqlite3, sys, unicodedata

import lang as L

HANDY = os.path.expanduser("~/Library/Application Support/com.pais.handy")
DB = os.path.join(HANDY, "history.db")
RECDIR = os.path.join(HANDY, "recordings")

VOWELS = set("aiueo")

# ── kana → normalized Japanese phones ──────────────────────────────────────
# Working inventory: k g s z ʃ ʒ t d ts tʃ dʒ n h ɸ b p m j r w  N(ん)  Q(っ)
# + vowels a i u e o.  ら-row → 'r'; ふ → 'ɸ' (distinct from 'f' so a labiodental
# substitution surfaces).
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
YOON = {
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


def kata_to_hira(s):
    out = []
    for c in s:
        o = ord(c)
        out.append(chr(o - 0x60) if 0x30A1 <= o <= 0x30F6 else c)
    return "".join(out)


def kana_to_phones(hira):
    """hiragana reading → [(phone, source-kana)]."""
    out, i = [], 0
    while i < len(hira):
        c = hira[i]
        pair = hira[i:i + 2]
        if len(pair) == 2 and pair in YOON:
            for p in YOON[pair]:
                out.append((p, pair))
            i += 2
        elif c == "っ":
            out.append(("Q", c)); i += 1
        elif c == "ー":
            if out and out[-1][0] in VOWELS:
                out.append((out[-1][0], c))
            i += 1
        elif c == "ん":
            out.append(("N", c)); i += 1
        elif c in KANA:
            for p in KANA[c]:
                out.append((p, c))
            i += 1
        else:
            i += 1
    return out


def split_morae(hira):
    """Hiragana → accent morae (small ゃゅょ fuse; ん っ ー each count as one mora)."""
    morae, i, small = [], 0, set("ゃゅょ")
    while i < len(hira):
        if i + 1 < len(hira) and hira[i + 1] in small:
            morae.append(hira[i:i + 2]); i += 2
        else:
            morae.append(hira[i]); i += 1
    return morae


_TAGGER = None


def get_tagger():
    global _TAGGER
    if _TAGGER is None:
        try:
            import fugashi
            _TAGGER = fugashi.Tagger()
        except Exception:
            _TAGGER = False
    return _TAGGER or None


def build_expected(text):
    """Tokenize with fugashi → (exp phones with word index + role, per-word accent meta).
    Falls back to pykakasi (no word index / accent) if fugashi is unavailable."""
    tagger = get_tagger()
    exp, meta = [], []
    if tagger is None:
        try:
            import pykakasi
            hira = "".join(i["hira"] for i in pykakasi.kakasi().convert(text))
        except Exception:
            return None, None
        for p, mora in kana_to_phones(hira):
            exp.append({"p": p, "mora": mora, "vowel": p in VOWELS, "role": "", "word": 0})
        meta = None
    else:
        for wi, tok in enumerate(tagger(text)):
            f = tok.feature
            reading = getattr(f, "pron", None) or getattr(f, "kana", None)
            hira = kata_to_hira(reading) if reading else ""
            for p, mora in kana_to_phones(hira):
                exp.append({"p": p, "mora": mora, "vowel": p in VOWELS, "role": "", "word": wi})
            at = getattr(f, "aType", None)
            m = re.match(r"\d+", str(at)) if at not in (None, "*", "") else None
            morae = split_morae(hira)
            meta.append({"surface": tok.surface, "n": len(morae),
                         "downstep": int(m.group()) if m else None})

    for idx, e in enumerate(exp):
        p = e["p"]
        if p == "Q":
            e["role"] = "geminate"
        elif p == "ɸ":
            e["role"] = "fu"
        elif p == "r":
            e["role"] = "rrow"
        elif e["vowel"] and idx > 0 and exp[idx - 1]["vowel"] and exp[idx - 1]["p"] == p:
            e["role"] = "long2"
    return exp, meta


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
    "ɛ": "e", "e": "e", "ɪ": "i", "i": "i", "ʊ": "u", "u": "u", "o": "o", "ɔ": "o", "ø": "e", "a": "a",
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
    """Allosaurus phones WITH timestamps → [{p, raw, t}]."""
    from allosaurus.app import read_recognizer
    m = read_recognizer()
    try:
        out = m.recognize(path, lang_id="jpn", timestamp=True)
    except Exception:
        out = m.recognize(path, timestamp=True)
    seq = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            try:
                t = float(parts[0])
            except ValueError:
                continue
            raw = "".join(parts[2:])
            seq.append({"p": norm(raw), "raw": raw, "t": t})
    return seq


def align(exp, act):
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
        return "l"
    if b in ("ɹ", "ɻ"):
        return "ɹ"
    if b in ("ɾ", "r", "ɽ", "ɺ"):
        return "flap"
    return "other"


def fu_realization(raw):
    b = strip_dia(raw)
    if b in ("f", "v", "ʋ"):
        return "f"
    if b in ("ɸ", "h", "ç", "x", "β"):
        return "ok"
    return "other"


def pitch_track(path):
    import parselmouth, numpy as np
    snd = parselmouth.Sound(path)
    p = snd.to_pitch()
    return p.xs(), p.selected_array["frequency"], snd


def accent_check(exp, meta, act, path):
    """Compare UniDic downstep position to where the pitch actually dropped.
    Words are located in time via the phone alignment; the contour is sampled per
    mora over the word's span (Japanese is mora-timed, so equal bins are fair)."""
    if not meta:
        return None
    try:
        import numpy as np
    except Exception:
        return None
    pairs = align(exp, act)
    wt = {}
    for e, a in pairs:
        if e is not None and a is not None and a.get("t") is not None:
            wt.setdefault(e["word"], []).append(a["t"])
    times, f0, _ = pitch_track(path)
    checked = []
    for wi, wm in enumerate(meta):
        ds, n = wm["downstep"], wm["n"]
        if ds is None or n < 2:
            continue
        ts = wt.get(wi)
        if not ts or len(ts) < 2:
            continue
        s, e0 = min(ts), max(ts)
        if e0 - s < 0.12:
            continue
        bins = []
        for k in range(n):
            a0 = s + (e0 - s) * k / n
            a1 = s + (e0 - s) * (k + 1) / n
            vals = [f0[j] for j in range(len(times)) if a0 <= times[j] < a1 and f0[j] > 0]
            bins.append(float(np.median(vals)) if vals else None)
        if sum(1 for b in bins if b) < 2:
            continue
        best_k, best_drop = 0, 0.0
        for k in range(1, n):
            if bins[k - 1] and bins[k]:
                d = 12 * math.log2(bins[k - 1] / bins[k])
                if d > best_drop:
                    best_drop, best_k = d, k
        realized = best_k if best_drop >= 2.0 else 0
        match = (ds == 0 and realized == 0) or (ds >= 1 and abs(realized - ds) <= 1)
        checked.append({"surface": wm["surface"], "n": n,
                        "expected_downstep": ds, "realized_downstep": realized, "match": match})
    return checked


def prosody(path):
    try:
        import numpy as np
        times, f0, snd = pitch_track(path)
    except Exception as e:
        return {"prosody": False, "err": str(e)}
    voiced = f0[f0 > 0]
    if voiced.size < 5:
        return {"prosody": True, "note": "too little voiced audio"}
    p10, p90 = np.percentile(voiced, [10, 90])
    range_st = float(12 * np.log2(p90 / p10)) if p10 > 0 else 0.0
    return {"prosody": True, "mean_f0_hz": round(float(np.median(voiced)), 1),
            "pitch_range_semitones": round(range_st, 1), "monotone_flag": range_st < 4.0}


def analyze(text, path):
    exp, meta = build_expected(text)
    if exp is None:
        return {"err": "pykakasi/fugashi not installed"}
    if not exp:
        return {"err": "no Japanese in transcript"}
    act = actual_phones(path)
    ea = [(e, a) for e, a in align(exp, act) if e is not None]
    matched = sum(1 for e, a in ea if a and e["p"] == a["p"])

    long2 = [(e, a) for e, a in ea if e["role"] == "long2"]
    long_short = [e["mora"] for e, a in long2 if a is None]
    rrow = [(e, a) for e, a in ea if e["role"] == "rrow"]
    r_subs = [(e["mora"], rrow_realization(a["raw"])) for e, a in rrow
              if a and rrow_realization(a["raw"]) in ("l", "ɹ")]
    fu = [(e, a) for e, a in ea if e["role"] == "fu"]
    fu_subs = [e["mora"] for e, a in fu if a and fu_realization(a["raw"]) == "f"]
    gem = [(e, a) for e, a in ea if e["role"] == "geminate"]
    gem_drop = sum(1 for e, a in gem if a is None)

    accent = accent_check(exp, meta, act, path)
    return {
        "n_expected": len(exp), "n_actual": len(act), "n_aligned": len(ea),
        "segment_match_pct": round(100 * matched / max(len(ea), 1)),
        "long_vowels": {"expected": len(long2), "shortened": len(long_short), "examples": long_short[:6]},
        "ra_row": {"expected": len(rrow), "substituted": len(r_subs), "examples": r_subs[:6]},
        "fu": {"expected": len(fu), "substituted": len(fu_subs), "examples": fu_subs[:6]},
        "geminate": {"expected": len(gem), "dropped": gem_drop},
        "accent": accent,
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
            ex = "  e.g. " + ", ".join(fu["examples"][:4]) if fu["examples"] else ""
            print(f"  ふ /ɸ/→f:         {fu['substituted']}/{fu['expected']} labiodental{ex}")
        if gem["expected"]:
            print(f"  促音 geminate っ:  {gem['dropped']}/{gem['expected']} dropped")
        ac = x["accent"]
        if ac:
            good = sum(1 for w in ac if w["match"])
            miss = [w for w in ac if not w["match"]]
            print(f"  アクセント pitch-accent: {good}/{len(ac)} words matched the dictionary pattern")
            for w in miss[:4]:
                exp_d = "heiban (no drop)" if w["expected_downstep"] == 0 else f"drop after mora {w['expected_downstep']}"
                got = "no drop" if w["realized_downstep"] == 0 else f"drop after mora {w['realized_downstep']}"
                print(f"      {w['surface']}: expected {exp_d}, heard {got}")
        pr = x["prosody"]
        if pr.get("prosody") and "pitch_range_semitones" in pr:
            flat = "  ⚑ flat" if pr.get("monotone_flag") else ""
            print(f"  prosody: pitch range {pr['pitch_range_semitones']} st, median {pr['mean_f0_hz']} Hz{flat}")
    print("─" * 64)
    print("Directional only — Allosaurus is imperfect and connected-speech accent has")
    print("phrasing effects; read trends, not single hits. Accent = UniDic (unidic-lite).")


if __name__ == "__main__":
    main()
