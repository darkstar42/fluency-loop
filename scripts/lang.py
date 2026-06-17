"""lang.py — language adapters + workspace config for the analyzer.

The audio analysis (pauses, phonation, length of runs) is language-neutral and
shared. What changes per language is small and lives here:

  • the UNIT speech is measured in (words for English, morae for Japanese, …)
  • the FILLER words that show up in transcripts ("um" vs "えーと")
  • how to TELL this language's takes apart from others in the shared Handy history

The target/native language is chosen during the onboarding `/teach` session and
written to `config.json` at the repo root. Scripts read it from there; a `--lang`
flag overrides it; with neither, they fall back to a language-neutral "generic"
adapter that still reports whitespace-word fluency.
"""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config.json")


def load_config():
    """Workspace config (target_language, native_language). {} if unset."""
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


# ── unit counters ─────────────────────────────────────────────────────────
def count_words(text):
    """Whitespace words. Returns (n, reading=None)."""
    return len(text.split()), None


_JA_SMALL = set("ゃゅょぁぃぅぇぉゎ")


def count_morae(text):
    """Japanese morae from mixed kanji/kana via pykakasi. Returns (n, kana)."""
    import pykakasi
    hira = "".join(i["hira"] for i in pykakasi.kakasi().convert(text))
    # each full-size kana = 1 mora (incl. っ, ん, ー); small ゃゅょ etc. fuse and don't count
    morae = [c for c in hira if (("ぁ" <= c <= "ん") or c == "ー") and c not in _JA_SMALL]
    return len(morae), hira


# ── script detection (filter the shared Handy DB to one language) ──────────
_CJK = re.compile(r"[぀-ヿ㐀-鿿豈-﫿]")   # kana + CJK ideographs
_LATIN = re.compile(r"[A-Za-z]")


def _is_english(text):
    return bool(_LATIN.search(text)) and not _CJK.search(text)


def _is_japanese(text):
    return bool(_CJK.search(text))


# ── filler lists (visible in transcripts; silent pauses come from audio) ───
EN_FILLERS = [
    r"\buh+\b", r"\bum+\b", r"\berm+\b", r"\bhmm+\b", r"\blike\b",
    r"\byou know\b", r"\bi mean\b", r"\bi don'?t know\b", r"\bsort of\b",
    r"\bkind of\b", r"\bbasically\b", r"\bwell\b", r"\byeah\b", r"\bso\b",
]
# Japanese fillers are heuristic — kept conservative to avoid flagging legit
# demonstratives. No word boundaries (Japanese isn't space-delimited).
JA_FILLERS = [r"えーと", r"えっと", r"ええと", r"あのー", r"うーん", r"なんか", r"まあ"]


ADAPTERS = {
    "en": {
        "name": "English", "unit": "words", "unit_one": "word", "rate_label": "wpm",
        "count": count_words, "fillers": EN_FILLERS, "is_target": _is_english,
        "min_pause": 0.3, "bands": None,
    },
    "ja": {
        "name": "Japanese", "unit": "morae", "unit_one": "mora", "rate_label": "morae/min",
        "count": count_morae, "fillers": JA_FILLERS, "is_target": _is_japanese,
        "min_pause": 0.25, "bands": "learner ≈320–360, native ≈450+",
    },
}

GENERIC = {
    "name": "your language", "unit": "words", "unit_one": "word",
    "rate_label": "wpm (whitespace words)", "count": count_words,
    "fillers": None, "is_target": lambda _t: True, "min_pause": 0.3, "bands": None,
}


def get_adapter(code):
    return ADAPTERS.get(code, GENERIC)


def resolve_code(cli_lang=None):
    """CLI --lang wins, else config.json target_language, else 'generic'."""
    return cli_lang or load_config().get("target_language") or "generic"
