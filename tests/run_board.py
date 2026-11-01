"""Daily challenge leaderboard on the stand-in database.

    python3 tests/run_board.py index.html src/bank.txt
"""
import os, pathlib, re, shutil, sys, tempfile, time
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "harness12.py"), encoding="utf-8").read())
sys.path.insert(0, str(KIT))
import fake_firebase as FF

site = pathlib.Path(tempfile.mkdtemp()); shutil.copy(GAME, site / "index.html")
srv = FF.start(str(site))
BASE = f"http://127.0.0.1:{srv.server_address[1]}"
URL = f"{BASE}/index.html?fb={BASE}&debug"
results = []
def check(name, ok, info=""):
    results.append(ok); print(("PASS " if ok else "FAIL ") + name + (f"  [{info}]" if info else "")); sys.stdout.flush()

def player(b):
    c = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    c.route("https://itunes.apple.com/**", apple); c.route("https://api.deezer.com/**", deezer)
    c.route(re.compile(r"https://(audio|dz)\.mock/.*"), media); c.route(re.compile(r"https://fonts\..*"), lambda r: r.abort())
    c.add_init_script("window.__last=null;const op=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){if(this.src.indexOf('mock')>0||this.src.startsWith('blob:')&&this.duration>1)window.__last=this;return op.call(this)};")
    pg = c.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.goto(URL); return c, pg

def play_daily(pg, right):
    pg.click('.mode[data-mode="daily"]'); pg.click("#btn-start")
    for i in range(5):
        answer_song(pg, correct=(i < right)); pg.click("#btn-next")
    pg.wait_for_selector("#result.active", timeout=20000)

with sync_playwright() as p:
    b = p.chromium.launch()
    c1, A = player(b)
    A.click('.mode[data-mode="daily"]')
    A.wait_for_selector("#home-daily-board:not([hidden])", timeout=10000)
    check("home shows today's board (empty)", "還沒有人上榜" in A.inner_text("#home-daily-board"))
    play_daily(A, 4)
    check("result offers to post the score", A.locator("#daily-board-wrap").is_visible() and A.locator("#daily-submit").is_visible())
    A.fill("#daily-name", "阿明"); A.click("#btn-daily-submit")
    A.wait_for_function("document.querySelector('#daily-board').textContent.includes('阿明')", timeout=10000)
    check("posted score appears on the board", "阿明" in A.inner_text("#daily-board"))
    check("post box hides after posting", A.locator("#daily-submit").is_hidden())
    score_a = int(A.inner_text("#res-score").replace(",", "") or 0)
    c2, B = player(b)
    play_daily(B, 5)
    B.fill("#daily-name", "小美"); B.click("#btn-daily-submit")
    B.wait_for_function("document.querySelector('#daily-board').textContent.includes('小美')", timeout=10000)
    rows = B.locator("#daily-board .pl .pl-name").all_inner_texts()
    check("board is sorted by score", [r.replace("你", "") for r in rows] == ["小美", "阿明"], rows)
    check("my row is highlighted", B.locator("#daily-board .pl.me").count() == 1)
    # a second try the same day: board keeps the first score, no second post
    B.click("#btn-again")
    for i in range(5):
        answer_song(B, correct=False); B.click("#btn-next")
    B.wait_for_selector("#result.active", timeout=20000)
    check("replay: no second post", B.locator("#daily-submit").is_hidden())
    keys = [k for k in (FF.get_at(["board"]) or {})]
    check("one entry per device per day", len(keys) == 2, keys)
    # a forged write over someone else's entry is refused by the rules
    import urllib.request, json
    req = urllib.request.Request(f"{BASE}/board/{keys[0]}.json", data=json.dumps({"n": "x", "s": 1, "ts": 1}).encode(), method="PUT")
    try: urllib.request.urlopen(req); refused = False
    except Exception: refused = True
    check("entries can't be overwritten", refused)
    # home screen of a third device shows the top of today's board
    c3, C = player(b)
    C.click('.mode[data-mode="daily"]')
    C.wait_for_function("document.querySelector('#home-daily-board').textContent.includes('小美')", timeout=10000)
    check("home shows the leaders", "2 人" in C.inner_text("#home-daily-board"))
    check("page errors: none", not errors, errors[:3])
    b.close()
print(f"\n{sum(results)}/{len(results)} checks passed")
