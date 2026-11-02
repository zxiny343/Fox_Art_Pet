# -*- coding: utf-8 -*-
"""v1.3 新增花纹：pattern_flame（火焰纹，滤色叠加）/ pattern_tabby（虎斑，碎横纹）。

只新增文件；v1.2 的 5 个花纹不动（run_patterns.py 不重跑）。

遮罩仍是"白色 + alpha"格式（信息在 alpha 通道），与 v1.2 一致。
混合规则写入 Patterns/_patterns_meta.json，由 run_assemble.apply_pattern 消费。
"""
import os
import sys
import json
import math

B = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(B, "tools"))
import numpy as np
from PIL import Image, ImageDraw
import fox_traits as ft

M = os.path.join(B, "assets", "master")
PAT = os.path.join(M, "Patterns")
REVIEW = os.path.join(B, "09_Review")

MASTER = Image.open(os.path.join(M, "Base",
                                 "fox_base_blue_q4@1024.png")).convert("RGBA")
fox_a = np.asarray(MASTER)[..., 3].astype(np.float32) / 255.0
BB = MASTER.getbbox()
yy, xx = np.mgrid[0:1024, 0:1024]

EYES = (((xx - 610) / 62.0) ** 2 + ((yy - 510) / 52.0) ** 2 <= 1.0) | \
       (((xx - 775) / 60.0) ** 2 + ((yy - 490) / 50.0) ** 2 <= 1.0) | \
       (((xx - 740) / 58.0) ** 2 + ((yy - 560) / 46.0) ** 2 <= 1.0)
FACE_BIG = (((xx - 700) / 195.0) ** 2 + ((yy - 470) / 165.0) ** 2 <= 1.0)
BODY = (fox_a > 0.35) & (~EYES)          # 含尾巴（尾巴属于剪影的一部分）
COAT = BODY & (~FACE_BIG)                # 躯干类花纹不进脸

# 火焰专属禁区：只护住五官与额头（"额头不上脸"），
# v1.2 的 FACE_BIG 椭圆过大，会把整段背脊一起排除，火焰就只剩尾巴上有。
FLAME_FORBID = (((xx - 610) / 96.0) ** 2 + ((yy - 510) / 84.0) ** 2 <= 1.0) | \
               (((xx - 775) / 94.0) ** 2 + ((yy - 490) / 82.0) ** 2 <= 1.0) | \
               (((xx - 740) / 88.0) ** 2 + ((yy - 558) / 74.0) ** 2 <= 1.0) | \
               (((xx - 700) / 104.0) ** 2 + ((yy - 408) / 92.0) ** 2 <= 1.0)
FLAME_ALLOW = BODY & (~FLAME_FORBID)


def save_mask(alpha01, name):
    a = (np.clip(alpha01, 0, 1) * 255).astype(np.uint8)
    out = np.dstack([np.full_like(a, 255), np.full_like(a, 255),
                     np.full_like(a, 255), a])
    Image.fromarray(out, "RGBA").save(os.path.join(PAT, name + "@1024.png"))
    im = Image.open(os.path.join(PAT, name + "@1024.png"))
    for n in (512, 256):
        im.resize((n, n), Image.LANCZOS).save(
            os.path.join(B, "assets", "export_%d" % n, name + "@%d.png" % n))
    body_n = max(1, int(BODY.sum()))
    print("  %-22s coverage_in_body=%.3f  px=%d"
          % (name, (alpha01 > 0.5).sum() / body_n, int((alpha01 > 0.5).sum())))


def flame_tongue(draw, cx, cy, ang_deg, L, W, phase=0.0, wobble=0.18):
    """一枚火焰舌：基部窄 → 中部宽 → 尖端收，边缘带波动。"""
    th = math.radians(ang_deg)
    c, s = math.cos(th), math.sin(th)
    up, dn = [], []
    N = 26
    for i in range(N + 1):
        u = i / N                      # 0=基部 1=尖端
        w = W * math.sin(math.pi * u) ** 0.65 * (1.0 - 0.55 * u)
        w *= 1.0 + wobble * math.sin(3.0 * math.pi * u + phase)
        px, py = u * L, w
        x = cx + px * c - py * s
        y = cy + px * s + py * c
        up.append((x, y))
        dn.append((cx + px * c + py * s, cy + px * s - py * c))
    draw.polygon(up + dn[::-1], fill=255)


def make_flame():
    """沿背脊 → 尾根 → 尾尖布置火苗：尾尖大、背部小，左右交替摇曳。

    双层结构（关键）：外焰 = 火舌高斯柔化 ×0.75，内焰 = 缩小版火舌。
    单层平涂在剪影内会被看成"锯齿毛边"，双层才有火焰的明暗层次。
    """
    from scipy import ndimage
    return _flame_field(ndimage)


def _flame_field(ndimage):
    """生成火焰场（外焰柔化 + 内焰高亮）。"""
    # 路径：颈背 → 背脊 → 尾根(425,505) → 尾尖(200,320)
    path = [(624, 548), (566, 560), (500, 574), (436, 540),
            (368, 470), (300, 410), (238, 362), (206, 334)]
    # 密采样
    pts = []
    for i in range(len(path) - 1):
        (x0, y0), (x1, y1) = path[i], path[i + 1]
        n = max(2, int(math.dist((x0, y0), (x1, y1)) / 6.0))
        for k in range(n):
            t = k / n
            pts.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    pts.append(path[-1])
    cum = [0.0]
    for i in range(1, len(pts)):
        cum.append(cum[-1] + math.dist(pts[i - 1], pts[i]))
    total = cum[-1]

    outer = Image.new("L", (1024, 1024), 0)
    inner = Image.new("L", (1024, 1024), 0)
    do, di = ImageDraw.Draw(outer), ImageDraw.Draw(inner)
    N = 26
    for i in range(N):
        f = i / (N - 1.0)                    # 0=背脊 1=尾尖
        s_target = total * (0.03 + 0.97 * f)
        j = min(range(len(cum)), key=lambda k: abs(cum[k] - s_target))
        j2 = min(j + 3, len(pts) - 1)
        (x0, y0), (x1, y1) = pts[j], pts[j2]
        tang = math.degrees(math.atan2(y1 - y0, x1 - x0))
        tr = math.radians(tang)
        cx, cy = pts[j]
        side = -1 if i % 2 == 0 else 1
        # 火苗斜向：沿路径偏转 ±34°，保证主体落在剪影内（纯法向会被剪影裁掉）
        ang = tang + side * 34.0
        # 尺寸适配剪影宽度：尾巴最宽处约 150px，过大反而被裁成碎块
        L = 58 + 78 * f
        W = 18 + 26 * f
        flame_tongue(do, cx, cy, ang, L, W, phase=0.9 * i, wobble=0.22)
        flame_tongue(di, cx, cy, ang, L * 0.68, W * 0.60,
                     phase=0.9 * i, wobble=0.18)
        # 侧分叉（每 3 枚一枚）
        if i % 3 == 1:
            flame_tongue(do, cx - math.cos(tr) * side * 0.26 * L,
                         cy - math.sin(tr) * side * 0.26 * L,
                         ang - side * 30.0, L * 0.5, W * 0.46,
                         phase=1.4 * i, wobble=0.28)
        # 尾尖收尾大火苗（尖端朝尾尖方向）
        if i == N - 1:
            flame_tongue(do, cx, cy, tang, L * 1.02, W * 0.9,
                         phase=2.2, wobble=0.24)
            flame_tongue(di, cx, cy, tang, L * 0.72, W * 0.6,
                         phase=2.2, wobble=0.20)

    o = np.asarray(outer).astype(np.float32) / 255.0
    i_ = np.asarray(inner).astype(np.float32) / 255.0
    o = ndimage.gaussian_filter(o, 4.0) * 0.78        # 外焰柔和
    i_ = ndimage.gaussian_filter(i_, 1.6)             # 内焰清晰
    return np.clip(o + i_, 0.0, 1.0)


def make_tabby():
    """虎斑：断点/碎横纹（与 pattern_stripes 的连续纵纹可并排区分）。"""
    rng = np.random.RandomState(20261103)
    m = Image.new("L", (1024, 1024), 0)
    d = ImageDraw.Draw(m)
    # 抖动网格：横向短纹，方向大致垂直于背脊（约 -70°，与条纹的 -22° 明显不同）
    for gy in range(BB[1] + 30, BB[3] - 20, 62):
        for gx in range(BB[0] + 20, BB[2] - 20, 58):
            if rng.rand() < 0.22:            # 随机断点
                continue
            cx = gx + rng.uniform(-14, 14)
            cy = gy + rng.uniform(-12, 12)
            if not (0 <= cx < 1024 and 0 <= cy < 1024):
                continue
            ang = -68.0 + rng.uniform(-16, 16)
            # 碎：一半的纹再切成两段（中间留缺口）
            segs = [(0.0, 1.0)]
            if rng.rand() < 0.5:
                cut = rng.uniform(0.42, 0.6)
                gap = rng.uniform(0.06, 0.12)
                segs = [(0.0, cut), (cut + gap, 1.0)]
            L = rng.uniform(52, 104)
            Wd = rng.uniform(11, 17)
            for (s0, s1) in segs:
                th = math.radians(ang)
                c, s = math.cos(th), math.sin(th)
                x0 = cx + (s0 - 0.5) * L * c
                y0 = cy + (s0 - 0.5) * L * s
                x1 = cx + (s1 - 0.5) * L * c
                y1 = cy + (s1 - 0.5) * L * s
                npts = []
                steps = 10
                for k in range(steps + 1):
                    t = k / steps
                    wob = math.sin(math.pi * t) * Wd * \
                        (1.0 + 0.15 * math.sin(6.0 * t))
                    px = x0 + (x1 - x0) * t
                    py = y0 + (y1 - y0) * t
                    npts.append((px - s * wob, py + c * wob))
                for k in range(steps, -1, -1):
                    t = k / steps
                    wob = math.sin(math.pi * t) * Wd * \
                        (1.0 + 0.15 * math.sin(6.0 * t))
                    px = x0 + (x1 - x0) * t
                    py = y0 + (y1 - y0) * t
                    npts.append((px + s * wob, py - c * wob))
                d.polygon(npts, fill=255)
    return np.asarray(m).astype(np.float32) / 255.0


def update_meta():
    p = os.path.join(PAT, "_patterns_meta.json")
    meta = {}
    if os.path.exists(p):
        meta = json.load(open(p, encoding="utf-8"))
    base = {"blend": "alpha", "tintRole": "shade", "strength": 0.85}
    for k in ("solid", "spots", "stripes", "gradient", "facemark"):
        meta.setdefault("pattern_%s" % k, dict(base))
    meta["pattern_flame"] = {
        "blend": "screen", "tintRole": "light", "strength": 0.95,
        "minLuma": 170.0,
        "note": "v1.3 P1：滤色/加法叠加，取毛色 light 色；light 亮度不足 150 时"
                "只提亮不改色相，保证深色毛(black/obsidian_gold)上仍清晰可见。"
                "遮罩沿背脊→尾尖分布，额头与五官为禁区",
    }
    meta["pattern_tabby"] = {
        "blend": "alpha", "tintRole": "shade", "strength": 0.85,
        "note": "v1.3 P2：断点/碎横纹，与 pattern_stripes 的连续纵纹并排可区分",
    }
    json.dump(meta, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("_patterns_meta.json:", list(meta))


def update_traits():
    p = os.path.join(B, "01_Data", "traits.json")
    d = json.load(open(p, encoding="utf-8"))
    pat = next(c for c in d["categories"] if c["id"] == "pattern")
    for v in ("pattern_flame", "pattern_tabby"):
        if v not in pat["values"]:
            pat["values"].append(v)
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("traits.json pattern.values =", pat["values"])


def main():
    os.makedirs(PAT, exist_ok=True)
    save_mask(make_flame() * FLAME_ALLOW, "pattern_flame_mask")
    save_mask(make_tabby() * COAT, "pattern_tabby_mask")
    update_meta()
    update_traits()

    # 验收图：火焰纹 × orange/black/white
    import run_assemble as ra
    cols = ["orange", "black", "white"]
    cell = 384
    sheet = Image.new("RGB", (cell * 3, cell), (170, 170, 170))
    for i, c in enumerate(cols):
        img, _ = ra.assemble(c, "short", "normal", "large", "round_blue",
                             pattern="flame", verbose=False)
        t = img.resize((cell, cell), Image.LANCZOS)
        bg = Image.new("RGBA", (cell, cell), (170, 170, 170, 255))
        bg.alpha_composite(t, (0, 0))
        sheet.paste(bg.convert("RGB"), (i * cell, 0))
    out = os.path.join(REVIEW, "_pattern_flame.png")
    sheet.save(out)
    print("验收图 ->", out)

    # 虎斑 vs 条纹 对照
    img1, _ = ra.assemble("orange", "short", "normal", "large", "round_blue",
                          pattern="tabby", verbose=False)
    img2, _ = ra.assemble("orange", "short", "normal", "large", "round_blue",
                          pattern="stripes", verbose=False)
    sheet2 = Image.new("RGB", (cell * 2, cell), (170, 170, 170))
    for i, im in enumerate((img1, img2)):
        bg = Image.new("RGBA", (cell, cell), (170, 170, 170, 255))
        bg.alpha_composite(im.resize((cell, cell), Image.LANCZOS), (0, 0))
        sheet2.paste(bg.convert("RGB"), (i * cell, 0))
    out2 = os.path.join(REVIEW, "_pattern_tabby_vs_stripes.png")
    sheet2.save(out2)
    print("对照图 ->", out2)


if __name__ == "__main__":
    main()
