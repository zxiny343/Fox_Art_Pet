# -*- coding: utf-8 -*-
"""批量组装若干性状组合，输出拼版图供目视验收，并做客观数值自检。"""
import os
import sys
import json
import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_assemble as ra

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

COMBOS = [
    # coat,          tail,     ear,       eye,           pupil,  pattern
    ("blue",         "normal", "large",   "round_blue",  None,   None),
    ("orange",       "long",   "pointed", "almond_gold", "slit", "stripes"),
    ("white",        "fluffy", "round",   "round_red",   None,   None),
    ("purple",       "curl",   "star",    "almond_purple", None, "spots"),
    ("obsidian_gold", "twin",  "large",   "round_gold",  None,   None),
    ("mint",         "short",  "small",   "sleepy_green", None,  "gradient"),
    ("black",        "normal", "star",    "almond_cyan", "star", None),
    ("sakura",       "fluffy", "round",   "round_purple", None,  "facemark"),
]


CORE_BBOX = (189, 150, 877, 928)   # 统一身体核心包络（全毛色实测一致）


def core_of(coat):
    core, _ = ra.make_core(coat, "short", seam="socketfill")
    a = np.asarray(core)[..., 3] > 8
    ys, xs = np.where(a)
    return a, (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def check(img, label, core_a=None, core_bbox=None):
    a = np.asarray(img)[..., 3] > 8
    lab, n = ndimage.label(a)
    sizes = sorted(ndimage.sum(a, lab, range(1, n + 1)).astype(int),
                   reverse=True)
    ys, xs = np.where(a)
    # 包络 v1.2：耳朵/尾巴允许突破包络，只要求不出血（离画布边 >= 4px）
    no_clip = (xs.min() >= 4 and ys.min() >= 4 and xs.max() <= 1019
               and ys.max() <= 1019)
    # 身体核心必须保持统一（这是唯一被强制对齐的对象）
    ok_core = (core_bbox is None or core_bbox == CORE_BBOX)
    # 破洞只统计"身体范围内"的透明缺口；
    # 双尾之间被围住的 background 口袋属于造型本身，不算破洞。
    filled = ndimage.binary_fill_holes(a)
    pockets = filled & ~a
    if core_a is not None:
        pockets = pockets & ndimage.binary_dilation(core_a, iterations=2)
    holes = int(pockets.sum())
    big = [s for s in sizes if s > 500]
    print("  %-26s comps=%d(>500px:%d) bbox=(%d,%d,%d,%d) noClip=%s "
          "coreBbox=%s bodyHoles=%d"
          % (label, n, len(big), xs.min(), ys.min(), xs.max(), ys.max(),
             no_clip, ok_core, holes))
    return len(big) == 1 and no_clip and ok_core and holes == 0


def main():
    cells = []
    allok = True
    for i, (coat, tail, ear, eye, pupil, pat) in enumerate(COMBOS):
        img, used = ra.assemble(coat, "short", tail, ear, eye, pupil, pat,
                                verbose=False)
        label = "%s/%s/%s" % (coat, tail, ear)
        ca, cb = core_of(coat)
        ok = check(img, label, core_a=ca, core_bbox=cb)
        allok &= ok
        ra.export(img, "fox_%s_%s_%s" % (coat, tail, ear))
        bg = Image.new("RGBA", (1024, 1024), (244, 244, 244, 255))
        bg.alpha_composite(img)
        cells.append(bg.convert("RGB").resize((300, 300), Image.LANCZOS))
        print("     used:", used)
    cols = 4
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (300 * cols, 300 * rows), (255, 255, 255))
    for i, c in enumerate(cells):
        sheet.paste(c, ((i % cols) * 300, (i // cols) * 300))
    p = os.path.join(B, "09_Review", "_assemble_batch.png")
    sheet.save(p)
    print("sheet ->", p)
    print("ALL OBJECTIVE CHECKS:", "PASS" if allok else "FAIL")


if __name__ == "__main__":
    main()
