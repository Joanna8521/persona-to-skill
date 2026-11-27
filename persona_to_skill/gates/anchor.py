#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G2: source anchor reconciliation.

Every claim attributed to the subject must name a source and quote it, and the
quote must appear in that source verbatim.

This gate recomputes independently: it reopens the corpus file from disk and
searches for the quote itself. It does not consult whatever index, offset, or
confidence score the extraction stage produced, because confirming an extraction with
its own bookkeeping is the self-referential gate that always passes.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List

from ..contract import AUTHORSHIP_NOT_OWN_WORDS
from . import Verdict

GATE = "G2-anchor"

# Numbers carry the most weight and are the easiest thing for a model to invent,
# so they are checked individually on top of the quote check.
_NUM = re.compile(r"\d[\d,._]*\d|\d")

# ------------------------------------------------------------------ folding
# Measured on real corpora, not guessed at: see experiments/g2_realcorpus.py.
# The extraction stage is a model regenerating text, not copying bytes, so a
# correctly extracted quote routinely differs from its source in ways that
# change no words. Before these were folded, exact matching rejected 12 of 12
# English passages whose contractions had been expanded, 9 of 9 Chinese
# passages whose punctuation had been written half-width, and 8 of 8 where a
# space had been added between Chinese and Latin text.
#
# Folding is restricted to transformations that cannot make a FABRICATED quote
# match. Each of these alters the byte sequence while leaving the token stream
# identical, so two strings that fold together said the same thing.
#
# What is deliberately NOT folded: a removed ellipsis. An ellipsis marks elided
# text, so dropping it asserts that two passages are contiguous when they are
# not. That is an integrity failure, not a formatting difference, and it stays
# a block, with an error message that says so.

# NFKC folds full-width digits and Latin, but 。，、：；（） are characters in
# their own right rather than compatibility forms of ASCII, so they survive it.
_CJK_PUNCT = str.maketrans({
    "，": ",", "。": ".", "、": ",", "：": ":", "；": ";",
    "（": "(", "）": ")", "！": "!", "？": "?",
    "「": '"', "」": '"', "『": '"', "』": '"',
    "〈": "<", "〉": ">", "《": '"', "》": '"',
})

# English contractions, applied to BOTH sides so either spelling matches.
#
# Order matters and got this wrong first time round: a generic "n't" rule
# placed before the irregulars turns "won't" into "wo not", so "will not" never
# matches. Irregulars first, generic last.
#
# Honest limit: this is a lexical list, like any other, and a nonstandard
# contraction will still be rejected. Unlike a blacklist, incompleteness here
# fails safe (an unfolded form blocks a real quote rather than letting a
# fabricated one through) and the set of standard English contractions is
# genuinely closed, so the list can be finished. It was measured, not guessed:
# see experiments/g2_realcorpus.py.
_CONTRACTIONS = (
    # irregular, before the generic rule below
    ("won't", "will not"), ("can't", "can not"), ("cannot", "can not"),
    ("shan't", "shall not"), ("ain't", "is not"), ("let's", "let us"),
    # "'s" only after a pronoun or determiner. A noun takes the possessive,
    # and expanding "Paul's essay" into "Paul is essay" would be nonsense.
    ("it's", "it is"), ("that's", "that is"), ("there's", "there is"),
    ("here's", "here is"), ("what's", "what is"), ("who's", "who is"),
    ("he's", "he is"), ("she's", "she is"), ("where's", "where is"),
    ("how's", "how is"), ("this's", "this is"),
    # generic, last
    ("n't", " not"), ("'re", " are"), ("'ve", " have"), ("'ll", " will"),
    ("'d", " would"), ("'m", " am"),
)
_CJK = r"\u4e00-\u9fff\u3400-\u4dbf"
_CJK_LATIN_SPACE = re.compile(
    rf"(?<=[{_CJK}])\s+(?=[A-Za-z0-9])|(?<=[A-Za-z0-9])\s+(?=[{_CJK}])")


def _expand(replacement: str):
    """Substitute `replacement` while keeping the matched text's own capital.

    Matching is case-insensitive, so replacing with a lowercase literal would
    quietly lowercase the text at every contraction site, turning "That's"
    into "that is" while leaving case alone everywhere else, and rejecting a
    correctly quoted sentence over its first letter. Found by running the gate
    against real corpora rather than by reading it.
    """
    def sub(m: "re.Match[str]") -> str:
        hit = m.group(0)
        if hit[:1].isupper():
            return replacement[:1].upper() + replacement[1:]
        return replacement
    return sub


def _normalize(text: str) -> str:
    """Fold what changes bytes without changing words, and nothing more.

    Case is NOT folded, and no word is added or removed: a quote that differs
    in wording is a different quote. What is folded is width, compatibility
    forms, whitespace runs, CJK punctuation width, the optional space between
    CJK and Latin text, and the closed set of English contractions. Each was
    measured against real corpora before being added (see
    experiments/g2_realcorpus.py) and each leaves the token stream intact.
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_CJK_PUNCT)
    for short, long in _CONTRACTIONS:
        if short in text.lower():
            text = re.sub(re.escape(short), _expand(long), text, flags=re.IGNORECASE)
    text = _CJK_LATIN_SPACE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


_ELLIPSIS = re.compile(r"\.\.\.|\u2026|\u22ef")


def _digits(text: str) -> List[str]:
    return [m.group(0).replace(",", "").replace("_", "") for m in _NUM.finditer(text)]


def check(claims: List[Dict[str, Any]], corpus_dir: Path,
          sources: List[Dict[str, Any]] | None = None) -> Verdict:
    """Reconcile `claims` against the corpus on disk.

    Each claim needs: `text` (what is being asserted), `source_id`, and `quote`
    (the passage it rests on). A claim may instead be marked
    `attribution: "inference"`, which exempts it from the quote check but
    requires the output to label it as an inference. G3 enforces that: an
    inference claim the rendered skill does not label BLOCKS there. Until
    B-reconcile was added, G3 only warned when the word appeared anywhere
    and said nothing when it was absent, so this comment described a check
    that did not exist and the exemption rested on nothing.

    `sources`, when given, carries each source's authorship. A quote can match
    its source exactly and still not be the subject's own words: The Art of the
    Deal is credited to Trump and was written by Tony Schwartz, who has said so
    publicly. So a claim resting on a source that is ghostwritten, co-authored,
    institutional or translated must set `attributed_to_source: true`, which
    makes the honest form available ("the book published under their name says
    X") and refuses the dishonest one ("they said X").
    """
    errors: List[str] = []
    warnings: List[str] = []
    corpus_dir = Path(corpus_dir)

    if not claims:
        return Verdict(GATE, False, ["no claims supplied; nothing to reconcile"])
    if not corpus_dir.is_dir():
        # Fail closed: without the corpus there is no independent check to run,
        # so this gate must block rather than report success.
        return Verdict(GATE, False, [f"corpus directory {corpus_dir} not found; cannot verify any claim"])

    # Read each source once, from disk, as the authority.
    cache: Dict[str, str] = {}

    resolved_root = corpus_dir.resolve()

    def corpus_text(source_id: str) -> str:
        """Read a source by id, from inside the corpus directory only.

        A source_id goes into a glob pattern, and "../secret" is a perfectly
        legal relative pattern: before this check, such an id read a file
        outside the corpus and G2 then confirmed, correctly, that the quote
        matched. An attacker or a confused extraction could quote any file on
        disk as if it were the subject's words.

        So an id must be a single path component with no separators and no
        parent reference, and the resolved file must still sit under the corpus
        root after symlinks are followed. Both checks, because either alone
        leaves a way through: the first stops the pattern escaping, the second
        stops a symlink inside the corpus pointing out of it.
        """
        if source_id in cache:
            return cache[source_id]
        cache[source_id] = ""
        if (not source_id or "/" in source_id or "\\" in source_id
                or source_id in (".", "..") or source_id.startswith(".")):
            return ""
        for hit in sorted(corpus_dir.glob(f"{source_id}.*")):
            try:
                real = hit.resolve()
                real.relative_to(resolved_root)
            except (OSError, ValueError):
                continue        # outside the corpus, or unreadable: not a source
            if not real.is_file():
                continue
            cache[source_id] = _normalize(real.read_text(encoding="utf-8", errors="replace"))
            break
        return cache[source_id]

    authorship = {str(s.get("id")): s.get("authorship")
                  for s in (sources or []) if s.get("id")}
    checked = inferences = not_own_words = 0
    for i, claim in enumerate(claims):
        label = claim.get("id") or f"<claim #{i}>"
        if claim.get("attribution") == "inference":
            inferences += 1
            continue

        sid = claim.get("source_id")
        quote = claim.get("quote")
        if not sid:
            errors.append(f"{label}: attributed to the subject but names no source_id")
            continue
        if not quote or not str(quote).strip():
            errors.append(f"{label}: names source {sid} but quotes nothing from it")
            continue

        body = corpus_text(str(sid))
        if not body:
            errors.append(f"{label}: source {sid} is not in the corpus directory")
            continue

        checked += 1

        author = authorship.get(str(sid))
        if author in AUTHORSHIP_NOT_OWN_WORDS:
            not_own_words += 1
            if not claim.get("attributed_to_source"):
                errors.append(
                    f"{label}: source {sid} is {author}, so the quote matched is not the "
                    "subject's own words. Set attributed_to_source: true and phrase the "
                    "claim as what the source says, not as what the subject said."
                )

        if _normalize(str(quote)) not in body:
            # Distinguish the one near-miss that is a real integrity problem
            # from a quote that simply is not there.
            if _ELLIPSIS.search(body) and not _ELLIPSIS.search(str(quote)):
                stitched = _normalize(_ELLIPSIS.sub("", body))
                if _normalize(str(quote)) in stitched:
                    errors.append(
                        f"{label}: the quote matches source {sid} only once an ellipsis is "
                        "removed. Dropping an ellipsis asserts that two passages are "
                        "contiguous when the source marks text as elided between them. "
                        "Quote one side, or keep the ellipsis."
                    )
                    continue
            errors.append(f"{label}: quote does not appear verbatim in source {sid}")
            continue

        # The quote is real; now check that the claim's own numbers are too.
        in_source = set(_digits(body))
        for num in _digits(str(claim.get("text", ""))):
            if num not in in_source:
                errors.append(
                    f"{label}: the figure {num} appears in the claim but nowhere in source {sid}"
                )

    if inferences:
        warnings.append(
            f"{inferences} claim(s) marked as inference and exempt from the quote check; "
            "G3 verifies that the output labels them"
        )

    return Verdict(
        GATE,
        not errors,
        errors,
        warnings,
        {"claims": len(claims), "quote_checked": checked, "inferences": inferences,
         "not_the_subjects_own_words": not_own_words},
    )
