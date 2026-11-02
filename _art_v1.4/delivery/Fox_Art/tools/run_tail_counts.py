# -*- coding: utf-8 -*-
"""v1.4 验收图：6 种尾型（含 short/thin，R1 修复项）× 3 毛色组装对照表。

输出：09_Review/_tail_counts.png
自检：连通域 / 不出血 / bodyCore 包络统一 / 身体破洞（复用 run_batch.check）。
"""
import os
import sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import run_assemble as ra

B = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REVIEW = os.path.join(B, "09_Review")

# v1.4：R1 验收要求本图含修好的 short / thin 两格，列扩到 6 种尾型
TAILS = ["short", "thin", "triple", "quad", "quint", "nine"]
COATS = ["blue", "orange", "purple"]

from run_batch import check, core_of   # noqa: E402


def main():
    results = []
    thumbs = []
    for coat in COATS:
        core_a, core_bb = core_of(coat)
        for tail in TAILS:
            img, used = ra.assemble(coat, "short", tail, "large",
                                    "round_blue", verbose=False)
            label = "%s/%s" % (coat, tail)
            ok = check(img, label, core_a, core_bb)
            results.append((label, ok))
            thumbs.append((label, img))
    n_ok = sum(1 for _, ok in results if ok)
    print("== %d/%d PASS ==" % (n_ok, len(results)))

    # 拼版：行=毛色，列=尾数
    cell = 384
    sheet = Image.new("RGB", (cell * len(TAILS), cell * len(COATS)),
                      (170, 170, 170))
    for r in range(len(COATS)):
        for c in range(len(TAILS)):
            _, img = thumbs[r * len(TAILS) + c]
            t = img.resize((cell, cell), Image.LANCZOS)
            bg = Image.new("RGBA", (cell, cell), (170, 170, 170, 255))
            bg.alpha_composite(t, (0, 0))
            sheet.paste(bg.convert("RGB"), (c * cell, r * cell))
    out = os.path.join(REVIEW, "_tail_counts.png")
    sheet.save(out)
    print("saved", out)
    return n_ok == len(results)


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
