# -*- coding: utf-8 -*-
"""
Fantasy Fox 阶段3 组装器
--------------------------------------------------
用可替换部件替换 body_core 上的对应部位，验证"换部件后不需要重新调整"。
  body_core(毛色X, 毛发型Y)
    + tail_型   (根点对齐 tail_root，主轴对齐 tail_root->tail_tip)
    + ear_型_L  (根点对齐 ear_root_l)
    + ear_型_R  (根点对齐 ear_root_r)
    + eye_型_色_L/R (中心对齐 eye_l / eye_r)
    + pupil_型  (中心对齐 eye_l / eye_r，可选叠加)
    + pattern   (alpha 遮罩，clip 到身体)
"""
import os
import sys
import json
import math
import numpy as np
from PIL import Image

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = os.path.join(B, "assets", "master")
OUTP = os.path.join(B, "assets", "master", "Parts")

# ---------- 阶段3 定稿锚点 v3.0（由 alpha 行列剖面实测修正 v2.0） ----------
ANCHORS = {
    "tail_root":  (425, 505),
    "tail_tip":   (200, 320),
    "ear_root_l": (505, 348),
    "ear_root_r": (762, 346),
    "eye_l":      (610, 510),
    "eye_r":      (775, 490),
}
TAIL_TARGET_AXIS = math.degrees(
    math.atan2(ANCHORS["tail_tip"][1] - ANCHORS["tail_root"][1],
               ANCHORS["tail_tip"][0] - ANCHORS["tail_root"][0]))

# R7(v1.4)：旧规格耳朵件（非 1024 全画布对齐）的原始内容高度，
# 供 legacy 分支按 intendedRel 等比缩放。数值实测自
# assets/master/Parts/part_ear_L|R@1024.png 的 alpha bbox 高度。
# 现在所有耳件都是 1024 对齐件，正常组装走不到该分支；此处补齐定义，
# 避免未来误用旧规格件时抛 NameError。
ORIG_EAR_H = {"L": 153, "R": 165}


def load_meta(sub, name):
    p = os.path.join(M, sub, "_%s_meta.json" % name)
    return json.load(open(p, encoding="utf-8"))


def rotate_about(img, root, deg):
    """绕 root 旋转（PIL 为逆时针），裁剪后返回 (img, root_in_new_img)。"""
    if abs(deg) < 1e-6:
        return img, root
    pad = int(max(img.size) * 0.8) + 8
    tmp = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad),
                    (0, 0, 0, 0))
    tmp.alpha_composite(img, (pad, pad))
    rx, ry = root[0] + pad, root[1] + pad
    tmp = tmp.rotate(deg, resample=Image.BICUBIC, center=(rx, ry))
    bb = tmp.getbbox()
    if bb:
        tmp = tmp.crop(bb)
        rx, ry = rx - bb[0], ry - bb[1]
    return tmp, (rx, ry)


def scale_rot_place(base, part, root_in_part, anchor, s=1.0, rot=0.0):
    """绕 root 旋转 rot、缩放 s 后，把 root 对齐到 anchor，合成到 base 上。"""
    part, root_in_part = rotate_about(part, root_in_part, rot)
    if abs(s - 1.0) > 1e-6:
        w, h = part.size
        part = part.resize((max(1, int(round(w * s))), max(1, int(round(h * s)))),
                           Image.LANCZOS)
        root_in_part = (root_in_part[0] * s, root_in_part[1] * s)
    ox = int(round(anchor[0] - root_in_part[0]))
    oy = int(round(anchor[1] - root_in_part[1]))
    out = base.copy()
    out.alpha_composite(part, (ox, oy))
    return out, (ox, oy), part.size


def axis_extent(img, root, axis_deg, sign=1.0):
    """内容沿 axis 方向从 root 出发的最远投影距离（像素）。"""
    a = np.asarray(img)[..., 3] > 8
    ys, xs = np.where(a)
    if len(xs) == 0:
        return 0.0
    r = math.radians(axis_deg)
    ux, uy = math.cos(r) * sign, math.sin(r) * sign
    proj = (xs - root[0]) * ux + (ys - root[1]) * uy
    return float(proj.max())


SEAM_PX = 4   # 接缝带宽度：窗口内"贴着身体"的像素深度，交给身体（尾巴插到身后）


def make_core(coat="blue", fur="short", seam="socketfill", with_base=True):
    """按 split_regions 从指定毛色/毛发的母版切出 body_core。

    seam="socketfill"（默认，尾巴下层方案）：
        尾巴区整体留成透明窗口，但窗口内"贴着身体"的 SEAM_PX 像素接缝带
        归身体所有并做 socket 补色 —— 尾巴自然插到身后，且任何尾型都不会露洞。
    seam="window"：
        整个尾巴区都是透明窗口，靠 tail_base 兜底件保证不露洞（供需要
        "尾巴压在身体上"的特殊表现使用）。
    """
    import run_split as rs
    from scipy import ndimage
    reg, _ = rs.load()
    if fur == "short":
        src = os.path.join(M, "Base", "fox_base_%s_q4@1024.png" % coat)
    else:
        src = os.path.join(M, "Base", "fox_fur_%s_blue_q4@1024.png" % fur)
    master = Image.open(src).convert("RGBA")
    ma = np.asarray(master)
    a = ma[..., 3] > 8
    W = a & rs.region_mask(reg["regions"]["tail"])
    fitset = np.zeros((1024, 1024), bool)
    for k, sp in reg["regions"].items():
        if k == "tail":          # 尾巴走窗口/接缝逻辑，不参与 socket 补色
            continue
        fitset |= rs.dilate(rs.region_mask(sp), reg.get("dilatePx", 3))
    filled = fitset & a
    window = W.copy()
    if seam == "socketfill":
        B0 = a & ~W & ~fitset
        seam_band = W & ndimage.binary_dilation(B0, iterations=SEAM_PX)
        window = W & ~seam_band
        filled = filled | (seam_band & a)
    core = ma.copy()
    core[..., 3] = np.where(filled, 255, np.where(window, 0, ma[..., 3]))
    if filled.any():
        from fox_traits import socket_fill
        cid = coat if fur == "short" else "blue"
        fl = socket_fill(ma, filled, cid)
        cr = core[..., :3].copy()
        cr[filled] = fl[filled]
        core[..., :3] = cr
    return Image.fromarray(core, "RGBA"), src


def assemble(coat="blue", fur="short", tail="normal", ear="large",
             eye="round_blue", pupil=None, pattern=None, verbose=True,
             seam="socketfill", tail_base=False):
    """图层顺序（自下而上）：
        [Tail_Base] -> Tail -> Body_Core(+Pattern) -> Ear_L -> Ear_R -> Eye_L -> Eye_R
       尾巴走身体下层，3/4 视角下默认在身后。"""
    core, src = make_core(coat, fur, seam=seam)
    used = {"core": os.path.basename(src), "seam": seam}

    # 部件跟随毛色：耳/尾素材原画为霜蓝，需随身体毛色做同款映射
    def tint_part(p):
        if coat == "blue":
            return p
        from fox_traits import load_colorways, recolor_coat
        cmap, _ = load_colorways(os.path.join(B, "01_Data", "colorways.json"))
        csrc, ctgt = cmap["blue"], cmap.get(coat, cmap["blue"])
        return recolor_coat(p, csrc, ctgt, strength=1.0)

    # 底层画布：尾巴与兜底件先画，身体再压上去
    stack = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))

    # --- 尾巴兜底件（仅 seam="window" 模式需要） ---
    if tail_base or seam == "window":
        bp = os.path.join(M, "Tails", "tail_base_%s@1024.png" % coat)
        if os.path.exists(bp):
            stack.alpha_composite(tint_part(Image.open(bp).convert("RGBA")), (0, 0))
            used["tail_base"] = os.path.basename(bp)

    # --- 尾巴（身体下层） ---
    # 配套件（从母版变体图按同一 mask 切出）是 1024 全画布对齐的，
    # 直接 (0,0) 叠加即可零错位；旧独立件才需要按锚点缩放旋转。
    tpath = os.path.join(M, "Tails", "tail_%s.png" % tail)
    tp = tint_part(Image.open(tpath).convert("RGBA"))
    if tp.size == (1024, 1024):
        stack.alpha_composite(tp, (0, 0))
        used["tail"] = os.path.basename(tpath)
        if verbose:
            print("  tail  BEHIND-BODY / ALIGNED-FULL-CANVAS")
    else:
        tm = load_meta("Tails", "tails")[tail]
        rot = TAIL_TARGET_AXIS - (-123.1)
        L_part = axis_extent(rotate_about(tp, tuple(tm["rootPointInCanvas"]), rot)[0],
                             rotate_about(tp, tuple(tm["rootPointInCanvas"]), rot)[1],
                             TAIL_TARGET_AXIS)
        L_orig = axis_extent(
            Image.open(os.path.join(OUTP, "part_tail@1024.png")).convert("RGBA"),
            ANCHORS["tail_root"], TAIL_TARGET_AXIS)
        rel = float(tm.get("intendedRel", 1.0))
        s = (L_orig * rel / L_part) if L_part > 1 else 1.0
        stack, off, sz = scale_rot_place(stack, tp, tuple(tm["rootPointInCanvas"]),
                                         ANCHORS["tail_root"], s, rot)
        used["tail"] = tm["file"]
        if verbose:
            print("  tail  BEHIND-BODY s=%.3f offset=%s (legacy part)" % (s, off))

    # --- 花纹（画在身体/尾巴层上，必须在耳/眼之前，否则盖住五官） ---
    # 火焰等花纹要求沿"背脊→尾尖"连续分布，尾巴在下层也必须着色，
    # 否则尾根之后的花纹会被身体裁掉。
    if pattern:
        stack = apply_pattern(stack, coat, pattern)
        core = apply_pattern(core, coat, pattern)
        used["pattern"] = "pattern_%s_mask@1024.png" % pattern

    # --- 身体压在尾巴之上 ---
    stack.alpha_composite(core, (0, 0))
    img = stack

    # --- 耳朵 ---
    em = load_meta("Ears", "ears")
    for side, anc in (("L", "ear_root_l"), ("R", "ear_root_r")):
        vpath = os.path.join(M, "Ears", "ear_%s_%s.png" % (ear, side))
        p = tint_part(Image.open(vpath).convert("RGBA"))
        if p.size == (1024, 1024):
            img.alpha_composite(p, (0, 0))
            used["ear_" + side] = os.path.basename(vpath)
            if verbose:
                print("  ear%-2s ALIGNED-FULL-CANVAS (variant part)" % side)
            continue
        key = "%s_%s" % (ear, side)
        m = em[key]
        bb = p.getbbox()
        h_part = bb[3] - bb[1]
        rel = float(m.get("intendedRel", 1.0))
        s = (ORIG_EAR_H[side] * rel / h_part) if h_part > 1 else 1.0
        img, off, sz = scale_rot_place(img, p, tuple(m["rootPointInCanvas"]),
                                       ANCHORS[anc], s, 0.0)
        used["ear_" + side] = m["file"]
        if verbose:
            print("  ear%-2s s=%.3f offset=%s (legacy anchored part)"
                  % (side, s, off))

    # --- 眼睛（eye 为空表示闭眼/笑眼，由表情件自己画） ---
    if eye:
      fname = "eye_%s.png" % eye
      ep = Image.open(os.path.join(M, "Eyes", fname)).convert("RGBA")
      bb = ep.getbbox()
      ec = ep.crop(bb)
      ew = ec.width
      target_w = 118.0            # 覆盖母版眼洞(约 109x97)
      for anc in ("eye_l", "eye_r"):
          img, off, sz = scale_rot_place(img, ec, (ew / 2.0 * (target_w / ew),
                                                   ec.height / 2.0 * (target_w / ew)),
                                         ANCHORS[anc], target_w / ew, 0.0)
      used["eye"] = fname

      # --- 瞳孔（可选，叠加在眼睛中心） ---
      if pupil:
          pm = load_meta("Eyes", "pupils")
          if pupil in pm:
              p = Image.open(os.path.join(M, "Eyes",
                                          pm[pupil]["file"])).convert("RGBA")
              bb = p.getbbox()
              pc = p.crop(bb)
              tgt = 46.0
              s = tgt / max(pc.size)
              for anc in ("eye_l", "eye_r"):
                  img, _, _ = scale_rot_place(img, pc,
                                             (pc.width / 2.0 * s, pc.height / 2.0 * s),
                                             ANCHORS[anc], s, 0.0)
              used["pupil"] = pm[pupil]["file"]

    img, fixed = repair_pockets(img)
    if fixed:
        used["pocketRepairPx"] = fixed
    return clean_islands(img), used


_WINDOW_CACHE = {}


def tail_window_mask():
    """母版尾巴窗口（懒加载缓存）。"""
    if "W" not in _WINDOW_CACHE:
        import run_split as rs
        reg, _ = rs.load()
        mp = os.path.join(M, "Base", "fox_base_blue_q4@1024.png")
        a = np.asarray(Image.open(mp).convert("RGBA"))[..., 3] > 8
        _WINDOW_CACHE["W"] = a & rs.region_mask(reg["regions"]["tail"])
    return _WINDOW_CACHE["W"]


def repair_pockets(img, max_px=40000):
    """封闭口袋修补：把"被不透明像素围住"的透明小洞补上邻色。

    只处理尾巴窗口内的口袋：短尾 distal 区是开放到背景的正常留白，不会被误填；
    双尾这类在臀部围出的封闭缺口会被补成体色，避免看起来像身上破了个洞。
    """
    from scipy import ndimage
    arr = np.asarray(img).copy()
    a = arr[..., 3] > 8
    filled = ndimage.binary_fill_holes(a)
    pockets = filled & ~a
    pockets = pockets & ndimage.binary_dilation(tail_window_mask(), iterations=2)
    if not pockets.any():
        return img, 0
    lab, n = ndimage.label(pockets)
    sizes = ndimage.sum(pockets, lab, range(1, n + 1))
    keep = np.zeros(n + 1, bool)
    keep[1:] = sizes <= max_px
    pockets = keep[lab]
    if not pockets.any():
        return img, 0
    src = a | ndimage.binary_dilation(pockets, iterations=1) == False  # noqa: E712
    known = a.copy()
    idx = ndimage.distance_transform_edt(~known, return_distances=False,
                                         return_indices=True)
    rgb = arr[..., :3][idx[0], idx[1]]
    arr[..., :3] = np.where(pockets[..., None], rgb, arr[..., :3])
    arr[..., 3] = np.where(pockets, 255, arr[..., 3])
    return Image.fromarray(arr, "RGBA"), int(pockets.sum())


def pattern_style(pattern):
    """读 Patterns/_patterns_meta.json：blend / tintRole / strength。

    v1.2 的 5 个花纹没有该文件时走默认（shade 色 alpha 混合），行为不变。
    """
    d = {"blend": "alpha", "tintRole": "shade", "strength": 0.85}
    p = os.path.join(M, "Patterns", "_patterns_meta.json")
    if os.path.exists(p):
        try:
            return json.load(open(p, encoding="utf-8")).get(pattern, d)
        except Exception:
            pass
    return d


def apply_pattern(core, coat, pattern):
    """花纹遮罩叠在身体层上。遮罩信息在 PNG 的 ALPHA 通道（RGB 恒为白）。
    必须在耳朵/眼睛之前调用，否则会盖住五官。
    blend=screen（火焰纹）：滤色叠加 + 取 light 色，深色毛上依然可见。"""
    cw = json.load(open(os.path.join(B, "01_Data", "colorways.json"),
                        encoding="utf-8"))
    coats = cw["colorways"] if isinstance(cw, dict) and "colorways" in cw else cw
    c = next((x for x in coats if x["id"] == coat), coats[0])
    from fox_traits import hex2rgb
    pmask = Image.open(os.path.join(M, "Patterns",
                                    "pattern_%s_mask@1024.png" % pattern))
    pa = np.asarray(pmask.getchannel("A")).astype(np.float32) / 255.0
    body_a = np.asarray(core)[..., 3].astype(np.float32) / 255.0
    st = pattern_style(pattern)
    tint = hex2rgb(c.get(st.get("tintRole", "shade"), c["base"]))
    arr = np.asarray(core).astype(np.float32)
    k = (pa * body_a)[..., None] * float(st.get("strength", 0.85))
    base = arr[..., :3]
    t = np.array(tint, np.float32)
    if st.get("blend") == "screen":
        # 深色毛的 light 色本身很暗（black 的 light 亮度约 105），
        # 滤色后仍看不清 —— 保证最小可见亮度（保留色相只提亮）。
        minl = float(st.get("minLuma", 0))
        if minl > 0:
            lum = float(0.299 * t[0] + 0.587 * t[1] + 0.114 * t[2])
            if lum < minl and lum < 255:
                kk = (minl - lum) / (255.0 - lum)
                t = t + (255.0 - t) * kk
        scr = 255.0 - (255.0 - base) * (255.0 - t) / 255.0
        arr[..., :3] = base * (1 - k) + scr * k
    else:
        arr[..., :3] = base * (1 - k) + t * k
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")


def clean_islands(img, min_area=600):
    """删除装配过程中产生的孤立小碎片（部件边缘抗锯齿残点）。"""
    from scipy import ndimage
    a = np.asarray(img)
    m = a[..., 3] > 8
    lab, n = ndimage.label(m)
    if n <= 1:
        return img
    sizes = ndimage.sum(m, lab, range(1, n + 1))
    keep = np.zeros(n + 1, bool)
    keep[1:] = sizes >= min_area
    out = a.copy()
    out[..., 3] = np.where(keep[lab], a[..., 3], 0)
    return Image.fromarray(out, "RGBA")


def export(img, name):
    d512 = os.path.join(B, "assets", "export_512")
    d256 = os.path.join(B, "assets", "export_256")
    img.resize((512, 512), Image.LANCZOS).save(
        os.path.join(d512, "%s@512.png" % name))
    img.resize((256, 256), Image.LANCZOS).save(
        os.path.join(d256, "%s@256.png" % name))
    return os.path.join(d512, "%s@512.png" % name)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    a = sys.argv
    g = lambda k, d: (a[a.index(k) + 1] if k in a else d)
    coat = g("--coat", "blue")
    fur = g("--fur", "short")
    tail = g("--tail", "normal")
    ear = g("--ear", "large")
    eye = g("--eye", "round_blue")
    pupil = g("--pupil", None)
    pattern = g("--pattern", None)
    seam = g("--seam", "socketfill")
    name = g("--name", "asm_%s_%s_%s" % (coat, tail, ear))
    print("assemble coat=%s fur=%s tail=%s ear=%s eye=%s pupil=%s pattern=%s seam=%s"
          % (coat, fur, tail, ear, eye, pupil, pattern, seam))
    img, used = assemble(coat, fur, tail, ear, eye, pupil, pattern, seam=seam)
    p = export(img, name)
    print("used:", used)
    print("->", p)
    prev = os.path.join(B, "09_Review", "_asm_%s.png" % name)
    bg = Image.new("RGBA", (1024, 1024), (140, 140, 140, 255))
    bg.alpha_composite(img)
    bg.convert("RGB").save(prev)
    print("preview ->", prev)
