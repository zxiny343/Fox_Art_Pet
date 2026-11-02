# -*- coding: utf-8 -*-
"""
基因与性状面板 · 育种引擎（设计稿 §18）

服务目标：隐性基因在外观上不可见，玩家无法据此做人工选择育种。
本模块提供四类数据，全部可由真实种群状态直接算出：

  1. carrier_view()      —— 个体：每个位点「表现出来的是什么 / 藏着什么」
                            含上位遮蔽（ww 盖住 A、D、P）与杂合携带
  2. predict_litter()    —— 配对：后代各性状的概率分布 + 隐性性状解锁概率
  3. population_panel()  —— 种群：每个等位基因的频率 / 拷贝数 / 携带者数（濒危预警）
  4. recommend_for()     —— 目标驱动：想培育某隐性性状，谁和谁配最优

设计红线（沿用 §5）：预测只对玩家可见，不改变实际配子随机组合。

概率算法：各位点独立分配 → 对某性状的依赖位点做联合枚举（每位点 ≤4 种
后代基因型，乘积 ≤64），无需 22 位点全笛卡尔积。
"""
from collections import defaultdict
from itertools import product

from fox_ecosystem_sim import (
    LOCUS_SPEC, LOCUS_KEYS, phenotype, allele_pool,
)

# =============================================================================
# 一、展示性状：玩家在狐狸身上能看见的东西 -> 依赖哪些位点
# =============================================================================
# name: 展示名; loci: 依赖位点; pick: 从 phenotype() 结果里取值
TRAITS = [
    {'key': 'color',    'name': '毛色',   'loci': ('A', 'D', 'W'),
     'pick': lambda ph: ph['color']},
    {'key': 'pattern',  'name': '斑纹',   'loci': ('P',),
     'pick': lambda ph: _PATTERN_CN.get(ph['pattern'], ph['pattern'])},
    {'key': 'tails',    'name': '尾数',   'loci': ('Tn1', 'Tn2', 'V'),
     'pick': lambda ph: '%d 尾' % ph['tails']},
    {'key': 'hair_len', 'name': '毛长',   'loci': ('L1', 'L2'),
     'pick': lambda ph: '%d/4 档' % ph['hair_len']},
    {'key': 'ear',      'name': '耳型',   'loci': ('Er',),
     'pick': lambda ph: _EAR_CN.get(ph['ear'], ph['ear'])},
    {'key': 'eye',      'name': '眼色',   'loci': ('Ey',),
     'pick': lambda ph: _EYE_CN.get(ph['eye'], ph['eye'])},
    {'key': 'curl',     'name': '卷毛',   'loci': ('K',),
     'pick': lambda ph: '卷毛' if ph['curl'] else '直毛'},
    {'key': 'hetero',   'name': '异色瞳', 'loci': ('Ht',),
     'pick': lambda ph: '异色瞳' if ph['hetero'] else '同色'},
    {'key': 'glow',     'name': '发光',   'loci': ('G',),
     'pick': lambda ph: '发光' if ph['glow'] else '不发光'},
    {'key': 'star',     'name': '星纹',   'loci': ('St',),
     'pick': lambda ph: '有星纹' if ph['star'] else '无'},
    {'key': 'halo',     'name': '光环',   'loci': ('Ha',),
     'pick': lambda ph: '有光环' if ph['halo'] else '无'},
    {'key': 'flame',    'name': '火焰纹', 'loci': ('Fl',),
     'pick': lambda ph: '有火焰' if ph['flame'] else '无'},
]

_PATTERN_CN = {'PT': '虎斑', 'Ps': '条纹', 'Pg': '斑点', 'p': '纯色'}
_EAR_CN = {'ErP': '尖耳', 'ErR': '圆耳', 'Erf': '折耳'}
_EYE_CN = {'EyG': '金瞳', 'EyC': '青瞳', 'EyB': '蓝瞳', 'EyV': '紫瞳'}

# 上位遮蔽关系：这些位点的表型会被别的位点盖住（基因型还在，但看不见）
EPISTATIC_HIDDEN = {
    'A': ('W', 'w'),   # ww 雪绒白会盖住 A/D/P
    'D': ('W', 'w'),
    'P': ('W', 'w'),
}


# 等位基因中文名（面板显示 + 导出给原型复用，避免两边各写一份而走样）
ALLELE_CN = {
    'A+': '赤橙', 'As': '霜灰', 'Av': '幽夜紫', 'Ab': '墨黑',
    'D': '深色', 'd': '稀释', 'W': '非白', 'w': '雪绒白',
    'PT': '虎斑', 'Ps': '条纹', 'Pg': '斑点', 'p': '纯色',
    'L': '长毛', 'l': '短毛', 'K': '卷毛', 'k': '直毛',
    'ErP': '尖耳', 'ErR': '圆耳', 'Erf': '折耳',
    'Ez': '大耳', 'ez': '小耳',
    'TpD': '深尖耳', 'TpW': '白尖耳', 'tp': '同色耳尖',
    'InL': '浅内耳', 'in': '深内耳', 'T': '多尾', 't': '少尾',
    'V': '九尾', 'v': '常尾', 'Tl': '长尾', 'tl': '短尾',
    'Tf': '蓬尾', 'tf': '细尾', 'TwW': '宽尾尖', 'TwK': '钩尾尖', 'tw': '无尾尖',
    'EyG': '金瞳', 'EyC': '青瞳', 'EyB': '蓝瞳', 'EyV': '紫瞳',
    'Ef': '圆眼', 'ef': '细眼', 'Ht': '异色瞳', 'ht': '同色',
    'G': '发光', 'g': '不发光', 'St': '星纹', 'st': '无星纹',
    'Ha': '光环', 'ha': '无光环', 'Fl': '火焰', 'fl': '无火焰',
}


def _allele_cn(locus, allele):
    """等位基因的中文显示名。"""
    return ALLELE_CN.get(allele, allele)


def _locus_pheno_cn(locus, gt):
    """单个位点的表型贡献（中文），用于面板左栏显示。"""
    spec = LOCUS_SPEC[locus]
    a, b = gt
    if spec['type'] == 'dosage':
        dom = spec['dom'][0]
        n = (1 if a == dom else 0) + (1 if b == dom else 0)
        return '%s（%d 个显性）' % (_allele_cn(locus, dom), n)
    order = spec['dom']
    ia = order.index(a) if a in order else 99
    ib = order.index(b) if b in order else 99
    top = order[min(ia, ib)] if min(ia, ib) < 99 else None
    return _allele_cn(locus, top) if top else '—'


# =============================================================================
# 二、个体：携带者视图（面板核心 —— 看得见什么、藏着什么）
# =============================================================================
def carrier_view(geno):
    """
    返回一个位点的列表，每项含：
      locus / 名称 / 基因型 / 可见表型 / 隐蔽的等位基因 / 是否携带者
    「隐蔽」包含两类：
      - 隐性携带：杂合子里被显性盖住的那个等位（如 A+/Ab 藏着 Ab）
      - 上位遮蔽：基因型有效但被别的位点盖住（如 ww 时 A/D/P 全部不可见）
    """
    ph = phenotype(geno)
    # 先判断上位遮蔽是否触发
    w = geno['W']
    ww = (w[0] == 'w' and w[1] == 'w')

    rows = []
    for loc in LOCUS_KEYS:
        spec = LOCUS_SPEC[loc]
        gt = geno[loc]
        a, b = gt
        hidden = []
        visible = True

        # 上位遮蔽
        if loc in EPISTATIC_HIDDEN:
            masker, mask_allele = EPISTATIC_HIDDEN[loc]
            if masker == 'W' and ww:
                visible = False

        # 隐性携带（仅完全显性位点才有意义；dosage 位点两个等位都表达）
        if spec['type'] in ('simple', 'multi'):
            order = spec['dom']
            for al in (a, b):
                if order.index(al) > 0 and al not in hidden:
                    hidden.append(al)

        rows.append({
            'locus': loc,
            'name': LOCUS_NAME.get(loc, loc),
            'geno': '%s / %s' % (_allele_cn(loc, a), _allele_cn(loc, b)),
            'geno_raw': (a, b),
            'pheno': _locus_pheno_cn(loc, gt),
            'hidden': [_allele_cn(loc, h) for h in hidden],
            'hidden_raw': hidden,
            'masked': (not visible),          # 被上位盖住
            'carrier': bool(hidden),          # 携带隐性等位
            'homo_rec': (a == b and spec['dom'].index(a) > 0),   # 隐性纯合（已表达）
        })
    return {'rows': rows, 'pheno': ph, 'epistatic_ww': ww}


LOCUS_NAME = {
    'A': '主毛色', 'D': '稀释', 'W': '白化上位', 'P': '斑纹',
    'L1': '毛长基因1', 'L2': '毛长基因2', 'K': '卷毛',
    'Er': '耳型', 'Ez': '耳大小', 'Tp': '耳尖色', 'In': '内耳色',
    'Tn1': '尾数基因1', 'Tn2': '尾数基因2', 'V': '九尾',
    'Tl': '尾长', 'Tf': '尾毛', 'Tw': '尾尖',
    'Ey': '眼色', 'Ef': '眼形', 'Ht': '异色瞳',
    'G': '发光', 'St': '星纹', 'Ha': '光环', 'Fl': '火焰纹',
}


def hidden_summary(geno):
    """摘要版：这只狐狸藏着哪些「外观上看不出来」的东西（面板顶部高亮用）。"""
    v = carrier_view(geno)
    items = []
    for r in v['rows']:
        if r['masked']:
            items.append({
                'locus': r['locus'], 'kind': '上位遮蔽',
                'text': '%s 基因型 %s 被雪绒白完全盖住' % (r['name'], r['geno']),
                'alleles': r['hidden_raw'],
            })
        elif r['carrier'] and not r['homo_rec']:
            items.append({
                'locus': r['locus'], 'kind': '隐性携带',
                'text': '%s 表现 %s，但携带 %s' % (r['name'], r['pheno'], '、'.join(r['hidden'])),
                'alleles': r['hidden_raw'],
            })
    return items


# =============================================================================
# 三、配对预测：后代性状概率 + 隐性解锁概率
# =============================================================================
def locus_offspring_dist(locus, gt_a, gt_b):
    """单个位点的后代基因型分布（各配子等概率 1/2 × 1/2）。"""
    order = LOCUS_SPEC[locus]['dom']

    def rank(s):
        return order.index(s) if s in order else 99
    out = defaultdict(float)
    for x in gt_a:
        for y in gt_b:
            key = tuple(sorted((x, y), key=rank))
            out[key] += 0.25
    return dict(out)


def predict_litter(geno_a, geno_b, mut_rate=0.0):
    """
    预测一窝后代的性状分布。返回：
      traits: [{key,name,items:[{value,prob}]}]  按概率降序
      unlock: [{trait,value,prob}]                隐性/稀有性状的解锁概率
    算法：对每个性状只枚举它的依赖位点（每位点 ≤4 种后代基因型），联合相乘。
    """
    result = []
    for t in TRAITS:
        loci = t['loci']
        dists = [locus_offspring_dist(l, geno_a[l], geno_b[l]) for l in loci]
        agg = defaultdict(float)
        for combo in product(*[list(d.items()) for d in dists]):
            p = 1.0
            g = {}
            for (gt, pi) in combo:
                p *= pi
            # 组装成完整基因型（未涉及位点任取，只影响被依赖的表型）
            base = {l: geno_a[l] for l in LOCUS_KEYS}
            for l, (gt, _pi) in zip(loci, combo):
                base[l] = gt
            try:
                val = t['pick'](phenotype(base))
            except Exception:
                val = '—'
            agg[val] += p
        items = sorted(({'value': k, 'prob': v} for k, v in agg.items()),
                       key=lambda d: -d['prob'])
        result.append({'key': t['key'], 'name': t['name'], 'items': items})

    # 隐性解锁概率：只挑「非最高概率」的稀有值，且概率 > 0
    unlock = []
    for t in result:
        if not t['items']:
            continue
        top = t['items'][0]
        for it in t['items']:
            if it['value'] == top['value']:
                continue
            if it['prob'] < 0.005:
                continue
            unlock.append({'trait': t['name'], 'value': it['value'],
                           'prob': it['prob']})
    unlock.sort(key=lambda d: -d['prob'])

    if mut_rate > 0:
        for t in result:
            t['items'] = [{'value': it['value'],
                           'prob': it['prob'] * (1 - mut_rate)} for it in t['items']]
            t['items'].append({'value': '突变新性状', 'prob': mut_rate})
    return {'traits': result, 'unlock': unlock}


def predict_target(geno_a, geno_b, trait_key, value):
    """精确算「后代出现某个具体性状值」的概率（如：雪绒白、5 尾）。"""
    t = next((x for x in TRAITS if x['key'] == trait_key), None)
    if t is None:
        return 0.0
    dists = [locus_offspring_dist(l, geno_a[l], geno_b[l]) for l in t['loci']]
    p = 0.0
    for combo in product(*[list(d.items()) for d in dists]):
        base = {l: geno_a[l] for l in LOCUS_KEYS}
        pr = 1.0
        for l, (gt, pi) in zip(t['loci'], combo):
            base[l] = gt
            pr *= pi
        if t['pick'](phenotype(base)) == value:
            p += pr
    return p


# =============================================================================
# 四、种群：隐性等位频率看板（濒危预警）
# =============================================================================
def population_panel(world, ids=None):
    """
    统计每个等位基因在存活种群里的：频率 / 拷贝数 / 携带者数 / 纯合数。
    用于面板的「哪些隐性基因快丢了」——玩家淘汰狐狸前的决策依据。
    """
    ids = list(ids) if ids is not None else list(world.alive_ids)
    if not ids:
        return []
    n = len(ids)
    rows = []
    for loc in LOCUS_KEYS:
        order = LOCUS_SPEC[loc]['dom']
        counts = {a: 0 for a in allele_pool(loc)}
        carriers = {a: 0 for a in allele_pool(loc)}
        homos = {a: 0 for a in allele_pool(loc)}
        for i in ids:
            a, b = world.foxes[i].geno[loc]
            counts[a] += 1
            counts[b] += 1
            for al in set((a, b)):
                carriers[al] += 1
            if a == b:
                homos[a] += 1
        for al in order:
            cnt = counts.get(al, 0)
            rows.append({
                'locus': loc, 'name': LOCUS_NAME.get(loc, loc),
                'allele': al, 'allele_cn': _allele_cn(loc, al),
                'freq': cnt / (2.0 * n),
                'copies': cnt,
                'carriers': carriers.get(al, 0),
                'homo': homos.get(al, 0),
                'dominant': (order.index(al) == 0),
                'recessive': (order.index(al) > 0),
                'endangered': (0 < cnt <= 3),      # 只剩 ≤3 个拷贝
                'lost': (cnt == 0),
            })
    return rows


def endangered_report(world, ids=None, max_copies=3):
    """濒危隐性等位清单：还在，但快没了。淘汰狐狸前先看这个。"""
    rows = population_panel(world, ids)
    return [r for r in rows if 0 < r['copies'] <= max_copies]


def unique_carriers(world, allele_by_locus):
    """
    找「全种群里唯一/唯二携带某等位」的个体。
    allele_by_locus: {locus: allele}，如 {'V':'V'}、{'W':'w'}
    返回 [{id, fox, loci:[...]}]，按携带的稀有等位数量降序。
    """
    out = []
    for i in world.alive_ids:
        f = world.foxes[i]
        hits = []
        for loc, al in allele_by_locus.items():
            if al in f.geno[loc]:
                hits.append(loc)
        if hits:
            out.append({'id': i, 'fox': f, 'loci': hits})
    return out


# =============================================================================
# 五、目标驱动的育种推荐
# =============================================================================
def recommend_for(world, trait_key, value, top=8, min_prob=0.01):
    """
    想培育出某个性状值（如雪绒白 / 5 尾 / 紫瞳），列出最优配对组合。
    排序：后代概率降序；并列时近交系数 F 升序。
    """
    ids = list(world.alive_ids)
    females = [i for i in ids if world.foxes[i].sex == 'F' and world.foxes[i].phase == 'adult']
    males = [i for i in ids if world.foxes[i].sex == 'M' and world.foxes[i].phase == 'adult']
    out = []
    for fi in females:
        for mi in males:
            p = predict_target(world.foxes[fi].geno, world.foxes[mi].geno,
                               trait_key, value)
            if p < min_prob:
                continue
            r = world.kinship(fi, mi)
            out.append({'dam': fi, 'sire': mi, 'prob': p, 'r': r,
                        'F': r,                      # 后代近交系数 = 双亲亲缘系数
                        'risk': '近交' if r >= 0.125 else '安全'})
    out.sort(key=lambda d: (-d['prob'], d['r']))
    return out[:top]


def trait_values():
    """面板下拉框用：每个展示性状有哪些可能取值。"""
    return [{'key': t['key'], 'name': t['name']} for t in TRAITS]
