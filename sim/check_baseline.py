# -*- coding: utf-8 -*-
"""统计等价性检查：当前代码 + v0.5 参数，跑 12 种子 × 20 年，
对照 v0.5 报告已发表的数字（世代 28.2 / F 0.097 / 杂合 0.416 / 指纹2 0.85）。
单轮轨迹在混沌系统里必然漂移，只有多种子均值才有意义。
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


def one(s):
    return _M.run_round(s, dict(_M.TUNED_V2_PARAMS), 20)


if __name__ == '__main__':
    seeds = [20261031 + i * 7919 for i in range(12)]
    with Pool(initializer=_init) as p:
        rs = p.map(one, seeds)
    m = lambda k: statistics.mean([r[k] for r in rs])
    sd = lambda k: statistics.pstdev([r[k] for r in rs]) / 12 ** 0.5
    print('12 种子 × 20 生态年（当前代码 + v0.5 参数）')
    for k, lab, ref in [('max_generation', '世代', '28.2'), ('meanF_end', '近交F', '0.097'),
                        ('het_end', '杂合度', '0.416'), ('fp2_ratio', '指纹2比', '0.85'),
                        ('final_pop', '末种群', '-'), ('mean_pop', '平均种群', '-'),
                        ('total_litters', '窝数', '-'), ('trimmed_pups', '裁剪幼崽', '0'),
                        ('migrated', '迁徙', '-'), ('total_births', '出生', '-')]:
        print('  %-8s %8.3f ± %.3f   (v0.5 报告: %s)' % (lab, m(k), sd(k), ref))
