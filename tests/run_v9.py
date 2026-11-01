import json, re, sys, time, urllib.parse, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src")); from build import ALIASES
from playwright.sync_api import sync_playwright
GAME = pathlib.Path(sys.argv[1]).resolve()
tone = (pathlib.Path(__file__).resolve().parent / "tone.mp3").read_bytes(); chorus = (pathlib.Path(__file__).resolve().parent / "chorus.mp3").read_bytes()
bank, cat = [], "zh"
for l in open(sys.argv[2], encoding="utf-8").read().splitlines():
    if not l or l.startswith("#"): continue
    if l.startswith("@"): cat = l[1:]; continue
    t, a, y = l.split("|"); alts = t.split("/")
    bank.append({"id": len(bank), "title": alts[0], "alts": alts, "artist": a.split("、")[0], "year": int(y), "cat": cat})
by_title = {}
for b in bank:
    for t in b["alts"]: by_title.setdefault(t.lower(), b)
S = {"chorus_layout": "first_flat", "served": [], "calls": 0}
def find(term):
    tl = term.lower(); best = None
    for b in bank:
        for t in b["alts"]:
            if t.lower() in tl and (best is None or len(t) > len(best[1])): best = (b, t)
    return best[0] if best else None
def apple_name(b):
    # what Apple's Taiwan store would show
    if b["cat"] == "kr":
        kor = next((t for t in b["alts"] if re.search(r"[가-힯]", t)), None)
        return kor or b["title"], (ALIASES.get(b["artist"]) or [b["artist"]])[0] if b["artist"] == "少女時代" else b["artist"]
    if b["title"] == "Uptown Funk": return "Uptown Funk (feat. Bruno Mars)", "Mark Ronson"
    if b["title"] == "See You Again": return "See You Again (feat. Charlie Puth)", "Wiz Khalifa"
    return b["title"], b["artist"]
def apple(r):
    S["calls"] += 1
    q = urllib.parse.parse_qs(urllib.parse.urlparse(r.request.url).query); b = find(q["term"][0]); res = []
    if b:
        name, artist = apple_name(b)
        mk = lambda n, al, tag: {"trackName": n, "artistName": artist, "collectionName": al, "previewUrl": f"https://audio.mock/{b['id']}-{tag}.m4a", "artworkUrl100": "", "trackViewUrl": ""}
        if b["cat"] == "kr": res.append(mk(name + " (Japanese Ver.)", "Japan Album", "jpver"))
        res += [mk(name, "Original Album", "a1"), mk(name, "Greatest Hits", "a2")]
    r.fulfill(status=200, content_type="text/javascript", body=f"{q['callback'][0]}({json.dumps({'results': res}, ensure_ascii=False)});")
def deezer(r):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(r.request.url).query); b = find(q["q"][0]); data = []
    if b: data = [{"title": b["title"], "artist": {"name": (ALIASES.get(b["artist"]) or [b["artist"]])[0]}, "album": {"title": "x", "cover_small": "", "cover_big": ""}, "preview": f"https://dz.mock/{b['id']}-dz.mp3", "link": ""}]
    r.fulfill(status=200, content_type="text/javascript", body=f"{q['callback'][0]}({json.dumps({'data': data}, ensure_ascii=False)});")
def media(r):
    m = re.search(r"/(\d+)-(\w+)\.(m4a|mp3)", r.request.url); tag = m.group(2)
    S["served"].append((int(m.group(1)), tag, r.request.resource_type))
    body = tone
    lay = S["chorus_layout"]
    if lay == "first_flat" and tag == "a2": body = chorus      # only the 2nd album's preview contains a chorus
    if lay == "deezer_only" and tag == "dz": body = chorus     # only Deezer's preview contains a chorus
    if lay == "all": body = chorus
    r.fulfill(status=200, content_type="audio/mpeg", body=body, headers={"Accept-Ranges": "bytes", "Access-Control-Allow-Origin": "*"})
errors = []
def new_page(b, w=390, h=844):
    c = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=True, has_touch=True)
    c.route("https://itunes.apple.com/**", apple); c.route("https://api.deezer.com/**", deezer)
    c.route(re.compile(r"https://(audio|dz)\.mock/.*"), media); c.route(re.compile(r"https://fonts\..*"), lambda r: r.abort())
    c.add_init_script("const op=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){if(this.src.indexOf('mock')>0||this.src.startsWith('blob:')&&this.duration>1)window.__last=this;return op.call(this)};")
    pg = c.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.goto(GAME.as_uri()); return c, pg
def ready(pg, t=90000): pg.wait_for_function("document.querySelector('#status-text').textContent.startsWith('點唱片') || !document.querySelector('#modal').hidden", timeout=t)
def close_modal(pg):
    if not pg.locator("#modal").is_hidden(): pg.click("#modal-actions button.primary")
def answer_song(pg, correct=True):
    ready(pg); close_modal(pg); ready(pg)
    pg.tap("#record"); pg.wait_for_selector("#options:not(.locked)", timeout=8000)
    opts = pg.locator("#options .opt .t").all_inner_texts()
    # identify the answer from the reveal after answering: pick by title of played song via the mock log
    sid = S["served"][-1][0] if S["served"] else None
    played = pg.evaluate("__last ? __last.src : ''"); m = re.search(r"/(\d+)-", played)
    if m: sid = int(m.group(1))
    title = bank[sid]["title"] if sid is not None else None
    idx = opts.index(title) if correct and title in opts else next((i for i, t in enumerate(opts) if t != title), 0)
    pg.locator("#options .opt").nth(idx).tap(); pg.wait_for_selector("#btn-next:not([hidden])")
    return sid, opts
with sync_playwright() as p:
    b = p.chromium.launch()
    # ---------- 1. categories ----------
    c, pg = new_page(b)
    print("category chips:", pg.locator("#chips-cat button").all_inner_texts())
    for k in ["zh", "tw", "yue", "en", "jp", "ot"]: pg.click(f'#chips-cat button[data-cat="{k}"]')     # leave only K-pop
    print("only 韓語 ->", pg.inner_text("#yr-count"), "| selected:", pg.locator("#chips-cat button.on").all_inner_texts())
    pg.click('#chips-cat button[data-cat="kr"]'); print("deselecting the last one is refused:", pg.locator("#chips-cat button.on").count() == 1)
    pg.click('#chips-cat button[data-cat="jp"]'); pg.click('#chips-cat button[data-cat="en"]'); pg.click('#chips-cat button[data-cat="ot"]'); pg.click('#chips-cat button[data-cat="yue"]')
    pg.screenshot(path="shots/30-home-cats.png", full_page=True)
    pg.click("#btn-start")
    seen = []
    for i in range(9):
        sid, opts = answer_song(pg, True)
        cats = {by_title[o.lower()]["cat"] for o in opts if o.lower() in by_title}
        seen.append((bank[sid]["cat"], bank[sid]["title"], pg.inner_text("#rv-verdict").startswith("答對"), cats == {bank[sid]["cat"]}))
        if i == 1: pg.screenshot(path="shots/31-kpop-question.png")
        pg.tap("#btn-next")
    print("songs (cat, title, answered right, options all same category):"); [print("   ", s) for s in seen]
    tags = {t for _, t, rt in S["served"] if rt == "media"}
    print("versions served:", tags, "| Japanese-version preview used:", "jpver" in tags)
    c.close()
    # ---------- 2. stage mode ----------
    c, pg = new_page(b)
    pg.click('.mode[data-mode="stage"]')
    print("stage levels on home:", pg.locator("#chips-level button").all_inner_texts()[:3], "| note:", pg.inner_text("#stage-note")[:40])
    pg.screenshot(path="shots/32-home-stage.png", full_page=True)
    pg.click("#btn-start"); pg.wait_for_selector("#modal:not([hidden])")
    print("intro:", pg.inner_text("#modal-title"), "|", pg.inner_text("#modal-text").split("\n")[0])
    pg.click("#modal-actions button.primary")
    for i in range(5):
        answer_song(pg, True)
        if i < 4: pg.tap("#btn-next")
    print("hud after level 1:", pg.inner_text("#hud-round"), "|", pg.inner_text("#hud-lives"), "| next:", pg.inner_text("#btn-next"))
    pg.tap("#btn-next"); pg.wait_for_selector("#modal:not([hidden])")
    print("level end:", pg.inner_text("#modal-title")); pg.screenshot(path="shots/33-stage-clear.png")
    pg.click("#modal-actions button.primary")      # go to level 2
    for i in range(5):
        answer_song(pg, False)
        if i < 4: pg.tap("#btn-next")
    pg.tap("#btn-next"); pg.wait_for_selector("#modal:not([hidden])")
    print("level 2 end:", pg.inner_text("#modal-title"), "|", pg.inner_text("#modal-text"))
    pg.click("#modal-actions button.primary")      # retry level 2
    ready(pg); print("after retry hud:", pg.inner_text("#hud-round"), "|", pg.inner_text("#hud-lives"))
    pg.tap("#btn-quit"); pg.click("#modal-actions button.primary"); pg.wait_for_selector("#result.active")
    print("result:", pg.inner_text("#res-kicker"), "|", pg.inner_text("#res-rank"), "|", pg.inner_text("#res-stats").replace("\n", " "))
    pg.click("#btn-home"); print("home after:", pg.inner_text("#best-stage"), "| unlocked chips:", pg.locator("#chips-level button:not([disabled])").count())
    c.close()
    # ---------- 3. chorus mode tries other previews ----------
    for layout in ("first_flat", "deezer_only"):
        S["chorus_layout"] = layout; S["served"] = []
        c, pg = new_page(b); pg.click('#seg-clip button[data-clip="chorus"]'); pg.click("#btn-start")
        ready(pg); pg.tap("#btn-diag"); pg.wait_for_selector("#modal:not([hidden])")
        line = [l for l in pg.inner_text("#modal-text").split("\n") if l.startswith("副歌偵測")][0]
        pg.click("#modal-actions button:not(.primary)")
        pg.tap("#record"); pg.wait_for_selector("#options:not(.locked)", timeout=8000); pg.wait_for_timeout(400)
        print(f"[chorus, {layout}] {line} | playing at {pg.evaluate('__last.currentTime'):.1f}s | analysed:", sorted({t for _, t, rt in S['served'] if rt == 'fetch'}))
        c.close()
    b.close()
print("errors:", errors or "none")
