# -*- coding: utf-8 -*-
"""清晰度实验：同一帧在不同 work（渲染分辨率）下，下采样到小尺寸后的质量。

判据：以 work=1024 渲染再 LANCZOS 缩到目标尺寸为「参考真值」，
比较各方案与真值的 PSNR（越高越接近真值），同时记录单帧耗时。
"""
import os
import sys
import time

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'sim'))
import anim as AN      # noqa: E402
import artmap as AM    # noqa: E402
from fox_ecosystem_sim import phenotype as PH  # noqa: E402

SIZE = int(sys.argv[1]) if len(sys.argv) > 1 else 168

import fox_ecosystem_sim as M                    # noqa: E402
w = M.World(dict(M.TUNED_V3_PARAMS), 20261101)
ids = sorted(w.alive_ids)
geno = dict(w.foxes[ids[0]].geno)
spec = AM.to_art(PH(geno))

items = [('idle_breath', 0.30), ('idle_tail_sway', 0.4)]


def render(work):
    layers = AN.get_layers(spec, work)
    t0 = time.time()
    img, _ = AN.render_frame(spec, 0, items, size=SIZE, layers=layers, work=work)
    return img, time.time() - t0


def psnr(a, b):
    A = np.asarray(a.convert('RGBA'), dtype=np.float64)
    B = np.asarray(b.convert('RGBA'), dtype=np.float64)
    mse = ((A - B) ** 2).mean()
    return 99.0 if mse <= 1e-9 else 10 * np.log10(255.0 ** 2 / mse)


# 参考真值：1024 渲染 → LANCZOS 到 SIZE
ref, t = render(1024)
print('ref work=1024  %.0f ms' % (t * 1000))

rows = []
for work in (SIZE, int(SIZE * 1.5), int(SIZE * 2), int(SIZE * 3), 512):
    img, dt = render(work)
    p = psnr(img, ref)
    rows.append((work, dt, p))
    print('work=%-4d  %5.1f ms  PSNR vs ref %5.2f dB' % (work, dt * 1000, p))

# 拼一张对比图（放大 3 倍看细节）
zoom = 3
tiles = [( 'ref 1024→%d' % SIZE, ref)] + [('work %d' % wk, render(wk)[0]) for wk, _, _ in rows]
tw, th = tiles[0][1].size
pad, head = 8, 22
out = Image.new('RGB', (tw * zoom * len(tiles) + pad * (len(tiles) + 1),
                        th * zoom + head + pad * 2), (245, 246, 248))
for i, (name, im) in enumerate(tiles):
    big = im.resize((tw * zoom, th * zoom), Image.NEAREST)
    bg = Image.new('RGBA', big.size, (255, 255, 255, 255))
    bg.alpha_composite(big)
    out.paste(bg.convert('RGB'), (pad + i * (tw * zoom + pad), head))

from PIL import ImageDraw, ImageFont  # noqa: E402
dr = ImageDraw.Draw(out)
try:
    f = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 15)
except Exception:
    f = ImageFont.load_default()
for i, (name, _) in enumerate(tiles):
    dr.text((pad + i * (tw * zoom + pad) + 2, 4), name, fill=(40, 44, 52), font=f)

op = os.path.join(ROOT, 'docs', 'probe-quality.png')
out.save(op)
print('saved', op, out.size)
