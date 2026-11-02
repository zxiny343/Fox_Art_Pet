# -*- coding: utf-8 -*-
"""P2 零散部件（v1.3 §4）：折耳 / 铜瞳 / 细尾。全部程序化派生，不出 AI 新图。

  折耳 ear_fold_L|R.png   以 ear_small 为基底，把耳尖沿折叠线翻折朝下
  铜瞳 eye_<shape>_copper.png  虹膜区 HSV 换色到 #B87333 系（保留高光与描边）
  细尾 tail_thin.png       tail_normal 沿横向压缩 + 开运算去毛刺（细、直、毛少）

同步更新 traits.json（ear/eyeColor/tail）与各 _meta.json。
"""
import os
import sys
import json
import colorsys

B = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(B, "tools"))
import numpy as np
from PIL import Image
from scipy import ndimage

M = os.path.join(B, "assets", "master")
EARS = os.path.join(M, "Ears")
EYES = os.path.join(M, "Eyes")
TAILS = os.path.join(M, "Tails")
E512 = os.path.join(B, "assets", "export_512")
E256 = os.path.join(B, "assets", "export_256")
REVIEW = os.path.join(B, "09_Review")

FOLD_FRAC = 0.38        # 被折的耳尖占耳朵全高的比例（自耳尖向下）
FOLD_SQUASH = 0.70      # 折下来部分的纵向压缩
FOLD_SHIFT = 0.12       # 折下来部分的横向偏移（朝脸侧）
COPPER = "#C07A38"       # #B87333 提亮版：虹膜在深色瞳孔旁会显得更暗，需补亮
COPPER_LIFT = 1.10       # Value 再抬 10%，保证与 gold 拉开区分度
THIN_W = 0.52           # 细尾横向压缩
THIN_L = 1.04           # 细尾略微拉长


def export_deriv(im, name):
    for n, d in ((512, E512), (256, E256)):
        im.resize((n, n), Image.LANCZOS).save(
            os.path.join(d, "%s@%d.png" % (name, n)))


# ---------------- 折耳 ----------------
def fold_by_rotation(src, side):
    """刚性旋转折耳：耳尖绕折痕点整体旋转，纹理不会被撕裂（网格弯曲会）。

    网格弯曲（bend_ear）在耳内多色区域会产生锯齿状撕裂；刚性旋转只改变
    几何位置，内部色块完整，折痕处用闭运算弥合。
    """
    x0, y0, x1, y1 = src.getbbox()
    H = y1 - y0
    yf = int(y0 + H * 0.52)                    # 折痕：耳朵中部偏上
    cx = int((x0 + x1) / 2.0)
    # 耳尖朝角色前方（画面右）下折：PIL 正角度 = 屏幕逆时针 = 朝右
    ang = 52.0 if side == "L" else 46.0
    top = src.crop((0, 0, 1024, yf))
    bot = src.crop((0, yf, 1024, 1024))
    rot = top.rotate(ang, resample=Image.BICUBIC, center=(cx, yf))
    out = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    out.paste(bot, (0, yf))
    out.alpha_composite(rot, (0, 0))
    a = np.array(out)
    m = a[..., 3] > 8
    m2 = ndimage.binary_closing(m, iterations=2)      # 弥合折痕缝
    a[..., 3] = np.where(m2, a[..., 3], 0)
    return Image.fromarray(a, "RGBA")


def bend_ear(src, side):
    """连续弯曲变形（无断口）：耳根不动，耳尖沿二次曲线朝脸侧下压。

    翻折贴片法会在折痕处留下直线切边和错位，改成整体网格弯曲后轮廓连续。
    逆映射：dst_y 与 src_y 同高，故 t 可先由目标 Y 求出，再回退偏移量。
    """
    from scipy import ndimage as ndi
    a = np.array(src).astype(np.float32)
    x0, y0, x1, y1 = src.getbbox()
    y_root, y_tip = float(y1), float(y0)
    H = max(1.0, y_root - y_tip)
    W = float(x1 - x0)
    t0 = 0.30                                  # 从耳根往上 30% 处开始折
    # 3/4 视角角色朝右前方：两耳都朝 +x（角色前方）折，双耳才对称
    sign = 1.0
    DX = 0.42 * W * sign
    DY = 0.42 * H                              # 向下压（+y）
    YY, XX = np.mgrid[0:1024, 0:1024].astype(np.float32)
    t = np.clip((y_root - YY) / H, 0.0, 1.0)
    u = np.clip((t - t0) / (1.0 - t0), 0.0, 1.0)
    # 指数 1.4 而非 2：折痕处转折更急，更像"折角"而不是整体歪斜
    sx = XX - DX * u ** 1.4
    sy = YY - DY * u ** 1.4
    out = np.zeros_like(a)
    for c in range(3):                      # RGB 用三次样条，避免拉伸出锯齿
        out[..., c] = ndi.map_coordinates(a[..., c], [sy, sx], order=3,
                                          mode="constant", cval=0.0)
    out[..., 3] = ndi.map_coordinates(a[..., 3], [sy, sx], order=1,
                                      mode="constant", cval=0.0)
    al = out[..., 3]
    al = np.clip((al - 40.0) / (170.0 - 40.0), 0.0, 1.0) * 255.0
    out[..., 3] = al
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")


def fold_ear(side):
    """折耳 = ear_small 连续弯曲下折。

    刚性旋转会在切口两侧裂开（只有中线一点重合），旋转出去的上半部看起来
    就是"破碎色块"；连续弯曲（bend_ear）轮廓始终相连，是这里唯一可行的做法。
    """
    src = Image.open(os.path.join(EARS, "ear_small_%s.png" % side)).convert("RGBA")
    return bend_ear(src, side)


def _old_fold_ear(side):
    """（已废弃）耳件是 1024 全画布对齐件：折叠在画布坐标里做，锚点天然不变。"""
    src = Image.open(os.path.join(EARS, "ear_small_%s.png" % side)).convert("RGBA")
    x0, y0, x1, y1 = src.getbbox()
    h = y1 - y0
    yf = int(y0 + h * FOLD_FRAC)                # 折叠线（靠耳尖一侧）
    top = src.crop((x0, y0, x1, yf))            # 耳尖部分
    # 上下翻转 → 耳尖朝下；纵向压缩 → 折耳的耷拉感
    top = top.transpose(Image.FLIP_TOP_BOTTOM)
    top = top.resize((top.width, max(1, int(top.height * FOLD_SQUASH))),
                     Image.LANCZOS)
    dx = int(top.width * FOLD_SHIFT) * (1 if side == "L" else -1)   # 朝脸侧
    # 清掉原耳尖区域
    from PIL import ImageDraw
    md = Image.new("L", src.size, 255)
    ImageDraw.Draw(md).rectangle([x0, y0, x1, yf], fill=0)
    out = src.copy()
    out.putalpha(Image.composite(src.getchannel("A"),
                                 Image.new("L", src.size, 0), md))
    out.alpha_composite(top, (x0 + dx, yf + 1))
    # 折痕处可能有 1~2px 缝：闭运算弥合（不动描边，只补 alpha）
    a = np.asarray(out).copy()
    m = a[..., 3] > 8
    m2 = ndimage.binary_closing(m, iterations=1)
    a[..., 3] = np.where(m2, a[..., 3], 0)
    return Image.fromarray(a, "RGBA")


# ---------------- 铜瞳 ----------------
def copper_eye(path):
    im = Image.open(path).convert("RGBA")
    a = np.array(im)
    rgb = a[..., :3].astype(np.float32) / 255.0
    alpha = a[..., 3]
    mx = rgb.max(-1)
    mn = rgb.min(-1)
    v = mx
    s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    iris = (s > 0.22) & (v > 0.28) & (alpha > 40)     # 虹膜：有饱和度且不是描边
    # 目标铜色 #B87333
    tr, tg, tb = (int(COPPER[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    th_, ts_, tv_ = colorsys.rgb_to_hsv(tr, tg, tb)
    hsv = np.zeros_like(rgb)
    for i in range(rgb.shape[0]):
        pass
    # 逐像素 RGB→HSV 只在小区域做（虹膜像素通常在 1 万以内）
    ys, xs = np.where(iris)
    out_rgb = rgb.copy()
    for y, x in zip(ys, xs):
        r_, g_, b_ = rgb[y, x]
        h_, s_, v_ = colorsys.rgb_to_hsv(r_, g_, b_)
        # 保留 Value（明暗/高光）与部分饱和度，只换色相到铜；整体上提亮度
        nv = min(1.0, v_ * COPPER_LIFT)
        ns = min(1.0, max(s_, ts_ * 0.95))
        nr, ng, nb = colorsys.hsv_to_rgb(th_, ns, nv)
        out_rgb[y, x] = (nr, ng, nb)
    a[..., :3] = (np.clip(out_rgb, 0, 1) * 255).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


# ---------------- 细尾 ----------------
def thin_tail():
    """锥形收细：根部 25% 保持原宽度（必须继续盖住 body_core 的尾根接缝带），
    之后沿轴线性收细到 THIN_W。整体仿射压缩会把根部一起压窄，导致
    body_core 上的接缝孤岛不再被覆盖，组装后出现第二块连通域。"""
    from scipy import ndimage as ndi
    src = Image.open(os.path.join(TAILS, "tail_normal.png")).convert("RGBA")
    a = np.array(src).astype(np.float32)
    root = np.array([425.0, 505.0])
    u = np.array([-0.843, -0.538])          # 根→尾尖
    n = np.array([-u[1], u[0]])
    XX, YY = np.mgrid[0:1024, 0:1024].astype(np.float32)
    rx, ry = XX - root[0], YY - root[1]
    d = rx * u[0] + ry * u[1]               # 沿轴距离
    v = rx * n[0] + ry * n[1]               # 横向偏移
    Lmax = 340.0
    d0 = 0.25 * Lmax
    f = 1.0 - (1.0 - THIN_W) * np.clip((d - d0) / (Lmax - d0), 0.0, 1.0) * THIN_L
    vsrc = np.where(f > 1e-3, v / np.maximum(f, 1e-3), v)
    sx = root[0] + u[0] * d + n[0] * vsrc
    sy = root[1] + u[1] * d + n[1] * vsrc
    out = np.zeros_like(a)
    for c in range(4):
        out[..., c] = ndi.map_coordinates(a[..., c], [sy, sx], order=1,
                                          mode="constant", cval=0.0)
    thin = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")
    ta = np.array(thin)
    al = ta[..., 3].astype(np.float32) / 255.0
    m = al > 0.5
    # 横向压缩会把尾巴原本的窄腰掐断（实测出现 4082px 的独立尾尖块）。
    # closing 只填窄缝不增粗，是这里唯一正确的形态学操作（opening 会切断）。
    m = ndimage.binary_closing(m, iterations=3)
    # 去毛刺：平滑 + 重阈值，让轮廓更"直、少毛"（sigma 偏大以削掉丝状毛尖）
    sm = ndimage.gaussian_filter(m.astype(np.float32), 1.7)
    m = sm > 0.55
    ta[..., 3] = np.where(m, 255, 0).astype(np.uint8)
    return Image.fromarray(ta, "RGBA")


def main():
    # --- 折耳 ---
    ear_meta = json.load(open(os.path.join(EARS, "_ears_meta.json"),
                              encoding="utf-8"))
    for side in ("L", "R"):
        im = fold_ear(side)
        im.save(os.path.join(EARS, "ear_fold_%s.png" % side))
        src_m = ear_meta["small_" + side]
        ear_meta["fold_" + side] = dict(
            src_m,
            file="ear_fold_%s.png" % side,
            intendedRel=0.78,
            note="v1.3 P2：ear_small 基础上耳尖沿 %.0f%% 高度处翻折朝下"
                 "（程序化派生，未出新 AI 图）；体量接近 ear_small"
                 % (FOLD_FRAC * 100))
        print("ear_fold_%s  bbox=%s" % (side, im.getbbox()))
    json.dump(ear_meta, open(os.path.join(EARS, "_ears_meta.json"), "w",
                             encoding="utf-8"), ensure_ascii=False, indent=1)

    # --- 铜瞳 ---
    shapes = sorted({f.split("_")[1] for f in os.listdir(EYES)
                     if f.startswith("eye_") and f.count("_") >= 1
                     and f.endswith("_blue.png")})
    made = []
    for sh in shapes:
        srcp = os.path.join(EYES, "eye_%s_blue.png" % sh)
        if not os.path.exists(srcp):
            continue
        im = copper_eye(srcp)
        out = os.path.join(EYES, "eye_%s_copper.png" % sh)
        im.save(out)
        made.append("eye_%s_copper.png" % sh)
    print("铜瞳:", made)

    # --- 细尾 ---
    tt = thin_tail()
    tt.save(os.path.join(TAILS, "tail_thin.png"))
    tm = json.load(open(os.path.join(TAILS, "_tails_meta.json"),
                        encoding="utf-8"))
    a = np.asarray(tt)[..., 3] > 8
    ys, xs = np.where(a)
    tm["thin"] = {
        "category": "tails", "canvas": [1024, 1024],
        "declaredAnchor": [425, 505], "rootPointInCanvas": [425, 505],
        "aligned": True, "file": "tail_thin.png",
        "source": "tail_normal.png 横向压缩 %.2f× + 开运算去毛刺" % THIN_W,
        "alphaPx": int(a.sum()),
        "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
        "boneSegments": 2,
        "note": "v1.3 P2：蓬尾的反义——细、直、毛量少",
    }
    json.dump(tm, open(os.path.join(TAILS, "_tails_meta.json"), "w",
                       encoding="utf-8"), ensure_ascii=False, indent=1)
    print("tail_thin  面积=%d bbox=%s" % (int(a.sum()), tm["thin"]["bbox"]))
    export_deriv(tt, "tail_thin")

    # --- traits.json ---
    p = os.path.join(B, "01_Data", "traits.json")
    d = json.load(open(p, encoding="utf-8"))
    ear = next(c for c in d["categories"] if c["id"] == "ear")
    if "ear_fold" not in ear["values"]:
        ear["values"].append("ear_fold")
    ec = next(c for c in d["categories"] if c["id"] == "eyeColor")
    if "eye_copper" not in ec["values"]:
        ec["values"].append("eye_copper")
    tail = next(c for c in d["categories"] if c["id"] == "tail")
    if "tail_thin" not in tail["values"]:
        tail["values"].append("tail_thin")
    tail["boneSegments"]["tail_thin"] = 2
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("traits: ear=%s" % ear["values"])
    print("traits: eyeColor=%s" % ec["values"])
    print("traits: tail boneSegments=%s" % tail["boneSegments"])


if __name__ == "__main__":
    main()
