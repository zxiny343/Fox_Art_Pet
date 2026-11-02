# 表型 → 美术部件 映射规范 v1（可执行版）

> 资产基准：`Fox_Art v1.3`（2026-11-01 交付，520 文件 / 52.9 MB）
> 实现：`sim/artmap.py` ｜ 自检：`sim/verify_artmap.py`（**69 项全通过**）
> 渲染样例：`docs/fox-render/` ｜ 日期：2026-11-01

---

## 0. 这一层是干什么的

设计稿有 22 个遗传位点，美术包有 335 个独立部件。两者之间需要一层胶水：把
`phenotype()` 输出的表型字典，翻译成组装器能吃的部件名，并直接渲染成 PNG。

```
基因型 dict
   │  fox_ecosystem_sim.phenotype()
   ▼
表型 dict  { color, tails, hair_len, curl, ear, ear_size, eye, eye_shape, ... }
   │  artmap.to_art()
   ▼
组装参数  { coat, fur, tail, ear, eye_l, eye_r, pupil, pattern, special[] }
   │  artmap._compose()
   ▼
PNG（1024 / 512 / 256）
```

三层职责严格分离，**桌宠、基因面板、批量出图都必须走这一个函数**，不允许各处
各写一遍——这是 22 位点系统唯一可行的维护方式。

### 对外接口

```python
import artmap as AM

AM.to_art(pheno)              # 表型 → 组装参数（纯数据，不碰磁盘）
AM.render(pheno, size=512)    # 表型 → PIL Image
AM.render_geno(geno, size=512)# 基因型 → PIL Image（内部调 phenotype）
```

`to_art()` 的返回除了部件名，还带 `notes`（降级/覆盖说明）和 `missing`
（无素材支撑的位点）——**任何映射损失都必须留痕，不许静默丢弃**。

---

## 1. 完整映射表

### 1.1 毛色（A × D × W，9 种可见色 + 3 个突变预留）

| 基因型 | 表型 | 部件 | 依据 |
|---|---|---|---|
| `ww` | 雪绒白 | `coat_white` | 上位，完全掩盖 A/D/P |
| `A⁺_ D_` | 赤橙 | `coat_orange` | |
| `A⁺_ dd` | 奶油金 | `coat_caramel` | 稀释 |
| `As_ D_` | 霜灰 | `coat_grey` | |
| `As_ dd` | 淡银蓝 | `coat_blue` | 稀释 |
| `Av_ D_` | 幽夜紫 | `coat_purple` | |
| `Av_ dd` | 淡雾紫 | `coat_mist_purple` | 稀释（v1.3 新增素材） |
| `Ab_ D_` | 墨黑 | `coat_black` | |
| `Ab_ dd` | 雾霭蓝 | `coat_haze_blue` | 稀释（v1.3 新增素材） |
| 突变 `A^sk` | 樱粉 | `coat_sakura` | §8.1.1 突变专属 |
| 突变 `A^mt` | 薄荷 | `coat_mint` | 同上 |
| 突变 `A^og` | 曜金 | `coat_obsidian_gold` | 同上 |

### 1.2 毛质（L1+L2 累加 0–4，K 卷毛覆盖）

| 累加档 | 部件 | 说明 |
|---|---|---|
| 0–1 | `fur_short` | 用 `fox_base_<coat>_q4` 母版 |
| 2–3 | `fur_mid` | 用 `fox_fur_mid_blue_q4` + 换色 |
| 4 | `fur_long` | 用 `fox_fur_long_blue_q4` + 换色 |
| `K_` | `fur_curly` | 覆盖毛长，且尾巴自动切卷尾 |

> ⚠️ 5 档压到 3 个部件，0–1 与 2–3 是合并的。美术侧只有 short/mid/long/curly 四件。

### 1.3 尾型（两个维度：数量 + 形态）

**数量优先**（Tn1+Tn2 累加 + V 九尾）：

| 尾数 | 部件 |
|---|---|
| 1 | 走形态逻辑（见下） |
| 2 / 3 / 4 / 5 | `tail_twin` / `tail_triple` / `tail_quad` / `tail_quint` |
| 9（`V_`） | `tail_nine` |
| 6–8（不可能出现） | 回退 `tail_nine` 并记 notes |

**单尾形态**（优先级：K > 尾长 > 蓬松度）：

| 基因 | 部件 | 实测形态依据 |
|---|---|---|
| `K_` | `tail_curl` | K 多效（§8.1.1），尾尖卷曲 306×179 |
| `Tl` 2 显性 | `tail_long` | 331×246，明显更长 |
| `Tl` 0 显性 | `tail_short` | 232×119，明显更短 |
| `Tl` 1 + `Tf` | `tail_fluffy` | 340×245，蓬松球状 |
| `Tl` 1 + `tf` | `tail_thin` | 184×351，细长下垂 |

> `tail_normal`（355×208，标准件）**没有基因出口**，只作为美术基准件与回退值。
> 这是刻意的：5 个形态件正好覆盖 Tl(3) × Tf(2) = 6 组合中的 5 个，唯一合并是
> 「长」档的蓬/纤两态（长尾本身毛量大，视觉上分不出）。

### 1.4 耳型（Er 3 态 × Ez 3 档 → 6 个部件）

| 条件 | 部件 | 备注 |
|---|---|---|
| `St_` | `ear_star` | 多效：覆盖 Er/Ez（§8.1.1） |
| `Erf` | `ear_fold` | 忽略 Ez（无折耳大小变体） |
| `ErP` | `ear_pointed` | 忽略 Ez（无尖耳大小变体） |
| `ErR` + Ez=0 | `ear_small` | |
| `ErR` + Ez=1 | `ear_round` | |
| `ErR` + Ez=2 | `ear_large` | |

> 9 种 Er×Ez 组合正好填满 5 个非星耳部件，语义自洽。

### 1.5 眼睛（Ef 剂量 3 档 × Ey 4 色 + Ht 异色）

| 维度 | 取值 | 部件 |
|---|---|---|
| 眼型 `Ef` | 0 / 1 / 2 显性 | `sleepy` / `almond` / `round` |
| 眼色 `Ey` | EyG / EyC / EyB / EyV | `gold` / `cyan` / `blue` / `purple` |
| 异色 `Ht` | `Ht_` | 右眼换 Ey 显性序列的**下一色** |

部件文件名格式 `eye_<shape>_<color>.png`，左右眼**分别指定**（`assemble` 只支持
左右同眼，异色瞳必须自己画）。

> `Ht` 的第二色是确定性规则（不是随机），保证同一只狐狸每帧渲染结果一致。

### 1.6 斑纹与特殊层

| 位点 | 表型 | 部件 / 处理 |
|---|---|---|
| `P` | `PT` / `Ps` / `Pg` / `p` | `pattern_tabby` / `stripes` / `spots` / `solid` |
| `Fl` | `Fl_` | `pattern_flame`，**覆盖** P 位点（单槽位限制） |
| `G` | `G_` | 程序化 `add_glow()`（美术未交付 `special_glow`） |
| `Ha` | `Ha_` | 程序化 `add_halo()`（美术未交付 `special_aura`） |
| `St` | `St_` | 星耳 + 星瞳 + 程序化 `add_star_mark()`（未交付 `special_star_mark`） |

### 1.7 无素材支撑的位点（记录在 `missing`，明确不表现）

| 位点 | 情况 |
|---|---|
| `Tp` 耳尖色 | 无贴花素材 |
| `In` 内耳色 | 由 `colorways.json` 的 `innerEar` 字段**统一**覆盖，不随基因变化 |
| `Tw` 尾尖色 | 无贴花素材 |

---

## 2. 三个缺口修正（本轮硬价值）

映射层的价值不只是"翻译"，还顺手补掉了三个会让功能直接失效的集成缺陷。

### 2.1 ★ 非短毛的狐狸会丢掉毛色（P0）

`run_assemble.make_core()` 在 `fur != 'short'` 时直接取
`fox_fur_<fur>_blue_q4@1024.png`，**把 coat 参数完全丢弃**：

```python
if fur == "short":
    src = fox_base_%s_q4          # 用 coat
else:
    src = fox_fur_%s_blue_q4      # coat 被忽略！
```

实测：`orange + long` → 核心是 `fox_fur_long_blue`，平均 RGB **(104, 133, 158) 蓝灰**。
也就是**所有长毛/中毛/卷毛狐狸都变成霜蓝色**，L1/L2 与 K 三个位点等于废掉。

修正：先按 blue 切核心，再用 LOCK-F 的 `recolor_coat` 换到目标毛色。实测色相
偏差 ≤ 0.026（0 = 完全一致），肉眼无差。

```python
core, src = _ORIG_MAKE_CORE('blue' if fur != 'short' else coat, fur)
if fur != 'short' and coat != 'blue':
    core = recolor_coat(core, cw['blue'], cw[coat])
```

### 2.2 `eye_narrow` 不存在，实际素材是 `eye_sleepy`

`traits.json` 声明 `eyeShape.values = [eye_round, eye_almond, eye_narrow]`，
但 `assets/master/Eyes/` 里从来没有 `eye_narrow.png`——实际是 `eye_sleepy`（细长困眼）。
映射层做别名 `narrow → sleepy`。

### 2.3 `fur_medium` 与文件 `fur_mid` 不一致

`traits.json` 写 `fur_medium`，母版文件名是 `fox_fur_mid_blue_q4`。
映射表用 `mid`，输出 `trait_fur` 时再拼成 `fur_medium` 供面板显示。

---

## 3. 程序化特殊层（补美术未交付的三件）

美术侧 `traits.json` 声明了 `special_glow` / `special_aura` / `special_star_mark`
三个值，但 `assets/master/` 下**没有任何对应文件**。目前用程序化合成兜底：

| 层 | 实现 | 位置依据 |
|---|---|---|
| `add_glow()` | alpha 高斯模糊 + 暖色垫底 | 整只 |
| `add_halo()` | 椭圆环 + 柔化描边 | 中心 (640, 128)：`body_core` bbox y 150–927，耳顶 y=166，光环必须压在其上 |
| `add_star_mark()` | 三颗大小不一的五角星 + 柔光，clip 到身体 alpha | 胸腹侧 (566,636)/(496,706)/(628,700) |

三者都是**幂等、无状态**的，可以任意叠加。

---

## 4. 自检（`python sim/verify_artmap.py`）

69 项断言，分四段：

| 段 | 内容 | 结果 |
|---|---|---|
| A 表型层逐维穷举 | 22 位点每个可取值都能映射到合法部件、素材文件确实存在 | 47 项 ✓ |
| A10/A11 值域与对账 | 432 组交叉组合，输出值必须可解析；素材 vs 机读数据全量对账 | 3 项 ✓ |
| D 换色保真 | 4 毛色 × 3 非短毛，色相与同色短毛一致（均值 Δ=0.006） | 13 项 ✓ |
| B/C 整链渲染 | 16 组随机表型渲染，连通性、出血、尾根缺口 | 6 项 ✓ |

关键指标：**主体最大岛占比最低 100%**（无碎片）、**0 组出血**。

已知不合格项（美术侧遗留，见 §5）：`tail_thin 35743 px` 尾根缺口。

---

## 5. 实测发现的美术侧缺陷（需反馈给素材生产）

按严重度排序，全部有量化依据。

| # | 问题 | 证据 | 影响 |
|---|---|---|---|
| **A1** | `ear_large` 的内容比 `ear_small` **还小 2.7 倍** | `ear_large` 内容 124×100 / 6054 px，`ear_small` 128×166 / 16344 px，且 large 的 topY=235 vs 其他 169 | 「大圆耳」视觉上最小，Er/Ez 组合语义反转。v1.2 起就是这样，v1.3 未修 |
| **A2** | 尾根缺口：`tail_thin` 35743 px、`tail_short` 32043 px | 「母版轮廓内、组装后却透明」的严格判据 | `thin` 是 Tf 的纤态，出现率约 25%，不修则该性状不可用 |
| **A3** | `traits.json` 的 values 漏登记 4 项 | `coat` 缺 `mist_purple`/`haze_blue`（colorways 有 12 色，values 只列 10）；`eyeColor` 缺 `eye_cyan`；`eyeShape` 写 `eye_narrow` 但素材是 `eye_sleepy`；`fur` 写 `fur_medium` 但文件是 `fur_mid` | 只信机读数据的程序会以为这些色/型不存在 |
| **A4** | 花纹遮罩覆盖率偏低 | `stripes`/`tabby` 在躯干只覆盖 22%，`spots` 9% | 128–256px 桌宠尺寸下花纹只剩淡淡纹理 |
| **A5** | `special_glow`/`special_aura`/`special_star_mark` 声明未交付 | `traits.json` 有值，`assets/master` 无文件 | 已用程序化合成兜底 |
| **A6** | `run_assemble.ORIG_EAR_H` 未定义 | 第 219 行引用，全文件无赋值 | 一旦走到 legacy 耳朵分支（非 1024 画布件）就 `NameError`，目前被"全部 1024 对齐"掩盖 |

---

## 6. 顺带发现：默认频率让外观过于单调

36 只真实种群渲染后发现：**一半以上是「卷毛 + 双尾 + 尖耳 + 赤橙」**。
量化（12 种子 × 5 年，只统计不渲染）：

| 方案 | 唯一外观 | 毛色熵 | 毛质熵 | 尾型熵 | 耳型熵 | 世代 | 近交 F |
|---|---|---|---|---|---|---|---|
| 基线 v0.6 | 27.4 | 2.04 | **1.36** | 2.33 | 1.37 | 30.3 | **0.082** |
| **只把 K 从 0.30 降到 0.12** | 27.5 | 2.04 | **1.65** | 2.38 | 1.37 | 30.3 | **0.082** |
| 只改 K + Er 均分 | 29.8 | 1.92 | 1.65 | 2.63 | 1.76 | 32.5 | 0.130 |
| 只改 A/D（稀释增多） | 27.0 | **2.49** | 1.41 | 2.34 | 1.67 | 30.2 | 0.105 |
| 全改 | 30.8 | 2.72 | 1.62 | 2.36 | 1.92 | 29.9 | 0.132 |

**关键发现：调 K 频率是零代价的。** 12 个种子的逐种子 F 值**完全相同**
（0.06 0.09 0.10 0.03 0.14 0.04 0.09 0.12 0.08 0.10 0.07 0.07）——
证明 K 位点与生态适应度完全解耦，只影响观感。毛质熵从 1.36 → 1.65（+21%）。

其余位点（Er、A、D）参与适应度，改动会把近交 F 从 0.082 抬到 0.13（+59%），
是"多样性与遗传健康"的权衡项，不建议默认启用。

> 建议：采纳「K 0.30 → 0.12」一条（免费），其余作为可选难度项。
> 已实现 `_freq_override` 参数支持局部覆盖创始频率，生态参数一字不动。

---

## 7. 用法

```bash
cd sim

# 单只渲染
python artmap.py

# 映射层自检（69 项）
python verify_artmap.py

# 真实种群批量渲染
python render_population.py --years 5

# 表型图谱
python render_atlas.py

# 外观多样性诊断
python diversity.py
```

产物：

```
docs/fox-render/
  fox-FX-0xxx.png        每只 512px
  _population.png        36 只拼版（带毛色/毛质/尾型/耳型标注）
  population.json        每只的组装参数 + notes + missing + 尾根缺口
  _atlas_01_毛色与毛质.png
  _atlas_02_尾型.png
  _atlas_03_耳型与眼睛.png
  _atlas_04_斑纹与特殊层.png
```

---

## 8. 环境注意

- **必须用系统 Python 3.10**（`E:/SoftWare/python3.10/python.exe`）。托管 3.13
  缺 pillow/numpy/scipy。
- 资产目录支持多版本共存，按版本号自然排序取最新（`v1.10` 排在 `v1.9` 之后），
  可用环境变量 `FOX_ART_ROOT` 指定。
- 不修改 `Fox_Art/tools/` 下任何文件，全部用包装 + 运行时补丁，
  美术升级不会冲突。
