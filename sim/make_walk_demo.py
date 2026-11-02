# -*- coding: utf-8 -*-
"""生成 walk 步态 GIF + 散步朝向切换演示图。

离屏渲染，不需要桌宠真跑。展示：
  1. walk-legs.gif        —— 12 帧朝右走循环（腿部 rig 生效）
  2. walk-legs-mirror.gif —— 同上镜像（朝左走，验证朝向）
  3. wander-demo.png      —— 模拟散步 6 步（右3 + 左3），展示朝向切换
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'sim'))
import anim as AN
import artmap as AM
from fox_ecosystem_sim import phenotype as PH
import fox_ecosystem_sim as M
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs')

w = M.World(dict(M.TUNED_V3_PARAMS), 20261101)
spec = AM.to_art(PH(dict(w.foxes[sorted(w.alive_ids)[0]].geno)))
AN.make_walk_action()
L = AN.get_layers(spec, 336)

# --- GIF：12 帧循环 ---
N = 12
frames_r = []
for i in range(N):
    t = i / float(N)
    img, _ = AN.render_frame(spec, 0, [('walk_fx', t)],
                             size=168, layers=L, work=336)
    img = img.transpose(Image.FLIP_LEFT_RIGHT) if False else img
    # 白底（GIF 不支持半透明，alpha 合到白底）
    bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
    bg.alpha_composite(img)
    frames_r.append(bg.convert('RGB').convert('P', palette=Image.ADAPTIVE))

frames_r[0].save(os.path.join(OUT, 'walk-legs.gif'),
                 save_all=True, append_images=frames_r[1:],
                 duration=90, loop=0, disposal=2)
print('saved walk-legs.gif  %d frames' % N)

# 镜像版（朝左）
frames_l = [f.transpose(Image.FLIP_LEFT_RIGHT) for f in frames_r]
frames_l[0].save(os.path.join(OUT, 'walk-legs-mirror.gif'),
                 save_all=True, append_images=frames_l[1:],
                 duration=90, loop=0, disposal=2)
print('saved walk-legs-mirror.gif')

# --- 散步朝向切换演示 ---
# 模拟 wander：3 步朝右 + 3 步朝左，每步取落地瞬间一帧
font = None
try:
    font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 18)
except Exception:
    font = ImageFont.load_default()

ts_snap = [0.0, 0.25, 0.5, 0.75]            # 一个循环里 4 个姿态
shots = []
# 朝右走 4 帧
for t in ts_snap:
    img, _ = AN.render_frame(spec, 0, [('walk_fx', t)],
                             size=168, layers=L, work=336)
    shots.append(('右走 t=%.2f' % t, img, False))
# 朝左走 4 帧（镜像）
for t in ts_snap:
    img, _ = AN.render_frame(spec, 0, [('walk_fx', t)],
                             size=168, layers=L, work=336)
    shots.append(('左走 t=%.2f' % t, img.transpose(Image.FLIP_LEFT_RIGHT), True))

zoom = 3
W, H = shots[0][1].size
cols = 4
rows = 2
pad = 12
out = Image.new('RGB',
                (cols * (W * zoom + pad) + pad,
                 rows * (H * zoom + pad) + pad + 40),
                (245, 246, 248))
dr = ImageDraw.Draw(out)
for i, (name, im, mirrored) in enumerate(shots):
    r = i // cols
    c = i % cols
    big = im.resize((W * zoom, H * zoom), Image.NEAREST)
    bg = Image.new('RGBA', big.size, (255, 255, 255, 255))
    bg.alpha_composite(big)
    x = pad + c * (W * zoom + pad)
    y = pad + 30 + r * (H * zoom + pad)
    out.paste(bg.convert('RGB'), (x, y))
    color = (200, 60, 60) if not mirrored else (60, 120, 200)
    dr.text((x, y - 22), name, fill=color, font=font)
dr.text((pad, 8), '上排：朝右走（原图）   下排：朝左走（镜像）   每排 4 帧为一个步态循环',
        fill=(40, 44, 52), font=font)
out.save(os.path.join(OUT, 'wander-demo.png'))
print('saved wander-demo.png', out.size)
