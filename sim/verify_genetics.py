# -*- coding: utf-8 -*-
"""
幻想小狐狸 —— 遗传引擎自检
=============================
不跑生态，只验证「遗传机制本身是否符合设计稿 §2.1 声明的遗传定律」。
每次改动配色表 / 位点表 / 表型函数后都应该重跑一遍。

    python sim/verify_genetics.py
"""

import random
import sys
from collections import Counter

sys.path.insert(0, __file__.rsplit('\\', 1)[0])
sys.path.insert(0, __file__.rsplit('/', 1)[0])

from fox_ecosystem_sim import (LOCUS_KEYS, LOCUS_SPEC, FOUNDER_FREQ, BASE_PARAMS,
                               World, phenotype, random_normal_trunc)

RNG = random.Random(20261031)
PASS = 0
FAIL = 0


def check(name, ok, detail):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  [通过] %-34s %s' % (name, detail), flush=True)
    else:
        FAIL += 1
        print('  [失败] %-34s %s' % (name, detail), flush=True)


def base_geno():
    return {k: (next(iter(FOUNDER_FREQ[k])),) * 2 for k in LOCUS_KEYS}


def gamete(g):
    return {k: g[k][RNG.randrange(2)] for k in LOCUS_KEYS}


def cross(g1, g2, n=12000):
    return [phenotype({k: (gamete(g1)[k], gamete(g2)[k]) for k in LOCUS_KEYS})
            for _ in range(n)]


def close(a, b, tol=0.012):
    return abs(a - b) <= tol


def main():
    print('一、孟德尔分离比', flush=True)
    g = {**base_geno(), 'A': ('A+', 'As'), 'W': ('W', 'W'), 'D': ('D', 'D')}
    c = Counter(x['color'] for x in cross(g, g))
    tot = sum(c.values())
    r = c['赤橙'] / tot
    check('完全显性 3:1', close(r, 0.75), '赤橙 %.3f / 霜灰 %.3f' % (r, 1 - r))

    g = {**base_geno(), 'A': ('A+', 'A+'), 'D': ('D', 'd'), 'W': ('W', 'W')}
    c = Counter(x['color'] for x in cross(g, g))
    tot = sum(c.values())
    check('隐性性状隔代重现', close(c['奶油金'] / tot, 0.25),
          '奶油金（dd）%.3f' % (c['奶油金'] / tot))

    print('二、上位效应', flush=True)
    g = {**base_geno(), 'W': ('W', 'w')}
    c = Counter(x['color'] for x in cross(g, g))
    tot = sum(c.values())
    check('W 位点 ww 上位掩盖 A/D', close(c['雪绒白'] / tot, 0.25),
          '雪绒白 %.3f（表型被掩盖，但 A/D 基因型仍在）' % (c['雪绒白'] / tot))

    g = {**base_geno(), 'V': ('V', 'v'), 'Tn1': ('T', 'T'), 'Tn2': ('T', 'T')}
    c = Counter(x['tails'] for x in cross(g, g))
    tot = sum(c.values())
    check('V 九尾显性上位覆盖 Tn', close(c[9] / tot, 0.75),
          '九尾 %.3f / 五尾 %.3f' % (c[9] / tot, c[5] / tot))

    print('三、不完全显性', flush=True)
    g = {**base_geno(), 'Ez': ('Ez', 'ez')}
    c = Counter(x['ear_size'] for x in cross(g, g))
    tot = sum(c.values())
    check('耳大小 剂量效应 1:2:1',
          close(c[0] / tot, 0.25) and close(c[1] / tot, 0.5) and close(c[2] / tot, 0.25),
          '大 %.3f / 中 %.3f / 小 %.3f' % (c[0] / tot, c[1] / tot, c[2] / tot))

    print('四、多基因数量性状', flush=True)
    g = {**base_geno(), 'Tn1': ('T', 't'), 'Tn2': ('T', 't'), 'V': ('v', 'v')}
    c = Counter(x['tails'] for x in cross(g, g))
    tot = sum(c.values())
    dist = [c[i] / tot for i in range(1, 6)]
    check('尾数 1:4:6:4:1 累加分布',
          all(close(dist[i], exp, 0.02) for i, exp in enumerate([.0625, .25, .375, .25, .0625])),
          ' '.join('%d尾=%.3f' % (i + 1, dist[i]) for i in range(5)))

    g = {**base_geno(), 'L1': ('L', 'l'), 'L2': ('L', 'l')}
    c = Counter(x['hair_len'] for x in cross(g, g))
    tot = sum(c.values())
    dist = [c[i] / tot for i in range(5)]
    check('毛长 5 档累加分布',
          all(close(dist[i], exp, 0.02) for i, exp in enumerate([.0625, .25, .375, .25, .0625])),
          ' '.join('%d=%.3f' % (i, dist[i]) for i in range(5)))

    print('五、复等位显性序列', flush=True)
    base = base_geno()
    # As/Ab × As/Ab：As > Ab，预期 霜灰 3 : 墨黑 1
    g = {**base, 'A': ('As', 'Ab'), 'W': ('W', 'W'), 'D': ('D', 'D')}
    c = Counter(x['color'] for x in cross(g, g)); tot = sum(c.values())
    check('As > Ab 显性序列', close(c['霜灰'] / tot, 0.75) and close(c['墨黑'] / tot, 0.25),
          '霜灰 %.3f / 墨黑 %.3f' % (c['霜灰'] / tot, c['墨黑'] / tot))
    # A+/A+ × As/As：F1 全赤橙 -> 证明 A+ 覆盖 As
    g1 = {**base, 'A': ('A+', 'A+'), 'W': ('W', 'W'), 'D': ('D', 'D')}
    g2 = {**base, 'A': ('As', 'As'), 'W': ('W', 'W'), 'D': ('D', 'D')}
    c = Counter(x['color'] for x in cross(g1, g2)); tot = sum(c.values())
    check('A+ 覆盖 As（F1 全显性）', close(c['赤橙'] / tot, 1.0),
          '赤橙 %.3f（全部携带 As，外观看不出来）' % (c['赤橙'] / tot))

    print('六、亲缘系数（标准谱系）', flush=True)
    w = World(BASE_PARAMS, 1)

    def add(i, mo, fa, gen):
        f = w.foxes[i] = type(w.foxes[list(w.foxes)[0]]).__new__(type(w.foxes[list(w.foxes)[0]]))
        f.id = i
        f.mother = mo
        f.father = fa
        f.gen = gen
        f.alive = True
        f.sex = 'F'
        f.geno = {k: ('X', 'X') for k in LOCUS_KEYS}
        f.source = 'test'
        f.is_founder = False
        f.ever_bred = False
        f.torpor_flag = False
        f.pheno = phenotype(f.geno)

    for i in (1, 2, 4, 5):
        add(i, None, None, 0)
    add(11, 1, 2, 1)
    add(12, 1, 2, 1)
    check('全同胞 r = 0.5', close(w.relationship(11, 12), 0.5, 0.001),
          'r = %.4f' % w.relationship(11, 12))
    add(16, 11, 4, 2)
    add(17, 12, 5, 2)
    check('表亲 r = 0.125', close(w.relationship(16, 17), 0.125, 0.001),
          'r = %.4f' % w.relationship(16, 17))
    add(18, 1, 4, 1)
    check('半同胞 r = 0.25', close(w.relationship(11, 18), 0.25, 0.001),
          'r = %.4f' % w.relationship(11, 18))
    check('无关个体 r = 0', close(w.relationship(4, 5), 0.0, 0.001),
          'r = %.4f' % w.relationship(4, 5))
    add(13, 11, 12, 2)
    check('全同胞后代 F = 0.25', close(w.F_of(13), 0.25, 0.001), 'F = %.4f' % w.F_of(13))

    print('七、基因型 ≠ 表型（§2.5）', flush=True)
    gA = {**base_geno(), 'A': ('A+', 'As'), 'D': ('D', 'd'), 'W': ('W', 'w')}
    gB = {**base_geno(), 'A': ('A+', 'A+'), 'D': ('D', 'D'), 'W': ('W', 'W')}
    check('外观相同但基因型不同', phenotype(gA)['color'] == phenotype(gB)['color'],
          '两者均为「%s」，但 A/D/W 位点不同 -> 后代表现不同' % phenotype(gA)['color'])

    print('八、截断正态分布 sanity', flush=True)
    vals = [random_normal_trunc(40, 8, 25, 70, RNG) for _ in range(5000)]
    check('截断正态落在区间内', all(25 <= v <= 70 for v in vals),
          'min=%.1f max=%.1f mean=%.1f' % (min(vals), max(vals), sum(vals) / len(vals)))

    print(flush=True)
    print('通过 %d 项，失败 %d 项' % (PASS, FAIL), flush=True)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
