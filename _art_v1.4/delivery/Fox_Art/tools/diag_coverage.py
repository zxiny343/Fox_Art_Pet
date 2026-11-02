# -*- coding: utf-8 -*-
"""诊断：各可替换部件对 socket 挖空区的覆盖率，定位谁没盖住导致露出补色块。"""
import os
import sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_assemble as ra
import run_split as rs

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
reg, _ = rs.load()
union = np.zeros((1024, 1024), bool)
for k, s in reg["regions"].items():
    union |= rs.region_mask(s)
HOLE = rs.dilate(union, reg.get("dilatePx", 3))


def coverage(coat, tail, ear, eye):
    core, src = ra.make_core(coat, "short")
    ma = np.asarray(Image.open(src).convert("RGBA"))
    hole = HOLE & (ma[..., 3] > 8)
    used = np.zeros((1024, 1024), bool)
    steps = []

    # tail
    tm = ra.load_meta("Tails", "tails")[tail]
    tp = Image.open(os.path.join(ra.M, "Tails", tm["file"])).convert("RGBA")
    rot = ra.TAIL_TARGET_AXIS - (-123.1)
    tp_r, root_r = ra.rotate_about(tp, tuple(tm["rootPointInCanvas"]), rot)
    L_part = ra.axis_extent(tp_r, root_r, ra.TAIL_TARGET_AXIS)
    L_orig = ra.axis_extent(
        Image.open(os.path.join(ra.OUTP, "part_tail@1024.png")).convert("RGBA"),
        ra.ANCHORS["tail_root"], ra.TAIL_TARGET_AXIS)
    s = L_orig * float(tm.get("intendedRel", 1.0)) / max(L_part, 1)
    p, root = ra.rotate_about(tp, tuple(tm["rootPointInCanvas"]), rot)
    p = p.resize((max(1, int(p.width * s)), max(1, int(p.height * s))), Image.LANCZOS)
    root = (root[0] * s, root[1] * s)
    off = (int(round(ra.ANCHORS["tail_root"][0] - root[0])),
           int(round(ra.ANCHORS["tail_root"][1] - root[1])))
    m = np.zeros((1024, 1024), bool)
    a = np.asarray(p)[..., 3] > 8
    m[off[1]:off[1] + p.height, off[0]:off[0] + p.width] |= a[:1024 - off[1], :1024 - off[0]] \
        if off[1] >= 0 else a
    used |= m
    steps.append(("tail", (m & hole).sum() / hole.sum()))

    # ears
    em = ra.load_meta("Ears", "ears")
    pm = __import__("json").load(
        open(os.path.join(ra.OUTP, "_parts_meta.json"), encoding="utf-8"))
    for side, anc in (("L", "ear_root_l"), ("R", "ear_root_r")):
        mm = em["%s_%s" % (ear, side)]
        ep = Image.open(os.path.join(ra.M, "Ears", mm["file"])).convert("RGBA")
        bb = ep.getbbox()
        s = pm["ear_" + side]["contentSize"][1] * float(mm.get("intendedRel", 1.0)) \
            / (bb[3] - bb[1])
        p = ep.resize((max(1, int(ep.width * s)), max(1, int(ep.height * s))), Image.LANCZOS)
        root = (mm["rootPointInCanvas"][0] * s, mm["rootPointInCanvas"][1] * s)
        off = (int(round(ra.ANCHORS[anc][0] - root[0])),
               int(round(ra.ANCHORS[anc][1] - root[1])))
        m = np.zeros((1024, 1024), bool)
        a = np.asarray(p)[..., 3] > 8
        y0, x0 = max(off[1], 0), max(off[0], 0)
        y1 = min(off[1] + p.height, 1024)
        x1 = min(off[0] + p.width, 1024)
        m[y0:y1, x0:x1] |= a[y0 - off[1]:y1 - off[1], x0 - off[0]:x1 - off[0]]
        used |= m
    steps.append(("ears", (used & hole).sum() / hole.sum()))

    # eyes
    ep = Image.open(os.path.join(ra.M, "Eyes", "eye_%s.png" % eye)).convert("RGBA")
    ec = ep.crop(ep.getbbox())
    s = 118.0 / ec.width
    for anc in ("eye_l", "eye_r"):
        p = ec.resize((int(ec.width * s), int(ec.height * s)), Image.LANCZOS)
        a = np.asarray(p)[..., 3] > 8
        root = (p.width / 2.0, p.height / 2.0)
        off = (int(round(ra.ANCHORS[anc][0] - root[0])),
               int(round(ra.ANCHORS[anc][1] - root[1])))
        m = np.zeros((1024, 1024), bool)
        m[off[1]:off[1] + p.height, off[0]:off[0] + p.width] |= a
        used |= m
    tot = (used & hole).sum() / hole.sum()
    print("%-8s %-7s %-7s hole=%d  tail=%.2f  +ears=%.2f  +eyes=%.2f  UNCOVERED=%.2f"
          % (coat, tail, ear, hole.sum(), steps[0][1], steps[1][1], tot, 1 - tot))
    return 1 - tot


if __name__ == "__main__":
    for c, t, e, y in (("white", "fluffy", "round", "round_red"),
                       ("blue", "normal", "large", "round_blue"),
                       ("orange", "long", "pointed", "almond_gold"),
                       ("black", "normal", "star", "almond_cyan")):
        coverage(c, t, e, y)
