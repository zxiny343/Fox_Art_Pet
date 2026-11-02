# -*- coding: utf-8 -*-
"""拆分单帧耗时：渲染 / 锐化 / PIL→QPixmap 各占多少。"""
import os
import sys
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(ROOT, 'sim'), os.path.join(ROOT, 'pet')):
    sys.path.insert(0, p)

from PIL import ImageFilter                        # noqa: E402
from PySide6.QtWidgets import QApplication         # noqa: E402

import anim as AN                                  # noqa: E402
import artmap as AM                                # noqa: E402
import app as APP                                  # noqa: E402
from fox_ecosystem_sim import phenotype as PH      # noqa: E402
import fox_ecosystem_sim as M                      # noqa: E402

# QPixmap 必须有 QGuiApplication 实例，否则 Qt 直接 qFatal 静默退出（exit 0）
_qapp = QApplication.instance() or QApplication(sys.argv)

w = M.World(dict(M.TUNED_V3_PARAMS), 20261101)
spec = AM.to_art(PH(dict(w.foxes[sorted(w.alive_ids)[0]].geno)))
SIZE = 168

for work in (256, 336):
    L = AN.get_layers(spec, work)
    N = 25
    for i in range(5):
        AN.render_frame(spec, 0, [('idle_breath', 0.3)], size=SIZE, layers=L, work=work)

    t0 = time.time()
    for i in range(N):
        img, _ = AN.render_frame(spec, 0, [('idle_breath', (i % 13) / 13.0),
                                           ('idle_tail_sway', 0.4)],
                                 size=SIZE, layers=L, work=work)
    t_render = (time.time() - t0) / N

    t0 = time.time()
    for i in range(N):
        sharp = img.filter(ImageFilter.UnsharpMask(radius=1.0, percent=55,
                                                   threshold=2))
    t_sharp = (time.time() - t0) / N

    t0 = time.time()
    for i in range(N):
        APP.pil_to_qpixmap(sharp)
    t_pix = (time.time() - t0) / N

    print('work=%d: render %.1f + 锐化 %.1f + QPixmap %.1f = %.1f ms'
          % (work, t_render * 1000, t_sharp * 1000, t_pix * 1000,
             (t_render + t_sharp + t_pix) * 1000))
