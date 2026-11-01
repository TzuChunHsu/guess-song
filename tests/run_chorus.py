import json, re, sys, time, urllib.parse, pathlib
from playwright.sync_api import sync_playwright
GAME = pathlib.Path(sys.argv[1]).resolve(); KIT = pathlib.Path(__file__).parent
audio = (KIT / "chorus.mp3").read_bytes()
bank = [l.split('|') for l in open(sys.argv[2], encoding='utf-8').read().splitlines() if l and not l.startswith('#') and not l.startswith('@')]
state = {"fail_next": 0, "calls": 0, "abort_all": False}
def it(r):
    state["calls"] += 1
    if state["abort_all"] or state["fail_next"] > 0:
        if state["fail_next"] > 0: state["fail_next"] -= 1
        return r.fulfill(status=403, body="rate limited")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(r.request.url).query); term = q['term'][0]
    hit = None
    for i, (t, a, y) in enumerate(bank):
        if t.split('/')[0] in term and (hit is None or len(t) > len(bank[hit][0])): hit = i
    res = [] if hit is None else [{"trackName": bank[hit][0].split('/')[0], "artistName": bank[hit][1].split('、')[0], "previewUrl": f"https://audio.mock/{hit}.m4a", "artworkUrl100": "", "trackViewUrl": ""}]
    r.fulfill(status=200, content_type="text/javascript", body=f"{q['callback'][0]}({json.dumps({'results': res}, ensure_ascii=False)});")
def ctx(b, cors=True):
    c = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    c.route("https://itunes.apple.com/**", it)
    hdr = {"Access-Control-Allow-Origin": "*"} if cors else {}
    c.route("https://audio.mock/**", lambda r: r.fulfill(status=200, content_type="audio/mpeg", body=audio, headers=hdr))
    c.route(re.compile(r"https://(fonts|api\.deezer).*"), lambda r: r.abort())
    c.add_init_script("window.__plays=[];const op=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){window.__last=this;window.__plays.push(this.src);return op.call(this)};")
    return c
errors = []
def page_of(c):
    pg = c.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.goto(GAME.as_uri()); return pg
with sync_playwright() as p:
    b = p.chromium.launch()
    # ---- 1. chorus mode with readable audio ----
    c = ctx(b); pg = page_of(c)
    
    pg.click('#seg-clip button[data-clip="chorus"]')
    pg.screenshot(path=KIT / "shots" / "16-home-chorus.png", full_page=True)
    pg.click("#btn-start"); pg.wait_for_selector("#game.active", timeout=20000)
    print("timer element present:", pg.locator("#timer").count() > 0)
    for rnd in range(3):
        pg.wait_for_function("document.querySelector('#status-text').textContent.startsWith('點唱片')", timeout=60000)
        status = pg.inner_text("#status-text")
        pg.tap("#record"); pg.wait_for_selector("#options:not(.locked)", timeout=8000); pg.wait_for_timeout(500)
        st = pg.evaluate("({src: __last.src.slice(0, 5), t: __last.currentTime, paused: __last.paused})")
        print(f"chorus round {rnd+1}: status='{status}' src={st['src']} t={st['t']:.2f} paused={st['paused']}")
        assert st['src'] == 'blob:' and 11.5 <= st['t'] <= 15.5 and not st['paused'], st
        if rnd == 0:
            pg.screenshot(path=KIT / "shots" / "17-chorus-playing.png")
            pg.tap("#btn-diag"); pg.wait_for_selector("#modal:not([hidden])")
            print("diag:", [l for l in pg.inner_text("#modal-text").split("\n") if "副歌" in l])
            pg.click("#modal-actions button:not(.primary)")
        pg.locator("#options .opt").first.tap(); pg.wait_for_selector("#btn-next:not([hidden])"); pg.tap("#btn-next")
    c.close()
    # ---- 2. no timer: wait past the old 25 s limit in random mode ----
    c = ctx(b); pg = page_of(c)
    pg.click("#btn-start"); pg.wait_for_selector("#options .opt", timeout=30000)
    pg.tap("#record"); pg.wait_for_selector("#options:not(.locked)"); pg.wait_for_timeout(27000)
    print("after 27 s idle, auto-answered:", not pg.locator("#btn-next").is_hidden())
    c.close()
    b.close()
print("errors:", errors or "none")
