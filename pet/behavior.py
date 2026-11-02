# -*- coding: utf-8 -*-
"""桌宠行为状态机 —— 决定每一刻该播哪些动作。

纯逻辑、不依赖 Qt，可以单独跑自检（见 verify_behavior.py）。

动作分层规则（沿用美术侧 animations.json 的设计）：
    base  同一时刻只有一个（互斥），决定"在干什么"
    add   叠加在 base 上，可多个（尾巴摆 + 耳朵抖）
    face  覆盖在 base 上，用于表情附件切换（眨眼）

每个动作有**自己的播放进度**：眨眼 0.4s、呼吸 4s，若共用一个时间轴，
眨眼会跟着呼吸一起循环，所以必须各自计时。

用法：
    bh = Behavior(seed=1)
    bh.tick(dt)                       # 推进
    items = bh.items()                # [(aid, t_norm), ...]
    img, pose = AN.render_frame(spec, 0, items, size=256)
"""

import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, 'sim')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import anim as AN                                          # noqa: E402


def dur(aid):
    return AN.duration(aid)


class Behavior(object):
    """三层动作调度 + 清醒/瞌睡/睡眠状态机。

    doze_after: 无交互多少秒后开始犯困（0 = 永不犯困）。
    """

    BASE_IDLE = 'idle_breath'
    ADD_IDLE = 'idle_tail_sway'
    SLEEP_BASE = 'sleep'          # 播到它就是真的睡着了（常驻，不再随机触发）

    # 随机触发：动作 -> 平均间隔（秒）
    TICKS = {'blink': 3.6, 'idle_ear_twitch': 5.5}

    # 交互动作 -> (动作, 播几遍)
    INTERACT = {
        'pet': ('happy_wag', 1.0),
        'bounce': ('happy_bounce', 1.0),
        'tilt': ('tilt_head', 1.0),
        'nod': ('nod', 1.0),
        'stretch': ('stretch', 1.0),
        'feed': ('eat', 1.0),
        'drink': ('drink', 1.0),
        'howl': ('howl', 1.0),
        'bark': ('bark', 1.0),
        'sparkle': ('sparkle', 1.0),
    }

    def __init__(self, seed=None, doze_after=90.0):
        self.rng = random.Random(seed)
        self.t = 0.0
        self.doze_after = doze_after
        self.last_interact = 0.0

        self.base = self.BASE_IDLE      # 当前 base 动作
        self.base_el = 0.0              # 已播秒数
        self.base_until = None          # 播到多少秒结束（None = 一直播）
        self.base_queue = []            # 结束后依次播这些 [(aid, cycles)]
        self.base_fallback = self.BASE_IDLE

        self.adds = [(self.ADD_IDLE, 0.0)]      # 常驻在最后
        self.faces = []
        self._next = dict(self.TICKS)
        self.state = 'awake'                    # awake / drowsy / asleep
        self.log = []

    # ------------------------------------------------------------------
    # 驱动
    # ------------------------------------------------------------------
    def tick(self, dt):
        dt = max(dt, 0.0)
        self.t += dt

        # base
        self.base_el += dt
        if self.base_until is not None and self.base_el >= self.base_until:
            self._advance_base()

        # add / face：一次性动作播完就移除
        keep = []
        for aid, el in self.adds:
            el += dt
            if aid == self.ADD_IDLE or el < dur(aid):
                keep.append((aid, el))
        self.adds = keep
        keep = []
        for aid, el in self.faces:
            el += dt
            if el < dur(aid):
                keep.append((aid, el))
        self.faces = keep

        # 随机触发
        if self.state != 'asleep':
            for key in list(self._next):
                self._next[key] -= dt
                if self._next[key] <= 0:
                    self._next[key] = self.rng.expovariate(
                        1.0 / self.TICKS[key]) + self.TICKS[key] * 0.3
                    if key == 'blink':
                        if not any(a == key for a, _ in self.faces):
                            self.faces.append((key, 0.0))
                    else:
                        if not any(a == key for a, _ in self.adds):
                            self.adds.insert(0, (key, 0.0))

        # 犯困 → 睡
        if self.doze_after and self.state == 'awake' \
                and (self.t - self.last_interact) > self.doze_after:
            self._doze()

    def _advance_base(self):
        if self.base_queue:
            aid, cyc = self.base_queue.pop(0)
            self._set_base(aid, cyc)
            return
        self.base = self.base_fallback
        self.base_el = 0.0
        self.base_until = None
        self.base_queue = []
        self.base_fallback = self.BASE_IDLE
        if self.state == 'drowsy':
            self.state = 'asleep'

    def _set_base(self, aid, cycles=1.0):
        self.base = aid
        self.base_el = 0.0
        d = dur(aid)
        # cycles=None 且动作本身 loop → 常驻，一直播到被别的交互打断
        self.base_until = None if (cycles is None
                                   and AN.ACTIONS[aid].get('loop')) else d * cycles
        if aid == self.SLEEP_BASE:
            self.state = 'asleep'

    def _doze(self):
        """犯困：坐下 → 趴下 → 睡（链式）。"""
        self.state = 'drowsy'
        self.log.append(('%.1fs' % self.t, 'doze'))
        self.base_fallback = 'sit_idle'
        self.base_queue = [('lie_down', 1.0), ('sleep', None)]
        self._set_base('sit_down', 1.0)

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def interact(self, kind='pet'):
        """用户交互。返回是否触发了动作。"""
        self.last_interact = self.t
        if kind == 'drag_start':
            if self.state == 'asleep':
                self.wake()
            self._set_base('drag', None)
            self.base_fallback = 'drag'
            return True
        if kind == 'drag_end':
            self.base_fallback = self.BASE_IDLE
            self.base_queue = []
            self._set_base('drop', 1.0)
            return True

        if self.state in ('drowsy', 'asleep'):
            self.wake()
            return True

        act = self.INTERACT.get(kind)
        if not act:
            return False
        aid, cyc = act
        self.base_fallback = self.BASE_IDLE
        self.base_queue = []
        self._set_base(aid, cyc)
        self.log.append(('%.1fs' % self.t, kind))
        return True

    def wake(self):
        self.state = 'awake'
        self.base_fallback = self.BASE_IDLE
        self.base_queue = []
        self._set_base('wake_up', 1.0)

    # ------------------------------------------------------------------
    # 输出
    # ------------------------------------------------------------------
    def items(self):
        """给 render_frame 的动作列表，每个带自己的归一化进度。"""
        out = [(self.base, self.base_el / dur(self.base))]
        for aid, el in self.adds:
            out.append((aid, el / dur(aid)))
        for aid, el in self.faces:
            out.append((aid, el / dur(aid)))
        return out

    def status(self):
        return {'state': self.state, 'base': self.base,
                'adds': [a for a, _ in self.adds],
                'faces': [a for a, _ in self.faces],
                't': round(self.t, 2)}
