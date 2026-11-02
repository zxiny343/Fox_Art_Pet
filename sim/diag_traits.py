# -*- coding: utf-8 -*-
"""累加性状（毛长 / 尾数）的定向响应诊断。

毛色受上位 + 低频隐性控制，有利等位藏在杂合子里，选择响应极慢（已由
diag_selection.py 证实：S>0 但 R≈0）。毛长与尾数是设计稿里的加性累加性状，
且是玩家一眼能分辨的特征 —— 检查它们能否承载「看得见的进化」。
"""
import os
import statistics
from multiprocessing import Pool

_HERE = os.path.dirname(os.path.abspath(__file__))
_M = None
SEEDS = [20261031 + i * 7919 for i in range(int(os.environ.get('NS', '12')))]
YEARS = float(os.environ.get('YEARS', '20'))


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


def yearly(rs, key):
    per = {}
    for r in rs:
        for d in r['daily']:
            per.setdefault(d['year'], []).append(d[key])
    return {y: statistics.mean(v) for y, v in sorted(per.items())}


def show(tag, rs, keys):
    print('\n--- %s ---' % tag)
    for k, lab in keys:
        v = yearly(rs, k)
        ys = sorted(v)
        print('  %-6s' % lab, ' '.join('%5.2f' % v[y] for y in ys))
        if len(ys) >= 4:
            head = statistics.mean([v[y] for y in ys[:len(ys) // 4]])
            tail = statistics.mean([v[y] for y in ys[-len(ys) // 4:]])
            print('        首段 %.3f -> 末段 %.3f  (%+.3f)' % (head, tail, tail - head))


if __name__ == '__main__':
    scenes = [
        ('基线 v0.5', {}),
        ('冬季严寒加权（季节选择放大）', {'Season_amp': 2.5}),
        ('尾数性选择加倍', {'Court_tail_bonus': 0.06}),
    ]
    tasks = [(t, o, s) for t, o in scenes for s in SEEDS]
    with Pool(initializer=_init) as pool:
        raw = pool.map(one, tasks, chunksize=1)
    store = {}
    for t, r in raw:
        store.setdefault(t, []).append(r)
    keys = [('mhair', '毛长'), ('mtail', '尾数'), ('lum', '毛色明度'), ('sfitc', '当期适应度')]
    for t, _ in scenes:
        show(t, store[t], keys)
    print('\n年份刻度:', ' '.join('%5d' % y for y in range(int(YEARS))))
