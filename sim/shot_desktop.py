# -*- coding: utf-8 -*-
"""桌面截图：间隔 N 秒抓两张，用于查看桌宠实际效果。"""
import os
import sys
import time

from PIL import ImageGrab

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
GAP = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
TAG = sys.argv[2] if len(sys.argv) > 2 else "shot"

os.makedirs(OUT, exist_ok=True)

paths = []
for i in (1, 2):
    if i == 2:
        time.sleep(GAP)
    img = ImageGrab.grab(all_screens=True)
    p = os.path.join(OUT, "desktop-%s-%d.png" % (TAG, i))
    img.save(p)
    paths.append(p)
    print(p, img.size, img.mode)

# 两张是否不同（判断桌宠是否在动）
from PIL import Image, ImageChops
a = Image.open(paths[0]).convert("RGB")
b = Image.open(paths[1]).convert("RGB")
if a.size != b.size:
    print("size differs")
else:
    diff = ImageChops.difference(a, b)
    bbox = diff.getbbox()
    print("diff bbox:", bbox)
