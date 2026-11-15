"""Decoy options: same singer, look-alike titles and same-gender singers by difficulty.

    python3 tests/run_options.py index.html src/bank.txt
"""
import json, pathlib, sys
from playwright.sync_api import sync_playwright
GAME = pathlib.Path(sys.argv[1]).resolve()
results = []
def check(name, ok, info=""):
    results.append(ok); print(("PASS " if ok else "FAIL ") + name + (f"  [{info}]" if info else ""))
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(); pg.goto(GAME.as_uri() + "?debug")
    stats = pg.evaluate("""() => {
      const { BANK, buildOptions, titleSim } = __erg, out = {};
      for (const diff of ['easy', 'normal', 'hard']) for (const n of [4, 6, 9]) {
        let same = 0, voice = 0, other = 0, near = 0, full = 0, dupTitle = 0, trials = 0, alike = 0, canAlike = 0;
        for (let i = 0; i < 600; i++){
          const song = BANK[Math.floor(Math.random() * BANK.length)];
          const opts = buildOptions(song, n, diff, Math.random, null);
          trials++; if (opts.length === n) full++;
          const others = BANK.filter(o => o.id !== song.id && o.cat === song.cat && !o.artists.some(a => song.artists.includes(a)));
          if (others.some(o => titleSim(song, o) >= 2)){ canAlike++;
            if (opts.some(o => o.id !== song.id && !o.artists.some(a => song.artists.includes(a)) && titleSim(song, o) >= 2)) alike++; }
          if (new Set(opts.map(o => o.title)).size !== opts.length) dupTitle++;
          for (const o of opts){ if (o.id === song.id) continue;
            if (o.artists.some(a => song.artists.includes(a))) same++;
            else { other++; if (o.v === song.v) voice++; if (Math.abs(o.year - song.year) <= 6) near++; } }
        }
        out[diff + n] = { sameSinger: +(same / trials).toFixed(2), sameGender: +(voice / Math.max(1, other)).toFixed(2), sameEra: +(near / Math.max(1, other)).toFixed(2), full: full === trials, dupTitle, alike: +(alike / Math.max(1, canAlike)).toFixed(2) };
      }
      // the voice labels that songs ended up with
      const v = {}; BANK.forEach(s => v[s.v] = (v[s.v] || 0) + 1); out.voices = v;
      // singers with at least 6 other songs in the same category: hard mode should use 6 of them with 9 choices
      const big = BANK.filter(s => BANK.filter(o => o.id !== s.id && o.cat === s.cat && o.artists.some(a => s.artists.includes(a))).length >= 6);
      let full4 = 0; for (let i = 0; i < 300; i++){ const song = big[Math.floor(Math.random() * big.length)];
        const o = buildOptions(song, 9, 'hard', Math.random, null).filter(x => x.id !== song.id && x.artists.some(a => song.artists.includes(a)));
        if (o.length === 6) full4++; }
      out.bigSingerHard9 = full4 / 300;
      const two = BANK.filter(s => BANK.filter(o => o.id !== s.id && o.cat === s.cat && o.artists.some(a => s.artists.includes(a))).length >= 2);
      let full2 = 0; for (let i = 0; i < 300; i++){ const song = two[Math.floor(Math.random() * two.length)];
        const o = buildOptions(song, 6, 'normal', Math.random, null).filter(x => x.id !== song.id && x.artists.some(a => song.artists.includes(a)));
        if (o.length === 2) full2++; }
      out.twoSingerNormal6 = full2 / 300;
      return out; }""")
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    check("every song gets the full number of choices", all(stats[k]["full"] for k in stats if k not in ("voices", "bigSingerHard9", "twoSingerNormal6")))
    check("no two choices share a title", all(stats[k]["dupTitle"] == 0 for k in stats if k not in ("voices", "bigSingerHard9", "twoSingerNormal6")))
    check("easy: no same-singer decoys with 4 choices, at most 2 with 9", stats["easy4"]["sameSinger"] == 0 and stats["easy9"]["sameSinger"] <= 2, (stats["easy4"]["sameSinger"], stats["easy9"]["sameSinger"]))
    check("every level: a look-alike title among the choices whenever one exists", all(stats[f"{d}{n}"]["alike"] >= 0.95 for d in ("easy", "normal", "hard") for n in (4, 6, 9) if not (d == "hard" and n == 4)), {k: v["alike"] for k, v in stats.items() if isinstance(v, dict) and "alike" in v})
    check("easy: about half same gender", 0.4 <= stats["easy9"]["sameGender"] <= 0.85, stats["easy9"]["sameGender"])
    check("normal: 2 same-singer decoys when the singer has enough songs", stats["twoSingerNormal6"] == 1, stats["twoSingerNormal6"])
    check("normal: other decoys mostly same gender", stats["normal9"]["sameGender"] >= 0.85, stats["normal9"]["sameGender"])
    check("hard: 6 of 8 wrong choices by the same singer when the singer has enough songs", stats["bigSingerHard9"] == 1, stats["bigSingerHard9"])
    check("hard: other decoys same gender", stats["hard9"]["sameGender"] >= 0.85, stats["hard9"]["sameGender"])
    check("hard: other decoys mostly same era", stats["hard9"]["sameEra"] >= 0.6, stats["hard9"]["sameEra"])
    b.close()
print(f"\n{sum(results)}/{len(results)} checks passed")
