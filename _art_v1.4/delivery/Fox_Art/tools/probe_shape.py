# -*- coding: utf-8 -*-
"""扫描母版 alpha 的行列剖面，用数据定位头/耳/尾的真实像素范围。"""
import os
import numpy as np
from PIL import Image

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = os.path.join(B, "assets", "master", "Base", "fox_base_blue_q4@1024.png")
a = np.asarray(Image.open(M).convert("RGBA"))[..., 3]
ON = a > 8
H, W = ON.shape


def runs(mask):
    """返回 True 区间的列表 [(start, end_inclusive), ...]"""
    out, s = [], None
    for i, v in enumerate(mask):
        if v and s is None:
            s = i
        elif not v and s is not None:
            out.append((s, i - 1))
            s = None
    if s is not None:
        out.append((s, len(mask) - 1))
    return out


print("=== 行剖面 (y: x 区间) ===")
for y in range(150, 940, 25):
    r = runs(ON[y])
    if r:
        print("y=%3d  " % y + "  ".join("[%3d-%3d w=%3d]" % (s, e, e - s + 1)
                                        for s, e in r))

print()
print("=== 列剖面 (x: y 区间) ===")
for x in range(150, 900, 25):
    r = runs(ON[:, x])
    if r:
        print("x=%3d  " % x + "  ".join("[%3d-%3d h=%3d]" % (s, e, e - s + 1)
                                        for s, e in r))

print()
print("=== 内容 bbox ===")
ys, xs = np.where(ON)
print("bbox x %d-%d  y %d-%d  w=%d h=%d" %
      (xs.min(), xs.max(), ys.min(), ys.max(),
       xs.max() - xs.min() + 1, ys.max() - ys.min() + 1))
print("fill px", int(ON.sum()))
