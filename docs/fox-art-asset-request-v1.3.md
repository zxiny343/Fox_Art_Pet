# 幻想小狐狸 美术素材补做任务单 v1.3（2026-11-01）

> **致素材生产任务空间**：本单是 Fox_Art v1.2 交付包的**增量补做订单**。
> 你无需了解遗传系统的细节，只需按本单的命名、规格、验收标准产出素材。
> 所有新素材必须与 v1.2 交付包（`Fox_Art_Delivery_v1.2_20261101.zip`）的现有规范兼容。

## 0. 背景与硬约束（务必先读）

v1.2 交付包的 LOCK 项继续有效，新素材一律遵守：

- **母版 1024×1024**，全画布 (0,0) 对齐，禁止为对齐包络而缩放部件（包络 v1.2：body_core bbox 统一为 (189,150)-(877,928)，**耳朵与尾巴允许突破包络**）。
- 图层顺序自底向上：`Tail_Base → Tail → Body_Core → Pattern → Ear_L/R → Eye_L/R`（尾巴在身体下层，socket 补色机制不变）。
- 描边使用自适应深色，**不得使用纯黑**（唯一例外：black / obsidian_gold 配色）。
- 四足姿态、既有笔刷与毛流风格不变；新部件要能过 `run_batch.py` 回归（单连通域 / 不出血 / 破洞 0）。
- **LOCK-G 不变：美术侧不定义任何显隐性/遗传概率。** 你只交素材与元数据。
- 文件命名：小写蛇形，母版带 `@1024` 后缀的沿用现有规则（尾巴/部件类现有文件有不带后缀的，按下文指定名称**原样使用**，不要自行改名）。
- **不要修改、重绘或重导任何 v1.2 已有文件**；新增内容全部以新文件落盘。

## 1. P0 —— 多尾素材（最高优先级，共 4 个部件 + 元数据）

**为什么急**：尾数（1→5）与九尾是产品侧已验证的**核心可见进化信号**，目前只有 `tail_normal`（1尾）与 `tail_twin`（2尾），3/4/5/九尾完全空缺。

**做法（不需要新出 AI 图）**：以 `tail_normal.png` 为基础形，**程序化多分支复制**——v1.2 的 `tail_twin` 就是用 `tail_root` 分叉方案做的（`traits.json` 里 `specialHandling.tail_twin = {branchCount:2, segmentsPerBranch:3, branchAngleDeg:28}`），本次是它的直接推广。分叉点统一在 socket 锚点 `tail_root = (425, 505)`。

| 新文件 | 分支数 | 各分支角度（度，0=正中，负左正右） | 骨骼元数据 |
|---|---|---|---|
| `assets/master/Tails/tail_triple.png` | 3 | -28, 0, +28 | branchCount 3, segmentsPerBranch 3 |
| `assets/master/Tails/tail_quad.png` | 4 | -28, -14, +14, +28 | branchCount 4, segmentsPerBranch 3 |
| `assets/master/Tails/tail_quint.png` | 5 | -28, -14, 0, +14, +28 | branchCount 5, segmentsPerBranch 3 |
| `assets/master/Tails/tail_nine.png` | 9 | -56, -42, -28, -14, 0, +14, +28, +42, +56（扇形展开） | branchCount 9, segmentsPerBranch 3 |

要求：

1. 外侧分支可**略缩短、略细化**（参考真实九尾狐插画的层次），但笔刷、毛流、描边规则与 `tail_normal` 一致；分支间不得有透明缝、不得糊成一团。
2. 九尾允许明显突破包络（tail 本就在 allowOverflow 名单里），但根点必须落在 (425,505)。
3. `tail_base_<coat>@1024.png` **不需要改**（它已 100% 覆盖 socket 并外扩 3px）。
4. 元数据同步更新：
   - `01_Data/traits.json` → `tail.values` 追加 4 个 id；`boneSegments` 与 `specialHandling` 按上表补齐；
   - `assets/master/Tails/_tails_meta.json` 同步登记；
   - `01_Data/animations.json` 中尾巴相关动作，按 `segmentsPerBranch=3` 为新尾型补骨骼关键帧（可整体复用 twin 的逐分支摆动参数起步）。
5. 验收图：3/4/5/9 尾 × 至少 3 个毛色（blue / orange / purple）各组装 1 只，拼一张对照表 `_tail_counts.png`。

## 2. P1 —— 两个稀释毛色（配色板 + 全套派生）

D 位点稀释系目前只覆盖了 caramel、blue 两个淡色，缺以下两个：

| coat id | 中文名 | 说明 | 参考基色（可调） |
|---|---|---|---|
| `mist_purple` | 淡雾紫 | purple 的稀释态：更浅、更灰 | base `#CDBDE8` / shade `#AF9BD0` / light `#E4D9F5` / belly `#F5F0FC` / outline `#5E4A80` |
| `haze_blue` | 雾霭蓝 | black 的稀释态：低饱和蓝灰 | base `#93A9C6` / shade `#6E87A8` / light `#BCCFE4` / belly `#E3ECF6` / outline `#3D5670` |

要求：

1. `01_Data/colorways.json` 追加两个完整调色板条目（base/shade/light/belly/innerEar/nose/outline 七字段齐全，innerEar/nose 与现有风格一致；**outline 不得纯黑**）。
2. 生产流程与现有 9 个非母版配色一致：以 blue 母版跑 `run_coat_colors.py` 色相映射 + 手工修正。
3. 每个新配色产出：`tail_base_<coat>@1024.png`、全套 512/256 导出。
4. 验收图：两个新配色各组装 1 只标准件（normal 尾 / pointed 耳 / round 眼），与 purple、black、blue 并排对照 `_new_coats.png`，确认「淡雾紫 ≠ purple」「雾霭蓝 ≠ blue、≠ grey」肉眼可区分。

## 3. P1 —— 火焰纹叠加层（1 个花纹 + 混合规则）

- 新文件 `assets/master/Patterns/pattern_flame_mask@1024.png`：火焰纹理遮罩，建议沿**背脊 → 尾尖**分布，额头不上脸（参考 spots 的遮罩分区思路）。
- 混合方式：仿 `special_glow` 的加法/滤色系叠加，颜色随毛色自动取 `light` 色（不需要逐色出图）；深色毛（black/obsidian_gold）上必须仍清晰可见。
- `traits.json` → `pattern.values` 追加 `pattern_flame`。
- 验收图：火焰纹 × orange / black / white 三只对照 `_pattern_flame.png`。

## 4. P2 —— 零散部件（**3 项**，可与 P0/P1 同批交付）

| 项 | 新文件 | 说明 |
|---|---|---|
| 虎斑（与条纹区分） | `assets/master/Patterns/pattern_tabby_mask@1024.png` | 现有 `pattern_stripes` 是连续纵纹；虎斑做**断点/碎横纹**。两者要能并排区分。`traits.json` 的 pattern.values 追加 `pattern_tabby`。 |
| 折耳 | `assets/master/Ears/ear_fold_L.png` + `ear_fold_R.png` | 耳尖向前/向下折叠，轮廓体量接近 `ear_small`；requiresPair 规则不变。`traits.json` ear.values 追加 `ear_fold`。 |
| 细尾 | `assets/master/Tails/tail_thin.png` | 蓬尾的反义：细、直、毛量少；boneSegments 2。`traits.json` tail.values 追加 `tail_thin`。 |

> **更正（2026-11-01）**：原单里的「铜瞳 `eye_copper`」**撤下，本次不做**。
> 经核对，遗传侧眼色 4 态是「金 / 青 / 蓝 / 紫」（见设计稿 §2.1），v1.2 的 `eye_cyan` 已覆盖青瞳，
> 遗传侧并不存在铜瞳。如有余力可自愿补做 `eye_copper` 作为留白素材，但不计入验收。

## 5. P3 —— 暂缓项（本单**不要求**交付，仅备案）

掌纹 Tp、趾长 In、尾尖 Tw 三个细节性状暂不出图，后续可能用运行时小贴花实现。若你有低成本方案（如 3 张 256px 贴花），可作为可选项附交，但不计入验收。

## 6. 交付物清单（Definition of Done）

1. 上述 P0–P2 全部新文件（母版 1024 + 512/256 导出，命名与本单完全一致）。
2. 更新的机读数据：`traits.json`、`colorways.json`、`animations.json`、相关 `_meta.json`。
3. 回归：`run_batch.py` 全量 PASS（含新部件的组装组合至少新增：4 种多尾 × 3 毛色、2 个新配色标准件、火焰纹 × 3 毛色、虎斑/折耳/细尾各 1 组）。
4. 验收图：`_tail_counts.png`、`_new_coats.png`、`_pattern_flame.png`、P2 三项各 1 张，放入 `09_Review/`。
5. 工作日志：追加一份 `10_Worklog/` 日志，记录分叉参数、配色映射的色相偏移量、踩坑。

## 7. 明确不做（避免返工）

- 不新出 AI 原始图（P0 多尾 = 程序化分叉；新配色 = 色相映射管线）。
- 不改 envelope v1.2、body_core、socket、PSD 结构。
- 不动 v1.2 任何已有文件的像素与元数据（追加条目除外）。
- 不为多尾做「每个尾型 × 每个尾数」的全组合——本次只做 normal 形制的多尾。
  「多尾 × long/fluffy/short/curl」的组合变体产品侧已拍板**先搁置、预留升级**：
  后续若补，沿用本次分叉管线扩展即可，因此**本次不需要为它预留额外文件或改结构**。
- 不做铜瞳 `eye_copper`（已撤下，原因见第四节更正框）。
