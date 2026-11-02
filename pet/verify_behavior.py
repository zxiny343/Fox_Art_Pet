# -*- coding: utf-8 -*-
"""桌宠行为状态机自检（纯逻辑，不启动 GUI）。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import behavior as BH                                       # noqa: E402
import anim as AN                                           # noqa: E402

PASS = FAIL = 0
LINES = []


def chk(cond, name, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        LINES.append('  [OK]   %-44s %s' % (name, detail))
    else:
        FAIL += 1
        LINES.append('  [FAIL] %-44s %s' % (name, detail))


def sec(t):
    LINES.append('')
    LINES.append('-- %s %s' % (t, '-' * max(0, 58 - len(t))))


def run(bh, seconds, dt=1 / 30.0):
    n = int(seconds / dt)
    for _ in range(n):
        bh.tick(dt)


# ---------------------------------------------------------------------------
def test_basic():
    sec('A · 初始状态与常驻层')
    bh = BH.Behavior(seed=1)
    st = bh.status()
    chk(st['state'] == 'awake', 'A1 初始 awake', st['state'])
    chk(st['base'] == 'idle_breath', 'A1 常驻 base = idle_breath', st['base'])
    chk('idle_tail_sway' in st['adds'], 'A1 常驻 add = 尾巴轻摆', str(st['adds']))

    it = dict(bh.items())
    chk(abs(it['idle_breath']) < 1e-9, 'A2 起始 base 进度为 0', '%.3f' % it['idle_breath'])
    run(bh, 1.0)
    it = dict(bh.items())
    chk(abs(it['idle_breath'] - 0.25) < 0.02, 'A2 1 秒后呼吸进度 0.25（4s 循环）',
        '%.3f' % it['idle_breath'])
    chk(abs(it['idle_tail_sway'] - (1.0 / 3.0)) < 0.02,
        'A2 1 秒后摆尾进度 0.33（3s 循环）', '%.3f' % it['idle_tail_sway'])


def test_blink():
    sec('B · 随机眨眼（face 层，一次性）')
    bh = BH.Behavior(seed=7)
    seen = 0
    last = None
    for i in range(int(30 * 30)):          # 30 秒 @30fps
        bh.tick(1 / 30.0)
        f = bh.status()['faces']
        if 'blink' in f and last != 'blink':
            seen += 1
        last = 'blink' if 'blink' in f else None
    chk(seen >= 3, 'B1 30 秒内至少眨眼 3 次', '%d 次' % seen)

    # 眨眼必须有自己的进度：出现时从 0 开始，走满 0.4s（12 帧 @30fps）后消失
    bh2 = BH.Behavior(seed=3)
    prog = []
    segs = []
    cur = 0
    for i in range(int(20 * 30)):
        bh2.tick(1 / 30.0)
        it = dict(bh2.items())
        if 'blink' in it:
            prog.append(it['blink'])
            cur += 1
        elif cur:
            segs.append(cur)
            cur = 0
    if cur:
        segs.append(cur)
    if prog:
        chk(prog[0] < 0.2, 'B2 眨眼从进度 0 附近开始', '%.3f' % prog[0])
        chk(max(prog) > 0.8, 'B2 眨眼能走到进度 >0.8', '%.3f' % max(prog))
        ok = segs and all(11 <= s <= 13 for s in segs)
        chk(ok, 'B2 每次眨眼约 12 帧 = 0.4s（不拖尾不截断）',
            '各次帧数 %s' % segs[:8])
    else:
        chk(False, 'B2 眨眼里出现了', '未捕获')

    # 眨眼不会永久停留
    bh3 = BH.Behavior(seed=11)
    run(bh3, 10.0)
    # 找一个 blink 刚结束的时刻：连续 1 秒不出现
    bh3.tick(0.5)
    got = False
    for _ in range(60):
        bh3.tick(1 / 30.0)
        if not bh3.status()['faces']:
            got = True
    chk(got, 'B3 眨眼结束后 face 层清空', '')


def test_independent_time():
    sec('C · 各动作独立计时（关键：否则眨眼会跟着呼吸循环）')
    bh = BH.Behavior(seed=5)
    run(bh, 3.0)
    bh.interact('pet')                       # happy_wag 2s
    base_at_pet = None
    samples = []
    for i in range(int(3.0 * 30)):
        bh.tick(1 / 30.0)
        it = dict(bh.items())
        samples.append((it.get('happy_wag'), it.get('idle_tail_sway'),
                        it.get('blink')))
    # 三个动作在同一帧的进度互不相同（不是同一个 t）
    diff = [s for s in samples if s[0] is not None and s[1] is not None]
    same = sum(1 for a, b, _ in diff if abs(a - b) < 1e-9)
    chk(diff and same == 0, 'C1 base 与 add 进度不相等',
        '%d 帧样本，%d 帧相同' % (len(diff), same))

    with_blink = [s for s in samples if s[2] is not None]
    if with_blink:
        chk(all(abs(a - c) > 1e-9 for a, _, c in with_blink),
            'C2 眨眼进度独立于 base', '%d 帧' % len(with_blink))
    else:
        chk(True, 'C2 眨眼进度独立于 base', '本轮未触发眨眼，跳过')


def test_interact():
    sec('D · 交互动作播完自动回到待机')
    bh = BH.Behavior(seed=2)
    ok = bh.interact('pet')
    chk(ok, 'D1 interact(pet) 返回 True', '')
    chk(bh.status()['base'] == 'happy_wag', 'D1 切到 happy_wag',
        bh.status()['base'])
    run(bh, 1.0)
    chk(bh.status()['base'] == 'happy_wag', 'D2 播到 1s 仍在 happy_wag',
        bh.status()['base'])
    run(bh, 1.2)
    chk(bh.status()['base'] == 'idle_breath', 'D2 2s 播完回到 idle_breath',
        bh.status()['base'])

    bh.interact('feed')
    chk(bh.status()['base'] == 'eat', 'D3 feed → eat', bh.status()['base'])
    run(bh, 2.2)
    chk(bh.status()['base'] == 'idle_breath', 'D3 播完回待机',
        bh.status()['base'])
    chk(bh.status()['state'] == 'awake', 'D3 状态仍 awake',
        bh.status()['state'])


def test_drag():
    sec('E · 拖拽状态')
    bh = BH.Behavior(seed=4)
    bh.interact('drag_start')
    chk(bh.status()['base'] == 'drag', 'E1 拖起 → drag', bh.status()['base'])
    run(bh, 5.0)
    chk(bh.status()['base'] == 'drag', 'E2 拖着不放一直保持 drag',
        bh.status()['base'])
    bh.interact('drag_end')
    chk(bh.status()['base'] == 'drop', 'E3 松手 → drop', bh.status()['base'])
    run(bh, 1.0)
    chk(bh.status()['base'] == 'idle_breath', 'E3 drop 播完回待机',
        bh.status()['base'])


def test_sleep():
    sec('F · 犯困 → 坐下 → 趴下 → 睡 → 唤醒')
    bh = BH.Behavior(seed=6, doze_after=3.0)
    run(bh, 3.5)
    chk(bh.status()['state'] == 'drowsy', 'F1 超时后进入 drowsy',
        bh.status()['state'])
    chk(bh.status()['base'] == 'sit_down', 'F1 先播 sit_down',
        bh.status()['base'])
    run(bh, 1.5)
    chk(bh.status()['base'] == 'lie_down', 'F2 接着播 lie_down',
        bh.status()['base'])
    run(bh, 2.0)
    chk(bh.status()['base'] == 'sleep', 'F2 再播 sleep', bh.status()['base'])
    chk(bh.status()['state'] == 'asleep', 'F2 状态 asleep',
        bh.status()['state'])

    # 睡着不眨眼
    blink_seen = False
    for _ in range(int(10 * 30)):
        bh.tick(1 / 30.0)
        if 'blink' in bh.status()['faces']:
            blink_seen = True
    chk(not blink_seen, 'F3 睡着时不眨眼', '')

    bh.interact('pet')
    chk(bh.status()['base'] == 'wake_up', 'F4 睡着时被摸 → wake_up',
        bh.status()['base'])
    run(bh, 2.2)
    chk(bh.status()['base'] == 'idle_breath' and bh.status()['state'] == 'awake',
        'F4 醒后回到待机', '%s / %s' % (bh.status()['base'],
                                       bh.status()['state']))

    # 唤醒后计时重置：再等 3s 才会重新犯困
    bh2 = BH.Behavior(seed=6, doze_after=3.0)
    run(bh2, 2.5)
    bh2.interact('pet')
    run(bh2, 2.5)
    chk(bh2.status()['state'] == 'awake', 'F5 交互后犯困计时重置',
        '已过 %.1fs，交互在 2.5s' % bh2.t)


def test_determinism():
    sec('G · 确定性（同 seed 可复现）')
    a = BH.Behavior(seed=42)
    b = BH.Behavior(seed=42)
    for _ in range(300):
        a.tick(1 / 30.0)
        b.tick(1 / 30.0)
    chk(a.status() == b.status(), 'G1 同 seed 状态一致', str(a.status()))
    ra, rb = BH.Behavior(seed=42), BH.Behavior(seed=43)
    sa = [ra.status()['faces'] for _ in range(300) if ra.tick(1 / 30.0) is None]
    sb = [rb.status()['faces'] for _ in range(300) if rb.tick(1 / 30.0) is None]
    chk(sa != sb, 'G2 不同 seed 随机序列不同', '')


def test_render_roundtrip():
    sec('H · 与渲染层对接（能真的出图）')
    import artmap as AM
    import render_kernel as RK
    from fox_ecosystem_sim import phenotype as PH
    g = RK.sample_genotypes(1)[0]
    spec = AM.to_art(PH(g))
    bh = BH.Behavior(seed=9)
    run(bh, 1.0)
    bh.interact('pet')
    layers = AN.get_layers(spec, 256)
    ok = True
    sizes = set()
    for i in range(12):
        bh.tick(1 / 30.0)
        img, _ = AN.render_frame(spec, 0, bh.items(), size=256,
                                 layers=layers, work=256)
        sizes.add(img.size)
        if img.size != (256, int(round(256 * AN.ASPECT))) or img.mode != 'RGBA':
            ok = False          # 画布向下扩了，高 = 宽 × 1.1875
    chk(ok, 'H1 连续 12 帧都能渲染',
        str(list(sizes)[0]) if len(sizes) == 1 else str(sizes))
    # 帧之间有变化（真的在动）
    bh2 = BH.Behavior(seed=9)
    run(bh2, 1.0)
    f1, _ = AN.render_frame(spec, 0, bh2.items(), size=256, layers=layers,
                            work=256)
    run(bh2, 0.5)
    f2, _ = AN.render_frame(spec, 0, bh2.items(), size=256, layers=layers,
                            work=256)
    import numpy as np
    d = np.abs(np.asarray(f1).astype(int) - np.asarray(f2).astype(int)).mean()
    chk(d > 0.5, 'H2 相隔 0.5s 的两帧有可见差异', '平均差 %.2f' % d)


def main():
    test_basic()
    test_blink()
    test_independent_time()
    test_interact()
    test_drag()
    test_sleep()
    test_determinism()
    test_render_roundtrip()
    print('\n'.join(LINES))
    print('')
    print('通过 %d / %d' % (PASS, PASS + FAIL))
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
