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
    CONFIDENCE_REQUIRING_GAPS_NAMED,
    CONFIDENCE_REQUIRING_NO_GAPS,
    EVASION_PHRASES,
    GAP_PERIPHERAL_KEY,
    HEDGE_MARKERS,
    MEMO_EMPTIABLE_FIELDS,
    MEMO_LOAD_BEARING_FIELDS,
    MEMO_REQUIRED_FIELDS,
    STATEMENT_CLASSES,
    THRESHOLD_NUMBER,
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


def _gaps_bearing_on_decision(gaps: Any) -> List[str]:
    """Which gaps count against a confident verdict.

    A gap is peripheral only when it says so. A bare string, or an object that
    omits the key, bears on the decision -- fail closed, so the way to reconcile
    a gap with high confidence is to mark it, not to remove it.
    """
    out: List[str] = []
    if not isinstance(gaps, (list, tuple)):
        gaps = [gaps] if gaps else []
    for g in gaps:
        if isinstance(g, dict):
            if g.get(GAP_PERIPHERAL_KEY) is False:
                continue
            out.append(_text_of(g.get("gap") or g.get("text") or g))
        elif g:
            out.append(_text_of(g))
    return out


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
        # The two load-bearing fields are named as such when they are the ones
        # missing. A memo without a flip condition or without a confidence
        # level is not one field short, it is missing the part that makes the
        # rest readable, and the message should not hide that among eleven
        # others.
        weight = " (load-bearing)" if key in MEMO_LOAD_BEARING_FIELDS else ""
        if key not in memo:
            errors.append(f"required field {key!r} ({zh}){weight} was never answered")
        elif _empty(memo.get(key)) and key not in MEMO_EMPTIABLE_FIELDS:
            errors.append(f"required field {key!r} ({zh}){weight} is empty")

    # ------------------------------------------------- R2  evasion, as a floor
    # Lexical, therefore a floor rather than a detector: the list is public and
    # so gameable, and it trips on mention as well as use. It blocks only where
    # the field's whole content is the phrase, which is unambiguous; otherwise
    # it warns. See the note on EVASION_PHRASES for why no structural
    # replacement is offered instead of this honest limit.
    for key, zh in MEMO_REQUIRED_FIELDS.items():
        text = _text_of(memo.get(key))
        stripped = text.strip()
        if not stripped:
            continue
        hits = _found(text, EVASION_PHRASES)
        if not hits:
            continue
        bare = all(
            stripped.strip("。．.,，、;；:：!！?？ \t\n「」\"'()（）") .lower() == h.lower()
            for h in hits[:1]
        )
        if bare:
            errors.append(
                f"{key} ({zh}) contains nothing but {hits[0]!r}, which decides nothing. "
                "Expand it into concrete conditions."
            )
        else:
            warnings.append(
                f"{key} ({zh}) uses {hits[0]!r}. If that phrase is carrying the field, "
                "expand it into concrete conditions; this check is lexical and cannot "
                "tell a dodge from a mention."
            )

    # ------------------------- R3  flip condition unknown forbids a committing verdict
    flip = memo.get("flip_condition")
    rec = memo.get("recommendation")
    verdict_value = rec.get("verdict") if isinstance(rec, dict) else None

    if isinstance(flip, dict):
        if _empty(flip.get("quantity")):
            errors.append("flip_condition names no quantity: what number decides this")
        threshold = flip.get("threshold")
        if _empty(threshold):
            errors.append("flip_condition names no threshold for its quantity")
        elif not THRESHOLD_NUMBER.search(_text_of(threshold)):
            # Structural, and sound: a threshold without a number is not one.
            errors.append(
                f"flip_condition threshold {_text_of(threshold)!r} contains no number. "
                "A threshold is the value the quantity is compared against; without one "
                "there is nothing to go and find out."
            )
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
        if float(level) >= CONFIDENCE_REQUIRING_NO_GAPS:
            bearing = _gaps_bearing_on_decision(memo.get("evidence_gaps"))
            if bearing:
                errors.append(
                    f"confidence {float(level):.0%} is claimed while "
                    f"{len(bearing)} evidence gap(s) bear on the decision: "
                    + "; ".join(bearing[:3])
                    + ". Either mark a gap "
                    f"{{{GAP_PERIPHERAL_KEY!r}: false}} where it genuinely does not affect "
                    "this decision, or state the lower confidence. Deleting the gap is not "
                    "the third option."
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
            "load_bearing_answered": sorted(
                k for k in MEMO_LOAD_BEARING_FIELDS if not _empty(memo.get(k))),
            "confidence": level if isinstance(level, (int, float)) and not isinstance(level, bool) else None,
        },
    )
