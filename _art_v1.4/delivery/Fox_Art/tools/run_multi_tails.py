# -*- coding: utf-8 -*-
"""P0 多尾素材：以 tail_normal.png 为基础，绕 tail_root=(425,505) 程序化分叉。

规格（任务单 v1.3 §1）：
  triple: -28, 0, +28
  quad  : -28, -14, +14, +28
  quint : -28, -14, 0, +14, +28
  nine  : -56,-42,-28,-14,0,+14,+28,+42,+56（扇形展开）
外侧分支略缩短、略细化；分叉点统一 (425,505)；无透明缝、不糊。

实现：绕"缩放中心 C"（根点向尾尖方向偏移 40px，避免根区被缩窄）做
旋转 θ + 非均匀缩放（沿主轴 s_l 缩短 / 垂直方向 s_w 细化）的仿射变换，
按 |θ| 降序 alpha 叠加（外侧分支在下层）。
"""
import os
import json
import math
import numpy as np
from PIL import Image

B = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TAILS = os.path.join(B, "assets", "master", "Tails")
REVIEW = os.path.join(B, "09_Review")

ROOT = np.array([425.0, 505.0])          # socket 锚点 tail_root
TIP_DIR = np.array([-0.843, -0.538])     # 根→尾尖方向（实测 -147.6°）
C_FRAC = 40.0                            # 缩放中心沿尾向偏移量（保护根区）
C = ROOT + TIP_DIR * C_FRAC

# 外侧分支参数：t = |θ|/56
S_LEN_K = 0.08                           # 最外侧缩短 8%
S_WID_K = 0.28                           # 最外侧细化 28%

BRANCHES = {
    "triple": [-28, 0, 28],
    "quad":   [-28, -14, 14, 28],
    "quint":  [-28, -14, 0, 14, 28],
    "nine":   [-56, -42, -28, -14, 0, 14, 28, 42, 56],
}


def branch_matrix(theta_deg, s_l, s_w):
    """源点 p -> 目标 p' = C + M·(p-C)；返回 PIL AFFINE 逆映射 6 参。"""
    th = math.radians(theta_deg)
    c, s = math.cos(th), math.sin(th)
    R = np.array([[c, -s], [s, c]])
    u = TIP_DIR
    n = np.array([-u[1], u[0]])
    U = np.stack([u, n], axis=1)                     # 局部系基
    M = R @ U @ np.diag([s_l, s_w]) @ U.T
    Minv = np.linalg.inv(M)
    a, b = Minv[0, 0], Minv[0, 1]
    d, e = Minv[1, 0], Minv[1, 1]
    cx, cy = C - M @ (Minv @ C)                      # 平移项：x = Minv(x'-C)+C
    t = C - Minv @ C
    return (a, b, t[0], d, e, t[1])


def make_branch(base, theta_deg):
    t = abs(theta_deg) / 56.0
    s_l = 1.0 - S_LEN_K * t
    s_w = 1.0 - S_WID_K * t
    mat = branch_matrix(theta_deg, s_l, s_w)
    return base.transform((1024, 1024), Image.AFFINE, mat,
                          resample=Image.BICUBIC)


def composite(branches):
    """按 |θ| 降序叠加（外侧在下层），中心分支最上。"""
    order = sorted(branches, key=lambda x: (-abs(x[0]), x[0]))
    canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    for th, im in order:
        canvas.alpha_composite(im, (0, 0))
    return canvas


def stats(im):
    a = np.asarray(im)[..., 3] > 8
    ys, xs = np.where(a)
    return (int(a.sum()),
            (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())))


def main():
    os.makedirs(REVIEW, exist_ok=True)
    base = Image.open(os.path.join(TAILS, "tail_normal.png")).convert("RGBA")
    assert base.size == (1024, 1024)

    prev = []
    for name, angles in BRANCHES.items():
        branches = [(th, make_branch(base, th)) for th in angles]
        out = composite(branches)
        p = os.path.join(TAILS, "tail_%s.png" % name)
        out.save(p)
        area, bbox = stats(out)
        clip = bbox[0] >= 4 and bbox[1] >= 4 and \
            bbox[2] <= 1019 and bbox[3] <= 1019
        print("tail_%-7s branches=%d area=%6d bbox=%s noClip=%s"
              % (name, len(angles), area, bbox, clip))
        prev.append((name, out))

    # --- 预览图：4 件 alpha 棋盘格拼版 ---
    cell = 512
    sheet = Image.new("RGB", (cell * 4, cell), (200, 200, 200))
    for i, (name, im) in enumerate(prev):
        s = im.resize((cell, cell), Image.LANCZOS)
        bg = Image.new("RGBA", (cell, cell))
        bgp = bg.load()
        for y in range(0, cell, 16):
            for x in range(0, cell, 16):
                v = 235 if ((x // 16) + (y // 16)) % 2 == 0 else 205
                for yy in range(y, min(y + 16, cell)):
                    for xx in range(x, min(x + 16, cell)):
                        bgp[xx, yy] = (v, v, v, 255)
        bg.alpha_composite(s, (0, 0))
        sheet.paste(bg.convert("RGB"), (i * cell, 0))
    sheet.save(os.path.join(REVIEW, "_multi_tails_preview.png"))
    print("preview -> 09_Review/_multi_tails_preview.png")

    # --- 更新 _tails_meta.json ---
    mp = os.path.join(TAILS, "_tails_meta.json")
    meta = json.load(open(mp, encoding="utf-8"))
    for name, angles in BRANCHES.items():
        area, bbox = stats(Image.open(os.path.join(
            TAILS, "tail_%s.png" % name)).convert("RGBA"))
        meta[name] = {
            "category": "tails",
            "canvas": [1024, 1024],
            "declaredAnchor": [425, 505],
            "rootPointInCanvas": [425, 505],
            "aligned": True,
            "file": "tail_%s.png" % name,
            "source": "程序化分叉：tail_normal.png 绕 tail_root(425,505) "
                      "旋转 %s°，外侧分支缩短≤8%%/细化≤28%%" % angles,
            "branchCount": len(angles),
            "branchAnglesDeg": angles,
            "alphaPx": area,
            "bbox": bbox,
            "note": "v1.3 P0 新增；与 tail_normal 同为 normal 形制"
        }
    json.dump(meta, open(mp, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("meta updated:", mp)


if __name__ == "__main__":
    main()
