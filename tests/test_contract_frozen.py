# -*- coding: utf-8 -*-
"""Frozen contract assertions. These values are the product's promises."""
import _base  # noqa: F401
from persona_to_skill import contract as c


def test_output_scopes_frozen():
    assert c.OUTPUT_SCOPES == ("PRIVATE", "PUBLISHED")


def test_only_disclosure_depends_on_scope():
    """Source tiers, anchors and holdout are about lawfulness and quality, so
    they run whatever the output scope. Collapsing that distinction is what
    made the earlier two-mode model wrong."""
    assert c.SCOPE_DEPENDENT_GATES == ("G3-disclosure",)


def test_tiers_frozen():
    assert set(c.SOURCE_TIERS) == {"T0", "T1", "T2", "T3"}
    assert c.TIERS_ALWAYS_FORBIDDEN == ("T3",)
    assert c.TIERS_REQUIRING_CONSENT == ("T0",)


def test_holdout_thresholds_frozen():
    assert c.HOLDOUT_MIN_ALIGNMENT == 0.80
    assert c.HOLDOUT_MAX_UNKNOWN_RATIO == 0.30
    assert c.HOLDOUT_MIN_ITEMS == 10
    assert c.HOLDOUT_MIN_DIVERGENT_ITEMS == 5


def test_consent_fields_frozen():
    assert c.CONSENT_REQUIRED_FIELDS == (
        "subject_name", "granted_to", "scope", "signed_date", "revocable",
    )


def test_disclosure_keys_frozen():
    assert c.DISCLOSURE_REQUIRED_KEYS == (
        "reconstruction_notice", "not_endorsed", "source_count",
        "holdout_alignment", "retrieved_date",
    )


def test_impersonation_patterns_cover_both_languages():
    joined = " ".join(c.IMPERSONATION_PATTERNS)
    for needle in ("you", "act", "pretend", "扮演", "就是", "模仿"):
        assert needle in joined, f"missing impersonation form: {needle}"
    assert all("{name}" in p for p in c.IMPERSONATION_PATTERNS)


def test_punct_gate_exempts_english():
    """The English README is canonical; the full-width punctuation rule must
    not be applied to it."""
    assert all(s.startswith(".zh-") for s in c.PUNCT_CHECKED_SUFFIXES)
    assert not any("en" in d for d in c.PUNCT_CHECKED_DIRS)


def test_private_impersonation_rationale_is_about_effectiveness():
    """Private use is warned, not blocked, and the warning has to explain why
    the phrasing works less well -- not lecture about law."""
    r = c.IMPERSONATION_RATIONALE_PRIVATE.lower()
    assert "voice" in r and "judgement" in r
    assert "illegal" not in r and "law" not in r


def test_memo_schema_frozen():
    assert tuple(c.MEMO_REQUIRED_FIELDS) == (
        "decision", "options", "known_facts", "consensus", "conflicts",
        "key_assumptions", "main_risks", "evidence_gaps", "flip_condition",
        "recommendation", "confidence", "next_actions",
    )
    assert c.MEMO_LOAD_BEARING_FIELDS == ("flip_condition", "confidence")
    assert c.MEMO_EMPTIABLE_FIELDS == ("evidence_gaps", "conflicts")
    assert c.VERDICTS == ("APPROVE", "REVISE", "INVESTIGATE", "DEFER")
    assert c.VERDICTS_REQUIRING_FLIP_CONDITION_KNOWN == ("APPROVE", "REVISE")
    assert c.CONFIDENCE_REQUIRING_NO_GAPS == 0.70
    assert c.CONFIDENCE_REQUIRING_GAPS_NAMED == 0.70


def test_statement_classes_frozen():
    """The four-way split is what makes the traps in fluent prose visible, plus
    UNKNOWN so "I do not know" has somewhere to go."""
    assert c.STATEMENT_CLASSES == (
        "FACT", "INFERENCE", "ASSUMPTION", "RECOMMENDATION", "UNKNOWN")
    assert c.ASSUMPTION_STATUSES == ("verified", "unverified", "unverifiable")


def test_evasion_and_hedging_are_separate_lists():
    """Different faults: evasion dodges a judgement, hedging fakes knowing a
    fact. Collapsing them would lose the second."""
    assert not set(c.EVASION_PHRASES) & set(c.HEDGE_MARKERS)
    for phrase in ("綜合評估", "視情況而定"):
        assert phrase in c.EVASION_PHRASES
    for marker in ("應該是", "通常會", "probably", "should be"):
        assert marker in c.HEDGE_MARKERS


def test_voice_and_likeness_declared_out_of_scope():
    joined = " ".join(c.OUT_OF_SCOPE_OUTPUTS).lower()
    assert "voice" in joined and "images" in joined and "first-person" in joined


if __name__ == "__main__":
    import sys
    sys.exit(_base.run_module(dict(globals())))
