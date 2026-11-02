# -*- coding: utf-8 -*-
"""R2 目视复核：多尾根部（锚点 425,505）在 v1.3 / v1.4 的对照。

返修单 2.5 的口径：200×200 窗口、2.8× 放大、orange 与 mist_purple 两个浅色毛。
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artmap as AM                                   # noqa: E402
import render_kernel as RK                            # noqa: E402
from fox_ecosystem_sim import phenotype as PH         # noqa: E402

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M13 = os.path.join(PROJ, '_art_v1.3', 'delivery', 'Fox_Art', 'assets', 'master')
M14 = AM.MASTER
DOCS = os.path.join(PROJ, 'docs')
ZOOM = (325, 405, 525, 605)
TAILS = ('normal', 'twin', 'quint', 'nine')
COATS = ('orange', 'mist_purple')


def fnt(sz):
    for p in (r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\simhei.ttf'):
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, sz)
            except OSError:
                pass
    return ImageFont.load_default()


def spec_of(kind, coat):
    n = {'normal': 1, 'twin': 2, 'quint': 5, 'nine': 9}[kind]
    g = dict(RK.sample_genotypes(1)[0])
    # 尾数：Tn1/Tn2 累加 + V 九尾
    g['Tn1'] = ('T', 'T') if n >= 2 else ('t', 't')
    g['Tn2'] = ('T', 'T') if n >= 3 else ('t', 't')
    g['V'] = ('V', 'V') if n == 9 else ('v', 'v')
    g.update({'L1': ('l', 'l'), 'L2': ('l', 'l'), 'K': ('k', 'k'),
              'Tl': ('Tl', 'tl'), 'Tf': ('Tf', 'Tf')})
    s = AM.to_art(PH(g))
    s['coat'], s['fur'] = coat, 'short'
    if kind == 'normal':
        s['tail'] = 'normal'
    return s


def main():
    tw = 250
    W = tw * len(TAILS) + 20
    H = 76 + (tw + 26) * len(COATS) * 2 + 20
    sh = Image.new('RGB', (W, H), (246, 246, 249))
    dr = ImageDraw.Draw(sh)
    dr.text((14, 10), 'R2 复核：多尾根部（锚点 425,505 周边 200×200，2.8× 放大）',
            font=fnt(18), fill=(20, 20, 24))
    dr.text((14, 42), '上排 v1.3（有深色碎片与白缝），下排 v1.4。看根部有没有被描边围住的深色碎片、跨毛面的白缝',
            font=fnt(12), fill=(110, 110, 120))

    y = 76
    for coat in COATS:
        for ver, M in (('v1.3', M13), ('v1.4', M14)):
            AM.MASTER = M
            dr.text((14, y + 4), '%s  coat=%s' % (ver, coat), font=fnt(14),
                    fill=(150, 40, 40) if ver == 'v1.3' else (30, 120, 60))
            y += 24
            for i, kind in enumerate(TAILS):
                spec = spec_of(kind, coat)
                img, _ = AM._compose(spec, 1024)
                bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
                bg.alpha_composite(img)
                tile = bg.convert('RGB').crop(ZOOM).resize((tw - 10, tw - 10),
                                                           Image.LANCZOS)
                x = 10 + i * tw
                sh.paste(tile, (x + 4, y))
                dr.rectangle([x + 3, y - 1, x + 4 + tw - 10, y + tw - 10],
                             outline=(205, 205, 212))
                dr.text((x + 8, y + tw - 8), kind, font=fnt(12),
                        fill=(30, 30, 40))
            y += tw + 2
    AM.MASTER = M14
    out = os.path.join(DOCS, 'v14-r2-root.png')
    sh.save(out)
    print('->', out)


if __name__ == '__main__':
    main()
