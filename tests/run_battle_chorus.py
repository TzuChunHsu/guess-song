"""Online battle in chorus mode: the host finds the chorus, guests play from the same spot.

    python3 tests/run_battle_chorus.py index.html src/bank.txt
"""
import os, pathlib, re, shutil, sys, tempfile, time
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_battle.py"), encoding="utf-8").read().split("with sync_playwright() as p:")[0])
S["chorus_layout"] = "first_flat"     # only the 2nd album's preview has a chorus: the host must hand out that file
if "--no-stream" in sys.argv: FF.NO_STREAM["on"] = True   # same game with event streams blocked: polling takes over
with sync_playwright() as p:
    b = p.chromium.launch(args=["--autoplay-policy=user-gesture-required"])
    ca, A = player(b)
    A.click('.mode[data-mode="battle"]'); A.click('#seg-clip button[data-clip="chorus"]')
    A.fill("#mp-name", "房主"); A.click("#btn-start"); A.wait_for_selector("#lb-players .pl", timeout=15000)
    code = A.inner_text("#lb-code").strip()
    check("room says chorus only", "只出副歌" in A.inner_text("#lb-cfg"))
    cb, B = player(b, URL + f"&room={code}")
    B.wait_for_timeout(500); B.fill("#mp-name", "客人"); B.click("#mp-join"); B.wait_for_selector("#lb-players .pl", timeout=15000)
    A.click('#lb-rounds button[data-r="5"]'); A.click("#lb-start")
    for i in range(5):
        play_round([A, B], ["right", "right"], i)
        q = A.evaluate(f"__erg.mp.room.q['n{i}']")
        if i == 0:
            check("question carries the chorus start", q.get("ch") == 1 and q.get("st", 0) > 0, (q.get("ch"), q.get("st")))
            sb = B.evaluate("__erg.mp.aud[0] ? __erg.mp.aud[0].audio.currentTime : -1")
            check("guest plays from the chorus", sb >= q["st"] - 0.5, (sb, q["st"]))
        gu = B.evaluate(f"__erg.mp.aud[{i}] ? __erg.mp.aud[{i}].url : ''")
        check(f"song {i + 1}: everyone gets the file the chorus was found in", q["u"].endswith("-a2.m4a") and gu == q["u"], (q["u"][-12:], gu[-12:]))
    for pg in (A, B): pg.wait_for_selector("#result.active", timeout=30000)
    check("chorus battle finishes", A.locator("#res-list .song").count() == 5)
    if FF.NO_STREAM["on"]: check("both devices fell back to polling", all(pg.evaluate("!!(__erg.mp.sub && __erg.mp.sub.polling())") for pg in (A, B)))
    check("page errors: none", not errors, errors[:3])
    b.close()
print(f"\n{sum(results)}/{len(results)} checks passed")
