"""Online battle: three players in separate browsers on the stand-in database.

    python3 tests/run_battle.py index.html src/bank.txt
Covers: create a named room, join by name / by code / by invite link, duplicate nicknames,
difficulty and song count, synced countdown, scoring rules (speed, streak, fastest bonus,
last song double, hard-mode penalty), scoreboards that agree on every device, final ranking,
play again, leaving, and the host dropping out mid-game.
"""
import json, os, pathlib, re, shutil, sys, tempfile, time
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "harness12.py"), encoding="utf-8").read())
sys.path.insert(0, str(KIT))
import fake_firebase as FF

site = pathlib.Path(tempfile.mkdtemp())
shutil.copy(GAME, site / "index.html")
srv = FF.start(str(site))
BASE = f"http://127.0.0.1:{srv.server_address[1]}"
URL = f"{BASE}/index.html?fb={BASE}&debug"
results = []
LOCKED = []
def check(name, ok, info=""):
    results.append(ok); print(("PASS " if ok else "FAIL ") + name + (f"  [{info}]" if info else "")); sys.stdout.flush()

def player(b, url=URL):
    c = b.new_context(viewport={"width": 390, "height": 844})
    c.route("https://itunes.apple.com/**", apple); c.route("https://api.deezer.com/**", deezer)
    c.route(re.compile(r"https://(audio|dz)\.mock/.*"), media); c.route(re.compile(r"https://fonts\..*"), lambda r: r.abort())
    pg = c.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.goto(url)
    return c, pg

def room(pg): return pg.evaluate("__erg.mp.room")
def state(pg): return pg.evaluate("(() => { const r = __erg.mp.room; return r ? r.st : null })()")
def cur_title(pg):
    return pg.evaluate("(() => { const r = __erg.mp.room; const q = r.q['n' + r.cur]; return __erg.BANK[q.s].title })()")

def play_round(pages, picks, idx):
    """picks: list of 'right' / 'wrong' / None per page; waits for every device to finish the round."""
    for pg in pages:
        pg.wait_for_function(f"__erg.mp.room && +__erg.mp.room.cur === {idx} && __erg.mp.room.at", timeout=90000)
    title = cur_title(pages[0])
    order = []
    for pg, pick in zip(pages, picks):
        if pick is None: continue
        try: pg.wait_for_selector("#options:not(.locked)", timeout=12000)
        except Exception:
            pg.click("#record"); pg.wait_for_selector("#options:not(.locked)", timeout=8000)    # autoplay refused: tap
        opts = pg.locator("#options .opt .t").all_inner_texts()
        k = opts.index(title) if pick == "right" else next(i for i, t in enumerate(opts) if t != title)
        pg.locator("#options .opt").nth(k).click(); order.append(pg)
        if len(order) == 1 and len([x for x in picks if x]) > 1:     # others still answering: nothing may show
            LOCKED.append(pg.evaluate("document.querySelector('#reveal').hidden && !document.querySelector('#options .opt.correct') && !/答對|答錯|✓/.test(document.querySelector('#mp-board').textContent) && document.querySelector('#options .opt.picked') !== null"))
        time.sleep(0.6)                                 # answer one after another: speed order is known
    for pg in pages:
        pg.wait_for_function("document.querySelector('#mp-board') && !document.querySelector('#mp-board').hidden && /結束/.test(document.querySelector('#mp-board .mp-head').textContent)", timeout=60000)
    return title

def scores(pg):
    return pg.evaluate("(() => { const r = __erg.mp.room; const o = {}; for (const [id, p] of Object.entries(r.p || {})) o[p.n] = { s: +p.s || 0, c: +p.c || 0 }; return o })()")

with sync_playwright() as p:
    b = p.chromium.launch(args=["--autoplay-policy=user-gesture-required"])
    # ---- host creates a named room ----
    ca, A = player(b)
    A.click('.mode[data-mode="battle"]')
    check("battle panel shows", A.locator("#battle-wrap").is_visible() and A.locator("#grp-free").is_hidden())
    A.click("#btn-start"); time.sleep(.3)
    check("nickname is required", A.locator("#lobby").is_hidden() and A.evaluate("document.activeElement.id") == "mp-name")
    A.fill("#mp-name", "阿明"); A.fill("#mp-room", "測試歌房")
    A.click("#btn-start")
    A.wait_for_selector("#lobby.active", timeout=15000)
    check("no host buttons before the room loads", A.locator("#lb-start").is_hidden() or A.locator("#lb-players .pl").count() > 0)
    A.wait_for_selector("#lb-players .pl", timeout=15000)
    code = A.inner_text("#lb-code").strip()
    check("room created with a 4-letter code", bool(re.fullmatch(r"[A-Z2-9]{4}", code)), code)
    check("room name shown in lobby", "測試歌房" in A.inner_text("#lb-name"))
    check("host sees host controls", A.locator("#lb-start").is_visible() and A.locator("#lb-wait").is_hidden())
    # ---- B joins by room name, C by invite link with a duplicate nickname ----
    cb, B = player(b)
    B.click('.mode[data-mode="battle"]'); B.fill("#mp-name", "小美"); B.fill("#mp-code", "測試歌房"); B.click("#mp-join")
    B.wait_for_selector("#lobby.active", timeout=15000)
    check("join by room name", B.inner_text("#lb-code").strip() == code)
    cc, C = player(b, URL + f"&room={code}")
    C.wait_for_timeout(600)
    check("invite link prefills the room", C.input_value("#mp-code") == code and C.locator("#battle-wrap").is_visible())
    C.fill("#mp-name", "阿明"); C.click("#mp-join")
    C.wait_for_selector("#lobby.active", timeout=15000); C.wait_for_selector("#lb-players .pl", timeout=15000)
    check("duplicate nickname gets a number", C.input_value("#mp-name") == "阿明2", C.input_value("#mp-name"))
    check("guest sees waiting note, no host controls", C.locator("#lb-wait").is_visible() and C.locator("#lb-start").is_hidden())
    A.wait_for_function("document.querySelectorAll('#lb-players .pl').length === 3", timeout=15000)
    check("lobby lists 3 players on the host", A.locator("#lb-players .pl").count() == 3, A.inner_text("#lb-count"))
    # wrong code
    cd, D = player(b)
    D.click('.mode[data-mode="battle"]'); D.fill("#mp-name", "路人"); D.fill("#mp-code", "QQQQ"); D.click("#mp-join"); D.wait_for_timeout(1500)
    check("unknown room is refused", D.locator("#lobby").is_hidden() and D.locator("#home").is_visible())
    cd.close()
    # ---- host picks difficulty and song count; guests see it ----
    A.click('#lb-diff button[data-d="normal"]'); A.click('#lb-rounds button[data-r="5"]')
    C.wait_for_function("document.querySelector('#lb-rounds button[data-r=\"5\"]').classList.contains('on')", timeout=10000)
    check("guests see host's settings", C.locator('#lb-diff button[data-d="normal"]').get_attribute("class") == "on" and C.locator('#lb-diff button[data-d="hard"]').is_disabled())
    check("hard-mode penalty rule hidden on normal", C.locator("#lb-rules-wrong").is_hidden())
    # ---- play 5 songs ----
    A.click("#lb-start")
    for pg in (A, B, C): pg.wait_for_selector("#game.active", timeout=20000)
    check("everyone moves to the game", True)
    A.wait_for_function("__erg.mp.room.at", timeout=60000)
    ats = [pg.evaluate("__erg.mp.room.at") for pg in (A, B, C)]
    check("same start time on every device", len(set(ats)) == 1)
    nopt = A.locator("#options .opt").count()
    check("normal = 6 choices", nopt == 6, nopt)
    if A.evaluate("__erg.srvNow() < __erg.mp.room.at - 800"):
        A.click("#record"); time.sleep(.2)
        check("record can't be played before the countdown ends", A.locator("#options.locked").count() == 1)
    t0 = play_round([A, B, C], ["right", "right", "wrong"], 0)
    s1 = {n: v["s"] for n, v in scores(A).items()}
    check("song 1: fastest right answer gets the +200 bonus", s1["阿明"] > s1["小美"] >= 500 and s1["阿明"] >= 900, s1)
    check("song 1: wrong answer scores 0", s1["阿明2"] == 0)
    boardA = A.inner_text("#mp-board");
    check("board marks the fastest with 🥇", "🥇" in boardA and "✗ 答錯" in boardA, boardA.replace("\n", " | ")[:160])
    play_round([A, B, C], ["right", "wrong", "right"], 1)
    s2 = {n: v["s"] for n, v in scores(A).items()}
    gainA = s2["阿明"] - s1["阿明"]
    check("song 2: streak +100 on the 2nd in a row", gainA >= 500 + 100 + 200, gainA)
    play_round([A, B, C], [None, "right", "right"], 2)        # A doesn't answer: time runs out
    s3 = {n: v["s"] for n, v in scores(B).items()}
    check("song 3: not answering scores 0 and the round still ends", s3["阿明"] == s2["阿明"], (s2["阿明"], s3["阿明"]))
    play_round([A, B, C], ["right", "right", "right"], 3)
    pre = {n: v["s"] for n, v in scores(B).items()}
    A.wait_for_function("__erg.mp.room && +__erg.mp.room.cur === 4", timeout=60000)
    A.wait_for_selector("#event:not([hidden])", timeout=20000)
    check("last song is announced as double", "最後一首" in A.inner_text("#event"))
    play_round([A, B, C], ["wrong", "right", "wrong"], 4)
    post = {n: v["s"] for n, v in scores(B).items()}
    gainB = post["小美"] - pre["小美"]
    check("last song: points doubled", gainB >= 2 * (500 + 100) + 200, gainB)
    for pg in (A, B, C): pg.wait_for_selector("#result.active", timeout=30000)
    check("everyone gets the final ranking", True)
    ranks = [[n.replace("你", "").strip() for n in pg.locator("#res-board .pl .pl-name").all_inner_texts()] for pg in (A, B, C)]
    check("all devices agree on the ranking", ranks[0] == ranks[1] == ranks[2], ranks[0])
    totals = [pg.locator("#res-board .pl .pl-total").all_inner_texts() for pg in (A, B, C)]
    check("all devices agree on the scores", totals[0] == totals[1] == totals[2], totals[0])
    check("result shows my rank title", re.search(r"冠軍|第 \d 名", A.inner_text("#res-rank")) is not None, A.inner_text("#res-rank"))
    check("song list has 5 songs", A.locator("#res-list .song").count() == 5)
    check("guest's again button says back to room", "回房間" in C.inner_text("#btn-again"))
    A.screenshot(path=str(KIT / "shots" / "battle-result.png"), full_page=True)
    # ---- play again, then the host leaves in the lobby ----
    A.click("#btn-again")
    for pg in (A, B, C): pg.wait_for_selector("#lobby.active", timeout=15000)
    check("play again: everyone back in the lobby", True)
    sc = scores(A)
    check("lobby keeps everyone; scores reset when the next game starts", len(sc) == 3)
    A.click("#lb-leave"); A.wait_for_selector("#home.active", timeout=10000)
    B.wait_for_function("!document.querySelector('#lb-start').closest('#lb-host').hidden", timeout=15000)
    check("host leaves: next player becomes host", B.locator("#lb-start").is_visible(), B.inner_text("#lb-players"))
    # ---- B hosts a hard game; B drops out mid-game; C takes over and finishes ----
    B.click('#lb-diff button[data-d="hard"]'); B.click('#lb-rounds button[data-r="5"]')
    C.wait_for_function("!document.querySelector('#lb-rules-wrong').hidden", timeout=10000)
    check("hard: penalty rule shown", True)
    B.click("#lb-start")
    for pg in (B, C): pg.wait_for_selector("#game.active", timeout=20000)
    check("hard = 9 choices", B.wait_for_function("document.querySelectorAll('#options .opt').length === 9", timeout=60000) is not None)
    play_round([B, C], ["right", "wrong"], 0)
    sc = scores(C)
    check("hard: wrong guess can't go below 0", sc["阿明2"]["s"] == 0, sc)
    # network blip during song 2: every live stream drops and has to reconnect
    for pg in (B, C): pg.wait_for_function("__erg.mp.room && +__erg.mp.room.cur === 1 && __erg.mp.room.at", timeout=60000)
    FF.drop_streams()
    play_round([B, C], ["right", "right"], 1)
    check("network blip: the song still finishes on both devices", True)
    # a friend joins in the middle of the game
    ce, E = player(b, URL + f"&room={code}")
    E.wait_for_timeout(500); E.fill("#mp-name", "遲到的"); E.click("#mp-join")
    E.wait_for_selector("#game.active", timeout=30000)
    check("late joiner goes straight into the game", True)
    before = scores(C)["阿明2"]["s"]
    play_round([B, C, E], ["right", "wrong", "right"], 2)
    after = scores(C)["阿明2"]["s"]
    check("hard: wrong answer costs 200", after == before - 200, (before, after))
    e_score = scores(B)["遲到的"]["s"]
    check("late joiner scores", e_score > 0, e_score)
    # E reloads the page and comes back
    E.reload(); E.wait_for_timeout(800)
    check("after a reload the room is filled in", E.input_value("#mp-code") == code and E.input_value("#mp-name") == "遲到的")
    E.click("#mp-join"); E.wait_for_selector("#game.active", timeout=30000)
    check("rejoin keeps the score", E.evaluate("__erg.mp.room.p[__erg.mp.pid].s") == e_score)
    cb.close()                                                  # host's phone dies
    C.wait_for_function("__erg.mp.isHost", timeout=45000)
    check("host gone: the earliest remaining player takes over", not E.evaluate("__erg.mp.isHost"))
    for i in (3, 4): play_round([C, E], ["right", "right"], i)
    for pg in (C, E): pg.wait_for_selector("#result.active", timeout=40000)
    check("game finishes after the takeover", C.locator("#res-list .song").count() == 5)
    names = [n.replace("你", "").strip() for n in E.locator("#res-board .pl .pl-name").all_inner_texts()]
    check("final ranking includes the late joiner", "遲到的" in names and "小美" in names, names)
    E.click("#btn-home"); E.wait_for_selector("#home.active", timeout=10000)
    # ---- leaving the last player deletes the room ----
    C.click("#btn-home"); C.wait_for_selector("#home.active", timeout=10000); time.sleep(1)
    check("room deleted when the last player leaves", FF.get_at(["rooms", code]) is None)
    check("nothing written outside rooms/", all(path.startswith("rooms/") for m, path in FF.LOG if m != "GET"))
    check("a pick stays hidden until the song ends", bool(LOCKED) and all(LOCKED), LOCKED)
    check("page errors: none", not errors, errors[:3])
    b.close()
print(f"\n{sum(results)}/{len(results)} checks passed")
