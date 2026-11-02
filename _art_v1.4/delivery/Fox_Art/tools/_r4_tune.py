# -*- coding: utf-8 -*-
"""R4 参数标定：只算覆盖率，不写文件。用于挑 tabby / spots 的密度参数。"""
import os, sys, math
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

B = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
M = os.path.join(B, "assets", "master")
master = Image.open(os.path.join(M, "Base", "fox_base_blue_q4@1024.png")).convert("RGBA")
fox_a = np.asarray(master)[..., 3].astype(np.float32) / 255.0
BB = master.getbbox()
yy, xx = np.mgrid[0:1024, 0:1024]
EYES = (((xx - 610) / 62.0) ** 2 + ((yy - 510) / 52.0) ** 2 <= 1.0) | \
       (((xx - 775) / 60.0) ** 2 + ((yy - 490) / 50.0) ** 2 <= 1.0) | \
       (((xx - 740) / 58.0) ** 2 + ((yy - 560) / 46.0) ** 2 <= 1.0)
FACE_BIG = (((xx - 700) / 195.0) ** 2 + ((yy - 470) / 165.0) ** 2 <= 1.0)
COAT = (fox_a > 0.35) & (~FACE_BIG)
TRUNK = COAT & (xx < 700)


def ratio(m):
    b = m > 0.5
    return round(float((b & TRUNK).sum() / TRUNK.sum()), 4), int(b.sum())


def tabby(gy, gx, wd, L, skip, seed):
    rng = np.random.RandomState(seed)
    im = Image.new("L", (1024, 1024), 0)
    d = ImageDraw.Draw(im)
    for y in range(BB[1] + 30, BB[3] - 20, gy):
        for x in range(BB[0] + 20, BB[2] - 20, gx):
            if rng.rand() < skip:
                continue
            cx, cy = x + rng.uniform(-14, 14), y + rng.uniform(-12, 12)
            ang = math.radians(-68.0 + rng.uniform(-16, 16))
            segs = [(0.0, 1.0)]
            if rng.rand() < 0.5:
                cut, gap = rng.uniform(0.42, 0.6), rng.uniform(0.06, 0.12)
                segs = [(0.0, cut), (cut + gap, 1.0)]
            ln, ww = rng.uniform(*L), rng.uniform(*wd)
            c, s = math.cos(ang), math.sin(ang)
            for (s0, s1) in segs:
                x0, y0 = cx + (s0 - .5) * ln * c, cy + (s0 - .5) * ln * s
                x1, y1 = cx + (s1 - .5) * ln * c, cy + (s1 - .5) * ln * s
                pts, steps = [], 10
                for k in range(steps + 1):
                    t = k / steps
                    wob = math.sin(math.pi * t) * ww * (1 + .15 * math.sin(6 * t))
                    pts.append((x0 + (x1 - x0) * t - s * wob,
                                y0 + (y1 - y0) * t + c * wob))
                for k in range(steps, -1, -1):
                    t = k / steps
                    wob = math.sin(math.pi * t) * ww * (1 + .15 * math.sin(6 * t))
                    pts.append((x0 + (x1 - x0) * t + s * wob,
                                y0 + (y1 - y0) * t - c * wob))
                d.polygon(pts, fill=255)
    return (np.asarray(im).astype(np.float32) / 255.0) * COAT


def spots(n, rlo, rhi, sep, seed):
    rng = np.random.RandomState(seed)
    m = np.zeros((1024, 1024), np.float32)
    placed = []
    for _ in range(n * 12):
        if len(placed) >= n:
            break
        cx, cy = rng.uniform(BB[0], BB[2]), rng.uniform(BB[1] + 40, BB[3])
        r = rng.uniform(rlo, rhi)
        if any(math.hypot(cx - px, cy - py) < sep * (r + pr)
               for px, py, pr in placed):
            continue
        placed.append((cx, cy, r))
        ry = r * rng.uniform(0.85, 1.15)
        m += (((xx - cx) / r) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0)
    return np.clip(m, 0, 1) * COAT, len(placed)


print("TRUNK", int(TRUNK.sum()), "COAT", int(COAT.sum()))
print("\n-- tabby 候选 (gy,gx,wd,L,skip) -> trunk覆盖率, maskPx")
for gy, gx in ((46, 44), (52, 50), (54, 52), (56, 54), (58, 56)):
    m = tabby(gy, gx, (14.0, 20.0), (58.0, 112.0), 0.12, 20261103)
    print("  grid %d x %d : %s" % (gy, gx, ratio(m)))
print("\n-- spots 候选 (n,rlo,rhi,sep) -> trunk覆盖率, maskPx, 实际落点")
for n, lo, hi, sep in ((88, 16, 38, 0.0), (150, 11, 25, 0.72),
                       (170, 11, 25, 0.78), (190, 10, 23, 0.80),
                       (150, 12, 27, 0.70)):
    m, cnt = spots(n, lo, hi, sep, 20261101)
    print("  n=%3d r=%d-%d sep=%.2f : %s placed=%d"
          % (n, lo, hi, sep, ratio(m), cnt))
