# -*- coding: utf-8 -*-
"""v1.3 全量回归：原有 8 组合 + 全部新增组合。

验收口径（沿用 v1.2 run_batch.check）：
  单连通域 / 不出血 / body_core 包络统一 / 身体范围内破洞 = 0
"""
import os
import sys

B = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_assemble as ra
from run_batch import COMBOS, check, core_of

# (coat, tail, ear, eye, pupil, pattern, label)
NEW = []
# P0 多尾 × 3 毛色（另见 run_tail_counts.py 的 12 组）
for c in ("blue", "orange", "purple"):
    for t in ("triple", "quad", "quint", "nine"):
        NEW.append((c, t, "large", "round_blue", None, None))
# P1 两个新配色标准件
for c in ("mist_purple", "haze_blue"):
    NEW.append((c, "normal", "pointed", "round_blue", None, None))
    NEW.append((c, "twin", "round", "round_gold", None, "spots"))
# P1 火焰纹 × 3 毛色
for c in ("orange", "black", "white"):
    NEW.append((c, "normal", "large", "round_blue", None, "flame"))
# P2 四项各 1 组（+虎斑与多尾/新配色交叉）
NEW += [
    ("orange", "normal", "large", "round_blue", None, "tabby"),
    ("blue", "normal", "fold", "round_copper", None, None),
    ("white", "thin", "fold", "almond_copper", None, None),
    ("purple", "thin", "small", "sleepy_copper", None, "flame"),
    ("mist_purple", "nine", "fold", "round_copper", None, "flame"),
]


def main():
    fails = []
    n = 0

    print("== 原有 8 组合（回归 v1.2 未被破坏） ==")
    for combo in COMBOS:
        coat, tail, ear, eye, pupil, pattern = combo
        img, _ = ra.assemble(coat, "short", tail, ear, eye, pupil, pattern,
                             verbose=False)
        ca, cb = core_of(coat)
        n += 1
        if not check(img, "%s/%s/%s" % (coat, tail, ear), ca, cb):
            fails.append(combo)

    print("\n== v1.3 新增组合 ==")
    for coat, tail, ear, eye, pupil, pattern in NEW:
        img, _ = ra.assemble(coat, "short", tail, ear, eye, pupil, pattern,
                             verbose=False)
        ca, cb = core_of(coat)
        label = "%s/%s/%s/%s" % (coat, tail, ear, pattern or "-")
        n += 1
        if not check(img, label, ca, cb):
            fails.append((coat, tail, ear, eye, pupil, pattern))

    print("\n== %d/%d PASS ==" % (n - len(fails), n))
    if fails:
        print("失败组合：")
        for f in fails:
            print("   ", f)
    return not fails


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
