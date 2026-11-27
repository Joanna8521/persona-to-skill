# -*- coding: utf-8 -*-
"""Pathological input must not hang anything.

Every regular expression in this project is pointed at third-party text:
caption files, scraped articles, PDFs someone uploaded. SECURITY.md names
corpus-driven attacks as a vulnerability class here rather than a theoretical
one, and catastrophic backtracking is the cheapest of them, since the attacker
only has to supply a file.

One such bug shipped and CodeQL caught it on the pull request:

    _VTT_VOICE = re.compile("<v(?:\\.[^ >]*)*\\s+(?P<who>[^>]+)>")

a quantifier inside a quantified group. On "<v" followed by dots and no space,
so the match is forced to fail, it measured 11ms at 18 dots, 243ms at 22, and
2.9s at 26. A forty-character caption file would have hung the pipeline.

So this file does not test that one pattern. It feeds pathological input to
every entry point that touches untrusted text and bounds the time, which is the
check that catches the next one too.
"""
import time

import _base  # noqa: F401
from persona_to_skill.collect import provenance as pv
from persona_to_skill.collect import transcript as tr
from persona_to_skill.gates import anchor

# Generous by three orders of magnitude against the bug it is guarding: the
# shipped one took 2.9 seconds on 26 characters. Anything linear finishes these
# in single-digit milliseconds.
BUDGET_S = 2.0


def _timed(label, fn, *args, **kwargs):
    start = time.perf_counter()
    fn(*args, **kwargs)
    elapsed = time.perf_counter() - start
    assert elapsed < BUDGET_S, f"{label} took {elapsed:.2f}s on pathological input"
    return elapsed


# ------------------------------------------------- the shape that shipped
def test_vtt_voice_tag_does_not_backtrack():
    for n in (26, 64, 2000, 50_000):
        _timed(f"_VTT_VOICE with {n} dots", tr._VTT_VOICE.search, "<v" + "." * n + "!")


def test_every_transcript_pattern_survives_its_own_worst_case():
    """Each pattern fed the input that forces it to fail as late as possible."""
    cases = {
        "_SENTENCE_FINAL": ("." + '"' * 50_000 + "x", tr._SENTENCE_FINAL),
        "_NON_SPEECH": ("(" + "a" * 50_000, tr._NON_SPEECH),
        "_BRACKET_SPEAKER": ("(" + "a" * 50_000, tr._BRACKET_SPEAKER),
        "_ARROW_SPEAKER": (">>" + " " * 50_000, tr._ARROW_SPEAKER),
        "_LABEL_SPEAKER": ("A" + "a" * 50_000, tr._LABEL_SPEAKER),
        "_VTT_TAG": ("<v" + "." * 50_000, tr._VTT_TAG),
        "_TIMECODE": ("0" * 50_000, tr._TIMECODE),
    }
    for label, (payload, pattern) in cases.items():
        _timed(label, pattern.search, payload)


# -------------------------------------------------- the public entry points
def test_parsing_a_hostile_caption_file_is_fast():
    """What an attacker actually supplies: a file, not a regex input."""
    blocks = []
    for i in range(200):
        blocks.append(f"00:00:{i % 60:02d}.000 --> 00:00:{(i + 1) % 60:02d}.000\n"
                      "<v" + "." * 200 + "!\n"
                      + "(" + "a" * 500 + "\n"
                      + ">>" + " " * 500 + "\n")
    _timed("parse_vtt on a hostile file", tr.parse_vtt, "WEBVTT\n\n" + "\n\n".join(blocks))


def test_joining_hostile_cues_is_fast():
    cues = [tr.Cue(i * 1000, "." + '"' * 2000 + " " * 2000) for i in range(300)]
    _timed("join_cues", tr.join_cues, cues)


def test_attributing_hostile_cues_is_fast():
    cues = [tr.Cue(i * 1000, "A" + "a" * 2000 + "：" + "b" * 2000) for i in range(300)]
    _timed("attribute", tr.attribute, cues, "Morris Chang")


def test_measuring_a_hostile_source_is_fast():
    for payload in ("." * 200_000, "a" * 200_000, "。" * 100_000, ". " * 100_000):
        _timed("provenance.measure", pv.measure, payload)


def test_normalising_a_hostile_quote_is_fast():
    """anchor._normalize folds contractions and CJK spacing, so it runs a
    sequence of substitutions over whatever text arrives."""
    for payload in ("n't" * 20_000, "中a" * 50_000, " " * 200_000, "，" * 100_000):
        _timed("anchor._normalize", anchor._normalize, payload)


def test_anchoring_against_a_hostile_corpus_is_fast(tmpdir=None):
    import tempfile
    from pathlib import Path
    d = Path(tempfile.mkdtemp())
    (d / "s1.txt").write_text("中a" * 50_000, encoding="utf-8")
    claims = [{"id": "c", "text": "x", "source_id": "s1", "quote": "中a" * 100}]
    _timed("anchor.check", anchor.check, claims, d)


# ------------------------------------------------ the documentation gate
def test_the_punctuation_gate_is_fast_on_a_hostile_document():
    import tempfile
    from pathlib import Path
    from persona_to_skill import validate_punct as vp
    d = Path(tempfile.mkdtemp())
    p = d / "README.zh-TW.md"
    p.write_text("\n".join(["`" * 5000, "中" * 5000 + ",", "-" * 5000,
                            "<" + "a" * 5000, "https://" + "a" * 5000] * 20),
                 encoding="utf-8")
    _timed("validate_punct.check_file", vp.check_file, p)


if __name__ == "__main__":
    import sys
    sys.exit(_base.run_module(dict(globals())))
