// Tiny polyline builders for the line network. Points are plain {x,y,z}
// objects — the Lines system only reads coordinates.

export function v(x, y, z) {
  return { x, y, z };
}

export function line(a, b, divisions = 12) {
  const points = [];
  for (let i = 0; i <= divisions; i++) {
    const t = i / divisions;
    points.push(v(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t));
  }
  return { points };
}

export function circle(cx, cz, r, y, segments = 64, start = 0, end = Math.PI * 2) {
  const points = [];
  for (let i = 0; i <= segments; i++) {
    const a = start + ((end - start) * i) / segments;
    points.push(v(cx + Math.cos(a) * r, y, cz + Math.sin(a) * r));
  }
  return { points };
}

// Closed rectangle outline (w × d) at height y, rotated ry, centred (cx, cz).
export function rect(w, d, y, ry = 0, cx = 0, cz = 0) {
  const c = Math.cos(ry);
  const s = Math.sin(ry);
  const corner = (lx, lz) => v(cx + c * lx + s * lz, y, cz - s * lx + c * lz);
  const points = [];
  const path = [
    [-w / 2, -d / 2],
    [w / 2, -d / 2],
    [w / 2, d / 2],
    [-w / 2, d / 2],
    [-w / 2, -d / 2],
  ];
  for (let i = 0; i < path.length - 1; i++) {
    const [ax, az] = path[i];
    const [bx, bz] = path[i + 1];
    for (let j = 0; j < 8; j++) {
      const t = j / 8;
      points.push(corner(ax + (bx - ax) * t, az + (bz - az) * t));
    }
  }
  points.push(corner(-w / 2, -d / 2));
  return { points };
}
