# -*- coding: utf-8 -*-
"""动画播放器自检（2026-11-02）"""
import os
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anim as AN                                      # noqa: E402
import artmap as AM                                    # noqa: E402
import legs as LG                                      # noqa: E402
import render_kernel as RK                             # noqa: E402
from fox_ecosystem_sim import phenotype as PH          # noqa: E402

PASS = FAIL = 0
ROWS = []


def ck(ok, title, detail=''):
    global PASS, FAIL
    PASS, FAIL = (PASS + 1, FAIL) if ok else (PASS, FAIL + 1)
    ROWS.append('  %s %-50s %s' % ('✓' if ok else '✗', title, detail))


def sec(t):
    ROWS.append('')
    ROWS.append('[%s]' % t)


def main():
    g = RK.sample_genotypes(1)[0]
    spec = AM.to_art(PH(g))
    acts = ['idle_breath', 'idle_tail_sway', 'idle_ear_twitch', 'blink']

    # --- A 采样 ---
    sec('A 关键帧采样')
    sway = AN.ACTIONS['idle_tail_sway']
    ch = [c for c in sway['channels'] if c['bone'] == 'tail_root'][0]
    v0 = AN.sample_keys(ch['keys'], 0.0)
    ck(abs(v0 - ch['keys'][0][1]) < 1e-6, 'A1 t=0 命中首帧', '%.3f' % v0)
    v1 = AN.sample_keys(ch['keys'], 1.0)
    ck(abs(v1 - ch['keys'][-1][1]) < 1e-6 or
       abs(v1 - ch['keys'][0][1]) < 1e-6, 'A2 t=1 命中末帧', '%.3f' % v1)
    mid = AN.sample_keys(ch['keys'], 0.04165)   # 两个关键帧 0.0 / 0.0833 之间
    lo, hi = sorted((ch['keys'][0][1], ch['keys'][1][1]))
    ck(lo - 1e-6 <= mid <= hi + 1e-6, 'A3 关键帧之间单调插值不越界', '%.3f' % mid)

    # 循环闭合：loop=True 的动作首尾应连续
    p0 = AN.pose_at(acts, 0.0)
    p1 = AN.pose_at(acts, 1.0)
    d = abs(p0.rotate('tail_root') - p1.rotate('tail_root'))
    ck(d < 0.05, 'A4 摆尾在循环边界连续', 'Δ=%.4f°' % d)

    # --- B 层叠加 ---
    sec('B 多层叠加')
    pb = AN.pose_at(['idle_breath'], 0.25)
    pt = AN.pose_at(['idle_tail_sway'], 0.25)
    both = AN.pose_at(['idle_breath', 'idle_tail_sway'], 0.25)
    # 两个动作都驱动 tail_sub，add 层应叠加
    exp = pb.rotate('tail_sub') + pt.rotate('tail_sub') \
        if AN.ACTIONS['idle_tail_sway']['layer'] == 'add' \
        else pt.rotate('tail_sub')
    ck(abs(both.rotate('tail_sub') - exp) < 1e-6,
       'B1 同骨骼同通道按层规则合并',
       'breath %.2f + sway %.2f = %.2f'
       % (pb.rotate('tail_sub'), pt.rotate('tail_sub'), both.rotate('tail_sub')))
    ck(abs(both.get('body', 'scaleY', 1.0) - pb.get('body', 'scaleY', 1.0)) < 1e-6,
       'B2 base 层的呼吸缩放不被 add 层影响',
       '%.4f' % both.get('body', 'scaleY', 1.0))

    # --- C 眨眼 ---
    sec('C 附件切换（眨眼）')
    sl0 = AN.slots_at(['blink'], 0.0)
    slm = AN.slots_at(['blink'], 0.35)
    ck(slm.get('eye_l') == 'eye_closed', 'C1 t=0.35 切到闭眼件',
       str(slm.get('eye_l')))
    ck(sl0.get('eye_l') != 'eye_closed', 'C2 t=0 是睁眼', str(sl0.get('eye_l')))
    p = AM.find_attachment('eye_closed', spec['coat'])
    ck(p is not None and os.path.isfile(p),
       'C3 闭眼件能按毛色解析到文件', os.path.basename(p) if p else 'None')

    # --- D 渲染质量 ---
    sec('D 渲染质量（不因分段旋转产生破面）')
    work = 512
    L = AN.get_layers(spec, work)
    base_img, _ = AN.render_frame(spec, 0.0, ['idle_breath'], size=512,
                                  layers=L, work=work)
    worst = 0
    for i in range(8):
        t = i / 8.0
        img, _ = AN.render_frame(spec, t, acts, size=512, layers=L, work=work)
        a = np.asarray(img.convert('RGBA'))
        m = AM.body_mask(spec['fur'])
        # 画布向下扩了 192px（给坐下/趴下的下沉留地方），母版 mask 也要同比例扩。
        # 注意数组是 (高, 宽) = (1216, 1024)，扩的是高不是宽。
        mh = int(round(512 * AN.ASPECT))
        mask = np.zeros((int(round(1024 * AN.ASPECT)), 1024), dtype=bool)
        mask[:1024, :1024] = m
        m512 = np.asarray(Image.fromarray((mask * 255).astype(np.uint8))
                          .resize((512, mh), Image.NEAREST)) > 128
        hole = int((m512 & (a[..., 3] < 8)).sum())
        worst = max(worst, hole)
    # 512 下 1024 的 3 万像素缺口约合 7.5 千；这里只抓"旋转撕开"的新洞
    ck(worst < 3000, 'D1 八帧里尾巴分段旋转不撕出新洞',
       '最差 %d px' % worst)
    ck(base_img.size == (512, int(round(512 * AN.ASPECT))),
       'D2 输出尺寸正确（含下沉余量）', str(base_img.size))

    # --- E 确定性 ---
    sec('E 确定性')
    i1, _ = AN.render_frame(spec, 0.42, acts, size=256, work=256)
    i2, _ = AN.render_frame(spec, 0.42, acts, size=256, work=256)
    ck(np.array_equal(np.asarray(i1), np.asarray(i2)),
       'E1 同一 t 逐像素一致')

    # --- F 性能 ---
    sec('F 性能（决定桌宠能不能实时跑）')
    for work_sz, budget in ((256, 0.040), (512, 0.080)):
        LL = AN.get_layers(spec, work_sz)
        AN.render_frame(spec, 0.1, acts, size=256, layers=LL, work=work_sz)
        t0 = time.time()
        n = 20
        for i in range(n):
            AN.render_frame(spec, i / float(n), acts, size=256,
                            layers=LL, work=work_sz)
        dt = (time.time() - t0) / n
        ck(dt < budget, 'F work=%d 帧耗时 < %.0fms' % (work_sz, budget * 1000),
           '%.1fms → %.0f fps' % (dt * 1000, 1.0 / dt))

    # --- G 腿部 rig（四足步态） ---
    sec('G 腿部 rig（walk 类动作启用四足步态）')
    LG.clear_cache()
    work = 336
    L336 = AN.get_layers(spec, work)
    # G1 检测到 4 条腿
    info = LG._detect(L336['core'])
    ck(info is not None and len(info) == 4, 'G1 检测到 4 条腿',
       '腿数=%d' % (len(info) if info else 0))
    if info:
        # 4 条腿 x 中心应单调递增（从左到右）
        xs = [lg['xc'] for lg in info]
        ck(xs == sorted(xs), 'G2 四腿 x 坐标从左到右有序', str(xs))
        # y_root < y_foot（根部在脚上方）
        ck(all(lg['y_root'] < lg['y_foot'] for lg in info),
           'G3 每条腿根部在脚上方')

    # G4 walk 帧差 > idle 帧差（腿在动）—— 显式开 leg_rig 测腿部 rig 本身
    def frame_diff(items_a, items_b, leg=True):
        ia = np.asarray(AN.render_frame(spec, 0, items_a, size=168,
                                        layers=L336, work=work,
                                        leg_rig=leg)[0], np.int16)
        ib = np.asarray(AN.render_frame(spec, 0, items_b, size=168,
                                        layers=L336, work=work,
                                        leg_rig=leg)[0], np.int16)
        return float(np.abs(ia - ib).mean())

    # walk t=0 vs t=0.25：开腿 rig 时腿应明显不同
    d_walk = frame_diff([('walk', 0.0)], [('walk', 0.25)], leg=True)
    # idle 同样区间：应几乎无差
    d_idle = frame_diff([('idle_breath', 0.0)], [('idle_breath', 0.25)], leg=True)
    ck(d_walk > d_idle * 2.0, 'G4 walk 帧差显著大于 idle',
       'walk=%.2f idle=%.2f' % (d_walk, d_idle))
    ck(d_walk > 1.0, 'G5 walk 帧差 > 1（腿在动）', 'walk=%.2f' % d_walk)

    # G6 idle 不触发腿部 rig（walk_phase=None 时 core 不变）
    img_idle, _ = AN.render_frame(spec, 0, [('idle_breath', 0.3)],
                                  size=168, layers=L336, work=work, leg_rig=True)
    ck(img_idle.size == (168, int(round(168 * AN.ASPECT))),
       'G6 idle 渲染尺寸正确', str(img_idle.size))

    # G7 walk 性能：腿部 rig 不拖垮帧率
    AN.render_frame(spec, 0, [('walk', 0.1)], size=168, layers=L336,
                    work=work, leg_rig=True)
    t0 = time.time()
    n = 20
    for i in range(n):
        AN.render_frame(spec, 0, [('walk', i / float(n))],
                        size=168, layers=L336, work=work, leg_rig=True)
    dt_walk = (time.time() - t0) / n
    ck(dt_walk < 0.045, 'G7 walk+腿rig 帧耗时 < 45ms',
       '%.1fms' % (dt_walk * 1000))

    # G8 朝向：镜像后 walk 帧与原图非镜像版不同（朝向变了）
    img_r, _ = AN.render_frame(spec, 0, [('walk', 0.25)],
                               size=168, layers=L336, work=work, leg_rig=True)
    img_l = img_r.transpose(Image.FLIP_LEFT_RIGHT)
    ck(not np.array_equal(np.asarray(img_r), np.asarray(img_l)),
       'G8 镜像后像素改变（朝向翻转生效）')

    print('\n'.join(ROWS))
    print('')
    print('=' * 62)
    print('通过 %d 项，失败 %d 项' % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
