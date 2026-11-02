# -*- coding: utf-8 -*-
"""
花纹做成与毛色正交的**白色 alpha 遮罩**：程序取毛色的 shade 色填充即可，
10 套毛色自动复用同一套花纹，不需要 10 x 5 = 50 张组合素材。

AI 生成的斑点/条纹密度过高（实测填充率 0.67，糊成一片），
花纹本质是简单几何图形，改为程序化生成：密度、间距、角度全部可控且可复现。
"""
import os
import sys
import math

BASE = "C:/Users/zxiny/WorkBuddy/2026-11-01-00-53-44/Fox_Art"
sys.path.insert(0, BASE + "/tools")
import numpy as np
from PIL import Image, ImageDraw
import fox_traits as ft

MASTER = Image.open(
    BASE + "/assets/master/Base/fox_base_blue_q4@1024.png").convert("RGBA")
fox_a = np.asarray(MASTER)[..., 3].astype(np.float32) / 255.0
BB = MASTER.getbbox()

yy, xx = np.mgrid[0:1024, 0:1024]
# 只避开眼鼻口，脸部其余区域允许有花纹（额头纹章就需要落在脸上）
EYES = (((xx - 610) / 62.0) ** 2 + ((yy - 510) / 52.0) ** 2 <= 1.0) | \
       (((xx - 775) / 60.0) ** 2 + ((yy - 490) / 50.0) ** 2 <= 1.0) | \
       (((xx - 740) / 58.0) ** 2 + ((yy - 560) / 46.0) ** 2 <= 1.0)
BODY = (fox_a > 0.35) & (~EYES)
# 躯干花纹（斑点/条纹/渐变）不进脸：整块头部区域排除，保证五官永远干净
FACE_BIG = (((xx - 700) / 195.0) ** 2 + ((yy - 470) / 165.0) ** 2 <= 1.0)
COAT = (fox_a > 0.35) & (~FACE_BIG)

outdir = os.path.join(BASE, "assets/master/Patterns")
os.makedirs(outdir, exist_ok=True)


def save_mask(alpha01, name):
    a = (np.clip(alpha01, 0, 1) * 255).astype(np.uint8)
    out = np.dstack([np.full_like(a, 255), np.full_like(a, 255),
                     np.full_like(a, 255), a])
    Image.fromarray(out, "RGBA").save(os.path.join(outdir, name + "@1024.png"))
    im = Image.open(os.path.join(outdir, name + "@1024.png"))
    for n in (512, 256):
        im.resize((n, n), Image.LANCZOS).save(
            os.path.join(BASE, "assets/export_%d" % n, name + "@%d.png" % n))
    # 相对狐狸剪影的覆盖率，比全画布覆盖率更能反映观感
    body_n = max(1, int(BODY.sum()))
    print("  %-24s coverage_in_body=%.3f" % (name, (alpha01 > 0.5).sum() / body_n))


# ---- 斑点 ----
rng = np.random.RandomState(20261101)
spots = np.zeros((1024, 1024), np.float32)
for _ in range(46):
    cx = rng.uniform(BB[0], BB[2])
    cy = rng.uniform(BB[1] + 40, BB[3])
    r = rng.uniform(14, 34)
    ry = r * rng.uniform(0.75, 1.25)
    spots += (((xx - cx) / r) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0).astype(np.float32)
save_mask(np.clip(spots, 0, 1) * COAT, "pattern_spots_mask")

# ---- 条纹：倾斜 ~22 度的等距粗条带 ----
stripes = np.zeros((1024, 1024), np.float32)
ang = math.radians(-22.0)
ca, sa = math.cos(ang), math.sin(ang)
u = (xx - 512) * ca + (yy - 520) * sa           # 沿条纹法线方向
v = -(xx - 512) * sa + (yy - 520) * ca          # 沿条纹走向
period, width = 74.0, 20.0
phase = ((u + 3000) % period) - period / 2.0
stripes = (np.abs(phase) < width / 2.0).astype(np.float32)
# 让条纹沿走向轻微起伏，避免死板的直尺感
stripes *= (np.abs(v + 26.0 * np.sin(u / 130.0)) < 460).astype(np.float32)
save_mask(np.clip(stripes, 0, 1) * COAT, "pattern_stripes_mask")

# ---- 额头纹章：五角星 + 两滴泪滴 ----
mark = Image.new("L", (1024, 1024), 0)
d = ImageDraw.Draw(mark)
cx, cy, R, r = 700, 398, 72, 30
pts = []
for i in range(10):
    ang_i = -math.pi / 2 + i * math.pi / 5
    rr = R if i % 2 == 0 else r
    pts.append((cx + rr * math.cos(ang_i), cy + rr * math.sin(ang_i)))
d.polygon(pts, fill=255)
for dx, dy in ((-38, 100), (38, 100)):
    d.ellipse([cx + dx - 17, cy + dy - 26, cx + dx + 17, cy + dy + 26], fill=255)
save_mask((np.asarray(mark).astype(np.float32) / 255.0) * BODY,
          "pattern_facemark_mask")

# ---- 渐变：上部浅、下部深（四肢与体侧加深）----
g = np.clip((yy - 560) / 340.0, 0.0, 1.0) * 0.80
save_mask(g * COAT, "pattern_gradient_mask")

# ---- 纯色：空遮罩，显式交付便于程序枚举 ----
save_mask(np.zeros((1024, 1024), np.float32), "pattern_solid_mask")

# ---- 预览：用霜蓝暗部色着色 ----
cw = ft.load_colorways(BASE + "/01_Data/colorways.json")[0]["blue"]
shade = ft.hex2rgb(cw["shade"])
base = np.asarray(MASTER).astype(np.float32)
prev = []
for nm in ("solid", "spots", "stripes", "gradient", "facemark"):
    p = os.path.join(outdir, "pattern_%s_mask@1024.png" % nm)
    a = np.asarray(Image.open(p).convert("RGBA")).astype(np.float32)[..., 3:] / 255.0
    rgb = base[..., :3] * (1 - a) + (shade[None, None, :] * a)
    im = Image.fromarray(np.dstack([rgb, base[..., 3:][..., 0]]).astype(np.uint8),
                         "RGBA")
    im.save(os.path.join(BASE, "assets/preview", "preview_pattern_%s.png" % nm))
    prev.append((im, nm))
ft.contact_sheet(prev, BASE + "/09_Review/_patterns_preview.png", cell=300, cols=5)
print("preview:", BASE + "/09_Review/_patterns_preview.png")
