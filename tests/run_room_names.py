"""Room names: 4-letter names like "test" become the room code; others are looked up by name.

    python3 tests/run_room_names.py index.html src/bank.txt
"""
import os, pathlib, re, shutil, sys, tempfile, time
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_battle.py"), encoding="utf-8").read().split("with sync_playwright() as p:")[0])
def host(b, name):
    c, pg = player(b); pg.click('.mode[data-mode="battle"]'); pg.fill("#mp-name", "房主"); pg.fill("#mp-room", name)
    pg.click("#btn-start"); pg.wait_for_selector("#lb-players .pl", timeout=15000); return c, pg
def join(b, text):
    c, pg = player(b); pg.click('.mode[data-mode="battle"]'); pg.fill("#mp-name", "朋友"); pg.fill("#mp-code", text); pg.click("#mp-join")
    try: pg.wait_for_selector("#lb-players .pl", timeout=8000); return c, pg.inner_text("#lb-code").strip()
    except Exception: return c, None
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, joins in [("test", ["test", "TEST", " Test "]), ("love", ["love", "LOVE"]), ("阿明的歌房", ["阿明的歌房", "阿明的歌房 "])]:
        ch, H = host(b, name)
        code = H.inner_text("#lb-code").strip()
        check(f"room named {name!r} opens", bool(re.fullmatch(r"[A-Z2-9]{4}", code)), code)
        check(f"lobby shows the name {name!r}", name in H.inner_text("#lb-name"))
        if name == "test": check("test becomes code TEST", code == "TEST")
        for j in joins:
            cj, got = join(b, j)
            check(f"join {name!r} by typing {j!r}", got == code, got); cj.close()
        cj, got = join(b, code)
        check(f"join {name!r} by its code", got == code); cj.close()
        c2, H2 = player(b); H2.click('.mode[data-mode="battle"]'); H2.fill("#mp-name", "別人"); H2.fill("#mp-room", name); H2.click("#btn-start"); H2.wait_for_timeout(1500)
        check(f"second room named {name!r} is refused while in use", H2.locator("#lobby").is_hidden()); c2.close()
        ch.close()
    check("page errors: none", not errors, errors[:3])
    b.close()
print(f"\n{sum(results)}/{len(results)} checks passed")
