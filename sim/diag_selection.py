# -*- coding: utf-8 -*-
"""用育种家方程定位「为什么看不见进化」：R = h^2 · S

    S（选择差）= 实际当上父母的个体，其毛色明度比种群均值高多少
    R（响应）  = 这些父母生下的幼崽，其明度比种群均值高多少

若 S≈0  -> 繁殖成功与表型无关 = 自然选择根本没在挑人（机制/样本量问题）
若 R<<S -> 选择挑对了人，但遗传传递断了（重组 / 突变 / 近交稀释）
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


def report(tag, rs):
    # 按生态年统计：种群平均明度、当父母者的平均明度、子代平均明度
    print('\n--- %s ---' % tag)
    print('  %4s %8s %8s %8s %8s %8s' % ('年', '种群lum', '母亲lum', 'S(选择差)', '子代lum', 'R(响应)'))
    rows = []
    for y in range(int(YEARS)):
        pop_l, mom_l, pup_l, fit_l = [], [], [], []
        for r in rs:
            for d in r['daily']:
                if d['year'] == y:
                    pop_l.append(d['lum'])
                    fit_l.append(d['sfitc'])
            for lg in r['litter_log']:
                if lg['year'] == y:
                    mom_l.append(lg['mom'])
                    pup_l += lg['pups']
        if not pop_l or not mom_l:
            continue
        P_ = statistics.mean(pop_l)
        M_ = statistics.mean(mom_l)
        C_ = statistics.mean(pup_l)
        rows.append((y, P_, M_, M_ - P_, C_, C_ - P_))
    for y, P_, M_, S, C_, R in rows:
        print('  %4d %8.2f %8.2f %+8.2f %8.2f %+8.2f' % (y, P_, M_, S, C_, R))
    Ss = [r[3] for r in rows]
    Rs = [r[5] for r in rows]
    print('  平均选择差 S = %+0.3f ; 平均响应 R = %+0.3f ; R/S = %s'
          % (statistics.mean(Ss), statistics.mean(Rs),
             ('%.2f' % (statistics.mean(Rs) / statistics.mean(Ss)))
             if abs(statistics.mean(Ss)) > 1e-6 else 'n/a'))
    print('  窝数/轮 %5.1f   子代总数/轮 %5.1f'
          % (statistics.mean([r['total_litters'] for r in rs]),
             statistics.mean([r['total_births'] for r in rs])))


if __name__ == '__main__':
    scenes = [
        ('基线 v0.5（光照恒 50）', {}),
        ('换壁纸 50→85（第 8 年）', {'Env_shift_year': 8, 'Env_shift_to': 85}),
    ]
    tasks = [(t, o, s) for t, o in scenes for s in SEEDS]
    with Pool(initializer=_init) as pool:
        raw = pool.map(one, tasks, chunksize=1)
    store = {}
    for t, r in raw:
        store.setdefault(t, []).append(r)
    for t, _ in scenes:
        report(t, store[t])
