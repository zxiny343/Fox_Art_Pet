# -*- coding: utf-8 -*-
"""R4（P1）提升花纹遮罩覆盖率：stripes/tabby >=40%、spots >=25%。

手段严格按返修单：只加粗笔画 / 增加条数 / 降低断点率，
不加深颜色（颜色由毛色 shade 自动取），保留 v1.2 的 FACE_BIG 面部保护。
flame / facemark / gradient / solid 一律不动（v1.3 已定稿）。
"""
import os, sys, json, math
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_assemble as ra

B = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
M = os.path.join(B, "assets", "master")
PAT = os.path.join(M, "Patterns")
E512 = os.path.join(B, "assets", "export_512")
E256 = os.path.join(B, "assets", "export_256")
REV = os.path.join(B, "09_Review")

MASTER = Image.open(os.path.join(M, "Base", "fox_base_blue_q4@1024.png")).convert("RGBA")
fox_a = np.asarray(MASTER)[..., 3].astype(np.float32) / 255.0
BB = MASTER.getbbox()
yy, xx = np.mgrid[0:1024, 0:1024]
EYES = (((xx - 610) / 62.0) ** 2 + ((yy - 510) / 52.0) ** 2 <= 1.0) | \
       (((xx - 775) / 60.0) ** 2 + ((yy - 490) / 50.0) ** 2 <= 1.0) | \
       (((xx - 740) / 58.0) ** 2 + ((yy - 560) / 46.0) ** 2 <= 1.0)
FACE_BIG = (((xx - 700) / 195.0) ** 2 + ((yy - 470) / 165.0) ** 2 <= 1.0)
COAT = (fox_a > 0.35) & (~FACE_BIG)                 # 生产脚本口径
TRUNK = COAT & (xx < 700)                           # diag 口径（更偏躯干）

# 新参数（v1.4 标定：stripes/tabby >=40%、spots >=25%，且 128px 下三者可辨）
# tabby 取 56x54 网格 / 略收窄笔宽 -> ~48%，避免 68% 那种「迷彩糊块」；
# spots 改成 170 颗小圆点 + 最小间距 -> ~30%，颗颗可数而不是融合成大斑。
STRIPE_PERIOD, STRIPE_WIDTH = 70.0, 34.0
SPOT_N, SPOT_R, SPOT_SEP = 170, (11.0, 25.0), 0.78
TABBY_GY, TABBY_GX = 56, 54
TABBY_SKIP, TABBY_L, TABBY_WD = 0.12, (58.0, 112.0), (14.0, 20.0)


def save_mask(alpha01, name):
    a = (np.clip(alpha01, 0, 1) * 255).astype(np.uint8)
    out = np.dstack([np.full_like(a, 255), np.full_like(a, 255),
                     np.full_like(a, 255), a])
    Image.fromarray(out, "RGBA").save(os.path.join(PAT, name + "@1024.png"))
    im = Image.open(os.path.join(PAT, name + "@1024.png"))
    for n, d in ((512, E512), (256, E256)):
        im.resize((n, n), Image.LANCZOS).save(os.path.join(d, name + "@%d.png" % n))
    m = a > 128
    return {"maskPx": int(m.sum()),
            "coat": round(float((m & COAT).sum() / COAT.sum()), 4),
            "trunk": round(float((m & TRUNK).sum() / TRUNK.sum()), 4)}


def make_stripes():
    ang = math.radians(-22.0)
    ca, sa = math.cos(ang), math.sin(ang)
    u = (xx - 512) * ca + (yy - 520) * sa
    v = -(xx - 512) * sa + (yy - 520) * ca
    phase = ((u + 3000) % STRIPE_PERIOD) - STRIPE_PERIOD / 2.0
    s = (np.abs(phase) < STRIPE_WIDTH / 2.0).astype(np.float32)
    s *= (np.abs(v + 26.0 * np.sin(u / 130.0)) < 460).astype(np.float32)
    return s * COAT


def make_spots():
    rng = np.random.RandomState(20261101)
    spots = np.zeros((1024, 1024), np.float32)
    placed = []
    # 带最小间距的拒绝采样：斑点互不融合，缩到 128px 仍是「一颗颗圆点」
    for _ in range(SPOT_N * 12):
        if len(placed) >= SPOT_N:
            break
        cx = rng.uniform(BB[0], BB[2])
        cy = rng.uniform(BB[1] + 40, BB[3])
        r = rng.uniform(*SPOT_R)
        if any(math.hypot(cx - px, cy - py) < SPOT_SEP * (r + pr)
               for px, py, pr in placed):
            continue
        placed.append((cx, cy, r))
        ry = r * rng.uniform(0.85, 1.15)
        spots += (((xx - cx) / r) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0).astype(np.float32)
    return np.clip(spots, 0, 1) * COAT


def make_tabby():
    rng = np.random.RandomState(20261103)
    m = Image.new("L", (1024, 1024), 0)
    d = ImageDraw.Draw(m)
    for gy in range(BB[1] + 30, BB[3] - 20, TABBY_GY):
        for gx in range(BB[0] + 20, BB[2] - 20, TABBY_GX):
            if rng.rand() < TABBY_SKIP:
                continue
            cx = gx + rng.uniform(-14, 14)
            cy = gy + rng.uniform(-12, 12)
            if not (0 <= cx < 1024 and 0 <= cy < 1024):
                continue
            ang = -68.0 + rng.uniform(-16, 16)
            segs = [(0.0, 1.0)]
            if rng.rand() < 0.5:
                cut = rng.uniform(0.42, 0.6)
                gap = rng.uniform(0.06, 0.12)
                segs = [(0.0, cut), (cut + gap, 1.0)]
            L = rng.uniform(*TABBY_L)
            Wd = rng.uniform(*TABBY_WD)
            for (s0, s1) in segs:
                th = math.radians(ang)
                c, s = math.cos(th), math.sin(th)
                x0 = cx + (s0 - 0.5) * L * c
                y0 = cy + (s0 - 0.5) * L * s
                x1 = cx + (s1 - 0.5) * L * c
                y1 = cy + (s1 - 0.5) * L * s
                pts = []
                steps = 10
                for k in range(steps + 1):
                    t = k / steps
                    wob = math.sin(math.pi * t) * Wd * (1.0 + 0.15 * math.sin(6.0 * t))
                    pts.append((x0 + (x1 - x0) * t - s * wob,
                                y0 + (y1 - y0) * t + c * wob))
                for k in range(steps, -1, -1):
                    t = k / steps
                    wob = math.sin(math.pi * t) * Wd * (1.0 + 0.15 * math.sin(6.0 * t))
                    pts.append((x0 + (x1 - x0) * t + s * wob,
                                y0 + (y1 - y0) * t - c * wob))
                d.polygon(pts, fill=255)
    return (np.asarray(m).astype(np.float32) / 255.0) * COAT


def main():
    res = {}
    for name, fn in (("stripes", make_stripes), ("tabby", make_tabby),
                     ("spots", make_spots)):
        res[name] = save_mask(fn(), "pattern_%s_mask" % name)
        print("%-9s maskPx=%6d  coat口径=%.3f  trunk口径=%.3f"
              % (name, res[name]["maskPx"], res[name]["coat"], res[name]["trunk"]))

    # 验收图：2 毛色 × 3 尺寸 × 3 花纹，128 档按 4x 放大（NEAREST）以便判可辨性
    cell = 320
    sheet = Image.new("RGB", (cell * 3, cell * 6), (175, 175, 175))
    for ri, (coat, size) in enumerate(
            [(c, s) for c in ("black", "white") for s in (128, 256, 512)]):
        for ci, pat in enumerate(("stripes", "tabby", "spots")):
            img, _ = ra.assemble(coat, "short", "normal", "large", "round_blue",
                                 pattern=pat, verbose=False)
            sm = img.convert("RGBA").resize((size, size), Image.LANCZOS)
            bg = Image.new("RGBA", (size, size), (175, 175, 175, 255))
            bg.alpha_composite(sm, (0, 0))
            disp = bg.resize((cell, cell),
                             Image.NEAREST if size == 128 else Image.LANCZOS)
            sheet.paste(disp.convert("RGB"), (ci * cell, ri * cell))
    sheet.save(os.path.join(REV, "_pattern_scales.png"))
    print("saved _pattern_scales.png")

    mp = os.path.join(PAT, "_patterns_meta.json")
    meta = json.load(open(mp, encoding="utf-8"))
    meta["_v14_R4"] = {
        "method": "加粗笔画 + 加密条数/斑点，不改颜色，保留 FACE_BIG 脸部保护",
        "stripePeriod": STRIPE_PERIOD, "stripeWidth": STRIPE_WIDTH,
        "spotCount": SPOT_N, "spotRadius": list(SPOT_R),
        "spotMinSeparation": SPOT_SEP, "tabbyGrid": [TABBY_GY, TABBY_GX],
        "coverage": res, "flameUnchanged": True,
    }
    json.dump(meta, open(mp, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("meta updated")


if __name__ == "__main__":
    main()
