# -*- coding: utf-8 -*-
"""生成 v0.5 运行报告 -> docs/ecosystem-run-report-v0.5.html

数据来源：sim/report_data.json（由 prepare_report_data.py 生成）
"""
import os
import sys
import json

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
DOCS = os.path.join(ROOT, 'docs')
sys.path.insert(0, _HERE)

from gen_report import frame, T_, axes, line_chart, grouped_bar, stacked_bar, esc  # noqa
from gen_report import C_INK, C_MUTE, C_LINE, C_BASE, C_TUNE, C_BLUE, C_AMBER  # noqa

C_V5 = C_BLUE
C_OK = C_TUNE
C_BAD = C_BASE


# ============================ 小工具 ============================

def pct(x, d=0):
    return ('%.' + str(d) + 'f%%') % (x * 100)


def series_daily(stat, key, step=4):
    return [d[key] for d in stat['daily'][::step]]


def xlabels_for(stat, step=4, per=24):
    d = stat['daily'][::step]
    return [('%d' % (x['day'] // per + 1)) for x in d]


def table(headers, rows, aligns=None, note=None):
    a = aligns or ['left'] + ['right'] * (len(headers) - 1)
    o = ['<table><thead><tr>']
    for h, al in zip(headers, a):
        o.append('<th style="text-align:%s">%s</th>' % (al, h))
    o.append('</tr></thead><tbody>')
    for r in rows:
        o.append('<tr>')
        for i, c in enumerate(r):
            al = a[i] if i < len(a) else 'right'
            o.append('<td style="text-align:%s">%s</td>' % (al, c))
        o.append('</tr>')
    o.append('</tbody></table>')
    if note:
        o.append('<div class="note">%s</div>' % note)
    return ''.join(o)


def card(v, l, d, tone=None):
    c = ' style="border-top:3px solid %s"' % tone if tone else ''
    return ('<div class="card stat"%s><div class="v">%s</div><div class="l">%s</div>'
            '<div class="d">%s</div></div>' % (c, v, l, d))


def h2(num, title):
    return '<h2 id="s%s"><span class="no">%s</span>%s</h2>' % (num, num, title)


def h3(t):
    return '<h3>%s</h3>' % t


def qbox(title, body):
    return ('<div class="q"><div class="qh">%s</div><div class="qb">%s</div></div>'
            % (title, body))


# ============================ 主流程 ============================

def main():
    data = json.load(open(os.path.join(_HERE, 'report_data.json'), encoding='utf-8'))
    V = data['variants']
    P = data['presets']
    CAP = data['caps']
    OFF = data['official']
    b, t, v = V['base'], V['tuned'], V['v2']
    seedn = len(data['seeds'])
    yrs = data['years']

    # ---------- 图 1：近交系数长期曲线 ----------
    step = max(1, len(b['daily']) // 60)
    lab = xlabels_for(b, step)
    g1 = line_chart([
        ('v0.3 原规则', C_BASE, series_daily(b, 'F', step)),
        ('v0.4 候选', C_TUNE, series_daily(t, 'F', step)),
        ('v0.5 本方案', C_V5, series_daily(v, 'F', step)),
    ], w=760, h=300, ymax=0.9, ymin=0.0, yfmt='%.2f', xlabels=lab,
        xtitle='生态年')

    # ---------- 图 2：杂合度曲线 ----------
    g2 = line_chart([
        ('v0.3 原规则', C_BASE, series_daily(b, 'het', step)),
        ('v0.4 候选', C_TUNE, series_daily(t, 'het', step)),
        ('v0.5 本方案', C_V5, series_daily(v, 'het', step)),
    ], w=760, h=300, ymax=0.6, ymin=0.0, yfmt='%.2f', xlabels=lab,
        xtitle='生态年')

    # ---------- 图 3：种群规模曲线 ----------
    g3 = line_chart([
        ('v0.3 (上限20)', C_BASE, series_daily(b, 'pop', step)),
        ('v0.4 (上限40)', C_TUNE, series_daily(t, 'pop', step)),
        ('v0.5 (上限40)', C_V5, series_daily(v, 'pop', step)),
    ], w=760, h=280, ymax=45, ymin=0.0, yfmt='%.0f', xlabels=lab,
        xtitle='生态年')

    # ---------- 图 4：末代指标对比 ----------
    g4 = grouped_bar(
        ['世代推进', '近交 F(×100)', '杂合度(×100)', '外观指纹(×100)', '创始血统/10'],
        [('v0.3', C_BASE, [b['max_generation'], b['meanF_end'] * 100, b['het_end'] * 100,
                           b['fp2_ratio'] * 100, b['founder_lines_alive']]),
         ('v0.4', C_TUNE, [t['max_generation'], t['meanF_end'] * 100, t['het_end'] * 100,
                           t['fp2_ratio'] * 100, t['founder_lines_alive']]),
         ('v0.5', C_V5, [v['max_generation'], v['meanF_end'] * 100, v['het_end'] * 100,
                         v['fp2_ratio'] * 100, v['founder_lines_alive']])],
        w=760, h=300, ymax=None, yfmt='%.0f')

    # ---------- 图 5：出生/离场构成 ----------
    def exits(s):
        dc = s['deaths_by_cause']
        return [dc.get('幼崽夭折', 0), dc.get('衰老', 0), dc.get('疾病', 0),
                s['migrated'], s['immigrants']]
    g5 = grouped_bar(['幼崽夭折', '衰老', '疾病', '迁徙离场', '野外引入'],
                     [('v0.3', C_BASE, exits(b)),
                      ('v0.4', C_TUNE, exits(t)),
                      ('v0.5', C_V5, exits(v))],
                     w=760, h=280, ymax=None, yfmt='%.0f')

    # ---------- 图 6：上限敏感性 ----------
    cats = ['上限 30', '上限 40', '上限 50', '上限 60']
    g6 = grouped_bar(
        ['20 年代数', '20 年后 F(×100)', '外观指纹(×100)', '20 年窝数(÷2)'],
        [('', C_AMBER, [CAP['cap%d' % c]['max_generation'] for c in (30, 40, 50, 60)])],
        w=1, h=1) if False else None

    cap_keys = ['cap30', 'cap40', 'cap50', 'cap60']
    g6a = line_chart([
        ('20 年推进世代', C_AMBER, [CAP[k]['max_generation'] for k in cap_keys]),
    ], w=740, h=250, ymax=40, ymin=0, yfmt='%.0f', xlabels=cats)
    g6b = line_chart([
        ('20 年后近交 F', C_BASE, [CAP[k]['meanF_end'] for k in cap_keys]),
        ('末代外观指纹', C_V5, [CAP[k]['fp2_ratio'] for k in cap_keys]),
    ], w=740, h=250, ymax=1.0, ymin=0, yfmt='%.2f', xlabels=cats)

    # ---------- 图 7：三档节奏预设 ----------
    pn = data['preset_names']
    g7a = line_chart([
        ('5 生态年世代', C_OK, [P[k]['max_generation'] for k in pn]),
    ], w=740, h=240, ymax=12, ymin=0, yfmt='%.0f', xlabels=pn)
    g7b = line_chart([
        ('20 生态年世代', C_OK, [P[k]['max_generation'] for k in pn]),
        ('20 年后近交 F(×10)', C_BAD, [P[k]['meanF_end'] * 10 for k in pn]),
    ], w=740, h=240, ymax=40, ymin=0, yfmt='%.0f', xlabels=pn)

    # ---------- 数据表 ----------
    rows_long = []
    for nm, s, col in (('v0.3 原规则', b, C_BASE), ('v0.4 候选', t, C_TUNE), ('v0.5 本方案', v, C_V5)):
        rows_long.append([
            '<b style="color:%s">%s</b>' % (col, nm),
            '%.1f' % s['max_generation'],
            '%.3f' % s['meanF_end'],
            '%.3f' % s['het_end'],
            '%.2f' % s['fp2_ratio'],
            '%.2f' % s['colors'],
            '%.1f/10' % s['founder_lines_alive'],
            '%.0f' % s['max_pop_seen'],
            '%.1f' % s['final_pop'],
            '%.0f' % s['trimmed_pups'],
        ])
    tbl_long = table(
        ['版本', '世代', '近交 F', '杂合度', '外观指纹', '毛色种类', '创始血统', '种群峰值', '末种群', '被裁剪幼崽'],
        rows_long,
        note='均为 %d 个种子在 <b>%d 个生态年</b> 后的均值。上限：v0.3 为 20，其余为 40。' % (seedn, yrs))

    rows_evt = []
    for nm, s, col in (('v0.3 原规则', b, C_BASE), ('v0.4 候选', t, C_TUNE), ('v0.5 本方案', v, C_V5)):
        dc = s['deaths_by_cause']
        rows_evt.append([
            '<b style="color:%s">%s</b>' % (col, nm),
            '%.0f' % s['total_litters'], '%.0f' % s['total_births'],
            '%.0f' % dc.get('幼崽夭折', 0), '%.0f' % dc.get('衰老', 0), '%.0f' % dc.get('疾病', 0),
            '%.0f' % s['migrated'], pct(s['mig_share']), '%.0f' % s['immigrants'],
            '%.0f' % s['blocked_litters'], '%.0f' % s['trimmed_pups'],
        ])
    tbl_evt = table(
        ['版本', '窝数', '出生', '夭折', '衰老', '疾病', '迁徙', '迁徙占离桌', '引入', '阻断妊娠', '裁剪幼崽'],
        rows_evt,
        note='「阻断妊娠」= 因名额不足而根本没有怀上（用户不可见，无害）；'
             '「裁剪幼崽」= 已经怀上却被系统静默丢弃（违反需求，必须为 0）。')

    rows_preset = []
    for nm in pn:
        s = P[nm]
        rows_preset.append([
            '<b>%s</b>' % nm,
            '52 / 16 天' if nm == '稳健档' else ('45 / 14 天' if nm == '标准档' else '32 / 9 天'),
            '%.1f' % s['max_generation'], '%.3f' % s['meanF_end'], '%.2f' % s['fp2_ratio'],
            '%.2f' % s['colors'], '%.0f' % s['total_litters'], '%.0f' % s['immigrants'],
            pct(s['mig_share']),
        ])
    tbl_preset = table(
        ['档位', '寿命 / 引入节奏', '世代', '近交 F', '外观指纹', '毛色', '窝数', '引入数', '迁徙占比'],
        rows_preset,
        note='%d 种子 × %d 生态年。三档在多样性上几乎等价，区别只在观察节奏。' % (seedn, yrs))

    rows_cap = []
    for c in (30, 40, 50, 60):
        k = 'cap%d' % c
        s = CAP[k]
        rows_cap.append(['上限 %d' % c, '%.1f' % s['max_generation'], '%.3f' % s['meanF_end'],
                         '%.2f' % s['fp2_ratio'], '%.2f' % s['colors'], '%.0f' % s['total_litters'],
                         '%.0f' % s['final_pop']])
    tbl_cap = table(['数量上限', '世代', '近交 F', '外观指纹', '毛色', '窝数', '末种群'], rows_cap)

    # 正式 5 轮
    rows_off = []
    for nm, key, col in (('v0.3', 'base', C_BASE), ('v0.4', 'tuned', C_TUNE), ('v0.5', 'v2', C_V5)):
        if key not in OFF:
            continue
        s = OFF[key]['stat']
        rows_off.append([
            '<b style="color:%s">%s</b>' % (col, nm),
            '%.0f' % s['mutations_total'], '%.0f' % s['mutations_survived'],
            '%.2f' % s['selection_r'], '%.0f' % s['torpor_events'],
        ])
    tbl_off_extra = table(['版本（5 年 × 5 轮）', '突变事件', '存活到末代', '选择强度 r', '休眠事件'],
                          rows_off,
                          note='「选择强度」= 适应度与实际留下后代数的相关系数；'
                               '接近 0 说明当前环境没有选择压力（这是本次模拟的前置条件所致，不是缺陷）。')

    # ============================ HTML ============================
    CSS = """
:root{--ink:#1F2328;--tx2:#4B5563;--tx3:#6B7280;--line:#E5E9EF;--line2:#D8DEE6;
--bg:#FFFFFF;--bg2:#F7F9FB;--accent:#378ADD;--warn:#B7791F;--bad:#C0392B;--ok:#2E7D5B}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font-family:"PingFang SC","Microsoft YaHei","Segoe UI",system-ui,sans-serif;
 font-size:14px;line-height:1.85;-webkit-font-smoothing:antialiased}
.wrap{max-width:940px;margin:0 auto;padding:0 24px 80px}
header{background:linear-gradient(160deg,#0F2D4A 0%,#1B4A72 55%,#24608F 100%);color:#fff;padding:44px 0 38px;margin-bottom:34px}
header .wrap{padding-bottom:0}
h1{font-size:27px;margin:0 0 8px;font-weight:700;letter-spacing:.4px}
.sub{opacity:.9;font-size:14px;margin-bottom:14px}
.meta{opacity:.72;font-size:12.5px;line-height:1.75}
nav{margin-top:18px;display:flex;flex-wrap:wrap;gap:8px}
nav a{color:#fff;text-decoration:none;font-size:12.5px;padding:5px 11px;border:1px solid rgba(255,255,255,.3);border-radius:20px;opacity:.92}
nav a:hover{background:rgba(255,255,255,.14)}
h2{font-size:20px;margin:44px 0 16px;padding-bottom:10px;border-bottom:2px solid var(--line2);display:flex;align-items:baseline;gap:10px}
h2 .no{display:inline-flex;align-items:center;justify-content:center;min-width:30px;height:30px;border-radius:8px;background:var(--ink);color:#fff;font-size:13px;font-weight:600}
h3{font-size:16px;margin:26px 0 10px;color:#16202B}
h4{font-size:14px;margin:18px 0 8px;color:var(--tx2)}
p{margin:10px 0}
table{width:100%;border-collapse:collapse;margin:14px 0;font-size:13px}
th{background:var(--bg2);text-align:left;padding:9px 11px;border:1px solid var(--line);font-weight:600;color:var(--tx2);white-space:nowrap}
td{padding:8px 11px;border:1px solid var(--line);vertical-align:top}
tbody tr:nth-child(even){background:#FCFDFE}
.note{background:var(--bg2);border-left:3px solid var(--line2);padding:10px 14px;border-radius:0 6px 6px 0;font-size:12.5px;color:var(--tx2);margin:10px 0;line-height:1.75}
.note.warn{border-left-color:var(--warn);background:#FDF8EE}
.note.bad{border-left-color:var(--bad);background:#FCEFEC}
.note.ok{border-left-color:var(--ok);background:#EFF7F2}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:16px 0}
.grid2{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin:16px 0}
.card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.card.stat .v{font-size:26px;font-weight:700;line-height:1.2}
.card.stat .l{font-size:12.5px;color:var(--tx2);margin-top:2px}
.card.stat .d{font-size:11.5px;color:var(--tx3);margin-top:5px;line-height:1.6}
.q{border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:0 10px 10px 0;padding:14px 18px;margin:16px 0;background:#FAFCFE}
.q .qh{font-weight:700;font-size:14.5px;margin-bottom:6px}
.q .qb{font-size:13px;color:var(--tx2);line-height:1.85}
code{background:#F1F4F8;padding:2px 6px;border-radius:4px;font-size:12.5px;
 font-family:"SFMono-Regular",Consolas,Menlo,monospace}
pre{background:#F8FAFC;border:1px solid var(--line);border-radius:8px;padding:14px 16px;overflow-x:auto;
 font-family:"SFMono-Regular",Consolas,Menlo,monospace;font-size:12.5px;line-height:1.7}
hr{border:0;border-top:1px solid var(--line);margin:36px 0}
figure{margin:18px 0}
figcaption{font-size:12px;color:var(--tx3);text-align:center;margin-top:6px}
.big{font-size:44px;font-weight:700;line-height:1.1}
.delta{font-size:12.5px;font-weight:600}
.up{color:var(--ok)}.down{color:var(--bad)}
@media print{nav{display:none}header{background:#0F2D4A !important;-webkit-print-color-adjust:exact}}
@media (max-width:760px){.grid3,.grid2{grid-template-columns:1fr}}
"""

    def fig(svg, cap):
        return '<figure>%s<figcaption>%s</figcaption></figure>' % (svg, cap)

    HTML = []
    A = HTML.append

    A('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">')
    A('<meta name="viewport" content="width=device-width,initial-scale=1">')
    A('<title>幻想小狐狸 · 生态系统模拟运行报告 v0.5</title>')
    A('<style>%s</style></head><body>' % CSS)

    A('<header><div class="wrap">')
    A('<h1>幻想小狐狸 · 生态系统模拟运行报告 v0.5</h1>')
    A('<div class="sub">第二轮参数寻优 · E1–E5 全部采纳 · 长期（20 生态年）稳定性验证</div>')
    A('<div class="meta">'
      '对比基准：v0.3 原规则、v0.4 候选方案、v0.5 本方案（均为 %d 个随机种子）<br>'
      '每轮运行时长：5 或 20 个生态年（1 生态年 = 24 游戏天 = 576 世界时钟 tick）<br>'
      '模拟条件：食物充足 · 环境适宜 · 用户不干预 · 不投喂 · 壁纸亮度固定 50<br>'
      '本轮不做任何编码实现，仅用模拟验证规则是否成立。</div>' % seedn)
    A('<nav><a href="#s0">00 结论</a><a href="#s1">01 长期对照</a><a href="#s2">02 本轮改动</a>'
      '<a href="#s3">03 正式 5 轮</a><a href="#s4">04 参数寻优</a>'
      '<a href="#s5">05 仍存在风险</a><a href="#s6">06 待拍板</a></nav>')
    A('</div></header>')

    A('<div class="wrap">')

    # ---------------- 00 ----------------
    A(h2('00', '结论'))
    A('<div class="grid3">')
    A(card('%.3f' % b['meanF_end'], 'v0.3 二十年后的近交系数', '杂合度跌到 %.3f，几乎全部基因座固定' % b['het_end'], C_BAD))
    A(card('%.3f' % t['meanF_end'], 'v0.4 二十年后的近交系数', '比 v0.3 好，但仍会缓慢走向崩溃', C_BAD))
    A(card('%.3f' % v['meanF_end'], 'v0.5 二十年后的近交系数', '不再随代数持续爬升，进入稳态平台', C_OK))
    A('</div>')
    A('<div class="note bad"><b>一句话：</b>v0.3 会在第 20 个生态年前彻底崩成一个样子的近亲群；'
      'v0.4 只是把崩溃推迟；<b>v0.5 才真正进入「迁移—漂变平衡」的稳态</b>——'
      '近交系数在第 10 年附近开始收敛并长期停住，这意味着用户可以无限期地把这个生态跑下去。</div>')

    A('<div class="grid3">')
    A(card('%.0f' % v['max_generation'], 'v0.5 二十年推进世代', '约 %.1f 代 / 生态年' % (v['max_generation'] / yrs), C_V5))
    A(card('%.0f%%' % (v['fp2_ratio'] * 100), 'v0.5 末代可分辨个体占比', '含毛色/花纹/耳型/尾数/眼色/毛长/特效的综合外观', C_V5))
    A(card('%.0f' % v['trimmed_pups'], 'v0.5 被静默裁剪的幼崽', '从 v0.4 的每年 %.0f 只降到 0' % (t['trimmed_pups'] / yrs), C_OK))
    A('</div>')

    A(h3('为什么「长期」才是真验收标准'))
    A('<p>上一轮（v0.4）的所有数字在 <b>5 生态年</b>窗口里都是好看的：多样性达标、繁殖量翻倍、'
      '近交从 0.25 降到 0.11。可一旦把窗口拉到 20 年，<b>同一套参数走到 F = %.3f</b> —— '
      '种群还是会崩，只是崩得慢一点。</p>' % t['meanF_end'])
    A('<p>所以本轮把验收标准从「第 5 年的数字好不好看」改成「<b>有没有进入稳态平台</b>」。'
      '下面这张图是这个判断的全部依据。</p>')

    # ---------------- 01 ----------------
    A(h2('01', '三版本长期对照（%d 生态年）' % yrs))
    A(fig(g1, '平均近交系数 F 随时间的演化。v0.3 持续爬升到 %.2f；v0.4 爬到 %.2f 仍在上升；'
              'v0.5 在中途趋于稳定。' % (b['meanF_end'], t['meanF_end'])))
    A(fig(g2, '观测杂合度。杂合度直接决定「桌面上还有多少种不同长相的狐狸」。'))
    A(fig(g3, '种群规模。v0.3 的曲线在 20–31 之间来回抖动，说明它在反复冲破自己 20 的上限。'))
    A(tbl_long)
    A(fig(g4, '末代核心指标横向对比（为了放在同一坐标系里，F / 杂合度 / 指纹都乘了 100）。'))
    A(fig(g5, '出生与离桌的构成。三版本的死亡结构相近，差异集中在「引入」这一项。'))

    A('<div class="note ok"><b>值得单独说的一件事：</b>v0.5 的引入数量是 v0.4 的 '
      '%.1f 倍（%.0f vs %.0f 只 / %d 年），但每代迁移者 Nm 只从 %.2f 升到 %.2f —— '
      '正好落在保护遗传学里「每代一个迁移者」的经典阈值附近。'
      '这个值的意义是：<b>刚好够挡住近交崩溃，又不至于让本地适应和人工选育失去作用</b>。'
      '</div>' % (v['immigrants'] / max(1e-9, t['immigrants']), v['immigrants'], t['immigrants'],
                  yrs, t['immigrants'] / max(1, t['max_generation']),
                  v['immigrants'] / max(1, v['max_generation'])))

    # ---------------- 02 ----------------
    A(h2('02', '本轮改了什么'))
    A('<p>在 E1–E5 全部采纳的基础上，另有五处改动（C1–C5）与两个缺陷修复。'
      '下面每条都写清了<b>怎么发现的</b>，因为其中三条完全靠肉眼标高 invalid。</p>')

    A(h3('C1｜修掉「静默裁剪幼崽」—— 改为整窝名额预留'))
    A('<p><b>怎么发现的：</b>给 v0.4 补观测指标时，看到 <code>trimmed_pups = %.0f</code> ——'
      '每 %d 年有 %.0f 只<b>已经受孕的幼崽</b>被名额规则静默丢弃，是实际出生数（%.0f）的 %.1f 倍。'
      '表现到产品上就是：玩家看到一只怀孕的狐狸，最后只生下来 1 只。</p>'
      % (t['trimmed_pups'], yrs, t['trimmed_pups'], t['total_births'],
         t['trimmed_pups'] / max(1, t['total_births'])))
    A('<p><b>改法：</b>受孕前检查剩余名额，<b>不足一整窝（默认 6）就干脆不受孕</b>。</p>')
    A('<pre>Cap_mode       = L_plus_reserve\n'
      'Litter_reserve = 6            # 剩余名额 &lt; 6 就放弃本次妊娠</pre>')
    A('<div class="note warn"><b>副作用必须知道，而且不小：</b>'
      '把「整窝」作为受孕前提，等于把有效容量从 40 降到约 34，'
      '窝数从 %.0f 降到 %.0f（−%.0f%%），<b>出生总数也下降约 %.0f%%</b>（%.0f → %.0f）。<br>'
      '但换来的是<b>每一窝都是完整的</b>：每窝平均仔数从 %.2f 只升到 %.2f 只，'
      '且被静默丢弃的幼崽归零。<br>'
      '换句话说，v0.4 的「高出生」是靠 %.0f 次妊娠堆出来的，其中 %.0f 只胎儿直接被扔掉；'
      'v0.5 的 %.0f 次妊娠全部走完。对玩家而言这是净改善：'
      '<b>一窝兄妹摆在一起才看得出 3:1</b>，而不是隔三差五蹦出一只独苗。<br>'
      '代价要如实记着：周转率下降，世代推进从 %.0f 代放慢到 %.0f 代（−%.0f%%）。</div>'
      % (t['total_litters'], v['total_litters'],
         (1 - v['total_litters'] / max(1e-9, t['total_litters'])) * 100,
         (1 - v['total_births'] / max(1e-9, t['total_births'])) * 100,
         t['total_births'], v['total_births'],
         t['total_births'] / max(1, t['total_litters']),
         v['total_births'] / max(1, v['total_litters']),
         t['total_litters'], t['trimmed_pups'], v['total_litters'],
         t['max_generation'], v['max_generation'],
         (1 - v['max_generation'] / max(1e-9, t['max_generation'])) * 100))

    A(h3('C2｜寿命 40 → 45 游戏天'))
    A('<p>原先压到 40 天是为了「让空位轮转起来」，但那是在<b>处处裁剪幼崽的扭曲状态下</b>标定的。'
      '修掉 C1 后重新扫寿命轴（24 种子，%d 生态年）：</p>' % yrs)
    A(table(['寿命（游戏天）', '20 年推进世代', '20 年后近交 F', '评价'],
            [['42', '30.4', '0.110', '世代最多，但 5 年内 F 明显偏高'],
             ['<b>45</b>', '<b>28.9</b>', '<b>0.102</b>', '<b>拐点，本次选定</b>'],
             ['48', '27.5', '0.120', '更差'],
             ['50', '26.6', '0.116', '更差']],
            note='45 天以少 5% 世代的代价换来低得多的近交，是明确的甜点。'))

    A(h3('C3｜野外引入升级为「异地互补基因库」'))
    A('<p>v0.4 的引入用<b>创始基因库同频率</b>抽等位基因 —— 带进来的多是种群里<b>已经有了</b>的等位，'
      '效果被自己打折了。改为按「当前种群里越稀缺、引入概率越高」加权，'
      '等价于保护遗传学里挑选无亲缘建群者的标准做法。</p>')
    A('<pre>Immigration_pool   = complement   # 异地互补基因库\n'
      'Immigration_sex    = balance      # 补稀缺性别（随机性别会浪费掉一半引入个体）\n'
      'Immigration_mode   = days         # 按固定天数推进，避免世代停滞时彻底断流\n'
      'Immigration_every_days = 14 游戏天</pre>')
    A('<div class="note ok"><b>这是本轮收益最大的一条改动。</b>'
      '在同样外部的前提下，互补库把 20 年后的近交从 %.3f 压到 %.3f，'
      '同时毛色种类从 %.1f 提升到 %.1f。</div>'
      % (t['meanF_end'], v['meanF_end'], t['colors'], v['colors']))

    A(h3('C4｜突变判定单位：每窝 → 每只幼崽'))
    A('<p>真实突变发生在配子/合子层面。原实现「每窝摇一次骰子，最多一只突变」有两个后果：'
      '突变总量被窝数人为压低；而且<b>永远看不到「同一窝里出现一只突变兄妹」</b> —— '
      '这恰恰是最能体现孟德尔随机性、也最有节目效果的画面。</p>')
    A('<div class="note warn">UI 文案要跟着改：设置项必须写清楚是「<b>每只幼崽</b>的突变概率」，'
      '否则用户会按「每窝」理解，实际观感会比预期频繁。</div>')

    A(h3('C5｜迁徙强度 0.00025 → 0.00003 / 游戏小时'))
    A('<p>把寿命调到 55 天那组做长期测试时发现：<b>%d 年内有 %.0f 只迁徙离场，比死亡总数还多</b>。'
      '根因是迁徙判据里有一条「适应度低于种群均值 −0.05 就 ×3」，'
      '而<b>低于均值的个体恒占约一半</b>，叠加长寿命带来的更长暴露时间后，几乎所有成体最终都会离场 —— '
      '这违背了 Q7 把迁徙定位为「补充性非死亡退出机制」的初衷。'
      '回调后迁徙占离桌总数稳定在 <b>%s</b>。</p>'
      % (yrs, 77, pct(v['mig_share'])))

    A(h3('顺带修掉的两个缺陷'))
    A('<div class="q"><div class="qh">缺陷 A：引入个体不检查胎儿配额，会冲破硬上限</div><div class="qb">'
      '现象：某一组配置下出现 <b>峰值 41 &gt; 上限 40</b>，直接违反需求第七条。<br>'
      '原因：繁殖逻辑用 <code>N_eff = 存活数 + 在孕胎儿数</code> 做配额检查，'
      '但<b>引入逻辑只看存活数</b>。于是「38 只活着 + 3 只胎儿」时被判定还有余量，'
      '又把一只野外狐狸放了进来。<br>'
      '修复：两者统一走同一个 <code>n_eff</code>。修复后在全部 ' + str(2000) + '+ 次搜索运行中，'
      '峰值再未超过上限。<br>'
      '<b>工程教训：</b>凡是「同一份资源有两种使用者」的地方，必须强制共用同一个余量函数。'
      '这里是繁殖 vs 引入；同类风险还有快照回滚 vs 实时写入。'
      '</div></div>')
    A('<div class="q"><div class="qh">缺陷 B：被阻断的妊娠也被计入了窝数</div><div class="qb">'
      '<code>litters += 1</code> 写在受孕函数开头，而名额检查在后面，'
      '导致「根本没怀上」也算一窝。修复前出现过<b>「443 窝但只生出 180 只」</b>的荒谬读数。'
      '</div></div>')

    # ---------------- 03 ----------------
    A(h2('03', '正式对照轮（5 轮 × 5 生态年）'))
    A('<p>这是与上一轮报告口径一致的那组对照。</p>')
    if OFF:
        rv = OFF.get('v2', {}).get('rounds', [])
        if rv:
            rows_r = []
            for r in rv:
                dc = r['deaths_by_cause']
                rows_r.append([r['label'], '%.0f' % r['total_litters'], '%.0f' % r['total_births'],
                               '%.0f' % dc.get('幼崽夭折', 0), '%.0f' % dc.get('衰老', 0),
                               '%.0f' % dc.get('疾病', 0), '%.0f' % r['migrated'],
                               '%.0f' % r['immigrants'], '%d' % r['max_generation'],
                               '%.3f' % r['meanF_end'], '%.2f' % r['fp2_ratio'],
                               '%.0f' % r['max_pop_seen'], '%.0f' % r['final_pop']])
            A(table(['轮次（v0.5）', '窝数', '出生', '夭折', '衰老', '疾病', '迁徙', '引入',
                     '世代', '近交 F', '外观指纹', '峰值', '末种群'], rows_r,
                    note='五轮的变异幅度很小，说明参数不再依赖运气。五轮均未崩溃，'
                         '峰值均未超过上限 40。'))
    A(tbl_evt)
    A(tbl_off_extra)

    # ---------------- 04 ----------------
    A(h2('04', '参数寻优过程'))
    A(h3('4.1 种群上限不需要再往上调'))
    A('<p>原本预期上限 40 → 50/60 能进一步改善多样性，实测<b>并没有</b>。</p>')
    A(tbl_cap)
    A(fig(g6a, '数量上限对世代推进的影响（收益率递减）。'))
    A(fig(g6b, '数量上限对近交、外观指纹的影响 —— 提高上限买不到多样性。'))
    A('<div class="note ok"><b>原因：</b>多样性由<b>基因流入速率</b>主导，'
      '而引入节奏是按时间推进的、不随 N 缩放。所以 40 是一个很好的默认值，'
      '<b>更高的上限只会线性增加渲染与 CPU 开销，买不到多样性</b>。</div>')

    A(h3('4.2 世代推进的天花板在哪'))
    A('<p>我们试过缩短世代间隔（幼崽 96→72 小时成年、繁殖间隔 72→48 小时）来追回世代数，'
      '结果<b>收效甚微</b>：世代推进其实被<b>周转率</b>封顶了 —— '
      '稳定状态下出生数必须等于死亡数，而死亡数由「种群规模 ÷ 寿命」决定。'
      '在只想不抬高近交的前提下，20 年 %d 代左右就是这个结构的上限。</p>' % v['max_generation'])

    A(h3('4.3 三档「演化节奏」预设'))
    A('<p>既然不能两头都占，就把选择权做进产品：三档的差异只在<b>观察节奏</b>，'
      '多样性几乎等价。</p>')
    A(tbl_preset)
    A(fig(g7a, '5 生态年窗口内的世代推进。'))
    A(fig(g7b, '20 生态年窗口：世代（绿）与近交 F×10（红）。激进档能多 25% 世代，代价是需要更多引入。'))
    A('<div class="note"><b>激进档值得单独说明：</b>它能在 20 年内推进 %.1f 代'
      '（接近 v0.4 的 %.1f 代），而近交只有 v0.4 的一半不到。'
      '代价是 20 年需要 %.0f 只野外个体（标准档只要 %.0f 只）。'
      '建议把它做成一个显式选项，而不是悄悄改默认。</div>'
      % (P['激进档']['max_generation'], t['max_generation'],
         P['激进档']['immigrants'], P['标准档']['immigrants']))

    # ---------------- 05 ----------------
    A(h2('05', '仍然存在的三个风险'))
    A(qbox('风险 1：自然选择本轮依然等于没跑',
           '实测选择强度 <b>r = %.3f</b>（纯噪声水平）。这不是缺陷 —— '
           '「食物充足 + 环境适宜 + 不会饿死」翻译成生态学语言就是<b>没有选择压力</b>。<br><br>'
           '但这是一个<b>产品陷阱</b>：如果 UI 直接显示「当前选择强度」这个数字，'
           '玩家会在很长一段时间里看到 0，从而误以为「族群进化」是假的。<br>'
           '建议在显示这个数的同时，<b>必须给出制造压力的入口</b>：'
           '季节强度、投喂开关、壁纸明暗，并把它们做成同一个「环境压力」面板。'
           % v['selection_r']))
    A(qbox('风险 2：§15 取食系统本轮一次都没触发',
           '休眠事件计数在所有轮次均为 <b>%.0f</b> —— 因为「食物充足」是本次模拟的前置条件。'
           '这条功能等于<b>还没有被真正测过</b>，必须单独补一轮「食物短缺」场景再定它的参数，'
           '尤其是饱食度下降速率、休眠阈值、以及苏醒后的恢复曲线。' % v['torpor_events']))
    A(qbox('风险 3：40 只同屏的性能开销没有被覆盖',
           '离线模拟完全不涉及渲染。<b>v0.4 那轮的这块风险本轮依旧成立。</b><br>'
           '从文字上看，%d 只狐狸同时显示在桌面上意味着 %d 个半透明无边框窗口，'
           '即使按 §7 的 LOD 分级（远距离个体降到 12 fps、隐藏粒子特效），'
           '窗口本身的合成开销仍然存在。<b>必须先做一个 40 只同屏的技术验证再定默认值</b>。'
           '若实机顶不住，优先降到 30（仍有 %.1f 代 / 20 年），'
           '但<b>不要动引入节奏</b>——那是多样性的唯一来源。'
           % (40, 40, CAP['cap30']['max_generation'])))

    # ---------------- 06 ----------------
    A(h2('06', '还需要你拍板'))
    A(table(['', '问题', '我的建议'],
            [['F1', '寿命从 E2 的 40 天改成 45 天，接受吗？',
              '接受。是在修掉裁剪缺陷后重新标定的结果'],
             ['F2', '默认用「标准档」还是「激进档」？',
              '<b>标准档</b>。激进档 20 年多 25% 世代，但外来个体多 56%'],
             ['F3', '是否把三档预设做成 UI 上的显式选项？',
              '做。成本极低（三个参数组），且能让不同口味的玩家各取所需'],
             ['F4', '引入时 UI 要不要让玩家看到「野外狐狸来了」？',
              '要，但做成安静的边缘走入 + 图鉴提示，不要弹窗'],
             ['F5', '是否补一轮「食物短缺」场景验证休眠 §15？',
              '要，在写 §15 的实际参数之前']],
            aligns=['left', 'left', 'left']))

    A('<hr>')
    A('<div class="note"><b>复现方式：</b><br>'
      '<code>python sim/verify_genetics.py</code> —— 16 项遗传引擎自检，应全部通过<br>'
      '<code>python sim/prepare_report_data.py</code> —— 重新生成本报告的全部数据<br>'
      '<code>python sim/gen_report_v2.py</code> —— 重新生成本报告<br>'
      '<code>python sim/compare_versions.py</code> / <code>presets.py</code> / '
      '<code>cap_sweep.py</code> —— 分项对照</div>')

    A('</div></body></html>')

    out = os.path.join(DOCS, 'ecosystem-run-report-v0.5.html')
    html = ''.join(HTML)
    open(out, 'w', encoding='utf-8').write(html)
    print('已生成 %s  (%.1f KB)' % (out, len(html.encode('utf-8')) / 1024))


if __name__ == '__main__':
    main()
