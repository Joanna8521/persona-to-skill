#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The command line, which `pyproject.toml` declared eleven commits before it
existed.

    persona-to-skill fetch   <url> [--robots FILE]   may this be fetched
    persona-to-skill import  <file> --subject NAME --tier T2 --corpus DIR
    persona-to-skill gates   <bundle.json> --corpus DIR
    persona-to-skill package <bundle.json> --corpus DIR --out DIR
    persona-to-skill punct   [PATH ...]

Every subcommand wraps a function that already existed and was already tested.
This module adds argument parsing and exit codes, and nothing else: a CLI that
contains judgement of its own is a second implementation, and the two drift.

Exit codes are the whole point of it being a command. 0 means the gate passed;
non-zero means it did not. Anything that prints a verdict and exits 0 is a gate
that cannot be put in a CI job, which is the same as not having one.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List

from ._console import force_utf8
from .contract import SOURCE_TIERS
from .collect import fetch, importer
from .deliver import package
from . import validate_punct


def _load_json(path: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"no such file: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path} is not valid JSON: {exc}")


def _print_verdicts(verdicts) -> None:
    for v in verdicts:
        mark = "PASS" if v.passed else "FAIL"
        print(f"  {mark}  {v.gate}")
        for e in v.errors:
            print(f"          {e}")
        for w in v.warnings:
            print(f"          (warning) {w}")


# ── fetch ───────────────────────────────────────────────

def cmd_fetch(args) -> int:
    """Whether a URL may be fetched, by robots.txt and nothing else.

    --robots takes a file rather than going to the network, because this
    command is also how you check what the decision WOULD be for a robots.txt
    you are holding. Reading the real one is a separate step the caller does.
    """
    robots = None
    if args.robots:
        robots = Path(args.robots).read_text(encoding="utf-8", errors="replace")
    d = fetch.decide(args.url, robots)
    print(f"  {d.verdict}  {args.url}")
    print(f"          {d.reason}")
    # d.may_fetch, not a comparison against a constant this module names
    # itself. The first version compared against fetch.FETCH_OK, which does not
    # exist: the constants are FETCH and IMPORT_ONLY. The entry-point guard
    # caught the missing module and nothing caught the wrong attribute, because
    # nothing ran the command. Hence tests/test_cli.py.
    if not d.may_fetch:
        print()
        print(fetch.refusal_message(args.url, d))
    return 0 if d.may_fetch else 1


# ── import ──────────────────────────────────────────────

def cmd_import(args) -> int:
    """Records in the import contract shape to a corpus directory on disk."""
    data = _load_json(args.file)

    records = data.get("records") if isinstance(data, dict) else data
    if not isinstance(records, list):
        raise SystemExit(
            f"{args.file}: expected a list of records, or an object with a "
            f'"records" list. Post Sync writes the latter.')

    contract = data.get("contract") if isinstance(data, dict) else None
    if contract == "persona-to-skill/import/v1":
        result = importer.from_postsync(records, args.subject, args.tier)
    else:
        result = importer.import_records(records, args.subject, args.tier)

    s = result.summary()
    print(f"  accepted {s['accepted']}   rejected {s['rejected']}")
    for why in s["reasons"]:
        n = sum(1 for _id, w in result.rejected if w == why)
        print(f"          {n}x  {why}")
    for note in result.notes:
        print(f"          note: {note}")

    if not result.accepted:
        print("\nnothing accepted, so nothing was written.")
        return 1

    # The manifest is written explicitly, because write_corpus only writes one
    # when given a path. G1 reads it, so an import that skipped it would leave
    # a corpus that no gate can consent-check: the first version of this
    # function did exactly that, and tests/test_cli.py caught it.
    manifest = Path(args.corpus) / "manifest.json"
    written = importer.write_corpus(result.accepted, args.corpus, manifest)
    print(f"\n  wrote {written['files']} sources to {written['corpus_dir']}")
    print(f"  manifest: {manifest}")
    return 0


# ── gates ───────────────────────────────────────────────

def cmd_gates(args) -> int:
    """Every gate, without packaging. This is the CI-shaped command."""
    bundle = _load_json(args.bundle)
    if not isinstance(bundle, dict):
        raise SystemExit(f"{args.bundle}: expected a JSON object")

    rendered = package.render.render_all(bundle)
    verdicts = package.run_gates(bundle, Path(args.corpus), rendered)
    _print_verdicts(verdicts)

    failed = [v for v in verdicts if not v.passed]
    print(f"\n  {len(verdicts) - len(failed)}/{len(verdicts)} gates passed")
    return 1 if failed else 0


# ── package ─────────────────────────────────────────────

def cmd_package(args) -> int:
    bundle = _load_json(args.bundle)
    if not isinstance(bundle, dict):
        raise SystemExit(f"{args.bundle}: expected a JSON object")

    zip_path, verdicts, errors = package.run(bundle, args.corpus, args.out)
    _print_verdicts(verdicts)
    if errors:
        print()
        for e in errors:
            print(f"  {e}")
    if zip_path is None:
        print("\n  nothing was written.")
        return 1
    print(f"\n  wrote {zip_path}")
    return 0


# ── punct ───────────────────────────────────────────────

def cmd_punct(args) -> int:
    return validate_punct.main(args.paths)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="persona-to-skill",
        description="Reconstruct a documented method as an agent skill, with receipts.",
    )
    # required=True so a bare `persona-to-skill` exits non-zero with the usage,
    # rather than exiting 0 having done nothing. A command that succeeds without
    # doing anything is the same failure this file exists because of.
    sub = p.add_subparsers(dest="command", required=True)

    f = sub.add_parser("fetch", help="may this URL be fetched (robots.txt only)")
    f.add_argument("url")
    f.add_argument("--robots", metavar="FILE",
                   help="the site's robots.txt, as a file; omitted means none was found")
    f.set_defaults(func=cmd_fetch)

    i = sub.add_parser("import", help="import records into a corpus directory")
    i.add_argument("file", help="JSON: a list of records, or {records: [...]}")
    i.add_argument("--subject", required=True, metavar="NAME",
                   help="whose method is being reconstructed")
    i.add_argument("--tier", required=True, choices=list(SOURCE_TIERS),
                   help="source tier; depends on the publication, not on the record")
    i.add_argument("--corpus", required=True, metavar="DIR")
    i.set_defaults(func=cmd_import)

    g = sub.add_parser("gates", help="run every gate on a bundle")
    g.add_argument("bundle", help="bundle JSON")
    g.add_argument("--corpus", required=True, metavar="DIR")
    g.set_defaults(func=cmd_gates)

    k = sub.add_parser("package", help="gate, then write the zip if every gate passed")
    k.add_argument("bundle", help="bundle JSON")
    k.add_argument("--corpus", required=True, metavar="DIR")
    k.add_argument("--out", required=True, metavar="DIR")
    k.set_defaults(func=cmd_package)

    u = sub.add_parser("punct", help="the punctuation gate on Markdown files")
    u.add_argument("paths", nargs="*", metavar="PATH")
    u.set_defaults(func=cmd_punct)

    return p


def main(argv: List[str] | None = None) -> int:
    """argv defaults to sys.argv[1:] so the console script can call main()."""
    force_utf8()
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
