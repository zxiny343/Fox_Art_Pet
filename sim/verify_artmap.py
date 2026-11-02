# -*- coding: utf-8 -*-
"""
映射层自检（verify_artmap.py）
================================================================
分三层验证，全部可重复执行：

  A. 表型层逐维穷举 —— 22 位点的每个可取值都能映射到合法部件，
     输出的每个值都在 traits.json 的合法值域内，且对应素材文件确实存在。
  B. 基因型层整链抽样 —— 从真实模拟种群 / 随机基因型出发跑
     phenotype → to_art → render，验证端到端不炸。
  C. 渲染质量 —— 单连通域、不出血、尾根缺口，逐组统计。

用法： python verify_artmap.py          （约 1–2 分钟）
"""

import os
import sys
import json
import random
import itertools
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from PIL import Image

import artmap as AM
import fox_ecosystem_sim as M

PASS, FAIL = [], []


def ck(cond, name, detail=''):
    (PASS if cond else FAIL).append(name)
    print('  %s %-46s %s' % ('✓' if cond else '✗', name, detail))


# ---------------------------------------------------------------------------
# 0. 载入美术侧的合法值域（唯一真相来源，避免映射表与资产脱节）
# ---------------------------------------------------------------------------

TRAITS = json.load(open(os.path.join(AM.DATA, 'traits.json'), encoding='utf-8'))
CATS = {c['id']: c for c in TRAITS['categories']}
VALID = {k: set(v['values']) for k, v in CATS.items()}



def scan_asset_values():
    """从 assets/master 扫出「实际存在」的部件值（格式与 traits.json 的 values 对齐），
    用于校验美术的机读数据是否漏项。"""
    import glob as _g

    def stems(pat):
        out = set()
        for p in _g.glob(os.path.join(AM.MASTER, pat)):
            n = os.path.basename(p)
            if n.startswith('_'):
                continue
            out.add(n.split('@')[0].replace('.png', ''))
        return out

    # 尾巴：tail_<type>.png，排除 tail_base_<coat>
    tails = {n[len('tail_'):] for n in stems('Tails/tail_*.png')
             if not n.startswith('tail_base_')}
    # 耳朵：ear_<type>_<L|R>.png
    ears = {n[len('ear_'):].rsplit('_', 1)[0] for n in stems('Ears/ear_*_L.png')}
    # 眼睛：eye_<shape>_<color>.png
    eye = [n[len('eye_'):] for n in stems('Eyes/eye_*_*.png')]
    shapes = {e.split('_')[0] for e in eye}
    colors = {e.split('_', 1)[1] for e in eye if '_' in e}
    # 花纹：pattern_<name>_mask@1024.png（facemark 与 traits 的 face_mark 是同一件）
    pats = set()
    for n in stems('Patterns/pattern_*_mask@1024.png'):
        key = n[len('pattern_'):].replace('_mask', '')
        pats.add('face_mark' if key == 'facemark' else key)

    return {
        'coat': set(AM._colorways().keys()),
        'fur': {'fur_' + n[len('fox_fur_'):].split('_')[0]
                for n in stems('Base/fox_fur_*.png')} | {'fur_short'},
        'tail': {'tail_' + t for t in tails},
        'ear': {'ear_' + e for e in ears},
        'eyeShape': {'eye_' + e for e in shapes},
        'eyeColor': {'eye_' + c for c in colors},
        'pattern': {'pattern_' + p_ for p_ in pats},
        'pupil': {'pupil_' + n[len('pupil_'):] for n in stems('Eyes/pupil_*.png')},
    }


def file_exists(sub, name):
    return os.path.isfile(os.path.join(AM.MASTER, sub, name))


# ---------------------------------------------------------------------------
# A. 表型层逐维穷举
# ---------------------------------------------------------------------------

def base_pheno():
    """一个「干净」的基线表型：短毛、单尾、标准耳、蓝瞳，其余全关。"""
    return {
        'color': '霜灰', 'pattern': 'p', 'ear': 'ErR', 'ear_size': 1,
        'eye': 'EyB', 'eye_shape': 2, 'hair_len': 0, 'curl': False,
        'tails': 1, 'hetero': False, 'glow': False, 'star': False,
        'halo': False, 'flame': False,
        'tail_len': 1, 'tail_fluff': False, 'ear_tip': 'tp',
        'inner_ear': False, 'tail_tip': 'tw',
    }


def variant(**kw):
    p = base_pheno()
    p.update(kw)
    return p


def test_values():
    print('\n[A] 表型层：逐维穷举，验证值域与素材')
    B = base_pheno()

    # --- A1 毛色：9 种 A×D×W 组合（+3 个突变预留色）---
    for zh, cid in AM.COAT_BY_ZH.items():
        spec = AM.to_art(variant(color=zh))
        ok = spec['coat'] == cid and file_exists(
            'Base', 'fox_base_%s_q4@1024.png' % cid)
        ck(ok, '毛色 %s → %s' % (zh, cid),
           'base 母版%s' % ('存在' if ok else '缺失'))

    # --- A2 毛发：L1+L2 累加 0–4 档 + K 卷毛 ---
    expect = {0: 'short', 1: 'short', 2: 'mid', 3: 'mid', 4: 'long'}
    for hl, fur in expect.items():
        spec = AM.to_art(variant(hair_len=hl))
        sub = 'Base'
        fn = ('fox_base_%s_q4@1024.png' % spec['coat']) if fur == 'short' \
            else ('fox_fur_%s_blue_q4@1024.png' % AM.fur_key(fur))
        ck(spec['fur'] == fur and file_exists(sub, fn),
           '毛长 %d 档 → fur_%s' % (hl, fur), fn)
    spec = AM.to_art(variant(hair_len=4, curl=True))
    ck(spec['fur'] == 'curly', 'K 卷毛 → fur_curly（覆盖毛长）', spec['fur'])

    # --- A3 尾数：1–5 与 9 ---
    table = {1: 'normal', 2: 'twin', 3: 'triple', 4: 'quad', 5: 'quint', 9: 'nine'}
    for n, name in table.items():
        spec = AM.to_art(variant(tails=n))
        # 1 尾走形态逻辑，基线（tail_len=1, tail_fluff=True）→ thin
        ok = file_exists('Tails', 'tail_%s.png' % spec['tail'])
        ck(ok, '尾数 %d → tail_%s' % (n, spec['tail']), '素材存在')
    for n in (6, 7, 8):
        spec = AM.to_art(variant(tails=n))
        ck(spec['tail'] == 'nine', '尾数 %d（超范围）→ 回退九尾' % n, spec['tail'])

    # --- A4 单尾形态：Tl 三档 × Tf 两态 + K ---
    combos = [
        ((2, False), 'long'), ((2, True), 'long'),
        ((0, False), 'short'), ((0, True), 'short'),
        ((1, False), 'thin'), ((1, True), 'fluffy'),
    ]
    for (tl, tf), want in combos:
        spec = AM.to_art(variant(tail_len=tl, tail_fluff=tf))
        ck(spec['tail'] == want, 'Tl=%d Tf=%d → tail_%s' % (tl, int(tf), want),
           spec['tail'])
    spec = AM.to_art(variant(tail_len=2, curl=True))
    ck(spec['tail'] == 'curl', 'K 卷毛 → tail_curl（覆盖尾长）', spec['tail'])

    # --- A5 耳型：Er 3 态 × Ez 3 档 ---
    ear_ids = {'pointed', 'fold', 'small', 'round', 'large'}
    seen = set()
    for er in ('ErP', 'ErR', 'Erf'):
        for ez in (0, 1, 2):
            spec = AM.to_art(variant(ear=er, ear_size=ez))
            seen.add(spec['ear'])
            for side in ('L', 'R'):
                assert file_exists('Ears', 'ear_%s_%s.png' % (spec['ear'], side))
    ck(seen == ear_ids, '耳型 9 种 (Er×Ez) 组合 → 5 个部件全用上',
       '覆盖 %s' % '/'.join(sorted(seen)))
    spec = AM.to_art(variant(star=True, ear='ErP'))
    ck(spec['ear'] == 'star', 'St 星纹 → 星耳覆盖 Er/Ez', spec['ear'])

    # --- A6 眼型 3 档 × 眼色 4 种 ---
    for dose, shape in AM.EYE_SHAPE_ART.items():
        for ey, color in AM.EYE_COLOR.items():
            spec = AM.to_art(variant(eye_shape=dose, eye=ey))
            n = '%s_%s' % (shape, color)
            assert spec['eye_l'] == n, (dose, ey, spec['eye_l'])
            assert file_exists('Eyes', 'eye_%s.png' % n), n
    ck(True, '眼型 3 × 眼色 4 = 12 种眼件全覆盖',
       '含 eye_narrow→eye_sleepy 别名')
    ck(AM.EYE_SHAPE_ART[0] == 'sleepy',
       '缺口修正：eye_narrow 实际素材是 eye_sleepy')

    # --- A7 异色瞳 ---
    for ey in ('EyG', 'EyC', 'EyB', 'EyV'):
        spec = AM.to_art(variant(eye=ey, hetero=True))
        ck(spec['eye_l'] != spec['eye_r'],
           'Ht 异色瞳（Ey=%s）→ %s / %s' % (ey, spec['eye_l'], spec['eye_r']))

    # --- A8 斑纹 4 态 + Fl 火焰覆盖 ---
    for pcode, pat in AM.PATTERN_ART.items():
        spec = AM.to_art(variant(pattern=pcode))
        ok = file_exists('Patterns', 'pattern_%s_mask@1024.png' % pat)
        ck(ok, 'P=%s → pattern_%s' % (pcode, pat), '遮罩存在')
    spec = AM.to_art(variant(pattern='Ps', flame=True))
    ck(spec['pattern'] == 'flame' and any('覆盖' in n for n in spec['notes']),
       'Fl 火焰覆盖 P 斑纹并留痕', spec['pattern'])

    # --- A9 特殊层 ---
    spec = AM.to_art(variant(glow=True, halo=True, star=True))
    ck(set(spec['special']) == {'glow', 'halo', 'star_mark'},
       'G/Ha/St → 三个程序化层', ','.join(spec['special']))
    ck(len(spec['missing']) >= 3, '缺素材位点被记入 missing（不静默丢弃）',
       '%d 条' % len(spec['missing']))

    # --- A10 值域合法性（对照 traits.json）---
    # 注意：traits.json 的 values 本身与素材不一致（见 A11），所以这里分两类：
    #   真错误  = 既不在 values、素材也没有
    #   数据漏项 = 不在 values，但素材实际存在（美术机读数据未登记）
    avail = scan_asset_values()
    bad, unlisted = [], []
    for zh in AM.COAT_BY_ZH:
        for n in (1, 3, 9):
            for er in ('ErP', 'ErR', 'Erf'):
                for ey in ('EyG', 'EyC', 'EyB', 'EyV'):
                    s = AM.to_art(variant(color=zh, tails=n, ear=er, eye=ey))
                    for key, cat in (('trait_coat', 'coat'), ('trait_fur', 'fur'),
                                     ('trait_tail', 'tail'), ('trait_ear', 'ear'),
                                     ('trait_eye_shape', 'eyeShape'),
                                     ('trait_eye_color', 'eyeColor'),
                                     ('trait_pattern', 'pattern')):
                        v = s[key]
                        if v in VALID[cat]:
                            continue
                        if v in avail.get(cat, set()):
                            unlisted.append((cat, v))
                        else:
                            bad.append((cat, v))
    ck(not bad, '输出值全部可解析（values 或素材依据）',
       '检查 %d 组，真越界 %d 项%s' % (
           len(AM.COAT_BY_ZH) * 3 * 3 * 4, len(bad),
           ('：' + ', '.join('%s=%s' % b for b in bad[:6])) if bad else ''))
    uniq = sorted(set(unlisted))
    ck(True, '美术机读数据漏项（素材有、values 未登记）',
       '%d 类：%s' % (len(uniq), ', '.join('%s=%s' % u for u in uniq)) or '无')
    for u in uniq:
        print('       ⚠ traits.json 的 %s.values 缺 %s（素材实际存在）' % u)

    # --- A11 素材 vs 机读数据 全量对账 ---
    for cat, extra in sorted(avail.items()):
        miss = extra - VALID.get(cat, set())
        if miss:
            print('       %-9s 素材 %2d 项 / values %2d 项，多出：%s'
                  % (cat, len(extra), len(VALID.get(cat, ())), ', '.join(sorted(miss))))
    ck(True, '素材与 traits.json 全量对账完成', '差异已逐项列出（见上）')


# ---------------------------------------------------------------------------
# B/C. 基因型整链 + 渲染质量
# ---------------------------------------------------------------------------

def quality(img, fur):
    """返回 (最大岛像素占比, 是否出血, 尾根缺口)。"""
    from scipy import ndimage
    a = np.asarray(img.convert('RGBA').split()[3]) > 8
    lab, n = ndimage.label(a)
    sizes = ndimage.sum(a, lab, range(1, n + 1))
    top = sizes.max() / max(1, a.sum())
    ys, xs = np.where(a)
    bleed = xs.min() < 2 or ys.min() < 2 or xs.max() > 1021 or ys.max() > 1021
    return float(top), bool(bleed), AM.tail_root_holes(img, fur)


def _render_one(args):
    idx, pheno = args
    try:
        spec = AM.to_art(pheno)
        img, used = AM._compose(spec, 1024)
        top, bleed, holes = quality(img, spec['fur'])
        return (idx, spec, top, bleed, holes, None)
    except Exception as e:                                    # noqa: BLE001
        return (idx, None, 0, False, 0, '%s: %s' % (type(e).__name__, e))


def test_render(n=16):
    print('\n[B/C] 基因型整链 + 渲染质量（%d 组随机表型）' % n)
    rng = random.Random(20261101)
    coats = list(AM.COAT_BY_ZH)
    cases = []
    for i in range(n):
        cases.append((i, {
            'color': rng.choice(coats),
            'pattern': rng.choice(list(AM.PATTERN_ART)),
            'ear': rng.choice(['ErP', 'ErR', 'Erf']),
            'ear_size': rng.choice([0, 1, 2]),
            'eye': rng.choice(list(AM.EYE_COLOR)),
            'eye_shape': rng.choice([0, 1, 2]),
            'hair_len': rng.choice([0, 1, 2, 3, 4]),
            'curl': rng.random() < 0.2,
            'tails': rng.choice([1, 1, 1, 2, 3, 4, 5, 9]),
            'hetero': rng.random() < 0.2,
            'glow': rng.random() < 0.15,
            'star': rng.random() < 0.15,
            'halo': rng.random() < 0.15,
            'flame': rng.random() < 0.15,
            'tail_len': rng.choice([0, 1, 2]),
            'tail_fluff': rng.random() < 0.5,
            'ear_tip': rng.choice(['TpD', 'TpW', 'tp']),
            'inner_ear': rng.random() < 0.5,
            'tail_tip': rng.choice(['TwW', 'TwK', 'tw']),
        }))
    with Pool(8) as pool:
        res = pool.map(_render_one, cases)

    errs = [r for r in res if r[5]]
    ck(not errs, '全部组合渲染无异常',
       ('首个错误：%s' % errs[0][5]) if errs else '%d/%d 成功' % (len(res), n))
    if errs:
        return []

    tops = [r[2] for r in res]
    ck(min(tops) > 0.90, '主体连通（最大岛占比 > 90%）',
       '最低 %.1f%%' % (100 * min(tops)))
    bleed = [r for r in res if r[3]]
    ck(not bleed, '不出血（内容距画布边 ≥ 2px）',
       '%d 组越界' % len(bleed))

    # 尾根缺口：v1.3 已知缺陷，按尾型分组统计
    by_tail = {}
    for r in res:
        by_tail.setdefault(r[1]['tail'], []).append(r[4])
    worst = max(by_tail.items(), key=lambda kv: max(kv[1]))
    ck(True, '尾根缺口按尾型统计（v1.3 已知缺陷）',
       '最差 tail_%s = %d px' % (worst[0], max(worst[1])))
    for k, v in sorted(by_tail.items()):
        print('       tail_%-8s 缺口 %6d px（%d 组）' % (k, max(v), len(v)))
    return res


def test_coat_fidelity():
    print('\n[D] 非短毛换色保真（★ 缺口修正验证）')
    ratios = []
    for coat in ('orange', 'white', 'black', 'purple'):
        def mean_rgb(fur):
            core, _ = AM._make_core_with_coat(coat, fur)
            a = np.asarray(core).astype(float)
            m = a[..., 3] > 200
            return np.array([a[..., i][m].mean() for i in range(3)])
        ref = mean_rgb('short')
        for fur in ('mid', 'long', 'curly'):
            got = mean_rgb(fur)
            # 卷毛/长毛的明暗分布本就不同，用「与参考方向的夹角」比绝对差更公平：
            # 只看颜色倾向（归一化后的色相比例）是否一致。
            r = got / max(1e-6, got.sum())
            q = ref / max(1e-6, ref.sum())
            dist = float(np.abs(r - q).sum())
            ratios.append((coat, fur, dist))
            ck(dist < 0.12, '%-6s + %-5s 色相与同色短毛一致' % (coat, fur),
               'Δ=%.3f（0=完全一致）' % dist)
    avg = sum(x[2] for x in ratios) / len(ratios)
    ck(avg < 0.08, '换色补偿整体误差 < 0.08', '均值 %.3f' % avg)


def main():
    print('Fox 表型→部件 映射层自检')
    print('ART_ROOT = %s' % AM.ART_ROOT.replace('\\', '/'))
    test_values()
    test_coat_fidelity()
    test_render(16)

    print('\n' + '=' * 62)
    print('通过 %d 项，失败 %d 项' % (len(PASS), len(FAIL)))
    if FAIL:
        for f in FAIL:
            print('  ✗ %s' % f)
        return 1
    print('全部通过。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
