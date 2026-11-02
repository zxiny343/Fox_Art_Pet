# -*- coding: utf-8 -*-
"""v1.1 效果演示：
1) 清晰度：同尺寸 168px 下，旧渲染（work=168）vs 新渲染（2x 超采样+锐化）
2) 散步：模拟 3 分钟，输出位置轨迹
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'sim'))
sys.path.insert(0, os.path.join(ROOT, 'pet'))

import anim as AN          # noqa: E402
import artmap as AM        # noqa: E402
import wander as WD        # noqa: E402
import config as CFG       # noqa: E402
from fox_ecosystem_sim import phenotype as PH          # noqa: E402
import fox_ecosystem_sim as M                          # noqa: E402

SIZE = CFG.DEFAULTS['base_size']

w = M.World(dict(M.TUNED_V3_PARAMS), 20261101)
geno = dict(w.foxes[sorted(w.alive_ids)[0]].geno)
spec = AM.to_art(PH(geno))
items = [('idle_breath', 0.30), ('idle_tail_sway', 0.4)]

# ---- 1. 清晰度对比 -------------------------------------------------------
old = AN.render_frame(spec, 0, items, size=SIZE, work=max(SIZE, 256))[0]
new_l = AN.get_layers(spec, int(SIZE * 2))
new = AN.render_frame(spec, 0, items, size=SIZE, layers=new_l,
                      work=int(SIZE * 2))[0]
new = new.filter(__import__('PIL.ImageFilter', fromlist=['UnsharpMask'])
                 .UnsharpMask(radius=1.0, percent=55, threshold=2))

zoom = 4
tw, th = SIZE, int(SIZE * AN.ASPECT)
pad, head = 10, 26
tiles = [('旧：渲染 256 直接缩', old), ('新：2x 超采样 + 锐化', new)]
out = Image.new('RGB', ((tw * zoom + pad) * 2 + pad, th * zoom + head + pad * 2),
                (245, 246, 248))
dr = ImageDraw.Draw(out)
try:
    f = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 16)
except Exception:
    f = ImageFont.load_default()
for i, (name, im) in enumerate(tiles):
    big = im.resize((tw * zoom, th * zoom), Image.NEAREST)
    bg = Image.new('RGBA', big.size, (255, 255, 255, 255))
    bg.alpha_composite(big)
    x = pad + i * (tw * zoom + pad)
    out.paste(bg.convert('RGB'), (x, head))
    dr.text((x, 5), name, fill=(40, 44, 52), font=f)
op = os.path.join(ROOT, 'docs', 'quality-v11.png')
out.save(op)
print('saved', op)

# ---- 2. 散步轨迹模拟 -----------------------------------------------------
wd = WD.Wanderer(seed=42, rest=(4.0, 14.0), speed=(55.0, 95.0))
x = 1500.0                     # 从右下角出发
X_MIN, X_MAX = 6.0, 1919.0 - 168 - 5
trail = []
dt = 1 / 30.0
for i in range(int(180 / dt)):          # 模拟 3 分钟
    dx, walking = wd.tick(dt, x, X_MIN, X_MAX)
    x += dx
    trail.append((i * dt, x, wd.state))

walk_time = sum(1 for t in trail if t[2] == 'walk') * dt
trips = wd.trips
xs = [t[1] for t in trail]
print('3 分钟模拟：完整走了 %d 段、行走 %.0f 秒，'
      'x 从 %.0f 移动到 %.0f（活动范围 %.0f px）'
      % (trips, walk_time, trail[0][1], xs[-1], max(xs) - min(xs)))
