# -*- coding: utf-8 -*-
"""渲染内核 v1 —— 基因型 / 表型 → PNG 的唯一入口。

S2 层。桌宠、基因面板、批量图鉴、族谱都只调这里，不各自去拼 artmap。

三件事是这一层独有的，artmap 不管：
  1. **缺件降级**：v1.3 有 3 个部件在成品里是坏的（thin / short 尾根 3 万像素缺口、
     ear_large 比 ear_small 还小）。降级表把它们临时换成可用件，并**逐次留痕**，
     v1.4 素材一到，改一个 `enabled=False` 就恢复，不用动调用方。
  2. **磁盘缓存**：同一基因型 + 尺寸只算一次。桌宠每帧都要图，不能每次重跑 12 层合成。
  3. **可复现**：缓存键包含素材版本号，换素材包自动失效，不会拿旧图当新图。

用法
----
    import render_kernel as RK

    img, meta = RK.render(geno=g, size=512)     # 基因型
    img, meta = RK.render(pheno=p, size=256)    # 表型（面板预览用）
    img, meta = RK.render(geno=g, allow_degrade=False)   # 关降级，看原始缺陷

    meta['degraded']  # [{'kind','from','to','reason','until'}]
    meta['holes']     # 尾根缺口像素（需 check_holes=True）

命令行
------
    python render_kernel.py --random 12 --size 512 --out ../docs/render-kernel
    python render_kernel.py --stats
"""
import hashlib
import json
import os
import re
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artmap as AM  # noqa: E402

_PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(_PROJECT, '_cache', 'render')

# 素材版本 = 交付目录名（v1.3 / v1.4 …），用于缓存失效
ART_VER = os.path.basename(os.path.dirname(os.path.dirname(AM.ART_ROOT))) \
    .replace('_art_', '')

SIZES = (1024, 512, 256, 128)

# 尾根缺口判据对「形态变化大」的尾型会误报：
# 卷尾把尾巴卷到身前，母版尾巴原位置自然空出来，那不是破面而是卷尾的正常形状
# （复核图 docs/_probe_curl.png：红色区域落在卷尾内侧的半圆里，视觉上无异常）。
# 这类尾型照常算数值，但不参与「破面」报警。
HOLE_EXEMPT = {'curl'}

# 破面报警阈值（1024 画布）。
# v1.3 真缺陷是 32,043 / 35,743 px（3% 面积，肉眼一眼看出）；
# 长毛/卷毛的母版轮廓比短毛蓬一圈，用它对 tail_normal 这类标准件比对时会
# 残留约 1–3 千 px 的"轮廓差"，那不是破面，实测 tail_fluffy 在 mid 毛上就有 1,414。
# 所以阈值取 5,000，只抓数量级明显的那一类。
HOLE_FAIL = 5000


# ---------------------------------------------------------------------------
# 1. 缺件降级表
# ---------------------------------------------------------------------------
# level: blocker = 成品里有肉眼可见的破面，必须替；
#        visual  = 观感不对（语义反转），替了更合理。
# until:  对应返修单条目。素材包版本 ≥ until 里写的版本时会自动失效
#         （见 _retire_degrade_rules），不需要手动改 enabled。

DEGRADE_RULES = [
    dict(kind='tail', value='thin', to='normal', enabled=True, level='blocker',
         reason='tail_thin 尾根 35,743px 缺口（v1.4 R1）', until='v1.4-R1'),
    dict(kind='tail', value='short', to='normal', enabled=True, level='blocker',
         reason='tail_short 尾根 32,043px 缺口（v1.4 R1）', until='v1.4-R1'),
    dict(kind='ear', value='large', to='round', enabled=True, level='visual',
         reason='ear_large 内容 6,054px，比 ear_small 还小 2.7 倍（v1.4 R3）',
         until='v1.4-R3'),
]


def _art_ver():
    """当前素材包版本号元组，如 (1, 4)。"""
    m = re.search(r'_art_v([\d.]+)', AM.ART_ROOT)
    return tuple(int(x) for x in m.group(1).split('.')) if m else (0,)


def _retire_degrade_rules():
    """素材包已修好就自动停用对应降级，避免"修好了还在替"。

    规则表本身留着当文档（记录曾经为什么替过），是否生效由版本决定。
    """
    ver = _art_ver()
    off = []
    for r in DEGRADE_RULES:
        m = re.match(r'v([\d.]+)-', r['until'])
        if not m:
            continue
        need = tuple(int(x) for x in m.group(1).split('.'))
        if ver >= need:
            if r['enabled']:
                off.append('%s→%s' % (r['value'], r['to']))
            r['enabled'] = False
    return ver, off


ART_VER_NUM, _RETIRED = _retire_degrade_rules()


def _apply_degrade(spec, allow_degrade=True):
    """就地替换 spec 的部件名，返回降级记录列表。"""
    hits = []
    if not allow_degrade:
        return hits
    for r in DEGRADE_RULES:
        if not r['enabled']:
            continue
        if spec.get(r['kind']) != r['value']:
            continue
        spec[r['kind']] = r['to']
        hits.append({'kind': r['kind'], 'from': r['value'], 'to': r['to'],
                     'level': r['level'], 'reason': r['reason'],
                     'until': r['until']})
        spec['notes'].append('降级：%s %s → %s（%s，等 %s）'
                             % (r['kind'], r['value'], r['to'],
                                r['level'], r['until']))
        # trait_* 只用于面板显示，必须跟着改，否则面板说「大耳」而画面是圆耳
        tk = {'tail': 'trait_tail', 'ear': 'trait_ear'}.get(r['kind'])
        if tk:
            spec[tk] = '%s_%s' % (r['kind'], r['to'])
    return hits


# ---------------------------------------------------------------------------
# 2. 缓存
# ---------------------------------------------------------------------------

def _key(geno, pheno, size, allow_degrade, kw):
    payload = {'geno': None, 'pheno': None, 'size': size,
               'degrade': bool(allow_degrade), 'art': ART_VER,
               'kw': {k: v for k, v in sorted(kw.items())}}
    if geno is not None:
        payload['geno'] = {k: list(v) for k, v in sorted(geno.items())}
    if pheno is not None:
        payload['pheno'] = {k: pheno[k] for k in sorted(pheno)}
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                     default=str).encode('utf-8')
    return hashlib.sha1(raw).hexdigest()[:20]


def _cache_paths(key):
    return (os.path.join(CACHE_DIR, key + '.png'),
            os.path.join(CACHE_DIR, key + '.json'))


def clear_cache():
    """清空渲染缓存，返回删除的文件数。"""
    n = 0
    if os.path.isdir(CACHE_DIR):
        for f in os.listdir(CACHE_DIR):
            if f.endswith(('.png', '.json')):
                try:
                    os.remove(os.path.join(CACHE_DIR, f))
                    n += 1
                except OSError:
                    pass
    return n


def cache_stats():
    if not os.path.isdir(CACHE_DIR):
        return {'files': 0, 'mb': 0.0}
    fs = [f for f in os.listdir(CACHE_DIR) if f.endswith('.png')]
    tot = sum(os.path.getsize(os.path.join(CACHE_DIR, f)) for f in fs)
    return {'files': len(fs), 'mb': round(tot / 1048576.0, 2)}


# ---------------------------------------------------------------------------
# 3. 主入口
# ---------------------------------------------------------------------------

def spec_of(geno=None, pheno=None, allow_degrade=True):
    """基因型/表型 → 组装参数（含降级），返回 (spec, meta)。"""
    from fox_ecosystem_sim import phenotype
    if pheno is None:
        if geno is None:
            raise ValueError('geno 或 pheno 必须给一个')
        pheno = phenotype(geno)
    spec = AM.to_art(pheno)
    spec['notes'] = list(spec.get('notes') or [])
    spec['missing'] = list(spec.get('missing') or [])
    degraded = _apply_degrade(spec, allow_degrade)
    meta = {
        'art_ver': ART_VER,
        'degraded': degraded,
        'notes': spec['notes'],
        'missing': spec['missing'],
        'pheno': {k: (bool(v) if isinstance(v, (bool, np.bool_)) else v)
                  for k, v in pheno.items()},
    }
    return spec, meta


def _mark_holes(meta, img, fur, tail_name):
    """补齐 holes 与豁免标记（缓存命中的旧 meta 也要补）。"""
    if 'holes' not in meta:
        meta['holes'] = AM.tail_root_holes(img, fur)
    if 'holes_exempt' not in meta:
        meta['holes_exempt'] = tail_name in HOLE_EXEMPT
        if meta['holes_exempt']:
            meta['holes_note'] = '判据不适用于 %s 形态（非破面）' % tail_name
    return meta


def render(geno=None, pheno=None, size=512, allow_degrade=True,
           use_cache=True, check_holes=False, **kw):
    """基因型 / 表型 → (PIL.Image, meta)。

    size 取 SIZES 之一；给 None 返回 1024 原尺寸。
    kw 透传 artmap._compose：pat_on_tail、pattern_scale、pattern_tint。
    """
    size = size or 1024
    key = _key(geno, pheno, size, allow_degrade, kw)
    png, jsn = _cache_paths(key)

    if use_cache and os.path.isfile(png) and os.path.isfile(jsn):
        try:
            meta = json.load(open(jsn, encoding='utf-8'))
            meta['cache'] = 'hit'
            img = Image.open(png).convert('RGBA')
            if check_holes:
                t = (meta.get('entities') or {}).get('tail', '')
                _mark_holes(meta, img, meta.get('fur', 'short'),
                            t.replace('tail_', '').replace('.png', ''))
            return img, meta
        except (OSError, ValueError):
            pass        # 缓存坏了就当没有

    t0 = time.time()
    spec, meta = spec_of(geno, pheno, allow_degrade)
    img, used = AM._compose(spec, size, **kw)
    meta.update({'entities': used, 'size': size, 'fur': spec['fur'],
                 'cache': 'miss', 'ms': int((time.time() - t0) * 1000),
                 'key': key})
    if check_holes:
        _mark_holes(meta, img, spec['fur'], spec['tail'])

    if use_cache:
        os.makedirs(CACHE_DIR, exist_ok=True)
        img.save(png)
        json.dump(meta, open(jsn, 'w', encoding='utf-8'), ensure_ascii=False)
    return img, meta


def render_to(path, **kw):
    """渲染并存盘，返回 meta。扩展名决定格式。"""
    img, meta = render(**kw)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if path.lower().endswith(('.jpg', '.jpeg')):
        bg = Image.new('RGB', img.size, (255, 255, 255))
        bg.paste(img, (0, 0), img)
        bg.save(path, quality=92)
    else:
        img.save(path)
    meta['path'] = os.path.abspath(path)
    return meta


# ---------------------------------------------------------------------------
# 4. 批量 / 命令行
# ---------------------------------------------------------------------------

def sample_genotypes(n, seed=20261101):
    """从 v0.6 生态里取真实个体（分布真实，不是均匀随机）。"""
    import fox_ecosystem_sim as M
    w = M.World(dict(M.TUNED_V3_PARAMS), seed)
    ids = sorted(w.alive_ids)
    out = []
    for i in range(n):
        out.append(w.foxes[ids[i % len(ids)]].geno)
    return out


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description='渲染内核 v1')
    ap.add_argument('--random', type=int, default=0, help='随机取 N 只真实个体')
    ap.add_argument('--seed', type=int, default=20261101)
    ap.add_argument('--geno', type=str, default=None, help='基因型 JSON 文件')
    ap.add_argument('--size', type=int, default=512, choices=SIZES)
    ap.add_argument('--out', type=str, default=None, help='输出目录或单文件')
    ap.add_argument('--no-degrade', action='store_true')
    ap.add_argument('--no-cache', action='store_true')
    ap.add_argument('--stats', action='store_true', help='打印缓存统计')
    a = ap.parse_args(argv)

    if a.stats:
        print(json.dumps({'cache': cache_stats(), 'art_ver': ART_VER,
                          'cache_dir': CACHE_DIR}, ensure_ascii=False, indent=1))
        print('降级规则：')
        for r in DEGRADE_RULES:
            print('  %-5s %-6s -> %-7s [%s] %s'
                  % (r['kind'], r['value'], r['to'],
                     'on' if r['enabled'] else 'off', r['reason']))
        return

    genos = []
    if a.geno:
        d = json.load(open(a.geno, encoding='utf-8'))
        genos = [d] if isinstance(d, dict) and not isinstance(
            list(d.values())[0], list) else list(d)
        if isinstance(genos[0], dict) and 'geno' in genos[0]:
            genos = [g['geno'] for g in genos]
    elif a.random:
        genos = sample_genotypes(a.random, a.seed)
    else:
        ap.error('需要 --random N 或 --geno file.json')

    outdir = a.out or os.path.join(_PROJECT, 'docs', 'render-kernel')
    t0 = time.time()
    bad = 0
    for i, g in enumerate(genos):
        meta = render_to(os.path.join(outdir, 'fox-%03d.png' % i),
                         geno=g, size=a.size,
                         allow_degrade=not a.no_degrade,
                         use_cache=not a.no_cache, check_holes=True)
        flag = ''
        if meta.get('holes', 0) >= HOLE_FAIL:
            if meta.get('holes_exempt'):
                flag = '  (缺口 %d，判据不适用)' % meta['holes']
            else:
                flag = '  <-破面 %d' % meta['holes']
                bad += 1
        if meta['degraded']:
            flag += '  [降级 %d]' % len(meta['degraded'])
        print('%-14s %-9s %-6s holes=%-6d %dms%s'
              % (os.path.basename(meta['path']),
                 meta['pheno'].get('color'), meta['entities'].get('tail', ''),
                 meta.get('holes', -1), meta.get('ms', 0), flag))
    print('\n%d 只 / %.1fs / 缓存 %s / 破面 %d 只'
          % (len(genos), time.time() - t0, cache_stats(), bad))


if __name__ == '__main__':
    main()
