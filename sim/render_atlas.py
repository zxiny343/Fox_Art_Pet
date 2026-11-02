# -*- coding: utf-8 -*-
"""
表型图谱（render_atlas.py）
================================================================
把映射层的**每一个出口**渲染成一张对照大图，用来：
  ① 目视验收「位点取值 → 部件」是否一一对应；
  ② 给设计文档/面板当图例；
  ③ 一眼看出哪些取值长得太像（美术侧重复）或根本没有素材。

输出 docs/fox-render/_atlas.png

用法： python render_atlas.py
"""

import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw, ImageFont

import artmap as AM
import fox_ecosystem_sim as M

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'docs', 'fox-render')

CELL = 250
LABEL_W = 116
ROWH = 296
MAXCOL = 6


def base_pheno():
    return {
        'color': '霜灰', 'pattern': 'p', 'ear': 'ErR', 'ear_size': 2,
        'eye': 'EyB', 'eye_shape': 2, 'hair_len': 0, 'curl': False,
        'tails': 1, 'hetero': False, 'glow': False, 'star': False,
        'halo': False, 'flame': False,
        'tail_len': 1, 'tail_fluff': True, 'ear_tip': 'tp',
        'inner_ear': False, 'tail_tip': 'tw',
    }


def v(**kw):
    p = base_pheno()
    p.update(kw)
    return p


# 每行： (行标题, [(格子文字, 表型)])
ROWS = [
    ('毛色\nA×D×W', [
        ('雪绒白 ww', v(color='雪绒白')),
        ('赤橙 A⁺D', v(color='赤橙')),
        ('奶油金 A⁺dd', v(color='奶油金')),
        ('霜灰 AsD', v(color='霜灰')),
        ('淡银蓝 Asdd', v(color='淡银蓝')),
        ('幽夜紫 AvD', v(color='幽夜紫')),
        ('淡雾紫 Avdd', v(color='淡雾紫')),
        ('墨黑 AbD', v(color='墨黑')),
        ('雾霭蓝 Abdd', v(color='雾霭蓝')),
        ('樱粉·突变', v(color='樱粉')),
        ('薄荷·突变', v(color='薄荷')),
        ('曜金·突变', v(color='曜金')),
    ]),
    ('毛质\nL1+L2 / K', [
        ('短毛 0–1', v(hair_len=0)),
        ('中毛 2–3', v(hair_len=2)),
        ('长毛 4', v(hair_len=4)),
        ('卷毛 K', v(hair_len=4, curl=True)),
    ]),
    ('尾型\nTn / Tl / Tf / V', [
        ('基准件 normal', {'_direct': {'tail': 'normal'}}),
        ('长尾 TlTl', v(tail_len=2)),
        ('短尾 tltl', v(tail_len=0)),
        ('蓬尾 中+蓬', v(tail_len=1, tail_fluff=True)),
        ('细尾 中+纤', v(tail_len=1, tail_fluff=False)),
        ('卷尾 K', v(curl=True)),
        ('双尾', v(tails=2)),
        ('三尾', v(tails=3)),
        ('四尾', v(tails=4)),
        ('五尾', v(tails=5)),
        ('九尾 V', v(tails=9)),
    ]),
    ('耳型\nEr / Ez', [
        ('大圆耳 ErR Ez2', v(ear='ErR', ear_size=2)),
        ('圆耳 ErR Ez1', v(ear='ErR', ear_size=1)),
        ('小圆耳 ErR Ez0', v(ear='ErR', ear_size=0)),
        ('尖耳 ErP', v(ear='ErP')),
        ('折耳 Erf', v(ear='Erf')),
        ('星耳 St', v(star=True)),
    ]),
    ('眼型 × 眼色\nEf / Ey', [
        ('圆·金', v(eye_shape=2, eye='EyG')),
        ('圆·青', v(eye_shape=2, eye='EyC')),
        ('圆·蓝', v(eye_shape=2, eye='EyB')),
        ('圆·紫', v(eye_shape=2, eye='EyV')),
        ('杏·金', v(eye_shape=1, eye='EyG')),
        ('杏·青', v(eye_shape=1, eye='EyC')),
        ('杏·蓝', v(eye_shape=1, eye='EyB')),
        ('杏·紫', v(eye_shape=1, eye='EyV')),
        ('细·金', v(eye_shape=0, eye='EyG')),
        ('细·青', v(eye_shape=0, eye='EyC')),
        ('细·蓝', v(eye_shape=0, eye='EyB')),
        ('细·紫', v(eye_shape=0, eye='EyV')),
    ]),
    ('异色瞳\nHt', [
        ('金/青', v(eye='EyG', hetero=True)),
        ('青/蓝', v(eye='EyC', hetero=True)),
        ('蓝/紫', v(eye='EyB', hetero=True)),
        ('紫/金', v(eye='EyV', hetero=True)),
    ]),
    ('斑纹\nP / Fl', [
        ('纯色 p', v(pattern='p')),
        ('斑点 Pg', v(pattern='Pg')),
        ('条纹 Ps', v(pattern='Ps')),
        ('虎斑 PT', v(pattern='PT')),
        ('火焰 Fl', v(pattern='p', flame=True)),
    ]),
    ('特殊层\nG / St / Ha', [
        ('发光 G', v(glow=True)),
        ('星纹 St', v(star=True)),
        ('光环 Ha', v(halo=True)),
        ('三者叠加', v(glow=True, star=True, halo=True)),
    ]),
]


def _job(args):
    row, col, pheno = args
    if '_direct' in pheno:      # 直接指定部件（美术基准件，无基因出口）
        spec = AM.to_art(base_pheno())
        spec.update(pheno['_direct'])
        img, _ = AM._compose(spec, CELL)
    else:
        img = AM.render(pheno, size=CELL)
    return row, col, img


def font(sz):
    for p in ('C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simhei.ttf'):
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, sz)
            except Exception:                                  # noqa: BLE001
                pass
    return ImageFont.load_default()


# 分页：把上面 8 行按主题切成几页，每页行宽不超过 MAXCOL 格
PAGES = [
    ('01 毛色与毛质', ['毛色\nA×D×W', '毛质\nL1+L2 / K']),
    ('02 尾型', ['尾型\nTn / Tl / Tf / V']),
    ('03 耳型与眼睛', ['耳型\nEr / Ez', '眼型 × 眼色\nEf / Ey', '异色瞳\nHt']),
    ('04 斑纹与特殊层', ['斑纹\nP / Fl', '特殊层\nG / St / Ha']),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    rowh = {t: c for t, c in ROWS}
    jobs = []
    for r, (_, cells) in enumerate(ROWS):
        for c, (_, ph) in enumerate(cells):
            jobs.append((r, c, ph))
    print('渲染 %d 格（%d px）…' % (len(jobs), CELL))
    with Pool(8) as pool:
        imgs = {}
        for r, c, im in pool.map(_job, jobs):
            imgs[(r, c)] = im

    f_title, f_cell, f_head = font(22), font(14), font(17)
    key_of = {t: i for i, (t, _) in enumerate(ROWS)}

    for page, (pname, titles) in enumerate(PAGES, 1):
        # 展开成「显示行」：超过 MAXCOL 的拆成多行
        disp = []
        for t in titles:
            cells = rowh[t]
            for i in range(0, len(cells), MAXCOL):
                disp.append((t if i == 0 else '', cells[i:i + MAXCOL],
                             key_of[t], i))
        W = LABEL_W + CELL * min(MAXCOL, max(len(x[1]) for x in disp))
        H = 64 + ROWH * len(disp)
        sheet = Image.new('RGB', (W, H), (248, 248, 250))
        d = ImageDraw.Draw(sheet)
        d.text((16, 16), 'Fox 表型图谱 %d/%d · %s · 22 位点 → 美术部件'
               '（artmap v1，资产 Fox_Art v1.3）' % (page, len(PAGES), pname),
               fill=(28, 28, 34), font=f_title)

        for k, (title, cells, row_i, off) in enumerate(disp):
            y0 = 64 + k * ROWH
            if k % 2 == 0:
                d.rectangle([0, y0, W, y0 + ROWH], fill=(243, 243, 246))
            if title:
                d.text((14, y0 + 14), title, fill=(85, 85, 96), font=f_head)
            for c, (label, _) in enumerate(cells):
                x0 = LABEL_W + c * CELL
                im = imgs[(row_i, off + c)]
                sheet.paste(im, (x0 + 4, y0 + 4), im)
                d.text((x0 + 8, y0 + CELL + 8), label, fill=(45, 45, 52),
                       font=f_cell)

        path = os.path.join(OUT, '_atlas_%02d_%s.png' % (page, pname.split(' ')[1]))
        sheet.save(path)
        print('  → %s  %dx%d  %.0f KB' % (os.path.basename(path), W, H,
                                          os.path.getsize(path) / 1024))


if __name__ == '__main__':
    main()
