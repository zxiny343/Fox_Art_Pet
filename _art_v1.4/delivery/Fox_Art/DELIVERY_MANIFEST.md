# 幻想小狐狸 · 桌宠美术资产包 —— 交付清单

- **版本**：v1.4（阶段 1–4 全交付 + v1.4 返修 R1–R7）
- **打包日期**：2026-11-02 10:18
- **根目录**：`Fox_Art/`
- **文件总数**：559 个（65.7 MB，未压缩）
- **画布规范**：1024×1024 RGBA 母版，原点左上；导出档 512 / 256；全画布对齐，程序零错位

---

## 1. 这个包里有什么

| 目录 | 内容 |
|---|---|
| `00_Spec/` | 10 份规范文档（总规范、部件依赖矩阵、配色性状、技术交接、包络 v1.2、阶段 4 动画规范、**v1.4 返修回执**…） |
| `01_Data/` | 机读数据：锚点 v3.0、12 套配色、性状字典、**`_meta.json` values 对账表**、拆分区域、骨骼树、36 动作、10 表情、tail socket |
| `assets/master/` | 母版资产 286 个 PNG（Base / Parts / Tails / Ears / Eyes / Patterns / **Special** / Expressions） |
| `assets/export_512`、`export_256` | 可直接进引擎的两档导出 |
| `assets/preview` | 预览图 |
| `assets/source/` | 分层可编辑 PSD（8 层） |
| `tools/` | 全部生产脚本（抠图 / 换色 / 拆分 / 组装 / 自检 / 打包） |
| `09_Review/` | 验收对照图（拼版、表情表、骨骼图、**v1.4 五张返修验收图**） |
| `10_Worklog/` | 逐阶段工作日志与踩坑记录（含 **v1.4 返修日志**） |
| `history/` | 阶段过程中的 AI 出图与中间版本 |

### 资产计数

| 部件目录 | PNG 数 |
|---|---|
| `Base/` | 16 |
| `Body/` | 12 |
| `Ears/` | 12 |
| `Expressions/` | 178 |
| `Eyes/` | 27 |
| `Head/` | 0 |
| `Limbs/` | 0 |
| `Parts/` | 8 |
| `Patterns/` | 7 |
| `Special/` | 3 |
| `Tail/` | 0 |
| `Tails/` | 23 |
| `assets/export_512/` | 54 |
| `assets/export_256/` | 54 |
| `assets/preview/` | 7 |
| `assets/source/` | 1 |

### 遗传性状规模

- 毛色 **12** 套（含 obsidian_gold 的 points 规则、v1.3 新增 2 个稀释色）
- 耳型 6 / 尾型 11 / 眼色 8 / 眼型 3 / 瞳孔 3 / 毛发 4 / 花纹 7
- 尾型骨段数：tail_normal=3, tail_long=5, tail_fluffy=3, tail_short=2, tail_curl=4, tail_twin=3, tail_triple=3, tail_quad=3, tail_quint=3, tail_nine=3, tail_thin=2
- 组合数约 **数百万级**（程序随机，美术侧不负责概率）

### v1.4 返修摘要（R1–R7 全部关闭）

| 单号 | 内容 | 结果 |
|---|---|---|
| R1 P0 | 短/细尾尾根缺口 | 根部绒毛过渡，32,043 / 35,743 → **0**（3 毛色） |
| R2 P1 | 多尾根部描边叠影 + 白缝 | 根区合形 + 统一毛流场，110–160px 羽化 |
| R3 P1 | 大耳反而最小 | round 母本重绘，6,054 → **31,740px**，比值 1.504 |
| R4 P1 | 花纹覆盖偏低 | stripes 47.1% / tabby 48.0% / spots 29.3% |
| R5 P1 | 3 个 special 有声明无文件 | 已补 glow / aura / star_mark（+ 双档导出） |
| R6 P2 | `traits.values` 4 处漏登记 | 已补 3 项 + 统一 `fur_medium` 命名，新增 `_meta.json` 对账表 |
| R7 P2 | `ORIG_EAR_H` 未定义 | `run_assemble.py` 第 43 行补定义 |

逐条改动行号、验收数值与判定口径见 `00_Spec/10_v1.4_返修回执.md`；过程与踩坑见 `10_Worklog/2026-11-02.md`。

### 动画准备

- 骨骼树：**20 骨 + 9 插槽**（`01_Data/skeleton.json`，坐标取自 v3.0 实测锚点）
- 动作库：**36 个**（30fps，逐骨骼通道关键帧，分 base/add/face 三层）
- 表情库：**10 种**（眼 × 眉 × 嘴 × 腮红，附件切换实现）

---

## 2. 目录结构

```
Fox_Art/
├── 00_Spec/  (10 文件, 0.08 MB)
    └── 10 个文件
├── 01_Data/  (10 文件, 1.95 MB)
    └── 10 个文件
├── 09_Review/  (45 文件, 16.22 MB)
    └── 45 个文件
├── 10_Worklog/  (2 文件, 0.03 MB)
    └── 2 个文件
├── assets/  (410 文件, 46.94 MB)
    ├── export_256/  (54 文件, 1.80 MB)
        └── 54 个文件
    ├── export_512/  (54 文件, 5.17 MB)
        └── 54 个文件
    ├── master/  (294 文件, 27.01 MB)
        ├── Base/  (16 文件, 7.49 MB)
        ├── Body/  (12 文件, 4.20 MB)
        ├── Ears/  (13 文件, 5.35 MB)
        ├── Expressions/  (178 文件, 1.58 MB)
        ├── Eyes/  (29 文件, 0.35 MB)
        ├── Head/  (0 文件, 0.00 MB)
        ├── Limbs/  (0 文件, 0.00 MB)
        ├── Parts/  (10 文件, 3.31 MB)
        ├── Patterns/  (8 文件, 0.10 MB)
        ├── Special/  (4 文件, 0.10 MB)
        ├── Tail/  (0 文件, 0.00 MB)
        ├── Tails/  (24 文件, 4.53 MB)
    ├── preview/  (7 文件, 3.23 MB)
        └── 7 个文件
    ├── source/  (1 文件, 9.73 MB)
        └── 1 个文件
├── history/  (27 文件, 0.09 MB)
    └── 27 个文件
├── mods/  (0 文件, 0.00 MB)
├── tools/  (52 文件, 0.30 MB)
    └── 52 个文件
└── 3 个文件
```

注：`master/Head`、`master/Limbs`、`master/Tail`、`mods/` 仍是**预留位**（正视/侧视扩展用），当前为空，不影响组装；`master/Special/` 已在 v1.4 交付 3 个实体层，不再是预留位。

---

## 3. 怎么用

### 3.1 组装一只狐狸（命令行）

```bash
cd tools
python run_assemble.py --coat obsidian_gold --fur short \
                       --tail twin --ear large \
                       --eye round_gold --pattern stripes
```

### 3.2 批量自检

```bash
python run_batch.py          # 8 组合拼版 + 几何体检
python run_regress_v12.py    # 4 毛色 × 6 尾型 + 2 毛色 × 5 耳型 全矩阵
python run_regress_v13.py    # v1.3 全量（32 组合）
python run_regress_v14.py    # v1.4 全量：既有回归 + 3 条新检查（12/12）
```

### 3.3 重新生成全部资产

```bash
python run_tail_layer.py      # body_core / socket / tail_base 兜底件
python run_expressions.py     # 178 个表情件
python run_expression_sheet.py# 10 表情对照表
python run_anim_spec.py       # 骨骼树 + 36 动作
python run_build_psd.py       # 分层 PSD
python make_delivery.py       # 重新打包
```

环境：Python 3.10 + pillow / numpy / scipy / psd-tools

---

## 4. 验收状态

| 项 | 结果 |
|---|---|
| body_core 包络统一（12 毛色） | bbox `(189,150)-(877,928)`，面积 240020 px，12/12 一致（含 v1.3 两个稀释色） |
| 8 基因组合拼版 | 8/8 PASS（单连通域 / 不出血 / core 统一 / 破洞 0） |
| 全矩阵回归 | v1.3 32/32 PASS；**v1.4 12/12 PASS** |
| 尾根缺口专项 | short / thin × 3 毛色 = **0**；6 尾型 × 3 毛色 18/18 PASS |
| 花纹 128px 可辨 | stripes 47.1% / tabby 48.0% / spots 29.3%，三型可辨 |
| `traits.values` 对账 | 60/60 id × 磁盘文件通过 |
| 尾巴下层 6 尾型 | 零缝、零白边、零破洞 |
| PSD 回读 | 8 层（尾巴在 body 之下，socket 遮罩层默认隐藏） |

---

## 5. 已知边界（务必先读）

1. 骨骼来自静态实测，导入 Spine 后**仍需刷权重**，呼吸缩放会让腹部/腿根轻微拉伸。
2. 动作关键帧为程序生成的正弦/斜坡曲线 —— 节奏正确可直接跑，但走/跑建议对着参考视频再调相位。
3. 长尾用 4 段链、短尾只需 2 段，导入时按尾型选链长。
4. 眉/嘴/闭眼是程序化绘制，风格已对齐但精细度低于母版 AI 原画。
5. 只有正/侧/3 视图中的 **3/4 站姿**已锁定，正视与侧视尚未产出。
6. `tail_curl` 远端仍有 8,295px 的开放式留白（返修单 1.2 表内「偏大」但非 P0，明确不在本单修复范围），回归中已留档。
7. `special_aura` 为俯视透视椭圆环（水平直径 300px、`ry=58`）；如需正圆环，改 `run_fix_r5.py` 的 `ry=150` 重生成即可。

---

## 6. 文件清单（全部 559 个）

```
00_Spec/01_美术资产总规范_v1.0.md  (16045 B)
00_Spec/02_部件拆分依赖矩阵与图层规范.md  (9327 B)
00_Spec/03_配色与性状字典_v1.0.md  (6818 B)
00_Spec/04_技术交接文档.md  (9145 B)
00_Spec/05_阶段1出图任务清单.md  (4162 B)
00_Spec/06_阶段2资产清单与性状字典.md  (7035 B)
00_Spec/07_阶段3模块化拆分与组装规范.md  (7271 B)
00_Spec/08_包络v1.2与尾巴分层方案.md  (5673 B)
00_Spec/09_阶段4动画准备规范.md  (7082 B)
00_Spec/10_v1.4_返修回执.md  (10593 B)
01_Data/_meta.json  (5288 B)
01_Data/anchors.view34.json  (5799 B)
01_Data/animations.json  (1982724 B)
01_Data/colorways.json  (4260 B)
01_Data/expressions.json  (4144 B)
01_Data/phenotype.example.json  (1535 B)
01_Data/skeleton.json  (31144 B)
01_Data/split_regions.json  (2274 B)
01_Data/tail_socket.json  (2021 B)
01_Data/traits.json  (6718 B)
09_Review/_anchor_overlay.png  (460407 B)
09_Review/_anchor_overlay_v2.png  (459497 B)
09_Review/_asm_asm_blue_normal_large.png  (407034 B)
09_Review/_assemble_batch.png  (468406 B)
09_Review/_body_core_gray.png  (298147 B)
09_Review/_coat_contact.png  (495381 B)
09_Review/_ear_shape.png  (173831 B)
09_Review/_ear_sizes.png  (573178 B)
09_Review/_expressions_full.png  (157023 B)
09_Review/_expressions_sheet.png  (474329 B)
09_Review/_flame_zoom.png  (730592 B)
09_Review/_fur_contact.png  (269364 B)
09_Review/_head_crop.png  (412509 B)
09_Review/_mouth_check.png  (243585 B)
09_Review/_multi_tails_preview.png  (540092 B)
09_Review/_new_coats.png  (399879 B)
09_Review/_p2_copper_eye.png  (268846 B)
09_Review/_p2_fold_ear.png  (224858 B)
09_Review/_p2_thin_tail.png  (119890 B)
09_Review/_parts_ears.png  (88843 B)
09_Review/_parts_eyecolors.png  (92485 B)
09_Review/_parts_eyes.png  (40536 B)
09_Review/_parts_pupils.png  (40092 B)
09_Review/_parts_split.png  (296341 B)
09_Review/_parts_tails.png  (118265 B)
09_Review/_pattern_flame.png  (235388 B)
09_Review/_pattern_scales.png  (684879 B)
09_Review/_pattern_tabby_vs_stripes.png  (153224 B)
09_Review/_patterns_preview.png  (124068 B)
09_Review/_r1_trial.png  (676153 B)
09_Review/_r1_trial2.png  (844744 B)
09_Review/_r1_trial3.png  (835185 B)
09_Review/_r1_zoom_1x.png  (568713 B)
09_Review/_r1_zoom_2x.png  (598950 B)
09_Review/_r4_128_zoom.png  (119744 B)
09_Review/_skeleton_map.png  (449638 B)
09_Review/_special_layers.png  (298023 B)
09_Review/_special_star_zoom.png  (825165 B)
09_Review/_split_preview.png  (271389 B)
09_Review/_tail_counts.png  (469219 B)
09_Review/_tail_counts_zoom.png  (727041 B)
09_Review/_tail_modes.png  (503098 B)
09_Review/_tail_root_fix.png  (697500 B)
09_Review/_twin_hole_zoom.png  (68285 B)
09_Review/阶段1_验收记录.md  (3773 B)
10_Worklog/2026-11-01.md  (19687 B)
10_Worklog/2026-11-02.md  (9726 B)
DELIVERY_MANIFEST.md  (36952 B)
README.md  (6888 B)
assets/export_256/asm_blue_normal_large@256.png  (51553 B)
assets/export_256/ear_fold_L@256.png  (3727 B)
assets/export_256/ear_fold_R@256.png  (2639 B)
assets/export_256/ear_large_L@256.png  (6565 B)
assets/export_256/ear_large_R@256.png  (7061 B)
assets/export_256/eye_almond_copper@256.png  (37315 B)
assets/export_256/eye_round_copper@256.png  (37369 B)
assets/export_256/eye_sleepy_copper@256.png  (24839 B)
assets/export_256/fox_base_black_q4@256.png  (44717 B)
assets/export_256/fox_base_blue_q4@256.png  (55149 B)
assets/export_256/fox_base_caramel_q4@256.png  (53403 B)
assets/export_256/fox_base_grey_q4@256.png  (47459 B)
assets/export_256/fox_base_haze_blue_q4@256.png  (52186 B)
assets/export_256/fox_base_mint_q4@256.png  (52793 B)
assets/export_256/fox_base_mist_purple_q4@256.png  (52175 B)
assets/export_256/fox_base_obsidian_gold_q4@256.png  (45332 B)
assets/export_256/fox_base_orange_q4@256.png  (54845 B)
assets/export_256/fox_base_purple_q4@256.png  (53025 B)
assets/export_256/fox_base_sakura_q4@256.png  (53233 B)
assets/export_256/fox_base_white_q4@256.png  (48494 B)
assets/export_256/fox_black_normal_pointed@256.png  (44613 B)
assets/export_256/fox_black_normal_star@256.png  (45701 B)
assets/export_256/fox_blue_normal_large@256.png  (56570 B)
assets/export_256/fox_blue_normal_pointed@256.png  (55810 B)
assets/export_256/fox_full_blue_34@256.png  (54378 B)
assets/export_256/fox_fur_curly_blue_q4@256.png  (63757 B)
assets/export_256/fox_fur_long_blue_q4@256.png  (73011 B)
assets/export_256/fox_fur_medium_blue_q4@256.png  (67202 B)
assets/export_256/fox_haze_blue_normal_pointed@256.png  (52496 B)
assets/export_256/fox_mint_short_small@256.png  (53961 B)
assets/export_256/fox_mist_purple_normal_pointed@256.png  (52719 B)
assets/export_256/fox_obsidian_gold_twin_large@256.png  (47378 B)
assets/export_256/fox_orange_long_pointed@256.png  (57315 B)
assets/export_256/fox_purple_curl_star@256.png  (56591 B)
assets/export_256/fox_purple_normal_pointed@256.png  (53228 B)
assets/export_256/fox_sakura_fluffy_round@256.png  (53259 B)
assets/export_256/fox_white_fluffy_round@256.png  (48647 B)
assets/export_256/pattern_facemark_mask@256.png  (1478 B)
assets/export_256/pattern_flame_mask@256.png  (4767 B)
assets/export_256/pattern_gradient_mask@256.png  (4065 B)
assets/export_256/pattern_solid_mask@256.png  (334 B)
assets/export_256/pattern_spots_mask@256.png  (12904 B)
assets/export_256/pattern_stripes_mask@256.png  (8486 B)
assets/export_256/pattern_tabby_mask@256.png  (16568 B)
assets/export_256/special_aura@256.png  (3445 B)
assets/export_256/special_glow@256.png  (22608 B)
assets/export_256/special_star_mark@256.png  (1048 B)
assets/export_256/tail_nine@256.png  (18659 B)
assets/export_256/tail_quad@256.png  (13770 B)
assets/export_256/tail_quint@256.png  (14036 B)
assets/export_256/tail_short@256.png  (8284 B)
assets/export_256/tail_thin@256.png  (13483 B)
assets/export_256/tail_triple@256.png  (13086 B)
assets/export_256/tail_twin@256.png  (8396 B)
assets/export_512/asm_blue_normal_large@512.png  (158052 B)
assets/export_512/ear_fold_L@512.png  (11370 B)
assets/export_512/ear_fold_R@512.png  (7711 B)
assets/export_512/ear_large_L@512.png  (20815 B)
assets/export_512/ear_large_R@512.png  (21694 B)
assets/export_512/eye_almond_copper@512.png  (106705 B)
assets/export_512/eye_round_copper@512.png  (101891 B)
assets/export_512/eye_sleepy_copper@512.png  (72250 B)
assets/export_512/fox_base_black_q4@512.png  (134029 B)
assets/export_512/fox_base_blue_q4@512.png  (173234 B)
assets/export_512/fox_base_caramel_q4@512.png  (165417 B)
assets/export_512/fox_base_grey_q4@512.png  (142634 B)
assets/export_512/fox_base_haze_blue_q4@512.png  (159620 B)
assets/export_512/fox_base_mint_q4@512.png  (161730 B)
assets/export_512/fox_base_mist_purple_q4@512.png  (159572 B)
assets/export_512/fox_base_obsidian_gold_q4@512.png  (134698 B)
assets/export_512/fox_base_orange_q4@512.png  (171430 B)
assets/export_512/fox_base_purple_q4@512.png  (163353 B)
assets/export_512/fox_base_sakura_q4@512.png  (163733 B)
assets/export_512/fox_base_white_q4@512.png  (144027 B)
assets/export_512/fox_black_normal_pointed@512.png  (83739 B)
assets/export_512/fox_black_normal_star@512.png  (135428 B)
assets/export_512/fox_blue_normal_large@512.png  (177003 B)
assets/export_512/fox_blue_normal_pointed@512.png  (107749 B)
assets/export_512/fox_full_blue_34@512.png  (169270 B)
assets/export_512/fox_fur_curly_blue_q4@512.png  (201683 B)
assets/export_512/fox_fur_long_blue_q4@512.png  (236445 B)
assets/export_512/fox_fur_medium_blue_q4@512.png  (220011 B)
assets/export_512/fox_haze_blue_normal_pointed@512.png  (99456 B)
assets/export_512/fox_mint_short_small@512.png  (161869 B)
assets/export_512/fox_mist_purple_normal_pointed@512.png  (100062 B)
assets/export_512/fox_obsidian_gold_twin_large@512.png  (141038 B)
assets/export_512/fox_orange_long_pointed@512.png  (171236 B)
assets/export_512/fox_purple_curl_star@512.png  (169866 B)
assets/export_512/fox_purple_normal_pointed@512.png  (101276 B)
assets/export_512/fox_sakura_fluffy_round@512.png  (160068 B)
assets/export_512/fox_white_fluffy_round@512.png  (143654 B)
assets/export_512/pattern_facemark_mask@512.png  (3401 B)
assets/export_512/pattern_flame_mask@512.png  (12042 B)
assets/export_512/pattern_gradient_mask@512.png  (8721 B)
assets/export_512/pattern_solid_mask@512.png  (1097 B)
assets/export_512/pattern_spots_mask@512.png  (29616 B)
assets/export_512/pattern_stripes_mask@512.png  (18334 B)
assets/export_512/pattern_tabby_mask@512.png  (39831 B)
assets/export_512/special_aura@512.png  (10195 B)
assets/export_512/special_glow@512.png  (72622 B)
assets/export_512/special_star_mark@512.png  (2660 B)
assets/export_512/tail_nine@512.png  (57766 B)
assets/export_512/tail_quad@512.png  (42141 B)
assets/export_512/tail_quint@512.png  (42605 B)
assets/export_512/tail_short@512.png  (25900 B)
assets/export_512/tail_thin@512.png  (41137 B)
assets/export_512/tail_triple@512.png  (39534 B)
assets/export_512/tail_twin@512.png  (24817 B)
assets/master/Base/fox_base_black_q4@1024.png  (381509 B)
assets/master/Base/fox_base_blue_q4@1024.png  (525605 B)
assets/master/Base/fox_base_caramel_q4@1024.png  (482275 B)
assets/master/Base/fox_base_grey_q4@1024.png  (404348 B)
assets/master/Base/fox_base_haze_blue_q4@1024.png  (462613 B)
assets/master/Base/fox_base_mint_q4@1024.png  (468992 B)
assets/master/Base/fox_base_mist_purple_q4@1024.png  (462583 B)
assets/master/Base/fox_base_obsidian_gold_q4@1024.png  (370503 B)
assets/master/Base/fox_base_orange_q4@1024.png  (499326 B)
assets/master/Base/fox_base_purple_q4@1024.png  (474765 B)
assets/master/Base/fox_base_sakura_q4@1024.png  (474295 B)
assets/master/Base/fox_base_white_q4@1024.png  (394965 B)
assets/master/Base/fox_full_blue_34@1024.png  (508574 B)
assets/master/Base/fox_fur_curly_blue_q4@1024.png  (502140 B)
assets/master/Base/fox_fur_long_blue_q4@1024.png  (734631 B)
assets/master/Base/fox_fur_medium_blue_q4@1024.png  (705209 B)
assets/master/Body/body_core_black@1024.png  (305380 B)
assets/master/Body/body_core_blue@1024.png  (433619 B)
assets/master/Body/body_core_caramel@1024.png  (394014 B)
assets/master/Body/body_core_grey@1024.png  (325359 B)
assets/master/Body/body_core_haze_blue@1024.png  (376180 B)
assets/master/Body/body_core_mint@1024.png  (383795 B)
assets/master/Body/body_core_mist_purple@1024.png  (377985 B)
assets/master/Body/body_core_obsidian_gold@1024.png  (300179 B)
assets/master/Body/body_core_orange@1024.png  (410944 B)
assets/master/Body/body_core_purple@1024.png  (387919 B)
assets/master/Body/body_core_sakura@1024.png  (386395 B)
assets/master/Body/body_core_white@1024.png  (317150 B)
assets/master/Ears/_ears_meta.json  (8650 B)
assets/master/Ears/ear_fold_L.png  (529188 B)
assets/master/Ears/ear_fold_R.png  (529159 B)
assets/master/Ears/ear_large_L.png  (53284 B)
assets/master/Ears/ear_large_R.png  (56911 B)
assets/master/Ears/ear_pointed_L.png  (462780 B)
assets/master/Ears/ear_pointed_R.png  (462747 B)
assets/master/Ears/ear_round_L.png  (575369 B)
assets/master/Ears/ear_round_R.png  (575760 B)
assets/master/Ears/ear_small_L.png  (542169 B)
assets/master/Ears/ear_small_R.png  (542172 B)
assets/master/Ears/ear_star_L.png  (635789 B)
assets/master/Ears/ear_star_R.png  (635721 B)
assets/master/Expressions/blush.png  (27874 B)
assets/master/Expressions/brow_angry_L.png  (5098 B)
assets/master/Expressions/brow_angry_L_black.png  (6313 B)
assets/master/Expressions/brow_angry_L_blue.png  (6933 B)
assets/master/Expressions/brow_angry_L_caramel.png  (6743 B)
assets/master/Expressions/brow_angry_L_grey.png  (6838 B)
assets/master/Expressions/brow_angry_L_mint.png  (6909 B)
assets/master/Expressions/brow_angry_L_obsidian_gold.png  (6297 B)
assets/master/Expressions/brow_angry_L_orange.png  (6858 B)
assets/master/Expressions/brow_angry_L_purple.png  (6847 B)
assets/master/Expressions/brow_angry_L_sakura.png  (7057 B)
assets/master/Expressions/brow_angry_L_white.png  (6917 B)
assets/master/Expressions/brow_angry_R.png  (5078 B)
assets/master/Expressions/brow_angry_R_black.png  (6101 B)
assets/master/Expressions/brow_angry_R_blue.png  (6730 B)
assets/master/Expressions/brow_angry_R_caramel.png  (6529 B)
assets/master/Expressions/brow_angry_R_grey.png  (6636 B)
assets/master/Expressions/brow_angry_R_mint.png  (6696 B)
assets/master/Expressions/brow_angry_R_obsidian_gold.png  (6110 B)
assets/master/Expressions/brow_angry_R_orange.png  (6650 B)
assets/master/Expressions/brow_angry_R_purple.png  (6651 B)
assets/master/Expressions/brow_angry_R_sakura.png  (6836 B)
assets/master/Expressions/brow_angry_R_white.png  (6724 B)
assets/master/Expressions/brow_neutral_L.png  (4911 B)
assets/master/Expressions/brow_neutral_L_black.png  (5884 B)
assets/master/Expressions/brow_neutral_L_blue.png  (6368 B)
assets/master/Expressions/brow_neutral_L_caramel.png  (6227 B)
assets/master/Expressions/brow_neutral_L_grey.png  (6297 B)
assets/master/Expressions/brow_neutral_L_mint.png  (6342 B)
assets/master/Expressions/brow_neutral_L_obsidian_gold.png  (5820 B)
assets/master/Expressions/brow_neutral_L_orange.png  (6308 B)
assets/master/Expressions/brow_neutral_L_purple.png  (6326 B)
assets/master/Expressions/brow_neutral_L_sakura.png  (6458 B)
assets/master/Expressions/brow_neutral_L_white.png  (6369 B)
assets/master/Expressions/brow_neutral_R.png  (4934 B)
assets/master/Expressions/brow_neutral_R_black.png  (5845 B)
assets/master/Expressions/brow_neutral_R_blue.png  (6331 B)
assets/master/Expressions/brow_neutral_R_caramel.png  (6199 B)
assets/master/Expressions/brow_neutral_R_grey.png  (6254 B)
assets/master/Expressions/brow_neutral_R_mint.png  (6319 B)
assets/master/Expressions/brow_neutral_R_obsidian_gold.png  (5788 B)
assets/master/Expressions/brow_neutral_R_orange.png  (6235 B)
assets/master/Expressions/brow_neutral_R_purple.png  (6283 B)
assets/master/Expressions/brow_neutral_R_sakura.png  (6406 B)
assets/master/Expressions/brow_neutral_R_white.png  (6334 B)
assets/master/Expressions/brow_raised_L.png  (4903 B)
assets/master/Expressions/brow_raised_L_black.png  (5790 B)
assets/master/Expressions/brow_raised_L_blue.png  (6190 B)
assets/master/Expressions/brow_raised_L_caramel.png  (6132 B)
assets/master/Expressions/brow_raised_L_grey.png  (6185 B)
assets/master/Expressions/brow_raised_L_mint.png  (6192 B)
assets/master/Expressions/brow_raised_L_obsidian_gold.png  (5756 B)
assets/master/Expressions/brow_raised_L_orange.png  (6172 B)
assets/master/Expressions/brow_raised_L_purple.png  (6170 B)
assets/master/Expressions/brow_raised_L_sakura.png  (6307 B)
assets/master/Expressions/brow_raised_L_white.png  (6230 B)
assets/master/Expressions/brow_raised_R.png  (4890 B)
assets/master/Expressions/brow_raised_R_black.png  (5761 B)
assets/master/Expressions/brow_raised_R_blue.png  (6205 B)
assets/master/Expressions/brow_raised_R_caramel.png  (6108 B)
assets/master/Expressions/brow_raised_R_grey.png  (6177 B)
assets/master/Expressions/brow_raised_R_mint.png  (6185 B)
assets/master/Expressions/brow_raised_R_obsidian_gold.png  (5743 B)
assets/master/Expressions/brow_raised_R_orange.png  (6175 B)
assets/master/Expressions/brow_raised_R_purple.png  (6195 B)
assets/master/Expressions/brow_raised_R_sakura.png  (6313 B)
assets/master/Expressions/brow_raised_R_white.png  (6218 B)
assets/master/Expressions/brow_sad_L.png  (4998 B)
assets/master/Expressions/brow_sad_L_black.png  (5969 B)
assets/master/Expressions/brow_sad_L_blue.png  (6459 B)
assets/master/Expressions/brow_sad_L_caramel.png  (6318 B)
assets/master/Expressions/brow_sad_L_grey.png  (6401 B)
assets/master/Expressions/brow_sad_L_mint.png  (6418 B)
assets/master/Expressions/brow_sad_L_obsidian_gold.png  (5913 B)
assets/master/Expressions/brow_sad_L_orange.png  (6358 B)
assets/master/Expressions/brow_sad_L_purple.png  (6424 B)
assets/master/Expressions/brow_sad_L_sakura.png  (6541 B)
assets/master/Expressions/brow_sad_L_white.png  (6439 B)
assets/master/Expressions/brow_sad_R.png  (4982 B)
assets/master/Expressions/brow_sad_R_black.png  (6050 B)
assets/master/Expressions/brow_sad_R_blue.png  (6538 B)
assets/master/Expressions/brow_sad_R_caramel.png  (6409 B)
assets/master/Expressions/brow_sad_R_grey.png  (6498 B)
assets/master/Expressions/brow_sad_R_mint.png  (6526 B)
assets/master/Expressions/brow_sad_R_obsidian_gold.png  (5960 B)
assets/master/Expressions/brow_sad_R_orange.png  (6466 B)
assets/master/Expressions/brow_sad_R_purple.png  (6483 B)
assets/master/Expressions/brow_sad_R_sakura.png  (6689 B)
assets/master/Expressions/brow_sad_R_white.png  (6539 B)
assets/master/Expressions/eye_closed.png  (6019 B)
assets/master/Expressions/eye_closed_black.png  (8267 B)
assets/master/Expressions/eye_closed_blue.png  (9341 B)
assets/master/Expressions/eye_closed_caramel.png  (8946 B)
assets/master/Expressions/eye_closed_grey.png  (9177 B)
assets/master/Expressions/eye_closed_mint.png  (9363 B)
assets/master/Expressions/eye_closed_obsidian_gold.png  (8116 B)
assets/master/Expressions/eye_closed_orange.png  (9228 B)
assets/master/Expressions/eye_closed_purple.png  (9253 B)
assets/master/Expressions/eye_closed_sakura.png  (9515 B)
assets/master/Expressions/eye_closed_white.png  (9230 B)
assets/master/Expressions/eye_happy.png  (5920 B)
assets/master/Expressions/eye_happy_black.png  (7958 B)
assets/master/Expressions/eye_happy_blue.png  (9019 B)
assets/master/Expressions/eye_happy_caramel.png  (8594 B)
assets/master/Expressions/eye_happy_grey.png  (8872 B)
assets/master/Expressions/eye_happy_mint.png  (8985 B)
assets/master/Expressions/eye_happy_obsidian_gold.png  (7796 B)
assets/master/Expressions/eye_happy_orange.png  (8813 B)
assets/master/Expressions/eye_happy_purple.png  (8872 B)
assets/master/Expressions/eye_happy_sakura.png  (9155 B)
assets/master/Expressions/eye_happy_white.png  (8920 B)
assets/master/Expressions/mouth_closed.png  (4996 B)
assets/master/Expressions/mouth_closed_black.png  (6244 B)
assets/master/Expressions/mouth_closed_blue.png  (6822 B)
assets/master/Expressions/mouth_closed_caramel.png  (6661 B)
assets/master/Expressions/mouth_closed_grey.png  (6749 B)
assets/master/Expressions/mouth_closed_mint.png  (6773 B)
assets/master/Expressions/mouth_closed_obsidian_gold.png  (6178 B)
assets/master/Expressions/mouth_closed_orange.png  (6703 B)
assets/master/Expressions/mouth_closed_purple.png  (6754 B)
assets/master/Expressions/mouth_closed_sakura.png  (6908 B)
assets/master/Expressions/mouth_closed_white.png  (6795 B)
assets/master/Expressions/mouth_default_master.png  (515310 B)
assets/master/Expressions/mouth_frown.png  (4869 B)
assets/master/Expressions/mouth_frown_black.png  (5739 B)
assets/master/Expressions/mouth_frown_blue.png  (6147 B)
assets/master/Expressions/mouth_frown_caramel.png  (5984 B)
assets/master/Expressions/mouth_frown_grey.png  (6089 B)
assets/master/Expressions/mouth_frown_mint.png  (6128 B)
assets/master/Expressions/mouth_frown_obsidian_gold.png  (5681 B)
assets/master/Expressions/mouth_frown_orange.png  (6085 B)
assets/master/Expressions/mouth_frown_purple.png  (6091 B)
assets/master/Expressions/mouth_frown_sakura.png  (6202 B)
assets/master/Expressions/mouth_frown_white.png  (6103 B)
assets/master/Expressions/mouth_open_o.png  (4550 B)
assets/master/Expressions/mouth_open_o_black.png  (4571 B)
assets/master/Expressions/mouth_open_o_blue.png  (4558 B)
assets/master/Expressions/mouth_open_o_caramel.png  (4560 B)
assets/master/Expressions/mouth_open_o_grey.png  (4559 B)
assets/master/Expressions/mouth_open_o_mint.png  (4558 B)
assets/master/Expressions/mouth_open_o_obsidian_gold.png  (4571 B)
assets/master/Expressions/mouth_open_o_orange.png  (4560 B)
assets/master/Expressions/mouth_open_o_purple.png  (4559 B)
assets/master/Expressions/mouth_open_o_sakura.png  (4559 B)
assets/master/Expressions/mouth_open_o_white.png  (4559 B)
assets/master/Expressions/mouth_smile.png  (5157 B)
assets/master/Expressions/mouth_smile_black.png  (6336 B)
assets/master/Expressions/mouth_smile_blue.png  (6914 B)
assets/master/Expressions/mouth_smile_caramel.png  (6689 B)
assets/master/Expressions/mouth_smile_grey.png  (6844 B)
assets/master/Expressions/mouth_smile_mint.png  (6914 B)
assets/master/Expressions/mouth_smile_obsidian_gold.png  (6275 B)
assets/master/Expressions/mouth_smile_orange.png  (6836 B)
assets/master/Expressions/mouth_smile_purple.png  (6864 B)
assets/master/Expressions/mouth_smile_sakura.png  (6987 B)
assets/master/Expressions/mouth_smile_white.png  (6872 B)
assets/master/Expressions/mouth_tongue.png  (4483 B)
assets/master/Expressions/mouth_tongue_black.png  (4472 B)
assets/master/Expressions/mouth_tongue_blue.png  (4481 B)
assets/master/Expressions/mouth_tongue_caramel.png  (4483 B)
assets/master/Expressions/mouth_tongue_grey.png  (4480 B)
assets/master/Expressions/mouth_tongue_mint.png  (4482 B)
assets/master/Expressions/mouth_tongue_obsidian_gold.png  (4473 B)
assets/master/Expressions/mouth_tongue_orange.png  (4476 B)
assets/master/Expressions/mouth_tongue_purple.png  (4482 B)
assets/master/Expressions/mouth_tongue_sakura.png  (4479 B)
assets/master/Expressions/mouth_tongue_white.png  (4482 B)
assets/master/Expressions/mouth_wavy.png  (5060 B)
assets/master/Expressions/mouth_wavy_black.png  (6379 B)
assets/master/Expressions/mouth_wavy_blue.png  (6944 B)
assets/master/Expressions/mouth_wavy_caramel.png  (6787 B)
assets/master/Expressions/mouth_wavy_grey.png  (6810 B)
assets/master/Expressions/mouth_wavy_mint.png  (6903 B)
assets/master/Expressions/mouth_wavy_obsidian_gold.png  (6323 B)
assets/master/Expressions/mouth_wavy_orange.png  (6805 B)
assets/master/Expressions/mouth_wavy_purple.png  (6923 B)
assets/master/Expressions/mouth_wavy_sakura.png  (7032 B)
assets/master/Expressions/mouth_wavy_white.png  (6919 B)
assets/master/Eyes/_eyes_meta.json  (1188 B)
assets/master/Eyes/_pupils_meta.json  (1199 B)
assets/master/Eyes/eye_almond.png  (15170 B)
assets/master/Eyes/eye_almond_blue.png  (14979 B)
assets/master/Eyes/eye_almond_copper.png  (15099 B)
assets/master/Eyes/eye_almond_cyan.png  (14997 B)
assets/master/Eyes/eye_almond_gold.png  (15051 B)
assets/master/Eyes/eye_almond_green.png  (14952 B)
assets/master/Eyes/eye_almond_purple.png  (15019 B)
assets/master/Eyes/eye_almond_red.png  (14935 B)
assets/master/Eyes/eye_round.png  (16494 B)
assets/master/Eyes/eye_round_blue.png  (15592 B)
assets/master/Eyes/eye_round_copper.png  (15646 B)
assets/master/Eyes/eye_round_cyan.png  (15567 B)
assets/master/Eyes/eye_round_gold.png  (15723 B)
assets/master/Eyes/eye_round_green.png  (15551 B)
assets/master/Eyes/eye_round_purple.png  (15693 B)
assets/master/Eyes/eye_round_red.png  (15502 B)
assets/master/Eyes/eye_sleepy.png  (9855 B)
assets/master/Eyes/eye_sleepy_blue.png  (9769 B)
assets/master/Eyes/eye_sleepy_copper.png  (9841 B)
assets/master/Eyes/eye_sleepy_cyan.png  (9796 B)
assets/master/Eyes/eye_sleepy_gold.png  (9854 B)
assets/master/Eyes/eye_sleepy_green.png  (9792 B)
assets/master/Eyes/eye_sleepy_purple.png  (9852 B)
assets/master/Eyes/eye_sleepy_red.png  (9797 B)
assets/master/Eyes/pupil_round.png  (12503 B)
assets/master/Eyes/pupil_slit.png  (18176 B)
assets/master/Eyes/pupil_star.png  (11361 B)
assets/master/Parts/_parts_meta.json  (2688 B)
assets/master/Parts/_variant_parts_meta.json  (5822 B)
assets/master/Parts/part_body_core@1024.png  (433619 B)
assets/master/Parts/part_body_core_v12@1024.png  (440400 B)
assets/master/Parts/part_ear_L@1024.png  (515574 B)
assets/master/Parts/part_ear_R@1024.png  (515673 B)
assets/master/Parts/part_eye_L@1024.png  (515124 B)
assets/master/Parts/part_eye_R@1024.png  (515064 B)
assets/master/Parts/part_tail@1024.png  (516516 B)
assets/master/Parts/tail_socket_mask@1024.png  (7444 B)
assets/master/Patterns/_patterns_meta.json  (1819 B)
assets/master/Patterns/pattern_facemark_mask@1024.png  (7261 B)
assets/master/Patterns/pattern_flame_mask@1024.png  (27857 B)
assets/master/Patterns/pattern_gradient_mask@1024.png  (9969 B)
assets/master/Patterns/pattern_solid_mask@1024.png  (6489 B)
assets/master/Patterns/pattern_spots_mask@1024.png  (16119 B)
assets/master/Patterns/pattern_stripes_mask@1024.png  (14479 B)
assets/master/Patterns/pattern_tabby_mask@1024.png  (19562 B)
assets/master/Special/_special_meta.json  (1701 B)
assets/master/Special/special_aura@1024.png  (18046 B)
assets/master/Special/special_glow@1024.png  (76022 B)
assets/master/Special/special_star_mark@1024.png  (10098 B)
assets/master/Tails/_tails_meta.json  (8609 B)
assets/master/Tails/tail_base_black@1024.png  (16112 B)
assets/master/Tails/tail_base_blue@1024.png  (96920 B)
assets/master/Tails/tail_base_caramel@1024.png  (18317 B)
assets/master/Tails/tail_base_grey@1024.png  (16686 B)
assets/master/Tails/tail_base_haze_blue@1024.png  (17948 B)
assets/master/Tails/tail_base_mint@1024.png  (17446 B)
assets/master/Tails/tail_base_mist_purple@1024.png  (17550 B)
assets/master/Tails/tail_base_obsidian_gold@1024.png  (16871 B)
assets/master/Tails/tail_base_orange@1024.png  (18570 B)
assets/master/Tails/tail_base_purple@1024.png  (18030 B)
assets/master/Tails/tail_base_sakura@1024.png  (17581 B)
assets/master/Tails/tail_base_white@1024.png  (14954 B)
assets/master/Tails/tail_curl.png  (538924 B)
assets/master/Tails/tail_fluffy.png  (645538 B)
assets/master/Tails/tail_long.png  (561362 B)
assets/master/Tails/tail_nine.png  (191796 B)
assets/master/Tails/tail_normal.png  (516516 B)
assets/master/Tails/tail_quad.png  (149254 B)
assets/master/Tails/tail_quint.png  (150402 B)
assets/master/Tails/tail_short.png  (520212 B)
assets/master/Tails/tail_thin.png  (495254 B)
assets/master/Tails/tail_triple.png  (139937 B)
assets/master/Tails/tail_twin.png  (547323 B)
assets/preview/_check_gray.png  (436459 B)
assets/preview/_check_gray_q4.png  (451596 B)
assets/preview/preview_pattern_facemark.png  (520494 B)
assets/preview/preview_pattern_gradient.png  (505905 B)
assets/preview/preview_pattern_solid.png  (525605 B)
assets/preview/preview_pattern_spots.png  (489247 B)
assets/preview/preview_pattern_stripes.png  (454580 B)
assets/source/Fox_Base.psd  (10200762 B)
history/000001.json  (197 B)
history/000002.json  (492 B)
history/000003.json  (600 B)
history/000004.json  (601 B)
history/000005.json  (913 B)
history/000006.json  (985 B)
history/000007.json  (1327 B)
history/000008.json  (1612 B)
history/000009.json  (1918 B)
history/000010.json  (2226 B)
history/000011.json  (2532 B)
history/000012.json  (2840 B)
history/000013.json  (3181 B)
history/000014.json  (3523 B)
history/000015.json  (3809 B)
history/000016.json  (4113 B)
history/000017.json  (4418 B)
history/000018.json  (4724 B)
history/000019.json  (5075 B)
history/000020.json  (5428 B)
history/000021.json  (5780 B)
history/000022.json  (6131 B)
history/000023.json  (6482 B)
history/000024.json  (6833 B)
history/000025.json  (7184 B)
history/000026.json  (7537 B)
history/000027.json  (7888 B)
project.json  (8238 B)
tools/_fetch_v14_evidence.py  (1169 B)
tools/_r4_tune.py  (3972 B)
tools/_read_v14_order.py  (873 B)
tools/diag_coverage.py  (4193 B)
tools/dl_s2.py  (6796 B)
tools/dl_s2b.py  (3621 B)
tools/dl_s2c.py  (4229 B)
tools/dl_s3.py  (7849 B)
tools/fox_pipeline.py  (12408 B)
tools/fox_traits.py  (18498 B)
tools/make_delivery.py  (14431 B)
tools/probe_belly.py  (1335 B)
tools/probe_envelope.py  (2500 B)
tools/probe_points.py  (1288 B)
tools/probe_shape.py  (1473 B)
tools/probe_socket2.py  (2684 B)
tools/probe_socket3.py  (1658 B)
tools/probe_tail_socket.py  (2259 B)
tools/run_anim_spec.py  (26234 B)
tools/run_assemble.py  (17727 B)
tools/run_batch.py  (3721 B)
tools/run_build_psd.py  (1618 B)
tools/run_coat_colors.py  (1854 B)
tools/run_diag_v14.py  (4958 B)
tools/run_export_v13.py  (1436 B)
tools/run_expression_sheet.py  (2965 B)
tools/run_expressions.py  (11897 B)
tools/run_fix_and_eyecolors.py  (5766 B)
tools/run_fix_r1.py  (5465 B)
tools/run_fix_r2.py  (5647 B)
tools/run_fix_r3.py  (5393 B)
tools/run_fix_r4.py  (7592 B)
tools/run_fix_r5.py  (8713 B)
tools/run_fur_and_patterns.py  (5237 B)
tools/run_multi_tail_bones.py  (8805 B)
tools/run_multi_tails.py  (5482 B)
tools/run_new_coats.py  (6360 B)
tools/run_p2_review.py  (2123 B)
tools/run_parts.py  (4619 B)
tools/run_parts_v13.py  (12765 B)
tools/run_patterns.py  (5037 B)
tools/run_patterns_v13.py  (11781 B)
tools/run_r1_trial.py  (5069 B)
tools/run_regress_v12.py  (3034 B)
tools/run_regress_v13.py  (2559 B)
tools/run_regress_v14.py  (10448 B)
tools/run_split.py  (7220 B)
tools/run_tail_counts.py  (1997 B)
tools/run_tail_layer.py  (11044 B)
tools/run_tail_modes.py  (3620 B)
tools/run_variant_parts.py  (3389 B)
tools/upload_master.py  (1334 B)
```

