# -*- coding: utf-8 -*-
"""v0.6 终选对照：在同一代码基线上逐项叠加改动，5 年（用户场景）与 20 年（长期稳定）。

叠加顺序（每步都保留前一步）：
    V5    v0.5 参数（对照）
    +A    密度软目标自洽（n_soft = N_max − Litter_reserve）+ 名额冷却
    +B    幼崽存活看自身基因（Juv_sel_strength）
    +C    尾数性选择加强（Court_tail_bonus）  —— 让「看得见的进化」更快
    +D    季节光照摆幅                        —— 给毛色一个周期性选择压力
"""
import os
import statistics
from multiprocessing import Pool

_HERE = os.path.dirname(os.path.abspath(__file__))
_M = None
SEEDS = [20261031 + i * 7919 for i in range(int(os.environ.get('NS', '12')))]


def _init():
    global _M
    import importlib.util
    spec = importlib.util.spec_from_file_location('m', os.path.join(_HERE, 'fox_ecosystem_sim.py'))
    _M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_M)


def one(a):
    tag, over, yrs, seed = a
    P = dict(_M.TUNED_V2_PARAMS)
    P.update(over)
    return tag, yrs, _M.run_round(seed, P, yrs)


def agg(rs):
    n = len(rs)
    m = lambda k: statistics.mean([r[k] for r in rs])
    se = lambda k: (statistics.pstdev([r[k] for r in rs]) / n ** 0.5) if n > 1 else 0.0
    return {
        'litters': m('total_litters'), 'blocked': m('blocked_litters'),
        'block_ratio': m('blocked_litters') / max(1e-9, m('blocked_litters') + m('total_litters')),
        'trimmed': m('trimmed_pups'), 'gen': m('max_generation'),
        'pop': m('final_pop'), 'F': m('meanF_end'), 'F_se': se('meanF_end'),
        'het': m('het_end'), 'fp2': m('fp2_ratio'),
        'sel_r': m('selection_r'), 'sel_se': se('selection_r'),
        'mtail': m('lum_end') * 0 + statistics.mean([r['daily'][-1]['mtail'] for r in rs]),
        'migrated': m('migrated'), 'deaths': m('total_deaths'),
        'collapse': sum(1 for r in rs if r['collapsed']),
        'mut_surv': m('mutations_survived'), 'mut_tot': m('mutations_total'),
    }


CFGS = [
    ('V5  v0.5 现状', {}),
    ('+A  密度自洽', {'N_soft_frac': 0.85, 'Blocked_cooldown_h': 24}),
    ('+B  幼崽选择', {'N_soft_frac': 0.85, 'Blocked_cooldown_h': 24, 'Juv_sel_strength': 1.2}),
    ('+C  尾选择性选择', {'N_soft_frac': 0.85, 'Blocked_cooldown_h': 24, 'Juv_sel_strength': 1.2,
                    'Court_tail_bonus': 0.045}),
    ('+D  季节光照', {'N_soft_frac': 0.85, 'Blocked_cooldown_h': 24, 'Juv_sel_strength': 1.2,
                   'Court_tail_bonus': 0.045, 'Env_light_season_amp': 22}),
]

if __name__ == '__main__':
    for yrs in (5, 20):
        tasks = [(t, o, yrs, s) for t, o in CFGS for s in SEEDS]
        with Pool(initializer=_init) as pool:
            raw = pool.map(one, tasks, chunksize=1)
        store = {}
        for tag, y, r in raw:
            store.setdefault((tag, y), []).append(r)
        print('\n===== %.0f 生态年 · %d 种子 =====' % (yrs, len(SEEDS)))
        print('%-16s %6s %6s %6s %5s %5s %7s %6s %5s %11s %6s %5s' %
              ('配置', '窝数', 'block%', '裁剪', '世代', '种群', 'F', '杂合', '尾数', '选择r', '突变存', '崩'))
        for t, _ in CFGS:
            a = agg(store[(t, yrs)])
            star = '*' if a['sel_r'] > 2 * max(a['sel_se'], 1e-9) else ' '
            print('%-16s %6.1f %5.0f%% %6.1f %5.1f %5.1f %7.3f %6.3f %5.2f %+6.3f%s %6.1f %5d' %
                  (t, a['litters'], a['block_ratio'] * 100, a['trimmed'], a['gen'], a['pop'],
                   a['F'], a['het'], a['mtail'], a['sel_r'], star, a['mut_surv'], a['collapse']))
