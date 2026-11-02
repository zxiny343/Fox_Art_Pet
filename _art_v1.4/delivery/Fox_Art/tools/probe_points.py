# -*- coding: utf-8 -*-
"""按部位采样曜金输出的实际颜色，验证点状配色是否达标。"""
import os
import sys

BASE = "C:/Users/zxiny/WorkBuddy/2026-11-01-00-53-44/Fox_Art"
sys.path.insert(0, BASE + "/tools")
import numpy as np
from PIL import Image

P = BASE + "/assets/master/Base/fox_base_obsidian_gold_q4@1024.png"
im = Image.open(P).convert("RGBA")
arr = np.asarray(im).astype(np.float32)
a = arr[..., 3]

BOXES = [
    ("forehead  ", 700, 380), ("brow      ", 700, 470), ("cheek     ", 660, 560),
    ("muzzle    ", 745, 555), ("chest     ", 681, 705), ("thigh     ", 450, 700),
    ("tailMid   ", 300, 450), ("tailTip   ", 230, 340), ("earInnerL ", 533, 338),
    ("back      ", 565, 640),
]


def goldness(rgb):
    """粗略判断是否偏金：R 明显高于 B 且有一定饱和。"""
    r, g, b = rgb
    return (r - b) > 25 and r > 90


print("name        avgRGB            alpha  gold?")
for name, cx, cy in BOXES:
    patch = arr[cy - 12:cy + 12, cx - 12:cx + 12]
    pa = patch[..., 3]
    m = pa > 120
    if m.sum() < 20:
        print("%s  (透明)" % name)
        continue
    rgb = patch[..., :3][m].mean(0)
    print("%s  %6.0f,%6.0f,%6.0f  %5.0f  %s" %
          (name, rgb[0], rgb[1], rgb[2], pa[m].mean(), "GOLD" if goldness(rgb) else "-"))
