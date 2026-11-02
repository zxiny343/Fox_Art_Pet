# -*- coding: utf-8 -*-
"""降级表效果对照图。

左列 = 关降级（v1.3 原始素材），右列 = 开降级（桌面/面板实际会看到的）。
缺口像素染红，直接对比「修不修」的差别。
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import artmap as AM            # noqa: E402
import render_kernel as RK     # noqa: E402
from fox_ecosystem_sim import phenotype as PH   # noqa: E402


def fnt(sz):
    for p in ('C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/arial.ttf'):
        if os.path.isfile(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def geno(kind):
    g = dict(RK.sample_genotypes(1)[0])
    one = {'Tn1': ('t', 't'), 'Tn2': ('t', 't'), 'V': ('v', 'v')}
    t = {'thin': dict(one, K=('k', 'k'), Tl=('Tl', 'tl'), Tf=('tf', 'tf')),
         'short': dict(one, K=('k', 'k'), Tl=('tl', 'tl'), Tf=('tf', 'tf'))}
    return dict(g, **t[kind])


def panel(g, allow, tag):
    img, m = RK.render(geno=g, size=1024, allow_degrade=allow,
                       use_cache=False, check_holes=True)
    a = np.asarray(img)
    hole = AM.body_mask(m['fur']) & (a[..., 3] < 8)
    bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
    bg.alpha_composite(img)
    rgb = np.asarray(bg.convert('RGB')).copy()
    # 只染「数量级明显」的破面；长毛母版轮廓差（2–3 千）不染，避免误导成还没修好
    if int(hole.sum()) >= RK.HOLE_FAIL:
        rgb[hole] = (232, 32, 32)
    tile = Image.fromarray(rgb).crop((150, 220, 700, 700)).resize((330, 288),
                                                                 Image.LANCZOS)
    return tile, m, int(hole.sum())


def main():
    cases = [('thin', '细尾 thin'), ('short', '短尾 short')]
    cw, ch = 340, 360
    W = cw * 4 + 20
    H = 60 + ch
    sheet = Image.new('RGB', (W, H), (252, 252, 253))
    dr = ImageDraw.Draw(sheet)
    dr.text((14, 12), '渲染内核降级表：v1.3 素材（左） vs 桌面实际显示（右）',
            font=fnt(23), fill=(20, 20, 24))
    dr.text((14, 42), '红色 = 母版轮廓内、组装后却透明的像素（≥5000px 才标红）；'
                      '右列渲染前把 thin/short 临时换成 normal', font=fnt(13),
            fill=(110, 110, 120))

    r = 0
    for kind, label in cases:
        g = geno(kind)
        for c, (allow, cap) in enumerate(((False, '关降级 · 原素材'),
                                          (True, '开降级 · 实际显示'))):
            x = 14 + (r * 2 + c) * cw
            y = 60
            tile, m, hole = panel(g, allow, kind)
            sheet.paste(tile, (x, y + 26))
            dr.rectangle([x, y + 26, x + 329, y + 26 + 287],
                         outline=(200, 200, 208))
            ok = hole < RK.HOLE_FAIL
            dr.text((x, y + 4), '%s · %s' % (label, cap), font=fnt(15),
                    fill=(30, 30, 40))
            dr.text((x, y + 320), '缺口 %d px  %s'
                    % (hole, '可用' if ok else '不可用'),
                    font=fnt(14), fill=(30, 120, 60) if ok else (200, 30, 30))
            if allow and ok:
                dr.text((x, y + 340), '残余为长毛母版轮廓差，非透空破面',
                        font=fnt(11), fill=(120, 120, 130))
        r += 1

    out = os.path.join(HERE, '..', 'docs', 'render-kernel-degrade.png')
    sheet.save(out)
    print(os.path.abspath(out))


if __name__ == '__main__':
    main()
