# -*- coding: utf-8 -*-
"""
表型 → 美术部件 可执行映射层 v1（2026-11-01）
================================================================
把模拟器 `phenotype()` 输出的表型字典，翻译成 Fox_Art 资产包的组装参数，
并直接渲染成 PNG。这是「遗传引擎」与「美术资产」之间唯一的一层胶水。

设计原则
--------
1. **只读交付物**：不修改 `Fox_Art/tools/` 下任何文件，全部用包装/运行时补丁。
2. **缺口显式化**：映射不到的位点写进 `notes` / `missing`，绝不静默丢弃。
3. **同一套规则**：面板、桌宠、批量出图都必须走这一个函数，避免三处各写一遍。

对外接口
--------
    to_art(pheno)            -> dict   表型 → 组装参数（纯数据，不碰磁盘）
    render(pheno, size=512)  -> Image  表型 → 成品图
    render_geno(geno, size)  -> Image  基因型 → 成品图（内部先 phenotype）

用法
----
    import artmap as AM
    AM.render_geno(geno, size=512).save('fox.png')
"""

import os
import re
import json
import glob

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# ---------------------------------------------------------------------------
# 0. 资产包定位（支持多个版本共存，按版本号自然排序取最新）
# ---------------------------------------------------------------------------

_PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _verkey(p):
    """v1.10 要排在 v1.9 之后，所以按数字元组排而不是按字符串。"""
    m = re.search(r'_art_v([\d.]+)', p)
    return tuple(int(x) for x in m.group(1).split('.')) if m else (0,)


def find_art_root():
    env = os.environ.get('FOX_ART_ROOT')
    if env:
        if os.path.isdir(env):
            return os.path.abspath(env)
        raise RuntimeError('FOX_ART_ROOT 指向的目录不存在：%s' % env)
    cands = glob.glob(os.path.join(_PROJECT, '_art_v*', 'delivery', 'Fox_Art'))
    cands = [c for c in cands
             if os.path.isfile(os.path.join(c, '01_Data', 'traits.json'))]
    if not cands:
        raise RuntimeError(
            '找不到 Fox_Art 资产包。请把交付包解压到 %s/_art_vX/delivery/Fox_Art，'
            '或设置环境变量 FOX_ART_ROOT。' % _PROJECT)
    return max(cands, key=_verkey)


ART_ROOT = find_art_root()
TOOLS = os.path.join(ART_ROOT, 'tools')
MASTER = os.path.join(ART_ROOT, 'assets', 'master')
DATA = os.path.join(ART_ROOT, '01_Data')

import sys
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import run_assemble as RA          # 美术侧组装器（只读复用）
from fox_traits import load_colorways, recolor_coat   # LOCK-F 换色算法

# ---------------------------------------------------------------------------
# 1. 映射表（纯数据，可被外部检查/覆盖）
# ---------------------------------------------------------------------------

# 1.1 毛色：模拟器表型中文名 → colorways.json 的 id
#     A×D×W 组合出 9 种可见色（设计稿 §2.1）；sakura/mint/obsidian_gold 为
#     突变专属等位（§8.1.1 已拍板挂突变池），此处预留接口。
COAT_BY_ZH = {
    '雪绒白': 'white',       # ww 上位
    '赤橙':   'orange',      # A+ × D
    '奶油金': 'caramel',     # A+ × dd
    '霜灰':   'grey',        # As × D
    '淡银蓝': 'blue',        # As × dd
    '幽夜紫': 'purple',      # Av × D
    '淡雾紫': 'mist_purple',  # Av × dd   ← v1.3 新增
    '墨黑':   'black',       # Ab × D
    '雾霭蓝': 'haze_blue',   # Ab × dd   ← v1.3 新增
    # ---- 突变专属（§8.1.1，模拟器尚未实现等位，接口先留好）----
    '樱粉':   'sakura',
    '薄荷':   'mint',
    '曜金':   'obsidian_gold',
}

# 1.2 毛发：L1+L2 累加 0–4 档 + K 卷毛
#     注意：美术侧母版文件名是 fur_mid（不是 medium），这是 v1.3 的既有命名。
FUR_BY_LEN = {0: 'short', 1: 'short', 2: 'mid', 3: 'mid', 4: 'long'}
FUR_CURLY = 'curly'

# 1.3 尾数：Tn1+Tn2 累加 → 1–5，V → 9
# 注意：run_assemble 内部拼 "tail_%s.png"/"ear_%s_L.png"，
# 所以这里存**裸名**（twin 而非 tail_twin），traits.json 的合法值在输出时再拼前缀。
TAIL_BY_COUNT = {2: 'twin', 3: 'triple', 4: 'quad', 5: 'quint', 9: 'nine'}

# 1.4 眼型：Ef 剂量 0/1/2
#     ⚠ 缺口修正：traits.json 声明的值是 eye_narrow，但 v1.1–v1.3 的实际素材
#       一直是 eye_sleepy（细长困眼），没有 eye_narrow.png。这里做别名。
EYE_SHAPE_ART = {0: 'sleepy', 1: 'almond', 2: 'round'}
EYE_SHAPE_TRAIT = {0: 'eye_narrow', 1: 'eye_almond', 2: 'eye_round'}

# 1.5 眼色：Ey 复等位（显性序列 EyG > EyC > EyB > EyV）
EYE_COLOR = {'EyG': 'gold', 'EyC': 'cyan', 'EyB': 'blue', 'EyV': 'purple'}
EYE_ORDER = ['EyG', 'EyC', 'EyB', 'EyV']

# 1.6 斑纹：P 位点 4 态（PT 虎斑 / Ps 条纹 / Pg 斑点 / p 纯色）
#     ⚠ facemark 是 v1.3 的文件名拼写（traits.json 里写 face_mark），以文件为准。
PATTERN_ART = {'PT': 'tabby', 'Ps': 'stripes', 'Pg': 'spots', 'p': 'solid'}

# 1.7 特殊层：美术侧**没有**对应素材，走程序化合成（见 §4）
#     traits.json 的 values 里声明了 special_glow / special_aura /
#     special_star_mark，但 assets/master 下不存在任何文件 —— 属声明未交付。
PROCEDURAL_SPECIAL = {'glow', 'halo', 'star_mark'}

# 1.8 完全无素材的位点（记入 missing，供覆盖报告统计）
NO_ASSET = {
    'ear_tip': '耳尖色（Tp：深尖/白尖/同色）—— 无贴花素材，暂不表现',
    'inner_ear': '内耳色（In：浅/深）—— 由 colorways.innerEar 统一覆盖，不随基因变化',
    'tail_tip': '尾尖色（Tw：宽白/钩形/无）—— 无贴花素材，暂不表现',
}


# ---------------------------------------------------------------------------
# 2. 表型 → 组装参数
# ---------------------------------------------------------------------------

def _single_tail(pheno):
    """单尾形态。优先级：K 卷毛（多效）> 尾长 > 蓬松度。

    依据 v1.3 素材的实测形态（bbox / 像素量）：
      normal 355×208 标准   long 331×246 更长   short 232×119 明显短
      fluffy 340×245 蓬松球状   thin 184×351 细长下垂   curl 306×179 尾尖卷曲
    所以 Tl 决定长/中/短，Tf 在「中」档分出蓬/纤 —— 五个件正好覆盖。
    """
    if pheno.get('curl'):
        return 'curl', ['K 位点多效：卷毛自动切卷尾（§8.1.1）']
    tl = pheno.get('tail_len', 1)
    if tl == 2:
        return 'long', []
    if tl == 0:
        return 'short', []
    if pheno.get('tail_fluff'):
        return 'fluffy', []
    return 'thin', []


def _ear(pheno):
    """耳型。6 个部件要接住 Er(3 态) × Ez(3 档) 的 9 种组合，规则：

      St 星耳（稀有突变，多效）> Erf 折耳（形态特异）> Ez 剂量决定大小
      ErP 尖耳 固定用 ear_pointed（尖耳没有大小变体）
      ErR 圆耳 + Ez=0/1/2 → small / round / large
    这样 6 个部件全部用上，且语义自洽。
    """
    notes = []
    if pheno.get('star'):
        return 'star', ['St 多效：星纹 → 星耳（覆盖 Er/Ez 形态）']
    if pheno.get('ear') == 'Erf':
        return 'fold', ['Erf 折耳：忽略 Ez 大小（无折耳大小变体）']
    if pheno.get('ear') == 'ErP':
        return 'pointed', ['ErP 尖耳：忽略 Ez 大小（无尖耳大小变体）']
    ez = pheno.get('ear_size', 1)
    name = {0: 'small', 1: 'round', 2: 'large'}[ez]
    return name, []


def _eyes(pheno):
    """左右眼色。Ht 异色瞳 = 右眼换 Ey 显性序列里的下一个眼色。

    规则是确定性的（同基因型永远得到同一结果），避免每帧抖动。
    """
    base = pheno.get('eye', 'EyB')
    left = EYE_COLOR[base]
    if pheno.get('hetero'):
        right = EYE_COLOR[EYE_ORDER[(EYE_ORDER.index(base) + 1) % 4]]
    else:
        right = left
    return left, right


def to_art(pheno):
    """表型字典 → 美术组装参数（纯数据，无副作用）。

    返回
    ----
    dict:
      coat / fur / tail / ear / eye_l / eye_r / pupil / pattern
      special      : ['glow', 'halo', 'star_mark', 'flame'] 子集（程序化层）
      trait_*      : 对应的 traits.json 合法值（供面板显示、便于校验）
      notes        : 降级/覆盖说明（人读）
      missing      : 无素材支撑的位点（供覆盖报告统计）
    """
    notes = []
    missing = []

    # --- 毛色 ---
    zh = pheno.get('color', '霜灰')
    coat = COAT_BY_ZH.get(zh)
    if coat is None:
        coat = 'grey'
        notes.append('未知毛色「%s」→ 回退霜灰' % zh)

    # --- 毛发 ---
    if pheno.get('curl'):
        fur = FUR_CURLY
    else:
        hl = int(pheno.get('hair_len', 0))
        fur = FUR_BY_LEN.get(hl, 'short')
        # 累加 5 档（0–4）压到 3 个部件，说明清楚哪几档合并了
    trait_fur = {'short': 'fur_short', 'mid': 'fur_medium',
                 'long': 'fur_long', 'curly': 'fur_curly'}[fur]

    # --- 尾巴 ---
    n = int(pheno.get('tails', 1))
    if n <= 1:
        tail, nt = _single_tail(pheno)
        notes.extend(nt)
    elif n in TAIL_BY_COUNT:
        tail = TAIL_BY_COUNT[n]
        # 多尾素材只有 normal 形制（H2 拍板：多尾 × 尾型组合先搁置）
        if pheno.get('curl') or pheno.get('tail_len', 1) != 1 \
                or pheno.get('tail_fluff'):
            notes.append('%d 尾：形态维度（长/短/蓬/卷）被忽略，'
                         '美术侧目前只有 normal 形制多尾' % n)
    else:
        tail = 'nine'
        notes.append('尾数 %d 超出素材范围 → 使用九尾' % n)

    # --- 耳朵 ---
    ear, nt = _ear(pheno)
    notes.extend(nt)

    # --- 眼睛 ---
    shape = EYE_SHAPE_ART[int(pheno.get('eye_shape', 2))]
    el, er = _eyes(pheno)
    eye_l, eye_r = '%s_%s' % (shape, el), '%s_%s' % (shape, er)
    # 素材完整性兜底：缺色/缺形时退回 round_blue（美术侧基准件）
    for side, name in (('左眼', eye_l), ('右眼', eye_r)):
        if not os.path.isfile(os.path.join(MASTER, 'Eyes', 'eye_%s.png' % name)):
            notes.append('%s %s 无素材 → 回退 round_blue' % (side, name))
            if side == '左眼':
                eye_l = 'round_blue'
            else:
                eye_r = 'round_blue'

    # --- 瞳孔 ---
    pupil = 'star' if pheno.get('star') else None

    # --- 斑纹 ---
    pcode = pheno.get('pattern', 'p')
    pattern = PATTERN_ART.get(pcode, 'solid')
    special = []
    if pheno.get('flame'):
        # Fl 火焰纹与 P 斑纹共用同一个叠加槽位（assemble 只接受一个 pattern）
        if pattern != 'solid':
            notes.append('Fl 火焰纹覆盖了 P 位点斑纹（%s）—— '
                         '单槽位限制，多花纹叠加待美术侧支持' % pattern)
        pattern = 'flame'

    # --- 特殊层（程序化）---
    if pheno.get('glow'):
        special.append('glow')
        missing.append('G 发光：美术声明了 special_glow 但未交付素材 → 程序化外发光')
    if pheno.get('halo'):
        special.append('halo')
        missing.append('Ha 光环：美术声明了 special_aura 但未交付素材 → 程序化光环')
    if pheno.get('star'):
        special.append('star_mark')
        missing.append('St 星纹：美术声明了 special_star_mark 但未交付素材 → 程序化星纹')

    # --- 无素材位点 ---
    for k, why in NO_ASSET.items():
        v = pheno.get(k)
        if v not in (None, False):
            missing.append(why)

    return {
        'coat': coat,
        'fur': fur,
        'tail': tail,
        'ear': ear,
        'eye_l': eye_l,
        'eye_r': eye_r,
        'pupil': pupil,
        'pattern': pattern,
        'special': special,
        # traits.json 合法值（面板显示 / 校验用）
        'trait_coat': coat,
        'trait_fur': trait_fur,
        'trait_tail': 'tail_%s' % tail,
        'trait_ear': 'ear_%s' % ear,
        'trait_eye_shape': EYE_SHAPE_TRAIT[int(pheno.get('eye_shape', 2))],
        'trait_eye_color': 'eye_hetero' if pheno.get('hetero') else 'eye_%s' % el,
        'trait_pupil': 'pupil_%s' % pupil if pupil else 'pupil_round',
        'trait_pattern': 'pattern_%s' % pattern,
        'notes': notes,
        'missing': missing,
    }


# ---------------------------------------------------------------------------
# 3. 渲染
# ---------------------------------------------------------------------------

_CW = None
_ORIG_MAKE_CORE = RA.make_core   # 保存原函数，避免运行时替换后自我递归


def _colorways():
    global _CW
    if _CW is None:
        _CW, _ = load_colorways(os.path.join(DATA, 'colorways.json'))
    return _CW


# --- 换色加速 ---------------------------------------------------------------
# 官方 recolor_coat 在 1024² 全画布上做 (H,W,7,3) 的广播差值，单次 ~1.0s；
# 一只狐狸要换 4 次（core + 尾 + 双耳）= 4s，桌宠不可能接受。
# 这里做两件事，结果与官方版逐像素一致（见 verify_artmap.py 的 E 段）：
#   1) 先裁到 alpha bbox —— 狐狸只占画布约一半，直接省掉一半像素；
#   2) |work-src|² 展开成一次矩阵乘，不再生成 (H,W,7,3) 的中间张量。
# 不修改美术侧任何文件，只在本模块替换调用点。

def _recolor_coat_fast(img, cw_src, cw_tgt, strength=1.0):
    from fox_traits import hex2rgb, ROLES
    im = img.convert('RGBA')
    bb = im.getchannel('A').getbbox()
    if not bb:
        return im.copy()
    box = (max(0, bb[0] - 2), max(0, bb[1] - 2),
           min(im.width, bb[2] + 2), min(im.height, bb[3] + 2))
    sub = im.crop(box)
    arr = np.asarray(sub).astype(np.float32)
    a = arr[..., 3]
    af = np.maximum(a / 255.0, 1.0 / 255.0)[..., None]
    work = np.clip((arr[..., :3] - 255.0 * (1.0 - af)) / af, 0, 255)

    src = np.stack([hex2rgb(cw_src[r]) for r in ROLES]).astype(np.float32)
    tgt = np.stack([hex2rgb(cw_tgt[r]) for r in ROLES]).astype(np.float32)

    s2 = (src * src).sum(1)
    d2 = (work * work).sum(-1)[..., None] - 2.0 * (work @ src.T) + s2
    d2 = np.maximum(d2, 0.0)                     # 浮点可能出负零
    w = 1.0 / (d2 + 200.0) ** 2
    w = w / np.maximum(w.sum(-1, keepdims=True), 1e-6)

    Ysrc_r, Ytgt_r = _lum(src), _lum(tgt)
    Csrc_r = src - Ysrc_r[:, None]
    Ctgt_r = tgt - Ytgt_r[:, None]
    Ysrc_b = (w * Ysrc_r).sum(-1)
    Ytgt_b = (w * Ytgt_r).sum(-1)
    Csrc_b = (w[..., None] * Csrc_r).sum(2)
    Ctgt_b = (w[..., None] * Ctgt_r).sum(2)

    Y = _lum(work)
    cpx = work - Y[..., None]
    Yout = Ytgt_b * (Y / np.maximum(Ysrc_b, 1.0))
    k = np.linalg.norm(cpx, axis=-1) / (np.linalg.norm(Csrc_b, axis=-1) + 0.5)
    k = np.clip(k, 0.0, 2.0)
    mapped = np.clip(Yout[..., None] + Ctgt_b * k[..., None], 0, 255)
    out = work * (1.0 - strength) + mapped * strength

    res = np.dstack([out, a]).astype(np.uint8)
    piece = Image.fromarray(res, 'RGBA')
    full = Image.new('RGBA', im.size, (0, 0, 0, 0))
    full.paste(piece, (box[0], box[1]))
    return full


def _lum(rgb):
    return 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]


# 部件级换色缓存：同一只狐换装/换帧时部件重复率高（尾巴 11 种 × 毛色 12 种）
_RECOLOR_CACHE = {}
_RECOLOR_MAX = 24


def _recolor(img, src_id, tgt_id, tag=None, strength=1.0):
    """带缓存的换色。tag 给得出唯一部件名时必须给，否则不缓存。"""
    if src_id == tgt_id:
        return img
    cw = _colorways()
    if tag is None:
        return _recolor_coat_fast(img, cw[src_id], cw[tgt_id], strength=strength)
    key = (tag, src_id, tgt_id, round(strength, 3))
    hit = _RECOLOR_CACHE.get(key)
    if hit is not None:
        return hit
    out = _recolor_coat_fast(img, cw[src_id], cw[tgt_id], strength=strength)
    if len(_RECOLOR_CACHE) >= _RECOLOR_MAX:
        _RECOLOR_CACHE.pop(next(iter(_RECOLOR_CACHE)))
    _RECOLOR_CACHE[key] = out
    return out


_FUR_ALIAS = None


def fur_key(fur):
    """中毛母版在 v1.3 叫 fur_mid、v1.4 重命名为 fur_medium；按磁盘实际存在者选。

    这样同一套映射层能同时跑 v1.3 与 v1.4 的素材包，换包不用改代码。
    """
    global _FUR_ALIAS
    if _FUR_ALIAS is None:
        _FUR_ALIAS = {
            k: os.path.isfile(os.path.join(
                MASTER, 'Base', 'fox_fur_%s_blue_q4@1024.png' % k))
            for k in ('short', 'mid', 'medium', 'long', 'curly')
        }
    if fur in ('mid', 'medium'):
        for k in ('medium', 'mid'):
            if _FUR_ALIAS.get(k):
                return k
    return fur


def _make_core_with_coat(coat, fur, seam='socketfill', with_base=True):
    """★ 缺口修正 ①：非短毛母版只有霜蓝一版。

    `run_assemble.make_core` 在 fur != 'short' 时直接取
    `fox_fur_<fur>_blue_q4@1024.png`，**把 coat 参数完全丢弃** ——
    结果是所有长毛/中毛/卷毛狐狸都变成霜蓝色。实测：
        orange+long → core=fox_fur_long_blue_q4，平均 RGB (104,133,158) 蓝灰。
    这里先按 blue 切出核心，再用 LOCK-F 的 recolor_coat 换到目标毛色。
    实测换色后均值与同毛色短毛版一致（orange: 155/115/86 → 154/114/84）。
    """
    fur = fur_key(fur)
    core, src = _ORIG_MAKE_CORE('blue' if fur != 'short' else coat, fur,
                                seam=seam, with_base=with_base)
    if fur != 'short' and coat != 'blue':
        cw = _colorways()
        core = _recolor(core, 'blue', coat)
        src = '%s  [recolor blue→%s]' % (os.path.basename(src), coat)
    return core, src


def _place_eyes(img, eye_l, eye_r, pupil=None):
    """自己放眼睛：assemble 只支持左右同一只眼，异色瞳必须分开画。

    尺寸/锚点与 run_assemble 内保持一致（target_w=118 覆盖母版眼洞 109×97）。
    """
    target_w = 118.0
    for name, anc in ((eye_l, 'eye_l'), (eye_r, 'eye_r')):
        ep = Image.open(os.path.join(MASTER, 'Eyes', 'eye_%s.png' % name)).convert('RGBA')
        bb = ep.getbbox()
        ec = ep.crop(bb)
        s = target_w / ec.width
        img, _, _ = RA.scale_rot_place(
            img, ec, (ec.width / 2.0 * s, ec.height / 2.0 * s),
            RA.ANCHORS[anc], s, 0.0)
    if pupil:
        pm = RA.load_meta('Eyes', 'pupils')
        if pupil in pm:
            p = Image.open(os.path.join(MASTER, 'Eyes', pm[pupil]['file'])).convert('RGBA')
            bb = p.getbbox()
            pc = p.crop(bb)
            s = 46.0 / max(pc.size)
            for anc in ('eye_l', 'eye_r'):
                img, _, _ = RA.scale_rot_place(
                    img, pc, (pc.width / 2.0 * s, pc.height / 2.0 * s),
                    RA.ANCHORS[anc], s, 0.0)
    return img


def _tint(part, coat, tag=None):
    """部件跟随毛色：耳/尾原画是霜蓝，需按 LOCK-F 换到目标毛色。"""
    if coat == 'blue':
        return part
    return _recolor(part, 'blue', coat, tag=tag)


# 花纹与底色的最小亮度差（低于这个值把 tint 往 outline / light 方向推）
PAT_MIN_DELTA = 48.0


def _pattern_tint(c, style):
    """花纹着色：保证与底色有足够亮度差。

    ★ 为什么需要这一步：colorways 的 shade 相对 base 只暗 20–38 级亮度，
      乘上 alpha 0.85 后实际差 ≈ 25 级 —— 在 128–256px 的桌宠尺寸上
      几乎与底色糊在一起（实测霜灰毛上 five 种花纹全部不可辨）。
      这里按底色明暗自动往 outline（浅毛）或 light（深毛）方向插值，
      直到亮度差达到 PAT_MIN_DELTA，色相仍来自原配色板。
    """
    from fox_traits import hex2rgb
    if style.get('blend') == 'screen':      # 火焰纹自带 minLuma 处理，不走这里
        return hex2rgb(c.get(style.get('tintRole', 'light'), c['base']))

    def lum(rgb):
        return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]

    base = np.array(hex2rgb(c['base']), np.float32)
    t0 = style.get('tintRole', 'shade')
    t = np.array(hex2rgb(c.get(t0, c['base'])), np.float32)
    if abs(lum(t) - lum(base)) >= PAT_MIN_DELTA:
        return tuple(t)
    target = c['outline'] if lum(base) > 110 else c['light']
    o = np.array(hex2rgb(target), np.float32)
    for k in (0.35, 0.5, 0.65, 0.8, 1.0):
        cand = base * (1 - k) + o * k
        if abs(lum(cand) - lum(base)) >= PAT_MIN_DELTA:
            return tuple(cand)
    return tuple(o)


def _apply_pattern(layer, coat, pattern, scale=1.0, tint_role=None):
    """花纹叠加（自实现，为了①控制强度②决定是否上尾巴）。

    run_assemble.apply_pattern 的规则一致：遮罩信息在 ALPHA 通道，
    blend=screen 用于火焰纹（深色毛上仍可见），其余走 alpha 混合。
    差异：strength 再乘一个 scale，便于在集成侧把「贴片感」调成「纹理感」。
    """
    from fox_traits import hex2rgb
    c = _colorways()[coat]
    st = RA.pattern_style(pattern)
    pmask = Image.open(os.path.join(MASTER, 'Patterns',
                                    'pattern_%s_mask@1024.png' % pattern))
    pa = np.asarray(pmask.getchannel('A')).astype(np.float32) / 255.0
    la = np.asarray(layer)[..., 3].astype(np.float32) / 255.0
    if tint_role:
        tint = hex2rgb(c.get(tint_role, c['base']))
    else:
        tint = _pattern_tint(c, st)
    arr = np.asarray(layer).astype(np.float32)
    k = (pa * la)[..., None] * float(st.get('strength', 0.85)) * scale
    base = arr[..., :3]
    t = np.array(tint, np.float32)
    if st.get('blend') == 'screen':
        minl = float(st.get('minLuma', 0))
        if minl > 0:
            lum = float(0.299 * t[0] + 0.587 * t[1] + 0.114 * t[2])
            if lum < minl and lum < 255:
                kk = (minl - lum) / (255.0 - lum)
                t = t + (255.0 - t) * kk
        scr = 255.0 - (255.0 - base) * (255.0 - t) / 255.0
        arr[..., :3] = base * (1 - k) + scr * k
    else:
        arr[..., :3] = base * (1 - k) + t * k
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGBA')


def _compose(spec, size=None, pat_on_tail=False, pattern_scale=1.0,
             pattern_tint=None):
    """完整组装。**自实现，不调用 run_assemble.assemble**，原因有三：

    1. assemble 只支持左右同一只眼 -> 异色瞳（Ht 位点）画不出来；
    2. assemble 会把花纹同时刷到尾巴层和身体层，尾巴被染色后与身体分裂感很强，
       而且虎斑/斑点会糊成一团（实测脏得没法用）；
    3. 需要控制花纹强度。

    图层顺序与美术规范一致：
        [tail] → body_core(+pattern) → ear_L → ear_R → eye_L → eye_R → pupil
    所有部件都是 1024 全画布对齐，(0,0) 直接叠加，不需要锚点换算。
    """
    coat, fur = spec['coat'], spec['fur']
    core, src = _make_core_with_coat(coat, fur)
    used = {'core': src, 'seam': 'socketfill'}

    # --- 尾巴（身体下层）---
    tail_tag = 'tail_%s' % spec['tail']
    tp = _tint(Image.open(os.path.join(MASTER, 'Tails',
                                       tail_tag + '.png')).convert('RGBA'), coat,
               tag=tail_tag)
    stack = Image.new('RGBA', (1024, 1024), (0, 0, 0, 0))
    stack.alpha_composite(tp)
    used['tail'] = 'tail_%s.png' % spec['tail']

    # --- 花纹 ---
    if spec['pattern'] != 'solid':
        if pat_on_tail:
            stack = _apply_pattern(stack, coat, spec['pattern'], pattern_scale, pattern_tint)
        core = _apply_pattern(core, coat, spec['pattern'], pattern_scale, pattern_tint)
        used['pattern'] = 'pattern_%s_mask@1024.png' % spec['pattern']

    # --- 身体压在尾巴之上 ---
    stack.alpha_composite(core, (0, 0))
    img = stack

    # --- 耳朵（v1.3 起全部为 1024 全画布对齐变体件）---
    for side in ('L', 'R'):
        fn = 'ear_%s_%s.png' % (spec['ear'], side)
        p = _tint(Image.open(os.path.join(MASTER, 'Ears', fn)).convert('RGBA'),
                  coat, tag=fn[:-4])
        if p.size != (1024, 1024):
            p = p.resize((1024, 1024), Image.LANCZOS)
        img.alpha_composite(p, (0, 0))
        used['ear_' + side] = fn

    # --- 眼睛 + 瞳孔 ---
    img = _place_eyes(img, spec['eye_l'], spec['eye_r'], spec['pupil'])
    used['eye'] = '%s / %s' % (spec['eye_l'], spec['eye_r'])
    if spec['pupil']:
        used['pupil'] = spec['pupil']

    # --- 修补（封闭口袋 + 抗锯齿碎片）---
    img, fixed = RA.repair_pockets(img)
    if fixed:
        used['pocketRepairPx'] = fixed
    img = RA.clean_islands(img)

    # --- 程序化特殊层 ---
    if 'glow' in spec['special']:
        img = add_glow(img)
    if 'halo' in spec['special']:
        img = add_halo(img)
    if 'star_mark' in spec['special']:
        img = add_star_mark(img)

    if size and size != img.width:
        img = img.resize((size, size), Image.LANCZOS)
    return img, used


def find_attachment(name, coat=None):
    """按 slot 值解析附件文件，找不到返回 None。

    animations.json 的 slots 值有两类写法：
      - 带毛色的完整名：`eye_round_blue`（主眼件，在 Eyes/）
      - 不带毛色的通用名：`eye_closed` / `brow_angry_L` / `mouth_smile` / `blush`
        （表情件，在 Expressions/，多数带毛色变体）
    所以解析顺序是「带毛色 → 通用 → 主眼件」，目录差异对调用方透明。
    """
    if name.startswith('eye_') and False:      # 保留：不要剥前缀，blush 这类没有
        name = name[4:]
    cands = []
    if coat:
        cands.append(os.path.join(MASTER, 'Expressions',
                                  '%s_%s.png' % (name, coat)))
    cands.append(os.path.join(MASTER, 'Expressions', '%s.png' % name))
    cands.append(os.path.join(MASTER, 'Eyes', '%s.png' % name))
    for p in cands:
        if os.path.isfile(p):
            return p
    return None


def layers(spec, pattern_scale=1.0, pattern_tint=None):
    """返回未叠加的部件层，供动画层各自做骨骼变换。

    与 `_compose` 用同一份加载/换色逻辑，保证静态与动态两套图一致。
    只给「能独立刚性变换」的四个部件：tail / core / ear_L / ear_R。
    眼睛单独由 `place_eyes_on` 处理（要支持眨眼附件切换）。
    """
    coat, fur = spec['coat'], spec['fur']
    core, src = _make_core_with_coat(coat, fur)
    if spec['pattern'] != 'solid':
        core = _apply_pattern(core, coat, spec['pattern'],
                              pattern_scale, pattern_tint)

    tail_tag = 'tail_%s' % spec['tail']
    tail = _tint(Image.open(os.path.join(
        MASTER, 'Tails', tail_tag + '.png')).convert('RGBA'), coat, tag=tail_tag)

    out = {'core': core, 'tail': tail, 'src': src, 'coat': coat, 'fur': fur}
    for side in ('L', 'R'):
        fn = 'ear_%s_%s.png' % (spec['ear'], side)
        p = _tint(Image.open(os.path.join(MASTER, 'Ears', fn)).convert('RGBA'),
                  coat, tag=fn[:-4])
        if p.size != (1024, 1024):
            p = p.resize((1024, 1024), Image.LANCZOS)
        out['ear_' + side] = p
    return out


def place_eyes_on(img, spec, override=None):
    """把眼睛叠到 img 上；override 可覆盖某一侧（眨眼时用闭眼件）。

    override 的 value 是 animations.json 里的通用名（如 `eye_closed`），
    按当前毛色解析到 `Expressions/eye_closed_<coat>.png`。
    """
    ov = override or {}
    target_w = 118.0
    for key, anc in (('eye_l', 'eye_l'), ('eye_r', 'eye_r')):
        name = ov.get(anc) or spec[key]
        p = find_attachment(name, spec.get('coat'))
        if p is None:                      # 附件缺失就退回原眼，不静默变空
            p = os.path.join(MASTER, 'Eyes', 'eye_%s.png' % spec[key])
        ep = Image.open(p).convert('RGBA')
        bb = ep.getbbox()
        ec = ep.crop(bb)
        s = target_w / ec.width
        img, _, _ = RA.scale_rot_place(
            img, ec, (ec.width / 2.0 * s, ec.height / 2.0 * s),
            RA.ANCHORS[anc], s, 0.0)
    if spec.get('pupil'):
        pm = RA.load_meta('Eyes', 'pupils')
        if spec['pupil'] in pm:
            pp = Image.open(os.path.join(
                MASTER, 'Eyes', pm[spec['pupil']]['file'])).convert('RGBA')
            bb = pp.getbbox()
            pc = pp.crop(bb)
            s = 46.0 / max(pc.size)
            for anc in ('eye_l', 'eye_r'):
                img, _, _ = RA.scale_rot_place(
                    img, pc, (pc.width / 2.0 * s, pc.height / 2.0 * s),
                    RA.ANCHORS[anc], s, 0.0)
    return img


def render(pheno, size=None, **kw):
    """表型 → 成品图（RGBA，1024 或指定边长）。

    kw 透传 _compose：pat_on_tail（花纹是否上尾，默认 False）、pattern_scale。
    """
    img, _ = _compose(to_art(pheno), size, **kw)
    return img


def render_geno(geno, size=None, **kw):
    """基因型 → 成品图。延迟 import 避免循环依赖。"""
    from fox_ecosystem_sim import phenotype
    return render(phenotype(geno), size=size, **kw)


# ---------------------------------------------------------------------------
# 4. 程序化特殊层（补美术未交付的 glow / halo / star_mark）
# ---------------------------------------------------------------------------

# 光环与星纹的位置来自母版实测（不是拍脑袋）：
#   body_core bbox x 189–876 / y 150–927；两只耳朵 bbox 顶边 y=166，头部 x 425–830。
#   所以光环要压在所有东西之上、耳朵之上，中心 y 必须 ≤ 166-ry。
HALO_CENTER = (640, 128)
HALO_RX, HALO_RY = 178, 40
# 星纹散布在左侧胸腹（狐狸朝右，尾巴在左，这块面积最大且不被尾巴挡）
STAR_SPOTS = [((566, 636), 50, 0.85), ((496, 706), 29, 0.7), ((628, 700), 21, 0.6)]


def add_glow(img, color=(255, 216, 140), radius=16, strength=0.62):
    """G 位点：外发光。用 alpha 模糊做光晕，垫在图下面。"""
    a = img.getchannel('A').filter(ImageFilter.GaussianBlur(radius))
    a = a.point(lambda v: int(v * strength))
    glow = Image.new('RGBA', img.size, color + (0,))
    glow.putalpha(a)
    out = Image.new('RGBA', img.size, (0, 0, 0, 0))
    out.alpha_composite(glow)
    out.alpha_composite(img)
    return out


def add_halo(img, color=(255, 224, 146, 225), width=8):
    """Ha 位点：头顶光环。椭圆环 + 柔化描边，压在耳朵上方。"""
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = HALO_CENTER
    d.ellipse([cx - HALO_RX, cy - HALO_RY, cx + HALO_RX, cy + HALO_RY],
              outline=color, width=width)
    layer = layer.filter(ImageFilter.GaussianBlur(1.6))
    out = img.copy()
    out.alpha_composite(layer)
    return out


def add_star_mark(img, color=(255, 250, 214, 230)):
    """St 位点：侧腹星纹。三颗大小不一的五角星 + 柔光，避免像贴纸。"""
    import math
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for (cx, cy), r, op in STAR_SPOTS:
        pts = []
        for i in range(10):
            ang = -math.pi / 2 + i * math.pi / 5
            rr = r if i % 2 == 0 else r * 0.42
            pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
        d.polygon(pts, fill=color[:3] + (int(color[3] * op),))
    layer = layer.filter(ImageFilter.GaussianBlur(1.1))
    # 只画在身体上，避免星纹飘到背景
    body = img.getchannel('A').point(lambda v: 255 if v > 8 else 0)
    layer.putalpha(Image.composite(layer.getchannel('A'),
                                   Image.new('L', img.size, 0), body))
    out = img.copy()
    out.alpha_composite(layer)
    return out


# ---------------------------------------------------------------------------
# 5. 质量自检：尾根缺口（v1.3 已知缺陷的回归位）
# ---------------------------------------------------------------------------

_BODY_MASK = {}


def body_mask(fur='short'):
    """母版狐狸轮廓（用于判「本该有像素却透明」）。

    ★ 必须按毛发选母版：长毛/卷毛的轮廓比短毛大一圈（耳朵和胸毛更蓬），
    用短毛轮廓去比会把蓬松部分误判成「缺口」。
    """
    if fur not in _BODY_MASK:
        name = 'fox_base_blue_q4@1024.png' if fur == 'short' \
            else 'fox_fur_%s_blue_q4@1024.png' % fur_key(fur)
        p = os.path.join(MASTER, 'Base', name)
        _BODY_MASK[fur] = np.asarray(Image.open(p).convert('RGBA').split()[3]) > 8
    return _BODY_MASK[fur]


def tail_root_holes(img, fur='short'):
    """尾根缺口像素数：母版轮廓内、组装后却透明的像素。

    v1.3 已知：thin 35743 / short 32043 / curl 8295 —— 窄尾盖不满 socket。
    这是「通向外部」的缺口，美术侧 repair_pockets 填不到，回归也查不出。
    """
    a = np.asarray(img.convert('RGBA').split()[3]) > 8
    m = body_mask(fur)
    if m.shape != a.shape:      # 缩放后的图按最近邻对齐 mask，避免广播错误
        m = np.asarray(Image.fromarray(m.astype(np.uint8) * 255).resize(
            img.size, Image.NEAREST)) > 127
    return int((m & ~a).sum())


if __name__ == '__main__':
    import fox_ecosystem_sim as M
    w = M.World(dict(M.TUNED_V3_PARAMS), 20261031)
    g = w.foxes[sorted(w.alive_ids)[0]].geno
    p = M.phenotype(g)
    print('表型:', p)
    spec = to_art(p)
    print('映射:', json.dumps({k: v for k, v in spec.items()
                              if not k.startswith('trait_')},
                             ensure_ascii=False, indent=1))
    im, used = _compose(spec)
    print('组装:', json.dumps(used, ensure_ascii=False))
    print('尾根缺口:', tail_root_holes(im), 'px')
