# -*- coding: utf-8 -*-
"""按 v1.2 图层顺序重建分层 PSD（尾巴在身体之下）。"""
import os
import sys

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fox_pipeline as fp
import run_assemble as ra

M = os.path.join(B, "assets", "master")
OUT = os.path.join(B, "assets", "source", "Fox_Base.psd")


def main():
    core, _ = ra.make_core("blue", "short", seam="socketfill")
    p_core = os.path.join(M, "Parts", "part_body_core_v12@1024.png")
    core.save(p_core)

    # build_psd: 列表中第一个位于最上层
    layers = [
        {"name": "08_Eye_R", "path": os.path.join(M, "Parts", "part_eye_R@1024.png")},
        {"name": "07_Eye_L", "path": os.path.join(M, "Parts", "part_eye_L@1024.png")},
        {"name": "06_Ear_R", "path": os.path.join(M, "Parts", "part_ear_R@1024.png")},
        {"name": "05_Ear_L", "path": os.path.join(M, "Parts", "part_ear_L@1024.png")},
        {"name": "04_Body_Core", "path": p_core},
        {"name": "03_Tail", "path": os.path.join(M, "Tails", "tail_normal.png")},
        {"name": "02_Tail_Base", "path": os.path.join(M, "Tails", "tail_base_blue@1024.png")},
        {"name": "01_Socket_Mask", "visible": False,
         "path": os.path.join(M, "Parts", "tail_socket_mask@1024.png")},
    ]
    fp.build_psd(layers, OUT)
    print("psd ->", OUT, os.path.getsize(OUT) // 1024, "KB")

    # 回读校验
    from psd_tools import PSDImage
    psd = PSDImage.open(OUT)
    print("layers(top->bottom):", [l.name for l in psd][::-1])


if __name__ == "__main__":
    main()
