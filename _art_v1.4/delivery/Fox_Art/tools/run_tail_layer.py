# -*- coding: utf-8 -*-
"""
阶段3 修订（包络 v1.2 + 尾巴下层方案）
--------------------------------------------------
两条规定：
  1) 包络以「身体核心」对齐：body_core 的坐标/尺寸/锚点全毛色统一；
     耳朵、尾巴等极端性状允许突破统一包络，不得为对齐包络压缩性状差异。
  2) 尾巴走身体下层：3/4 视角默认在身后。
     body_core 的尾巴连接区做成「透明窗口 + 统一 socket 锚点」，
     另提供 tail_base（基础尾根）兜底件，保证短尾替换也不会露出透明漏洞。

产物：
  assets/master/Parts/part_body_core@1024.png      母版（霜蓝）身体核心（带尾巴窗口）
  assets/master/Body/body_core_<coat>@1024.png     10 套毛色的身体核心
  assets/master/Parts/tail_socket_mask@1024.png    socket 区域遮罩（alpha）
  assets/master/Tails/tail_base_<coat>@1024.png    基础尾根兜底件（10 套毛色）
  assets/master/Tails/tail_normal.png              统一为母版原版配套件（替换旧的 768 独立件）
  01_Data/tail_socket.json                         机读规格
"""
import os
import sys
import json
import numpy as np
from PIL import Image
from scipy import ndimage

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = os.path.join(B, "assets", "master")
DATA = os.path.join(B, "01_Data")
PARTS = os.path.join(M, "Parts")
BODY = os.path.join(M, "Body")
TAILS = os.path.join(M, "Tails")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TAIL_ROOT_ANCHOR = (425, 505)      # 统一 socket 锚点（= tail_root）
COATS = ["white", "orange", "black", "grey", "blue", "purple",
         "caramel", "sakura", "mint", "obsidian_gold"]


def load_regions():
    import run_split as rs
    reg, _ = rs.load()
    return reg, rs


def build_masks(reg, rs, master_alpha):
    """返回 (W 尾巴窗口, fitset 耳眼挖空区, B0 无尾身体)"""
    a = master_alpha > 8 if master_alpha.ndim == 2 else master_alpha[..., 3] > 8
    W = a & rs.region_mask(reg["regions"]["tail"])          # 尾巴窗口（不膨胀，与部件像素级互补）
    fitset = np.zeros((1024, 1024), bool)
    for k, sp in reg["regions"].items():
        if k == "tail":
            continue
        fitset |= rs.dilate(rs.region_mask(sp), reg.get("dilatePx", 3))
    # 真正的"身体"：母版挖掉全部区域（含尾巴）后的主体
    B0 = a & ~W & ~fitset
    return W, fitset, B0, a


def make_body_core(ma, W, fitset, coat="blue"):
    """身体核心：尾巴区留成透明窗口；耳/眼挖空区做 socket 补色（保持不透明）。"""
    core = ma.copy()
    core[..., 3] = np.where(W | fitset, 0, ma[..., 3])
    hole = fitset & (ma[..., 3] > 8)
    if hole.any():
        from fox_traits import socket_fill
        fill = socket_fill(ma, hole, coat)
        cr = core[..., :3].copy()
        cr[hole] = fill[hole]
        core[..., :3] = cr
        core[..., 3] = np.where(hole, 255, core[..., 3])
    return Image.fromarray(core, "RGBA"), int((W & (ma[..., 3] > 8)).sum()), int(hole.sum())


def make_socket(W, B0, seam_px=4, dilate_px=2):
    """socket = 尾巴窗口里"贴着身体"的接缝带（去掉尾巴会让身体破洞/缺口的区域）。

    seam_px  : 沿身体法线方向的接缝深度（默认 4px，与 run_assemble.SEAM_PX 一致）
    dilate_px: 向外放的安全余量
    socket 只取窗口内的部分：窗口外由 body_core 自己覆盖，不需要兜底。
    """
    near = ndimage.binary_dilation(B0, iterations=seam_px)
    seam = W & near
    socket = ndimage.binary_dilation(seam, iterations=dilate_px) & W
    return seam, socket


def make_tail_base(ma, W, socket, grow=3, feather=2):
    """基础尾根兜底件：完全覆盖 socket（再向外 grow px），颜色取自母版尾巴邻域。
    它位于最底层，只会在"变体尾巴没盖住的窗口处"露出来，因此永远不会造成透明洞。"""
    region = ndimage.binary_dilation(socket, iterations=grow)
    known = W & (ma[..., 3] > 8)
    if known.sum() < 50:
        known = ma[..., 3] > 8
    idx = ndimage.distance_transform_edt(~known, return_distances=False,
                                         return_indices=True)
    rgb = ma[..., :3][idx[0], idx[1]]
    a = np.where(region, 255, 0).astype(np.uint8)
    if feather > 0:
        d = ndimage.distance_transform_edt(region)
        a = np.clip(d / float(feather), 0, 1)
        a = np.where(region, 1.0, a)
        a = (a * 255).astype(np.uint8)
    out = np.dstack([rgb.astype(np.uint8), a])
    return Image.fromarray(out, "RGBA"), int(region.sum())


def tint(img, coat):
    if coat == "blue":
        return img
    from fox_traits import load_colorways, recolor_coat
    cmap, _ = load_colorways(os.path.join(DATA, "colorways.json"))
    return recolor_coat(img, cmap["blue"], cmap.get(coat, cmap["blue"]), strength=1.0)


def main():
    reg, rs = load_regions()
    master_path = os.path.join(M, "Base", "fox_base_blue_q4@1024.png")
    ma = np.asarray(Image.open(master_path).convert("RGBA"))
    W, fitset, B0, alpha = build_masks(reg, rs, ma)
    seam, socket = make_socket(W, B0)

    os.makedirs(BODY, exist_ok=True)
    os.makedirs(PARTS, exist_ok=True)

    # --- socket 遮罩 ---
    sm = np.zeros((1024, 1024, 4), np.uint8)
    sm[..., :3] = 255
    sm[..., 3] = np.where(socket, 255, 0)
    Image.fromarray(sm, "RGBA").save(os.path.join(PARTS, "tail_socket_mask@1024.png"))
    ys, xs = np.where(socket)
    sbbox = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
    print("socket: area=%d bbox=%s | 接缝带 area=%d"
          % (int(socket.sum()), sbbox, int(seam.sum())))

    # --- 母版身体核心 + 10 套毛色 ---
    core0, wpx, spx = make_body_core(ma, W, fitset, "blue")
    core0.save(os.path.join(PARTS, "part_body_core@1024.png"))
    print("body_core(blue): 尾巴窗口 %d px, 耳眼 socket 补色 %d px -> %s"
          % (wpx, spx, os.path.join(PARTS, "part_body_core@1024.png")))
    for c in COATS:
        src = os.path.join(M, "Base", "fox_base_%s_q4@1024.png" % c)
        if not os.path.exists(src):
            print("  skip coat", c)
            continue
        ma_c = np.asarray(Image.open(src).convert("RGBA"))
        core_c, _, _ = make_body_core(ma_c, W, fitset, c)
        core_c.save(os.path.join(BODY, "body_core_%s@1024.png" % c))
    print("body_core 毛色版 ->", BODY, len(COATS))

    # --- 基础尾根兜底件（10 套毛色） ---
    base0, bpx = make_tail_base(ma, W, socket)
    base0.save(os.path.join(TAILS, "tail_base_blue@1024.png"))
    for c in COATS:
        if c == "blue":
            continue
        tint(base0, c).save(os.path.join(TAILS, "tail_base_%s@1024.png" % c))
    print("tail_base: 覆盖 %d px x10 毛色 -> %s" % (bpx, TAILS))

    # --- 统一 normal 尾巴为母版原版配套件（替换旧的 768 独立件） ---
    src_part = os.path.join(PARTS, "part_tail@1024.png")
    Image.open(src_part).convert("RGBA").save(os.path.join(TAILS, "tail_normal.png"))
    tmeta_path = os.path.join(TAILS, "_tails_meta.json")
    tmeta = json.load(open(tmeta_path, encoding="utf-8"))
    tmeta["normal"] = {
        "category": "tails", "canvas": [1024, 1024],
        "declaredAnchor": list(TAIL_ROOT_ANCHOR),
        "rootPointInCanvas": list(TAIL_ROOT_ANCHOR),
        "aligned": True, "file": "tail_normal.png",
        "source": "part_tail@1024.png（母版原版尾巴，与 body_core 像素级互补）",
        "note": "旧版 768 独立件已废弃：独立件会破坏包络并引入旋转缩放误差",
    }
    json.dump(tmeta, open(tmeta_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("tail_normal 已统一为母版配套件")

    # --- socket 覆盖验收 ---
    print("\n--- socket 覆盖验收（变体尾巴 + tail_base 兜底）---")
    ok = True
    for f in sorted(os.listdir(TAILS)):
        if not f.endswith(".png") or "tail_base" in f:
            continue
        p = Image.open(os.path.join(TAILS, f)).convert("RGBA")
        if p.size != (1024, 1024):
            print("  %-20s 尺寸 %s 非配套件 -> 跳过" % (f, p.size))
            ok = False
            continue
        a = np.asarray(p)[..., 3] > 8
        cov = float((a & socket).sum()) / max(int(socket.sum()), 1)
        cov_full = float(((a | (np.asarray(base0)[..., 3] > 8)) & socket).sum()) \
            / max(int(socket.sum()), 1)
        flag = "OK" if cov_full >= 0.999 else "!! 兜底不足"
        print("  %-20s 单独覆盖 %.3f | 叠加 tail_base %.3f  %s" % (f, cov, cov_full, flag))
        if cov_full < 0.999:
            ok = False

    # --- 机读规格 ---
    spec = {
        "schemaVersion": "1.0",
        "rule": "tail-behind-body / socket-window",
        "layerOrderBottomToTop": [
            "Tail_Base", "Tail", "Body_Core", "Pattern",
            "Ear_L", "Ear_R", "Eye_L", "Eye_R",
        ],
        "socket": {
            "anchor": list(TAIL_ROOT_ANCHOR),
            "anchorName": "tail_root",
            "note": "统一 socket 锚点；所有尾巴部件以全画布 (0,0) 对齐，根点天然落在此锚点",
            "regionMask": "assets/master/Parts/tail_socket_mask@1024.png",
            "seamAreaPx": int(seam.sum()),
            "socketAreaPx": int(socket.sum()),
            "socketBBox": sbbox,
            "seamPx": 4,
            "socketDilatePx": 2,
            "definition": "窗口内'贴着身体'的 4px 接缝带外扩 2px；"
                          "接缝带归 body_core 所有并做 socket 补色（默认方案），"
                          "因此任何尾型都不会露出透明漏洞",
        },
        "tailWindow": {
            "region": "split_regions.json#regions.tail",
            "noDilate": True,
            "note": "窗口不做膨胀，使 body_core 与 tail 部件像素级互补，合成零缝零白边",
            "areaPx": int((W & alpha).sum()),
        },
        "tailBase": {
            "pattern": "assets/master/Tails/tail_base_<coat>@1024.png",
            "coats": COATS,
            "coverage": "100% 覆盖 socket（额外外扩 3px），短尾/异形尾替换时不会露出透明洞",
            "compositeRule": "Tail_Base 置于最底层，仅在变体尾巴未覆盖的窗口处可见",
        },
        "envelope": {
            "version": "1.2",
            "alignTarget": "body_core",
            "rule": "身体核心的坐标/尺寸/锚点全毛色统一；耳朵与尾巴允许突破统一包络，"
                    "禁止为对齐包络而缩放部件（会压缩性状差异）",
            "bodyCoreBBox": [189, 150, 877, 928],
            "allowOverflow": ["tail", "ear_L", "ear_R"],
        },
        "verified": ok,
    }
    json.dump(spec, open(os.path.join(DATA, "tail_socket.json"), "w",
                         encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\nspec ->", os.path.join(DATA, "tail_socket.json"), "verified=", ok)


if __name__ == "__main__":
    main()
