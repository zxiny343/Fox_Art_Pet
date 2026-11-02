# -*- coding: utf-8 -*-
"""探测母版上 belly（浅色区）的实际分布，用于曜金的点状配色区域定义。"""
import os
import sys

BASE = "C:/Users/zxiny/WorkBuddy/2026-11-01-00-53-44/Fox_Art"
sys.path.insert(0, BASE + "/tools")
import fox_traits as ft
import numpy as np
from PIL import Image
from scipy import ndimage

MASTER = BASE + "/assets/master/Base/fox_base_blue_q4@1024.png"
cws, _ = ft.load_colorways(BASE + "/01_Data/colorways.json")
src = cws["blue"]

im = Image.open(MASTER).convert("RGBA")
arr = np.asarray(im).astype(np.float32)
work = ft._unpremultiply(arr[..., :3], arr[..., 3])
a = arr[..., 3]

roles = ft.ROLES
srcarr = np.stack([ft.hex2rgb(src[r]) for r in roles])
d2 = ((work[..., None, :] - srcarr[None, None, :, :]) ** 2).sum(-1)
w = 1.0 / (d2 + 200.0) ** 2
w = w / w.sum(-1, keepdims=True)
bi = roles.index("belly")
belly = (w[..., bi] > 0.45) & (a > 40)

lab, n = ndimage.label(belly)
sizes = ndimage.sum(belly, lab, range(1, n + 1))
order = np.argsort(sizes)[::-1]
print("belly clusters:", n)
for idx in order[:10]:
    if sizes[idx] < 300:
        continue
    ys, xs = np.where(lab == (idx + 1))
    cx, cy = int(xs.mean()), int(ys.mean())
    print("  area=%7d  bbox=(%4d,%4d)-(%4d,%4d)  centroid=(%4d,%4d)" %
          (int(sizes[idx]), xs.min(), ys.min(), xs.max(), ys.max(), cx, cy))
