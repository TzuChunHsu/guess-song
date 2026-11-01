import json, re, sys, time, urllib.parse, pathlib
from playwright.sync_api import sync_playwright
GAME = pathlib.Path(sys.argv[1]).resolve(); KIT = pathlib.Path(__file__).parent
tone = (KIT / "tone.mp3").read_bytes()
bank = [l.split('|') for l in open(sys.argv[2], encoding='utf-8').read().splitlines() if l and not l.startswith('#') and not l.startswith('@')]
def find(term):
    hit = None
    for i, (t, a, y) in enumerate(bank):
        if t.split('/')[0] in term and (hit is None or len(t) > len(bank[hit][0])): hit = i
    return hit
def apple(r):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(r.request.url).query); h = find(q['term'][0])
    res = [] if h is None else [{"trackName": bank[h][0].split('/')[0], "artistName": bank[h][1].split('、')[0], "previewUrl": f"https://audio.mock/{h}.m4a", "artworkUrl100": "", "trackViewUrl": ""}]
    r.fulfill(status=200, content_type="text/javascript", body=f"{q['callback'][0]}({json.dumps({'results': res}, ensure_ascii=False)});")
errors = []
def new_page(b, w=390, h=844):
    c = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=True, has_touch=True)
    c.route("https://itunes.apple.com/**", apple)
    c.route("https://audio.mock/**", lambda r: r.fulfill(status=200, content_type="audio/mpeg", body=tone, headers={"Accept-Ranges": "bytes"}))
    c.route(re.compile(r"https://(fonts|api\.deezer).*"), lambda r: r.abort())
    c.add_init_script("const op=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){if(this.src.indexOf('mock')>0)window.__last=this;return op.call(this)};")
    pg = c.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.goto(GAME.as_uri()); return c, pg
def ready(pg): pg.wait_for_function("document.querySelector('#status-text').textContent.startsWith('點唱片')", timeout=60000)
def correct_index(pg):
    sid = int(re.search(r"/(\d+)\.m4a", pg.evaluate("__last.src")).group(1)); title = bank[sid][0].split('/')[0]
    return pg.locator("#options .opt .t").all_inner_texts().index(title)
def start_play(pg):
    ready(pg); pg.tap("#record"); pg.wait_for_selector("#options:not(.locked)", timeout=8000)
with sync_playwright() as p:
    b = p.chromium.launch()
    # --- 10 s limit: titles only, speed scoring, pause on dialog, timeout ---
    c, pg = new_page(b)
    pg.click('#seg-time button[data-t="10"]')
    pg.screenshot(path=KIT / "shots" / "24-home-time.png", full_page=True)
    pg.click("#btn-start")
    start_play(pg)
    print("artist text inside options:", pg.locator("#options .opt .a").count(), "| option texts:", pg.locator("#options .opt").all_inner_texts()[:3])
    print("clock after start:", pg.inner_text("#hud-time"))
    pg.wait_for_timeout(400); pg.screenshot(path=KIT / "shots" / "25-game-n9.png")
    pg.locator("#options .opt").nth(correct_index(pg)).tap(); pg.wait_for_selector("#btn-next:not([hidden])")
    fast = pg.inner_text("#rv-verdict"); fast_pts = int(pg.inner_text("#hud-score").replace(",", ""))
    pg.wait_for_timeout(900); pg.screenshot(path=KIT / "shots" / "26-reveal-n9.png")
    pg.tap("#btn-next"); start_play(pg)
    # open the diagnostics dialog for 3 s: the clock must not run meanwhile
    t_before = float(re.search(r"([\d.]+)", pg.inner_text("#hud-time")).group(1))
    pg.tap("#btn-diag"); pg.wait_for_timeout(3000); pg.click("#modal-actions button:not(.primary)")
    t_after = float(re.search(r"([\d.]+)", pg.inner_text("#hud-time")).group(1))
    print(f"clock {t_before} -> {t_after} across a 3 s dialog (paused if the drop is small)")
    pg.wait_for_timeout(3500)
    pg.locator("#options .opt").nth(correct_index(pg)).tap(); pg.wait_for_selector("#btn-next:not([hidden])")
    slow = pg.inner_text("#rv-verdict"); slow_pts = int(pg.inner_text("#hud-score").replace(",", "")) - fast_pts
    print(f"fast: '{fast}' -> {fast_pts} pts | slow: '{slow}' -> {slow_pts} pts")
    pg.tap("#btn-next"); start_play(pg)
    pg.wait_for_timeout(11000)
    print("after 11 s idle with 10 s limit:", pg.inner_text("#rv-verdict"), "| answered:", not pg.locator("#btn-next").is_hidden())
    c.close()
    # --- unlimited ---
    c, pg = new_page(b); pg.click('#seg-time button[data-t="0"]'); pg.click("#btn-start"); start_play(pg)
    pg.wait_for_timeout(12000)
    print("unlimited after 12 s:", pg.inner_text("#hud-time"), "| timer bar hidden:", pg.locator("#timer").is_hidden(), "| auto-answered:", not pg.locator("#btn-next").is_hidden())
    c.close()
    # --- layout on a small phone (iPhone SE) with 9 and 4 options ---
    for n in (9, 4):
        c, pg = new_page(b, 375, 667); pg.click(f'#seg-n button[data-n="{n}"]'); pg.click("#btn-start"); start_play(pg)
        box = pg.locator("#options .opt").first.bounding_box()
        bottom = pg.evaluate("document.querySelector('#items').getBoundingClientRect().bottom")
        print(f"SE {n} options: box {box['width']:.0f}x{box['height']:.0f}px, items bottom {bottom:.0f} / 667")
        pg.screenshot(path=KIT / "shots" / f"27-se-n{n}.png"); c.close()
    b.close()
print("errors:", errors or "none")
