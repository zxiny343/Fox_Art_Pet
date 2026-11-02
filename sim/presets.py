# -*- coding: utf-8 -*-
"""三档「演化节奏」预设对照：稳健 / 标准 / 激进。

用户可以按偏好切换；三档共用同一套不变量（不破上限、不裁剪幼崽、迁徙占比受控）。
"""
import os
import statistics
from multiprocessing import Pool

_HERE = os.path.dirname(os.path.abspath(__file__))
_M = None


def _init():
    global _M
    import importlib.util
    spec = importlib.util.spec_from_file_location('m', os.path.join(_HERE, 'fox_ecosystem_sim.py'))
    _M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_M)


# 三档共用 v0.6 的不变量（L_plus_fit 上限、幼崽选择、季节光照），只调「演化节奏」
PRESETS = {
    '稳健档': dict(Lifespan_mean_days=52, Lifespan_sd_days=10, Lifespan_min_days=32,
                   Lifespan_max_days=88, Immigration_every_days=16 * 24),
    '标准档(推荐)': dict(),
    '激进档': dict(Lifespan_mean_days=32, Lifespan_sd_days=7, Lifespan_min_days=20,
                   Lifespan_max_days=54, Migrate_base=0.00006, Immigration_every_days=9 * 24),
}


def one(a):
    name, seed, yrs = a
    P = dict(_M.TUNED_V3_PARAMS)
    P.update(PRESETS[name])
    return name, yrs, _M.run_round(seed, P, yrs)


if __name__ == '__main__':
    seeds = [20261031 + i * 7919 for i in range(12)]
    tasks = [(n, s, y) for n in PRESETS for s in seeds for y in (5, 20)]
    with Pool(initializer=_init) as pool:
        raw = pool.map(one, tasks, chunksize=1)
    store = {}
    for n, y, r in raw:
        store.setdefault((n, y), []).append(r)

    def st(rs, k):
        v = [r[k] for r in rs]
        return statistics.mean(v), statistics.pstdev(v) / max(1.0, len(v) ** 0.5)

    for yrs in (5, 20):
        print('===== %d 生态年 · 12 种子 =====' % yrs)
        print('%-14s %12s %14s %12s %10s %10s %10s %10s' %
              ('档位', '世代', '近交 F', '指纹2', '毛色', '窝', '迁徙占比', '引入数'))
        for n in PRESETS:
            rs = store[(n, yrs)]
            G, Gs = st(rs, 'max_generation')
            F, Fs = st(rs, 'meanF_end')
            P2, _ = st(rs, 'fp2_ratio')
            C = statistics.mean([len(r['end_colors']) for r in rs])
            L, _ = st(rs, 'total_litters')
            share = statistics.mean([r['migrated'] / max(1, r['migrated'] + r['total_deaths']) for r in rs])
            IM, _ = st(rs, 'immigrants')
            print('%-14s %6.1f±%-5.1f %6.3f±%-5.3f %12.2f %10.2f %10.0f %9.0f%% %10.1f' %
                  (n, G, Gs, F, Fs, P2, C, L, share * 100, IM))
        print()
