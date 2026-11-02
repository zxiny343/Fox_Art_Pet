# -*- coding: utf-8 -*-
"""
Fantasy Fox 阶段3 母版模块化拆分
--------------------------------------------------
把 1024 母版按 split_regions.json 定义的区域切成分层部件：
  tail / ear_L / ear_R / eye_L / eye_R  = 母版原部件（与身体像素级无缝）
  body_core                              = 母版挖掉上述区域后的主体
预览模式输出区域叠加图供目视验证；正式模式输出部件 PNG + meta。
"""
import os
import sys
import json
import numpy as np
from PIL import Image, ImageDraw

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(B, "assets", "master", "Base", "fox_base_blue_q4@1024.png")
REG = os.path.join(B, "01_Data", "split_regions.json")
OUT = os.path.join(B, "assets", "master", "Parts")


def _grid(w=1024, h=1024):
    yy, xx = np.mgrid[0:h, 0:w]
    return xx.astype(np.float32), yy.astype(np.float32)


def region_mask(spec, w=1024, h=1024):
    xx, yy = _grid(w, h)
    if spec["type"] in ("capsule", "polyline"):
        pts = spec.get("points") or [spec["p0"], spec["p1"]]
        r2 = spec["radius"] ** 2
        best = np.full((h, w), 1e18, np.float32)
        for i in range(len(pts) - 1):
            (x0, y0), (x1, y1) = pts[i], pts[i + 1]
            vx, vy = float(x1 - x0), float(y1 - y0)
            L2 = max(vx * vx + vy * vy, 1e-6)
            t = np.clip(((xx - x0) * vx + (yy - y0) * vy) / L2, 0.0, 1.0)
            dx = xx - (x0 + t * vx)
            dy = yy - (y0 + t * vy)
            best = np.minimum(best, dx * dx + dy * dy)
        m = best <= r2
        clip = spec.get("clip")
        if clip:
            if "yMax" in clip:
                m = m & (yy <= clip["yMax"])
            if "yMin" in clip:
                m = m & (yy >= clip["yMin"])
            if "xMax" in clip:
                m = m & (xx <= clip["xMax"])
            if "xMin" in clip:
                m = m & (xx >= clip["xMin"])
        return m
    if spec["type"] == "ellipse":
        cx, cy = spec["center"]
        a = float(np.radians(spec.get("rotDeg", 0)))
        ca, sa = np.cos(a), np.sin(a)
        u = (xx - cx) * ca + (yy - cy) * sa
        v = -(xx - cx) * sa + (yy - cy) * ca
        return (u / spec["rx"]) ** 2 + (v / spec["ry"]) ** 2 <= 1.0
    raise ValueError("unknown region type: %s" % spec["type"])


def dilate(mask, n):
    if n <= 0:
        return mask
    out = mask.copy()
    for _ in range(n):
        p = np.pad(out, 1, mode="constant", constant_values=False)
        out = (p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:] | out)
    return out


def load():
    reg = json.load(open(REG, encoding="utf-8"))
    master = Image.open(MASTER).convert("RGBA")
    return reg, master


def preview():
    reg, master = load()
    bg = Image.new("RGBA", (1024, 1024), (255, 255, 255, 255))
    bg.alpha_composite(master)
    im = bg.convert("RGB")
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    colors = {"tail": (255, 40, 40), "ear_L": (40, 190, 40),
              "ear_R": (60, 90, 240), "eye_L": (250, 200, 0),
              "eye_R": (0, 210, 210)}
    for k, spec in reg["regions"].items():
        m = dilate(region_mask(spec), reg.get("dilatePx", 3))
        c = colors.get(k, (200, 0, 200))
        arr = np.zeros((1024, 1024, 4), np.uint8)
        arr[..., 0], arr[..., 1], arr[..., 2] = c
        arr[..., 3] = np.where(m, 60, 0)
        d_im = Image.fromarray(arr, "RGBA")
        ov.alpha_composite(d_im)
        # 只画区域真实轮廓，不画外接矩形（外接矩形会误导判断）
        edge = m & ~dilate(~m, 1)
        arr2 = np.zeros((1024, 1024, 4), np.uint8)
        arr2[..., 0], arr2[..., 1], arr2[..., 2] = c
        arr2[..., 3] = np.where(edge, 255, 0)
        ov.alpha_composite(Image.fromarray(arr2, "RGBA"))
        ys, xs = np.where(m)
        d.text((int(xs.mean()) - 14, int(ys.mean()) - 8), k, fill=c + (255,))
    im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
    p = os.path.join(B, "09_Review", "_split_preview.png")
    im.save(p)
    print("preview ->", p)
    for k, spec in reg["regions"].items():
        m = region_mask(spec)
        ys, xs = np.where(m)
        print("  %-6s bbox=(%d,%d)-(%d,%d) area=%d" %
              (k, xs.min(), ys.min(), xs.max(), ys.max(), int(m.sum())))


def split():
    reg, master = load()
    os.makedirs(OUT, exist_ok=True)
    ma = np.asarray(master)
    alpha_all = ma[..., 3] > 8
    union = np.zeros((1024, 1024), bool)
    metas = {}
    for k, spec in reg["regions"].items():
        m = region_mask(spec)
        union |= m
        part = ma.copy()
        part[..., 3] = np.where(m, ma[..., 3], 0)
        p = Image.fromarray(part, "RGBA")
        f = os.path.join(OUT, "part_%s@1024.png" % k)
        p.save(f)
        ys, xs = np.where(m & alpha_all)
        metas[k] = {
            "file": os.path.basename(f),
            "regionType": spec["type"],
            "regionSpec": spec,
            "contentBBox": [int(xs.min()), int(ys.min()),
                            int(xs.max()) + 1, int(ys.max()) + 1],
            "contentSize": [int(xs.max()) - int(xs.min()) + 1,
                            int(ys.max()) - int(ys.min()) + 1],
            "coverPx": int((m & alpha_all).sum()),
        }
        print("part %-6s -> %s  bbox=%s" % (k, os.path.basename(f),
                                            metas[k]["contentBBox"]))

    core_a = ma[..., 3].copy()
    metas["body_core"] = {"file": "part_body_core@1024.png",
                          "regionType": "master minus union(regions) dilated"}
    hole = dilate(union, reg.get("dilatePx", 3)) & (ma[..., 3] > 8)
    core_a[dilate(union, reg.get("dilatePx", 3))] = 0
    core = ma.copy()
    core[..., 3] = core_a
    # socket 补色：挖空区用身体邻色做最近邻扩散填充，
    # 避免"小部件盖不满挖空区"时露出透明洞（2D 换装的标准 socket 层做法）
    if hole.any():
        from scipy import ndimage
        rgb = ma[..., :3]
        known = (~hole) & (ma[..., 3] > 8)
        idx = ndimage.distance_transform_edt(~known, return_distances=False,
                                             return_indices=True)
        fill = rgb[idx[0], idx[1]]
        cr = core[..., :3].copy()
        cr[hole] = fill[hole]
        core[..., :3] = cr
        core[..., 3] = np.where(hole, 255, core[..., 3])
        metas["body_core"]["socketPx"] = int(hole.sum())
        print("socket inpaint -> filled %d px" % int(hole.sum()))
    Image.fromarray(core, "RGBA").save(
        os.path.join(OUT, "part_body_core@1024.png"))
    metas["body_core"]["removedPx"] = int(((ma[..., 3] > 8) & (core_a == 0)).sum())
    metas["body_core"]["socketPx"] = int(metas["body_core"].get("socketPx", 0))
    print("body_core -> removed %d px, socket filled %d px"
          % (metas["body_core"]["removedPx"], metas["body_core"]["socketPx"]))

    json.dump(metas, open(os.path.join(OUT, "_parts_meta.json"), "w",
                          encoding="utf-8"), ensure_ascii=False, indent=2)
    print("meta ->", os.path.join(OUT, "_parts_meta.json"))


if __name__ == "__main__":
    if "--split" in sys.argv:
        split()
    else:
        preview()
