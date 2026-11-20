// Code 128 symbol widths from ISO/IEC 15417, indexed by symbol value.
const patterns = `
212222 222122 222221 121223 121322 131222 122213 122312 132212 221213
221312 231212 112232 122132 122231 113222 123122 123221 223211 221132
221231 213212 223112 312131 311222 321122 321221 312212 322112 322211
212123 212321 232121 111323 131123 131321 112313 132113 132311 211313
231113 231311 112133 112331 132131 113123 113321 133121 313121 211331
231131 213113 213311 213131 311123 311321 331121 312113 312311 332111
314111 221411 431111 111224 111422 121124 121421 141122 141221 112214
112412 122114 122411 142112 142211 241211 221114 413111 241112 134111
111242 121142 121241 114212 124112 124211 411212 421112 421211 212141
214121 412121 111143 111341 131141 114113 114311 411113 411311 113141
114131 311141 411131 211412 211214 211232 2331112
`.trim().split(/\s+/).map(pattern => Array.from(pattern, Number));

const START_B = 104;
const STOP = 106;
const quietZone = 10;

export function barcodeImage(code: string) {
  const values = Array.from(code, char => char.charCodeAt(0) - 32);
  const checksum = values.reduce((sum, value, index) => sum + value * (index + 1), START_B) % 103;
  let x = quietZone;
  const bars = [START_B, ...values, checksum, STOP].flatMap(value =>
    patterns[value].map((width, index) => {
      const start = x;
      x += width;
      return index % 2 === 0 ? `<rect x="${start}" width="${width}" height="52"/>` : "";
    })
  );
  const width = x + quietZone;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width * 2}" height="104" viewBox="0 0 ${width} 52" shape-rendering="crispEdges"><rect width="${width}" height="52" fill="white"/>${bars.join("")}</svg>`;
  return "data:image/svg+xml," + encodeURIComponent(svg);
}

function errorFor(runs: number[], offset: number, pattern: number[], modules: number) {
  const unit = runs.slice(offset, offset + pattern.length).reduce((sum, width) => sum + width, 0) / modules;
  if (unit < 1 || runs.length < offset + pattern.length) return Infinity;
  // Allow about one pixel of rounding in narrow bars.
  const tolerance = Math.max(0.8, 1.15 / unit);
  let error = 0;
  for (let i = 0; i < pattern.length; i++) {
    const gap = Math.abs(runs[offset + i] / unit - pattern[i]);
    if (gap > tolerance) return Infinity;
    error += gap;
  }
  return error / modules;
}

function decodeRuns(runs: number[]) {
  for (let start = 1; start + 19 < runs.length; start += 2) {
    if (runs[start - 1] < 5 || errorFor(runs, start, patterns[START_B], 11) > 0.19) continue;
    const values: number[] = [];
    for (let offset = start + 6; offset + 6 < runs.length && values.length <= 28; offset += 6) {
      if (values.length >= 4 && errorFor(runs, offset, patterns[STOP], 13) <= 0.19) {
        const checksum = values[values.length - 1];
        const data = values.slice(0, -1);
        const expected = data.reduce((sum, value, i) => sum + value * (i + 1), START_B) % 103;
        const code = String.fromCharCode(...data.map(value => value + 32));
        if (checksum === expected && /^SR-[A-Z0-9-]{1,24}$/.test(code)) return code;
      }
      let best = -1;
      let threshold = 0.21;
      for (let value = 0; value < 103; value++) {
        const distance = errorFor(runs, offset, patterns[value], 11);
        if (distance < threshold) {
          threshold = distance;
          best = value;
        }
      }
      if (best < 0) break;
      values.push(best);
    }
  }
  return null;
}

function runsAtThreshold(gray: Uint8Array, threshold: number) {
  let black = gray[0] < threshold;
  const runs = black ? [0] : [];
  let start = 0;
  for (let x = 1; x < gray.length; x++) {
    const next = gray[x] < threshold;
    if (next === black) continue;
    // Estimate where a blurred bar edge falls between adjacent camera pixels.
    const edge = x - 1 + (threshold - gray[x - 1]) / (gray[x] - gray[x - 1]);
    runs.push(edge - start);
    start = edge;
    black = next;
  }
  runs.push(gray.length - start);
  if (black) runs.push(0);
  return runs;
}

export function readBarcodeRow(gray: Uint8Array) {
  if (!gray.length) return null;
  const sorted = gray.slice().sort();
  const dark = sorted[Math.floor(sorted.length * 0.05)];
  const light = sorted[Math.floor(sorted.length * 0.95)];
  const contrast = light - dark;
  if (contrast < 40) return null;

  // Screen glare or shadows can produce different contrast across one label.
  for (const fraction of [0.5, 0.35, 0.65]) {
    const runs = runsAtThreshold(gray, dark + contrast * fraction);
    const code = decodeRuns(runs) ?? decodeRuns(runs.reverse());
    if (code) return code;
  }
  return null;
}
