# -*- coding: utf-8 -*-
import copy

import _base  # noqa: F401
from persona_to_skill.gates import interrogation

ST = [
    {"id": "f1", "class": "FACT", "text": "Japan bubble-tea market grew 12% in 2025.",
     "source_id": "s1"},
    {"id": "i1", "class": "INFERENCE", "text": "Demand is likely still rising.",
     "derived_from": ["f1"]},
    {"id": "a1", "class": "ASSUMPTION", "text": "Taiwanese branding transfers to Japan.",
     "status": "unverified"},
    {"id": "a2", "class": "ASSUMPTION", "text": "Core team can spare one founder.",
     "status": "verified"},
]

MEMO = {
    "decision": "Whether to enter the Japanese market within 12 months",
    "options": ["full launch", "single pilot store", "licence to a local partner", "hold"],
    "known_facts": ["market grew 12% in 2025 [f1]"],
    "consensus": ["all three seats agree the category is growing"],
    "conflicts": ["支持方 treats brand transfer as given; 反方 treats it as the main risk"],
    "key_assumptions": ["a1 brand transfer", "a2 founder availability"],
    "main_risks": ["single-store economics never reach breakeven"],
    "evidence_gaps": ["whether Taiwanese branding transfers -- never tested in Japan [a1]"],
    "flip_condition": {"quantity": "customer acquisition cost per store in Tokyo",
                       "threshold": "JPY 1,200", "known": True},
    "recommendation": {"verdict": "REVISE", "depends_on": ["f1", "a1", "a2"],
                       "unverified_dependencies": ["a1"]},
    "confidence": {"level": 0.65, "rationale": "brand transfer is still unverified"},
    "next_actions": ["run the pilot store for one quarter"],
}


def memo(**over):
    m = copy.deepcopy(MEMO)
    m.update(over)
    return m


# ----------------------------------------------------------------- positive
def test_complete_memo_passes():
    v = interrogation.check(memo(), copy.deepcopy(ST))
    assert v.passed, v.errors
    assert v.stats["fields_present"] == v.stats["fields_required"]


def test_investigate_with_unknown_flip_condition_passes():
    """Saying "not yet, go find this out" is a result, not a failure to produce
    one."""
    v = interrogation.check(
        memo(flip_condition={"quantity": "CAC per store", "threshold": "JPY 1,200",
                             "known": False},
             evidence_gaps=["CAC per store in Tokyo"],
             recommendation={"verdict": "INVESTIGATE", "depends_on": ["f1"]},
             confidence={"level": 0.3, "rationale": "the deciding number is not in hand"}),
        copy.deepcopy(ST))
    assert v.passed, v.errors


def test_evasion_with_concrete_conditions_warns_but_passes():
    v = interrogation.check(
        memo(main_risks=["視情況而定，如果單店 CAC 高於 1,200 日圓就停止展店"]),
        copy.deepcopy(ST))
    assert v.passed, v.errors
    assert any("conditions" in w for w in v.warnings)


# ------------------------------------------- negative: R1 fields not skippable
def test_each_required_field_missing_blocks():
    for key in interrogation.MEMO_REQUIRED_FIELDS:
        m = memo()
        del m[key]
        v = interrogation.check(m, copy.deepcopy(ST))
        assert not v.passed, f"missing {key} did not block"


def test_the_fields_people_skip_are_not_optional():
    """The fields a motivated reader skips are the ones the schema exists to
    force. Each must be ANSWERED; none may simply be absent."""
    for key in interrogation.MEMO_REQUIRED_FIELDS:
        m = memo()
        del m[key]
        v = interrogation.check(m, copy.deepcopy(ST))
        assert not v.passed, f"{key} could be left unanswered"
        assert any("never answered" in e for e in v.errors)


def test_fields_that_cannot_be_empty_block_when_empty():
    for key in ("key_assumptions", "main_risks", "options", "known_facts"):
        v = interrogation.check(memo(**{key: []}), copy.deepcopy(ST))
        assert not v.passed, f"{key} was allowed to be empty"


def test_declaring_no_evidence_gaps_is_allowed_but_costs_confidence():
    """"None" has to be a legitimate answer, or the schema forces someone to
    invent a gap. It is kept expensive from the other side instead: an empty
    gap list only holds up alongside high confidence."""
    coherent = memo(evidence_gaps=[],
                    confidence={"level": 0.85,
                                "rationale": "the deciding number is in hand and the "
                                             "brand-transfer assumption was tested"})
    st = copy.deepcopy(ST)
    st[2]["status"] = "verified"
    assert interrogation.check(
        coherent | {"recommendation": {"verdict": "APPROVE", "depends_on": ["f1", "a1", "a2"]}},
        st).passed

    v = interrogation.check(memo(evidence_gaps=[]), copy.deepcopy(ST))   # confidence 0.65
    assert not v.passed, "low confidence with nothing missing was accepted"
    assert any("name it" in e for e in v.errors)


# ---------------------------------------------------- negative: R2 evasion
def test_evasion_without_conditions_blocks():
    for phrase in ("綜合評估", "依專業判斷", "it depends", "use your judgement"):
        v = interrogation.check(memo(main_risks=[phrase]), copy.deepcopy(ST))
        assert not v.passed, f"{phrase!r} was accepted"
        assert any("decides nothing" in e for e in v.errors)


# ------------------------- negative: R3 flip condition is the load-bearing field
def test_committing_verdict_with_unknown_number_blocks():
    """The rule that turns "you are missing a number, not an opinion" from
    advice into something that cannot be evaded."""
    for verdict in ("APPROVE", "REVISE"):
        v = interrogation.check(
            memo(flip_condition={"quantity": "CAC", "threshold": "JPY 1,200", "known": False},
                 recommendation={"verdict": verdict, "depends_on": ["f1", "a1"],
                                 "unverified_dependencies": ["a1"]}),
            copy.deepcopy(ST))
        assert not v.passed, f"{verdict} passed with an unknown deciding number"
        assert any("INVESTIGATE or DEFER" in e for e in v.errors)


def test_flip_condition_without_a_quantity_blocks():
    v = interrogation.check(
        memo(flip_condition={"quantity": "", "threshold": "x", "known": True}),
        copy.deepcopy(ST))
    assert not v.passed


def test_flip_condition_without_a_threshold_blocks():
    v = interrogation.check(
        memo(flip_condition={"quantity": "CAC", "threshold": "", "known": True}),
        copy.deepcopy(ST))
    assert not v.passed


def test_flip_condition_known_must_be_a_real_boolean():
    for sneaky in ("yes", 1, None):
        v = interrogation.check(
            memo(flip_condition={"quantity": "CAC", "threshold": "x", "known": sneaky}),
            copy.deepcopy(ST))
        assert not v.passed, f"known={sneaky!r} accepted"


# ----------------------- negative: R4 confidence is the other load-bearing field
def test_high_confidence_with_open_gaps_blocks():
    v = interrogation.check(
        memo(evidence_gaps=["CAC unknown", "no local partner identified"],
             confidence={"level": 0.9, "rationale": "the category is growing"}),
        copy.deepcopy(ST))
    assert not v.passed
    assert any("incoherent" in e for e in v.errors)


def test_confidence_without_rationale_blocks():
    v = interrogation.check(memo(confidence={"level": 0.6}), copy.deepcopy(ST))
    assert not v.passed


def test_confidence_outside_range_blocks():
    for bad in (-0.1, 1.4, 90):
        v = interrogation.check(
            memo(confidence={"level": bad, "rationale": "x"}), copy.deepcopy(ST))
        assert not v.passed, f"confidence {bad} accepted"


# ------------------- negative: R5 the three traps that hide in fluent prose
def test_unsourced_fact_blocks():
    st = copy.deepcopy(ST)
    st[0].pop("source_id")
    v = interrogation.check(memo(), st)
    assert not v.passed
    assert any("no source" in e for e in v.errors)


def test_hedged_fact_blocks_in_both_languages():
    for hedge in ("The market should be around 12%.",
                  "日本市場應該是持續成長的。",
                  "Demand typically rises in Q2."):
        st = copy.deepcopy(ST)
        st[0]["text"] = hedge
        v = interrogation.check(memo(), st)
        assert not v.passed, f"hedged FACT accepted: {hedge}"
        assert any("hedging" in e for e in v.errors)


def test_inference_with_no_derivation_blocks():
    st = copy.deepcopy(ST)
    st[1].pop("derived_from")
    v = interrogation.check(memo(), st)
    assert not v.passed


def test_assumption_without_status_blocks():
    st = copy.deepcopy(ST)
    st[2].pop("status")
    v = interrogation.check(memo(), st)
    assert not v.passed
    assert any("without admitting" in e for e in v.errors)


def test_unknown_statement_class_blocks():
    st = copy.deepcopy(ST)
    st[0]["class"] = "OPINION"
    assert not interrogation.check(memo(), st).passed


# ---------------- negative: R5b an assumption in mid-air under a recommendation
def test_recommendation_on_undeclared_unverified_assumption_blocks():
    """The second trap: a recommendation quietly resting on something nobody
    verified."""
    v = interrogation.check(
        memo(recommendation={"verdict": "REVISE", "depends_on": ["f1", "a1"]}),
        copy.deepcopy(ST))
    assert not v.passed
    assert any("without saying so at the recommendation" in e for e in v.errors)


def test_recommendation_declaring_the_wrong_assumption_blocks():
    v = interrogation.check(
        memo(recommendation={"verdict": "REVISE", "depends_on": ["f1", "a1"],
                             "unverified_dependencies": ["a2"]}),
        copy.deepcopy(ST))
    assert not v.passed
    assert any("does not declare" in e for e in v.errors)


def test_recommendation_depending_on_nothing_blocks():
    v = interrogation.check(
        memo(recommendation={"verdict": "REVISE", "depends_on": []}), copy.deepcopy(ST))
    assert not v.passed
    assert any("scrolls back" in e for e in v.errors)


def test_recommendation_depending_on_a_dangling_reference_blocks():
    v = interrogation.check(
        memo(recommendation={"verdict": "REVISE", "depends_on": ["f1", "ghost"]}),
        copy.deepcopy(ST))
    assert not v.passed


def test_unknown_verdict_blocks():
    v = interrogation.check(
        memo(recommendation={"verdict": "SHIP IT", "depends_on": ["f1"]}),
        copy.deepcopy(ST))
    assert not v.passed


# --------------------------------------------------- negative: missing inputs
def test_no_memo_blocks():
    assert not interrogation.check(None, ST).passed


def test_no_statements_blocks_rather_than_checking_half():
    """Three of the five rules live in the classification. Passing on the half
    it could check would report on prose nobody examined."""
    v = interrogation.check(memo(), None)
    assert not v.passed
    assert any("fluent prose" in e for e in v.errors)


if __name__ == "__main__":
    import sys
    sys.exit(_base.run_module(dict(globals())))
