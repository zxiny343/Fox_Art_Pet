# -*- coding: utf-8 -*-
"""v1.4 修单的视觉证据图。

产出两张图（都放 docs/）：
  1. fix-evidence-tails-v1.4.png
     A：8 种尾型的尾根观察区，把「母版轮廓内、组装后却透明」的像素染成红色
     B：normal / twin / nine 根部 2× 放大对照，看描边堆叠成的黑团与接缝线
  2. fix-evidence-ears-v1.4.png
     ear_small / ear_round / ear_large 在同一 1024 坐标下的真实体量对比

A 段判据与 check_tails_v13.py 完全一致，只是把结果画出来。
用法：E:/SoftWare/python3.10/python.exe sim/make_fix_evidence.py
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, '..', '_art_v1.3', 'delivery', 'Fox_Art')
sys.path.insert(0, os.path.join(ART, 'tools'))
import run_assemble as RA  # noqa: E402

DOCS = os.path.join(HERE, '..', 'docs')
TAILS = ['normal', 'twin', 'triple', 'quad', 'quint', 'nine', 'short', 'thin']
PAD = (150, 240, 620, 620)          # 尾根观察窗（比 socket 大一圈）
ZOOM = (325, 405, 525, 605)         # 放大窗：锚点 (425,505) 周围 200×200
BG = (252, 252, 253)


def _font(sz):
    for p in ('C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/msyhbd.ttc',
              'C:/Windows/Fonts/arial.ttf'):
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                pass
    return ImageFont.load_default()


F_T = _font(23)
F_S = _font(16)
F_XS = _font(13)

MASTER_PATH = os.path.join(ART, 'assets', 'master', 'Base',
                           'fox_base_blue_q4@1024.png')
MASTER = Image.open(MASTER_PATH).convert('RGBA')
MASTER_A = np.asarray(MASTER.split()[3]) > 8


def _white(img):
    """RGBA -> RGB 白底。直接 paste 会把透明区变黑，必须先 alpha_composite。"""
    bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
    bg.alpha_composite(img.convert('RGBA'))
    return bg.convert('RGB')


def tail_report():
    """逐尾型算缺口像素，返回 [(name, hole_px, img, hole_map, repair_px)]。"""
    out = []
    for t in TAILS:
        img, used = RA.assemble(coat='blue', tail=t, ear='large',
                                eye='round_blue', verbose=False)
        a = np.asarray(img.convert('RGBA'))
        # 严格判据：母版狐狸轮廓内、组装后却透明 = 真漏洞
        hole_map = MASTER_A & (a[..., 3] < 8)
        out.append((t, int(hole_map.sum()), img, hole_map,
                    used.get('pocketRepairPx', 0)))
    return out


def _card(sheet, dr, x, y, w, h, title, title_col=(20, 20, 24)):
    """画一张卡片：白底 + 1px 边框 + 顶部标签条。"""
    dr.rectangle([x, y, x + w - 1, y + h - 1], fill=(255, 255, 255),
                 outline=(198, 200, 208))
    dr.line([(x, y + 30), (x + w - 1, y + 30)], fill=(226, 228, 234))
    if title:
        dr.text((x + 8, y + 7), title, font=F_S, fill=title_col)


def sheet_tails(rows):
    gap = 14
    cw, ch = 420, 392
    W = cw * 4 + gap * 5
    bw = (W - gap * 4) // 3
    bh = int(bw * (ZOOM[3] - ZOOM[1]) / float(ZOOM[2] - ZOOM[0])) + 78
    head, bhead = 52, 46
    H = head + ch * 2 + gap + 20 + bhead + bh + 16
    sheet = Image.new('RGB', (W, H), BG)
    dr = ImageDraw.Draw(sheet)

    dr.text((gap + 2, 10), 'A · 尾根缺口 —— 母版轮廓内、组装后却透明的像素（红色标注）',
            font=F_T, fill=(20, 20, 24))
    dr.text((gap + 2, 38), '统一条件 coat=blue / ear=large / eye=round_blue；'
                           '红色整片 = 该性状在成品里是破的', font=F_XS,
            fill=(110, 110, 120))

    tw, th = cw - 14, int((cw - 14) * (PAD[3] - PAD[1]) / float(PAD[2] - PAD[0]))
    for i, (name, hole, img, hole_map, pr) in enumerate(rows):
        x = gap + (i % 4) * (cw + gap)
        y = head + (i // 4) * (ch + gap)
        ok = hole < 500
        mid = 500 <= hole < 5000
        _card(sheet, dr, x, y, cw, ch, 'tail_%s   %d px' % (name, hole),
              title_col=(30, 120, 60) if ok else
              ((160, 110, 10) if mid else (200, 30, 30)))
        rgb = np.asarray(_white(img)).copy()
        rgb[hole_map] = (232, 32, 32)          # 缺口染红
        tile = Image.fromarray(rgb).crop(PAD).resize((tw, th), Image.LANCZOS)
        sheet.paste(tile, (x + 7, y + 33))
        if ok:
            pass
        elif mid:
            dr.text((x + 8, y + 33 + th + 4), '轻微 · 记录即可，可顺手处理',
                    font=F_XS, fill=(160, 110, 10))
        else:
            dr.text((x + 8, y + 33 + th + 4), '↑ 必须修：这个性状现在不可用',
                    font=F_XS, fill=(200, 30, 30))

    y0 = head + ch * 2 + gap + 16
    dr.line([(gap, y0), (W - gap, y0)], fill=(214, 216, 224))
    dr.text((gap + 2, y0 + 8), 'B · 根部 2.8× 放大 —— 分支描边绕锚点 (425,505) 复制后'
                               '互相叠压，留下深色叠影与接缝线（normal 作干净基准）',
            font=F_T, fill=(20, 20, 24))

    notes = {'normal': '基准：根部干净，只有一条外轮廓',
             'twin': '2 分支：已见深色叠影 + 1 条接缝线',
             'nine': '9 分支：叠影与接缝最多，放大/动画时最易察觉'}
    for k, name in enumerate(('normal', 'twin', 'nine')):
        row = [r for r in rows if r[0] == name][0]
        x = gap + k * (bw + gap)
        y = y0 + bhead
        _card(sheet, dr, x, y, bw, bh, 'tail_%s' % name)
        tile = _white(row[2]).crop(ZOOM).resize(
            (bw - 12, bh - 66), Image.LANCZOS)
        sheet.paste(tile, (x + 6, y + 32))
        dr.text((x + 8, y + bh - 28), notes[name], font=F_XS,
                fill=(30, 120, 60) if name == 'normal' else (200, 30, 30))

    out = os.path.join(DOCS, 'fix-evidence-tails-v1.4.png')
    sheet.save(out)
    return out


def sheet_ears():
    names = [('ear_small_L', 'small / Ez0'), ('ear_round_L', 'round / Ez1'),
             ('ear_large_L', 'large / Ez2')]
    infos = []
    for n, _ in names:
        p = os.path.join(ART, 'assets', 'master', 'Ears', '%s.png' % n)
        im = Image.open(p).convert('RGBA')
        al = np.asarray(im.split()[3])
        bb = im.split()[3].point(lambda v: 255 if v > 8 else 0).getbbox()
        infos.append((n, im, bb, int((al > 8).sum())))
    l, t = min(i[2][0] for i in infos), min(i[2][1] for i in infos)
    r, b = max(i[2][2] for i in infos), max(i[2][3] for i in infos)
    box = (max(0, l - 40), max(0, t - 40), min(1024, r + 40), b + 40)
    cw, ch = box[2] - box[0], box[3] - box[1]
    col = max(cw + 20, 300)                 # 固定列宽，给文字留位置
    gap = 14
    W = col * 3 + gap * 4
    H = 66 + ch + 72
    sheet = Image.new('RGB', (W, H), BG)
    dr = ImageDraw.Draw(sheet)
    dr.text((gap + 2, 8), 'C · 耳型三件真实体量（同一 1024 画布，1:1 未缩放）',
            font=F_T, fill=(20, 20, 24))
    dr.text((gap + 2, 38), 'Ez 三档应满足 small < round < large；'
                           '实测 large 的内容比 small 还小 2.7 倍，且整体下沉 66px',
            font=F_XS, fill=(110, 110, 120))
    for i, (n, im, bb, px) in enumerate(infos):
        x = gap + i * (col + gap)
        y = 66
        _card(sheet, dr, x, y, col, ch + 62,
              n, title_col=(200, 30, 30) if n == 'ear_large_L' else (40, 40, 48))
        tile = _white(im).crop(box)
        px0 = x + (col - cw) // 2
        sheet.paste(tile, (px0, y + 33))
        bx = (bb[0] - box[0], bb[1] - box[1], bb[2] - box[0], bb[3] - box[1])
        dr.rectangle([px0 + bx[0], y + 33 + bx[1], px0 + bx[2], y + 33 + bx[3]],
                     outline=(232, 32, 32) if n == 'ear_large_L' else (60, 110, 200))
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        dr.text((x + 10, y + 36 + ch), '内容 %d×%d · %d px · topY=%d'
                % (w, h, px, bb[1]), font=F_XS, fill=(110, 110, 120))

    out = os.path.join(DOCS, 'fix-evidence-ears-v1.4.png')
    sheet.save(out)
    return out, infos


if __name__ == '__main__':
    rows = tail_report()
    print('%-8s %10s %10s' % ('tail', 'hole_px', 'repair_px'))
    for t, h, _, _, pr in rows:
        print('%-8s %10d %10d' % (t, h, pr))
    p1 = sheet_tails(rows)
    p2, infos = sheet_ears()
    print('\ntails ->', os.path.abspath(p1))
    print('ears  ->', os.path.abspath(p2))
    for n, _, bb, px in infos:
        print('  %-14s %3dx%-3d  %6d px  topY=%d'
              % (n, bb[2] - bb[0], bb[3] - bb[1], px, bb[1]))
