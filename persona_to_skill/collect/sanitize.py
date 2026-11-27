#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Corpus text is downloaded from third parties, so it is hostile input.

This runs at ingest rather than at a gate, and the difference matters. If
stored text is already clean, the fingerprint covers the clean version and G2
never sees the attack. A gate that merely detected the problem would be
reporting on something already loaded.

A second pass over the corpus directory exists anyway, because a file placed
there by hand never went through ingest. Depth, not redundancy.

WHAT IS REMOVED, and the first one is the reason this file exists:

  Bidirectional overrides (U+202A-U+202E, U+2066-U+2069) reorder how text
  displays without changing the bytes. That is an attack aimed squarely at G2:
  the quote matches the source byte for byte, and a reader sees something else.
  A gate verifying bytes while a human reads glyphs is exactly the gap these
  characters open, and a prose corpus has no legitimate use for them; genuine
  right-to-left text works from its base direction.

  Zero-width space and the byte-order mark are invisible and can be inserted
  to break a match or to make two identical-looking strings differ.

  C0 and C1 controls other than tab and newline cannot appear in prose and can
  truncate or confuse downstream readers.

WHAT IS ONLY FLAGGED, because removing it would do damage:

  Zero-width joiner and non-joiner are load-bearing in emoji sequences and in
  several Indic scripts. Stripping them corrupts real text.

  Mixed-script words, narrowly: Cyrillic or Greek letters inside an otherwise
  Latin word, which is how a quote is forged to look identical. Latin mixed
  with CJK is flagged by nothing here, because it is ordinary ("iPhone 用戶").

  Instruction-shaped sentences. These cannot be filtered away and should not
  be: a transcript may legitimately contain somebody saying "ignore the
  previous instruction". The defence is structural rather than lexical, and it
  is stated in one line because it is the whole of it: CORPUS TEXT IS ONLY EVER
  QUOTED, NEVER FOLLOWED. The flag exists so a person can see what arrived.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ..gates import Verdict

GATE = "A-sanitize"

# Reorder display without changing bytes. No legitimate use in prose.
#
# U+061C ARABIC LETTER MARK belongs here and was missing. It is a bidi control
# like the rest, it just lives outside the two ranges below, so a set defined
# by those ranges looks complete and is not. Found by running every known
# carrier through clean() rather than by reading the ranges.
BIDI_CONTROLS = "".join(chr(c) for c in
                        list(range(0x202A, 0x202F))
                        + list(range(0x2066, 0x206A))) + "\u061c"

# Invisible, and not needed by any script.
#
# Four more were added after testing each one against clean():
#
#   U+00AD SOFT HYPHEN. The one with a consequence inside this project. G2
#   verifies a quote by matching it against the source byte for byte, and PDF
#   to text conversion inserts a soft hyphen at every hyphenation point. One
#   of them in the corpus makes a correct quote unanchorable, so the gate
#   refuses a claim that is true. That is a denial of service on the gate, and
#   it arrives through ordinary data rather than through an attacker.
#
#   U+034F COMBINING GRAPHEME JOINER. Invisible, and it breaks the same
#   matching. It does have uses in Hebrew collation, which this corpus will
#   not contain; the trade is stated rather than assumed.
#
#   U+FFF9 to U+FFFB, the interlinear annotation characters. They let a span
#   carry hidden annotation text that renderers drop.
#
#   U+1D173 to U+1D17A, musical format controls. Invisible in prose.
INVISIBLE_REMOVED = (
    "​‎‏﻿⁠᠎"
    "\u00ad\u034f"
    + "".join(chr(c) for c in range(0xFFF9, 0xFFFC))
    + "".join(chr(c) for c in range(0x1D173, 0x1D17B))
)

# The tag block, U+E0000 to U+E007F.
#
# This one is removed as a block, and the reason is its capacity rather than
# its visibility. Tag characters mirror the whole printable ASCII range, so a
# span of them carries an arbitrary hidden message: a complete set of
# instructions can sit inside a sentence that renders as the sentence alone.
# That is the ASCII smuggling technique, and prose is exactly where it hides.
#
# The cost, stated rather than glossed: subdivision flag emoji (England,
# Scotland, Wales) encode their subdivision in tag characters after U+1F3F4,
# so they degrade to a plain black flag. An exception for "tags preceded by
# U+1F3F4" would preserve them, and it would also be a hole with a rule around
# it, in the one place where a hole carries a full instruction channel. A tool
# that reconstructs a method from prose can lose three flags.
TAG_CHARACTERS = "".join(chr(c) for c in range(0xE0000, 0xE0080))

# Invisible and load-bearing: emoji sequences, Devanagari, Persian.
INVISIBLE_KEPT = "‌‍"

_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
_REMOVE = re.compile(
    f"[{re.escape(BIDI_CONTROLS + INVISIBLE_REMOVED + TAG_CHARACTERS)}]")

# Cyrillic or Greek inside an otherwise Latin word. Narrow on purpose: Latin
# next to CJK is ordinary and is not flagged.
_MIXED_SCRIPT = re.compile(
    r"\b(?=\w*[A-Za-z])(?=\w*[Ѐ-ӿͰ-Ͽ])\w+\b")

# Sentences shaped like an instruction to a model. Flagged, never removed.
_INSTRUCTION_SHAPED = re.compile(
    r"(?i)\b(ignore (?:all |the )?(?:previous|prior|above)|"
    r"disregard (?:all |the )?(?:previous|prior|above)|"
    r"you are now|new instructions?|system prompt|"
    r"act as (?:an? )?(?:ai|assistant|model))\b"
    r"|忽略(?:上面|先前|以上|前面)|你現在是|新的指令|系統提示")

# A corpus file larger than this is refused rather than read. Nothing a person
# wrote in public is this long, and reading it first is the cost an attacker
# wants to impose.
MAX_SOURCE_BYTES = 8 * 1024 * 1024


@dataclass
class Findings:
    removed: Dict[str, int] = field(default_factory=dict)
    flagged: Dict[str, List[str]] = field(default_factory=dict)

    @property
    def clean(self) -> bool:
        return not self.removed and not self.flagged

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if self.removed:
            out["removed"] = dict(self.removed)
        if self.flagged:
            out["flagged"] = {k: v[:5] for k, v in self.flagged.items()}
        return out


def _note(d: Dict[str, int], key: str, n: int) -> None:
    if n:
        d[key] = d.get(key, 0) + n


def clean(text: str) -> Tuple[str, Findings]:
    """Return (sanitised text, what was found).

    Order matters. NFC first, so a composed and a decomposed form of the same
    character are one thing before anything is counted or compared. Removal
    after, so a control character hidden inside a decomposition is still seen.
    """
    f = Findings()
    text = unicodedata.normalize("NFC", text)

    _note(f.removed, "bidi_control", len(re.findall(f"[{re.escape(BIDI_CONTROLS)}]", text)))
    _note(f.removed, "invisible", len(re.findall(f"[{re.escape(INVISIBLE_REMOVED)}]", text)))
    _note(f.removed, "control_character", len(_CONTROL.findall(text)))

    # Tag characters are counted AND decoded.
    #
    # The first version removed them and said nothing, because they were added
    # to the removal pattern and not to the counting above. Thirty-two of them
    # carrying a complete sentence came out silently, and the findings read as
    # though the source had been clean. A sanitiser that removes something
    # without saying so is a small version of the thing this project is about.
    #
    # Decoded rather than merely counted, because the block mirrors printable
    # ASCII, so the payload is recoverable and it is the single most useful
    # thing a reviewer can be told: not "32 invisible characters" but the
    # sentence somebody hid in a quote.
    tags = [c for c in text if c in TAG_CHARACTERS]
    if tags:
        _note(f.removed, "tag_character", len(tags))
        decoded = "".join(
            chr(ord(c) - 0xE0000) if 0xE0020 <= ord(c) <= 0xE007E else "\ufffd"
            for c in tags)
        f.flagged["tag_character_payload"] = [decoded[:200]]

    text = _REMOVE.sub("", text)
    text = _CONTROL.sub("", text)

    kept = [c for c in text if c in INVISIBLE_KEPT]
    if kept:
        f.flagged["zero_width_joiner_kept"] = [
            f"U+{ord(c):04X} x{kept.count(c)}" for c in sorted(set(kept))]

    mixed = _MIXED_SCRIPT.findall(text)
    if mixed:
        f.flagged["mixed_script_word"] = sorted(set(mixed))

    instructions = _INSTRUCTION_SHAPED.findall(text)
    if instructions:
        hits = [m if isinstance(m, str) else next(x for x in m if x) for m in instructions]
        f.flagged["instruction_shaped"] = sorted({h.strip() for h in hits if h})

    return text, f


def check(corpus_dir: str | Path) -> Verdict:
    """Second pass: the corpus directory as it stands on disk.

    Fails closed on a missing directory, and on anything that ingest would have
    removed, because its presence means the file did not come through ingest.
    """
    d = Path(corpus_dir)
    if not d.is_dir():
        return Verdict(GATE, False, [f"corpus directory {d} not found"])

    errors: List[str] = []
    warnings: List[str] = []
    checked = 0

    for path in sorted(d.rglob("*")):
        if not path.is_file():
            continue
        size = path.stat().st_size
        if size > MAX_SOURCE_BYTES:
            errors.append(
                f"{path.name}: {size / 1048576:.1f} MB, over the "
                f"{MAX_SOURCE_BYTES // 1048576} MB limit. Nothing written in public is "
                "this long; reading it is the cost an attacker wants to impose.")
            continue
        checked += 1
        raw = path.read_text(encoding="utf-8", errors="replace")
        cleaned, f = clean(raw)
        if cleaned != raw:
            errors.append(
                f"{path.name}: contains {', '.join(f.removed)} that ingest removes. "
                "Either it was placed here by hand, or ingest did not run. Bidirectional "
                "overrides matter most: they change how a quote displays without changing "
                "the bytes G2 verifies.")
        for kind, examples in f.flagged.items():
            warnings.append(f"{path.name}: {kind}: {', '.join(examples[:3])}")

    if not checked and not errors:
        return Verdict(GATE, False, [f"no readable files in {d}"])

    if any("instruction_shaped" in w for w in warnings):
        warnings.append(
            "Instruction-shaped text is flagged and kept. It cannot be filtered away and "
            "should not be: a transcript may legitimately contain somebody saying "
            "\"ignore the previous instruction\". Corpus text is only ever quoted, never "
            "followed.")

    return Verdict(GATE, not errors, errors, warnings, {"files_checked": checked})
