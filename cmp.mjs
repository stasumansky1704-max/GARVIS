import fs from "node:fs";
import zlib from "node:zlib";

function decode(file) {
  const buf = fs.readFileSync(file);
  let pos = 8, width, height, colorType;
  const idat = [];
  while (pos < buf.length) {
    const len = buf.readUInt32BE(pos);
    const type = buf.toString("ascii", pos + 4, pos + 8);
    const data = buf.subarray(pos + 8, pos + 8 + len);
    if (type === "IHDR") { width = data.readUInt32BE(0); height = data.readUInt32BE(4); colorType = data[9]; }
    else if (type === "IDAT") idat.push(data);
    else if (type === "IEND") break;
    pos += 12 + len;
  }
  const ch = colorType === 6 ? 4 : 3;
  const raw = zlib.inflateSync(Buffer.concat(idat));
  const stride = width * ch;
  const out = Buffer.alloc(height * stride);
  let p = 0;
  const paeth = (a, b, c) => { const q = a + b - c, pa = Math.abs(q - a), pb = Math.abs(q - b), pc = Math.abs(q - c); return pa <= pb && pa <= pc ? a : pb <= pc ? b : c; };
  for (let y = 0; y < height; y++) {
    const f = raw[p++];
    for (let x = 0; x < stride; x++) {
      const v = raw[p++];
      const a = x >= ch ? out[y * stride + x - ch] : 0;
      const b = y > 0 ? out[(y - 1) * stride + x] : 0;
      const c = x >= ch && y > 0 ? out[(y - 1) * stride + x - ch] : 0;
      let r;
      switch (f) { case 0: r = v; break; case 1: r = v + a; break; case 2: r = v + b; break; case 3: r = v + ((a + b) >> 1); break; case 4: r = v + paeth(a, b, c); break; default: r = v; }
      out[y * stride + x] = r & 0xff;
    }
  }
  return { out, width, height, ch };
}

function region(img, x0, y0, x1, y1) {
  const { out, width, height, ch } = img;
  let R = 0, G = 0, B = 0, n = 0, bright = 0, cyan = 0, mx = 0;
  for (let y = Math.floor(y0 * height); y < y1 * height; y += 2)
    for (let x = Math.floor(x0 * width); x < x1 * width; x += 2) {
      const i = y * (width * ch) + x * ch;
      const r = out[i], g = out[i + 1], b = out[i + 2];
      R += r; G += g; B += b; n++;
      const L = (r + g + b) / 3; if (L > mx) mx = L;
      if (L > 130) bright++;
      if (b > 70 && b >= r + 18 && g >= r + 8) cyan++;
    }
  return { lum: Math.round((R + G + B) / (3 * n)), max: Math.round(mx), brightPct: +(100 * bright / n).toFixed(1), cyanPct: +(100 * cyan / n).toFixed(1) };
}

for (const f of process.argv.slice(2)) {
  const img = decode(f);
  console.log(`\n=== ${f} (${img.width}x${img.height}) ===`);
  console.log("CORE_CENTER ", region(img, 0.43, 0.30, 0.57, 0.62));
  console.log("PORTAL_RING ", region(img, 0.36, 0.22, 0.64, 0.70));
  console.log("LEFT_WALL   ", region(img, 0.02, 0.20, 0.20, 0.75));
  console.log("RIGHT_WALL  ", region(img, 0.80, 0.20, 0.98, 0.75));
  console.log("FLOOR_REFL  ", region(img, 0.30, 0.70, 0.70, 0.92));
  console.log("FULL        ", region(img, 0, 0, 1, 1));
}
