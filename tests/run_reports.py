"""'Not the chorus' reports: undo on the spot, list and clear them, and the one-time fix for 遺失的美好.

    python3 tests/run_reports.py index.html src/bank.txt
"""
import json, os, re, sys, time
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "harness12.py"), encoding="utf-8").read())
results = []
def check(name, ok, info=""):
    results.append(ok); print(("PASS " if ok else "FAIL ") + name + (f"  [{info}]" if info else ""))
S["chorus_layout"] = "all"
pre = {"遺失的美好|張韶涵": 1, "晴天|周杰倫": 2}
with sync_playwright() as p:
    b = p.chromium.launch()
    c, pg = new_page(b)
    pg.evaluate(f"""() => {{ localStorage.setItem('erg_notChorus', JSON.stringify({json.dumps(pre, ensure_ascii=False)}));
      localStorage.setItem('erg_chorus4', JSON.stringify({{'遺失的美好|張韶涵': {{reject: true, ts: 1}}, '晴天|周杰倫': {{reject: true, ts: 2}}}}));
      localStorage.removeItem('erg_fixReport1'); }}""")
    pg.reload(); pg.wait_for_timeout(500)
    nc = pg.evaluate("JSON.parse(localStorage.getItem('erg_notChorus'))")
    check("mistaken report on 遺失的美好 is cancelled", "遺失的美好|張韶涵" not in nc and "晴天|周杰倫" in nc, list(nc))
    ch = pg.evaluate("JSON.parse(localStorage.getItem('erg_chorus4'))")
    check("遺失的美好 can be a chorus question again", "遺失的美好|張韶涵" not in ch)
    check("home shows how many songs were reported", "副歌回報 1 首" in pg.inner_text("#reports-wrap") and pg.locator("#reports-wrap").is_visible())
    pg.reload(); pg.wait_for_timeout(300)
    check("the one-time fix doesn't undo later reports", "晴天|周杰倫" in pg.evaluate("JSON.parse(localStorage.getItem('erg_notChorus'))"))
    pg.click("#btn-reports"); pg.wait_for_selector("#modal:not([hidden])")
    check("report list names the song", "晴天" in pg.inner_text("#modal-text"))
    pg.click("#modal-actions button.primary"); pg.wait_for_timeout(200)
    check("clear all reports", pg.evaluate("Object.keys(JSON.parse(localStorage.getItem('erg_notChorus'))).length") == 0 and pg.locator("#reports-wrap").is_hidden())
    # a report made by mistake during a game is undone by pressing the button again
    pg.click('#seg-clip button[data-clip="chorus"]'); pg.click('.mode[data-mode="classic"]'); pg.click("#btn-start")
    sid, _ = answer_song(pg, correct=True)
    pg.wait_for_selector("#btn-notchorus:not([hidden])", timeout=10000)
    pg.click("#btn-notchorus")
    k = pg.evaluate("Object.keys(JSON.parse(localStorage.getItem('erg_notChorus')))")
    check("report during a game", len(k) == 1 and "再按一次取消" in pg.inner_text("#btn-notchorus"), (k, pg.inner_text("#btn-notchorus")))
    pg.click("#btn-notchorus")
    k2 = pg.evaluate("Object.keys(JSON.parse(localStorage.getItem('erg_notChorus')))")
    check("pressing again cancels it", k2 == [] and "已取消" in pg.inner_text("#btn-notchorus"), k2)
    check("page errors: none", not errors, errors[:3])
    b.close()
print(f"\n{sum(results)}/{len(results)} checks passed")
