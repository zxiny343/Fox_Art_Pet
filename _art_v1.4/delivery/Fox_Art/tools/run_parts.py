# -*- coding: utf-8 -*-
"""
阶段2-B：白底部件表 -> 独立可替换部件 PNG
用法: python run_parts.py <sheet.png> <category> <name1,name2,...> [--min-area N]
"""
import os
import sys
import json

BASE = "C:/Users/zxiny/WorkBuddy/2026-11-01-00-53-44/Fox_Art"
sys.path.insert(0, BASE + "/tools")
import numpy as np
from PIL import Image
import fox_pipeline as fp
import fox_traits as ft


def order_row_major(parts):
    """先按 y 分行，再在行内按 x 排序（部件表可能是多行网格）。"""
    if not parts:
        return parts
    info = []
    for p in parts:
        bb = p.getbbox()
        info.append((p, bb, (bb[1] + bb[3]) / 2.0, (bb[0] + bb[2]) / 2.0))
    heights = sorted(bb[3] - bb[1] for _, bb, _, _ in info)
    med_h = heights[len(heights) // 2]
    rows, cur, cur_y = [], [], info[0][2]
    for item in sorted(info, key=lambda t: t[2]):
        if abs(item[2] - cur_y) > max(med_h * 0.6, 20):
            rows.append(cur)
            cur, cur_y = [], item[2]
        cur.append(item)
    rows.append(cur)
    out = []
    for r in rows:
        out.extend([it[0] for it in sorted(r, key=lambda t: t[3])])
    return out


def main():
    sheet_path = sys.argv[1]
    category = sys.argv[2]
    names = sys.argv[3].split(",")
    min_area = 1200
    cut_bottom = 0.0
    rotate = False
    split_halves = False
    if "--min-area" in sys.argv:
        min_area = int(sys.argv[sys.argv.index("--min-area") + 1])
    if "--cut-bottom" in sys.argv:
        cut_bottom = float(sys.argv[sys.argv.index("--cut-bottom") + 1])
    if "--rotate" in sys.argv:
        rotate = True
    if "--split-halves" in sys.argv:
        split_halves = True

    cws, _ = ft.load_colorways(BASE + "/01_Data/colorways.json")
    raw = fp.load_rgba(sheet_path)
    cut = fp.matte_by_flood(raw, tol=46)
    cut = fp.crisp_alpha(cut, thr=128, feather=0.6)
    parts = ft.split_components(cut, min_area=min_area, max_count=16)
    parts = order_row_major(parts)

    def halve(p):
        bb = p.getbbox()
        mx = (bb[0] + bb[2]) // 2
        return [p.crop((bb[0], bb[1], mx, bb[3])),
                p.crop((mx, bb[1], bb[2], bb[3]))]

    pieces = []
    for p in parts:
        pieces.extend(halve(p) if split_halves else [p])

    print("sheet:", os.path.basename(sheet_path), "components:", len(parts),
          "pieces:", len(pieces), "expected:", len(names))
    if len(pieces) != len(names):
        print("!! 数量不符，按最大面积取前 N 个，请人工核对拼版图")
        pieces = sorted(pieces, key=lambda p: (p.getbbox()[2] - p.getbbox()[0]) *
                        (p.getbbox()[3] - p.getbbox()[1]), reverse=True)[:len(names)]
        pieces = order_row_major(pieces)

    outdir = os.path.join(BASE, "assets/master",
                          {"ears": "Ears", "tails": "Tails", "eyes": "Eyes",
                           "pupils": "Eyes"}[category])
    os.makedirs(outdir, exist_ok=True)
    review = os.path.join(BASE, "09_Review")
    os.makedirs(review, exist_ok=True)

    fixed_scale = ft.common_scale(pieces, category, pad_ratio=0.10)
    print("common scale:", round(fixed_scale, 4))

    metas, items = {}, []
    for i, (nm, p) in enumerate(zip(names, pieces)):
        # palette_force 只对齐调色板，力度 0.7 保留生成图自身的明暗细节
        forced = ft.palette_force(p, cws["blue"], "blue", cws, strength=0.70) \
            if category != "pupils" else p
        forced = ft.cut_bottom_fraction(forced, cut_bottom)
        if rotate:
            canvas, meta = ft.fit_part_rotated(forced, category,
                                               fixed_scale=fixed_scale)
        else:
            canvas, meta = ft.fit_part(forced, category,
                                       fixed_scale=fixed_scale)
        meta["cutBottom"] = cut_bottom
        fn = "%s_%s" % (category[:-1] if category.endswith("s") else category, nm)
        canvas.save(os.path.join(outdir, fn + ".png"))
        meta["file"] = fn + ".png"
        meta["sourceSheet"] = os.path.basename(sheet_path)
        meta["index"] = i
        metas[nm] = meta
        items.append((canvas, nm))
        print("  ->", fn + ".png", meta["placedSize"], "bbox", meta["placedBBox"])

    with open(os.path.join(outdir, "_%s_meta.json" % category), "w",
              encoding="utf-8") as f:
        json.dump(metas, f, ensure_ascii=False, indent=2)

    sheet = ft.contact_sheet(items, os.path.join(review, "_parts_%s.png" % category),
                             cell=300, cols=len(items))
    print("review sheet:", sheet)


if __name__ == "__main__":
    main()
