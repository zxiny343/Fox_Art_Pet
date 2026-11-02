# -*- coding: utf-8 -*-
"""包络 v1.2 + 尾巴下层 全矩阵回归：尾型 x 毛色 / 耳型 x 毛色，只看客观指标。"""
import os
import sys
import numpy as np
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_assemble as ra

CORE_BBOX = (189, 150, 877, 928)
TAILS = ["normal", "long", "fluffy", "curl", "short", "twin"]
EARS = ["large", "pointed", "round", "small", "star"]
COATS = ["white", "orange", "black", "grey", "blue", "purple",
         "caramel", "sakura", "mint", "obsidian_gold"]


def metrics(img, core_a):
    a = np.asarray(img)[..., 3] > 8
    lab, n = ndimage.label(a)
    sizes = ndimage.sum(a, lab, range(1, n + 1))
    ys, xs = np.where(a)
    no_clip = (xs.min() >= 4 and ys.min() >= 4 and xs.max() <= 1019
               and ys.max() <= 1019)
    pockets = ndimage.binary_fill_holes(a) & ~a
    holes = int((pockets & ndimage.binary_dilation(core_a, iterations=2)).sum())
    return (n, int((sizes > 500).sum()), no_clip, holes,
            (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())))


def main():
    fails = []
    cache = {}
    for coat in COATS:
        core, _ = ra.make_core(coat, "short", seam="socketfill")
        ca = np.asarray(core)[..., 3] > 8
        ys, xs = np.where(ca)
        cb = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
        cache[coat] = (ca, cb)
        if cb != CORE_BBOX:
            fails.append("core bbox %s != %s @%s" % (cb, CORE_BBOX, coat))
    print("body_core 包络一致性: %s (%s)" %
          ("PASS" if not fails else "FAIL", CORE_BBOX))

    n_ok = 0
    for coat in ("blue", "orange", "obsidian_gold", "white"):
        ca, cb = cache[coat]
        for t in TAILS:
            img, used = ra.assemble(coat, "short", t, "large", "round_blue",
                                    verbose=False)
            n, big, noclip, holes, bb = metrics(img, ca)
            ok = n == 1 and big == 1 and noclip and holes == 0
            n_ok += ok
            if not ok:
                fails.append("tail %s/%s comps=%d big=%d clip=%s holes=%d"
                             % (coat, t, n, big, noclip, holes))
            print("  %-14s tail_%-7s comps=%d holes=%d bbox=%s %s"
                  % (coat, t, n, holes, bb, "OK" if ok else "FAIL"))

    for coat in ("blue", "purple"):
        ca, cb = cache[coat]
        for e in EARS:
            img, _ = ra.assemble(coat, "short", "normal", e, "round_blue",
                                 verbose=False)
            n, big, noclip, holes, bb = metrics(img, ca)
            ok = n == 1 and big == 1 and noclip and holes == 0
            n_ok += ok
            if not ok:
                fails.append("ear %s/%s comps=%d holes=%d" % (coat, e, n, holes))
            print("  %-14s ear_%-8s comps=%d holes=%d bbox=%s %s"
                  % (coat, e, n, holes, bb, "OK" if ok else "FAIL"))

    print("\nTOTAL OK = %d" % n_ok)
    print("FAILS:", fails if fails else "none")


if __name__ == "__main__":
    main()
