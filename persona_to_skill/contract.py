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

import re

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
# But a raw alignment figure over all holdout questions measures almost
# nothing, because most of what any practitioner says out loud is consensus.
# Ask ten negotiation consultants what matters and the lists overlap; compress
# them and you have the generic advice a model already holds. A reconstruction
# scores well on those questions whether or not it learned anything, so a
# question set drawn from them issues a flattering grade to an empty shell.
#
# What carries information is where the subject's model of the world DIVERGES
# from the default -- and that shows up in what they refuse. "Walk away past 60
# days rather than discount" rests on a causal claim (discounting teaches the
# buyer that waiting works) that the generic answer does not hold. Reproducing
# that is evidence; reproducing a consensus answer is not.
#
# So holdout items are scored in two pools, decided by a recorded BASELINE: the
# same question answered with no reconstruction loaded at all.
#
#   consensus pool -- the baseline already matches the subject. Reported,
#                     never gated: the reconstruction cannot be credited for an
#                     answer the default gets right.
#   divergent pool -- the baseline is wrong, so only judgement actually carried
#                     across can be right. THIS is the pool the gate reads.
#
# Alignment therefore means "alignment where the default would have failed",
# which is the lift over baseline, measured directly rather than subtracted.
#
# The honest consequence: a subject whose public positions are all consensus
# cannot be meaningfully reconstructed, and this gate says so instead of
# producing a well-scored shell.
#
# UNKNOWN is a first-class state. An unobserved result is never counted as a
# pass and never as a failure -- it is excluded from the denominator and
# reported separately.
#
# The alternative corrupts the only number that matters. Score an unobserved
# item as a failure and a thin question set reads as a bad reconstruction;
# score it as a pass and the gate flatters whatever it could not check. Both
# answers are invented. Carrying the gap forward is the only honest option.

# Applied to the DIVERGENT pool only (see the two-pool note above).
HOLDOUT_MIN_ALIGNMENT = 0.80

# A high UNKNOWN rate is a defect in the holdout question set, not in the
# reconstruction, and it must not be reported as either. Above this, the gate
# fails and asks for better questions.
HOLDOUT_MAX_UNKNOWN_RATIO = 0.30

# Below this many scored items, an alignment ratio is noise. Fail rather than
# publish a percentage that means nothing.
HOLDOUT_MIN_ITEMS = 10

# Of those, how many must sit in the divergent pool. A set of 20 consensus
# questions and 1 divergent one cannot support a claim about judgement, however
# the total reads.
HOLDOUT_MIN_DIVERGENT_ITEMS = 5

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

# ------------------------------------------------------- deliberation memo
# The one-page memo a reconstruction produces for a decision. Fixed schema, and
# the fixedness is the point: people deciding something look only at what they
# already want to look at, so the fields anyone would skip -- key assumptions,
# main risks, what evidence is still missing -- are exactly the ones a schema
# has to make non-skippable. A field left blank is visible; a field never asked
# for is not.
#
# Chinese names are the ones used in the deliberation method these come from.
MEMO_REQUIRED_FIELDS = {
    "decision": "決策問題",
    "options": "選項",
    "known_facts": "目前已知事實",
    "consensus": "三方共識",
    "conflicts": "關鍵分歧",
    "key_assumptions": "關鍵假設",
    "main_risks": "主要風險",
    "evidence_gaps": "尚缺證據",
    "flip_condition": "決策翻轉條件",
    "recommendation": "建議方案",
    "confidence": "Confidence 信心水位",
    "next_actions": "下一步行動",
}

# Of those, the two that carry the weight. The flip condition turns anxiety
# into a solvable information gap; the confidence level changes how everything
# above it should be read. Each gets a hard rule of its own in G5.
MEMO_LOAD_BEARING_FIELDS = ("flip_condition", "confidence")

# Fields where "none" is a legitimate answer rather than a dodge. Requiring
# these to be non-empty would force someone to invent an evidence gap, which is
# the opposite of the point.
#
# So the requirement is that a field be ANSWERED, not that it be non-empty: the
# key must be present, and an explicit empty value counts as "none". A missing
# key does not -- that is the skip the schema exists to make visible.
#
# "No gaps" still has to be paid for. See CONFIDENCE_REQUIRING_GAPS_NAMED: low
# confidence with nothing missing is as incoherent as high confidence with
# plenty missing, which makes an empty gap list expensive to claim falsely in
# either direction.
MEMO_EMPTIABLE_FIELDS = ("evidence_gaps",)

# conflicts is deliberately NOT emptiable. The seats that produce a memo are
# set against each other on purpose -- one argues for, one argues against -- so
# a run that surfaces no conflict has not found agreement, it has found that a
# seat did not hold its position. Where opposed positions genuinely converge,
# that needs saying, and saying it is content, so the field is non-empty either
# way. Conflict is also where the value is: it marks the spot where two models
# of the world differ, which is the thing worth digging into.

# Below this, declaring no evidence gaps is incoherent: something is making you
# unsure, and naming it is the whole job.
CONFIDENCE_REQUIRING_GAPS_NAMED = 0.70

VERDICTS = ("APPROVE", "REVISE", "INVESTIGATE", "DEFER")

# A verdict that commits to the decision. Not available while the quantity that
# decides it is still unknown -- then the honest output is "go find this out",
# which is what INVESTIGATE and DEFER are for. Being able to say "not yet" with
# a straight face is a result, not a failure to produce one.
VERDICTS_REQUIRING_FLIP_CONDITION_KNOWN = ("APPROVE", "REVISE")

# Claiming this much confidence while a gap that BEARS ON THE DECISION is still
# open is not a judgement call, it is incoherent.
#
# An earlier version forbade any open gap at all above this level, which was
# wrong twice over. It blocked a perfectly reasonable memo -- high confidence
# with a minor gap noted -- and worse, the way to satisfy it was to delete the
# gap, so the rule paid people to do the one thing the schema exists to stop.
#
# So the combination is not forbidden, it is made explicit: a gap is either
# marked as not bearing on the decision, or it counts against the confidence.
# Marking is cheaper than deleting, which puts the incentive back the right way
# round. An unmarked gap counts as bearing -- fail closed.
CONFIDENCE_REQUIRING_NO_GAPS = 0.70

# How an evidence gap says it is peripheral. Absent, a gap bears on the
# decision.
GAP_PERIPHERAL_KEY = "bears_on_decision"

# Evasion. "綜合評估" means "work it out yourself", so a field whose content is
# that phrase is a field not filled.
#
# Read what this list can and cannot do. It is lexical, so it is a FLOOR, not a
# detector of evasion:
#   * it is gameable -- the list is public, and "整體來看需要權衡各方面因素" is
#     the same dodge in words the list does not hold;
#   * it false-positives on mention rather than use -- "不能用綜合評估帶過" is
#     a correct sentence that trips it.
# A structural replacement was considered and rejected: there is no reliable
# test separating a dodge from a specific statement, because "the unit
# economics never reach breakeven" contains neither a condition nor a number
# and is not evasive at all.
#
# So a lexical hit WARNS rather than blocks, except where the field's content
# is nothing but the phrase, which is unambiguous. The checks that block are
# the ones that can be verified: a threshold has to contain a number, a
# confidence level has to be numeric. Inventing a second rule to prop up the
# first would only move the guesswork somewhere less visible.
EVASION_PHRASES = (
    "綜合評估", "自己判斷", "看情況決定", "依專業判斷", "彈性處理", "視情況而定",
    "見機行事", "酌情處理",
    "use your judgement", "as appropriate", "case by case", "it depends",
    "holistically", "weigh all factors",
)


# False confidence about a fact, as distinct from evasion of a judgement. These
# read as knowing and mean not knowing, which is why they cannot appear in
# anything classified as a fact. The remedy is reclassification, not deletion:
# a hedged statement is an inference or an unknown, and saying so is honest.
HEDGE_MARKERS = (
    "應該是", "應該會", "通常會", "一般來說", "據說", "多半", "大概", "似乎",
    "推測", "可能是", "照理說", "按理說",
    "probably", "typically", "generally", "usually", "should be", "likely",
    "presumably", "it seems", "arguably", "tends to",
)

STATEMENT_CLASSES = ("FACT", "INFERENCE", "ASSUMPTION", "RECOMMENDATION", "UNKNOWN")

# A threshold with no number in it is not a threshold. One of the few places a
# structural check is sound rather than guessed at.
THRESHOLD_NUMBER = re.compile(r"\d")

# A recommendation must name the assumptions it rests on, at the recommendation.
# Listing them three fields away does not work: nobody reading a recommendation
# scrolls back to check what it stands on.
ASSUMPTION_STATUSES = ("verified", "unverified", "unverifiable")

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
    "HOLDOUT_MIN_DIVERGENT_ITEMS",
    "IMPERSONATION_PATTERNS",
    "DISCLOSURE_REQUIRED_KEYS",
    "MEMO_REQUIRED_FIELDS",
    "MEMO_LOAD_BEARING_FIELDS",
    "VERDICTS",
    "VERDICTS_REQUIRING_FLIP_CONDITION_KNOWN",
    "CONFIDENCE_REQUIRING_NO_GAPS",
    "CONFIDENCE_REQUIRING_GAPS_NAMED",
    "MEMO_EMPTIABLE_FIELDS",
    "GAP_PERIPHERAL_KEY",
    "EVASION_PHRASES",
    "HEDGE_MARKERS",
)
