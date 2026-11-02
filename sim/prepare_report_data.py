# -*- coding: utf-8 -*-
"""为 v0.5 运行报告准备全部数据 -> sim/report_data.json

内容：
  1) 三版本（v0.3 base / v0.4 tuned / v0.5）× 12 种子 × 20 生态年：逐日均值序列 + 汇总统计
  2) 三档节奏预设（稳健 / 标准 / 激进）× 12 种子 × 20 生态年
  3) 种群上限敏感性（30/40/50/60）
  4) 正式对照轮（各版本 5 轮 × 5 生态年，由 fox_ecosystem_sim.py 生成）
"""
import os
import sys
import json
import statistics
from multiprocessing import Pool

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
_M = None


def _init():
    global _M
    sys.path.insert(0, _HERE)
    import importlib.util
    spec = importlib.util.spec_from_file_location('m', os.path.join(_HERE, 'fox_ecosystem_sim.py'))
    _M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_M)


PRESETS = {
    '稳健档': dict(Lifespan_mean_days=52, Lifespan_sd_days=10, Lifespan_min_days=32,
                   Lifespan_max_days=88, Migrate_base=0.00003, Immigration_every_days=16 * 24),
    '标准档': dict(),
    '激进档': dict(Lifespan_mean_days=32, Lifespan_sd_days=7, Lifespan_min_days=20,
                   Lifespan_max_days=54, Migrate_base=0.00006, Immigration_every_days=9 * 24),
}


def task(t):
    kind, name, over, seed, yrs = t
    if kind == 'variant':
        P = dict({'base': _M.BASE_PARAMS, 'tuned': _M.TUNED_PARAMS, 'v2': _M.TUNED_V2_PARAMS}[name])
    elif kind == 'preset':
        P = dict(_M.TUNED_V2_PARAMS); P.update(over)
    elif kind == 'cap':
        P = dict(_M.TUNED_V2_PARAMS); P.update(over)
    r = _M.run_round(seed, P, yrs)
    return kind, name, r


KEYS_STAT = ('max_generation', 'meanF_end', 'het_start', 'het_end', 'het_loss_pct',
             'fp_ratio', 'fp2_ratio', 'unique_fingerprints', 'unique_fingerprints2',
             'founder_lines_alive', 'total_litters', 'total_births', 'total_deaths',
             'migrated', 'immigrants', 'blocked_litters', 'trimmed_pups', 'max_pop_seen',
             'final_pop', 'mean_pop', 'mutations_total', 'mutations_survived',
             'court_attempts', 'court_abandoned', 'torpor_events', 'selection_r',
             'cap_ratio', 'cap_day')


def summarize(rs):
    out = {}
    for k in KEYS_STAT:
        try:
            out[k] = round(statistics.mean([r[k] for r in rs]), 4)
        except Exception:
            out[k] = None
    out['_se'] = {}
    for k in ('max_generation', 'meanF_end', 'het_end', 'fp2_ratio'):
        v = [r[k] for r in rs]
        out['_se'][k] = round(statistics.pstdev(v) / max(1.0, len(v) ** 0.5), 4)
    out['colors'] = round(statistics.mean([len(r['end_colors']) for r in rs]), 3)
    out['end_colors'] = {}
    for r in rs:
        for k, v in r['end_colors'].items():
            out['end_colors'][k] = out['end_colors'].get(k, 0) + v
    # 死因均值
    dc = {}
    for r in rs:
        for k, v in r['deaths_by_cause'].items():
            dc[k] = dc.get(k, 0.0) + v
    out['deaths_by_cause'] = {k: round(v / len(rs), 2) for k, v in dc.items()}
    out['mig_share'] = round(statistics.mean(
        [r['migrated'] / max(1, r['migrated'] + r['total_deaths']) for r in rs]), 4)
    # 逐日序列（按天对齐后取均值）
    n = min(len(r['daily']) for r in rs)
    daily = []
    for i in range(n):
        daily.append({
            'day': rs[0]['daily'][i]['day'],
            'pop': round(statistics.mean([r['daily'][i]['pop'] for r in rs]), 2),
            'het': round(statistics.mean([r['daily'][i]['het_o'] for r in rs]), 4),
            'F': round(statistics.mean([r['daily'][i]['meanF'] for r in rs]), 4),
            'maxgen': round(statistics.mean([r['daily'][i]['maxgen'] for r in rs]), 2),
            'colors': round(statistics.mean([len(r['daily'][i]['colors']) for r in rs]), 2),
        })
    out['daily'] = daily
    return out


if __name__ == '__main__':
    seeds = [20261031 + i * 7919 for i in range(12)]
    tasks = []
    for v in ('base', 'tuned', 'v2'):
        tasks += [('variant', v, {}, s, 20) for s in seeds]
    for nm, ov in PRESETS.items():
        tasks += [('preset', nm, ov, s, 20) for s in seeds]
    for cap in (30, 40, 50, 60):
        tasks += [('cap', 'cap%d' % cap, {'N_max': cap, 'Litter_reserve': 6}, s, 20) for s in seeds]
    print('共 %d 次 20 生态年运行' % len(tasks))
    with Pool(initializer=_init) as pool:
        raw = pool.map(task, tasks, chunksize=1)

    store = {}
    for kind, name, r in raw:
        store.setdefault((kind, name), []).append(r)

    data = {'seeds': seeds, 'years': 20}
    data['variants'] = {v: summarize(store[('variant', v)]) for v in ('base', 'tuned', 'v2')}
    data['presets'] = {k: summarize(store[('preset', k)]) for k in PRESETS}
    data['caps'] = {'cap%d' % c: summarize(store[('cap', 'cap%d' % c)]) for c in (30, 40, 50, 60)}
    data['preset_names'] = list(PRESETS.keys())

    # 正式 5 轮 × 5 年对照
    off = {}
    for v, fn in (('base', 'results_base_r5_y5.json'),
                  ('tuned', 'results_tuned_r5_y5.json'),
                  ('v2', 'results_v2_r5_y5.json')):
        p = os.path.join(_HERE, fn)
        if os.path.exists(p):
            d = json.load(open(p, encoding='utf-8'))
            off[v] = {'rounds': d['rounds'], 'stat': summarize(d['rounds'])}
    data['official'] = off

    out = os.path.join(_HERE, 'report_data.json')
    json.dump(data, open(out, 'w', encoding='utf-8'), ensure_ascii=False)
    print('已写入', out, '(%.1f KB)' % (os.path.getsize(out) / 1024))
