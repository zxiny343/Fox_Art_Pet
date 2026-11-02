# -*- coding: utf-8 -*-
"""把两张桌面截图按「桌宠窗口矩形」裁剪放大并并排对比，方便肉眼看清效果。"""
import ctypes
import os
from ctypes import wintypes

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
p1 = os.path.join(DOCS, "desktop-mvp-1.png")
p2 = os.path.join(DOCS, "desktop-mvp-2.png")


def pet_rect():
    u32 = ctypes.windll.user32
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    hits = []

    def cb(hwnd, lparam):
        n = u32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            u32.GetWindowTextW(hwnd, buf, n + 1)
            if "幻想小狐狸" in buf.value:
                r = wintypes.RECT()
                u32.GetWindowRect(hwnd, ctypes.byref(r))
                hits.append((r.left, r.top, r.right, r.bottom))
        return True

    u32.EnumWindows(EnumWindowsProc(cb), 0)
    return hits[0] if hits else None


a = Image.open(p1).convert("RGB")
b = Image.open(p2).convert("RGB")
W, H = a.size

r = pet_rect()
if r:
    x0, y0, x1, y1 = r
    pad = 30
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(W, x1 + pad), min(H, y1 + pad)
    print("pet window rect", r)
else:
    from PIL import ImageChops
    x0, y0, x1, y1 = ImageChops.difference(a, b).convert("L").getbbox()
    print("fallback diff bbox", (x0, y0, x1, y1))

ca, cb_ = a.crop((x0, y0, x1, y1)), b.crop((x0, y0, x1, y1))
zoom = 2
ca = ca.resize((ca.width * zoom, ca.height * zoom), Image.LANCZOS)
cb_ = cb_.resize((cb_.width * zoom, cb_.height * zoom), Image.LANCZOS)

gap, head = 18, 48
out = Image.new("RGB", (ca.width * 2 + gap * 3, ca.height + head + gap * 2), (30, 32, 38))
out.paste(ca, (gap, head))
out.paste(cb_, (ca.width + gap * 2, head))

dr = ImageDraw.Draw(out)
try:
    ft = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 24)
except Exception:
    ft = ImageFont.load_default()
dr.text((gap, 12), "T+0s", fill=(255, 205, 110), font=ft)
dr.text((ca.width + gap * 2, 12), "T+3s", fill=(255, 205, 110), font=ft)
dr.rectangle([gap, head, gap + ca.width - 1, head + ca.height - 1], outline=(90, 100, 120))
dr.rectangle([ca.width + gap * 2, head, ca.width * 2 + gap * 2 - 1, head + ca.height - 1],
             outline=(90, 100, 120))

op = os.path.join(DOCS, "desktop-shot-compare.png")
out.save(op)
print("saved", op, out.size)
