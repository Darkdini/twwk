/* Генератор капчи: PNG с 4-значным кодом, без внешних зависимостей. */
'use strict';
const zlib = require('zlib');

// 5x7 шрифт цифр
const FONT = {
  '0': ['01110','10001','10011','10101','11001','10001','01110'],
  '1': ['00100','01100','00100','00100','00100','00100','01110'],
  '2': ['01110','10001','00001','00010','00100','01000','11111'],
  '3': ['11111','00010','00100','00010','00001','10001','01110'],
  '4': ['00010','00110','01010','10010','11111','00010','00010'],
  '5': ['11111','10000','11110','00001','00001','10001','01110'],
  '6': ['00110','01000','10000','11110','10001','10001','01110'],
  '7': ['11111','00001','00010','00100','01000','01000','01000'],
  '8': ['01110','10001','10001','01110','10001','10001','01110'],
  '9': ['01110','10001','10001','01111','00001','00010','01100'],
};

// CRC32
const CRC = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; }
  return t;
})();
function crc32(buf) { let c = 0xffffffff; for (let i = 0; i < buf.length; i++) c = CRC[(c ^ buf[i]) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; }

function pngEncode(width, height, rgb) {
  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const chunk = (type, data) => {
    const len = Buffer.alloc(4); len.writeUInt32BE(data.length, 0);
    const t = Buffer.from(type);
    const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(Buffer.concat([t, data])), 0);
    return Buffer.concat([len, t, data, crc]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0); ihdr.writeUInt32BE(height, 4); ihdr[8] = 8; ihdr[9] = 2; // RGB 8bit
  const stride = width * 3 + 1;
  const raw = Buffer.alloc(stride * height);
  for (let y = 0; y < height; y++) { raw[y * stride] = 0; rgb.copy(raw, y * stride + 1, y * width * 3, (y + 1) * width * 3); }
  const idat = zlib.deflateSync(raw);
  return Buffer.concat([sig, chunk('IHDR', ihdr), chunk('IDAT', idat), chunk('IEND', Buffer.alloc(0))]);
}

function makeCaptcha(len = 4) {
  let code = '';
  for (let i = 0; i < len; i++) code += String(Math.floor(Math.random() * 10));
  const S = 7, GAP = 2, MX = 8, MY = 8;
  const cw = 5 * S + GAP * S, W = MX * 2 + len * cw, H = MY * 2 + 7 * S;
  const rgb = Buffer.alloc(W * H * 3);
  // фон светлый
  for (let i = 0; i < W * H; i++) { rgb[i * 3] = 230; rgb[i * 3 + 1] = 226; rgb[i * 3 + 2] = 214; }
  const set = (x, y, r, g, b) => { if (x < 0 || y < 0 || x >= W || y >= H) return; const o = (y * W + x) * 3; rgb[o] = r; rgb[o + 1] = g; rgb[o + 2] = b; };
  // шумовые точки
  for (let i = 0; i < W * H / 12; i++) set((Math.random() * W) | 0, (Math.random() * H) | 0, 150 + Math.random() * 60 | 0, 100, 80);
  // цифры
  for (let i = 0; i < len; i++) {
    const g = FONT[code[i]]; const ox = MX + i * cw + (S * Math.random() | 0); const oy = MY + (S * (Math.random() - 0.5) | 0);
    const col = [120 + (Math.random() * 60 | 0), 30, 20];
    for (let r = 0; r < 7; r++) for (let c = 0; c < 5; c++) if (g[r][c] === '1')
      for (let sy = 0; sy < S; sy++) for (let sx = 0; sx < S; sx++) set(ox + c * S + sx, oy + r * S + sy, col[0], col[1], col[2]);
  }
  return { code, img: pngEncode(W, H, rgb).toString('base64') };
}

module.exports = { makeCaptcha };
