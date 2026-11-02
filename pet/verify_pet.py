# -*- coding: utf-8 -*-
"""桌宠外壳自检（离屏，不打扰桌面）。

用 QT_QPA_PLATFORM=offscreen 建窗口但不真的显示，抓窗口像素检查：
透明背景、狐狸真的画出来了、缩放/换只/状态切换都能渲染、帧率够 30fps。
"""

import os
import sys
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, 'sim'), os.path.dirname(os.path.abspath(__file__))):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np                                              # noqa: E402
from PIL import Image                                           # noqa: E402
from PySide6.QtCore import Qt                                   # noqa: E402
from PySide6.QtWidgets import QApplication                      # noqa: E402

import config as CFG                                            # noqa: E402
import anim as AN                                               # noqa: E402
import artmap as AM                                             # noqa: E402
from fox_ecosystem_sim import phenotype as PH                    # noqa: E402

PASS = FAIL = 0
LINES = []
DOCS = os.path.join(ROOT, 'docs')


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


def grab(pet):
    """抓窗口内容 → numpy RGBA。"""
    q = pet.grab()
    from PySide6.QtGui import QImage as _QI
    im = q.toImage().convertToFormat(_QI.Format.Format_RGBA8888)
    w, h = im.width(), im.height()
    buf = im.constBits()
    a = np.frombuffer(bytes(buf), dtype=np.uint8).reshape(h, w, 4)
    return np.ascontiguousarray(a)


def main():
    import app as APP

    app = QApplication.instance() or QApplication(sys.argv)
    cfg, state_path = CFG.load(None)
    state_path = os.path.join(ROOT, '_pet_test_state.json')
    cfg['x'], cfg['y'] = 300, 300
    cfg['scale'] = 1.0          # 不吃本机 state 里的缩放，保证断言稳定
    cfg['fps'] = 24             # 与 config 默认一致（30fps 会把 2× 超采样逼到降档）
    cfg['log'] = False          # 自检别往 pet.log 里灌日志
    cfg['geno'] = None          # 也不吃本机那只，保证「换一只」一定换得掉
    cfg['ssaa'] = 2.0           # ssaa 不落盘，这里显式给默认值

    sec('A · 窗口属性')
    pet = APP.FoxPet(cfg, state_path)
    f = pet.windowFlags()
    chk(bool(f & Qt.FramelessWindowHint), 'A1 无边框', '')
    chk(bool(f & Qt.Tool), 'A1 不在任务栏显示（Qt.Tool）', '')
    chk(bool(f & Qt.WindowStaysOnTopHint), 'A1 置顶', '')
    chk(pet.testAttribute(Qt.WA_TranslucentBackground),
        'A1 透明背景属性已开', '')
    exp_w = int(cfg['base_size'] * cfg['scale'])
    exp_h = int(exp_w * AN.ASPECT)
    chk(pet.width() == exp_w and pet.height() == exp_h,
        'A2 窗口尺寸 = base×scale 宽 / ×%.4f 高（给下沉留地方）' % AN.ASPECT,
        '%dx%d (期望 %dx%d)' % (pet.width(), pet.height(), exp_w, exp_h))
    pet.show()
    app.processEvents()

    sec('B · 渲染与透明背景')
    pet._tick()
    app.processEvents()
    a = grab(pet)
    chk(a.shape[2] == 4, 'B1 抓到 RGBA', str(a.shape))
    trans = float((a[..., 3] < 8).mean())
    opaque = float((a[..., 3] > 200).mean())
    chk(trans > 0.25, 'B1 大部分区域透明（不是实心方块）',
        '透明 %.1f%% / 不透明 %.1f%%' % (trans * 100, opaque * 100))
    chk(opaque > 0.10, 'B1 狐狸本体画出来了', '不透明 %.1f%%' % (opaque * 100))

    # 边角必须透明（否则是一个白/黑方块贴在桌面上）
    corners = [a[2, 2, 3], a[2, -3, 3], a[-3, 2, 3], a[-3, -3, 3]]
    chk(max(corners) < 20, 'B2 四个角透明', str(corners))
    # 中心必须有内容
    c = a[a.shape[0] // 2, a.shape[1] // 2, 3]
    chk(c > 100, 'B2 画布中心有狐狸', 'alpha=%d' % int(c))

    sec('C · 帧率（决定能不能流畅）')
    pet.timer.stop()
    for _ in range(150):        # 先让自适应降档收敛（30 帧评估一次）
        pet._tick()
    n = 60
    t0 = time.time()
    for _ in range(n):
        pet._tick()
    dt = (time.time() - t0) / n
    budget = 1.0 / float(cfg['fps'])
    chk(dt < budget, 'C1 单帧渲染 < 1/目标fps（%.0f fps）' % cfg['fps'],
        '%.1f ms/帧 → %.0f fps (ssaa=%.1f work=%d)'
        % (dt * 1000, 1.0 / dt, pet.ssaa, pet.work))
    chk(pet.fps > 0, 'C1 fps 统计有值', '%.1f' % pet.fps)
    chk(pet.ssaa >= 2.0 - 1e-6, 'C2 24fps 下 2× 超采样没被误降档',
        'ssaa=%.1f work=%d' % (pet.ssaa, pet.work))

    sec('D · 缩放')
    w0 = pet.width()
    pet.set_scale(2.0)
    chk(pet.width() > w0, 'D1 放大后窗口变大', '%d → %d' % (w0, pet.width()))
    chk(pet.work >= 256, 'D1 工作分辨率随缩放提升', 'work=%d' % pet.work)
    pet._tick()
    app.processEvents()
    a2 = grab(pet)
    chk(a2.shape[0] == pet.height(), 'D1 抓图尺寸与窗口一致', str(a2.shape))
    chk(float((a2[..., 3] > 200).mean()) > 0.08, 'D1 放大后仍有内容',
        '不透明 %.1f%%' % (float((a2[..., 3] > 200).mean()) * 100))
    pet.set_scale(0.5)
    chk(pet.width() < w0, 'D2 缩小后窗口变小', '%d' % pet.width())
    chk(pet.work == 256, 'D2 小尺寸时 work 保底 256', 'work=%d' % pet.work)
    # 滚轮是按 1.12 倍步进的，非整数缩放必须也能跑（setFixedSize 只吃 int）
    pet.set_scale(1.12)
    chk(pet.width() == int(cfg['base_size'] * 1.12),
        'D3 非整数缩放后尺寸取整', '%d' % pet.width())
    ok = True
    try:
        pet._tick()
        pet._tick()
    except Exception as ex:
        ok = False
        LINES.append('       %s' % ex)
    chk(ok, 'D3 非整数缩放下连续渲染不报错', 'work=%d' % pet.work)
    pet.set_scale(1.0)

    sec('E · 交互动作都能渲染')
    for kind in ('pet', 'feed', 'drink', 'stretch', 'howl', 'bark',
                 'sparkle', 'drag_start'):
        pet.bh.interact(kind)
        try:
            img, _ = AN.render_frame(pet.spec, 0, pet.bh.items(),
                                     size=pet.width(), layers=pet.layers,
                                     work=pet.work)
            ok = img.size == (pet.width(), int(round(pet.width() * AN.ASPECT)))
        except Exception as ex:
            ok = False
            LINES.append('       %s: %s' % (kind, ex))
        chk(ok, 'E1 interact(%s) 能渲染' % kind, pet.bh.status()['base'])
    pet.bh.interact('drag_end')
    for _ in range(60):
        pet.bh.tick(1 / 30.0)
    chk(pet.bh.status()['base'] == 'idle_breath', 'E2 动作播完回到待机',
        pet.bh.status()['base'])

    sec('F · 睡眠链路在窗口里跑通')
    pet.bh._doze()
    for _ in range(int(6 * 30)):
        pet.bh.tick(1 / 30.0)
        pet._tick()
    chk(pet.bh.status()['state'] == 'asleep', 'F1 6 秒后睡着',
        '%s / %s' % (pet.bh.status()['state'], pet.bh.status()['base']))
    pet.bh.interact('pet')
    for _ in range(int(3 * 30)):
        pet.bh.tick(1 / 30.0)
        pet._tick()
    chk(pet.bh.status()['state'] == 'awake', 'F2 摸一下唤醒',
        pet.bh.status()['state'])

    sec('G · 换一只')
    g0 = json_dump = None
    import json
    g0 = json.dumps(pet.geno, sort_keys=True)
    pet.new_fox()
    g1 = json.dumps(pet.geno, sort_keys=True)
    chk(g0 != g1, 'G1 换只后基因型变了', '')
    pet._tick()
    app.processEvents()
    a3 = grab(pet)
    chk(float((a3[..., 3] > 200).mean()) > 0.08, 'G1 换只后仍能渲染',
        '不透明 %.1f%%' % (float((a3[..., 3] > 200).mean()) * 100))

    sec('J · 清晰度与散步（v1.1）')
    # J1 超采样：渲染分辨率 = 显示尺寸 × ssaa
    disp = int(cfg['base_size'] * cfg['scale'])
    chk(pet.work == int(min(1024, max(256, round(disp * pet.ssaa)))),
        'J1 work = 显示尺寸 × ssaa', 'disp=%d ssaa=%.1f work=%d'
        % (disp, pet.ssaa, pet.work))
    # J2 锐化后处理确实改变图像
    pet._facing = 1
    img_raw, _ = AN.render_frame(pet.spec, 0, [('idle_breath', 0.3)],
                                 size=disp, layers=pet.layers, work=pet.work)
    pet.sharpen = False
    img_off = pet._post(img_raw.copy())
    pet.sharpen = True
    img_on = pet._post(img_raw.copy())
    d = float(np.abs(np.asarray(img_on, np.int16) - np.asarray(img_off, np.int16)).mean())
    chk(d > 0.5, 'J2 锐化改变了输出（且幅度 sane）', '平均差 %.2f' % d)
    # J3 镜像：facing=-1 输出 = 原图水平翻转
    pet.sharpen = False
    img_r = pet._post(img_raw.copy())                       # facing=1
    pet._facing = -1
    img_l = pet._post(img_raw.copy())                       # facing=-1
    pet._facing = 1
    same = np.abs(np.asarray(img_l, np.int16)
                  - np.asarray(img_r.transpose(Image.FLIP_LEFT_RIGHT),
                               np.int16)).max()
    chk(same == 0, 'J3 facing=-1 输出 = 原图镜像', 'max diff %d' % same)
    # J4 walk_fx 已注册且幅度被放大
    import anim as _AN
    _AN.make_walk_action()                                  # 幂等
    p_old = _AN.pose_at_multi([('walk', 0.125)]).get('body', 'translateY')
    p_new = _AN.pose_at_multi([(APP.WALK_AID, 0.125)]).get('body', 'translateY')
    chk(abs(p_new) > abs(p_old) > 0, 'J4 walk_fx 身体起伏幅度放大',
        'walk %.2f → %s %.2f' % (p_old, APP.WALK_AID, p_new))
    chk(_AN.ACTIONS[APP.WALK_AID].get('loop'), 'J4 walk_fx 是循环动作', '')
    # J5 Wanderer 状态机：rest → walk → 到达 → rest
    wd = APP.WD.Wanderer(seed=7, rest=(0.05, 0.1), speed=(300, 300),
                         step=(150, 150))
    walked = 0.0
    x = 400.0
    for _ in range(3000):
        dx, walking = wd.tick(1 / 30.0, x, 100.0, 900.0)
        x += dx
        walked += abs(dx)
        if wd.trips >= 2:
            break
    chk(wd.trips >= 1 and walked > 100, 'J5 散步状态机能走完并返回 rest',
        'trips=%d walked=%.0f' % (wd.trips, walked))
    # J6 边界：目标在界外时被夹住
    wd2 = APP.WD.Wanderer(seed=3, rest=(0.01, 0.02), speed=(500, 500),
                          step=(50, 5000))
    x = 890.0
    for _ in range(400):
        dx, _w = wd2.tick(1 / 30.0, x, 100.0, 900.0)
        x += dx
        if x > 900.0:
            break
    chk(x <= 900.0 + 1e-6, 'J6 散步不越出屏幕边界', 'x=%.1f' % x)
    # J7 暂停：pause 后不走
    wd3 = APP.WD.Wanderer(seed=11, rest=(0.01, 0.01))
    wd3.pause(10.0)
    dx, walking = wd3.tick(0.5, 400.0, 100.0, 900.0)
    chk(dx == 0 and not walking, 'J7 交互暂停期间不出门', '')
    # J8 睡着时 _wander_step 不走
    pet.bh._doze()
    for _ in range(int(6 * 30)):
        pet.bh.tick(1 / 30.0)
    dx, walking = pet._wander_step(1 / 30.0)
    chk(not walking and dx == 0, 'J8 睡着时散步挂起',
        '%s base=%s' % (pet.bh.status()['state'], pet.bh.status()['base']))
    pet.bh.wake()
    for _ in range(int(2.5 * 30)):
        pet.bh.tick(1 / 30.0)
    # J9 小尺寸渲染不糊：work 下限保护
    pet.set_scale(0.5)
    chk(pet.work == 256, 'J9 缩到最小也保底 work=256', 'work=%d' % pet.work)
    pet.set_scale(1.0)
    # J10 自适应降档：帧耗时持续超预算时 ssaa 自动下调
    pet._frame_ms = [100.0] * 30        # 伪造 30 帧高耗时
    pet.ssaa = 2.0
    pet._tick()
    chk(pet.ssaa == 1.5 and pet._ssaa_floor_hit,
        'J10 超帧率预算自动降 ssaa', 'ssaa=%.1f work=%d' % (pet.ssaa, pet.work))
    # J11 只是小幅超支（35ms < 41.7ms 预算）不该降档，否则清晰度白给
    pet.ssaa = 2.0
    pet._apply_size()
    pet.layers = AN.get_layers(pet.spec, pet.work)
    pet._ssaa_floor_hit = False
    pet._frame_ms = [35.0] * 30
    pet._tick()
    chk(pet.ssaa == 2.0 and not pet._ssaa_floor_hit,
        'J11 35ms 在 24fps 预算内不降档', 'ssaa=%.1f' % pet.ssaa)
    pet._frame_ms = [5.0] * 30
    pet.ssaa = 2.0
    pet._apply_size()
    pet.layers = AN.get_layers(pet.spec, pet.work)
    pet._ssaa_floor_hit = False

    sec('H · 配置持久化')
    pet.move(123, 456)
    pet._save_pos()
    cfg2, _ = CFG.load(state_path)
    chk(cfg2['x'] == 123 and cfg2['y'] == 456, 'H1 位置已存盘',
        '%s,%s' % (cfg2['x'], cfg2['y']))
    chk(cfg2.get('geno') is not None, 'H1 基因型已存盘', '')
    # JSON 往返会把 ('K','k') 变成 ['K','k']，读回必须还原成 tuple
    chk(all(isinstance(v, tuple) for v in cfg2['geno'].values()),
        'H1 基因型读回是 tuple（不是 list）',
        str(type(list(cfg2['geno'].values())[0]).__name__))
    chk(PH(cfg2['geno']) == PH(pet.geno), 'H1 读回后表型与存盘前一致', '')
    chk(CFG.clamp_scale(99) == 3.0 and CFG.clamp_scale(0.01) == 0.4,
        'H2 缩放夹到 [0.4, 3.0]', '')
    # 坏配置不能让桌宠起不来
    open(state_path, 'w').write('{ 这不是 JSON')
    cfg3, _ = CFG.load(state_path)
    chk(cfg3['x'] is None, 'H3 坏配置退回默认值', 'x=%s' % cfg3['x'])
    # v1.0 老状态里 base_size=256（旧默认），v1.1 一次性迁到 168
    with open(state_path, 'w', encoding='utf-8') as fh:
        json.dump({'base_size': 256, 'x': 10, 'y': 20}, fh)
    cfg4, _ = CFG.load(state_path)
    chk(cfg4['base_size'] == 168, 'H4 旧默认 base_size=256 迁移到 168',
        'base_size=%s' % cfg4['base_size'])
    with open(state_path, 'w', encoding='utf-8') as fh:
        json.dump({'base_size': 200, 'x': 10, 'y': 20}, fh)
    cfg5, _ = CFG.load(state_path)
    chk(cfg5['base_size'] == 200, 'H4 用户自定义的 base_size 不被动',
        'base_size=%s' % cfg5['base_size'])
    try:
        os.remove(state_path)
    except OSError:
        pass

    sec('I · 出一张成品预览')
    os.makedirs(DOCS, exist_ok=True)
    pet.set_scale(1.0)
    pet.bh = APP.BH.Behavior(seed=2026, doze_after=0)
    for _ in range(45):
        pet.bh.tick(1 / 30.0)
    pet.bh.interact('pet')
    for _ in range(20):
        pet.bh.tick(1 / 30.0)
    pet._tick()
    app.processEvents()
    out = os.path.join(DOCS, 'pet-preview.png')
    pet.grab().save(out)
    chk(os.path.isfile(out), 'I1 预览图已出', os.path.basename(out))

    print('\n'.join(LINES))
    print('')
    print('通过 %d / %d' % (PASS, PASS + FAIL))
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
