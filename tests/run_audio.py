import json, re, sys, urllib.parse, pathlib
from playwright.sync_api import sync_playwright
GAME = pathlib.Path(sys.argv[1]).resolve(); KIT = pathlib.Path(__file__).parent
tone = (KIT / "tone.mp3").read_bytes()
def it(r):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(r.request.url).query)
    term = q["term"][0]
    res = [{"trackName": term.split(" ")[-1], "artistName": term.split(" ")[0] if " " in term else "X", "previewUrl": "http://audio.mock/a.m4a", "artworkUrl100": "", "trackViewUrl": ""}]
    r.fulfill(status=200, content_type="text/javascript", body=f"{q['callback'][0]}({json.dumps({'results': res}, ensure_ascii=False)});")
with sync_playwright() as p:
    b = p.chromium.launch()   # default autoplay policy (like a real phone/desktop browser)
    c = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    c.route("https://itunes.apple.com/**", it)
    c.route(re.compile(r"https?://audio\.mock/.*"), lambda r: r.fulfill(status=200, content_type="audio/mpeg", body=tone, headers={"Accept-Ranges": "bytes"}))
    c.route(re.compile(r"https://(fonts|api\.deezer).*"), lambda r: r.abort())
    c.add_init_script("window.__plays=[];const op=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){window.__last=this;window.__plays.push(this.src);return op.call(this)};")
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(GAME.as_uri())
    # sound test button on home
    pg.click("#btn-beep"); pg.wait_for_timeout(300)
    print("beep playing:", pg.evaluate("!window.__last.paused || window.__last.ended"))
    pg.click("#btn-start"); pg.wait_for_selector("#options .opt", timeout=60000)
    for rnd in range(3):
        pg.tap("#record"); pg.wait_for_selector("#options:not(.locked)", timeout=8000)
        pg.wait_for_timeout(1200)
        st = pg.evaluate("({src: __last.src, paused: __last.paused, muted: __last.muted, vol: __last.volume, t: __last.currentTime})")
        frag = float(st["src"].split("#t=")[1])
        print(f"round {rnd+1}: https={st['src'].startswith('https://')} frag={frag} t={st['t']:.2f} paused={st['paused']} muted={st['muted']} vol={st['vol']}")
        assert not st["paused"] and not st["muted"] and frag <= st["t"] <= frag + 3.2, st
        pg.wait_for_timeout(2500)
        assert pg.evaluate("__last.paused"), "clip should stop at its end"
        # replay starts again from the clip start
        pg.tap("#btn-replay"); pg.wait_for_timeout(700)
        t2 = pg.evaluate("__last.currentTime"); assert frag <= t2 <= frag + 1.5 and not pg.evaluate("__last.paused"), t2
        pg.wait_for_timeout(2600)
        # extend -> 6s
        ext = float(re.search(r"→ ([\d.]+) 秒", pg.inner_text("#ext-sub")).group(1))   # random events can halve clips
        pg.tap("#btn-extend"); pg.wait_for_timeout(int((ext - 1.2) * 1000))
        assert not pg.evaluate("__last.paused"), f"extended {ext}s clip should still play near its end"
        pg.wait_for_timeout(2200); assert pg.evaluate("__last.paused"), "extended clip should stop at its end"
        if rnd == 0:
            pg.tap("#btn-diag"); pg.wait_for_selector("#modal:not([hidden])")
            print("diag:", pg.inner_text("#modal-text").split("\n\n")[-1].replace("\n", " | "))
            pg.screenshot(path=KIT / "shots" / "11-diag.png")
            pg.click("#modal-actions button.primary"); pg.wait_for_timeout(200)
        pg.locator("#options .opt").first.tap(); pg.wait_for_selector("#btn-next:not([hidden])")
        pg.wait_for_timeout(500)
        print("   reveal keeps playing:", not pg.evaluate("__last.paused"))
        pg.tap("#btn-next"); pg.wait_for_selector("#options .opt .t", timeout=60000)
    print("errors:", errs or "none")
    b.close()
