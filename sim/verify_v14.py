# -*- coding: utf-8 -*-
"""
v1.4 素材包独立验收（2026-11-02）
================================================================
不复用美术侧的 run_regress_v14.py 判据（那是他们自查用的），
这里按返修单第 1–7 节各自的验收条款独立实现一遍，只对覆盖率这类
需要对齐的口径沿用他们文档里写明的定义（TRUNK = master_a & ~FACE_BIG & x<700）。

跑法：  python sim/verify_v14.py
"""
import io
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artmap as AM                                     # noqa: E402
import render_kernel as RK                              # noqa: E402
from fox_ecosystem_sim import phenotype as PH           # noqa: E402

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V14 = os.path.join(PROJ, '_art_v1.4', 'delivery', 'Fox_Art')
V13 = os.path.join(PROJ, '_art_v1.3', 'delivery', 'Fox_Art')
M14 = os.path.join(V14, 'assets', 'master')
M13 = os.path.join(V13, 'assets', 'master')
DOCS = os.path.join(PROJ, 'docs')

PASS = FAIL = 0
LINES = []


def ck(ok, title, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
    else:
        FAIL += 1
    LINES.append('  %s %-46s %s' % ('✓' if ok else '✗', title, detail))
    return ok


def sec(name):
    LINES.append('')
    LINES.append('[%s]' % name)


def alpha_gt8(path):
    return np.asarray(Image.open(path).convert('RGBA').split()[3]) > 8


def content_stats(path):
    """返回 (bbox, 像素量)。"""
    a = alpha_gt8(path)
    ys, xs = np.where(a)
    if len(xs) == 0:
        return None, 0
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1,
            int(ys.max()) + 1), int(a.sum())


# ---------------------------------------------------------------------------
# A · R1 尾根缺口：走产品自己的渲染路径（artmap._compose）
# ---------------------------------------------------------------------------
def tail_geno(kind, coat='blue', fur='short'):
    """构造指定单尾形态 + 指定毛质/毛色的基因型。"""
    g = dict(RK.sample_genotypes(1)[0])
    one = {'Tn1': ('t', 't'), 'Tn2': ('t', 't'), 'V': ('v', 'v')}
    ll = {'short': ('l', 'l'), 'mid': ('L', 'l'), 'long': ('L', 'L')}[fur]
    g.update(one)
    g['L1'], g['L2'] = ll, ll
    g['K'] = ('k', 'k') if fur != 'curly' else ('K', 'K')
    table = {
        'thin':   {'K': ('k', 'k'), 'Tl': ('Tl', 'tl'), 'Tf': ('tf', 'tf')},
        'short':  {'K': ('k', 'k'), 'Tl': ('tl', 'tl'), 'Tf': ('tf', 'tf')},
        'normal': {'K': ('k', 'k'), 'Tl': ('Tl', 'tl'), 'Tf': ('Tf', 'Tf')},
        'curl':   {'K': ('K', 'K')},
    }
    g.update(table[kind])
    # 毛色：直接改表型不现实，用 A 位点最容易的方式——渲染时覆写 coat
    return g


def test_r1():
    sec('A · R1 尾根缺口（产品渲染路径 artmap._compose，短毛母版）')
    worst = {}
    for kind in ('short', 'thin', 'normal'):
        for coat in ('blue', 'black', 'orange', 'white'):
            g = tail_geno(kind, fur='short')
            p = PH(g)
            spec = AM.to_art(p)
            spec['coat'] = coat                     # 强制毛色，隔离遗传随机性
            spec['fur'] = 'short'
            if kind == 'normal':
                spec['tail'] = 'normal'   # tail_normal 没有基因出口，只能直接指定
            if spec['tail'] != kind:
                ck(False, 'R1 %s 构造失败' % kind, spec['tail'])
                continue
            img, _ = AM._compose(spec, 1024)
            hole = AM.tail_root_holes(img, 'short')
            worst.setdefault(kind, []).append((coat, hole))
    for kind, rows in worst.items():
        mx = max(h for _, h in rows)
        lim = 500 if kind in ('short', 'thin') else 3000
        ck(mx < lim, 'R1 %-6s 缺口 < %d（4 毛色最大）' % (kind, lim),
           '最大 %d px  %s' % (mx, ' '.join('%s=%d' % r for r in rows)))


def test_r1_shape():
    sec('B · R1 形态保持（v1.3 ↔ v1.4 尾件本体，修法只许动根部）')
    for name in ('tail_short', 'tail_thin'):
        b13, p13 = content_stats(os.path.join(M13, 'Tails', name + '.png'))
        b14, p14 = content_stats(os.path.join(M14, 'Tails', name + '.png'))
        if b13 is None:
            ck(False, '%s v1.3 读不到' % name)
            continue
        # 修法本身就是「往窗口里填绒毛」，像素必然大增、bbox 必然外扩，
        # 所以这项只记录不判失败；形态是否保住由下方 alpha 质量项负责。
        grow = 100.0 * (p14 - p13) / p13
        LINES.append('  ·  %-10s v1.3 %s/%6d px → v1.4 %s/%6d px（%+6.1f%%）'
                     % (name, b13, p13, b14, p14, grow))
        LINES.append('       修法=往尾巴窗口填根部绒毛，增量属预期；真正要看的是下面第 I 段')


# ---------------------------------------------------------------------------
# C · R3 耳朵三件
# ---------------------------------------------------------------------------
def test_r3():
    sec('C · R3 耳型三件体量单调性（返修单：比值∈[1.25,1.6]、topY 差 ≤6）')
    st = {}
    for n in ('small', 'round', 'large'):
        p = os.path.join(M14, 'Ears', 'ear_%s_L.png' % n)
        b, px = content_stats(p)
        st[n] = (b, px)
        print('    ear_%-6s bbox=%s  px=%d  topY=%d' % (n, b, px, b[1]))
    px = [st[k][1] for k in ('small', 'round', 'large')]
    tops = [st[k][0][1] for k in ('small', 'round', 'large')]
    mono = px[0] < px[1] < px[2]
    ratio = px[2] / float(px[1])
    dt = max(tops) - min(tops)
    ck(mono, 'R3 内容像素单调递增', str(px))
    ck(1.25 <= ratio <= 1.6, 'R3 large/round ∈ [1.25, 1.6]', '%.3f' % ratio)
    ck(dt <= 6, 'R3 三件 topY 差 ≤ 6', '%d px  %s' % (dt, tops))
    # 左右都要改
    ok = all(os.path.isfile(os.path.join(M14, 'Ears', 'ear_large_%s.png' % s))
             for s in ('L', 'R'))
    ck(ok, 'R3 ear_large 左右两件都已重绘')


# ---------------------------------------------------------------------------
# D · R4 花纹躯干覆盖率（口径与他们文档一致，实现独立）
# ---------------------------------------------------------------------------
def test_r4():
    sec('D · R4 花纹躯干覆盖率（TRUNK = master_a & ~FACE_BIG & x<700）')
    base = np.asarray(Image.open(
        os.path.join(M14, 'Base', 'fox_base_blue_q4@1024.png')
    ).convert('RGBA').split()[3]) > 8
    yy, xx = np.mgrid[0:1024, 0:1024]
    face = (((xx - 700) / 195.0) ** 2 + ((yy - 470) / 165.0) ** 2 <= 1.0)
    trunk = base & (~face) & (xx < 700)
    lim = {'stripes': 0.40, 'tabby': 0.40, 'spots': 0.25}
    for p in ('stripes', 'tabby', 'spots'):
        f = os.path.join(M14, 'Patterns', 'pattern_%s_mask@1024.png' % p)
        m = alpha_gt8(f)
        cov = float((m & trunk).sum()) / float(trunk.sum())
        ck(cov >= lim[p], 'R4 %-8s 躯干覆盖 ≥ %.0f%%' % (p, lim[p] * 100),
           '%.1f%%' % (cov * 100))


# ---------------------------------------------------------------------------
# E · R5 special 三件
# ---------------------------------------------------------------------------
def test_r5():
    sec('E · R5 三个 special 层（声明要有文件，且规格可用）')
    sp = os.path.join(M14, 'Special')
    for n in ('glow', 'aura', 'star_mark'):
        f = os.path.join(sp, 'special_%s@1024.png' % n)
        ck(os.path.isfile(f), 'R5 special_%s 文件存在' % n)
    if not os.path.isdir(sp):
        return
    base = np.asarray(Image.open(
        os.path.join(M14, 'Base', 'fox_base_blue_q4@1024.png')
    ).convert('RGBA').split()[3]) > 8

    # glow：外沿必须衰减到 0（不能是一块硬边方块）
    a = np.asarray(Image.open(
        os.path.join(sp, 'special_glow@1024.png')).convert('RGBA'))
    far = nd_distance(base) > 120
    outer = float(a[..., 3][far].mean()) / 255.0
    inner = float(a[..., 3][base].mean()) / 255.0
    ck(outer < 0.01 and inner > 0.01, 'R5 glow 外沿衰减到 0、体内有量',
       '外沿 %.4f / 体内 %.3f' % (outer, inner))

    # aura：环心 (640,128)、水平直径 ~300、宽度 14–20
    a = np.asarray(Image.open(
        os.path.join(sp, 'special_aura@1024.png')).convert('RGBA'))
    m = a[..., 3] > 8
    ys, xs = np.where(m)
    if len(xs):
        w = int(xs.max() - xs.min())
        cx = float(xs.mean())
        cy = float(ys[:len(xs)][np.argmin(np.abs(ys - 128))]) if len(ys) else -1
        ck(280 <= w <= 330, 'R5 aura 水平直径 ~300', '%d px' % w)
        ck(abs(cx - 640) <= 20, 'R5 aura 环心 x ≈ 640', '%.0f' % cx)
        ck(abs(cy - 128) <= 40, 'R5 aura 环心 y ≈ 128', '%.0f' % cy)

    # star_mark：纯 alpha 遮罩、落在身体内、3 个连通域
    a = np.asarray(Image.open(
        os.path.join(sp, 'special_star_mark@1024.png')).convert('RGBA'))
    m = a[..., 3] > 8
    inside = float((m & base).sum()) / max(int(m.sum()), 1)
    ck(inside > 0.99, 'R5 star_mark 完全落在身体内', '%.1f%%' % (inside * 100))
    ck(n_components(m) == 3, 'R5 star_mark 3 颗星（独立连通域）',
       '%d 个' % n_components(m))


def nd_distance(mask):
    """简易欧氏距离变换（避免依赖 scipy；mask 为 bool）。"""
    from scipy import ndimage
    return ndimage.distance_transform_edt(~mask)


def n_components(mask):
    from scipy import ndimage
    lab, n = ndimage.label(mask)
    return n


# ---------------------------------------------------------------------------
# F · R6 traits.json values 全量对账（独立实现）
# ---------------------------------------------------------------------------
def _files_of(root_master):
    out = set()
    for d, _, fs in os.walk(root_master):
        for f in fs:
            if f.endswith('.png'):
                out.add(f[:-4].split('@')[0])
    return out


def test_r6():
    """R6：values 与磁盘对账。权威映射在 01_Data/_meta.json 的 fileMap / exemptions。"""
    sec('F · R6 traits.json values × 磁盘文件全量对账')
    tr = json.load(io.open(os.path.join(V14, '01_Data', 'traits.json'),
                           encoding='utf-8'))
    meta = json.load(io.open(os.path.join(V14, '01_Data', '_meta.json'),
                             encoding='utf-8'))
    vfc = meta.get('valueFileCheck', {})
    fmap = vfc.get('fileMap', {})
    exem = vfc.get('exemptions', {})
    cats = tr.get('categories', [])

    # 1) fileMap 声明的文件必须真实存在
    miss_file = []
    for vid, paths in fmap.items():
        for rel in paths:
            if not os.path.isfile(os.path.join(V14, rel)):
                miss_file.append('%s → %s' % (vid, rel))
    ck(not miss_file, 'R6 fileMap 声明的文件都存在',
       '%d 个 id / %d 个路径，缺 %d' % (len(fmap), sum(len(v) for v in fmap.values()),
                                        len(miss_file)))
    for m in miss_file[:6]:
        LINES.append('     ' + m)

    # 2) 每个 value id 必须有 fileMap 条目或 exemptions 声明
    total = orphan = 0
    for body in cats:
        for v in body.get('values', []):
            total += 1
            if v in fmap or v in exem:
                continue
            orphan += 1
            LINES.append('     无归属: %s.%s' % (body.get('id'), v))
    ck(orphan == 0, 'R6 每个 value id 都有文件映射或显式豁免',
       '%d 个 id，无归属 %d 个' % (total, orphan))

    # 3) exemptions 的 composedOf 引用的文件也必须存在
    bad = []
    for vid, info in exem.items():
        for rel in (info.get('composedOf') or []):
            if not os.path.isfile(os.path.join(V14, rel)):
                bad.append('%s → %s' % (vid, rel))
        if not info.get('procedural') and not info.get('composedOf'):
            bad.append('%s 既非 procedural 也无 composedOf' % vid)
    ck(not bad, 'R6 豁免项声明自洽（composedOf 引用的文件存在）',
       '%d 个豁免，问题 %d 个' % (len(exem), len(bad)))
    for b in bad[:6]:
        LINES.append('     ' + b)

    # 4) 本次点名要修的四项
    for v in ('mist_purple', 'haze_blue', 'eye_cyan', 'eye_sleepy'):
        paths = fmap.get(v) or []
        ok = bool(paths) and all(os.path.isfile(os.path.join(V14, r)) for r in paths)
        ck(ok, 'R6 新增/改名 %s 有实体文件' % v,
           '%s' % (', '.join(os.path.basename(r) for r in paths) if paths else '无映射'))
    ck('eye_narrow' not in [v for b in cats if b.get('id') == 'eyeShape'
                            for v in b.get('values', [])],
       'R6 eye_narrow 已从 values 移除（实际文件是 eye_sleepy）')


# ---------------------------------------------------------------------------
# G · R7 ORIG_EAR_H
# ---------------------------------------------------------------------------
def test_r7():
    sec('G · R7 run_assemble.py 的 ORIG_EAR_H')
    p = os.path.join(V14, 'tools', 'run_assemble.py')
    src = io.open(p, encoding='utf-8').read()
    ck('ORIG_EAR_H' in src and
       ('ORIG_EAR_H =' in src or 'ORIG_EAR_H=' in src),
       'R7 ORIG_EAR_H 已定义（不再是未定义变量）')


# ---------------------------------------------------------------------------
# H · 种群批量渲染 + 破面
# ---------------------------------------------------------------------------
def test_population():
    sec('H · 真实种群 36 只批量渲染（含破面与降级统计）')
    RK.clear_cache()
    bad = []
    deg = 0
    worst = 0
    for g in RK.sample_genotypes(36):
        img, meta = RK.render(geno=g, size=512, check_holes=True)
        h = meta.get('holes', 0)
        worst = max(worst, h)
        if meta.get('degraded'):
            deg += 1
        if h >= RK.HOLE_FAIL and not meta.get('holes_exempt'):
            bad.append((meta.get('tail'), h))
    ck(not bad, 'H 36 只无破面', '最差缺口 %d px；破面 %d 只' % (worst, len(bad)))
    LINES.append('     触发降级 %d 只（v1.4 修好后应为 0）' % deg)


def test_r1_quality():
    """观察项：缺口判据只看 alpha<8，填了但很淡也会判通过。

    桌宠是透明背景，所以另看「新增绒毛区」的最终实心度与纹理。
    参照系是 tail_normal 在同一窗口的表现。
    """
    sec('I · R1 填充质量（观察项，修单未要求，但决定桌宠观感）')
    ref = None
    for kind in ('normal', 'short', 'thin'):
        a13 = np.asarray(Image.open(os.path.join(
            M13, 'Tails', 'tail_%s.png' % kind)).convert('RGBA'))[..., 3]
        a14 = np.asarray(Image.open(os.path.join(
            M14, 'Tails', 'tail_%s.png' % kind)).convert('RGBA'))[..., 3]
        base = AM.body_mask('short')
        if kind == 'normal':
            s13 = np.asarray(Image.open(os.path.join(
                M13, 'Tails', 'tail_short.png')).convert('RGBA'))[..., 3]
            zone = base & (s13 <= 8) & (a14 > 8)
        else:
            zone = (a14 > 8) & (a13 <= 8)
        g = dict(RK.sample_genotypes(1)[0])
        g.update({'Tn1': ('t', 't'), 'Tn2': ('t', 't'), 'V': ('v', 'v'),
                  'L1': ('l', 'l'), 'L2': ('l', 'l'), 'K': ('k', 'k'),
                  'Tl': ('tl', 'tl') if kind == 'short' else ('Tl', 'tl'),
                  'Tf': ('tf', 'tf')})
        spec = AM.to_art(PH(g))
        spec['coat'], spec['fur'], spec['tail'] = 'blue', 'short', kind
        img, _ = AM._compose(spec, 1024)
        a = np.asarray(img.convert('RGBA'))
        av = a[..., 3][zone]
        lum = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2])[zone]
        row = (int(av.size), float(av.mean()), float(np.median(av)),
               100.0 * float((av > 200).mean()), float(lum.std()))
        if kind == 'normal':
            ref = row
        LINES.append('  ·  %-7s 区域%6d  alpha均值%6.1f  中位%5.1f  >200占%5.1f%%  纹理std%5.1f'
                     % ((kind,) + row))
    LINES.append('     tail_normal 是参照：同一窗口它应该接近实心（%d px / 均值 %.0f）'
                 % (ref[0], ref[1]))
    LINES.append('     short / thin 若均值远低于参照，说明填的是半透明雾而不是毛。')


def main():
    test_r1()
    test_r1_shape()
    test_r1_quality()
    test_r3()
    test_r4()
    test_r5()
    test_r6()
    test_r7()
    test_population()
    print('\n'.join(LINES))
    print('')
    print('=' * 60)
    print('通过 %d 项，失败 %d 项' % (PASS, FAIL))
    print('全部通过。' if FAIL == 0 else '有失败项，见上。')
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
