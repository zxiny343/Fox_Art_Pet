# -*- coding: utf-8 -*-
"""在不牺牲多样性的前提下追回世代推进速度：调节「世代间隔」而非「死亡速度」。

候选旋钮：
  Mature_hours   幼崽->成年所需游戏小时
  Breed_interval 两次妊娠之间的最小间隔（游戏小时）
  MINB           成年后还需等待多久才能首次繁殖
  引入节奏       更快更多次 -> 允许更高周转率而不抬高近交
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


def one(a):
    cfg, seed, yrs = a
    P = dict(_M.TUNED_V2_PARAMS)
    P.update(cfg)
    return cfg, _M.run_round(seed, P, yrs)


if __name__ == '__main__':
    import itertools
    base = dict(_M.TUNED_V2_PARAMS) if False else None
    combos = {}
    for mat, bi, mb, every in itertools.product([72, 96], [48, 72], [12], [12, 14]):
        if mat == 96 and bi == 72 and every == 14:
            tag = '基线 mat96/int72/E14'
        else:
            tag = 'mat%d/int%d/E%d' % (mat, bi, every)
        combos[tag] = dict(Mature_hours=mat, Breed_interval=bi,
                           Min_breed_extra=mb, Immigration_every_days=every * 24)
    seeds = [20261031 + i * 7919 for i in range(12)]
    tasks = [(cfg, s, 20) for cfg in combos.values() for s in seeds]
    with Pool(initializer=_init) as pool:
        raw = pool.map(one, tasks, chunksize=1)
    store = {}
    for cfg, r in raw:
        store.setdefault(tuple(sorted(cfg.items())), []).append(r)

    def stat(rs, k):
        v = [r[k] for r in rs]
        return statistics.mean(v), statistics.pstdev(v) / max(1.0, len(v) ** 0.5)

    print('===== 20 生态年 · 12 种子 =====')
    print('%-24s %12s %14s %12s %10s %10s %10s' %
          ('配置', '世代', '近交 F', '指纹2', '毛色', '出生', '引入数'))
    rows = []
    for tag, cfg in combos.items():
        rs = store[tuple(sorted(cfg.items()))]
        G, Gse = stat(rs, 'max_generation')
        F, Fse = stat(rs, 'meanF_end')
        P2, _ = stat(rs, 'fp2_ratio')
        C = statistics.mean([len(r['end_colors']) for r in rs])
        B, _ = stat(rs, 'total_births')
        IM, _ = stat(rs, 'immigrants')
        rows.append((tag, G, Gse, F, Fse, P2, C, B, IM))
    rows.sort(key=lambda x: -x[1])
    for tag, G, Gse, F, Fse, P2, C, B, IM in rows:
        print('%-24s %6.1f±%-5.1f %6.3f±%-5.3f %12.2f %10.2f %10.0f %10.1f' %
              (tag, G, Gse, F, Fse, P2, C, B, IM))
