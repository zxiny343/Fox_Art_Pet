# -*- coding: utf-8 -*-
"""渲染 10 种表情对照表（头部特写 + 全身小图）。"""
import os
import sys
import json
import numpy as np
from PIL import Image, ImageDraw

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = os.path.join(B, "assets", "master")
EXP = os.path.join(M, "Expressions")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_assemble as ra

DATA = json.load(open(os.path.join(B, "01_Data", "expressions.json"), encoding="utf-8"))
HEAD = (500, 320, 920, 680)     # 头部特写裁剪框


def render(e, coat="blue", tail="normal", ear="large"):
    eye = e["eye"]
    arc = None
    if eye in ("eye_closed", "eye_happy"):
        arc = os.path.join(EXP, "%s_%s.png" % (eye, coat))
        eye = None
    elif eye.startswith("eye_"):
        eye = eye[4:]                      # 组装器内部会再加 eye_ 前缀
    img, _ = ra.assemble(coat, "short", tail, ear, eye, verbose=False)
    for side in ("L", "R"):
        p = os.path.join(EXP, "brow_%s_%s_%s.png" % (e["brow"], side, coat))
        img.alpha_composite(Image.open(p).convert("RGBA"), (0, 0))
    img.alpha_composite(Image.open(os.path.join(EXP, "mouth_%s_%s.png"
                                                % (e["mouth"], coat))).convert("RGBA"), (0, 0))
    if arc:
        img.alpha_composite(Image.open(arc).convert("RGBA"), (0, 0))
    if e["blush"]:
        img.alpha_composite(Image.open(os.path.join(EXP, "blush.png")).convert("RGBA"), (0, 0))
    return img


def main():
    exprs = DATA["expressions"]
    cell, cols = 336, 5
    rows = (len(exprs) + cols - 1) // cols
    sheet = Image.new("RGB", (cell * cols, cell * rows + 26), (240, 240, 240))
    d = ImageDraw.Draw(sheet)
    d.text((10, 6), "10 expressions  (coat=blue, tail=normal, ear=large)  "
                    "head crop x500-920 y320-680", fill=(20, 20, 20))
    full = []
    for i, e in enumerate(exprs):
        img = render(e)
        full.append(img)
        c = img.crop(HEAD)
        bg = Image.new("RGBA", c.size, (150, 150, 150, 255))
        bg.alpha_composite(c)
        sm = bg.convert("RGB").resize((cell - 6, cell - 6), Image.LANCZOS)
        x, y = (i % cols) * cell + 3, 26 + (i // cols) * cell
        sheet.paste(sm, (x, y))
        d.text((x + 6, y + cell - 24), "%s %s" % (e["id"], e["name"]), fill=(200, 30, 30))
    p = os.path.join(B, "09_Review", "_expressions_sheet.png")
    sheet.save(p)
    print("sheet ->", p)

    # 全身小图
    fw, fh = 260, 260
    fs = Image.new("RGB", (fw * cols, fh * rows), (244, 244, 244))
    for i, img in enumerate(full):
        bg = Image.new("RGBA", (1024, 1024), (244, 244, 244, 255))
        bg.alpha_composite(img)
        fs.paste(bg.convert("RGB").resize((fw, fh), Image.LANCZOS),
                 ((i % cols) * fw, (i // cols) * fh))
    p2 = os.path.join(B, "09_Review", "_expressions_full.png")
    fs.save(p2)
    print("full  ->", p2)


if __name__ == "__main__":
    main()
