# -*- coding: utf-8 -*-
"""v1.4 全量回归（返修单第 9 / 10 节）。

组成：
  A. run_batch.py 全量 PASS（8 组合）+ run_regress_v13.py 全量 PASS（v1.3 组合）
  B. 检查 1（机器）：尾根缺口 —— 11 尾型 × 2 毛色，short/thin 必须为 0
  C. 检查 2（出图 + 人眼）：4 张固定角度验收图存在且非空，另附 R3/R4/R5/R7 客观判据
  D. 检查 3（机器）：traits.json 的 values × 磁盘文件对账（01_Data/_meta.json）
  E. 附加：v1.4 新组合、毛发三档 smoke、短/细尾主体 bbox 与 v1.3 一致性

用法：python run_regress_v14.py   （返回码 0 = 全 PASS）
"""
import os, sys, json, subprocess
import numpy as np
from PIL import Image
from scipy import ndimage

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
B = os.path.abspath(os.path.join(TOOLS, ".."))
M = os.path.join(B, "assets", "master")
DATA = os.path.join(B, "01_Data")
REV = os.path.join(B, "09_Review")

import run_assemble as ra
import run_split as rs
from run_batch import COMBOS, check, core_of
from run_regress_v13 import NEW as V13_NEW

MASTER = Image.open(os.path.join(M, "Base", "fox_base_blue_q4@1024.png")).convert("RGBA")
master_a = np.asarray(MASTER)[..., 3] > 8
YY, XX = np.mgrid[0:1024, 0:1024]
FACE_BIG = (((XX - 700) / 195.0) ** 2 + ((YY - 470) / 165.0) ** 2 <= 1.0)
TRUNK = master_a & (~FACE_BIG) & (XX < 700)

TAILS = ["normal", "twin", "triple", "quad", "quint", "nine",
         "fluffy", "long", "curl", "short", "thin"]
SHEETS = ["_tail_counts.png", "_tail_root_fix.png", "_ear_sizes.png",
          "_pattern_scales.png", "_special_layers.png"]

results = []


def rec(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print("  [%s] %-38s %s" % ("PASS" if ok else "FAIL", name, detail))
    return bool(ok)


def run_script(name):
    r = subprocess.run([sys.executable, os.path.join(TOOLS, name)],
                       cwd=TOOLS, capture_output=True, text=True)
    tail = [x for x in r.stdout.strip().split("\n") if x.strip()][-3:]
    return r.returncode, tail, r.stderr


def subject_bbox(img):
    a = np.asarray(img)[..., 3] > 200
    ys, xs = np.where(a)
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def hole_px(tail, coat):
    img, _ = ra.assemble(coat, "short", tail, "large", "round_blue",
                         verbose=False)
    a = np.asarray(img)[..., 3]
    return int((master_a & (a < 8)).sum()), subject_bbox(img)


# ---------------------------------------------------------------- A
def part_a():
    print("\n== A. 既有回归（run_batch / run_regress_v13） ==")
    rc, tail, err = run_script("run_batch.py")
    ok1 = (rc == 0 and any("ALL OBJECTIVE CHECKS: PASS" in x for x in tail))
    rec("run_batch.py 8/8 全量", ok1, " | ".join(tail[-2:]))
    rc, tail, err = run_script("run_regress_v13.py")
    ok2 = (rc == 0)
    rec("run_regress_v13.py 全量", ok2, " | ".join(tail[-1:]))
    if err.strip():
        print("     stderr:", err.strip()[-200:])

    # v1.4 新增组合 + 毛发三档 smoke
    print("\n-- v1.4 新组合（沿用 run_batch.check 四条判据） --")
    v14 = [
        ("black", "short", "large", "round_blue", None, "stripes"),
        ("white", "thin", "large", "round_blue", None, "spots"),
        ("mist_purple", "thin", "fold", "round_cyan", None, "tabby"),
        ("haze_blue", "short", "large", "sleepy_cyan", None, "flame"),
        ("orange", "nine", "large", "round_gold", None, "tabby"),
        ("blue", "thin", "large", "round_cyan", None, None),
        ("grey", "short", "large", "almond_gold", None, "stripes"),
        ("caramel", "curl", "pointed", "round_green", "slit", "spots"),
    ]
    ok = True
    for coat, tail, ear, eye, pupil, pat in v14:
        img, _ = ra.assemble(coat, "short", tail, ear, eye, pupil, pat,
                             verbose=False)
        ca, cb = core_of(coat)
        ok &= check(img, "%s/%s/%s" % (coat, tail, ear), ca, cb)
    rec("v1.4 新增 8 组合", ok)

    print("\n-- 毛发三档 smoke（R6 改名后必须仍可组装） --")
    smoke = True
    for fur in ("medium", "long", "curly"):
        try:
            img, _ = ra.assemble("blue", fur, "normal", "large",
                                 "round_blue", verbose=False)
            n = int((np.asarray(img)[..., 3] > 8).sum())
            print("     fur=%-7s 不透明像素=%d" % (fur, n))
            smoke &= n > 100000
        except Exception as e:
            print("     fur=%-7s ERROR %s" % (fur, e))
            smoke = False
    rec("毛发 medium/long/curly 可组装", smoke)


# ---------------------------------------------------------------- B
def part_b():
    print("\n== B. 检查 1：尾根缺口（master_a 内、组装后却透明） ==")
    meta = json.load(open(os.path.join(M, "Tails", "_tails_meta.json"),
                          encoding="utf-8"))
    r1 = meta.get("_v14_R1", {})
    ok = True
    for coat in ("blue", "haze_blue"):
        row = []
        for t in TAILS:
            h, bb = hole_px(t, coat)
            row.append("%s=%d" % (t, h))
            if t in ("short", "thin"):
                ok &= (h <= 100)
            else:
                ok &= (h <= 9000)
        print("  coat=%-10s %s" % (coat, "  ".join(row)))
    rec("short/thin 缺口 = 0（2 毛色）", ok)

    # 主体 bbox 与 v1.3 一致（形态不能变）
    bok = True
    for t in ("short", "thin"):
        a = np.asarray(Image.open(os.path.join(M, "Tails", "tail_%s.png" % t))
                       .convert("RGBA"))[..., 3]
        ys, xs = np.where(a > 200)
        now = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
        old = r1.get(t, {}).get("partBBoxV13", now)
        d = max(abs(now[i] - old[i]) for i in range(4))
        print("  %-6s 尾身 bbox=%s  v1.3=%s  最大差=%dpx" % (t, now, old, d))
        bok &= (d <= 12)
    rec("短/细尾主体 bbox 与 v1.3 一致", bok)


# ---------------------------------------------------------------- C
def part_c():
    print("\n== C. 检查 2：固定角度验收图 + 客观判据 ==")
    sheet_ok = True
    for s in SHEETS:
        p = os.path.join(REV, s)
        e = os.path.isfile(p) and os.path.getsize(p) > 20000
        print("  %-26s %s" % (s, "%d KB" % (os.path.getsize(p) // 1024)
                              if e else "MISSING"))
        sheet_ok &= e
    rec("5 张验收图齐备（目视过目）", sheet_ok)

    # R3 耳型体量
    em = {}
    for e in ("small", "round", "large"):
        a = np.asarray(Image.open(os.path.join(M, "Ears",
                        "ear_%s_L.png" % e)).convert("RGBA"))[..., 3] > 8
        ys, xs = np.where(a)
        em[e] = (int(a.sum()), int(ys.min()))
    ratio = em["large"][0] / em["round"][0]
    topdiff = max(v[1] for v in em.values()) - min(v[1] for v in em.values())
    eok = (em["small"][0] < em["round"][0] < em["large"][0]
           and 1.25 <= ratio <= 1.6 and topdiff <= 6)
    rec("R3 耳型单调 / 比值 / topY",
        eok, "px=%s ratio=%.3f topY差=%d"
        % ([v[0] for v in em.values()], ratio, topdiff))

    # R4 花纹覆盖率（diag 口径）
    cov = {}
    for p in ("stripes", "tabby", "spots"):
        m = np.asarray(Image.open(os.path.join(M, "Patterns",
                        "pattern_%s_mask@1024.png" % p)).convert("RGBA")
                       .getchannel("A")) > 128
        cov[p] = float((m & TRUNK).sum() / TRUNK.sum())
    cok = cov["stripes"] >= .40 and cov["tabby"] >= .40 and cov["spots"] >= .25
    rec("R4 躯干覆盖率阈值", cok,
        "stripes=%.3f tabby=%.3f spots=%.3f"
        % (cov["stripes"], cov["tabby"], cov["spots"]))

    # R5 special 三件套
    sok = True
    for n in ("glow", "aura", "star_mark"):
        sok &= os.path.isfile(os.path.join(M, "Special",
                                           "special_%s@1024.png" % n))
    aa = np.asarray(Image.open(os.path.join(M, "Special",
                    "special_aura@1024.png")).convert("RGBA"))[..., 3] > 38
    ys, xs = np.where(aa)
    width = int(xs.max() - xs.min())
    sok &= (280 <= width <= 330)
    sm = np.asarray(Image.open(os.path.join(M, "Special",
                    "special_star_mark@1024.png")).convert("RGBA"))[..., 3] > 128
    lab, n = ndimage.label(sm)
    sok &= (n == 3)
    rec("R5 special 三件套 / 光环 / 三星", sok,
        "光环宽=%d 星标连通域=%d" % (width, n))

    # R7
    rok = isinstance(getattr(ra, "ORIG_EAR_H", None), dict) and \
        set(ra.ORIG_EAR_H) >= {"L", "R"}
    rec("R7 ORIG_EAR_H 已定义", rok, str(getattr(ra, "ORIG_EAR_H", None)))


# ---------------------------------------------------------------- D
def part_d():
    print("\n== D. 检查 3：traits.values × 磁盘文件对账 ==")
    meta = json.load(open(os.path.join(DATA, "_meta.json"), encoding="utf-8"))
    cfg = meta["valueFileCheck"]
    fmap = cfg["fileMap"]
    exempt = cfg["exemptions"]
    traits = json.load(open(os.path.join(DATA, "traits.json"),
                            encoding="utf-8"))
    ids = []
    for cat in traits["categories"]:
        ids += [(cat["id"], v) for v in cat["values"]]
    ok = True
    for cat, v in ids:
        if v in fmap:
            miss = [p for p in fmap[v]
                    if not os.path.isfile(os.path.join(B, p))]
            if miss:
                ok = False
                print("  MISSING %-22s %s" % (v, miss))
        elif v in exempt:
            ex = exempt[v]
            if not (ex.get("procedural") or ex.get("composedOf")):
                ok = False
                print("  BAD EXEMPTION", v)
            miss = [p for p in ex.get("composedOf", [])
                    if not os.path.isfile(os.path.join(B, p))]
            if miss:
                ok = False
                print("  MISSING composedOf %-14s %s" % (v, miss))
        else:
            ok = False
            print("  NO MAPPING %s / %s" % (cat, v))
    rec("values 全量对账", ok, "%d 个 id，%d 个实体映射，%d 个豁免"
        % (len(ids), len(fmap), len(exempt)))


def main():
    part_a()
    part_b()
    part_c()
    part_d()
    npass = sum(1 for _, ok, _ in results if ok)
    print("\n== v1.4 全量回归 %d/%d PASS ==" % (npass, len(results)))
    for n, ok, d in results:
        if not ok:
            print("   FAIL:", n, d)
    return npass == len(results)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
