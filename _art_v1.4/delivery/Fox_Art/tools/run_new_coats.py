# -*- coding: utf-8 -*-
"""P1：两个 D 位点稀释毛色 —— mist_purple（淡雾紫）/ haze_blue（雾霭蓝）。

只新增文件，不重跑/覆盖 v1.2 已有配色（任务单 §7）。
流程与 run_coat_colors.py 一致：blue 母版 → recolor_coat 色相映射（保护眼睛）。

产出：
  01_Data/colorways.json                      追加 2 条
  assets/master/Base/fox_base_<coat>_q4@1024.png
  assets/master/Body/body_core_<coat>@1024.png
  assets/master/Tails/tail_base_<coat>@1024.png
  assets/export_512|256/fox_base_<coat>_q4@512|256.png
  09_Review/_new_coats.png                    新配色 vs purple/black/blue 对照
"""
import os
import sys
import json

B = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(B, "tools"))

import fox_traits as ft
from PIL import Image

DATA = os.path.join(B, "01_Data")
M = os.path.join(B, "assets", "master")
BASE = os.path.join(M, "Base")
BODY = os.path.join(M, "Body")
TAILS = os.path.join(M, "Tails")
E512 = os.path.join(B, "assets", "export_512")
E256 = os.path.join(B, "assets", "export_256")
REVIEW = os.path.join(B, "09_Review")

MASTER = os.path.join(BASE, "fox_base_blue_q4@1024.png")
EYES = [(610, 510, 50, 42), (775, 490, 48, 40)]

# 任务单 v1.3 §2 指定基色；innerEar/nose 沿用同系稀释风格
NEW_COATS = [
    {
        "id": "mist_purple",
        "nameZh": "淡雾紫",
        "rarity": "fine",
        "base": "#CDBDE8", "shade": "#AF9BD0", "light": "#E4D9F5",
        "belly": "#F5F0FC", "innerEar": "#F4D2E2", "nose": "#6B587E",
        "outline": "#5E4A80",
        "note": "purple 的 D 位点稀释态：更浅、更灰（v1.3 P1）",
    },
    {
        "id": "haze_blue",
        "nameZh": "雾霭蓝",
        "rarity": "fine",
        "base": "#93A9C6", "shade": "#6E87A8", "light": "#BCCFE4",
        "belly": "#E3ECF6", "innerEar": "#C9A0A6", "nose": "#4E5A6B",
        "outline": "#3D5670",
        "note": "black 的 D 位点稀释态：低饱和蓝灰（v1.3 P1）",
    },
]


def add_colorways():
    p = os.path.join(DATA, "colorways.json")
    d = json.load(open(p, encoding="utf-8"))
    ids = [c["id"] for c in d["colorways"]]
    added = []
    for c in NEW_COATS:
        if c["id"] in ids:
            print("  已存在，跳过:", c["id"])
            continue
        d["colorways"].append(c)
        added.append(c["id"])
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("colorways.json 追加:", added, "-> 共", len(d["colorways"]))
    return added


def load_cw():
    cmap, _ = ft.load_colorways(os.path.join(DATA, "colorways.json"))
    return cmap


def make_coat(cid, cmap):
    master = Image.open(MASTER)
    cw = cmap[cid]
    out = ft.recolor_coat(master, cmap["blue"], cw,
                          protect_ellipses=EYES, strength=1.0)
    if cw.get("pointsRule"):
        pr = cw["pointsRule"]
        masks = {pr.get("applyTo", "belly"):
                 ft.build_region_mask((1024, 1024), pr["regions"])}
        out = ft.apply_points_rule(out, master, cmap["blue"], cw,
                                   strength=1.0)
    name = "fox_base_%s_q4" % cid
    out.save(os.path.join(BASE, name + "@1024.png"))
    out.resize((512, 512), Image.LANCZOS).save(
        os.path.join(E512, name + "@512.png"))
    out.resize((256, 256), Image.LANCZOS).save(
        os.path.join(E256, name + "@256.png"))
    return out


def make_body_core(cid, cmap):
    """复用 run_tail_layer 的窗口/兜底件定义，只针对新配色生成。"""
    import run_tail_layer as rtl
    reg, rs = rtl.load_regions()
    src = os.path.join(BASE, "fox_base_%s_q4@1024.png" % cid)
    ma = np_asarray(src)
    W, fitset, B0, alpha = rtl.build_masks(reg, rs, ma)
    core, wpx, spx = rtl.make_body_core(ma, W, fitset, cid)
    core.save(os.path.join(BODY, "body_core_%s@1024.png" % cid))
    return W, wpx, spx


def np_asarray(path):
    import numpy as np
    from PIL import Image as _I
    return np.asarray(_I.open(path).convert("RGBA"))


def make_tail_base(cid, cmap):
    import run_tail_layer as rtl
    reg, rs = rtl.load_regions()
    ma = np_asarray(MASTER)
    W, fitset, B0, alpha = rtl.build_masks(reg, rs, ma)
    seam, socket = rtl.make_socket(W, B0)
    base0, bpx = rtl.make_tail_base(ma, W, socket)
    rtl.tint(base0, cid).save(os.path.join(TAILS,
                                           "tail_base_%s@1024.png" % cid))
    return bpx


def main():
    added = add_colorways()
    if not added:
        print("无新增配色，仅重出验收图")
    cmap = load_cw()

    for c in NEW_COATS:
        cid = c["id"]
        img = make_coat(cid, cmap)
        W, wpx, spx = make_body_core(cid, cmap)
        bpx = make_tail_base(cid, cmap)
        # 平均色核对（判断是否与母版色/同系色混淆）
        import numpy as np
        a = np.asarray(img)
        m = a[..., 3] > 200
        rgb = a[..., :3][m].mean(0)
        print("  %-12s 母版已出 | body_core 窗口 %d px socket %d px | "
              "tail_base 覆盖 %d px | 实体平均色 RGB(%d,%d,%d)"
              % (cid, wpx, spx, bpx, rgb[0], rgb[1], rgb[2]))

    # --- 验收图：新配色 × 标准件 + purple/black/blue 对照 ---
    import run_assemble as ra
    cols = [("mist_purple", "淡雾紫"), ("haze_blue", "雾霭蓝"),
            ("purple", "紫(对照)"), ("black", "黑(对照)"), ("blue", "蓝(对照)")]
    cell = 384
    sheet = Image.new("RGB", (cell * len(cols), cell), (170, 170, 170))
    for i, (cid, zh) in enumerate(cols):
        img, used = ra.assemble(cid, "short", "normal", "pointed",
                                "round_blue", verbose=False)
        img.resize((cell, cell), Image.LANCZOS).save(
            os.path.join(E512, "fox_%s_normal_pointed@512.png" % cid))
        img.resize((256, 256), Image.LANCZOS).save(
            os.path.join(E256, "fox_%s_normal_pointed@256.png" % cid))
        t = img.resize((cell, cell), Image.LANCZOS)
        bg = Image.new("RGBA", (cell, cell), (170, 170, 170, 255))
        bg.alpha_composite(t, (0, 0))
        sheet.paste(bg.convert("RGB"), (i * cell, 0))
    out = os.path.join(REVIEW, "_new_coats.png")
    sheet.save(out)
    print("验收图 ->", out)


if __name__ == "__main__":
    main()
