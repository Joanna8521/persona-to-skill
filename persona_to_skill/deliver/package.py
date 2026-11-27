#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gate, then package. The ordering carries the design.

Installing a skill is a manual step, and installing one inside a conversation
lasts only for that conversation, so every correction costs the user a
reinstall. A pipeline whose trigger for revalidation is the user noticing a
misattribution has put its quality control after its most expensive step.

So: nothing is packaged until every gate passes, and the gates run on the
rendered text rather than on the bundle that produced it.

That second clause is why render comes before gate here. G3 refuses
impersonation in published output, and the thing that could impersonate is the
generated SKILL.md, not the structured bundle. A gate that checked the bundle
would be checking something nobody reads.

The zip is named with the version and the inner directory is not. The filename
answers "which of these three downloads is current"; the inner directory is the
install path, and if it moved with the version every update would add a copy
instead of replacing one.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..collect import sanitize as sanitize_gate
from ..extract import contradictions as contradictions_gate
from ..extract import profile as profile_gate
from ..extract import seats as seats_gate
from ..extract import sensitivity as sensitivity_gate
from ..gates import Verdict
from ..gates import anchor as anchor_gate
from ..gates import consent as consent_gate
from ..gates import disclosure as disclosure_gate
from ..gates import holdout as holdout_gate
from ..gates import interrogation as interrogation_gate
from . import render

# Windows cannot open these, and a skill installer that meets one rejects the
# whole archive, so they are refused before anything is written.
ILLEGAL = set('<>:"|?*') | {chr(c) for c in range(32)}
RESERVED = {"CON", "PRN", "AUX", "NUL"} | {
    f"{p}{i}" for p in ("COM", "LPT") for i in range(1, 10)}


def corpus_fingerprint(corpus_dir: Path) -> str:
    """A short digest of the corpus as it stood at build time.

    Stamped into sources.json so a user holding two installs can tell which
    corpus each came from. Deliberately covers content, not timestamps: a
    re-download that changes nothing should fingerprint the same.
    """
    h = hashlib.sha256()
    for path in sorted(Path(corpus_dir).rglob("*")):
        if path.is_file():
            h.update(path.relative_to(corpus_dir).as_posix().encode("utf-8"))
            h.update(hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()[:16]


# A slug becomes a directory inside the zip and part of the filename beside
# it, so it is a path, and a path that comes out of the bundle is a path
# somebody else chose. `../../escaped` passed straight through and the zip
# landed outside the directory the caller asked for. Verified rather than
# supposed: write_zip was called with that slug and the file appeared two
# levels up.
_SLUG_OK = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


def slug(bundle: Dict[str, Any]) -> str:
    s = str((bundle.get("subject") or {}).get("slug") or "").strip()
    if not s:
        raise ValueError("bundle has no subject.slug; it names the output")
    # One path component, and a conservative one. Not "reject ..": that is a
    # blocklist, and a blocklist on paths is a list of the tricks somebody
    # thought of. `....//` defeats a naive strip of "..", and a leading slash
    # or a drive letter defeats a check for separators alone.
    if not _SLUG_OK.match(s):
        raise ValueError(
            f"unusable subject.slug {s!r}. It names a directory inside the "
            f"package and a file beside it, so it has to be a single path "
            f"component: letters, digits, dot, dash and underscore, starting "
            f"with a letter or a digit, at most 64 characters.")
    if s.strip(".") == "":
        raise ValueError(f"unusable subject.slug {s!r}: dots only")
    return s


def run_gates(bundle: Dict[str, Any], corpus_dir: Path,
              rendered: Dict[str, str]) -> List[Verdict]:
    """Every gate, in order, on this bundle and its rendered output."""
    name = str((bundle.get("subject") or {}).get("name") or "")
    scope = bundle.get("scope")
    consent_path = bundle.get("consent_path")

    verdicts = [
        # First, because everything after it reads the corpus. A file placed
        # here by hand never went through ingest.
        sanitize_gate.check(corpus_dir),
        consent_gate.check(bundle.get("sources") or [],
                           Path(consent_path) if consent_path else None),
        seats_gate.check(bundle),
        contradictions_gate.check(bundle.get("contradictions")),
        sensitivity_gate.check(bundle.get("sensitivity")),
        profile_gate.check(bundle.get("holdout_by_seat")),
        holdout_gate.check(bundle.get("holdout")),
    ]

    # G2 reconciles every claim the seats make, plus both sides of every
    # contradiction and every flip-condition threshold: the figures that matter
    # most are the easiest to invent.
    claims: List[Dict[str, Any]] = []
    for e in seats_gate.all_entries(bundle):
        claims.append({**e, "text": e.get("claim")})
    for i, rec in enumerate(bundle.get("contradictions") or []):
        for side in ("earlier", "later"):
            s = rec.get(side) or {}
            if s.get("source_id"):
                claims.append({"id": f"contradiction[{i}].{side}",
                               "text": s.get("claim"), "source_id": s.get("source_id"),
                               "quote": s.get("quote")})
    for i, rec in enumerate(bundle.get("sensitivity") or []):
        if rec.get("source_id") and rec.get("quote"):
            claims.append({"id": f"sensitivity[{i}]",
                           "text": f"{rec.get('quantity')} {rec.get('threshold')}",
                           "source_id": rec.get("source_id"), "quote": rec.get("quote")})
    if claims:
        # The source manifest goes with the claims: G2 is the gate that knows
        # which source a claim rests on, so it is where authorship has its
        # consequence.
        verdicts.append(anchor_gate.check(claims, corpus_dir, bundle.get("sources")))

    # G3 reads the rendered SKILL.md, because that is the text that could
    # impersonate and the text a reader sees.
    verdicts.append(disclosure_gate.check(
        rendered.get("SKILL.md", ""), name, scope, bundle.get("disclosure")))

    # G5 only when a memo was produced; a reconstruction need not have run a
    # deliberation yet.
    if bundle.get("memo") is not None:
        verdicts.append(interrogation_gate.check(bundle.get("memo"),
                                                 bundle.get("statements")))
    return verdicts


def _path_errors(names: List[str]) -> List[str]:
    errs = []
    lowered: Dict[str, str] = {}
    for n in names:
        # Traversal and absolute paths, checked here as well as at the slug.
        # Two checks because they protect against different mistakes: the slug
        # check guards the value the bundle supplies, this one guards whatever
        # a future caller assembles. A zip entry that escapes its own directory
        # is the archive version of the same bug, and it is the one that bites
        # the person who unpacks it rather than the person who builds it.
        if ".." in n.split("/") or n.startswith("/") or "\\" in n:
            errs.append(f"{n}: path escapes the package directory")
        if ":" in n[:3]:
            errs.append(f"{n}: looks like an absolute Windows path")
        if any(ord(c) > 127 for c in n):
            errs.append(f"{n}: non-ASCII path; some installers reject the whole archive")
        if set(n) & ILLEGAL:
            errs.append(f"{n}: character Windows cannot open")
        for part in n.split("/"):
            if part.split(".")[0].upper() in RESERVED:
                errs.append(f"{n}: reserved device name {part!r}")
            if part != part.rstrip(". "):
                errs.append(f"{n}: path component ends in a dot or space")
        if n.lower() in lowered and lowered[n.lower()] != n:
            errs.append(f"{n}: collides with {lowered[n.lower()]} on a case-insensitive disk")
        lowered.setdefault(n.lower(), n)
    return errs


def write_zip(rendered: Dict[str, str], inner: str, out_path: Path) -> List[str]:
    """Write and then read back. Returns errors; on any error nothing remains."""
    names = [f"{inner}/{fn}" for fn in rendered]
    errs = _path_errors(names)
    if errs:
        return errs

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED,
                         allowZip64=False) as zf:
        for fn, text in sorted(rendered.items()):
            info = zipfile.ZipInfo(f"{inner}/{fn}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, text.encode("utf-8"))

    # Read back rather than trust the write. A silently dropped file is the
    # failure a packer is least likely to notice.
    try:
        with zipfile.ZipFile(out_path) as zf:
            if zf.testzip() is not None:
                errs.append(f"CRC mismatch on {zf.testzip()}")
            got = set(zf.namelist())
            missing = set(names) - got
            extra = got - set(names)
            if missing:
                errs.append(f"missing from the archive: {sorted(missing)}")
            if extra:
                errs.append(f"unexpected in the archive: {sorted(extra)}")
            for fn, text in rendered.items():
                if zf.read(f"{inner}/{fn}").decode("utf-8") != text:
                    errs.append(f"{fn}: content differs after read-back")
    except zipfile.BadZipFile as exc:
        errs.append(f"archive will not open: {exc}")

    if errs and out_path.exists():
        os.remove(out_path)
    return errs


def run(bundle: Dict[str, Any], corpus_dir: str | Path,
        out_dir: str | Path) -> Tuple[Optional[Path], List[Verdict], List[str]]:
    """Render, gate, and package only if every gate passed.

    Returns (zip_path_or_None, verdicts, errors). A None path with an empty
    error list cannot happen: either something blocked, or there is a zip.
    """
    corpus_dir = Path(corpus_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    bundle = dict(bundle)
    bundle.setdefault("corpus_fingerprint", corpus_fingerprint(corpus_dir))

    rendered = render.render_all(bundle)
    verdicts = run_gates(bundle, corpus_dir, rendered)

    failed = [v for v in verdicts if not v.passed]
    if failed:
        return None, verdicts, [f"{v.gate}: {e}" for v in failed for e in v.errors]

    version = str(bundle.get("version") or "").strip()
    if not version:
        no_version = (
            "bundle has no version. The filename carries it, so that a user "
            "holding three downloads can tell which is current."
        )
        return None, verdicts, [no_version]
    label = version if version.startswith("v") else f"v{version}"
    inner = f"{slug(bundle)}-method"
    out_path = out_dir / f"{inner}-{label}.zip"

    errs = write_zip(rendered, inner, out_path)
    if errs:
        return None, verdicts, errs

    manifest = {
        "package": out_path.name,
        "inner_directory": inner,
        "version": label,
        "corpus_fingerprint": bundle["corpus_fingerprint"],
        "files": sorted(rendered),
        "gates_passed": [v.gate for v in verdicts],
    }
    (out_dir / f"{inner}-{label}.manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return out_path, verdicts, []
