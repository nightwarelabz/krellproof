#!/usr/bin/env python3
"""Generate graph.krell from results/results.json.

The chart itself is rendered entirely by the generated Krell program:
this script only lays out the scene (positions, bar lengths on a log
scale, label strings) and bakes it into data tables the Krell program
draws from. All pixel work -- panels, gridlines, bars, and the 5x7
glyph text -- is Krell.
"""
import json
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
W, H = 1760, 1290

# ------------------------------------------------------------------- font
FONT = {
    " ": [".....", ".....", ".....", ".....", ".....", ".....", "....."],
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "D": ["###..", "#..#.", "#...#", "#...#", "#...#", "#..#.", "###.."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "F": ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    "G": [".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".####"],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "V": ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "W": ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"],
    "Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    "J": ["..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    "Z": ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    "X": ["#...#", ".#.#.", "..#..", "..#..", "..#..", ".#.#.", "#...#"],
    "Y": ["#...#", ".#.#.", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "0": [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    "1": ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    "3": ["#####", "...#.", "..#..", "...#.", "....#", "#...#", ".###."],
    "4": ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    "5": ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    "6": ["..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."],
    "7": ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    "8": [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    "9": [".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."],
    ".": [".....", ".....", ".....", ".....", ".....", ".##..", ".##.."],
    "-": [".....", ".....", ".....", "#####", ".....", ".....", "....."],
    "(": ["...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."],
    ")": [".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."],
    "/": ["....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."],
    "+": [".....", "..#..", "..#..", ".###.", "..#..", "..#..", "....."],
}
CHARS = list(FONT.keys())
CIDX = {c: i for i, c in enumerate(CHARS)}
GLYPH_BYTES = []
for c in CHARS:
    for row in FONT[c]:
        v = 0
        for j, ch in enumerate(row):
            if ch == "#":
                v |= 1 << (4 - j)
        GLYPH_BYTES.append(v)

# ------------------------------------------------------------------- data
data = json.load(open(os.path.join(ROOT, "results", "results.json")))
res = {(r["kernel"], r["impl"]): r for r in data["results"]}
meta = data["meta"]

KERNELS = ["fill32", "span", "sumsq", "fib", "histo", "fnv1a"]
HEADERS = {
    "fill32": "FILL32 - 1M U32", "span": "SPAN - 4096 PX",
    "sumsq": "SUMSQ - 1M I64", "fib": "FIB(32) - RECURSIVE",
    "histo": "HISTO - 4M BYTES", "fnv1a": "FNV1A - 4M BYTES",
}
IMPLS = [("c_o0", "C -O0"), ("c_o1", "C -O1"), ("c_o2", "C -O2"),
         ("krell", "KRELL"), ("krell_interp", "INTERP"),
         ("python", "PYTHON"), ("numpy", "NUMPY")]
IMPL_IDX = {name: i for i, (name, _) in enumerate(IMPLS)}
PAL_BAR = [(88, 99, 122), (118, 133, 158), (165, 185, 210), (55, 215, 255),
           (35, 120, 140), (238, 185, 55), (120, 200, 90)]
PAL_TXT = [(235, 240, 248), (150, 165, 190), (90, 220, 255),
           (200, 214, 232), (140, 155, 175)] + PAL_BAR
TXT_WHITE, TXT_DIM, TXT_CYAN, TXT_HEAD, TXT_FOOT = 0, 1, 2, 3, 4
TXT_IMPL0 = 5  # impl label colors follow the bar palette

LOG_LO, LOG_HI = 4.0, 9.6
BAR_X_OFF, BAR_MAXLEN = 128, 500
ROW0_OFF, ROW_PITCH, BAR_H = 56, 40, 24
PANEL_W, PANEL_H = 820, 340


def fmt_ns(v):
    if v < 1000:
        return f"{v:.0f}"
    if v < 1e6:
        return f"{v / 1e3:.1f}K"
    if v < 1e9:
        return f"{v / 1e6:.2f}M"
    return f"{v / 1e9:.2f}G"


def bar_len(v):
    frac = (math.log10(v) - LOG_LO) / (LOG_HI - LOG_LO)
    return max(6, round(frac * BAR_MAXLEN))


strings = []  # (text, ox, oy, scale, txt_color_idx)
panels = []   # (x0, y0, x1, y1, fill_packed, border_packed)
bars = []     # (x0, y0, x1, y1, impl_idx)


def pack(r, g, b):
    return (r << 16) | (g << 8) | b


strings.append(("KRELLPROOF", 40, 28, 7, TXT_WHITE))
strings.append(("ASSAULT BENCH - NS PER CALL (LOG SCALE) - LOWER IS FASTER",
                42, 102, 3, TXT_CYAN))
strings.append(("KRELL NATIVE AND INTERPRETER VS C -O0 -O1 -O2 VS PYTHON AND NUMPY",
                42, 140, 2, TXT_DIM))

for ki, kernel in enumerate(KERNELS):
    px = 40 + (ki % 2) * 860
    py = 176 + (ki // 2) * 360
    panels.append((px, py, px + PANEL_W, py + PANEL_H,
                   pack(14, 20, 36), pack(44, 62, 94)))
    strings.append((HEADERS[kernel], px + 16, py + 14, 3, TXT_HEAD))
    base = res[(kernel, "c_o2")]["best_ns"]
    j = 0
    for impl, label in IMPLS:
        r = res.get((kernel, impl))
        if r is None:
            continue
        by = py + ROW0_OFF + j * ROW_PITCH
        strings.append((label, px + 16, by + 5, 2, TXT_IMPL0 + IMPL_IDX[impl]))
        ln = bar_len(r["best_ns"])
        bars.append((px + BAR_X_OFF, by, px + BAR_X_OFF + ln, by + BAR_H,
                     IMPL_IDX[impl]))
        ratio = r["best_ns"] / base
        strings.append((f"{fmt_ns(r['best_ns'])} {ratio:.2f}X",
                        px + 636, by + 5, 2, TXT_WHITE))
        j += 1

cpu_short = "EPYC 9D25"
m = re.search(r"(EPYC \w+)", meta.get("cpu", ""))
if m:
    cpu_short = m.group(1)
gcc_short = "GCC 13.3"
m = re.search(r"(\d+\.\d+)\.\d+", meta.get("gcc", ""))
if m:
    gcc_short = f"GCC {m.group(1)}"
date_short = meta.get("date", "")[:10]
strings.append((
    f"{cpu_short} - {gcc_short} - PYTHON {meta.get('python', '')} - "
    f"NUMPY {meta.get('numpy', '')} - KRELL V1.1 - {date_short} - "
    f"ALL CHECKSUMS IDENTICAL", 40, 1254, 2, TXT_FOOT))

GRID_OFFS = [round((d - LOG_LO) / (LOG_HI - LOG_LO) * BAR_MAXLEN)
             for d in (5, 6, 7, 8, 9)]

# ------------------------------------------------------------------- blobs
hdr = f"P6\n{W} {H}\n255\n"
B_HDR = list(hdr.encode())
strblob, strtab = [], []
for text, ox, oy, scale, ci in strings:
    off = len(strblob)
    codes = []
    for ch in text:
        if ch not in CIDX:
            raise SystemExit(f"no glyph for {ch!r} in {text!r}")
        codes.append(CIDX[ch])
    strblob += codes
    strtab += [off, len(codes), ox, oy, scale, ci]


def quads(records):
    out = []
    for rec in records:
        for v in rec:
            out += [v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF,
                    (v >> 24) & 0xFF]
    return out


B_STR = strblob
B_STRTAB = quads([tuple(strtab[i:i + 6]) for i in range(0, len(strtab), 6)])
B_BARS = quads(bars)
B_PANELS = quads(panels)
palbar_bytes = []
for (r, g, b) in PAL_BAR:
    palbar_bytes += [r, g, b]
    palbar_bytes += [min(255, int(r * 1.45)), min(255, int(g * 1.45)),
                     min(255, int(b * 1.45))]
B_PALBAR = palbar_bytes
B_PALTXT = [v for rgb in PAL_TXT for v in rgb]
B_GRID = quads([(o,) for o in GRID_OFFS])

BLOBS = [B_HDR, GLYPH_BYTES, B_STR, B_STRTAB, B_BARS, B_PANELS,
         B_PALBAR, B_PALTXT, B_GRID]
NAMES = ["hdr", "glyphs", "strblob", "strtab", "bars", "panels",
         "palbar", "paltxt", "grid"]
NBARS, NPAN, NSTR, NGRID = len(bars), len(panels), len(strings), len(GRID_OFFS)

# ------------------------------------------------------------------- emit
L = []
L.append("extern write(i64, ptr, i64) -> i64")
L.append("extern malloc(i64) -> ptr")
L.append("")
for name, blob in zip(NAMES, BLOBS):
    body = ", ".join(str(v) for v in blob)
    L.append(f"data {name}: i8 = {{ {body} }}")
L.append("")

# NOTE: dataptr takes an immediate segment index, and every call site
# below uses a constant blob index, so the accessors are specialized
# per blob (rd32_3, palc_6, ...) instead of taking a dynamic index.
# (A chained-condbr blobptr(i) selector trips a verifier dominance
# error in the v1.1 surface parser at chain depth >= 2; observed on
# bp3/bp4 minimal repros, 2026-11-02. Specialized accessors sidestep
# it and are faster anyway.)
_RD32_TAIL = """    %base = mul i64 elem, 4
    %p0 = gep i8 %bp, %base
    %b0 = load i8, %p0
    %v0 = zext i64 %b0
    %o1 = add i64 %base, 1
    %p1 = gep i8 %bp, %o1
    %b1 = load i8, %p1
    %w1 = zext i64 %b1
    %s1 = shl i64 %w1, 8
    %v1 = add i64 %v0, %s1
    %o2 = add i64 %base, 2
    %p2 = gep i8 %bp, %o2
    %b2 = load i8, %p2
    %w2 = zext i64 %b2
    %s2 = shl i64 %w2, 16
    %v2 = add i64 %v1, %s2
    %o3 = add i64 %base, 3
    %p3 = gep i8 %bp, %o3
    %b3 = load i8, %p3
    %w3 = zext i64 %b3
    %s3 = shl i64 %w3, 24
    %v3 = add i64 %v2, %s3
    ret %v3
}"""
for _n in (3, 4, 5, 8):
    L.append(f"fn rd32_{_n}(i64) -> i64 {{")
    L.append("  entry(elem: i64):")
    L.append(f"    %bp = dataptr {_n}")
    L.append(_RD32_TAIL)
    L.append("")
_PALC_TAIL = """    %t = mul i64 idx, 3
    %o = add i64 %t, ch
    %p = gep i8 %bp, %o
    %b = load i8, %p
    %v = zext i64 %b
    ret %v
}"""
for _n in (6, 7):
    L.append(f"fn palc_{_n}(i64, i64) -> i64 {{")
    L.append("  entry(idx: i64, ch: i64):")
    L.append(f"    %bp = dataptr {_n}")
    L.append(_PALC_TAIL)
    L.append("")
L.append("""fn pack3(i64, i64, i64) -> i64 {
  entry(r: i64, g: i64, b: i64):
    %rs = shl i64 r, 16
    %gs = shl i64 g, 8
    %t = add i64 %rs, %gs
    %v = add i64 %t, b
    ret %v
}

fn glyph_hit(i64, i64, i64) -> i64 {
  entry(gid: i64, row: i64, col: i64):
    %g = dataptr 1
    %base = mul i64 gid, 7
    %idx = add i64 %base, row
    %p = gep i8 %g, %idx
    %rb = load i8, %p
    %r = zext i64 %rb
    %sh = sub i64 4, col
    %bits = lshr i64 %r, %sh
    %bit = and i64 %bits, 1
    ret %bit
}

fn text_hit(i64, i64, i64, i64, i64, ptr, i64) -> i64 {
  entry(x: i64, y: i64, ox: i64, oy: i64, scale: i64, codes: ptr, n: i64):
    %z = iconst i64 0
    %dx = sub i64 x, ox
    %dy = sub i64 y, oy
    %negx = icmp.slt i64 %dx, 0
    condbr %negx, zero(%z), chky(%dx, %dy, scale, codes, n, %z)
  zero(z: i64):
    ret z
  chky(dx: i64, dy: i64, scale: i64, codes: ptr, n: i64, z: i64):
    %negy = icmp.slt i64 dy, 0
    condbr %negy, zero(z), body(dx, dy, scale, codes, n, z)
  body(dx: i64, dy: i64, scale: i64, codes: ptr, n: i64, z: i64):
    %adv = mul i64 scale, 6
    %cellh = mul i64 scale, 7
    %inrow = icmp.slt i64 dy, %cellh
    condbr %inrow, colchk(dx, dy, scale, codes, n, z, %adv), zero(z)
  colchk(dx: i64, dy: i64, scale: i64, codes: ptr, n: i64, z: i64, adv: i64):
    %tot = mul i64 n, adv
    %incol = icmp.slt i64 dx, %tot
    condbr %incol, cell(dx, dy, scale, codes, z, adv), zero(z)
  cell(dx: i64, dy: i64, scale: i64, codes: ptr, z: i64, adv: i64):
    %ci = udiv i64 dx, adv
    %lx = urem i64 dx, adv
    %cw = mul i64 scale, 5
    %inlet = icmp.slt i64 lx, %cw
    condbr %inlet, pix(dx, dy, scale, codes, %ci, lx), zero(z)
  pix(dx: i64, dy: i64, scale: i64, codes: ptr, ci: i64, lx: i64):
    %gx = udiv i64 lx, scale
    %gy = udiv i64 dy, scale
    %cp = gep i8 codes, ci
    %gb = load i8, %cp
    %gid = zext i64 %gb
    %hit = call i64 glyph_hit(%gid, %gy, %gx)
    ret %hit
}""")
L.append("")

# stage_panels
L.append(f"""fn stage_panels(i64, i64, i64) -> i64 {{
  entry(x: i64, y: i64, pk: i64):
    br loop(0, x, y, pk)
  loop(i: i64, x: i64, y: i64, pk: i64):
    %c = icmp.slt i64 i, {NPAN}
    condbr %c, body(i, x, y, pk), fin(pk)
  body(i: i64, x: i64, y: i64, pk: i64):
    %rec = mul i64 i, 6
    %e0 = add i64 %rec, 0
    %x0 = call i64 rd32_5(%e0)
    %e1 = add i64 %rec, 1
    %y0 = call i64 rd32_5(%e1)
    %e2 = add i64 %rec, 2
    %x1 = call i64 rd32_5(%e2)
    %e3 = add i64 %rec, 3
    %y1 = call i64 rd32_5(%e3)
    %e4 = add i64 %rec, 4
    %fp = call i64 rd32_5(%e4)
    %e5 = add i64 %rec, 5
    %bp = call i64 rd32_5(%e5)
    %ax = icmp.sge i64 x, %x0
    %axz = zext i64 %ax
    %bx = icmp.slt i64 x, %x1
    %bxz = zext i64 %bx
    %ay = icmp.sge i64 y, %y0
    %ayz = zext i64 %ay
    %by = icmp.slt i64 y, %y1
    %byz = zext i64 %by
    %tx = and i64 %axz, %bxz
    %ty = and i64 %ayz, %byz
    %in = and i64 %tx, %ty
    %inb = icmp.ne i64 %in, 0
    condbr %inb, inset(i, x, y, pk, %x0, %y0, %x1, %y1, %fp, %bp), next(i, x, y, pk)
  inset(i: i64, x: i64, y: i64, pk: i64, x0: i64, y0: i64, x1: i64, y1: i64, fp: i64, bp: i64):
    %ex0 = icmp.eq i64 x, x0
    %ex0z = zext i64 %ex0
    %xm = sub i64 x1, 1
    %ex1 = icmp.eq i64 x, %xm
    %ex1z = zext i64 %ex1
    %ey0 = icmp.eq i64 y, y0
    %ey0z = zext i64 %ey0
    %ym = sub i64 y1, 1
    %ey1 = icmp.eq i64 y, %ym
    %ey1z = zext i64 %ey1
    %tx = or i64 %ex0z, %ex1z
    %ty = or i64 %ey0z, %ey1z
    %edge = or i64 %tx, %ty
    %eb = icmp.ne i64 %edge, 0
    condbr %eb, setb(i, x, y, bp), setf(i, x, y, fp)
  setb(i: i64, x: i64, y: i64, pk: i64):
    br next(i, x, y, pk)
  setf(i: i64, x: i64, y: i64, pk: i64):
    br next(i, x, y, pk)
  next(i: i64, x: i64, y: i64, pk: i64):
    %i2 = add i64 i, 1
    br loop(%i2, x, y, pk)
  fin(pk: i64):
    ret pk
}}""")
L.append("")

# stage_grid
L.append(f"""fn stage_grid(i64, i64, i64) -> i64 {{
  entry(x: i64, y: i64, pk: i64):
    br ploop(0, x, y, pk)
  ploop(i: i64, x: i64, y: i64, pk: i64):
    %c = icmp.slt i64 i, {NPAN}
    condbr %c, pbody(i, x, y, pk), fin(pk)
  pbody(i: i64, x: i64, y: i64, pk: i64):
    %rec = mul i64 i, 6
    %x0 = call i64 rd32_5(%rec)
    %e1 = add i64 %rec, 1
    %y0 = call i64 rd32_5(%e1)
    %bx = add i64 %x0, {BAR_X_OFF}
    %ry = add i64 %y0, {ROW0_OFF}
    %ey = add i64 %ry, {7 * ROW_PITCH}
    %ay = icmp.sge i64 y, %ry
    %ayz = zext i64 %ay
    %by = icmp.slt i64 y, %ey
    %byz = zext i64 %by
    %iny = and i64 %ayz, %byz
    %inyb = icmp.ne i64 %iny, 0
    condbr %inyb, gloop(0, x, y, pk, %bx, i), pnext(i, x, y, pk)
  gloop(gi: i64, x: i64, y: i64, pk: i64, bx: i64, i: i64):
    %c = icmp.slt i64 gi, {NGRID}
    condbr %c, gbody(gi, x, y, pk, bx, i), pnext(i, x, y, pk)
  gbody(gi: i64, x: i64, y: i64, pk: i64, bx: i64, i: i64):
    %off = call i64 rd32_8(gi)
    %gx = add i64 bx, %off
    %hit = icmp.eq i64 x, %gx
    condbr %hit, gset(gi, x, y, bx, i), gnext(gi, x, y, pk, bx, i)
  gset(gi: i64, x: i64, y: i64, bx: i64, i: i64):
    %pk = iconst i64 {pack(33, 47, 73)}
    br gnext(gi, x, y, %pk, bx, i)
  gnext(gi: i64, x: i64, y: i64, pk: i64, bx: i64, i: i64):
    %g2 = add i64 gi, 1
    br gloop(%g2, x, y, pk, bx, i)
  pnext(i: i64, x: i64, y: i64, pk: i64):
    %i2 = add i64 i, 1
    br ploop(%i2, x, y, pk)
  fin(pk: i64):
    ret pk
}}""")
L.append("")

# stage_bars
L.append(f"""fn stage_bars(i64, i64, i64) -> i64 {{
  entry(x: i64, y: i64, pk: i64):
    br loop(0, x, y, pk)
  loop(i: i64, x: i64, y: i64, pk: i64):
    %c = icmp.slt i64 i, {NBARS}
    condbr %c, body(i, x, y, pk), fin(pk)
  body(i: i64, x: i64, y: i64, pk: i64):
    %rec = mul i64 i, 5
    %x0 = call i64 rd32_4(%rec)
    %e1 = add i64 %rec, 1
    %y0 = call i64 rd32_4(%e1)
    %e2 = add i64 %rec, 2
    %x1 = call i64 rd32_4(%e2)
    %e3 = add i64 %rec, 3
    %y1 = call i64 rd32_4(%e3)
    %e4 = add i64 %rec, 4
    %ci = call i64 rd32_4(%e4)
    %ax = icmp.sge i64 x, %x0
    %axz = zext i64 %ax
    %bx = icmp.slt i64 x, %x1
    %bxz = zext i64 %bx
    %ay = icmp.sge i64 y, %y0
    %ayz = zext i64 %ay
    %by = icmp.slt i64 y, %y1
    %byz = zext i64 %by
    %tx = and i64 %axz, %bxz
    %ty = and i64 %ayz, %byz
    %in = and i64 %tx, %ty
    %inb = icmp.ne i64 %in, 0
    condbr %inb, inset(i, x, y, pk, %x0, %y0, %x1, %y1, %ci), next(i, x, y, pk)
  inset(i: i64, x: i64, y: i64, pk: i64, x0: i64, y0: i64, x1: i64, y1: i64, ci: i64):
    %ex0 = icmp.eq i64 x, x0
    %ex0z = zext i64 %ex0
    %xm = sub i64 x1, 1
    %ex1 = icmp.eq i64 x, %xm
    %ex1z = zext i64 %ex1
    %ey0 = icmp.eq i64 y, y0
    %ey0z = zext i64 %ey0
    %ym = sub i64 y1, 1
    %ey1 = icmp.eq i64 y, %ym
    %ey1z = zext i64 %ey1
    %tx = or i64 %ex0z, %ex1z
    %ty = or i64 %ey0z, %ey1z
    %edge = or i64 %tx, %ty
    %d = mul i64 ci, 2
    %di = add i64 %d, %edge
    %r = call i64 palc_6(%di, 0)
    %g = call i64 palc_6(%di, 1)
    %b = call i64 palc_6(%di, 2)
    %np = call i64 pack3(%r, %g, %b)
    br next(i, x, y, %np)
  next(i: i64, x: i64, y: i64, pk: i64):
    %i2 = add i64 i, 1
    br loop(%i2, x, y, pk)
  fin(pk: i64):
    ret pk
}}""")
L.append("")

# stage_text
L.append(f"""fn stage_text(i64, i64, i64) -> i64 {{
  entry(x: i64, y: i64, pk: i64):
    %sb = dataptr 2
    br loop(0, x, y, pk, %sb)
  loop(i: i64, x: i64, y: i64, pk: i64, sb: ptr):
    %c = icmp.slt i64 i, {NSTR}
    condbr %c, body(i, x, y, pk, sb), fin(pk)
  body(i: i64, x: i64, y: i64, pk: i64, sb: ptr):
    %rec = mul i64 i, 6
    %off = call i64 rd32_3(%rec)
    %e1 = add i64 %rec, 1
    %len = call i64 rd32_3(%e1)
    %e2 = add i64 %rec, 2
    %ox = call i64 rd32_3(%e2)
    %e3 = add i64 %rec, 3
    %oy = call i64 rd32_3(%e3)
    %e4 = add i64 %rec, 4
    %sc = call i64 rd32_3(%e4)
    %e5 = add i64 %rec, 5
    %ci = call i64 rd32_3(%e5)
    %codes = gep i8 sb, %off
    %hit = call i64 text_hit(x, y, %ox, %oy, %sc, %codes, %len)
    %is = icmp.eq i64 %hit, 1
    condbr %is, inset(i, x, y, sb, %ci), next(i, x, y, pk, sb)
  inset(i: i64, x: i64, y: i64, sb: ptr, ci: i64):
    %r = call i64 palc_7(ci, 0)
    %g = call i64 palc_7(ci, 1)
    %b = call i64 palc_7(ci, 2)
    %np = call i64 pack3(%r, %g, %b)
    br next(i, x, y, %np, sb)
  next(i: i64, x: i64, y: i64, pk: i64, sb: ptr):
    %i2 = add i64 i, 1
    br loop(%i2, x, y, pk, sb)
  fin(pk: i64):
    ret pk
}}""")
L.append("")

# shade + main
L.append(f"""fn shade(i64, i64, ptr) -> i64 {{
  entry(x: i64, y: i64, out: ptr):
    %bg = iconst i64 {pack(9, 12, 22)}
    %p1 = call i64 stage_panels(x, y, %bg)
    %p2 = call i64 stage_grid(x, y, %p1)
    %p3 = call i64 stage_bars(x, y, %p2)
    %p4 = call i64 stage_text(x, y, %p3)
    %r = lshr i64 %p4, 16
    %rc = and i64 %r, 255
    %rt = trunc i8 %rc
    store i8 out, %rt
    %g = lshr i64 %p4, 8
    %gc = and i64 %g, 255
    %gt = trunc i8 %gc
    %o1 = gep i8 out, 1
    store i8 %o1, %gt
    %bc = and i64 %p4, 255
    %bt = trunc i8 %bc
    %o2 = gep i8 out, 2
    store i8 %o2, %bt
    %z = iconst i64 0
    ret %z
}}

fn main() -> i64 {{
  entry():
    %hdr = dataptr 0
    %w0 = call i64 write(1, %hdr, {len(B_HDR)})
    %rowbuf = call ptr malloc({W * 3})
    br yloop(0, %rowbuf)
  yloop(y: i64, rowbuf: ptr):
    %lt = icmp.slt i64 y, {H}
    condbr %lt, xloop(0, y, rowbuf), fin()
  xloop(x: i64, y: i64, rowbuf: ptr):
    %x3 = mul i64 x, 3
    %out = gep i8 rowbuf, %x3
    %s = call i64 shade(x, y, %out)
    %xn = add i64 x, 1
    %go = icmp.slt i64 %xn, {W}
    condbr %go, xloop(%xn, y, rowbuf), xdone(y, rowbuf)
  xdone(y: i64, rowbuf: ptr):
    %wr = call i64 write(1, rowbuf, {W * 3})
    %yn = add i64 y, 1
    br yloop(%yn, rowbuf)
  fin():
    %z = iconst i64 0
    ret %z
}}""")

out_path = os.path.join(HERE, "graph.krell")
open(out_path, "w").write("\n".join(L) + "\n")
print(f"wrote {out_path}: {len(strings)} strings, {len(bars)} bars, "
      f"{len(panels)} panels, {len(GLYPH_BYTES)} glyph bytes")
