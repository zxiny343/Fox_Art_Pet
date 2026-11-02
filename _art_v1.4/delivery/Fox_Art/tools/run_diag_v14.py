# -*- coding: utf-8 -*-
"""v1.4 返修单复现：R1 尾根缺口 / R3 耳型体量 / R4 花纹覆盖率 / R6 values。
数值一律以脚本为准，目视只判观感。
"""
import os, sys, json, io
import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_assemble as ra
import run_split as rs

B = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
M = os.path.join(B, "assets", "master")
BASE = os.path.join(M, "Base", "fox_base_blue_q4@1024.png")

master = Image.open(BASE).convert("RGBA")
master_a = np.asarray(master)[..., 3] > 8
reg, _ = rs.load()
W = master_a & rs.region_mask(reg["regions"]["tail"])
root = np.array([425.0, 505.0])

print("=== 窗口与母版")
print("master_a", int(master_a.sum()), "W(tail window)", int(W.sum()))
ys, xs = np.where(W)
print("W bbox", (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())))

print()
print("=== R1 各尾型：组装后缺口（master_a & assembled_alpha<8）")
TAILS = ["normal", "twin", "triple", "quad", "quint", "nine",
         "fluffy", "long", "curl", "short", "thin"]
for t in TAILS:
    p = os.path.join(M, "Tails", "tail_%s.png" % t)
    if not os.path.exists(p):
        print("%-8s MISSING" % t)
        continue
    pm = np.asarray(Image.open(p).convert("RGBA"))
    pa = pm[..., 3] > 8
    py, px = np.where(pa)
    img, _ = ra.assemble("blue", "short", t, "large", "round_blue", verbose=False)
    a = np.asarray(img)[..., 3]
    hole = master_a & (a < 8)
    hy, hx = np.where(hole)
    # 缺口距尾根的距离分布
    if len(hx):
        d = np.hypot(hx - root[0], hy - root[1])
        hist = [int((d < r).sum()) for r in (100, 150, 200, 260, 340, 450, 999)]
    else:
        hist = [0] * 7
    print("%-8s partSize=%-9s partPx=%6d partBBox=(%d,%d,%d,%d) | hole=%6d "
          "holeBBox=%s | d<100/150/200/260/340/450/all=%s"
          % (t, str(Image.open(p).size), int(pa.sum()),
             int(px.min()), int(py.min()), int(px.max()), int(py.max()),
             int(hole.sum()),
             (int(hx.min()), int(hy.min()), int(hx.max()), int(hy.max())) if len(hx) else None,
             hist))

print()
print("=== R1 缺口与窗口的关系（short / thin）")
for t in ("short", "thin"):
    p = os.path.join(M, "Tails", "tail_%s.png" % t)
    pm = np.asarray(Image.open(p).convert("RGBA"))
    pa = pm[..., 3] > 8
    img, _ = ra.assemble("blue", "short", t, "large", "round_blue", verbose=False)
    a = np.asarray(img)[..., 3]
    hole = master_a & (a < 8)
    print("%-6s hole=%d  hole∩W=%d  hole∩~W=%d  W未被部件覆盖=%d  "
          "部件在W内=%d  W=%d"
          % (t, int(hole.sum()), int((hole & W).sum()), int((hole & ~W).sum()),
             int((W & ~pa).sum()), int((W & pa).sum()), int(W.sum())))
    # 缺口按 x 分段
    for x0 in range(140, 560, 60):
        print("   x %3d-%3d: %5d" % (x0, x0 + 60,
                                     int(hole[:, x0:x0 + 60].sum())))
    for y0 in range(280, 560, 40):
        print("   y %3d-%3d: %5d" % (y0, y0 + 40,
                                     int(hole[y0:y0 + 40, :].sum())))

print()
print("=== R3 耳型体量")
for e in ("small", "round", "large", "fold", "pointed"):
    p = os.path.join(M, "Ears", "ear_%s_L.png" % e)
    if not os.path.exists(p):
        continue
    a = np.asarray(Image.open(p).convert("RGBA"))[..., 3] > 8
    ys, xs = np.where(a)
    print("%-8s px=%6d bbox=(%d,%d,%d,%d) w=%3d h=%3d topY=%d"
          % (e, int(a.sum()), xs.min(), ys.min(), xs.max(), ys.max(),
             xs.max() - xs.min(), ys.max() - ys.min(), ys.min()))

print()
print("=== R4 花纹覆盖率（躯干定义：母版alpha ∩ 非脸部椭圆 ∩ x<700）")
yy, xx = np.mgrid[0:1024, 0:1024]
face = (((xx - 700) / 195.0) ** 2 + ((yy - 470) / 165.0) ** 2 <= 1.0)
trunk = master_a & (~face) & (xx < 700)
print("trunk px", int(trunk.sum()))
for pat in ("stripes", "tabby", "spots", "facemark", "flame"):
    p = os.path.join(M, "Patterns", "pattern_%s_mask@1024.png" % pat)
    if not os.path.exists(p):
        print("%-10s MISSING" % pat)
        continue
    pm = np.asarray(Image.open(p).convert("RGBA").getchannel("A")) > 128
    print("%-10s maskPx=%6d trunk∩=%6d  ratio=%.3f"
          % (pat, int(pm.sum()), int((pm & trunk).sum()),
             (pm & trunk).sum() / max(1, trunk.sum())))

print()
print("=== R6 traits.json values 现状")
tr = json.load(open(os.path.join(B, "01_Data", "traits.json"), encoding="utf-8"))
for item in tr.get("categories", tr):
    print(item["id"], "=", item.get("values"))

print()
print("=== R7 ORIG_EAR_H")
s = io.open(os.path.join(os.path.dirname(__file__), "run_assemble.py"),
            encoding="utf-8").read()
for i, ln in enumerate(s.split("\n"), 1):
    if "ORIG_EAR_H" in ln:
        print("  line", i, ln.strip())
print("assigned:", any(ln.strip().startswith("ORIG_EAR_H =")
                      for ln in s.split("\n")))
