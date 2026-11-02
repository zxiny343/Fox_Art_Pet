# -*- coding: utf-8 -*-
"""
真实种群批量渲染（render_population.py）
================================================================
跑一次 v0.6 生态模拟，把存活个体全部经映射层渲染成 PNG，并输出：
  docs/fox-render/fox-<ID>.png        每只 512px 单图
  docs/fox-render/_population.png     带标注的拼版图
  docs/fox-render/population.json     每只的组装参数 + 提示 + 尾根缺口

用途：① 验证 22 位点 → 美术部件的端到端覆盖；② 目视检查真实种群是否
      出现「看起来一样但基因不同」或「根本没有素材」的情况。

用法： python render_population.py [--years 5] [--seed 20261031]
"""

import os
import sys
import json
import argparse
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import artmap as AM
import fox_ecosystem_sim as M

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'docs', 'fox-render')

# 中文标签（用于拼版图注释）
CN_COAT = {v: k for k, v in AM.COAT_BY_ZH.items()}
CN_TAIL = {'normal': '单尾', 'long': '长尾', 'short': '短尾', 'fluffy': '蓬尾',
           'thin': '细尾', 'curl': '卷尾', 'twin': '双尾', 'triple': '三尾',
           'quad': '四尾', 'quint': '五尾', 'nine': '九尾'}
CN_EAR = {'large': '大圆耳', 'small': '小圆耳', 'round': '圆耳',
          'pointed': '尖耳', 'fold': '折耳', 'star': '星耳'}
CN_PAT = {'solid': '纯色', 'spots': '斑点', 'stripes': '条纹',
          'tabby': '虎斑', 'flame': '火焰', 'gradient': '渐变', 'facemark': '面纹'}
CN_FUR = {'short': '短毛', 'mid': '中毛', 'long': '长毛', 'curly': '卷毛'}


def _job(item):
    fid, geno, gen, sex = item
    pheno = M.phenotype(geno)
    spec = AM.to_art(pheno)
    full, used = AM._compose(spec, 1024)
    holes = AM.tail_root_holes(full, spec['fur'])
    img = full.resize((512, 512), Image.LANCZOS)
    img.save(os.path.join(OUT, 'fox-%s.png' % fid))
    return {
        'id': fid, 'gen': gen, 'sex': sex,
        'pheno': pheno, 'spec': spec, 'used': used,
        'tail_holes': holes,
        'label': '%s · %s · %s · %s' % (
            CN_COAT.get(spec['coat'], spec['coat']),
            CN_FUR.get(spec['fur'], spec['fur']),
            CN_TAIL.get(spec['tail'], spec['tail']),
            CN_EAR.get(spec['ear'], spec['ear'])),
        'sub': '%s · %d代 · %s' % (
            CN_PAT.get(spec['pattern'], spec['pattern']),
            gen, '♂' if sex == 'm' else '♀'),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--years', type=int, default=5)
    ap.add_argument('--seed', type=int, default=20261031)
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    print('运行 v0.6 生态 %d 年（seed=%d）…' % (a.years, a.seed))
    w = M.World(dict(M.TUNED_V3_PARAMS), a.seed)
    total = int(a.years * M.DAYS_PER_YEAR * M.HOURS_PER_DAY)
    while w.t < total and w.alive_ids:
        w.step()
    ids = sorted(w.alive_ids)
    print('存活 %d 只，世代 %d' % (len(ids), max(w.foxes[i].gen for i in ids)))

    jobs = [(w.foxes[i].id, w.foxes[i].geno, w.foxes[i].gen, w.foxes[i].sex)
            for i in ids]
    with Pool(8) as pool:
        rows = pool.map(_job, jobs)

    # --- 统计 ---
    from collections import Counter
    stat = {
        'seed': a.seed, 'years': a.years, 'n_alive': len(rows),
        'coat': dict(Counter(r['spec']['coat'] for r in rows)),
        'tail': dict(Counter(r['spec']['tail'] for r in rows)),
        'ear': dict(Counter(r['spec']['ear'] for r in rows)),
        'fur': dict(Counter(r['spec']['fur'] for r in rows)),
        'pattern': dict(Counter(r['spec']['pattern'] for r in rows)),
        'notes': dict(Counter(n for r in rows for n in r['spec']['notes'])),
        'missing': dict(Counter(n for r in rows for n in r['spec']['missing'])),
        'tail_holes_max': max((r['tail_holes'] for r in rows), default=0),
        'foxes': rows,
    }
    with open(os.path.join(OUT, 'population.json'), 'w', encoding='utf-8') as f:
        json.dump(stat, f, ensure_ascii=False, indent=1)

    # --- 拼版图 ---
    cols = 6
    cw, ch = 190, 240
    nrow = (len(rows) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * cw, nrow * ch + 54), (247, 247, 249))
    d = ImageDraw.Draw(sheet)

    def font(sz):
        for p in ('C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simhei.ttf'):
            if os.path.isfile(p):
                try:
                    return ImageFont.truetype(p, sz)
                except Exception:                              # noqa: BLE001
                    pass
        return ImageFont.load_default()

    f1, f2 = font(13), font(11)
    d.text((10, 8), 'v0.6 生态 · %d 年 · 存活 %d 只 · 全部由 artmap 映射层渲染'
           % (a.years, len(rows)), fill=(30, 30, 34), font=font(16))

    for i, r in enumerate(rows):
        im = Image.open(os.path.join(OUT, 'fox-%s.png' % r['id'])).convert('RGBA')
        im = im.resize((168, 168), Image.LANCZOS)
        x, y = (i % cols) * cw + 11, (i // cols) * ch + 34
        sheet.paste(im, (x, y), im)
        d.text((x, y + 170), r['label'], fill=(35, 35, 40), font=f1)
        d.text((x, y + 187), r['sub'], fill=(110, 110, 120), font=f2)
        if r['tail_holes'] > 5000:
            d.text((x, y + 202), '⚠尾根缺口 %d' % r['tail_holes'],
                   fill=(190, 60, 40), font=f2)
    sheet.save(os.path.join(OUT, '_population.png'))

    print('\n毛色:', stat['coat'])
    print('尾型:', stat['tail'])
    print('耳型:', stat['ear'])
    print('毛质:', stat['fur'])
    print('斑纹:', stat['pattern'])
    print('提示（去重）:')
    for k, v in stat['notes'].items():
        print('   %2d×  %s' % (v, k))
    print('缺素材位点:')
    for k, v in stat['missing'].items():
        print('   %2d×  %s' % (v, k))
    print('\n输出目录 %s' % OUT)


if __name__ == '__main__':
    main()
