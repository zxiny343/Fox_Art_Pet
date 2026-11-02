# -*- coding: utf-8 -*-
"""实测：母版尾巴段与躯干的空间关系，为 tail socket 窗口定几何。"""
import os
import sys
import json
import numpy as np
from PIL import Image

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = os.path.join(B, "assets", "master")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def runs(mask, y):
    row = mask[y]
    idx = np.where(row)[0]
    if len(idx) == 0:
        return []
    out = []
    s = idx[0]
    p = idx[0]
    for x in idx[1:]:
        if x != p + 1:
            out.append((int(s), int(p)))
            s = x
        p = x
    out.append((int(s), int(p)))
    return out


def main():
    import run_split as rs
    reg, _ = rs.load()
    master = np.asarray(Image.open(os.path.join(M, "Base", "fox_base_blue_q4@1024.png")).convert("RGBA"))
    ma = master[..., 3] > 8
    tail_m = rs.region_mask(reg["regions"]["tail"])
    tail_a = ma & tail_m
    # 躯干 = 母版去掉尾巴/耳/眼挖空区
    union = np.zeros((1024, 1024), bool)
    for k, spec in reg["regions"].items():
        union |= rs.region_mask(spec)
    body = ma & ~rs.dilate(union, reg.get("dilatePx", 3))

    print("母版 alpha 面积", int(ma.sum()), " 尾巴区面积", int(tail_a.sum()),
          " 躯干(挖空后)面积", int(body.sum()))
    print("尾巴与躯干重叠像素:", int((tail_a & body).sum()))

    print("\n--- 行剖面：母版 / 躯干 / 尾巴 ---")
    for y in range(300, 545, 15):
        print("y=%3d master=%s" % (y, runs(ma, y)))
        print("      body  =%s" % (runs(body, y),))
        print("      tail  =%s" % (runs(tail_a, y),))

    # 尾巴沿中轴方向的投影长度分布
    print("\n--- 尾巴沿 root->tip 轴的覆盖 ---")
    ys, xs = np.where(tail_a)
    print("尾巴像素 bbox:", xs.min(), ys.min(), xs.max(), ys.max())
    print("躯干在尾巴 bbox 内的像素数:", int(body[ys.min():ys.max()+1, xs.min():xs.max()+1].sum()))

    # 检查 y=505 切线下，尾巴下缘是否贴着躯干
    for y in (495, 500, 505, 510, 520, 540):
        ov = int((tail_a[y] & body[y]).sum())
        print("y=%d: tail=%d body=%d overlap=%d" % (y, int(tail_a[y].sum()), int(body[y].sum()), ov))


if __name__ == "__main__":
    main()
