"""Survival/stage with only a few playable songs: the game must keep going (repeats allowed) and never freeze."""
import sys, re, time
exec(open(__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "harness12.py"), encoding="utf-8").read())
jp = [x for x in bank if x["cat"] == "ot"]; OK = {x["id"] for x in jp[:12]}
def apple2(r):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(r.request.url).query); b_ = find(q["term"][0]); res = []
    if b_ and b_["id"] in OK:
        res = [{"trackName": b_["title"], "artistName": b_["artist"], "collectionName": "x", "previewUrl": f"https://audio.mock/{b_['id']}-a1.m4a", "artworkUrl100": "", "trackViewUrl": ""}]
    r.fulfill(status=200, content_type="text/javascript", body=f"{q['callback'][0]}({json.dumps({'results': res}, ensure_ascii=False)});")
def deezer2(r):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(r.request.url).query)
    r.fulfill(status=200, content_type="text/javascript", body=f"{q['callback'][0]}({{\"data\":[]}});")
with sync_playwright() as p:
    b = p.chromium.launch()
    c = b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    c.route("https://itunes.apple.com/**", apple2); c.route("https://api.deezer.com/**", deezer2)
    c.route(re.compile(r"https://(audio|dz)\.mock/.*"), media); c.route(re.compile(r"https://fonts\..*"), lambda r: r.abort())
    c.add_init_script("const op=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){if(this.src.indexOf('mock')>0)window.__last=this;return op.call(this)};")
    pg = c.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.goto(GAME.as_uri())
    for k in ["zh", "tw", "yue", "en", "kr", "jp"]: pg.click(f'#chips-cat button[data-cat="{k}"]')
    pg.click('.mode[data-mode="survival"]'); pg.click("#btn-start"); pg.wait_for_selector("#game.active")
    seen = []; t0 = time.time()
    for i in range(18):
        ready(pg); close_modal(pg); ready(pg); pg.tap("#record"); pg.wait_for_selector("#options:not(.locked)", timeout=8000)
        sid = int(re.search(r"/(\d+)-", pg.evaluate("__last.src")).group(1)); seen.append(sid)
        opts = pg.locator("#options .opt .t").all_inner_texts(); pg.locator("#options .opt").nth(opts.index(bank[sid]["title"])).tap()
        pg.wait_for_selector("#btn-next:not([hidden])"); pg.click("#btn-next")
    print(f"survival with 12 playable of 40 (其他語言): 18 rounds in {time.time()-t0:.1f}s, distinct songs {len(set(seen))}, all playable: {set(seen) <= OK}")
    print("first 12 distinct before any repeat:", len(set(seen[:12])) == 12, seen, sorted(OK)); print(pg.evaluate("JSON.stringify(localStorage)")[:600])
    b.close()
print("errors:", errors or "none")
