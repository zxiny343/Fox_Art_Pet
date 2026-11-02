# -*- coding: utf-8 -*-
"""阶段2-A：从霜蓝母版映射出全部 10 套毛色（本地，0 灵感值）。"""
import os
import sys

BASE = "C:/Users/zxiny/WorkBuddy/2026-11-01-00-53-44/Fox_Art"
sys.path.insert(0, BASE + "/tools")

import fox_traits as ft
from PIL import Image

MASTER = BASE + "/assets/master/Base/fox_base_blue_q4@1024.png"
CW_PATH = BASE + "/01_Data/colorways.json"

cws, _ = ft.load_colorways(CW_PATH)
src = cws["blue"]
master = Image.open(MASTER)

# 眼睛保护：眼色是独立性状，不随毛色改变
EYES = [(610, 510, 50, 42), (775, 490, 48, 40)]

items = []
report = []
for cid, cw in cws.items():
    if cid == "blue":
        out = master.copy()
    else:
        masks = None
        pr = cw.get("pointsRule")
        if pr:
            masks = {pr.get("applyTo", "belly"):
                     ft.build_region_mask((1024, 1024), pr["regions"])}
        out = ft.recolor_coat(master, src, cw, protect_ellipses=EYES,
                              strength=1.0, role_masks=masks)
        out = ft.apply_points_rule(out, master, src, cw, strength=1.0)
    name = "fox_base_%s_q4" % cid
    d1024 = os.path.join(BASE, "assets/master/Base")
    os.makedirs(d1024, exist_ok=True)
    out.save(os.path.join(d1024, name + "@1024.png"))
    out.resize((512, 512), Image.LANCZOS).save(
        os.path.join(BASE, "assets/export_512", name + "@512.png"))
    out.resize((256, 256), Image.LANCZOS).save(
        os.path.join(BASE, "assets/export_256", name + "@256.png"))
    items.append((out, "%s %s" % (cid, cw["nameZh"])))
    report.append((cid, cw["nameZh"], cw["rarity"]))

sheet = ft.contact_sheet(items, BASE + "/09_Review/_coat_contact.png", cell=300, cols=5)
print("contact sheet:", sheet)
for r in report:
    print("  ", r)
print("total colorways:", len(report))
