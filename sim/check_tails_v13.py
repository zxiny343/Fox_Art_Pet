# -*- coding: utf-8 -*-
"""v1.3 多尾素材的 socket 覆盖体检。

对每种尾型做同参数组装，检查尾巴根部区域（socket bbox）是否
出现「透明洞」或「异常黑块」，并输出接缝区放大拼图供人工复核。
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', '_art_v1.3', 'delivery', 'Fox_Art', 'tools'))
import run_assemble as RA  # noqa: E402

MASTER = Image.open(os.path.join(os.path.dirname(RA.__file__), '..', 'assets', 'master', 'Base', 'fox_base_blue_q4@1024.png')).convert('RGBA')
MASTER_RGB = np.asarray(MASTER)[..., :3].astype(float)
BB = (208, 298, 503, 506)      # tail_socket.json 的 socketBBox
PAD = (150, 240, 620, 620)     # 观察窗：比 socket 大一圈，能看见缺口入体
TAILS = ['normal', 'twin', 'triple', 'quad', 'quint', 'nine', 'thin', 'short']

COL = ['%s' % t for t in TAILS]
rows = []
crops = []
for t in TAILS:
    img, used = RA.assemble(coat='blue', tail=t, ear='large', eye='round_blue',
                            verbose=False)
    if used.get('pocketRepairPx'):
        print('   [%s] pocketRepair %s px' % (t, used['pocketRepairPx']))
    a = np.asarray(img.convert('RGBA'))
    # 严格判据：母版狐狸轮廓内、组装后却透明的像素 = 真漏洞
    body = np.asarray(MASTER.split()[3]) > 8
    hole_map = body & (a[..., 3] < 8)
    hole = int(hole_map.sum())
    # 黑块：轮廓内近黑且不在母版黑块位置上的新增像素
    luma = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    m_luma = 0.299 * MASTER_RGB[..., 0] + 0.587 * MASTER_RGB[..., 1] + 0.114 * MASTER_RGB[..., 2]
    dark_new = int((body & (a[..., 3] > 200) & (luma < 45) & ~(m_luma < 45)).sum())
    rows.append((t, int(body.sum()), hole, dark_new))
    bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
    bg.alpha_composite(img)
    crops.append(bg.convert('RGB').crop(PAD).resize((320, 260), Image.LANCZOS))

print('%-8s %10s %8s %10s' % ('tail', '轮廓px', '真漏洞', '新增黑块'))
for t, n, h, d in rows:
    flag = ''
    if h > 0:
        flag += ' <-洞'
    if d > 60:
        flag += ' <-黑块'
    print('%-8s %8d %8d %8d%s' % (t, n, h, d, flag))

sheet = Image.new('RGB', (320 * 4, 300 * 2 + 10), (250, 250, 250))
dr = ImageDraw.Draw(sheet)
for i, (t, c) in enumerate(zip(TAILS, crops)):
    x, y = (i % 4) * 320, (i // 4) * 300
    sheet.paste(c, (x, y + 22))
    dr.text((x + 8, y + 6), 'tail_%s' % t, fill=(20, 20, 20))
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs',
                   'tail-socket-check-v13.png')
sheet.save(out)
print('拼图 ->', os.path.abspath(out))
