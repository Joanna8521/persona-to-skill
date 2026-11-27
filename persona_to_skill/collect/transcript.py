#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Captions and transcripts into prose that a quote can be found in.

Caption tracks are segmented by display timing, not by sentence, so a sentence
routinely runs across several cues and cues carry their own line breaks for
on-screen wrapping. Stored cue-by-cue, such a source defeats G2 for a reason
that has nothing to do with whether anyone misquoted anyone: the quote spans a
boundary the storage invented.

Measured on a real human-written transcript of a talk, 427 cues:

    cues ending on sentence punctuation      59%
    cues ending mid-sentence                 41%
    cues beginning lower-case                28%

So two in five quotes drawn across a cue boundary would have failed. Joining is
not a nicety.

Rejoining is also exactly what was already needed for hard-wrapped prose; see
experiments/g2_realcorpus.py, where every passage crossing a wrap point failed
to match before wrapped lines were rejoined.

Nothing here edits words. Cues are concatenated, display wrapping is undone,
and paragraph breaks are placed where the source itself shows one.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

# A paragraph break needs BOTH a finished sentence and a pause. Either alone
# fires constantly: a speaker pauses mid-sentence, and a sentence ends every
# few seconds. The pause length is a formatting choice with no bearing on what
# the words are, which is why it is not a frozen contract.
DEFAULT_PARAGRAPH_GAP_MS = 2500

_TIMECODE = re.compile(
    r"(?P<h>\d{1,2}):(?P<m>\d{2}):(?P<s>\d{2})[.,](?P<ms>\d{1,3})"
    r"\s*-->\s*"
    r"(?P<h2>\d{1,2}):(?P<m2>\d{2}):(?P<s2>\d{2})[.,](?P<ms2>\d{1,3})")
# WebVTT allows mm:ss.mmm as well as hh:mm:ss.mmm
_TIMECODE_SHORT = re.compile(
    r"(?P<m>\d{1,2}):(?P<s>\d{2})[.,](?P<ms>\d{1,3})"
    r"\s*-->\s*"
    r"(?P<m2>\d{1,2}):(?P<s2>\d{2})[.,](?P<ms2>\d{1,3})")
_VTT_TAG = re.compile(r"</?(?:v|c|i|b|u|lang|ruby|rt)(?:[. ][^>]*)?>", re.I)
_VTT_TS_TAG = re.compile(r"<\d{2}:\d{2}:\d{2}[.,]\d{1,3}>")
_SENTENCE_FINAL = re.compile(r"[.!?。！？][\"'”’）)\]]*\s*$")
# Bracketed stage directions: (Laughter), [MUSIC], （笑聲）
_NON_SPEECH = re.compile(r"^\s*[\(\[（【][^)\]）】]{0,40}[\)\]）】]\s*$")

# ------------------------------------------------------- speaker attribution
# A transcript carries other people's words: an interviewer, an audience, a
# co-panellist. Stored as one undifferentiated stream, those become quotable as
# the subject's, and G2 would pass such a quote correctly, because the words
# really are in the source. That is misattribution produced by the storage, and
# it is the exact failure this project exists to prevent.
#
# Found in real data, not reasoned about: a human transcript of a talk stored
# "(Audience) Good." inline, two cues after the speaker's own first sentence.
#
# So speaker turns are detected and tagged. Nothing is deleted: a question put
# to the subject is context worth keeping, it just is not something the subject
# said. Tagging lets a later stage refuse to anchor a claim about the subject
# to a passage somebody else spoke.
# All three patterns avoid putting \s* next to a character class that itself
# matches whitespace. That overlap makes the same run of spaces splittable many
# ways, and the engine tries them all before failing.
#
# _ARROW_SPEAKER was written with it and measured polynomial: ">>" followed by
# spaces and no colon took 4ms at 200 characters, 19ms at 400, 80ms at 800,
# 293ms at 1600, so roughly 290s at 50k. Caption files come from third parties.
# CodeQL did not flag this one (it reported the exponential _VTT_VOICE), and
# tests/test_redos.py found it by feeding every pattern its own worst case
# rather than checking the one instance already known about.
#
# The names are stripped in split_speaker, so the patterns do not need to
# absorb surrounding whitespace themselves.
_BRACKET_SPEAKER = re.compile(
    "^[ \t]*[(\uff08][ \t]*(?P<who>[^)\uff09\n]{1,30}?)[)\uff09][ \t]*(?P<rest>.+)$", re.S)
_ARROW_SPEAKER = re.compile(
    "^[ \t]*>>[ \t]*(?P<who>[^:\uff1a\n]{1,30}?)[:\uff1a][ \t]*(?P<rest>.*)$", re.S)
# A full-width colon carries no following space in Chinese or Japanese, so the
# space is optional after it and required after the ASCII one; without that
# asymmetry "ratio:" inside an English sentence starts matching.
_LABEL_SPEAKER = re.compile(
    "^[ \t]*(?P<who>[A-Z][A-Za-z.' -]{1,28}|[\u4e00-\u9fff]{2,10})"
    "(?:[\uff1a][ \t]*|:[ \t]+)(?P<rest>.*)$", re.S)

_SPEAKER_PATTERNS = (_BRACKET_SPEAKER, _ARROW_SPEAKER, _LABEL_SPEAKER)
# <v Name>, <v.loud Name>, <v.loud.red Name>. The cue classes are
# dot-separated, but "." is already inside [^ >], so one quantifier covers the
# whole prefix.
#
# It was written as "<v(?:\.[^ >]*)*\s+..." first, which is a quantifier
# inside a quantified group: the exponential backtracking shape. Measured on
# "<v" followed by dots and no space, so the match is forced to fail:
# 18 dots 11ms, 22 dots 243ms, 26 dots 2.9s. Caption files are downloaded from
# third parties, so a forty-character file would have hung the pipeline, which
# SECURITY.md names as a vulnerability class in this project rather than a
# style problem. Found by CodeQL on the pull request.
_VTT_VOICE = re.compile("<v[^ >]*\\s+(?P<who>[^>]+)>", re.I)

# Labels that are never the subject speaking, whatever the subject is called.
NON_SUBJECT_LABELS = (
    "audience", "laughter", "applause", "music", "crosstalk", "interviewer",
    "host", "narrator", "voiceover", "moderator", "question", "questioner",
    "\u89c0\u773e", "\u8046\u773e", "\u4e3b\u6301\u4eba", "\u65c1\u767d",
    "\u63d0\u554f", "\u8a18\u8005", "\u7ffb\u8b6f",
)


def _plausible_label(who: str) -> bool:
    """Whether a candidate reads like a name or role rather than prose.

    A Latin label is written as a name is written: every word capitalised, or
    the whole thing in capitals, and few words. CJK has no case, so length
    carries the constraint there.
    """
    if re.fullmatch(r"[\u4e00-\u9fff]{2,10}", who):
        return True
    words = [w for w in re.split(r"[ \-.']+", who) if w]
    if not words or len(words) > 3:
        return False
    return all(w.isupper() or (w[:1].isupper() and w[1:].islower() or len(w) == 1)
               for w in words)


def split_speaker(text):
    """Return (speaker_or_None, remaining_text, inline).

    Only a label at the very start of a cue counts; a colon inside a sentence
    is punctuation, not attribution.

    `inline` separates the two ways transcripts mark a speaker, which have
    different reach:

        (Audience) Good.      bracketed, an interjection, this cue only
        INTERVIEWER: Why?     colon-prefixed, a turn, until the next label

    Conflating them is not cosmetic. On a real 427-cue transcript, treating one
    bracketed "(Audience)" as a turn change reassigned the remaining 382 cues
    away from the speaker.
    """
    for pat in _SPEAKER_PATTERNS:
        m = pat.match(text)
        if not m:
            continue
        who = m.group("who").strip()
        rest = m.group("rest").strip()
        if not (who and rest):
            continue
        if not _plausible_label(who):
            # "I said: never discount." is a sentence, not an attribution. The
            # false positive matters more than the miss: mislabelling the
            # subject's own words as another speaker's would drop them from
            # what can be quoted as theirs.
            continue
        return who, rest, pat is _BRACKET_SPEAKER
    return None, text.strip(), False


def is_non_subject(speaker):
    """Whether a detected label is someone other than the subject by definition."""
    if not speaker:
        return False
    low = speaker.strip().lower()
    return any(lbl in low for lbl in NON_SUBJECT_LABELS)



@dataclass
class Cue:
    start_ms: int
    text: str
    end_ms: Optional[int] = None


def _ms(h: str, m: str, s: str, ms: str) -> int:
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms.ljust(3, "0"))


def parse_vtt(raw: str) -> List[Cue]:
    """Parse WebVTT or SRT. One format reader: they differ only in the
    separator inside a timecode and in SRT's leading index line."""
    cues: List[Cue] = []
    blocks = re.split(r"\n\s*\n", raw.replace("\r\n", "\n").replace("\r", "\n"))
    for block in blocks:
        lines = [ln for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        times = None
        body_from = 0
        for i, ln in enumerate(lines[:3]):
            m = _TIMECODE.search(ln)
            if m:
                times = (_ms(m["h"], m["m"], m["s"], m["ms"]),
                         _ms(m["h2"], m["m2"], m["s2"], m["ms2"]))
                body_from = i + 1
                break
            m = _TIMECODE_SHORT.search(ln)
            if m:
                times = (_ms("0", m["m"], m["s"], m["ms"]),
                         _ms("0", m["m2"], m["s2"], m["ms2"]))
                body_from = i + 1
                break
        if times is None:
            continue                      # WEBVTT header, NOTE, STYLE, stray index
        body = "\n".join(lines[body_from:])
        voice = _VTT_VOICE.search(body)
        body = _VTT_TS_TAG.sub("", _VTT_TAG.sub("", body))
        if body.strip():
            if voice:
                # Recover <v Name> before the tag stripper discards it.
                body = f"{voice.group('who').strip()}: {body.strip()}"
            cues.append(Cue(start_ms=times[0], text=body, end_ms=times[1]))
    return cues


def parse_cue_list(items: Sequence[Dict[str, Any]]) -> List[Cue]:
    """Accept an already-structured cue list, as several transcript APIs give."""
    out: List[Cue] = []
    for it in items:
        text = it.get("text") or it.get("content") or ""
        if not str(text).strip():
            continue
        start = it.get("time", it.get("start", it.get("offset", 0)))
        try:
            start_ms = int(float(start))
        except (TypeError, ValueError):
            start_ms = 0
        dur = it.get("duration", it.get("dur"))
        end = None
        if dur is not None:
            try:
                end = start_ms + int(float(dur))
            except (TypeError, ValueError):
                end = None
        out.append(Cue(start_ms=start_ms, text=str(text), end_ms=end))
    return out


def join_cues(cues: Iterable[Cue],
              paragraph_gap_ms: int = DEFAULT_PARAGRAPH_GAP_MS,
              drop_non_speech: bool = True) -> str:
    """Join cues into paragraphs, changing no words.

    A paragraph break is placed only where the previous cue finished a sentence
    AND the gap to the next one exceeds `paragraph_gap_ms`. Requiring both is
    deliberate: a speaker pauses mid-sentence often, and sentences end
    constantly, so either signal alone breaks paragraphs at random.
    """
    paragraphs: List[List[str]] = []
    current: List[str] = []
    prev: Optional[Cue] = None

    for cue in cues:
        text = re.sub(r"\s*\n\s*", " ", cue.text).strip()
        if not text:
            continue
        if drop_non_speech and _NON_SPEECH.match(text):
            # (Laughter), [MUSIC]. Not words the subject said, and quoting them
            # as the subject's would be wrong.
            prev = cue
            continue

        if prev is not None and current:
            gap = cue.start_ms - (prev.end_ms if prev.end_ms is not None else prev.start_ms)
            if gap >= paragraph_gap_ms and _SENTENCE_FINAL.search(current[-1]):
                paragraphs.append(current)
                current = []
        current.append(text)
        prev = cue

    if current:
        paragraphs.append(current)
    return "\n".join(re.sub(r"\s{2,}", " ", " ".join(p)).strip() for p in paragraphs)


def ingest(raw: str = "", cue_items: Optional[Sequence[Dict[str, Any]]] = None,
           **extra: Any) -> Dict[str, Any]:
    """Turn a caption track into stored text plus its measurement.

    Returns {"text": ..., "provenance": {...}}. The provenance records that the
    source arrived cue-segmented and how many cues were joined, so a later
    reader can see that this prose was assembled rather than published.
    """
    from .provenance import measure

    cues = parse_cue_list(cue_items) if cue_items is not None else parse_vtt(raw)
    text = join_cues(cues, **{k: v for k, v in extra.items()
                              if k in ("paragraph_gap_ms", "drop_non_speech")})
    prov = measure(
        text, kind="transcript",
        cue_segmented=True,
        cues_joined=len(cues),
        declared_track_kind=extra.get("declared_track_kind"),
        notes=list(extra.get("notes") or []),
    )
    return {"text": text, "provenance": prov.to_dict()}


# --------------------------------------------------------------- attribution
# Label detection is heuristic and always will be: Chinese and Japanese carry
# no case, so "我覺得：這樣不行" ("I think: this will not work") looks exactly
# like an attribution. The design therefore tolerates error instead of
# depending on precision, the same way G4 treats an unrecorded observation.
#
# A turn is the subject's only when the label matches the subject. It is
# somebody else's only when the label says so outright. Everything else is
# UNKNOWN: surfaced for a person to resolve, never silently assigned. Guessing
# in either direction is the failure -- guess "subject" and another person's
# words become quotable as theirs; guess "other" and the subject's own words
# are dropped from what can be quoted.
SUBJECT = "subject"
OTHER = "other"
UNKNOWN_SPEAKER = "unknown"


def _same_person(label: str, subject_name: str) -> bool:
    """Whether a transcript label names the subject.

    Deliberately narrow. A transcript writes a name as "JOHN", "John Smith" or
    a surname alone, so those match; anything looser would start matching
    unrelated people.
    """
    a = re.sub(r"[^\w一-鿿]+", " ", label).strip().lower()
    b = re.sub(r"[^\w一-鿿]+", " ", subject_name).strip().lower()
    if not a or not b:
        return False
    if a == b:
        return True
    pa, pb = [w for w in a.split() if w], [w for w in b.split() if w]
    if pa and pb and (pa == pb[-1:] or pa == pb[:1]):
        return True          # surname or given name alone
    return bool(re.fullmatch(r"[一-鿿]{2,10}", b)) and (a in b or b in a)


# An unlabelled cue after a turn marker belongs to that turn only if the
# transcript labels its turns consistently. Where only some turns are marked --
# commonly just the interviewer's questions -- inheriting the last label
# assigns the subject's own answers to somebody else, which is the worst
# direction to be wrong in. So inheritance is conditional on how much of the
# transcript is actually labelled, and below this it yields UNKNOWN instead.
#
# The figure is a shape, not a fine judgement: a consistently labelled
# interview marks a label every few cues, while a monologue with one
# interjection marks almost none. Anything in the middle of that range behaves
# the same.
MIN_LABEL_COVERAGE_TO_INHERIT = 0.25


def attribute(cues: Iterable[Cue], subject_name: str) -> Dict[str, Any]:
    """Tag each cue with whose words it carries, and keep what prompted it.

    Other speakers are context, not contamination. A question determines what
    an answer means: "Not always." says nothing without the "Always?" before
    it, and material where the subject is pushed is the most informative
    material there is. So non-subject turns are kept and marked, and each
    subject turn records the turn that prompted it.

    What the marking buys is narrow and important: a claim attributed to the
    subject has to anchor in a SUBJECT turn, while the question that gives it
    meaning travels with it as somebody else's words.
    """
    cue_list = list(cues)
    turns: List[Dict[str, Any]] = []
    counts = {SUBJECT: 0, OTHER: 0, UNKNOWN_SPEAKER: 0}
    labels_seen: Dict[str, int] = {}
    current_class = SUBJECT          # before any label, a transcript is the subject
    current_label: Optional[str] = None

    # Measure labelling density first, so inheritance is decided on what this
    # transcript actually looks like rather than on an assumption about
    # transcripts in general.
    speech = [c for c in cue_list
              if c.text.strip() and not _NON_SPEECH.match(re.sub(r"\s*\n\s*", " ", c.text).strip())]
    turn_markers = 0
    for c in speech:
        who, _, inline = split_speaker(re.sub(r"\s*\n\s*", " ", c.text).strip())
        if who and not inline:
            turn_markers += 1
    coverage = (turn_markers / len(speech)) if speech else 0.0
    may_inherit = coverage >= MIN_LABEL_COVERAGE_TO_INHERIT

    for cue in cue_list:
        text = re.sub(r"\s*\n\s*", " ", cue.text).strip()
        if not text or _NON_SPEECH.match(text):
            continue
        who, rest, inline = split_speaker(text)
        cue_class, cue_label = current_class, current_label
        if who:
            labels_seen[who] = labels_seen.get(who, 0) + 1
            if _same_person(who, subject_name):
                cue_class, cue_label = SUBJECT, who
            elif is_non_subject(who):
                cue_class, cue_label = OTHER, who
            else:
                cue_class, cue_label = UNKNOWN_SPEAKER, who
            text = rest
            if not inline:
                # A turn marker holds until the next label; an interjection
                # does not, so the running speaker is left as it was.
                current_class, current_label = cue_class, cue_label
        elif not may_inherit and current_class != SUBJECT:
            # Sparsely labelled: carrying the last non-subject label forward
            # would be a guess, and the costly kind.
            cue_class, cue_label = UNKNOWN_SPEAKER, None
        if not text:
            continue
        counts[cue_class] += 1
        if turns and turns[-1]["speaker_class"] == cue_class \
                and turns[-1]["label"] == cue_label:
            turns[-1]["cues"].append(text)
        else:
            turns.append({"speaker_class": cue_class, "label": cue_label,
                          "cues": [text], "start_ms": cue.start_ms})

    unresolved = sorted(
        (lbl for lbl in labels_seen
         if not _same_person(lbl, subject_name) and not is_non_subject(lbl)),
        key=lambda x: -labels_seen[x])

    # Attach what prompted each subject turn. The preceding non-subject turn is
    # the question, the challenge or the disagreement that makes the answer
    # legible, and it is the reason dialogue yields more than monologue.
    for i, turn in enumerate(turns):
        if turn["speaker_class"] != SUBJECT:
            continue
        # Walk back for what prompted this. A bare interjection between two of
        # the subject's own turns did not prompt anything: the subject is
        # continuing an answer through it, so that earlier turn's prompt is
        # still the one in force.
        for prev in reversed(turns[:i]):
            if prev["speaker_class"] == SUBJECT:
                if "prompted_by" in prev:
                    turn["prompted_by"] = dict(prev["prompted_by"])
                    turn["continues_through_interjection"] = True
                break
            if _NON_SPEECH.match(" ".join(prev["cues"])) or len(" ".join(prev["cues"])) < 25:
                continue      # an interjection, not a question
            turn["prompted_by"] = {
                "speaker_class": prev["speaker_class"],
                "label": prev["label"],
                "text": " ".join(prev["cues"]),
            }
            break

    return {
        "turns": turns,
        "counts": counts,
        "labels_seen": labels_seen,
        "unresolved_labels": unresolved,
        "label_coverage": round(coverage, 3),
        "inherited_labels": may_inherit,
    }
