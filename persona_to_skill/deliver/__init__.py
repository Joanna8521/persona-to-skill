# -*- coding: utf-8 -*-
"""Stage C: render the deliverables, gate them, and only then package.

Named "deliver" rather than "build". A package called build inside a Python
project collides with the universal name for build output, and with every
.gitignore that carries "build/" unanchored: this directory was silently
excluded from its own commit that way, so the tests referenced modules that
had never been pushed, everything passed locally, and CI was the only thing
that noticed.

The ordering is the whole point. See package.run for why rendering has to
happen before the gates and packaging strictly after them.
"""
