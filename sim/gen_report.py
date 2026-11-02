# -*- coding: utf-8 -*-
"""
由 sim/results_*.json 生成 HTML 运行报告。

    python sim/gen_report.py
产出：docs/sim-run-report-v0.3.html
"""

import json
import os
import statistics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, 'docs')

C_INK = '#1F2328'
C_MUTE = '#6B7280'
C_LINE = '#D8DEE6'
C_BASE = '#C0392B'      # 原规则：红
C_TUNE = '#2E7D5B'      # 改进：绿
C_BLUE = '#378ADD'
C_AMBER = '#B7791F'


# ============================ SVG 工具 ============================

def esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def T_(x, y, s, fill=C_INK, size=11, anchor=None, weight=None):
    a = ' text-anchor="%s"' % anchor if anchor else ''
    w = ' font-weight="%s"' % weight if weight else ''
    return ('<text x="%.1f" y="%.1f" fill="%s" font-size="%d"%s%s>%s</text>'
            % (x, y, fill, size, a, w, esc(s)))


def frame(w, h, pad=46):
    return ('<svg viewBox="0 0 %d %d" width="100%%" style="max-width:%dpx" xmlns="http://www.w3.org/2000/svg">'
            % (w, h, w))


def axes(pad, w, h, xt, yt, xlabels, y_fmt, ymin, ymax, nyt=5):
    o = []
    pw = w - pad - 14
    ph = h - pad - 30
    for i in range(nyt + 1):
        yy = pad + ph - ph * i / nyt
        val = ymin + (ymax - ymin) * i / nyt
        o.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s" stroke-width="1"/>'
                 % (pad, yy, pad + pw, yy, C_LINE))
        o.append(T_(pad - 6, yy + 3.5, y_fmt % val if '%' in y_fmt else y_fmt.format(val),
                    C_MUTE, 10, 'end'))
    if xlabels:
        n = len(xlabels)
        for i, lab in enumerate(xlabels):
            xx = pad + pw * i / max(1, n - 1)
            o.append(T_(xx, h - 12, lab, C_MUTE, 10, 'middle'))
    o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1.2"/>'
             % (pad, pad, pad, pad + ph, '#9AA5B1'))
    o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1.2"/>'
             % (pad, pad + ph, pad + pw, pad + ph, '#9AA5B1'))
    return ''.join(o), pad, w - pad - 14, pad, h - pad - 30


def line_chart(series, w=760, h=280, ymax=1.0, ymin=0.0, yfmt='%.0f', xlabels=None,
               xtitle='', marker_step=0):
    """series: [(name, color, [v...]), ...]"""
    pad = 46
    pw = w - pad - 14
    ph = h - pad - 30
    o = [frame(w, h)]
    grid, _, _, _, _ = axes(pad, w, h, '', '', xlabels, yfmt, ymin, ymax)
    o.append(grid)
    for name, color, vals in series:
        pts = []
        for i, v in enumerate(vals):
            xx = pad + pw * (i / max(1, len(vals) - 1))
            vv = min(ymax, max(ymin, v))
            yy = pad + ph - ph * (vv - ymin) / max(1e-9, (ymax - ymin))
            pts.append('%.1f,%.1f' % (xx, yy))
        o.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="1.9" '
                 'stroke-linejoin="round" opacity="0.95"/>' % (' '.join(pts), color))
    # 图例
    lx = pad + 4
    for name, color, _ in series:
        o.append('<rect x="%d" y="%d" width="16" height="3" rx="1.5" fill="%s"/>' % (lx, h - 22, color))
        o.append(T_(lx + 21, h - 18, name, C_MUTE, 10))
        lx += 26 + len(name) * 8
    if xtitle:
        o.append(T_(pad + pw / 2, h - 2, xtitle, C_MUTE, 10, 'middle'))
    o.append('</svg>')
    return ''.join(o)


def grouped_bar(cats, series, w=760, h=250, ymax=None, yfmt='%.0f', unit=''):
    pad = 46
    pw = w - pad - 14
    ph = h - pad - 34
    if ymax is None:
        ymax = max(max(s[2]) for s in series) * 1.18
    o = [frame(w, h)]
    grid, _, _, _, _ = axes(pad, w, h, '', '', cats, yfmt, 0, ymax)
    o.append(grid)
    n = len(series)
    gw = pw / max(1, len(cats))
    bw = min(28, gw * 0.7 / n)
    for si, (name, color, vals) in enumerate(series):
        for ci, v in enumerate(vals):
            cx = pad + gw * ci + gw / 2
            x = cx - (n * bw) / 2 + si * bw
            hh = ph * min(v, ymax) / ymax
            o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" fill="%s"/>'
                     % (x, pad + ph - hh, bw - 2, hh, color))
            o.append(T_(x + bw / 2 - 1, pad + ph - hh - 4, yfmt % v + unit, C_MUTE, 9, 'middle'))
    lx = pad + 4
    for name, color, _ in series:
        o.append('<rect x="%d" y="%d" width="13" height="9" rx="2" fill="%s"/>' % (lx, h - 20, color))
        o.append(T_(lx + 18, h - 12, name, C_MUTE, 10))
        lx += 24 + len(name) * 8
    o.append('</svg>')
    return ''.join(o)


def stacked_bar(cats, stacks, colors, w=760, h=230):
    """stacks: dict key -> [per-cat values]；图例放在右侧，画布相应加宽"""
    pad = 60
    pw = w - pad - 14
    ph = h - pad - 34
    total_w = w + 130
    o = [frame(total_w, h, total_w)]
    o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#9AA5B1"/>'
             % (pad, pad + ph, pad + pw, pad + ph))
    gw = pw / max(1, len(cats))
    bw = min(70, gw * 0.55)
    keys = list(stacks.keys())
    for ci, cat in enumerate(cats):
        tot = sum(stacks[k][ci] for k in keys) or 1
        cy = pad + ph
        cx = pad + gw * ci + gw / 2 - bw / 2
        for k in keys:
            v = stacks[k][ci]
            if v <= 0:
                continue
            hh = ph * v / tot
            cy -= hh
            o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
                     % (cx, cy, bw, hh, colors.get(k, '#999')))
            if hh > 13:
                o.append(T_(cx + bw / 2, cy + hh / 2 + 3.5, '%d' % v, '#fff', 10, 'middle'))
        o.append(T_(pad + gw * ci + gw / 2, pad + ph + 15, cat, C_MUTE, 10, 'middle'))
    ly = pad - 34
    o.append(T_(pad + pw + 8, ly, '毛色', C_MUTE, 10))
    for k in keys:
        o.append('<rect x="%.0f" y="%.0f" width="12" height="9" rx="2" fill="%s"/>'
                 % (pad + pw + 8, ly + 8, colors.get(k, '#999')))
        o.append(T_(pad + pw + 24, ly + 16, k, C_MUTE, 10))
        ly += 15
    o.append('</svg>')
    return ''.join(o)


# ============================ 数据 ============================

def load(variant):
    p = os.path.join(ROOT, 'sim', 'results_%s_r5_y5.json' % variant)
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def agg(rounds, key):
    return statistics.mean([r[key] for r in rounds])


def main():
    base = load('base')
    tuned = load('tuned')
    rb, rt = base['rounds'], tuned['rounds']
    PB, PT = base['params'], tuned['params']

    mean_b = {
        'litters': agg(rb, 'total_litters'), 'births': agg(rb, 'total_births'),
        'deaths': agg(rb, 'total_deaths'), 'migrated': agg(rb, 'migrated'),
        'gens': agg(rb, 'max_generation'), 'het0': agg(rb, 'het_start'),
        'het1': agg(rb, 'het_end'), 'F': agg(rb, 'meanF_end'),
        'capday': agg(rb, 'cap_day'), 'capratio': agg(rb, 'cap_ratio'),
        'lines': agg(rb, 'founder_lines_alive'), 'peak': max(r['max_pop_seen'] for r in rb),
        'fp': agg(rb, 'unique_fingerprints'), 'colors': statistics.mean([len(r['end_colors']) for r in rb]),
        'muts': agg(rb, 'mutations_total'), 'muts_alive': agg(rb, 'mutations_survived'),
        'finalpop': agg(rb, 'final_pop'), 'meanpop': agg(rb, 'mean_pop'),
        'selr': agg(rb, 'selection_r'), 'fitspread': agg(rb, 'fit_spread'),
        'juv': agg(rb, 'deaths_by_cause').get('幼崽夭折', 0) if False else None,
    }
    mean_t = {
        'litters': agg(rt, 'total_litters'), 'births': agg(rt, 'total_births'),
        'deaths': agg(rt, 'total_deaths'), 'migrated': agg(rt, 'migrated'),
        'gens': agg(rt, 'max_generation'), 'het0': agg(rt, 'het_start'),
        'het1': agg(rt, 'het_end'), 'F': agg(rt, 'meanF_end'),
        'capday': agg(rt, 'cap_day'), 'capratio': agg(rt, 'cap_ratio'),
        'lines': agg(rt, 'founder_lines_alive'), 'peak': max(r['max_pop_seen'] for r in rt),
        'fp': agg(rt, 'unique_fingerprints'), 'colors': statistics.mean([len(r['end_colors']) for r in rt]),
        'muts': agg(rt, 'mutations_total'), 'muts_alive': agg(rt, 'mutations_survived'),
        'finalpop': agg(rt, 'final_pop'), 'meanpop': agg(rt, 'mean_pop'),
        'selr': agg(rt, 'selection_r'), 'fitspread': agg(rt, 'fit_spread'),
        'juv': None,
    }
    causes_b = {k: statistics.mean([r['deaths_by_cause'].get(k, 0) for r in rb])
                for k in ('幼崽夭折', '衰老', '疾病')}
    causes_t = {k: statistics.mean([r['deaths_by_cause'].get(k, 0) for r in rt])
                for k in ('幼崽夭折', '衰老', '疾病')}

    xlabels = ['Y0', 'Y1', 'Y2', 'Y3', 'Y4', 'Y5']

    # ---- 图 1：种群曲线（各轮 + 均值）----
    def daily_series(rounds, key):
        out = []
        for i, r in enumerate(rounds):
            out.append((r['label'], '#9AA5B1' if key != 'pop' else '#BAC3CE', [d[key] for d in r['daily']]))
        return out

    fig_pop_b = line_chart(
        daily_series(rb, 'pop') + [('均值', C_BASE,
                                    [statistics.mean([r['daily'][i]['pop'] for r in rb])
                                     for i in range(len(rb[0]['daily']))])],
        ymax=PB['N_max'] * 1.5, yfmt='%.0f', xlabels=xlabels, xtitle='生态年')
    fig_pop_t = line_chart(
        daily_series(rt, 'pop') + [('均值', C_TUNE,
                                    [statistics.mean([r['daily'][i]['pop'] for r in rt])
                                     for i in range(len(rt[0]['daily']))])],
        ymax=PT['N_max'] * 1.35, yfmt='%.0f', xlabels=xlabels, xtitle='生态年')

    # ---- 图 2：ρ 与 L ----
    fig_rho = line_chart(
        [('原规则 ρ', '#D9A3A3', [statistics.mean([r['daily'][i]['rho'] for r in rb])
                                  for i in range(len(rb[0]['daily']))]),
         ('原规则 L(ρ)', C_BASE, [statistics.mean([r['daily'][i]['L'] for r in rb])
                                  for i in range(len(rb[0]['daily']))]),
         ('改进后 ρ', '#A9CDBA', [statistics.mean([r['daily'][i]['rho'] for r in rt])
                                  for i in range(len(rt[0]['daily']))]),
         ('改进后 L(ρ)', C_TUNE, [statistics.mean([r['daily'][i]['L'] for r in rt])
                                  for i in range(len(rt[0]['daily']))])],
        ymax=1.05, yfmt='%.1f', xlabels=xlabels, xtitle='拥挤度 ρ 与繁殖欲望 L — 原规则几乎全程贴在 1 / 0')

    # ---- 图 3：遗传多样性 ----
    fig_div = line_chart(
        [('原规则 观察杂合度', C_BASE, [statistics.mean([r['daily'][i]['het_o'] for r in rb])
                                        for i in range(len(rb[0]['daily']))]),
         ('改进后 观察杂合度', C_TUNE, [statistics.mean([r['daily'][i]['het_o'] for r in rt])
                                        for i in range(len(rt[0]['daily']))]),
         ('原规则 平均近交 F', '#E4A0A0', [statistics.mean([r['daily'][i]['meanF'] for r in rb])
                                          for i in range(len(rb[0]['daily']))]),
         ('改进后 平均近交 F', '#8FC4A9', [statistics.mean([r['daily'][i]['meanF'] for r in rt])
                                          for i in range(len(rt[0]['daily']))])],
        ymax=0.62, yfmt='%.2f', xlabels=xlabels, xtitle='24 个位点平均杂合度与平均近交系数')

    # ---- 图 4：关键指标对比 ----
    cats = ['5年窝数', '出生数', '最大世代', '存活创始系', '外观指纹数', '新突变', '突变存活']
    fig_cmp = grouped_bar(
        cats,
        [('原规则 v0.3', C_BASE, [mean_b['litters'], mean_b['births'], mean_b['gens'],
                                  mean_b['lines'], mean_b['fp'], mean_b['muts'], mean_b['muts_alive']]),
         ('改进方案 v0.4', C_TUNE, [mean_t['litters'], mean_t['births'], mean_t['gens'],
                                    mean_t['lines'], mean_t['fp'], mean_t['muts'], mean_t['muts_alive']])],
        ymax=None, yfmt='%.0f')

    # ---- 图 5：风险指标对比 ----
    cats2 = ['末期平均近交 F', '峰值/上限', '处于 ρ=1 天数占比']
    fig_risk = grouped_bar(
        cats2,
        [('原规则 v0.3', C_BASE, [mean_b['F'], mean_b['peak'] / PB['N_max'] * 100, mean_b['capratio'] * 100]),
         ('改进方案 v0.4', C_TUNE, [mean_t['F'], mean_t['peak'] / PT['N_max'] * 100, mean_t['capratio'] * 100])],
        ymax=180, yfmt='%.0f', unit='')

    # ---- 图 6：末代毛色构成 ----
    color_keys = ['赤橙', '奶油金', '霜灰', '淡银蓝', '墨黑', '雾霭蓝', '幽夜紫', '淡雾紫', '雪绒白']
    palette = {'赤橙': '#E08A3C', '奶油金': '#EFD8AC', '霜灰': '#9BA5B0', '淡银蓝': '#B7CBD9',
               '墨黑': '#4C4653', '雾霭蓝': '#7BA7CE', '幽夜紫': '#A98AD2', '淡雾紫': '#C3B2DC',
               '雪绒白': '#DDD9D4'}


    def merge_colors(rounds):
        m = {}
        for k in color_keys:
            vals = [r['end_colors'].get(k, 0) for r in rounds]
            m[k] = vals
        # 只保留出现过的
        return {k: v for k, v in m.items() if sum(v) > 0}

    fig_color_b = stacked_bar(['R1', 'R2', 'R3', 'R4', 'R5'], merge_colors(rb), palette)
    fig_color_t = stacked_bar(['R1', 'R2', 'R3', 'R4', 'R5'], merge_colors(rt), palette)

    # ============================ HTML ============================
    def rowsillin(rounds, P):
        o = []
        for r in rounds:
            dc = r['deaths_by_cause']
            over = r['max_pop_seen'] - P['N_max']
            o.append('<tr><td><b>%s</b><br><small>种子 %d</small></td>'
                     '<td>%d</td><td>%d</td>'
                     '<td>%d / %d / %d</td><td>%d</td><td>%d</td>'
                     '<td style="color:%s"><b>%d</b></td>'
                     '<td>%.3f → %.3f</td><td>%.3f</td>'
                     '<td>D%d</td><td>%.0f%%</td><td>%d / 10</td>'
                     '<td>%d</td><td>%d (存活%d)</td></tr>' % (
                         r['label'], r['seed'], r['total_litters'], r['total_births'],
                         dc.get('幼崽夭折', 0), dc.get('衰老', 0), dc.get('疾病', 0),
                         r['migrated'], r['immigrants'],
                         C_BASE if over > 0 else C_MUTE, r['max_pop_seen'],
                         r['het_start'], r['het_end'], r['meanF_end'],
                         r['cap_day'] if r['cap_day'] is not None else -1,
                         r['cap_ratio'] * 100, r['founder_lines_alive'],
                         r['unique_fingerprints'], r['mutations_total'], r['mutations_survived']))
        return ''.join(o)

    HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>幻想小狐狸生态系统 · 5 轮模拟运行报告</title>
<style>
:root{{--ink:{{ink}};--tx2:#4A5158;--tx3:#6B7280;--line:{{line}};--bg:#FFFFFF;--soft:#F7F9FB;
--accent:#3B6FD4;--accent-bg:#EDF2FC;--warn:#B7791F;--warn-bg:#FDF6E7;--bad:#C0392B;--bad-bg:#FBEEEB;--ok:#2E7D5B;--ok-bg:#EAF5F0;}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:"PingFang SC","Microsoft YaHei","Segoe UI",system-ui,sans-serif;
color:var(--ink);background:#F2F4F7;line-height:1.75;font-size:14px}}
.wrap{{max-width:1000px;margin:0 auto;background:var(--bg);padding:0 0 50px;box-shadow:0 0 40px rgba(0,0,0,.05)}}
header{{padding:34px 40px 22px;border-bottom:1px solid var(--line);background:linear-gradient(180deg,#FBF7F2,var(--bg))}}
h1{{margin:0 0 6px;font-size:25px;letter-spacing:.5px}}
.sub{{color:var(--tx3);font-size:13px}}
.meta{{margin-top:10px;font-size:12.5px;color:var(--tx3)}}
main{{padding:0 40px}}
h2{{font-size:19px;margin:34px 0 12px;padding-bottom:8px;border-bottom:2px solid var(--line)}}
h2 .no{{display:inline-block;min-width:34px;color:#fff;background:var(--accent);border-radius:5px;
font-size:12px;text-align:center;padding:2px 7px;margin-right:9px;vertical-align:2px}}
h3{{font-size:15px;margin:22px 0 8px;color:var(--tx2)}}
p{{margin:9px 0}}
table{{width:100%;border-collapse:collapse;margin:12px 0;font-size:12.5px}}
th,td{{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}}
th{{background:var(--soft);font-weight:600;font-size:12px;text-align:center}}
td{{text-align:center}}
td:first-child{{text-align:left}}
tr:nth-child(even) td{{background:#FCFDFE}}
small{{color:var(--tx3)}}
.note{{border-left:4px solid var(--accent);background:var(--accent-bg);padding:11px 15px;border-radius:0 7px 7px 0;margin:13px 0;font-size:13px}}
.note.warn{{border-color:var(--warn);background:var(--warn-bg)}}
.note.bad{{border-color:var(--bad);background:var(--bad-bg)}}
.note.ok{{border-color:var(--ok);background:var(--ok-bg)}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
.grid3{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}
.card{{border:1px solid var(--line);border-radius:9px;padding:14px 16px;background:#fff}}
.fig{{border:1px solid var(--line);border-radius:9px;padding:10px;margin:12px 0;background:#fff}}
.cap{{font-size:12px;color:var(--tx3);margin:4px 0 10px}}
.stat{{text-align:center}}
.stat .v{{font-size:26px;font-weight:600;font-family:Consolas,monospace}}
.stat .l{{font-size:12px;color:var(--tx3)}}
.stat .d{{font-size:11.5px;color:var(--warn);margin-top:2px}}
.chip{{display:inline-block;padding:1px 8px;border-radius:9px;font-size:11.5px;background:#EEF1F5;color:var(--tx2);margin:0 3px 3px 0}}
.chip.b{{background:var(--bad-bg);color:var(--bad)}}
.chip.g{{background:var(--ok-bg);color:var(--ok)}}
.chip.y{{background:var(--warn-bg);color:var(--warn)}}
code{{background:#F1F3F6;padding:1px 5px;border-radius:4px;font-size:12.5px;font-family:Consolas,monospace}}
.q{{border:1px solid var(--line);border-radius:9px;margin:11px 0;overflow:hidden}}
.qh{{background:var(--soft);padding:9px 14px;font-weight:600;font-size:13.5px;border-bottom:1px solid var(--line)}}
.qb{{padding:11px 15px;font-size:13px}}
footer{{margin:34px 40px 0;padding-top:16px;border-top:1px solid var(--line);color:var(--tx3);font-size:12px}}
.ev{{font-family:Consolas,monospace;font-size:12px;background:#F7F9FB;border:1px solid var(--line);
border-radius:6px;padding:8px 11px;margin:8px 0;color:#374151}}
</style></head><body><div class="wrap">

<header>
  <h1>幻想小狐狸生态系统 · 模拟运行报告</h1>
  <div class="sub">按 v0.3 已固化规则离线跑 5 轮 × 5 生态年 · 食物充足 · 环境适宜 · 全程加速模式</div>
  <div class="meta">模拟引擎：<code>sim/fox_ecosystem_sim.py</code>　｜　遗传自检：<code>sim/verify_genetics.py</code>（16 项全通过）<br>
  数据：<code>sim/results_base_r5_y5.json</code>　｜　对照：<code>sim/results_tuned_r5_y5.json</code></div>
</header>

<main>

<h2><span class="no">01</span>一句话结论</h2>
<div class="note bad"><b>按现在的规则，这个生态系统在第 6 游戏天就停了。</b><br>
5 轮全部在开局的<b>第 6 天</b>撞到数量上限（20 只），此后 <b>{bcap:.0f}% 的时间</b>拥挤度 ρ 恒等于 1、繁殖欲望 L 恒等于 0。
剩下的 5 个生态年基本是靠"有狐狸老死 → 补一个空位"在维持，5 年只发生 <b>{blit:.0f} 窝</b>繁殖、
只推进了 <b>{bgen:.1f} 代</b>、全种群只出现过 <b>{bmuts:.0f} 次</b>突变。<br>
更糟的是它<b>没有守住你自己的硬要求</b>：峰值种群达到 <b>{bpeak}</b> 只，超过 20 的上限达 <b>{bover:.0f}%</b>。
而在画面上，20 只狐狸最终只剩下 <b>{bcolors:.1f} 种毛色</b>、最多 <b>{bfp:.1f} 种外观组合</b>——
"不同基因组合形成不同外观"这条核心需求，在跑满 5 年后实际上失效了。</div>

<div class="grid3">
  <div class="card stat"><div class="v" style="color:var(--bad)">{bcap:.0f}%</div><div class="l">处于「繁殖完全停止」状态的时间占比</div><div class="d">ρ=1 意味着 L=0</div></div>
  <div class="card stat"><div class="v" style="color:var(--bad)">第 {bcapday:.0f} 天</div><div class="l">撞上限的平均时间</div><div class="d">总时长 120 游戏天</div></div>
  <div class="card stat"><div class="v" style="color:var(--bad)">{bpeak} 只</div><div class="l">峰值种群（上限 {bnmax}）</div><div class="d">超出 {bover:.0f}%</div></div>
</div>

<h2><span class="no">02</span>实验怎么搭的</h2>
<p>没有启动桌宠，只跑逻辑层。生态时钟按 <code>1 游戏小时 = 1 tick</code> 推进，5 生态年 = <b>2880 个 tick</b>，
等价于 <b>1× 流速下连续跑 48 真实小时</b>、或 <b>10× 流速下跑 4.8 小时</b>。因为是纯逻辑模拟，实际耗时约 0.3 秒。</p>

<h3>2.1 参数的两种来源</h3>
<p>设计稿里有一部分数值是<b>已经写死的</b>，还有一部分<b>只写了概念、没给数字</b>。后者我按生态学惯例标定了初值，标定值都列在下表里，方便你直接改。</p>
<table>
<thead><tr><th style="width:150px">参数</th><th style="width:110px">取值</th><th>来源</th></tr></thead>
<tbody>
<tr><td>数量上限 N_max</td><td>20</td><td>设计稿 §7 默认值</td></tr>
<tr><td>密度曲线 k</td><td>3</td><td>§9.1 推荐值</td></tr>
<tr><td>胎儿计入 N_eff</td><td>是</td><td>Q13A</td></tr>
<tr><td>妊娠 / 繁殖间隔 / 最低繁殖年龄</td><td>48h / 72h / 成年+12h</td><td>§5 UI 表</td></tr>
<tr><td>性成熟门槛</td><td>40 / 100 健康 · 50 / 100 饱食</td><td>§5 UI 表</td></tr>
<tr><td>每窝仔数</td><td>3 – 6</td><td>Q9C</td></tr>
<tr><td>幼崽夭折率</td><td>25% – 35%</td><td>Q9C · 创始代减半（D3）</td></tr>
<tr><td>近交阈值 / 放弃概率</td><td>r ≥ 0.125 时 50% 放弃</td><td>Q6B + 你的补充</td></tr>
<tr><td>突变率</td><td>每窝 1.5%</td><td>Q5A 默认</td></tr>
<tr><td>创始世代</td><td>10 只幼崽，r = 0</td><td>Q12 / B5</td></tr>
<tr><td style="background:#FFF8F4">幼崽→成年</td><td style="background:#FFF8F4">96 游戏小时</td><td style="background:#FFF8F4"><b>模拟器标定</b>（文档未定）</td></tr>
<tr><td style="background:#FFF8F4">寿命</td><td style="background:#FFF8F4">正态 60±10 天，截断 [35,95]</td><td style="background:#FFF8F4"><b>模拟器标定</b>（文档未定）</td></tr>
<tr><td style="background:#FFF8F4">老年起点</td><td style="background:#FFF8F4">寿命的 70%</td><td style="background:#FFF8F4"><b>模拟器标定</b></td></tr>
<tr><td style="background:#FFF8F4">每小时基础发病率</td><td style="background:#FFF8F4">0.16%</td><td style="background:#FFF8F4"><b>模拟器标定</b></td></tr>
<tr><td style="background:#FFF8F4">求偶间隔</td><td style="background:#FFF8F4">3.2 游戏小时</td><td style="background:#FFF8F4">取自 §9.4 界面文案</td></tr>
<tr><td style="background:#FFF8F4">创始等位基因频率</td><td style="background:#FFF8F4">见代码 FOUNDER_FREQ</td><td style="background:#FFF8F4"><b>模拟器标定</b>（稀有性状初始为 0，只能靠突变产生）</td></tr>
</tbody></table>

<h3>2.2 先证明模拟器没有算错</h3>
<p>在拿结论说事之前，遗传引擎本身必须过关。<code>sim/verify_genetics.py</code> 跑 16 项断言，全部通过：</p>
<table>
<thead><tr><th style="width:170px">验证项</th><th>实测</th><th style="width:120px">期望</th></tr></thead>
<tbody>
<tr><td>完全显性分离比</td><td>赤橙 0.751 / 霜灰 0.249</td><td>3 : 1</td></tr>
<tr><td>隐性性状隔代重现（dd）</td><td>0.253</td><td>0.25</td></tr>
<tr><td>W 位点上位掩盖</td><td>雪绒白 0.246</td><td>0.25</td></tr>
<tr><td>V 九尾显性上位</td><td>九尾 0.757 / 五尾 0.243</td><td>3 : 1</td></tr>
<tr><td>不完全显性（耳大小）</td><td>0.246 / 0.504 / 0.250</td><td>1 : 2 : 1</td></tr>
<tr><td>尾数累加分布</td><td>0.063 0.252 0.376 0.243 0.065</td><td>1 : 4 : 6 : 4 : 1</td></tr>
<tr><td>复等位显性序列 As &gt; Ab</td><td>霜灰 0.745 / 墨黑 0.255</td><td>3 : 1</td></tr>
<tr><td>亲缘系数（全同胞 / 半同胞 / 表亲 / 无关）</td><td>0.5000 / 0.2500 / 0.1250 / 0.0000</td><td>标准值</td></tr>
<tr><td>近交系数 F（全同胞后代）</td><td>0.2500</td><td>0.25</td></tr>
<tr><td>外观相同 ≠ 基因型相同</td><td>两只均渲染为「赤橙」</td><td>§2.5</td></tr>
</tbody></table>
<div class="note warn">写这套自检的过程中，模拟器自己被抓出两个 bug，都已修：<br>
① 亲缘递归时展开的是<b>年长</b>一方而不是年轻一方，导致所有 r 恒为 0 —— 近交机制等于没接上；<br>
② 数量性状位点被算成"是否携带显性"的二分，<b>尾数最多 3 尾、毛长最多 2 档</b>，与设计稿的 1–5 尾不符。<br>
这两类 bug 在真实开发里都极难靠肉眼发现，但它们会让整个自然选择机制静默失效。这也是这次离线模拟最主要的价值。</div>

<h2><span class="no">03</span>五轮运行结果</h2>
<h3>3.1 原规则 v0.3（每轮 5 生态年）</h3>
<table>
<thead><tr><th style="width:76px">轮次</th><th>窝数</th><th>出生</th><th>死亡<br><small>夭折/衰老/疾病</small></th><th>迁徙</th><th>引入</th>
<th>峰值<br><small>上限20</small></th><th>杂合度<br><small>起→终</small></th><th>末期<br>平均 F</th>
<th>撞上限</th><th>ρ=1<br>占比</th><th>存活<br>创始系</th><th>外观<br>指纹</th><th>新突变<br><small>(存活)</small></th></tr></thead>
<tbody>{rows_b}</tbody></table>

<div class="grid2">
<div><div class="fig">{fpb}</div><div class="cap">种群数量：5 轮全部在第 6 天前后挤满，之后长期贴着上限运行</div></div>
<div><div class="fig">{fpt}</div><div class="cap">对照：采用改进方案后的种群曲线（后面 §06 详述）</div></div>
</div>

<div class="fig">{frho}</div>
<div class="cap">拥挤度 ρ 与繁殖欲望 L(ρ)：原规则把 96% 的时间花在 ρ=1 / L=0 的状态上</div>

<h3>3.2 三个"看不见但更要命"的结果</h3>
<div class="grid3">
  <div class="card stat"><div class="v">{bgen:.1f}</div><div class="l">平均最大世代数</div><div class="d">5 个生态年只推进了 7 代左右</div></div>
  <div class="card stat"><div class="v">{blines:.1f} / 10</div><div class="l">5 年后仍有后代的创始血统</div><div class="d">家谱功能会看到一半祖先中断</div></div>
  <div class="card stat"><div class="v">{bmuts:.1f}</div><div class="l">5 年累计突变事件</div><div class="d">5 轮里有 4 轮一次都没发生</div></div>
</div>
<div class="grid3" style="margin-top:12px">
  <div class="card stat"><div class="v">{bcourt:.0f}</div><div class="l">5 年求偶判定次数</div><div class="d">其中 {baband:.0f} 次因近交被放弃</div></div>
  <div class="card stat"><div class="v">{bdead:.0f}</div><div class="l">平均死亡数</div><div class="d">夭折 {bcjuv:.1f} / 衰老 {bcold:.1f} / 疾病 {bcdis:.1f}</div></div>
  <div class="card stat"><div class="v">{bmig:.0f}</div><div class="l">平均迁徙数</div><div class="d">已排到第二大输出口</div></div>
</div>

<div class="fig">{fdiv}</div>
<div class="cap">遗传多样性：观察杂合度（24 位点平均）与平均近交系数 F</div>

<div class="fig">{fcb}</div>
<div class="cap">末代毛色构成（原规则）：多轮跑完全被单一毛色吞掉</div>

<h2><span class="no">04</span>暴露出的问题</h2>

<div class="q"><div class="qh">问题 1（致命）：上限不是"上限"，而是"开关"——而且是會被冲破的开关</div><div class="qb">
<b>证据：</b>5 轮峰值种群分别为 {peaks}，全部超过设定上限 20，最坏一轮达到 <b>{bpeak} 只（超出 {bover:.0f}%）</b>。<br>
<b>成因：</b>L(ρ) 只作用在"是否受孕"的概率上，而妊娠一旦成立，分娩时<b>没人再检查剩余名额</b>。Q13A 让胎儿计入 N_eff 是为了提前预警，
但 ρ 到了 0.9 时 L 仍有 27%，多只雌性同时妊娠仍会把上限冲破。<br>
<b>风险：</b>你的需求第七条第 1 款写死"同时存在的狐狸数量不得超过用户设置的上限"。这是唯一一条会被用户直接感知为"程序有 bug"的规则。<br>
<b>修复：</b>受孕时校验 <code>N_eff + 本窝仔数 ≤ N_max</code>，超出则削减仔数或放弃本次受孕。这是 §06 的 B1。
</div></div>

<div class="q"><div class="qh">问题 2（致命）：繁殖在 95% 的时间里是被完全关闭的</div><div class="qb">
<b>证据：</b>{bcap:.0f}% 的时间 ρ ≥ 0.999、L = 0；5 年平均只有 {blit:.0f} 窝 / {tb_b:.0f} 只出生。<br>
<b>成因：</b>把"环境容纳量"实现成了<b>存量闸门</b>而不是<b>流量闸门</b>。在"食物充足 + 不会饿死 + 无天敌 + 寿命长达 2.5 个生态年"的条件下，
死亡输出速率极低，于是"补一个空位"几乎就是全部的繁殖活动——<b>繁殖被死亡速率反向锁死</b>，而死亡速率又是这套规则里最慢的变量。<br>
<b>后果：</b>用户花两个小时挂机看到的画面是：一群狐狸静止不动，偶尔某只老死，才补生一只。<b>产品核心卖点（繁殖 / 遗传 / 突变）全都处于停摆状态。</b>
</div></div>

<div class="q"><div class="qh">问题 3（严重）：20 只的种群撑不起"看得见的多样性"</div><div class="qb">
<b>证据：</b>5 轮末代表色种类平均只剩 <b>{bcolors:.1f} 种</b>，其中占比最高的毛色平均吃掉 {bdom:.0f}% 的个体；
按"毛色 × 花纹 × 耳型 × 尾数 × 特殊性状"统计的外观指纹，末代只有 <b>{bfp:.1f} 种</b>（最差一轮 20 只狐狸只有 4 种组合）。<br>
<b>成因：</b>这是<b>群体遗传学的硬约束</b>，不是规则 bug。有效种群 Ne ≈ 20 时，每代杂合度损失约 1/(2Ne) = 2.5%，
5 年 7 代下来必然损失 {bhetloss:.0f}%；再加上一次偶然的优势繁殖个体，几条血统会迅速吞掉整个种群。<br>
<b>真实案例：</b>第 1 轮跑完，10 条创始血统只剩 4 条，末代 20 只狐狸<b>无一例外全部来自这 4 条幸存血统</b>；
更极端的是<b>第 2 轮：末代 20 只全部是「赤橙 + 同一种外观」，只有 4 种毛色×花纹组合</b>——
桌面上摆着 20 只看起来一模一样的狐狸。这正是"20 只撑不起多样性"的直接后果。<br>
<b>含义：</b>"不同基因型 → 不同外观"这条需求，只有在 Ne 足够大或有持续基因流入时才成立。
</div></div>

<div class="q"><div class="qh">问题 4（严重）：近交回避触发了，但挡不住——因为根本没得选</div><div class="qb">
<b>证据：</b>5 轮里求偶判定总共只发生约 {bcourt:.0f} 次，其中约 {baband:.0f} 次因亲缘系数 r ≥ 0.125 被放弃（放弃率约 {babandr:.0f}%）。
Q6B 的这条规则<b>确实执行了</b>，但末期平均近交系数仍然达到 <b>F = {bF:.3f}</b>（约等于全同胞后代的水平）。<br>
<b>成因：</b>回避机制生效的前提是<b>种群里存在足够多的「不沾亲」的配偶</b>。当 Ne ≈ 20 且所有个体都是同一小撮祖先的后代时，
候选配偶几乎人人带亲，<b>放弃一次只是把交配推迟到下一次同样近亲的对象上</b>，近交累积不可避免。<br>
<b>对照：</b>改进方案下求偶判定升到约 {tcourt:.0f} 次 / 放弃 {taband:.0f} 次，而 F 反而降到 {tF:.3f}——
说明真正起作用的是<b>可选配偶变多</b>与<b>外部基因流入</b>，而不是回避规则本身。<br>
<b>含义：</b>近交的正解是基因流入，不是回避。回避只负责"别让最坏的情况当场发生"。
</div></div>

<div class="q"><div class="qh">问题 5（严重）：突变系统供不上货</div><div class="qb">
<b>证据：</b>5 轮里 4 轮的突变事件为 <b>0 次</b>，唯一发生突变的那次也没有活到末代。全部 5 轮合计 <b>{bmuts:.0f} 次</b>突变、<b>{bmutalive:.0f} 次</b>存活。<br>
<b>成因：</b>突变是按"每窝 1.5%"判定的。当全年只有十来窝时，期望值就是 0.2 次。稀有性状（紫毛、九尾、发光、星纹）在设计中被规定为"只能由突变产生"，
结果就是<b>用户几乎永远看不到任何一个稀有个体</b>。<br>
<b>含义：</b>这张最容易带来惊喜的功能，被前面的繁殖停滞连坐了。
</div></div>

<div class="q"><div class="qh">问题 6（中等）：本轮条件下，自然选择几乎没有运行</div><div class="qb">
<b>证据：</b>把每个个体的适应度与它实际留下的后代数做相关性检验，5 轮平均相关系数 <b>r = {bsel:.3f}</b>（围绕 0 波动，纯噪声）；
种群内适应度的全距只有 <b>{bfit:.1%}</b>。<br>
<b>成因是设计正确的：</b>你要求"环境适宜、食物充足、不会饿死"，这正是<b>没有选择压力</b>的定义。
§8.0 那张适应度表里每一项都需要有一个偏离适宜点的环境才能显出差值——本轮刻意把它们全部关掉了。<br>
<b>结论：</b>这不是 bug，但它说明一件事：<b>"自然选择"这个卖点只有在用户让环境变差、或开启资源竞争时才会启动。</b>
如果产品宣传语里把"自然选择"放在核心位置，就必须给玩家一个能方便地<b>制造环境压力</b>的入口（季节强度滑块、投喂开关、壁纸明暗），
否则大部分用户全程都跑在"无效选择"的状态里。<br>
<b>另外一个反常项：</b>5 轮中有 2 轮的相关系数为负，意味着<b>适应度高的个体反而留下更少后代</b>——在小种群里，随机性完全压过选择，这是正常的，
但和"适者生存"的直觉相反，值得在 UI 里用"当前选择强度：弱 / 中 / 强"这样的指示器明示。
</div></div>

<div class="q"><div class="qh">问题 7（中等）：迁徙成了仅次于死亡的输出口，且触发原因很怪</div><div class="qb">
<b>证据：</b>5 轮平均 {bmig:.0f} 只迁徙，同期平均死亡 {bdead:.0f} 只。迁徙本应是"温和的、偶发的退出"，实际排到了第二大出口。<br>
<b>成因：</b>§16.2 把"适应度显著低于种群均值"列为触发条件之一，但<b>没有定义"显著"的阈值</b>。
我在模拟器里先用绝对阈值实现时，几乎所有个体都"低于阈值"，导致这个条件退化成一个常量倍率；改成相对种群均值后才正常。<br>
<b>含义：</b>这条规则进入编码之前，必须在文档里写清楚是"低于均值 X 个点"还是"低于均值 X 个标准差"，否则实现者会各自发挥。
</div></div>

<div class="q"><div class="qh">问题 8（中等）：休眠机制在本轮完全没被验证到</div><div class="qb">
<b>证据：</b>5 轮休眠事件 <b>{btorpor}</b> 次。<br>
<b>含义：</b>这是"食物充足"这一前置条件的必然结果（饱食度始终维持高位）。
它验证了<b>不变量：投入充足食物时不会误触发休眠、也不会出现饿死</b>——这条是好的。
但同时也说明：§15 取食系统与 §15.4 的三级状态，<b>必须单独跑一组"食物短缺"场景才能验证</b>，本轮覆盖不到。建议下一轮补做。
</div></div>

<div class="q"><div class="qh">问题 9：时间与世代的换算关系，设计稿里缺一笔账</div><div class="qb">
按 §14.2 的默认时钟：1 生态年 = 24 游戏天 = <b>576 游戏小时 = 9.6 真实小时（1×）</b>。<br>
本轮实测：原规则下 5 个生态年只推进 <b>{bgen:.1f} 代</b>，平均 <b>0.69 个生态年才推进 1 代</b>。<br>
而 §12 种群统计那张图的目标是"观察一个基因如何在<b>几十代之后</b>成为优势基因"。按当前节奏换算：<br>
<div class="ev">原规则：达到 40 代 ≈ {y40b:.0f} 个生态年 ≈ {h40b:.0f} 真实小时（1×） / {h40b10:.0f} 小时（10×）
改进后：达到 40 代 ≈ {y40t:.0f} 个生态年 ≈ {h40t:.0f} 真实小时（1×） / {h40t10:.0f} 小时（10×）</div>
也就是说，<b>要让"几十代后基因频率变化"这件事真的能发生，用户需要连续挂机好几天</b>。<br>
建议：① 在统计面板上直接显示"当前第 N 代 / 预计还需 X 小时到达第 40 代"；
② 提供更高档流速或"离线补算"开关；③ 把 §12 那张图的横轴标注从"代"改成"生态年（≈N 代）"，不要给用户错误预期。
</div></div>

<h2><span class="no">05</span>为什么会发生：一条因果链</h2>
<div class="note"><b>根因只有一个，其余都是它的下游。</b><br><br>
<b>N_max 被实现成了"存量上限 + 生育开关"，而不是"流量上限"。</b><br><br>
一旦种群打满：<br>
① L(ρ) → 0 ⇒ 繁殖停止；<br>
② 而死亡输出只有"衰老 / 疾病 / 幼崽夭折"三条，其中疾病与衰老都很慢 ⇒ 空位释放极慢；<br>
③ 繁殖流量 = 空位流量 ⇒ <b>整个世代更替速率被死亡速率反向锁死</b>；<br>
④ 世代推进慢 + 繁殖事件少 ⇒ 突变机会趋近于 0、家谱没有分叉、近交回避规则成为死代码；<br>
⑤ 长期小 Ne + 世代累积 ⇒ 遗传漂变主导 ⇒ 表型趋同、创始血统成片断绝。<br><br>
<b>所以只调任意一个参数都没用</b>：把上限从 20 提到 40，只会把"第 6 天撞墙"推迟到"第 13 天撞墙"。
要真正解开，必须<b>同时</b>放开流量（更替率）并补上多样性来源（基因流入 + 创始库 + 突变率）。
</div>

<h2><span class="no">06</span>改进方案与对照验证</h2>
<p>下面每一条都是<b>先写进模拟器、再跑一轮对照</b>得出的，不是纸面推演。对照组为同一批种子、同样 5 生态年、同样"食物充足 + 环境适宜"。</p>

<table>
<thead><tr><th style="width:52px">编号</th><th style="width:170px">改动</th><th>内容</th><th style="width:80px">涉及决策</th></tr></thead>
<tbody>
<tr><td><b>B1</b></td><td>受孕时校验剩余名额</td><td><code>N_eff + 本窝仔数 ≤ N_max</code>，超出则削减仔数 / 放弃本次受孕。<b>把"不超过上限"从概率约束升级为硬约束</b></td><td>不改任何已有决策，只是补齐第七条第 1 款的实现</td></tr>
<tr><td><b>B2</b></td><td>默认上限 20 → 40</td><td>提高 Ne，降低漂变速率。用户仍可在 5/10/20/50/自定义之间自由选择</td><td>需你点头（渲染开销）</td></tr>
<tr><td><b>B3</b></td><td>创始基因库最大化</td><td>10 只创始个体在<b>保持各等位基因边际频率不变</b>的前提下，让每只尽量杂合，使 10 只尽可能覆盖全部常见等位</td><td>纯实现细节，不影响规则</td></tr>
<tr><td><b>B4</b></td><td>缩短寿命到 40 游戏天</td><td>60 → 40 天（约 1.7 个生态年），并同步上调幼崽夭折到 30–40%，让"空位-补位"的周转真正跑起来</td><td>需你点头（文档原本未定寿命）</td></tr>
<tr><td><b>B5</b></td><td>野外引入（gene flow）</td><td>每推进 3 个世代引入 1 只与种群无亲缘的个体。<b>这是破解近交的唯一有效手段</b></td><td>Q18–Q25 默认包里本身就包含"提供野外引入"</td></tr>
<tr><td><b>B6</b></td><td>突变率 1.5% → 3%</td><td>仍在 Q5A 授权的 0–10% 区间内；仅在 UI 提示中标注"默认 3%"</td><td>需你点头（数字变动）</td></tr>
</tbody></table>

<h3>6.1 改进前 vs 改进后（各 5 轮平均）</h3>
<table>
<thead><tr><th style="width:190px">指标</th><th>原规则 v0.3</th><th>改进方案 v0.4</th><th>变化</th></tr></thead>
<tbody>
<tr><td>5 年窝数</td><td>{blit:.0f}</td><td><b>{tlit:.0f}</b></td><td>{d_lit}</td></tr>
<tr><td>出生总数</td><td>{tb_b:.0f}</td><td><b>{tb_t:.0f}</b></td><td>{d_birth}</td></tr>
<tr><td>最大世代数</td><td>{bgen:.1f}</td><td><b>{tgen:.1f}</b></td><td>{d_gen}</td></tr>
<tr><td>存活创始血统</td><td>{blines:.1f} / 10</td><td><b>{tlines:.1f} / 10</b></td><td>{d_lines}</td></tr>
<tr><td>末期平均近交 F</td><td>{bF:.3f}</td><td><b>{tF:.3f}</b></td><td>{d_F}</td></tr>
<tr><td>峰值种群 / 上限</td><td style="color:var(--bad)"><b>{bpeak} / {bnmax}</b></td><td><b>{tpeak} / {tnmax}</b></td><td>{d_peak}</td></tr>
<tr><td>ρ=1 时间占比</td><td>{bcap:.0%}</td><td><b>{tcap:.0%}</b></td><td>{d_cap}</td></tr>
<tr><td>末代毛色种类</td><td>{bcolors:.1f}</td><td><b>{tcolors:.1f}</b></td><td>{d_colors}</td></tr>
<tr><td>末代外观指纹数</td><td>{bfp:.1f}</td><td><b>{tfp:.1f}</b></td><td>{d_fp}</td></tr>
<tr><td>新突变（存活到末代）</td><td>{bmuts:.1f}（{bmutalive:.1f}）</td><td><b>{tmuts:.1f}（{tmutalive:.1f}）</b></td><td>{d_mut}</td></tr>
</tbody></table>

<div class="fig">{fcmp}</div>
<div class="cap">关键产出指标：改进后所有"有没有事情发生"的指标都成倍提升</div>

<div class="fig">{frisk}</div>
<div class="cap">风险指标：峰值不再冲破上限、ρ=1 时间大幅缩短、近交系数下降约 60%</div>

<div class="fig">{fct}</div>
<div class="cap">末代毛色构成（改进方案）：5 轮都保住了多种毛色共存</div>

<div class="note ok"><b>最有说服力的一组数字：</b>峰值种群从 <b>{bpeak}（超上限 {bover:.0f}%）</b> 降到 <b>{tpeak}（恰等于上限）</b>，
处于完全停产状态的时间从 <b>{bcap:.0f}%</b> 降到 <b>{tcap:.0f}%</b>，
而繁殖产出从 {blit:.0f} 窝 / {tb_b:.0f} 只提升到 {tlit:.0f} 窝 / {tb_t:.0f} 只。<br>
<b>数量上限没有被放松一分钟</b>，产出的提升全部来自"周转率"而不是"放宽约束"。</div>

<h3>6.2 仍然没有解决的问题</h3>
<div class="note warn">
<b>① 世代推进仍然偏慢。</b>改进后 5 生态年推进 {tgen:.1f} 代（原 {bgen:.1f} 代）。要到 §12 设想的"几十代"，仍需约 {y40t:.0f} 个生态年。
这不是参数问题，而是<b>时钟换算</b>问题（见问题 9）。<br><br>
<b>② 自然选择仍然很弱。</b>改进后的适应度-繁殖成功率相关系数约 {tsel:.3f}，比原规则的 {bsel:.3f} 好一些但依然偏弱。
这是本轮实验条件（环境适宜、食物充足）决定的，<b>不能靠调参修复</b>，只能靠提供"制造环境压力"的用户入口。<br><br>
<b>③ 视觉多样性会随时间缓慢下降。</b>即使改进后，杂合度 5 年仍下降 {thetloss:.0f}%。
建议做一个长期对策：<b>当某个位点的等位基因数降到 1 时，触发一次"野外引入优先携带该位点稀有等位"</b>，让频临灭绝的性状有机会回来。
这条我没有在模拟器里实现，属于下一轮工作。<br><br>
<b>④ 40 只狐狸的渲染开销没有被本次模拟覆盖。</b>这里只验证了逻辑层。窗口数量、帧率、CPU 占用必须在真实渲染下实测。
如果顶不住，建议回落至 B 方案（上限 30），指标仍显著优于现行规则：5 年约 128 窝 / 6.6 条创始系 / F≈0.15。
</div>

<h2><span class="no">07</span>需要你拍板的 5 项</h2>
<table>
<thead><tr><th style="width:52px">编号</th><th style="width:230px">问题</th><th>我的建议</th></tr></thead>
<tbody>
<tr><td><b>E1</b></td><td>默认数量上限是否从 20 提到 40？</td><td><b>是</b>（配套 §7 的 LOD 分级）。若不改，建议至少提到 30，并明确告诉用户"20 只不足以维持多样性"</td></tr>
<tr><td><b>E2</b></td><td>寿命能否定为 40 游戏天（约 1.7 生态年）？</td><td><b>是</b>。当前文档根本没有这个数值，留空会导致实现时各写各的</td></tr>
<tr><td><b>E3</b></td><td>野生个体引入是否默认开启？</td><td><b>默认开启</b>（每 3 代 1 只），并在设置里可关闭 + 可调频率。它已经是 Q18–Q25 默认包的一部分</td></tr>
<tr><td><b>E4</b></td><td>突变率默认从 1.5% 调到 3%？</td><td><b>是</b>。1.5% 在真实繁殖量下等于"几乎永不发生"</td></tr>
<tr><td><b>E5</b></td><td>统计面板要不要显式提示"当前选择强度"？</td><td><b>要</b>。否则用户会在完全无选择的条件下，误以为"自然选择没做出来"</td></tr>
</tbody></table>
<div class="note">另外还有一项建议（不计入上表）：为 §15 单独补跑一组<b>食物短缺场景</b>，验证饱食三级状态与休眠，本轮实验条件覆盖不到。</div>

<h2><span class="no">08</span>怎么复现</h2>
<div class="ev">cd "E:/workdubby_space/desktop pet"
python sim/verify_genetics.py                                    # 遗传引擎自检（16 项）
python sim/fox_ecosystem_sim.py --rounds 5 --years 5 --variant base     # 本报告 §03 的数据
python sim/fox_ecosystem_sim.py --rounds 5 --years 5 --variant tuned    # 本报告 §06 的对照
python sim/calibrate.py                                          # 第一轮参数搜索
python sim/calibrate2.py                                         # 第二轮定向搜索
python sim/gen_report.py                                         # 重新生成本报告</div>
<p>改了任何规则或参数后，<b>先跑 verify_genetics.py</b> 确认遗传引擎没有跑偏，再跑模拟器对比——
本次就是这样抓出两个静默 bug 的。</p>

</main>
<footer>
幻想小狐狸 Fantasy Fox · 桌面生态桌宠 — 5 轮离线模拟运行报告<br>
模拟范围：仅逻辑层（时钟 / 繁殖 / 遗传 / 突变 / 死亡 / 迁徙 / 密度），不含渲染、窗口管理与文件取食。<br>
所有结论均由上述脚本在指定随机种子下产生，可直接重跑复现。
</footer>
</div></body></html>"""

    def delta(a, b, unit='', good_up=True, pct=False):
        """a=原规则 b=改进方案"""
        if pct:
            d = (b / a - 1) * 100 if a else 0
            return '<span style="color:%s">%+.0f%%</span>' % (C_TUNE if d > 0 else C_MUTE, d)
        d = b - a
        rel = (b / a - 1) * 100 if a else 0
        col = C_TUNE if (d > 0) == good_up else C_BASE
        return '<span style="color:%s">%+.1f (%+.0f%%)</span>' % (col, d, rel)

    y40b = 40 / mean_b['gens'] * 5
    y40t = 40 / mean_t['gens'] * 5
    h40b = y40b * 9.6
    h40t = y40t * 9.6

    dom_b = 0
    for r in rb:
        if r['end_colors']:
            dom_b += max(r['end_colors'].values()) / sum(r['end_colors'].values())
    dom_b = dom_b / len(rb) * 100

    html = HTML.format(
        ink=C_INK, line=C_LINE,
        rows_b=rowsillin(rb, PB),
        rows_t=rowsillin(rt, PT),
        fpb=fig_pop_b, fpt=fig_pop_t, frho=fig_rho, fdiv=fig_div,
        fcmp=fig_cmp, frisk=fig_risk, fcb=fig_color_b, fct=fig_color_t,
        # 汇总
        bcap=mean_b['capratio'], bcapday=mean_b['capday'], bpeak=mean_b['peak'],
        bnmax=PB['N_max'], bover=(mean_b['peak'] / PB['N_max'] - 1) * 100,
        blit=mean_b['litters'], tb_b=mean_b['births'], bgen=mean_b['gens'],
        blines=mean_b['lines'], bmuts=mean_b['muts'], bmutalive=mean_b['muts_alive'],
        bcolors=mean_b['colors'], bfp=mean_b['fp'], bF=mean_b['F'],
        bdom=dom_b, bhetloss=(1 - mean_b['het1'] / mean_b['het0']) * 100,
        bsel=mean_b['selr'], bfit=mean_b['fitspread'], bmig=mean_b['migrated'],
        btorpor=sum(r['torpor_events'] for r in rb),
        bcourt=agg(rb, 'court_attempts'), baband=agg(rb, 'court_abandoned'),
        babandr=agg(rb, 'court_abandoned') / max(1e-9, agg(rb, 'court_attempts')) * 100,
        tcourt=agg(rt, 'court_attempts'), taband=agg(rt, 'court_abandoned'),
        bdead=agg(rb, 'total_deaths'),
        bcjuv=causes_b['幼崽夭折'], bcold=causes_b['衰老'], bcdis=causes_b['疾病'],
        peaks='、'.join(str(r['max_pop_seen']) for r in rb),
        # tuned
        tcap=mean_t['capratio'], tcapday=mean_t['capday'], tpeak=mean_t['peak'],
        tnmax=PT['N_max'], tlit=mean_t['litters'], tb_t=mean_t['births'],
        tgen=mean_t['gens'], tlines=mean_t['lines'], tmuts=mean_t['muts'],
        tmutalive=mean_t['muts_alive'], tcolors=mean_t['colors'], tfp=mean_t['fp'],
        tF=mean_t['F'], tsel=mean_t['selr'],
        thetloss=(1 - mean_t['het1'] / mean_t['het0']) * 100,
        # deltas
        d_lit=delta(mean_b['litters'], mean_t['litters'], pct=True),
        d_birth=delta(mean_b['births'], mean_t['births'], pct=True),
        d_gen=delta(mean_b['gens'], mean_t['gens'], pct=True),
        d_lines=delta(mean_b['lines'], mean_t['lines'], pct=True),
        d_F=delta(mean_b['F'], mean_t['F'], good_up=False, pct=True),
        d_cap=delta(mean_b['capratio'], mean_t['capratio'], good_up=False, pct=True),
        d_colors=delta(mean_b['colors'], mean_t['colors'], pct=True),
        d_fp=delta(mean_b['fp'], mean_t['fp'], pct=True),
        d_peak='<span style="color:%s">超上限 %.0f%% → 恰好等于上限</span>' % (C_TUNE, (mean_b['peak'] / PB['N_max'] - 1) * 100),
        d_mut='<span style="color:%s">0 → 每轮平均 %.1f 个新突变存活下来</span>' % (C_TUNE, mean_t['muts_alive']),
        # 时间
        y40b=y40b, y40t=y40t, h40b=h40b, h40t=h40t, h40b10=h40b / 10, h40t10=h40t / 10,
    )
    out = os.path.join(DOCS, 'sim-run-report-v0.3.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print('已生成', out, '大小 %.1f KB' % (len(html.encode('utf-8')) / 1024))


if __name__ == '__main__':
    main()
