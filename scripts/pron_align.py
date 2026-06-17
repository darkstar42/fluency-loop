#!/usr/bin/env python3
"""
pron_align.py — actionable pronunciation feedback, fully offline.

Pipeline per take:
  1. EXPECTED phones  — from the transcript words via CMUdict (`pronouncing`),
     ARPAbet → IPA, with word-final voiced obstruents tagged.
  2. ACTUAL phones    — from the .wav via Allosaurus (universal phone recognizer).
  3. ALIGN            — global (Needleman-Wunsch) alignment of expected vs actual,
     on a normalized phone inventory.
  4. FLAG             — German→English transfer patterns:
        • th  (θ/ð) realized as s/z/t/d/f
        • w / v confusion
        • ŋ  realized as n / ŋk
        • æ  realized as ɛ
        • final-obstruent DEVOICING (the big German tell: "dog"→"dok")

This is DIRECTIONAL, not clinical: Allosaurus output is imperfect and CMUdict
misses out-of-vocabulary words (names etc.), so read rates/trends, not single hits.

  scripts/.venv/bin/python scripts/pron_align.py --ids 805,806,807,808
  scripts/.venv/bin/python scripts/pron_align.py --since 801 --json
"""
import argparse, json, os, re, sqlite3, sys, unicodedata

HANDY = os.path.expanduser("~/Library/Application Support/com.pais.handy")
DB = os.path.join(HANDY, "history.db")
RECDIR = os.path.join(HANDY, "recordings")

ARPA2IPA = {
    "AA": ["ɑ"], "AE": ["æ"], "AH": ["ʌ"], "AO": ["ɔ"], "AW": ["a", "ʊ"],
    "AY": ["a", "ɪ"], "B": ["b"], "CH": ["tʃ"], "D": ["d"], "DH": ["ð"],
    "EH": ["ɛ"], "ER": ["ɹ"], "EY": ["e", "ɪ"], "F": ["f"], "G": ["g"],
    "HH": ["h"], "IH": ["ɪ"], "IY": ["i"], "JH": ["dʒ"], "K": ["k"], "L": ["l"],
    "M": ["m"], "N": ["n"], "NG": ["ŋ"], "OW": ["o", "ʊ"], "OY": ["ɔ", "ɪ"],
    "P": ["p"], "R": ["ɹ"], "S": ["s"], "SH": ["ʃ"], "T": ["t"], "TH": ["θ"],
    "UH": ["ʊ"], "UW": ["u"], "V": ["v"], "W": ["w"], "Y": ["j"], "Z": ["z"],
    "ZH": ["ʒ"],
}

MODIFIERS = set("ʰʲʷːˑ˞ʼˀˤ͡ⁿˠˡ̚ʱ")
VARIANTS = {
    "r": "ɹ", "ʁ": "ɹ", "ɾ": "ɹ", "ɻ": "ɹ", "ɽ": "ɹ", "ʀ": "ɹ",
    "ʂ": "ʃ", "ɕ": "ʃ", "ʐ": "ʒ", "ʑ": "ʒ", "ɡ": "g", "ɫ": "l",
    "ɲ": "n", "ɱ": "m", "ŋ": "ŋ", "ʈ": "t", "ɖ": "d",
    "tʂ": "tʃ", "tɕ": "tʃ", "dʐ": "dʒ", "dʑ": "dʒ", "c": "k", "ɟ": "g",
    "ʔ": "", "ə": "ə", "ɨ": "ɪ", "ɯ": "u", "ø": "ɛ", "œ": "ɛ", "y": "j",
}
VOICED_OBSTRUENTS = {"b": "p", "d": "t", "g": "k", "z": "s", "v": "f",
                     "ð": "θ", "dʒ": "tʃ"}
DEVOICED = set(VOICED_OBSTRUENTS.values())


def strip_dia(tok):
    tok = "".join(c for c in tok if c not in MODIFIERS)
    tok = "".join(c for c in tok if not unicodedata.combining(c))
    return tok


def norm(tok):
    if tok == "":
        return ""
    if tok in VARIANTS:
        tok = VARIANTS[tok]
    t = strip_dia(tok)
    if t in VARIANTS:
        t = VARIANTS[t]
    # affricates that survive as 2 chars
    if t in ("tʃ", "dʒ", "ts"):
        return t
    return t[:1] if len(t) > 1 else t


def expected_phones(text):
    """Return list of dicts: {p, word, final_voiced_obstruent(bool)}."""
    try:
        import pronouncing
    except Exception:
        return None
    seq = []
    for w in re.findall(r"[a-zA-Z']+", text):
        prons = pronouncing.phones_for_word(w.lower())
        if not prons:
            continue  # OOV — skip (names etc.)
        arpa = [re.sub(r"\d", "", a) for a in prons[0].split()]
        ipa = []
        for a in arpa:
            ipa.extend(ARPA2IPA.get(a, [a.lower()]))
        for i, p in enumerate(ipa):
            is_final = (i == len(ipa) - 1) and (p in VOICED_OBSTRUENTS)
            seq.append({"p": norm(p), "raw": p, "word": w, "final_vo": is_final})
    return seq


VOWELS = set("iɪeɛæaʌɑɔoʊuəɝ")


def is_vowel(p):
    return bool(p) and p[0] in VOWELS


def actual_phones(path):
    from allosaurus.app import read_recognizer
    m = read_recognizer()
    try:
        raw = m.recognize(path, lang_id="eng").split()   # constrain to English inventory
    except Exception:
        raw = m.recognize(path).split()
    return [{"p": norm(t), "raw": t} for t in raw]


def align(exp, act):
    """Needleman-Wunsch on normalized phones. Returns list of (e_or_None, a_or_None)."""
    n, m = len(exp), len(act)
    INF = float("inf")
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


def analyze(text, path):
    exp = expected_phones(text)
    if exp is None:
        return {"err": "pronouncing not installed"}
    act = actual_phones(path)
    pairs = [(e, a) for e, a in align(exp, act) if e is not None]

    targets = {"th (θ/ð)": (["θ", "ð"], []), "w↔v": (["w", "v"], []),
               "ŋ (-ng)": (["ŋ"], []), "æ (cat)": (["æ"], [])}
    for e, a in pairs:
        ep = e["p"]; ap = a["p"] if a else "∅"
        for label, (phs, subs) in targets.items():
            if ep in phs:
                subs.append((e["raw"], ap, e["word"]))

    # final-obstruent devoicing
    devoiced = []
    fvo_total = 0
    for e, a in pairs:
        if e["final_vo"]:
            fvo_total += 1
            ap = a["p"] if a else "∅"
            if ap in DEVOICED or ap == "∅":
                devoiced.append((e["word"], e["p"], ap))

    out = {"n_expected": len(exp), "n_actual": len(act), "n_aligned": len(pairs)}
    for label, (phs, subs) in targets.items():
        # only count same-class substitutions; cross-class (vowel<->consonant) = alignment noise
        scored = [(r, s, w) for (r, s, w) in subs
                  if s != "∅" and is_vowel(norm(r)) == is_vowel(s)]
        wrong = [(r, s, w) for (r, s, w) in scored if norm(r) != s]
        out[label] = {"expected": len(scored), "substituted": len(wrong),
                      "examples": wrong[:6]}
    # split true devoicing (voiced obstruent -> its voiceless pair) from dropped (∅)
    true_dev = [(w, p, s) for (w, p, s) in devoiced if s != "∅"]
    dropped = [(w, p, s) for (w, p, s) in devoiced if s == "∅"]
    out["final_devoicing"] = {"final_voiced_obstruents": fvo_total,
                              "devoiced": len(true_dev), "dropped": len(dropped),
                              "examples": true_dev[:6]}
    return out


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
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=int); ap.add_argument("--ids")
    ap.add_argument("--last", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if not os.path.exists(DB):
        sys.exit("no db")

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
        print(f"#{x['id']}  ({x['n_aligned']} phones aligned of {x['n_expected']} expected)")
        for label in ["th (θ/ð)", "w↔v", "ŋ (-ng)", "æ (cat)"]:
            t = x[label]
            if t["expected"]:
                rate = int(100 * t["substituted"] / t["expected"])
                ex = "  e.g. " + ", ".join(f"{r}→{s} ({w})" for r, s, w in t["examples"][:3]) if t["examples"] else ""
                print(f"  {label:10s}: {t['substituted']}/{t['expected']} off ({rate}%){ex}")
        fd = x["final_devoicing"]
        if fd["final_voiced_obstruents"]:
            rate = int(100 * fd["devoiced"] / fd["final_voiced_obstruents"])
            ex = "  e.g. " + ", ".join(f"{w} ({p}→{s})" for w, p, s in fd["examples"][:3]) if fd["examples"] else ""
            print(f"  final-devoicing: {fd['devoiced']}/{fd['final_voiced_obstruents']} ({rate}%)"
                  f"  [+{fd['dropped']} dropped/unclear]{ex}")
    print("─" * 64)
    print("Directional only — Allosaurus & CMUdict are imperfect; read trends, not single hits.")


if __name__ == "__main__":
    main()
