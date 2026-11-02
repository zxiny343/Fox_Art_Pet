# -*- coding: utf-8 -*-
"""R2（P1）修复：多尾分支根部的深色描边叠影 + 1~2px 白色接缝线。

根因：每条分支都是带完整闭合描边的 tail_normal 副本，N 条 = N 圈描边在
tail_root(425,505) 附近互相叠压；分支之间留下描边都没覆盖到的空隙。

修法（返修单 2.4 方案 A 的轻量实现，只处理根节点区域）：
  - 距 root < 80px 全强度、80~110px 羽化过渡
  - 该区内：把「整体形状内部」的描边像素换成最近的非描边毛色（去内部叠影）
  - 该区内：对 alpha 做 1 次 closing，填掉 1~2px 白缝，新像素取邻近毛色
  - 只保留最外层轮廓描边（interior = erosion(fill_holes(alpha), 4)）
  - 区域外用羽化权重平滑混合，不出现圆盘硬边
"""
import os, sys, json
import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_assemble as ra

B = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
M = os.path.join(B, "assets", "master")
T = os.path.join(M, "Tails")
E512 = os.path.join(B, "assets", "export_512")
E256 = os.path.join(B, "assets", "export_256")
REV = os.path.join(B, "09_Review")
ROOT = np.array([425.0, 505.0])
NAMES = ["twin", "triple", "quad", "quint", "nine"]
R_IN, R_OUT = 110.0, 160.0

YY, XX = np.mgrid[0:1024, 0:1024]
_d = np.hypot(XX - ROOT[0], YY - ROOT[1])
W = np.clip((R_OUT - _d) / (R_OUT - R_IN), 0.0, 1.0)
W = ndimage.gaussian_filter(W, 1.5)
DISC = _d < R_OUT + 4


def make_root_field(normal):
    """从 tail_normal 构造连续毛流场：去掉描边像素，并把有效毛色外推到全画布。
    D 区内所有分支都改用这一份毛流 => 从数学上消除 N 圈描边/BICUBIC 边缘
    抗锯齿条纹互相叠加，根部看起来是「同一丛毛里扇出多条尾巴」。"""
    rgb = normal[..., :3].astype(np.float32)
    a = normal[..., 3] > 8
    good = a & (rgb.mean(2) >= 96)
    _, inds = ndimage.distance_transform_edt(~good, return_indices=True)
    flat = rgb.reshape(-1, 3)
    field = flat[inds[0] * 1024 + inds[1]].reshape(1024, 1024, 3)
    # 轻微柔化，避免外推产生硬纹
    return ndimage.gaussian_filter(field, (1.2, 1.2, 0))


def fix_one(arr, field):
    rgb = arr[..., :3].astype(np.float32)
    al = arr[..., 3]
    a = al > 8
    lum = rgb.mean(2)
    stroke = (lum < 96) & a
    filled = ndimage.binary_fill_holes(a)
    interior = ndimage.binary_erosion(filled, iterations=4)
    inner_stroke = stroke & interior & DISC

    # 合形：填 1~2px 白缝 + 把根区半透明抗锯齿边缘硬化为不透明
    # （灰白雾块的根源就是 N 个副本的半透明边缘互相叠加，只换 RGB 消不掉）
    closed = ndimage.binary_closing(a, structure=np.ones((3, 3)), iterations=1)
    gap = closed & ~a & DISC
    hard = np.where(closed, 255.0, 0.0)

    w = W[..., None]
    # 根部统一毛流；内部描边与白缝处强制使用
    new_rgb = field * w + rgb * (1 - w)
    force = ((inner_stroke | gap) & DISC)[..., None]
    new_rgb = np.where(force, field, new_rgb)
    out_al = np.clip(al * (1 - W) + hard * W, 0, 255)
    out = arr.copy()
    out[..., :3] = np.clip(new_rgb, 0, 255).astype(np.uint8)
    out[..., 3] = out_al.astype(np.uint8)
    return out, int(inner_stroke.sum()), int(gap.sum())


def main():
    normal = np.asarray(Image.open(os.path.join(T, "tail_normal.png"))
                        .convert("RGBA"))
    field = make_root_field(normal)
    info = {}
    for n in NAMES:
        p = os.path.join(T, "tail_%s.png" % n)
        arr = np.asarray(Image.open(p).convert("RGBA")).copy()
        before_a = (arr[..., 3] > 8).sum()
        out, ns, ng = fix_one(arr, field)
        Image.fromarray(out, "RGBA").save(p)
        for sz, d in ((512, E512), (256, E256)):
            Image.fromarray(out, "RGBA").resize((sz, sz), Image.LANCZOS).save(
                os.path.join(d, "tail_%s@%d.png" % (n, sz)))
        after_a = (out[..., 3] > 8).sum()
        info[n] = {"innerStrokePx": ns, "seamPx": ng,
                   "alphaBefore": int(before_a), "alphaAfter": int(after_a)}
        print("%-7s 内部描边%5d  白缝%4d  alpha %d -> %d"
              % (n, ns, ng, before_a, after_a))

    # --- 验收图：normal/twin/quint/nine × orange/mist_purple，根部 200x200 → 2.8x ---
    cols, rows = 4, 2
    cell = 560
    sheet = Image.new("RGB", (cell * cols, cell * rows), (170, 170, 170))
    box = (325, 405, 525, 605)
    for ri, coat in enumerate(("orange", "mist_purple")):
        for ci, tail in enumerate(("normal", "twin", "quint", "nine")):
            img, _ = ra.assemble(coat, "short", tail, "large", "round_blue",
                                 verbose=False)
            bg = Image.new("RGBA", (1024, 1024), (170, 170, 170, 255))
            bg.alpha_composite(img.convert("RGBA"), (0, 0))
            c = bg.crop(box).resize((cell, cell), Image.LANCZOS)
            sheet.paste(c.convert("RGB"), (ci * cell, ri * cell))
    sheet.save(os.path.join(REV, "_tail_root_fix.png"))
    print("saved _tail_root_fix.png")

    mp = os.path.join(T, "_tails_meta.json")
    meta = json.load(open(mp, encoding="utf-8"))
    meta["_v14_R2"] = {
        "method": "root-disc de-outline + seam closing + single outer contour",
        "radiusInner": R_IN, "radiusOuter": R_OUT, "perTail": info,
        "note": "只处理 tail_root 附近 110px；区域外保留各分支原有描边与毛流",
    }
    json.dump(meta, open(mp, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("meta updated")


if __name__ == "__main__":
    main()
