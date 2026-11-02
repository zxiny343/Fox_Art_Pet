# -*- coding: utf-8 -*-
"""v1.5 返修单证据图：
1. fix-evidence-legs-v1.5.png — 程序化切图法 walk 4 帧穿模实拍
2. fix-evidence-pixel-v1.5.png — 1024→168 像素化对比 + body_core 腿部位置标注
"""
import os, sys, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sim'))
import anim as AN
import legs as LG
import artmap as AM
from fox_ecosystem_sim import phenotype as PH
import fox_ecosystem_sim as M

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
ART = AM.find_art_root()

# 拿一只橙狐
w = M.World(dict(M.TUNED_V3_PARAMS), 20261101)
geno = dict(w.foxes[sorted(w.alive_ids)[0]].geno)
spec = AM.to_art(PH(geno))
AN.make_walk_action()

# ============================================================
# 图 1：程序化切图法 walk 穿模实拍
# ============================================================
L336 = AN.get_layers(spec, 336)
ts = [0.0, 0.25, 0.5, 0.75]

# 临时启用腿部 rig（验证用的，桌宠默认关）
import anim as _AN
_orig_render = _AN.render_frame

frames_leg = []
frames_idle = []
for t in ts:
    # 带腿部 rig（手动调 rig_legs）
    core = _AN._scaled_core(L336['core'], _AN.pose_at_multi([('walk_fx', t)]), 336)
    core = LG.rig_legs(core, t, _AN._spec_key(spec), 336)
    # 组装完整帧（简化：只 core + tail + ear，不画眼）
    canvas = Image.new('RGBA', (336, 336), (0, 0, 0, 0))
    canvas.alpha_composite(_AN.rig_tail(L336['tail'], spec['tail'],
                                        _AN.pose_at_multi([('walk_fx', t)]), 336))
    canvas.alpha_composite(core)
    canvas.alpha_composite(_AN.rig_ear(L336['ear_L'], 'L',
                                       _AN.pose_at_multi([('walk_fx', t)]), 336))
    canvas.alpha_composite(_AN.rig_ear(L336['ear_R'], 'R',
                                       _AN.pose_at_multi([('walk_fx', t)]), 336))
    canvas = _AN._apply_root(canvas, _AN.pose_at_multi([('walk_fx', t)]), 336)
    frames_leg.append(canvas.resize((168, int(168 * _AN.ASPECT)), Image.LANCZOS))
    # idle 对照
    img0, _ = _AN.render_frame(spec, 0, [('idle_breath', 0.3)],
                               size=168, layers=L336, work=336)
    frames_idle.append(img0)

zoom = 4
W, Hh = frames_leg[0].size
pad = 10
label_h = 24
out1 = Image.new('RGB', ((W*zoom+pad)*4+pad, (Hh*zoom+label_h)*2+pad+30), (250,250,252))
dr = ImageDraw.Draw(out1)
try:
    f = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 14)
except Exception:
    f = ImageFont.load_default()

dr.text((pad, 6), '上排：程序化切图法 walk 4 帧（腿摆动 ±12°，可见穿模/脱离）', fill=(200,40,40), font=f)
dr.text((pad, 22), '下排：idle 对照（腿不动）', fill=(80,80,80), font=f)

for i, (im_leg, im_idle) in enumerate(zip(frames_leg, frames_idle)):
    big_leg = im_leg.resize((W*zoom, Hh*zoom), Image.NEAREST)
    big_idle = im_idle.resize((W*zoom, Hh*zoom), Image.NEAREST)
    # 白底（alpha_composite 要 RGBA）
    bg_leg = Image.new('RGBA', big_leg.size, (255,255,255,255))
    bg_leg.alpha_composite(big_leg)
    bg_idle = Image.new('RGBA', big_idle.size, (255,255,255,255))
    bg_idle.alpha_composite(big_idle)
    x = pad + i*(W*zoom+pad)
    y_top = label_h + pad
    y_bot = label_h + pad + Hh*zoom + pad
    out1.paste(bg_leg.convert('RGB'), (x, y_top))
    out1.paste(bg_idle.convert('RGB'), (x, y_bot))
    dr.text((x, y_top + Hh*zoom + 2), 'walk t=%.2f' % ts[i], fill=(40,44,52), font=f)

out1.save(os.path.join(ROOT, 'docs', 'fix-evidence-legs-v1.5.png'))
print('saved fix-evidence-legs-v1.5.png', out1.size)

# ============================================================
# 图 2：像素化对比 + body_core 腿部位置标注
# ============================================================
# 2a: 1024 vs 168 像素化
core_path = os.path.join(ART, 'assets', 'master', 'Body', 'body_core_orange@1024.png')
core_1024 = Image.open(core_path).convert('RGBA')
# 找 alpha bbox 裁出来
a = np.asarray(core_1024.split()[3])
ys, xs = np.where(a > 30)
x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
core_crop = core_1024.crop((x0, y0, x1, y1))
# 缩到 168 宽
w168 = 168
h168 = int(w168 * core_crop.height / core_crop.width)
core_168 = core_crop.resize((w168, h168), Image.LANCZOS)

# 2b: body_core 底部腿位置标注
core_mark = core_1024.copy()
dr2 = ImageDraw.Draw(core_mark)
info = LG._detect(core_1024)
leg_colors = [(220,60,60), (60,180,80), (60,100,220), (220,160,40)]
leg_names = ['hip_far', 'hip_near', 'shoulder_far', 'shoulder_near']
bone_starts = {'hip_near':(430,655), 'hip_far':(370,650),
               'shoulder_near':(700,600), 'shoulder_far':(650,595)}
if info:
    for i, lg in enumerate(info):
        c = leg_colors[i % 4]
        # 标腿位置
        dr2.rectangle([lg['x0'], lg['y_root'], lg['x1'], lg['y_foot']],
                      outline=c, width=4)
        dr2.ellipse([lg['xc']-8, lg['y_foot']-8, lg['xc']+8, lg['y_foot']+8],
                    outline=c, width=3)
# 标骨骼锚点
for name, (bx, by) in bone_starts.items():
    dr2.ellipse([bx-10, by-10, bx+10, by+10], fill=(180,0,180,200))
    dr2.text((bx+14, by-8), name, fill=(180,0,180), font=f)

# 拼图
out2 = Image.new('RGB', (1100, 760), (250,250,252))
dr3 = ImageDraw.Draw(out2)
dr3.text((20, 10), '左：body_core 底部 4 条腿位置（彩色框）+ 骨骼锚点（紫点）', fill=(40,44,52), font=f)
dr3.text((20, 30), '右：1024 缩到 168px 的像素化（4× 放大看细节丢失）', fill=(40,44,52), font=f)
# 左：标注图（裁到 alpha bbox）
mark_crop = core_mark.crop((x0-20, y0-20, x1+20, y1+20))
mark_small = mark_crop.resize((500, int(500*mark_crop.height/mark_crop.width)), Image.LANCZOS)
out2.paste(mark_small.convert('RGB'), (20, 55))
# 右：像素化 4× 放大
big168 = core_168.resize((w168*4, h168*4), Image.NEAREST)
bg168 = Image.new('RGBA', big168.size, (255,255,255,255))
bg168.alpha_composite(big168)
out2.paste(bg168.convert('RGB'), (560, 55))
dr3.text((560, 55+h168*4+8), '168px ×4 放大（NEAREST）', fill=(200,40,40), font=f)
# 原始 1024 缩略
core_small = core_crop.resize((400, int(400*core_crop.height/core_crop.width)), Image.LANCZOS)
out2.paste(core_small.convert('RGB'), (560, 55+h168*4+40))
dr3.text((560, 55+h168*4+32), '1024 原图（缩略）', fill=(80,80,80), font=f)

out2.save(os.path.join(ROOT, 'docs', 'fix-evidence-pixel-v1.5.png'))
print('saved fix-evidence-pixel-v1.5.png', out2.size)
