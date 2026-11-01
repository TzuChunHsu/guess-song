import json, re, sys, time, urllib.parse, pathlib
sys.path.insert(0, "/home/claude/songgame")
from build import ALIASES
from playwright.sync_api import sync_playwright
GAME = pathlib.Path(sys.argv[1]).resolve(); KIT = pathlib.Path(__file__).parent
tone = (KIT / "tone.mp3").read_bytes(); chorus = (KIT / "chorus.mp3").read_bytes()
bank = [l.split('|') for l in open(sys.argv[2], encoding='utf-8').read().splitlines() if l and not l.startswith('#') and not l.startswith('@')]
S = {"apple": "ok", "deezer": "ok", "bad_audio": set(), "calls": {"it": 0, "dz": 0}}
def find(term):
    hit = None
    for i, (t, a, y) in enumerate(bank):
        if t.split('/')[0] in term and (hit is None or len(t) > len(bank[hit][0])): hit = i
    return hit
def apple(r):
    S["calls"]["it"] += 1
    if S["apple"] == "down": return r.fulfill(status=403, body="Forbidden")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(r.request.url).query); h = find(q['term'][0])
    res = [] if h is None else [{"trackName": bank[h][0].split('/')[0], "artistName": bank[h][1].split('、')[0], "previewUrl": f"https://audio.mock/{h}.m4a", "artworkUrl100": "", "trackViewUrl": ""}]
    r.fulfill(status=200, content_type="text/javascript", body=f"{q['callback'][0]}({json.dumps({'results': res}, ensure_ascii=False)});")
def deezer(r):
    S["calls"]["dz"] += 1
    if S["deezer"] == "down": return r.abort()
    q = urllib.parse.parse_qs(urllib.parse.urlparse(r.request.url).query); h = find(q['q'][0])
    data = []
    if h is not None:
        a0 = bank[h][1].split('、')[0]; name = (ALIASES.get(a0) or [a0])[0]   # Deezer often lists English artist names
        data = [{"title": bank[h][0].split('/')[0], "artist": {"name": name}, "album": {"title": "Album", "cover_small": "", "cover_big": ""}, "preview": f"https://dz.mock/{h}.mp3?hdnea=x", "link": "https://www.deezer.com/track/1"}]
    r.fulfill(status=200, content_type="text/javascript", body=f"{q['callback'][0]}({json.dumps({'data': data}, ensure_ascii=False)});")
def media(r):
    m = re.search(r"/(\d+)\.(m4a|mp3)", r.request.url); sid = int(m.group(1))
    if sid in S["bad_audio"]: return r.fulfill(status=404, body="")
    r.fulfill(status=200, content_type="audio/mpeg", body=tone, headers={"Accept-Ranges": "bytes", "Access-Control-Allow-Origin": "*"})
errors = []
def new_page(b):
    c = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, is_mobile=True, has_touch=True)
    c.route("https://itunes.apple.com/**", apple); c.route("https://api.deezer.com/**", deezer)
    c.route(re.compile(r"https://(audio|dz)\.mock/.*"), media)
    c.route(re.compile(r"https://fonts\..*"), lambda r: r.abort())
    c.add_init_script("const op=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){if(!this.src.startsWith('blob:')||this.duration>1)window.__last=this;return op.call(this)};")
    pg = c.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.goto(GAME.as_uri()); return c, pg
def ready(pg, timeout=60000):
    pg.wait_for_function("document.querySelector('#status-text').textContent.startsWith('點唱片') || !document.querySelector('#modal').hidden", timeout=timeout)
def play_round(pg):
    ready(pg)
    pg.tap("#record"); pg.wait_for_selector("#options:not(.locked)", timeout=8000); pg.wait_for_timeout(300)
    src = pg.evaluate("__last.src"); playing = not pg.evaluate("__last.paused")
    m = re.search(r"/(\d+)\.(m4a|mp3)", src); sid = int(m.group(1)) if m else None
    pg.locator("#options .opt").first.tap(); pg.wait_for_selector("#btn-next:not([hidden])"); pg.tap("#btn-next")
    return sid, src, playing
with sync_playwright() as p:
    b = p.chromium.launch()
    # 1) Apple refuses everything, Deezer works -> game starts right away and keeps going
    S.update(apple="down", deezer="ok"); S["calls"] = {"it": 0, "dz": 0}
    c, pg = new_page(b); t0 = time.time(); pg.click("#btn-start"); ready(pg); first = time.time() - t0
    pg.tap("#btn-diag"); pg.wait_for_selector("#modal:not([hidden])")
    diag = [l for l in pg.inner_text("#modal-text").split("\n") if l.startswith(("這首來源", "查歌"))]
    pg.click("#modal-actions button:not(.primary)")
    rounds = [play_round(pg) for _ in range(6)]
    print(f"[Apple down] first question after {first:.1f}s; played {len(rounds)} rounds, all playing={all(r[2] for r in rounds)}, sources={set(r[1].split('/')[2] for r in rounds)}")
    print("   Apple calls:", S["calls"]["it"], "(circuit breaker should keep this tiny) | Deezer calls:", S["calls"]["dz"])
    print("  ", diag)
    pg.screenshot(path=KIT / "shots" / "23-apple-down.png"); c.close()
    # 2) Some previews are broken -> they never become questions, game moves on quickly
    S.update(apple="ok", deezer="ok"); S["bad_audio"] = set(range(0, len(bank), 3))   # every 3rd song's audio 404s
    c, pg = new_page(b); pg.click("#btn-start")
    t0 = time.time(); rounds = [play_round(pg) for _ in range(8)]
    bad_shown = [r[0] for r in rounds if r[0] in S["bad_audio"]]
    print(f"[broken previews] 8 rounds in {time.time()-t0:.1f}s, broken songs shown as questions: {bad_shown}, all playing={all(r[2] for r in rounds)}")
    c.close(); S["bad_audio"] = set()
    # 3) Both sources down -> clear message, quickly
    S.update(apple="down", deezer="down")
    c, pg = new_page(b); t0 = time.time(); pg.click("#btn-start"); pg.wait_for_selector("#modal:not([hidden])", timeout=90000)
    print(f"[both down] dialog after {time.time()-t0:.1f}s:", pg.inner_text("#modal-title"), "|", pg.inner_text("#modal-text"))
    c.close()
    # 4) Apple recovers after being down: retry button works
    S.update(apple="ok", deezer="down")
    b.close()
print("errors:", errors or "none")
