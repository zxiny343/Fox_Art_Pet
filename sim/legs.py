# -*- coding: utf-8 -*-
"""四足步态腿部 rig —— body_core 的四条腿画在一张位图里、没有独立骨骼，
原始 walk 的腿部通道（hip/shoulder/foot/paw）全被丢弃。

这里程序化补救：扫描 core 底部 alpha 找到四条脚，切成独立腿图层，按
四足 walk 步态（对角两两同步）绕根部摆动 + 抬腿。只处理 Q 版短腿
（脚露在身体下缘的那种），幅度小、切口在腿根部，视觉自然。

朝向：腿永远按「朝右走」摆动（正角度=向前=朝右），镜像在 app._post
整图翻转时一起翻，自然变成朝左。

缓存策略：腿部位置检测（_detect）按 (spec_key, work) 缓存——一只狐狸
在同一工作分辨率下腿位置不变；切件（_split）每帧做，因为 core 每帧
被 _scaled_core 呼吸缩放改过，要切当前帧的像素。切件成本约 1ms。
"""
import math
import numpy as np
from PIL import Image

# (spec_key, work) -> info[list of 4 legs] 或 None
_INFO_CACHE = {}

# 四足 walk 步态：对角两两同步。
# 4 条腿从左到右假设 [LB, LF, RF, RB]（左后/左前/右前/右后），
# 对角 = LB+RF (idx 0,2) / LF+RB (idx 1,3)，用相位偏移让 0+2 同相、1+3 +0.5
_GAIT_OFFSET = (0.0, 0.5, 0.0, 0.5)

# 哪些动作启用腿部 rig（散步/奔跑类）
WALK_AIDS = ('walk', 'run', 'walk_fast', 'walk_fx', 'sneak', 'trot')


def _find_leg_peaks(density, min_dist, min_h):
    """在列密度曲线上找局部极大值，合并近邻峰。"""
    peaks = []
    n = len(density)
    for i in range(3, n - 3):
        v = density[i]
        if v >= min_h and v >= density[i - 1] and v >= density[i + 1] \
                and v >= density[i - 2] and v >= density[i + 2]:
            peaks.append((i, v))
    merged = []
    for p in peaks:
        if merged and p[0] - merged[-1][0] < min_dist:
            if p[1] > merged[-1][1]:
                merged[-1] = p
        else:
            merged.append(p)
    return [p[0] for p in merged]


def _detect(core_img):
    """扫描 core 底部 alpha，返回 4 条腿信息或 None（检测失败）。

    检测区域用底部 22%（找腿的 x 位置，范围够宽能定位），
    但切件高度只取底部 ~11%（_split 里 y_root = y_foot - leg_cut_h），
    避免切到身体下缘造成撕裂。

    每条腿：xc（中心 x）、y_root（根部 y，切件上界）、
            y_foot（脚底 y，= alpha 底端）、x0/x1（切的左右边界）。
    """
    a = np.asarray(core_img.split()[3])
    h, w = a.shape
    ys, xs = np.where(a > 30)
    if len(xs) < 50:
        return None
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    body_h = y1 - y0
    if body_h < 80:
        return None
    # 检测区域：底部 22%（找 x 峰用，范围宽）
    leg_detect_h = max(40, int(body_h * 0.22))
    leg_detect_y0 = y1 - leg_detect_h
    region = a[leg_detect_y0:y1, :]
    density = (region > 30).sum(axis=0).astype(float)
    if len(density) > 9:                       # 平滑掉单像素噪点
        kern = np.ones(7)
        density = np.convolve(density, kern / 7.0, mode='same')
    min_dist = max(30, int((x1 - x0) * 0.08))
    min_h = max(10, leg_detect_h * 0.12)
    peaks = _find_leg_peaks(density, min_dist, min_h)
    if len(peaks) < 4:
        # 退化：取密度最高的若干候选，按 min_dist 聚类
        cand = sorted(np.argsort(density)[-12:][::-1])
        peaks = []
        for x in cand:
            if not peaks or x - peaks[-1] >= min_dist:
                peaks.append(x)
        peaks = sorted(peaks)[:4]
    if len(peaks) < 4:
        peaks = [int(x0 + (x1 - x0) * f) for f in (0.28, 0.42, 0.58, 0.72)]
    peaks = sorted(peaks)[:4]
    # 切件宽度：窄一点，只覆盖脚部，不切身体两侧
    leg_w = max(20, int((x1 - x0) * 0.045))
    # 切件高度：底部 ~11%（只切脚部，避免撕裂身体下缘）
    leg_cut_h = max(22, int(body_h * 0.11))
    y_root = y1 - leg_cut_h
    info = []
    for xc in peaks:
        info.append(dict(xc=int(xc), y_root=int(y_root), y_foot=int(y1),
                         x0=max(0, int(xc) - leg_w),
                         x1=min(w, int(xc) + leg_w)))
    return info


def _split(core_img, info):
    """切：torso（腿部 mask 清零 + 缺口填采样色）+ 4 条独立 leg 图层（bbox 尺寸）。

    腿摆开后 torso 缺口会露出背景；用切口上方身体下缘的采样色填缺口，
    视觉上是「身体下缘实心色」而非白底，避免撕裂感。采样色半透明（α=200），
    让边缘和身体融合。

    leg 图层只切 bbox 尺寸（x0..x1, y_root..y_foot），alpha_composite
    时带 dest 偏移贴回，避免在全画布上做 transform 和合成。
    """
    arr = np.array(core_img, dtype=np.uint8)            # H,W,4 RGBA（只读源）
    alpha = arr[:, :, 3]
    torso_arr = arr.copy()
    legs = []
    for lg in info:
        y0, y1 = lg['y_root'], lg['y_foot']
        x0, x1 = lg['x0'], lg['x1']
        sub_alpha = alpha[y0:y1, x0:x1]
        mask_sub = sub_alpha > 20
        if not mask_sub.any():
            continue
        # 采样身体下缘色：切口上方 12px 的非透明像素平均 RGB
        sy0 = max(0, y0 - 12)
        sy1 = max(sy0 + 1, y0 - 2)
        sregion = arr[sy0:sy1, x0:x1]
        salpha = alpha[sy0:sy1, x0:x1]
        smask = salpha > 20
        if smask.any():
            fill_rgb = sregion[smask][:, :3].mean(axis=0).astype(np.uint8)
        else:
            fill_rgb = np.array([100, 70, 50], dtype=np.uint8)  # 退化深棕
        # torso：腿部 mask 清零后填采样色（半透明，融合边缘）
        for ch in range(3):
            torso_arr[y0:y1, x0:x1, ch][mask_sub] = int(fill_rgb[ch])
        torso_arr[y0:y1, x0:x1, 3][mask_sub] = 200
        # leg layer：bbox 尺寸，只这条腿有像素（原始颜色，全 alpha）
        leg_arr = np.zeros((y1 - y0, x1 - x0, 4), dtype=np.uint8)
        leg_arr[mask_sub] = arr[y0:y1, x0:x1][mask_sub]
        legs.append((lg, Image.fromarray(leg_arr)))
    torso_img = Image.fromarray(torso_arr)
    return torso_img, legs


def _get_info(spec_key, core_img, work):
    """腿位置检测，按 (spec_key, work) 缓存。"""
    key = (spec_key, work)
    if key in _INFO_CACHE:
        return _INFO_CACHE[key]
    info = _detect(core_img)
    _INFO_CACHE[key] = info
    return info


def rig_legs(core_img, t, spec_key, work, amp_deg=12.0, lift_px=8.0):
    """返回合成 core：torso + 4 条按 walk 步态摆动的腿。

    core_img  当前帧的 core（已被 _scaled_core 呼吸缩放过）
    t         walk 动作归一化时间 [0,1)
    amp_deg   摆动角度峰值（度），±12° —— Q 版短腿在 168px 显示下
              ±6° 只有 ~3px 位移看不清，提到 12° 脚端位移约 6px 才可见
    lift_px   抬腿高度峰值（px @ work 分辨率）
    """
    info = _get_info(spec_key, core_img, work)
    if info is None or len(info) < 4:
        return core_img                      # 检测失败，退回原图
    torso, legs = _split(core_img, info)
    if len(legs) < 4:
        return core_img
    out = torso.copy()
    for i, (lg, leg) in enumerate(legs):
        off = _GAIT_OFFSET[i % 4]
        ph = (t + off) % 1.0
        # 正弦摆动：前半周（0~0.5）腿向前 + 抬起，后半周向后 + 落地
        s = math.sin(ph * 2 * math.pi)
        ang = amp_deg * s
        up = max(0.0, s) * lift_px
        # leg 是 bbox 尺寸，bbox 顶 = y_root，所以 bbox 内 pivot = (xc-x0, 0)
        cx_in = lg['xc'] - lg['x0']
        cy_in = 0
        rad = math.radians(ang)
        co, si = math.cos(rad), math.sin(rad)
        a_, b_ = co, si
        c_ = cx_in * (1 - co) + cy_in * si
        d_, e_ = -si, co
        f_ = -cx_in * si + cy_in * (1 - co) - up
        leg_t = leg.transform(leg.size, Image.AFFINE,
                              (a_, b_, c_, d_, e_, f_),
                              resample=Image.BILINEAR)
        out.alpha_composite(leg_t, (lg['x0'], lg['y_root']))
    return out


def walk_phase(items):
    """从动作列表里找第一个 walk 类动作，返回其 t；没有返回 None。"""
    for aid, t in items:
        if aid in WALK_AIDS:
            return t
    return None


def clear_cache():
    """换狐狸/换分辨率后清缓存（自检用）。"""
    _INFO_CACHE.clear()
