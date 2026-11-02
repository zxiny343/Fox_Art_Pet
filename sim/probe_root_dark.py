# -*- coding: utf-8 -*-
"""R2 的量化指标探索：根部「成片暗斑」怎么量。

目视判据是「1× 下读作一块黑斑」，对应的量化形式是：
把亮度图做中等半径模糊（抹掉单条描边，只留成片明暗），再看根部区域的
低分位亮度比周围毛色暗多少。单条描边模糊后会被周围毛色平均掉，
多条描边挤在一起才会形成持续的暗区。
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, '..', '_art_v1.3', 'delivery', 'Fox_Art')
sys.path.insert(0, os.path.join(ART, 'tools'))
import run_assemble as RA  # noqa: E402

M = Image.open(os.path.join(ART, 'assets', 'master', 'Base',
                            'fox_base_blue_q4@1024.png')).convert('RGBA')
MA = np.asarray(M.split()[3]) > 8

yy, xx = np.mgrid[0:1024, 0:1024]
disk = ((xx - 425) ** 2 + (yy - 505) ** 2) <= 110 ** 2


def luma_of(img):
    return (0.299 * np.asarray(img)[..., 0] + 0.587 * np.asarray(img)[..., 1]
            + 0.114 * np.asarray(img)[..., 2])


print('%-8s %8s %8s %8s' % ('tail', 'p05', 'ref', 'ratio'))
ref = None
for t in ['normal', 'twin', 'triple', 'quad', 'quint', 'nine',
          'fluffy', 'long', 'curl', 'short', 'thin']:
    img, _ = RA.assemble(coat='blue', tail=t, ear='large', eye='round_blue',
                         verbose=False)
    rgba = np.asarray(img.convert('RGBA'))
    luma = luma_of(img.convert('RGBA'))
    # 只模糊亮度，把透明区当成背景白，避免边缘发黑干扰
    l = Image.fromarray(np.clip(luma, 0, 255).astype('uint8'))
    lb = np.asarray(l.filter(ImageFilter.GaussianBlur(14))).astype(float)
    opaque = disk & MA & (rgba[..., 3] > 200)
    p05 = float(np.percentile(lb[opaque], 5)) if opaque.any() else 0.0
    p50 = float(np.percentile(lb[opaque], 50))
    if ref is None:
        ref = p05
    print('%-8s %8.1f %8.1f %7.2f' % (t, p05, p50, p05 / max(ref, 1)))
