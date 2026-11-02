# -*- coding: utf-8 -*-
"""P2 验收图：折耳 / 铜瞳 / 细尾（虎斑对照在 _pattern_tabby_vs_stripes.png）。"""
import os
import sys

B = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(B, "tools"))
from PIL import Image
import run_assemble as ra

REVIEW = os.path.join(B, "09_Review")


def paste(sheet, img, i, cell, crop=None):
    bg = Image.new("RGBA", (1024, 1024), (170, 170, 170, 255))
    bg.alpha_composite(img, (0, 0))
    if crop:
        bg = bg.crop(crop)
    sheet.paste(bg.resize((cell, cell), Image.LANCZOS).convert("RGB"),
                (i * cell, 0))


def main():
    cell = 384

    # 1) 折耳：与 ear_small / ear_large 对照（头部特写）
    s = Image.new("RGB", (cell * 3, cell), (170, 170, 170))
    for i, ear in enumerate(("fold", "small", "large")):
        img, _ = ra.assemble("blue", "short", "normal", ear,
                             "round_blue", verbose=False)
        paste(s, img, i, cell, crop=(400, 140, 900, 640))
    s.save(os.path.join(REVIEW, "_p2_fold_ear.png"))

    # 2) 铜瞳：三种眼型 × copper，与 gold 对照（眼部特写）
    s = Image.new("RGB", (cell * 4, cell), (170, 170, 170))
    cols = [("round", "copper"), ("almond", "copper"),
            ("sleepy", "copper"), ("round", "gold")]
    for i, (sh, col) in enumerate(cols):
        img, _ = ra.assemble("blue", "short", "normal", "large",
                             "%s_%s" % (sh, col), verbose=False)
        paste(s, img, i, cell, crop=(520, 420, 880, 620))
    s.save(os.path.join(REVIEW, "_p2_copper_eye.png"))

    # 3) 细尾：thin vs normal vs fluffy
    s = Image.new("RGB", (cell * 3, cell), (170, 170, 170))
    for i, tail in enumerate(("thin", "normal", "fluffy")):
        img, _ = ra.assemble("blue", "short", tail, "large",
                             "round_blue", verbose=False)
        paste(s, img, i, cell)
    s.save(os.path.join(REVIEW, "_p2_thin_tail.png"))
    print("P2 验收图 -> 09_Review/_p2_fold_ear.png, _p2_copper_eye.png, "
          "_p2_thin_tail.png")


if __name__ == "__main__":
    main()
