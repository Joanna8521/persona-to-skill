#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""What a source is, measured rather than taken on trust.

A transcript is a rendering of what was said, not the thing itself, so a quote
from one is a quote of the rendering. How much that matters varies: a reviewed
caption track reads like prose, an unreviewed stream does not.

The tempting shortcut is YouTube's `trackKind`, which marks a track `ASR` or
`standard`. Do not build on it. Whether editing an auto-generated track
reclassifies it is not documented anywhere we could find, so the label may say
"automatic" about a track someone corrected line by line.

So the artifact is measured instead. What the measurement establishes, and what
it does not, matters more than the numbers:

    IT DOES establish anchorability. Text with sentence-ending punctuation and
    sentence casing can support G2's quote reconciliation. An uncapitalised,
    unpunctuated stream cannot: there are no sentence boundaries to quote
    between, and the words themselves are a guess.

    IT DOES NOT establish human review. Current speech recognition punctuates
    its own output, so punctuation is evidence of a punctuating producer, human
    or otherwise. Anyone reading `anchorable` as "a person checked this" is
    reading more than is here.

That distinction is the whole reason this module reports a consequence for
QUOTING rather than a level of trust. Trust in the content is G2's and G5's
business, on evidence; this is about whether their checks can run at all.

Thresholds come from measurement, not from judgement. Across ~190k characters
of real human-written text in two languages (three essays, one encyclopaedia
article, one human transcript of a talk), sentence-ending marks per hundred
characters ran:

    essays, English          1.02, 1.03, 1.04
    encyclopaedia, Chinese   1.85
    talk transcript, human   1.58

and the same texts with punctuation stripped measured exactly 0.00. The
separation is absolute rather than graded, so the bar sits far below the lowest
observed human value, where any cut in that gap behaves identically.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

SENTENCE_END = re.compile(r"[.!?。！？]")
_SENTENCE_START = re.compile(r"[.!?]\s+([A-Za-z])")
_CJK = re.compile(r"[一-鿿㐀-䶿]")

# Lowest observed in real human text: 1.02 per 100 characters. Unpunctuated
# text measures 0.00 exactly. The bar is set at roughly a third of the lowest
# real value: comfortably clear of prose, unreachable without punctuation.
MIN_SENTENCE_DENSITY = 0.30

# Of the positions following a sentence end, how many begin with a capital.
# Real texts measured 87% (Chinese, where most sentences start with a character
# that has no case) to 100%. Applies only where there are Latin sentence starts
# to count; Chinese alone yields none, and the field stays None rather than
# being scored.
MIN_SENTENCE_CASING = 0.50

# A short source is anchorable whatever its punctuation, and the density test
# does not apply to it.
#
# This was a real error, not a missing feature. A 40-character post with no
# full stop measured 0.00 and was called unanchorable, when in fact it is the
# easiest thing in the world to quote: the unit of quotation is the whole
# source. Density answers "can a quote be located between sentence
# boundaries", and that question only arises once a source is long enough for
# the location to be in doubt.
#
# PROVISIONAL. 1000 characters is a guess that comfortably covers a social post
# or a short comment while staying well below anything where locating a quote
# needs sentence structure. What would settle it: take real sources either side
# of the line and find where ambiguity about a quote's position actually
# starts.
SHORT_SOURCE_CHARS = 1000

# How a source may be stored, and what each can support.
#   text              prose as published
#   transcript        a rendering of speech, anchorable or not per measurement
#   ocr               characters recovered from an image
KINDS = ("text", "transcript", "ocr")


@dataclass
class Provenance:
    """What was measured about one source. No verdict on its honesty."""
    kind: str
    chars: int
    sentence_density: float
    sentence_casing: Optional[float]
    cjk_ratio: float
    cue_segmented: bool = False
    cues_joined: int = 0
    declared_track_kind: Optional[str] = None   # recorded, never relied upon
    notes: List[str] = field(default_factory=list)

    @property
    def anchorable(self) -> bool:
        """Can G2 reconcile a quote against this source at all.

        Not a judgement about the source's accuracy, and not a claim that a
        person reviewed it.
        """
        if self.chars == 0:
            return False
        if self.chars <= SHORT_SOURCE_CHARS:
            # Nothing to locate between: the whole source is the quotable unit.
            return True
        if self.sentence_density < MIN_SENTENCE_DENSITY:
            return False
        if self.sentence_casing is not None and self.sentence_casing < MIN_SENTENCE_CASING:
            return False
        return True

    @property
    def why_not_anchorable(self) -> List[str]:
        out: List[str] = []
        if self.chars == 0:
            return ["the source is empty"]
        if self.chars <= SHORT_SOURCE_CHARS:
            return []
        if self.sentence_density < MIN_SENTENCE_DENSITY:
            out.append(
                f"{self.sentence_density:.2f} sentence-ending marks per 100 characters, "
                f"below {MIN_SENTENCE_DENSITY}. Real human-written text measures 1.02 or "
                "above; unpunctuated output measures zero. Without sentence boundaries "
                "there is nothing to quote between, so a quote cannot be reconciled "
                "against this source."
            )
        if self.sentence_casing is not None and self.sentence_casing < MIN_SENTENCE_CASING:
            out.append(
                f"{self.sentence_casing:.0%} of sentence starts are capitalised, below "
                f"{MIN_SENTENCE_CASING:.0%}. Taken with the density figure this is "
                "recognition output nobody has punctuated."
            )
        return out

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "kind": self.kind,
            "chars": self.chars,
            "sentence_density": round(self.sentence_density, 3),
            "sentence_casing": None if self.sentence_casing is None else round(self.sentence_casing, 3),
            "cjk_ratio": round(self.cjk_ratio, 3),
            "cue_segmented": self.cue_segmented,
            "cues_joined": self.cues_joined,
            "anchorable": self.anchorable,
        }
        if self.declared_track_kind is not None:
            # Carried through for the record. Nothing above reads it.
            d["declared_track_kind"] = self.declared_track_kind
        if self.notes:
            d["notes"] = list(self.notes)
        if not self.anchorable:
            d["why_not_anchorable"] = self.why_not_anchorable
        return d


def measure(text: str, kind: str = "text", **extra: Any) -> Provenance:
    """Measure one source's stored text.

    `extra` may carry cue_segmented, cues_joined, declared_track_kind, notes.
    """
    if kind not in KINDS:
        raise ValueError(f"unknown source kind {kind!r}; expected one of {list(KINDS)}")

    t = (text or "").strip()
    n = len(t)
    density = (len(SENTENCE_END.findall(t)) / n * 100) if n else 0.0

    starts = _SENTENCE_START.findall(t)
    casing = (sum(1 for c in starts if c.isupper()) / len(starts)) if starts else None

    cjk = (len(_CJK.findall(t)) / n) if n else 0.0

    return Provenance(
        kind=kind,
        chars=n,
        sentence_density=density,
        sentence_casing=casing,
        cjk_ratio=cjk,
        cue_segmented=bool(extra.get("cue_segmented", False)),
        cues_joined=int(extra.get("cues_joined", 0)),
        declared_track_kind=extra.get("declared_track_kind"),
        notes=list(extra.get("notes") or []),
    )
