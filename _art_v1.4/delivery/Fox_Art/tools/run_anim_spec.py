# -*- coding: utf-8 -*-
"""
阶段 4 · 骨骼树 + 动作库生成
--------------------------------------------------
产出：
  01_Data/skeleton.json    骨骼树（层级/坐标/长度/约束，坐标取自 v3.0 实测锚点）
  01_Data/animations.json  28 个动作，逐骨骼通道关键帧（30fps）
  09_Review/_skeleton_map.png  骨骼叠加示意图
"""
import os
import sys
import json
import math
import numpy as np
from PIL import Image, ImageDraw

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = os.path.join(B, "assets", "master")
DATA = os.path.join(B, "01_Data")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FPS = 30
A = {a["id"]: (a["x"], a["y"]) for a in
     json.load(open(os.path.join(DATA, "anchors.view34.json"), encoding="utf-8"))["anchors"]}

# ---------------- 骨骼树 ----------------
# (id, parent, 起点锚点, 终点锚点或长度, 说明)
SKELETON = [
    ("root",        None,   "root",           None,      "根节点，地面接触/位移基准"),
    ("pelvis",      "root", "pelvis",         None,      "身体旋转中心，后腿挂载"),
    ("body",        "pelvis", "pelvis",       "back_top","躯干，呼吸缩放骨"),
    ("neck",        "body", "neck",           None,      "头身唯一连接点"),
    ("head",        "neck", "neck",           "head_center", "头部旋转/微动"),
    ("ear_l",       "head", "ear_root_l",     [(478, 190)], "左耳根→耳尖"),
    ("ear_r",       "head", "ear_root_r",     [(800, 178)], "右耳根→耳尖"),
    ("muzzle",      "head", "muzzle",         None,      "鼻/嘴插槽挂载点"),
    ("tail_root",   "pelvis", "tail_root",    None,      "唯一尾巴旋转中心（所有尾型共用）"),
    ("tail_mid",    "tail_root", "tail_mid",  None,      "尾巴中段"),
    ("tail_sub",    "tail_mid", None,         [(250, 375)], "尾巴次段"),
    ("tail_tip",    "tail_sub", None,         "tail_tip", "尾巴末段"),
    ("hip_near",    "pelvis", "hip_near",     [(432, 780)], "近侧后腿大腿"),
    ("foot_hind_near", "hip_near", None,      "foot_hind_near", "近侧后脚"),
    ("hip_far",     "pelvis", "hip_far",      [(382, 775)], "远侧后腿大腿"),
    ("foot_hind_far", "hip_far", None,        "foot_hind_far", "远侧后脚"),
    ("shoulder_near", "body", "shoulder_near", [(700, 750)], "近侧前腿"),
    ("paw_front_near", "shoulder_near", None, "paw_front_near", "近侧前爪"),
    ("shoulder_far", "body", "shoulder_far",  [(648, 745)], "远侧前腿"),
    ("paw_front_far", "shoulder_far", None,   "paw_front_far", "远侧前爪"),
]

SLOTS = [
    ("eye_l",  "head", "eye_l",  "眼插槽 L"),
    ("eye_r",  "head", "eye_r",  "眼插槽 R"),
    ("brow_l", "head", None,     "眉插槽 L（锚点 brow_l 606,428）"),
    ("brow_r", "head", None,     "眉插槽 R（锚点 brow_r 778,408）"),
    ("mouth",  "muzzle", None,   "嘴插槽（锚点 mouth 736,578）"),
    ("blush",  "head", None,     "腮红叠加层"),
    ("tail",   "tail_root", None, "尾巴附件插槽（6 型尾）"),
    ("ear_l_att", "ear_l", None, "左耳附件插槽（5 型耳）"),
    ("ear_r_att", "ear_r", None, "右耳附件插槽（5 型耳）"),
]
EXTRA_PTS = {"brow_l": (606, 428), "brow_r": (778, 408), "mouth": (736, 578)}


def pt(v):
    if isinstance(v, str):
        return A[v]
    return tuple(v)


def build_skeleton():
    bones = []
    for bid, par, p0, p1, note in SKELETON:
        a = pt(p0) if p0 else None
        if a is None and par:
            a = next(b["end"] for b in bones if b["id"] == par)
        if p1 is None:
            b = a
            L = 0.0
        elif isinstance(p1, str):
            b = pt(p1)
        else:
            b = tuple(p1[0])
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        bones.append({"id": bid, "parent": par, "start": list(a), "end": list(b),
                      "length": round(L, 1), "restRotationDeg": round(ang, 2),
                      "note": note})
    slots = []
    for sid, bone, anc, note in SLOTS:
        p = pt(anc) if anc else EXTRA_PTS.get(sid, pt("head_center"))
        slots.append({"id": sid, "bone": bone, "anchor": list(p), "note": note})
    return bones, slots


# ---------------- 关键帧工具 ----------------
def sine(bone, ch, amp, cycles, base=0.0, phase=0.0, n=12, curve="easeInOutSine"):
    keys = []
    for i in range(n + 1):
        t = i / n
        v = base + amp * math.sin(2 * math.pi * (cycles * t + phase))
        keys.append([round(t, 4), round(v, 3), curve])
    return {"bone": bone, "channel": ch, "keys": keys}


def ramp(bone, ch, pts, curve="easeInOutQuad"):
    keys = []
    for item in pts:
        t, v = item[0], item[1]
        c = item[2] if len(item) > 2 else curve
        keys.append([round(t, 4), round(v, 3), c])
    return {"bone": bone, "channel": ch, "keys": keys}


def hold(bone, ch, v):
    return {"bone": bone, "channel": ch, "keys": [[0.0, v, "linear"]]}


def leg_cycle(amp, n=8):
    """四足交替：近前/远后 同相，远前/近后 反相。"""
    return [
        sine("hip_near", "rotate", amp, 1, phase=0.0, n=n),
        sine("foot_hind_near", "rotate", amp * 0.5, 1, phase=0.25, n=n),
        sine("hip_far", "rotate", amp, 1, phase=0.5, n=n),
        sine("foot_hind_far", "rotate", amp * 0.5, 1, phase=0.75, n=n),
        sine("shoulder_near", "rotate", amp * 0.8, 1, phase=0.5, n=n),
        sine("paw_front_near", "rotate", amp * 0.4, 1, phase=0.75, n=n),
        sine("shoulder_far", "rotate", amp * 0.8, 1, phase=0.0, n=n),
        sine("paw_front_far", "rotate", amp * 0.4, 1, phase=0.25, n=n),
    ]


def tail_wave(amp, cycles=1, n=12):
    return [
        sine("tail_root", "rotate", amp * 0.35, cycles, phase=0.0, n=n),
        sine("tail_mid", "rotate", amp * 0.7, cycles, phase=0.12, n=n),
        sine("tail_sub", "rotate", amp, cycles, phase=0.24, n=n),
        sine("tail_tip", "rotate", amp * 1.25, cycles, phase=0.36, n=n),
    ]


def breath(amp=0.02, cycles=1, n=12):
    return [
        sine("body", "scaleY", amp, cycles, base=1.0, n=n),
        sine("body", "scaleX", -amp * 0.5, cycles, base=1.0, n=n),
        sine("head", "translateY", 3, cycles, n=n),
    ]


# ---------------- 28 个动作 ----------------
def action(aid, zh, frames, loop, channels, slots=None, layer="base",
           priority=0, note=""):
    return {"id": aid, "nameZh": zh, "fps": FPS, "frames": frames,
            "durationSec": round(frames / float(FPS), 3), "loop": loop,
            "layer": layer, "priority": priority,
            "channels": channels, "slots": slots or [], "note": note}


def build_actions():
    out = []
    A_ = out.append

    # --- 待机系 ---
    A_(action("idle_breath", "呼吸待机", 120, True,
              breath(0.022, 2) + [sine("tail_sub", "rotate", 3, 2, n=12),
                                  sine("ear_l", "rotate", 1.5, 3, n=12),
                                  sine("ear_r", "rotate", 1.5, 3, phase=0.3, n=12)],
              note="默认待机；与 idle_tail_sway 可叠加"))
    A_(action("idle_tail_sway", "尾巴轻摆", 90, True, tail_wave(6, 2),
              layer="add", note="叠加在 idle_breath 上"))
    A_(action("idle_ear_twitch", "耳朵抖动", 24, False,
              [ramp("ear_l", "rotate", [[0, 0], [0.15, -9], [0.3, 6], [0.45, -4],
                                        [0.6, 0]]),
               ramp("ear_r", "rotate", [[0, 0], [0.2, 7], [0.4, -5], [0.6, 0]])],
              layer="add", priority=2, note="随机间隔触发的抽动"))
    A_(action("blink", "眨眼", 12, False,
              [hold("head", "rotate", 0)],
              slots=[{"slot": "eye_l", "keys": [[0.0, "eye_round_blue"],
                                                [0.35, "eye_closed"],
                                                [0.7, "eye_round_blue"]]},
                     {"slot": "eye_r", "keys": [[0.0, "eye_round_blue"],
                                                [0.35, "eye_closed"],
                                                [0.7, "eye_round_blue"]]}],
              layer="face", priority=5, note="附件切换，不是骨骼动画"))
    A_(action("idle_look_around", "左右张望", 150, True,
              [sine("head", "rotate", 7, 1, n=16),
               sine("head", "translateX", 6, 1, n=16),
               sine("ear_l", "rotate", 4, 1, phase=0.2, n=16),
               sine("ear_r", "rotate", 4, 1, phase=0.4, n=16)] +
              breath(0.018, 2),
              layer="base", note="待机变体"))

    # --- 移动系 ---
    A_(action("walk", "行走", 48, True,
              leg_cycle(14) + [sine("body", "translateY", 4, 2, n=12),
                               sine("body", "rotate", 2, 2, n=12),
                               sine("head", "rotate", -2, 2, n=12)] +
              tail_wave(7, 2)))
    A_(action("run", "奔跑", 24, True,
              leg_cycle(28) + [sine("body", "translateY", 9, 2, n=12),
                               sine("body", "rotate", 5, 2, n=12),
                               sine("pelvis", "translateY", -6, 2, n=12)] +
              tail_wave(12, 2)))
    A_(action("walk_fast", "快走", 36, True,
              leg_cycle(20) + [sine("body", "translateY", 6, 2, n=12),
                               sine("body", "rotate", 3, 2, n=12)] +
              tail_wave(9, 2)))
    A_(action("jump", "起跳", 30, False,
              [ramp("pelvis", "translateY", [[0, 0], [0.25, 26], [0.5, -60],
                                             [1.0, -90]], curve="linear"),
               ramp("body", "rotate", [[0, 0], [0.25, 8], [0.5, -12], [1.0, -16]]),
               ramp("paw_front_near", "rotate", [[0, 0], [0.3, -40], [1.0, -55]]),
               ramp("paw_front_far", "rotate", [[0, 0], [0.3, -35], [1.0, -50]]),
               ramp("foot_hind_near", "rotate", [[0, 0], [0.3, 35], [1.0, 48]]),
               ramp("foot_hind_far", "rotate", [[0, 0], [0.3, 30], [1.0, 42]])] +
              [ramp(b, "rotate", [[0, 0], [0.4, v], [1.0, v * 1.2]])
               for b, v in (("tail_root", -10), ("tail_mid", -18),
                            ("tail_sub", -22), ("tail_tip", -26))]))
    A_(action("land", "落地", 18, False,
              [ramp("pelvis", "translateY", [[0, -90], [0.4, 0, "easeInQuad"],
                                             [0.6, 16], [1.0, 0]]),
               ramp("body", "scaleY", [[0, 1.0], [0.6, 0.86], [1.0, 1.0]]),
               ramp("body", "scaleX", [[0, 1.0], [0.6, 1.12], [1.0, 1.0]]),
               ramp("foot_hind_near", "rotate", [[0, 48], [0.5, -6], [1.0, 0]]),
               ramp("foot_hind_far", "rotate", [[0, 42], [0.5, -5], [1.0, 0]])]))
    A_(action("fall", "下落", 30, True,
              [sine("body", "rotate", 6, 1, n=10),
               sine("paw_front_near", "rotate", 14, 1, n=10),
               sine("paw_front_far", "rotate", 12, 1, phase=0.3, n=10),
               sine("foot_hind_near", "rotate", -12, 1, n=10),
               sine("foot_hind_far", "rotate", -10, 1, phase=0.3, n=10)] +
              tail_wave(14, 1)))

    # --- 姿态切换 ---
    A_(action("sit_down", "坐下", 36, False,
              [ramp("pelvis", "translateY", [[0, 0], [1.0, 96]]),
               ramp("body", "rotate", [[0, 0], [1.0, 16]]),
               ramp("foot_hind_near", "rotate", [[0, 0], [1.0, 74]]),
               ramp("foot_hind_far", "rotate", [[0, 0], [1.0, 70]]),
               ramp("tail_root", "rotate", [[0, 0], [1.0, 22]])]))
    A_(action("sit_idle", "坐姿待机", 120, True,
              [hold("pelvis", "translateY", 96)] + breath(0.024, 2) +
              tail_wave(5, 2),
              note="承接 sit_down 的末态"))
    A_(action("stand_up", "起立", 36, False,
              [ramp("pelvis", "translateY", [[0, 96], [1.0, 0]]),
               ramp("body", "rotate", [[0, 16], [1.0, 0]]),
               ramp("foot_hind_near", "rotate", [[0, 74], [1.0, 0]]),
               ramp("foot_hind_far", "rotate", [[0, 70], [1.0, 0]])]))
    A_(action("lie_down", "趴下", 48, False,
              [ramp("pelvis", "translateY", [[0, 0], [1.0, 150]]),
               ramp("body", "rotate", [[0, 0], [1.0, -6]]),
               ramp("paw_front_near", "rotate", [[0, 0], [1.0, 82]]),
               ramp("paw_front_far", "rotate", [[0, 0], [1.0, 78]]),
               ramp("head", "translateY", [[0, 0], [1.0, 40]])]))
    A_(action("sleep", "睡觉", 240, True,
              [hold("pelvis", "translateY", 150)] +
              [sine("body", "scaleY", 0.035, 6, base=1.0, n=24),
               sine("body", "scaleX", -0.018, 6, base=1.0, n=24),
               sine("tail_sub", "rotate", 4, 3, n=24)],
              slots=[{"slot": "eye_l", "keys": [[0.0, "eye_closed"]]},
                     {"slot": "eye_r", "keys": [[0.0, "eye_closed"]]}],
              note="Z 字气泡为 UI 层，不进骨骼"))
    A_(action("wake_up", "醒来", 60, False,
              [ramp("body", "scaleY", [[0, 0.9], [0.4, 1.12], [1.0, 1.0]]),
               ramp("head", "rotate", [[0, 12], [0.5, -8], [1.0, 0]]),
               ramp("ear_l", "rotate", [[0, 20], [0.5, -10], [1.0, 0]]),
               ramp("ear_r", "rotate", [[0, 18], [0.5, -9], [1.0, 0]])],
              slots=[{"slot": "eye_l", "keys": [[0.0, "eye_closed"],
                                                [0.45, "eye_round_blue"]]},
                     {"slot": "eye_r", "keys": [[0.0, "eye_closed"],
                                                [0.45, "eye_round_blue"]]}]))
    A_(action("stretch", "伸懒腰", 72, False,
              [ramp("pelvis", "translateY", [[0, 0], [0.4, 40], [1.0, 0]]),
               ramp("body", "scaleX", [[0, 1.0], [0.45, 1.16], [1.0, 1.0]]),
               ramp("body", "scaleY", [[0, 1.0], [0.45, 0.88], [1.0, 1.0]]),
               ramp("paw_front_near", "rotate", [[0, 0], [0.45, -70], [1.0, 0]]),
               ramp("paw_front_far", "rotate", [[0, 0], [0.45, -64], [1.0, 0]]),
               ramp("head", "rotate", [[0, 0], [0.45, -14], [1.0, 0]])] +
              tail_wave(10, 1)))

    # --- 情绪表现 ---
    A_(action("happy_wag", "摇尾巴（开心）", 60, True, tail_wave(20, 3, n=16) +
              [sine("pelvis", "translateY", 3, 3, n=16),
               sine("ear_l", "rotate", 5, 3, n=16),
               sine("ear_r", "rotate", 5, 3, phase=0.2, n=16)]))
    A_(action("happy_bounce", "开心蹦跳", 48, True,
              [sine("pelvis", "translateY", -26, 2, n=12),
               sine("body", "scaleY", 0.05, 2, base=1.0, n=12),
               sine("body", "scaleX", -0.03, 2, base=1.0, n=12),
               sine("ear_l", "rotate", 8, 2, n=12),
               sine("ear_r", "rotate", 8, 2, phase=0.2, n=12)] +
              tail_wave(16, 2)))
    A_(action("nod", "点头", 24, False,
              [ramp("head", "rotate", [[0, 0], [0.3, 14], [0.6, -4], [1.0, 0]]),
               ramp("neck", "rotate", [[0, 0], [0.3, 5], [0.6, -2], [1.0, 0]])]))
    A_(action("shake_head", "摇头", 30, False,
              [ramp("head", "rotate", [[0, 0], [0.2, -16], [0.45, 14],
                                       [0.7, -9], [1.0, 0]]),
               ramp("ear_l", "rotate", [[0, 0], [0.3, -12], [0.7, 8], [1.0, 0]]),
               ramp("ear_r", "rotate", [[0, 0], [0.3, -10], [0.7, 7], [1.0, 0]])]))
    A_(action("tilt_head", "歪头（好奇）", 36, False,
              [ramp("head", "rotate", [[0, 0], [0.4, -18], [1.0, -14]]),
               ramp("ear_l", "rotate", [[0, 0], [0.4, -10], [1.0, -8]]),
               ramp("ear_r", "rotate", [[0, 0], [0.4, 12], [1.0, 9]])] +
              tail_wave(6, 1),
              slots=[{"slot": "mouth", "keys": [[0.0, "mouth_wavy"]]}]))
    A_(action("sad_droop", "垂头丧气", 120, True,
              [hold("head", "rotate", 14)] +
              [sine("head", "translateY", 3, 2, n=12),
               sine("ear_l", "rotate", -6, 2, n=12),
               sine("ear_r", "rotate", -6, 2, n=12),
               sine("tail_sub", "rotate", -4, 2, n=12)],
              slots=[{"slot": "eye_l", "keys": [[0.0, "eye_almond_blue"]]},
                     {"slot": "eye_r", "keys": [[0.0, "eye_almond_blue"]]},
                     {"slot": "mouth", "keys": [[0.0, "mouth_frown"]]}],
              note="尾/耳下垂 + 表情件切换"))
    A_(action("angry_puff", "生气炸毛", 60, True,
              [sine("body", "scaleX", 0.05, 4, base=1.04, n=16),
               sine("body", "scaleY", 0.04, 4, base=1.03, n=16),
               sine("pelvis", "translateX", 4, 4, n=16),
               sine("ear_l", "rotate", -8, 4, n=16),
               sine("ear_r", "rotate", -8, 4, n=16)] +
              tail_wave(14, 4, n=16),
              slots=[{"slot": "brow_l", "keys": [[0.0, "brow_angry_L"]]},
                     {"slot": "brow_r", "keys": [[0.0, "brow_angry_R"]]},
                     {"slot": "mouth", "keys": [[0.0, "mouth_frown"]]}]))

    # --- 互动/特殊 ---
    A_(action("scratch", "挠痒", 60, True,
              [sine("foot_hind_near", "rotate", 26, 4, n=16),
               sine("hip_near", "rotate", 8, 4, n=16),
               sine("head", "rotate", 5, 4, phase=0.3, n=16),
               sine("ear_l", "rotate", 6, 4, n=16)]))
    A_(action("roll_over", "打滚", 72, False,
              [ramp("root", "rotate", [[0, 0], [0.5, 180], [1.0, 360]], curve="linear"),
               ramp("pelvis", "translateY", [[0, 0], [0.5, 120], [1.0, 0]]),
               ramp("paw_front_near", "rotate", [[0, 0], [0.5, -60], [1.0, 0]]),
               ramp("paw_front_far", "rotate", [[0, 0], [0.5, -55], [1.0, 0]])]))
    A_(action("play_bow", "邀玩鞠躬", 48, False,
              [ramp("body", "rotate", [[0, 0], [0.4, 22], [1.0, 18]]),
               ramp("pelvis", "translateY", [[0, 0], [0.4, 60], [1.0, 52]]),
               ramp("paw_front_near", "rotate", [[0, 0], [0.4, 60], [1.0, 54]]),
               ramp("paw_front_far", "rotate", [[0, 0], [0.4, 56], [1.0, 50]])] +
              tail_wave(22, 2),
              slots=[{"slot": "mouth", "keys": [[0.0, "mouth_smile"]]}]))
    A_(action("howl", "嚎叫", 90, False,
              [ramp("head", "rotate", [[0, 0], [0.3, -22], [0.75, -20], [1.0, 0]]),
               ramp("neck", "rotate", [[0, 0], [0.3, -8], [0.75, -7], [1.0, 0]]),
               ramp("body", "scaleY", [[0, 1.0], [0.4, 1.06], [1.0, 1.0]])] +
              [ramp(b, "rotate", [[0, 0], [0.4, -v], [1.0, 0]])
               for b, v in (("tail_root", 12), ("tail_mid", 20),
                            ("tail_sub", 26), ("tail_tip", 30))],
              slots=[{"slot": "eye_l", "keys": [[0.0, "eye_closed"]]},
                     {"slot": "eye_r", "keys": [[0.0, "eye_closed"]]},
                     {"slot": "mouth", "keys": [[0.0, "mouth_closed"],
                                                [0.3, "mouth_open_o"]]}]))
    A_(action("bark", "吠叫", 30, False,
              [ramp("head", "rotate", [[0, 0], [0.25, -10], [0.5, 4], [1.0, 0]]),
               ramp("body", "scaleY", [[0, 1.0], [0.3, 0.94], [0.6, 1.04],
                                       [1.0, 1.0]])],
              slots=[{"slot": "mouth", "keys": [[0.0, "mouth_closed"],
                                                [0.3, "mouth_open_o"],
                                                [0.6, "mouth_closed"]]}]))
    A_(action("eat", "进食", 60, True,
              [sine("head", "rotate", 12, 3, n=12),
               sine("head", "translateY", 8, 3, n=12),
               sine("muzzle", "rotate", 6, 6, n=12)],
              slots=[{"slot": "eye_l", "keys": [[0.0, "eye_happy"]]},
                     {"slot": "eye_r", "keys": [[0.0, "eye_happy"]]},
                     {"slot": "mouth", "keys": [[0.0, "mouth_wavy"]]}]))
    A_(action("drink", "喝水", 60, True,
              [sine("head", "rotate", 16, 2, n=12),
               sine("head", "translateY", 14, 2, n=12),
               sine("muzzle", "translateY", 4, 4, n=12)],
              slots=[{"slot": "eye_l", "keys": [[0.0, "eye_closed"]]},
                     {"slot": "eye_r", "keys": [[0.0, "eye_closed"]]}]))
    A_(action("pet_response", "被抚摸", 90, True,
              [sine("head", "rotate", 6, 2, n=12),
               sine("head", "translateY", 4, 2, n=12),
               sine("ear_l", "rotate", -8, 2, n=12),
               sine("ear_r", "rotate", -8, 2, n=12)] +
              tail_wave(18, 3, n=12),
              slots=[{"slot": "eye_l", "keys": [[0.0, "eye_happy"]]},
                     {"slot": "eye_r", "keys": [[0.0, "eye_happy"]]},
                     {"slot": "blush", "keys": [[0.0, "blush"]]},
                     {"slot": "mouth", "keys": [[0.0, "mouth_smile"]]}],
              priority=3))
    A_(action("drag", "被拖拽", 30, True,
              [sine("body", "rotate", 10, 1, n=10),
               sine("pelvis", "translateY", 5, 1, n=10),
               sine("paw_front_near", "rotate", 12, 1, n=10),
               sine("paw_front_far", "rotate", 10, 1, phase=0.3, n=10)],
              slots=[{"slot": "eye_l", "keys": [[0.0, "eye_round_cyan"]]},
                     {"slot": "eye_r", "keys": [[0.0, "eye_round_cyan"]]}],
              priority=4, note="拖拽中循环播放"))
    A_(action("drop", "掉落", 24, False,
              [ramp("root", "rotate", [[0, 0], [0.6, 14], [1.0, 0]]),
               ramp("body", "scaleY", [[0, 1.08], [0.7, 0.9], [1.0, 1.0]]),
               ramp("body", "scaleX", [[0, 0.94], [0.7, 1.08], [1.0, 1.0]])]))
    A_(action("sparkle", "闪光（升级/变异）", 120, False,
              [ramp("body", "scaleY", [[0, 1.0], [0.3, 1.12], [0.6, 0.96],
                                        [1.0, 1.0]]),
               ramp("body", "scaleX", [[0, 1.0], [0.3, 0.9], [0.6, 1.06],
                                        [1.0, 1.0]]),
               ramp("head", "rotate", [[0, 0], [0.35, -10], [0.7, 6], [1.0, 0]])] +
              tail_wave(24, 2),
              slots=[{"slot": "eye_l", "keys": [[0.0, "eye_round_gold"]]},
                     {"slot": "eye_r", "keys": [[0.0, "eye_round_gold"]]}],
              priority=6, note="粒子/光效为 UI 层"))
    return out


# ---------------- 骨骼示意图 ----------------
def skeleton_map(bones, slots):
    im = Image.open(os.path.join(M, "Base", "fox_base_blue_q4@1024.png")).convert("RGBA")
    bg = Image.new("RGBA", (1024, 1024), (252, 252, 252, 255))
    bg.alpha_composite(im)
    ov = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for b in bones:
        if b["length"] < 1:
            continue
        d.line([tuple(b["start"]), tuple(b["end"])], fill=(230, 40, 40, 255), width=7)
    for b in bones:
        x, y = b["start"]
        r = 8 if b["id"] in ("root", "pelvis", "neck", "tail_root") else 5
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 210, 0, 255),
                  outline=(40, 40, 40, 255), width=2)
    fnt = None
    for b in bones:
        if b["id"] in ("root", "pelvis", "neck", "tail_root", "head",
                       "tail_tip", "muzzle"):
            d.text((b["start"][0] + 9, b["start"][1] - 6), b["id"],
                   fill=(20, 20, 20, 255))
    for s in slots:
        x, y = s["anchor"]
        d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(60, 160, 255, 255),
                  outline=(255, 255, 255, 255), width=2)
        if s["id"] in ("eye_l", "eye_r", "mouth", "brow_l", "brow_r"):
            d.text((x + 8, y - 6), s["id"], fill=(20, 60, 160, 255))
    out = Image.alpha_composite(bg, ov).convert("RGB")
    p = os.path.join(B, "09_Review", "_skeleton_map.png")
    out.save(p)
    return p


def main():
    bones, slots = build_skeleton()
    sk = {
        "schemaVersion": "1.0",
        "anchorSet": "v3.0-view34-quadruped",
        "canvas": 1024,
        "note": "坐标取自 01_Data/anchors.view34.json 的实测锚点；"
                "bone.start 为骨骼原点，restRotationDeg 为静止角度。",
        "bones": bones,
        "slots": slots,
        "twinTailOverride": {
            "rule": "tail_twin（S 级）在 tail_root 下分叉为 tail_root_a / tail_root_b，"
                    "各挂 3 段链；其余 5 种尾型共用同一条 4 段链，不新建根节点。",
            "extraBones": ["tail_root_a", "tail_mid_a", "tail_tip_a",
                           "tail_root_b", "tail_mid_b", "tail_tip_b"],
        },
    }
    json.dump(sk, open(os.path.join(DATA, "skeleton.json"), "w",
                       encoding="utf-8"), ensure_ascii=False, indent=1)
    acts = build_actions()
    an = {
        "schemaVersion": "1.0",
        "fps": FPS,
        "skeleton": "01_Data/skeleton.json",
        "units": {"rotate": "deg", "translate": "px @1024 母版",
                  "scale": "ratio(1.0=原始)", "time": "归一化 0..1"},
        "slotNaming": "眼 eye_<shape>_<color> / 眉 brow_<kind>_<L|R>_<coat> / "
                      "嘴 mouth_<kind>_<coat> / 腮红 blush",
        "layers": {"base": "基础姿态，独占", "add": "叠加层（可与 base 同时播放）",
                   "face": "表情层，优先级最高"},
        "actionCount": len(acts),
        "actions": acts,
    }
    json.dump(an, open(os.path.join(DATA, "animations.json"), "w",
                       encoding="utf-8"), ensure_ascii=False, indent=1)
    p = skeleton_map(bones, slots)
    print("skeleton.json: %d bones / %d slots" % (len(bones), len(slots)))
    print("animations.json: %d actions" % len(acts))
    for a in acts:
        ch = len(a["channels"])
        print("  %-16s %-14s %3df %s ch=%-2d slot=%d"
              % (a["id"], a["nameZh"], a["frames"],
                 "loop" if a["loop"] else "once", ch, len(a["slots"])))
    print("map ->", p)


if __name__ == "__main__":
    main()
