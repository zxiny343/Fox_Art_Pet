# -*- coding: utf-8 -*-
"""阶段2-C：毛发3型（图生图全身变体） + 花纹5型（白色 alpha 遮罩，与毛色正交）。"""
import os
import sys

BASE = "C:/Users/zxiny/WorkBuddy/2026-11-01-00-53-44/Fox_Art"
sys.path.insert(0, BASE + "/tools")
import numpy as np
from PIL import Image
import fox_pipeline as fp
import fox_traits as ft

RAW = BASE + "/09_Review/raw_s2"

# ---------------- 毛发 ----------------
print("== 毛发 ==")
for key in ("medium", "long", "curly"):
    src = os.path.join(RAW, "fur_%s.png" % key)
    raw = fp.load_rgba(src)
    cut = fp.matte_by_flood(raw, tol=42)
    cut, n = fp.keep_largest_component(cut)
    m = fp.normalize(cut, fit_width=True)
    ok, rep = fp.audit(m)
    name = "fox_fur_%s_blue_q4" % key
    m.save(os.path.join(BASE, "assets/master/Base", name + "@1024.png"))
    m.resize((512, 512), Image.LANCZOS).save(
        os.path.join(BASE, "assets/export_512", name + "@512.png"))
    m.resize((256, 256), Image.LANCZOS).save(
        os.path.join(BASE, "assets/export_256", name + "@256.png"))
    print("  %-10s audit=%s  bbox=%s  components=%d"
          % (key, "PASS" if ok else "FAIL", rep["bbox"], n))

# ---------------- 花纹 ----------------
print("== 花纹遮罩 ==")
MASTER = Image.open(BASE + "/assets/master/Base/fox_base_blue_q4@1024.png").convert("RGBA")
fox_a = np.asarray(MASTER)[..., 3].astype(np.float32) / 255.0
bb = MASTER.getbbox()          # (147,150,877,928)

# 脸部保护区：花纹不盖脸，避免五官糊掉
yy, xx = np.mgrid[0:1024, 0:1024]
FACE = (((xx - 700) / 195.0) ** 2 + ((yy - 505) / 140.0) ** 2) <= 1.0
BODY = (fox_a > 0.35) & (~FACE)


def mask_png(alpha01, path):
    a = (np.clip(alpha01, 0, 1) * 255).astype(np.uint8)
    out = np.dstack([np.full_like(a, 255), np.full_like(a, 255),
                     np.full_like(a, 255), a])
    Image.fromarray(out, "RGBA").save(path)


def load_pattern(name):
    raw = fp.load_rgba(os.path.join(RAW, "patterns_1.png"))
    cut = fp.matte_by_flood(raw, tol=60)
    cut = fp.crisp_alpha(cut, thr=128, feather=0.5)
    parts = ft.split_components(cut, min_area=800, max_count=8)
    parts = ft.order_row_major(parts) if hasattr(ft, "order_row_major") else parts
    return parts


parts = load_pattern("patterns_1")
print("  pattern components:", len(parts))
names = ["spots", "stripes", "facemark"]
outdir = os.path.join(BASE, "assets/master/Patterns")
os.makedirs(outdir, exist_ok=True)

if len(parts) >= 3:
    for nm, p in zip(names, parts[:3]):
        arr = np.asarray(p)
        m = (arr[..., 3] > 90).astype(np.float32)
        if nm == "facemark":
            # 额头纹章：缩到约 150px 宽，放到额头 (700,405)
            h, w = m.shape
            s = 150.0 / w
            im = Image.fromarray((m * 255).astype(np.uint8), "L")
            im = im.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)
            mm = np.asarray(im).astype(np.float32) / 255.0
            lay = np.zeros((1024, 1024), np.float32)
            ox, oy = 700 - mm.shape[1] // 2, 405 - mm.shape[0] // 2
            lay[oy:oy + mm.shape[0], ox:ox + mm.shape[1]] = mm
        else:
            # 斑点/条纹：拉伸铺满躯干区域后与狐狸剪影求交
            bw, bh = bb[2] - bb[0], bb[3] - bb[1]
            im = Image.fromarray((m * 255).astype(np.uint8), "L")
            im = im.resize((bw, bh), Image.LANCZOS)
            mm = np.asarray(im).astype(np.float32) / 255.0
            lay = np.zeros((1024, 1024), np.float32)
            lay[bb[1]:bb[3], bb[0]:bb[2]] = mm
        final = np.clip(lay, 0, 1) * BODY
        mask_png(final, os.path.join(outdir, "pattern_%s_mask.png" % nm))
        print("  pattern_%s_mask.png  coverage=%.3f" % (nm, final.mean()))
else:
    print("  !! 只切出 %d 个部件，不足 3 个" % len(parts))

# 渐变：程序化，从背部往下逐渐加深
g = np.clip((yy - 640) / 300.0, 0.0, 1.0) * 0.85
mask_png(g * BODY, os.path.join(outdir, "pattern_gradient_mask.png"))
print("  pattern_gradient_mask.png  coverage=%.3f" % (g * BODY).mean())

# 纯色 = 空遮罩（显式交付，方便程序枚举）
mask_png(np.zeros((1024, 1024), np.float32),
         os.path.join(outdir, "pattern_solid_mask.png"))
print("  pattern_solid_mask.png (空遮罩)")

# 预览：用霜蓝暗部色给遮罩上色，便于肉眼验收
cw = ft.load_colorways(BASE + "/01_Data/colorways.json")[0]["blue"]
shade = ft.hex2rgb(cw["shade"])
prev = []
for nm in ("solid", "spots", "stripes", "gradient", "facemark"):
    p = os.path.join(outdir, "pattern_%s_mask.png" % nm)
    if not os.path.exists(p):
        continue
    a = np.asarray(Image.open(p).convert("RGBA")).astype(np.float32)[..., 3:] / 255.0
    tint = (np.ones((1024, 1024, 3)) * shade[None, None, :]) * a
    base = np.asarray(MASTER).astype(np.float32)
    rgb = base[..., :3] * (1 - a) + tint * a + base[..., :3] * 0.0
    comp = np.dstack([rgb, base[..., 3:][..., 0]])
    im = Image.fromarray(comp.astype(np.uint8), "RGBA")
    im.save(os.path.join(BASE, "assets/preview", "preview_pattern_%s.png" % nm))
    prev.append((im, nm))
ft.contact_sheet(prev, BASE + "/09_Review/_patterns_preview.png", cell=300, cols=5)
print("preview:", BASE + "/09_Review/_patterns_preview.png")
