# 幻想小狐狸 美术素材返修单 v1.5（2026-11-02）

> **致素材生产任务空间**
> 本单基于 `Fox_Art_Delivery_v1.4_20261102.zip`（559 文件 / 56.7 MB）的**实机验收结果**
> 以及桌宠 v1.2 上线后的**真实使用反馈**。
> v1.4 验收已通过（R1–R7 全达标），本单不再处理 v1.4 缺陷，
> 而是处理两类**新需求**：
>
> 1. **分腿部件（L1，P0）**——v1.4 腿画在 `body_core` 一张位图里、无独立骨骼，
>    18 个动作（walk/run/jump/sit/stretch 等）没法真正动。桌宠散步时我们做了程序化
>    切图补救（`sim/legs.py`），实测在 Q 版短腿上**必然穿模、脱离主体**，不可用。
>    要让狐狸自然走路，必须美术出分腿部件。这不是优化，是让 18 个动作从「不可用」变「可用」。
> 2. **造型细腻度（Q1，P1）**——桌宠缩到 168px 后像素化突出、造型不够可爱。
>
> 另有 4 条承接自 v1.4 验收 / 动画数据体检的观察项（O1–O4），都是小修，建议同批出。
>
> 优先级：**P0 = 阻塞核心功能（走路），必须修；P1 = 观感问题，强烈建议修；P2 = 元数据与契约，顺手修。**

---

## 0. 一分钟摘要

| # | 级别 | 问题 | 一句话影响 | 涉及文件 |
|---|---|---|---|---|
| **L1** | **P0** | 四条腿画在 `body_core` 一张位图、无独立骨骼 | walk / run / jump / sit / stretch 等 **18 个动作不可用**；程序化切图补救在 Q 版短腿上必然穿模 | `body_core` + 新增 4 个腿部件 |
| **Q1** | P1 | 1024 源图缩到 168px 像素化突出；造型不够圆润可爱 | 桌宠默认尺寸下观感粗糙 | 全部件 2048 重绘 |
| O1 | P1 | v1.4 尾根缺口填的是半透明雾（alpha 均值 62–73），不是毛 | 短尾/细尾根部是一片淡毛色，不是「毛从身体长出来」 | `tail_short` / `tail_thin` |
| O2 | P2 | `eye_closed` 缺 mist_purple / haze_blue 两个毛色变体 | 这两个毛色的狐狸眨眼时眼睑毛色对不上 | `Expressions/eye_closed_*` |
| O3 | P2 | `ear_l_att` / `ear_r_att` / `tail` 三个插槽 anchor 全是 (660,450) | 复制粘贴遗留，照 anchor 定位附件的实现会错位 | `skeleton.json` |
| O4 | P2 | 附件命名带毛色与不带毛色混用 | 下游每家都要自己猜解析规则 | `animations.json` slot 值 |

**L1 是本单唯一阻塞项**；Q1 + O1 建议同批；O2–O4 顺手修。

---

## 1. L1（P0）分腿部件 —— 让 18 个动作从不可用变可用

### 1.1 现象

桌宠 v1.2 上线后，用户反馈「散步时腿不动，程序化补救后脚穿模、脱离主体，完全不自然」。

根因在素材结构：**四条腿和躯干画在同一张 `body_core` 位图里，像素连续，没有独立骨骼**。
`skeleton.json` 定义了 4 条腿骨（`hip_near` / `hip_far` / `shoulder_near` / `shoulder_far`，
每条 2 个关节），`animations.json` 的 walk/run/jump 等动作也驱动了这些骨骼——
但腿的像素在 `body_core` 里，骨骼驱动不了它们。

我方程序化补救（`sim/legs.py`）的做法：扫描 `body_core` 底部 alpha 找 4 条腿的 x 位置，
切成独立图层按四足步态摆动。**这个方法在 Q 版短腿上根本做不到自然**：

- 腿和躯干像素连续，切走腿后身体留缺口；
- 缺口填采样色（色块），腿摆动时和身体边缘不连续；
- 腿抬起时缺口露出填色，像身体被削掉一块；
- 幅度大到能看出走路（±12°）时腿脱离身体根部，幅度小（±6°）又看不出在动。

这不是幅度问题——降到 ±2° 也会穿，只是穿得少。**切图法在「腿身同图」的素材上是死路。**
证据：`fix-evidence-legs-v1.5.png`（程序化切图的穿模实拍，用户已确认「完全不自然」）。

### 1.2 影响范围

`animations.json` 共 36 个动作，其中 **18 个**驱动 `hip_* / foot_* / shoulder_* / paw_*` 或
需要腿独立变换：

```
walk  run  walk_fast  trot  sneak  jump  sit_down  lie_down  roll_over
stretch  scratch  play_bow  drag  drop  happy_bounce  shake_off  dig  kick
```

这 18 个现在全部退化成「只有尾巴和耳朵在动，身体和腿是静止贴图」。
其中 `walk` 是桌宠散步的核心动作，`sit_down` / `lie_down` 是睡眠链的必经动作
（虽然这两步的腿不动可以用整体 pelvis 下沉兜底，但不自然）。

### 1.3 需求规格

#### 1.3.1 骨骼锚点（已由 skeleton.json 定义，直接用）

四条腿的骨骼链（每条 2 个关节，Q 版短腿一节就够，不做踝/腕）：

| 腿 | 上段骨骼 | 上段 start（髋/肩） | 下段骨骼 | 下段 start（膝/肘） | side |
|---|---|---|---|---|---|
| 后腿·近侧 | `hip_near` | (430, 655) | `hip_near` 子 | (432, 780) | near |
| 后腿·远侧 | `hip_far` | (370, 650) | `hip_far` 子 | (382, 775) | far |
| 前腿·近侧 | `shoulder_near` | (700, 600) | `shoulder_near` 子 | (700, 750) | near |
| 前腿·远侧 | `shoulder_far` | (650, 595) | `shoulder_far` 子 | (648, 745) | far |

> near/far 是 3/4 正面视角下的近侧/远侧（不是严格的左右）。
> 当前 `body_core` 是正面偏 3/4 朝向，四条腿在底部从左到右大约：
> hip_far(370) → hip_near(430) → shoulder_far(650) → shoulder_near(700)。

#### 1.3.2 部件清单（新增 4 个腿部件 × 12 毛色 = 48 文件，或按方案 B 免）

**方案 A（首选：分毛色出腿部件）**

为每条腿出一个独立 PNG，文件结构：

```
assets/master/Legs/
  leg_hip_near_<coat>@1024.png     # 近侧后腿，pivot 在 (430,655)
  leg_hip_far_<coat>@1024.png      # 远侧后腿，pivot 在 (370,650)
  leg_shoulder_near_<coat>@1024.png# 近侧前腿，pivot 在 (700,600)
  leg_shoulder_far_<coat>@1024.png # 远侧前腿，pivot 在 (650,595)
```

- 12 个毛色各 4 件 = **48 个文件**（如果腿是纯色可以改成 1 件 + 运行时换色，见方案 B）；
- 每件 PNG 的 alpha 通道 = 这条腿的完整轮廓（从髋/肩到脚），背景全透明；
- pivot 点 = 对应骨骼的 start 坐标，画在 PNG 的像素原点上
  （即 PNG 左上角到 pivot 的偏移 = 骨骼 start 坐标，和现有 `ear_l`/`tail` 部件一致）；
- 腿的毛色、毛流、描边笔触沿用 `body_core` 的画法，保证接缝不可见；
- **远侧两条腿（far）可以画得稍暗一点**（3/4 视角的远侧自然有空气透视），
  但不要暗到和近侧色系脱节。

**方案 B（推荐：1 套腿 + 运行时换色）**

如果腿是纯色（没有复杂花纹），只出 **4 个母版腿部件**（用一个固定毛色画）：

```
assets/master/Legs/
  leg_hip_near@1024.png
  leg_hip_far@1024.png
  leg_shoulder_near@1024.png
  leg_shoulder_far@1024.png
```

我方运行时按 `coat` 用 `artmap._recolor_coat_fast` 换色（已有，单部件 < 20ms）。
花纹（stripes/tabby/spots）是否上腿由我方决定，美术不用出腿的花纹 mask。

**方案 B 的前提**：腿的明暗纹理是均匀的（不依赖毛色的局部 shading）。
如果不同毛色的腿有独立的毛流方向或高光位置，就只能走方案 A。
**请评估后告知选哪个。**

#### 1.3.3 body_core 镂空

`body_core` 当前包含躯干 + 四条腿。分腿后，**body_core 对应腿的区域要镂空**（alpha = 0），
让腿部件独立贴回时不叠色。

- 镂空范围 = 4 条腿的 alpha 轮廓外扩 2px（给接缝留余量，避免 1px 缝）；
- 镂空后 body_core 只剩躯干 + 头 + 尾根区（如果尾根还在 body_core 里的话）；
- **不要把身体下缘的毛流也切掉**——腿根以上的躯干轮廓保持完整，
  只切腿本身（脚 + 腿下段），髋/肩以上的躯干不动。

> 如果担心镂空后躯干下缘出现「悬空」感（腿根以上没有支撑），
> 可以在髋/肩位置留一小块 alpha 渐变（腿根绒毛），过渡到腿部件。
> 这和 v1.4 R1 尾根的「毛从身体长出来」是同一个思路。

#### 1.3.4 不需要改的

- `skeleton.json` 的骨骼定义**不用改**（腿骨已定义）；
- `animations.json` 的 walk/run 等动作数据**不用改**（腿骨通道已有）；
- `traits.json` 不用改（腿不是性状，是所有狐狸共有的结构）；
- 尾巴、耳朵、眼睛、花纹部件**不用改**。

### 1.4 验收标准

**L1 是 P0，验收用机器判据 + 目视双重卡：**

1. **部件完整性**：4 个腿部件 ×（12 毛色 或 1 母版）全部存在，
   `verify_legs.py`（我方新增）逐件 alpha bbox 与 pivot 检查通过；
2. **body_core 镂空**：镂空后 body_core 的 alpha 区域不再包含 4 条腿的像素，
   `body_core` 内容像素减少量 ≈ 4 条腿部件内容像素之和（±5%）；
3. **组装无叠色**：`render_kernel.render()` 组装后，腿部件与 body_core 在接缝处
   无可见色差（同一毛色下 RGB 差 < 8）；
4. **walk 动画**：`anim.render_frame(walk, t)` 在 t=0/0.25/0.5/0.75 四帧，
   腿部像素位置有可见变化（帧间差 > idle 的 3 倍）；
5. **目视**：出 `_walk_legs.png`——同一只狐（coat=orange）walk 四帧 1:1 并排 +
   2.8× 放大，腿摆动自然、身体下缘无穿模、无缺口、无重影。

### 1.5 我方配合

- 新增 `sim/verify_legs.py`：腿部件完整性 + pivot + 镂空对账；
- `anim.py` 的腿部 rig 代码（`sim/legs.py`）在分腿部件到位后**自动停用切图法**，
  改读独立腿部件按骨骼旋转（和现有 ear/tail 的 rig 方式一致）；
- `render_kernel.py` 的 `DEGRADE_RULES` 加一条：腿部件缺失时退回 `body_core` 整图
  （降级，不崩），`until` 版本写 1.5。

---

## 2. Q1（P1）造型细腻度

### 2.1 现象

桌宠默认显示尺寸 168px（源图 1024 缩到 168，每 6 个源像素挤到 1 个显示像素）。
用户反馈「造型不够细腻、不可爱、像素化有点突出」。

两个层面：

**像素化**是分辨率物理：1024 源图缩到 168，细节必然丢失。
我方已做 2× 超采样 + LANCZOS + 轻度锐化（PSNR 33dB），但**超采样只能让边缘更锐，
不能无中生有**。要更细腻，源图得提到 2048。

**造型不可爱**是美术设计本身：轮廓、五官、配色、Q 版比例。
代码只能换色（按基因型）、摆姿态，改不了造型。要更可爱需要重绘。

### 2.2 需求

#### Q1.1 源图分辨率 1024 → 2048

所有母版部件（`body_core` / `tail_*` / `ear_*` / `eye_*` / `pattern_*` / `special_*`）
从 1024 提到 **2048**。

- 不需要改画布比例（仍按现有 ASPECT）；
- 导出时同时出 2048 + 1024 两档（1024 给桌宠小尺寸用，避免缩太多；
  2048 给大尺寸 / 图鉴 / 静态展示用）；
- `skeleton.json` 的坐标不用改（骨骼坐标是逻辑坐标，和源图分辨率无关）。

> 如果 2048 全量重绘工作量太大，**可以只重绘 `body_core` + `ear_*` + `eye_*`**，
> 这三件是桌宠小尺寸下最影响观感的。尾巴和花纹可以后续。

#### Q1.2 造型迭代（方向性建议，不替原画师做决定）

以下是基于用户反馈和桌宠小尺寸特性的**方向性建议**，具体造型由原画师定：

| 方面 | 现状 | 建议方向 |
|---|---|---|
| 轮廓线 | 偏直、偏硬 | 更圆润，Q 版比例头身比可以再大一点（当前约 1:2，可以试 1:1.8） |
| 眼睛 | 单层高光 | 加双层高光（大光斑 + 小光点），让眼睛更「有神」 |
| 毛流 | 明暗纹理 std 15–70 | 尾根 / 耳根 / 身体边缘的毛流可以更柔和的渐变，减少「贴片感」 |
| 配色 | 12 色各自独立 | 稀释色（mist_purple / haze_blue）的明暗过渡可以更柔和，和基础色的色阶衔接 |

**关键**：造型迭代是主观的，**请先出 1–2 张风格探索稿（coat=orange 的 body_core + ear + eye）**，
我方在桌宠 168px 实尺寸下预览，确认方向后再全量重绘。
不要直接全量改完再交付，避免方向跑偏返工。

### 2.3 验收标准

- 源图 2048 全量（或 body_core + ear + eye 三件）出齐；
- 2048 缩到 168 后，与 1024 缩到 168 对比，PSNR 提升 ≥ 3dB
  （我方 `sim/probe_quality.py` 复跑）；
- 目视：出 `_quality_2048.png`——1024 vs 2048 同一只狐缩到 168 并排 4× 放大；
- 造型方向：1–2 张探索稿过目后再全量。

---

## 3. O1（P1）尾根雾填充实心度

### 承接 v1.4 验收报告 §2.1

v1.4 把 `tail_short` / `tail_thin` 的尾根缺口用 `alpha = 255·exp(-d/40)` 填了绒毛过渡，
**缺口归零、验收通过**。但填充区是「半透明雾」而不是「毛」：

| 尾型 | 区域 px | alpha 均值 | >200 占比 | 亮度 std（纹理） |
|---|---|---|---|---|
| tail_normal（参照） | 33,077 | **253.2** | **99.0%** | **70.9** |
| tail_short | 33,077 | **73.3** | 8.2% | 15.4 |
| tail_thin | 37,410 | **62.1** | 9.2% | 16.3 |

即短尾/细尾的尾根区在成品上是约 25% 不透明度的一片淡毛色，几乎无纹理。

**根因**：衰减长度 40 px 相对填充区尺度（约 180×180）太短，
`exp(-d/40)` 在 d>80 就归零，大片区域只剩 alpha 下限。

### 建议

- 衰减长度从 40 放到 **120–160**，或改成分段曲线（近端实心 → 远端在窗口边缘之外才衰减到 0）；
- 把 `tail_normal` 的高频毛流明暗按现行幅度搬进去，让 std 从 15 提到 **60+**；
- 不需要改结构，只改 `tail_short` / `tail_thin` 两件的填充区。

### 验收

- `tail_short` / `tail_thin` 填充区 alpha 均值 ≥ 200，>200 占比 ≥ 85%，亮度 std ≥ 50；
- 出 `_tail_fill_alpha.png`：short / thin / normal 三件填充区 alpha 热力图并排。

---

## 4. O2（P2）eye_closed 缺两个毛色变体

### 承接动画数据体检 §4.1

`Expressions/eye_closed_<coat>.png` 12 个毛色里缺 **mist_purple** 和 **haze_blue**
（v1.4 新增的两个稀释色）。

这两个毛色的狐狸眨眼时会退化到无毛色的 `eye_closed.png`，眼睑周围毛色对不上。

### 建议

补 `eye_closed_mist_purple.png` 和 `eye_closed_haze_blue.png`，
画法沿用其他 10 个毛色的 `eye_closed_<coat>.png`。

### 验收

`verify_anim_data.py` 的「eye_closed 毛色覆盖」检查从 10/12 变 12/12。

---

## 5. O3（P2）三个插槽 anchor 是复制粘贴遗留

### 承接动画数据体检 §4.2

| 插槽 | 当前 anchor | 所属骨骼 start | 应有 anchor |
|---|---|---|---|
| `ear_l_att` | (660,450) | ear_l (505,348) | **(505,348)** |
| `ear_r_att` | (660,450) | ear_r (762,346) | **(762,346)** |
| `tail` | (660,450) | tail_root (425,505) | **(425,505)** |

(660,450) 是 `head` 骨的中点——三个插槽的 anchor 都被填成了 head 的位置，是复制粘贴遗留。

**对我方无影响**（耳朵/尾巴是整张全画布部件，绕骨骼 start 旋转，不读插槽 anchor），
但照 anchor 定位附件的实现会错位。建议修。

### 验收

`skeleton.json` 三个插槽的 anchor 改为各自骨骼的 start。

---

## 6. O4（P2）附件命名带毛色与不带毛色混用

### 承接动画数据体检 §4.3

`animations.json` 的 slot 值有两种写法混在一起：

- 带毛色完整名：`eye_round_blue`（主眼件，在 `Eyes/`）
- 不带毛色裸名：`eye_closed` / `brow_angry_L` / `mouth_smile` / `blush`
  （表情件，在 `Expressions/`，多数带毛色变体）

我方已实现 `artmap.find_attachment()` 按「带毛色 → 裸名 → 主眼件」三档解析，0 缺失。
但下游每家都要自己猜，建议统一。

### 建议

二选一，**不要保持现状**：

- **选项 A（推荐）**：表情件统一带毛色后缀（`eye_closed_blue` 而非 `eye_closed`），
  与主眼件命名一致；
- **选项 B**：表情件统一不带毛色（`eye_closed`），由产品侧按 coat 拼接查找路径，
  `traits.json` 里标注「该附件有毛色变体」。

### 验收

`animations.json` 全部 slot 值遵循同一命名规则，`verify_anim_data.py` 附件命名检查通过。

---

## 7. 明确不做（避免过度返工）

- **R2 多尾根部碎片**：v1.4 验收结论「净效果 ≈ 0，结案不再返修」（见 v1.4 验收报告 §2.2）。
- **火焰纹亮斑 / 折耳拉伸 / eye_copper**：v1.4 已明确不动，沿用。
- **多尾 × long/fluffy/short/curl 组合变体**：仍搁置，不做。
- **Spine / DragonBones 骨骼蒙皮（LBS）**：桌宠 168px 下头部转 5° 只有 3px 位移，
  LBS 收益小于实现成本，不做。分腿部件用刚性旋转足够。
- **18 个需腿动作里除 walk 外的 run/jump/sit 等**：只要 L1 分腿部件到位，
  这些动作的骨骼通道已有，我方播放器自动支持，美术不用单独处理。

---

## 8. 交付物清单（Definition of Done）

1. **L1**：4 个腿部件 ×（12 毛色 或 1 母版，按 1.3.2 方案 A/B 选定）+ 镂空后的 `body_core`；
2. **Q1**：2048 源图全量（或 body_core + ear + eye 三件）+ 1–2 张造型探索稿（先过目）；
3. **O1**：修好的 `tail_short` / `tail_thin`（填充区实心化）；
4. **O2**：`eye_closed_mist_purple.png` / `eye_closed_haze_blue.png`；
5. **O3**：修好的 `skeleton.json`（三个插槽 anchor）；
6. **O4**：修好的 `animations.json`（附件命名统一，按选定方案）；
7. **回归**：`run_batch.py` 全量 PASS，并新增第 9 节的腿部件检查；
8. **验收图**：`_walk_legs.png`（L1）、`_quality_2048.png`（Q1）、`_tail_fill_alpha.png`（O1），
   放入 `09_Review/`；
9. **工作日志**：`10_Worklog/` 追加，记录 L1 选了方案 A 还是 B、Q1 的造型方向。

---

## 9. 建议补进回归的检查（腿部件专项）

v1.4 的回归漏掉了 R1 尾根缺口（缺口通向外部，连通域仍是 1）。v1.5 的腿部件有类似的陷阱：
**腿部件和 body_core 镂空如果对不齐，组装后腿根会露缝或叠色，但单部件自检看不出来。**

```python
# 检查 L1-A：腿部件 pivot 与骨骼 start 对账
for leg_name, bone_start in [('hip_near',(430,655)), ('hip_far',(370,650)),
                             ('shoulder_near',(700,600)), ('shoulder_far',(650,595))]:
    img = Image.open(f'Legs/leg_{leg_name}@1024.png')
    # pivot 应在 PNG 的 (bone_start[0], bone_start[1]) 像素位置
    # 即 PNG 左上角到 pivot = 骨骼 start（和 ear_l 部件一致）
    assert pivot_correct(img, bone_start), f'{leg_name} pivot 错位'

# 检查 L1-B：body_core 镂空区 = 4 条腿部件 alpha 的并集
core = np.asarray(Image.open('Body/body_core_orange@1024.png').split()[3])
leg_union = sum(leg_alpha for leg in legs)  # 4 条腿 alpha 合并
# 镂空区（core 里 alpha=0 但腿部件 alpha>0 的区域）应 ≥ 腿部件 alpha 的 95%
hollow = (core < 8) & (leg_union > 8)
coverage = hollow.sum() / (leg_union > 8).sum()
assert coverage > 0.95, f'body_core 镂空未覆盖腿部件 {coverage:.0%}'

# 检查 L1-C：组装无叠色（同毛色下腿与身体接缝 RGB 差 < 8）
assembled = render(coat='orange', leg='hip_near', ...)
seam_region = assembled[leg_root_bbox]
assert seam_rgb_diff(seam_region) < 8, '腿与身体接缝色差过大'
```

检查 L1-B 是关键：**腿部件和 body_core 镂空必须对齐**，否则要么露缝（镂空太大）
要么叠色（镂空太小）。这条在单部件自检里看不出来，必须组装后查。

---

## 10. 我方怎么验收

拿到 v1.5 后，同一个环境、同一套脚本重跑：

1. **L1 腿部件**：`verify_legs.py`（新增）+ `verify_anim.py` walk 四帧帧差 +
   目视 `_walk_legs.png`；
2. **Q1 清晰度**：`probe_quality.py` 2048 vs 1024 PSNR 对比 + 目视 `_quality_2048.png`；
3. **O1 尾根**：`probe_r1_alpha.py` 复跑，alpha 均值 ≥ 200；
4. **O2 eye_closed**：`verify_anim_data.py` 毛色覆盖 12/12；
5. **O3/O4**：`verify_anim_data.py` anchor + 命名检查；
6. **真实种群 36 只批量渲染**：walk 动画每只 4 帧，无穿模、无叠色、无缺口。

通过标准就是本单第 1–6 节各自的验收条款，不额外加码。

---

## 附：证据图

| 文件 | 内容 |
|---|---|
| `fix-evidence-legs-v1.5.png` | 程序化切图法（`sim/legs.py`）在 walk 4 帧上的穿模实拍——腿脱离身体根部、缺口填色色块可见 |
| `fix-evidence-pixel-v1.5.png` | 1024 源图缩到 168px 的像素化对比 + body_core 腿部位置标注（4 条腿的 x 峰与髋/肩锚点） |

两图均用 v1.4 交付包在我方渲染路径上生成，除标注文字外未改像素。
