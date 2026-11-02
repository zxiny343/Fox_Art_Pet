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

DEFAULTS = {
    'x': None,              # None = 首次启动自动贴到屏幕右下
    'y': None,
    'scale': 1.0,           # 显示倍率（0.4 ~ 3.0）
    'base_size': 256,       # 渲染分辨率
    'always_top': True,
    'click_through': False,  # 鼠标穿透（穿透后不能拖拽，靠托盘菜单关）
    'geno': None,           # 当前这只狐狸的基因型；None = 随机抽一只
    'seed': 20261102,
    'doze_after': 90.0,     # 无交互多少秒后犯困；0 = 不犯困
    'fps': 30,
}


def load(path=None):
    path = path or DEFAULT_PATH
    cfg = dict(DEFAULTS)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            got = json.load(f)
        if isinstance(got, dict):
            for k, v in got.items():
                if k in DEFAULTS:
                    cfg[k] = v
    except (IOError, OSError, ValueError):
        pass
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
