# -*- coding: utf-8 -*-
"""桌宠自动散步 —— 纯逻辑状态机，不依赖 Qt（可单独自检）。

职责：决定「这一帧窗口水平移动多少像素、朝向哪边」。
与渲染/行为的关系由 app.py 编排：
    - 只在 awake、非拖拽、base 是 idle/walk 时允许走；
    - 移动只发生在水平方向（y 由用户拖放决定，散步不改变地面高度）；
    - 朝向 facing = +1 用原图，-1 水平镜像。

节奏：rest(4~14s) → 选目标 → walk(55~95 px/s) → 到达 → rest ...
交互时调 pause()，走一半被打断就回到 rest 重新计时。
"""

import random


class Wanderer(object):

    WALK = 'walk'
    REST = 'rest'

    def __init__(self, seed=None, enabled=True,
                 rest=(4.0, 14.0), speed=(55.0, 95.0), step=(120.0, 420.0),
                 min_step=60.0):
        self.rng = random.Random(seed)
        self.enabled = enabled
        self.rest_range = tuple(rest)
        self.speed_range = tuple(speed)
        self.step_range = tuple(step)
        self.min_step = min_step

        self.state = self.REST
        self.t = 0.0
        self.rest_left = self.rng.uniform(*self.rest_range)
        self.target_x = None
        self.speed = 0.0
        self.facing = 1              # +1 原图朝向 / -1 镜像
        self.pause_until = 0.0       # 交互后的暂停截止时刻
        self.trips = 0               # 完成的段数（自检/统计用）

    # ------------------------------------------------------------------
    def pause(self, sec=8.0):
        """交互（摸/喂/拖拽…）后暂停一段时间；走一半被打断就回到 rest。"""
        self.pause_until = self.t + max(0.0, sec)
        if self.state == self.WALK:
            self.state = self.REST
            self.rest_left = self.rng.uniform(*self.rest_range)
            self.target_x = None

    # ------------------------------------------------------------------
    def tick(self, dt, x, x_min, x_max):
        """推进一步。

        x      当前窗口左缘
        x_min/x_max 窗口左缘允许的范围（app 侧按屏幕可用区算好）
        返回 (dx, walking)。dx 为本帧水平位移（像素，可为 0）。
        """
        dt = max(0.0, dt)
        self.t += dt
        if not self.enabled:
            return 0.0, False

        if self.t < self.pause_until:
            return 0.0, False

        if self.state == self.REST:
            self.rest_left -= dt
            if self.rest_left <= 0:
                self._pick_target(x, x_min, x_max)
            return 0.0, False

        # WALK
        remain = self.target_x - x
        step = self.speed * dt
        if abs(remain) <= max(step, 2.0):
            self._arrive()
            return 0.0, False
        dx = (step if remain > 0 else -step)
        if dx > 0:
            dx = min(dx, x_max - x)
        else:
            dx = max(dx, x_min - x)
        if dx:
            self.facing = 1 if dx > 0 else -1
        return dx, True

    # ------------------------------------------------------------------
    def _pick_target(self, x, x_min, x_max):
        for _ in range(6):                      # 尝试几次找一个够远的目标
            dist = self.rng.uniform(*self.step_range)
            direction = self.rng.choice((-1.0, 1.0))
            tx = min(max(x + direction * dist, x_min), x_max)
            if abs(tx - x) >= self.min_step:
                break
        else:
            self._arrive()                      # 区域太窄：放弃这次
            return
        self.target_x = tx
        self.speed = self.rng.uniform(*self.speed_range)
        self.state = self.WALK

    def _arrive(self):
        self.state = self.REST
        self.rest_left = self.rng.uniform(*self.rest_range)
        self.target_x = None
        self.trips += 1

    # ------------------------------------------------------------------
    def status(self):
        return {'state': self.state, 'facing': self.facing,
                'target': self.target_x, 'trips': self.trips,
                'enabled': self.enabled}
