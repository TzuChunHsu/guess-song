"""Randomness + options statistics through the ?debug hook."""
import sys, pathlib, json
from playwright.sync_api import sync_playwright
GAME = pathlib.Path(sys.argv[1]).resolve()
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(); pg.goto(GAME.as_uri() + "?debug")
    r = pg.evaluate("""() => {
      const E = window.__erg, zh = E.BANK.filter(s => s.cat === 'zh'), N = zh.length, R = {};
      // 1) is the first song uniformly random? draw many first songs, compare per-song counts with the expected value
      const T = 3000, firstCnt = new Map(), artistShare = {};
      for (let t = 0; t < T; t++){ const o = E.diverseOrder(zh, Math.random); firstCnt.set(o[0].id, (firstCnt.get(o[0].id) || 0) + 1); }
      // songs per singer -> expected share of a singer = its song count / N
      const per = {}; zh.forEach(s => per[s.artists[0]] = (per[s.artists[0]] || 0) + 1);
      let jay = 0; firstCnt.forEach((c, id) => { if (E.BANK[id].artists[0] === '周杰倫') jay += c; });
      R.firstSong = { jayObserved: (jay / T * 100).toFixed(1) + '%', jayExpectedIfUniform: (per['周杰倫'] / N * 100).toFixed(1) + '%', distinctFirstSongs: firstCnt.size + ' / ' + N };
      // 2) whole 10-song games: singer repeats within 5, and how often a singer shows up twice in a game
      let close = 0, twice = 0, G = 500; const seenSongs = new Set();
      for (let g = 0; g < G; g++){ const a = E.diverseOrder(zh, Math.random).slice(0, 10); a.forEach(s => seenSongs.add(s.id));
        const ar = a.map(s => s.artists[0]); if (new Set(ar).size < 10) twice++;
        for (let i = 0; i < 10; i++) for (let j = i + 1; j < Math.min(10, i + 6); j++) if (ar[i] === ar[j]) close++; }
      R.games = { singerRepeatWithin5: close, gamesWithASingerTwice: (twice / G * 100).toFixed(0) + '%', songsSeenIn500Games: seenSongs.size + ' / ' + N };
      // 3) recently heard songs come after unheard ones
      const recent = new Set(zh.slice(0, 200).map(s => s.id));
      const o = E.diverseOrder(zh, Math.random, null, recent), firstRecent = o.findIndex(s => recent.has(s.id));
      R.recent = { firstRecentlyHeardSongAtPosition: firstRecent, unheardSongs: N - 200 };
      // 4) options: same-singer decoys per difficulty, decoys within a game
      const opt = {};
      for (const diff of ['easy', 'normal', 'hard']) for (const n of [4, 6, 9]){
        let same = 0, bad = 0, T2 = 400;
        for (let t = 0; t < T2; t++){ const song = zh[Math.floor(Math.random() * N)], os = E.buildOptions(song, n, diff, Math.random);
          if (os.length !== n || !os.includes(song) || new Set(os.map(s => s.title)).size !== n) bad++;
          same += os.filter(s => s !== song && s.artists.some(a => song.artists.includes(a))).length / T2; }
        opt[diff + n] = { avgSameSingerDecoys: +same.toFixed(2), badOptionSets: bad };
      }
      R.options = opt;
      let rep = 0; for (let g = 0; g < 200; g++){ const seen = { ids: new Set() }, ids = [];
        E.diverseOrder(zh, Math.random).slice(0, 10).forEach(song => E.buildOptions(song, 9, 'normal', Math.random, seen).forEach(s => { if (s !== song) ids.push(s.id); }));
        rep += ids.length - new Set(ids).size; }
      R.optionsRepeatedDecoysPerGame = (rep / 200).toFixed(2);
      // 5) every category can build 9 options
      const cats = {}; ['zh','tw','yue','en','kr','jp','ot'].forEach(c => { const L = E.BANK.filter(s => s.cat === c); let ok = true;
        for (let t = 0; t < 100; t++){ const song = L[Math.floor(Math.random() * L.length)], os = E.buildOptions(song, 9, 'hard', Math.random); if (os.length !== 9 || os.some(s => s.cat !== c)) ok = false; }
        cats[c] = L.length + (ok ? ' ok' : ' BAD'); });
      R.categories = cats;
      return R;
    }""")
    print(json.dumps(r, ensure_ascii=False, indent=1)); b.close()
