#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Frozen contract for persona-to-skill.

Every value in this module is a FROZEN CONTRACT. Changing one changes what the
tool is allowed to produce, so a change here requires a new major version and a
FROZEN.md entry -- never an in-place edit. tests/test_contract_frozen.py asserts
these values; if you edit them without bumping the version, CI goes red.

Why these particular values exist is a legal question, not a taste question.
See docs/legal.md. In short: the 2024-2026 wave of digital-replica statutes
(Tennessee ELVIS Act, Washington SB 5886, California SB 1111, the proposed
federal NO FAKES Act) targets VOICE and VISUAL LIKENESS. Reconstructing a
documented method in text, with citations, sits outside that range -- but only
as long as the output does not impersonate. The gates below are what keep it
outside.
"""
from __future__ import annotations

CONTRACT_VERSION = "persona-to-skill/contract/v1"

# ------------------------------------------------------------- output scope
# The only axis that needs a mode. "Whose material is this" is already answered
# per-source by the tier system below, so it is not repeated here.
#
# PRIVATE   : the result stays with the person who built it. No third party is
#             being informed of anything, so nothing needs disclosing.
# PUBLISHED : the result is shared, sold, hosted, or handed to someone else.
#             Disclosure and the impersonation ban both bite here.
OUTPUT_SCOPES = ("PRIVATE", "PUBLISHED")

# Which gates care about scope, and which do not. The distinction matters
# because three of the four gates are not about protecting the subject at all:
#   G1 source tiers   -- lawfulness of the material.    Scope-independent.
#   G2 source anchors -- quality. Protects the BUILDER: an advisor that invents
#                        "he said X" will have you acting on a rule nobody holds.
#                        Scope-independent, and it matters MORE in private use,
#                        because no reviewer will catch it for you.
#   G4 holdout        -- quality, same reasoning. Scope-independent.
#   G3 disclosure     -- informing a third party. The only scope-dependent gate.
SCOPE_DEPENDENT_GATES = ("G3-disclosure",)

# ---------------------------------------------------------------- source tiers
# Assigned per source document, never per project. A project is a mix of tiers.
SOURCE_TIERS = {
    "T0": "Private material supplied by the subject. Requires a consent record.",
    "T1": "Public and freely citable (interviews, talks, posts, public Q&A).",
    "T2": "Public but copyrighted. Short quotations with attribution only; never reproduced wholesale.",
    "T3": "Prohibited. Paywalled, leaked, scraped from a closed community, or obtained without permission.",
}

# T3 is never usable, in any mode, with any consent record. It is not a
# threshold to clear; it is a category that does not enter the pipeline.
TIERS_ALWAYS_FORBIDDEN = ("T3",)

# T0 is the subject's private material, so it requires a consent record naming
# it -- whether the builder is the subject, or someone the subject granted it to,
# and whatever the output scope. Without a record it does not enter the pipeline.
TIERS_REQUIRING_CONSENT = ("T0",)

# --------------------------------------------------------- consent record shape
# A consent record is checked for structure only. This tool cannot verify that a
# signature is genuine, and it does not pretend to: see CAPABILITY_LIMITS.
CONSENT_REQUIRED_FIELDS = (
    "subject_name",      # who is granting permission
    "granted_to",        # who may build from the material
    "scope",             # which sources the permission covers
    "signed_date",       # when
    "revocable",         # whether the subject can withdraw, and how
)

# ----------------------------------------------------------- holdout scoring
# The only evidence that a reconstruction captured a method rather than a voice:
# answer questions the subject has publicly answered, using material the
# extraction never saw, then compare.
#
# UNKNOWN is a first-class state. An unobserved result is never counted as a
# pass and never as a failure -- it is excluded from the denominator and
# reported separately.
#
# The alternative corrupts the only number that matters. Score an unobserved
# item as a failure and a thin question set reads as a bad reconstruction;
# score it as a pass and the gate flatters whatever it could not check. Both
# answers are invented. Carrying the gap forward is the only honest option.
HOLDOUT_MIN_ALIGNMENT = 0.80

# A high UNKNOWN rate is a defect in the holdout question set, not in the
# reconstruction, and it must not be reported as either. Above this, the gate
# fails and asks for better questions.
HOLDOUT_MAX_UNKNOWN_RATIO = 0.30

# Below this many scored items, an alignment ratio is noise. Fail rather than
# publish a percentage that means nothing.
HOLDOUT_MIN_ITEMS = 10

# -------------------------------------------------------- impersonation forms
# PUBLISHED scope: these block. They turn a cited reconstruction into a stand-in
# for a person, which is the line the digital-replica statutes draw and the line
# Taiwan's 混淆誤認 (likelihood of confusion) test draws.
#
# PRIVATE scope: these warn, and the warning is about effectiveness, not law.
# Telling a model "you are X" points it at the one thing it is already good at
# -- voice -- and away from the one thing it is bad at: judgement. The result
# sounds like the person and reasons like a general-purpose model, which is the
# worst case for a private user, because the voice is convincing and nobody
# else is reviewing it. "Apply the documented method of X, citing sources"
# forces retrieval instead, so a gap shows up as a gap.
#
# A private user who still wants impersonation gets to have it. The tool says
# why it is a worse tool and proceeds.
#
# {name} is substituted with the subject's name at check time. Patterns are
# matched case-insensitively against the generated skill text.
IMPERSONATION_PATTERNS = (
    r"you\s+are\s+{name}",
    r"you\s+are\s+now\s+{name}",
    r"act\s+as\s+{name}",
    r"pretend\s+to\s+be\s+{name}",
    r"roleplay\s+as\s+{name}",
    r"speak\s+as\s+{name}",
    r"in\s+{name}'?s\s+voice",
    r"你(?:現在)?就是\s*{name}",
    r"扮演\s*{name}",
    r"模仿\s*{name}\s*的(?:語氣|口吻|聲音)",
    r"以\s*{name}\s*的(?:身分|身份|口吻|語氣)(?:回答|說話|回覆)",
)

# Voice and likeness are squarely inside the statutes. The tool produces text
# and refuses to help produce these, in either mode.
IMPERSONATION_RATIONALE_PRIVATE = (
    "Impersonation phrasing steers the model toward voice, which it imitates well, "
    "and away from judgement, which it does not. Expect something that sounds right "
    "and decides generically. Prefer: apply the documented method of <name>, citing "
    "sources, so an unanswerable question reads as unanswerable."
)

# Refused in every scope. Voice and likeness sit squarely inside the statutes,
# and this tool produces text.
OUT_OF_SCOPE_OUTPUTS = (
    "voice cloning or any audio rendition of the subject",
    "images, video, or avatars depicting the subject",
    "first-person dialogue presented as the subject speaking",
    "claims that the subject endorses, reviewed, or authored the output",
)

# ------------------------------------------------------------ disclosure block
# PUBLISHED scope must carry all of these. Absent any one, the gate fails.
# PRIVATE scope requires none of them: there is no third party to inform.
DISCLOSURE_REQUIRED_KEYS = (
    "reconstruction_notice",  # states this is a reconstruction from public sources
    "not_endorsed",           # states the subject neither authored nor endorsed it
    "source_count",           # how many sources it rests on
    "holdout_alignment",      # the measured alignment, stated honestly
    "retrieved_date",         # when the sources were gathered
)

# ----------------------------------------------------------- punctuation scope
# House rule: Chinese text uses full-width punctuation. English does not, and
# the English README is the canonical one, so the punctuation gate must not run
# against it. Only these paths are checked.
PUNCT_CHECKED_SUFFIXES = (".zh-TW.md", ".zh-CN.md")
PUNCT_CHECKED_DIRS = ("docs/zh-TW", "docs/zh-CN")

# ------------------------------------------------------------ capability limits
# Stated plainly so the tool is not read as offering something it cannot do.
CAPABILITY_LIMITS = (
    "Cannot verify that a consent record is genuine; it checks structure only.",
    "Cannot establish that a source is authentic, correctly attributed, or current.",
    "Cannot determine whether a use is lawful in any given jurisdiction. Not legal advice.",
    "Cannot reconstruct judgement the sources never recorded; sparse material yields a sparse result, reported as such.",
    "Cannot detect that a subject has withdrawn consent after a build.",
)

FROZEN = (
    "OUTPUT_SCOPES",
    "SOURCE_TIERS",
    "TIERS_ALWAYS_FORBIDDEN",
    "SCOPE_DEPENDENT_GATES",
    "CONSENT_REQUIRED_FIELDS",
    "HOLDOUT_MIN_ALIGNMENT",
    "HOLDOUT_MAX_UNKNOWN_RATIO",
    "HOLDOUT_MIN_ITEMS",
    "IMPERSONATION_PATTERNS",
    "DISCLOSURE_REQUIRED_KEYS",
)
