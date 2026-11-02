# -*- coding: utf-8 -*-
"""第二轮定向搜索：把「上周所见的三个硬约束」拆开来逐个验证杠杆效果。"""

import statistics

from fox_ecosystem_sim import BASE_PARAMS, run_round

SEEDS = [20261031 + i * 7919 for i in range(3)]


def met(runs):
    g = lambda k: statistics.mean([r[k] for r in runs])
    return {
        'births': g('total_births'),
        'gens': g('max_generation'),
        'lines': g('founder_lines_alive'),
        'F': g('meanF_end'),
        'het0': g('het_start'),
        'het1': g('het_end'),
        'colors': statistics.mean([len(r['end_colors']) for r in runs]),
        'fp': g('unique_fingerprints'),
        'fpshare': g('fp_top_share') * 100,
        'muts': g('mutations_total'),
        'muts_alive': g('mutations_survived'),
        'cap': g('cap_ratio') * 100,
        'maxpop': max(r['max_pop_seen'] for r in runs),
        'litters': g('total_litters'),
    }


def sc(m):
    return (min(1, m['births'] / 120.0) * 1.0
            + min(1, m['gens'] / 20.0) * 1.0
            + min(1, m['lines'] / 7.0) * 1.0
            + (1 - min(1, m['F'] / 0.15)) * 1.0
            + min(1, m['colors'] / 3.0) * 1.0
            + min(1, m['fp'] / 6.0) * 1.0
            + min(1, m['muts'] / 3.0) * 1.0)


def build(**over):
    P = dict(BASE_PARAMS)
    P.update({'Cap_mode': 'L_plus_slot', 'Lifespan_mean_days': 40,
              'Lifespan_sd_days': 8, 'Lifespan_min_days': 25, 'Lifespan_max_days': 70,
              'Juv_mort_lo': 0.30, 'Juv_mort_hi': 0.40,
              'Inbreed_threshold': 0.0625})
    P.update(over)
    return P


def stage2():
    print('===== 第二阶段：上限 × 野外引入（gene flow） × 创始基因库最大化 =====')
    rows = []
    for nmax in (20, 30, 40):
        for imm in [(False, 3, 0), (True, 3, 1), (True, 2, 1), (True, 2, 2)]:
            for pool in (False, True):
                P = build(N_max=nmax, Immigration_enable=imm[0],
                          Immigration_every_gen=imm[1], Immigration_n=imm[2],
                          Founder_pool_max=pool)
                runs = [run_round(s, P, 5) for s in SEEDS]
                rows.append(((nmax, imm, pool), met(runs)))
    rows.sort(key=lambda x: -sc(x[1]))
    print('%-5s %-14s %-6s | %5s %5s %6s %6s %6s %5s %5s %5s %6s | %5s' %
          ('上限', '野外引入', '库最大', '出生', '世代', '创始系', 'F均值', '毛色', '指纹', '突变', '突变活', '至上限', '得分'))
    for (nmax, imm, pool), m in rows:
        imm_s = '关' if not imm[0] else '每%d代%d只' % (imm[1], imm[2])
        print('%-5d %-14s %-6s | %5.0f %5.1f %6.1f %6.3f %6.1f %5.1f %5.1f %5.1f %6.0f%% | %5.2f' %
              (nmax, imm_s, '是' if pool else '否',
               m['births'], m['gens'], m['lines'], m['F'], m['colors'], m['fp'],
               m['muts'], m['muts_alive'], m['cap'], sc(m)))
    return rows


def stage3(base_cfg):
    print()
    print('===== 第三阶段：在最优点上微调寿命与近交阈值 =====')
    nmax, imm, pool = base_cfg
    rows = []
    for life in (28, 40, 55, 70):
        for thr in (0.125, 0.0625):
            P = build(N_max=nmax, Immigration_enable=imm[0], Immigration_every_gen=imm[1],
                      Immigration_n=imm[2], Founder_pool_max=pool,
                      Lifespan_mean_days=life, Lifespan_sd_days=max(5, life * 0.2),
                      Lifespan_min_days=max(18, life * 0.6), Lifespan_max_days=life * 1.5,
                      Inbreed_threshold=thr)
            runs = [run_round(s, P, 5) for s in SEEDS]
            rows.append(((life, thr), met(runs)))
    rows.sort(key=lambda x: -sc(x[1]))
    print('%-6s %-8s | %5s %5s %6s %6s %6s %5s %5s %5s %6s | %5s' %
          ('寿命', '近交阈值', '出生', '世代', '创始系', 'F均值', '毛色', '指纹', '突变', '突变活', '至上限', '得分'))
    for (life, thr), m in rows:
        print('%-6d %-8s | %5.0f %5.1f %6.1f %6.3f %6.1f %5.1f %5.1f %5.1f %6.0f%% | %5.2f' %
              (life, thr, m['births'], m['gens'], m['lines'], m['F'], m['colors'], m['fp'],
               m['muts'], m['muts_alive'], m['cap'], sc(m)))
    return rows


if __name__ == '__main__':
    rows = stage2()
    best = rows[0][0]
    print()
    print('第二阶段最优：上限=%d 引入=%s 库最大化=%s' % (best[0], best[1], '是' if best[2] else '否', ))
    stage3(best)
