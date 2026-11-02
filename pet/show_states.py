# -*- coding: utf-8 -*-
"""出一张桌宠状态对照图：待机 / 摇尾巴 / 睡觉 / 被拖起。

离屏渲染，不打扰桌面。用来一眼确认行为状态机接对了。
"""

import os
import sys
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, 'sim'), os.path.dirname(os.path.abspath(__file__))):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np                                       # noqa: E402
from PIL import Image, ImageDraw, ImageFont              # noqa: E402
from PySide6.QtWidgets import QApplication               # noqa: E402
from PySide6.QtGui import QImage as _QI                  # noqa: E402

import app as APP                                        # noqa: E402
import config as CFG                                     # noqa: E402
import behavior as BH                                    # noqa: E402
import anim as AN                                        # noqa: E402

DOCS = os.path.join(ROOT, 'docs')
BG = (246, 246, 249)


def font(sz, bold=False):
    for p in (r'C:\Windows\Fonts\msyhbd.ttc' if bold else r'C:\Windows\Fonts\msyh.ttc',
              r'C:\Windows\Fonts\simhei.ttf'):
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, sz)
            except OSError:
                pass
    return ImageFont.load_default()


def grab_rgba(pet):
    im = pet.grab().toImage().convertToFormat(_QI.Format.Format_RGBA8888)
    w, h = im.width(), im.height()
    a = np.frombuffer(bytes(im.constBits()), dtype=np.uint8).reshape(h, w, 4)
    return np.ascontiguousarray(a)


def checker(size, cell=16):
    """棋盘格背景，用来证明透明区是真的透明。"""
    y, x = np.mgrid[0:size, 0:size]
    c = ((x // cell) + (y // cell)) % 2
    a = np.where(c == 0, 232, 214).astype(np.uint8)
    return np.dstack([a, a, a, np.full_like(a, 255)])


def main():
    application = QApplication.instance() or QApplication(sys.argv)
    cfg, _ = CFG.load(None)
    cfg['x'], cfg['y'] = 200, 200
    pet = APP.FoxPet(cfg, os.path.join(ROOT, '_pet_test_state.json'))
    pet.show()

    panels = []

    # 1. 待机（跑 2 秒，让呼吸/摆尾/眨眼都进入状态）
    pet.bh = BH.Behavior(seed=101, doze_after=0)
    for _ in range(60):
        pet.bh.tick(1 / 30.0)
    # offscreen 下第一次 paint 需要多轮事件循环才生效，否则抓到空帧
    for _ in range(3):
        pet._tick()
        application.processEvents()
    panels.append(('待机 idle_breath + 尾巴轻摆', grab_rgba(pet)))

    # 2. 摸一摸 → 摇尾巴
    pet.bh.interact('pet')
    for _ in range(20):
        pet.bh.tick(1 / 30.0)
    pet._tick()
    application.processEvents()
    panels.append(('摸一摸 → happy_wag', grab_rgba(pet)))

    # 3. 睡觉
    pet.bh = BH.Behavior(seed=101, doze_after=1.0)
    for _ in range(int(8 * 30)):
        pet.bh.tick(1 / 30.0)
    pet._tick()
    application.processEvents()
    panels.append(('90 秒没理它 → sleep（%s）' % pet.bh.status()['state'],
                   grab_rgba(pet)))

    # 4. 被拖起
    pet.bh.interact('pet')
    for _ in range(int(3 * 30)):
        pet.bh.tick(1 / 30.0)
    pet.bh.interact('drag_start')
    for _ in range(15):
        pet.bh.tick(1 / 30.0)
    pet._tick()
    application.processEvents()
    panels.append(('拖起来 → drag', grab_rgba(pet)))

    # 排版
    n = len(panels)
    sz = panels[0][1].shape[0]
    tile = 250
    W = tile * n + 14 * (n + 1)
    H = 54 + tile + 34 + 20
    sheet = Image.new('RGB', (W, H), BG)
    dr = ImageDraw.Draw(sheet)
    dr.text((14, 12), '桌宠四种状态（棋盘格 = 窗口透明区，直接透到桌面）',
            font=font(16, True), fill=(20, 20, 24))
    dr.text((14, 34), '渲染 %d fps · 256×256 · PySide6 透明置顶窗'
            % int(pet.fps or 96), font=font(11), fill=(110, 110, 120))

    for i, (label, a) in enumerate(panels):
        x = 14 + i * (tile + 14)
        rgb = np.asarray(Image.fromarray(a).resize((tile, tile), Image.LANCZOS))
        bg = checker(tile)[..., :3].astype(float)
        al = (rgb[..., 3:].astype(float) / 255.0)
        comp = (rgb[..., :3] * al + bg * (1 - al)).astype(np.uint8)
        t = Image.fromarray(comp)
        sheet.paste(t, (x, 54))
        dr.rectangle([x, 54, x + tile - 1, 54 + tile - 1], outline=(205, 205, 212))
        dr.text((x + 2, 54 + tile + 8), label, font=font(12), fill=(40, 40, 48))

    out = os.path.join(DOCS, 'pet-states.png')
    sheet.save(out)
    print('->', out, sheet.size)
    return 0


if __name__ == '__main__':
    sys.exit(main())
