# -*- coding: utf-8 -*-
"""The punctuation gate, and above all what it must NOT flag.

This gate existed as two frozen contract values and nothing else: declared,
asserted by a test for their shape, and read by no code at all. A frozen value
nothing consults is worse than none, because it implies a check that is not
running. On its first real run it found 16 violations in four files.
"""
import tempfile
from pathlib import Path

import _base  # noqa: F401
from persona_to_skill import validate_punct as vp

CLEAN_EN = "# Title\n\nA sentence with a colon: and a comma, and nothing else.\n"
CLEAN_ZH = "# 標題\n\n一個句子，帶著全形逗號與全形句號。數字 1,000 與 `code_name` 用半形。\n"
CLEAN_JA = "# 見出し\n\n日本語の文です、読点と句点を使います。コードは `half_width` のままです。\n"


def _write(name: str, text: str) -> Path:
    d = Path(tempfile.mkdtemp())
    p = d / name
    p.write_text(text, encoding="utf-8")
    return p


# ----------------------------------------------------------------- positive
def test_clean_files_pass():
    for name, text in (("README.md", CLEAN_EN),
                       ("README.zh-TW.md", CLEAN_ZH),
                       ("README.ja.md", CLEAN_JA)):
        assert vp.check_file(_write(name, text)) == [], name


def test_the_repository_is_clean():
    """The gate has to hold on the real tree, not only on fixtures."""
    root = Path(__file__).resolve().parent.parent
    files = [p for p in root.rglob("*.md") if ".git" not in p.parts]
    assert files, "no Markdown found"
    found = vp.check_paths(files)
    assert not found, {str(k): v for k, v in found.items()}


# ------------------------------------- negative: dashes, banned everywhere
def test_em_dash_blocks_in_english():
    hits = vp.check_file(_write("README.md", "A sentence — broken by a dash.\n"))
    assert hits and hits[0][1] == "dash variant"


def test_en_dash_blocks():
    assert vp.check_file(_write("README.md", "Range 2024–2026 here.\n"))


def test_prose_double_hyphen_blocks():
    hits = vp.check_file(_write("README.md", "A clause -- and another.\n"))
    assert hits and "double hyphen" in hits[0][1]


def test_dash_blocks_in_chinese_and_japanese_too():
    assert vp.check_file(_write("README.zh-TW.md", "一個句子 —— 被破折號切開。\n"))
    assert vp.check_file(_write("README.ja.md", "文です —— 切られています。\n"))


# ---------------- negative: full-width rule, Chinese files only
def test_half_width_comma_after_chinese_blocks():
    hits = vp.check_file(_write("README.zh-TW.md", "一個句子, 帶著半形逗號。\n"))
    assert hits and "half-width punctuation" in hits[0][1]


def test_half_width_period_after_chinese_blocks():
    assert vp.check_file(_write("README.zh-TW.md", "這是一個句子.\n"))


def test_half_width_bracket_around_chinese_blocks():
    assert vp.check_file(_write("README.zh-TW.md", "一個說明(括號裡面)在這裡。\n"))


def test_straight_quote_around_chinese_blocks():
    assert vp.check_file(_write("README.zh-TW.md", '他說"先別報價"就掛了電話。\n'))


def test_the_rule_applies_inside_the_scoped_directory():
    d = Path(tempfile.mkdtemp())
    (d / "docs" / "zh-TW").mkdir(parents=True)
    p = d / "docs" / "zh-TW" / "journey.md"
    p.write_text("一個句子, 半形逗號。\n", encoding="utf-8")
    assert vp.in_fullwidth_scope(p)
    assert vp.check_file(p)


# -------------------- THE ONE THAT MATTERS: Japanese is not Chinese
def test_japanese_is_not_checked_against_the_chinese_table():
    """Japanese writes 、 and 。 where Chinese writes ，and 。. Applying the
    Chinese rule to Japanese flags correct text as wrong, which is why
    PUNCT_CHECKED_DIRS covers docs/zh-TW and not docs/ja."""
    ja = _write("README.ja.md", "日本語の文です、読点を使います。括弧は（全角）です。\n")
    assert not vp.in_fullwidth_scope(ja)
    assert vp.check_file(ja) == []


def test_japanese_half_width_punctuation_is_not_flagged():
    """Not because it is correct Japanese, but because this gate has no
    authority over Japanese typography and must not pretend otherwise."""
    ja = _write("README.ja.md", "これは文です, 半角のカンマです.\n")
    assert vp.check_file(ja) == []


def test_english_is_not_checked_against_the_chinese_table():
    en = _write("README.md", "Plain English, with half-width punctuation. Fine.\n")
    assert not vp.in_fullwidth_scope(en)
    assert vp.check_file(en) == []


def test_scope_is_decided_by_the_frozen_contract():
    from persona_to_skill import contract as c
    assert ".zh-TW.md" in c.PUNCT_CHECKED_SUFFIXES
    assert "docs/zh-TW" in c.PUNCT_CHECKED_DIRS
    assert not any("ja" in d for d in c.PUNCT_CHECKED_DIRS)
    assert not any(".ja." in s for s in c.PUNCT_CHECKED_SUFFIXES)


# ------------------------------------------------------- exemptions
def test_code_fences_are_exempt():
    text = "# 標題\n\n```\nprint(\"a, b.\")\n```\n\n一個句子。\n"
    assert vp.check_file(_write("README.zh-TW.md", text)) == []


def test_inline_code_and_urls_are_exempt():
    text = "# 標題\n\n看 `a, b.` 與 https://example.com/a,b. 這些。\n"
    assert vp.check_file(_write("README.zh-TW.md", text)) == []


def test_table_rules_and_cli_flags_are_not_prose_dashes():
    assert vp.check_file(_write("README.md", "|---|---|\n")) == []
    assert vp.check_file(_write("README.md", "Run `ruff check --fix` now.\n")) == []


def test_numbers_and_code_keep_half_width_after_chinese():
    text = "營收 1,000 萬元。版本 3.5 可用。見 `a.b` 設定。\n"
    assert vp.check_file(_write("README.zh-TW.md", text)) == []


def test_exit_code_is_one_on_a_violation():
    p = _write("README.zh-TW.md", "一個句子, 錯的。\n")
    assert vp.main([str(p)]) == 1
    ok = _write("README.zh-TW.md", CLEAN_ZH)
    assert vp.main([str(ok)]) == 0


if __name__ == "__main__":
    import sys
    sys.exit(_base.run_module(dict(globals())))
