#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Punctuation gate for the documentation.

Two rules, with different scopes, and the difference is the point.

DASHES are banned in every Markdown file, English included. Em dash, en dash,
and a double hyphen used as prose punctuation. A sentence that wants a break
takes a colon, a comma, a full stop or a rewrite.

FULL-WIDTH punctuation is required only in Chinese files. Chinese sets commas,
full stops, colons, brackets and quotes full-width, with half-width reserved
for Latin letters, digits, code and URLs. That rule is about Chinese
typography, so it is not applied to English, and it is NOT applied to Japanese:
Japanese writes 、 and 。 where Chinese writes ，and 。, so checking Japanese
against the Chinese table would flag correct text as wrong.

Scope comes from contract.PUNCT_CHECKED_SUFFIXES and PUNCT_CHECKED_DIRS, which
until now were declared and read by nothing. A frozen value no code consults is
worse than no value: it implies a check that is not running, and a test
asserting its shape makes it look verified.

Scope is Markdown only. Python docstrings and comments use "--" as an ordinary
developer convention, and an English-canonical repository that forbade it there
would be odd; the rule here is about the documents people read.

Usage:
    python3 -m persona_to_skill.validate_punct [path ...]

Exit code 1 on any violation, so CI can gate on it.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from .contract import PUNCT_CHECKED_DIRS, PUNCT_CHECKED_SUFFIXES

CJK = r"㐀-䶿一-鿿豈-﫿"

# Dash variants, banned everywhere. U+30FC (ー) is a Japanese letter, not a
# dash, and is not matched.
DASH = re.compile(r"[—–―−]")

# A double hyphen as prose. Table rules (|---|), front-matter fences and
# command-line flags (--fix) are not prose, so they are excluded by requiring a
# space before and after.
PROSE_DOUBLE_HYPHEN = re.compile(r"(?<=\s)--(?=\s)")

# Half-width punctuation directly after a Chinese character. A digit or Latin
# letter after it means the mark belongs to code or a number (1,000 / 3.5), so
# those are not flagged.
HALF_AFTER_CJK = re.compile(rf"[{CJK}]([,;:!?])(?![0-9A-Za-z])|[{CJK}](\.)(?![0-9A-Za-z])")
HALF_BRACKET_AFTER_CJK = re.compile(rf"[{CJK}](\()|\)(?=[{CJK}])")
STRAIGHT_QUOTE_AROUND_CJK = re.compile(rf'"(?=[{CJK}])|(?<=[{CJK}])"')

# Fenced code, inline code and HTML attributes are exempt from the full-width
# rule: half-width there is correct.
CODE_FENCE = re.compile(r"^```")
INLINE_CODE = re.compile(r"`[^`]*`")
HTML_TAG = re.compile(r"<[^>]+>")
URL = re.compile(r"https?://\S+")


def in_fullwidth_scope(path: Path) -> bool:
    """Whether the Chinese typography rule applies to this file."""
    name = path.name
    if any(name.endswith(sfx) for sfx in PUNCT_CHECKED_SUFFIXES):
        return True
    posix = path.as_posix()
    return any(f"/{d}/" in f"/{posix}" or posix.startswith(f"{d}/")
               for d in PUNCT_CHECKED_DIRS)


def _strip_exempt(line: str) -> str:
    return URL.sub(" ", HTML_TAG.sub(" ", INLINE_CODE.sub(" ", line)))


def check_file(path: Path) -> List[Tuple[int, str, str]]:
    """Return [(line_number, rule, excerpt)] for every violation."""
    out: List[Tuple[int, str, str]] = []
    fullwidth = in_fullwidth_scope(path)
    in_code = False

    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if CODE_FENCE.match(raw.strip()):
            in_code = not in_code
            continue
        if in_code:
            continue
        line = _strip_exempt(raw)

        for m in DASH.finditer(line):
            out.append((n, "dash variant", raw.strip()[:90]))
            break
        if PROSE_DOUBLE_HYPHEN.search(line):
            out.append((n, "double hyphen as prose", raw.strip()[:90]))

        if not fullwidth:
            continue
        if HALF_AFTER_CJK.search(line):
            out.append((n, "half-width punctuation after Chinese", raw.strip()[:90]))
        if HALF_BRACKET_AFTER_CJK.search(line):
            out.append((n, "half-width bracket around Chinese", raw.strip()[:90]))
        if STRAIGHT_QUOTE_AROUND_CJK.search(line):
            out.append((n, "straight quote around Chinese", raw.strip()[:90]))
    return out


def check_paths(paths: Iterable[Path]) -> Dict[Path, List[Tuple[int, str, str]]]:
    found: Dict[Path, List[Tuple[int, str, str]]] = {}
    for p in paths:
        hits = check_file(p)
        if hits:
            found[p] = hits
    return found


def _collect(args: List[str]) -> List[Path]:
    if args:
        out: List[Path] = []
        for a in args:
            p = Path(a)
            out.extend(sorted(p.rglob("*.md")) if p.is_dir() else [p])
        return out
    return sorted(Path(".").rglob("*.md"))


def main(argv: List[str]) -> int:
    paths = [p for p in _collect(argv) if ".git" not in p.parts]
    if not paths:
        print("no Markdown files to check")
        return 0

    found = check_paths(paths)
    scoped = [p for p in paths if in_fullwidth_scope(p)]
    print(f"checked {len(paths)} file(s); "
          f"{len(scoped)} under the Chinese typography rule")
    for p in scoped:
        print(f"  full-width scope: {p}")

    if not found:
        print("clean")
        return 0
    for p, hits in found.items():
        print(f"\n{p}")
        for n, rule, excerpt in hits:
            print(f"  line {n}: {rule}\n    {excerpt}")
    print(f"\n{sum(len(v) for v in found.values())} violation(s)")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
