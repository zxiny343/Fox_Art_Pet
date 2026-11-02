# -*- coding: utf-8 -*-
"""比较不同 socket 口径下各尾巴变体的覆盖率，选出"兜底件不必露脸"的最大口径。"""
import os
import sys
import numpy as np
from PIL import Image
from scipy import ndimage

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = os.path.join(B, "assets", "master")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    import run_split as rs
    reg, _ = rs.load()
    ma = np.asarray(Image.open(os.path.join(M, "Base", "fox_base_blue_q4@1024.png")).convert("RGBA"))
    a = ma[..., 3] > 8
    W = a & rs.region_mask(reg["regions"]["tail"])
    fitset = np.zeros((1024, 1024), bool)
    for k in ("ear_L", "ear_R", "eye_L", "eye_R"):
        fitset |= rs.dilate(rs.region_mask(reg["regions"][k]), 3)
    B0 = a & ~W & ~fitset
    seam = W & ndimage.binary_dilation(B0, iterations=4)

    tails = {}
    for f in sorted(os.listdir(os.path.join(M, "Tails"))):
        if f.endswith(".png") and "base" not in f:
            im = Image.open(os.path.join(M, "Tails", f)).convert("RGBA")
            if im.size == (1024, 1024):
                tails[f] = np.asarray(im)[..., 3] > 8

    for d in (0, 2, 4, 6, 8):
        soc = ndimage.binary_dilation(seam, iterations=d) & W
        line = ["dilate=%d area=%5d" % (d, int(soc.sum()))]
        worst = 1.0
        for f, tp in tails.items():
            c = float((tp & soc).sum()) / max(int(soc.sum()), 1)
            worst = min(worst, c)
            line.append("%s=%.2f" % (f.replace("tail_", "").replace(".png", ""), c))
        print("  ".join(line) + "   worst=%.3f" % worst)


if __name__ == "__main__":
    main()
