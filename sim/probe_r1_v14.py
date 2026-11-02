# -*- coding: utf-8 -*-
"""R1 修法专项复核：v1.4 新增的半透明绒毛到底落在哪、看上去是什么样。

出两张图：
  docs/v14-r1-short.png   v1.3 / v1.4 × 白底 / 深底 组装对照（short + thin）
  docs/v14-r1-mask.png    新增半透明像素的空间分布（绿=轮廓内，红=溢出轮廓）
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artmap as AM                                   # noqa: E402
from fox_ecosystem_sim import phenotype as PH         # noqa: E402

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M13 = os.path.join(PROJ, '_art_v1.3', 'delivery', 'Fox_Art', 'assets', 'master')
M14 = os.path.join(PROJ, '_art_v1.4', 'delivery', 'Fox_Art', 'assets', 'master')
DOCS = os.path.join(PROJ, 'docs')

TAILS = ('short', 'thin')
COATS = ('blue', 'orange')


def fnt(sz):
    for p in (r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\simhei.ttf'):
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, sz)
            except OSError:
                pass
    return ImageFont.load_default()


F_S, F_XS, F_T = fnt(15), fnt(12), fnt(18)


def on_bg(img, color):
    bg = Image.new('RGBA', img.size, color + (255,))
    bg.alpha_composite(img)
    return bg.convert('RGB')


def tail_spec(kind, coat, fur='short'):
    import render_kernel as RK
    g = dict(RK.sample_genotypes(1)[0])
    g.update({'Tn1': ('t', 't'), 'Tn2': ('t', 't'), 'V': ('v', 'v')})
    g['L1'] = g['L2'] = {'short': ('l', 'l'), 'mid': ('L', 'l'),
                         'long': ('L', 'L')}[fur]
    g['K'] = ('k', 'k')
    if kind == 'short':
        g['Tl'], g['Tf'] = ('tl', 'tl'), ('tf', 'tf')
    else:
        g['Tl'], g['Tf'] = ('Tl', 'tl'), ('tf', 'tf')
    spec = AM.to_art(PH(g))
    spec['coat'], spec['fur'] = coat, fur
    assert spec['tail'] == kind, (kind, spec['tail'])
    return spec


def main():
    # ---------- 1. 组装对照 ----------
    cw, ch = 330, 340
    rows = len(TAILS) * len(COATS)
    cols = 4                      # v1.3白 / v1.3深 / v1.4白 / v1.4深
    W = cw * cols + 20
    H = 76 + ch * rows + 20
    sheet = Image.new('RGB', (W, H), (246, 246, 249))
    dr = ImageDraw.Draw(sheet)
    dr.text((14, 12), 'R1 复核：短尾 / 细尾的 v1.3 → v1.4 组装对照',
            font=F_T, fill=(20, 20, 24))
    dr.text((14, 42), '左两列 v1.3（缺口用红标出），右两列 v1.4；白底看缺口，深底看半透明绒毛有没有雾块',
            font=F_XS, fill=(110, 110, 120))

    r = 0
    for kind in TAILS:
        for coat in COATS:
            spec = tail_spec(kind, coat)
            y = 76 + r * ch
            dr.text((14, y + 6), 'tail_%-6s coat=%s' % (kind, coat),
                    font=F_S, fill=(20, 20, 24))
            for c, (tag, bgcol) in enumerate(
                    (('v1.3', (255, 255, 255)), ('v1.3', (40, 42, 52)),
                     ('v1.4', (255, 255, 255)), ('v1.4', (40, 42, 52)))):
                AM.MASTER = M13 if tag == 'v1.3' else M14
                img, _ = AM._compose(spec, 1024)
                rgb = np.asarray(on_bg(img, bgcol)).copy()
                if tag == 'v1.3':
                    m = AM.body_mask('short')
                    a = np.asarray(img.convert('RGBA'))[..., 3]
                    hole = m & (a < 8)
                    if int(hole.sum()) >= 5000:
                        rgb[hole] = (232, 32, 32)
                tile = Image.fromarray(rgb).crop((120, 220, 700, 740)) \
                                           .resize((cw - 10, ch - 40), Image.LANCZOS)
                x = 10 + c * cw
                sheet.paste(tile, (x + 4, y + 30))
                dr.rectangle([x + 3, y + 29, x + 4 + cw - 10, y + 29 + ch - 40],
                             outline=(205, 205, 212))
                dr.text((x + 6, y + ch - 6), '%s %s' % (tag, '白底' if bgcol[0] > 200 else '深底'),
                        font=F_XS, fill=(90, 90, 100))
            r += 1
    AM.MASTER = M14
    out1 = os.path.join(DOCS, 'v14-r1-short.png')
    sheet.save(out1)
    print('->', out1)

    # ---------- 2. 新增半透明像素的空间分布 ----------
    base = np.asarray(Image.open(os.path.join(
        M14, 'Base', 'fox_base_blue_q4@1024.png')).convert('RGBA').split()[3]) > 8
    tiles = []
    for kind in TAILS:
        a13 = np.asarray(Image.open(os.path.join(M13, 'Tails', 'tail_%s.png' % kind))
                         .convert('RGBA'))[..., 3]
        a14 = np.asarray(Image.open(os.path.join(M14, 'Tails', 'tail_%s.png' % kind))
                         .convert('RGBA'))[..., 3]
        new = (a14 > 8) & (a13 <= 8)              # v1.4 新长出来的像素
        semi = new & (a14 <= 200)                 # 其中半透明的
        inside = semi & base
        outside = semi & ~base
        tiles.append((kind, new, semi, inside, outside))
        print('%-6s 新增 %6d（半透明 %6d）  轮廓内 %6d  溢出轮廓 %6d'
              % (kind, int(new.sum()), int(semi.sum()),
                 int(inside.sum()), int(outside.sum())))

    tw = 300
    W2 = tw * len(tiles) + 20
    H2 = 60 + tw + 30
    sh2 = Image.new('RGB', (W2, H2), (246, 246, 249))
    d2 = ImageDraw.Draw(sh2)
    d2.text((14, 10), 'v1.4 新增半透明绒毛的分布：绿 = 落在母版轮廓内（对），红 = 溢出轮廓（会在桌宠上显雾）',
            font=F_XS, fill=(20, 20, 24))
    for i, (kind, new, semi, inside, outside) in enumerate(tiles):
        rgb = np.full((1024, 1024, 3), 255, np.uint8)
        rgb[inside] = (40, 160, 90)
        rgb[outside] = (232, 40, 40)
        t = Image.fromarray(rgb).crop((120, 220, 700, 740)).resize((tw - 10, tw - 10))
        x = 10 + i * tw
        sh2.paste(t, (x + 4, 46))
        d2.rectangle([x + 3, 45, x + 4 + tw - 10, 45 + tw - 10], outline=(205, 205, 212))
        d2.text((x + 6, 46 + tw - 4),
                'tail_%s  内 %d / 溢出 %d' % (kind, int(inside.sum()), int(outside.sum())),
                font=F_XS, fill=(20, 20, 24))
    out2 = os.path.join(DOCS, 'v14-r1-mask.png')
    sh2.save(out2)
    print('->', out2)


if __name__ == '__main__':
    main()
