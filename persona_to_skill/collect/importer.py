#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The import contract. Anything that can produce this shape can feed the tool.

persona-to-skill fetches what is openly crawlable and asks for everything else
(see fetch.py). "Asks for" needs a format, and this is it: one record per
source, carrying what the gates need and nothing they do not.

Defining the contract instead of writing collectors is the better trade, and
not mainly for effort. Responsibility for a platform's terms stays with whoever
operates the collector, under their own credentials. The tool cannot become the
thing a platform reports for scraping. And it reaches platforms nobody here
will ever support.

NO ROUTE COVERS EVERYBODY, which is why the contract matters more than any one
producer. A browser extension needs that browser; a platform export needs the
account; pasting needs patience. All three produce this shape, so nothing
downstream changes with the route, and a user on an unsupported browser is not
a user with no path.

WHAT THE IMPORTER REFUSES TO GUESS:

  The tier. Whether a source is freely citable or copyright-restricted depends
  on the publication, not on anything in the record, so it is a parameter of
  the import rather than a field the importer invents. One tier per batch is
  how people actually import ("these are all public posts").

  The author. A captured post written by somebody else is not this subject's
  corpus. Where the record names an author who is not the subject, the record
  is reported and left out rather than quietly folded in, because folding it in
  is the misattribution this project exists to prevent.

  Whether the author is known at all. A collector that inferred the author from
  a post's first line says so, and that becomes authorship "unknown" rather
  than "self_written".
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..contract import AUTHORSHIP_KINDS, SOURCE_TIERS
from .sanitize import clean

# A record is this, and nothing here is optional except where said.
REQUIRED_FIELDS = ("id", "text", "platform", "url", "retrieved_at", "authorship")

_SLUG = re.compile(r"[^a-z0-9]+")


@dataclass
class ImportResult:
    accepted: List[Dict[str, Any]] = field(default_factory=list)
    rejected: List[Tuple[str, str]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def summary(self) -> Dict[str, Any]:
        return {"accepted": len(self.accepted), "rejected": len(self.rejected),
                "reasons": sorted({why for _, why in self.rejected})}


def source_id(platform: str, url: str, index: int) -> str:
    """A filesystem-safe, ASCII, single-component id.

    Single component on purpose: a source_id reaches a glob pattern, and
    "../secret" is a legal one. G2 rejects separators now, and generating one
    here would be a way to trip that gate from inside.
    """
    tail = _SLUG.sub("-", (url or "").rsplit("/", 1)[-1].lower()).strip("-")
    base = f"{_SLUG.sub('-', platform.lower()).strip('-') or 'src'}-{index:04d}"
    return f"{base}-{tail[:24]}" if tail else base


def normalise(record: Dict[str, Any], subject_name: str, tier: str,
              index: int) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Validate and clean one record. Returns (record, None) or (None, reason)."""
    text = str(record.get("text") or "")
    if not text.strip():
        return None, "no text"

    author = str(record.get("author") or "").strip()
    guessed = bool(record.get("author_guessed"))

    if author and not guessed and not _same_person(author, subject_name):
        return None, f"written by someone else ({author})"

    cleaned, findings = clean(text)
    if not cleaned.strip():
        return None, "nothing left after sanitising"

    out = {
        "id": record.get("id") or source_id(str(record.get("platform") or "src"),
                                            str(record.get("url") or ""), index),
        "text": cleaned,
        "platform": str(record.get("platform") or "unknown"),
        "url": str(record.get("url") or ""),
        "retrieved_at": record.get("retrieved_at"),
        "published": record.get("published"),
        "tier": tier,
        # A collector that had to infer the author from a post's first line has
        # not established who wrote it.
        "authorship": "unknown" if (guessed or not author) else "self_written",
        "kind": record.get("kind") or "text",
    }
    if record.get("thread_id"):
        out["thread_id"] = str(record["thread_id"])
        out["thread_index"] = int(record.get("thread_index") or 0)
    if record.get("embedded_other_party"):
        # A quote-post carries somebody else's words inside the subject's. Kept
        # and marked, the same way a transcript keeps an interviewer's turn.
        out["embedded_other_party"] = str(record["embedded_other_party"])
    if not findings.clean:
        out["sanitised"] = findings.to_dict()
    return out, None


def _same_person(author: str, subject_name: str) -> bool:
    a = re.sub(r"[^\w一-鿿]+", " ", author).strip().lower()
    b = re.sub(r"[^\w一-鿿]+", " ", subject_name).strip().lower()
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    pa, pb = a.split(), b.split()
    return bool(pa and pb and (pa[-1] == pb[-1] or pa[0] == pb[0]))


def import_records(records: Iterable[Dict[str, Any]], subject_name: str,
                   tier: str) -> ImportResult:
    """Take records in the contract shape and return what is usable.

    `tier` is a parameter rather than a field, because whether a source is
    freely citable depends on the publication and nothing in the record says.
    """
    if tier not in SOURCE_TIERS:
        raise ValueError(f"unknown tier {tier!r}; expected one of {list(SOURCE_TIERS)}")

    result = ImportResult()
    for i, rec in enumerate(records):
        out, why = normalise(rec, subject_name, tier, i)
        if out is None:
            result.rejected.append((str(rec.get("url") or rec.get("id") or i), why or ""))
        else:
            result.accepted.append(out)

    threads = {r["thread_id"] for r in result.accepted if r.get("thread_id")}
    if threads:
        result.notes.append(
            f"{len(threads)} thread(s) present. A thread is one argument across several "
            "posts, so its parts are joined before storage for the same reason caption "
            "cues are: a quote spanning two posts would otherwise fail G2 on a boundary "
            "the storage invented.")
    unknown = sum(1 for r in result.accepted if r["authorship"] == "unknown")
    if unknown:
        result.notes.append(
            f"{unknown} record(s) with authorship unknown, because the collector inferred "
            "the author rather than reading it. Claims resting on them are not blocked, "
            "but nothing establishes the words are the subject's own.")
    return result


def join_threads(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Join a thread's posts into one source, in order.

    Same reasoning as joining caption cues: the unit of argument is the thread,
    and a quote crossing two posts would otherwise fail against a boundary the
    storage invented.
    """
    singles = [r for r in records if not r.get("thread_id")]
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        if r.get("thread_id"):
            grouped.setdefault(r["thread_id"], []).append(r)

    joined = []
    for tid, parts in sorted(grouped.items()):
        parts.sort(key=lambda r: r.get("thread_index", 0))
        head = dict(parts[0])
        head["text"] = "\n\n".join(p["text"] for p in parts)
        head["thread_parts"] = len(parts)
        head.pop("thread_index", None)
        joined.append(head)
    return singles + joined


def write_corpus(records: List[Dict[str, Any]], corpus_dir: str | Path,
                 manifest_path: str | Path | None = None) -> Dict[str, Any]:
    """Write one file per source, plus the manifest G1 reads."""
    d = Path(corpus_dir)
    d.mkdir(parents=True, exist_ok=True)
    manifest = []
    for r in records:
        if "/" in r["id"] or "\\" in r["id"] or r["id"].startswith("."):
            raise ValueError(f"unusable source id {r['id']!r}")
        (d / f"{r['id']}.txt").write_text(r["text"], encoding="utf-8")
        entry = {k: v for k, v in r.items() if k != "text"}
        manifest.append(entry)
    if manifest_path:
        Path(manifest_path).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
    return {"files": len(manifest), "corpus_dir": str(d), "sources": manifest}


# --------------------------------------------------------------------- adapters
def from_postsync(captures: Iterable[Dict[str, Any]], subject_name: str,
                  tier: str) -> ImportResult:
    """Adapt Post Sync's capture records.

    Post Sync (github.com/Joanna8521/PostSync) is a browser extension that
    saves a social post when its user clicks, under that user's own
    credentials, with no automated collection and no auto-scrolling. That is
    the "a tool the user runs" route in fetch.py, and the reason it is the
    route rather than something this project does itself.

    Its records already carry what is needed, including one field worth
    naming: `authorGuessed` is set when the author could not be read from the
    page and was inferred from a post's first line. That is this project's
    authorship axis arriving for free, so it maps to authorship "unknown"
    rather than being discarded.
    """
    mapped = []
    for c in captures:
        mapped.append({
            "text": c.get("text"),
            "author": c.get("author"),
            "author_guessed": c.get("authorGuessed"),
            "platform": c.get("platform") or c.get("platformLabel"),
            "url": c.get("permalink") or c.get("pageUrl"),
            "retrieved_at": c.get("capturedAt"),
            "published": c.get("timeText"),
            "thread_id": c.get("threadId"),
            "thread_index": c.get("threadIndex"),
            "embedded_other_party": c.get("quotedText"),
            "kind": "text",
        })
    return import_records(mapped, subject_name, tier)


ADAPTERS = {"postsync": from_postsync}


def known_authorship_kinds() -> Tuple[str, ...]:
    return AUTHORSHIP_KINDS
