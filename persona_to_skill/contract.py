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
# DECLARED, not FROZEN, and the distinction is the honest one: this records a
# design property that no code yet consults. Its proper home is the orchestrator
# that runs the gates in order and hands `scope` only to the ones that take it,
# which does not exist yet because stage B is not wired to packaging. When it
# does, this moves to FROZEN and the orchestrator reads it.
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

# ----------------------------------------------------------- the eval harness
# G4 says what a holdout score has to clear. This says what a RECORDED
# observation has to look like before it counts as one, which is a different
# question and the one that decides whether the score means anything.
#
# The harness never produces an observation. It reads a manifest (the questions,
# and what the subject actually said, anchored to a source) and a run (what the
# reconstruction answered, what a baseline answered, and whether each matched).
# Both come from outside. A harness that answered its own questions would be
# measuring itself, and the number would be a self-report wearing a percentage
# sign.
#
# Two fields carry the weight, and neither is bureaucracy.
#
# JUDGED_BY. Someone or something decided "this answer matches what the subject
# said". That decision is a measurement, so it has an instrument, and an
# unnamed instrument cannot be checked. An item without it is not scored.
#
# BLIND. The judge must not know which candidate came from the reconstruction
# and which from the baseline. This is the one that actually protects the
# number: a judge told "this one is the reconstruction" has been handed the
# answer the experiment is supposed to produce, and LLM-as-judge is as
# susceptible to that as a person. Non-blind items are counted and reported,
# never gated, which is the same treatment G4 already gives items that were
# seen during extraction. Not a punishment: a non-blind judgement is evidence
# of something, just not of this.
EVAL_MANIFEST_REQUIRED_FIELDS = (
    # The question, held back from extraction, that the subject has answered.
    "id", "question",
    # What the subject actually said, and where. The ground truth has to be
    # anchorable or the whole comparison rests on an unverified claim, which is
    # the failure this project exists to make impossible.
    "source_id", "subject_said",
)

EVAL_RUN_REQUIRED_FIELDS = (
    "id",
    # The two answers. Kept verbatim so a reader can disagree with the judge.
    "reconstruction", "baseline",
    # The judgements. Explicit booleans or null; see G4 on UNKNOWN.
    "aligned", "baseline_aligned",
    # Who judged, and whether they were blind to which answer was which.
    "judged_by", "blind",
)

# How a run item may answer "did this match". A string is refused on purpose:
# "yes" and "probably" are not observations, and coercing either would invent
# the measurement this module promises never to estimate.
EVAL_OBSERVATION_VALUES = (True, False, None)

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
# and this tool produces text. Declared, not enforced: see the note above.
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

# ------------------------------------------------------------- who wrote it
# Provenance and authorship are orthogonal and must not be conflated.
# Provenance asks how this text came to exist (published prose, a transcript,
# OCR). Authorship asks whose words these are. A ghostwritten book is published
# prose that the subject did not write; a transcript is the subject's own words
# written down by a machine.
#
# G2 verifies that a quote appears in the source it names. It cannot verify
# that the source's author is the subject, and that gap is not hypothetical:
# The Art of the Deal is credited to Trump and was written by Tony Schwartz,
# who has said so publicly. A quote from it matches the source exactly and is
# still not the subject's own words.
AUTHORSHIP_KINDS = (
    "self_written",     # the subject wrote or spoke it
    "ghostwritten",     # published under their name, written by someone else
    "co_authored",      # shared, so a given sentence cannot be assigned
    "institutional",    # a company or campaign statement in their name
    "translated",       # the words matched are the translator's
    "unknown",          # not established
)

# Authorship that makes a quote something other than the subject's own words.
# A claim resting on one of these has to say so: the honest form is "the book
# published under their name says X", not "they said X".
AUTHORSHIP_NOT_OWN_WORDS = ("ghostwritten", "co_authored", "institutional", "translated")

# `unknown` warns rather than blocks, and the reason is practical rather than
# principled: for most sources authorship cannot be established from outside,
# so blocking on it would make the pipeline unusable and push people towards
# declaring self_written to get past the gate. A gate that is routinely lied to
# is worse than one that reports a gap.

# ---------------------------------------------------------------- the seats
# What a reconstruction extracts is not what the subject concluded, it is how
# they get to a conclusion. A cited conclusion is still a conclusion: an
# adviser who walks in and says "looks fine" is useless whether or not the
# sentence has a footnote. So extraction is organised by the seats a
# deliberation has, and each seat is defined by what the subject does in it.
#
# These are seats in a method, not a transcript of one. A subject who never
# deliberated out loud still occupies them; the corpus just has less to say
# about some.
SEATS = {
    "decompose": "拆解",
    "support": "支持",
    "oppose": "反對",
    "evidence": "證據",
    "crosscheck": "交叉檢核",
    "synthesise": "統整",
    "interrogate": "拷問",
}

# What each seat owes. A seat with nothing recorded is not a seat the subject
# lacks, it is a seat the corpus could not fill, and the two are reported
# differently: see extract.seats.
SEAT_OBLIGATIONS = {
    "decompose": ("first_question", "options_added", "framing_refused"),
    "support": ("strongest_case", "conditions_that_favour"),
    "oppose": ("premortem", "underestimated", "refusals"),
    "evidence": ("demanded_before_acting", "treated_as_fact", "treated_as_inference"),
    "crosscheck": ("conflicts_sought", "sensitivity_question"),
    "synthesise": ("weighting", "confidence_calibration"),
    "interrogate": ("self_attacks", "independence_check"),
}

# ADVERSARIAL BY DEFAULT.
#
# The dangerous case is not a user with no view. It is a user who already has
# an answer and wants it confirmed, holding a reconstruction of someone they
# admire: it agrees, in a voice they trust, and agreement from that voice does
# not read as flattery, it reads as confirmation.
#
# So the first seat that takes a POSITION is oppose. Decompose comes before it
# because a problem has to be carved up before anything can be objected to, and
# carving it up is framing rather than a position. The support seat is
# reachable but never volunteered, and the deliverable is what this subject
# would object to rather than what they would advise. The test of an answer is
# that it survives the objections, not that it collects an endorsement.
SEAT_ENTRY_ORDER = ("decompose", "oppose", "evidence", "crosscheck",
                    "synthesise", "interrogate")
SEATS_ON_REQUEST_ONLY = ("support",)

# A contradiction is the find, not the problem.
#
# Someone who argued one thing in 2021 and the opposite in 2024 has rarely
# reversed. Usually an unstated condition changed, and recovering that
# condition is the most valuable thing in a reconstruction, because it is a
# criterion the subject has never spelled out. So every contradiction record
# has to answer what condition makes both sides true.
#
# Fail-closed: where no condition can be found the record stays UNRESOLVED and
# is reported as worth digging into. Taking the newer side and moving on throws
# the find away, which is why "pick the latest" is not an available outcome.
CONTRADICTION_REQUIRED_FIELDS = (
    "earlier", "later", "reconciling_condition", "status",
)

# When unresolved contradictions stop being dig sites and start being the
# finding.
#
# "Unresolved is the intended outcome" is true at three and false at three
# hundred. A corpus full of positions that no condition reconciles is itself
# the result: the subject's stance moves as a tactic rather than with
# circumstances, and there may be no reconstructible method to find. Producing
# hundreds of "worth digging into" entries and calling that normal is the
# failure.
#
# PROVISIONAL. Both numbers are guesses. Nothing here has been run against a
# corpus with a real contradiction count, and the ratio is the more meaningful
# of the two while being unstable on small corpora, which is why there is a
# floor as well. Measure before freezing: see PROVISIONAL below.
CONTRADICTION_MAX_UNRESOLVED_RATIO = 0.60
CONTRADICTION_UNRESOLVED_RATIO_FLOOR = 8
CONTRADICTION_STATUSES = ("reconciled", "unresolved")

# The flip condition, and why it is the highest-value output.
#
# Hesitation is usually not disagreement, it is a missing number. What a
# practitioner is worth, for a class of decision, is knowing WHICH quantity
# decides it and roughly where the line sits. That is a bounded, checkable
# claim, unlike "thinks like X".
#
# A threshold must contain a number (THRESHOLD_NUMBER), which puts it under
# G2's figure check: a threshold cannot be invented without the corpus
# containing it.
SENSITIVITY_REQUIRED_FIELDS = (
    "decision_class", "quantity", "threshold", "direction", "source_id",
)

# Reported per seat, never as one number.
#
# A subject is usually distinctive in one or two seats and generic in the rest:
# someone who has watched things fail has a strong oppose seat, someone who
# knows which figures lie has a strong evidence seat, and their decompose seat
# may be ordinary. A single score hides that. A per-seat profile lets the
# reconstruction claim only the seats it earned, which is both honest and more
# useful: the reader knows where to trust it.
SEAT_PROFILE_VERDICTS = ("distinctive", "generic", "unfilled")

# ----------------------------------------------------------- punctuation scope
# House rule: Chinese text uses full-width punctuation. English does not, and
# the English README is the canonical one, so the punctuation gate must not run
# against it. Only these paths are checked.
PUNCT_CHECKED_SUFFIXES = (".zh-TW.md", ".zh-CN.md")
PUNCT_CHECKED_DIRS = ("docs/zh-TW", "docs/zh-CN")

# ---------------------------------------------------------------------------
# DECLARED PROSE, not enforced by code
#
# The two tuples below are statements of policy. No gate reads them, and none
# can: nothing here generates audio or images, so there is no output to inspect
# for them, and no amount of checking establishes what this tool cannot do.
#
# They are kept in the contract so the claims live next to the code they
# describe rather than only in a README that drifts, and they are listed in
# DECLARED rather than FROZEN so that nobody reads an enforced guarantee into
# them. An unenforced value sitting among enforced ones implies a check that is
# not running, which is the failure this separation exists to prevent.
#
# Both are surfaced in a build's report, so they reach the reader rather than
# sitting unread in a source file.
# ---------------------------------------------------------------------------

CAPABILITY_LIMITS = (
    "Cannot verify that a consent record is genuine; it checks structure only.",
    "Cannot establish that a source is authentic, correctly attributed, or current.",
    "Cannot determine whether a use is lawful in any given jurisdiction. Not legal advice.",
    "Cannot reconstruct judgement the sources never recorded; sparse material yields a sparse result, reported as such.",
    "Cannot detect that a subject has withdrawn consent after a build.",
)

# Every enforced contract value, enumerated. tests/test_no_false_furniture.py
# asserts that this tuple names each one and that each is read by code outside
# this module, so a value cannot be added here and left unwired, and cannot be
# wired and left out.
FROZEN = (
    "OUTPUT_SCOPES",
    "SOURCE_TIERS",
    "TIERS_ALWAYS_FORBIDDEN",
    "TIERS_REQUIRING_CONSENT",
    "CONSENT_REQUIRED_FIELDS",
    "HOLDOUT_MIN_ALIGNMENT",
    "HOLDOUT_MAX_UNKNOWN_RATIO",
    "IMPERSONATION_PATTERNS",
    "IMPERSONATION_RATIONALE_PRIVATE",
    "DISCLOSURE_REQUIRED_KEYS",
    "MEMO_REQUIRED_FIELDS",
    "MEMO_LOAD_BEARING_FIELDS",
    "MEMO_EMPTIABLE_FIELDS",
    "VERDICTS",
    "VERDICTS_REQUIRING_FLIP_CONDITION_KNOWN",
    "GAP_PERIPHERAL_KEY",
    "EVASION_PHRASES",
    "HEDGE_MARKERS",
    "STATEMENT_CLASSES",
    "ASSUMPTION_STATUSES",
    "THRESHOLD_NUMBER",
    "EVAL_MANIFEST_REQUIRED_FIELDS",
    "EVAL_RUN_REQUIRED_FIELDS",
    "EVAL_OBSERVATION_VALUES",
    "PUNCT_CHECKED_SUFFIXES",
    "PUNCT_CHECKED_DIRS",
    "SEATS",
    "SEAT_OBLIGATIONS",
    "SEAT_ENTRY_ORDER",
    "SEATS_ON_REQUEST_ONLY",
    "AUTHORSHIP_KINDS",
    "AUTHORSHIP_NOT_OWN_WORDS",
    "CONTRADICTION_REQUIRED_FIELDS",
    "CONTRADICTION_STATUSES",
    "SENSITIVITY_REQUIRED_FIELDS",
    "SEAT_PROFILE_VERDICTS",
)

# Read by code, and not yet justified by measurement.
#
# A number in FROZEN says "this was measured or argued, and changing it needs a
# version bump". Several numbers here were neither: they were picked because
# something had to go in the slot. Leaving them in FROZEN borrowed an authority
# they had not earned, and the frozen-contract machinery exists to protect
# decisions that were actually made.
#
# So they sit here, each with what would settle it. Changing one needs no
# version bump, because there is nothing yet to be faithful to. Moving one into
# FROZEN needs a measurement, the way MIN_SENTENCE_DENSITY was set from 190k
# characters of real text and HOLDOUT folding was set from a corpus experiment.
#
# The registry covers guessed numbers wherever they live, not only the ones in
# this file. Restricting it to this module was half the idea: the guesses had
# simply scattered into the modules that used them, which is harder to notice
# rather than better.
PROVISIONAL = {
    "HOLDOUT_MIN_ITEMS":
        "run holdout sets of varying size and find where the alignment figure "
        "stops moving with one more question",
    "HOLDOUT_MIN_DIVERGENT_ITEMS":
        "same, on the divergent slice only, which is where the gate reads",
    "CONFIDENCE_REQUIRING_NO_GAPS":
        "collect memos people actually wrote and find the confidence level "
        "above which an open gap reads as incoherent to a reader",
    "CONFIDENCE_REQUIRING_GAPS_NAMED":
        "same question from the other side",
    "CONTRADICTION_MAX_UNRESOLVED_RATIO":
        "reconstruct several subjects and compare the unresolved ratio against "
        "whether a usable method came out",
    "CONTRADICTION_UNRESOLVED_RATIO_FLOOR":
        "find the corpus size below which the ratio is noise",
    "SHORT_SOURCE_CHARS":
        "take real sources either side of the line and find where ambiguity "
        "about a quote's position actually starts",
    "DEFAULT_PARAGRAPH_GAP_MS":
        "compare paragraph breaks against where a human transcriber put them, "
        "on a transcript that has both",
    "MIN_LABEL_COVERAGE_TO_INHERIT":
        "collect transcripts that label every turn and transcripts that label "
        "only some, and find where the two populations separate",
    "MIN_DIVERGENT_PER_SEAT":
        "the same question as HOLDOUT_MIN_DIVERGENT_ITEMS, on a single seat's "
        "slice, which is smaller and therefore noisier",
    "MAX_SOURCE_BYTES":
        "measure the largest genuine public corpus for one subject; the limit "
        "only has to sit above that",
    "DEFAULT_CRAWL_DELAY_S":
        "nothing to measure here, only to respect: it applies when robots.txt "
        "names no crawl-delay, so it stays until a site complains or a "
        "convention settles",
}

# Policy stated in prose. No code reads these for a decision, and the same test
# asserts they are NOT in FROZEN, so the distinction cannot quietly collapse.
DECLARED = (
    "CAPABILITY_LIMITS",
    "OUT_OF_SCOPE_OUTPUTS",
    "SCOPE_DEPENDENT_GATES",
)
