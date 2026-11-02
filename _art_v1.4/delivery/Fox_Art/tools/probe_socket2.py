# -*- coding: utf-8 -*-
"""定义 tail socket：窗口里"挖在身体上"的那部分（去掉尾巴会造成身体破洞的区域）。"""
import os
import sys
import math
import numpy as np
from PIL import Image
from scipy import ndimage

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = os.path.join(B, "assets", "master")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = (425, 505)
TIP = (205, 332)


def main():
    import run_split as rs
    reg, _ = rs.load()
    master = np.asarray(Image.open(os.path.join(M, "Base", "fox_base_blue_q4@1024.png")).convert("RGBA"))
    ma = master[..., 3] > 8
    tail_m = rs.region_mask(reg["regions"]["tail"])
    W = ma & tail_m                                    # 尾巴窗口（母版尾巴像素）
    union = np.zeros((1024, 1024), bool)
    for k, sp in reg["regions"].items():
        union |= rs.region_mask(sp)
    B0 = ma & ~rs.dilate(union, 3)                     # 去尾去耳去眼后的身体

    # 尾巴窗口里"贴着身体"的像素（=挖掉会在身体上留洞的部分）
    near = ndimage.binary_dilation(B0, iterations=4)
    hole = W & near

    ux = TIP[0] - ROOT[0]; uy = TIP[1] - ROOT[1]
    L = math.hypot(ux, uy); ux, uy = ux / L, uy / L
    yy, xx = np.mgrid[0:1024, 0:1024]
    t = (xx - ROOT[0]) * ux + (yy - ROOT[1]) * uy      # 沿尾轴投影（根=0，尖=L）
    perp = -(xx - ROOT[0]) * uy + (yy - ROOT[1]) * ux

    print("窗口像素 W =", int(W.sum()), "  其中贴身体(潜在破洞) =", int(hole.sum()),
          "  占比 %.1f%%" % (100.0 * hole.sum() / W.sum()))
    print("尾轴长度 L = %.1f" % L)
    print("hole 沿轴投影 t: min=%.1f max=%.1f" % (t[hole].min(), t[hole].max()))
    print("W    沿轴投影 t: min=%.1f max=%.1f" % (t[W].min(), t[W].max()))
    print("hole 横向 perp: min=%.1f max=%.1f" % (perp[hole].min(), perp[hole].max()))

    # 分位：找出覆盖 hole 95% 的 t 上限
    ts = np.sort(t[hole])
    for q in (0.50, 0.80, 0.90, 0.95, 0.98, 1.0):
        print("  hole t 分位 %.2f -> %.1f" % (q, ts[int(q * (len(ts) - 1))]))

    # 各尾巴变体对 hole 的覆盖率
    print("\n--- 各尾巴变体对 hole 的覆盖率 ---")
    for f in sorted(os.listdir(os.path.join(M, "Tails"))):
        if not f.endswith(".png"):
            continue
        a = np.asarray(Image.open(os.path.join(M, "Tails", f)).convert("RGBA"))[..., 3] > 8
        cov = (a & hole).sum() / max(hole.sum(), 1)
        winc = (a & ~W).sum()
        print("  %-18s hole覆盖 %.3f   窗口外像素 %d" % (f, cov, int(winc)))

    np.save(os.path.join(B, "01_Data", "_hole_mask.npy"), hole)


if __name__ == "__main__":
    main()
