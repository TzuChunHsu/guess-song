/* ================= 好友對戰 (online battle) =================
   Rooms live in a Firebase Realtime Database, used through its REST API: fetch for writes and a
   server-sent-events stream (EventSource) to follow the room live, so no SDK and no sign-in.
   The host's device picks and checks every song with the same pipeline as a solo game and writes
   each question to the room; every device plays the preview itself, starting together at a time
   given in server time. Room layout (rooms/CODE):
     v, bv (song bank version), host (player id), nm (room name, optional), ts, st ('lobby' | 'play' | 'end'), gk (game id),
     cfg { cats, y0, y1, diff, n, t, clip, r }, cur (question index), at (server ms the question starts),
     q/nI { s song id, u preview, st clip start, o option ids, ev, src, art, th, lk, alt, ch, ce },
     a/nI/PLAYER { k picked song id (-1 time up, -2 can't play), t seconds, p points },
     p/PLAYER { n name, j joined, hb heartbeat, s score, c correct, tt seconds spent on correct answers }
   Battle rules (modelled on Kahoot-style speed scoring and the fastest-answer bonus of music quizzes):
     correct = 500 + up to 500 for speed (× 0.6 / × 0.35 after listening longer), +100 per song in a row
     (up to +300), fastest correct answer of the song +200, the last song counts double,
     hard mode costs 200 for a wrong answer; ties go to more correct answers, then the faster total time. */
const FB_DEFAULT = 'https://guess-song-f9971-default-rtdb.firebaseio.com';   // the Firebase Realtime Database URL, e.g. https://xxx-default-rtdb.asia-southeast1.firebasedatabase.app
const FB = (() => {
  const ok = u => /^https:\/\/[a-z0-9-]+(\.[a-z0-9-]+)*\.(firebaseio\.com|firebasedatabase\.app)$/i.test(u) || /^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(u);
  let q = ''; try { q = new URLSearchParams(location.search).get('fb') || ''; } catch(e){}
  return [q, FB_DEFAULT].map(u => String(u || '').trim().replace(/\/+$/, '')).find(ok) || '';
})();
const SV_TS = { '.sv': 'timestamp' };
const fb = {
  url: p => FB + '/' + p + '.json',
  async req(method, p, body){
    const init = { method, cache: 'no-store' };
    if (body !== undefined) init.body = JSON.stringify(body);
    const r = await fetch(fb.url(p), init);
    if (!r.ok) throw new Error('http ' + r.status);
    const t = await r.text();
    return t ? JSON.parse(t) : null;
  },
  get: p => fb.req('GET', p),
  put: (p, v) => fb.req('PUT', p, v),
  patch: (p, v) => fb.req('PATCH', p, v),
  del: p => fb.req('DELETE', p)
};
async function fbTry(fn, n = 3){
  for (let i = 0; ; i++){
    try { return await fn(); } catch(e){ if (i >= n - 1) throw e; await sleep(700 * (i + 1)); }
  }
}
/* set a value inside a JSON tree by a slash path ("/q/n0"); null removes it */
function treeSet(root, path, val){
  const parts = String(path).split('/').filter(Boolean);
  if (!parts.length) return val == null ? null : val;
  if (root == null || typeof root !== 'object') root = {};
  let o = root;
  for (let i = 0; i < parts.length - 1; i++){
    if (o[parts[i]] == null || typeof o[parts[i]] !== 'object') o[parts[i]] = {};
    o = o[parts[i]];
  }
  const k = parts[parts.length - 1];
  if (val == null) delete o[k]; else o[k] = val;
  return root;
}
/* follow a path live; onData gets the whole subtree after every change.
   Some networks (proxies, school or office Wi-Fi) break event streams: if no data comes through,
   fall back to asking for the room once a second. */
function fbListen(path, onData, onState){
  let tree = null, es = null, closed = false, got = false, fails = 0, poll = 0, watchdog = 0;
  const startPolling = () => {
    if (closed || poll) return;
    if (es){ es.close(); es = null; }
    onState('polling');
    const tick = async () => {
      if (closed) return;
      try { tree = await fb.get(path); fails = 0; onState('open'); onData(tree); }
      catch(e){ if (++fails >= 3) onState('error'); if (/http 40[13]/.test(String(e.message))) onState('denied'); }
    };
    tick(); poll = setInterval(tick, 1000);
  };
  const open = () => {
    if (closed || poll) return;
    try { es = new EventSource(fb.url(path)); } catch(e){ return startPolling(); }
    clearTimeout(watchdog);
    watchdog = setTimeout(() => { if (!got) startPolling(); }, 7000);     // nothing arrived: the stream doesn't work here
    es.addEventListener('put', e => {
      let m; try { m = JSON.parse(e.data); } catch(err){ return; }
      got = true; fails = 0;
      tree = m.path === '/' ? m.data : treeSet(tree, m.path, m.data);
      onData(tree);
    });
    es.addEventListener('patch', e => {
      let m; try { m = JSON.parse(e.data); } catch(err){ return; }
      for (const k in m.data) tree = treeSet(tree, m.path.replace(/\/$/, '') + '/' + k, m.data[k]);
      onData(tree);
    });
    es.addEventListener('cancel', () => onState('denied'));
    es.onopen = () => onState('open');
    es.onerror = () => {
      if (closed || poll) return;
      onState('error');
      if (++fails >= 4 && !got) return startPolling();
      if (es.readyState === 2){ es.close(); setTimeout(open, 2500); }   // the browser gave up: reconnect ourselves
    };
  };
  open();
  return { close(){ closed = true; clearTimeout(watchdog); clearInterval(poll); if (es) es.close(); }, polling: () => !!poll };
}

/* ---- server clock: every device counts down to the same server time ---- */
const mpClock = { off: 0, samples: [] };
function srvNow(){ return Date.now() + mpClock.off; }
function clockSample(t0, t1, ts){
  if (typeof ts !== 'number' || !isFinite(ts)) return;
  mpClock.samples.push({ rtt: t1 - t0, off: ts - (t0 + t1) / 2, at: t1 });
  mpClock.samples = mpClock.samples.filter(x => t1 - x.at < 180000).slice(-12);
  mpClock.off = mpClock.samples.reduce((a, b) => b.rtt < a.rtt ? b : a).off;   // the quickest round trip is the most exact
}

const MP_ALPHA = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';     // no I/O/0/1, easy to read out loud
const MP_LEAD = 3000;          // countdown before a song starts
const MP_GRACE = 7000;         // extra time on top of the time limit for slow loaders
const MP_HOLD = 6000;          // how long the answer and scores stay up before the next song
const MP_STALE = 15000;        // a player whose heartbeat is older than this is treated as gone
const MP_HOST_STALE = 20000;   // after this long without the host, the next player takes over
const BANK_VER = hashStr(BANK_RAW).toString(36);
/* difficulty presets for battles: everyone in the room plays the same settings */
const MP_DIFF = {
  easy:   { name: '輕鬆', n: 4, t: 20, wrong: 0,   desc: '片段 5 秒 · 4 選 1 · 限時 20 秒 · 答錯不扣分' },
  normal: { name: '普通', n: 6, t: 15, wrong: 0,   desc: '片段 3 秒 · 6 選 1 · 限時 15 秒 · 混 1 首同歌手的歌' },
  hard:   { name: '地獄', n: 9, t: 10, wrong: 200, desc: '片段 1.5 秒 · 9 選 1 · 限時 10 秒 · 一半是同歌手陷阱 · 答錯倒扣 200' }
};
const MP_FAST = 200;          // bonus for the fastest correct answer of a song
/* A room can be found by its 4-letter code or by a name: the name is hashed into the code. */
function mpCodeFor(input){
  const raw = String(input || '').normalize('NFKC').trim().replace(/\s+/g, ' ');
  const up = raw.toUpperCase().replace(/\s/g, '');
  if (up.length === 4 && [...up].every(c => MP_ALPHA.includes(c))) return { code: up, name: '' };
  if ([...raw].length < 2) return null;
  let h = hashStr('erg-room|' + raw.toLowerCase()), code = '';
  for (let i = 0; i < 4; i++){ code += MP_ALPHA[h & 31]; h >>>= 5; }
  return { code, name: [...raw].slice(0, 16).join('') };
}
const mpSameName = (a, b) => String(a || '').normalize('NFKC').trim().replace(/\s+/g, ' ').toLowerCase() === String(b || '').normalize('NFKC').trim().replace(/\s+/g, ' ').toLowerCase();
/* someone is still in this room (any heartbeat in the last 5 minutes) */
function mpRoomBusy(room){ return !!room && mpPlayers(room).some(p => Date.now() - (+p.hb || 0) < 5 * 60000); }
const mp = { code: null, pid: null, room: null, sub: null, hb: 0, tick: 0, isHost: false, gameKey: null, roundIdx: -1,
  aud: {}, local: {}, overAt: {}, preparing: false, noMore: false, producer: false, patching: 0, finalShown: false, busy: false };
const mpArr = x => Array.isArray(x) ? x : Object.values(x || {});     // the database may hand arrays back as objects

function mpPid(){
  let id = null;
  try { id = sessionStorage.getItem('erg_mp_pid'); } catch(e){}
  if (!id || !/^u[a-z0-9]{6,16}$/.test(id)){
    id = 'u' + Array.from(crypto.getRandomValues(new Uint8Array(9)), b => (b % 36).toString(36)).join('');   // starts with a letter: never read back as an array index
    try { sessionStorage.setItem('erg_mp_pid', id); } catch(e){}
  }
  return id;
}
function mpName(){
  const v = [...($('#mp-name').value || '').normalize('NFKC').trim().replace(/\s+/g, ' ')].slice(0, 12).join('');
  if (!v){ toast('先輸入你的暱稱，朋友才認得你'); $('#mp-name').focus(); return ''; }
  $('#mp-name').value = v;
  store.set('mpName', v);
  return v;
}
function mpLink(code){
  const u = new URL(location.href);
  [...u.searchParams.keys()].filter(k => k !== 'fb' && k !== 'debug').forEach(k => u.searchParams.delete(k));
  if (code) u.searchParams.set('room', code);
  u.hash = '';
  return u.toString();
}
function mpCfgFromSettings(){
  const old = (mp.room && mp.room.cfg) || {};
  const r = +(old.r || store.get('mpRounds', 10)) || 10;
  const diff = MP_DIFF[old.diff] ? old.diff : MP_DIFF[store.get('mpDiff', 'normal')] ? store.get('mpDiff', 'normal') : 'normal';
  return { cats: settings.cats.slice(), y0: settings.y0, y1: settings.y1, diff, n: MP_DIFF[diff].n, t: MP_DIFF[diff].t, clip: settings.clip, r };
}
function mpCfgText(c){
  const cats = mpArr(c.cats).length ? mpArr(c.cats) : ['zh'];
  return `${catLabel(cats)} · ${rangeLabel(+c.y0 || MINY, +c.y1 || MAXY)}${c.clip === 'chorus' ? ' · 只出副歌' : ' · 隨機片段'} · 共 ${poolFor(cats, +c.y0 || MINY, +c.y1 || MAXY).length} 首可抽`;
}
function mpStartLabel(){
  if (!mp.code) return '建立房間';
  return mp.isHost && mp.room && mp.room.st === 'lobby' ? `用這些設定 · 回到房間 ${mp.code}` : `回到房間 ${mp.code}`;
}
function mpBusy(on){ mp.busy = on; $('#mp-join').disabled = on || !FB; $('#btn-start').disabled = on || $('#btn-start').disabled; if (!on) renderHome(); }
function mpPlayers(room){ return Object.entries((room && room.p) || {}).filter(([, p]) => p && typeof p === 'object').map(([id, p]) => Object.assign({ id }, p)); }
function mpActive(room, now){ return mpPlayers(room).filter(p => now - (+p.hb || 0) < MP_STALE); }
function mpT(room){ const c = (room && room.cfg) || {}; return (MP_DIFF[c.diff] || MP_DIFF.normal).t; }

/* ---- create / join / leave ---- */
async function mpCreate(){
  if (!FB || mp.busy) return;
  const name = mpName();
  if (!name) return;
  if (poolFor(settings.cats, settings.y0, settings.y1).length < MIN_POOL) return toast('題目太少，放寬類別或年代');
  const rn = [...($('#mp-room').value || '').normalize('NFKC').trim().replace(/\s+/g, ' ')].slice(0, 16).join('');
  const named = rn ? mpCodeFor(rn) : null;      // a 4-letter name such as "test" simply becomes the room code TEST
  if (rn && !named) return toast('房間名稱至少要 2 個字');
  mpBusy(true);
  try {
    const pid = mpPid();
    let code = null;
    if (named){
      const ex = await fb.get(`rooms/${named.code}`);
      if (ex && mpRoomBusy(ex) && !(ex.p && ex.p[pid])) return toast(`「${rn}」這個房間名稱正在使用中，換一個名稱`);
      code = named.code;
      store.set('mpRoomName', rn);
    } else {
      for (let i = 0; i < 6 && !code; i++){
        const c = Array.from(crypto.getRandomValues(new Uint8Array(4)), b => MP_ALPHA[b % MP_ALPHA.length]).join('');
        const ex = await fb.get(`rooms/${c}`);
        if (!ex || !mpRoomBusy(ex)) code = c;                          // unused, or abandoned
      }
    }
    if (!code) throw new Error('no code');
    const t0 = Date.now();
    const room = await fb.put(`rooms/${code}`, Object.assign({ v: 1, bv: BANK_VER, host: pid, ts: SV_TS, st: 'lobby', cfg: mpCfgFromSettings(), p: { [pid]: { n: name, j: SV_TS, hb: SV_TS, s: 0, c: 0 } } }, named ? { nm: rn } : {}));
    clockSample(t0, Date.now(), room && room.ts);
    mpEnter(code, pid);
  } catch(e){ toast('建立房間失敗，請確認網路後再試'); }
  finally { mpBusy(false); }
}
async function mpJoin(raw){
  if (!FB || mp.busy) return;
  const target = mpCodeFor(raw);
  if (!target) return toast('輸入 4 碼房號，或房主取的房間名稱');
  const code = target.code;
  if (mp.code === code) return show(mp.room && mp.room.st === 'play' ? 'game' : 'lobby');
  let name = mpName();
  if (!name) return;
  mpBusy(true);
  try {
    if (mp.code) await mpLeave();
    const pid = mpPid();
    const room = await fb.get(`rooms/${code}`);
    if (!room || !room.host || (target.name && !mpSameName(room.nm, target.name))) return toast(target.name ? `找不到「${target.name}」這個房間，確認一下名稱或改用房號` : '找不到這個房間，確認一下房號');
    const taken = new Set(mpPlayers(room).filter(p => p.id !== pid && Date.now() - (+p.hb || 0) < 60000).map(p => String(p.n || '').toLowerCase()));
    if (taken.has(name.toLowerCase())){
      let k = 2; while (taken.has((name + k).toLowerCase())) k++;
      name = name + k; store.set('mpName', name); $('#mp-name').value = name;
      toast(`房間裡已經有人叫這個名字，你改叫「${name}」`);
    }
    if (room.bv && room.bv !== BANK_VER) return showModal('遊戲版本不一樣', '你的遊戲版本跟房主的不同，題目會對不上。請重新整理頁面後再加入；還是不行的話，請房主也重新整理。', [{ label: '取消' }, { label: '重新整理', primary: true, fn: () => location.reload() }]);
    const me = room.p && room.p[pid];
    const t0 = Date.now();
    const v = await fb.patch(`rooms/${code}/p/${pid}`, me ? { n: name, hb: SV_TS } : { n: name, j: SV_TS, hb: SV_TS, s: 0, c: 0 });
    clockSample(t0, Date.now(), v && v.hb);
    mpEnter(code, pid);
  } catch(e){ toast('加入失敗，請確認網路後再試'); }
  finally { mpBusy(false); }
}
function mpEnter(code, pid){
  mpStop(false);
  Object.assign(mp, { code, pid, room: null, isHost: false, gameKey: null, roundIdx: -1, aud: {}, local: {}, overAt: {}, preparing: false, noMore: false, producer: false, patching: 0, finalShown: false, boardHtml: '', lobbyHtml: '' });
  try { sessionStorage.setItem('erg_mp_room', code); } catch(e){}
  try { history.replaceState(null, '', mpLink(code)); } catch(e){}
  $('#mp-code').value = code;
  mp.sub = fbListen(`rooms/${code}`, mpOnRoom, mpOnNet);
  mp.hb = setInterval(mpHeartbeat, 4000);
  mp.tick = setInterval(mpTick, 250);
  $('#lb-code').textContent = code;
  // until the room arrives nobody gets host buttons
  $('#lb-host').hidden = true; $('#lb-wait').hidden = false; $('#lb-wait').textContent = '連線中…';
  $('#lb-players').innerHTML = ''; $('#lb-name').hidden = true; $('#lb-cfg').textContent = '';
  show('lobby');
}
function mpStop(clearUrl){
  if (mp.sub) mp.sub.close();
  clearInterval(mp.hb); clearInterval(mp.tick); clearTimeout(mp.netTimer);
  if (G && G.mode === 'battle'){ G.dead = true; G.queue.forEach(q => audioPool.release(q.audio)); G.queue = []; }
  Object.values(mp.aud).forEach(a => audioPool.release(a.audio));
  Object.values(mp.local).forEach(it => audioPool.release(it.audio));
  Object.assign(mp, { code: null, room: null, sub: null, isHost: false, gameKey: null, roundIdx: -1, aud: {}, local: {}, overAt: {} });
  $('#mp-net').hidden = true;
  if (clearUrl){
    try { sessionStorage.removeItem('erg_mp_room'); } catch(e){}
    try { history.replaceState(null, '', mpLink(null)); } catch(e){}
  }
}
async function mpLeave(){
  const code = mp.code, pid = mp.pid, room = mp.room;
  mpStop(true);
  if (!code || !room) return;
  try {
    const others = mpActive(room, srvNow()).filter(p => p.id !== pid).sort((a, b) => (+a.j || 0) - (+b.j || 0));
    if (!others.length) await fb.del(`rooms/${code}`);
    else {
      const upd = { [`p/${pid}`]: null };
      if (room.host === pid) upd.host = others[0].id;
      await fb.patch(`rooms/${code}`, upd);
    }
  } catch(e){}
}
function mpGone(msg){
  const wasIn = !!mp.code;
  mpStop(true);
  if (!wasIn) return;
  if (G && G.mode === 'battle') G.dead = true;
  stopPlayback(); stopTimer();
  showModal('房間已關閉', msg, [{ label: '回主選單', primary: true, fn: goHome }]);
}
async function mpHeartbeat(){
  if (!mp.code) return;
  const code = mp.code, t0 = Date.now();
  mp.hbSent = t0;
  try { const v = await fb.patch(`rooms/${code}/p/${mp.pid}`, { n: store.get('mpName', '') || '玩家', hb: SV_TS }); if (code === mp.code) clockSample(t0, Date.now(), v && v.hb); } catch(e){}
}
function mpOnNet(state){
  if (state === 'open'){ clearTimeout(mp.netTimer); mp.netTimer = 0; $('#mp-net').hidden = true; }
  else if (state === 'error'){ if (!mp.netTimer) mp.netTimer = setTimeout(() => { if (mp.code) $('#mp-net').hidden = false; }, 2500); }
  else if (state === 'denied') mpGone('線上資料庫拒絕讀取這個房間，可能是資料庫的規則沒有設定好。');
}
function mpOnRoom(room){
  if (!mp.code) return;
  if (!room || typeof room !== 'object' || !room.host){ mpGone('房主已經關閉了這個房間。'); return; }
  mp.room = room;
  const me = room.p && room.p[mp.pid];
  if (me && typeof me.hb === 'number' && me.hb !== mp.hbSeen && mp.hbSent){ mp.hbSeen = me.hb; clockSample(mp.hbSent, Date.now(), me.hb); }
  mp.isHost = room.host === mp.pid;
  mpRender();
}
/* write to the room and apply it locally right away, so the next tick doesn't repeat it */
function mpPatchRoom(v){
  if (!mp.code) return Promise.resolve();
  const code = mp.code;
  for (const k in v) treeSet(mp.room, k, v[k]);
  mp.isHost = !!mp.room && mp.room.host === mp.pid;
  mp.patching++;
  return fbTry(() => fb.patch(`rooms/${code}`, v)).catch(() => toast('房間連線不順，請確認網路')).finally(() => { mp.patching--; });
}
function mpTick(){
  if (!mp.code || !mp.room) return;
  const now = srvNow();
  mpMaybeTakeOver(now);
  mpRender();
}
function mpMaybeTakeOver(now){
  const room = mp.room;
  if (mp.isHost || mp.patching) return;
  const host = room.p && room.p[room.host];
  if (host && now - (+host.hb || 0) < MP_HOST_STALE) return;
  const act = mpActive(room, now).sort((a, b) => (+a.j || 0) - (+b.j || 0) || (a.id < b.id ? -1 : 1));
  if (act.length && act[0].id === mp.pid){ mpPatchRoom({ host: mp.pid }); toast('房主斷線了，由你接手當房主'); }
}

/* ---- what each device shows ---- */
function mpRender(){
  const room = mp.room;
  if (!room || !mp.code) return;
  const now = srvNow();
  if (room.st === 'lobby'){
    if (mp.gameKey){ mp.gameKey = null; if (G && G.mode === 'battle') G.dead = true; stopPlayback(); stopTimer(); }
    if ($('#game').classList.contains('active') || $('#result').classList.contains('active')) show('lobby');
    if ($('#lobby').classList.contains('active')) mpRenderLobby(now);
    if ($('#home').classList.contains('active')) $('#btn-start').textContent = mpStartLabel();
    return;
  }
  if (room.gk && mp.gameKey !== room.gk) mpStartLocal(room);
  if (room.st === 'play') mpRenderPlay(now);
  else if (room.st === 'end'){ mpShowFinal(); if ($('#lobby').classList.contains('active')) mpRenderLobby(now); }
  if (mp.isHost && room.st === 'play') mpHostDuties(now);
}
function mpRenderLobby(now){
  const room = mp.room;
  const act = new Set(mpActive(room, now).map(p => p.id));
  const ps = mpPlayers(room).filter(p => act.has(p.id) || p.id === mp.pid).sort((a, b) => (+a.j || 0) - (+b.j || 0));
  const html = ps.map(p => `<li class="pl${p.id === mp.pid ? ' me' : ''}"><span class="pl-rank">${p.id === room.host ? '👑' : '🎧'}</span><span class="pl-name">${esc(p.n || '玩家')}${p.id === mp.pid ? '<small>你</small>' : ''}</span>${p.id === room.host ? '<span class="pl-round">房主</span>' : ''}</li>`).join('');
  if (html !== mp.lobbyHtml){ mp.lobbyHtml = html; $('#lb-players').innerHTML = html; }
  $('#lb-code').textContent = mp.code;
  $('#lb-name').hidden = !room.nm;
  $('#lb-name').textContent = room.nm ? `房間名稱「${room.nm}」· 朋友輸入名稱或房號都能加入` : '';
  $('#lb-count').textContent = `玩家 · ${ps.length} 人`;
  const c = room.cfg || {};
  const d = MP_DIFF[c.diff] ? c.diff : 'normal';
  $('#lb-cfg').textContent = mpCfgText(c);
  $('#lb-diff-note').textContent = `${MP_DIFF[d].name}：${MP_DIFF[d].desc}`;
  $$('#lb-diff button').forEach(b => { b.classList.toggle('on', b.dataset.d === d); b.disabled = !mp.isHost; });
  $('#lb-rules-wrong').hidden = !MP_DIFF[d].wrong;
  $('#lb-host').hidden = !mp.isHost;
  $('#lb-wait').hidden = mp.isHost;
  $('#lb-wait').textContent = room.st === 'end' ? '這局結束了，等房主開下一局…' : '等房主按開始…';
  $$('#lb-rounds button').forEach(b => { b.classList.toggle('on', +b.dataset.r === (+c.r || 10)); b.disabled = !mp.isHost; });
  $('#lb-start').textContent = ps.length > 1 ? `開始對戰 · ${ps.length} 人` : '開始（朋友還沒進來，也可以先自己試玩）';
}
function mpRankText(){
  const room = mp.room;
  if (!room || !G) return '';
  const now = srvNow();
  const ps = mpPlayers(room).filter(p => p.id === mp.pid || now - (+p.hb || 0) < MP_STALE || +p.s > 0);
  const rank = 1 + ps.filter(p => p.id !== mp.pid && (+p.s || 0) > G.score).length;
  return ps.length > 1 ? `第 ${rank} 名 · ${ps.length} 人` : '';
}
function mpStartLocal(room){
  const c = room.cfg || {};
  if (G){ G.dead = true; G.queue.forEach(q => audioPool.release(q.audio)); }
  stopPlayback(); stopTimer();
  Object.values(mp.aud).forEach(a => audioPool.release(a.audio));
  Object.values(mp.local).forEach(it => audioPool.release(it.audio));
  const cats = mpArr(c.cats).filter(k => CATS.some(x => x[0] === k));
  const diff = MP_DIFF[c.diff] ? c.diff : 'normal';
  const nopt = MP_DIFF[diff].n;
  const y0 = +c.y0 || MINY, y1 = +c.y1 || MAXY;
  const poolArr = poolFor(cats.length ? cats : ['zh'], y0, y1);
  G = {
    mode: 'battle', diff, nopt, y0, y1, cats: cats.length ? cats : ['zh'], daily: false, tlimit: MP_DIFF[diff].t, mpWrong: MP_DIFF[diff].wrong, mpTime: 0, chorus: c.clip === 'chorus', blobs: [], dateKey: todayKey(), cfg: DIFF[diff],
    rounds: Math.max(1, Math.min(30, +c.r || 10)), roundNo: 0, score: 0, combo: 0, maxCombo: 0, lives: 0, level: 0, correct: 0,
    items: { cut: 0, free: 0, skip: 0 },
    history: [], played: new Set(), failed: new Set(), retry: new Map(), optSeen: { ids: new Set(), artists: new Map() }, bag: [], poolIds: new Set(poolArr.map(s => s.id)),
    queue: [], waiters: [], filling: false, netFails: 0, audioFails: 0, skipped: 0, netError: false, audioError: false, dead: false
  };
  const me = room.p && room.p[mp.pid];
  if (me){ G.score = +me.s || 0; G.correct = +me.c || 0; G.mpTime = +me.tt || 0; }       // back in after a reload
  Object.assign(mp, { gameKey: room.gk, roundIdx: -1, aud: {}, local: {}, overAt: {}, preparing: false, noMore: false, producer: false, finalShown: false, boardHtml: '', cd: 0, netRetry: 0 });
  R = null;
  $('#game').classList.toggle('n9', G.nopt === 9);
  $('#res-board-wrap').hidden = true;
  if (room.st === 'play'){
    resetClock();
    $('#event').hidden = true; $('#reveal').hidden = true; $('#status').hidden = false;
    $('#options').innerHTML = ''; $('#options').className = 'options locked';
    $('#items').hidden = true; $('#btn-next').hidden = true; $('#mp-board').hidden = true;
    $('#label').classList.remove('show', 'big'); $('#label-q').className = 'q load'; $('#label-q').textContent = '?';
    $('#status-text').textContent = '房主正在準備第一首歌…';
    renderHud();
    show('game');
  }
}
/* preload a question's preview on this device */
function mpLoadAudio(k, q){
  if (mp.aud[k]) return mp.aud[k];
  if (mp.local[k]){ const it = mp.local[k]; return (mp.aud[k] = { audio: it.audio, url: it.url, ok: true }); }
  const audio = audioPool.take();
  const urls = [q.u, ...mpArr(q.alt)].filter(Boolean).map(u => String(u).replace(/^http:\/\//, 'https://'));
  const rec = mp.aud[k] = { audio, url: urls[0], ok: null };
  (async () => {
    for (const u of urls){
      audio.src = u + '#t=' + (+q.st || 0); rec.url = u;
      const r = await verifyAudio(audio, 8000);
      if (mp.aud[k] !== rec) return;
      if (r !== 'error'){ rec.ok = true; return; }
    }
    rec.ok = false;
    if (R && R.mpIdx === k && R.mpStarted) mpCantPlay();
  })();
  return rec;
}
function mpRenderPlay(now){
  const room = mp.room, i = +room.cur || 0;
  if (!$('#game').classList.contains('active') && $('#modal').hidden) show('game');
  const q = room.q && room.q['n' + i];
  [i, i + 1].forEach(k => { const qq = room.q && room.q['n' + k]; if (qq && k < G.rounds) mpLoadAudio(k, qq); });
  if (mp.roundIdx !== i){
    if (!q){
      if (!R) $('#status-text').textContent = '房主正在找歌…';
      else if (R.answered) mpRenderBoard('房主正在找下一首歌…');
      return;
    }
    mpSetupRound(i, q);
  }
  if (!R || R.mpIdx !== i) return;
  if (!room.at){ if (!R.answered) $('#status-text').textContent = '等大家準備好…'; return; }
  const left = room.at - now;
  if (left > 0){
    const n = Math.ceil(left / 1000);
    if (mp.cd !== n){ mp.cd = n; $('#label-q').textContent = n; $('#status-text').textContent = `第 ${i + 1} 首 · ${n} 秒後大家一起播放`; if (n <= 3) sfx.tick(); }
    return;
  }
  if (!R.mpStarted){
    R.mpStarted = true;
    R.mpDeadline = room.at + mpT(room) * 1000 + MP_GRACE;
    $('#label-q').textContent = '?';
    const rec = mp.aud[i];
    if (rec) R.url = rec.url;
    if (rec && rec.ok === false) mpCantPlay();
    else playClip();                      // may be refused without a tap: then the status asks for one
  }
  if (!R.mpOver && mpRoundOver(room, i, now)){ R.mpOver = true; mpOnRoundOver(); }
  if (R.answered) mpRenderBoard();
}
function mpSetupRound(i, q){
  stopPlayback(); stopTimer();
  Object.keys(mp.aud).forEach(k => { if (+k < i){ audioPool.release(mp.aud[k].audio); delete mp.aud[k]; } });
  Object.keys(mp.local).forEach(k => { if (+k < i){ audioPool.release(mp.local[k].audio); delete mp.local[k]; } });
  mp.roundIdx = i; mp.cd = 0; mp.boardHtml = '';
  G.roundNo = i + 1;
  const song = BANK[q.s];
  const options = mpArr(q.o).map(id => BANK[id]).filter(Boolean);
  if (!song || options.length < 2) return mpGone('題目對不上，可能是大家的遊戲版本不同。請所有人重新整理頁面後再開一局。');
  const a = mpLoadAudio(i, q);
  R = {
    song, info: { u: q.u, art: q.art || '', thumb: q.th || '', link: q.lk || '', src: q.src || '' }, audio: a.audio, url: a.url, verified: a.ok === true,
    rng: cryptoRnd, clipIdx: 0, penalty: 0, usedFree: false, played: false, answered: false, t0: 0, limit: 0,
    event: null, start: 0, options, removed: new Set(),
    chorus: q.ch ? { cs: +q.st || 0, ce: +q.ce || (+q.st || 0) + 10, via: 'host' } : null, mpIdx: i, mpFinal: i + 1 >= G.rounds
  };
  const lens = clipLens(), maxLen = lens[lens.length - 1];
  if (R.chorus){ R.start = R.chorus.cs; R.lens = [...new Set(lens.map(l => Math.max(1, Math.min(l, Math.round((29.6 - R.start) * 10) / 10))))]; }
  else { R.lens = lens; R.start = Math.min(+q.st || 0, Math.max(0, 29.5 - maxLen)); }
  resetClock();
  const ev = $('#event');
  if (R.mpFinal && G.rounds > 1){ ev.dataset.kind = 'double'; ev.innerHTML = `🔥 最後一首 <small>分數加倍</small>`; ev.hidden = false; sfx.ev(); }
  else ev.hidden = true;
  $('#reveal').hidden = true; $('#status').hidden = false;
  $('#label').classList.remove('show', 'big'); $('#art').removeAttribute('src');
  $('#label-q').className = 'q'; $('#label-q').textContent = '?';
  $('#options').innerHTML = options.map((s, k) =>
    `<button class="opt" data-i="${k}"><span class="k">${k + 1}</span><span class="t${[...s.title].length >= 9 ? ' xl' : [...s.title].length >= 6 ? ' l' : ''}">${esc(s.title)}</span></button>`).join('');
  $('#options').className = 'options locked';
  $('#controls').hidden = false; $('#items').hidden = true; $('#btn-next').hidden = true;
  $('#btn-replay').disabled = $('#btn-extend').disabled = true; $('#ext-sub').textContent = '';
  $('#mp-board').hidden = true; $('#mp-board').innerHTML = '';
  $('#status-text').textContent = '等大家準備好…';
  setRing(0); renderHud(); updateExtend();
  a.audio.onerror = () => { if (R && R.audio === a.audio && R.mpStarted && !R.answered){ const rec = mp.aud[i]; if (rec && rec.ok !== null) mpCantPlay(); } };
}
function mpLimit(){ return Math.max(3, Math.min(G.tlimit, (R.mpDeadline - srvNow()) / 1000 - 1)); }
function mpCantPlay(){
  if (!R || R.answered) return;
  R.answered = true; R.mpSkip = true;
  stopPlayback(); stopTimer();
  $('#options').classList.add('locked');
  $('#status-text').textContent = '這首試聽在你的裝置播不出來，這題跳過（不扣分）';
  G.history.push({ song: R.song, info: R.info, url: R.url, ok: false, pts: 0, emoji: '⬜', picked: null, chorus: R.chorus, time: 0 });
  mpSubmit({ k: -2, t: 0, p: 0 });
  mpRenderBoard();
}
/* points for a correct answer in a battle (see the rules at the top of this section) */
function mpScore(elapsed){
  const base = 500 + 500 * Math.max(0, 1 - elapsed / G.tlimit);
  const streak = Math.min(G.combo, 3) * 100;                              // G.combo = songs right in a row before this one
  return Math.round((base * EXT_MULT[R.penalty] + streak) * (R.mpFinal ? 2 : 1) / 10) * 10;
}
function mpSubmit(a){
  if (!mp.code || !R) return;
  const i = R.mpIdx, code = mp.code;
  if (+a.k === R.song.id) G.mpTime = (G.mpTime || 0) + (+a.t || 0);
  const upd = { [`a/n${i}/${mp.pid}`]: a, [`p/${mp.pid}/s`]: G.score, [`p/${mp.pid}/c`]: G.correct, [`p/${mp.pid}/tt`]: Math.round((G.mpTime || 0) * 100) / 100 };
  for (const k in upd) treeSet(mp.room, k, upd[k]);
  fbTry(() => fb.patch(`rooms/${code}`, upd)).catch(() => toast('答案送出失敗，網路不太穩'));
}
function mpRoundOver(room, i, now){
  if (+room.cur !== i || !room.at || now < room.at) return false;
  if (now >= room.at + mpT(room) * 1000 + MP_GRACE) return true;
  const ans = (room.a && room.a['n' + i]) || {};
  const need = mpActive(room, now).filter(p => !(+p.j > room.at));     // players who were here when the song started
  return need.length > 0 && need.every(p => ans[p.id]);
}
function mpFastest(room, i, song){
  const ans = (room.a && room.a['n' + i]) || {};
  const ok = Object.entries(ans).filter(([, a]) => a && +a.k === song.id).map(([id, a]) => ({ id, t: +a.t || 0 }));
  if (!ok.length) return new Set();
  const best = Math.min(...ok.map(x => x.t));
  return new Set(ok.filter(x => x.t === best).map(x => x.id));
}
/* the pick is in: keep it to yourself until the song ends for everyone */
function mpLockIn(idx, elapsed){
  $$('#options .opt').forEach((b, i) => b.classList.add(i === idx ? 'picked' : 'dim'));
  $('#options').classList.add('done');
  $('#controls').hidden = true; $('#items').hidden = true;
  $('#status').hidden = false;
  $('#status-text').textContent = idx == null ? '時間到 · 等這首結束' : `已作答 · ${elapsed.toFixed(1)} 秒 · 等這首結束揭曉`;
  stopPlayback(); setRing(0);
  renderHud();
  mpRenderBoard();
}
function mpOnRoundOver(){
  const i = R.mpIdx, room = mp.room;
  if (!mp.overAt[i]) mp.overAt[i] = srvNow();
  if (R.mpPending){ const p = R.mpPending; R.mpPending = null; revealAnswer(p.idx, p.ok, p.pts, p.elapsed, false, null); }
  else if (!R.answered){
    if (!R.played){ R.played = true; R.t0 = performance.now(); }
    answer(null, false);                  // never answered: time is up
  } else if (R.mpSkip){
    $('#status').hidden = true;
    $('#rv-verdict').className = 'rv-verdict no'; $('#rv-verdict').textContent = '這首在你的裝置播不出來';
    $('#rv-title').textContent = '《' + R.song.title + '》'; $('#rv-meta').textContent = `${R.song.artist} · ${R.song.year}`;
    $('#reveal').hidden = false; $('#btn-notchorus').hidden = true;
    $$('#options .opt').forEach((b, k) => b.classList.add(R.options[k].id === R.song.id ? 'correct' : 'dim'));
  }
  // fastest correct answer of the song (only when there is someone to race)
  const many = Object.keys((room.a && room.a['n' + i]) || {}).length >= 2 || mpActive(room, srvNow()).length >= 2;
  if (many && !R.mpBonus && mpFastest(room, i, R.song).has(mp.pid)){
    R.mpBonus = true;
    G.score += MP_FAST;
    const code = mp.code, upd = { [`p/${mp.pid}/s`]: G.score };
    treeSet(mp.room, `p/${mp.pid}/s`, G.score);
    fbTry(() => fb.patch(`rooms/${code}`, upd)).catch(() => {});
    setTimeout(() => {
      sfx.item(); toast(`🥇 最快答對！搶答獎勵 +${MP_FAST}`);
      const f = $('#float-pts'); f.textContent = '🥇 +' + MP_FAST; f.classList.remove('go'); void f.offsetWidth; f.classList.add('go');
      renderHud(true);
    }, 1100);
  }
  mpRenderBoard();
}
function mpRenderBoard(note){
  const room = mp.room;
  if (!room || !R) return;
  const i = R.mpIdx, now = srvNow();
  const ans = (room.a && room.a['n' + i]) || {};
  const act = new Set(mpActive(room, now).map(p => p.id));
  const over = !!R.mpOver;
  const ps = mpPlayers(room).filter(p => act.has(p.id) || ans[p.id] || +p.s > 0 || p.id === mp.pid)
    .map(p => Object.assign(p, { s: p.id === mp.pid ? G.score - (R.mpPending ? R.mpPending.pts : 0) : (+p.s || 0) - (!over && ans[p.id] ? +ans[p.id].p || 0 : 0) }))
    .sort((a, b) => b.s - a.s);
  const need = mpActive(room, now).filter(p => !(+p.j > room.at));
  const done = need.filter(p => ans[p.id]).length;
  const last = i + 1 >= G.rounds;
  const head = note || (R.mpOver ? (last ? '最後一首結束，馬上公布名次' : '這首結束 · 下一首馬上開始') : `等其他人作答 · ${done} / ${need.length}`);
  const fast = R.mpOver && ps.length > 1 ? mpFastest(room, i, R.song) : new Set();
  const html = `<li class="mp-head">${esc(head)}</li>` + ps.map(p => {
    const a = ans[p.id];
    let res = R.mpOver ? '<span class="pl-round">沒作答</span>' : '<span class="pl-round">作答中…</span>';
    if (a && !over) res = '<span class="pl-round ok">已作答</span>';
    else if (a) res = +a.k === -2 ? '<span class="pl-round">播不出來</span>' : +a.k === R.song.id ? `<span class="pl-round ok">${fast.has(p.id) ? '🥇' : '✓'} ${(+a.t || 0).toFixed(1)}s · +${fmt((+a.p || 0) + (fast.has(p.id) ? MP_FAST : 0))}</span>` : `<span class="pl-round no">${+a.k === -1 ? '時間到' : +a.p < 0 ? '✗ ' + fmt(+a.p) : '✗ 答錯'}</span>`;
    const rank = 1 + ps.filter(x => x.s > p.s).length;
    return `<li class="pl${p.id === mp.pid ? ' me' : ''}${act.has(p.id) ? '' : ' off'}"><span class="pl-rank">${rank}</span><span class="pl-name">${esc(p.n || '玩家')}${p.id === mp.pid ? '<small>你</small>' : ''}</span>${res}<b class="pl-total">${fmt(p.s)}</b></li>`;
  }).join('');
  if (html !== mp.boardHtml){ mp.boardHtml = html; $('#mp-board').innerHTML = html; }
  $('#mp-board').hidden = false;
  renderHud();
}

/* ---- the host keeps questions coming ---- */
function mpEnsureProducer(){
  if (mp.producer || !G || G.mode !== 'battle') return;
  mp.producer = true;
  const used = Object.values((mp.room && mp.room.q) || {}).map(q => q && q.s).filter(x => x != null);
  G.played = new Set(used);
  const left = BANK.filter(s => G.poolIds.has(s.id) && !G.played.has(s.id));
  G.bag = diverseOrder(left, cryptoRnd, null, new Set(store.get('recent', [])));
}
function mpHostDuties(now){
  const room = mp.room;
  if (!G || G.dead || G.mode !== 'battle') return;
  mpEnsureProducer();
  const i = +room.cur || 0;
  const hasQ = k => !!(room.q && room.q['n' + k]);
  if (!mp.preparing && !mp.noMore && ((i < G.rounds && !hasQ(i)) || (i + 1 < G.rounds && !hasQ(i + 1)))) mpPrepare();
  if (mp.patching) return;
  if (!hasQ(i)){
    if (mp.noMore && !mp.preparing) mpPatchRoom({ st: 'end' });          // ran out of songs that play
    return;
  }
  if (!room.at){ mpPatchRoom({ at: now + MP_LEAD }); return; }
  if (mpRoundOver(room, i, now)){
    const t = mp.overAt[i] || (mp.overAt[i] = now);
    if (now - t < MP_HOLD) return;
    if (i + 1 >= G.rounds || (!hasQ(i + 1) && mp.noMore && !mp.preparing)) mpPatchRoom({ st: 'end' });
    else mpPatchRoom({ cur: i + 1, at: hasQ(i + 1) ? now + MP_LEAD : null });
  }
}
async function mpPrepare(){
  if (mp.preparing) return;
  mp.preparing = true;
  const g = G, code = mp.code;
  try {
    for (let guard = 0; guard < 12; guard++){
      const room = mp.room;
      if (!room || room.st !== 'play' || !mp.isHost || g !== G || g.dead || code !== mp.code) break;
      const i = +room.cur || 0;
      const k = [i, i + 1].find(x => x < g.rounds && !(room.q && room.q['n' + x]));
      if (k == null) break;
      const it = await nextReady();
      if (g !== G || g.dead || code !== mp.code){ if (it) audioPool.release(it.audio); break; }
      if (!it){
        if (g.netError && (mp.netRetry = (mp.netRetry || 0) + 1) <= 3){
          toast('找歌的網路不太順，再試一次…');
          Object.assign(g, { netError: false, audioError: false, netFails: 0, audioFails: 0 });
          await sleep(2500); continue;
        }
        mp.noMore = true; break;
      }
      const now = mp.room;
      if (!now || (now.q && now.q['n' + k])){ g.queue.unshift(it); continue; }   // filled meanwhile by another device
      const opts = buildOptions(it.song, g.nopt, g.diff, cryptoRnd, g.optSeen);
      const info = it.info;
      const q = { s: it.song.id, u: String(info.u).replace(/^http:\/\//, 'https://'), st: it.start, o: opts.map(s => s.id), src: info.src || '', art: info.art || '', th: info.thumb || '', lk: info.link || '' };
      if (Array.isArray(info.alts) && info.alts.length) q.alt = info.alts.slice(0, 2);
      if (it.chorus){ q.ch = 1; q.ce = it.chorus.ce; }
      mp.local[k] = it;
      treeSet(mp.room, `q/n${k}`, q);
      await fbTry(() => fb.put(`rooms/${code}/q/n${k}`, q));
    }
  } catch(e){ toast('房間連線不順，重試中…'); }
  finally { mp.preparing = false; }
}

/* ---- lobby buttons ---- */
async function mpStartGame(){
  const room = mp.room;
  if (!room || !mp.isHost) return;
  const c = room.cfg || {};
  if (poolFor(mpArr(c.cats).length ? mpArr(c.cats) : ['zh'], +c.y0 || MINY, +c.y1 || MAXY).length < MIN_POOL) return toast('題目太少，按「改類別、難度、年代」放寬一點');
  const now = srvNow();
  const upd = { st: 'play', cur: 0, at: null, q: null, a: null, gk: Date.now().toString(36) + Math.floor(cryptoRnd() * 1e6).toString(36), ts: SV_TS };
  mpPlayers(room).forEach(p => {
    if (p.id !== mp.pid && now - (+p.hb || 0) > MP_STALE) upd[`p/${p.id}`] = null;   // drop players who already left
    else { upd[`p/${p.id}/s`] = 0; upd[`p/${p.id}/c`] = 0; }
  });
  await mpPatchRoom(upd);
}
function mpStartButton(){
  if (!mp.code) return mpCreate();
  const room = mp.room;
  if (mp.isHost && room && room.st === 'lobby'){
    const cfg = mpCfgFromSettings();
    mpPatchRoom({ cfg });
  }
  show(room && room.st === 'play' ? 'game' : 'lobby');
  mpRender();
}
function mpAgain(){
  if (!mp.code) return goHome();
  if (mp.isHost) mpPatchRoom({ st: 'lobby', cur: 0, at: null, q: null, a: null });
  show('lobby');
  mpRender();
}
function mpShowFinal(){
  if (mp.finalShown) return;
  mp.finalShown = true;
  const room = mp.room, g = G;
  g.dead = true;
  stopPlayback(); stopTimer();
  g.queue.forEach(q => audioPool.release(q.audio)); g.queue = [];
  const now = srvNow();
  const act = new Set(mpActive(room, now).map(p => p.id));
  const ps = mpPlayers(room).filter(p => act.has(p.id) || +p.s > 0 || +p.c > 0 || p.id === mp.pid)
    .map(p => Object.assign(p, { s: p.id === mp.pid ? g.score : +p.s || 0, c: p.id === mp.pid ? g.correct : +p.c || 0, tt: p.id === mp.pid ? g.mpTime || 0 : +p.tt || 0 }));
  const better = (x, p) => x.s > p.s || (x.s === p.s && (x.c > p.c || (x.c === p.c && x.tt < p.tt)));   // tie: more right, then faster
  ps.sort((a, b) => better(a, b) ? -1 : better(b, a) ? 1 : 0);
  const rankOf = p => 1 + ps.filter(x => better(x, p)).length;
  const me = ps.find(p => p.id === mp.pid) || { s: g.score, c: g.correct };
  const myRank = rankOf(me), many = ps.length > 1;
  $('#res-kicker').textContent = `好友對戰 · ${room.nm ? room.nm + ' · ' : ''}房號 ${mp.code} · ${MP_DIFF[g.diff].name} · ${g.rounds} 首`;
  $('#res-rank').textContent = !many ? '試玩完成' : myRank === 1 ? '冠軍！🏆' : `第 ${myRank} 名`;
  $('#res-rank-sub').textContent = !many ? '找朋友進房間一起比吧。' : myRank === 1 ? '耳朵最靈的就是你。' : myRank === ps.length ? '下一局一定扳回來！' : '差一點點，再來一局！';
  $('#res-newrec').innerHTML = '';
  $('#res-grid').textContent = g.history.map(h => h.emoji).join('');
  const okTimes = g.history.filter(h => h.ok).map(h => h.time);
  const avgT = okTimes.length ? okTimes.reduce((a, b) => a + b, 0) / okTimes.length : 0;
  $('#res-stats').innerHTML = [[`${myRank}/${ps.length}`, '名次'], [`${g.correct}/${g.history.length || g.rounds}`, '答對'], [okTimes.length ? avgT.toFixed(1) + 's' : '–', '平均答對秒數']]
    .map(([b, s]) => `<div class="stat"><b>${b}</b><small>${s}</small></div>`).join('');
  $('#btn-share').hidden = true;
  const medal = r => r === 1 ? '🥇' : r === 2 ? '🥈' : r === 3 ? '🥉' : r;
  $('#res-board').innerHTML = ps.map(p => `<li class="pl${p.id === mp.pid ? ' me' : ''}"><span class="pl-rank">${medal(rankOf(p))}</span><span class="pl-name">${esc(p.n || '玩家')}${p.id === mp.pid ? '<small>你</small>' : ''}</span><span class="pl-round">答對 ${p.c} 首</span><b class="pl-total">${fmt(p.s)}</b></li>`).join('');
  $('#res-board-wrap').hidden = false;
  $('#daily-board-wrap').hidden = true;
  $('#res-list').innerHTML = g.history.map((h, i) => `
    <li class="song">
      ${h.info.thumb ? `<img src="${esc(h.info.thumb)}" alt="" loading="lazy">` : '<span class="noart"></span>'}
      <div class="info"><b>${esc(h.song.title)}</b><small>${esc(h.song.artist)} · ${h.song.year}${h.info.link ? ` · <a href="${esc(h.info.link)}" target="_blank" rel="noopener">${esc(h.info.src)} ↗</a>` : ''}</small></div>
      <span class="mark">${h.emoji}</span>
      <button class="play" data-i="${i}" aria-label="重聽">▶</button>
    </li>`).join('');
  $('#btn-again').textContent = mp.isHost ? '再來一局（同一個房間）' : '回房間等下一局';
  $('#btn-home').textContent = '離開房間';
  const recent = store.get('recent', []).filter(id => !g.history.some(h => h.song.id === id));
  store.set('recent', [...g.history.map(h => h.song.id), ...recent].slice(0, 150));
  hideModal();
  show('result');
  countUp($('#res-score'), g.score);
  if (many && myRank === 1) sfx.up();
}

/* check once that the database answers and its rules let rooms through */
let mpChecked = null;
function mpCheckDb(){
  if (!FB || mpChecked) return;
  mpChecked = 'checking';
  fetch(fb.url('rooms/ZZZZ'), { cache: 'no-store' }).then(async r => {
    if (r.ok){ mpChecked = 'ok'; return; }
    const t = await r.text().catch(() => '');
    mpChecked = 'bad';
    $('#mp-off').hidden = false;
    $('#mp-off').textContent = /permission/i.test(t) || r.status === 401 ? '線上資料庫拒絕存取：Firebase 的「規則」還沒貼上對戰用的規則，房主請照設定說明貼上後按「發布」。' : `線上資料庫回應錯誤（${r.status}），稍後再試。`;
  }).catch(() => { mpChecked = null; $('#mp-off').hidden = false; $('#mp-off').textContent = '連不上線上資料庫，請確認網路後再試。'; });
}
$('#mp-join').addEventListener('click', () => { sfx.init(); audioPool.unlock(); mpJoin($('#mp-code').value); });
$('#mp-code').addEventListener('keydown', e => { if (e.key === 'Enter'){ e.preventDefault(); $('#mp-join').click(); } });
$('#mp-room').addEventListener('change', () => store.set('mpRoomName', ($('#mp-room').value || '').trim()));
$('#mp-name').addEventListener('change', () => { const v = $('#mp-name').value.trim().slice(0, 12); if (v) store.set('mpName', v); });
$('#lb-start').addEventListener('click', () => { sfx.init(); audioPool.unlock(); mpStartGame(); });
$('#lb-edit').addEventListener('click', () => { settings.mode = 'battle'; saveSettings(); show('home'); });
$('#lb-leave').addEventListener('click', () => { mpLeave(); goHome(); });
$('#lb-diff').addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b || !mp.isHost || !mp.room) return;
  const d = b.dataset.d; if (!MP_DIFF[d]) return;
  store.set('mpDiff', d);
  mpPatchRoom({ 'cfg/diff': d, 'cfg/n': MP_DIFF[d].n, 'cfg/t': MP_DIFF[d].t }); mpRender();
});
$('#lb-rounds').addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b || !mp.isHost || !mp.room) return;
  const r = +b.dataset.r; store.set('mpRounds', r);
  mpPatchRoom({ 'cfg/r': r }); mpRender();
});
$('#lb-share').addEventListener('click', async () => {
  const link = mpLink(mp.code);
  const nm = mp.room && mp.room.nm;
  const text = `來玩「耳熟能詳」猜歌對戰！${nm ? `房間「${nm}」，` : ''}房號 ${mp.code}\n${link}`;
  if (navigator.share){ try { await navigator.share({ title: '耳熟能詳 · 好友對戰', text, url: link }); return; } catch(e){ if (e && e.name === 'AbortError') return; } }
  let ok = false;
  try { await navigator.clipboard.writeText(text); ok = true; } catch(e){
    const ta = document.createElement('textarea'); ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0'; document.body.appendChild(ta); ta.select();
    try { ok = document.execCommand('copy'); } catch(e2){} ta.remove();
  }
  toast(ok ? '邀請連結已複製，貼給朋友！' : '複製失敗，直接把房號 ' + mp.code + ' 告訴朋友');
});
/* opened from an invite link (or reloaded while in a room): fill in the room number */
{
  $('#mp-name').value = store.get('mpName', '');
  $('#mp-room').value = store.get('mpRoomName', '');
  let code = '';
  try { code = (new URLSearchParams(location.search).get('room') || sessionStorage.getItem('erg_mp_room') || '').toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 4); } catch(e){}
  if (code && FB){
    settings.mode = 'battle'; store.set('settings', settings);
    $('#mp-code').value = code;
    setTimeout(() => { $('#battle-wrap').scrollIntoView({ block: 'center', behavior: 'smooth' }); toast(`房號 ${code}：填好暱稱後按「加入房間」`); if (!$('#mp-name').value) $('#mp-name').focus(); }, 400);
  }
}

/* ================= 每日挑戰排行榜 =================
   Everyone gets the same 5 songs each day, so the first try of the day can go on a shared board:
   board/YYYYMMDD_DEVICE = { n name, s score, c correct, g emoji grid, ts }. Entries can't be overwritten. */
function devId(){
  let id = store.get('devId', '');
  if (!/^d[a-z0-9]{8,20}$/.test(id)){ id = 'd' + Array.from(crypto.getRandomValues(new Uint8Array(10)), b => (b % 36).toString(36)).join(''); store.set('devId', id); }
  return id;
}
const dayKey = dk => String(dk).replace(/-/g, '');
const daily = { cache: {}, at: {} };
async function dailyFetch(dk, fresh){
  const k = dayKey(dk);
  if (!fresh && daily.cache[k] && Date.now() - daily.at[k] < 30000) return daily.cache[k];
  const q = `orderBy=${encodeURIComponent('"$key"')}&startAt=${encodeURIComponent(`"${k}_"`)}&endAt=${encodeURIComponent(`"${k}_~"`)}`;
  const r = await fetch(`${FB}/board.json?${q}`, { cache: 'no-store' });
  if (!r.ok) throw new Error('http ' + r.status);
  const v = await r.json();
  const list = Object.entries(v || {}).filter(([, e]) => e && typeof e === 'object')
    .map(([id, e]) => ({ id, n: [...String(e.n || '')].slice(0, 12).join(''), s: +e.s || 0, c: +e.c || 0, g: [...String(e.g || '')].slice(0, 10).join('') }))
    .filter(e => e.n && e.s >= 0 && e.s <= 20000)                      // drop anything no real game can score
    .sort((a, b) => b.s - a.s || b.c - a.c);
  daily.cache[k] = list; daily.at[k] = Date.now();
  return list;
}
function dailyRows(list, mine, top){
  const rankOf = e => 1 + list.filter(x => x.s > e.s || (x.s === e.s && x.c > e.c)).length;
  const medal = r => r === 1 ? '🥇' : r === 2 ? '🥈' : r === 3 ? '🥉' : r;
  const rows = list.slice(0, top);
  const me = list.find(e => e.id === mine);
  if (me && !rows.includes(me)) rows.push(me);
  return rows.map(e => `<li class="pl${e.id === mine ? ' me' : ''}"><span class="pl-rank">${medal(rankOf(e))}</span><span class="pl-name">${esc(e.n)}${e.id === mine ? '<small>你</small>' : ''}</span><span class="pl-round">${esc(e.g)} ${e.c}/5</span><b class="pl-total">${fmt(e.s)}</b></li>`).join('');
}
async function dailyShow(el, dk, top, note, fresh){
  if (!FB){ el.hidden = true; return; }
  const mine = dayKey(dk) + '_' + devId();
  try {
    const list = await dailyFetch(dk, fresh);
    el.innerHTML = list.length ? `<li class="mp-head">${esc(note)} · ${list.length} 人</li>` + dailyRows(list, mine, top) : `<li class="mp-head">${esc(note)} · 今天還沒有人上榜</li>`;
  } catch(e){ el.innerHTML = '<li class="mp-head">排行榜暫時讀不到</li>'; }
  el.hidden = false;
}
function dailyHome(){
  const el = $('#home-daily-board');
  if (settings.mode !== 'daily' || !FB){ el.hidden = true; return; }
  dailyShow(el, todayKey(), 5, '今日排行榜');
}
function dailyResult(g){
  const wrap = $('#daily-board-wrap');
  if (!g.daily || !FB){ wrap.hidden = true; return; }
  wrap.hidden = false;
  const rec = store.get('daily_' + g.dateKey, null);
  const done = store.get('dailyUp_' + g.dateKey, false);
  $('#daily-name').value = store.get('mpName', '');
  $('#daily-submit').hidden = !rec || done;
  $('#daily-first').hidden = !rec || done || (rec.score === g.score && rec.correct === g.correct);
  dailyShow($('#daily-board'), g.dateKey, 10, '今日排行榜', true);
}
$('#btn-daily-submit').addEventListener('click', async () => {
  const g = G; if (!g || !g.daily) return;
  const rec = store.get('daily_' + g.dateKey, null); if (!rec) return;
  const n = [...($('#daily-name').value || '').normalize('NFKC').trim().replace(/\s+/g, ' ')].slice(0, 12).join('');
  if (!n){ toast('先輸入暱稱'); $('#daily-name').focus(); return; }
  store.set('mpName', n);
  const btn = $('#btn-daily-submit'); btn.disabled = true;
  try {
    await fb.put(`board/${dayKey(g.dateKey)}_${devId()}`, { n, s: rec.score, c: rec.correct, g: rec.grid || '', ts: SV_TS });
    store.set('dailyUp_' + g.dateKey, true); toast('上榜了！');
  } catch(e){
    if (/401|403/.test(String(e.message))){ store.set('dailyUp_' + g.dateKey, true); toast('這台裝置今天已經上傳過了'); }
    else toast('上傳失敗，請確認網路後再試');
  }
  btn.disabled = false;
  $('#daily-submit').hidden = !!store.get('dailyUp_' + g.dateKey, false);
  dailyShow($('#daily-board'), g.dateKey, 10, '今日排行榜', true);
});
