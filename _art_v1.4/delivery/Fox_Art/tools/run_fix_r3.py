# -*- coding: utf-8 -*-
"""R3（P1）重绘 ear_large_L/R：修正 Ez 位点「大耳反而最小」的语义反转。

返修单 3.2：以 ear_round 为母本，内容像素 ≈ round×1.3~1.5，topY 与
small/round 一致(169±4)，耳内绒毛/内耳色/毛流沿用 round，且描边宽度
保持 3~4px（直接整体缩放会把描边从 3px 拉到 4.5~5.5px）。

实现：
  1. 分离「外轮廓描边」：把 alpha 边界 4px 内的深色像素换成邻近填充色
  2. 以 (内容水平中心, topY) 为锚做 sx=1.20 / sy=1.16 仿射放大填充
     —— 顶部锚定，所以 topY 不变；纵向向下延伸，不盖到眼睛
  3. 对放大后的形状重画唯一一条 3px 外轮廓（宽度与母版一致）
  4. 内部深色分界线随填充放大（约 3→3.6px，在容差内）
"""
import os, sys, json
import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_assemble as ra

B = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
M = os.path.join(B, "assets", "master")
E = os.path.join(M, "Ears")
E512 = os.path.join(B, "assets", "export_512")
E256 = os.path.join(B, "assets", "export_256")
REV = os.path.join(B, "09_Review")
SX, SY = 1.20, 1.16


def nearest_fill(rgb, a, bad):
    good = a & ~bad
    _, inds = ndimage.distance_transform_edt(~good, return_indices=True)
    flat = rgb.reshape(-1, 3)
    return flat[inds[0] * 1024 + inds[1]].reshape(1024, 1024, 3)


def enlarge(src):
    arr = np.asarray(src.convert("RGBA"))
    a = arr[..., 3] > 8
    ys, xs = np.where(a)
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    cx = (x0 + x1) / 2.0
    lum = arr[..., :3].astype(np.float32).mean(2)
    dark = a & (lum < 96)
    edge = a & ~ndimage.binary_erosion(a, iterations=4)
    bad = edge & dark
    stroke_color = np.median(arr[..., :3][dark], axis=0).astype(np.uint8) \
        if dark.any() else np.array([46, 40, 56], np.uint8)
    field = nearest_fill(arr[..., :3], a, bad)
    fill = arr.copy()
    fill[..., :3] = np.where(bad[..., None], field, fill[..., :3])

    # 逆映射：x' = cx + SX*(x-cx), y' = y0 + SY*(y-y0)
    mat = (1.0 / SX, 0.0, cx - cx / SX,
           0.0, 1.0 / SY, y0 - y0 / SY)
    big = np.asarray(Image.fromarray(fill, "RGBA").transform(
        (1024, 1024), Image.AFFINE, mat, resample=Image.BICUBIC))
    A = big[..., 3] > 128
    # 7x7 一次膨胀 = 均匀 3px 外轮廓（十字迭代会留下菱形锯齿/虚线边）
    outer = ndimage.binary_dilation(A, structure=np.ones((7, 7))) & ~A
    out = big.copy()
    out[..., :3] = np.where(outer[..., None], stroke_color, out[..., :3])
    out[..., 3] = np.where(A | outer, 255, 0).astype(np.uint8)
    return Image.fromarray(out, "RGBA"), (x0, y0, x1, y1), stroke_color.tolist()


def metrics(im):
    a = np.asarray(im)[..., 3] > 8
    ys, xs = np.where(a)
    return {"px": int(a.sum()), "topY": int(ys.min()),
            "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]}


def main():
    info = {}
    for side in ("L", "R"):
        p = os.path.join(E, "ear_large_%s.png" % side)
        round_p = os.path.join(E, "ear_round_%s.png" % side)
        src = Image.open(round_p).convert("RGBA")
        out, bbox, col = enlarge(src)
        out.save(p)
        for sz, d in ((512, E512), (256, E256)):
            out.resize((sz, sz), Image.LANCZOS).save(
                os.path.join(d, "ear_large_%s@%d.png" % (side, sz)))
        m = metrics(out)
        mr = metrics(src)
        info[side] = {"round": mr, "large": m, "strokeColor": col,
                      "scale": [SX, SY]}
        print("%s  round px=%d topY=%d  ->  large px=%d topY=%d  ratio=%.3f  "
              "bbox=%s 描边色=%s"
              % (side, mr["px"], mr["topY"], m["px"], m["topY"],
                 m["px"] / mr["px"], m["bbox"], col))

    # 验收图：上排三件 1:1 并排；下排各自组装到同一只蓝狐头部
    cell = 420
    sheet = Image.new("RGB", (cell * 3, cell * 2), (180, 180, 180))
    for i, name in enumerate(("small", "round", "large")):
        im = Image.open(os.path.join(E, "ear_%s_L.png" % name)).convert("RGBA")
        bg = Image.new("RGBA", (1024, 1024), (180, 180, 180, 255))
        bg.alpha_composite(im, (0, 0))
        sheet.paste(bg.crop((400, 140, 620, 360)).resize(
            (cell, cell), Image.LANCZOS).convert("RGB"), (i * cell, 0))
    for i, name in enumerate(("small", "round", "large")):
        img, _ = ra.assemble("blue", "short", "normal", name, "round_blue",
                             verbose=False)
        bg = Image.new("RGBA", (1024, 1024), (180, 180, 180, 255))
        bg.alpha_composite(img.convert("RGBA"), (0, 0))
        sheet.paste(bg.crop((400, 120, 820, 540)).resize(
            (cell, cell), Image.LANCZOS).convert("RGB"), (i * cell, cell))
    sheet.save(os.path.join(REV, "_ear_sizes.png"))
    print("saved _ear_sizes.png")

    mp = os.path.join(E, "_ears_meta.json")
    meta = json.load(open(mp, encoding="utf-8"))
    meta["_v14_R3"] = {
        "method": "ear_round 母本 + 外轮廓分离 + 锚定 topY 放大 + 重画 3px 描边",
        "scale": [SX, SY], "metrics": info,
    }
    json.dump(meta, open(mp, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("meta updated")


if __name__ == "__main__":
    main()
