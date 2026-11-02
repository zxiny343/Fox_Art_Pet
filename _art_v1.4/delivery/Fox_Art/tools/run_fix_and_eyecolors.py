# -*- coding: utf-8 -*-
"""
1) 性状尺寸归一化：AI 出图没有严格按提示词给出尺寸梯度（如"小耳"反而比"大耳"高），
   这里按设计意图对每个部件施加 displayScale，并把实测值与目标值都写进 meta。
2) 眼色：虹膜区域 HSV 色相旋转，保留 S/V（即保留原有的明暗与高光），
   瞳孔(暗)、高光(白)、描边(暗)都不受影响。产出 6 色 x 3 眼型。
"""
import os
import sys
import json
import math

BASE = "C:/Users/zxiny/WorkBuddy/2026-11-01-00-53-44/Fox_Art"
sys.path.insert(0, BASE + "/tools")
import numpy as np
from PIL import Image

# ---------------- 1. 尺寸归一化 ----------------
INTENDED = {
    "ears": {"large": 1.15, "pointed": 1.05, "star": 1.00, "round": 0.90, "small": 0.75},
    "tails": {"long": 1.28, "twin": 1.12, "fluffy": 1.06, "normal": 1.00,
              "curl": 0.98, "short": 0.72},
}


def rescale_part(path, meta, s, canvas_wh):
    im = Image.open(path).convert("RGBA")
    cw, ch = canvas_wh
    bb = im.getbbox()
    crop = im.crop(bb)
    rx = meta["rootPointInCanvas"][0] - bb[0]
    ry = meta["rootPointInCanvas"][1] - bb[1]
    new = crop.resize((max(1, int(round(crop.width * s))),
                       max(1, int(round(crop.height * s)))), Image.LANCZOS)
    ox = (cw - new.width) // 2
    oy = (ch - new.height) // 2
    out = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    out.alpha_composite(new, (ox, oy))
    out.save(path)
    meta["rootPointInCanvas"] = [int(round(ox + rx * s)), int(round(oy + ry * s))]
    meta["placedSize"] = [new.width, new.height]
    meta["placedBBox"] = [ox, oy, ox + new.width, oy + new.height]


def normalize_category(cat, subdir):
    d = os.path.join(BASE, "assets/master", subdir)
    mp = os.path.join(d, "_%s_meta.json" % cat)
    if not os.path.exists(mp):
        print("skip", cat)
        return
    metas = json.load(open(mp, encoding="utf-8"))
    intents = INTENDED[cat]

    # 以"尺寸最大的那个"作为基准反推目标绝对尺寸：确保缩放后不会超出画布
    meas = {}
    for k, m in metas.items():
        typ = k.rsplit("_", 1)[0]
        w, h = m["placedSize"]
        meas[k] = math.hypot(w, h)
    base_k = max(meas, key=lambda k: meas[k])
    base_type = base_k.rsplit("_", 1)[0]
    k_abs = meas[base_k] / intents[base_type]      # 单位：px / 意图系数

    for k, m in metas.items():
        typ = k.rsplit("_", 1)[0]
        target = k_abs * intents[typ]
        s = target / meas[k]
        m["measuredDiagPx"] = round(meas[k], 1)
        m["intendedRel"] = intents[typ]
        m["targetDiagPx"] = round(target, 1)
        m["displayScale"] = round(s, 4)
        rescale_part(os.path.join(d, m["file"]), m, s, tuple(m["canvas"]))
    json.dump(metas, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    for k in sorted(metas):
        m = metas[k]
        print("  %-16s measured=%6.1f -> target=%6.1f  scale=%.3f"
              % (k, m["measuredDiagPx"], m["targetDiagPx"], m["displayScale"]))


if "--eyes-only" not in sys.argv:
    print("== 耳朵尺寸归一化 ==")
    normalize_category("ears", "Ears")
    print("== 尾巴尺寸归一化 ==")
    normalize_category("tails", "Tails")

# ---------------- 2. 眼色 ----------------
EYE_COLORS = {
    "blue": 205.0, "gold": 42.0, "red": 353.0,
    "green": 128.0, "purple": 275.0, "cyan": 186.0,
}


def recolor_eye(img, hue_deg):
    im = img.convert("RGBA")
    arr = np.asarray(im).astype(np.float32)
    a = arr[..., 3]
    rgb = arr[..., :3] / 255.0
    mx = rgb.max(-1)
    mn = rgb.min(-1)
    v = mx
    s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    # 虹膜 = 有明显饱和度且不是极暗(瞳孔/描边)也不是极亮(高光)
    mask = (s > 0.28) & (v > 0.18) & (v < 0.96) & (a > 40)
    if mask.sum() < 50:
        return img
    # 色相替换：S/V 在原图基础上略作提升，否则暖色（金/红/青）会发灰
    # （原图是天蓝虹膜，其 S/V 对暖色来说偏低）
    s = np.clip(s * 1.18, 0.0, 1.0)
    v = np.clip(v * 1.10, 0.0, 1.0)
    h = np.full(rgb.shape[:2], hue_deg / 360.0)
    # HSV -> RGB
    i = np.floor(h * 6.0)
    f = h * 6.0 - i
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    i = i % 6
    r = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5],
                  [v, q, p, p, t, v])
    g = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5],
                  [t, v, v, q, p, p])
    b = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5],
                  [p, p, t, v, v, q])
    out = np.dstack([r, g, b]) * 255.0
    rgb_out = np.where(mask[..., None], out, rgb * 255.0)
    # 高光强制回纯白（原图高光偏灰，换色后会显得脏）
    hl = (v > 0.88) & (np.clip(s / 1.18, 0, 1) < 0.18) & (a > 40)
    rgb_out = np.where(hl[..., None], 255.0, rgb_out)
    res = np.dstack([np.clip(rgb_out, 0, 255), a]).astype(np.uint8)
    return Image.fromarray(res, "RGBA")


edir = os.path.join(BASE, "assets/master/Eyes")
shapes = ["round", "almond", "sleepy"]
os.makedirs(edir, exist_ok=True)
print("== 眼色 x 眼型 ==")
items = []
for sh in shapes:
    src = os.path.join(edir, "eye_%s.png" % sh)
    if not os.path.exists(src):
        print("missing", src)
        continue
    base = Image.open(src)
    for cid, hue in EYE_COLORS.items():
        out = recolor_eye(base, hue)
        fn = "eye_%s_%s.png" % (sh, cid)
        out.save(os.path.join(edir, fn))
        items.append((out, "%s/%s" % (sh, cid)))
    print("  eye_%s -> 6 colors" % sh)

import fox_traits as ft
ft.contact_sheet(items, BASE + "/09_Review/_parts_eyecolors.png", cell=190, cols=6)
print("eye color sheet:", BASE + "/09_Review/_parts_eyecolors.png")
