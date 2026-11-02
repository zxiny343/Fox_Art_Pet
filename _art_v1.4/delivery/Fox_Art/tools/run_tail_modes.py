# -*- coding: utf-8 -*-
"""对比三种尾巴分层方案：
  A top    尾巴压在身体上（旧方案）
  B window 身体留整块透明窗口 + tail_base 兜底（尾巴在身后）
  C seam   窗口接缝带归身体并 socket 补色（尾巴在身后，推荐）
对每种尾型都出一张，直接目视验收。
"""
import os
import sys
import numpy as np
from PIL import Image, ImageDraw

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_assemble as ra

TAILS = ["normal", "long", "fluffy", "curl", "short", "twin"]
OUT = os.path.join(B, "09_Review", "_tail_modes.png")


def render_a(coat, tail, ear="large", eye="round_blue"):
    """旧方案：把尾巴画在 body_core 之上（用整块窗口 core，尾在上）"""
    core, _ = ra.make_core(coat, "short", seam="window")
    tp = Image.open(os.path.join(ra.M, "Tails", "tail_%s.png" % tail)).convert("RGBA")
    core.alpha_composite(tp, (0, 0))
    img = core
    for side in ("L", "R"):
        img.alpha_composite(Image.open(
            os.path.join(ra.M, "Ears", "ear_%s_%s.png" % (ear, side))).convert("RGBA"), (0, 0))
    ep = Image.open(os.path.join(ra.M, "Eyes", "eye_%s.png" % eye)).convert("RGBA")
    ec = ep.crop(ep.getbbox())
    s = 118.0 / ec.width
    for anc in ("eye_l", "eye_r"):
        img, _, _ = ra.scale_rot_place(img, ec, (ec.width / 2.0 * s, ec.height / 2.0 * s),
                                       ra.ANCHORS[anc], s, 0.0)
    return img


def main():
    cols = ["A 尾巴在上(旧)", "B 透明窗口+兜底", "C 接缝归身体(推荐)"]
    cell = 340
    rows = len(TAILS)
    W = cell * 3
    H = cell * rows + 40
    sheet = Image.new("RGB", (W, H), (238, 238, 238))
    d = ImageDraw.Draw(sheet)
    for j, c in enumerate(cols):
        d.text((10 + j * cell, 12), c, fill=(20, 20, 20))
    for i, t in enumerate(TAILS):
        imgs = [
            render_a("blue", t),
            ra.assemble("blue", "short", t, "large", "round_blue", verbose=False,
                        seam="window")[0],
            ra.assemble("blue", "short", t, "large", "round_blue", verbose=False,
                        seam="socketfill")[0],
        ]
        for j, im in enumerate(imgs):
            bg = Image.new("RGBA", (1024, 1024), (150, 150, 150, 255))
            bg.alpha_composite(im)
            sm = bg.resize((cell - 8, cell - 8), Image.LANCZOS).convert("RGB")
            sheet.paste(sm, (j * cell + 4, 36 + i * cell))
        d.text((4, 36 + i * cell + cell - 22), t, fill=(200, 0, 0))
    sheet.save(OUT)
    print("->", OUT)

    # 量化：每种方案下"身体上的透明破洞"像素数（body 区域内 alpha=0 且被身体包围）
    print("\n--- 破洞/缝隙量化（组装图内的孤立透明像素，越少越好）---")
    from scipy import ndimage
    for t in TAILS:
        line = []
        for tag, im in (("A", render_a("blue", t)),
                        ("B", ra.assemble("blue", "short", t, "large", "round_blue",
                                          verbose=False, seam="window")[0]),
                        ("C", ra.assemble("blue", "short", t, "large", "round_blue",
                                          verbose=False, seam="socketfill")[0])):
            a = np.asarray(im)[..., 3] > 8
            filled = ndimage.binary_fill_holes(a)
            holes = int((filled & ~a).sum())
            lab, n = ndimage.label(a)
            line.append("%s holes=%d comps=%d" % (tag, holes, n))
        print("  tail_%-7s %s" % (t, "  ".join(line)))


if __name__ == "__main__":
    main()
