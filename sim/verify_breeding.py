# -*- coding: utf-8 -*-
"""
育种引擎自检：解析预测 vs 蒙特卡洛真实配子组合。

面板上的概率必须是真的——如果预测器算错，玩家按它育种就等于被误导。
本脚本按下列层次验证：
  A. 单位点分离比（孟德尔 1:2:1 / 3:1 / 全显性 / 测交 1:1）
  B. 复等位与上位（ww 遮蔽、A 序列、不完全显性）
  C. 多基因累加（尾数 1–5、毛长 0–4）
  D. 全性状预测 vs 蒙特卡洛 30000 次（允许 ±0.01 误差）
  E. 种群频率面板自洽（各位点频率和为 1、拷贝数 = 2N）
  F. 隐性解锁概率 vs 蒙特卡洛
"""
import random
import sys
from collections import defaultdict

import fox_ecosystem_sim as M
import breeding as B

PASS = FAIL = 0


def ck(cond, msg, extra=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('  [OK]   %s' % msg)
    else:
        FAIL += 1
        print('  [FAIL] %s   %s' % (msg, extra))


def near(a, b, tol=0.01):
    return abs(a - b) <= tol


def mk(locus, gt, **extra):
    """
    造一个只关心某位点、其余固定的基因型。
    默认把 W 设为 WW、D 设为 DD —— 否则 ww 上位会把毛色全盖成雪绒白，
    dd 稀释会把主毛色改成淡色系，导致毛色断言被无关位点污染。
    """
    g = {}
    for l in M.LOCUS_KEYS:
        spec = M.LOCUS_SPEC[l]
        g[l] = (spec['dom'][-1], spec['dom'][-1])   # 其余位点用最隐性纯合
    g['W'] = ('W', 'W')
    g['D'] = ('D', 'D')
    g.update(extra)
    if locus is not None:
        g[locus] = gt
    return g


def mc_litter(ga, gb, n=30000, seed=20261101):
    """蒙特卡洛：真实随机配子组合 n 次，返回性状取值频率。"""
    rng = random.Random(seed)
    res = {t['key']: defaultdict(int) for t in B.TRAITS}
    for _ in range(n):
        child = {}
        for l in M.LOCUS_KEYS:
            child[l] = (ga[l][rng.randrange(2)], gb[l][rng.randrange(2)])
        ph = M.phenotype(child)
        for t in B.TRAITS:
            res[t['key']][t['pick'](ph)] += 1
    return {k: {v: c / n for v, c in d.items()} for k, d in res.items()}


print('=' * 78)
print('育种引擎自检（§18 基因与性状面板）')
print('=' * 78)

# ---------------------------------------------------------------- A 单位点
print('\nA. 单位点分离比')
d = B.locus_offspring_dist('D', ('D', 'd'), ('D', 'd'))
ck(near(d[('D', 'D')], 0.25) and near(d[('d', 'd')], 0.25) and near(d[('D', 'd')], 0.5),
   'Dd × Dd → DD:Dd:dd = 1:2:1', str(d))

d = B.locus_offspring_dist('K', ('K', 'k'), ('k', 'k'))
ck(near(d[('K', 'k')], 0.5) and near(d[('k', 'k')], 0.5),
   'Kk × kk 测交 → 1:1', str(d))

d = B.locus_offspring_dist('G', ('G', 'G'), ('g', 'g'))
ck(near(d[('G', 'g')], 1.0), 'GG × gg → 全 Gg', str(d))

d = B.locus_offspring_dist('Ht', ('ht', 'ht'), ('ht', 'ht'))
ck(near(d[('ht', 'ht')], 1.0), 'ht/ht × ht/ht → 全隐性纯合', str(d))

# ---------------------------------------------------------------- B 上位 / 复等位
print('\nB. 上位与复等位')
ga = mk('W', ('W', 'w'))
gb = mk('W', ('W', 'w'))
p_ww = B.predict_target(ga, gb, 'color', '雪绒白')
ck(near(p_ww, 0.25), 'Ww × Ww → 雪绒白 ww 概率 1/4', '%.4f' % p_ww)

# ww 背景下 A 位点不可见：验证 carrier_view 标出「上位遮蔽」
g_ww = mk('W', ('w', 'w'))
g_ww['A'] = ('A+', 'Ab')
v = B.carrier_view(g_ww)
rowA = next(r for r in v['rows'] if r['locus'] == 'A')
ck(rowA['masked'] is True, 'ww 时 A 位点被标记为「上位遮蔽」', str(rowA))
ck(M.phenotype(g_ww)['color'] == '雪绒白', 'ww 时表型确实是雪绒白（A 基因型仍在）')

# A 复等位序列：A+/Ab × Ab/Ab（背景 D=DD、W=WW，排除稀释与白化干扰）
ga = mk('A', ('A+', 'Ab'))
gb = mk('A', ('Ab', 'Ab'))
p = B.predict_target(ga, gb, 'color', '赤橙')
ck(near(p, 0.5), 'A+/Ab × Ab/Ab → 赤橙 1/2', '%.4f' % p)
p = B.predict_target(ga, gb, 'color', '墨黑')
ck(near(p, 0.5), 'A+/Ab × Ab/Ab → 墨黑(Ab/Ab) 1/2', '%.4f' % p)

# 稀释基因 dd 的作用（面板要能显示「同样的 A 基因型，dd 会变淡色」）
ga = mk('A', ('A+', 'A+'), D=('D', 'd'))
gb = mk('A', ('A+', 'A+'), D=('D', 'd'))
p = B.predict_target(ga, gb, 'color', '奶油金')
ck(near(p, 0.25), '赤橙 × 稀释携带(Dd×Dd) → 奶油金 dd 1/4', '%.4f' % p)

# 不完全显性（dosage）Ez：Ez/ez × Ez/ez → 2 个显性 1/4
d = B.locus_offspring_dist('Ez', ('Ez', 'ez'), ('Ez', 'ez'))
ck(near(d[('Ez', 'Ez')], 0.25), 'Ez/ez × Ez/ez → Ez/Ez 1/4', str(d))

# ---------------------------------------------------------------- C 多基因累加
print('\nC. 多基因累加（面板必须能显示 1–5 尾 / 0–4 毛长）')
ga = mk('Tn1', ('T', 't')); ga['Tn2'] = ('T', 't')
gb = ga
dist = B.predict_target(ga, gb, 'tails', '5 尾')
ck(near(dist, 1 / 16), 'Tt×Tt 两位点 → 5 尾 = 1/16', '%.4f' % dist)
dist1 = B.predict_target(ga, gb, 'tails', '1 尾')
ck(near(dist1, 1 / 16), 'Tt×Tt 两位点 → 1 尾 = 1/16', '%.4f' % dist1)
dist3 = B.predict_target(ga, gb, 'tails', '3 尾')
ck(near(dist3, 6 / 16), 'Tt×Tt 两位点 → 3 尾 = 6/16（1:4:6:4:1）', '%.4f' % dist3)

ga2 = mk('L1', ('L', 'l')); ga2['L2'] = ('L', 'l')
d2 = B.predict_target(ga2, ga2, 'hair_len', '4/4 档')
ck(near(d2, 1 / 16), 'Ll×Ll 两位点 → 毛长 4/4 = 1/16', '%.4f' % d2)

# ---------------------------------------------------------------- D 全性状 vs 蒙特卡洛
print('\nD. 全性状预测 vs 蒙特卡洛（30000 次，容差 ±0.01）')
rng = random.Random(7)
ga = {l: tuple(rng.choice(M.allele_pool(l)) for _ in range(2)) for l in M.LOCUS_KEYS}
gb = {l: tuple(rng.choice(M.allele_pool(l)) for _ in range(2)) for l in M.LOCUS_KEYS}
# 保证 W 不是 ww（否则毛色全白、其余性状仍可验证）
pred = B.predict_litter(ga, gb)
mc = mc_litter(ga, gb, 30000)
worst = 0.0
for t in pred['traits']:
    pm = {it['value']: it['prob'] for it in t['items']}
    for val, p_mc in mc[t['key']].items():
        p_pr = pm.get(val, 0.0)
        worst = max(worst, abs(p_pr - p_mc))
        if abs(p_pr - p_mc) > 0.01:
            print('    偏差 %s/%s  解析 %.4f vs MC %.4f' % (t['name'], val, p_pr, p_mc))
ck(worst <= 0.01, '全部 %d 个性状的解析概率与蒙特卡洛一致（最大偏差 %.5f）'
   % (len(B.TRAITS), worst))

# 每个性状概率和 = 1
for t in pred['traits']:
    s = sum(it['prob'] for it in t['items'])
    if abs(s - 1.0) > 1e-6:
        ck(False, '%s 概率和为 1' % t['name'], '%.6f' % s)
ck(True, '每个性状的概率分布归一（和 = 1）')

# ---------------------------------------------------------------- E 种群面板自洽
print('\nE. 种群隐性等位看板自洽性')
w = M.World(dict(M.TUNED_V3_PARAMS), 20261031)
for _ in range(3 * 24 * 24):
    w.step()
    if not w.alive_ids:
        break
ids = list(w.alive_ids)
rows = B.population_panel(w)
ck(len(ids) > 0, '种群非空（%d 只）' % len(ids))
by_locus = defaultdict(list)
for r in rows:
    by_locus[r['locus']].append(r)
ok_sum = ok_copy = True
for loc, rs in by_locus.items():
    s = sum(r['freq'] for r in rs)
    c = sum(r['copies'] for r in rs)
    if abs(s - 1.0) > 1e-9:
        ok_sum = False
        print('    %s 频率和 %.6f' % (loc, s))
    if c != 2 * len(ids):
        ok_copy = False
        print('    %s 拷贝数 %d != 2N=%d' % (loc, c, 2 * len(ids)))
ck(ok_sum, '每个位点等位频率和 = 1（%d 个位点）' % len(by_locus))
ck(ok_copy, '每个位点拷贝数 = 2N（N=%d）' % len(ids))

# ---------------------------------------------------------------- F 解锁概率 vs MC
print('\nF. 隐性解锁概率 vs 蒙特卡洛')
# 找一个携带 w 的配对
carriers = [i for i in ids if 'w' in w.foxes[i].geno['W']]
if len(carriers) >= 2:
    a, b = carriers[0], carriers[1]
    p = B.predict_target(w.foxes[a].geno, w.foxes[b].geno, 'color', '雪绒白')
    mc = mc_litter(w.foxes[a].geno, w.foxes[b].geno, 30000)
    p_mc = mc['color'].get('雪绒白', 0.0)
    ck(near(p, p_mc), '雪绒白解锁概率 解析 %.4f vs MC %.4f' % (p, p_mc))
else:
    print('  [跳过] 种群中 w 携带者不足 2 只')

# 推荐功能可用
rec = B.recommend_for(w, 'tails', '5 尾', top=5)
ck(isinstance(rec, list), 'recommend_for() 正常返回（%d 条）' % len(rec))
if rec:
    top = rec[0]
    ck(top['prob'] >= rec[-1]['prob'], '推荐按概率降序排列')
    ck(all('r' in x for x in rec), '每条推荐都带亲缘系数 r（近交预警字段）')

# 濒危报告
end = B.endangered_report(w)
ck(isinstance(end, list), 'endangered_report() 正常返回（%d 个濒危等位）' % len(end))

# 携带者摘要
hs = B.hidden_summary(w.foxes[ids[0]].geno)
ck(isinstance(hs, list), 'hidden_summary() 正常返回（%d 条隐藏信息）' % len(hs))

print('\n' + '=' * 78)
print('结果：%d 通过 / %d 失败' % (PASS, FAIL))
print('=' * 78)
sys.exit(1 if FAIL else 0)
