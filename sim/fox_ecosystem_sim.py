# -*- coding: utf-8 -*-
"""
幻想小狐狸 · 桌面生态系统 —— 离线数值模拟器
=============================================
依据 docs/fantasy-fox-design-v0.3.html 与 docs/requirements-confirmed-v0.3.md
中已固化的规则实现，用于在不启动桌宠的前提下，检验生态规则本身的长期行为。

不依赖第三方库，只做数值/逻辑层，不涉及渲染。

用法：
    python fox_ecosystem_sim.py --rounds 5 --years 5
    python fox_ecosystem_sim.py --rounds 5 --years 5 --variant tuned
"""

import argparse
import json
import math
import random
import statistics
import sys
from collections import defaultdict

# =============================================================================
# 一、基因位点定义（对应设计稿 §2.1 的 22 个位点；L/L 与 Tn/Tn 各拆为两个locus）
# =============================================================================

# type:
#   multi  —— 复等位 + 完全显性序列，phenotype = 显性序最靠前的等位基因
#   simple —— 两等位 + 完全显性
#   dosage —— 不完全显性：0/1/2 个显性等位基因 -> 三档表型
LOCUS_SPEC = {
    'A':   {'type': 'multi',  'dom': ['A+', 'As', 'Av', 'Ab']},
    'D':   {'type': 'simple', 'dom': ['D', 'd']},
    'W':   {'type': 'simple', 'dom': ['W', 'w']},
    'P':   {'type': 'multi',  'dom': ['PT', 'Ps', 'Pg', 'p']},
    'L1':  {'type': 'simple', 'dom': ['L', 'l']},
    'L2':  {'type': 'simple', 'dom': ['L', 'l']},
    'K':   {'type': 'simple', 'dom': ['K', 'k']},
    'Er':  {'type': 'multi',  'dom': ['ErP', 'ErR', 'Erf']},
    'Ez':  {'type': 'dosage', 'dom': ['Ez', 'ez']},
    'Tp':  {'type': 'multi',  'dom': ['TpD', 'TpW', 'tp']},
    'In':  {'type': 'simple', 'dom': ['InL', 'in']},
    'Tn1': {'type': 'simple', 'dom': ['T', 't']},
    'Tn2': {'type': 'simple', 'dom': ['T', 't']},
    'V':   {'type': 'simple', 'dom': ['V', 'v']},
    'Tl':  {'type': 'dosage', 'dom': ['Tl', 'tl']},
    'Tf':  {'type': 'simple', 'dom': ['Tf', 'tf']},
    'Tw':  {'type': 'multi',  'dom': ['TwW', 'TwK', 'tw']},
    'Ey':  {'type': 'multi',  'dom': ['EyG', 'EyC', 'EyB', 'EyV']},
    'Ef':  {'type': 'dosage', 'dom': ['Ef', 'ef']},
    'Ht':  {'type': 'simple', 'dom': ['Ht', 'ht']},
    'G':   {'type': 'simple', 'dom': ['G', 'g']},
    'St':  {'type': 'simple', 'dom': ['St', 'st']},
    'Ha':  {'type': 'simple', 'dom': ['Ha', 'ha']},
    'Fl':  {'type': 'simple', 'dom': ['Fl', 'fl']},
}
LOCUS_KEYS = list(LOCUS_SPEC.keys())

# 创始种群等位基因频率（文档中未定，属模拟器标定）。
# 设计原则：稀有突变（V/G/St/Ha/Fl/EyV/Av）在创始代频率为 0，
# 只能靠 §8.1 的突变机制产生 —— 这与设计稿「突变是新性状来源」的设定一致。
FOUNDER_FREQ = {
    'A':   {'A+': 0.45, 'As': 0.35, 'Ab': 0.20, 'Av': 0.00},
    'D':   {'D': 0.80, 'd': 0.20},
    'W':   {'W': 0.90, 'w': 0.10},
    'P':   {'PT': 0.35, 'Ps': 0.25, 'Pg': 0.20, 'p': 0.20},
    'L1':  {'L': 0.45, 'l': 0.55},
    'L2':  {'L': 0.45, 'l': 0.55},
    'K':   {'K': 0.30, 'k': 0.70},
    'Er':  {'ErP': 0.50, 'ErR': 0.30, 'Erf': 0.20},
    'Ez':  {'Ez': 0.50, 'ez': 0.50},
    'Tp':  {'TpD': 0.40, 'TpW': 0.30, 'tp': 0.30},
    'In':  {'InL': 0.60, 'in': 0.40},
    'Tn1': {'T': 0.18, 't': 0.82},
    'Tn2': {'T': 0.18, 't': 0.82},
    'V':   {'V': 0.00, 'v': 1.00},
    'Tl':  {'Tl': 0.50, 'tl': 0.50},
    'Tf':  {'Tf': 0.50, 'tf': 0.50},
    'Tw':  {'TwW': 0.35, 'TwK': 0.35, 'tw': 0.30},
    'Ey':  {'EyG': 0.50, 'EyC': 0.30, 'EyB': 0.20, 'EyV': 0.00},
    'Ef':  {'Ef': 0.50, 'ef': 0.50},
    'Ht':  {'Ht': 0.12, 'ht': 0.88},
    'G':   {'G': 0.00, 'g': 1.00},
    'St':  {'St': 0.00, 'st': 1.00},
    'Ha':  {'Ha': 0.00, 'ha': 1.00},
    'Fl':  {'Fl': 0.00, 'fl': 1.00},
}

def founder_freq(params):
    """创始/引入池的等位频率。允许参数里用 _freq_override 局部覆盖，
    用于「只调外观位点频率、不动生态参数」的对照实验。"""
    over = params.get('_freq_override') if params else None
    if not over:
        return FOUNDER_FREQ
    f = {k: dict(v) for k, v in FOUNDER_FREQ.items()}
    for k, v in over.items():
        f[k] = dict(v)
    return f


# 突变时可抽到的完整等位基因池（= 该位点全部等位基因）
def allele_pool(locus):
    return list(LOCUS_SPEC[locus]['dom'])

# =============================================================================
# 二、模拟参数
# =============================================================================

HOURS_PER_DAY = 24
DAYS_PER_YEAR = 24          # 1 生态年 = 24 游戏天（设计稿 §14.2）

BASE_PARAMS = {
    # ---- 时间 ----
    'Years': 5,
    # ---- 种群 ----
    'N_max': 20,             # 默认上限（设计稿 §7 默认）
    'Cap_mode': 'L_only',    # L_only / L_plus_slot / L_plus_reserve（推荐）
    'N_soft_frac': 1.0,      # 密度曲线的软目标 = 该比例 × 硬上限
    'Litter_reserve': 3,     # 剩余名额不足这么多时整窝不怀（Cap_mode=L_plus_reserve）
    'Founders': 10,
    'Founder_pool_max': False,   # 创始基因库杂合度最大化（改进项 B3）
    'Founder_sex_floor': 3,  # 保底 3♂3♀（B5）
    # ---- 密度制约（§9.1）----
    'k_curve': 3,
    'Fetus_counts': True,    # Q13A：胎儿计入 N_eff
    # ---- 繁殖（§5）----
    'Mature_hours': 96,      # 幼崽->成年（文档未定，模拟器标定 = 4 游戏天）
    'Min_breed_extra': 12,   # 成年后 12 游戏小时
    'Breed_interval': 72,
    'Gestation': 48,
    'Health_gate': 65,
    'Satiety_gate': 50,
    'Court_interval': 3.2,   # §9.4 文案：求偶尝试平均间隔 3.2 分钟（=3.2 游戏小时）
    'Court_tail_bonus': 0.03,   # 性选择强度：每多一条尾的求偶加权（§8.0 原文 +12%/尾）
    'Litter_min': 3,         # Q9C
    'Litter_max': 6,
    # ---- 幼崽夭折（§8.0）----
    'Juv_mort_lo': 0.25,
    'Juv_mort_hi': 0.35,
    'Founder_mort_halved': True,   # D3
    # ---- 近交（B2）----
    'Inbreed_threshold': 0.125,
    'Inbreed_abandon': 0.5,
    'Defect_per_r': {0.5: 0.25, 0.25: 0.18, 0.125: 0.10, 0.0625: 0.04},
    # ---- 突变（§8.1）----
    'Mut_rate': 0.015,
    # ---- 寿命 / 健康（文档未定，模拟器标定）----
    'Lifespan_mean_days': 60,
    'Lifespan_sd_days': 10,
    'Lifespan_min_days': 35,
    'Lifespan_max_days': 95,
    'Old_frac': 0.70,
    'Health_regen': 0.20,          # 每小时恢复
    'Disease_base': 0.0016,        # 每小时基础发病
    'Defect_disease_mult': 2.0,
    # ---- 迁徙（§16）----
    'Migrate_base': 0.00025,
    'Court_fail_trigger': 6,
    'Migrate_fit_margin': 0.05,     # 低于种群均值多少才算「不适应」（§16.2）
    'Immigration_enable': False,
    'Immigration_mode': 'gen',
    'Immigration_every_gen': 3,
    'Immigration_every_days': 10 * HOURS_PER_DAY,
    'Immigration_n': 1,
    'Immigration_pool': 'founder',
    'Immigration_sex': 'random',
    'Immigration_min_ratio': 0.70,   # 供给满足率低于此值不再有野外个体迁入（没食物的栖息地不会吸引移民）
    'Deep_dormancy_at': 3,           # 剩这么多只且全体休眠 -> 深度休眠，停衰老/停疾病（保底不全灭）
    # ---- 环境（本轮：食物充足 + 环境适宜）----
    'Env_light': 50,
    'Season_amp': 1.0,             # 季节影响强度
    'Food_abundant': True,
    # ---- v0.6 新增：可开关的生态机制（默认全部关闭 = 与 v0.5 行为一致）----
    'Juv_sel_strength': 0.0,       # G2 幼崽存活受「自身表型适应度」影响的强度
    'Food_mode': 'abundant',       # G3 abundant（无限） / pool（食物池 + 竞争取食）
    'Food_supply_per_day': 0.0,    # G3 pool 模式：每天投递的食物份数
    'Food_pool_init': 120.0,
    'Food_pool_cap': 2000.0,      # 必须 >= 日供给量，否则会把投递截断、各档塌成同一结果
    'Torpor_floor': 15.0,         # 休眠个体靠体内储备维持的饱食下限（保证「不饿死」）
    'Torpor_aging_factor': 0.10,  # 休眠时生理时钟的推进速度（代谢压低 -> 衰老减速）
    'Food_shift_year': None,       # 第几个生态年改变供给（模拟「玩家回来投喂」）
    'Food_shift_to': None,
    # 取食/代谢：净盈余仍为 +1.2/h（与 v0.5 的 abundant 行为等价），但把「掉膘门槛」
    # 定在供给满足率 70%（= 代谢/最大进食），低于承载力才会掉膘 -> 休眠。
    # 由此 pool 模式的承载力 N* = Food_supply_per_day / (intake_rate × 24) = supply / 96。
    'Food_intake_rate': 4.00,      # 每只每小时最大进食（份）
    'Food_metabolism': 2.80,       # 每只每小时基础代谢（份）
    'Env_light_season_amp': 0.0,   # G4 季节光照摆幅（冬暗夏亮）
    'Env_shift_year': None,        # H1 环境切换：第几个生态年换「壁纸」（光照突变）
    'Env_shift_to': None,
    'Blocked_cooldown_h': 0,       # G1 因名额被拦下后的重试冷却（小时）
    'Density_disease': 0.0,        # G5 密度相关疫病强度（0=关闭）
    # ---- 计算 ----
    'Seed0': 20261031,
}

# v0.4 候选改进参数 —— 由 sim/calibrate.py 与 sim/calibrate2.py 的对照搜索标定得出
# 六项改动的详情见 docs/ecology-tuning-proposal-v0.4.md
TUNED_PARAMS = dict(BASE_PARAMS)
TUNED_PARAMS.update({
    # B1 上限不再只靠 L 曲线软压制：受孕时校验剩余名额，防止分娩冲破上限
    'Cap_mode': 'L_plus_slot',
    # B2 有效种群放大：默认上限 20 -> 40（需求第七条允许用户自定，这里只改默认值）
    'N_max': 40,
    # B3 创始基因库杂合度最大化：10 只创始个体尽可能覆盖全部常见等位
    'Founder_pool_max': True,
    # B4 提高更替率：寿命缩短到 40 游戏天（约 1.7 个生态年），让空位真正轮转起来
    'Lifespan_mean_days': 40,
    'Lifespan_sd_days': 8,
    'Lifespan_min_days': 25,
    'Lifespan_max_days': 70,
    'Juv_mort_lo': 0.30,
    'Juv_mort_hi': 0.40,
    # B5 野外引入（gene flow）：每推进 3 个世代引入 1 只无亲缘个体
    'Immigration_enable': True,
    'Immigration_mode': 'gen',   # gen = 按世代；days = 按固定天数
    'Immigration_every_gen': 3,
    'Immigration_every_days': 10 * HOURS_PER_DAY,
    'Immigration_n': 1,
    'Immigration_pool': 'founder',   # founder / complement（异地互补基因库）
    'Immigration_sex': 'random',     # random / balance（补稀缺性别）
    # B6 突变供给：默认 1.5% -> 3%（仍在用户可调 0-10% 区间内）
    'Mut_rate': 0.030,
    'Inbreed_threshold': 0.125,
})
# v0.5 最终推荐参数 —— 在 E1-E5 全部采纳的基础上，由 sim/calibrate3.py
# 的两阶段网格搜索 + 5/10/20 生态年长期稳定性对照选出。
# 与 v0.4 的差异见 docs/ecology-tuning-proposal-v0.5.md
TUNED_V2_PARAMS = dict(BASE_PARAMS)
TUNED_V2_PARAMS.update({
    # C1 上限实施：种群在上限之下留出「整窝」余裕，宁可不怀，也不把已孕育的幼崽静默裁掉
    'Cap_mode': 'L_plus_reserve',
    'Litter_reserve': 6,          # 剩余名额不足 6 就不受孕 -> trimmed_pups 恒为 0
    'N_soft_frac': 1.0,
    # E1 硬上限 40（需求第七条允许用户自定，这里只改默认值）
    'N_max': 40,
    # B3 创始基因库杂合度最大化
    'Founder_pool_max': True,
    # C2 寿命 45 游戏天：整窝闸门上线后周转率不再依赖「死得多快」，
    #     45 天是 24 种子对照下「世代推进」与「近交累积」的拐点
    #     （42 天多 5% 世代但 5 年 F 高 0.03；50 天 F 反而更高）
    'Lifespan_mean_days': 45,
    'Lifespan_sd_days': 9,
    'Lifespan_min_days': 27,
    'Lifespan_max_days': 76,
    'Juv_mort_lo': 0.25,
    'Juv_mort_hi': 0.35,
    # C3 野外引入：异地互补基因库 + 补稀缺性别 + 按天推进，使 Nm ≈ 1.1 只/世代
    'Immigration_enable': True,
    'Immigration_mode': 'days',
    'Immigration_every_days': 14 * HOURS_PER_DAY,
    'Immigration_n': 1,
    'Immigration_pool': 'complement',
    'Immigration_sex': 'balance',
    # C5 迁徙强度回调到 0.00003/h：原 0.00025 会让「适应度低于均值」的个体几乎必然离场，
    #     5 年迁徙数比死亡数还多。回调后迁徙占离桌总数约 20%，死亡重新成为主要出口
    'Migrate_base': 0.00003,
    # C4 突变改为「每只幼崽独立判定」（真实突变发生在合子层面），默认 3%
    'Mut_rate': 0.030,
    'Inbreed_threshold': 0.125,
})

# v0.6 最终推荐参数 —— 在 v0.5（E1-E5）基础上，针对三个被 quantify 出来的缺陷修正：
#   D1 上限实施与密度曲线不自洽：n_soft 顶到硬上限，导致 95% 的妊娠被闸门空转拦下。
#      -> 改用 L_plus_fit（窝仔数适配剩余名额）+ n_soft = 0.9 × N_max，空转降到 8%
#   D2 幼崽存活完全不看幼崽自己的基因，切断了自然选择最主要的通路
#      -> Juv_sel_strength = 1.2
#   D3 环境恒定 -> 没有方向可选，只剩漂变与突变负荷（实测 sfit 恒为负）
#      -> Env_light_season_amp = 22，让季节给出周期性方向
# 详见 docs/ecology-tuning-proposal-v0.6.md
TUNED_V3_PARAMS = dict(BASE_PARAMS)
TUNED_V3_PARAMS.update({
    # D1 上限实施：越挤窝越小，但绝不先怀后裁（trimmed_pups 恒为 0）
    'Cap_mode': 'L_plus_fit',
    'N_soft_frac': 0.90,
    'Blocked_cooldown_h': 24,     # 被拦下后冷却，让机会在不同个体之间轮转
    # E1 硬上限 40（需求第七条允许用户自定，这里只改默认值）
    'N_max': 40,
    # B3 创始基因库杂合度最大化
    'Founder_pool_max': True,
    'Lifespan_mean_days': 45,
    'Lifespan_sd_days': 9,
    'Lifespan_min_days': 27,
    'Lifespan_max_days': 76,
    'Juv_mort_lo': 0.25,
    'Juv_mort_hi': 0.35,
    # D2 幼崽存活受自身表型影响
    'Juv_sel_strength': 1.2,
    # D3 季节光照摆幅（夏亮冬暗）
    'Env_light_season_amp': 22,
    # C3 野外引入：异地互补基因库 + 补稀缺性别
    'Immigration_enable': True,
    'Immigration_mode': 'days',
    'Immigration_every_days': 14 * HOURS_PER_DAY,
    'Immigration_n': 1,
    'Immigration_pool': 'complement',
    'Immigration_sex': 'balance',
    'Migrate_base': 0.00003,
    'Mut_rate': 0.030,
    'Inbreed_threshold': 0.125,
})

DEFAULT_PARAMS = BASE_PARAMS


# =============================================================================
# 三、表型换算（对应 §2.2 与 §2.1）
# =============================================================================

# 静态适应度的统一参考环境（秋 · 正午 · 基准光照）：用于跨时间段比较「基因层面是否变适应」
REF_ENV_BASE = {'light': 50, 'season': '秋', 'is_night': False, 'day': 0, 'hod': 12, 'year': 0}

# 毛色 -> 明度（0-100），用于「毛色 × 光照」隐蔽计算
COLOR_LUM = {
    '赤橙': 55, '奶油金': 80, '霜灰': 62, '淡银蓝': 78,
    '墨黑': 25, '雾霭蓝': 45, '幽夜紫': 48, '淡雾紫': 74, '雪绒白': 92,
}


def phenotype(geno):
    """把基因型翻译成表型字典（§2.1/§2.2 规则）。"""
    def get(locus):
        a, b = geno[locus]
        spec = LOCUS_SPEC[locus]
        if spec['type'] == 'dosage':
            dom = spec['dom'][0]
            n = (1 if a == dom else 0) + (1 if b == dom else 0)
            return n
        order = spec['dom']
        ia = order.index(a) if a in order else 99
        ib = order.index(b) if b in order else 99
        return order[min(ia, ib)] if min(ia, ib) < 99 else None

    A = get('A')
    D = get('D')
    W = get('W')
    P = get('P')
    if W == 'w':                      # ww 上位：完全掩盖 A/D/P
        base = '雪绒白'
    else:
        if A == 'A+':
            base = '赤橙' if D == 'D' else '奶油金'
        elif A == 'As':
            base = '霜灰' if D == 'D' else '淡银蓝'
        elif A == 'Av':
            base = '幽夜紫' if D == 'D' else '淡雾紫'
        else:                          # Ab
            base = '墨黑' if D == 'D' else '雾霭蓝'
    def count_dom(locus):
        """多基因累加位点（§2.1 L1/L2、Tn1/Tn2）：数「显性等位基因的个数」而不是「是否携带"""
        return (1 if geno[locus][0] == LOCUS_SPEC[locus]['dom'][0] else 0) + \
               (1 if geno[locus][1] == LOCUS_SPEC[locus]['dom'][0] else 0)

    tails = 1 + count_dom('Tn1') + count_dom('Tn2')
    if get('V') == 'V':
        tails = 9
    return {
        'color': base,
        'pattern': P,
        'ear': get('Er'),
        'ear_size': get('Ez'),
        'eye': get('Ey'),
        'eye_shape': get('Ef'),
        'hair_len': count_dom('L1') + count_dom('L2'),
        'curl': get('K') == 'K',
        'tails': tails,
        'hetero': (get('Ht') == 'Ht'),
        'glow': get('G') == 'G',
        'star': get('St') == 'St',
        'halo': get('Ha') == 'Ha',
        'flame': get('Fl') == 'Fl',
        # ---- 纯外观位点（不影响适应度，仅供美术映射层使用）----
        # Tl 不完全显性：2 显性=长 / 1=中 / 0=短（§2.1）
        'tail_len': (1 if geno['Tl'][0] == 'Tl' else 0) +
                    (1 if geno['Tl'][1] == 'Tl' else 0),
        'tail_fluff': get('Tf') == 'Tf',      # Tf 蓬 > tf 纤
        'ear_tip': get('Tp'),                 # 耳尖色：TpD 深 / TpW 白 / tp 同色
        'inner_ear': get('In') == 'InL',      # 内耳色：InL 浅 / in 深
        'tail_tip': get('Tw'),                # 尾尖色：TwW 宽白 / TwK 钩形 / tw 无
    }


def fitness(ind_pheno, env, params):
    """
    适应度（§8.0 环境 × 对照表）。返回一个接近 1.0 的乘子。
    sel = params.get('Selection_strength', 1.0) 作为总体强度系数。
    """
    sel = params.get('Selection_strength', 1.0)
    f = 1.0
    # 隐蔽：毛色明度与光照的错配 -> 受惊扰 / 暴露代价
    mismatch = abs(COLOR_LUM.get(ind_pheno['color'], 60) - env['light']) / 100.0
    f -= 0.18 * mismatch * sel
    # 季节 × 毛长：秋冬长毛有利，夏季不利
    ideal_len = 3 if env['season'] in ('秋', '冬') else 1
    f -= 0.05 * abs(ind_pheno['hair_len'] - ideal_len) / 4.0 * sel * params['Season_amp']
    # 垂耳：觅食效率轻度劣势
    if ind_pheno['ear'] == 'Erf':
        f -= 0.02 * sel
    # 星纹：维持成本微负
    if ind_pheno['star']:
        f -= 0.01 * sel
    # 光环：食物匮乏时代价高；本轮食物充足 -> 近似中性
    if ind_pheno['halo'] and not params['Food_abundant']:
        f -= 0.03 * sel
    # 发光：白天暴露、夜间加成
    if ind_pheno['glow']:
        f += (0.03 if env['is_night'] else -0.03) * sel
    # 焰尾：冬季保温有利，夏季代谢负担
    if ind_pheno['flame']:
        f += (0.02 if env['season'] in ('秋', '冬') else -0.02) * sel * params['Season_amp']
    return max(0.30, min(1.30, f))


def court_bonus(ind_pheno, bonus=0.03):
    """求偶层面的加成：多尾 +12%/尾（§8.0）；bonus 可调（性选择强度）。"""
    t = ind_pheno['tails']
    return 1.0 + bonus * max(0, t - 1)


# =============================================================================
# 四、个体与世界
# =============================================================================

class Fox:
    __slots__ = ('id', 'sex', 'geno', 'birth', 'death', 'cause', 'mother', 'father',
                 'gen', 'health', 'ceiling', 'satiety', 'phase', 'lifespan',
                 'last_birth', 'pregnant_until', 'litter', 'sire', 'court_fail',
                 'defect_load', 'F', 'juv_death_t', 'alive', 'exited', 'pheno',
                 'is_founder', 'source', 'ever_bred', 'torpor_flag', 'blocked_until', 'aging')

    def __init__(self, fid, sex, geno, birth_t, mother, father, gen, params, rng):
        self.id = fid
        self.sex = sex
        self.geno = geno
        self.birth = birth_t
        self.death = None
        self.cause = None
        self.mother = mother
        self.father = father
        self.gen = gen
        self.health = 100.0
        self.ceiling = 100.0
        self.satiety = 95.0
        self.phase = 'pup'
        ls = random_normal_trunc(params['Lifespan_mean_days'], params['Lifespan_sd_days'],
                                 params['Lifespan_min_days'], params['Lifespan_max_days'], rng)
        self.lifespan = ls * HOURS_PER_DAY
        self.last_birth = -10 ** 9
        self.pregnant_until = None
        self.litter = 0
        self.sire = None
        self.court_fail = 0
        self.defect_load = 0.0
        self.F = 0.0
        self.juv_death_t = None
        self.alive = True
        self.exited = None            # 'migrated' | None
        self.pheno = phenotype(geno)
        self.is_founder = False
        self.source = 'birth'
        self.ever_bred = False
        self.torpor_flag = False
        self.blocked_until = -1
        self.aging = 0.0          # 生理年龄（休眠时走得更慢）

    def age_h(self, t):
        return t - self.birth

    def is_adult(self, t, params):
        return self.age_h(t) >= params['Mature_hours']


def random_normal_trunc(mu, sd, lo, hi, rng):
    while True:
        v = rng.gauss(mu, sd)
        if lo <= v <= hi:
            return v


# =============================================================================
# 五、世界模型
# =============================================================================

class World:
    def __init__(self, params, seed):
        self.P = params
        self.rng = random.Random(seed)
        self.t = 0
        self.next_id = 1
        self.foxes = {}            # id -> Fox（含已死亡，用于谱系）
        self.alive_ids = set()
        self.pregnancies = []      # dict(mother, sire, due, litter, rolled_mut)
        self.events = []           # 关键事件日志
        self.mutations = []        # 突变记录
        self.kin_memo = {}
        self.daily = []            # 每日快照
        self.collapse_t = None
        self.migrated = []
        self.births = 0
        self.blocked_litters = 0      # 因名额不足被拦下的妊娠
        self.trimmed_pups = 0         # 因剩余名额不足被削减的仔数
        self.ever_parent = set()      # 一生中至少参与过一次成功繁殖的个体
        self.max_pop_seen = 0
        self.deaths_by_cause = defaultdict(int)
        self.litters = 0
        self.court_attempts = 0
        self.court_abandoned = 0
        self.immigrants = 0
        self.torpor_events = 0
        # G3 食物池
        self.food_pool = params.get('Food_pool_init', 0.0)
        self.food_shortage_ticks = 0
        # 繁殖事件明细：用于育种家方程（选择差 S / 遗传响应 R）诊断
        self.litter_log = []
        self.last_ratio = 1.0
        self.deep_dormancy = False
        self._init_founders()

    # ---------- 家谱 / 亲缘 ----------
    def _parent_ids(self, i):
        f = self.foxes.get(i)
        if f is None:
            return (None, None)
        return (f.mother, f.father)

    def kinship(self, a, b):
        """Wright 亲缘系数 f(a,b)；r = 2f/sqrt((1+Fa)(1+Fb))。"""
        if a is None or b is None:
            return 0.0
        if a == b:
            pa, pb = self._parent_ids(a)
            if pa is None or pb is None:
                return 0.5
            return 0.5 * (1.0 + self.kinship(pa, pb))
        fa = self.foxes.get(a)
        fb = self.foxes.get(b)
        if fa is None or fb is None:
            return 0.0
        # 递归必须展开「较年轻」的一方（gen 更大），否则会朝着无父母的根节点塌缩
        if fa.gen < fb.gen:
            a, b = b, a
            fa, fb = fb, fa
        key = (a, b)
        if key in self.kin_memo:
            return self.kin_memo[key]
        pa, pb = self._parent_ids(a)
        v = 0.0
        if pa is not None:
            v += 0.5 * self.kinship(pa, b)
        if pb is not None:
            v += 0.5 * self.kinship(pb, b)
        self.kin_memo[key] = v
        return v

    def relationship(self, a, b):
        f_ab = self.kinship(a, b)
        fa = self.kinship(a, a) - 0.5     # = 0.5*F_a
        fb = self.kinship(b, b) - 0.5
        denom = math.sqrt(max(1e-9, (1 + 2 * fa) * (1 + 2 * fb)))
        return 2 * f_ab / denom

    def F_of(self, i):
        pa, pb = self._parent_ids(i)
        if pa is None or pb is None:
            return 0.0
        return self.kinship(pa, pb)

    # ---------- 基因操作 ----------
    def make_gamete(self, geno):
        return {k: geno[k][self.rng.randrange(2)] for k in LOCUS_KEYS}

    def combine(self, ga, gb):
        return {k: (ga[k], gb[k]) for k in LOCUS_KEYS}

    def apply_mutation(self, geno):
        """
        §8.1 突变：随机抽一个位点，把随机一条染色体上的等位基因替换为池中另一个等位基因。
        稀有位点（V/G/St/Ha/Fl）权重略低，避免稀有性状泛滥。
        返回 (locus, old, new) 或 None（该位点只有一个等位基因时不发生）。
        """
        rare = ('V', 'G', 'St', 'Ha', 'Fl')
        weights = {k: (0.45 if k in rare else 1.0) for k in LOCUS_KEYS}
        loci = list(weights.keys())
        ws = [weights[l] for l in loci]
        locus = self.rng.choices(loci, weights=ws)[0]
        idx = self.rng.randrange(2)
        old = geno[locus][idx]
        pool = [x for x in allele_pool(locus) if x != old]
        if not pool:
            return None
        new = self.rng.choice(pool)
        geno[locus] = (new, geno[locus][1]) if idx == 0 else (geno[locus][0], new)
        return (locus, old, new)

    # ---------- 初始种群（B5）----------
    def _init_founders(self):
        P = self.P
        n = P['Founders']
        sexes = ['F'] * (n // 2) + ['M'] * (n - n // 2)
        self.rng.shuffle(sexes)
        # 保底性别平衡
        if min(sexes.count('F'), sexes.count('M')) < P['Founder_sex_floor']:
            sexes = ['F'] * P['Founder_sex_floor'] + ['M'] * P['Founder_sex_floor']
            while len(sexes) < n:
                sexes.append(self.rng.choice('FM'))
            self.rng.shuffle(sexes)

        FF = founder_freq(P)      # 本次建群使用的等位频率（可被 _freq_override 覆盖）

        # 10 对虚构始祖（不出现在桌面，但是谱系根）
        ghost_pairs = []
        for i in range(n):
            ghost_pairs.append((-1000 - i * 2, -1000 - i * 2 - 1))
            for gid in ghost_pairs[-1]:
                gf = Fox.__new__(Fox)
                gf.id = gid
                gf.mother = None
                gf.father = None
                gf.gen = 0
                gf.alive = False
                gf.sex = 'M' if gid % 2 == 0 else 'F'
                gf.geno = {k: (allele_pool(k)[0], allele_pool(k)[0]) for k in LOCUS_KEYS}
                gf.source = 'ghost'
                gf.cause = None
                gf.pheno = None
                gf.is_founder = False
                # 只用于亲缘递推，不参与统计
                self.foxes[gid] = gf

        # 创始基因库：两种模式
        #   off   —— 按频率独立抽样（遗传漂变的自然起点）
        #   max   —— 在保证边际频率的前提下最大化杂合度，让 10 只个体尽可能覆盖全部常见等位
        pool_max = P.get('Founder_pool_max', False)
        prebuilt = self._make_pool(n) if pool_max else None
        for i in range(n):
            geno = {}
            for k in LOCUS_KEYS:
                if pool_max:
                    geno[k] = (prebuilt[k][2 * i], prebuilt[k][2 * i + 1])
                else:
                    freq = FF[k]
                    alleles = list(freq.keys())
                    ws = [freq[a] for a in alleles]
                    geno[k] = tuple(self.rng.choices(alleles, weights=ws, k=2))
            # 每只幼崽的父母 = 自己专属的一对虚构始祖 -> 彼此 r = 0
            mo, fa = ghost_pairs[i]
            mo_id = mo if self.foxes[mo].sex == 'F' else fa
            fa_id = fa if mo_id == mo else mo
            f = Fox.__new__(Fox)
            Fox.__init__(f, self.next_id, sexes[i], geno, 0, mo_id, fa_id, 1, P, self.rng)
            self.next_id += 1
            f.is_founder = True
            f.phase = 'pup'
            # 幼崽期夭折（创始者保护：减半，D3）
            base = self.rng.uniform(P['Juv_mort_lo'], P['Juv_mort_hi'])
            if P['Founder_mort_halved']:
                base *= 0.5
            if self.rng.random() < base:
                f.juv_death_t = self.rng.randrange(1, P['Mature_hours'])
            self.foxes[f.id] = f
            self.alive_ids.add(f.id)

    def _make_pool(self, n):
        """为 n 只创始个体构建「杂合度最大化且边际频率不变」的等位基因表。"""
        FF = founder_freq(self.P)
        slots = {}
        for k in LOCUS_KEYS:
            freq = FF[k]
            alleles = [a for a in freq.keys()]
            nslot = 2 * n
            # 系统性配额：按频率分配整数名额，保证边际频率不被扭曲
            counts = {}
            assigned = 0
            for idx, a in enumerate(alleles):
                if idx == len(alleles) - 1:
                    counts[a] = nslot - assigned
                else:
                    counts[a] = int(round(freq[a] * nslot))
                    assigned += counts[a]
            pool = []
            for a in alleles:
                pool += [a] * max(0, counts[a])
            pool = pool[:nslot]
            while len(pool) < nslot:
                pool.append(alleles[0])
            # 洗牌后，尽量让每一对的两个等位互不相同
            for _ in range(200):
                self.rng.shuffle(pool)
                homo = [(j, pool[j] == pool[nslot - 1 - j]) for j in range(nslot)]
                # 交换成：把相同的一对拆开
                pairs = [(pool[2 * i], pool[2 * i + 1]) for i in range(n)]
                bad = [i for i, (x, y) in enumerate(pairs) if x == y]
                if not bad:
                    break
                # 把重复的第二个等位 genes 与另一对的等位互换
                for b in bad:
                    if pairs[b][0] == pairs[b][1]:
                        for j in range(len(pairs)):
                            if j != b and pairs[j][0] != pairs[b][1] and pairs[j][1] != pairs[b][1]:
                                pool[2 * b + 1], pool[2 * j] = pool[2 * j], pool[2 * b + 1]
                                break
            slots[k] = pool
        return slots

    # ---------- 环境 ----------
    def env(self):
        P = self.P
        day = self.t // HOURS_PER_DAY
        hour_of_day = self.t % HOURS_PER_DAY
        season_idx = (day // 6) % 4            # 每季 6 游戏天
        season = ['春', '夏', '秋', '冬'][season_idx]
        is_night = hour_of_day < 6 or hour_of_day >= 20
        # H1 环境切换：玩家换了一张亮度不同的壁纸 -> 光照发生一次阶跃（§14 环境绑定）。
        # 这是「肉眼可见的定向进化」最真实的来源：隐蔽色最优解被整体挪走。
        base_light = P['Env_light']
        sy = P.get('Env_shift_year')
        if sy is not None and day >= sy * DAYS_PER_YEAR:
            base_light = P.get('Env_shift_to', P['Env_light'])
        # G4：季节光照摆幅（夏亮冬暗）。默认 0，与环境光照恒定时完全等价。
        light = base_light + P.get('Env_light_season_amp', 0.0) * \
            {'春': 0.0, '夏': 1.0, '秋': -0.3, '冬': -1.0}[season]
        return {'day': day, 'hod': hour_of_day, 'season': season,
                'is_night': is_night, 'light': max(5.0, min(95.0, light)),
                'year': day // DAYS_PER_YEAR}

    # ---------- 食物池（G3）----------
    def food_step(self):
        """食物池：每天投递 -> 按需取食 -> 按适应度竞争分配。

        返回本 tick 的「供给满足率」 ratio（1.0 = 管饱，<1 = 短缺）。
        竞争规则：每只的取食权重 = 自身适应度 / 种群平均适应度，
        因此短缺时高适应度个体先吃饱，低适应度个体先掉膘 -> 休眠。
        """
        P = self.P
        if P.get('Food_mode', 'abundant') != 'pool':
            return 1.0
        pop = max(1, len(self.alive_ids))
        # 连续投递（每天一次会让当天出现「前半饱、后半饿」的锯齿，使平均供给率失真）
        supply = P.get('Food_supply_per_day', 0.0)
        fy = P.get('Food_shift_year')
        if fy is not None and self.t >= fy * DAYS_PER_YEAR * HOURS_PER_DAY:
            supply = P.get('Food_shift_to', supply)
        self.food_pool = min(P['Food_pool_cap'], self.food_pool + supply / HOURS_PER_DAY)
        demand = pop * P['Food_intake_rate']
        ratio = 1.0 if demand <= 0 else min(1.0, self.food_pool / demand)
        self.food_pool = max(0.0, self.food_pool - demand * ratio)
        self.food_shortage_ticks += (1 if ratio < 0.999 else 0)
        return ratio

    # ---------- 密度 ----------
    def rho_and_L(self):
        P = self.P
        alive = len(self.alive_ids)
        fetus = sum(p['litter'] for p in self.pregnancies) if P['Fetus_counts'] else 0
        n_eff = alive + fetus
        # 密度曲线对齐「软目标 N_soft」而不是硬上限：
        # 这样种群会均衡在硬上限之下留出配额余裕，完整窝才能落地，而不是把幼崽裁掉。
        n_soft = P['N_soft_frac'] * P['N_max']
        rho = min(1.0, n_eff / float(max(1.0, n_soft)))
        L = max(0.0, min(1.0, 1.0 - rho ** P['k_curve']))
        return n_eff, rho, L

    # =========================================================================
    # 主循环
    # =========================================================================
    def step(self):
        P = self.P
        rng = self.rng
        t = self.t
        e = self.env()
        _, rho, L = self.rho_and_L()
        # 食物供给：abundant 模式恒定为 1.0（与 v0.5 行为一致）；pool 模式按池子算
        if P.get('Food_mode', 'abundant') == 'pool':
            ratio = self.food_step()
            food_competitive = True
        else:
            ratio = 1.0 if P['Food_abundant'] else 0.0
            food_competitive = False
        self.last_ratio = ratio
        # 深度休眠：种群凋零到最后几只、且全部处于休眠时，抱团过冬 —— 停衰老、停疾病。
        # 目的是守住「玩家长期不投喂回来也不会发现狐狸全没了」这条产品底线。
        n_alive = len(self.alive_ids)
        self.deep_dormancy = (P.get('Deep_dormancy_at', 0) > 0 and 0 < n_alive <= P['Deep_dormancy_at']
                              and all(self.foxes[i].torpor_flag for i in self.alive_ids))

        # ---------- 1. 出生 ----------
        still = []
        for p in self.pregnancies:
            if p['due'] <= t:
                self._deliver(p, e)
            else:
                still.append(p)
        self.pregnancies = still

        # ---------- 2. 个体更新 ----------
        fits = [fitness(self.foxes[i].pheno, e, P) for i in self.alive_ids]
        mean_fit = statistics.mean(fits) if fits else 1.0
        for fid in list(self.alive_ids):
            f = self.foxes[fid]
            # 幼崽夭折执行
            if f.phase == 'pup' and f.juv_death_t is not None and (t - f.birth) >= f.juv_death_t:
                self._kill(f, '幼崽夭折', t)
                continue
            # 生理时钟：休眠时代谢压低，衰老也走得更慢（真实休眠动物的寿命消耗远低于活跃期）
            # 本 tick 刚出生的个体不推进，保证 aging 与 v0.5 的 age_h(t) 逐小时一致
            if f.birth < t and not self.deep_dormancy:
                f.aging += P.get('Torpor_aging_factor', 0.10) if f.torpor_flag else 1.0
            # 成长
            if f.phase == 'pup' and f.aging >= P['Mature_hours']:
                f.phase = 'adult'
                f.juv_death_t = None
            # 饱食：取食量 − 代谢。取食量受「当日供给满足率 × 个体取食竞争力」调制，
            # 竞争力 = 自身适应度 / 种群均值 —— 短缺时高适应度个体先吃饱（G3）。
            fit_h = fitness(f.pheno, e, P)
            w_i = clamp(fit_h / max(0.2, mean_fit), 0.4, 1.6) if food_competitive else 1.0
            intake = P['Food_intake_rate'] * ratio * w_i
            metab = P['Food_metabolism'] * (0.35 if f.torpor_flag else 1.0)
            f.satiety = clamp(f.satiety + intake - metab, 0.0, 100.0)
            # 休眠维持：进入休眠后靠体内脂肪储备，饱食度不再继续掉到 0 —— §15「不会饿死」
            if f.torpor_flag and f.satiety < P.get('Torpor_floor', 15.0):
                f.satiety = P.get('Torpor_floor', 15.0)
            if f.satiety < 25 and not f.torpor_flag:
                f.torpor_flag = True
                self.torpor_events += 1
            elif f.satiety >= 60:
                f.torpor_flag = False
            # 健康：老化
            old_start = P['Old_frac'] * f.lifespan
            if f.aging > old_start:
                prog = (f.aging - old_start) / max(1.0, f.lifespan - old_start)
                f.ceiling = max(8.0, 100.0 - 92.0 * prog)
                if f.health > f.ceiling:
                    f.health = f.ceiling
            else:
                if f.health < f.ceiling and f.satiety > 60:
                    f.health = min(f.ceiling, f.health + P['Health_regen'])
                # 休眠期间靠储备维持，健康不再被饥饿侵蚀 —— §15「不投喂也不会饿死」
                if not f.torpor_flag:
                    f.health -= 0.02 * (100 - min(100, f.satiety)) / 100.0
                if f.health > f.ceiling:
                    f.health = f.ceiling
            # 疾病（G5：密度越高传播越快）
            fit = fit_h
            disease_p = P['Disease_base'] * ((1 - f.health / 100.0) ** 2) * \
                (1 + P['Defect_disease_mult'] * f.defect_load) / max(0.4, fit) * \
                (1.0 + P.get('Density_disease', 0.0) * rho)
            if not self.deep_dormancy and rng.random() < disease_p:
                self._kill(f, '疾病', t)
                continue
            # 衰老终点
            if f.aging >= f.lifespan:
                self._kill(f, '衰老', t)
                continue
            # 迁徙（§16）—— 与死亡竞争，谁先到算谁
            if f.phase == 'adult':
                mig = P['Migrate_base']
                if f.court_fail >= P['Court_fail_trigger']:
                    mig *= 12.0
                if f.satiety < 40:
                    mig *= 6.0
                if f.health < P['Health_gate'] * 0.8:
                    mig *= 4.0
                # 适应度显著低于「种群均值」才算不适应（§16.2 原文）
                if mean_fit > 0 and fit < mean_fit - P.get('Migrate_fit_margin', 0.05):
                    mig *= 3.0
                if rng.random() < mig:
                    f.alive = False
                    f.exited = 'migrated'
                    f.death = t
                    f.cause = '迁徙'
                    self.alive_ids.discard(fid)
                    self.migrated.append(fid)
                    self.events.append({'t': t, 'type': 'migrate', 'id': fid})
                    continue

        # ---------- 3. 繁殖 ----------
        adults_F = [self.foxes[i] for i in self.alive_ids if self.foxes[i].sex == 'F'
                    and self.foxes[i].phase == 'adult']
        adults_M = [self.foxes[i] for i in self.alive_ids if self.foxes[i].sex == 'M'
                    and self.foxes[i].phase == 'adult']
        _, rho2, L2 = self.rho_and_L()

        for fem in adults_F:
            if not fem.alive or fem.pregnant_until is not None:
                continue
            age = f.aging
            if age < P['Mature_hours'] + P['Min_breed_extra']:
                continue
            if t - fem.last_birth < P['Breed_interval']:
                continue
            if t < fem.blocked_until:                 # G1：上次因名额被拦，冷却期内不再空转重试
                continue
            if fem.health < P['Health_gate'] or fem.satiety < P['Satiety_gate']:
                continue
            if not adults_M:
                continue
            # P配对 = Base × f(年龄) × f(健康) × f(饱食) × f(季节) × L(ρ) × f(配偶可得性)
            p_base = 1.0 / P['Court_interval']
            f_age = 1.0 if f.aging < P['Old_frac'] * fem.lifespan else 0.35
            f_health = clamp((fem.health - P['Health_gate']) / (100 - P['Health_gate']), 0.05, 1.0)
            f_satiety = clamp((fem.satiety - P['Satiety_gate']) / (100 - P['Satiety_gate']), 0.0, 1.0)
            season_mult = {'春': 1.15, '夏': 0.95, '秋': 1.0, '冬': 0.80}[e['season']]
            mate_avail = clamp(len(adults_M) / 3.0, 0.0, 1.0)     # §9.2 配偶可得性
            fit_mult = clamp(fitness(fem.pheno, e, P), 0.4, 1.3)
            p_pair = p_base * f_age * (0.4 + 0.6 * f_health) * (0.5 + 0.5 * f_satiety) \
                * season_mult * L2 * mate_avail * fit_mult
            if rng.random() >= p_pair:
                continue
            self.court_attempts += 1
            # 选雄性
            candidates = [m for m in adults_M if m.alive and m.health >= P['Health_gate']
                          and m.satiety >= P['Satiety_gate']]
            if not candidates:
                fem.court_fail += 1
                continue
            weights = [court_bonus(m.pheno, P.get('Court_tail_bonus', 0.03))
                       * clamp(fitness(m.pheno, e, P), 0.4, 1.3) for m in candidates]
            male = rng.choices(candidates, weights=weights)[0]
            r = self.relationship(fem.id, male.id)
            if r >= P['Inbreed_threshold'] and rng.random() < P['Inbreed_abandon']:
                fem.court_fail += 1
                male.court_fail += 1
                self.court_abandoned += 1
                continue
            # 妊娠
            self.conceive(fem, male, t, r)

        # ---------- 4. 野外引入（可选）----------
        # 注意：引入必须与繁殖共用同一个 n_eff（含在孕胎儿），
        # 否则会在「存活数未满但胎儿已占满」的时刻把引入个体塞进来，冲破硬上限。
        n_eff_now, _, _ = self.rho_and_L()
        if P.get('Immigration_enable') and n_eff_now + P.get('Immigration_n', 1) <= P['N_max'] \
                and self.last_ratio >= P.get('Immigration_min_ratio', 0.70):
            trigger = False
            if P.get('Immigration_mode', 'gen') == 'days':
                every = P.get('Immigration_every_days', 10 * HOURS_PER_DAY)
                trigger = (t > 0) and (t % max(1, int(every)) == 0)
            else:
                maxgen = max((self.foxes[i].gen for i in self.alive_ids), default=1)
                trigger = (maxgen // P.get('Immigration_every_gen', 10**9)) > self.immigrants
            if trigger:
                for _ in range(P.get('Immigration_n', 1)):
                    ne, _, _ = self.rho_and_L()
                    if ne + 1 > P['N_max']:
                        break
                    self._introduce_wild(t)

        # ---------- 5. 快照 ----------
        self.max_pop_seen = max(self.max_pop_seen, len(self.alive_ids))
        if (t + 1) % HOURS_PER_DAY == 0:
            self.snapshot()

        self.t += 1

    # ---------- 繁殖细节 ----------
    def _block(self, fem, t):
        """因名额不足拦下这次妊娠。

        v0.5 的行为是「什么都不做」，于是同一只雌性会在下一个 tick 立刻重新掷骰，
        blocked_litters 被重复计数放大到上千次，而真正的繁殖机会被空转吃掉。
        G1：拦下后进入冷却并计一次求偶失败，让机会在不同个体之间轮转。
        """
        self.blocked_litters += 1
        cd = self.P.get('Blocked_cooldown_h', 0)
        if cd > 0:
            fem.blocked_until = t + cd
            fem.court_fail += 1

    def conceive(self, fem, male, t, r):
        P = self.P
        rng = self.rng
        # 一窝仔数：3-6，受母体健康与食物丰度影响
        base = rng.randint(P['Litter_min'], P['Litter_max'])
        health_factor = 0.5 + 0.5 * clamp((fem.health - 40) / 60.0, 0, 1)
        food_factor = 1.0 if P['Food_abundant'] else 0.7
        n = max(1, int(round(base * (0.6 + 0.4 * health_factor) * food_factor)))
        n = min(n, P['Litter_max'])
        if P.get('Cap_mode') in ('L_plus_slot', 'L_plus_reserve', 'L_plus_fit'):
            n_eff_now, _, _ = self.rho_and_L()
            remain = P['N_max'] - n_eff_now
            if remain <= 0:
                self._block(fem, t)
                return
            if P.get('Cap_mode') == 'L_plus_reserve':
                # 名额不够「一整窝」就不要怀上——避免把已孕育的幼崽静默裁掉
                reserve = P.get('Litter_reserve', P['Litter_min'])
                if remain < reserve:
                    self._block(fem, t)
                    return
            elif P.get('Cap_mode') == 'L_plus_fit':
                # 窝仔数适配剩余名额：越拥挤窝越小（密度制约的自然表现），
                # 但绝不先怀上再裁掉。名额连一窝最小仔数都放不下才拒绝受孕。
                if remain < P['Litter_min']:
                    self._block(fem, t)
                    return
                n = min(n, int(remain))
            if n > remain:
                self.trimmed_pups += (n - remain)
                n = int(remain)
        fem.pregnant_until = t + P['Gestation']
        self.litters += 1
        fem.ever_bred = True
        male.ever_bred = True
        self.ever_parent.add(fem.id)
        self.ever_parent.add(male.id)
        fem.last_birth = t
        due = fem.pregnant_until
        # 缺陷：近交 -> 后代缺陷概率上升
        defect_p = 0.0
        for thr, add in sorted(P['Defect_per_r'].items(), reverse=True):
            if r >= thr - 1e-9:
                defect_p = add
                break
        self.pregnancies.append({'mother': fem.id, 'sire': male.id, 'due': due,
                                 'litter': n, 'r': r, 'defect_p': defect_p})

    def _deliver(self, pregnancy, env):
        P = self.P
        rng = self.rng
        mom = self.foxes[pregnancy['mother']]
        sire = self.foxes[pregnancy['sire']]
        mom.pregnant_until = None
        mom.court_fail = 0
        n = pregnancy['litter']
        pups_lum = []
        pups_fit = []
        # 突变：按「每只幼崽独立判定」。
        # 真实突变发生在配子/合子层面，每窝只判一次会随窝的大小人为压低突变总量，
        # 也会让「同一窝里出现一只突变兄妹」这个最能体现随机性的画面永远看不到。
        for i in range(n):
            ga = self.make_gamete(mom.geno)
            gb = self.make_gamete(sire.geno)
            geno = self.combine(ga, gb)
            mut_applied = None
            if rng.random() < P['Mut_rate']:
                mut_applied = self.apply_mutation(geno)
            sex = rng.choice('FM')
            gen = max(mom.gen, sire.gen) + 1
            cub = Fox(self.next_id, sex, geno, self.t, mom.id, sire.id, gen, P, rng)
            self.next_id += 1
            cub.phase = 'pup'
            cub.satiety = 90.0
            cub.F = self.F_of(cub.id)
            if mut_applied is not None:
                cub.source = 'mutation'
                self.mutations.append({'t': self.t, 'id': cub.id, 'locus': mut_applied[0],
                                       'old': mut_applied[1], 'new': mut_applied[2]})
            if pregnancy['defect_p'] > 0 and rng.random() < pregnancy['defect_p']:
                cub.defect_load = rng.uniform(0.4, 1.0)
                cub.ceiling = 100 - 18 * cub.defect_load
                cub.health = min(cub.health, cub.ceiling)
                cub.lifespan *= (1 - 0.15 * cub.defect_load)
            # 幼崽夭折率：25-35%，受母体健康 / 食物 / 季节影响
            mort = rng.uniform(P['Juv_mort_lo'], P['Juv_mort_hi'])
            mort *= (1.25 - 0.5 * clamp((mom.health - 50) / 50.0, 0, 1))
            # G2：幼崽存活受「自身表型适应度」影响。
            # v0.5 里夭折率只看母亲健康/食物/季节，完全不看幼崽自己的基因，
            # 于是自然选择最主要的一条通路（幼崽存活率差异）是断开的 —— 这是
            # selection_r 长期停在噪声水平的根本原因之一。
            if P.get('Juv_sel_strength', 0.0) > 0:
                fit_cub = fitness(cub.pheno, env, P)
                mort *= (1.0 + P['Juv_sel_strength'] * (1.0 - fit_cub))
            if not P['Food_abundant']:
                mort *= 1.25
            if env['season'] == '冬':
                mort *= 1.15
            if cub.defect_load > 0:
                mort *= (1 + 0.8 * cub.defect_load)
            mort = clamp(mort, 0.05, 0.75)
            if rng.random() < mort:
                cub.juv_death_t = self.rng.randrange(1, max(2, P['Mature_hours']))
            self.foxes[cub.id] = cub
            self.alive_ids.add(cub.id)
            self.births += 1
            self.kin_memo.clear()
            pups_lum.append(COLOR_LUM.get(cub.pheno['color'], 60))
            pups_fit.append(fitness(cub.pheno, env, P))
        if pups_lum:
            self.litter_log.append({
                't': self.t, 'year': self.t // (HOURS_PER_DAY * DAYS_PER_YEAR),
                'mom': COLOR_LUM.get(mom.pheno['color'], 60),
                'sire': COLOR_LUM.get(sire.pheno['color'], 60),
                'pups': pups_lum, 'pups_fit': pups_fit,
                'n': len(pups_lum),
            })

    def _wild_allele_weights(self, locus):
        """野外引入个体的等位基因权重。

        founder   —— 与创始基因库同频率（默认，v0.4 行为）
        complement—— 按「当前种群里越稀缺、引入概率越高」加权。
                     这相当于从基因组成不同的异地种群引入个体，杂合度增益最大，
                     也是保护遗传学里挑选无亲缘建群者的标准做法。
        """
        mode = self.P.get('Immigration_pool', 'founder')
        base = founder_freq(self.P)[locus]
        alleles = list(base.keys())
        if mode != 'complement':
            ws = [base[a] for a in alleles]
        else:
            cur = {}
            tot = 0
            for fid in self.alive_ids:
                f = self.foxes[fid]
                if f.pheno is None:
                    continue
                for a in f.geno[locus]:
                    cur[a] = cur.get(a, 0) + 1
                tot += 2
            ws = []
            for a in alleles:
                if base[a] <= 0:
                    ws.append(1e-6)          # 只由突变产生的稀有等位不靠引入刷出来
                    continue
                p = cur.get(a, 0) / max(1, tot)
                ws.append(base[a] * max(0.05, 1.0 - p))
        return alleles, ws

    def _introduce_wild(self, t):
        P = self.P
        if P.get('Immigration_sex', 'random') == 'balance':
            # 补稀缺性别：随机性别会有半数引入个体没有繁殖机会
            nF = sum(1 for i in self.alive_ids if self.foxes[i].sex == 'F')
            nM = sum(1 for i in self.alive_ids if self.foxes[i].sex == 'M')
            sex = 'F' if nF <= nM else 'M'
        else:
            sex = self.rng.choice('FM')
        geno = {}
        for k in LOCUS_KEYS:
            alleles, ws = self._wild_allele_weights(k)
            geno[k] = tuple(self.rng.choices(alleles, weights=ws, k=2))
        ghost_a = -5000 - self.immigrants * 2
        for gid in (ghost_a, ghost_a - 1):
            gf = Fox.__new__(Fox)
            gf.id = gid
            gf.mother = None
            gf.father = None
            gf.gen = 0
            gf.alive = False
            gf.sex = 'M'
            gf.source = 'ghost'
            gf.cause = None
            gf.pheno = None
            gf.is_founder = False
            gf.ever_bred = False
            self.foxes[gid] = gf
        f = Fox(self.next_id, sex, geno, t, ghost_a, ghost_a - 1, 1, P, self.rng)
        self.next_id += 1
        f.phase = 'adult'
        f.is_founder = True
        f.source = 'immigrant'
        self.foxes[f.id] = f
        self.alive_ids.add(f.id)
        self.immigrants += 1
        self.events.append({'t': t, 'type': 'immigrate', 'id': f.id})

    def _kill(self, f, cause, t):
        f.alive = False
        f.death = t
        f.cause = cause
        f.pregnant_until = None
        self.alive_ids.discard(f.id)
        self.deaths_by_cause[cause] += 1
        self.pregnancies = [p for p in self.pregnancies if p['mother'] != f.id]

    # ---------- 采样 ----------
    def snapshot(self):
        P = self.P
        ids = list(self.alive_ids)
        pop = len(ids)
        n_eff, rho, L = self.rho_and_L()
        adults = [self.foxes[i] for i in ids if self.foxes[i].phase == 'adult']
        gen_max = max((self.foxes[i].gen for i in ids), default=0)
        # 杂合度
        het_o = 0.0
        het_e = 0.0
        counts = defaultdict(lambda: defaultdict(int))
        nloci = 0
        for k in LOCUS_KEYS:
            allele_count = defaultdict(int)
            tot = 0
            ho = 0
            for i in ids:
                a, b = self.foxes[i].geno[k]
                if a != b:
                    ho += 1
                allele_count[a] += 1
                allele_count[b] += 1
                tot += 2
            if tot == 0:
                continue
            nloci += 1
            het_o += ho / float(len(ids))
            exp_h = 1.0 - sum((c / float(tot)) ** 2 for c in allele_count.values())
            het_e += exp_h
            counts[k] = dict(allele_count)
        meanF = statistics.mean([self.F_of(i) for i in ids]) if ids else 0.0
        # 平均适应度：mfit = 当下环境下的实际适应度；sfit = 统一参考环境下的静态适应度。
        # 只有 sfit 上升才算「种群在基因层面真的变适应了」—— mfit 会被季节/昼夜波动带偏。
        e_now = self.env()
        mfit = statistics.mean([fitness(self.foxes[i].pheno, e_now, P) for i in ids]) if ids else 0.0
        sfit = statistics.mean([fitness(self.foxes[i].pheno, REF_ENV_BASE, P)
                                for i in ids]) if ids else 0.0
        # sfitc = 以「当前阶段光照」为参考的静态适应度：环境切换后，它才衡量
        # 「种群有没有追上新环境」，固定参考环境的 sfit 会随环境漂移而失真。
        ref_now = dict(REF_ENV_BASE)
        ref_now['light'] = e_now['light']
        sfitc = statistics.mean([fitness(self.foxes[i].pheno, ref_now, P)
                                 for i in ids]) if ids else 0.0
        lum_mean = statistics.mean([COLOR_LUM.get(self.foxes[i].pheno['color'], 60)
                                    for i in ids]) if ids else 0.0
        # 累加性状的群体均值：毛长（0-4 档）与尾数（1-5）。这两项是「一眼能分辨」的
        # 可见进化载体，也是加性遗传 —— 响应远快于上位/隐性控制的毛色。
        mhair = statistics.mean([self.foxes[i].pheno['hair_len'] for i in ids]) if ids else 0.0
        mtail = statistics.mean([self.foxes[i].pheno['tails'] for i in ids]) if ids else 0.0
        meye = statistics.mean([1.0 if self.foxes[i].pheno['glow'] else 0.0 for i in ids]) if ids else 0.0
        # 表型分布
        pheno_color = defaultdict(int)
        pheno_tails = defaultdict(int)
        specials = {'glow': 0, 'star': 0, 'halo': 0, 'flame': 0, 'hetero': 0}
        for i in ids:
            ph = self.foxes[i].pheno
            pheno_color[ph['color']] += 1
            pheno_tails[ph['tails']] += 1
            for sp in specials:
                if ph.get(sp):
                    specials[sp] += 1
        self.daily.append({
            't': self.t, 'day': self.t // HOURS_PER_DAY,
            'year': self.t // (HOURS_PER_DAY * DAYS_PER_YEAR),
            'pop': pop, 'adults': len(adults), 'pups': pop - len(adults),
            'rho': round(rho, 4), 'L': round(L, 4),
            'mfit': round(mfit, 4), 'sfit': round(sfit, 4),             'sfitc': round(sfitc, 4),
            'lum': round(lum_mean, 2),
            'mhair': round(mhair, 3), 'mtail': round(mtail, 3),
            'glow': round(meye, 3),
            'het_o': round(het_o / max(1, nloci), 4),
            'het_e': round(het_e / max(1, nloci), 4),
            'meanF': round(meanF, 4),
            'maxgen': gen_max,
            'births': self.births, 'litters': self.litters,
            'dead': sum(self.deaths_by_cause.values()),
            'migrated': len(self.migrated),
            'colors': dict(pheno_color), 'tails': dict(pheno_tails),
            'specials': dict(specials),
            'alleles': {k: dict(v) for k, v in counts.items() if k in
                        ('A', 'W', 'P', 'Ey', 'Er', 'Tw', 'V', 'G', 'St', 'Ha', 'Fl', 'D')},
        })


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


# =============================================================================
# 六、后处理：谱系存活 / 突变命运 / 汇总
# =============================================================================

def descendants(world, root_id):
    """统计某祖先的存活后代数（BFS）。"""
    children = defaultdict(list)
    for fid, f in world.foxes.items():
        if fid < 0:
            continue
        if f.mother is not None and f.mother > 0:
            children[f.mother].append(fid)
        if f.father is not None and f.father > 0:
            children[f.father].append(fid)
    seen = set()
    stack = [root_id]
    while stack:
        cur = stack.pop()
        for c in children.get(cur, []):
            if c not in seen:
                seen.add(c)
                stack.append(c)
    return seen


def summarize(world, params, years_label):
    P = params
    alive = [world.foxes[i] for i in world.alive_ids]
    total_born = world.births + P['Founders']
    # 创始血统存活数
    founders = [f for f in world.foxes.values() if f.is_founder and f.source == 'birth']
    founder_lines = []
    founder_alive_desc = 0
    for fo in founders:
        desc = descendants(world, fo.id)
        living = [d for d in desc if d in world.alive_ids]
        founder_lines.append({'id': fo.id, 'alive': fo.alive,
                              'desc_total': len(desc), 'desc_alive': len(living)})
        if living:
            founder_alive_desc += 1
    # 突变命运
    mut_res = []
    for m in world.mutations:
        desc = descendants(world, m['id'])
        living = [d for d in desc if d in world.alive_ids]
        mut_res.append({**m, 'desc_total': len(desc), 'desc_alive': len(living),
                        'survived': len(living) > 0})
    mut_survived = sum(1 for m in mut_res if m['survived'])

    # 基因型 vs 表型（演示隐藏的隐性库存）
    alive_nonwhite = [f for f in alive]
    ww_carriers = sum(1 for f in alive if 'w' in f.geno['W'] and phenotype(f.geno)['color'] != '雪绒白')
    av_carriers = sum(1 for f in alive if 'Av' in f.geno['A'] and phenotype(f.geno)['color'] != '幽夜紫')

    # 外观指纹：色 × 花纹 × 耳型 × 尾数 × 特殊性状 —— 真正决定"一眼能不能分辨"
    fp = {}
    for f in alive:
        ph = f.pheno
        key = (ph['color'], ph['pattern'], ph['ear'], ph['tails'],
               'G' if ph['glow'] else '', 'S' if ph['star'] else '',
               'H' if ph['halo'] else '', 'F' if ph['flame'] else '')
        fp[key] = fp.get(key, 0) + 1
    uniq_fp = len(fp)
    fp_top = max(fp.values()) if fp else 0
    # 扩展指纹：把「眼睛颜色 + 毛长」也算进去。设计稿 §2 把它们列为可遗传可见特征，
    # 且两者在 64px 桌宠尺寸下都清晰可辨，因此更适合衡量「玩家一眼分辨」的能力。
    fp2 = {}
    for f in alive:
        ph = f.pheno
        key2 = (ph['color'], ph['pattern'], ph['ear'], ph['tails'], ph['eye'], ph['hair_len'],
                'G' if ph['glow'] else '', 'S' if ph['star'] else '',
                'H' if ph['halo'] else '', 'F' if ph['flame'] else '')
        fp2[key2] = fp2.get(key2, 0) + 1
    uniq_fp2 = len(fp2)
    # ---- 自然选择是否真的在起作用？ ----
    # 用「统一环境下的静态适应度」与「实际留下后代数」的相关性来判定
    ref_env = {'light': world.P['Env_light'], 'season': '秋', 'is_night': False,
               'day': 0, 'hod': 12, 'year': 0}
    xy = []
    allfit = []
    for fid, f in world.foxes.items():
        if fid < 0:                       # 虚构始祖不参与
            continue
        if f.phase != 'adult' and not f.is_founder:
            continue
        fit_v = fitness(f.pheno, ref_env, world.P)
        allfit.append(fit_v)
        kids = sum(1 for g in world.foxes.values()
                   if g.mother == fid or g.father == fid)
        if kids or f.ever_bred:
            xy.append((fit_v, kids))
    if len(xy) >= 3:
        xs = [a for a, _ in xy]
        ys = [b for _, b in xy]
        mx = sum(xs) / len(xs)
        my = sum(ys) / len(ys)
        num = sum((xs[i] - mx) * (ys[i] - my) for i in range(len(xs)))
        den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
        sel_r = num / den if den > 1e-9 else 0.0
    else:
        sel_r = 0.0
    fit_spread = (max(allfit) - min(allfit)) if allfit else 0.0
    mean_fit = sum(allfit) / len(allfit) if allfit else 0.0

    # ---- 繁殖集中度：少数个体垄断繁殖会把有效种群 Ne 打崩 ----
    kids_of = {}
    for g in world.foxes.values():
        if g.id < 0:
            continue
        if g.source in ('immigrant',):
            continue
        kids_of[g.mother] = kids_of.get(g.mother, 0) + 1
        kids_of[g.father] = kids_of.get(g.father, 0) + 1
    realised = sorted(kids_of.values(), reverse=True)
    n_off = sum(realised) or 1
    top_sire_share = round(realised[0] / n_off, 3) if realised else 0.0
    top5_share = round(sum(realised[:5]) / n_off, 3) if realised else 0.0
    parents_n = len(realised)
    # Ne 的 Wright 估计（两性、非均等后代数）
    if parents_n >= 2:
        mn = statistics.mean(realised)
        var = statistics.pvariance(realised)
        Ne_est = (4 * parents_n - 4) / max(0.05, (var / max(1e-9, mn) + 2 - 2.0 / parents_n))
    else:
        Ne_est = 0.0

    het_now = world.daily[-1]['het_o'] if world.daily else 0
    het_0 = world.daily[0]['het_o'] if world.daily else 0
    first = world.daily[0]
    last = world.daily[-1]

    # 打满上限的时间点
    cap_day = None
    for d in world.daily:
        if d['pop'] >= P['N_max']:
            cap_day = d['day']
            break
    days_at_cap = sum(1 for d in world.daily if d['rho'] >= 0.999)
    mean_L = statistics.mean([d['L'] for d in world.daily]) if world.daily else 0
    mean_pop = statistics.mean([d['pop'] for d in world.daily]) if world.daily else 0

    # 选择差：适应度与繁殖成功的相关性（用 environments roughly averaged）
    return {
        'label': years_label,
        'blocked_litters': world.blocked_litters,
        'trimmed_pups': world.trimmed_pups,
        'ever_parent': len(world.ever_parent),
        'max_pop_seen': world.max_pop_seen,
        'params_used': {k: P[k] for k in sorted(P)},
        'final_pop': len(alive),
        'mean_pop': round(mean_pop, 2),
        'max_pop': max((d['pop'] for d in world.daily), default=0),
        'total_births': world.births,
        'total_litters': world.litters,
        'deaths_by_cause': dict(world.deaths_by_cause),
        'total_deaths': sum(world.deaths_by_cause.values()),
        'migrated': len(world.migrated),
        'immigrants': world.immigrants,
        'max_generation': last['maxgen'] if world.daily else 0,
        'het_start': round(het_0, 4),
        'het_end': round(het_now, 4),
        'het_loss_pct': round(100 * (1 - het_now / het_0), 1) if het_0 else 0,
        'meanF_end': last['meanF'] if world.daily else 0,
        'cap_day': cap_day,
        'days_at_cap': days_at_cap,
        'days_total': len(world.daily),
        'cap_ratio': round(days_at_cap / max(1, len(world.daily)), 3),
        'mean_L': round(mean_L, 3),
        'court_attempts': world.court_attempts,
        'court_abandoned': world.court_abandoned,
        'abandon_ratio': round(world.court_abandoned / max(1, world.court_attempts), 3),
        'mutations_total': len(world.mutations),
        'mutations_survived': mut_survived,
        'mutation_rate_obs': round(len(world.mutations) / max(1, world.litters), 4),
        'founder_lines_alive': founder_alive_desc,
        'founder_lines_total': len(founders),
        'founder_lines': founder_lines,
        'mutations': mut_res,
        'end_colors': dict(last['colors']) if world.daily else {},
        'end_alleles': last['alleles'] if world.daily else {},
        'end_specials': dict(last['specials']) if world.daily else {},
        'end_tails': dict(last['tails']) if world.daily else {},
        'unique_fingerprints': uniq_fp,
        'top_sire_share': top_sire_share,
        'top5_parent_share': top5_share,
        'parents_n': parents_n,
        'Ne_wright': round(Ne_est, 1),
        'fp_ratio': round(uniq_fp / max(1, len(alive)), 3),
        'unique_fingerprints2': uniq_fp2,
        'fp2_ratio': round(uniq_fp2 / max(1, len(alive)), 3),
        'fit_spread': round(fit_spread, 4),
        'fit_mean': round(mean_fit, 4),
        'selection_r': round(sel_r, 4),
        'sfit_start': round(first['sfit'], 4) if world.daily else 0,
        'sfit_end': round(last['sfit'], 4) if world.daily else 0,
        'sfit_gain': round(last['sfit'] - first['sfit'], 4) if world.daily else 0,
        'sfit_max': round(max(d['sfit'] for d in world.daily), 4) if world.daily else 0,
        'sfitc_start': round(first['sfitc'], 4) if world.daily else 0,
        'sfitc_end': round(last['sfitc'], 4) if world.daily else 0,
        'sfitc_gain': round(last['sfitc'] - first['sfitc'], 4) if world.daily else 0,
        'lum_start': round(first['lum'], 2) if world.daily else 0,
        'lum_end': round(last['lum'], 2) if world.daily else 0,
        'lum_gain': round(last['lum'] - first['lum'], 2) if world.daily else 0,
        'food_shortage_ratio': round(world.food_shortage_ticks / max(1, world.t), 3),
        'mean_satiety_end': round(statistics.mean([f.satiety for f in alive]), 1) if alive else 0,
        'torpid_end': sum(1 for f in alive if f.torpor_flag),
        'torpor_events': world.torpor_events,
        'fp_top_share': round(fp_top / max(1, len(alive)), 3),
        'carrier_w': ww_carriers,
        'carrier_av': av_carriers,
        'collapsed': len(alive) == 0,
        'daily': world.daily,
        'events_head': world.events[:40],
    }


# =============================================================================
# 七、入口
# =============================================================================

def run_round(seed, params, years, label=None):
    P = dict(params)
    w = World(P, seed)
    total_ticks = int(years * DAYS_PER_YEAR * HOURS_PER_DAY)
    while w.t < total_ticks:
        w.step()
        if not w.alive_ids:
            w.collapse_t = w.t
            break
    lab = label or ('seed%d' % seed)
    res = summarize(w, P, lab)
    res['litter_log'] = w.litter_log          # 育种家方程诊断用（选择差 / 响应）
    res['seed'] = seed
    res['ticks'] = w.t
    res['years_elapsed'] = round(w.t / float(DAYS_PER_YEAR * HOURS_PER_DAY), 2)
    res['collapse_t'] = w.collapse_t
    res['collapsed'] = w.collapse_t is not None
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rounds', type=int, default=5)
    ap.add_argument('--years', type=float, default=5)
    ap.add_argument('--variant', default='base', choices=['base', 'tuned', 'v2', 'v3'])
    ap.add_argument('--out', default=None)
    ap.add_argument('--seed0', type=int, default=None)
    ap.add_argument('--cap', default=None, choices=['L_only', 'L_plus_slot'])
    a = ap.parse_args()

    P = dict({'base': BASE_PARAMS, 'tuned': TUNED_PARAMS,
              'v2': TUNED_V2_PARAMS, 'v3': TUNED_V3_PARAMS}[a.variant])
    P['Years'] = a.years
    if a.cap:
        P['Cap_mode'] = a.cap
    if a.seed0:
        P['Seed0'] = a.seed0

    rounds = []
    for i in range(a.rounds):
        seed = P['Seed0'] + i * 7919
        r = run_round(seed, P, a.years, label='R%d' % (i + 1))
        print('[%s] 第 %d 轮 种子=%d  世代=%d  末种群=%d  平均种群=%.1f  '
              '打满上限日=D%d  至上限占比=%.0f%%  杂合度 %.3f→%.3f  新突变=%d(存活%d)'
              % (a.variant, i + 1, seed, r['max_generation'], r['final_pop'], r['mean_pop'],
                 (r['cap_day'] if r['cap_day'] is not None else -1), r['cap_ratio'] * 100,
                 r['het_start'], r['het_end'], r['mutations_total'], r['mutations_survived']))
        rounds.append(r)

    out = a.out or ('sim/results_%s_r%d_y%g.json' % (a.variant, a.rounds, a.years))
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'variant': a.variant, 'params': P, 'rounds': rounds}, f, ensure_ascii=False)
    print('已写入', out)


if __name__ == '__main__':
    main()
