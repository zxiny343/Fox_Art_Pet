# -*- coding: utf-8 -*-
"""桌宠配置持久化。

存 JSON，位置默认在 <项目>/pet_state.json（可被 --state 覆盖）。
坏了就退回默认值，不让一只坏配置导致桌宠起不来。
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, 'sim')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DEFAULT_PATH = os.path.join(ROOT, 'pet_state.json')

LEGACY_BASE_SIZE = 256    # v1.0 的默认显示宽度；v1.1 改为 168 并做一次性迁移

DEFAULTS = {
    'x': None,              # None = 首次启动自动贴到屏幕右下
    'y': None,
    'scale': 1.0,           # 显示倍率（0.4 ~ 3.0）
    'base_size': 168,       # 显示宽度（窗口高 = 宽 × 1.1875）
    'ssaa': 2.0,            # 超采样倍率：渲染分辨率 = 显示尺寸 × ssaa，
                            # 再 LANCZOS 缩回来。缩小后不糊的关键。
    'sharpen': True,        # 超采样缩回后轻度锐化，抵消 LANCZOS 的偏软
    'wander': True,         # 自动散步（水平漫步）
    'always_top': True,
    'click_through': False,  # 鼠标穿透（穿透后不能拖拽，靠托盘菜单关）
    'geno': None,           # 当前这只狐狸的基因型；None = 随机抽一只
    'seed': 20261102,
    'doze_after': 90.0,     # 无交互多少秒后犯困；0 = 不犯困
    # 24fps：桌宠的呼吸(4s)/摇尾(3s)/走路(1.6s) 都慢，24fps 看不出来；
    # 定 30fps 会把 2× 超采样逼到降档（实测 35ms/帧），清晰度反而更差。
    'fps': 24,
    'log': True,            # 把退出原因/降档等事件写 pet.log
}


def load(path=None):
    path = path or DEFAULT_PATH
    cfg = dict(DEFAULTS)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            got = json.load(f)
        if isinstance(got, dict):
            for k, v in got.items():
                if k not in DEFAULTS:
                    continue
                # ssaa 是运行时自适应参数，不落盘：一旦把降档结果写回去，
                # 下次启动就永久从低倍率开始（清晰度白给）。每次都按默认 2× 试。
                if k == 'ssaa':
                    continue
                cfg[k] = v
    except (IOError, OSError, ValueError):
        pass
    # 一次性迁移：老版本的 state 存着旧默认 base_size=256，用户并没有
    # 真正自定义过（代码里没有改它的入口），v1.1 起统一迁到新默认 168。
    if cfg.get('base_size') == LEGACY_BASE_SIZE:
        cfg['base_size'] = DEFAULTS['base_size']
    # 同理 fps：v1.0 存的是 30，v1.1 改 24（30fps 会把 2× 超采样逼到降档）。
    if cfg.get('fps') == 30:
        cfg['fps'] = DEFAULTS['fps']
    cfg['geno'] = norm_geno(cfg.get('geno'))
    return cfg, path


def save(cfg, path=None):
    path = path or DEFAULT_PATH
    tmp = path + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
        if os.path.isfile(path):
            os.remove(path)
        os.rename(tmp, path)
        return True
    except (IOError, OSError):
        return False


def norm_geno(g):
    """基因型归一化：JSON 往返会把 ('K','k') 变成 ['K','k']。

    phenotype() 对两者算出的表型一致，但别处可能有 `alleles == ('K','k')`
    这种写法，list 就会静默不等。存盘/读盘统一转成 tuple 最省心。
    """
    if not isinstance(g, dict):
        return None
    out = {}
    for k, v in g.items():
        if isinstance(v, (list, tuple)):
            out[k] = tuple(v)
        else:
            out[k] = v
    return out or None


def clamp_scale(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 1.0
    return max(0.4, min(3.0, v))


def clamp_ssaa(v):
    """超采样倍率：太小没意义，太大拖垮帧率。1.0 ~ 4.0。"""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 2.0
    return max(1.0, min(4.0, v))
