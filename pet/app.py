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
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, 'sim'), os.path.dirname(os.path.abspath(__file__))):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from PySide6.QtCore import Qt, QPoint, QTimer, QElapsedTimer, Signal  # noqa: E402
from PySide6.QtGui import (QImage, QPixmap, QPainter, QIcon,           # noqa: E402
                           QAction, QCursor)
from PySide6.QtWidgets import (QApplication, QWidget, QMenu,            # noqa: E402
                               QSystemTrayIcon, QMessageBox)
from PIL import Image                                                   # noqa: E402

import anim as AN                                                       # noqa: E402
import artmap as AM                                                     # noqa: E402
import render_kernel as RK                                              # noqa: E402
import config as CFG                                                    # noqa: E402
import behavior as BH                                                   # noqa: E402
from fox_ecosystem_sim import phenotype as PH                           # noqa: E402


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
        self.work = max(int(self.base * self.scale), 256)
        # 画布向下扩了 192px 给「坐下/趴下/睡觉」的下沉留地方，
        # 所以窗口不是正方形，高 = 宽 × 1.1875（见 anim.ASPECT）
        self.setFixedSize(int(self.base * self.scale),
                          int(self.base * self.scale * AN.ASPECT))

        # 个体
        self.geno = cfg.get('geno') or pick_fox(fox_idx, cfg.get('seed', 20261101))
        self.pheno = PH(self.geno)
        self.spec = AM.to_art(self.pheno)
        self.layers = AN.get_layers(self.spec, self.work)

        # 行为
        self.bh = BH.Behavior(seed=cfg.get('seed', 20261101) + fox_idx,
                              doze_after=cfg.get('doze_after', 90.0))

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

        self._place_initial()
        self.timer.start(int(1000.0 / max(1, cfg.get('fps', 30))))

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
        t0 = time.time()
        img, _ = AN.render_frame(self.spec, 0, self.bh.items(),
                                 size=int(self.base * self.scale),
                                 layers=self.layers, work=self.work)
        self._pix = pil_to_qpixmap(img)
        self.update()

        self._fps_acc += time.time() - t0
        self._fps_n += 1
        if self._fps_n >= 30:
            self.fps = 1.0 / (self._fps_acc / self._fps_n)
            self._fps_acc = 0.0
            self._fps_n = 0

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
            self.sig_state.emit('摸一摸')
        e.accept()

    def mouseDoubleClickEvent(self, e):
        self.bh.interact('bounce')
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
        self.work = max(int(self.base * self.scale), 256)
        self.setFixedSize(int(self.base * s), int(self.base * s * AN.ASPECT))
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
            ('摸一摸', lambda: self.bh.interact('pet')),
            ('喂食', lambda: self.bh.interact('feed')),
            ('喝水', lambda: self.bh.interact('drink')),
            ('伸懒腰', lambda: self.bh.interact('stretch')),
            ('嚎叫', lambda: self.bh.interact('howl')),
            (None, None),
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
        QApplication.quit()

    def closeEvent(self, e):
        self._save_pos()
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

    pet = FoxPet(cfg, state_path, fox_idx=(hash(time.time()) % 997) if args.new else 0)
    if cfg['click_through']:
        pet.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    pet.show()

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
    tm.addAction(_mk('摸一摸', lambda: pet.bh.interact('pet')))
    tm.addAction(_mk('喂食', lambda: pet.bh.interact('feed')))
    tm.addSeparator()
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
