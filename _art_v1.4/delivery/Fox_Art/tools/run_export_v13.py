# -*- coding: utf-8 -*-
"""v1.3 新增部件的 512/256 导出（补齐 DoD §6.1）。"""
import os

B = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
M = os.path.join(B, "assets", "master")
E512 = os.path.join(B, "assets", "export_512")
E256 = os.path.join(B, "assets", "export_256")
from PIL import Image


def exp(rel, name):
    p = os.path.join(M, rel)
    if not os.path.exists(p):
        print("  MISS", rel)
        return False
    im = Image.open(p).convert("RGBA")
    for n, d in ((512, E512), (256, E256)):
        im.resize((n, n), Image.LANCZOS).save(
            os.path.join(d, "%s@%d.png" % (name, n)))
    print("  %-28s -> %s@512/256" % (rel, name))
    return True


def main():
    items = [
        # P0 多尾
        ("Tails/tail_triple.png", "tail_triple"),
        ("Tails/tail_quad.png", "tail_quad"),
        ("Tails/tail_quint.png", "tail_quint"),
        ("Tails/tail_nine.png", "tail_nine"),
        # P2
        ("Ears/ear_fold_L.png", "ear_fold_L"),
        ("Ears/ear_fold_R.png", "ear_fold_R"),
        ("Eyes/eye_round_copper.png", "eye_round_copper"),
        ("Eyes/eye_almond_copper.png", "eye_almond_copper"),
        ("Eyes/eye_sleepy_copper.png", "eye_sleepy_copper"),
        ("Tails/tail_thin.png", "tail_thin"),
    ]
    ok = 0
    for rel, name in items:
        ok += exp(rel, name)
    print("导出 %d/%d" % (ok, len(items)))


if __name__ == "__main__":
    main()
