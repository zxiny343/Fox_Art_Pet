# -*- coding: utf-8 -*-
"""R5（P1）补齐 3 个 special 层：glow / aura / star_mark。

按返修单第 5 节「选项 1（推荐）：补 3 个文件」实施，全部为 1024 RGBA
透明 PNG，并同步导出 512 / 256 两档。

  special_glow        贴身柔光：由母版 alpha 外扩的高斯柔光，不带任何底色，
                      外沿按距离自然衰减到 0，可整只叠加。
  special_aura        头顶光环：环心 (640,128)、水平直径 300px、环体宽 17px、
                      暖色柔边（俯视透视取 ry=58 的椭圆环）。
  special_star_mark   胸腹侧一簇 3 颗大小不一的五角星，纯 alpha 遮罩
                      （RGB 恒白），由产品侧按毛色上色并裁到身体范围内。
"""
import os, sys, json, math
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
B = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
M = os.path.join(B, "assets", "master")
S = os.path.join(M, "Special")
E512 = os.path.join(B, "assets", "export_512")
E256 = os.path.join(B, "assets", "export_256")
REV = os.path.join(B, "09_Review")
os.makedirs(S, exist_ok=True)

BASE = os.path.join(M, "Base", "fox_base_blue_q4@1024.png")
master = np.asarray(Image.open(BASE).convert("RGBA")).astype(np.float32)
body_a = master[..., 3] / 255.0
YY, XX = np.mgrid[0:1024, 0:1024]


def save_layer(rgb, alpha01, name):
    """rgb: (3,) 常量色；alpha01: 1024x1024 0..1。"""
    arr = np.zeros((1024, 1024, 4), np.uint8)
    arr[..., 0] = int(rgb[0]); arr[..., 1] = int(rgb[1]); arr[..., 2] = int(rgb[2])
    arr[..., 3] = (np.clip(alpha01, 0, 1) * 255).astype(np.uint8)
    im = Image.fromarray(arr, "RGBA")
    p = os.path.join(S, name + "@1024.png")
    im.save(p)
    for n, d in ((512, E512), (256, E256)):
        im.resize((n, n), Image.LANCZOS).save(
            os.path.join(d, "%s@%d.png" % (name, n)))
    return im, p


def make_glow():
    # 轮廓外柔光：blur(a)-a 在贴边处最大、向外按高斯自然衰减到 0；
    # 身体内部只留 10% 均匀微光，整只叠加不会糊掉原有赛璐璐明暗。
    blur = ndimage.gaussian_filter(body_a, 16.0)
    outer = np.clip(blur - body_a, 0, 1)
    al = np.clip(outer * 1.25 + body_a * 0.10, 0, 0.72)
    al = ndimage.gaussian_filter(al, 2.0)
    return save_layer((255, 246, 214), al, "special_glow")


def make_aura():
    # 头顶光环：水平直径 300px (rx=150)，透视压扁为 ry=58，环体宽 17px。
    rx, ry, cx, cy, width = 150.0, 58.0, 640.0, 128.0, 17.0
    r = np.hypot((XX - cx) / rx, (YY - cy) / ry)   # 归一化椭圆半径
    # 把宽度换算到 r 空间：外沿 r=1，内沿 r=(rx-width)/rx 近似
    sigma = (width / 2.0) / rx / 2.355
    ring = np.exp(-((r - 1.0) ** 2) / (2.0 * sigma ** 2))
    ring = ndimage.gaussian_filter(ring, 1.2)
    al = np.clip(ring * 0.88, 0, 0.88)
    # 环心偏上留一点更亮的暖芯，仍是纯柔光、无底色
    core = np.clip(1.0 - r, 0, 1) ** 2 * 0.06
    al = np.clip(al + core, 0, 0.90)
    return save_layer((255, 213, 138), al, "special_aura")


def star_polygon(cx, cy, r, rot=-90.0):
    pts = []
    for k in range(10):
        ang = math.radians(rot + k * 36.0)
        rr = r if k % 2 == 0 else r * 0.42
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    return pts


def make_star_mark():
    # 4x 超采样画五角星， Lanczos 缩回获得干净抗锯齿边缘
    K = 4
    m = Image.new("L", (1024 * K, 1024 * K), 0)
    d = ImageDraw.Draw(m)
    stars = [(655, 700, 30.0), (700, 668, 20.0), (622, 738, 14.0)]
    for cx, cy, r in stars:
        d.polygon([(x * K, y * K) for x, y in star_polygon(cx, cy, r)],
                  fill=255)
    al = np.asarray(m.resize((1024, 1024), Image.LANCZOS)).astype(
        np.float32) / 255.0
    im, _ = save_layer((255, 255, 255), al, "special_star_mark")
    return im, stars


def preview(layers):
    """验收拼版：上排 blue、下排 black，列为 原图 / glow / aura / star / 全叠。"""
    import run_assemble as ra
    cell, cols, rows = 320, 5, 2
    sheet = Image.new("RGB", (cell * cols, cell * rows), (168, 168, 168))
    for ri, coat in enumerate(("blue", "black")):
        img, _ = ra.assemble(coat, "short", "normal", "large",
                             "round_blue", verbose=False)
        base = img.convert("RGBA")
        for ci, keys in enumerate(([], ["glow"], ["aura"], ["star"],
                                   ["glow", "aura", "star"])):
            comp = base.copy()
            for k in keys:
                comp.alpha_composite(layers[k], (0, 0))
            bg = Image.new("RGBA", (1024, 1024), (168, 168, 168, 255))
            bg.alpha_composite(comp)
            sheet.paste(bg.resize((cell, cell), Image.LANCZOS).convert("RGB"),
                        (ci * cell, ri * cell))
    p = os.path.join(REV, "_special_layers.png")
    sheet.save(p)
    print("saved", os.path.basename(p))


def main():
    glow, pg = make_glow()
    aura, pa = make_aura()
    star, stars = make_star_mark()

    # 客观自检：alpha 外沿衰减、环体尺寸、星标落在身体范围内
    ga = np.asarray(glow)[..., 3].astype(np.float32) / 255.0
    aa = np.asarray(aura)[..., 3].astype(np.float32) / 255.0
    sa = np.asarray(star)[..., 3].astype(np.float32) / 255.0
    print("glow  maxA=%.3f  边缘(距轮廓>120px)均值=%.4f  体内均值=%.3f"
          % (ga.max(), ga[ndimage.distance_transform_edt(body_a < .5) > 120].mean(),
             ga[body_a > .9].mean()))
    ys, xs = np.where(aa > 0.15)
    print("aura  bbox=(%d,%d,%d,%d) 宽=%d 高=%d 中心=(%d,%d)"
          % (xs.min(), ys.min(), xs.max(), ys.max(),
             xs.max() - xs.min(), ys.max() - ys.min(),
             (xs.min() + xs.max()) // 2, (ys.min() + ys.max()) // 2))
    inside = sa > 0.5
    print("star  maskPx=%d  落在身体alpha内=%d (%.1f%%)  三颗中心=%s"
          % (int(inside.sum()), int((inside & (body_a > .5)).sum()),
             100.0 * (inside & (body_a > .5)).sum() / max(1, inside.sum()),
             [(x, y, r) for x, y, r in stars]))

    # 验收拼版里星标按产品侧约定「按毛色上色」做一次金色 tint，
    # 否则纯白 alpha 遮罩叠在白色胸毛上几乎看不见（交付文件本身仍是纯白遮罩）。
    tinted = np.asarray(star).copy()
    tinted[..., 0] = 255; tinted[..., 1] = 208; tinted[..., 2] = 96
    layers = {"glow": glow, "aura": aura,
              "star": Image.fromarray(tinted, "RGBA")}
    preview(layers)

    meta = {
        "schemaVersion": "1.0",
        "note": "v1.4 R5：special 三件套由美术侧交付，不再依赖产品侧程序化兜底。",
        "canvas": "1024x1024 RGBA，全画布对齐，(0,0) 叠加",
        "layers": {
            "special_glow": {
                "file": "special_glow@1024.png",
                "procedural": False, "blend": "alpha-over",
                "clipToBody": False,
                "description": "贴身柔光，无底色；外沿按高斯自然衰减到 0，可整只叠加",
                "color": [255, 246, 214],
            },
            "special_aura": {
                "file": "special_aura@1024.png",
                "procedural": False, "blend": "alpha-over",
                "clipToBody": False,
                "description": "头顶暖色光环；环心 (640,128)，水平直径 300px，"
                               "环体宽 17px，柔边；俯视透视取 ry=58 椭圆",
                "color": [255, 213, 138],
            },
            "special_star_mark": {
                "file": "special_star_mark@1024.png",
                "procedural": False, "blend": "tint-by-coat",
                "clipToBody": True,
                "description": "胸腹侧一簇 3 颗五角星，纯 alpha 遮罩（RGB 恒白）；"
                               "产品侧按毛色上色并裁到身体范围内",
                "stars": [{"cx": x, "cy": y, "r": r} for x, y, r in stars],
            },
        },
        "composedOf": {
            "special_ear_star": ["Ears/ear_star_L.png", "Ears/ear_star_R.png"],
            "special_pupil_star": ["Eyes/pupil_star.png"],
            "special_twin_tail": ["Tails/tail_twin.png"],
        },
        "notes": "traits.json 的 special.values 共 6 项：3 项为本目录实体文件，"
                 "另 3 项为既有部件组合，不做空引用。",
    }
    mp = os.path.join(S, "_special_meta.json")
    json.dump(meta, open(mp, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("meta ->", os.path.basename(mp))


if __name__ == "__main__":
    main()
