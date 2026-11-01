"""Drive the game in headless Chromium with mocked iTunes/Deezer/audio responses."""
import json, re, sys, urllib.parse, pathlib, random
from playwright.sync_api import sync_playwright

GAME = pathlib.Path(sys.argv[1]).resolve()
KIT = pathlib.Path(__file__).parent
OUT = KIT / "shots"; OUT.mkdir(exist_ok=True)
import opencc
t2s = opencc.OpenCC("t2s")

bank = []
for l in open(sys.argv[2], encoding="utf-8").read().splitlines():
    if l and not l.startswith("#") and not l.startswith("@"):
        t, a, y = l.split("|")
        bank.append({"id": len(bank), "title": t.split("/")[0], "alts": t.split("/"), "artist": a.split("、")[0], "year": int(y)})

MISSING = {5, 17, 40}      # songs the mock store "doesn't have"
SIMPLIFIED = {3, 9, 60}    # returned in simplified chars
LIVE_TOO = {0, 100}        # also return a live version
calls = {"itunes": 0, "deezer": 0}

def find_song(term):
    tn = term.replace(" ", "")
    best = None
    for s in bank:
        for alt in s["alts"]:
            for v in (alt, t2s.convert(alt)):
                if v.replace(" ", "") in tn and (best is None or len(v) > len(best[1])):
                    best = (s, v)
    return best[0] if best else None

def itunes(route):
    calls["itunes"] += 1
    q = urllib.parse.parse_qs(urllib.parse.urlparse(route.request.url).query)
    cb = q["callback"][0]; term = q["term"][0]
    s = find_song(term)
    res = []
    if s and s["id"] not in MISSING:
        name = s["title"]; artist = s["artist"]
        if s["id"] in SIMPLIFIED:
            name = t2s.convert(name); artist = t2s.convert(artist)
        mk = lambda n, sid: {"trackName": n, "artistName": artist, "collectionName": "專輯", "previewUrl": f"https://audio.mock/{sid}.m4a",
                             "artworkUrl100": f"https://img.mock/{sid}/100x100bb.jpg", "trackViewUrl": f"https://music.apple.com/tw/song/{sid}"}
        if s["id"] in LIVE_TOO:
            res.append(mk(name + " (Live)", f"{s['id']}-live"))
        res.append(mk(name, s["id"]))
        res.append({**mk(name + "愛", 9999), "artistName": "別人"})  # decoy
    route.fulfill(status=200, content_type="text/javascript", body=f"{cb}({json.dumps({'resultCount': len(res), 'results': res}, ensure_ascii=False)});")

def deezer(route):
    calls["deezer"] += 1
    q = urllib.parse.parse_qs(urllib.parse.urlparse(route.request.url).query)
    route.fulfill(status=200, content_type="text/javascript", body=f"{q['callback'][0]}({{\"data\":[]}});")

errors = []
def run(page_fn):
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        ctx.route("https://itunes.apple.com/**", itunes)
        ctx.route("https://api.deezer.com/**", deezer)
        ctx.route("https://audio.mock/**", lambda r: r.fulfill(status=200, content_type="audio/mpeg", body=(KIT / "tone.mp3").read_bytes()))
        ctx.route("https://img.mock/**", lambda r: r.fulfill(status=200, content_type="image/png", body=(KIT / "art.png").read_bytes()))
        ctx.route(re.compile(r"https://fonts\.(googleapis|gstatic)\.com/.*"), lambda r: r.abort())
        ctx.add_init_script("""
          window.__toasts = []; window.__status = [];
          document.addEventListener('DOMContentLoaded', () => {
            new MutationObserver(m => m.forEach(r => r.addedNodes.forEach(n => n.textContent && __toasts.push(n.textContent)))).observe(document.querySelector('#toast'), {childList: true});
            new MutationObserver(() => __status.push(document.querySelector('#status-text').textContent)).observe(document.querySelector('#status-text'), {childList: true, characterData: true, subtree: true});
          });
          window.__plays = [];
          const op = HTMLMediaElement.prototype.play;
          HTMLMediaElement.prototype.play = function(){ window.__plays.push(this.src); return op.call(this); };
        """)
        page = ctx.new_page()
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(GAME.as_uri())
        page_fn(page)
        b.close()

def current_song_id(page):
    src = page.evaluate("window.__plays[window.__plays.length-1]")
    return int(re.search(r"/(\d+)(-live)?\.m4a", src).group(1)), src

def play_and_wait(page):
    page.wait_for_function("document.querySelector('#status-text').textContent.startsWith('點唱片')", timeout=120000)
    page.click("#record")
    try:
        page.wait_for_selector("#options:not(.locked)", timeout=8000)
    except Exception:
        print("DEBUG all toasts:", page.evaluate("__toasts"), "| last statuses:", page.evaluate("__status.slice(-8)"))
        print("DEBUG status:", page.inner_text("#status-text"), "| hud:", page.inner_text("#hud-round"), "| toasts:", page.locator("#toast .toast").all_inner_texts())
        page.screenshot(path=OUT / "debug.png"); raise

def answer(page, correct=True):
    sid, src = current_song_id(page)
    title = bank[sid]["title"]
    opts = page.locator("#options .opt .t").all_inner_texts()
    idx = opts.index(title) if correct else next(i for i, t in enumerate(opts) if t != title)
    page.locator("#options .opt").nth(idx).click()
    page.wait_for_selector("#btn-next:not([hidden])")
    return sid, src, opts

def classic(page):
    page.screenshot(path=OUT / "1-home.png", full_page=True)
    page.click("#btn-start")
    page.wait_for_selector("#options .opt")
    page.screenshot(path=OUT / "2-ready.png")
    for r in range(10):
        play_and_wait(page)
        if r == 0:
            page.wait_for_timeout(700)
            page.screenshot(path=OUT / "3-playing.png")
        if r == 1:
            page.wait_for_selector("#btn-extend:not([disabled])", timeout=6000)
            page.click("#btn-extend"); page.wait_for_timeout(300)
        if r == 2:
            page.click('#items .item[data-item="cut"]')
            assert page.locator("#options .opt.removed").count() == 4, "cut should remove 4 of 9"
        if r == 3:
            before = current_song_id(page)[0]
            page.click('#items .item[data-item="skip"]')
            page.wait_for_selector("#options .opt"); play_and_wait(page)
            assert current_song_id(page)[0] != before
        sid, src, opts = answer(page, correct=(r not in (4, 7)))
        assert "-live" not in src, "picked live version"
        assert len(opts) == 9 and len(set(opts)) == 9, opts
        if r == 0:
            page.wait_for_timeout(600)
            page.screenshot(path=OUT / "4-reveal.png")
        if r == 4:
            page.screenshot(path=OUT / "5-wrong.png")
        page.click("#btn-next")
    page.wait_for_selector("#result.active")
    page.wait_for_timeout(1200)
    page.screenshot(path=OUT / "6-result.png", full_page=True)
    print("classic:", page.inner_text("#res-score"), page.inner_text("#res-grid"), page.inner_text("#res-stats").replace("\n", " "))
    # replay from results
    page.locator("#res-list .play").first.click(); page.wait_for_timeout(500)
    assert page.locator("#res-list .play.on").count() == 1
    page.click("#btn-home")
    page.wait_for_selector("#home.active")
    print("home best:", page.inner_text("#best-classic"))

def survival_hard(page):
    page.click('.mode[data-mode="survival"]'); page.click('#seg-diff button[data-diff="hard"]'); page.click('#seg-n button[data-n="6"]')
    page.click("#btn-start")
    n = 0
    while True:
        page.wait_for_selector("#options .opt")
        play_and_wait(page)
        opts = page.locator("#options .opt").count()
        assert opts == 6, opts
        answer(page, correct=n < 6)
        n += 1
        if n == 2: page.screenshot(path=OUT / "7-survival.png")
        if page.inner_text("#btn-next").startswith("看結果"):
            page.click("#btn-next"); break
        page.click("#btn-next")
    page.wait_for_selector("#result.active")
    print("survival rounds:", n, "|", page.inner_text("#res-rank"), page.inner_text("#res-stats").replace("\n", " "))
    page.click("#btn-home")

def daily_seq(page):
    page.click('.mode[data-mode="daily"]')
    page.screenshot(path=OUT / "8-home-daily.png", full_page=True)
    page.click("#btn-start")
    seq = []
    for r in range(5):
        page.wait_for_selector("#options .opt")
        play_and_wait(page)
        sid, _, opts = answer(page, True)
        seq.append((sid, tuple(opts)))
        page.click("#btn-next")
    page.wait_for_selector("#result.active")
    page.screenshot(path=OUT / "9-daily-result.png", full_page=True)
    return seq

def year_range(page):
    page.click('#yr-presets button:has-text("90 年代")')
    print("range label:", page.inner_text("#yr-label"), page.inner_text("#yr-count"))
    page.screenshot(path=OUT / "12-home-range.png", full_page=True)
    # narrow range via the slider -> start must be disabled
    page.evaluate("""() => { const a = document.querySelector('#yr-a'), b = document.querySelector('#yr-b');
      a.value = 2021; a.dispatchEvent(new Event('input')); b.value = 2022; b.dispatchEvent(new Event('input')); b.dispatchEvent(new Event('change')); }""")
    print("narrow:", page.inner_text("#yr-label"), "|", page.inner_text("#yr-count"), "| start disabled:", page.is_disabled("#btn-start"))
    # dragging A past B is clamped
    page.evaluate("""() => { const a = document.querySelector('#yr-a'); a.value = 2022; a.dispatchEvent(new Event('input')); a.value = 1985; a.dispatchEvent(new Event('input')); a.dispatchEvent(new Event('change')); }""")
    print("after drag:", page.inner_text("#yr-label"), page.inner_text("#yr-count"))
    page.click('#yr-presets button:has-text("90 年代")')
    page.click("#btn-start")
    years = []
    for r in range(10):
        page.wait_for_selector("#options .opt"); play_and_wait(page)
        sid, _, _ = answer(page, True); years.append(bank[sid]["year"]); page.click("#btn-next")
    page.wait_for_selector("#result.active")
    print("90s game years:", sorted(years), "all in range:", all(1990 <= y <= 1999 for y in years))
    print("kicker:", page.inner_text("#res-kicker"))
    page.click("#btn-home")
    page.click('#yr-presets button:has-text("全部")')

run(year_range)
run(classic)
run(survival_hard)
s1 = []; s2 = []
run(lambda p: s1.extend(daily_seq(p)))
run(lambda p: s2.extend(daily_seq(p)))
print("daily deterministic:", s1 == s2, [x[0] for x in s1])
print("api calls:", calls)
print("errors:", errors or "none")
