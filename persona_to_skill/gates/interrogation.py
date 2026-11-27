#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G5 -- interrogation of the deliberation memo.

The traps this gate exists to catch all hide in fluent prose, which is why
catching them cannot be left to an alert reader:

  * an unsourced claim written as established fact;
  * a recommendation quietly resting on an assumption nobody verified;
  * a hedge ("should be", "usually", "應該是") standing where "I do not know"
    belongs.

Fluency is the camouflage. The more polished a memo reads, the more it needs
this pass.

The gate works off a fixed schema, and the fixedness is the point. People
deciding something look at what they already want to look at, so the fields
anyone would skip -- key assumptions, main risks, what evidence is missing --
have to be made non-skippable. A blank field is visible; a field never asked
for is not.

Two kinds of leak are checked separately, because they are different faults:

  evasion  a field filled with "work it out yourself" phrasing. The judgement
           was dodged.
  hedging  a statement classified as fact while carrying language that means
           not-knowing. The remedy is reclassification, not deletion: a hedged
           statement is an inference or an unknown, and saying so is honest.

Every statement carries one of four classes, and each class owes something:
    FACT            a source, and no hedging
    INFERENCE       what it was derived from
    ASSUMPTION      a verification status
    RECOMMENDATION  the statements it rests on, named at the recommendation
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..contract import (
    ASSUMPTION_STATUSES,
    CONDITIONAL_MARKERS,
    CONFIDENCE_REQUIRING_GAPS_NAMED,
    CONFIDENCE_REQUIRING_NO_GAPS,
    MEMO_EMPTIABLE_FIELDS,
    EVASION_PHRASES,
    HEDGE_MARKERS,
    MEMO_REQUIRED_FIELDS,
    STATEMENT_CLASSES,
    VERDICTS,
    VERDICTS_REQUIRING_FLIP_CONDITION_KNOWN,
)
from . import Verdict

GATE = "G5-interrogation"


def _empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict)):
        return len(value) == 0
    return False


def _text_of(value: Any) -> str:
    """Flatten a field to searchable text without inventing structure."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_text_of(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(_text_of(v) for v in value)
    return str(value) if value is not None else ""


def _found(text: str, needles) -> List[str]:
    low = text.lower()
    return [n for n in needles if (n.lower() in low)]


def check(memo: Dict[str, Any] | None,
          statements: List[Dict[str, Any]] | None = None) -> Verdict:
    """Interrogate the memo being delivered.

    `memo` holds the fields in contract.MEMO_REQUIRED_FIELDS. `statements` is
    the classified breakdown of its prose; absent, the classification rules
    cannot run and the gate blocks rather than passing the part it did check.
    """
    if memo is None:
        return Verdict(GATE, False, ["no memo supplied; nothing to interrogate"])
    if not isinstance(memo, dict):
        return Verdict(GATE, False, ["memo must be a mapping of fields"])
    if statements is None:
        # Fail closed. Three of the five rules live in the classification, so a
        # pass here would report on a memo whose prose was never examined.
        return Verdict(
            GATE, False,
            ["no classified statements supplied. Every claim in the memo must carry one "
             f"of {list(STATEMENT_CLASSES)}; without that breakdown the unsourced-fact "
             "and hidden-assumption checks cannot run, and the traps they catch are the "
             "ones that hide in fluent prose."],
        )

    errors: List[str] = []
    warnings: List[str] = []

    # ------------------------------------------ R1  no field left unanswered
    # Answered, not non-empty. For a field where "none" is a real answer, an
    # explicit empty value counts and a missing key does not: the skip is what
    # this has to make visible, and forcing content would only invent some.
    for key, zh in MEMO_REQUIRED_FIELDS.items():
        if key not in memo:
            errors.append(f"required field {key!r} ({zh}) was never answered")
        elif _empty(memo.get(key)) and key not in MEMO_EMPTIABLE_FIELDS:
            errors.append(f"required field {key!r} ({zh}) is empty")

    # --------------------------------------------- R2  no field filled by evasion
    for key, zh in MEMO_REQUIRED_FIELDS.items():
        text = _text_of(memo.get(key))
        if not text.strip():
            continue
        hits = _found(text, EVASION_PHRASES)
        if hits:
            if _found(text, CONDITIONAL_MARKERS):
                warnings.append(
                    f"{key} ({zh}) uses {hits[0]!r} but does go on to state conditions; "
                    "check the conditions actually cover the case"
                )
            else:
                errors.append(
                    f"{key} ({zh}) is filled with {hits[0]!r}, which decides nothing. "
                    "Expand it into concrete conditions."
                )

    # ------------------------- R3  flip condition unknown forbids a committing verdict
    flip = memo.get("flip_condition")
    rec = memo.get("recommendation")
    verdict_value = rec.get("verdict") if isinstance(rec, dict) else None

    if isinstance(flip, dict):
        if _empty(flip.get("quantity")):
            errors.append("flip_condition names no quantity: what number decides this")
        if _empty(flip.get("threshold")):
            errors.append("flip_condition names no threshold for its quantity")
        known = flip.get("known")
        if not isinstance(known, bool):
            errors.append("flip_condition.known must be true or false: is the number in hand")
        elif known is False and verdict_value in VERDICTS_REQUIRING_FLIP_CONDITION_KNOWN:
            errors.append(
                f"verdict {verdict_value} commits to the decision while the quantity that "
                f"decides it ({flip.get('quantity')!r}) is still unknown. The honest output "
                "is INVESTIGATE or DEFER: what is missing here is a number, not an opinion."
            )
    elif not _empty(flip):
        errors.append("flip_condition must be an object with quantity, threshold and known")

    if verdict_value is not None and verdict_value not in VERDICTS:
        errors.append(f"unknown verdict {verdict_value!r}; expected one of {list(VERDICTS)}")

    # ------------------------------ R4  confidence must be coherent with the gaps
    conf = memo.get("confidence")
    level = conf.get("level") if isinstance(conf, dict) else conf
    if isinstance(level, bool) or not isinstance(level, (int, float)):
        if not _empty(conf):
            errors.append("confidence.level must be a number between 0 and 1")
    else:
        if not 0.0 <= float(level) <= 1.0:
            errors.append(f"confidence.level {level} is outside 0 to 1")
        if isinstance(conf, dict) and _empty(conf.get("rationale")):
            errors.append("confidence states a level with no rationale for why that level")
        if float(level) >= CONFIDENCE_REQUIRING_NO_GAPS and not _empty(memo.get("evidence_gaps")):
            errors.append(
                f"confidence {float(level):.0%} is claimed while evidence_gaps is not empty. "
                "That is incoherent rather than optimistic: either the gaps do not bear on "
                "the decision, and belong elsewhere, or the confidence is lower than stated."
            )
        # The mirror image, and the reason an empty gap list cannot simply be
        # left blank to get past R1. Unsure about something means something is
        # missing; naming it is the whole job.
        if float(level) < CONFIDENCE_REQUIRING_GAPS_NAMED and "evidence_gaps" in memo \
                and _empty(memo.get("evidence_gaps")):
            errors.append(
                f"confidence {float(level):.0%} is stated while evidence_gaps is empty. "
                "Something is making this uncertain: name it. If nothing is missing, the "
                "confidence is higher than stated."
            )

    # ------------------------------------- R5  per-class obligations on statements
    seen_ids = set()
    for i, st in enumerate(statements):
        sid = st.get("id") or f"<statement #{i}>"
        seen_ids.add(st.get("id"))
        cls = st.get("class")
        text = _text_of(st.get("text"))

        if cls not in STATEMENT_CLASSES:
            errors.append(f"{sid}: class {cls!r} is not one of {list(STATEMENT_CLASSES)}")
            continue

        if cls == "FACT":
            if _empty(st.get("source_id")):
                errors.append(
                    f"{sid}: classified FACT with no source. An unsourced claim written as "
                    "established fact is the first trap; reclassify it as INFERENCE or "
                    "UNKNOWN, or cite it."
                )
            hedges = _found(text, HEDGE_MARKERS)
            if hedges:
                errors.append(
                    f"{sid}: classified FACT while hedging with {hedges[0]!r}. Hedged "
                    "language reads as knowing and means not knowing. This is an "
                    "INFERENCE or an UNKNOWN, and saying so is the honest version."
                )
        elif cls == "INFERENCE":
            if _empty(st.get("derived_from")):
                errors.append(f"{sid}: classified INFERENCE but names nothing it was derived from")
        elif cls == "ASSUMPTION":
            status = st.get("status")
            if status not in ASSUMPTION_STATUSES:
                errors.append(
                    f"{sid}: classified ASSUMPTION with status {status!r}; expected one of "
                    f"{list(ASSUMPTION_STATUSES)}. An assumption whose status is unstated is "
                    "being used as a premise without admitting it."
                )

    # ------------------- R5b  a recommendation must stand on something, in place
    if isinstance(rec, dict):
        depends = rec.get("depends_on")
        if _empty(depends):
            errors.append(
                "recommendation names nothing it depends on. Listing the basis in other "
                "fields does not work: nobody reading a recommendation scrolls back to "
                "check what it stands on."
            )
        elif isinstance(depends, (list, tuple)):
            by_id = {st.get("id"): st for st in statements if st.get("id")}
            unverified: List[str] = []
            for ref in depends:
                if ref not in by_id:
                    errors.append(f"recommendation depends on {ref!r}, which is not a statement")
                    continue
                st = by_id[ref]
                if st.get("class") == "ASSUMPTION" and st.get("status") == "unverified":
                    unverified.append(str(ref))
            if unverified:
                if _empty(rec.get("unverified_dependencies")):
                    errors.append(
                        "recommendation rests on unverified assumption(s) "
                        f"({', '.join(unverified)}) without saying so at the recommendation. "
                        "Name them in unverified_dependencies."
                    )
                else:
                    declared = {str(x) for x in rec["unverified_dependencies"]}
                    undeclared = [u for u in unverified if u not in declared]
                    if undeclared:
                        errors.append(
                            "recommendation does not declare unverified assumption(s) it "
                            f"rests on: {', '.join(undeclared)}"
                        )

    return Verdict(
        GATE, not errors, errors, warnings,
        {
            "fields_present": sum(1 for k in MEMO_REQUIRED_FIELDS if not _empty(memo.get(k))),
            "fields_required": len(MEMO_REQUIRED_FIELDS),
            "statements": len(statements),
            "verdict": verdict_value,
            "confidence": level if isinstance(level, (int, float)) and not isinstance(level, bool) else None,
        },
    )
