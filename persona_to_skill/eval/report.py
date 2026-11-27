#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render a holdout score so that an outsider can see what it rests on.

### Why the report is part of the harness rather than an afterthought

The gated figure is one number, and one number invites the reader to stop. What
decides whether that number means anything is everything around it: how many
items were scored, how many were not and for which of four distinct reasons,
how the divergent pool compares with the consensus pool, and who judged.

So the report leads with the gated figure and then shows what would change it.
The consensus figure is printed next to it and labelled as not gated, because
the alternative is that someone quotes the flattering number by accident.

### Nothing here computes

Every value is passed in, from gates.holdout.score and eval.suite.reconcile. A
report that recomputed anything would be a second implementation of the score,
and the two would drift in exactly the direction that makes a build look better.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..contract import HOLDOUT_MIN_ALIGNMENT, HOLDOUT_MIN_DIVERGENT_ITEMS


def _pct(value: Any) -> str:
    """None is "not measured", never 0%.

    0% reads as "measured, and bad", which is a different claim and a worse
    one to make by accident.
    """
    return "not measured" if value is None else f"{value * 100:.0f}%"


def _row(name: str, pool: Dict[str, Any], gated: bool) -> str:
    """One pool's row. The Gated column is the point of the table: without it a
    reader has no way to tell which of the two figures the gate reads."""
    mark = "**yes**" if gated else "no"
    return (f"| {name} | {pool['aligned']} | {pool['diverged']} | "
            f"{pool['scored']} | {_pct(pool['alignment'])} | {mark} |")


def _ids(label: str, ids: List[str], why: str) -> List[str]:
    if not ids:
        return []
    shown = ", ".join(f"`{i}`" for i in ids[:8])
    more = f" (+{len(ids) - 8} more)" if len(ids) > 8 else ""
    return [f"### {label} — {len(ids)}", "", why, "", shown + more, ""]


# ── the prose, named ────────────────────────────────────
#
# These were written inline, as multi-line strings inside the `lines` list.
# CodeQL flagged every one of them: implicit string concatenation in a list is
# ambiguous, because a wrapped string and a missing comma look identical.
#
# It was right, and the hazard is the silent kind. A stray comma turns one
# paragraph into two list entries, which renders as two paragraphs. A missing
# comma merges two entries into one. Neither raises anything; the report just
# comes out subtly different, and this report exists to be read closely.
#
# Naming them fixes the ambiguity and makes the template readable: the prose is
# the valuable part of this module, and the structure of the document is now
# visible in one screen of `lines`.

WHY_DIVERGENT = (
    "This is alignment on questions where a model with no reconstruction "
    "loaded answered *wrongly*. It is the lift over baseline, measured "
    "directly rather than subtracted."
)

WHY_CONSENSUS_NOT_GATED = (
    "The consensus pool is where a model with no reconstruction was already "
    "right. Alignment there is evidence of nothing, which is why it is "
    "reported and never gated: most of what any practitioner says out loud is "
    "consensus, so pooling the two produces a flattering grade for an empty "
    "shell."
)

WHY_FOUR_REASONS = (
    "Four different defects, four different fixes: write more items, name your "
    "judge, blind your judge, hold the material back. Collapsing them into one "
    "number would hide which one a run has."
)

WHY_TWO_TABLES = (
    "The first four rows are the same items as the total beneath them, not "
    "additional ones. They are shown separately because the total alone says a "
    "run is thin without saying why, and the two tables are kept apart because "
    "the second is not about missing observations at all: those items were "
    "observed and then set aside."
)

WHY_MISSING = (
    "The manifest asks these and the run has no entry. Not a failure and not a "
    "pass: nobody looked."
)

WHY_UNJUDGED = (
    "Something decided these matched and the instrument is unnamed, so the "
    "decision cannot be checked."
)

WHY_NOT_BLIND = (
    "The judge knew which answer came from the reconstruction. A judge told "
    "which candidate is under test has been handed the result the experiment "
    "was supposed to produce."
)

NO_JUDGE_AT_ALL = (
    "No judge is named anywhere in this run, so nothing above is a measurement."
)

HOW_TO_READ_A_THIN_REPORT = (
    "A low unobserved share with few scored items means the question set is "
    "small. A high unobserved share means the run is incomplete. Those are "
    "different problems and the table above distinguishes them, because a "
    "reconstruction should not be blamed for a thin question set, and a thin "
    "question set should not pass as a reconstruction."
)

NOT_MEASURED = "not measured: no divergent item carried a blind, judged observation"


def _too_few(scored: int) -> str:
    return (
        f"> Only {scored} divergent item(s) were scored, below the floor of "
        f"{HOLDOUT_MIN_DIVERGENT_ITEMS}. Below that, a ratio is noise whatever "
        f"it reads, so the figure above is reported and not relied on."
    )


def _does_not_reconcile(parts: int, total: int) -> str:
    return (
        f"> **These numbers do not reconcile.** The four reasons above sum to "
        f"{parts} and the scorer reports {total} unobserved items. They are "
        f"meant to be the same items counted two ways, so one of the two "
        f"modules has changed what it counts and nothing in this report should "
        f"be relied on until that is resolved."
    )


def render(score: Dict[str, Any], reconciled: Dict[str, Any],
           subject: str = "") -> str:
    """Markdown. `score` from holdout.score, `reconciled` from suite.reconcile."""
    div = score["divergent"]
    con = score["consensus"]
    who = f" — {subject}" if subject else ""

    # What is left once the harness's own three reasons are taken out: an
    # observation the run recorded as null on purpose. Derived rather than
    # counted again, so it cannot disagree with the total.
    null_recorded = max(0, score["unknown"]
                        - len(reconciled["missing"])
                        - len(reconciled["unjudged"])
                        - len(reconciled["not_blind"]))

    gated = score["gated_alignment"]
    enough = div["scored"] >= HOLDOUT_MIN_DIVERGENT_ITEMS
    verdict = (NOT_MEASURED if gated is None else
               f"{_pct(gated)} against a floor of {_pct(HOLDOUT_MIN_ALIGNMENT)}")

    lines = [
        f"# Holdout report{who}",
        "",
        "## The gated figure",
        "",
        f"**Divergent-pool alignment: {_pct(gated)}**",
        "",
        verdict + ".",
        "",
        WHY_DIVERGENT,
        "",
    ]

    if not enough:
        lines += [_too_few(div["scored"]), ""]

    lines += [
        "## Both pools",
        "",
        "| Pool | Aligned | Diverged | Scored | Alignment | Gated |",
        "|------|---------|----------|--------|-----------|-------|",
        _row("Divergent", div, gated=True),
        _row("Consensus", con, gated=False),
        "",
        WHY_CONSENSUS_NOT_GATED,
        "",
        "## What was not scored, and why each is separate",
        "",
        "| Reason | Count |",
        "|--------|-------|",
        f"| No entry in the run | {len(reconciled['missing'])} |",
        f"| No judge named | {len(reconciled['unjudged'])} |",
        f"| Judge was not blind | {len(reconciled['not_blind'])} |",
        f"| Observation recorded as null | {null_recorded} |",
        f"| **Unobserved, total** | **{score['unknown']}** |",
        "",
        "| Excluded before scoring | Count |",
        "|--------|-------|",
        f"| Seen during extraction | {score['seen_excluded']} |",
        f"| Judged, but no baseline recorded | {score['no_baseline']} |",
        "",
        WHY_FOUR_REASONS,
        "",
        WHY_TWO_TABLES,
        "",
        f"Unobserved share of eligible items: **{_pct(score['unknown_ratio'])}**.",
        "",
    ]

    # The report checks its own arithmetic.
    #
    # The four unobserved reasons have to account for exactly the total that
    # holdout.score reports, because they are the same items counted two ways.
    # If they ever stop adding up, one of the two modules has changed what it
    # counts, and the table above would still look perfectly reasonable while
    # being wrong. A report that cannot reconcile its own numbers says so
    # instead of printing them.
    parts = (len(reconciled["missing"]) + len(reconciled["unjudged"])
             + len(reconciled["not_blind"]) + null_recorded)
    if parts != score["unknown"]:
        lines += [_does_not_reconcile(parts, score["unknown"]), ""]

    lines += _ids("No entry in the run", reconciled["missing"], WHY_MISSING)
    lines += _ids("No judge named", reconciled["unjudged"], WHY_UNJUDGED)
    lines += _ids("Judge was not blind", reconciled["not_blind"], WHY_NOT_BLIND)

    lines += [
        "## Who judged",
        "",
    ]
    if reconciled["judges"]:
        lines += [f"- `{j}`" for j in reconciled["judges"]] + [""]
    else:
        lines += [NO_JUDGE_AT_ALL, ""]

    lines += [
        "## How to read a thin report",
        "",
        HOW_TO_READ_A_THIN_REPORT,
        "",
    ]
    return "\n".join(lines)
