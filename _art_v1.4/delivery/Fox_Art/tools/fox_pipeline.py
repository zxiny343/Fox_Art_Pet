# -*- coding: utf-8 -*-
"""
Fantasy Fox 角色美术资产后处理管线

可灵输出的是扁平 RGB 栅格图，本脚本负责把它变成可交付资产：
    抠图去背 -> 边缘去色(消除白边) -> 规整到 1024 母版(按 LOCK-B 包络) ->
    导出 512/256 -> trim+offsets -> 合成分层 PSD -> 红线自检

用法（示例）:
    python fox_pipeline.py normalize  input.png  out_master.png
    python fox_pipeline.py audit     out_master.png
    python fox_pipeline.py psd       layers.json  Fox_Base.psd

依赖: pillow, numpy, psd-tools
"""

import json
import os
import sys

from PIL import Image, ImageFilter
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer

# ---- LOCK 常量（与 01_Data/anchors.view34.json 保持一致）----
CANVAS = 1024
SAFE_MARGIN = 60
CENTER_X = 512
GROUND_Y = 928
EAR_TIP_Y = 150
ENVELOPE_HEIGHT = GROUND_Y - EAR_TIP_Y  # 778
EXPORTS = (512, 256)
TOL_PX = 12


def load_rgba(path):
    return Image.open(path).convert("RGBA")


def sample_background(img, corners=12):
    """取图像四角像素均值作为背景色估计。"""
    import numpy as np
    a = img.convert("RGB")
    w, h = a.size
    n = corners
    px = []
    for i in range(n):
        for j in range(n):
            px.append(a.getpixel((i, j)))
            px.append(a.getpixel((w - 1 - i, j)))
            px.append(a.getpixel((i, h - 1 - j)))
            px.append(a.getpixel((w - 1 - i, h - 1 - j)))
    return tuple(int(round(sum(p[k] for p in px) / float(len(px)))) for k in range(3))


def remove_background(img, soft_from=26.0, soft_to=78.0, erode_px=1):
    """
    色度抠图 + 边缘去色 + 轻微侵蚀。

    soft_from/soft_to: 与背景色的欧氏距离阈值，之间为半透明过渡带。
    erode_px: alpha 通道侵蚀量，用于吃掉抗锯齿白边。
    返回: RGBA 图像，背景 alpha=0，边缘已去色（不留白边）。
    """
    import numpy as np
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32)
    bg = np.array(sample_background(img), dtype=np.float32)
    dist = np.sqrt(((rgb - bg) ** 2).sum(axis=2))

    alpha = np.clip((dist - soft_from) / (soft_to - soft_from), 0.0, 1.0)
    if erode_px > 0:
        from PIL import ImageChops
        a_img = Image.fromarray((alpha * 255).astype("uint8"), mode="L")
        for _ in range(erode_px):
            a_img = a_img.filter(ImageFilter.MinFilter(3))
        alpha = np.asarray(a_img, dtype=np.float32) / 255.0

    a = alpha[..., None]
    # 去色：C = (C_obs - (1-a) * BG) / a，消除半透明像素里残留的背景色
    eps = 1e-6
    out = np.clip((rgb - (1.0 - a) * bg) / (a + eps), 0, 255)
    rgba = np.concatenate([out, (alpha * 255)[..., None]], axis=2).astype("uint8")
    return Image.fromarray(rgba, mode="RGBA")


def content_bbox(img):
    """按 alpha>8 求内容包围盒。"""
    return img.getbbox() if img.getchannel("A").getextrema()[1] > 8 else None


def matte_by_flood(img, tol=42, feather=0.7):
    """
    边界洪水填充抠图 —— 角色含大面积白色部位时的正确做法。

    色度抠图会把角色身上的白色胸腹、白色脸颊一起当成背景抠掉，形成透明洞。
    这里改为：先把"颜色接近背景"的像素连通域标记出来，只把**与画布边缘连通**
    的那些判为真背景；被描边围在角色内部的大片白色因为不与边缘连通，得以保留。
    """
    import numpy as np
    from scipy import ndimage
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32)
    bg = np.array(sample_background(img), dtype=np.float32)
    dist = np.sqrt(((rgb - bg) ** 2).sum(axis=2))
    bg_like = dist < tol

    labels, n = ndimage.label(bg_like)
    if n == 0:
        alpha = np.full(rgb.shape[:2], 255.0)
    else:
        border = set(labels[0, :].tolist()) | set(labels[-1, :].tolist()) \
            | set(labels[:, 0].tolist()) | set(labels[:, -1].tolist())
        border.discard(0)
        background = np.isin(labels, list(border)) if border else np.zeros_like(bg_like)
        alpha = np.where(background, 0.0, 255.0)

    if feather > 0:
        from PIL import ImageFilter
        a_img = Image.fromarray(alpha.astype("uint8"), mode="L").filter(
            ImageFilter.GaussianBlur(feather))
        alpha = np.asarray(a_img, dtype=np.float32)
        alpha = np.where(alpha > 247, 255.0, np.where(alpha < 8, 0.0, alpha))

    out = img.copy()
    out.putalpha(Image.fromarray(alpha.astype("uint8"), mode="L"))
    return out


def crisp_alpha(img, thr=128, feather=0.6):
    """
    把 alpha 硬化为接近二值，并做极轻微羽化。

    用途一：可灵常给角色加地面投影，灰色阴影在色度抠图后会变成一大片半透明脏区，
    硬化 alpha 能直接把它切掉。
    用途二：赛璐璐描边素材本身就是要硬边，半透明边缘反而会产生白边观感。
    """
    import numpy as np
    a = np.asarray(img.getchannel("A"), dtype=np.float32)
    a = np.where(a >= thr, 255.0, 0.0)
    if feather > 0:
        from PIL import ImageFilter
        a_img = Image.fromarray(a.astype("uint8"), mode="L").filter(
            ImageFilter.GaussianBlur(feather))
        a = np.asarray(a_img, dtype=np.float32)
        a = np.where(a > 247, 255.0, np.where(a < 8, 0.0, a))
    out = img.copy()
    out.putalpha(Image.fromarray(a.astype("uint8"), mode="L"))
    return out


def keep_largest_component(img, min_area=400):
    """
    只保留最大的连通域，剔除角落水印、飞散色点等与主图分离的内容。

    可灵的部分输出会在右下角带半透明水印，抠图后会成为独立小连通域，
    既污染包围盒（破坏包络对齐）又留下脏点，这一步专门清掉它。
    """
    try:
        from scipy import ndimage
    except ImportError:
        return img, 0
    import numpy as np
    a = np.asarray(img.getchannel("A"))
    mask = a > 24
    labels, n = ndimage.label(mask)
    if n <= 1:
        return img, int(n)
    sizes = ndimage.sum(mask, labels, range(1, n + 1))
    keep = int(np.argmax(sizes)) + 1
    cleaned = mask & (labels == keep)
    # 次级连通域若面积足够大（如双尾分离），也保留
    for i, s in enumerate(sizes, start=1):
        if i != keep and s >= min_area and s >= sizes[keep - 1] * 0.05:
            cleaned = cleaned | (labels == i)
    alpha = np.where(cleaned, a, 0).astype("uint8")
    out = img.copy()
    out.putalpha(Image.fromarray(alpha, mode="L"))
    return out, int(n)


def normalize(img, target=CANVAS, envelope_height=ENVELOPE_HEIGHT,
              ground_y=GROUND_Y, center_x=CENTER_X, fit_width=True):
    """
    把抠好的图规整到母版画布：
    - 内容底边对齐 GROUND_Y(928)
    - 内容水平中心对齐 CENTER_X(512)
    - 缩放取 min(包络高/内容高, 安全宽/内容宽)，保证不撑出安全框

    fit_width=True 是四足站姿必需的：四足为横向构图，若只按高度 778 缩放，
    宽度会超出 904 的安全上限，因此改为等比装框。
    """
    bb = content_bbox(img)
    if bb is None:
        raise ValueError("空图像：抠图后无可见内容")
    crop = img.crop(bb)
    max_w = target - 2 * SAFE_MARGIN
    scale = envelope_height / float(crop.height)
    if fit_width:
        scale = min(scale, max_w / float(crop.width))
    new_w = max(1, int(round(crop.width * scale)))
    new_h = max(1, int(round(crop.height * scale)))
    crop = crop.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (target, target), (0, 0, 0, 0))
    x = int(round(center_x - new_w / 2.0))
    y = int(round(ground_y - new_h))
    canvas.paste(crop, (x, y), crop)
    return canvas


def trim_and_offsets(img):
    """trim 版 + 偏移，供图集打包使用。"""
    bb = content_bbox(img)
    if bb is None:
        return None, {"x": 0, "y": 0, "w": 0, "h": 0, "offsetX": 0, "offsetY": 0}
    x, y, x2, y2 = bb
    trimmed = img.crop(bb)
    return trimmed, {"x": x, "y": y, "w": x2 - x, "h": y2 - y,
                     "offsetX": x, "offsetY": y}


def export_scales(img, outdir, basename):
    os.makedirs(outdir, exist_ok=True)
    paths = {}
    paths["master"] = os.path.join(outdir, f"{basename}@1024.png")
    img.save(paths["master"])
    for n in EXPORTS:
        p = os.path.join(outdir, f"{basename}@{n}.png")
        img.resize((n, n), Image.LANCZOS).save(p)
        paths[str(n)] = p
    return paths


def build_psd(layer_spec, out_path, canvas=CANVAS):
    """
    layer_spec: [{"name": "Body_Base", "path": "xxx.png"}, ...]
    顺序 = 图层顺序（第一个在最上）。所有层按全画布 1024 原点 (0,0) 贴入。
    """
    psd = PSDImage.new(mode="RGBA", size=(canvas, canvas))
    for spec in layer_spec:
        im = load_rgba(spec["path"])
        if im.size != (canvas, canvas):
            c = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
            c.paste(im, (0, 0), im)
            im = c
        lay = PixelLayer.frompil(im, psd, spec["name"])
        lay.visible = spec.get("visible", True)
        psd.append(lay)
    psd.save(out_path)
    return out_path


def audit(img, tol=TOL_PX):
    """总规范 §8 红线自检，返回 (passed, report)。"""
    rep = {}
    w, h = img.size
    rep["01_size"] = (w == CANVAS and h == CANVAS, f"{w}x{h}")

    import numpy as np
    a = np.asarray(img.getchannel("A"), dtype=np.int16)
    corner_alpha = int(a[0, 0])
    rep["02_bg_transparent"] = (corner_alpha == 0, f"corner alpha={corner_alpha}")

    bb = content_bbox(img)
    if bb is None:
        return False, {"fatal": "empty image"}
    x, y, x2, y2 = bb
    lo = SAFE_MARGIN - tol
    hi = CANVAS - SAFE_MARGIN + tol
    rep["04_safe_area"] = (y >= lo and y2 <= hi and x >= lo and x2 <= hi,
                           f"bbox=({x},{y})-({x2},{y2}) safe=[{SAFE_MARGIN},{CANVAS - SAFE_MARGIN}]")
    rep["05_ground_y"] = (abs(y2 - GROUND_Y) <= tol, f"bottom y={y2} (target {GROUND_Y})")

    cx = (x + x2) / 2.0
    rep["06_center_x"] = (abs(cx - CENTER_X) <= tol, f"center x={cx:.1f} (target {CENTER_X})")

    width = x2 - x
    rep["07_envelope_w"] = (width <= CANVAS - 2 * SAFE_MARGIN + tol,
                            f"content w={width} (max {CANVAS - 2 * SAFE_MARGIN})")

    # 边缘白边检测：半透明像素中偏白的占比
    semi = (a > 8) & (a < 247)
    white_halo = 0.0
    if semi.any():
        rgb = np.asarray(img.convert("RGB"), dtype=np.int16)
        near_white = ((rgb[..., 0] > 236) & (rgb[..., 1] > 236) & (rgb[..., 2] > 236))
        white_halo = float((near_white & semi).sum()) / float(semi.sum())
    rep["03_no_white_edge"] = (white_halo < 0.30, f"white halo ratio={white_halo:.3f}")

    failed = [k for k, (ok, _) in rep.items() if not ok]
    return (len(failed) == 0), {"failed": failed, "detail": rep,
                                "bbox": {"x": x, "y": y, "x2": x2, "y2": y2}}


def process(src_path, basename, master_dir, psd_out=None, layer_spec=None):
    """一次性跑完：抠图 -> 规整 -> 导出三档 -> 自检。"""
    raw = load_rgba(src_path)
    cut = remove_background(raw)
    master = normalize(cut)
    paths = export_scales(master, master_dir, basename)
    ok, rep = audit(master)
    trimmed, off = trim_and_offsets(master)
    if trimmed is not None:
        trimmed.save(paths["master"].replace(".png", "_trim.png"))
        with open(paths["master"].replace(".png", "_trim.json"), "w", encoding="utf-8") as f:
            json.dump(off, f, ensure_ascii=False, indent=2)
    if psd_out and layer_spec:
        paths["psd"] = build_psd(layer_spec, psd_out)
    return {"paths": paths, "audit_passed": ok, "report": rep}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "normalize":
        src, out = sys.argv[2], sys.argv[3]
        r = process(src, os.path.splitext(os.path.basename(out))[0], os.path.dirname(out) or ".")
        print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
    elif cmd == "audit":
        ok, rep = audit(load_rgba(sys.argv[2]))
        print("PASS" if ok else "FAIL")
        print(json.dumps(rep, ensure_ascii=False, indent=2, default=str))
    elif cmd == "psd":
        spec = json.load(open(sys.argv[2], encoding="utf-8"))
        print(build_psd(spec, sys.argv[3]))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
