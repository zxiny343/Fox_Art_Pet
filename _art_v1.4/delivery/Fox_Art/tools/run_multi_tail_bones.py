# -*- coding: utf-8 -*-
"""P0 配套：多尾的骨骼定义 + 逐分支关键帧 + traits.json 元数据。

产出：
  01_Data/skeleton.json  → 追加 tailBranchTemplates（每尾型的分支骨链）
  01_Data/animations.json → 追加 tailVariants（逐分支 × 3 段的真实关键帧）
  01_Data/traits.json   → tail.values / boneSegments / specialHandling / incompatible

骨骼命名：tail_b{i}_{root|mid|sub|tip}；segmentsPerBranch = 3（mid/sub/tip）。
分支 i 的链 = 单尾链绕 tail_root(425,505) 旋转 branchAnglesDeg[i]，
并按与素材一致的比例缩短（外侧分支略短）。
关键帧：复用单尾同名通道曲线，加相位偏移 i*0.05（循环动作取模）与
振幅衰减（外侧分支振幅降至 90%）。
"""
import os
import json
import math

B = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(B, "01_Data")

ROOT = (425.0, 505.0)
# 单尾链（v1.2 skeleton.json 实测）
CHAIN = [(425, 505), (312, 415), (250, 375), (200, 320)]   # root, mid, sub, tip
S_LEN_K = 0.08          # 与 run_multi_tails.py 保持一致

BRANCHES = {
    "tail_triple": [-28, 0, 28],
    "tail_quad":   [-28, -14, 14, 28],
    "tail_quint":  [-28, -14, 0, 14, 28],
    "tail_nine":   [-56, -42, -28, -14, 0, 14, 28, 42, 56],
}
SEGMENTS = ["root", "mid", "sub", "tip"]
PHASE_STEP = 0.05
AMP_FALLOFF = 0.10          # |θ|=56° 时振幅 ×0.90


def rot(p, deg, s=1.0):
    """绕 ROOT 旋转 deg（屏幕坐标）并按 s 缩放。"""
    th = math.radians(deg)
    c, si = math.cos(th), math.sin(th)
    x, y = p[0] - ROOT[0], p[1] - ROOT[1]
    xr, yr = (c * x - si * y) * s, (si * x + c * y) * s
    return [round(ROOT[0] + xr, 1), round(ROOT[1] + yr, 1)]


def branch_bone_angles(tail_id):
    return BRANCHES[tail_id]


def build_skeleton_templates():
    """每尾型 → 分支骨定义（4 骨/分支：root/mid/sub/tip）。"""
    out = {}
    for tid, angles in BRANCHES.items():
        branches = []
        for i, a in enumerate(angles):
            t = abs(a) / 56.0
            s = 1.0 - S_LEN_K * t
            pts = [rot(p, a, s) for p in CHAIN]
            bones = []
            for j, seg in enumerate(SEGMENTS):
                parent = ("tail_root" if seg == "root"
                          else "tail_b%d_%s" % (i, SEGMENTS[j - 1]))
                bones.append({
                    "id": "tail_b%d_%s" % (i, seg),
                    "parent": parent,
                    "start": pts[j],
                    "end": pts[j],
                    "length": round(math.dist(pts[j],
                                              pts[min(j + 1, 3)]), 1),
                    "restRotationDeg": (round(a, 2) if seg == "root" else 0.0),
                })
            branches.append({"branchIndex": i, "branchAngleDeg": a,
                             "lengthScale": round(s, 4), "bones": bones})
        out[tid] = {
            "branchCount": len(angles),
            "branchAnglesDeg": angles,
            "segmentsPerBranch": 3,
            "rootAnchor": [425, 505],
            "branches": branches,
        }
    return out


def shift_keys(keys, phase, amp, loop, center):
    out = []
    for k in keys:
        t, v, curve = k[0], k[1], (k[2] if len(k) > 2 else "linear")
        t2 = (t + phase) % 1.0 if loop else min(1.0, t + phase)
        v2 = center + (v - center) * amp
        out.append([round(t2, 4), round(v2, 4), curve])
    out.sort(key=lambda x: x[0])
    # 去重（clamp 可能把多个 key 压到同一点）
    ded = []
    for k in out:
        if ded and abs(ded[-1][0] - k[0]) < 1e-6:
            continue
        ded.append(k)
    return ded


def build_animation_variants(anim):
    tail_bones = {"tail_root", "tail_mid", "tail_sub", "tail_tip"}
    variants = {}
    for tid, angles in BRANCHES.items():
        per_action = {}
        for act in anim["actions"]:
            chs = [c for c in act["channels"] if c["bone"] in tail_bones]
            if not chs:
                continue
            loop = bool(act.get("loop", False))
            frames = act.get("frames", 0)
            out_chs = []
            for i, a in enumerate(angles):
                phase = PHASE_STEP * i
                amp = 1.0 - AMP_FALLOFF * (abs(a) / 56.0)
                for c in chs:
                    seg = c["bone"].split("_", 1)[1]     # root/mid/sub/tip
                    center = 1.0 if c["channel"].startswith("scale") else 0.0
                    keys = shift_keys(c["keys"], phase, amp, loop, center)
                    out_chs.append({
                        "bone": "tail_b%d_%s" % (i, seg),
                        "channel": c["channel"],
                        "branchIndex": i,
                        "branchAngleDeg": a,
                        "phaseOffset": round(phase, 3),
                        "amplitudeScale": round(amp, 3),
                        "keys": keys,
                    })
            per_action[act["id"]] = {
                "fps": act.get("fps", anim.get("fps", 30)),
                "frames": frames,
                "loop": loop,
                "channels": out_chs,
            }
        variants[tid] = {
            "branchAnglesDeg": angles,
            "segmentsPerBranch": 3,
            "actions": per_action,
        }
    return {
        "note": "多尾型（v1.3 P0）逐分支骨骼关键帧。单尾动作中的 "
                "tail_root/mid/sub/tip 曲线按分支复制：命名 tail_b{i}_{root|mid|sub|tip}，"
                "分支 i 相位 +%.2f·周期，振幅随 |分叉角| 线性衰减至 %.2f。"
                "分叉角本身写在骨骼 restRotationDeg，不写进 keys。"
                % (PHASE_STEP, 1.0 - AMP_FALLOFF),
        "boneNaming": "tail_b{branchIndex}_{root|mid|sub|tip}",
        "rootAnchor": [425, 505],
        "phaseStepPerBranch": PHASE_STEP,
        "amplitudeFalloffAt56Deg": AMP_FALLOFF,
        "branches": ["tail_b{i}_root", "tail_b{i}_mid", "tail_b{i}_sub",
                     "tail_b{i}_tip"],
        "variants": variants,
    }


def update_traits():
    p = os.path.join(DATA, "traits.json")
    d = json.load(open(p, encoding="utf-8"))
    tail = next(c for c in d["categories"] if c["id"] == "tail")
    for tid in BRANCHES:
        if tid not in tail["values"]:
            tail["values"].append(tid)
        tail["boneSegments"][tid] = 3
        tail["specialHandling"][tid] = {
            "branchCount": len(BRANCHES[tid]),
            "segmentsPerBranch": 3,
            "branchAnglesDeg": BRANCHES[tid],
            "branchRootAnchor": [425, 505],
            "note": "程序化分叉（v1.3 P0）：以 tail_normal 基础形绕 tail_root 旋转复制，"
                    "外侧分支缩短≤8%/细化≤28%",
        }
    # 尾数维度互斥：多尾与短尾/卷尾概念冲突（沿用 tail_twin 的既有规则）
    multi = list(BRANCHES)
    for extra in ("tail_short", "tail_curl"):
        for m in multi:
            if not any(set(x["pair"]) == {m, extra}
                       for x in d["incompatible"]):
                d["incompatible"].append(
                    {"pair": [m, extra],
                     "reason": "tail-count trait conflicts with %s; "
                               "branch count is the visible evolution signal"
                               % extra})
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("traits.json 更新：tail.values =", tail["values"])


def main():
    update_traits()

    # skeleton.json
    p = os.path.join(DATA, "skeleton.json")
    sk = json.load(open(p, encoding="utf-8"))
    sk["tailBranchTemplates"] = build_skeleton_templates()
    json.dump(sk, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("skeleton.json 追加 tailBranchTemplates：%s"
          % ", ".join("%s(%d支)" % (k, v["branchCount"])
                      for k, v in sk["tailBranchTemplates"].items()))

    # animations.json
    p = os.path.join(DATA, "animations.json")
    anim = json.load(open(p, encoding="utf-8"))
    anim["tailVariants"] = build_animation_variants(anim)
    json.dump(anim, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n_act = sum(len(v["actions"]) for v in anim["tailVariants"]["variants"].values())
    n_key = sum(len(c["keys"])
                for v in anim["tailVariants"]["variants"].values()
                for a in v["actions"].values() for c in a["channels"])
    print("animations.json 追加 tailVariants：%d 尾型 × %d 动作实例，"
          "共 %d 条通道 / %d 个关键帧"
          % (len(anim["tailVariants"]["variants"]), n_act, n_key // 13, n_key))
    print("animations.json 体积 %.2f MB"
          % (os.path.getsize(p) / 1048576.0))


if __name__ == "__main__":
    main()
