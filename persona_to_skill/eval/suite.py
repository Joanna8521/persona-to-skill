#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reconcile an eval manifest against a recorded run.

### What this module refuses to do

It does not answer the questions, and it does not decide whether an answer
matched. Both come from outside, in the run file. A harness that produced its
own observations would be measuring itself, and the output would be a
self-report wearing a percentage sign.

That restraint is the whole design. Everything below is about making sure the
observations that arrive are the kind that can carry a number.

### The four ways a run stops counting, and why each is separate

    MISSING       The manifest asks it; the run has no entry. Not a failure and
                  not a pass: nobody looked. It leaves the denominator, exactly
                  as G4 treats a null observation, and is reported on its own so
                  a thin run reads as thin rather than as bad.

    UNJUDGED      An entry exists, with no judged_by. Someone decided "this
                  matches" and the instrument is unnamed, so the decision cannot
                  be checked. Counted, never scored.

    NOT BLIND     The judge knew which answer came from the reconstruction. This
                  is the one that actually protects the number. Told which
                  candidate is the one under test, a judge has been handed the
                  result the experiment was supposed to produce, and a model
                  judge is no more resistant to that than a person. Counted,
                  reported, never gated, which is the treatment G4 already gives
                  material that was seen during extraction.

    SEEN          The material was used to build the skill. Alignment on it is
                  evidence of nothing. G4 already excludes these; the harness
                  passes the flag through rather than deciding again.

Collapsing any two of those into one number would hide which defect a run has,
and they need different fixes: write more items, name your judge, blind your
judge, hold the material back.

### Extra questions are refused outright

A run entry whose id is not in the manifest is an error, not a warning. The
manifest is the question set the subject's answers were pinned to; an answer to
some other question has no ground truth here, and scoring it would silently
measure something nobody specified.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ..contract import (
    EVAL_MANIFEST_REQUIRED_FIELDS,
    EVAL_OBSERVATION_VALUES,
    EVAL_RUN_REQUIRED_FIELDS,
)
from ..gates import anchor


class EvalError(ValueError):
    """A manifest or run that cannot be scored. Raised rather than returned:
    a caller that ignored a return value would score garbage."""


def _as_items(data: Any, what: str) -> List[Dict[str, Any]]:
    """Accept a bare list or {"items": [...]}, and nothing else."""
    if isinstance(data, dict):
        data = data.get("items")
    if not isinstance(data, list):
        raise EvalError(
            f"{what}: expected a list of items, or an object with an "
            f'"items" list')
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise EvalError(f"{what}: item {i} is not an object")
    return data


def _read(path: str | Path, what: str) -> Any:
    p = Path(path)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise EvalError(f"{what}: no such file: {p}") from None
    except json.JSONDecodeError as exc:
        raise EvalError(f"{what}: not valid JSON: {exc}") from None


def _require_fields(item: Dict[str, Any], fields: Tuple[str, ...],
                    what: str, index: int) -> None:
    missing = [f for f in fields if f not in item]
    if missing:
        ident = item.get("id") or f"index {index}"
        raise EvalError(f"{what} {ident}: missing {', '.join(missing)}")


def _unique_ids(items: List[Dict[str, Any]], what: str) -> None:
    seen = set()
    for item in items:
        i = item.get("id")
        if not isinstance(i, str) or not i.strip():
            raise EvalError(f"{what}: an item has no usable id")
        if i in seen:
            raise EvalError(
                f"{what}: duplicate id {i!r}. Two entries for one question "
                f"means one of them silently wins, and which one depends on "
                f"iteration order.")
        seen.add(i)


def load_manifest(path: str | Path) -> List[Dict[str, Any]]:
    """The question set, with what the subject actually said."""
    items = _as_items(_read(path, "manifest"), "manifest")
    if not items:
        raise EvalError("manifest: no items. An empty question set cannot "
                        "support a claim about anything.")
    for i, item in enumerate(items):
        _require_fields(item, EVAL_MANIFEST_REQUIRED_FIELDS, "manifest item", i)
        if not str(item.get("subject_said") or "").strip():
            raise EvalError(
                f"manifest item {item['id']}: subject_said is empty. The "
                f"ground truth has to be a quote, or the comparison rests on "
                f"nothing.")
        if not str(item.get("source_id") or "").strip():
            raise EvalError(
                f"manifest item {item['id']}: no source_id. An unanchored "
                f"ground truth is the failure this project exists to prevent.")
    _unique_ids(items, "manifest")
    return items


def load_run(path: str | Path) -> List[Dict[str, Any]]:
    """The observations, recorded outside this tool."""
    items = _as_items(_read(path, "run"), "run")
    for i, item in enumerate(items):
        _require_fields(item, EVAL_RUN_REQUIRED_FIELDS, "run item", i)
        for field in ("aligned", "baseline_aligned"):
            # `is`, not `in`. `1 in (True, False, None)` is True in Python,
            # because 1 == True, so membership would accept a JSON 1 as an
            # observation and it would then be summed as an alignment.
            #
            # That is the exact hazard this project's own holdout module
            # documents, and it bit here, inside the validator written to
            # prevent it. Identity comparison is the fix: 1 is True is False.
            if not any(item[field] is ok for ok in EVAL_OBSERVATION_VALUES):
                raise EvalError(
                    f"run item {item['id']}: {field} is {item[field]!r}. It "
                    f"must be true, false, or null. A string is refused on "
                    f'purpose: "yes" and "probably" are not observations, and '
                    f"coercing either would invent the measurement.")
        if not isinstance(item["blind"], bool):
            raise EvalError(
                f"run item {item['id']}: blind is {item['blind']!r}, not a "
                f"boolean. Whether the judge knew which answer was which is "
                f"the field that protects the number; it cannot be left vague.")
    _unique_ids(items, "run")
    return items


def reconcile(manifest: List[Dict[str, Any]],
              run: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Join the two and return items in the shape G4's score() reads.

    Returns {"items": [...], "missing": [...], "unjudged": [...],
             "not_blind": [...], "judges": [...]}.

    The four lists are ids, not counts, because the next question after "how
    many" is always "which ones".
    """
    by_id = {m["id"]: m for m in manifest}
    extra = [r["id"] for r in run if r["id"] not in by_id]
    if extra:
        raise EvalError(
            f"run has {len(extra)} item(s) the manifest does not ask: "
            f"{', '.join(sorted(extra)[:5])}"
            f"{'...' if len(extra) > 5 else ''}. The manifest is the question "
            f"set the subject's answers were pinned to, so an answer to some "
            f"other question has no ground truth here.")

    run_by_id = {r["id"]: r for r in run}
    items: List[Dict[str, Any]] = []
    missing, unjudged, not_blind = [], [], []
    judges = set()

    for m in manifest:
        mid = m["id"]
        r = run_by_id.get(mid)
        base = {
            "id": mid,
            "seat": m.get("seat"),
            "seen_in_extraction": m.get("seen_in_extraction") is True,
        }
        if r is None:
            # Nobody looked. Not a failure, not a pass. G4 reads `aligned`
            # as UNKNOWN when it is absent, so absence is passed through
            # rather than filled in.
            missing.append(mid)
            items.append(base)
            continue

        judged_by = str(r.get("judged_by") or "").strip()
        if not judged_by:
            unjudged.append(mid)
            items.append(base)  # aligned stays absent: UNKNOWN
            continue
        judges.add(judged_by)

        if not r["blind"]:
            not_blind.append(mid)
            items.append(base)  # counted, reported, never gated
            continue

        items.append(dict(base, aligned=r["aligned"],
                          baseline_aligned=r["baseline_aligned"]))

    return {
        "items": items,
        "missing": missing,
        "unjudged": unjudged,
        "not_blind": not_blind,
        "judges": sorted(judges),
    }


def anchor_manifest(manifest: List[Dict[str, Any]], corpus_dir: str | Path,
                    sources: List[Dict[str, Any]] | None = None):
    """Check every ground truth against the corpus, through G2.

    The ground truth is a claim like any other: "the subject said X, in source
    Y". If that quote is not in that source, the whole comparison downstream
    rests on an unverified assertion, which is the one failure this project
    exists to make impossible. An eval suite is not exempt from the gate just
    because it is the thing doing the measuring.

    G2 is reused rather than reimplemented. A second quote-matching routine
    would drift from the first, and it would drift in the direction that makes
    a suite easier to write, which is the wrong direction.

    Note what this does NOT check: whether the question was genuinely held back
    from extraction. Nothing in the files can show that, and the harness says
    so rather than implying the flag was verified. `seen_in_extraction` is the
    author's declaration, and a run where everything is flagged seen scores
    nothing at all, which is the honest outcome.
    """
    claims = [
        {
            # `id` is the eval item, so a failure names which item is
            # unanchored rather than making the reader find it.
            "id": m["id"],
            # `text` is the QUOTE, not the question.
            #
            # The first version put the question here, reasoning that a failure
            # should name the item. It does name it, through `id`. And putting
            # the question in `text` broke G2's figure check, which requires
            # every number in the claim to appear in the source: "Question 1
            # put to the subject?" contains a 1, src1 did not, and all fourteen
            # items failed on their own question numbers.
            #
            # The deeper error was semantic. G2's `text` is what rests on the
            # source. For an eval item that is the subject's quote, and the
            # figure check then does exactly what it should: a quoted figure
            # the source does not contain is a fabricated ground truth, which
            # would be the worst kind to have.
            "text": m["subject_said"],
            "source_id": m["source_id"],
            "quote": m["subject_said"],
        }
        for m in manifest
    ]
    return anchor.check(claims, Path(corpus_dir), sources)
