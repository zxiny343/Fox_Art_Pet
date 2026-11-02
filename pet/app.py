# -*- coding: utf-8 -*-
"""幻想小狐狸桌宠 —— 桌面外壳 MVP（PySide6）。

用法：
    python pet/app.py                  # 正常启动
    python pet/app.py --new            # 换一只新的狐狸
    python pet/app.py --no-top         # 不置顶（调试用）
    python pet/app.py --fps 60

窗口：无边框 + 每像素透明 + 可选置顶 + 不出现在任务栏。
交互：左键拖拽 / 单击摸一摸 / 滚轮缩放 / 右键菜单 / 托盘图标。
"""

import argparse
import atexit
import json
import os
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, 'sim'), os.path.dirname(os.path.abspath(__file__))):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from PySide6.QtCore import Qt, QPoint, QTimer, QElapsedTimer, Signal  # noqa: E402
from PySide6.QtGui import (QImage, QPixmap, QPainter, QIcon,           # noqa: E402
                           QAction, QCursor)                           # noqa: E402
from PySide6.QtWidgets import (QApplication, QWidget, QMenu,            # noqa: E402
                               QSystemTrayIcon, QMessageBox)            # noqa: E402
from PIL import Image, ImageFilter                                      # noqa: E402

import anim as AN                                                       # noqa: E402
import artmap as AM                                                     # noqa: E402
import render_kernel as RK                                              # noqa: E402
import config as CFG                                                    # noqa: E402
import behavior as BH                                                   # noqa: E402
import wander as WD                                                     # noqa: E402
from fox_ecosystem_sim import phenotype as PH                           # noqa: E402

# 程序化增强版 walk（原始 walk 的腿部通道没有 rig，缩到桌宠尺寸像静止滑行）
WALK_AID = AN.make_walk_action()

LOG_PATH = os.path.join(ROOT, 'pet.log')


def _log(cfg, msg):
    """轻量事件日志：启动、退出原因、降档。写 pet.log（已 gitignore）。

    桌宠是长期后台进程，之前两次「跑了几个小时后 exit 0 消失」查不到原因，
    所以把退出路径都记一笔：正常退出、关窗、未捕获异常、Qt 循环结束。
    """
    if not (cfg or {}).get('log', True):
        return
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write('%s  %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg))
    except (IOError, OSError):
        pass


def pick_fox(idx=0, seed=20261101):
    """从 v0.6 生态里取第 idx 只活体（分布真实，不是均匀随机基因型）。"""
    import fox_ecosystem_sim as M
    w = M.World(dict(M.TUNED_V3_PARAMS), seed)
    ids = sorted(w.alive_ids)
    return dict(w.foxes[ids[idx % len(ids)]].geno)


def pil_to_qpixmap(im):
    """PIL RGBA → QPixmap。

    QImage 不持有 data，必须保证 bytes 活着；这里转成 QPixmap 后
    Qt 内部会拷一份，函数返回后 data 被回收是安全的。
    """
    if im.mode != 'RGBA':
        im = im.convert('RGBA')
    data = im.tobytes('raw', 'RGBA')
    qimg = QImage(data, im.width, im.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


class FoxPet(QWidget):
    """桌宠窗口。"""

    sig_state = Signal(str)      # 状态变化，给托盘提示用

    def __init__(self, cfg, state_path, fox_idx=0):
        super().__init__()
        self.cfg = cfg
        self.state_path = state_path
        self.fox_idx = fox_idx

        flags = Qt.FramelessWindowHint | Qt.Tool
        if cfg['always_top']:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setWindowTitle('幻想小狐狸')

        self.scale = CFG.clamp_scale(cfg['scale'])
        self.base = int(cfg['base_size'])
        self.ssaa = CFG.clamp_ssaa(cfg.get('ssaa', 2.0))
        self.sharpen = bool(cfg.get('sharpen', True))
        # 显示尺寸（窗口大小）
        self._apply_size()

        # 个体
        self.geno = cfg.get('geno') or pick_fox(fox_idx, cfg.get('seed', 20261101))
        self.pheno = PH(self.geno)
        self.spec = AM.to_art(self.pheno)
        self.layers = AN.get_layers(self.spec, self.work)

        # 行为
        self.bh = BH.Behavior(seed=cfg.get('seed', 20261101) + fox_idx,
                              doze_after=cfg.get('doze_after', 90.0))

        # 散步
        self.wander = WD.Wanderer(seed=(cfg.get('seed', 20261101) + fox_idx) * 7 + 1,
                                  enabled=bool(cfg.get('wander', True)))
        self._facing = 1            # +1 原图朝向 / -1 水平镜像

        # 交互状态
        self._drag_off = None
        self._press_pos = None
        self._press_t = 0.0
        self._moved = False

        # 帧循环
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.clock = QElapsedTimer()
        self.clock.start()
        self._last_ms = 0
        self._fps_acc = 0.0
        self._fps_n = 0
        self.fps = 0.0
        self._pix = None
        self._frame_ms = []         # 自适应降档的滚动帧耗时样本
        self._warm_skip = 60        # 前 60 帧不计样本（建层/首帧冷启动）
        self._ssaa_floor_hit = False

        self._place_initial()
        self.timer.start(int(1000.0 / max(1, cfg.get('fps', 30))))

    # ------------------------------------------------------------------
    # 尺寸与清晰度
    # ------------------------------------------------------------------
    def _apply_size(self):
        """窗口 = 显示尺寸；渲染分辨率 = 显示尺寸 × ssaa（超采样抗糊）。

        缩小后发糊的根源是「渲染分辨率跟着显示尺寸一起缩」。这里把渲染
        固定在显示尺寸的 ssaa 倍（默认 2×，LANCZOS 缩回），实测 168px 显示
        时 work=336 约 20ms/帧（49fps），PSNR 与 512 渲染几乎持平。
        """
        disp = int(self.base * self.scale)
        self.work = int(min(1024, max(256, round(disp * self.ssaa))))
        # 画布向下扩了 192px 给「坐下/趴下/睡觉」的下沉留地方，
        # 所以窗口不是正方形，高 = 宽 × 1.1875（见 anim.ASPECT）
        self.setFixedSize(disp, int(disp * AN.ASPECT))

    # ------------------------------------------------------------------
    # 位置
    # ------------------------------------------------------------------
    def _place_initial(self):
        scr = QApplication.primaryScreen()
        ag = scr.availableGeometry()
        x, y = self.cfg.get('x'), self.cfg.get('y')
        w = self.width()
        if x is None or y is None:
            x = ag.right() - w - 40
            y = ag.bottom() - self.height() - 60
        self.move(int(x), int(y))
        self._clamp_into_screen()

    def _clamp_into_screen(self):
        """保证整只狐狸在屏幕内（换显示器/改分辨率后不会飘到外面）。"""
        scr = QApplication.screenAt(self.frameGeometry().center()) \
            or QApplication.primaryScreen()
        ag = scr.availableGeometry()
        x = min(max(self.x(), ag.left()), ag.right() - self.width() + 1)
        y = min(max(self.y(), ag.top()), ag.bottom() - self.height() + 1)
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)

    # ------------------------------------------------------------------
    # 渲染
    # ------------------------------------------------------------------
    def _tick(self):
        now = self.clock.elapsed()
        dt = (now - self._last_ms) / 1000.0
        self._last_ms = now
        if dt > 0.5:            # 休眠/卡顿后回来，别让动画瞬移
            dt = 1.0 / self.cfg.get('fps', 30)
        if dt <= 0:
            return

        self.bh.tick(dt)

        # 散步：决定这一帧窗口平移多少（可能为 0）
        dx, walking = self._wander_step(dt)

        t0 = time.time()
        img, _ = AN.render_frame(self.spec, 0, self.bh.items(),
                                 size=int(self.base * self.scale),
                                 layers=self.layers, work=self.work)
        img = self._post(img)
        self._pix = pil_to_qpixmap(img)
        self.update()

        self._fps_acc += time.time() - t0
        self._fps_n += 1
        if self._fps_n >= 30:
            self.fps = 1.0 / (self._fps_acc / self._fps_n)
            self._fps_acc = 0.0
            self._fps_n = 0

        # 自适应降档：渲染跟不上目标帧率就降超采样（只降不升，避免震荡）。
        # 帧耗时 ~ O(work²)，scale 大时 2× 超采样可能把 24fps 拖垮。
        # 注意：前 60 帧不计入（换只/缩放要重建部件层，1.3s 的冷峰会误判成"太慢"），
        # 用中位数而不是均值，抗偶发卡顿。
        if self._warm_skip > 0:
            self._warm_skip -= 1
        else:
            self._frame_ms.append((time.time() - t0) * 1000.0)
        if len(self._frame_ms) >= 30:
            avg = sorted(self._frame_ms)[len(self._frame_ms) // 2]
            self._frame_ms = []
            budget = 1000.0 / max(1.0, float(self.cfg.get('fps', 24)))
            if avg > budget and self.ssaa > 1.05:
                self.ssaa = max(1.0, round(self.ssaa - 0.5, 2))
                self._ssaa_floor_hit = True
                # 只改运行时，不写进 cfg/state：否则下次启动永久从低倍率开始
                self._apply_size()
                self.layers = AN.get_layers(self.spec, self.work)
                self._warm_skip = 30           # 重建层后再跳过一批样本
                msg = ('帧耗时中位 %.0fms 超预算 %.0fms → ssaa 降到 %.1f (work=%d)'
                       % (avg, budget, self.ssaa, self.work))
                print('[pet] ' + msg)
                _log(self.cfg, msg)

    def _post(self, img):
        """渲染后处理：朝向镜像 + 轻度锐化（自检也直接测这个方法）。"""
        if self._facing < 0:            # 朝向镜像（画布左右对称，翻转安全）
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        if self.sharpen:                # 抵消 LANCZOS 缩小的偏软
            img = img.filter(ImageFilter.UnsharpMask(radius=1.0, percent=55,
                                                     threshold=2))
        return img

    def _wander_step(self, dt):
        """散步编排：返回 (dx, walking)。

        允许走的前提：没在拖拽、清醒、base 正闲着（idle 或已在 walk）。
        正在播交互动作（happy_wag / eat…）或睡着时不出门。
        """
        if self._drag_off is not None:
            self.wander.pause(6.0)
            return 0.0, False

        scr = QApplication.screenAt(self.frameGeometry().center()) \
            or QApplication.primaryScreen()
        ag = scr.availableGeometry()
        x_min = ag.left() + 6
        x_max = ag.right() - self.width() - 5
        dx, walking = self.wander.tick(dt, self.x(), x_min, x_max)

        if walking:
            if self.bh.base == WALK_AID or \
                    (self.bh.state == 'awake'
                     and self.bh.base == BH.Behavior.BASE_IDLE):
                if self.bh.base != WALK_AID:
                    self.bh._set_base(WALK_AID, None)
                if dx:
                    # 同步朝向：wander.facing 在 tick 里按 dx 方向设好，
                    # 但之前漏了把它传到 self._facing → 镜像永远不发生，
                    # 往左走时原图朝右不变，看起来像倒退着走。
                    self._facing = self.wander.facing
                    self.move(int(self.x() + dx), self.y())
                return dx, True
            self.wander.pause(2.0)      # 忙别的事，稍后再说
            return 0.0, False

        if self.bh.base == WALK_AID:    # 走完了 → 回 idle
            self.bh._set_base(BH.Behavior.BASE_IDLE, None)
        return 0.0, False

    def paintEvent(self, e):
        if self._pix is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.drawPixmap(0, 0, self._pix)
        p.end()

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self._menu(e.globalPosition().toPoint() if hasattr(e, 'globalPosition')
                       else e.globalPos())
            return
        if e.button() != Qt.LeftButton:
            return
        gp = e.globalPosition().toPoint() if hasattr(e, 'globalPosition') else e.globalPos()
        self._drag_off = gp - self.frameGeometry().topLeft()
        self._press_pos = gp
        self._press_t = time.time()
        self._moved = False
        e.accept()

    def mouseMoveEvent(self, e):
        if self._drag_off is None:
            return
        gp = e.globalPosition().toPoint() if hasattr(e, 'globalPosition') else e.globalPos()
        if self._press_pos and (gp - self._press_pos).manhattanLength() > 4:
            if not self._moved:
                self._moved = True
                self.bh.interact('drag_start')
        if self._moved:
            self.move(gp - self._drag_off)
        e.accept()

    def mouseReleaseEvent(self, e):
        if self._drag_off is None:
            return
        off, moved = self._drag_off, self._moved
        self._drag_off = None
        self._press_pos = None
        if moved:
            self.bh.interact('drag_end')
            self._clamp_into_screen()
            self._save_pos()
        else:
            # 没移动 = 单击 = 摸一摸
            self.bh.interact('pet')
            self.wander.pause(8.0)
            self.sig_state.emit('摸一摸')
        e.accept()

    def mouseDoubleClickEvent(self, e):
        self.bh.interact('bounce')
        self.wander.pause(8.0)
        e.accept()

    def wheelEvent(self, e):
        d = e.angleDelta().y()
        if not d:
            return
        self.set_scale(self.scale * (1.12 if d > 0 else 1.0 / 1.12))
        e.accept()

    def set_scale(self, s):
        s = CFG.clamp_scale(s)
        if abs(s - self.scale) < 1e-3:
            return
        cx, cy = self.geometry().center().x(), self.geometry().bottom()
        self.scale = s
        self._apply_size()
        self.layers = AN.get_layers(self.spec, self.work)
        # 以"脚下"为锚缩放，视觉上不会乱跳
        self.move(cx - self.width() // 2, cy - self.height())
        self._clamp_into_screen()
        self.cfg['scale'] = s
        self._save_pos()

    def _save_pos(self):
        self.cfg['x'], self.cfg['y'] = self.x(), self.y()
        self.cfg['scale'] = self.scale
        CFG.save(self.cfg, self.state_path)

    def _menu(self, pos):
        m = QMenu(self)
        acts = [
            ('摸一摸', lambda: self._do('pet')),
            ('喂食', lambda: self._do('feed')),
            ('喝水', lambda: self._do('drink')),
            ('伸懒腰', lambda: self._do('stretch')),
            ('嚎叫', lambda: self._do('howl')),
            (None, None),
            ('散步：开' if not self.wander.enabled else '散步：关',
             self.toggle_wander),
            ('换一只', self.new_fox),
            ('睡一觉', lambda: self.bh.interact('pet') if False
             else self._force_sleep()),
            (None, None),
            ('置顶', self.toggle_top),
            ('鼠标穿透', self.toggle_through),
            (None, None),
            ('退出', self.quit),
        ]
        for label, fn in acts:
            if label is None:
                m.addSeparator()
                continue
            a = QAction(label, self)
            a.triggered.connect(fn)
            m.addAction(a)
        m.exec(pos)

    def _do(self, kind):
        """菜单/托盘触发的交互：先让散步停一停。"""
        self.wander.pause(8.0)
        self.bh.interact(kind)

    def toggle_wander(self):
        self.wander.enabled = not self.wander.enabled
        if not self.wander.enabled:
            self.wander.pause(0.0)
        self.cfg['wander'] = self.wander.enabled
        CFG.save(self.cfg, self.state_path)

    def _force_sleep(self):
        if self.bh.state == 'asleep':
            self.bh.wake()
        else:
            self.bh._doze()

    def toggle_top(self):
        self.cfg['always_top'] = not self.cfg['always_top']
        was = self.isVisible()
        flags = Qt.FramelessWindowHint | Qt.Tool
        if self.cfg['always_top']:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        if was:
            self.show()
        CFG.save(self.cfg, self.state_path)

    def toggle_through(self):
        self.cfg['click_through'] = not self.cfg['click_through']
        self.setAttribute(Qt.WA_TransparentForMouseEvents,
                          self.cfg['click_through'])
        CFG.save(self.cfg, self.state_path)

    def new_fox(self):
        self.fox_idx += 1
        self.geno = pick_fox(self.fox_idx, self.cfg.get('seed', 20261101))
        self.cfg['geno'] = CFG.norm_geno(self.geno)
        self.pheno = PH(self.geno)
        self.spec = AM.to_art(self.pheno)
        self.layers = AN.get_layers(self.spec, self.work)
        self.bh = BH.Behavior(seed=self.cfg.get('seed', 20261101) + self.fox_idx,
                              doze_after=self.cfg.get('doze_after', 90.0))
        CFG.save(self.cfg, self.state_path)
        self.sig_state.emit('换了一只新狐狸')

    def quit(self):
        self._save_pos()
        # 记调用链：能区分「右键菜单」「托盘菜单」「程序内部」三种来源，
        # 之前两次「跑几小时后自己消失」就是缺这条线索才查不出来。
        chain = ' <- '.join('%s:%d %s' % (os.path.basename(f.filename), f.lineno,
                                          f.name)
                            for f in traceback.extract_stack()[-4:-1])
        _log(self.cfg, '退出：quit() 调用链 %s' % chain)
        QApplication.quit()

    def closeEvent(self, e):
        self._save_pos()
        _log(self.cfg, '退出：窗口关闭')
        super().closeEvent(e)


def main(argv=None):
    ap = argparse.ArgumentParser(description='幻想小狐狸桌宠')
    ap.add_argument('--new', action='store_true', help='换一只新狐狸')
    ap.add_argument('--no-top', action='store_true', help='不置顶')
    ap.add_argument('--fps', type=int, default=None)
    ap.add_argument('--state', type=str, default=None, help='状态文件路径')
    ap.add_argument('--once', action='store_true',
                    help='渲染一帧就退出（自检用）')
    args = ap.parse_args(argv)

    cfg, state_path = CFG.load(args.state)
    if args.no_top:
        cfg['always_top'] = False
    if args.fps:
        cfg['fps'] = args.fps
    if args.new:
        cfg['geno'] = None

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 退出原因埋点：任何一条路径停下来都能在 pet.log 里查到
    def _hook(exc_type, exc, tb):
        _log(cfg, '未捕获异常：\n' + ''.join(
            traceback.format_exception(exc_type, exc, tb)))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _hook
    app.aboutToQuit.connect(lambda: _log(cfg, '退出：Qt 事件循环结束'))
    atexit.register(lambda: _log(cfg, '退出：进程结束（atexit）'))

    pet = FoxPet(cfg, state_path, fox_idx=(hash(time.time()) % 997) if args.new else 0)
    if cfg['click_through']:
        pet.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    pet.show()
    _log(cfg, '启动 pid=%d 显示 %dx%d work=%d fps=%s ssaa=%.1f wander=%s'
         % (os.getpid(), pet.width(), pet.height(), pet.work,
            cfg.get('fps'), pet.ssaa, pet.wander.enabled))

    if args.once:
        pet._tick()
        print('OK  %dx%d  fps-capable  work=%d  state=%s'
              % (pet.width(), pet.height(), pet.work, pet.bh.status()['state']))
        return 0

    # 托盘
    icon = QIcon(pil_to_qpixmap(
        AN.render_frame(pet.spec, 0, ['idle_breath'], size=64)[0]))
    tray = QSystemTrayIcon(icon, app)
    tray.setToolTip('幻想小狐狸')

    def _mk(title, fn):
        a = QAction(title, app)
        a.triggered.connect(fn)
        return a

    tm = QMenu()
    tm.addAction(_mk('摸一摸', lambda: pet._do('pet')))
    tm.addAction(_mk('喂食', lambda: pet._do('feed')))
    tm.addSeparator()
    tm.addAction(_mk('散步：开' if not pet.wander.enabled else '散步：关',
                    pet.toggle_wander))
    tm.addAction(_mk('换一只', pet.new_fox))
    tm.addAction(_mk('睡一觉 / 唤醒', pet._force_sleep))
    tm.addSeparator()
    tm.addAction(_mk('显示 / 隐藏',
                    lambda: pet.setVisible(not pet.isVisible())))
    tm.addAction(_mk('退出', pet.quit))
    tray.setContextMenu(tm)
    tray.activated.connect(lambda r: pet.bh.interact('pet')
                           if r == QSystemTrayIcon.Trigger else None)
    tray.show()

    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
