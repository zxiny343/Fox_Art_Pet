# -*- coding: utf-8 -*-
"""
阶段 4 · 表情件生成
--------------------------------------------------
生成可替换的表情部件（眉 / 嘴 / 腮红 / 闭眼），全部 1024 全画布对齐，
描边色取自母版实测，风格与母版统一（深色描边 + 圆头厚笔）。

  assets/master/Expressions/brow_<type>_L.png / _R.png   (4 型 x2 侧)
  assets/master/Expressions/mouth_<type>.png             (6 型)
  assets/master/Expressions/blush.png                    (腮红叠加层)
  assets/master/Expressions/eye_closed.png / eye_happy.png (闭眼 / 笑眼)
  01_Data/expressions.json                               机读表情定义
  09_Review/_expressions_sheet.png                       10 表情对照表
"""
import os
import sys
import json
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = os.path.join(B, "assets", "master")
EXP = os.path.join(M, "Expressions")
DATA = os.path.join(B, "01_Data")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 锚点（v3.0 实测）
EYE_L = (610, 510)
EYE_R = (775, 490)
MOUTH = (736, 578)     # 鼻子实测 (742,552)，嘴在鼻下 26px、左偏 6px
BROW_L = (606, 428)
BROW_R = (778, 408)
BLUSH_L = (600, 570)
BLUSH_R = (806, 542)


def load_colorways():
    d = json.load(open(os.path.join(DATA, "colorways.json"), encoding="utf-8"))
    cw = d["colorways"] if isinstance(d, dict) and "colorways" in d else d
    return cw


def hex2rgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def outline_colors():
    """每套毛色的描边色（LOCK-E：描边 = 毛色暗部加深，不是纯黑）。
    母版实测最暗像素是 (0,0,0)，那来自抠图残留而非描边，故以 colorways.json
    的 outline 字段为准。"""
    out = {}
    for c in load_colorways():
        out[c["id"]] = hex2rgb(c.get("outline", "#2A2430"))
    return out


def bez(p0, p1, p2, n=40):
    out = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        out.append((x, y))
    return out


def taper_stroke(pts, w0, w1, color, canvas=1024, blur=1.2):
    """沿折线画两头渐细的笔触（眉毛/嘴线）。w0=起端半宽, w1=末端半宽。"""
    lay = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    n = len(pts)
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        if i == 0:
            dx, dy = pts[1][0] - x, pts[1][1] - y
        elif i == n - 1:
            dx, dy = x - pts[-2][0], y - pts[-2][1]
        else:
            dx, dy = pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L
        t = i / (n - 1.0)
        # 中段最粗，两端收细
        k = math.sin(math.pi * min(max(t, 0.0), 1.0)) ** 0.55
        w = (w0 * (1 - t) + w1 * t) * (0.35 + 0.65 * k)
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    d.polygon(left + right[::-1], fill=color + (255,))
    if blur:
        lay = lay.filter(ImageFilter.GaussianBlur(blur))
        al = np.asarray(lay)[..., 3]
        al = np.where(al > 60, 255, np.clip(al * 3, 0, 255))
        arr = np.asarray(lay).copy()
        arr[..., 3] = al
        lay = Image.fromarray(arr, "RGBA")
    return lay


def brow(kind, side, color):
    """kind: neutral | angry | sad | raised"""
    c = BROW_R if side == "R" else BROW_L
    s = 1.0 if side == "R" else -1.0     # 左耳侧镜像
    y0 = {"neutral": 0, "angry": 2, "sad": -4, "raised": -20}[kind]
    tilt = {"neutral": 10, "angry": 26, "sad": -14, "raised": 4}[kind]
    cx, cy = c[0], c[1] + y0
    half = 46
    # 内侧(靠鼻)端点 / 外侧端点：tilt>0 表示内侧低（生气）
    inner = (cx - s * half * 0.15, cy + tilt * 0.55)
    outer = (cx + s * half, cy - tilt * 0.35)
    ctrl = (cx + s * half * 0.35, cy - 16 - abs(tilt) * 0.25)
    pts = bez(outer, ctrl, inner)
    return taper_stroke(pts, 15, 11, color)


def mouth(kind, color):
    """kind: closed | smile | open_o | frown | tongue | wavy"""
    lay = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    mx, my = MOUTH
    if kind == "closed":
        # 小猫嘴 ω：两段弧
        pts = bez((mx - 34, my - 6), (mx - 16, my + 12), (mx, my - 2))
        lay.alpha_composite(taper_stroke(pts, 8, 7, color))
        pts = bez((mx, my - 2), (mx + 16, my + 12), (mx + 34, my - 6))
        lay.alpha_composite(taper_stroke(pts, 7, 8, color))
    elif kind == "smile":
        pts = bez((mx - 40, my - 10), (mx, my + 20), (mx + 40, my - 10))
        lay.alpha_composite(taper_stroke(pts, 9, 9, color))
        # 张口的一小块暗部
        d.pieslice([mx - 22, my - 2, mx + 22, my + 30], 0, 180,
                   fill=color + (255,))
    elif kind == "open_o":
        d.ellipse([mx - 26, my - 14, mx + 26, my + 30], fill=color + (255,))
        d.ellipse([mx - 18, my + 6, mx + 18, my + 28], fill=(226, 118, 132, 255))
    elif kind == "frown":
        pts = bez((mx - 36, my + 12), (mx, my - 12), (mx + 36, my + 12))
        lay.alpha_composite(taper_stroke(pts, 8, 8, color))
    elif kind == "tongue":
        d.pieslice([mx - 26, my - 6, mx + 26, my + 28], 0, 180,
                   fill=color + (255,))
        d.ellipse([mx - 14, my + 8, mx + 14, my + 36], fill=(232, 110, 128, 255))
        d.line([(mx, my + 14), (mx, my + 30)], fill=(190, 80, 100, 255), width=5)
    elif kind == "wavy":
        pts = bez((mx - 40, my + 4), (mx - 20, my - 10), (mx, my + 4))
        lay.alpha_composite(taper_stroke(pts, 8, 8, color))
        pts = bez((mx, my + 4), (mx + 20, my + 16), (mx + 40, my + 2))
        lay.alpha_composite(taper_stroke(pts, 8, 7, color))
    return lay


def eye_arc(kind, color):
    """kind: closed(‿ 向下弯) | happy(^ 向上弯)"""
    lay = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    for cx, cy in (EYE_L, EYE_R):
        if kind == "closed":
            pts = bez((cx - 44, cy - 8), (cx, cy + 20), (cx + 44, cy - 8))
        else:
            pts = bez((cx - 44, cy + 10), (cx, cy - 20), (cx + 44, cy + 10))
        lay.alpha_composite(taper_stroke(pts, 11, 9, color))
    return lay


def blush(color=(255, 150, 165)):
    lay = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for cx, cy in (BLUSH_L, BLUSH_R):
        d.ellipse([cx - 36, cy - 20, cx + 36, cy + 20], fill=color + (150,))
    lay = lay.filter(ImageFilter.GaussianBlur(14))
    arr = np.asarray(lay).copy()
    arr[..., 3] = np.clip(arr[..., 3].astype(np.float32) * 1.5, 0, 255)
    return Image.fromarray(arr, "RGBA")


# ---------------- 10 种表情定义 ----------------
EXPRS = [
    # id, 中文, 眼件, 眉, 嘴, 腮红, 头部微动(rot,dx,dy)
    ("neutral",  "平静", "eye_round_blue",  "neutral", "closed", 0, (0, 0, 0)),
    ("happy",    "开心", "eye_happy",       "raised",  "smile",  0, (0, 2, -4)),
    ("excited",  "兴奋", "eye_round_gold",  "raised",  "open_o", 1, (0, 0, -8)),
    ("sad",      "难过", "eye_almond_blue", "sad",     "frown",  0, (3, -2, 6)),
    ("angry",    "生气", "eye_almond_red",  "angry",   "frown",  0, (-2, 0, 2)),
    ("surprised","惊讶", "eye_round_cyan",  "raised",  "open_o", 0, (0, 0, -10)),
    ("sleepy",   "困倦", "eye_sleepy_blue", "neutral", "closed", 0, (4, 0, 8)),
    ("curious",  "好奇", "eye_round_green", "raised",  "wavy",   0, (-8, 4, -4)),
    ("shy",      "害羞", "eye_sleepy_purple", "sad",   "wavy",   1, (5, -3, 5)),
    ("smug",     "得意", "eye_almond_purple", "raised", "tongue", 0, (-4, 3, 0)),
]


def main():
    os.makedirs(EXP, exist_ok=True)
    cols = outline_colors()
    coats = [c["id"] for c in load_colorways()]
    print("描边色:", {k: v for k, v in cols.items() if k in ("blue", "white", "black")})

    made = {}
    for coat in coats:
        col = cols[coat]
        for k in ("neutral", "angry", "sad", "raised"):
            for s in ("L", "R"):
                p = os.path.join(EXP, "brow_%s_%s_%s.png" % (k, s, coat))
                brow(k, s, col).save(p)
        for k in ("closed", "smile", "open_o", "frown", "tongue", "wavy"):
            mouth(k, col).save(os.path.join(EXP, "mouth_%s_%s.png" % (k, coat)))
        for k in ("closed", "happy"):
            eye_arc(k, col).save(os.path.join(EXP, "eye_%s_%s.png" % (k, coat)))
    made["brows"] = "brow_<kind>_<L|R>_<coat>.png  (4x2x%d)" % len(coats)
    made["mouths"] = "mouth_<kind>_<coat>.png  (6x%d)" % len(coats)
    made["eyeArcs"] = "eye_<closed|happy>_<coat>.png  (2x%d)" % len(coats)
    blush().save(os.path.join(EXP, "blush.png"))
    made["blush"] = "blush.png（腮红与毛色无关，单件）"
    for k, v in made.items():
        print("  %-8s %s" % (k, v))

    # 母版自带嘴（切出来留档，作为 mouth_default 参考）
    import run_split as rs
    reg, _ = rs.load()
    ma = np.asarray(Image.open(os.path.join(M, "Base", "fox_base_blue_q4@1024.png")).convert("RGBA"))
    mm = rs.region_mask(reg["regions"]["mouth"]) & (ma[..., 3] > 8)
    part = ma.copy()
    part[..., 3] = np.where(mm, ma[..., 3], 0)
    Image.fromarray(part, "RGBA").save(os.path.join(EXP, "mouth_default_master.png"))
    print("母版自带嘴留档 -> mouth_default_master.png  (%d px)" % int(mm.sum()))

    # 机读定义
    spec = {
        "schemaVersion": "1.0",
        "anchorSet": "v3.0-view34-quadruped",
        "note": "表情 = 眼件 + 眉件 + 嘴件 + 腮红 + 头部微动参数的组合；"
                "全部部件 1024 全画布对齐，(0,0) 叠加，不需要程序侧调坐标。",
        "coatTinting": "眉/嘴/闭眼件按 colorways.json 的 outline 色逐毛色烘焙，"
                       "文件名带 _<coat> 后缀；腮红与毛色无关，只有一件。",
        "slots": {
            "eye": {"anchor": "eye_l / eye_r",
                    "assets": "assets/master/Eyes/eye_<shape>_<color>.png "
                              "+ Expressions/eye_closed_<coat>.png / eye_happy_<coat>.png",
                    "shapes": ["round", "almond", "sleepy", "closed", "happy"],
                    "colors": ["blue", "cyan", "gold", "green", "purple", "red"]},
            "brow": {"anchor": "brow_l(606,446) / brow_r(778,426)",
                     "assets": "assets/master/Expressions/brow_<kind>_<L|R>.png",
                     "kinds": ["neutral", "angry", "sad", "raised"]},
            "mouth": {"anchor": "mouth(730,596)",
                      "assets": "assets/master/Expressions/mouth_<kind>.png",
                      "kinds": ["closed", "smile", "open_o", "frown", "tongue", "wavy"],
                      "socket": "body_core 上已挖出 mouth 区并 socket 补色"},
            "blush": {"anchor": "blush_l(558,548) / blush_r(812,512)",
                      "assets": "assets/master/Expressions/blush.png",
                      "blend": "normal / 可改用 screen"},
        },
        "expressions": [
            {"id": e[0], "name": e[1], "eye": e[2], "brow": e[3], "mouth": e[4],
             "blush": bool(e[5]),
             "head": {"rotDeg": e[6][0], "dx": e[6][1], "dy": e[6][2]}}
            for e in EXPRS
        ],
    }
    json.dump(spec, open(os.path.join(DATA, "expressions.json"), "w",
                         encoding="utf-8"), ensure_ascii=False, indent=2)
    print("spec ->", os.path.join(DATA, "expressions.json"))


if __name__ == "__main__":
    main()
