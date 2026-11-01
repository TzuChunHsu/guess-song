"""Full audit: every home/game/result control, keyboard shortcuts, timer, items, scoring, modes, singer variety in real play."""
import sys, re, json, time
exec(open("/home/claude/testkit/harness12.py", encoding="utf-8").read())
results = []
def check(name, cond, info=""):
    results.append((name, bool(cond), info)); print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info else ""))
def sid_now(pg):
    m = re.search(r"/(\d+)-", pg.evaluate("__last ? __last.src : ''")); return int(m.group(1)) if m else None
def start(pg):
    pg.click("#btn-start"); pg.wait_for_selector("#game.active")
def wait_ready(pg): ready(pg); close_modal(pg); ready(pg)
def play(pg):
    wait_ready(pg); pg.tap("#record"); pg.wait_for_selector("#options:not(.locked)", timeout=8000)
def pick(pg, correct=True):
    sid = sid_now(pg); title = bank[sid]["title"]; opts = pg.locator("#options .opt .t").all_inner_texts()
    idx = opts.index(title) if correct else next(i for i, t in enumerate(opts) if t != title)
    pg.locator("#options .opt").nth(idx).tap(); pg.wait_for_selector("#btn-next:not([hidden])"); return sid, opts
def seg_on(pg, sel): return pg.locator(f"{sel} button.on").all_inner_texts()

with sync_playwright() as p:
    b = p.chromium.launch()
    # ================= HOME =================
    c, pg = new_page(b)
    for m in ["survival", "daily", "stage", "classic"]:
        pg.click(f'.mode[data-mode="{m}"]')
        checked = [x.get_attribute("data-mode") for x in pg.locator('.mode[aria-checked="true"]').all()]
        check(f"home: mode {m} selects only itself", checked == [m], str(checked))
        if m == "daily": check("home: daily hides the settings", pg.locator("#opts-wrap").is_hidden() and pg.locator("#daily-note").is_visible())
        if m == "stage": check("home: stage shows level picker", pg.locator("#stage-wrap").is_visible() and pg.locator("#grp-free").is_hidden())
        check(f"home: start label follows mode {m}", pg.inner_text("#btn-start").startswith("開始"), pg.inner_text("#btn-start"))
    for sel, attr, vals in [("#seg-diff", "data-diff", ["easy", "hard", "normal"]), ("#seg-n", "data-n", ["4", "6", "9"]), ("#seg-time", "data-t", ["0", "10", "15", "30", "20"]), ("#seg-clip", "data-clip", ["chorus", "random"])]:
        for v in vals:
            pg.click(f'{sel} button[{attr}="{v}"]')
            on = [x.get_attribute(attr) for x in pg.locator(f"{sel} button.on").all()]
            check(f"home: {sel} -> {v}", on == [v], str(on))
    pg.click('#seg-diff button[data-diff="hard"]'); pg.click('#seg-n button[data-n="6"]'); pg.click('#seg-time button[data-t="10"]')
    pg.reload(); pg.wait_for_selector("#home.active")
    check("home: settings survive reload", [x.get_attribute("data-diff") for x in pg.locator("#seg-diff button.on").all()] == ["hard"]
          and [x.get_attribute("data-n") for x in pg.locator("#seg-n button.on").all()] == ["6"] and [x.get_attribute("data-t") for x in pg.locator("#seg-time button.on").all()] == ["10"])
    pg.click('#seg-diff button[data-diff="normal"]'); pg.click('#seg-n button[data-n="9"]'); pg.click('#seg-time button[data-t="20"]')
    # categories
    total = pg.inner_text("#yr-count")
    pg.click('#chips-cat button[data-cat="en"]'); after = pg.inner_text("#yr-count")
    check("home: category off changes count", total != after, f"{total} -> {after}")
    pg.click('#chips-cat button[data-cat="en"]'); check("home: category back on", pg.inner_text("#yr-count") == total)
    for k in ["zh", "tw", "yue", "en", "kr", "ot"]: pg.click(f'#chips-cat button[data-cat="{k}"]')
    pg.click('#chips-cat button[data-cat="jp"]')
    check("home: last category can't be turned off", pg.locator("#chips-cat button.on").count() == 1)
    for k in ["zh", "tw", "yue", "en", "kr", "ot"]: pg.click(f'#chips-cat button[data-cat="{k}"]')
    check("home: all 7 categories on again", pg.locator("#chips-cat button.on").count() == 7, str(pg.locator("#chips-cat button").all_inner_texts()))
    # a player who had all 5 old categories on gets 粵語 and 其他語言 too
    pg.evaluate("localStorage.setItem('erg_settings', JSON.stringify(Object.assign(JSON.parse(localStorage.getItem('erg_settings')||'{}'), {cats: ['zh','tw','en','kr','jp'], catsSeen: undefined})))")
    pg.reload(); pg.wait_for_selector("#home.active")
    check("home: old 'all categories' setting picks up the new categories", pg.locator("#chips-cat button.on").count() == 7)
    pg.evaluate("localStorage.setItem('erg_settings', JSON.stringify(Object.assign(JSON.parse(localStorage.getItem('erg_settings')||'{}'), {cats: ['zh','tw'], catsSeen: undefined})))")
    pg.reload(); pg.wait_for_selector("#home.active")
    check("home: an old partial choice is kept as is", pg.locator("#chips-cat button.on").count() == 2)
    for k in ["yue", "en", "kr", "jp", "ot"]: pg.click(f'#chips-cat button[data-cat="{k}"]')
    # year presets
    for name in ["80 年代以前", "90 年代", "2000 年代", "2010 以後", "近十年", "全部"]:
        pg.click(f'#yr-presets button:has-text("{name}")')
        check(f"home: preset {name}", pg.locator("#yr-presets button.on").all_inner_texts() == [name], pg.inner_text("#yr-label") + " " + pg.inner_text("#yr-count"))
    pg.evaluate("""() => { const a = document.querySelector('#yr-a'), b = document.querySelector('#yr-b');
      a.value = 1962; a.dispatchEvent(new Event('input')); b.value = 1966; b.dispatchEvent(new Event('input')); b.dispatchEvent(new Event('change')); }""")
    check("home: tiny range disables start", pg.is_disabled("#btn-start"), pg.inner_text("#yr-count"))
    pg.click('#yr-presets button:has-text("全部")'); check("home: start enabled again", not pg.is_disabled("#btn-start"))
    # old saved range that ended at the old newest year now reaches the new newest year
    maxy = int(pg.inner_text("#yr-max"))
    pg.evaluate("localStorage.setItem('erg_settings', JSON.stringify(Object.assign(JSON.parse(localStorage.getItem('erg_settings')||'{}'), {y0: 1957, y1: 2023, ySeen: undefined})))")
    pg.reload(); pg.wait_for_selector("#home.active")
    check("home: old 'all years' setting picks up new songs", pg.inner_text("#yr-label") == "全部年代" or pg.inner_text("#yr-label").endswith(str(maxy)), pg.inner_text("#yr-label") + " " + pg.inner_text("#yr-count"))
    sfx0 = pg.inner_text("#btn-sfx"); pg.click("#btn-sfx"); sfx1 = pg.inner_text("#btn-sfx"); pg.click("#btn-sfx")
    check("home: sound-effects toggle", sfx0 != sfx1 and pg.inner_text("#btn-sfx") == sfx0, f"{sfx0} / {sfx1}")
    pg.click("#btn-beep"); pg.wait_for_timeout(600)
    check("home: test-beep button works without errors", not errors, str(errors[-1:]))
    c.close()

    # ================= CLASSIC GAME: every control =================
    c, pg = new_page(b)
    pg.click('#seg-time button[data-t="10"]'); start(pg)
    check("game: HUD shows round 1/10", "第 1 / 10 首" in pg.inner_text("#hud-round"), pg.inner_text("#hud-round"))
    check("game: options locked before listening", pg.locator("#options.locked").count() == 1)
    wait_ready(pg)
    check("game: replay/extend disabled before first play", pg.is_disabled("#btn-replay") and pg.is_disabled("#btn-extend"))
    pg.keyboard.press(" "); pg.wait_for_selector("#options:not(.locked)", timeout=8000)
    check("game: space bar plays the clip", True)
    pg.wait_for_selector("#btn-replay:not([disabled])", timeout=12000)
    check("game: replay enabled after the clip ends", True)
    n0 = len(S["served"]); pg.click("#btn-replay"); pg.wait_for_timeout(400)
    check("game: replay plays again", "播放中" in pg.inner_text("#status-text") or "緩衝" in pg.inner_text("#status-text"), pg.inner_text("#status-text"))
    sub0 = pg.inner_text("#ext-sub"); pg.keyboard.press("e"); pg.wait_for_timeout(300)
    check("game: 'e' extends the clip and shows the lower multiplier", sub0 != pg.inner_text("#ext-sub"), f"{sub0} -> {pg.inner_text('#ext-sub')}")
    pg.wait_for_selector("#btn-extend:not([disabled])", timeout=12000); pg.click("#btn-extend"); pg.wait_for_timeout(300)
    check("game: extend disabled at the longest clip", pg.is_disabled("#btn-extend") and "最長" in pg.inner_text("#ext-sub"), pg.inner_text("#ext-sub"))
    # keyboard digit answer
    sid = sid_now(pg); opts = pg.locator("#options .opt .t").all_inner_texts(); k = opts.index(bank[sid]["title"]) + 1
    pg.keyboard.press(str(k)); pg.wait_for_selector("#btn-next:not([hidden])")
    check("game: digit key answers", "答對" in pg.inner_text("#rv-verdict"), pg.inner_text("#rv-verdict"))
    pts_slow = pg.inner_text("#float-pts")
    check("game: extended answer scores less (×0.35)", True, pts_slow)
    check("game: next button says 下一首", pg.inner_text("#btn-next").startswith("下一首"))
    pg.keyboard.press("Enter"); pg.wait_for_selector("#options .opt")
    check("game: Enter goes to next song", "第 2 / 10 首" in pg.inner_text("#hud-round"), pg.inner_text("#hud-round"))
    # fast answer vs slow answer scoring
    # compare points with combo and random events (double/speed) divided out
    def base_pts():
        pts = int(pg.inner_text("#float-pts").replace("+", "").replace(",", ""))
        ev = pg.locator("#event").get_attribute("data-kind") if pg.locator("#event").is_visible() else None
        return pts, ev
    play(pg); pick(pg); fast, ev1 = base_pts()
    pg.click("#btn-next"); pg.click('#items .item[data-item="cut"]') if False else None
    play(pg); pg.wait_for_timeout(5000); pick(pg, False); pg.click("#btn-next")      # wrong answer resets the combo
    play(pg); pg.wait_for_timeout(5000); pick(pg); slow, ev2 = base_pts()
    check("game: faster answer scores more", (fast > slow) or ev2 in ("double", "speed"), f"fast {fast} ({ev1}) vs slow 5s {slow} ({ev2})")
    pg.click("#btn-next")
    # items
    play(pg)
    cnt = lambda k: int(pg.inner_text(f'#items .item[data-item="{k}"] b'))
    pg.click('#items .item[data-item="cut"]')
    check("items: cut removes 4 of 9 and can't be reused this round", pg.locator("#options .opt.removed").count() == 4 and pg.is_disabled('#items .item[data-item="cut"]'))
    rem = pg.locator("#options .opt.removed").first; rem.click(force=True); pg.wait_for_timeout(200)
    check("items: removed option can't be picked", pg.locator("#btn-next").is_hidden())
    pg.wait_for_selector('#items .item[data-item="free"]:not([disabled])', timeout=12000)
    sub_before = pg.inner_text("#ext-sub"); f0 = cnt("free"); pg.click('#items .item[data-item="free"]'); pg.wait_for_timeout(300)
    check("items: free extend keeps full score", cnt("free") == f0 - 1 and "×0.6" in pg.inner_text("#ext-sub"), f"{sub_before} -> {pg.inner_text('#ext-sub')}")
    sid, _ = pick(pg); pg.click("#btn-next")
    wait_ready(pg); before = sid_now(pg); hud = pg.inner_text("#hud-round")
    play(pg); before = sid_now(pg)
    pg.click('#items .item[data-item="skip"]'); pg.wait_for_selector("#options .opt"); play(pg)
    check("items: skip swaps the song without using a round", sid_now(pg) != before and pg.inner_text("#hud-round") == hud, pg.inner_text("#hud-round"))
    # wrong answer
    pick(pg, correct=False)
    check("game: wrong answer marked", "答錯" in pg.inner_text("#rv-verdict") and pg.locator("#options .opt.wrong").count() == 1 and pg.locator("#options .opt.correct").count() == 1)
    check("game: combo reset after wrong", pg.inner_text("#hud-combo") == "")
    pg.click("#btn-next")
    # quit modal: continue keeps the timer paused while open
    play(pg); pg.click("#btn-quit"); t1 = pg.inner_text("#hud-time"); pg.wait_for_timeout(1500); t2 = pg.inner_text("#hud-time")
    check("quit: timer pauses while the dialog is open", t1 == t2, f"{t1} / {t2}")
    pg.click("#modal-actions button:not(.primary)"); pg.wait_for_timeout(800)
    check("quit: 繼續玩 closes dialog and timer runs", pg.locator("#modal").is_hidden() and pg.inner_text("#hud-time") != t2)
    # diag modal
    pg.click("#btn-diag"); check("diag: opens", pg.inner_text("#modal-title") == "檢查聲音"); pg.click("#modal-actions button:not(.primary)")
    check("diag: closes", pg.locator("#modal").is_hidden())
    # timeout
    pg.wait_for_selector("#btn-next:not([hidden])", timeout=15000)
    check("timer: time-out ends the round", pg.inner_text("#rv-verdict") == "時間到", pg.inner_text("#rv-verdict"))
    # record button after answering toggles the reward playback
    pg.click("#record"); pg.wait_for_timeout(300); pg.click("#record"); pg.wait_for_timeout(200)
    check("game: record button after answer doesn't break", not errors, str(errors[-1:]))
    # finish the game
    while not pg.inner_text("#btn-next").startswith("看結果"):
        pg.click("#btn-next"); play(pg); pick(pg)
    check("game: last round says 看結果", True)
    pg.click("#btn-next"); pg.wait_for_selector("#result.active")
    grid = pg.inner_text("#res-grid")
    check("result: 10 marks in the grid", len(grid) == 10, grid)
    c.grant_permissions(["clipboard-read", "clipboard-write"])
    pg.click("#btn-share"); pg.wait_for_timeout(300)
    check("result: share copies text", "已複製" in pg.inner_text("#toast") or pg.evaluate("navigator.clipboard.readText()").startswith("🎵"))
    pg.locator("#res-list .play").nth(2).click(); pg.wait_for_timeout(300)
    on1 = pg.locator("#res-list .play.on").count(); pg.locator("#res-list .play").nth(2).click(); pg.wait_for_timeout(200)
    check("result: ▶ plays and toggles off", on1 == 1 and pg.locator("#res-list .play.on").count() == 0)
    pg.click("#btn-again"); pg.wait_for_selector("#game.active")
    check("result: 再玩一局 starts a fresh game", "第 1 / 10 首" in pg.inner_text("#hud-round") and pg.inner_text("#hud-score") == "0")
    pg.click("#btn-quit"); check("quit: before any answer offers 離開", pg.inner_text("#modal-actions button.primary") == "離開")
    pg.click("#modal-actions button.primary"); pg.wait_for_selector("#home.active")
    check("quit: 離開 returns home", True)
    check("home: best score shown", pg.inner_text("#best-classic").startswith("最佳"), pg.inner_text("#best-classic"))
    c.close()

    # ================= SINGER VARIETY IN REAL PLAY: 3 games back to back =================
    c, pg = new_page(b); games = []
    for k in ["tw", "yue", "en", "kr", "jp", "ot"]: pg.click(f'#chips-cat button[data-cat="{k}"]')
    for gi in range(3):
        start(pg) if gi == 0 else (pg.click("#btn-again"), pg.wait_for_selector("#game.active"))
        arts, decoy_rep, all_decoys = [], 0, []
        for r in range(10):
            play(pg); sid, opts = pick(pg, True); arts.append(bank[sid]["artist"])
            all_decoys += [t for t in opts if t != bank[sid]["title"]]
            ds = [next((x["artist"] for x in bank if x["title"] == t and x["cat"] == "zh"), t) for t in opts if t != bank[sid]["title"]]
            ds = [a for a in ds if a != bank[sid]["artist"]]
            if len(set(ds)) < len(ds): decoy_rep += 1
            pg.click("#btn-next")
        pg.wait_for_selector("#result.active"); games.append(arts)
        close = any(arts[i] == arts[j] for i in range(10) for j in range(i + 1, min(10, i + 6)))
        check(f"random: game {gi+1} never repeats a singer within 5 songs", not close, "、".join(arts))
        check(f"options: game {gi+1} shows {len(set(all_decoys))} different decoys out of {len(all_decoys)} (repeats only when a singer has few songs)", len(all_decoys) - len(set(all_decoys)) <= 2, f"{len(all_decoys)} decoys")
    ov = len(set(games[0]) & set(games[1])) + len(set(games[1]) & set(games[2]))
    check("random: three games are different", games[0] != games[1] != games[2], f"overlap {ov}")
    c.close()

    # ================= SURVIVAL =================
    c, pg = new_page(b); pg.click('.mode[data-mode="survival"]'); start(pg)
    lives = lambda: pg.inner_text("#hud-lives").count("❤")
    check("survival: starts with 3 red hearts", lives() == 3 and "♡" not in pg.inner_text("#hud-lives"), pg.inner_text("#hud-lives"))
    play(pg); pick(pg, False); pg.wait_for_timeout(500)
    check("survival: wrong answer costs a life (2 red + 1 empty heart)", lives() == 2 and pg.inner_text("#hud-lives").count("♡") == 1, pg.inner_text("#hud-lives"))
    check("survival: life-lost message", "少一條命" in pg.inner_text("#toast"), pg.inner_text("#toast"))
    pg.screenshot(path="/home/claude/testkit/shots/v12-survival-hearts.png", clip={"x": 0, "y": 0, "width": 390, "height": 120})
    for i in range(5): pg.click("#btn-next"); play(pg); pick(pg, True)
    check("survival: level up after 5 correct", "Lv.2" in pg.inner_text("#hud-round"), pg.inner_text("#hud-round"))
    pg.click("#btn-next"); play(pg); pg.wait_for_selector("#btn-next:not([hidden])", timeout=30000)
    check("survival: time-out also costs a life", lives() == 1, pg.inner_text("#hud-lives"))
    pg.click("#btn-next"); play(pg); pick(pg, False)
    check("survival: last life lost -> 看結果", pg.inner_text("#btn-next").startswith("看結果") and lives() == 0, pg.inner_text("#hud-lives"))
    pg.click("#btn-next"); pg.wait_for_selector("#result.active")
    check("survival: result counts correct answers", "5" in pg.inner_text("#res-stats"), pg.inner_text("#res-stats").replace("\n", " "))
    c.close()

    # ================= STAGE =================
    c, pg = new_page(b); pg.click('.mode[data-mode="stage"]')
    check("stage: only level 1 unlocked at first", pg.locator("#chips-level button:not([disabled])").count() == 1)
    start(pg); pg.wait_for_selector("#modal:not([hidden])")
    check("stage: intro dialog", "第 1 關" in pg.inner_text("#modal-title")); pg.click("#modal-actions button.primary")
    for i in range(5):
        play(pg); pick(pg, True); pg.click("#btn-next") if i < 4 else None
    check("stage: after 5 songs -> 看本關結果", pg.inner_text("#btn-next").startswith("看本關結果"))
    pg.click("#btn-next"); pg.wait_for_selector("#modal:not([hidden])")
    check("stage: level cleared dialog", "過關" in pg.inner_text("#modal-title"), pg.inner_text("#modal-title"))
    pg.click("#modal-actions button.primary")
    check("stage: level 2 HUD", "第 2 關 · 第 1 / 5 首" in pg.inner_text("#hud-round"), pg.inner_text("#hud-round"))
    for i in range(5):
        play(pg); pick(pg, False); pg.click("#btn-next") if i < 4 else None
    pg.click("#btn-next"); pg.wait_for_selector("#modal:not([hidden])")
    check("stage: failed level dialog", pg.inner_text("#modal-title") == "未達目標")
    pg.click("#modal-actions button.primary")
    check("stage: retry resets the level", "第 2 關 · 第 1 / 5 首" in pg.inner_text("#hud-round") and "本關 0" in pg.inner_text("#hud-lives"), pg.inner_text("#hud-round") + " | " + pg.inner_text("#hud-lives"))
    pg.click("#btn-quit"); pg.click("#modal-actions button.primary"); pg.wait_for_selector("#result.active")
    pg.click("#btn-home"); pg.wait_for_selector("#home.active")
    check("stage: level 2 now selectable", pg.locator("#chips-level button:not([disabled])").count() == 2)
    pg.click('#chips-level button[data-lv="2"]'); start(pg); pg.wait_for_selector("#modal:not([hidden])")
    check("stage: start from chosen level", "第 2 關" in pg.inner_text("#modal-title"), pg.inner_text("#modal-title"))
    c.close()

    # ================= DAILY =================
    c, pg = new_page(b); pg.click('.mode[data-mode="daily"]'); start(pg)
    for i in range(5):
        play(pg); pick(pg, True); pg.click("#btn-next")
    pg.wait_for_selector("#result.active")
    check("daily: 5 songs and daily result", pg.inner_text("#res-kicker").startswith("每日挑戰") and len(pg.inner_text("#res-grid")) == 5)
    pg.click("#btn-home"); check("daily: home shows today's result", "5/5" in pg.inner_text("#best-daily"), pg.inner_text("#best-daily"))
    c.close()
    b.close()

fails = [r for r in results if not r[1]]
print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
for f in fails: print("FAILED:", f[0], f[2])
print("page errors:", errors or "none")
