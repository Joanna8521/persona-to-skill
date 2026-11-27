#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Make stdout and stderr take UTF-8, whatever the console claims.

One implementation, because the same bug has now appeared three times in this
project and once in the house-rules package it borrows from:

  * the punctuation gate reports a violation by quoting the line, and the lines
    it is most needed for contain Chinese;
  * the standalone test runner prints test names, and several of this project's
    tests are named in Chinese;
  * the canonical validate_punct.py in joan-skill-conventions printed a tick
    character, which took 34 packages with it before anyone noticed.

On a Windows console the default encoding is a legacy code page, so those
prints raise UnicodeEncodeError. The failure is worse than a crash: the process
exits non-zero either way, so a clean run and a genuinely broken one become
indistinguishable, both failing for a reason that has nothing to do with what
was being checked.

errors="replace" is deliberate. If a character cannot be encoded even after
this, print a replacement glyph rather than let one unprintable character
decide an exit code.
"""
from __future__ import annotations

import sys


def force_utf8(*streams) -> None:
    """Reconfigure the given streams, or stdout and stderr by default.

    Guarded: a stream that cannot be reconfigured (already wrapped, not a real
    stream, closed) is left alone rather than raising.
    """
    for stream in (streams or (sys.stdout, sys.stderr)):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
