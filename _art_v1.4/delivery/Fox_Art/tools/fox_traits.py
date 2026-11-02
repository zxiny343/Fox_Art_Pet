# -*- coding: utf-8 -*-
"""
Fantasy Fox 阶段2 性状管线
--------------------------------------------------
1) recolor_coat  : nearest-role ratio transfer，把母版霜蓝映射到任意配色
2) split_components : 白底部件表 -> 连通域切分为独立部件
3) fit_part      : 部件规整到带锚点的部件画布
4) palette_force : 把 AI 生成的部件强制对齐到官方调色板
5) contact_sheet : 生成用于人工视觉验收的拼版图
"""
import os
import json
import numpy as np
from PIL import Image, ImageDraw

# ---------- 部件画布与锚点约定（阶段2 定义，阶段3 组装时使用） ----------
PART_SPEC = {
    "ears":  {"canvas": (384, 384),  "anchor": (192, 320), "rootRule": "bottom-center",
              "note": "耳朵根在底部中心，向上生长"},
    "tails": {"canvas": (768, 768),  "anchor": (672, 576), "rootRule": "bottom-right",
              "note": "尾根在右下角，向左上生长（3/4 视角尾巴在身后左侧）"},
    "eyes":  {"canvas": (160, 160),  "anchor": (80, 80),   "rootRule": "center",
              "note": "眼睛以中心对齐眼窝锚点"},
    "pupils": {"canvas": (160, 160), "anchor": (80, 80),   "rootRule": "center",
               "note": "瞳孔作为独立图层叠加在眼睛中心，与眼型正交组合"},
}

ROLES = ["outline", "shade", "base", "light", "belly", "innerEar", "nose"]


def hex2rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


def load_colorways(path):
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    return {c["id"]: c for c in d["colorways"]}, d


def _unpremultiply(rgb, a):
    """源图是在白底上抠出来的，边缘半透明像素混了白色。还原真实颜色。"""
    af = (a / 255.0)[..., None]
    af = np.maximum(af, 1.0 / 255.0)
    true = (rgb - 255.0 * (1.0 - af)) / af
    return np.clip(true, 0, 255)


def _lum(rgb):
    """Rec.601 亮度。"""
    return 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]


def recolor_coat(img, cw_src, cw_tgt, protect_ellipses=None, strength=1.0,
                 role_masks=None):
    """
    LOCK-F 换色算法：亮度映射 + 色度向量迁移（nearest-role tone/chroma transfer）

      1) 每个像素按与源配色 7 个角色色的距离做反距离加权，得到该像素"属于哪个明暗层"
      2) 亮度：Y_out = Y_tgt_blend * (Y_px / Y_src_blend)
         —— 把整体明度搬到目标配色的明度区间，同时严格保留像素内部的相对明暗
      3) 色度：out = Y_out + chroma_tgt_blend * (|chroma_px| / |chroma_src_blend|)
         —— 色相与饱和度完全来自目标配色，饱和度强弱来自源图像自身的层次

    相比"逐通道比值法"，该方法在近中性目标色（雪白/烟灰）上不会放大通道噪声，
    不会出现偏绿/偏品红的染色，也不会把暗部压死。
    protect_ellipses: [(cx, cy, rx, ry), ...] 这些区域保持原色（眼睛是独立性状）。
    """
    im = img.convert("RGBA")
    arr = np.asarray(im).astype(np.float32)
    rgb = arr[..., :3]
    a = arr[..., 3]

    work = _unpremultiply(rgb, a)

    src = np.stack([hex2rgb(cw_src[r]) for r in ROLES])          # (7,3)
    tgt = np.stack([hex2rgb(cw_tgt[r]) for r in ROLES])          # (7,3)

    d2 = ((work[..., None, :] - src[None, None, :, :]) ** 2).sum(-1)   # (H,W,7)
    w = 1.0 / (d2 + 200.0) ** 2
    if role_masks:
        # 区域级角色禁用：把该角色在这些像素上的权重清零。
        # 必须这样做而不是事后改色 —— 否则金+紫在权重边界上会混成土黄褐色。
        for role_name, allow in role_masks.items():
            w[..., ROLES.index(role_name)] *= allow.astype(np.float32)
    # 归一化必须无条件执行：只在 role_masks 存在时归一化会让无 pointsRule 的
    # 配色权重和远大于 1，Yout 被压到近 0，整只变黑（阶段3 实测踩过）。
    w = w / np.maximum(w.sum(-1, keepdims=True), 1e-6)

    Ysrc_r = _lum(src)                       # (7,)
    Ytgt_r = _lum(tgt)
    Csrc_r = src - Ysrc_r[:, None]           # (7,3) 角色色度向量
    Ctgt_r = tgt - Ytgt_r[:, None]

    Ysrc_b = (w * Ysrc_r[None, None, :]).sum(-1)
    Ytgt_b = (w * Ytgt_r[None, None, :]).sum(-1)
    Csrc_b = (w[..., None] * Csrc_r[None, None]).sum(2)
    Ctgt_b = (w[..., None] * Ctgt_r[None, None]).sum(2)

    Y = _lum(work)
    cpx = work - Y[..., None]

    Yout = Ytgt_b * (Y / np.maximum(Ysrc_b, 1.0))
    k = np.linalg.norm(cpx, axis=-1) / (np.linalg.norm(Csrc_b, axis=-1) + 0.5)
    k = np.clip(k, 0.0, 2.0)

    mapped = np.clip(Yout[..., None] + Ctgt_b * k[..., None], 0, 255)
    out = work * (1.0 - strength) + mapped * strength

    # 眼睛保护：眼睛颜色是独立性状，不随毛色改变
    if protect_ellipses:
        h, wd = a.shape
        yy, xx = np.mgrid[0:h, 0:wd]
        keep = np.zeros((h, wd), dtype=bool)
        for (cx, cy, rx, ry) in protect_ellipses:
            keep |= (((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2) <= 1.0
        out[keep] = work[keep]

    res = np.dstack([out, a]).astype(np.uint8)
    return Image.fromarray(res, "RGBA")


def role_weights(img, cw_src):
    """返回每个像素对各角色色的归一化权重 (H,W,7)，用于区域级精细控制。"""
    im = img.convert("RGBA")
    arr = np.asarray(im).astype(np.float32)
    work = _unpremultiply(arr[..., :3], arr[..., 3])
    src = np.stack([hex2rgb(cw_src[r]) for r in ROLES])
    d2 = ((work[..., None, :] - src[None, None, :, :]) ** 2).sum(-1)
    w = 1.0 / (d2 + 200.0) ** 2
    return w / w.sum(-1, keepdims=True)


def build_region_mask(shape, regions):
    """把 pointsRule.regions 编译成布尔掩膜 (H,W)。"""
    h, wd = shape
    yy, xx = np.mgrid[0:h, 0:wd]
    allow = np.zeros((h, wd), dtype=bool)
    for r in regions:
        if r["type"] == "ellipse":
            allow |= (((xx - r["cx"]) / float(r["rx"])) ** 2 +
                      ((yy - r["cy"]) / float(r["ry"])) ** 2) <= 1.0
        else:
            allow |= ((xx - r["cx"]) ** 2 + (yy - r["cy"]) ** 2) <= float(r["r"]) ** 2
    return allow


def apply_points_rule(img, master, cw_src, cw_tgt, strength=1.0):
    """
    点状配色（points）约束：曜金这类"金色只出现在胸腹与尾尖"的配色，
    默认换色会把所有浅色区（口鼻、脸颊、耳内、四肢内侧）一起染成金色。
    这里把 belly 角色中**不在**指定区域内的像素改投 altColor，
    只保留亮度（保留原有明暗层次），色度换成 alt 色。
    """
    rule = cw_tgt.get("pointsRule")
    if not rule:
        return img
    role = rule.get("applyTo", "belly")
    ri = ROLES.index(role)

    im = img.convert("RGBA")
    out = np.asarray(im).astype(np.float32)
    a = out[..., 3]
    w = role_weights(master, cw_src)
    dom = (w[..., ri] > 0.45) & (a > 40)

    h, wd = dom.shape
    yy, xx = np.mgrid[0:h, 0:wd]
    allow = np.zeros((h, wd), dtype=bool)
    for r in rule["regions"]:
        if r["type"] == "ellipse":
            allow |= (((xx - r["cx"]) / float(r["rx"])) ** 2 +
                      ((yy - r["cy"]) / float(r["ry"])) ** 2) <= 1.0
        else:
            allow |= ((xx - r["cx"]) ** 2 + (yy - r["cy"]) ** 2) <= float(r["r"]) ** 2

    fix = dom & (~allow)
    if not fix.any():
        return img

    # socket 视觉优化：平色补色在未覆盖区会露成硬边色块。
    # 改为"原部件模糊 + 体色"各半混合，露出时读起来是柔和的底毛而不是补丁。
    if soft:
        from scipy import ndimage
        from PIL import Image as _I, ImageFilter as _F
        org = np.stack([ndimage.gaussian_filter(
            ma[..., i].astype(np.float32), sigma=6) for i in range(3)], -1)
        base = np.array(hex2rgb(c["base"]), np.float32)
        blended = np.clip(org * 0.5 + base * 0.5, 0, 255)
        out[hole] = blended[hole]
        return out
    alt = hex2rgb(rule["altColor"])
    altC = alt - _lum(alt[None, None, :])[0]
    Y = _lum(out[..., :3])
    newcol = np.clip(Y[..., None] + altC[None, None, :], 0, 255)
    rgb = out[..., :3]
    rgb[fix] = rgb[fix] * (1.0 - strength) + newcol[fix] * strength
    out = np.dstack([rgb, a]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def palette_force(img, cw_tgt, cw_src_id="blue", colorways=None, strength=0.85):
    """把 AI 生成的部件强制拉回官方调色板，保证跨批次风格一致。"""
    cw_src = colorways[cw_src_id]
    return recolor_coat(img, cw_src, cw_tgt, strength=strength)


# ---------- 部件表切分 ----------
def split_components(img, min_area=1500, max_count=12):
    """
    白底部件表 -> alpha 连通域 -> 若干独立部件（RGBA，已裁到各自 bbox）。
    依赖 scipy.ndimage.label。
    """
    from scipy import ndimage
    im = img.convert("RGBA")
    a = np.asarray(im)[..., 3]
    mask = a > 60
    lab, n = ndimage.label(mask)
    if n == 0:
        return []
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    order = np.argsort(sizes)[::-1]
    parts = []
    for idx in order[:max_count]:
        if sizes[idx] < min_area:
            continue
        ys, xs = np.where(lab == (idx + 1))
        box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
        parts.append(im.crop(box))
    # 按 bbox 左上角 x 排序，保证左右顺序稳定
    parts.sort(key=lambda p: p.getbbox()[0])
    return parts


def _avail(category, pad_ratio=0.10):
    cw, ch = PART_SPEC[category]["canvas"]
    return int(min(cw, ch) * (1 - 2 * pad_ratio))


def common_scale(parts, category, pad_ratio=0.10):
    """
    同一类别的部件必须用**同一个**缩放系数，否则"大耳/小耳""长尾/短尾"
    会被各自填满画布而抹平尺寸差异，性状就失效了。
    """
    avail = _avail(category, pad_ratio)
    scales = []
    for p in parts:
        bb = p.getbbox()
        if not bb:
            continue
        bw, bh = bb[2] - bb[0], bb[3] - bb[1]
        scales.append(min(avail / float(bw), avail / float(bh)))
    return min(scales) if scales else 1.0


def fit_part(part, category, pad_ratio=0.10, fixed_scale=None):
    """
    把部件等比缩放并放进该类别的标准部件画布，使 rootRule 定义的根点落在 anchor 上。
    fixed_scale: 同一类别共用缩放系数，保留部件之间的相对大小。
    返回 (canvas_img, meta)
    """
    spec = PART_SPEC[category]
    cw, ch = spec["canvas"]
    ax, ay = spec["anchor"]
    bb = part.getbbox()
    crop = part.crop(bb)
    bw, bh = crop.size

    if fixed_scale:
        s = fixed_scale
    else:
        avail_w = int(cw * (1 - 2 * pad_ratio))
        avail_h = int(ch * (1 - 2 * pad_ratio))
        s = min(avail_w / float(bw), avail_h / float(bh))
    nw, nh = max(1, int(round(bw * s))), max(1, int(round(bh * s)))
    crop = crop.resize((nw, nh), Image.LANCZOS)

    # 根点在缩放后部件内的位置
    if spec["rootRule"] == "bottom-center":
        rx, ry = nw / 2.0, float(nh)
    elif spec["rootRule"] == "bottom-right":
        rx, ry = float(nw), float(nh)
    else:  # center
        rx, ry = nw / 2.0, nh / 2.0

    # 内容居中放置，绝不裁切；根点的真实像素坐标记进 meta，由组装端对齐
    ox = (cw - nw) // 2
    oy = (ch - nh) // 2
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    canvas.alpha_composite(crop, (ox, oy))
    meta = {
        "category": category,
        "canvas": [cw, ch],
        "declaredAnchor": [ax, ay],
        "rootRule": spec["rootRule"],
        "rootPointInCanvas": [int(round(ox + rx)), int(round(oy + ry))],
        "placedBBox": [ox, oy, ox + nw, oy + nh],
        "placedSize": [nw, nh],
        "scale": round(s, 4),
        "note": "内容居中不裁切；组装时把 rootPointInCanvas 对齐到狐狸身上的锚点",
    }
    return canvas, meta


def cut_bottom_fraction(part, frac):
    """裁掉部件底部 frac 比例的高度（用于去掉 AI 生成的道具阴影底座）。"""
    if frac <= 0:
        return part
    bb = part.getbbox()
    h = bb[3] - bb[1]
    cut = int(round(h * frac))
    if cut <= 0 or cut >= h:
        return part
    return part.crop((bb[0], bb[1], bb[2], bb[3] - cut))


def fit_part_rotated(part, category, target_angle=-123.1, root_find="right",
                     fixed_scale=None):
    """
    尾巴专用规整：
      root  = 形状最右侧点（道具连接扣所在端，即尾根）
      tip   = 距 root 最远的点
      rot   = 目标朝向 - 当前主轴朝向，把所有尾型统一旋到母版尾巴的朝向上
    旋转绕 root 进行，最后把 root 放到 anchor 上。这样 6 种尾型共用一套骨骼曲线。
    """
    spec = PART_SPEC[category]
    cw, ch = spec["canvas"]
    ax, ay = spec["anchor"]
    bb = part.getbbox()
    crop = part.crop(bb)

    if fixed_scale:
        s = fixed_scale
    else:
        avail = _avail(category)
        s = min(avail / float(crop.width), avail / float(crop.height))
    crop = crop.resize((max(1, int(round(crop.width * s))),
                        max(1, int(round(crop.height * s)))), Image.LANCZOS)

    arr = np.asarray(crop)
    alpha = arr[..., 3]
    ys, xs = np.where(alpha > 60)
    if len(xs) == 0:
        return fit_part(part, category)
    if root_find == "right":
        sel = xs >= xs.max() - 4
        root = np.array([xs[sel].mean(), ys[sel].mean()])
    else:
        sel = ys >= ys.max() - 4
        root = np.array([xs[sel].mean(), ys[sel].mean()])
    d = (xs - root[0]) ** 2 + (ys - root[1]) ** 2
    i = int(np.argmax(d))
    tip = np.array([xs[i], ys[i]], dtype=np.float64)
    axis = float(np.degrees(np.arctan2(tip[1] - root[1], tip[0] - root[0])))
    # PIL 的 rotate 是逆时针，数学角 phi 会变成 phi - rot；
    # 想让主轴落到 target，即 axis - rot = target，所以 rot = axis - target。
    rot = (axis - target_angle + 180.0) % 360.0 - 180.0

    # 绕 root 旋转：先把 root 摆到大画布中心，旋转后 root 仍在中心
    S = int(np.ceil(np.hypot(crop.width, crop.height))) + 8
    big = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    big.alpha_composite(crop, (S // 2 - int(round(root[0])),
                               S // 2 - int(round(root[1]))))
    big = big.rotate(rot, resample=Image.BICUBIC, center=(S // 2, S // 2))
    bb2 = big.getbbox()
    if bb2 is None:
        return fit_part(part, category)
    cropped = big.crop(bb2)

    # 旋转后可能超出部件画布，再缩一次
    if cropped.width > cw or cropped.height > ch:
        s2 = min(cw / float(cropped.width), ch / float(cropped.height))
        cropped = cropped.resize((max(1, int(round(cropped.width * s2))),
                                  max(1, int(round(cropped.height * s2)))), Image.LANCZOS)
        scale_total = s * s2
        # root 在新裁剪图中的位置按比例换算
        rx = (S // 2 - bb2[0]) * s2
        ry = (S // 2 - bb2[1]) * s2
    else:
        scale_total = s
        rx = S // 2 - bb2[0]
        ry = S // 2 - bb2[1]

    # 内容居中放置，绝不裁切；旋转后的根点真实坐标记进 meta
    ox = (cw - cropped.width) // 2
    oy = (ch - cropped.height) // 2
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    canvas.alpha_composite(cropped, (ox, oy))
    meta = {
        "category": category,
        "canvas": [cw, ch],
        "declaredAnchor": [ax, ay],
        "rootRule": "auto-detected thick end + axis rotation",
        "rootPointInCanvas": [int(round(ox + rx)), int(round(oy + ry))],
        "rotationDeg": round(rot, 2),
        "detectedAxisDeg": round(axis, 2),
        "targetAxisDeg": target_angle,
        "placedBBox": [ox, oy, ox + cropped.width, oy + cropped.height],
        "placedSize": [cropped.width, cropped.height],
        "scale": round(scale_total, 4),
        "note": "已按主轴旋到母版尾巴朝向；组装时把 rootPointInCanvas 对齐 tail_root",
    }
    return canvas, meta


def socket_fill(ma, hole, coat, colorways=None, outline_tol=90, soft=True):
    """
    给 body_core 的挖空区补色（socket 层），解决"小部件盖不满挖空区"露出透明洞的问题。

    关键：填充源必须排除描边像素。若从描边扩散，挖空区会被填成近黑色，
    导致整只在视觉上变成剪影（阶段3 实测踩过这个坑）。
    做法：从"非描边的体色像素"做最近邻扩散，无可用源时回退到毛色 base。
    """
    from scipy import ndimage
    rgb = ma[..., :3]
    alpha = ma[..., 3] > 8
    cws = colorways or load_colorways(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "01_Data", "colorways.json"))
    if isinstance(cws, tuple):          # load_colorways 返回 (map, raw)
        cws = list(cws[0].values())
    c = next((x for x in cws if x.get("id") == coat), cws[0])
    outline = np.array(hex2rgb(c["outline"]), np.float32)
    dist = np.abs(rgb.astype(np.float32) - outline).sum(-1)
    known = (~hole) & alpha & (dist > outline_tol)
    out = rgb.copy()
    if known.any():
        idx = ndimage.distance_transform_edt(~known, return_distances=False,
                                             return_indices=True)
        out[hole] = rgb[idx[0], idx[1]][hole]
    else:
        out[hole] = np.array(hex2rgb(c["base"]), np.uint8)
    # 极少数离体色过远的像素再压回 base，避免出现孤立暗块
    base = np.array(hex2rgb(c["base"]), np.float32)
    far = np.abs(out.astype(np.float32) - base).sum(-1) > 320
    out[hole & far] = base.astype(np.uint8)
    return out


# ---------- 验收用拼版 ----------
def contact_sheet(items, out_path, cell=320, cols=5, bg=(238, 238, 238)):
    """
    items: [(PIL.Image, label), ...]
    """
    rows = int(np.ceil(len(items) / float(cols)))
    W = cols * cell
    H = rows * (cell + 28)
    sheet = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(sheet)
    for i, (im, label) in enumerate(items):
        r, c = divmod(i, cols)
        x, y = c * cell, r * (cell + 28)
        thumb = im.convert("RGBA").copy()
        thumb.thumbnail((cell - 16, cell - 16), Image.LANCZOS)
        px = x + (cell - thumb.width) // 2
        py = y + (cell - thumb.height) // 2
        sheet.paste(thumb, (px, py), thumb)
        d.text((x + 8, y + cell + 6), label, fill=(30, 30, 30))
    sheet.save(out_path)
    return out_path
