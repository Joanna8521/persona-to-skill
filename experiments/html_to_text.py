#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Strip HTML to text WITHOUT normalising punctuation.

The whole experiment depends on this step changing nothing a model would not
also change. So: tags out, entities decoded, paragraph breaks kept. Quote
style, dash style, spacing inside a sentence, full-width versus half-width --
all left exactly as served.
"""
import html
import re
import sys
from pathlib import Path

# NB: <table> is NOT dropped. Older hand-written pages lay the whole essay out
# in a table cell, and dropping it removes the entire body -- which is exactly
# what happened on the first run of this experiment.
DROP = re.compile(
    r"<(script|style|nav|footer|sup|figure|figcaption)\b.*?</\1\s*>",
    re.I | re.S)
# Hand-written pages hard-wrap their prose with a single <br> per line and use
# <br><br> for a paragraph break. Treating every <br> as a paragraph break
# leaves nothing but short fragments -- which is what happened on the second run
# of this experiment. So: double break is a paragraph, single break is the
# space it stands for.
PARA = re.compile(r"(?:<br\s*/?>\s*){2,}|</(?:p|div|li|h[1-6]|blockquote)\s*>", re.I)
LINEWRAP = re.compile(r"<br\s*/?>", re.I)
TAG = re.compile(r"<[^>]+>")


def to_text(raw: str) -> str:
    t = DROP.sub(" ", raw)
    t = PARA.sub("\n\n", t)
    t = LINEWRAP.sub(" ", t)
    t = TAG.sub("", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t]+", " ", t)          # runs of spaces, not newlines
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = "\n".join(ln.strip() for ln in t.splitlines()).strip()

    # These files are hard-wrapped in the source itself, with real newlines
    # inside a paragraph, so a blank line marks a paragraph and a lone newline
    # is a wrap. Rejoining the wraps is what any ingest would do, and it is also
    # the thing that makes a quote crossing a wrap point findable at all.
    # Linear: see transcript._unwrap for why the regex form is quadratic.
    paragraphs = [" ".join(w for w in p.split() if w) for p in t.split("\n\n")]
    return "\n".join(p for p in paragraphs if p)


def main(src_dir: str, out_dir: str) -> int:
    src, out = Path(src_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for f in sorted(src.glob("*.html")):
        text = to_text(f.read_text(encoding="utf-8", errors="replace"))
        paras = [p for p in text.split("\n") if len(p) > 120]
        if not paras:
            print(f"  {f.stem:<22} NO PARAGRAPHS -- extraction dropped the body")
        body = "\n".join(paras)
        (out / f"{f.stem}.txt").write_text(body, encoding="utf-8")
        curly = sum(body.count(c) for c in "“”‘’")
        emdash = body.count("—") + body.count("–")
        fw = sum(body.count(c) for c in "，。：；（）、")
        print(f"  {f.stem:<22} {len(body):>8,} chars  curly={curly:<4} dash={emdash:<4} "
              f"fullwidth={fw:<5} paras={len(paras)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
