# -*- coding: utf-8 -*-
"""R1 方案试验：短尾/细尾的「毛量渐变过渡」候选对比。
数值判据：master_a & (assembled alpha < 8) < 500。
视觉要求：不许平涂、不许硬描边、尾身形态不变。
"""
import os, sys, shutil
import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_assemble as ra
import run_split as rs

B = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
M = os.path.join(B, "assets", "master")
REV = os.path.join(B, "09_Review")
master = np.asarray(Image.open(os.path.join(M, "Base", "fox_base_blue_q4@1024.png"))
                   .convert("RGBA"))
master_a = master[..., 3] > 8
reg, _ = rs.load()
W = master_a & rs.region_mask(reg["regions"]["tail"])
normal = np.asarray(Image.open(os.path.join(M, "Tails", "tail_normal.png"))
                   .convert("RGBA")).copy()

# --- 构造无描边的 normal 毛流底 ---
lum = normal[..., :3].astype(np.float32).mean(2)
stroke = (lum < 85) & (normal[..., 3] > 8)
# 最近的非描边像素颜色
_, inds = ndimage.distance_transform_edt(stroke, return_indices=True)
flat = normal[..., :3].reshape(-1, 3)
idx = inds[0] * 1024 + inds[1]
nostroke_rgb = flat[idx].reshape(1024, 1024, 3)

# 蓝色绒毛底：身体 base 色 + normal 的高频毛流明暗（不含白色内毛扇形 / 不含硬描边）
_base = np.array([108.0, 165.0, 205.0], np.float32)
_nr = normal[..., :3].astype(np.float32)
_blur = ndimage.gaussian_filter(_nr, (7, 7, 0))
_detail = np.clip(_nr - _blur, -46, 46)
fluff_rgb = np.clip(_base + _detail * 0.55, 0, 255)


def make_patch(part, mode, scale=70.0, floor=14.0, white_mix=0.0):
    pa = part[..., 3] > 8
    add = W & ~pa
    d = ndimage.distance_transform_edt(~pa)          # 距最近部件像素的距离
    out = part.copy()
    if mode == "hard":
        out[add] = normal[add]
        return out
    # 渐变 alpha：毛量从根部向远端衰减
    if mode == "dist" or mode.startswith("fluff"):
        al = 255.0 * np.exp(-d / scale)
    elif mode == "axis":
        # 沿尾根→尾尖长轴衰减（x 越小越远）
        al = 255.0 * np.clip((np.indices((1024, 1024))[1] - 140.0) / 360.0, 0, 1) ** 1.4
    else:
        al = np.full((1024, 1024), 255.0)
    al = np.clip(al, floor, 255.0)
    rgb = fluff_rgb.astype(np.float32) if mode.startswith("fluff") else \
        nostroke_rgb.astype(np.float32)
    if white_mix:
        # 与身体蓝色混合，压低白色内毛的对比
        base = np.array([108.0, 165.0, 205.0], np.float32)
        rgb = rgb * (1 - white_mix) + base * white_mix
    out[add, :3] = np.clip(rgb[add], 0, 255).astype(np.uint8)
    out[add, 3] = np.clip(al[add], 0, 255).astype(np.uint8)
    return out


def hole_of(img):
    a = np.asarray(img)[..., 3]
    return int((master_a & (a < 8)).sum())


def assemble_with(part_img, coat, tail, ear="large"):
    """临时把部件写到 Tails 覆盖路径再走正规组装（保证 tint/换色一致）。"""
    p = os.path.join(M, "Tails", "tail_%s.png" % tail)
    bak = p + ".orig"
    if not os.path.exists(bak):
        shutil.copyfile(p, bak)
    Image.fromarray(part_img, "RGBA").save(p)
    try:
        return ra.assemble(coat, "short", tail, ear, "round_blue", verbose=False)[0]
    finally:
        shutil.copyfile(bak, p)


TRIALS = [
    ("C0 现状", None),
    ("C9 绒毛 d30", ("fluff", 30.0, 10.0, 0.0)),
    ("C10 绒毛 d40", ("fluff", 40.0, 10.0, 0.0)),
    ("C11 绒毛 d55", ("fluff", 55.0, 10.0, 0.0)),
]

cell = 620
sheet = Image.new("RGB", (cell * len(TRIALS), cell * 2), (168, 168, 168))
for ti, (name, spec) in enumerate(TRIALS):
    for ri, tail in enumerate(("short", "thin")):
        p = os.path.join(M, "Tails", "tail_%s.png" % tail)
        part = np.asarray(Image.open(p).convert("RGBA")).copy()
        if spec is None:
            pm = part
            img = ra.assemble("blue", "short", tail, "large", "round_blue",
                              verbose=False)[0]
        else:
            pm = make_patch(part, spec[0], *spec[1:])
            img = assemble_with(pm, "blue", tail)
        h = hole_of(img)
        print("%-20s %-6s hole=%6d" % (name, tail, h))
        bg = Image.new("RGBA", (1024, 1024), (168, 168, 168, 255))
        bg.alpha_composite(img.convert("RGBA"), (0, 0))
        c = bg.crop((110, 210, 690, 790)).resize((cell, cell), Image.LANCZOS)
        sheet.paste(c.convert("RGB"), (ti * cell, ri * cell))
        # 主体形态 bbox（alpha>200，排除渐淡绒毛层）
        aa = np.asarray(img)[..., 3] > 200
        yy, xx = np.where(aa)
        print("     主体bbox=(%d,%d,%d,%d)" % (xx.min(), yy.min(), xx.max(), yy.max()))
sheet.save(os.path.join(REV, "_r1_trial3.png"))
print("saved _r1_trial3.png")

# 复原备份（保留 .bak 供后续脚本还原）
for tail in ("short", "thin"):
    p = os.path.join(M, "Tails", "tail_%s.png" % tail)
    bak = p + ".orig"
    if os.path.exists(bak):
        shutil.copyfile(bak, p)
        os.remove(bak)
        print("restored", tail)
