"""Statistical check of singer variety: song order and answer options (uses the ?debug hook, no audio)."""
import sys, pathlib, json
from playwright.sync_api import sync_playwright
GAME = pathlib.Path(sys.argv[1]).resolve()
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(); pg.goto(GAME.as_uri() + "?debug")
    r = pg.evaluate("""() => {
      const E = window.__erg, zh = E.BANK.filter(s => s.cat === 'zh');
      const games = 400, N = 10, res = { distinctPerGame: 0, repeatGames: 0, jayGames: 0, top: {} };
      const cnt = {};
      // old behaviour for comparison: plain shuffle
      const sh = a => { a = a.slice(); for (let i = a.length - 1; i > 0; i--){ const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
      let old = { distinct: 0, repeat: 0, jay: 0 };
      for (let g = 0; g < games; g++){
        const o = E.diverseOrder(zh).slice(0, N), a = o.map(s => s.artists[0]);
        const d = new Set(a).size; res.distinctPerGame += d / games; if (d < N) res.repeatGames++;
        if (a.includes('周杰倫')) res.jayGames++;
        a.forEach(x => cnt[x] = (cnt[x] || 0) + 1);
        const so = sh(zh).slice(0, N).map(s => s.artists[0]), sd = new Set(so).size;
        old.distinct += sd / games; if (sd < N) old.repeat++; if (so.includes('周杰倫')) old.jay++;
      }
      res.top = Object.entries(cnt).sort((x, y) => y[1] - x[1]).slice(0, 8).map(([k, v]) => k + ' ' + (v / (games * N) * 100).toFixed(1) + '%');
      res.artistsSeen = Object.keys(cnt).length + ' / ' + new Set(zh.map(s => s.artists[0])).size;
      res.old = old;
      // within-game minimum gap between two songs of the same singer (whole bag)
      let minGap = 1e9; const bag = E.diverseOrder(zh); const last = {};
      bag.slice(0, 60).forEach((s, i) => { s.artists.forEach(x => { if (x in last) minGap = Math.min(minGap, i - last[x]); last[x] = i; }); });
      res.minGapFirst60 = minGap === 1e9 ? 'none' : minGap;
      // options: how many distinct singers among the choices, per difficulty
      const opt = {};
      for (const diff of ['easy', 'normal', 'hard']) for (const n of [4, 6, 9]){
        let same = 0, dupDecoy = 0, jayDecoy = 0, T = 300;
        for (let t = 0; t < T; t++){
          const song = zh[Math.floor(Math.random() * zh.length)];
          const os = E.buildOptions(song, n, diff, Math.random);
          if (os.length !== n || !os.includes(song)) return 'BAD OPTIONS ' + diff + n;
          const decoys = os.filter(s => s !== song);
          same += decoys.filter(s => s.artists.some(a => song.artists.includes(a))).length / T;
          const ds = decoys.filter(s => !s.artists.some(a => song.artists.includes(a))).map(s => s.artists[0]);
          if (new Set(ds).size < ds.length) dupDecoy++;
          if (song.artists[0] !== '周杰倫' && decoys.some(s => s.artists[0] === '周杰倫')) jayDecoy++;
        }
        opt[diff + n] = { sameSingerDecoys: +same.toFixed(2), gamesWithRepeatedDecoySinger: dupDecoy, jayAsDecoyPct: (jayDecoy / T * 100).toFixed(0) + '%' };
      }
      res.options = opt;
      // a whole 10-round game of 9 choices: how many different decoy singers / repeated decoy songs
      let dS = 0, rep = 0, G2 = 200;
      for (let t = 0; t < G2; t++){
        const seen = { ids: new Set(), artists: new Map() }, ids = [], arts = new Set();
        E.diverseOrder(zh).slice(0, 10).forEach(song => E.buildOptions(song, 9, 'normal', Math.random, seen).forEach(s => { if (s !== song){ ids.push(s.id); arts.add(s.artists[0]); } }));
        dS += arts.size / G2; rep += (ids.length - new Set(ids).size) / G2;
      }
      res.gameOptions = { decoys: 80, distinctDecoySingers: +dS.toFixed(1), repeatedDecoySongs: +rep.toFixed(2) };
      // famous singers: chance of showing up as an answer in a 10-song game
      const fam = {}; ['周杰倫', '五月天', '林俊傑', '孫燕姿', '李聖傑', '梁靜茹'].forEach(a => fam[a] = 0);
      for (let g = 0; g < 400; g++){ const a = new Set(E.diverseOrder(zh).slice(0, 10).flatMap(s => s.artists)); Object.keys(fam).forEach(k => { if (a.has(k)) fam[k]++; }); }
      Object.keys(fam).forEach(k => fam[k] = (fam[k] / 4).toFixed(0) + '%');
      res.famousPerGame = fam;
      return res;
    }""")
    r.pop("options"); print(json.dumps(r, ensure_ascii=False, indent=1))
    b.close()
