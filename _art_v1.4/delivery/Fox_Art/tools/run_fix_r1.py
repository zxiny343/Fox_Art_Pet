# -*- coding: utf-8 -*-
"""R1（P0）修复：tail_short / tail_thin 尾根缺口。

方案 = 返修单 1.4 方案 A 的「毛量渐变过渡」实现：
  body_core 挖掉的是整块 normal 尾巴窗口 W(40294px)，短尾/细尾自身只填
  7k/3k px，其余通向外部背景 => 既不封闭（repair_pockets 抓不到）也不算破洞。
  这里不把缺口平涂成纯色，而是补一层「根部绒毛过渡」：
   - RGB = 毛色 base + tail_normal 的高频毛流明暗（无白色内毛扇形、无硬描边）
   - alpha = 255*exp(-dist/40)，下限 10；距尾身越远毛量越稀
   - 只在 W & ~partAlpha 区域写入，尾身像素一个都不动
  => 母版轮廓内不再透明（hole=0），而 alpha>200 的「尾身主体」bbox 完全不变。
"""
import os, sys
import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_assemble as ra
import run_split as rs

B = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
M = os.path.join(B, "assets", "master")
E512 = os.path.join(B, "assets", "export_512")
E256 = os.path.join(B, "assets", "export_256")
REV = os.path.join(B, "09_Review")

master = np.asarray(Image.open(os.path.join(M, "Base", "fox_base_blue_q4@1024.png"))
                   .convert("RGBA"))
master_a = master[..., 3] > 8
reg, _ = rs.load()
W = master_a & rs.region_mask(reg["regions"]["tail"])
normal = np.asarray(Image.open(os.path.join(M, "Tails", "tail_normal.png"))
                   .convert("RGBA"))
BASE = np.array([108.0, 165.0, 205.0], np.float32)
_nr = normal[..., :3].astype(np.float32)
_blur = ndimage.gaussian_filter(_nr, (7, 7, 0))
_detail = np.clip(_nr - _blur, -46, 46)
FLUFF = np.clip(BASE + _detail * 0.55, 0, 255)

SCALE = 40.0
FLOOR = 10.0


def patch(part):
    pa = part[..., 3] > 8
    add = W & ~pa
    d = ndimage.distance_transform_edt(~pa)
    al = np.clip(255.0 * np.exp(-d / SCALE), FLOOR, 255.0)
    out = part.copy()
    out[add, :3] = FLUFF[add].astype(np.uint8)
    out[add, 3] = al[add].astype(np.uint8)
    return out


def hole_of(img):
    return int((master_a & (np.asarray(img)[..., 3] < 8)).sum())


def subject_bbox(img):
    aa = np.asarray(img)[..., 3] > 200
    ys, xs = np.where(aa)
    return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


def render_before():
    out = {}
    for t in ("short", "thin"):
        img, _ = ra.assemble("blue", "short", t, "large", "round_blue",
                             verbose=False)
        out[t] = img.convert("RGBA")
    return out


def composite(img, box, cell):
    bg = Image.new("RGBA", (1024, 1024), (168, 168, 168, 255))
    bg.alpha_composite(img, (0, 0))
    return bg.crop(box).resize((cell, cell), Image.LANCZOS).convert("RGB")


def main():
    before = render_before()
    info = {"r1": {"method": "root-fluff-gradient", "scale": SCALE,
                    "alphaFloor": FLOOR, "windowPx": int(W.sum())}}
    for t in ("short", "thin"):
        p = os.path.join(M, "Tails", "tail_%s.png" % t)
        part = np.asarray(Image.open(p).convert("RGBA")).copy()
        pa = part[..., 3] > 8
        ys, xs = np.where(pa)
        old_bbox_part = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
        out = patch(part)
        Image.fromarray(out, "RGBA").save(p)
        for n, d in ((512, E512), (256, E256)):
            Image.fromarray(out, "RGBA").resize((n, n), Image.LANCZOS).save(
                os.path.join(d, "tail_%s@%d.png" % (t, n)))
        print("%-6s 补丁像素=%d 部件原bbox=%s" % (t, int((W & ~pa).sum()),
                                                 old_bbox_part))
        info["r1"][t] = {"patchedPx": int((W & ~pa).sum()),
                         "partBBoxV13": list(old_bbox_part)}

    # 验收数值
    for t in ("short", "thin"):
        row = info["r1"][t]
        for coat in ("blue", "black", "haze_blue"):
            img, _ = ra.assemble(coat, "short", t, "large", "round_blue",
                                 verbose=False)
            h = hole_of(img)
            print("  %-6s %-10s hole=%d  subjectBBox=%s (v1.3: %s)"
                  % (t, coat, h, subject_bbox(img), subject_bbox(before[t])))
            row["hole_" + coat] = h
            row["subjectBBox"] = list(subject_bbox(img))
            row["subjectBBoxV13"] = list(subject_bbox(before[t]))

    # 验收图：2 行(short/thin) × 2 列(v1.3 现状 / v1.4 修复)，1x 与 2x 各一张
    for tag, box, cell in (("1x", (110, 210, 690, 790), 580),
                           ("2x", (180, 280, 500, 600), 640)):
        sheet = Image.new("RGB", (cell * 2, cell * 2), (168, 168, 168))
        for ri, t in enumerate(("short", "thin")):
            img, _ = ra.assemble("blue", "short", t, "large", "round_blue",
                                 verbose=False)
            sheet.paste(composite(before[t], box, cell), (0, ri * cell))
            sheet.paste(composite(img.convert("RGBA"), box, cell),
                        (cell, ri * cell))
        fp = os.path.join(REV, "_r1_zoom_%s.png" % tag)
        sheet.save(fp)
        print("saved", os.path.basename(fp))

    import json
    mp = os.path.join(M, "Tails", "_tails_meta.json")
    meta = json.load(open(mp, encoding="utf-8"))
    meta["_v14_R1"] = info["r1"]
    json.dump(meta, open(mp, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("meta updated")


if __name__ == "__main__":
    main()
