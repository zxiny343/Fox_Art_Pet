# -*- coding: utf-8 -*-
"""用 ctypes 枚举窗口，找到桌宠窗口的屏幕矩形（Add-Type 被安全策略拦了，改用 python）。"""
import ctypes
from ctypes import wintypes

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
            hits.append((hwnd, r.left, r.top, r.right - r.left, r.bottom - r.top))
    return True


u32.EnumWindows(EnumWindowsProc(cb), 0)
if not hits:
    print("NOT FOUND")
for h, x, y, w, ht in hits:
    print("hwnd=%d  x=%d y=%d  w=%d h=%d" % (h, x, y, w, ht))
