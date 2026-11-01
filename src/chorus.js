/* Chorus finder for a 30-second preview (runs in the browser; also loaded by the Node tests).
   Looks for the stretch that is loud, full and melodically repeated (what a chorus is), snaps
   its start to the section change where the music lifts, and reports how sure it is.
   Returns null when the preview is too short, or { cs, ce, conf, contrast, rep } in seconds. */
function findChorus(ab){
  const sr = ab.sampleRate, n = ab.length, C = ab.numberOfChannels;
  const x = new Float32Array(n);
  for (let c = 0; c < C; c++){ const d = ab.getChannelData(c); for (let i = 0; i < n; i++) x[i] += d[i] / C; }
  const N = 2048, half = N / 2, hop = Math.round(sr * .1);
  const F = Math.floor((n - N) / hop) + 1;
  if (F < 100) return null;
  // ---- FFT tables ----
  const win = new Float32Array(N), rev = new Uint32Array(N), cosT = new Float32Array(half), sinT = new Float32Array(half);
  for (let i = 0; i < N; i++) win[i] = .5 - .5 * Math.cos(2 * Math.PI * i / (N - 1));
  for (let i = 0, bits = Math.log2(N); i < N; i++){ let r = 0; for (let b = 0; b < bits; b++) r |= ((i >> b) & 1) << (bits - 1 - b); rev[i] = r; }
  for (let i = 0; i < half; i++){ cosT[i] = Math.cos(2 * Math.PI * i / N); sinT[i] = -Math.sin(2 * Math.PI * i / N); }
  const re = new Float32Array(N), im = new Float32Array(N);
  function fft(){
    for (let i = 0; i < N; i++){ const j = rev[i]; if (j > i){ let t = re[i]; re[i] = re[j]; re[j] = t; t = im[i]; im[i] = im[j]; im[j] = t; } }
    for (let size = 2; size <= N; size <<= 1){
      const h = size >> 1, step = N / size;
      for (let s = 0; s < N; s += size) for (let k = 0; k < h; k++){
        const wr = cosT[k * step], wi = sinT[k * step], a = s + k, b = a + h;
        const tr = re[b] * wr - im[b] * wi, ti = re[b] * wi + im[b] * wr;
        re[b] = re[a] - tr; im[b] = im[a] - ti; re[a] += tr; im[a] += ti;
      }
    }
  }
  const pc = new Int8Array(half).fill(-1);
  for (let k = 1; k < half; k++){ const f = k * sr / N; if (f >= 80 && f <= 4000) pc[k] = ((Math.round(12 * Math.log2(f / 440)) % 12) + 12) % 12; }
  // ---- frame features: loudness (dB), spectral flux (fullness / drive), chroma (melody & harmony) ----
  const loud = new Float32Array(F), flux = new Float32Array(F), chroma = new Float32Array(F * 12), prev = new Float32Array(half);
  for (let f = 0; f < F; f++){
    const o = f * hop; let e = 0;
    for (let i = 0; i < N; i++){ const v = x[o + i] || 0; e += v * v; re[i] = v * win[i]; im[i] = 0; }
    fft();
    let fl = 0;
    for (let k = 1; k < half; k++){
      const m = Math.sqrt(re[k] * re[k] + im[k] * im[k]);
      const d = m - prev[k]; if (d > 0) fl += d; prev[k] = m;
      if (pc[k] >= 0) chroma[f * 12 + pc[k]] += m;
    }
    loud[f] = 10 * Math.log10(e / N + 1e-10); flux[f] = fl;
  }
  // ---- pool into half-second blocks ----
  const P = 5, B = Math.floor(F / P);
  const E = new Float32Array(B), X = new Float32Array(B), Ch = new Float32Array(B * 12);
  for (let b = 0; b < B; b++){
    let e = 0, fl = 0;
    for (let k = 0; k < P; k++){ const f = b * P + k; e += loud[f]; fl += flux[f]; for (let j = 0; j < 12; j++) Ch[b * 12 + j] += chroma[f * 12 + j]; }
    E[b] = e / P; X[b] = Math.log(1 + fl / P);
    let nrm = 0; for (let j = 0; j < 12; j++) nrm += Ch[b * 12 + j] ** 2; nrm = Math.sqrt(nrm) || 1;
    for (let j = 0; j < 12; j++) Ch[b * 12 + j] /= nrm;
  }
  const dot = (a, b) => { let s = 0; for (let j = 0; j < 12; j++) s += Ch[a * 12 + j] * Ch[b * 12 + j]; return s; };
  // ---- repetition: how strongly each moment recurs 4–15 s later or earlier ----
  const seg = 6, Rp = new Float32Array(B);
  for (let L = 8; L <= Math.min(30, B - seg - 1); L++){
    for (let i = 0; i + L + seg <= B; i++){
      let s = 0; for (let k = 0; k < seg; k++) s += dot(i + k, i + L + k); s /= seg;
      for (let k = 0; k < seg; k++){ if (s > Rp[i + k]) Rp[i + k] = s; if (s > Rp[i + L + k]) Rp[i + L + k] = s; }
    }
  }
  const lo = 2, hi = B - 2;                                   // skip the ~1 s fade at each end
  const stats = (A, a = lo, b = hi) => { let m = 0, c = 0; for (let k = a; k < b; k++){ m += A[k]; c++; } m /= c || 1; let v = 0; for (let k = a; k < b; k++) v += (A[k] - m) ** 2; return [m, Math.sqrt(v / (c || 1)) || 1]; };
  const [mE, sE] = stats(E), [mR, sR] = stats(Rp), [mX, sX] = stats(X);
  // ---- section boundaries: where loudness, fullness or harmony change most (2 s either side) ----
  const meanOf = (A, a, b) => { a = Math.max(lo, a); b = Math.min(hi, b); let m = 0; for (let k = a; k < b; k++) m += A[k]; return b > a ? m / (b - a) : 0; };
  const chordOf = (a, b) => { const v = new Float32Array(12); for (let k = Math.max(lo, a); k < Math.min(hi, b); k++) for (let j = 0; j < 12; j++) v[j] += Ch[k * 12 + j]; let n2 = 0; for (let j = 0; j < 12; j++) n2 += v[j] * v[j]; n2 = Math.sqrt(n2) || 1; for (let j = 0; j < 12; j++) v[j] /= n2; return v; };
  const nov = new Float32Array(B);
  for (let b = lo + 4; b <= hi - 4; b++){
    const dE = meanOf(E, b, b + 4) - meanOf(E, b - 4, b), dX = (meanOf(X, b, b + 4) - meanOf(X, b - 4, b)) / sX;
    const c1 = chordOf(b - 4, b), c2 = chordOf(b, b + 4); let cs = 0; for (let j = 0; j < 12; j++) cs += c1[j] * c2[j];
    nov[b] = Math.abs(dE) / 2 + Math.abs(dX) + 3 * (1 - cs);
  }
  const cand = [];
  for (let b = lo + 4; b <= hi - 4; b++) if (nov[b] > 0 && nov[b] >= nov[b - 1] && nov[b] >= nov[b + 1]) cand.push(b);
  cand.sort((p, q) => nov[q] - nov[p]);
  const [mN, sN] = stats(nov, lo + 4, hi - 3);
  const cuts = [];
  for (const b of cand){ if (nov[b] < mN + .15 * sN || cuts.length >= 5) break; if (cuts.every(c => Math.abs(c - b) >= 6)) cuts.push(b); }
  cuts.push(lo, hi); cuts.sort((p, q) => p - q);
  // ---- pick the section that is loudest, fullest and most repeated ----
  const segs = [];
  for (let i = 0; i + 1 < cuts.length; i++){
    const a = cuts[i], b = cuts[i + 1];
    if (b - a < 6) continue;                                    // shorter than 3 s
    segs.push({ a, b, e: meanOf(E, a, b), x: meanOf(X, a, b), r: meanOf(Rp, a, b) });
  }
  if (!segs.length) return null;
  for (const g of segs) g.score = (g.e - mE) / sE + .5 * (g.x - mX) / sX + .4 * (g.r - mR) / sR;
  const best = segs.reduce((p, q) => q.score > p.score ? q : p);
  // ---- strict confidence: only accept a chorus we can actually see begin ----
  const others = segs.filter(g => g !== best);
  let oe = 0, ow = 0; for (const g of others){ oe += g.e * (g.b - g.a); ow += g.b - g.a; }
  const contrast = ow ? best.e - oe / ow : 0;
  const lift = best.a > lo ? meanOf(E, best.a, best.a + 4) - meanOf(E, best.a - 4, best.a) : 0;     // the jump where it kicks in
  const clearlyLoudest = others.length > 0 && others.every(g => best.e - g.e >= 1 && best.x >= g.x - .05);
  const longEnough = (best.b - best.a) >= (best.b >= hi ? 8 : 10);                                   // ≥ 4–5 s of it in the preview
  const drop = best.b < hi - 2 ? meanOf(E, best.b - 4, best.b) - meanOf(E, best.b, best.b + 4) : 0;   // the fall where it ends
  const buildUp = hi - best.b >= 2 && meanOf(E, best.b, hi) > best.e + .5;                           // something louder follows: a build-up
  const seenStart = best.a > lo + 1 && lift >= 1.5;                       // we can hear the chorus kick in
  const seenEnd = best.a <= lo + 1 && drop >= 1.5 && best.b - best.a >= 10; // preview opens inside the chorus and we hear it end
  const conf = seenStart && clearlyLoudest && contrast >= 1.5 && longEnough && !buildUp;      // (seenEnd alone proved unreliable)
  const start = best.a;
  return { cs: Math.round(start * P) / 10, ce: Math.round(best.b * P) / 10, conf, contrast: Math.round(contrast * 10) / 10, lift: Math.round(lift * 10) / 10, rep: Math.round(best.r * 100) / 100, sections: segs.length };
}
if (typeof module !== 'undefined') module.exports = { findChorus };
