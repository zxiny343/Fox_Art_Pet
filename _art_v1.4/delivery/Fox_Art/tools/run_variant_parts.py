# -*- coding: utf-8 -*-
"""
阶段3-B：从"母版变体图"切出配套部件。

与阶段2 的隔离部件表不同，这里的部件来自"以母版为参考只改某部位"的整只变体图，
因此与母版同姿态、同比例、同位置，用同一套 split_regions mask 切出后天然配套，
覆盖率远高于独立生成的部件（阶段3 实测：独立件只覆盖 40-52%，配套件接近 100%）。
"""
import os
import sys
import json
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_split as rs
import fox_pipeline as fp

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(B, "09_Review", "raw_s3")
M = os.path.join(B, "assets", "master")
OUT = os.path.join(B, "assets", "master", "Parts")

# 变体图文件名 -> (部件类别, 变体名)
VARIANTS = [
    ("tail_long.png", "tail", "long"),
    ("tail_fluffy.png", "tail", "fluffy"),
    ("tail_short.png", "tail", "short"),
    ("tail_curl.png", "tail", "curl"),
    ("tail_twin.png", "tail", "twin"),
    ("ear_large.png", "ear", "large"),
    ("ear_small.png", "ear", "small"),
    ("ear_pointed.png", "ear", "pointed"),
    ("ear_round.png", "ear", "round"),
    ("ear_star.png", "ear", "star"),
]


def align_to_master(path):
    """变体图 -> 抠图 -> 规整到母版包络（同母版一样的 fit_width 装框），保证位置对齐。"""
    raw = fp.load_rgba(path)
    cut = fp.matte_by_flood(raw, tol=42)
    cut, _ = fp.keep_largest_component(cut)
    return fp.normalize(cut, fit_width=True)


def main():
    reg, _ = rs.load()
    metas = {}
    for fname, cat, vname in VARIANTS:
        p = os.path.join(RAW, fname)
        if not os.path.exists(p):
            print("MISSING", fname)
            continue
        img = align_to_master(p)
        ma = np.asarray(img)
        if cat == "tail":
            keys = ["tail"]
        else:
            keys = ["ear_L", "ear_R"]
        for k in keys:
            m = rs.region_mask(reg["regions"][k])
            part = ma.copy()
            part[..., 3] = np.where(m, ma[..., 3], 0)
            im = Image.fromarray(part, "RGBA")
            bb = im.getbbox()
            if bb is None:
                print("  !! %s/%s empty" % (fname, k))
                continue
            out_name = ("tail_%s.png" % vname) if cat == "tail" else \
                       ("ear_%s_%s.png" % (vname, k[-1]))
            dst_dir = os.path.join(M, "Tails" if cat == "tail" else "Ears")
            im.save(os.path.join(dst_dir, out_name))
            metas[out_name] = {
                "source": fname,
                "region": k,
                "variant": vname,
                "category": "tails" if cat == "tail" else "ears",
                "contentBBox": list(bb),
                "contentSize": [bb[2] - bb[0], bb[3] - bb[1]],
                "aligned": True,
                "note": "从母版变体图按同一 mask 切出，与母版同姿态同位置，天然配套",
            }
            print("  %-18s bbox=%s size=%s" % (out_name, bb,
                                               metas[out_name]["contentSize"]))
    old = os.path.join(OUT, "_variant_parts_meta.json")
    json.dump(metas, open(old, "w", encoding="utf-8"), ensure_ascii=False,
              indent=2)
    print("meta ->", old)


if __name__ == "__main__":
    main()
