# -*- coding: utf-8 -*-
"""矛盾與翻轉條件：兩個 fail-closed 規則。

這兩支的重點都不是「抓得到格式錯誤」，是**抓得到那個看起來像完成工作、
實際上把發現丟掉的動作**。矛盾那邊是「取最新的那個就好」，翻轉條件那邊是
「數字還沒查到但還是給了建議」。
"""
import _base  # noqa: F401
from persona_to_skill.extract import contradictions as co
from persona_to_skill.extract import sensitivity as se

SIDE_A = {"claim": "一定要自己開店", "source_id": "s1", "quote": "我們自己開"}
SIDE_B = {"claim": "找當地夥伴比較好", "source_id": "s9", "quote": "找夥伴比較快"}


def rec(**over):
    r = {"id": "c1", "earlier": dict(SIDE_A), "later": dict(SIDE_B),
         "status": "reconciled",
         "reconciling_condition": "單一市場人口超過兩千萬時自己開，低於就找夥伴"}
    r.update(over)
    return r


def flip(**over):
    f = {"id": "f1", "decision_class": "進入新市場",
         "quantity": "單店客戶取得成本", "threshold": "1,200 日圓",
         "direction": "above_stops", "source_id": "s1",
         "known": False, "how_to_find": "先開一家試營運一季"}
    f.update(over)
    return f


# ======================================================= 矛盾
def test_和解的矛盾要附條件():
    assert co.check([rec()]).passed
    assert not co.check([rec(reconciling_condition="")]).passed


def test_用取最新結案要被擋():
    """這是整支最重要的一條：那個動作看起來像推進，實際上是刪除。"""
    for how in ("latest", "newest", "later"):
        v = co.check([rec(resolution=how)])
        assert not v.passed, how
        assert any("deletion" in e for e in v.errors)


def test_未解的矛盾可以交付並被標出來():
    v = co.check([rec(status="unresolved", reconciling_condition="",
                      why_unresolved="兩邊的市場規模都查不到")])
    assert v.passed, v.errors
    assert v.stats["unresolved"] == 1
    assert any("intended outcome" in w for w in v.warnings)


def test_未解卻又寫了條件是矛盾的():
    assert not co.check([rec(status="unresolved")]).passed


def test_未解但沒說試過什麼只給警告():
    v = co.check([rec(status="unresolved", reconciling_condition="")])
    assert v.passed
    assert any("where you stopped" in w for w in v.warnings)


def test_兩邊都必須是引文():
    assert not co.check([rec(earlier={"claim": "x"})]).passed
    assert not co.check([rec(later={"claim": "x", "source_id": "s1"})]).passed


def test_狀態必須合法():
    assert not co.check([rec(status="probably")]).passed


def test_沒給與給空陣列是不同的宣稱():
    """「找不到矛盾」是一個結果，「沒去找」不是。"""
    assert not co.check(None).passed
    assert co.check([]).passed


# ======================================================= 翻轉條件
def test_完整的翻轉條件通過():
    v = se.check([flip()])
    assert v.passed, v.errors
    assert v.stats["awaiting_lookup"] == 1


def test_門檻沒有數字要被擋():
    """門檻是拿來比的值。沒有數字就沒有東西可以去查，G2 也無從對帳。"""
    for vague in ("低到可以接受", "reasonable", "合理範圍"):
        v = se.check([flip(threshold=vague)])
        assert not v.passed, vague
        assert any("no number" in e for e in v.errors)


def test_量化對象是話題不是數字要被擋():
    for topic in ("市場狀況", "整體風險", "market conditions", "team capacity"):
        v = se.check([flip(quantity=topic)])
        assert not v.passed, topic
        assert any("not a quantity" in e for e in v.errors)


def test_方向必須講明哪一邊會停():
    assert not se.check([flip(direction="maybe")]).passed
    for d in se.DIRECTIONS:
        assert se.check([flip(direction=d)]).passed, d


def test_數字在不在手上必須是明確的布林():
    for sneaky in (None, "yes", 1, 0):
        assert not se.check([flip(known=sneaky)]).passed, repr(sneaky)


def test_說數字在手上就要給觀測值():
    assert not se.check([flip(known=True)]).passed
    assert se.check([flip(known=True, observed_value="980 日圓")]).passed


def test_數字不在手上而沒說怎麼查只給警告():
    v = se.check([flip(how_to_find="")])
    assert v.passed
    assert any("Naming the lookup" in w for w in v.warnings)


def test_一個決策類別有多個翻轉條件要警告():
    v = se.check([flip(id="f1"), flip(id="f2", quantity="每月回購率",
                                      threshold="30%")])
    assert v.passed
    assert any("drawn too wide" in w for w in v.warnings)


def test_完全沒有翻轉條件要被擋():
    """一份沒有翻轉條件的重建，沒有抽到值得抽的那個東西。"""
    v = se.check([])
    assert not v.passed
    assert any("one lookup they can do themselves" in e for e in v.errors)
    assert not se.check(None).passed


def test_必填欄位缺一個就擋():
    from persona_to_skill.contract import SENSITIVITY_REQUIRED_FIELDS
    for field in SENSITIVITY_REQUIRED_FIELDS:
        assert not se.check([flip(**{field: ""})]).passed, field


if __name__ == "__main__":
    import sys
    sys.exit(_base.run_module(dict(globals())))
