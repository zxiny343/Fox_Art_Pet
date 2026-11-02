# Fox_Art_Pet · 幻想小狐狸桌宠

一个跑在 Windows 桌面上的透明桌宠：孟德尔遗传 + 繁殖 + 突变 + 自然选择的生态模拟内核，
配一套自研骨骼动画播放器（非 Spine）和 PySide6 无边框透明窗口外壳。

当前阶段：**桌宠外壳 MVP 已可运行**（任务 13 完成），生态引擎尚未接入外壳。

---

## 1. 环境要求

| 项 | 版本 | 备注 |
|---|---|---|
| 系统 | Windows 10/11 | 透明置顶窗口用了 Win32 分层窗口特性 |
| Python | 3.10（3.9+ 均可） | 仓库代码只用到标准库 + 下面三个包 |
| PySide6 | 6.12.x | 桌宠外壳 GUI |
| Pillow | ≥ 9.0 | 素材拼装 / 换色 / 逐帧合成 |
| numpy | ≥ 1.23 | 换色矩阵加速 |

```bash
pip install PySide6 pillow numpy
```

## 2. 快速开始

```bash
git clone https://github.com/zxiny343/Fox_Art_Pet.git
cd Fox_Art_Pet
pip install PySide6 pillow numpy
python pet/app.py --new          # --new 随机换一只狐狸；不加则读 pet_state.json 里存的那只
```

美术素材（v1.4，559 个文件 / 58M）已经随仓库一起分发，clone 完即可直接运行，不用另外下载。

可选参数：

| 参数 | 作用 |
|---|---|
| `--new` | 重新随机生成一只（忽略存档） |
| `--no-top` | 取消窗口置顶 |
| `--fps N` | 指定渲染帧率（默认按显示器刷新率，实测 ~96fps） |

**交互**

- 拖拽 = 抓住狐狸移动（尾部会上翘）
- 单击 = 摸一下（会中断睡眠）
- 双击 = 跳一下
- 滚轮 = 缩放（0.4× ~ 3.0×）
- 右键 = 菜单（换一只 / 置顶开关 / 退出）

**默认外观**：窗口 256×304（画布 1024×1216 的 1/4），位于屏幕右下角。
觉得小可以滚轮放大，或改 `pet/config.py` 的 `base_size`。

## 3. 目录结构

```
pet/                桌宠外壳（PySide6）
  app.py            主窗口：无边框 + 透明 + 置顶 + Qt.Tool，拖拽/交互/托盘
  behavior.py       行为状态机：base 互斥 / add 叠加 / face 覆盖三层动作调度
  config.py         状态存档 pet_state.json + 基因型归一化
  verify_behavior.py / verify_pet.py   自检（37 项 / 40 项）
sim/                渲染与生态内核
  anim.py           动画播放器：读 skeleton.json + animations.json，多动作混合
  artmap.py         表型 → 部件映射 + 换色 + 部件级 LRU 缓存
  render_kernel.py  唯一渲染入口 render()，含缺件降级表与素材版本自动失效
  fox_ecosystem_sim.py / breeding.py / diversity.py ...   生态与遗传模拟
  verify_*.py       各模块自检脚本
_art_v1.4/          v1.4 美术交付包（已在仓库内，运行必需）
  delivery/Fox_Art/  assets（部件 png）+ 01_Data（skeleton/animations/traits）+ 00_Spec
docs/               设计稿、验收报告、返修单、动画播放器文档
```

素材查找规则（`sim/artmap.py:find_art_root`）：先在 `_art_v*/delivery/Fox_Art` 里找版本号最高的一份；
也可以设环境变量 `FOX_ART_ROOT` 指向任意一份。

## 4. 自检（改完代码务必跑）

```bash
python sim/verify_artmap.py        # 表型→部件映射       期望 69/69
python sim/verify_anim.py          # 动画播放器          期望 14/14
python sim/verify_render_kernel.py # 渲染内核与降级表    自适应版本
python pet/verify_behavior.py      # 行为状态机          期望 37/37
QT_QPA_PLATFORM=offscreen python pet/verify_pet.py   # 桌宠外壳（离屏）期望 40/40
```

最后一条必须离屏跑，否则会在你屏幕上弹窗。

## 5. 已知限制

- 36 个动作里有 18 个需要「分腿部件」：腿目前画在 `body_core` 位图里，没法单独摆，这些动作暂不可用。
- 头部转动需要切图资源，当前未实现（只有整体 `pelvis` 平移/旋转）。
- `eye_closed` 缺 `mist_purple` / `haze_blue` 两个眼色；附件命名不统一 → 记在 v1.5 美术返修清单。
- v1.4 尾根缺口用半透明雾填充（alpha 均值 ~70，正常部件 ~253），衰减长度偏短 → v1.5 待修。
- idle 静止态动画幅度偏小，放着不动时几乎看不出在动 → 待调。
- `sim/dl_v14.py` 依赖本机资料库 skill 路径，换机器直接失效，仅作存档。

## 6. 没进仓库的东西

- `_art_v1.2/` `_art_v1.3/`：历史美术版本（112M / 92M），需要时单独从资料库取。
- `Fox_Art_Delivery_v1.4_20261102.zip`：与 `_art_v1.4/` 内容重复。
- `.workbuddy/`、`pet_state.json`、`docs/desktop-*.png`：本机会话/状态/桌面截图。

## 7. 文档索引（docs/）

| 文档 | 内容 |
|---|---|
| `fantasy-fox-design-v0.3.html` | 完整设定与美术需求 |
| `fox-art-fix-request-v1.4.md` | v1.4 返修单（R1–R7） |
| `art-v1.4-acceptance.md` | v1.4 验收结论 |
| `artmap-spec-v1.md` | 表型→部件映射规格 |
| `anim-prototype-v1.md` | 动画播放器设计与性能（0.92s→9.3ms/帧） |
| `desktop-pet-mvp-v1.md` | 桌宠外壳 MVP 设计 |
| `ecology-tuning-proposal-v0.6.md` | 生态参数 v0.6 |
