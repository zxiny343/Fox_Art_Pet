# -*- coding: utf-8 -*-
"""
动画播放器原型 v1（2026-11-02）
================================================================
读 01_Data/skeleton.json + animations.json，把 artmap 的成品图按骨骼姿态驱动。

设计前提（重要，决定了能做什么、不能做什么）
--------------------------------------------
美术交付的是**整张 1024 部件位图**（尾巴一张、耳朵一张、身体一张），
不是 Spine 那种分槽网格。所以：

- 能做：独立部件的**刚性变换**（尾绕根转、耳绕耳根转、整体缩放、附件切换）
- 难做：让一张位图内部弯曲（尾巴分段旋转、头部相对身体转动）需要切割，
        切割处会露缝，本模块用「重叠 + 羽化」压住
- 不做：网格蒙皮（LBS）。桌宠实际显示 128–256 px，收益小于成本

分层顺序沿用 artmap._compose：tail → core(+pattern) → ear_L → ear_R → eyes
"""

import json
import math
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artmap as AM                                    # noqa: E402
import legs as _LEG                                    # noqa: E402

DATA = AM.DATA
MASTER = AM.MASTER


def _spec_key(spec):
    """基因型摘要 clave，layers/legs 缓存共用。"""
    return spec.get('_key') or json.dumps(
        {k: spec[k] for k in ('coat', 'fur', 'tail', 'ear', 'eye_l', 'eye_r',
                              'pupil', 'pattern', 'special')},
        sort_keys=True, default=str)

with open(os.path.join(DATA, 'skeleton.json'), encoding='utf-8') as f:
    SKEL = json.load(f)
with open(os.path.join(DATA, 'animations.json'), encoding='utf-8') as f:
    ANIM = json.load(f)

BONES = {b['id']: b for b in SKEL['bones']}
ACTIONS = {a['id']: a for a in ANIM['actions']}
FPS = ANIM['fps']

# ---------------------------------------------------------------------------
# 1. 缓动与关键帧采样
# ---------------------------------------------------------------------------

def _ease(name, t):
    t = min(max(t, 0.0), 1.0)
    if name in (None, '', 'linear'):
        return t
    if name == 'easeInOutSine':
        return -(math.cos(math.pi * t) - 1) / 2.0
    if name == 'easeInSine':
        return 1 - math.cos(t * math.pi / 2)
    if name == 'easeOutSine':
        return math.sin(t * math.pi / 2)
    if name == 'easeInOutQuad':
        return 2 * t * t if t < 0.5 else 1 - ((-2 * t + 2) ** 2) / 2
    if name == 'easeOutQuad':
        return 1 - (1 - t) ** 2
    if name == 'easeInQuad':
        return t * t
    if name == 'easeOutBack':
        c1, c3 = 1.70158, 2.70158
        return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2
    if name == 'easeOutElastic':
        if t == 0 or t == 1:
            return t
        return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * (2 * math.pi / 3)) + 1
    return t          # 未知缓动退化成线性，不报错


def sample_keys(keys, t):
    """keys = [[t, value, easing?], ...]，t 归一化 0..1。"""
    if not keys:
        return 0.0
    if t <= keys[0][0]:
        return keys[0][1]
    if t >= keys[-1][0]:
        return keys[-1][1]
    for i in range(len(keys) - 1):
        t0, v0 = keys[i][0], keys[i][1]
        t1, v1 = keys[i + 1][0], keys[i + 1][1]
        if t0 <= t <= t1:
            span = t1 - t0
            if span <= 1e-9:
                return v1
            e = keys[i][2] if len(keys[i]) > 2 else 'linear'
            return v0 + (v1 - v0) * _ease(e, (t - t0) / span)
    return keys[-1][1]


# ---------------------------------------------------------------------------
# 2. 姿态：多层叠加
# ---------------------------------------------------------------------------

class Pose(object):
    """每根骨骼的各个通道值。bone -> channel -> value"""

    def __init__(self):
        self.b = {}

    def set(self, bone, ch, v):
        self.b.setdefault(bone, {})[ch] = v

    def add(self, bone, ch, v):
        self.b.setdefault(bone, {})
        self.b[bone][ch] = self.b[bone].get(ch, 0.0) + v

    def get(self, bone, ch, default=0.0):
        return self.b.get(bone, {}).get(ch, default)

    def rotate(self, bone):
        return self.get(bone, 'rotate')

    def __repr__(self):
        return 'Pose(%s)' % {k: {c: round(v, 2) for c, v in d.items()}
                             for k, d in self.b.items()}


def duration(aid):
    """动作时长（秒）。桌宠要用真实时间驱动，不能假设所有动作同长。"""
    return ACTIONS[aid].get('frames', 1) / float(FPS)


def _norm_t(aid, t):
    """归一化时间：loop 动作取模，一次性动作夹到 [0,1]。"""
    return (t % 1.0) if ACTIONS[aid].get('loop') else min(max(t, 0.0), 1.0)


def pose_at_multi(items):
    """按层合并若干动作的姿态，**每个动作用自己的局部时间**。

    items = [(action_id, t_norm), ...]，t_norm 已归一化到 0..1。
    base 独占（后写的覆盖）、add 叠加、face 最后写因此优先级最高。

    桌宠必须走这个入口：眨眼 0.4s、呼吸 4s，共用同一个 t 会让眨眼
    跟着呼吸一起循环，所以每个动作要各自的播放进度。
    """
    p = Pose()
    order = {'base': 0, 'add': 1, 'face': 2}
    for aid, t in sorted(items, key=lambda it: order.get(
            ACTIONS[it[0]].get('layer', 'base'), 1)):
        a = ACTIONS[aid]
        layer = a.get('layer', 'base')
        tt = _norm_t(aid, t)
        for ch in a.get('channels', []):
            v = sample_keys(ch.get('keys', []), tt)
            if layer == 'add':
                p.add(ch['bone'], ch['channel'], v)
            else:
                p.set(ch['bone'], ch['channel'], v)
    return p


def slots_at_multi(items):
    """附件切换（眨眼/闭眼），face 层优先。items 同 pose_at_multi。"""
    out = {}
    order = {'base': 0, 'add': 1, 'face': 2}
    for aid, t in sorted(items, key=lambda it: order.get(
            ACTIONS[it[0]].get('layer', 'base'), 1)):
        a = ACTIONS[aid]
        if a.get('layer') != 'face':
            continue
        tt = _norm_t(aid, t)
        for s in a.get('slots', []):
            ks = s.get('keys', [])
            if not ks:
                continue
            # 阶梯采样：取 <= t 的最后一个关键帧
            val = ks[0][1]
            for k in ks:
                if k[0] <= tt:
                    val = k[1]
            out[s['slot']] = val
    return out


def pose_at(action_ids, t):
    """兼容入口：所有动作共用同一个 t（出 GIF 时用，桌宠别用）。"""
    return pose_at_multi([(aid, t) for aid in action_ids])


def slots_at(action_ids, t):
    """兼容入口：所有动作共用同一个 t。"""
    return slots_at_multi([(aid, t) for aid in action_ids])


# ---------------------------------------------------------------------------
# 3. 几何工具
# ---------------------------------------------------------------------------

def rot_point(p, c, deg):
    r = math.radians(deg)
    dx, dy = p[0] - c[0], p[1] - c[1]
    co, si = math.cos(r), math.sin(r)
    return (c[0] + dx * co - dy * si, c[1] + dx * si + dy * co)


def _mask_layer(img, mask):
    """按 mask 抠出一层（mask 外 alpha 归零）。img 为 RGBA。"""
    a = np.asarray(img).copy()
    a[..., 3] = np.where(mask, a[..., 3], 0)
    return Image.fromarray(a)


def _rotate_layer(layer, pivot, deg):
    if abs(deg) < 1e-6:
        return layer
    return layer.rotate(deg, center=pivot, resample=Image.BICUBIC)


# ---------------------------------------------------------------------------
# 4. 尾巴：沿主轴分 3 段，链式刚性旋转
# ---------------------------------------------------------------------------
# 骨骼链 tail_root → tail_mid → tail_sub → tail_tip；
# tail_mid 与 tail_sub 起点重合（都是 (312,415)），所以合并成一段，共 3 段。

# 画布：向下扩 192px。
# 坐下 pelvis translateY=96、趴下/睡觉 =150，而母版内容底边在 y=927、
# 原 1024 画布只剩 96px 余量 → 不扩展的话趴下去会被切掉脚。
# 只向下扩，宽度不变，桌宠窗口按 1:1.1875 显示即可。
CANVAS_W = 1024
CANVAS_H = 1216
ASPECT = CANVAS_H / float(CANVAS_W)          # 1.1875

# root 是整只狐狸的根骨骼，整体旋转绕它
ROOT_PIVOT = tuple(BONES['root']['start'])    # (512, 928)

TAIL_ROOT = tuple(BONES['tail_root']['start'])


def _tail_axis():
    """尾巴主轴单位向量：根 → 尾尖。"""
    tip = BONES['tail_tip']['end']
    d = (tip[0] - TAIL_ROOT[0], tip[1] - TAIL_ROOT[1])
    n = math.hypot(*d) or 1.0
    return (d[0] / n, d[1] / n)


TAIL_U = _tail_axis()


def _tail_proj(yy, xx):
    """每个像素沿主轴的投影距离（用于分段）。"""
    return (xx - TAIL_ROOT[0]) * TAIL_U[0] + (yy - TAIL_ROOT[1]) * TAIL_U[1]


def _tail_splits():
    """三段的投影分界：root→mid、mid→sub末、之后。"""
    def pr(p):
        return (p[0] - TAIL_ROOT[0]) * TAIL_U[0] + (p[1] - TAIL_ROOT[1]) * TAIL_U[1]
    d1 = pr(BONES['tail_mid']['start'])
    d2 = pr(BONES['tail_sub']['end'])
    return [d1, d2]


_TAIL_CACHE = {}


def _tail_seg_masks(tail_name, work=1024):
    """缓存每个尾型的分段 mask（含 overlap，避免段间裂缝）。

    按工作分辨率缓存：桌宠只在 256/512 上跑，没必要每次算 1024 的。
    """
    key = (tail_name, work)
    if key in _TAIL_CACHE:
        return _TAIL_CACHE[key]
    p = os.path.join(MASTER, 'Tails', 'tail_%s.png' % tail_name)
    a = np.asarray(Image.open(p).convert('RGBA').split()[3])
    if work != 1024:
        a = np.asarray(Image.fromarray(a).resize((work, work), Image.NEAREST))
    solid = a > 8
    n = work
    yy, xx = np.mgrid[0:n, 0:n]
    k = work / 1024.0
    proj = ((xx - TAIL_ROOT[0] * k) * TAIL_U[0] +
            (yy - TAIL_ROOT[1] * k) * TAIL_U[1])
    s1, s2 = [v * k for v in _tail_splits()]
    ov = 8.0 * k
    masks = [
        solid & (proj < s1 + ov),
        solid & (proj >= s1 - ov) & (proj < s2 + ov),
        solid & (proj >= s2 - ov),
    ]
    _TAIL_CACHE[key] = (solid, masks)
    return _TAIL_CACHE[key]


def _rot_crop(layer, world, box_pad=6):
    """裁到内容 bbox 再转，转完贴回原位。

    全画布 1024² 转一次 60ms，尾巴内容只占几分之一，裁完能省 5–10 倍。
    rotate 不 expand，尺寸不变，所以贴回原 box 即可。
    """
    bb = layer.getbbox()
    if bb is None:
        return layer
    W, H = layer.size
    box = (max(0, bb[0] - box_pad), max(0, bb[1] - box_pad),
           min(W, bb[2] + box_pad), min(H, bb[3] + box_pad))
    sub = layer.crop(box)
    for pivot, ang in world:
        if abs(ang) < 1e-6:
            continue
        sub = sub.rotate(ang, center=(pivot[0] - box[0], pivot[1] - box[1]),
                         resample=Image.BICUBIC)
    out = Image.new('RGBA', layer.size, (0, 0, 0, 0))
    out.alpha_composite(sub, dest=(box[0], box[1]))
    return out


def _tail_chain(pose):
    """返回每步的 (pivot_world, angle)，pivot 已按链式推进到世界位置。"""
    steps = [
        (tuple(BONES['tail_root']['start']), pose.rotate('tail_root')),
        (tuple(BONES['tail_mid']['start']),
         pose.rotate('tail_mid') + pose.rotate('tail_sub')),
        (tuple(BONES['tail_tip']['start']), pose.rotate('tail_tip')),
    ]
    world, cur = [], [list(s[0]) for s in steps]
    for i, (pivot, ang) in enumerate(steps):
        world.append((tuple(cur[i]), ang))
        for j in range(i + 1, len(cur)):
            cur[j] = rot_point(cur[j], cur[i], ang)
    return world


def rig_tail(tail_img, tail_name, pose, work=1024):
    """尾巴按 3 段链式旋转（段 i 累积前 i+1 个关节的旋转）。"""
    _, masks = _tail_seg_masks(tail_name, work)
    world = _tail_chain(pose)
    k = work / 1024.0
    world = [((p[0] * k, p[1] * k), a) for p, a in world]

    out = Image.new('RGBA', tail_img.size, (0, 0, 0, 0))
    for i, m in enumerate(masks):
        layer = _mask_layer(tail_img, m)
        out.alpha_composite(_rot_crop(layer, world[:i + 1]))
    return out


# ---------------------------------------------------------------------------
# 5. 耳朵与身体
# ---------------------------------------------------------------------------

EAR_PIVOT = {'L': tuple(BONES['ear_l']['start']),
             'R': tuple(BONES['ear_r']['start'])}


def rig_ear(ear_img, side, pose, work=1024):
    pivot = EAR_PIVOT[side]
    deg = pose.rotate('ear_l' if side == 'L' else 'ear_r')
    if abs(deg) < 1e-6:
        return ear_img
    k = work / 1024.0
    return _rot_crop(ear_img, [((pivot[0] * k, pivot[1] * k), deg)])


PELVIS = tuple(BONES['pelvis']['start'])


def rig_core(core_img, pose):
    """身体呼吸：绕 pelvis 做 X/Y 缩放。

    头部本该绕 neck 单独转，但 core 是一整张位图（头身腿一体），
    切割会露缝 —— 原型阶段先不做，见模块 docstring 的「难做」说明。
    """
    sx, sy = pose.get('body', 'scaleX', 1.0), pose.get('body', 'scaleY', 1.0)
    if abs(sx - 1.0) < 1e-4 and abs(sy - 1.0) < 1e-4:
        return core_img
    w, h = core_img.size
    # 绕 pelvis 缩放：先平移到原点，缩放，再平移回去
    a, b, c = sx, 0.0, PELVIS[0] * (1 - sx)
    d, e, f = 0.0, sy, PELVIS[1] * (1 - sy)
    return core_img.transform((w, h), Image.AFFINE, (a, b, c, d, e, f),
                              resample=Image.BICUBIC)


# ---------------------------------------------------------------------------
# 6. 帧渲染
# ---------------------------------------------------------------------------

_LAYER_CACHE = {}
_LAYER_CACHE_ORDER = []


def get_layers(spec, work=512):
    """按 (基因型摘要, 工作分辨率) 缓存部件层。

    layers() 本身要 1.3s（换色 + 花纹），一只狐狸在一段动画里只做一次。
    """
    key = (_spec_key(spec), work)
    if key in _LAYER_CACHE:
        return _LAYER_CACHE[key]
    L = AM.layers(spec)
    if work != 1024:
        L = {k: (v.resize((work, work), Image.LANCZOS) if hasattr(v, 'resize')
                 else v) for k, v in L.items()}
    if len(_LAYER_CACHE) > 24:                      # 别无限涨
        _LAYER_CACHE.pop(_LAYER_CACHE_ORDER.pop(0))
    _LAYER_CACHE[key] = L
    _LAYER_CACHE_ORDER.append(key)
    return L


def _apply_root(canvas, pose, work):
    """整体变换：pelvis 位移 + root 旋转。

    骨骼层级里 pelvis 的子孙**包含四条腿**（hip→foot、shoulder→paw），
    所以 pelvis translate 的语义是「整只狐狸升降」而不是「躯干下沉」——
    坐下 +96、趴下/睡觉 +150、蹦跳 ±22.5。这是整体平移，不用切图就能做对。

    同时 root 旋转（drop 14°、roll_over 360°）也是整体旋转。
    两者都在放完眼睛之后做，这样眼耳尾一起跟着动。
    """
    k = work / float(CANVAS_W)
    dx = pose.get('pelvis', 'translateX', 0.0) * k
    dy = pose.get('pelvis', 'translateY', 0.0) * k
    rot = pose.get('root', 'rotate', 0.0)

    H = int(round(work * ASPECT))
    out = Image.new('RGBA', (work, H), (0, 0, 0, 0))
    out.alpha_composite(canvas, (0, 0))

    if abs(rot) < 0.05 and abs(dx) < 0.5 and abs(dy) < 0.5:
        return out

    cx, cy = ROOT_PIVOT[0] * k, ROOT_PIVOT[1] * k
    r = math.radians(rot)
    co, si = math.cos(r), math.sin(r)
    # PIL AFFINE: x' = a*x + b*y + c ; y' = d*x + e*y + f
    a, b = co, -si
    d, e = si, co
    c = cx - cx * co + cy * si + dx
    f = cy - cx * si - cy * co + dy
    return out.transform(out.size, Image.AFFINE, (a, b, c, d, e, f),
                         resample=Image.BICUBIC)


def render_frame(spec, t, actions, size=512, layers=None, work=None):
    """渲染一帧。

    actions 两种写法：
      - `['idle_breath', 'blink']` —— 所有动作共用 t（出 GIF 用）
      - `[('idle_breath', 0.31), ('blink', 0.5)]` —— 每个动作自己的
        归一化进度（桌宠用），见 pose_at_multi

    work = 变换发生的分辨率。桌宠只显示 256，在 1024 上做旋转是浪费
    （实测 0.6s/帧 → 512 上 0.15s、256 上 0.04s）。默认取 max(size, 256)。
    """
    work = work or max(size or 512, 256)
    if layers is None:
        layers = get_layers(spec, work)
    items = actions if (actions and isinstance(actions[0], (tuple, list))) \
        else [(a, t) for a in actions]
    pose = pose_at_multi(items)
    sl = slots_at_multi(items)

    canvas = Image.new('RGBA', (work, work), (0, 0, 0, 0))
    canvas.alpha_composite(rig_tail(layers['tail'], spec['tail'], pose, work))
    # core 层：walk 类动作时启用腿部 rig（腿画在 body_core 位图里无独立骨骼，
    # 原始 walk 的腿部通道被丢弃；这里把 4 条短腿切出来按四足步态摆动）
    core_layer = _scaled_core(layers['core'], pose, work)
    wt = _LEG.walk_phase(items)
    if wt is not None:
        core_layer = _LEG.rig_legs(core_layer, wt, _spec_key(spec), work)
    canvas.alpha_composite(core_layer)
    for side in ('L', 'R'):
        canvas.alpha_composite(rig_ear(layers['ear_' + side], side, pose, work))
    # 眼睛在工作分辨率上放：place_eyes_on 用 1024 锚点，这里按比例换算
    canvas = _place_eyes_scaled(canvas, spec, sl, work)
    # 不做 repair_pockets / clean_islands：那是为静态成品设计的，
    # 每帧跑会把动态边缘当成碎片抹掉，而且太慢。

    # 整体升降 / 整体旋转（坐下、趴下、睡觉、蹦跳、掉落）
    canvas = _apply_root(canvas, pose, work)

    if size and size != canvas.width:
        canvas = canvas.resize((size, int(round(size * ASPECT))),
                               Image.LANCZOS)
    return canvas, pose


def _scaled_core(core, pose, work):
    """body 呼吸缩放：绕 pelvis 做 X/Y 缩放（pivot 按工作分辨率换算）。"""
    sx, sy = pose.get('body', 'scaleX', 1.0), pose.get('body', 'scaleY', 1.0)
    if abs(sx - 1.0) < 1e-4 and abs(sy - 1.0) < 1e-4:
        return core
    k = work / 1024.0
    cx, cy = PELVIS[0] * k, PELVIS[1] * k
    w, h = core.size
    return core.transform((w, h), Image.AFFINE,
                          (sx, 0.0, cx * (1 - sx), 0.0, sy, cy * (1 - sy)),
                          resample=Image.BICUBIC)


def make_walk_action(src='walk', out='walk_fx', boost=2.6, bob_px=16.0):
    """程序化增强版 walk，解决「走路像滑行」。

    原始 walk 的大部分通道在腿骨上（hip/shoulder/foot/paw），而腿画在
    body_core 位图里没法单独摆 → 这些通道全部被丢弃；剩下的 body 起伏
    只有 ±3.5px@1024，缩到 168px 显示只剩 0.6px，等于静止贴图。

    这里把**能 rig 的通道**（body 位移/旋转、tail 全链）幅度放大 boost 倍，
    再叠加 pelvis 上下 bob（与 body bob 同相、每循环 4 个完整起伏，对应
    四足一步一沉的重心），生成新动作注册进 ACTIONS 并返回 id。
    head/hip/foot/shoulder/paw 通道直接丢弃（无 rig）。
    """
    s = ACTIONS[src]
    chs = []
    for c in s.get('channels', []):
        b, ch = c.get('bone'), c.get('channel')
        usable = (b == 'body' and ch in ('translateY', 'rotate')) \
            or (b and b.startswith('tail'))
        if not usable:
            continue
        ks = [[k[0], k[1] * boost] + list(k[2:]) for k in c.get('keys', [])]
        chs.append(dict(bone=b, channel=ch, keys=ks))
    n = 24
    keys = [[round(i / float(n), 4),
             round(bob_px * math.sin(4 * 2 * math.pi * i / float(n)), 3)]
            for i in range(n + 1)]                    # 4 周期/循环
    chs.append(dict(bone='pelvis', channel='translateY', keys=keys))
    act = dict(s)
    act.update(id=out, channels=chs, slots=[],
               note='程序化增强 walk：腿不可分，放大 body/tail 幅度 + pelvis bob')
    ACTIONS[out] = act
    return out


_EYE_CACHE = {}


def _place_eyes_scaled(canvas, spec, override, work):
    """把眼睛放上去，并按 (眼件组合, 分辨率) 缓存整层。

    眼睛在一帧里只有「睁 / 闭」两种状态，却占了整帧 1/3 的时间
    （place_eyes_on 写死 1024 锚点，低分辨率要先放大再缩回）。
    缓存后只有眨眼那一帧才真的重算。
    """
    import artmap as _AM
    ov = override or {}
    key = (spec['eye_l'], spec['eye_r'], spec.get('pupil'), spec['coat'],
           ov.get('eye_l'), ov.get('eye_r'), work)
    layer = _EYE_CACHE.get(key)
    if layer is None:
        big = Image.new('RGBA', (1024, 1024), (0, 0, 0, 0))
        big = _AM.place_eyes_on(big, spec, override=override)
        layer = big if work == 1024 else big.resize((work, work), Image.LANCZOS)
        if len(_EYE_CACHE) > 64:
            _EYE_CACHE.clear()
        _EYE_CACHE[key] = layer
    out = canvas.copy()
    out.alpha_composite(layer)
    return out


def to_gif(spec, actions, frames=60, size=256, path=None, fps=None):
    """出一段 GIF。frames 按 base 动作的时长取，默认 60 帧（2 秒 @30fps）。"""
    # 部件层必须与 work 同分辨率，否则 mask 与图层对不上
    work = max(size, 256)
    layers = get_layers(spec, work)
    imgs = []
    for i in range(frames):
        t = i / float(frames)
        img, _ = render_frame(spec, t, actions, size=size, layers=layers,
                              work=work)
        bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
        bg.alpha_composite(img)
        imgs.append(bg.convert('P', palette=Image.ADAPTIVE, colors=128))
    if path is None:
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'docs', 'anim-preview.gif')
    imgs[0].save(path, save_all=True, append_images=imgs[1:],
                 duration=int(1000.0 / (fps or FPS)), loop=0, optimize=True)
    return path
