# -*- coding: utf-8 -*-
"""
派生pet 生态参数搜索 —— 第二阶段（v0.5）

在已批准的 E1-E5 基础（上限 40 / 寿命 40 游戏天 / 野外引入开启 / 突变 3% / 选择强度指示）
之上，继续搜索更优的组合。所有 configuration 都不突破以下红线：

  R1  硬上限 N_max 恒定 40（ceiling 只由这里收紧，不由里任何别的机制替代）
  R2  峰值种群 <= N_max（违反即该候选作废）
  R3  不靠放松上限换取指标：任何指标的提升都必须来自周转率 / 多样性来源
  R4  静默裁剪的幼崽数接近 0（不再出现"怀了 4 只只生 1 只"的隐形删减）
  R5  5 年不崩溃（末种群 >= 50% 上限）

评分采用产品导向的加权：多样性 / 近交 / 世代推进 / 稀有供给 / 毛色 / 血统留存 / 画面活性。
"""

import os
import sys
import json
import itertools
import statistics
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FOXMOD = None


def _init():
    global FOXMOD
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'foxsim', os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'fox_ecosystem_sim.py'))
    FOXMOD = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(FOXMOD)


# =============================================================================
# 评分：全部归一化到 0-1，权重之和 100
# =============================================================================
WEIGHTS = {
    'div': 22,     # 末代表型指纹丰富度（一眼能否分辨每一只）
    'inb': 22,     # 近交抑制
    'gen': 14,     # 世代推进速度（演化可观察性）
    'agency': 12,  # 用户选育能动性：基因流入过猛会淹没人工选择，按「每代迁移者 Nm≈1」取最优
    'act': 8,      # 画面活性（繁殖事件密度）
    'mut': 8,      # 稀有/突变的实际供给
    'line': 8,     # 创始血统留存
    'color': 6,    # 毛色种类
}


def clamp01(x):
    return max(0.0, min(1.0, x))


def score_one(r, P):
    """单个种子的评分；返回 (score, 硬性否决原因 or None)"""

    def violated(reason):
        return -1.0, reason

    # ---- 硬红线 ----
    if r['max_pop_seen'] > P['N_max']:
        return violated('冲破上限 %d>%d' % (r['max_pop_seen'], P['N_max']))
    if r['final_pop'] < 0.5 * P['N_max']:
        return violated('种群崩溃 末=%d' % r['final_pop'])
    if r['cap_ratio'] > 0.88:
        return violated('长期冻结 %.0f%%' % (r['cap_ratio'] * 100))
    if r['trimmed_pups'] > 0.25 * max(1, r['total_births']):
        return violated('裁剪过多 %d' % r['trimmed_pups'])

    ippg = r['immigrants'] / max(1.0, r['max_generation'])   # 每代迁移者数 Nm
    parts = {
        'div': clamp01(r['fp_ratio'] / 0.80),
        'agency': clamp01(1.0 - abs(ippg - 1.0) / 1.2),
        'inb': clamp01((0.12 - r['meanF_end']) / 0.10),
        'gen': clamp01((r['max_generation'] - 5) / 10.0),
        'mut': clamp01(r['mutations_survived'] / 4.0),
        'color': clamp01((len(r['end_colors']) - 2.0) / 3.0),
        'line': clamp01((r['founder_lines_alive'] - 5.0) / 4.0),
        'act': clamp01(r['total_litters'] / 70.0),
    }
    total = sum(WEIGHTS[k] * parts[k] for k in parts) / 100.0
    return total, parts


# =============================================================================
# 候选配置构造
# =============================================================================
def build_params(base, over):
    P = dict(base)
    P.update(over)
    life = P['Lifespan_mean_days']
    P.setdefault('Lifespan_sd_days', max(4, life * 0.2))
    P['Lifespan_sd_days'] = max(4, life * 0.2)
    P['Lifespan_min_days'] = max(16, int(life * 0.62))
    P['Lifespan_max_days'] = int(life * 1.7)
    return P


def grid_stage1(base):
    """网格 v2：围绕「零裁剪 + Nm≈1/代 + 异地互补引入」做精细化。"""
    out = []
    mig_specs = [('g1', 'gen', 1), ('d10', 'days', 10), ('d14', 'days', 14), ('d18', 'days', 18)]
    for tag, life, mut, soft, reserve in itertools.product(
            [t for t, _, _ in mig_specs],
            [38, 45, 55],
            [0.030, 0.045],
            [0.85, 1.0],
            [5, 6]):
        mdict = {t: (m, c) for t, m, c in mig_specs}
        mode, cadence = mdict[tag]
        over = dict(
            Cap_mode='L_plus_reserve',
            Litter_reserve=reserve,
            N_soft_frac=soft,
            Immigration_enable=True,
            Immigration_mode=mode,
            Immigration_n=1,
            Immigration_pool='complement',
            Immigration_sex='balance',
            Lifespan_mean_days=life,
            Mut_rate=mut,
            Juv_mort_lo=0.25, Juv_mort_hi=0.35,
        )
        if mode == 'gen':
            over['Immigration_every_gen'] = cadence
        else:
            over['Immigration_every_days'] = cadence * 24
        out.append(('%s/L%d/M%.1f%%/S%.2f/R%d' % (tag, life, mut * 100, soft, reserve), over))
    return out


def grid_stage2(base):
    """第二阶段：在第一阶段胜出的「每 10 天 1 只 / 长寿 / 整窝预留」家族附近精细步长。"""
    out = []
    for every, life, juv in itertools.product(
            [8, 9, 10, 11, 12, 14],
            [48, 52, 55, 60],
            [(0.25, 0.35), (0.20, 0.30)]):
        over = dict(
            Cap_mode='L_plus_reserve',
            Litter_reserve=6,
            N_soft_frac=1.0,
            Immigration_enable=True,
            Immigration_mode='days',
            Immigration_every_days=every * 24,
            Immigration_n=1,
            Immigration_pool='complement',
            Immigration_sex='balance',
            Lifespan_mean_days=life,
            Mut_rate=0.030,
            Juv_mort_lo=juv[0], Juv_mort_hi=juv[1],
        )
        out.append(('E%d/L%d/J%d' % (every, life, int(juv[0] * 100)), over))
    return out


# =============================================================================
# 并行执行
# =============================================================================
def run_task(args):
    name, over, seeds, years = args
    P = build_params(FOXMOD.TUNED_PARAMS, over)
    rs = [FOXMOD.run_round(s, P, years) for s in seeds]
    vals = []
    reasons = []
    for r in rs:
        sc, parts = score_one(r, P)
        vals.append(sc)
        if sc < 0:
            reasons.append(parts)
    mean = lambda k: statistics.mean([r[k] for r in rs])
    return {
        'name': name, 'over': {k: (str(v) if isinstance(v, tuple) else v) for k, v in over.items()},
        'score': statistics.mean(vals) if not reasons else -1.0,
        'veto': reasons[0] if reasons else None,
        'seed_scores': vals,
        'litters': mean('total_litters'), 'births': mean('total_births'),
        'trimmed': mean('trimmed_pups'), 'blocked': mean('blocked_litters'),
        'F': mean('meanF_end'), 'het_end': mean('het_end'),
        'gens': mean('max_generation'), 'fp': mean('unique_fingerprints'),
        'fp_ratio': mean('fp_ratio'), 'fp2_ratio': mean('fp2_ratio'),
        'colors': statistics.mean([len(r['end_colors']) for r in rs]),
        'lines': mean('founder_lines_alive'), 'imm': mean('immigrants'),
        'mutS': mean('mutations_survived'), 'mutT': mean('mutations_total'),
        'pop': mean('final_pop'), 'peak': mean('max_pop_seen'),
        'capr': mean('cap_ratio'), 'mig': mean('migrated'),
    }


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', type=int, default=1)
    ap.add_argument('--seeds', type=int, default=6)
    ap.add_argument('--years', type=int, default=5)
    ap.add_argument('--top', type=int, default=12)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()
    _init()          # 主进程也要加载，构造候选网格时需要读 BASE/TUNED 参数

    seed0 = 20261031
    def seeds_for(n):
        return [seed0 + i * 7919 for i in range(n)]

    if args.stage == 2:
        cands = grid_stage2(FOXMOD.TUNED_PARAMS)
        print('第二阶段：候选 %d 组 × 种子 %d 个 = %d 次运行' % (
            len(cands), args.seeds, len(cands) * args.seeds))
    elif args.stage == 1:
        cands = grid_stage1(FOXMOD.TUNED_PARAMS)
        print('第一阶段：候选 %d 组 × 种子 %d 个 = %d 次运行' % (
            len(cands), args.seeds, len(cands) * args.seeds))
    else:
        # 第二阶段在阶段 1 的前若干名附近做精修
        prev = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           'search_stage1.json'), encoding='utf-8'))
        best = [c for c in prev['results'] if c['score'] > 0][:6]
        cands = []
        for b in best:
            src = [c for c in grid_stage1(FOXMOD.TUNED_PARAMS) if c[0] == b['name']]
            if not src:
                continue
            base_over = src[0][1]
            for delta in ({}, {'Immigration_every_days': 8 * 24},
                          {'Immigration_every_days': 12 * 24},
                          {'Mut_rate': round(b['over']['Mut_rate'] * 1.5, 4)},
                          {'Lifespan_mean_days': int(b['over']['Lifespan_mean_days'] * 0.85)},
                          {'Lifespan_mean_days': int(b['over']['Lifespan_mean_days'] * 1.15)}):
                o = dict(base_over); o.update(delta)
                tag = b['name'] + ('' if not delta else '+' + ','.join(
                    '%s=%s' % (k, v) for k, v in delta.items()))
                cands.append((tag, o))
        print('第二阶段：精修候选 %d 组 × 种子 %d 个' % (len(cands), args.seeds))

    tasks = [(n, o, seeds_for(args.seeds), args.years) for n, o in cands]
    with Pool(initializer=_init) as pool:
        results = pool.map(run_task, tasks, chunksize=1)

    results.sort(key=lambda x: -x['score'])
    hdr = ('%-34s %6s %6s %6s %6s %6s %6s %6s %6s %6s %6s %6s %6s'
           % ('配置', '总分', 'F', '指纹', '指纹2', '世代', '突变活', '毛色', '血统', '引入', '窝', '裁剪', '末pop'))
    print('\n' + hdr)
    print('-' * len(hdr))
    for r in results[:args.top]:
        if r['score'] < 0:
            print('%-34s %6s  【否决】%s' % (r['name'], '--', r['veto']))
            continue
        print('%-34s %6.3f %6.3f %6.2f %6.2f %6.1f %6.1f %6.2f %6.1f %6.1f %6.0f %6.0f %6.1f'
              % (r['name'], r['score'], r['F'], r['fp_ratio'], r['fp2_ratio'], r['gens'],
                 r['mutS'], r['colors'], r['lines'], r['imm'], r['litters'],
                 r['trimmed'], r['pop']))
    nveto = sum(1 for r in results if r['score'] < 0)
    print('\n被硬红线否决的候选：%d / %d' % (nveto, len(results)))

    out = args.out or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   'search_stage%d.json' % args.stage)
    json.dump({'stage': args.stage, 'seeds': args.seeds, 'years': args.years,
               'weights': WEIGHTS, 'results': results},
              open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('已写入', out)


if __name__ == '__main__':
    main()
