# -*- coding: utf-8 -*-
"""v0.6 参数搜索 stage1：修复「繁殖机会被闸门空转吃掉」与「幼崽存活不看自身基因」。

对照维度：
    N_soft_frac        —— 密度曲线的软目标（决定种群稳态离硬上限多远 = 余裕）
    Blocked_cooldown_h —— 因名额被拦后的冷却（避免同一只雌性每 tick 空转重试）
    Juv_sel_strength   —— 幼崽夭折率受自身表型适应度影响的强度

指标：窝数吞吐、blocked 空转比、静态适应度增益 sfit_gain（= 真进化）、
      选择相关 selection_r、近交 F、杂合度、外观多样性、裁剪数（必须 0）、崩溃率。
"""
import itertools
import json
import os
import statistics
import sys
from multiprocessing import Pool

_HERE = os.path.dirname(os.path.abspath(__file__))
_M = None
SEEDS = [20261031 + i * 7919 for i in range(int(os.environ.get('NS', '12')))]
YEARS = float(os.environ.get('YEARS', '5'))


def _init():
    global _M
    import importlib.util
    spec = importlib.util.spec_from_file_location('m', os.path.join(_HERE, 'fox_ecosystem_sim.py'))
    _M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_M)


def one(a):
    tag, over, seed = a
    P = dict(_M.TUNED_V2_PARAMS)
    P.update(over)
    return tag, _M.run_round(seed, P, YEARS)


def agg(rs):
    n = len(rs)

    def m(k):
        return statistics.mean([r[k] for r in rs])

    def se(k):
        if n < 2:
            return 0.0
        return statistics.pstdev([r[k] for r in rs]) / n ** 0.5

    return {
        'n': n,
        'litters': m('total_litters'),
        'births': m('total_births'),
        'blocked': m('blocked_litters'),
        'block_ratio': m('blocked_litters') / max(1e-9, m('blocked_litters') + m('total_litters')),
        'trimmed': m('trimmed_pups'),
        'gen': m('max_generation'),
        'pop': m('final_pop'),
        'mean_pop': m('mean_pop'),
        'F': m('meanF_end'), 'F_se': se('meanF_end'),
        'het': m('het_end'),
        'fp2': m('fp2_ratio'),
        'sfit_start': m('sfit_start'),
        'sfit_end': m('sfit_end'),
        'sfit_gain': m('sfit_gain'), 'sfit_se': se('sfit_gain'),
        'sel_r': m('selection_r'), 'sel_se': se('selection_r'),
        'fit_spread': m('fit_spread'),
        'migrated': m('migrated'),
        'deaths': m('total_deaths'),
        'collapse': sum(1 for r in rs if r['collapsed']),
    }


def run(grid, title):
    tasks = []
    for tag, over in grid:
        for s in SEEDS:
            tasks.append((tag, over, s))
    with Pool(initializer=_init) as pool:
        raw = pool.map(one, tasks, chunksize=1)
    store = {}
    for tag, r in raw:
        store.setdefault(tag, []).append(r)
    out = {t: agg(rs) for t, rs in store.items()}
    print('\n===== %s  (%d 种子 × %.0f 生态年) =====' % (title, len(SEEDS), YEARS))
    print('%-30s %7s %7s %7s %6s %5s %6s %6s %6s %8s %8s %6s %5s' %
          ('配置', '窝数', 'block%', '裁剪', '世代', '种群', 'F', '杂合', 'fp2',
           'sfit增益', '选择r', '迁徙', '崩'))
    for tag, _ in grid:
        a = out[tag]
        star = ' *' if a['sel_r'] > 2 * max(a['sel_se'], 1e-9) else ''
        print('%-30s %7.1f %6.0f%% %7.1f %6.1f %5.1f %6.3f %6.3f %6.2f %+5.3f±%.3f %+5.3f%s %6.1f %5d' %
              (tag, a['litters'], a['block_ratio'] * 100, a['trimmed'], a['gen'], a['pop'],
               a['F'], a['het'], a['fp2'], a['sfit_gain'], a['sfit_se'], a['sel_r'], star,
               a['migrated'], a['collapse']))
    return out


if __name__ == '__main__':
    grid = []
    for ns, cd in itertools.product((0.70, 0.80, 0.90, 1.00), (0, 12, 24, 48)):
        grid.append(('soft%.2f/cool%d' % (ns, cd),
                     {'N_soft_frac': ns, 'Blocked_cooldown_h': cd}))
    o1 = run(grid, 'stage1 · 余裕 × 冷却')

    best = max(o1.items(), key=lambda kv: kv[1]['litters'])
    print('\n吞吐最高的配置：%s（窝数 %.1f）' % (best[0], best[1]['litters']))
    over_best = [ov for tg, ov in grid if tg == best[0]][0]

    grid2 = []
    for js in (0.0, 0.6, 1.2, 1.8):
        ov = dict(over_best)
        ov['Juv_sel_strength'] = js
        grid2.append(('%s/juv%.1f' % (best[0], js), ov))
    o2 = run(grid2, 'stage2 · 幼崽选择强度（基于 stage1 最优）')
    json.dump({'stage1': o1, 'stage2': o2, 'best_over': over_best},
              open(os.path.join(_HERE, 'search_v6_stage12.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
