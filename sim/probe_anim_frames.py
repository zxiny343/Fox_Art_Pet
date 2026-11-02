# -*- coding: utf-8 -*-
"""动画关键帧检查：并排看 4 帧 + 帧间差异，确认真的在动且没有裂缝。"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anim as AN                                     # noqa: E402
import artmap as AM                                   # noqa: E402
import render_kernel as RK                            # noqa: E402
from fox_ecosystem_sim import phenotype as PH         # noqa: E402

DOCS = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'docs')


def fnt(sz):
    for p in (r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\simhei.ttf'):
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, sz)
            except OSError:
                pass
    return ImageFont.load_default()


def on_white(img):
    bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
    bg.alpha_composite(img)
    return bg.convert('RGB')


def main():
    g = RK.sample_genotypes(1)[0]
    spec = AM.to_art(PH(g))
    acts = ['idle_breath', 'idle_tail_sway', 'idle_ear_twitch', 'blink']
    layers = AM.layers(spec)

    ts = (0.0, 0.25, 0.5, 0.75)
    frames, poses = [], []
    for t in ts:
        img, pose = AN.render_frame(spec, t, acts, size=512, layers=layers)
        frames.append(np.asarray(img.convert('RGBA')))
        poses.append(pose)

    cw = 300
    W = cw * len(ts) + 20
    H = 76 + cw + 130
    sh = Image.new('RGB', (W, H), (246, 246, 249))
    dr = ImageDraw.Draw(sh)
    dr.text((14, 10), '待机四层叠加：idle_breath + idle_tail_sway + idle_ear_twitch + blink',
            font=fnt(17), fill=(20, 20, 24))
    dr.text((14, 40), 'coat=%s fur=%s tail=%s ear=%s' %
            (spec['coat'], spec['fur'], spec['tail'], spec['ear']),
            font=fnt(12), fill=(110, 110, 120))

    for i, (t, a) in enumerate(zip(ts, frames)):
        x = 10 + i * cw
        sh.paste(on_white(Image.fromarray(a)).resize((cw - 10, cw - 10),
                                                     Image.LANCZOS), (x + 4, 66))
        dr.rectangle([x + 3, 65, x + 4 + cw - 10, 65 + cw - 10],
                     outline=(205, 205, 212))
        dr.text((x + 6, 66 + cw - 6), 't=%.2f' % t, font=fnt(13),
                fill=(20, 20, 24))
        p = poses[i]
        dr.text((x + 6, 66 + cw + 12),
                'tail r/m+s/t = %+.1f / %+.1f / %+.1f'
                % (p.rotate('tail_root'),
                   p.rotate('tail_mid') + p.rotate('tail_sub'),
                   p.rotate('tail_tip')),
                font=fnt(11), fill=(60, 60, 70))
        dr.text((x + 6, 66 + cw + 30),
                'body scale %.3f/%.3f  ear %+.1f/%+.1f'
                % (p.get('body', 'scaleX', 1), p.get('body', 'scaleY', 1),
                   p.rotate('ear_l'), p.rotate('ear_r')),
                font=fnt(11), fill=(60, 60, 70))

    # 帧间差异（只看 alpha 变化，最能暴露「动没动」和「有没有裂缝」）
    y = 66 + cw + 56
    dr.text((14, y - 18), '相邻帧 alpha 差异（红=消失，绿=出现）——看尾巴与耳朵是否真的在动',
            font=fnt(12), fill=(20, 20, 24))
    for i in range(len(ts) - 1):
        d = frames[i + 1][..., 3].astype(np.int16) - frames[i][..., 3].astype(np.int16)
        rgb = np.full((512, 512, 3), 235, np.uint8)
        rgb[d < -40] = (232, 60, 60)
        rgb[d > 40] = (50, 170, 90)
        x = 10 + i * cw
        sh.paste(Image.fromarray(rgb).resize((cw - 10, 60), Image.LANCZOS),
                 (x + 4, y))
        dr.text((x + 6, y + 62), '%.2f→%.2f  变化 %d px'
                % (ts[i], ts[i + 1], int((np.abs(d) > 40).sum())),
                font=fnt(11), fill=(60, 60, 70))

    out = os.path.join(DOCS, 'anim-frames.png')
    sh.save(out)
    print('->', out)


if __name__ == '__main__':
    main()
