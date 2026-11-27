#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G2 -- source anchor reconciliation.

Every claim attributed to the subject must name a source and quote it, and the
quote must appear in that source verbatim.

This gate recomputes independently: it reopens the corpus file from disk and
searches for the quote itself. It does not consult whatever index, offset, or
confidence score the extraction stage produced -- confirming an extraction with
its own bookkeeping is the self-referential gate that always passes.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List

from . import Verdict

GATE = "G2-anchor"

# Numbers carry the most weight and are the easiest thing for a model to invent,
# so they are checked individually on top of the quote check.
_NUM = re.compile(r"\d[\d,._]*\d|\d")


def _normalize(text: str) -> str:
    """Fold the differences that are not substantive, and nothing more.

    Width (full-width vs half-width), compatibility forms, and runs of
    whitespace differ between a web page and its extracted text without the
    wording differing. Case and punctuation are NOT folded: a quote that
    differs in wording is a different quote.
    """
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip()


def _digits(text: str) -> List[str]:
    return [m.group(0).replace(",", "").replace("_", "") for m in _NUM.finditer(text)]


def check(claims: List[Dict[str, Any]], corpus_dir: Path) -> Verdict:
    """Reconcile `claims` against the corpus on disk.

    Each claim needs: `text` (what is being asserted), `source_id`, and `quote`
    (the passage it rests on). A claim may instead be marked
    `attribution: "inference"`, which exempts it from the quote check but
    requires the output to label it as an inference -- G3 checks that label.
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

    def corpus_text(source_id: str) -> str:
        if source_id not in cache:
            hits = sorted(corpus_dir.glob(f"{source_id}.*"))
            cache[source_id] = _normalize(hits[0].read_text(encoding="utf-8", errors="replace")) if hits else ""
        return cache[source_id]

    checked = inferences = 0
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
        if _normalize(str(quote)) not in body:
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
        {"claims": len(claims), "quote_checked": checked, "inferences": inferences},
    )
