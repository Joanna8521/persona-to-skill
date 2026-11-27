# -*- coding: utf-8 -*-
"""取得語料:什麼可以抓、什麼要請人提供、進來之後怎麼處理。

這個專案不抓取。它抓公開可爬的，其他一律請人提供，而那條線不是判斷題:
robots.txt 就是「這裡允不允許自動取用」的機器可讀聲明。
"""
import json
import tempfile
from pathlib import Path

import _base  # noqa: F401
from persona_to_skill.collect import fetch, importer

PLATFORM_BLOCKS_ALL = "User-agent: *\nDisallow: /\n"
BLOG_ALLOWS = "User-agent: *\nDisallow: /admin/\nCrawl-delay: 2\nAllow: /\n"
PARTIAL = "User-agent: *\nDisallow: /private/\n"


# ============================================================ 抓或不抓
def test_社群平台全擋的_robots_就不抓():
    """X、Instagram、LinkedIn 自己的 robots.txt 就擋掉大部分爬取。
    不需要我手維護平台封鎖名單。"""
    d = fetch.decide("https://x.com/someone/status/1", PLATFORM_BLOCKS_ALL)
    assert not d.may_fetch
    assert "disallows" in d.reason


def test_公開可爬的頁面就直接抓():
    d = fetch.decide("https://example.com/post/leverage", BLOG_ALLOWS)
    assert d.may_fetch
    assert d.crawl_delay_s == 2.0


def test_同一站的禁區與開放區分開判定():
    assert fetch.decide("https://example.com/public/a", PARTIAL).may_fetch
    assert not fetch.decide("https://example.com/private/a", PARTIAL).may_fetch
    assert not fetch.decide("https://example.com/admin/x", BLOG_ALLOWS).may_fetch


def test_沒有_robots_當作沒有限制():
    """一個沒有 robots.txt 的站沒有聲明任何限制，所有爬蟲都是這樣讀的。
    真要限制的站會說。"""
    d = fetch.decide("https://example.com/a", None)
    assert d.may_fetch
    assert "no restriction stated" in d.reason


def test_非_http_一律不抓():
    for url in ("file:///etc/passwd", "ftp://x/y", "javascript:alert(1)", "", "/a/b"):
        assert not fetch.decide(url, None).may_fetch, url


def test_判定是純函式不連網():
    """robots 文字當參數傳進去，所以離線全測得到，網路那層只負責去拿檔案。"""
    import inspect
    src = inspect.getsource(fetch.decide)
    for forbidden in ("urlopen", "requests", "socket", "http.client"):
        assert forbidden not in src


# ---------------------------------------------- 兩個軸不是同一個軸
def test_可爬不等於可重製():
    """robots.txt 管能不能抓，授權分級管能不能重製。一篇新聞通常同時是
    公開可爬與完整受著作權保護，那是 T2:短引加標註，不整篇重製。"""
    doc = fetch.__doc__ or ""
    assert "TWO AXES" in doc
    assert "FETCHED" in doc and "REPRODUCED" in doc


def test_不抓的時候要說替代路線而不是只說失敗():
    msg = fetch.refusal_message("https://x.com/a/status/1",
                                fetch.decide("https://x.com/a/status/1",
                                             PLATFORM_BLOCKS_ALL))
    assert "Instead:" in msg
    assert len(fetch.IMPORT_ROUTES) >= 3
    assert any("browser extension needs that browser" in r for r in fetch.IMPORT_ROUTES), \
        "沒有一條路線涵蓋所有人，而這件事要寫出來"


def test_只讀文字型的回應():
    ok, _ = fetch.content_type_ok("text/html; charset=utf-8")
    assert ok
    for bad in ("application/pdf", "image/png", "application/octet-stream", None):
        assert not fetch.content_type_ok(bad)[0], bad


def test_每個主機之間有間隔():
    slept = []
    clock = iter([0.0, 0.0, 0.5, 2.5])
    pacer = fetch.HostPacer(clock=lambda: next(clock), sleeper=slept.append)
    pacer.wait("https://a.example/1", 2.0)
    assert slept == []
    pacer.wait("https://a.example/2", 2.0)
    assert slept and slept[0] > 0


# ============================================================ 匯入
def _caps():
    return [
        {"platform": "x", "text": "停滯超過六十天就放手 不打折", "author": "王小明",
         "authorGuessed": False, "permalink": "https://x.com/a/status/1",
         "timeText": "2026-08-13", "capturedAt": 1760000000000},
        {"platform": "threads", "text": "第一段論證", "author": "", "authorGuessed": True,
         "permalink": "https://www.threads.com/@a/post/2", "capturedAt": 1760000001000,
         "threadId": "t1", "threadIndex": 0},
        {"platform": "threads", "text": "第二段接續", "author": "", "authorGuessed": True,
         "permalink": "https://www.threads.com/@a/post/3", "capturedAt": 1760000002000,
         "threadId": "t1", "threadIndex": 1},
    ]


def test_postsync_的形狀直接吃得下():
    r = importer.from_postsync(_caps(), "王小明", "T1")
    assert r.summary()["accepted"] == 3, r.rejected


def test_別人寫的貼文被拒而不是靜默收進來():
    """收到的貼文是別人寫的，那不是這個對象的語料。靜默收進來就是這個
    專案存在要防的那個張冠李戴。"""
    caps = _caps() + [{"platform": "x", "text": "別人寫的", "author": "李大華",
                       "authorGuessed": False, "permalink": "https://x.com/b/status/9",
                       "capturedAt": 1}]
    r = importer.from_postsync(caps, "王小明", "T1")
    assert len(r.rejected) == 1
    assert "someone else" in r.rejected[0][1]


def test_作者是猜的就不算_self_written():
    """PostSync 的 authorGuessed 在作者抓不到、只能從第一行推時為真。
    那正是 authorship 軸，所以對應 unknown 而不是丟掉。"""
    r = importer.from_postsync(_caps(), "王小明", "T1")
    by_author = {rec["authorship"] for rec in r.accepted if rec["platform"] == "threads"}
    assert by_author == {"unknown"}
    assert any("inferred the author" in n for n in r.notes)


def test_thread_合併成一個來源():
    """一串 thread 是一個論證。不合併的話，跨兩則貼文的引文會在一個
    儲存方式自己造出來的邊界上掛掉，跟字幕 cue 同一科。"""
    r = importer.from_postsync(_caps(), "王小明", "T1")
    joined = importer.join_threads(r.accepted)
    assert len(joined) == 2
    thread = [j for j in joined if j.get("thread_parts")][0]
    assert thread["thread_parts"] == 2
    assert "第一段論證" in thread["text"] and "第二段接續" in thread["text"]


def test_進門就清理雙向控制字元():
    caps = [{"platform": "x", "text": "帶攻擊的‮反向‬貼文", "author": "王小明",
             "authorGuessed": False, "permalink": "https://x.com/a/4", "capturedAt": 1}]
    r = importer.from_postsync(caps, "王小明", "T1")
    rec = r.accepted[0]
    assert "‮" not in rec["text"]
    assert rec["sanitised"]["removed"]["bidi_control"] == 2


def test_引用轉推裡別人的話被保留並標記():
    caps = [{"platform": "x", "text": "我不同意", "author": "王小明", "authorGuessed": False,
             "permalink": "https://x.com/a/5", "capturedAt": 1,
             "quotedText": "原推說打折是必要的"}]
    r = importer.from_postsync(caps, "王小明", "T1")
    assert r.accepted[0]["embedded_other_party"] == "原推說打折是必要的"


def test_分級是參數不是欄位():
    """一筆來源能不能自由引用取決於出版形式，記錄裡沒有任何欄位說得出來，
    所以它是匯入的參數而不是匯入器發明的欄位。"""
    for tier in ("T0", "T1", "T2"):
        r = importer.from_postsync(_caps(), "王小明", tier)
        assert all(rec["tier"] == tier for rec in r.accepted)
    try:
        importer.from_postsync(_caps(), "王小明", "T9")
    except ValueError:
        return
    raise AssertionError("未知分級被接受了")


def test_沒有文字的記錄被拒():
    caps = [{"platform": "x", "text": "   ", "author": "王小明", "authorGuessed": False,
             "permalink": "https://x.com/a/6", "capturedAt": 1}]
    assert importer.from_postsync(caps, "王小明", "T1").rejected


def test_source_id_永遠是單一路徑成分():
    """source_id 會進 glob 模式，而 ../secret 是合法模式。從這裡生出一個
    帶分隔符的 id，就是從內部觸發 G2 那道閘門的方法。"""
    for url in ("https://x.com/../../etc/passwd", "https://x.com/a/b/c",
                "https://x.com/.hidden"):
        sid = importer.source_id("x", url, 0)
        assert "/" not in sid and "\\" not in sid and not sid.startswith("."), sid
        assert all(ord(c) < 128 for c in sid), sid


def test_寫出語料與_g1_讀的清單():
    r = importer.from_postsync(_caps(), "王小明", "T1")
    d = Path(tempfile.mkdtemp())
    out = importer.write_corpus(importer.join_threads(r.accepted),
                                d / "corpus", d / "sources.json")
    assert out["files"] == 2
    manifest = json.loads((d / "sources.json").read_text(encoding="utf-8"))
    assert all("tier" in m and "authorship" in m for m in manifest)
    assert all("text" not in m for m in manifest), "清單不該夾帶全文"
    for m in manifest:
        assert (d / "corpus" / f"{m['id']}.txt").is_file()


def test_寫出來的語料過得了_g1_與_sanitize():
    from persona_to_skill.collect import sanitize
    from persona_to_skill.gates import consent
    r = importer.from_postsync(_caps(), "王小明", "T1")
    d = Path(tempfile.mkdtemp())
    out = importer.write_corpus(importer.join_threads(r.accepted), d / "corpus")
    assert sanitize.check(d / "corpus").passed
    assert consent.check(out["sources"]).passed


if __name__ == "__main__":
    import sys
    sys.exit(_base.run_module(dict(globals())))
