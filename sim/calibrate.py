# -*- coding: utf-8 -*-
"""
幻想小狐狸生态 —— 参数标定搜索
================================
用 Base 规则跑不通的地方，靠这组对照实验找出能跑通的参数区间。

评分目标（都是产品视角的可观测指标）：
  T1 出生流量   5 年出生数 ≥ 120        —— 决定用户能不能"看到事情发生"
  T2 世代推进   最大世代数 ≥ 20          —— 决定能不能叫"进化"
  T3 血统留存   存活创始系 ≥ 7/10        —— 决定家谱功能有没有内容
  T4 近交控制   末期平均 F ≤ 0.15        —— 决定系统是否陷入近交衰退
  T5 视觉多样性 末代表色数 ≥ 3 且单色占比 ≤ 60%
  T6 突变供给   5 年突变事件 ≥ 3 且至少 1 个存活到末代
"""

import itertools
import statistics
import sys

from fox_ecosystem_sim import BASE_PARAMS, run_round


def metrics(runs):
    g = lambda k: statistics.mean([r[k] for r in runs])
    colors = statistics.mean([len(r['end_colors']) for r in runs])
    dominance = statistics.mean([
        (max(r['end_colors'].values()) / max(1, sum(r['end_colors'].values())))
        for r in runs if r['end_colors']])
    return {
        'births': g('total_births'),
        'gens': g('max_generation'),
        'lines': g('founder_lines_alive'),
        'F': g('meanF_end'),
        'het_loss': g('het_loss_pct'),
        'colors': colors,
        'dominant_pct': dominance * 100,
        'muts': g('mutations_total'),
        'muts_alive': g('mutations_survived'),
        'maxpop': max(r['max_pop_seen'] for r in runs),
        'cap_ratio': g('cap_ratio'),
        'litters': g('total_litters'),
        'migrated': g('migrated'),
    }


def score(m):
    s = 0.0
    s += 1.0 * min(1.0, m['births'] / 120.0)
    s += 1.0 * min(1.0, m['gens'] / 20.0)
    s += 1.0 * min(1.0, m['lines'] / 7.0)
    s += 1.0 * (1.0 - min(1.0, m['F'] / 0.15))
    s += 1.0 * min(1.0, m['colors'] / 3.0)
    s += 1.0 * (1.0 - min(1.0, max(0.0, m['dominant_pct'] - 60.0) / 40.0))
    s += 1.0 * min(1.0, m['muts'] / 3.0)
    s += 0.5 * min(1.0, m['muts_alive'] / 1.0)
    return s


def main():
    seeds = [20261031 + i * 7919 for i in range(3)]
    grid = []
    for nmax in (20, 30):
        for life in (60, 40, 28):
            for juv in ((0.25, 0.35), (0.35, 0.45)):
                for imm in (False, True):
                    grid.append((nmax, life, juv, imm))
    # 额外一组：更替激进 + 季节性繁殖松弛
    rows = []
    for (nmax, life, juv, imm) in grid:
        P = dict(BASE_PARAMS)
        P.update({
            'Cap_mode': 'L_plus_slot',
            'N_max': nmax,
            'Lifespan_mean_days': life,
            'Lifespan_sd_days': max(5, life * 0.18),
            'Lifespan_min_days': max(16, life * 0.55),
            'Lifespan_max_days': life * 1.55,
            'Juv_mort_lo': juv[0],
            'Juv_mort_hi': juv[1],
            'Immigration_enable': imm,
            'Immigration_every_gen': 3,
            'Immigration_n': 1,
        })
        runs = [run_round(s, P, 5, label='c') for s in seeds]
        m = metrics(runs)
        rows.append(((nmax, life, juv, imm), m, score(m)))
    rows.sort(key=lambda x: -x[2])

    print('%-6s %-6s %-12s %-6s | %6s %5s %6s %6s %6s %7s %6s %6s %6s | %5s' %
          ('上限', '寿命', '幼崽夭折', '野外引入', '出生', '世代', '创始系', 'F均值', '毛色数',
           '单色%', '突变', '突变活', '至上限%', '得分'))
    for (nmax, life, juv, imm), m, sc in rows:
        print('%-6d %-6d %-12s %-6s | %6.0f %5.1f %6.1f %6.3f %6.1f %7.0f %6.1f %6.1f %6.0f%% | %5.2f' %
              (nmax, life, '%.2f-%.2f' % juv, '开' if imm else '关',
               m['births'], m['gens'], m['lines'], m['F'], m['colors'], m['dominant_pct'],
               m['muts'], m['muts_alive'], m['cap_ratio'] * 100, sc))

    best = rows[0]
    print()
    print('最优组合：上限=%d 寿命=%d天 夭折=%.2f-%.2f 野外引入=%s  得分=%.2f' %
          (best[0][0], best[0][1], best[0][2][0], best[0][2][1], '开' if best[0][3] else '关', best[2]))
    print('  出生=%.0f 世代=%.1f 创始系=%.1f/10 F=%.3f 杂合损失=%.1f%% 毛色数=%.1f 单色占比=%.0f%% 突变=%.1f(存活%.1f) 峰值种群=%d' %
          (best[1]['births'], best[1]['gens'], best[1]['lines'], best[1]['F'], best[1]['het_loss'],
           best[1]['colors'], best[1]['dominant_pct'], best[1]['muts'], best[1]['muts_alive'],
           best[1]['maxpop']))


if __name__ == '__main__':
    main()
