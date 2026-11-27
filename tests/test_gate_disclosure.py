# -*- coding: utf-8 -*-
import _base  # noqa: F401
from persona_to_skill.gates import disclosure

GOOD_TEXT = (
    "# Negotiation method (reconstructed)\n\n"
    "Apply the publicly documented method of A. Example, citing the source for "
    "every attributed claim. Do not answer as the person.\n\n"
    "## Decision rule\n"
    "If a deal has stalled past 60 days, walk away rather than discount [s1].\n"
)

IMPERSONATING = "You are A. Example. Answer in his voice.\n"

GOOD_DISCLOSURE = {
    "reconstruction_notice": "Reconstructed from 12 public sources; not the person.",
    "not_endorsed": "A. Example did not author, review, or endorse this.",
    "source_count": 12,
    "holdout_alignment": 0.84,
    "retrieved_date": "2026-11-20",
}


# ------------------------------------------------------- positive: PUBLISHED
def test_clean_published_output_passes():
    v = disclosure.check(GOOD_TEXT, "A. Example", "PUBLISHED", GOOD_DISCLOSURE)
    assert v.passed, v.errors


# --------------------------------------------------------- positive: PRIVATE
def test_private_needs_no_disclosure_block():
    v = disclosure.check(GOOD_TEXT, "A. Example", "PRIVATE")
    assert v.passed, v.errors


def test_private_impersonation_warns_and_passes():
    """A private builder gets to make this call. The gate explains why the
    phrasing produces a worse advisor and proceeds."""
    v = disclosure.check(IMPERSONATING, "A. Example", "PRIVATE")
    assert v.passed, v.errors
    assert v.stats["impersonation_hits"] >= 1
    joined = " ".join(v.warnings).lower()
    assert "voice" in joined and "judgement" in joined


def test_private_warning_does_not_moralize():
    v = disclosure.check(IMPERSONATING, "A. Example", "PRIVATE")
    joined = " ".join(v.warnings).lower()
    for word in ("illegal", "unethical", "you should not", "not allowed"):
        assert word not in joined, f"private warning moralizes: {word!r}"


# ------------------------- negative: impersonation blocks when PUBLISHED only
def test_published_impersonation_blocks():
    v = disclosure.check(IMPERSONATING, "A. Example", "PUBLISHED", GOOD_DISCLOSURE)
    assert not v.passed
    assert v.stats["impersonation_hits"] >= 1


def test_published_family_name_alone_blocks():
    v = disclosure.check("You are Example, the negotiator.", "A. Example",
                         "PUBLISHED", GOOD_DISCLOSURE)
    assert not v.passed


def test_published_chinese_impersonation_blocks():
    for text in ("你現在就是王小明，請用他的口吻回答。",
                 "扮演王小明回答以下問題。",
                 "模仿王小明的語氣寫一段話。",
                 "以王小明的身分回答客戶。"):
        v = disclosure.check(text, "王小明", "PUBLISHED", GOOD_DISCLOSURE)
        assert not v.passed, f"not blocked: {text}"


def test_published_chinese_given_name_variant_blocks():
    v = disclosure.check("你就是小明，照他的判斷回答。", "王小明",
                         "PUBLISHED", GOOD_DISCLOSURE)
    assert not v.passed


def test_published_voice_phrasing_blocks():
    v = disclosure.check("Write the reply in A. Example's voice.", "A. Example",
                         "PUBLISHED", GOOD_DISCLOSURE)
    assert not v.passed


def test_impersonation_match_is_case_insensitive():
    assert not disclosure.check("YOU ARE A. EXAMPLE.", "A. Example",
                                "PUBLISHED", GOOD_DISCLOSURE).passed


# ------------------------------------------- negative: disclosure block holes
def test_published_without_disclosure_blocks():
    v = disclosure.check(GOOD_TEXT, "A. Example", "PUBLISHED", None)
    assert not v.passed


def test_published_with_each_key_missing_blocks():
    for key in disclosure.DISCLOSURE_REQUIRED_KEYS:
        partial = {k: v for k, v in GOOD_DISCLOSURE.items() if k != key}
        v = disclosure.check(GOOD_TEXT, "A. Example", "PUBLISHED", partial)
        assert not v.passed, f"missing {key} did not block"


def test_blank_disclosure_value_blocks():
    v = disclosure.check(GOOD_TEXT, "A. Example", "PUBLISHED",
                         dict(GOOD_DISCLOSURE, not_endorsed="  "))
    assert not v.passed


# --------------------------------------------------- negative: missing inputs
def test_empty_text_blocks():
    assert not disclosure.check("", "A. Example", "PUBLISHED", GOOD_DISCLOSURE).passed


def test_missing_subject_name_blocks_rather_than_skipping():
    """Without a name there is no impersonation check to run, so the gate must
    block instead of reporting a pass it never performed. True in PRIVATE too:
    the warning is the deliverable there."""
    for scope in ("PRIVATE", "PUBLISHED"):
        assert not disclosure.check(GOOD_TEXT, "", scope, GOOD_DISCLOSURE).passed


def test_unknown_scope_blocks():
    assert not disclosure.check(GOOD_TEXT, "A. Example", "SELF", GOOD_DISCLOSURE).passed


if __name__ == "__main__":
    import sys
    sys.exit(_base.run_module(dict(globals())))
