import json, re, sys, urllib.parse, pathlib
from playwright.sync_api import sync_playwright
import opencc
t2s = opencc.OpenCC("t2s")
GAME = pathlib.Path(sys.argv[1]).resolve(); KIT = pathlib.Path(__file__).parent
bank = []
for l in open(sys.argv[2], encoding="utf-8").read().splitlines():
    if l and not l.startswith("#") and not l.startswith("@"):
        t, a, y = l.split("|")
        bank.append({"id": len(bank), "title": t.split("/")[0], "alts": t.split("/"), "artist": a.split("、")[0]})

# Only these exist in the mock store; all of them are returned in SIMPLIFIED Chinese, some with variant chars.
AVAILABLE = {i for i, s in enumerate(bank) if s["title"] in ("不能說的祕密", "癡心絕對", "姊妹", "舞孃", "戀曲1990", "你，好不好？", "Super Star", "愛", "Last Dance", "年少有為", "說好不哭", "雙截棍")}
RENAME = {"不能說的祕密": "不能说的秘密", "癡心絕對": "痴心绝对", "姊妹": "姐妹 (Live)", "舞孃": "舞娘", "你，好不好？": "你,好不好?", "Super Star": "SUPER STAR", "愛": "爱 (Remastered)", "雙截棍": "双节棍"}
calls = {"itunes": 0, "deezer": 0}

def find(term):
    tn = term.replace(" ", "")
    best = None
    for s in bank:
        for alt in s["alts"]:
            for v in (alt, t2s.convert(alt)):
                if v.replace(" ", "") in tn and (best is None or len(v) > len(best[1])): best = (s, v)
    return best[0] if best else None

def itunes(route, fail=False):
    calls["itunes"] += 1
    if fail: return route.abort()
    q = urllib.parse.parse_qs(urllib.parse.urlparse(route.request.url).query)
    s = find(q["term"][0]); res = []
    if s and s["id"] in AVAILABLE:
        res.append({"trackName": RENAME.get(s["title"], t2s.convert(s["title"])), "artistName": t2s.convert(s["artist"]) + " Extra",
                    "previewUrl": f"https://audio.mock/{s['id']}.m4a", "artworkUrl100": "", "trackViewUrl": ""})
    route.fulfill(status=200, content_type="text/javascript", body=f"{q['callback'][0]}({json.dumps({'results': res}, ensure_ascii=False)});")

def deezer(route):
    calls["deezer"] += 1
    q = urllib.parse.parse_qs(urllib.parse.urlparse(route.request.url).query)
    route.fulfill(status=200, content_type="text/javascript", body=f"{q['callback'][0]}({{\"data\":[]}});")

def ctx_for(b, fail=False):
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    ctx.route("https://itunes.apple.com/**", lambda r: itunes(r, fail))
    ctx.route("https://api.deezer.com/**", deezer)
    ctx.route("https://audio.mock/**", lambda r: r.fulfill(status=200, content_type="audio/mpeg", body=(KIT / "tone.mp3").read_bytes()))
    ctx.route(re.compile(r"https://fonts\..*"), lambda r: r.abort())
    ctx.add_init_script("window.__plays=[];const op=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){window.__plays.push(this.src);return op.call(this)};")
    return ctx

errors = []
with sync_playwright() as p:
    b = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    # 1) layout width on mobile
    page = ctx_for(b).new_page(); page.goto(GAME.as_uri())
    print("scrollWidth", page.evaluate("document.documentElement.scrollWidth"), "viewport", page.evaluate("innerWidth"))
    # 2) sparse store: only simplified / variant-char tracks exist
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.click("#btn-start")
    got = []
    for r in range(10):
        page.wait_for_selector("#options .opt", timeout=60000)
        page.click("#record"); page.wait_for_selector("#options:not(.locked)", timeout=8000)
        sid = int(re.search(r"/(\d+)\.m4a", page.evaluate("__plays[__plays.length-1]")).group(1))
        got.append(bank[sid]["title"])
        page.locator("#options .opt").first.click(); page.wait_for_selector("#btn-next:not([hidden])")
        page.click("#btn-next")
    page.wait_for_selector("#result.active")
    print("played:", got)
    print("calls:", calls)
    # second game should reuse the cache (misses cached too)
    before = dict(calls); page.click("#btn-again"); page.wait_for_selector("#options .opt", timeout=60000)
    print("extra calls for 2nd game start:", calls["itunes"] - before["itunes"], calls["deezer"] - before["deezer"])
    # 3) network down
    page2 = ctx_for(b, fail=True).new_page(); page2.goto(GAME.as_uri()); page2.click("#btn-start")
    page2.wait_for_selector("#modal:not([hidden])", timeout=60000)
    print("net modal:", page2.inner_text("#modal-title"))
    page2.screenshot(path=KIT / "shots" / "10-neterror.png")
    b.close()
print("errors:", errors or "none")
