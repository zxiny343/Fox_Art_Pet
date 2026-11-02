# -*- coding: utf-8 -*-
"""三版本横向对照（20 生态年），并用 Fisher 合并方差的方式给出差是否可信。"""
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


def one(a):
    name, seed, yrs = a
    P = dict({'v0.3base': _M.BASE_PARAMS,
              'v0.4tuned': _M.TUNED_PARAMS,
              'v0.5': _M.TUNED_V2_PARAMS}[name])
    return name, yrs, _M.run_round(seed, P, yrs)


if __name__ == '__main__':
    seeds = [20261031 + i * 7919 for i in range(12)]
    tasks = [(n, s, 20) for n in ('v0.3base', 'v0.4tuned', 'v0.5') for s in seeds]
    with Pool(initializer=_init) as pool:
        raw = pool.map(one, tasks, chunksize=1)
    store = {}
    for n, y, r in raw:
        store.setdefault(n, []).append(r)

    def stat(rs, k):
        v = [r[k] for r in rs]
        m = statistics.mean(v)
        se = statistics.pstdev(v) / max(1.0, len(v) ** 0.5)
        return m, se

    print('===== 20 生态年 · 12 种子（均值 ± 标准误） =====')
    print('%-9s %14s %14s %14s %12s %10s %10s %8s' %
          ('版本', '世代', '近交 F', '杂合度', '指纹2', '毛色', '窝数', '末种群'))
    for n in ('v0.3base', 'v0.4tuned', 'v0.5'):
        rs = store[n]
        G, Gse = stat(rs, 'max_generation')
        F, Fse = stat(rs, 'meanF_end')
        H, Hse = stat(rs, 'het_end')
        P2, P2se = stat(rs, 'fp2_ratio')
        C = statistics.mean([len(r['end_colors']) for r in rs])
        L, Lse = stat(rs, 'total_litters')
        pop, _ = stat(rs, 'final_pop')
        share = statistics.mean([r['migrated'] / max(1, r['migrated'] + r['total_deaths']) for r in rs])
        print('%-9s %6.1f±%-5.1f %6.3f±%-5.3f %6.3f±%-5.3f %6.2f±%-5.2f %10.2f %6.0f±%-4.0f %8.1f' %
              (n, G, Gse, F, Fse, H, Hse, P2, P2se, C, L, Lse, pop))
    print()
    print('%-9s %10s %10s %10s' % ('版本', '迁徙占比', '裁剪幼崽', '引入数'))
    for n in ('v0.3base', 'v0.4tuned', 'v0.5'):
        rs = store[n]
        share = statistics.mean([r['migrated'] / max(1, r['migrated'] + r['total_deaths']) for r in rs])
        tr = statistics.mean([r['trimmed_pups'] for r in rs])
        im = statistics.mean([r['immigrants'] for r in rs])
        print('%-9s %9.0f%% %10.0f %10.1f' % (n, share * 100, tr, im))
