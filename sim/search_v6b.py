# -*- coding: utf-8 -*-
"""v0.6 参数搜索 stage3：自洽的密度软目标 × 选择差强度 × 幼崽选择。

v0.5 的内在冲突：n_soft = 1.0 × N_max，于是种群到 35 只时 L 仍有 0.33（鼓励受孕），
但剩余名额只剩 5 < Litter_reserve 6 -> 98% 的妊娠被闸门拦下（纯空转）。
自洽解：n_soft = N_max − Litter_reserve，让「密度曲线何时归零」与「闸门何时触发」对齐。

同时放大选择差（Selection_strength）：只有适应度差异大到能压过繁殖成功率的抽样噪声，
自然选择才推得动种群（否则 sfit_gain 恒为负 = 漂变/近交主导）。
"""
import itertools
import json
import os
import statistics
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
        return statistics.pstdev([r[k] for r in rs]) / n ** 0.5 if n > 1 else 0.0

    d = {
        'n': n,
        'litters': m('total_litters'), 'births': m('total_births'),
        'blocked': m('blocked_litters'),
        'block_ratio': m('blocked_litters') / max(1e-9, m('blocked_litters') + m('total_litters')),
        'trimmed': m('trimmed_pups'),
        'gen': m('max_generation'), 'pop': m('final_pop'), 'mean_pop': m('mean_pop'),
        'F': m('meanF_end'), 'F_se': se('meanF_end'),
        'het': m('het_end'), 'fp2': m('fp2_ratio'),
        'sfit_gain': m('sfit_gain'), 'sfit_se': se('sfit_gain'),
        'sel_r': m('selection_r'), 'sel_se': se('selection_r'),
        'fit_spread': m('fit_spread'),
        'migrated': m('migrated'), 'deaths': m('total_deaths'),
        'collapse': sum(1 for r in rs if r['collapsed']),
        'abandon': m('abandon_ratio'),
    }
    d['mig_share'] = d['migrated'] / max(1e-9, d['migrated'] + d['deaths'])
    return d


def run(grid, title):
    tasks = [(tag, ov, s) for tag, ov in grid for s in SEEDS]
    with Pool(initializer=_init) as pool:
        raw = pool.map(one, tasks, chunksize=1)
    store = {}
    for tag, r in raw:
        store.setdefault(tag, []).append(r)
    out = {t: agg(rs) for t, rs in store.items()}
    print('\n===== %s  (%d 种子 × %.0f 年) =====' % (title, len(SEEDS), YEARS))
    print('%-26s %6s %6s %5s %5s %5s %6s %6s %5s %12s %11s %5s %5s' %
          ('配置', '窝数', 'block%', '裁剪', '世代', '种群', 'F', '杂合', 'fp2',
           'sfit增益', '选择r', '迁%', '崩'))
    for tag, _ in grid:
        a = out[tag]
        star = '*' if abs(a['sfit_gain']) > 2 * max(a['sfit_se'], 1e-9) and a['sfit_gain'] > 0 else ' '
        sr = '*' if a['sel_r'] > 2 * max(a['sel_se'], 1e-9) else ' '
        print('%-26s %6.1f %5.0f%% %5.1f %5.1f %5.1f %6.3f %6.3f %5.2f %+6.3f±%.3f%s %+5.3f%s %4.0f%% %5d' %
              (tag, a['litters'], a['block_ratio'] * 100, a['trimmed'], a['gen'], a['pop'],
               a['F'], a['het'], a['fp2'], a['sfit_gain'], a['sfit_se'], star,
               a['sel_r'], sr, a['mig_share'] * 100, a['collapse']))
    return out


if __name__ == '__main__':
    base = {'Blocked_cooldown_h': 24}
    grid = []
    for ns, ss, js in itertools.product((0.80, 0.85, 0.90), (1.0, 2.0, 3.0), (0.0, 1.2)):
        ov = dict(base)
        ov.update({'N_soft_frac': ns, 'Selection_strength': ss, 'Juv_sel_strength': js})
        grid.append(('soft%.2f/sel%.0f/juv%.1f' % (ns, ss, js), ov))
    o = run(grid, 'stage3 · 软目标 × 选择差 × 幼崽选择')
    json.dump(o, open(os.path.join(_HERE, 'search_v6_stage3.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    ranked = sorted(o.items(), key=lambda kv: -kv[1]['sfit_gain'])
    print('\n按 sfit 增益排序（前 8）：')
    for t, a in ranked[:8]:
        print('  %-26s sfit%+0.4f  sel_r%+0.3f  窝%5.1f  F%.3f  het%.3f  崩%d'
              % (t, a['sfit_gain'], a['sel_r'], a['litters'], a['F'], a['het'], a['collapse']))
