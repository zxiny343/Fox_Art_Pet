# -*- coding: utf-8 -*-
"""
导出真实种群快照 -> docs/gene-panel-data.js

面板原型要能真跑起来，就得用真实模拟出来的种群，而不是手编的假数据。
存活个体带完整基因型；已死亡/已迁徙个体只保留家谱字段（亲缘系数计算需要，
但不需要它们的基因型，可显著压缩体积）。
"""
import json
import os
import re

import fox_ecosystem_sim as M
import breeding as B

SEED = 20261031
YEARS = 5

w = M.World(dict(M.TUNED_V3_PARAMS), SEED)
while w.t < YEARS * 24 * 24:
    w.step()
    if not w.alive_ids:
        break

alive = list(w.alive_ids)
# 家谱闭包：存活个体 + 其全部祖先
ped_ids = set()
stack = list(alive)
while stack:
    i = stack.pop()
    if i in ped_ids:
        continue
    ped_ids.add(i)
    for p in (w.foxes[i].mother, w.foxes[i].father):
        if p is not None and p in w.foxes:
            stack.append(p)

pedigree = {}
for i in sorted(ped_ids):
    f = w.foxes[i]
    pedigree[str(i)] = {'m': f.mother, 'f': f.father, 'g': f.gen}

foxes = []
for i in sorted(alive):
    f = w.foxes[i]
    foxes.append({
        'id': i, 'sex': f.sex, 'gen': f.gen, 'phase': f.phase,
        'health': round(f.health, 1), 'satiety': round(f.satiety, 1),
        'geno': {l: list(f.geno[l]) for l in M.LOCUS_KEYS},
        'pheno': f.pheno,
        'F': round(w.F_of(i), 4),
        'founder': f.is_founder,
        'source': f.source,
    })

panel = B.population_panel(w)
endangered = B.endangered_report(w, max_copies=3)

# 预计算「目标育种推荐」，减少原型端计算量（同时也用于核对 JS 端结果）
targets = {}
for tk, tv in [('color', '雪绒白'), ('tails', '5 尾'), ('eye', '紫瞳'),
               ('color', '奶油金'), ('pattern', '纯色'), ('hair_len', '4/4 档'),
               ('color', '幽夜紫'), ('hetero', '异色瞳')]:
    rec = B.recommend_for(w, tk, tv, top=6, min_prob=0.0)
    targets['%s|%s' % (tk, tv)] = [
        {'dam': x['dam'], 'sire': x['sire'], 'prob': round(x['prob'], 4),
         'r': round(x['r'], 4)} for x in rec]

data = {
    'meta': {
        'seed': SEED, 'years': YEARS, 'variant': 'v3',
        't': w.t, 'generation': max(f['gen'] for f in foxes),
        'n_alive': len(alive), 'n_pedigree': len(pedigree),
        'births': w.births, 'migrations': w.migrated,
    },
    'loci': {l: M.LOCUS_SPEC[l] for l in M.LOCUS_KEYS},
    'locus_order': M.LOCUS_KEYS,
    'locus_name': B.LOCUS_NAME,
    'allele_cn': B.ALLELE_CN if hasattr(B, 'ALLELE_CN') else None,
    'foxes': foxes,
    'pedigree': pedigree,
    'population': [{
        'locus': r['locus'], 'name': r['name'], 'allele': r['allele'],
        'cn': r['allele_cn'], 'freq': round(r['freq'], 4), 'copies': r['copies'],
        'carriers': r['carriers'], 'homo': r['homo'],
        'endangered': r['endangered'], 'recessive': r['recessive'],
    } for r in panel],
    'endangered': [{
        'locus': r['locus'], 'name': r['name'], 'cn': r['allele_cn'],
        'copies': r['copies'], 'carriers': r['carriers'],
        'holders': [i for i in alive if r['allele'] in w.foxes[i].geno[r['locus']]],
    } for r in endangered],
    'targets': targets,
}

here = os.path.dirname(os.path.abspath(__file__))
docs = os.path.abspath(os.path.join(here, '..', 'docs'))

# 1) 单独的数据文件（便于调试 / 复用）
out = os.path.join(docs, 'gene-panel-data.js')
with open(out, 'w', encoding='utf-8') as fp:
    fp.write('// 自动生成：python sim/export_panel_data.py —— 请勿手改\n')
    fp.write('window.PANEL_DATA = ')
    json.dump(data, fp, ensure_ascii=False, separators=(',', ':'))
    fp.write(';\n')

# 2) 注入原型 HTML，产出自包含单文件（可重复运行：用正则替换 script#pd 内容）
html_path = os.path.join(docs, 'gene-panel-v0.4.html')
payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
with open(html_path, encoding='utf-8') as fp:
    html = fp.read()

pat = re.compile(r'(<script id="pd" type="application/json">)(.*?)(</script>)', re.S)
if not pat.search(html):
    raise SystemExit('模板里找不到 <script id="pd"> 占位块，无法注入')
html = pat.sub(lambda m: m.group(1) + payload + m.group(3), html, count=1)
with open(html_path, 'w', encoding='utf-8') as fp:
    fp.write(html)

print('已导出 %s' % out)
print('已注入 %s（自包含单文件）' % html_path)
print('  存活 %d 只 / 家谱 %d 个 / 世代 %d / 濒危等位 %d 个'
      % (len(alive), len(pedigree), data['meta']['generation'], len(endangered)))
print('  数据 %.1f KB ｜ HTML %.1f KB'
      % (os.path.getsize(out) / 1024, os.path.getsize(html_path) / 1024))
