# -*- coding: utf-8 -*-
"""
面板实战检验：在真实种群上回答三个问题（决定 §18 面板是否值得做）

  Q1 外观相同 ≠ 基因型：外观一模一样的两只，面板能否区分？
  Q2 隐性解锁可行性：想培育雪绒白 / 5 尾 / 紫瞳，种群里有没有可行配对？
  Q3 濒危预警准不准：濒危等位是否真的集中在少数个体身上（误删风险）？
"""
import statistics
from collections import defaultdict

import fox_ecosystem_sim as M
import breeding as B

w = M.World(dict(M.TUNED_V3_PARAMS), 20261031)
for _ in range(5 * 24 * 24):          # 5 生态年
    w.step()
    if not w.alive_ids:
        break
ids = list(w.alive_ids)
print('种群：%d 只（第 %d 代）\n' % (len(ids), max(w.foxes[i].gen for i in ids)))

# ---------------------------------------------------------------- Q1
print('=' * 78)
print('Q1  外观相同 ≠ 基因型（§2.5 的教学点，面板必须能揭示）')
print('=' * 78)
def look_key(i):
    ph = w.foxes[i].pheno
    return (ph['color'], ph['pattern'], ph['tails'], ph['hair_len'], ph['curl'])

groups = defaultdict(list)
for i in ids:
    groups[look_key(i)].append(i)

found = 0
for k, members in sorted(groups.items(), key=lambda x: -len(x[1])):
    if len(members) < 2:
        continue
    # 这群外观相同的，基因型差异有多大？
    sigs = set()
    for i in members:
        sig = tuple(tuple(sorted(w.foxes[i].geno[l])) for l in M.LOCUS_KEYS)
        sigs.add(sig)
    # 面板视角：它们藏的隐性等位一样吗
    hides = [set(a for r in B.carrier_view(w.foxes[i].geno)['rows'] for a in r['hidden_raw'])
             for i in members]
    diff = len(set(frozenset(h) for h in hides))
    print('  外观「%s / %s / %d尾 / 毛长%d / %s」共 %d 只 → %d 种基因型、%d 种隐藏组合'
          % (k[0], B._PATTERN_CN.get(k[1], k[1]), k[2], k[3],
             '卷毛' if k[4] else '直毛', len(members), len(sigs), diff))
    if diff > 1 and found < 3:
        for i in members[:3]:
            hs = B.hidden_summary(w.foxes[i].geno)
            print('      FX-%04d 藏着：%s' % (i, '；'.join(h['text'] for h in hs[:3]) or '（无）'))
        found += 1
    if found >= 3:
        break

# ---------------------------------------------------------------- Q2
print('\n' + '=' * 78)
print('Q2  隐性性状解锁：目标驱动育种可行性')
print('=' * 78)
targets = [('color', '雪绒白'), ('tails', '5 尾'), ('eye', '紫瞳'),
           ('color', '奶油金'), ('pattern', '纯色'), ('hair_len', '4/4 档')]
for tk, tv in targets:
    rec = B.recommend_for(w, tk, tv, top=3, min_prob=0.0)
    if not rec:
        print('  %-8s %-8s → 当前种群无可行配对' % (tk, tv))
        continue
    best = rec[0]
    safe = [x for x in rec if x['r'] < 0.125]
    n_pair_all = sum(1 for a in ids if w.foxes[a].sex == 'F' and w.foxes[a].phase == 'adult') * \
                 sum(1 for b in ids if w.foxes[b].sex == 'M' and w.foxes[b].phase == 'adult')
    feasible = sum(1 for x in B.recommend_for(w, tk, tv, top=10 ** 6, min_prob=0.0)
                   if x['prob'] > 0)
    print('  %-8s %-8s → 最优 %.1f%%（FX-%04d × FX-%04d，r=%.3f %s）| 可行配对 %d/%d'
          % (tk, tv, best['prob'] * 100, best['dam'], best['sire'], best['r'],
             best['risk'], feasible, n_pair_all))

# ---------------------------------------------------------------- Q3
print('\n' + '=' * 78)
print('Q3  濒危隐性等位：误删风险')
print('=' * 78)
end = B.endangered_report(w, max_copies=3)
if not end:
    print('  当前无濒危等位（拷贝数均 > 3）')
for r in end:
    # 这些拷贝集中在谁身上
    holders = [i for i in ids if r['allele'] in w.foxes[i].geno[r['locus']]]
    print('  %-8s %-10s 仅剩 %d 拷贝 / %d 只携带 → 集中在 %s'
          % (r['name'], r['allele_cn'], r['copies'], r['carriers'],
             '、'.join('FX-%04d' % i for i in holders)))

# ---------------------------------------------------------------- 补充：性选择靶点
print('\n' + '=' * 78)
print('补充  尾数是唯一可见进化载体 —— 面板应把它放主位')
print('=' * 78)
tails = [w.foxes[i].pheno['tails'] for i in ids]
print('  当前尾数分布：%s' % dict(sorted(
    {t: tails.count(t) for t in set(tails)}.items())))
print('  平均 %.2f 尾' % statistics.mean(tails))
tn1 = B.population_panel(w)
for loc in ('Tn1', 'Tn2'):
    rs = [x for x in tn1 if x['locus'] == loc and x['allele'] == 'T']
    if rs:
        print('  %s 显性等位 T 频率 %.3f（创始 0.18）' % (loc, rs[0]['freq']))
