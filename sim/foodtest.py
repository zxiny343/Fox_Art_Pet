# -*- coding: utf-8 -*-
"""F5 食物短缺场景：食物池 + 按适应度竞争取食。

设计约束（§15）：不投喂 -> 活跃度降低 -> 休眠，**不能饿死**。
v0.5 的实现是「Food_abundant=False 时饱食度单调 -0.35/h 永不回升」，
等价于全体必然掉膘，无法表达「投喂/不投喂」的真实节奏，因此这里换成食物池：
    每天投递 supply -> 种群按 自身适应度/种群均值 竞争取食 -> 不足者先掉膘、先休眠
"""
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
    P = dict(_M.TUNED_V3_PARAMS)
    P.update(over)
    return tag, _M.run_round(seed, P, YEARS)


def main():
    # 承载力 N* = 供给 / (4.0 份/时 × 24 时) = 供给/96；供给低于承载力才掉膘->休眠
    scenes = [
        ('充足 3800/天', {'Food_mode': 'pool', 'Food_supply_per_day': 3800}),
        ('正常 2900/天', {'Food_mode': 'pool', 'Food_supply_per_day': 2900}),
        ('短缺 1900/天', {'Food_mode': 'pool', 'Food_supply_per_day': 1900}),
        ('饥荒 1000/天', {'Food_mode': 'pool', 'Food_supply_per_day': 1000}),
        ('断供    0/天', {'Food_mode': 'pool', 'Food_supply_per_day': 0}),
        ('断供2年→恢复', {'Food_mode': 'pool', 'Food_supply_per_day': 0,
                       'Food_shift_year': 2, 'Food_shift_to': 3800}),
    ]
    tasks = [(t, o, s) for t, o in scenes for s in SEEDS]
    with Pool(initializer=_init) as pool:
        raw = pool.map(one, tasks, chunksize=1)
    store = {}
    for t, r in raw:
        store.setdefault(t, []).append(r)

    print('===== 食物场景 · %d 种子 × %.0f 生态年 =====' % (len(SEEDS), YEARS))
    print('%-14s %6s %6s %7s %7s %7s %7s %7s %7s %6s %6s %5s' %
          ('场景', '末种群', '窝数', '出生', '夭折', '疾病', '衰老', '休眠次数',
           '末饱食', '迁徙', '适应度r', '崩'))
    for tag, _ in scenes:
        rs = store[tag]
        dm = lambda k: statistics.mean([r[k] for r in rs])
        dc = statistics.mean([r['deaths_by_cause'].get('幼崽夭折', 0) for r in rs])
        dd = statistics.mean([r['deaths_by_cause'].get('疾病', 0) for r in rs])
        da = statistics.mean([r['deaths_by_cause'].get('衰老', 0) for r in rs])
        print('%-14s %6.1f %6.1f %7.1f %7.1f %7.1f %7.1f %7.1f %7.1f %6.1f %+6.3f %5d' %
              (tag, dm('final_pop'), dm('total_litters'), dm('total_births'), dc, dd, da,
               dm('torpor_events'), dm('mean_satiety_end'), dm('migrated'),
               dm('selection_r'), sum(1 for r in rs if r['collapsed'])))
    print()
    print('%-14s %8s %8s %8s %8s' % ('场景', '供给满足率', '休眠占比', '毛色明度', '尾数'))
    for tag, _ in scenes:
        rs = store[tag]
        dm = lambda k: statistics.mean([r[k] for r in rs])
        print('%-14s %8.2f %8.1f %8.2f %8.2f' %
              (tag, 1 - dm('food_shortage_ratio'), dm('torpid_end'),
               dm('lum_end'), dm('meanF_end') * 0 + statistics.mean([r['daily'][-1]['mtail'] for r in rs])))
    print('\n注：断供档验证「不会饿死」——只看种群是否归零、休眠是否接管。')


if __name__ == '__main__':
    main()
