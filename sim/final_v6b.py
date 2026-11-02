# -*- coding: utf-8 -*-
"""v0.6 终选（24 种子）：在 fit/soft0.90 上限方案上逐项叠加，并追踪尾数进化轨迹。
尾数是唯一被证实能「肉眼看见」的定向进化载体（加性累加 + 性选择），
因此这里额外报告首段/末段的位移量。
"""
import os
import statistics
from multiprocessing import Pool

_HERE = os.path.dirname(os.path.abspath(__file__))
_M = None
SEEDS = [20261031 + i * 7919 for i in range(int(os.environ.get('NS', '24')))]


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


BASE = {'Cap_mode': 'L_plus_fit', 'N_soft_frac': 0.90, 'Blocked_cooldown_h': 24}


def ov(**kw):
    d = dict(BASE)
    d.update(kw)
    return d


CFGS = [
    ('V5   v0.5 现状', {}),
    ('F1   fit/soft0.90', ov()),
    ('F2   +幼崽选择', ov(Juv_sel_strength=1.2)),
    ('F3   +尾性选择', ov(Juv_sel_strength=1.2, Court_tail_bonus=0.045)),
    ('F4   +季节光照', ov(Juv_sel_strength=1.2, Env_light_season_amp=22)),
    ('F5   +尾选择+季节', ov(Juv_sel_strength=1.2, Court_tail_bonus=0.045,
                        Env_light_season_amp=22)),
]


def tail_trend(rs):
    """尾数：最前 1/4 时段 vs 最后 1/4 时段的均值。"""
    per = {}
    for r in rs:
        ds = r['daily']
        for d in ds:
            per.setdefault(d['day'], []).append(d['mtail'])
    days = sorted(per)
    q = max(1, len(days) // 4)
    head = statistics.mean([statistics.mean(per[d]) for d in days[:q]])
    tail = statistics.mean([statistics.mean(per[d]) for d in days[-q:]])
    return head, tail


def agg(rs):
    n = len(rs)
    m = lambda k: statistics.mean([r[k] for r in rs])
    se = lambda k: (statistics.pstdev([r[k] for r in rs]) / n ** 0.5) if n > 1 else 0.0
    h, t = tail_trend(rs)
    return {
        'litters': m('total_litters'), 'births': m('total_births'),
        'block_ratio': m('blocked_litters') / max(1e-9, m('blocked_litters') + m('total_litters')),
        'trimmed': m('trimmed_pups'), 'gen': m('max_generation'),
        'pop': m('final_pop'), 'F': m('meanF_end'), 'F_se': se('meanF_end'),
        'het': m('het_end'), 'het_se': se('het_end'), 'fp2': m('fp2_ratio'),
        'sel_r': m('selection_r'), 'sel_se': se('selection_r'),
        'tail_h': h, 'tail_t': t,
        'collapse': sum(1 for r in rs if r['collapsed']),
        'mut_surv': m('mutations_survived'),
    }


if __name__ == '__main__':
    for yrs in (5, 20):
        tasks = [(t, o, yrs, s) for t, o in CFGS for s in SEEDS]
        with Pool(initializer=_init) as pool:
            raw = pool.map(one, tasks, chunksize=1)
        store = {}
        for tag, y, r in raw:
            store.setdefault((tag, y), []).append(r)
        print('\n===== %.0f 生态年 · %d 种子 =====' % (yrs, len(SEEDS)))
        print('%-17s %6s %5s %5s %5s %7s %6s %6s %5s %11s %13s %5s' %
              ('配置', '窝数', 'blk%', '裁剪', '世代', '种群', 'F', '杂合', 'fp2', '选择r', '尾数 首→末', '崩'))
        for t, _ in CFGS:
            a = agg(store[(t, yrs)])
            star = '*' if a['sel_r'] > 2 * max(a['sel_se'], 1e-9) else ' '
            print('%-17s %6.1f %4.0f%% %5.1f %5.1f %7.1f %6.3f %6.3f %5.2f %+6.3f%s %5.2f→%5.2f %5d' %
                  (t, a['litters'], a['block_ratio'] * 100, a['trimmed'], a['gen'], a['pop'],
                   a['F'], a['het'], a['fp2'], a['sel_r'], star, a['tail_h'], a['tail_t'],
                   a['collapse']))
