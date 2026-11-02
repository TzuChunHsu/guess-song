"""Online battle: a preview that won't load on one phone is swapped for everyone before it plays,
and while the next song is late, the last one keeps playing.

    python3 tests/run_battle_swap.py index.html src/bank.txt
"""
import os, pathlib, re, shutil, sys, tempfile, time
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_battle.py"), encoding="utf-8").read().split("with sync_playwright() as p:")[0])

BAD = {"seen": [], "ids": set()}
def bad_media(r):
    """the guest's phone can't load the 2nd song it is handed (every file of it)"""
    sid = int(re.search(r"/(\d+)-(\w+)\.(m4a|mp3)", r.request.url).group(1))
    if sid not in BAD["seen"]:
        BAD["seen"].append(sid)
        if len(BAD["seen"]) == 2: BAD["ids"].add(sid)
    if sid in BAD["ids"]: return r.fulfill(status=404, body="")
    media(r)

def player_bad(b, url):
    c = b.new_context(viewport={"width": 390, "height": 844})
    c.route("https://itunes.apple.com/**", apple); c.route("https://api.deezer.com/**", deezer)
    c.route(re.compile(r"https://(audio|dz)\.mock/.*"), bad_media); c.route(re.compile(r"https://fonts\..*"), lambda r: r.abort())
    pg = c.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.goto(url)
    return c, pg

with sync_playwright() as p:
    b = p.chromium.launch(args=["--autoplay-policy=user-gesture-required"])
    ca, A = player(b)
    A.click('.mode[data-mode="battle"]')
    A.fill("#mp-name", "房主"); A.click("#btn-start"); A.wait_for_selector("#lb-players .pl", timeout=15000)
    code = A.inner_text("#lb-code").strip()
    cb, B = player_bad(b, URL + f"&room={code}")
    B.wait_for_timeout(500); B.fill("#mp-name", "客人"); B.click("#mp-join"); B.wait_for_selector("#lb-players .pl", timeout=15000)
    A.click('#lb-rounds button[data-r="5"]')
    A.wait_for_function("__erg.G && __erg.G.queue.length >= 2", timeout=60000)
    A.click("#lb-start")

    # ---- the guest can't load one of the songs written ahead: it is replaced before it plays ----
    t0 = time.time()
    while not BAD["ids"] and time.time() - t0 < 40: B.wait_for_timeout(200)
    check("guest hit a preview that won't load", bool(BAD["ids"]))
    bad = next(iter(BAD["ids"]), -1)
    A.wait_for_function(f"(() => {{ const r = __erg.mp.room; const qs = Object.values(r.q || {{}}).filter(Boolean); return qs.length >= 3 && !qs.some(q => +q.s === {bad}) && !Object.keys(r.bad || {{}}).length }})()", timeout=40000)
    check("host swapped that song for another one", True)
    dead = A.evaluate("JSON.parse(localStorage.getItem('erg_deadSongs') || '{}')")
    check("the song is marked so it isn't picked again for a while", any(k.split("|")[0] == A.evaluate(f"__erg.BANK[{bad}].title") for k in dead), list(dead)[:3])
    B.wait_for_function("(() => { const r = __erg.mp.room; return [0, 1, 2].every(k => { const q = r.q && r.q['n' + k], a = __erg.mp.aud[k]; return q && a && a.qu === String(q.u) && a.ok === true }) })()", timeout=40000)
    check("guest has the replacement loaded", True)

    # ---- the host stops finding songs for a while: the 4th song is late ----
    time.sleep(1)
    A.evaluate("""(() => { const mp = __erg.mp; let v = mp.preparing; window.__hold = true;
        Object.defineProperty(mp, 'preparing', { configurable: true, get(){ return window.__hold || v }, set(x){ v = x } }) })()""")
    for i in range(3): play_round([A, B], ["right", "right"], i)
    B.wait_for_function("/準備第 4 首/.test(document.querySelector('#mp-board .mp-head').textContent)", timeout=30000)
    check("guest is told the next song is on its way", True)
    check("host says what it is doing", "正在找第 4 首" in A.inner_text("#mp-board .mp-head"), A.inner_text("#mp-board .mp-head"))
    time.sleep(20)                     # past the end of the 14-second reveal
    for name, pg in (("host", A), ("guest", B)):
        st = pg.evaluate("({ idx: __erg.R && __erg.R.mpIdx, paused: __erg.R && __erg.R.audio.paused, t: __erg.R && __erg.R.audio.currentTime })")
        check(f"{name}: song 3 keeps playing while waiting", st["idx"] == 2 and st["paused"] is False, st)
    A.evaluate("window.__hold = false")
    play_round([A, B], ["right", "right"], 3)
    check("the late song plays once it is ready", True)
    play_round([A, B], ["right", "right"], 4)
    for pg in (A, B): pg.wait_for_selector("#result.active", timeout=30000)
    check("game finishes with 5 songs", A.locator("#res-list .song").count() == 5 and B.locator("#res-list .song").count() == 5)
    bpid = B.evaluate("__erg.mp.pid")
    skips = A.evaluate(f"Object.values(__erg.mp.room.a || {{}}).filter(n => n && n['{bpid}'] && +n['{bpid}'].k === -2).length")
    check("guest never had to sit a song out", skips == 0, skips)
    check("the swapped song never came back", A.evaluate(f"!Object.values(__erg.mp.room.q || {{}}).some(q => q && +q.s === {bad})"))
    check("page errors: none", not errors, errors[:3])
    b.close()
print(f"\n{sum(results)}/{len(results)} checks passed")
