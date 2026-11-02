# -*- coding: utf-8 -*-
"""打包交付：生成 DELIVERY_MANIFEST.md 并打两个 zip。

用法：
    python make_delivery.py

产出（写到 Fox_Art 的上级 dist/ 目录）：
    Fox_Art_Delivery_v1.4_<日期>.zip   交付包（不含 AI 原始出图 raw_s1/s2/s3）
    Fox_Art_Full_v1.4_<日期>.zip       完整归档（含一切，含原始出图与中间图）
"""
import os
import io
import json
import zipfile
from datetime import datetime

B = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DIST = os.path.abspath(os.path.join(B, "..", "dist"))
DATE = datetime.now().strftime("%Y%m%d")
VER = "v1.4"

# 交付包排除：AI 原始出图（过程素材，体积 23.5MB）+ Python 缓存
EXCLUDE_DIRS = {"raw_s1", "raw_s2", "raw_s3", "__pycache__", ".ipynb_checkpoints"}
EXCLUDE_EXT = {".pyc", ".pyo", ".tmp", ".bak"}


def walk_files(base):
    out = []
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in sorted(files):
            if os.path.splitext(f)[1].lower() in EXCLUDE_EXT:
                continue
            out.append(os.path.join(root, f))
    return sorted(out)


def tree_lines(base, rel="", depth=0, maxdepth=2):
    lines = []
    cur = os.path.join(base, rel) if rel else base
    try:
        items = sorted(os.listdir(cur))
    except OSError:
        return lines
    dirs = [d for d in items
            if os.path.isdir(os.path.join(cur, d)) and d not in EXCLUDE_DIRS]
    files = [f for f in items if os.path.isfile(os.path.join(cur, f))]
    for d in dirs:
        sub = os.path.join(rel, d) if rel else d
        n, t = dir_stat(os.path.join(base, sub))
        lines.append("%s├── %s/  (%d 文件, %.2f MB)"
                     % ("    " * depth, d, n, t / 1048576.0))
        if depth < maxdepth:
            lines += tree_lines(base, sub, depth + 1, maxdepth)
    if files and depth <= maxdepth:
        lines.append("%s└── %d 个文件" % ("    " * depth, len(files)))
    return lines


def dir_stat(p):
    n = 0
    t = 0
    for r, d, fs in os.walk(p):
        d[:] = [x for x in d if x not in EXCLUDE_DIRS]
        for f in fs:
            if os.path.splitext(f)[1].lower() in EXCLUDE_EXT:
                continue
            n += 1
            try:
                t += os.path.getsize(os.path.join(r, f))
            except OSError:
                pass
    return n, t


def count_assets():
    """统计资产数量，用于写入清单正文。"""
    m = os.path.join(B, "assets", "master")
    out = {}
    for d in sorted(os.listdir(m)):
        p = os.path.join(m, d)
        if os.path.isdir(p):
            out[d] = len([f for f in os.listdir(p) if f.lower().endswith(".png")])
    exp = {}
    for d in ("export_512", "export_256", "preview", "source"):
        p = os.path.join(B, "assets", d)
        if os.path.isdir(p):
            exp[d] = len(os.listdir(p))
    return out, exp


def load_counts():
    r = {}
    p = os.path.join(B, "01_Data", "animations.json")
    if os.path.exists(p):
        r["actions"] = json.load(open(p, encoding="utf-8")).get("actionCount")
    p = os.path.join(B, "01_Data", "skeleton.json")
    if os.path.exists(p):
        d = json.load(open(p, encoding="utf-8"))
        r["bones"] = len(d.get("bones", []))
        r["slots"] = len(d.get("slots", []))
    p = os.path.join(B, "01_Data", "expressions.json")
    if os.path.exists(p):
        r["expressions"] = len(json.load(open(p, encoding="utf-8")).get(
            "expressions", []))
    p = os.path.join(B, "01_Data", "colorways.json")
    if os.path.exists(p):
        j = json.load(open(p, encoding="utf-8"))
        cw = j["colorways"] if isinstance(j, dict) and "colorways" in j else j
        r["colorways"] = len(cw)
    p = os.path.join(B, "01_Data", "traits.json")
    if os.path.exists(p):
        r["traits"] = json.load(open(p, encoding="utf-8"))
    return r


def build_manifest(files):
    ac, ex = count_assets()
    c = load_counts()
    tr = c.get("traits") or {}
    n, t = dir_stat(B)
    total_master = sum(ac.values())

    L = []
    A = L.append
    A("# 幻想小狐狸 · 桌宠美术资产包 —— 交付清单")
    A("")
    A("- **版本**：%s（阶段 1–4 全交付 + v1.4 返修 R1–R7）" % VER)
    A("- **打包日期**：%s" % datetime.now().strftime("%Y-%m-%d %H:%M"))
    A("- **根目录**：`Fox_Art/`")
    A("- **文件总数**：%d 个（%.1f MB，未压缩）" % (n, t / 1048576.0))
    A("- **画布规范**：1024×1024 RGBA 母版，原点左上；导出档 512 / 256；"
      "全画布对齐，程序零错位")
    A("")
    A("---")
    A("")
    A("## 1. 这个包里有什么")
    A("")
    A("| 目录 | 内容 |")
    A("|---|---|")
    A("| `00_Spec/` | 10 份规范文档（总规范、部件依赖矩阵、配色性状、技术交接、"
      "包络 v1.2、阶段 4 动画规范、**v1.4 返修回执**…） |")
    A("| `01_Data/` | 机读数据：锚点 v3.0、12 套配色、性状字典、**`_meta.json` "
      "values 对账表**、拆分区域、骨骼树、36 动作、10 表情、tail socket |")
    A("| `assets/master/` | 母版资产 %d 个 PNG（Base / Parts / Tails / Ears / "
      "Eyes / Patterns / **Special** / Expressions） |" % total_master)
    A("| `assets/export_512`、`export_256` | 可直接进引擎的两档导出 |")
    A("| `assets/preview` | 预览图 |")
    A("| `assets/source/` | 分层可编辑 PSD（8 层） |")
    A("| `tools/` | 全部生产脚本（抠图 / 换色 / 拆分 / 组装 / 自检 / 打包） |")
    A("| `09_Review/` | 验收对照图（拼版、表情表、骨骼图、**v1.4 五张返修验收图**） |")
    A("| `10_Worklog/` | 逐阶段工作日志与踩坑记录（含 **v1.4 返修日志**） |")
    A("| `history/` | 阶段过程中的 AI 出图与中间版本 |")
    A("")
    A("### 资产计数")
    A("")
    A("| 部件目录 | PNG 数 |")
    A("|---|---|")
    for k, v in ac.items():
        A("| `%s/` | %d |" % (k, v))
    for k, v in ex.items():
        A("| `assets/%s/` | %d |" % (k, v))
    A("")
    A("### 遗传性状规模")
    A("")
    A("- 毛色 **%s** 套（含 obsidian_gold 的 points 规则、v1.3 新增 2 个稀释色）"
      % c.get("colorways", "?"))
    cats = tr.get("categories", []) if isinstance(tr, dict) else tr
    if cats:
        def cnt(cid):
            v = next((x["values"] for x in cats if x["id"] == cid), [])
            return len(v)
        A("- 耳型 %d / 尾型 %d / 眼色 %d / 眼型 %d / 瞳孔 %d / 毛发 %d / 花纹 %d"
          % (cnt("ear"), cnt("tail"), cnt("eyeColor"), cnt("eyeShape"),
             cnt("pupil"), cnt("fur"), cnt("pattern")))
        bs = next((x.get("boneSegments", {}) for x in cats
                   if x["id"] == "tail"), {})
        A("- 尾型骨段数：%s" % ", ".join("%s=%d" % (k, v)
                                    for k, v in bs.items()))
    A("- 组合数约 **数百万级**（程序随机，美术侧不负责概率）")
    A("")
    A("### v1.4 返修摘要（R1–R7 全部关闭）")
    A("")
    A("| 单号 | 内容 | 结果 |")
    A("|---|---|---|")
    A("| R1 P0 | 短/细尾尾根缺口 | 根部绒毛过渡，32,043 / 35,743 → **0**（3 毛色） |")
    A("| R2 P1 | 多尾根部描边叠影 + 白缝 | 根区合形 + 统一毛流场，110–160px 羽化 |")
    A("| R3 P1 | 大耳反而最小 | round 母本重绘，6,054 → **31,740px**，比值 1.504 |")
    A("| R4 P1 | 花纹覆盖偏低 | stripes 47.1% / tabby 48.0% / spots 29.3% |")
    A("| R5 P1 | 3 个 special 有声明无文件 | 已补 glow / aura / star_mark（+ 双档导出） |")
    A("| R6 P2 | `traits.values` 4 处漏登记 | 已补 3 项 + 统一 `fur_medium` 命名，"
      "新增 `_meta.json` 对账表 |")
    A("| R7 P2 | `ORIG_EAR_H` 未定义 | `run_assemble.py` 第 43 行补定义 |")
    A("")
    A("逐条改动行号、验收数值与判定口径见 `00_Spec/10_v1.4_返修回执.md`；"
      "过程与踩坑见 `10_Worklog/2026-11-02.md`。")
    A("")
    A("### 动画准备")
    A("")
    A("- 骨骼树：**%s 骨 + %s 插槽**（`01_Data/skeleton.json`，"
      "坐标取自 v3.0 实测锚点）" % (c.get("bones", "?"), c.get("slots", "?")))
    A("- 动作库：**%s 个**（30fps，逐骨骼通道关键帧，分 base/add/face 三层）"
      % c.get("actions", "?"))
    A("- 表情库：**%s 种**（眼 × 眉 × 嘴 × 腮红，附件切换实现）"
      % c.get("expressions", "?"))
    A("")
    A("---")
    A("")
    A("## 2. 目录结构")
    A("")
    A("```")
    A("Fox_Art/")
    for ln in tree_lines(B, maxdepth=2):
        A(ln)
    A("```")
    A("")
    A("注：`master/Head`、`master/Limbs`、`master/Tail`、`mods/` 仍是**预留位**"
      "（正视/侧视扩展用），当前为空，不影响组装；"
      "`master/Special/` 已在 v1.4 交付 3 个实体层，不再是预留位。")
    A("")
    A("---")
    A("")
    A("## 3. 怎么用")
    A("")
    A("### 3.1 组装一只狐狸（命令行）")
    A("")
    A("```bash")
    A("cd tools")
    A("python run_assemble.py --coat obsidian_gold --fur short \\")
    A("                       --tail twin --ear large \\")
    A("                       --eye round_gold --pattern stripes")
    A("```")
    A("")
    A("### 3.2 批量自检")
    A("")
    A("```bash")
    A("python run_batch.py          # 8 组合拼版 + 几何体检")
    A("python run_regress_v12.py    # 4 毛色 × 6 尾型 + 2 毛色 × 5 耳型 全矩阵")
    A("python run_regress_v13.py    # v1.3 全量（32 组合）")
    A("python run_regress_v14.py    # v1.4 全量：既有回归 + 3 条新检查（12/12）")
    A("```")
    A("")
    A("### 3.3 重新生成全部资产")
    A("")
    A("```bash")
    A("python run_tail_layer.py      # body_core / socket / tail_base 兜底件")
    A("python run_expressions.py     # 178 个表情件")
    A("python run_expression_sheet.py# 10 表情对照表")
    A("python run_anim_spec.py       # 骨骼树 + 36 动作")
    A("python run_build_psd.py       # 分层 PSD")
    A("python make_delivery.py       # 重新打包")
    A("```")
    A("")
    A("环境：Python 3.10 + pillow / numpy / scipy / psd-tools")
    A("")
    A("---")
    A("")
    A("## 4. 验收状态")
    A("")
    A("| 项 | 结果 |")
    A("|---|---|")
    A("| body_core 包络统一（12 毛色） | bbox `(189,150)-(877,928)`，"
      "面积 240020 px，12/12 一致（含 v1.3 两个稀释色） |")
    A("| 8 基因组合拼版 | 8/8 PASS（单连通域 / 不出血 / core 统一 / 破洞 0） |")
    A("| 全矩阵回归 | v1.3 32/32 PASS；**v1.4 12/12 PASS** |")
    A("| 尾根缺口专项 | short / thin × 3 毛色 = **0**；6 尾型 × 3 毛色 18/18 PASS |")
    A("| 花纹 128px 可辨 | stripes 47.1% / tabby 48.0% / spots 29.3%，三型可辨 |")
    A("| `traits.values` 对账 | 60/60 id × 磁盘文件通过 |")
    A("| 尾巴下层 6 尾型 | 零缝、零白边、零破洞 |")
    A("| PSD 回读 | 8 层（尾巴在 body 之下，socket 遮罩层默认隐藏） |")
    A("")
    A("---")
    A("")
    A("## 5. 已知边界（务必先读）")
    A("")
    A("1. 骨骼来自静态实测，导入 Spine 后**仍需刷权重**，呼吸缩放会让腹部/腿根"
      "轻微拉伸。")
    A("2. 动作关键帧为程序生成的正弦/斜坡曲线 —— 节奏正确可直接跑，但走/跑建议"
      "对着参考视频再调相位。")
    A("3. 长尾用 4 段链、短尾只需 2 段，导入时按尾型选链长。")
    A("4. 眉/嘴/闭眼是程序化绘制，风格已对齐但精细度低于母版 AI 原画。")
    A("5. 只有正/侧/3 视图中的 **3/4 站姿**已锁定，正视与侧视尚未产出。")
    A("6. `tail_curl` 远端仍有 8,295px 的开放式留白（返修单 1.2 表内「偏大」"
      "但非 P0，明确不在本单修复范围），回归中已留档。")
    A("7. `special_aura` 为俯视透视椭圆环（水平直径 300px、`ry=58`）；"
      "如需正圆环，改 `run_fix_r5.py` 的 `ry=150` 重生成即可。")
    A("")
    A("---")
    A("")
    A("## 6. 文件清单（全部 %d 个）" % len(files))
    A("")
    A("```")
    for f in files:
        rel = os.path.relpath(f, B).replace("\\", "/")
        A("%s  (%d B)" % (rel, os.path.getsize(f)))
    A("```")
    A("")
    return "\n".join(L) + "\n"


def zip_it(files, out_path, root):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED,
                         compresslevel=9) as z:
        for f in files:
            z.write(f, os.path.join("Fox_Art",
                                    os.path.relpath(f, root)).replace("\\", "/"))
    return os.path.getsize(out_path)


def main():
    os.makedirs(DIST, exist_ok=True)
    mp = os.path.join(B, "DELIVERY_MANIFEST.md")

    # 先落一版清单，再重新扫描（把清单自身计入），最后用准确列表覆写
    io.open(mp, "w", encoding="utf-8").write(build_manifest(walk_files(B)))
    files = walk_files(B)
    man = build_manifest(files)
    io.open(mp, "w", encoding="utf-8").write(man)
    print("manifest:", os.path.relpath(mp, B), len(man), "chars")

    # --- 交付包（排除 AI 原始出图） ---
    dpath = os.path.join(DIST, "Fox_Art_Delivery_%s_%s.zip" % (VER, DATE))
    dsz = zip_it(files, dpath, B)
    print("delivery :", dpath, "%.1f MB" % (dsz / 1048576.0))

    # --- 完整归档（含 raw_s1/s2/s3） ---
    allf = []
    for r, d, fs in os.walk(B):
        d[:] = [x for x in d if x not in ("__pycache__",)]
        for f in sorted(fs):
            if os.path.splitext(f)[1].lower() in EXCLUDE_EXT:
                continue
            allf.append(os.path.join(r, f))
    fpath = os.path.join(DIST, "Fox_Art_Full_%s_%s.zip" % (VER, DATE))
    fsz = zip_it(sorted(allf), fpath, B)
    print("full     :", fpath, "%.1f MB" % (fsz / 1048576.0))
    print("files    :", len(files), "(delivery) /", len(allf), "(full)")


if __name__ == "__main__":
    main()
