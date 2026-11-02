# -*- coding: utf-8 -*-
"""上限实施方式的三种方案对照（同一代码基线、同一批种子）。

    reserve6  v0.5 方案：名额不足「一整窝(6)」就拒绝受孕 —— 不裁剪，但空转多、种群偏低
    fit       新方案  ：窝仔数去适配剩余名额（越挤窝越小），名额 < 最小窝仔数才拒孕
    slot      v0.4 方案：先怀满再裁掉多余幼崽 —— 会静默杀掉已孕育个体，仅作对照
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
    return {
        'litters': m('total_litters'), 'births': m('total_births'),
        'blocked': m('blocked_litters'),
        'block_ratio': m('blocked_litters') / max(1e-9, m('blocked_litters') + m('total_litters')),
        'trimmed': m('trimmed_pups'), 'litter_size': m('total_births') / max(1e-9, m('total_litters')),
        'gen': m('max_generation'), 'pop': m('final_pop'), 'mean_pop': m('mean_pop'),
        'F': m('meanF_end'), 'het': m('het_end'), 'fp2': m('fp2_ratio'),
        'sel_r': m('selection_r'), 'collapse': sum(1 for r in rs if r['collapsed']),
        'court': m('court_attempts'),
    }


CFGS = [
    ('reserve6/soft0.85', {'Cap_mode': 'L_plus_reserve', 'Litter_reserve': 6,
                           'N_soft_frac': 0.85, 'Blocked_cooldown_h': 24}),
    ('fit/soft1.00', {'Cap_mode': 'L_plus_fit', 'N_soft_frac': 1.00, 'Blocked_cooldown_h': 24}),
    ('fit/soft0.90', {'Cap_mode': 'L_plus_fit', 'N_soft_frac': 0.90, 'Blocked_cooldown_h': 24}),
    ('fit/soft0.80', {'Cap_mode': 'L_plus_fit', 'N_soft_frac': 0.80, 'Blocked_cooldown_h': 24}),
    ('slot(v0.4 对照)', {'Cap_mode': 'L_plus_slot', 'N_soft_frac': 1.00}),
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
        print('%-18s %6s %6s %5s %6s %5s %6s %6s %6s %6s %5s %7s %5s' %
              ('方案', '窝数', '出生', '窝仔', 'block%', '裁剪', '世代', '种群', 'F', '杂合', 'fp2', '选择r', '崩'))
        for t, _ in CFGS:
            a = agg(store[(t, yrs)])
            print('%-18s %6.1f %6.1f %5.2f %5.0f%% %6.1f %6.1f %6.1f %6.3f %6.3f %5.2f %+7.3f %5d' %
                  (t, a['litters'], a['births'], a['litter_size'], a['block_ratio'] * 100,
                   a['trimmed'], a['gen'], a['pop'], a['F'], a['het'], a['fp2'],
                   a['sel_r'], a['collapse']))
