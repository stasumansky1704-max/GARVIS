import * as THREE from "three";

/**
 * Procedural canvas textures for the chamber surfaces — no external assets.
 * - brushed-metal albedo with vertical streaks + a soft vertical gradient
 * - emissive panel map: tech rectangles / lines that glow on the wall panels
 * Cached as singletons so every wall shares one GPU upload.
 */

let _brushed: THREE.CanvasTexture | null = null;
let _panelEmissive: THREE.CanvasTexture | null = null;
let _panelEmissiveB: THREE.CanvasTexture | null = null;

export function brushedMetal(): THREE.CanvasTexture {
  if (_brushed) return _brushed;
  const c = document.createElement("canvas");
  c.width = 256;
  c.height = 512;
  const ctx = c.getContext("2d")!;

  // base vertical gradient (brighter mid, darker edges) so the metal isn't flat
  const g = ctx.createLinearGradient(0, 0, 0, 512);
  g.addColorStop(0, "#16273a");
  g.addColorStop(0.5, "#33597b");
  g.addColorStop(0.75, "#274761");
  g.addColorStop(1, "#0f1f30");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 256, 512);

  // vertical brushed streaks
  for (let i = 0; i < 900; i++) {
    const x = Math.random() * 256;
    const len = 40 + Math.random() * 360;
    const y = Math.random() * 512;
    const a = Math.random() * 0.06;
    ctx.strokeStyle =
      Math.random() > 0.5 ? `rgba(180,210,235,${a})` : `rgba(8,16,26,${a})`;
    ctx.lineWidth = Math.random() * 1.2;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + (Math.random() - 0.5) * 2, y + len);
    ctx.stroke();
  }

  // a few horizontal seam lines (panel divisions)
  for (let y = 40; y < 512; y += 64 + Math.random() * 30) {
    ctx.strokeStyle = "rgba(6,12,20,0.5)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(256, y);
    ctx.stroke();
    ctx.strokeStyle = "rgba(120,200,235,0.06)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, y + 2);
    ctx.lineTo(256, y + 2);
    ctx.stroke();
  }

  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.anisotropy = 4;
  _brushed = tex;
  return tex;
}

function makePanelEmissive(seed: number): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = 128;
  c.height = 256;
  const ctx = c.getContext("2d")!;
  ctx.fillStyle = "#020a12";
  ctx.fillRect(0, 0, 128, 256);

  // pseudo-random but deterministic
  let s = seed * 9973;
  const rnd = () => {
    s = (s * 1103515245 + 12345) & 0x7fffffff;
    return s / 0x7fffffff;
  };

  // glowing tech rectangles / bars (asymmetric, varies per seed)
  const n = 5 + Math.floor(rnd() * 5);
  for (let i = 0; i < n; i++) {
    const x = 12 + rnd() * 80;
    const y = 10 + rnd() * 220;
    const w = 10 + rnd() * 90;
    const h = 3 + rnd() * 10;
    const hot = rnd() > 0.7;
    ctx.fillStyle = hot ? "rgba(150,225,255,0.95)" : "rgba(50,150,200,0.7)";
    ctx.fillRect(x, y, w, h);
  }
  // a couple of bright accent dots
  for (let i = 0; i < 4; i++) {
    ctx.fillStyle = "rgba(190,235,255,0.9)";
    ctx.beginPath();
    ctx.arc(14 + rnd() * 100, 14 + rnd() * 228, 2 + rnd() * 2, 0, Math.PI * 2);
    ctx.fill();
  }
  // thin vertical data line
  const lx = 20 + rnd() * 88;
  ctx.strokeStyle = "rgba(80,200,240,0.5)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(lx, 12);
  ctx.lineTo(lx, 244);
  ctx.stroke();

  const tex = new THREE.CanvasTexture(c);
  return tex;
}

export function panelEmissiveA(): THREE.CanvasTexture {
  if (!_panelEmissive) _panelEmissive = makePanelEmissive(3);
  return _panelEmissive;
}
export function panelEmissiveB(): THREE.CanvasTexture {
  if (!_panelEmissiveB) _panelEmissiveB = makePanelEmissive(11);
  return _panelEmissiveB;
}

/* ---------------- night-city skyline (seen through the wall windows) ---------------- */

let _city: THREE.CanvasTexture | null = null;

export function nightCity(): THREE.CanvasTexture {
  if (_city) return _city;
  const W = 1024;
  const H = 512;
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const ctx = c.getContext("2d")!;

  // deep blue atmospheric sky + horizon glow
  const sky = ctx.createLinearGradient(0, 0, 0, H);
  sky.addColorStop(0, "#02060e");
  sky.addColorStop(0.55, "#04223a");
  sky.addColorStop(0.78, "#0a4d72");
  sky.addColorStop(1, "#0b2c44");
  ctx.fillStyle = sky;
  ctx.fillRect(0, 0, W, H);

  // soft atmospheric haze band near the horizon
  const haze = ctx.createLinearGradient(0, H * 0.6, 0, H);
  haze.addColorStop(0, "rgba(40,150,210,0)");
  haze.addColorStop(1, "rgba(40,150,210,0.35)");
  ctx.fillStyle = haze;
  ctx.fillRect(0, H * 0.6, W, H * 0.4);

  let s = 1337;
  const rnd = () => {
    s = (s * 1103515245 + 12345) & 0x7fffffff;
    return s / 0x7fffffff;
  };

  // building layers: far (dim) -> near (brighter), for depth
  const layers = [
    { count: 46, minH: 60, maxH: 150, base: "#06223a", lit: 0.1, y: H * 0.62 },
    { count: 38, minH: 110, maxH: 240, base: "#082d4c", lit: 0.16, y: H * 0.66 },
    { count: 30, minH: 170, maxH: 340, base: "#0b3a5e", lit: 0.22, y: H * 0.72 },
  ];

  for (const L of layers) {
    let x = -20;
    while (x < W + 20) {
      const bw = 14 + rnd() * 46;
      const bh = L.minH + rnd() * (L.maxH - L.minH);
      const top = L.y - bh;
      // building body
      ctx.fillStyle = L.base;
      ctx.fillRect(x, top, bw, bh);
      // subtle right-edge shade
      ctx.fillStyle = "rgba(0,0,0,0.25)";
      ctx.fillRect(x + bw - 3, top, 3, bh);

      // lit windows grid
      const cols = Math.max(1, Math.floor(bw / 7));
      const rows = Math.max(1, Math.floor(bh / 9));
      for (let cx = 0; cx < cols; cx++) {
        for (let cy = 0; cy < rows; cy++) {
          if (rnd() < L.lit) {
            const wx = x + 3 + cx * 7;
            const wy = top + 4 + cy * 9;
            const warm = rnd() > 0.78;
            ctx.fillStyle = warm
              ? `rgba(255,220,150,${0.5 + rnd() * 0.5})`
              : `rgba(150,225,255,${0.5 + rnd() * 0.5})`;
            ctx.fillRect(wx, wy, 3, 4);
          }
        }
      }
      // occasional rooftop beacon
      if (rnd() > 0.9) {
        ctx.fillStyle = "rgba(255,120,120,0.9)";
        ctx.fillRect(x + bw / 2 - 1, top - 3, 2, 3);
      }
      x += bw + 3 + rnd() * 10;
    }
  }

  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  _city = tex;
  return tex;
}
