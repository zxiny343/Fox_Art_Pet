# -*- coding: utf-8 -*-
"""
外观多样性诊断（diversity.py）
================================================================
映射层跑通后暴露的真问题：默认等位频率会让种群「看起来几乎一样」。

本脚本只统计表型、不渲染（秒级），对比几组创始频率下的多样性：

  Simpson 指数 D  —— 「随机抓两只，外观不同的概率」，0=全同，1=全不同
  唯一签名数      —— (毛色, 毛质, 尾型, 耳型, 斑纹) 五元组去重后的个数
  各维熵          —— 找出是哪几个位点在拖低多样性
  生态代价        —— 同一批方案跑 20 年，看世代 / 近交 F / 杂合是否变差

结论（2026-11-01）：只有把 K（卷毛）从 0.30 降到 0.12 是零代价的 ——
12 个种子的逐种子 F 值完全相同，证明该位点与适应度完全解耦。
Er / A / D 参与适应度，改动会把近交 F 从 0.082 抬到 0.13，属权衡项。

用法： python diversity.py
"""

import sys
import os
import math
import statistics
from collections import Counter
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import artmap as AM
import fox_ecosystem_sim as M

SEEDS = [20261031 + i * 7919 for i in range(12)]
YEARS = 5

# 只调外观位点的创始频率；生态参数一字不动
VARIANTS = {
    '基线（当前 v0.6）': {},
    'K/Tn 减半': {'K': {'K': 0.15, 'k': 0.85},
                  'Tn1': {'T': 0.09, 't': 0.91},
                  'Tn2': {'T': 0.09, 't': 0.91}},
    'K/Tn 减半 + Er 均分': {'K': {'K': 0.15, 'k': 0.85},
                            'Tn1': {'T': 0.09, 't': 0.91},
                            'Tn2': {'T': 0.09, 't': 0.91},
                            'Er': {'ErP': 0.34, 'ErR': 0.33, 'Erf': 0.33}},
    'K/Tn 减半 + Er 均分 + 稀释增多': {
        'K': {'K': 0.15, 'k': 0.85},
        'Tn1': {'T': 0.09, 't': 0.91},
        'Tn2': {'T': 0.09, 't': 0.91},
        'Er': {'ErP': 0.34, 'ErR': 0.33, 'Erf': 0.33},
        'D': {'D': 0.62, 'd': 0.38},
        'A': {'A+': 0.30, 'As': 0.30, 'Ab': 0.20, 'Av': 0.20}},
}


def _run(job):
    seed, freq_over, years = job
    P = dict(M.TUNED_V3_PARAMS)
    P['_freq_override'] = freq_over
    w = M.World(P, seed)
    total = int(years * M.DAYS_PER_YEAR * M.HOURS_PER_DAY)
    while w.t < total and w.alive_ids:
        w.step()
    out = []
    for i in sorted(w.alive_ids):
        spec = AM.to_art(M.phenotype(w.foxes[i].geno))
        out.append((spec['coat'], spec['fur'], spec['tail'],
                    spec['ear'], spec['pattern']))
    return out


def simpson(items):
    n = len(items)
    if n < 2:
        return 0.0
    c = Counter(items)
    return 1.0 - sum(v * (v - 1) for v in c.values()) / (n * (n - 1))


def entropy(items):
    c = Counter(items)
    n = len(items)
    return -sum((v / n) * math.log(v / n, 2) for v in c.values())


def main():
    print('外观多样性诊断（%d 种子 × %d 生态年，只看表型不渲染）\n'
          % (len(SEEDS), YEARS))
    print('%-28s %6s %6s %7s %7s   %s'
          % ('方案', '存活', '唯一', 'Simpson', '尾型熵', '尾型分布'))

    for name, over in VARIANTS.items():
        jobs = [(s, over, YEARS) for s in SEEDS]
        with Pool(12) as pool:
            res = pool.map(_run, jobs)

        sigs, pops, per = [], [], {'coat': [], 'fur': [], 'tail': [],
                                   'ear': [], 'pattern': []}
        for r in res:
            pops.append(len(r))
            sigs.append(len(set(r)))
            for k, idx in (('coat', 0), ('fur', 1), ('tail', 2),
                           ('ear', 3), ('pattern', 4)):
                per[k].extend(x[idx] for x in r)

        tail_c = Counter(per['tail'])
        print('%-28s %6.1f %6.1f %7.3f %7.2f   %s'
              % (name, statistics.mean(pops), statistics.mean(sigs),
                 simpson(per['tail']), entropy(per['tail']),
                 ' '.join('%s:%d' % (k, v) for k, v in tail_c.most_common(5))))

    print('\n各维熵（越高越多样，单位 bit）：')
    print('%-28s %6s %6s %6s %6s %6s' % ('方案', '毛色', '毛质', '尾型', '耳型', '斑纹'))
    for name, over in VARIANTS.items():
        jobs = [(s, over, YEARS) for s in SEEDS]
        with Pool(12) as pool:
            res = pool.map(_run, jobs)
        per = {'coat': [], 'fur': [], 'tail': [], 'ear': [], 'pattern': []}
        for r in res:
            for k, idx in (('coat', 0), ('fur', 1), ('tail', 2),
                           ('ear', 3), ('pattern', 4)):
                per[k].extend(x[idx] for x in r)
        print('%-28s %6.2f %6.2f %6.2f %6.2f %6.2f'
              % (name, entropy(per['coat']), entropy(per['fur']),
                 entropy(per['tail']), entropy(per['ear']),
                 entropy(per['pattern'])))


# ---------------------------------------------------------------------------
# 第二部分：生态代价（同一批方案跑 20 年）
# ---------------------------------------------------------------------------

ECO_PLANS = {
    '基线 v0.6': {},
    '只改 K': {'K': {'K': 0.12, 'k': 0.88}},
    '只改 K+Er': {'K': {'K': 0.12, 'k': 0.88},
                  'Er': {'ErP': 0.34, 'ErR': 0.33, 'Erf': 0.33}},
    '只改 A/D': {'D': {'D': 0.62, 'd': 0.38},
                 'A': {'A+': 0.30, 'As': 0.30, 'Ab': 0.20, 'Av': 0.20}},
    'K+Er+A/D': {'K': {'K': 0.12, 'k': 0.88},
                 'Er': {'ErP': 0.34, 'ErR': 0.33, 'Erf': 0.33},
                 'D': {'D': 0.62, 'd': 0.38},
                 'A': {'A+': 0.30, 'As': 0.30, 'Ab': 0.20, 'Av': 0.20}},
}


def _eco(job):
    seed, over = job
    P = dict(M.TUNED_V3_PARAMS)
    if over:
        P['_freq_override'] = over
    return M.run_round(seed, P, 20)


def eco_cost():
    print('\n生态代价（%d 种子 × 20 生态年，生态参数一字未动）\n' % len(SEEDS))
    print('%-13s %6s %7s %7s %6s  %s'
          % ('方案', '世代', '近交F', '杂合', '崩溃', '逐种子 F'))
    for name, over in ECO_PLANS.items():
        with Pool(12) as pool:
            rs = pool.map(_eco, [(s, over) for s in SEEDS])
        F = [r['meanF_end'] for r in rs]
        print('%-13s %6.1f %7.3f %7.3f %5d/12  %s'
              % (name,
                 statistics.mean(r['max_generation'] for r in rs),
                 statistics.mean(F),
                 statistics.mean(r['het_end'] for r in rs),
                 sum(1 for r in rs if r['collapsed']),
                 ' '.join('%.2f' % f for f in F)))


if __name__ == '__main__':
    main()
    eco_cost()
