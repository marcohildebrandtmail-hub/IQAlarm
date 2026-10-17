/* Home Assistant areas are linked only when the user saves a floorplan area. */
const AREA_PREFIX = "ha-area:";
export const areaReference = id => `${AREA_PREFIX}${id}`;

export function roomGroups(rooms, areas) {
  const configured = Object.values(rooms);
  const linked = new Set(configured.map(room => room.area_id).filter(Boolean));
  const sort = items => items.sort((a, b) => a.name.localeCompare(b.name, "de"));
  return [
    {name: "IQAlarm-Räume", items: sort(configured.map(room => ({id: room.id, name: room.name})))},
    {name: "Home-Assistant-Bereiche", items: sort(areas.filter(area => !linked.has(area.id)).map(area => ({id: areaReference(area.id), name: area.name})))},
  ].filter(group => group.items.length);
}

export function hasRoomReference(rooms, areas, reference) {
  return Object.hasOwn(rooms, reference) || areas.some(area => areaReference(area.id) === reference);
}

export function randomId(cryptoObj = globalThis.crypto) {
  if (typeof cryptoObj?.randomUUID === "function") return cryptoObj.randomUUID().replaceAll("-", "");
  if (typeof cryptoObj?.getRandomValues === "function") {
    const bytes = new Uint8Array(16);
    cryptoObj.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    return Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("");
  }
  return Array.from({length: 32}, () => Math.floor(Math.random() * 16).toString(16)).join("");
}

export function resolveRoom(rooms, areas, reference, newName, createId = randomId) {
  const name = newName.trim();
  if (reference && name) throw new Error("Bitte einen vorhandenen Raum wählen oder einen neuen benennen");
  if (!reference && !name) throw new Error("Bitte einen Raum auswählen oder einen Namen eingeben. Dein Entwurf bleibt erhalten.");
  if (reference && Object.hasOwn(rooms, reference)) return {id: reference, room: null};
  const area = reference ? areas.find(item => areaReference(item.id) === reference) : null;
  if (reference && !area) throw new Error("Der gewählte Raum oder Home-Assistant-Bereich wurde entfernt. Dein Entwurf bleibt erhalten.");
  const existing = area && Object.values(rooms).find(room => room.area_id === area.id);
  if (existing) return {id: existing.id, room: null};
  const id = createId();
  return {id, room: {id, name: area ? area.name : name, area_id: area?.id || null, adjacent: [], home_enabled: false}};
}

function simplifyLine(points, tolerance) {
  if (points.length <= 2) return points;
  const [x1, y1] = points[0], [x2, y2] = points.at(-1);
  const dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy);
  let maxDist = 0, split = 1;
  for (let i = 1; i < points.length - 1; i += 1) {
    const dist = len === 0 ? Math.hypot(points[i][0] - x1, points[i][1] - y1) : Math.abs(dy * (points[i][0] - x1) - dx * (points[i][1] - y1)) / len;
    if (dist > maxDist) { maxDist = dist; split = i; }
  }
  if (maxDist <= tolerance) return [points[0], points.at(-1)];
  return [...simplifyLine(points.slice(0, split + 1), tolerance).slice(0, -1), ...simplifyLine(points.slice(split), tolerance)];
}

function polygonArea(points) {
  let sum = 0;
  for (let i = 0; i < points.length; i += 1) {
    const [x1, y1] = points[i], [x2, y2] = points[(i + 1) % points.length];
    sum += x1 * y2 - y1 * x2;
  }
  return Math.abs(sum) / 2;
}

function rasterizePolygon(points, size) {
  const mask = new Uint8Array(size * size);
  for (let y = 0; y < size; y += 1) {
    const py = (y + 0.5) / size, xs = [];
    for (let i = 0; i < points.length; i += 1) {
      const [x1, y1] = points[i], [x2, y2] = points[(i + 1) % points.length];
      if ((y1 <= py && y2 > py) || (y2 <= py && y1 > py)) xs.push(x1 + ((py - y1) * (x2 - x1)) / (y2 - y1));
    }
    xs.sort((a, b) => a - b);
    for (let i = 0; i + 1 < xs.length; i += 2) {
      const start = Math.max(0, Math.floor(xs[i] * size)), end = Math.min(size - 1, Math.ceil(xs[i + 1] * size) - 1);
      for (let x = start; x <= end; x += 1) mask[y * size + x] = 1;
    }
  }
  return mask;
}

export function mergePolygons(pointsA, pointsB) {
  if (!Array.isArray(pointsA) || pointsA.length < 3) return structuredClone(pointsB || []);
  if (!Array.isArray(pointsB) || pointsB.length < 3) return structuredClone(pointsA);
  const size = 240, maxGap = 18;
  const maskA = rasterizePolygon(pointsA, size), maskB = rasterizePolygon(pointsB, size);
  const combined = new Uint8Array(size * size);
  for (let i = 0; i < combined.length; i += 1) combined[i] = maskA[i] ? 1 : maskB[i] ? 2 : 0;
  for (const vertical of [false, true]) {
    for (let line = 0; line < size; line += 1) {
      let lastKind = 0, lastPos = -1;
      for (let pos = 0; pos < size; pos += 1) {
        const idx = vertical ? pos * size + line : line * size + pos;
        const kind = maskA[idx] ? 1 : maskB[idx] ? 2 : 0;
        if (kind) {
          if (lastKind && lastKind !== kind && pos - lastPos - 1 <= maxGap) {
            for (let fill = lastPos + 1; fill < pos; fill += 1) combined[vertical ? fill * size + line : line * size + fill] = 3;
          }
          lastKind = kind; lastPos = pos;
        }
      }
    }
  }
  const edges = new Map(), key = (x, y) => `${x},${y}`, addEdge = (x1, y1, x2, y2) => {
    const k = key(x1, y1); if (!edges.has(k)) edges.set(k, []); edges.get(k).push([x2, y2]);
  };
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      if (!combined[y * size + x]) continue;
      if (y === 0 || !combined[(y - 1) * size + x]) addEdge(x, y, x + 1, y);
      if (x === size - 1 || !combined[y * size + x + 1]) addEdge(x + 1, y, x + 1, y + 1);
      if (y === size - 1 || !combined[(y + 1) * size + x]) addEdge(x + 1, y + 1, x, y + 1);
      if (x === 0 || !combined[y * size + x - 1]) addEdge(x, y + 1, x, y);
    }
  }
  const loops = [];
  while (edges.size) {
    const firstKey = edges.keys().next().value;
    let [cx, cy] = firstKey.split(",").map(Number);
    const [sx, sy] = [cx, cy], loop = [];
    while (edges.has(key(cx, cy))) {
      loop.push([cx, cy]);
      const list = edges.get(key(cx, cy)), next = list.pop();
      if (!list.length) edges.delete(key(cx, cy));
      [cx, cy] = next;
      if (cx === sx && cy === sy) break;
    }
    if (cx === sx && cy === sy && loop.length >= 4) {
      const corners = loop.filter((p, i) => {
        const prev = loop[(i + loop.length - 1) % loop.length], next = loop[(i + 1) % loop.length];
        return p[0] - prev[0] !== next[0] - p[0] || p[1] - prev[1] !== next[1] - p[1];
      });
      if (corners.length >= 3) loops.push(corners);
    }
  }
  if (!loops.length) return structuredClone(pointsA);
  const outline = loops.reduce((best, cur) => (polygonArea(cur) > polygonArea(best) ? cur : best));
  let split = 1, maxDist = -1;
  for (let i = 1; i < outline.length; i += 1) {
    const d = Math.hypot(outline[i][0] - outline[0][0], outline[i][1] - outline[0][1]);
    if (d > maxDist) { maxDist = d; split = i; }
  }
  const origX = [...pointsA, ...pointsB].map(p => p[0]), origY = [...pointsA, ...pointsB].map(p => p[1]);
  const snap = (val, list) => {
    let best = val, bestDiff = 1.6 / size;
    for (const item of list) { const diff = Math.abs(item - val); if (diff <= bestDiff) { bestDiff = diff; best = item; } }
    return Math.round(best * 10000) / 10000;
  };
  let tolerance = 1.4;
  for (let attempt = 0; attempt < 8; attempt += 1) {
    const simplified = [...simplifyLine(outline.slice(0, split + 1), tolerance).slice(0, -1), ...simplifyLine([...outline.slice(split), outline[0]], tolerance).slice(0, -1)];
    if (simplified.length >= 3 && simplified.length <= 64) {
      return simplified.map(([x, y]) => [snap(x / size, origX), snap(y / size, origY)]);
    }
    tolerance *= 1.6;
  }
  return structuredClone(pointsA);
}

function pointInPolygon(px, py, points) {
  let inside = false;
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const [xi, yi] = points[i], [xj, yj] = points[j];
    if ((yi > py) !== (yj > py) && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function pointToSegmentDist(px, py, x1, y1, x2, y2) {
  const dx = x2 - x1, dy = y2 - y1, len2 = dx * dx + dy * dy;
  const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / len2));
  return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
}

export function roomVisualCenter(points) {
  if (!Array.isArray(points) || !points.length) return [0.5, 0.5];
  const xs = points.map(p => p[0]), ys = points.map(p => p[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  let best = [(minX + maxX) / 2, (minY + maxY) / 2], bestDist = -1;
  const steps = 16;
  for (let iy = 1; iy < steps; iy += 1) {
    for (let ix = 1; ix < steps; ix += 1) {
      const px = minX + ((maxX - minX) * ix) / steps, py = minY + ((maxY - minY) * iy) / steps;
      if (!pointInPolygon(px, py, points)) continue;
      let minDist = Infinity;
      for (let i = 0; i < points.length; i += 1) {
        const [x1, y1] = points[i], [x2, y2] = points[(i + 1) % points.length];
        minDist = Math.min(minDist, pointToSegmentDist(px, py, x1, y1, x2, y2));
      }
      if (minDist > bestDist) { bestDist = minDist; best = [px, py]; }
    }
  }
  return best;
}

export function buildGraphicZones(planZones, rooms) {
  const result = {};
  for (const [id, pts] of Object.entries(planZones || {})) {
    if (Array.isArray(pts) && pts.length >= 3) result[id] = pts;
  }
  const unmapped = Object.values(rooms || {}).filter(r => !result[r.id]);
  if (!unmapped.length) return result;
  const existingPts = Object.values(result).flat();
  const baseMinX = existingPts.length ? Math.min(...existingPts.map(p => p[0])) : 0.08;
  const baseMaxX = existingPts.length ? Math.max(...existingPts.map(p => p[0])) : 0.92;
  const startY = existingPts.length ? Math.min(0.82, Math.max(...existingPts.map(p => p[1])) + 0.05) : 0.12;
  const cols = Math.min(3, Math.max(1, unmapped.length));
  const totalW = Math.max(0.36, baseMaxX - baseMinX);
  const gap = 0.025, cellW = (totalW - gap * (cols - 1)) / cols, cellH = existingPts.length ? 0.14 : 0.28;
  unmapped.forEach((room, idx) => {
    const col = idx % cols, row = Math.floor(idx / cols);
    const x1 = Math.max(0.04, Math.min(0.96 - cellW, baseMinX + col * (cellW + gap)));
    const y1 = Math.max(0.04, Math.min(0.95 - cellH, startY + row * (cellH + gap)));
    const x2 = Math.min(0.96, x1 + cellW), y2 = Math.min(0.96, y1 + cellH);
    result[room.id] = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]];
  });
  return result;
}

export function graphicViewBox(zones, width, height) {
  const pts = Object.values(zones || {}).flat();
  if (!pts.length) return {viewBox: `0 0 ${width} ${height}`, scale: 1};
  const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const spanX = Math.max(0.18, maxX - minX), spanY = Math.max(0.18, maxY - minY);
  const padX = Math.max(0.04, spanX * 0.1), padY = Math.max(0.04, spanY * 0.12);
  const x0 = Math.max(0, minX - padX), y0 = Math.max(0, minY - padY);
  const x1 = Math.min(1, maxX + padX), y1 = Math.min(1, maxY + padY);
  const vw = Math.max(120, (x1 - x0) * width), vh = Math.max(100, (y1 - y0) * height);
  return {
    viewBox: `${Math.round(x0 * width)} ${Math.round(y0 * height)} ${Math.round(vw)} ${Math.round(vh)}`,
    scale: Math.max(0.35, Math.min(1, Math.max(x1 - x0, y1 - y0))),
  };
}
