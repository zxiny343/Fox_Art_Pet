# -*- coding: utf-8 -*-
"""R2 复核：把多尾根部放到 4× 看看到底糊不糊。

三列对照：normal 组装 / nine 组装 / tail_nine 素材本身。
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, '..', '_art_v1.3', 'delivery', 'Fox_Art')
sys.path.insert(0, os.path.join(ART, 'tools'))
import run_assemble as RA  # noqa: E402

BOX = (325, 405, 525, 605)      # 200x200，绕锚点 (425,505)
Z = 4
W = (BOX[2] - BOX[0]) * Z
BG = (252, 252, 253)


def fnt(sz):
    for p in ('C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/arial.ttf'):
        if os.path.isfile(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def white(img):
    bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
    bg.alpha_composite(img.convert('RGBA'))
    return bg.convert('RGB')


items = []
for t in ('normal', 'twin', 'nine'):
    img, _ = RA.assemble(coat='blue', tail=t, ear='large', eye='round_blue',
                         verbose=False)
    items.append(('assemble tail_%s' % t, white(img)))
items.append(('asset tail_nine.png',
              white(Image.open(os.path.join(ART, 'assets', 'master', 'Tails',
                                            'tail_nine.png')))))
items.append(('asset tail_twin.png',
              white(Image.open(os.path.join(ART, 'assets', 'master', 'Tails',
                                            'tail_twin.png')))))

cols = len(items)
sheet = Image.new('RGB', (W * cols + 12 * (cols + 1), W + 60), BG)
dr = ImageDraw.Draw(sheet)
dr.text((14, 10), 'R2 复核 · 根部 4x（锚点 425,505 周围 200x200）',
        font=fnt(22), fill=(20, 20, 24))
for i, (label, im) in enumerate(items):
    x = 12 + i * (W + 12)
    sheet.paste(im.crop(BOX).resize((W, W), Image.LANCZOS), (x, 48))
    dr.text((x, 30), label, font=fnt(15), fill=(30, 30, 40))
    dr.rectangle([x, 48, x + W - 1, 48 + W - 1], outline=(200, 200, 208))

out = os.path.join(HERE, '..', 'docs', '_probe_root_4x.png')
sheet.save(out)
print(out)
