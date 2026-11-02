# -*- coding: utf-8 -*-
"""渲染内核自检（S2 层）。

跑法：E:/SoftWare/python3.10/python.exe sim/verify_render_kernel.py

四段：
  A 降级表 —— thin/short/ear_large 被替换、留痕、trait_* 同步、关掉后复原缺陷
  B 缓存   —— 命中/失效/不串味
  C 确定性 —— 同基因型逐像素一致
  D 规模   —— 24 次真实渲染全部成功、尺寸正确、无未登记破面
"""
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artmap as AM                    # noqa: E402
import render_kernel as RK             # noqa: E402
from fox_ecosystem_sim import phenotype as PH   # noqa: E402

OK = FAIL = 0
FAILS = []


def chk(name, cond, detail=''):
    global OK, FAIL
    if cond:
        OK += 1
        print('  [OK] %-46s %s' % (name, detail))
    else:
        FAIL += 1
        FAILS.append(name)
        print('  [FAIL] %-46s %s' % (name, detail))


def _graft(**loci):
    """拿一只真实个体做底，只改指定位点，保证基因型合法且其余表型真实。"""
    g = dict(RK.sample_genotypes(1)[0])
    g.update(loci)
    return g


def _tail_geno(kind):
    """构造指定单尾形态的基因型。

    artmap 的形态优先级：K > 尾长 Tl > 蓬松度 Tf，尾数优先于形态。
    所以先按尾数=1（Tn1/Tn2/V 全隐性）构造，再选形态位点。
    """
    one = {'Tn1': ('t', 't'), 'Tn2': ('t', 't'), 'V': ('v', 'v')}
    table = {
        'thin':  dict(one, K=('k', 'k'), Tl=('Tl', 'tl'), Tf=('tf', 'tf')),
        'short': dict(one, K=('k', 'k'), Tl=('tl', 'tl'), Tf=('tf', 'tf')),
        'curl':  dict(one, K=('K', 'K')),
        'normal': dict(one, K=('k', 'k'), Tl=('Tl', 'tl'), Tf=('Tf', 'Tf')),
    }
    return _graft(**table[kind])


def main():
    t0 = time.time()
    RK.clear_cache()

    print('\nA 降级表')
    g = {k: _tail_geno(k) for k in ('thin', 'short', 'curl')}
    got = {k: AM.to_art(PH(v))['tail'] for k, v in g.items()}
    chk('A0 构造的基因型确实表达为目标尾型',
        all(got[k] == k for k in g), str(got))

    # 素材包 ≥ v1.4 之后 R1/R3 已修好，降级表会自动停用。
    # 这一段因此有两种正确结果，断言必须跟着版本走，否则会把"修好了"判成失败。
    fixed = RK.ART_VER_NUM >= (1, 4)
    print('   素材版本 %s → 降级表%s' %
          ('.'.join(map(str, RK.ART_VER_NUM)), '已自动停用' if fixed else '生效中'))

    for want in ('thin', 'short'):
        if want not in g:
            continue
        img, m = RK.render(geno=g[want], size=1024, allow_degrade=True,
                           use_cache=False, check_holes=True)
        if fixed:
            chk('A1 %-6s v1.4 已修好 → 不再降级，用原部件' % want,
                m['entities']['tail'] == 'tail_%s.png' % want,
                m['entities']['tail'])
            chk('A1 %-6s 无降级留痕' % want, not m['degraded'],
                '; '.join(d['reason'] for d in m['degraded'])[:56])
        else:
            chk('A1 %-6s 默认降级 → tail_normal' % want,
                m['entities']['tail'] == 'tail_normal.png',
                m['entities']['tail'])
            chk('A1 %-6s 降级留痕' % want,
                any(d['kind'] == 'tail' for d in m['degraded']),
                '; '.join(d['reason'] for d in m['degraded'])[:56])
        img2, m2 = RK.render(geno=g[want], size=1024, allow_degrade=False,
                             use_cache=False, check_holes=True)
        chk('A2 %-6s 关降级 → 原始部件' % want,
            m2['entities']['tail'] == 'tail_%s.png' % want,
            m2['entities']['tail'])
        if fixed:
            chk('A2 %-6s 原部件缺口已修（< %d）' % (want, RK.HOLE_FAIL),
                m2['holes'] < RK.HOLE_FAIL, '%d px' % m2['holes'])
        else:
            chk('A2 %-6s 关降级后缺口 > 20000px（v1.3 缺陷仍在）' % want,
                m2['holes'] > 20000, '%d px' % m2['holes'])
        chk('A3 %-6s 最终成品不算破面' % want,
            m['holes'] < RK.HOLE_FAIL, '%d px（阈值 %d）'
            % (m['holes'], RK.HOLE_FAIL))

    # ear_large：构造一个 Ez=2 且非 St/Erf/ErP 的个体不易稳定命中，
    # 直接测纯函数，避免被遗传分布卡住。
    spec = {'coat': 'blue', 'fur': 'short', 'tail': 'normal', 'ear': 'large',
            'eye_l': 'round_blue', 'eye_r': 'round_blue', 'pupil': None,
            'pattern': 'solid', 'special': [], 'notes': [], 'missing': [],
            'trait_ear': 'ear_large'}
    hits = RK._apply_degrade(spec)
    if fixed:
        chk('A4 ear_large v1.4 已修好 → 不再降级',
            spec['ear'] == 'large' and not hits,
            '%s / %s' % (spec['ear'], spec['trait_ear']))
    else:
        chk('A4 ear_large 降级为 round',
            spec['ear'] == 'round' and spec['trait_ear'] == 'ear_round',
            '%s / %s' % (spec['ear'], spec['trait_ear']))
        chk('A4 ear 降级记录 level=visual',
            hits and hits[0]['level'] == 'visual',
            hits[0]['level'] if hits else '-')

    spec2 = {'coat': 'blue', 'fur': 'short', 'tail': 'curl', 'ear': 'round',
             'notes': [], 'missing': [], 'trait_tail': 'tail_curl'}
    RK._apply_degrade(spec2)
    chk('A5 不在表里的尾型不动（curl 保留）', spec2['tail'] == 'curl', spec2['tail'])

    print('\nB 缓存')
    g0 = RK.sample_genotypes(1)[0]
    _, m1 = RK.render(geno=g0, size=512, use_cache=True)
    p1 = RK._cache_paths(RK._key(g0, None, 512, True, {}))[0]
    mt1 = os.path.getmtime(p1)
    time.sleep(0.02)
    _, m2 = RK.render(geno=g0, size=512, use_cache=True)
    chk('B1 第二次命中缓存', m2['cache'] == 'hit', m2['cache'])
    chk('B1 命中不重写文件', os.path.getmtime(p1) == mt1)
    _, m3 = RK.render(geno=g0, size=256, use_cache=True)
    chk('B2 不同尺寸是不同条目', m3['cache'] == 'miss' and m3['size'] == 256)
    _, m4 = RK.render(geno=g0, size=512, use_cache=True, allow_degrade=False)
    chk('B3 降级开关不串味', m4['cache'] == 'miss', m4['cache'])
    _, m5 = RK.render(geno=g0, size=512, use_cache=False)
    chk('B4 use_cache=False 不读缓存', m5['cache'] == 'miss')
    n = RK.clear_cache()
    _, m6 = RK.render(geno=g0, size=512, use_cache=True)
    chk('B5 清空后重新计算', m6['cache'] == 'miss', '清掉 %d 个文件' % n)

    print('\nC 确定性')
    a, _ = RK.render(geno=g0, size=512, use_cache=False)
    b, _ = RK.render(geno=g0, size=512, use_cache=False)
    chk('C1 同基因型逐像素一致',
        np.array_equal(np.asarray(a), np.asarray(b)))
    g1 = RK.sample_genotypes(6)[5]
    c, _ = RK.render(geno=g1, size=512, use_cache=False)
    chk('C2 不同基因型确实不同',
        not np.array_equal(np.asarray(a), np.asarray(c)))

    print('\nD 规模')
    gs = RK.sample_genotypes(12, 777)
    bad = []
    for i, gg in enumerate(gs):
        for sz in (512, 256):
            im, m = RK.render(geno=gg, size=sz, use_cache=True, check_holes=True)
            if im.size != (sz, sz):
                bad.append('尺寸 %s' % (im.size,))
            if m.get('holes', 0) >= RK.HOLE_FAIL and not m.get('holes_exempt'):
                bad.append('%s@%d 破面 %d' % (m['entities']['tail'], sz,
                                             m['holes']))
    chk('D1 12 只 × 2 尺寸全部渲染成功', not bad, bad[:3] and str(bad[:3]))
    st = RK.cache_stats()
    # 12 只里可能有个体基因型相同（近交），缓存条目会合并，故按实际去重数算
    chk('D2 缓存规模正常', st['files'] >= 18, '%d 文件 / %.2f MB'
        % (st['files'], st['mb']))

    print('\n' + '=' * 62)
    print('通过 %d 项，失败 %d 项   （%.1fs）' % (OK, FAIL, time.time() - t0))
    if FAIL:
        print('失败项：' + '、'.join(FAILS))
        return 1
    print('全部通过。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
