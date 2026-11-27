#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Does G2's verbatim matching survive real corpora?

G2 blocks a claim whose quote does not appear in its source. That is only a
usable rule if quotes an extraction stage actually produces are findable in
text as actually stored. If exact matching fails routinely, G2 is not strict,
it is broken, and it breaks the first stage of the pipeline.

The failure mode worth testing is NOT scanning noise. It is that the extraction
stage is a model REGENERATING text rather than copying bytes. A model writing a
quote field tends, without being asked, to:

  * straighten curly quotes and apostrophes
  * normalise dashes (em, en, double hyphen)
  * collapse a line break mid-sentence into a space
  * drop a bracketed interjection or an ellipsis
  * expand or contract "don't" / "do not"
  * fix an obvious typo in the source
  * trim a trailing comma to end the quote cleanly
  * in Chinese: swap full-width and half-width punctuation, add or remove the
    space between Chinese and Latin text

This script applies each transformation INDIVIDUALLY to passages taken from
real text, then asks G2 whether the quote still matches. One transformation per
case, so a failure names its own cause.

Usage:
    python3 experiments/g2_realcorpus.py <corpus-dir>

The corpus dir holds <source_id>.txt files of real, uncleaned text.
"""
from __future__ import annotations

import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from persona_to_skill.gates import anchor  # noqa: E402

# ------------------------------------------------- the transformations, named
def straighten_quotes(t: str) -> str:
    for a, b in (("“", '"'), ("”", '"'), ("‘", "'"), ("’", "'")):
        t = t.replace(a, b)
    return t


def normalise_dashes(t: str) -> str:
    return t.replace("—", "--").replace("–", "-")


def collapse_newline(t: str) -> str:
    return re.sub(r"\s*\n\s*", " ", t)


def drop_ellipsis(t: str) -> str:
    return t.replace("...", "").replace("…", "")


def expand_contractions(t: str) -> str:
    for a, b in (("don't", "do not"), ("it's", "it is"), ("can't", "cannot"),
                 ("won't", "will not"), ("doesn't", "does not"), ("isn't", "is not"),
                 ("you're", "you are"), ("they're", "they are"), ("that's", "that is")):
        t = t.replace(a, b).replace(a.capitalize(), b.capitalize())
    return t


def trim_trailing_comma(t: str) -> str:
    return t.rstrip().rstrip(",;:").rstrip()


def halfwidth_cjk_punct(t: str) -> str:
    for a, b in (("，", ","), ("。", "."), ("：", ":"), ("；", ";"),
                 ("（", "("), ("）", ")"), ("、", ",")):
        t = t.replace(a, b)
    return t


def strip_cjk_latin_space(t: str) -> str:
    t = re.sub(r"(?<=[一-鿿])\s+(?=[A-Za-z0-9])", "", t)
    return re.sub(r"(?<=[A-Za-z0-9])\s+(?=[一-鿿])", "", t)


def add_cjk_latin_space(t: str) -> str:
    t = re.sub(r"(?<=[一-鿿])(?=[A-Za-z0-9])", " ", t)
    return re.sub(r"(?<=[A-Za-z0-9])(?=[一-鿿])", " ", t)


def fullwidth_digits(t: str) -> str:
    return t.translate(str.maketrans("0123456789", "０１２３４５６７８９"))


def fix_a_typo(t: str) -> str:
    """Stand-in for a model silently correcting the source."""
    return t.replace("  ", " ", 1) if "  " in t else t.replace("teh ", "the ", 1)


TRANSFORMS = [
    ("verbatim (control)", lambda t: t),
    ("straightened curly quotes", straighten_quotes),
    ("normalised dashes", normalise_dashes),
    ("newline collapsed to space", collapse_newline),
    ("ellipsis dropped", drop_ellipsis),
    ("contractions expanded", expand_contractions),
    ("trailing comma trimmed", trim_trailing_comma),
    ("CJK punctuation to half-width", halfwidth_cjk_punct),
    ("CJK/Latin space removed", strip_cjk_latin_space),
    ("CJK/Latin space added", add_cjk_latin_space),
    ("digits to full-width", fullwidth_digits),
    ("double space squeezed", fix_a_typo),
]


def passages(text: str, n: int, rng: random.Random) -> list[str]:
    """Take sentence-ish spans long enough to be real quotes."""
    parts = [p.strip() for p in re.split(r"(?<=[.!?。！？])\s+", text) if len(p.strip()) > 60]
    if not parts:
        parts = [text[i:i + 200] for i in range(0, min(len(text), 2000), 200)]
    rng.shuffle(parts)
    out, seen = [], set()
    for p in parts:
        key = p[:40]
        if key in seen:
            continue
        seen.add(key)
        out.append(p if len(p) < 300 else p[:300])
        if len(out) >= n:
            break
    return out


def main(corpus_dir: str, per_source: int = 12, seed: int = 11) -> int:
    d = Path(corpus_dir)
    files = sorted(f for f in d.iterdir() if f.suffix == ".txt")
    if not files:
        print(f"no .txt corpus files in {d}")
        return 2

    rng = random.Random(seed)
    results: dict[str, list[int]] = {name: [0, 0] for name, _ in TRANSFORMS}

    for f in files:
        raw = f.read_text(encoding="utf-8", errors="replace")
        sid = f.stem
        quotes = passages(raw, per_source, rng)
        print(f"\n=== {sid}  ({len(raw):,} chars, {len(quotes)} passages)")
        for name, fn in TRANSFORMS:
            ok = bad = 0
            for q in quotes:
                mutated = fn(q)
                if mutated == q and name != "verbatim (control)":
                    continue          # transformation did not apply here
                v = anchor.check(
                    [{"id": "c", "text": "a claim", "source_id": sid, "quote": mutated}], d)
                if v.passed:
                    ok += 1
                else:
                    bad += 1
            results[name][0] += ok
            results[name][1] += bad
            if ok or bad:
                flag = "" if bad == 0 else "   <-- FAILS"
                print(f"  {name:<34} matched {ok:>3} / {ok + bad:<3}{flag}")

    print("\n" + "=" * 68)
    print("TOTAL, by transformation")
    print("=" * 68)
    broken = []
    for name, (ok, bad) in results.items():
        total = ok + bad
        if not total:
            print(f"  {name:<34} not applicable to this corpus")
            continue
        rate = ok / total
        print(f"  {name:<34} {rate:6.1%}  ({ok}/{total})")
        if rate < 1.0:
            broken.append((name, rate, ok, total))

    print()
    if not broken:
        print("G2 survived every transformation. Verbatim matching is viable as built.")
        return 0
    print("G2 is defeated by:")
    for name, rate, ok, total in sorted(broken, key=lambda x: x[1]):
        print(f"  {rate:6.1%}  {name}   ({total - ok} of {total} claims would be blocked)")
    print("\nEach line is a way a correctly-extracted quote gets rejected.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "experiments/corpus"))
