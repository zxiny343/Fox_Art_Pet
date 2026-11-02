# -*- coding: utf-8 -*-
"""R1 修法质量量化：新增绒毛区域在最终成品里到底有多实。

缺口判据只看 alpha<8，所以"填了但很淡"也会判通过。桌宠是透明背景，
真正要的是这块区域接近实心、且有毛流纹理。这里量化并最终出图。
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


def fnt(sz):
    for p in (r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\simhei.ttf'):
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, sz)
            except OSError:
                pass
    return ImageFont.load_default()


def tail_spec(kind, coat='blue'):
    g = dict(RK.sample_genotypes(1)[0])
    g.update({'Tn1': ('t', 't'), 'Tn2': ('t', 't'), 'V': ('v', 'v'),
              'L1': ('l', 'l'), 'L2': ('l', 'l'), 'K': ('k', 'k')})
    if kind == 'short':
        g['Tl'], g['Tf'] = ('tl', 'tl'), ('tf', 'tf')
    elif kind == 'thin':
        g['Tl'], g['Tf'] = ('Tl', 'tl'), ('tf', 'tf')
    else:
        g['Tl'], g['Tf'] = ('Tl', 'tl'), ('Tf', 'Tf')
    spec = AM.to_art(PH(g))
    spec['coat'], spec['fur'] = coat, 'short'
    if kind == 'normal':
        spec['tail'] = 'normal'      # tail_normal 没有基因出口，只能直接指定
    assert spec['tail'] == kind, (kind, spec['tail'])
    return spec


def main():
    print('%-8s %8s %8s %8s %8s %8s' %
          ('tail', '区域px', 'alpha均值', '中位', '>200占比', '纹理std'))
    res = {}
    for kind in ('normal', 'short', 'thin'):
        # 新增绒毛区域 = v1.4 有而 v1.3 没有的像素（仅 short/thin 有意义）
        a13 = np.asarray(Image.open(os.path.join(M13, 'Tails', 'tail_%s.png' % kind))
                         .convert('RGBA'))[..., 3]
        a14 = np.asarray(Image.open(os.path.join(M14, 'Tails', 'tail_%s.png' % kind))
                         .convert('RGBA'))[..., 3]
        zone = (a14 > 8) & (a13 <= 8)
        if kind == 'normal':
            # 参照：正常尾在尾巴窗口区域的实心度（用 v1.3 的 short 缺口区当窗口）
            s13 = np.asarray(Image.open(os.path.join(M13, 'Tails', 'tail_short.png'))
                             .convert('RGBA'))[..., 3]
            base = AM.body_mask('short')
            zone = base & (s13 <= 8) & (a14 > 8)
        spec = tail_spec(kind)
        img, _ = AM._compose(spec, 1024)
        a = np.asarray(img.convert('RGBA'))
        av = a[..., 3][zone]
        if av.size == 0:
            print('%-8s %8d  (区域为空)' % (kind, 0))
            continue
        lum = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2])[zone]
        print('%-8s %8d %8.1f %8.1f %7.1f%% %8.1f' %
              (kind, av.size, av.mean(), np.median(av),
               100.0 * (av > 200).mean(), lum.std()))
        res[kind] = (img, zone, a)

    # ---- 出图：三行分别是 normal / short / thin，左=成品，右=该区域 alpha 灰度 ----
    tw = 300
    W = tw * 2 + 30
    H = 70 + tw * len(res) + 20
    sh = Image.new('RGB', (W, H), (246, 246, 249))
    dr = ImageDraw.Draw(sh)
    dr.text((14, 10), 'R1 修法质量：左=成品（棋盘格=透明），右=新增绒毛区 alpha 灰度（白=实心255，黑=全透明）',
            font=fnt(13), fill=(20, 20, 24))
    dr.text((14, 36), 'normal 是参照：正常尾在尾巴窗口处应接近全白（实心）', font=fnt(12),
            fill=(110, 110, 120))

    chk = np.full((1024, 1024, 3), 220, np.uint8)
    chk[::16, :] = 200
    chk[:, ::16] = 200

    for i, kind in enumerate(('normal', 'short', 'thin')):
        if kind not in res:
            continue
        img, zone, a = res[kind]
        y = 70 + i * tw
        # 左：成品叠棋盘格
        bg = Image.fromarray(chk).convert('RGBA')
        bg.alpha_composite(img)
        l1 = bg.crop((120, 220, 700, 740)).resize((tw - 10, tw - 10), Image.LANCZOS)
        sh.paste(l1, (10, y))
        # 右：alpha 灰度
        g = np.zeros((1024, 1024, 3), np.uint8)
        g[..., 0] = g[..., 1] = g[..., 2] = a[..., 3]
        g[~zone] = 235
        l2 = Image.fromarray(g).crop((120, 220, 700, 740)) \
                               .resize((tw - 10, tw - 10), Image.LANCZOS)
        sh.paste(l2, (20 + tw, y))
        dr.text((12, y - 18), 'tail_%s' % kind, font=fnt(14), fill=(20, 20, 24))
        av = a[..., 3][zone]
        if av.size:
            dr.text((22 + tw, y - 18), 'alpha均值 %.0f  >200占 %.0f%%'
                    % (av.mean(), 100.0 * (av > 200).mean()),
                    font=fnt(12), fill=(150, 40, 40) if av.mean() < 180 else (30, 120, 60))
    out = os.path.join(DOCS, 'v14-r1-alpha.png')
    sh.save(out)
    print('->', out)


if __name__ == '__main__':
    main()
