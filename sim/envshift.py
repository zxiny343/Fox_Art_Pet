# -*- coding: utf-8 -*-
"""H1 环境切换实验：换一张亮度不同的壁纸，种群会不会「肉眼可见地」跟着变颜色？

设计稿 §14 把光照绑定到壁纸亮度。对玩家来说，这是唯一不需要读数据就能感知的进化：
换壁纸 -> 隐蔽色的最优解整体挪走 -> 若干代后种群毛色朝新背景收敛。

指标：
    lum    = 存活个体毛色明度的均值（0-100，越大越浅）
    sfitc  = 以「当前光照」为参考的静态适应度（衡量有没有追上新环境）
输出按生态年的轨迹，看切换后多少年、多少代能看到位移。
"""
import os
import statistics
from multiprocessing import Pool

_HERE = os.path.dirname(os.path.abspath(__file__))
_M = None
SEEDS = [20261031 + i * 7919 for i in range(int(os.environ.get('NS', '12')))]
YEARS = float(os.environ.get('YEARS', '20'))
SHIFT_YEAR = float(os.environ.get('SY', '8'))


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
    """把 daily 序列按生态年聚合。"""
    per = {}
    for r in rs:
        for d in r['daily']:
            per.setdefault(d['year'], []).append(d[key])
    return {y: statistics.mean(v) for y, v in sorted(per.items())}


def main():
    scenes = [
        ('A 恒定 50（对照）', {}),
        ('B 50→85 变亮', {'Env_shift_year': SHIFT_YEAR, 'Env_shift_to': 85}),
        ('C 50→20 变暗', {'Env_shift_year': SHIFT_YEAR, 'Env_shift_to': 20}),
    ]
    tasks = [(t, o, s) for t, o in scenes for s in SEEDS]
    with Pool(initializer=_init) as pool:
        raw = pool.map(one, tasks, chunksize=1)
    store = {}
    for t, r in raw:
        store.setdefault(t, []).append(r)

    print('===== 环境切换实验 · %d 种子 × %.0f 年 · 第 %.0f 年换壁纸 =====' % (len(SEEDS), YEARS, SHIFT_YEAR))
    for tag, _ in scenes:
        rs = store[tag]
        lum = yearly(rs, 'lum')
        sfc = yearly(rs, 'sfitc')
        gen = yearly(rs, 'maxgen')
        print('\n--- %s ---' % tag)
        print('  年 :', ' '.join('%4d' % y for y in lum))
        print('  lum:', ' '.join('%4.1f' % v for v in lum.values()))
        print('  sfit:', ' '.join('%4.2f' % v for v in sfc.values()))
        print('  世代:', ' '.join('%4.1f' % v for v in gen.values()))
        ys = sorted(lum)
        pre = statistics.mean([lum[y] for y in ys if y < SHIFT_YEAR])
        post5 = statistics.mean([lum[y] for y in ys if SHIFT_YEAR <= y < SHIFT_YEAR + 5])
        tail = statistics.mean([lum[y] for y in ys if y >= SHIFT_YEAR + 10])
        print('  切换前 lum=%.1f -> 切换后 5 年 %.1f (%+.1f) -> 末段 %.1f (%+.1f)'
              % (pre, post5, post5 - pre, tail, tail - pre))
        print('  末代种群 %.1f  近交F %.3f  杂合 %.3f  fp2 %.2f  崩溃 %d'
              % (statistics.mean([r['final_pop'] for r in rs]),
                 statistics.mean([r['meanF_end'] for r in rs]),
                 statistics.mean([r['het_end'] for r in rs]),
                 statistics.mean([r['fp2_ratio'] for r in rs]),
                 sum(1 for r in rs if r['collapsed'])))
        print('  sfitc: %.4f -> %.4f (%+.4f)'
              % (statistics.mean([r['sfitc_start'] for r in rs]),
                 statistics.mean([r['sfitc_end'] for r in rs]),
                 statistics.mean([r['sfitc_gain'] for r in rs])))
        print('  selection_r %.3f  sfit_gain(固定参考) %+.4f'
              % (statistics.mean([r['selection_r'] for r in rs]),
                 statistics.mean([r['sfit_gain'] for r in rs])))


if __name__ == '__main__':
    main()
