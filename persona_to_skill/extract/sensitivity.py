#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Which number decides it, and roughly where the line sits.

Most hesitation is not disagreement. Someone stuck on a decision usually has
the arguments already and is missing a quantity, which is why a third opinion
changes nothing and one lookup changes everything.

That reframes what a practitioner is worth. Not their view, which is often
consensus and which a general model already holds. What they have is knowing,
for this class of decision, which single quantity decides it and roughly where
the line falls. That claim is bounded and checkable, unlike "thinks like X",
and it hands the user something they can act on alone.

It also fixes the default behaviour. When the deciding number is not in hand,
the honest output is "go and find this out", not advice. An impersonating
reconstruction gives advice there, because advice feels like helping.

A threshold has to contain a number. That is what puts this file under G2's
figure check: a threshold the corpus does not contain cannot be written down,
so the most valuable field is also the one hardest to invent.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..contract import SENSITIVITY_REQUIRED_FIELDS, THRESHOLD_NUMBER
from ..gates import Verdict

GATE = "B-sensitivity"

# Which way the threshold cuts. A bare number decides nothing: "CAC of 1,200"
# is not a rule until you know whether above or below it stops the project.
DIRECTIONS = ("above_stops", "below_stops", "above_proceeds", "below_proceeds")

# Phrasings that look like a quantity and name none.
_VAGUE = (
    "market conditions", "the economy", "team capacity", "overall risk",
    "customer sentiment", "competitive landscape",
    "市場狀況", "大環境", "團隊狀況", "整體風險", "客戶觀感", "競爭態勢",
)


def _vague_hits(text: str) -> List[str]:
    low = text.lower()
    return [v for v in _VAGUE if v.lower() in low]


def check(records: List[Dict[str, Any]] | None) -> Verdict:
    """Validate the flip-condition records.

    `None` blocks and an empty list blocks, and they block for the same reason:
    a reconstruction with no flip condition has not extracted the thing worth
    extracting. If the corpus genuinely never shows the subject naming a
    deciding quantity, that is a finding about a thin corpus and belongs in the
    unfilled-seat report, not in a silent absence here.
    """
    if records is None:
        return Verdict(GATE, False, ["no sensitivity records supplied"])
    if not isinstance(records, (list, tuple)):
        return Verdict(GATE, False, ["sensitivity records must be a list"])
    if not records:
        return Verdict(GATE, False, [
            "no flip conditions extracted. This is the output that turns a decision "
            "someone is stuck on into one lookup they can do themselves; a reconstruction "
            "without any has not found what it was looking for. If the corpus never shows "
            "the subject naming a deciding quantity, say so in the unfilled-seat report "
            "rather than leaving this empty."])

    errors: List[str] = []
    warnings: List[str] = []
    known = unknown = 0
    classes: Dict[str, int] = {}

    for i, rec in enumerate(records):
        label = (rec.get("id") if isinstance(rec, dict) else None) or f"<sensitivity #{i}>"
        if not isinstance(rec, dict):
            errors.append(f"{label}: must be an object")
            continue

        for field in SENSITIVITY_REQUIRED_FIELDS:
            if not str(rec.get(field, "") or "").strip():
                errors.append(f"{label}: missing {field!r}")

        quantity = str(rec.get("quantity") or "")
        vague = _vague_hits(quantity)
        if vague:
            errors.append(
                f"{label}: quantity {quantity!r} names no number. {vague[0]!r} is a topic, "
                "not a quantity: nobody can go and look it up. Name the measurement.")

        threshold = str(rec.get("threshold") or "")
        if threshold.strip() and not THRESHOLD_NUMBER.search(threshold):
            errors.append(
                f"{label}: threshold {threshold!r} contains no number. A threshold is the "
                "value the quantity is compared against; without one there is nothing to "
                "go and find out, and nothing for G2 to check against the corpus.")

        direction = rec.get("direction")
        if direction and direction not in DIRECTIONS:
            errors.append(f"{label}: direction {direction!r} must be one of "
                          f"{list(DIRECTIONS)}. A bare number decides nothing until you "
                          "know which side of it stops the decision.")

        in_hand = rec.get("known")
        if in_hand is True:
            known += 1
            if not str(rec.get("observed_value") or "").strip():
                errors.append(f"{label}: marked known with no observed_value")
        elif in_hand is False:
            unknown += 1
            if not str(rec.get("how_to_find") or "").strip():
                warnings.append(
                    f"{label}: the deciding number is not in hand and the record does not "
                    "say how to get it. Naming the lookup is most of the value here.")
        else:
            errors.append(f"{label}: known must be true or false. Whether the number is in "
                          "hand decides whether the output is advice or a lookup.")

        cls = str(rec.get("decision_class") or "").strip()
        if cls:
            classes[cls] = classes.get(cls, 0) + 1

    for cls, n in sorted(classes.items()):
        if n > 1:
            warnings.append(
                f"decision class {cls!r} has {n} flip conditions. More than one quantity "
                "deciding the same class usually means the class is drawn too wide; "
                "check whether it is really two classes.")

    return Verdict(GATE, not errors, errors, warnings,
                   {"records": len(records), "number_in_hand": known,
                    "awaiting_lookup": unknown, "decision_classes": len(classes)})
