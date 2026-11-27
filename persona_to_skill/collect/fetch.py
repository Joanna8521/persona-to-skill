#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Whether a URL may be fetched, and what to do when it may not.

This project does not scrape. It fetches what is openly crawlable and asks for
everything else, and the line between those is not a judgement call: robots.txt
is the machine-readable statement of whether automated collection is permitted.
A page a general-purpose crawler may read is a page this may read, doing the
same thing search engines do. A page that disallows crawling is a page the user
supplies by another route.

That rule needs no hand-maintained list of platforms. X, Instagram and LinkedIn
disallow most crawling in their own robots.txt; blogs, newsletters, news sites,
court records and government archives generally allow it. The platforms
disallow it because their terms say so, and the file says the same thing in a
form code can read.

TWO AXES, AND THEY ARE NOT THE SAME AXIS. robots.txt governs whether text may
be FETCHED. The source tier governs whether it may be REPRODUCED. Crawlable
does not mean reusable: a news article is usually both openly crawlable and
fully copyrighted, which is T2, quoted briefly with attribution and never
reproduced whole. Conflating them would turn "we were allowed to read it" into
"we are allowed to republish it", which is a different claim entirely.

WHEN THE ANSWER IS NO, the tool says what to do instead rather than trying
harder. Three routes, with what each needs, because no single one covers
everybody:

  platform data export   works anywhere, needs no tooling, and is the only
                         route that is unambiguously clean for a subject's own
                         private material
  a tool the user runs   runs under their own credentials and their own
                         acceptance of the platform's terms, which is where
                         that responsibility belongs; needs whatever the tool
                         needs, and a browser extension needs that browser
  paste or upload        works anywhere, needs nothing, scales badly

The design point is that persona-to-skill defines the import contract and does
not care which route produced it. See importer.py.
"""
from __future__ import annotations

import time
import urllib.robotparser
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

# Honest about what it is. A crawler that claims to be a browser is lying about
# exactly the thing robots.txt exists to let a site decide.
USER_AGENT = "persona-to-skill"

# Only text. A binary body is not prose and reading one is a cost an attacker
# can choose.
ALLOWED_CONTENT_TYPES = (
    "text/plain", "text/html", "text/vtt", "text/markdown",
    "application/xhtml+xml", "application/json",
)

# Seconds between requests to one host, when robots.txt names no crawl-delay.
# PROVISIONAL: polite rather than measured.
DEFAULT_CRAWL_DELAY_S = 1.0

FETCH, IMPORT_ONLY = "fetch", "import_only"


@dataclass
class Decision:
    verdict: str            # FETCH or IMPORT_ONLY
    reason: str
    crawl_delay_s: float = DEFAULT_CRAWL_DELAY_S

    @property
    def may_fetch(self) -> bool:
        return self.verdict == FETCH


IMPORT_ROUTES = (
    "Export your data from the platform. Works anywhere, needs no tooling, and "
    "for the subject's own private material it is the only unambiguously clean "
    "route.",
    "Run your own collector. It acts under your credentials and your acceptance "
    "of the platform's terms, which is where that responsibility belongs. Note "
    "what the tool needs: a browser extension needs that browser, so it is not "
    "a route for everybody.",
    "Paste or upload the text. Works anywhere, needs nothing, scales badly.",
)


def decide(url: str, robots_txt: Optional[str]) -> Decision:
    """Decide from the URL and the site's robots.txt. Does no network work.

    `robots_txt` is None when the file could not be retrieved. That is treated
    as permission, because a site with no robots.txt has stated no restriction,
    which is how every crawler reads it. A site that means to restrict says so.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return Decision(IMPORT_ONLY, f"not an http(s) URL: {parsed.scheme or 'no scheme'}")
    if not parsed.netloc:
        return Decision(IMPORT_ONLY, "no host in the URL")

    if robots_txt is None:
        return Decision(FETCH, "no robots.txt retrieved, so no restriction stated")

    rp = urllib.robotparser.RobotFileParser()
    rp.parse(robots_txt.splitlines())

    if not rp.can_fetch(USER_AGENT, url):
        return Decision(
            IMPORT_ONLY,
            f"robots.txt disallows automated access to this path for "
            f"{USER_AGENT!r}. That is the site stating that collection here is "
            "not permitted, so it is not something to work around.")

    delay = rp.crawl_delay(USER_AGENT)
    return Decision(FETCH, "robots.txt permits automated access",
                    float(delay) if delay else DEFAULT_CRAWL_DELAY_S)


def content_type_ok(content_type: Optional[str]) -> Tuple[bool, str]:
    """Whether a response body is the kind of thing this reads."""
    if not content_type:
        return False, "no content type declared"
    base = content_type.split(";")[0].strip().lower()
    if base not in ALLOWED_CONTENT_TYPES:
        return False, (f"content type {base!r} is not text. This reads prose and "
                       "captions; a binary body is a cost an attacker can choose.")
    return True, base


class HostPacer:
    """One delay per host, so a run does not hammer a single site.

    Separate from `decide` because politeness is state and a decision is not.
    """

    def __init__(self, clock=time.monotonic, sleeper=time.sleep):
        self._last: Dict[str, float] = {}
        self._clock = clock
        self._sleep = sleeper

    def wait(self, url: str, delay_s: float) -> float:
        """Block until this host may be hit again. Returns the seconds waited."""
        host = urlparse(url).netloc
        now = self._clock()
        last = self._last.get(host)
        waited = 0.0
        if last is not None:
            remaining = delay_s - (now - last)
            if remaining > 0:
                self._sleep(remaining)
                waited = remaining
        self._last[host] = self._clock()
        return waited


def refusal_message(url: str, decision: Decision) -> str:
    """What to show a user when a URL cannot be fetched.

    Says what to do rather than only what failed, because the alternative is a
    user who concludes the tool is broken and goes looking for a scraper.
    """
    host = urlparse(url).netloc or url
    lines = [f"Not fetching {host}: {decision.reason}", "", "Instead:"]
    lines += [f"  {i}. {route}" for i, route in enumerate(IMPORT_ROUTES, 1)]
    lines.append("")
    lines.append("Any of these produce the same import format, so nothing downstream "
                 "changes with the route. See the importer.")
    return "\n".join(lines)
