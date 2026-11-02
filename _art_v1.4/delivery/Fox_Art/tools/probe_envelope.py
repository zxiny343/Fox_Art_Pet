# -*- coding: utf-8 -*-
"""包络体检：检查各变体部件是否突破统一包络、以及身体核心是否保持对齐。"""
import os
import sys
import numpy as np
from PIL import Image

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = os.path.join(B, "assets", "master")
PART = os.path.join(M, "Parts")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SAFE = (147, 150, 876, 927)   # 统一包络（母版实测）


def bbox_of(p):
    a = np.asarray(Image.open(p).convert("RGBA"))[..., 3] > 8
    ys, xs = np.where(a)
    if len(xs) == 0:
        return None
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def main():
    print("统一包络 SAFE =", SAFE)
    for sub in ("Tails", "Ears"):
        d = os.path.join(M, sub)
        print("\n===", sub)
        for f in sorted(os.listdir(d)):
            if not f.endswith(".png"):
                continue
            bb = bbox_of(os.path.join(d, f))
            if bb is None:
                print("  %-20s EMPTY" % f)
                continue
            out = [k for k, v in zip("LTRB", bb) for k2, v2 in
                   zip("LTRB", SAFE) if False]
            over = []
            if bb[0] < SAFE[0]: over.append("x0-%d" % (SAFE[0] - bb[0]))
            if bb[1] < SAFE[1]: over.append("y0-%d" % (SAFE[1] - bb[1]))
            if bb[2] > SAFE[2]: over.append("x1+%d" % (bb[2] - SAFE[2]))
            if bb[3] > SAFE[3]: over.append("y1+%d" % (bb[3] - SAFE[3]))
            print("  %-20s bbox=%s  %s" % (f, bb, ("超出:" + ",".join(over)) if over else "在包络内"))

    # 身体核心一致性：比较各母版毛色的 body_core 区域
    print("\n=== 身体核心一致性（body_core 挖空后的躯干 alpha bbox）===")
    import run_split as rs
    reg, _ = rs.load()
    union = np.zeros((1024, 1024), bool)
    for k, spec in reg["regions"].items():
        union |= rs.region_mask(spec)
    hole = rs.dilate(union, 3)
    for f in sorted(os.listdir(os.path.join(M, "Base"))):
        if "fox_base" not in f:
            continue
        a = np.asarray(Image.open(os.path.join(M, "Base", f)).convert("RGBA"))[..., 3]
        core = (a > 8) & ~hole
        ys, xs = np.where(core)
        print("  %-34s bbox=%s area=%d" % (f, (int(xs.min()), int(ys.min()),
                                               int(xs.max()) + 1, int(ys.max()) + 1),
                                           int(core.sum())))


if __name__ == "__main__":
    main()
