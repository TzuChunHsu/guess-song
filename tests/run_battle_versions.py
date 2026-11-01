"""Online battle between different versions of the song list.

    python3 tests/run_battle_versions.py index.html src/bank.txt
A second copy of the game is built from a song list with an extra song at the very top, so every
song id is shifted by one. The host plays the real build, the guest the shifted one: the guest must
still join, see the right titles and score; a host takeover by the guest must not repeat songs.
A room made by an old build (v1, other song list) must be refused with a clear message.
"""
import os, pathlib, re, shutil, subprocess, sys, tempfile, time
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_battle.py"), encoding="utf-8").read().split("with sync_playwright() as p:")[0])
SRC = KIT.parent / "src"
alt_bank = pathlib.Path(tempfile.mkdtemp()) / "bank.txt"
lines = open(SRC / "bank.txt", encoding="utf-8").read().split("\n")
i = lines.index("@zh") + 1
lines.insert(i, "測試用的歌|測試歌手|2000")                       # shifts every id by one
alt_bank.write_text("\n".join(lines), encoding="utf-8")
singers = (SRC / "singers.txt").read_text(encoding="utf-8")
tmp_src = pathlib.Path(tempfile.mkdtemp())
for f in ("build.py", "template.html", "battle.js", "chorus.js"): shutil.copy(SRC / f, tmp_src / f)
(tmp_src / "singers.txt").write_text(singers + "測試歌手|m\n", encoding="utf-8")
subprocess.run([sys.executable, str(tmp_src / "build.py"), str(tmp_src / "template.html"), str(alt_bank), str(site / "alt.html")], check=True, capture_output=True)
ALT = f"{BASE}/alt.html?fb={BASE}&debug"

with sync_playwright() as p:
    b = p.chromium.launch(args=["--autoplay-policy=user-gesture-required"])
    ca, A = player(b)
    A.click('.mode[data-mode="battle"]'); A.fill("#mp-name", "新版房主"); A.fill("#mp-room", "版本測試")
    A.click("#btn-start"); A.wait_for_selector("#lb-players .pl", timeout=15000)
    code = A.inner_text("#lb-code").strip()
    cb, B = player(b, ALT)
    check("the two pages really have different song lists", A.evaluate("__erg.BANK[5].title") != B.evaluate("__erg.BANK[5].title"))
    B.click('.mode[data-mode="battle"]'); B.fill("#mp-name", "舊版朋友"); B.fill("#mp-code", "版本測試"); B.click("#mp-join")
    B.wait_for_selector("#lb-players .pl", timeout=15000)
    check("guest on another version can join", B.inner_text("#lb-code").strip() == code and B.locator("#modal").is_hidden())
    A.click('#lb-rounds button[data-r="5"]'); A.click("#lb-start")
    for i in range(2):
        play_round([A, B], ["right", "right"], i)
        ta = A.locator("#options .opt .t").all_inner_texts(); tb = B.locator("#options .opt .t").all_inner_texts()
        check(f"song {i + 1}: both devices show the same choices", ta == tb, (ta[:3], tb[:3]))
        check(f"song {i + 1}: both devices reveal the same title", A.inner_text("#rv-title") == B.inner_text("#rv-title"), (A.inner_text("#rv-title"), B.inner_text("#rv-title")))
    sc = scores(A)
    check("the guest's right answers count", sc["舊版朋友"]["c"] == 2 and sc["舊版朋友"]["s"] > 0, sc)
    ca.close()                                                     # host leaves: the other-version guest takes over
    B.wait_for_function("__erg.mp.isHost", timeout=45000)
    for i in (2, 3, 4): play_round([B], ["right"], i)
    B.wait_for_selector("#result.active", timeout=40000)
    titles = B.locator("#res-list .song .info b").all_inner_texts()
    check("game finishes after the other-version takeover", len(titles) == 5, titles)
    check("no song asked twice", len(set(titles)) == 5, titles)
    # a room opened by an old build
    FF.set_at(["rooms", "XLDV"], {"v": 1, "bv": "oldbuild", "host": "uold", "ts": int(time.time() * 1000), "st": "lobby", "cfg": {"cats": ["zh"], "r": 5}, "p": {"uold": {"n": "舊房主", "hb": int(time.time() * 1000), "j": 1, "s": 0}}})
    cc, C = player(b)
    C.click('.mode[data-mode="battle"]'); C.fill("#mp-name", "新朋友"); C.fill("#mp-code", "XLDV"); C.click("#mp-join")
    C.wait_for_selector("#modal:not([hidden])", timeout=10000)
    check("old-version room: clear message for the host", "房主" in C.inner_text("#modal-title") and C.locator("#lobby").is_hidden(), C.inner_text("#modal-title"))
    check("version shown on the home screen", re.search(r"版本 \d{4}\.\d\d\.\d\d", C.inner_text("#ver")) is not None, C.inner_text("#ver"))
    check("page errors: none", not errors, errors[:3])
    b.close()
print(f"\n{sum(results)}/{len(results)} checks passed")
