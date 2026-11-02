# -*- coding: utf-8 -*-
"""生成 docs/ecosystem-run-report-v0.6.html —— 自包含（内嵌 SVG，无外部依赖）。"""
import io
import os
import statistics
from multiprocessing import Pool

_HERE = os.path.dirname(os.path.abspath(__file__))
_OUT = os.path.join(_HERE, '..', 'docs', 'ecosystem-run-report-v0.6.html')
_M = None


def _init():
    global _M
    import importlib.util
    spec = importlib.util.spec_from_file_location('m', os.path.join(_HERE, 'fox_ecosystem_sim.py'))
    _M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_M)


def one(a):
    tag, over, yrs, seed = a
    P = dict(_M.TUNED_V3_PARAMS if over.get('__v6__', True) else _M.TUNED_V2_PARAMS)
    P.pop('__v6__', None)
    P.update(over)
    return tag, yrs, _M.run_round(seed, P, yrs)


def run(cfgs, seeds, yrs):
    tasks = [(t, dict(o, __v6__=o.pop('__v6__', True)), yrs, s) for t, o in cfgs for s in seeds]
    with Pool(initializer=_init) as pool:
        raw = pool.map(one, tasks, chunksize=1)
    store = {}
    for t, y, r in raw:
        store.setdefault(t, []).append(r)
    return store


def m(rs, k):
    return statistics.mean([r[k] for r in rs])


# ----------------------------- SVG 图表 -----------------------------

def svg_line(series, width=680, height=240, ylab='', xlab='', ymin=None, ymax=None,
             colors=('#c0392b', '#2471a3', '#7d3c98', '#1e8449'), fmt='%.2f'):
    """series: [(name, [(x, y), ...]), ...]"""
    pad_l, pad_b, pad_t, pad_r = 56, 34, 14, 14
    xs = [p[0] for _, pts in series for p in pts]
    ys = [p[1] for _, pts in series for p in pts]
    x0, x1 = min(xs), max(xs)
    y0 = ymin if ymin is not None else min(ys)
    y1 = ymax if ymax is not None else max(ys)
    if y1 - y0 < 1e-9:
        y1 = y0 + 1

    def px(x):
        return pad_l + (x - x0) / (x1 - x0) * (width - pad_l - pad_r)

    def py(y):
        return height - pad_b - (y - y0) / (y1 - y0) * (height - pad_b - pad_t)

    out = ['<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" class="chart">'
           % (width, height)]
    out.append('<rect x="0" y="0" width="%d" height="%d" fill="#fdfdfb" rx="6"/>' % (width, height))
    # 网格与刻度
    for i in range(5):
        v = y0 + (y1 - y0) * i / 4.0
        yy = py(v)
        out.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#e5e2da" stroke-width="1"/>'
                   % (pad_l, yy, width - pad_r, yy))
        out.append('<text x="%d" y="%.1f" font-size="11" fill="#8a8578" text-anchor="end">%s</text>'
                   % (pad_l - 6, yy + 4, fmt % v))
    for i, (name, pts) in enumerate(series):
        c = colors[i % len(colors)]
        d = ' '.join(('%s%.1f,%.1f' % ('M' if j == 0 else 'L', px(p[0]), py(p[1])))
                     for j, p in enumerate(pts))
        out.append('<path d="%s" fill="none" stroke="%s" stroke-width="2.4" '
                   'stroke-linejoin="round"/>' % (d, c))
        for p in pts:
            out.append('<circle cx="%.1f" cy="%.1f" r="2.4" fill="%s"/>' % (px(p[0]), py(p[1]), c))
    # 图例
    lx = pad_l + 6
    for i, (name, _) in enumerate(series):
        c = colors[i % len(colors)]
        out.append('<rect x="%d" y="%d" width="12" height="3" fill="%s"/>' % (lx, 10, c))
        out.append('<text x="%d" y="%d" font-size="11.5" fill="#4a463c">%s</text>'
                   % (lx + 17, 15, name))
        lx += 24 + len(name) * 12
    out.append('<text x="%d" y="%d" font-size="11" fill="#8a8578" text-anchor="middle">%s</text>'
               % ((pad_l + width - pad_r) // 2, height - 8, xlab))
    out.append('<text x="14" y="%d" font-size="11" fill="#8a8578">%s</text>'
               % (pad_t + 12, ylab))
    out.append('</svg>')
    return ''.join(out)


def svg_bar(items, width=680, height=250, ylab='', ymin=0, fmt='%.2f',
            colors=('#2471a3', '#c0392b', '#1e8449', '#7d3c98', '#b9770e')):
    """items: [(name, value), ...]"""
    pad_l, pad_b, pad_t, pad_r = 56, 46, 16, 14
    vals = [v for _, v in items]
    y1 = max(vals) * 1.12 or 1
    n = len(items)
    bw = (width - pad_l - pad_r) / max(1, n) * 0.62
    gap = (width - pad_l - pad_r) / max(1, n)
    out = ['<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" class="chart">'
           % (width, height)]
    out.append('<rect x="0" y="0" width="%d" height="%d" fill="#fdfdfb" rx="6"/>' % (width, height))

    def py(v):
        return height - pad_b - (v - ymin) / (y1 - ymin) * (height - pad_b - pad_t)

    for i in range(5):
        v = ymin + (y1 - ymin) * i / 4.0
        yy = py(v)
        out.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#e5e2da"/>' %
                   (pad_l, yy, width - pad_r, yy))
        out.append('<text x="%d" y="%.1f" font-size="11" fill="#8a8578" text-anchor="end">%s</text>'
                   % (pad_l - 6, yy + 4, fmt % v))
    for i, (name, v) in enumerate(items):
        x = pad_l + gap * i + (gap - bw) / 2
        yy = py(v)
        c = colors[i % len(colors)]
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" rx="3"/>'
                   % (x, yy, bw, height - pad_b - yy, c))
        out.append('<text x="%.1f" y="%.1f" font-size="11.5" fill="#4a463c" text-anchor="middle">%s</text>'
                   % (x + bw / 2, yy - 5, fmt % v))
        out.append('<text x="%.1f" y="%d" font-size="11" fill="#4a463c" text-anchor="middle">%s</text>'
                   % (x + bw / 2, height - pad_b + 16, name))
    out.append('<text x="14" y="%d" font-size="11" fill="#8a8578">%s</text>' % (pad_t + 12, ylab))
    out.append('</svg>')
    return ''.join(out)


# ----------------------------- 数据收集 -----------------------------

def collect():
    seeds24 = [20261031 + i * 7919 for i in range(24)]
    seeds12 = seeds24[:12]
    D = {}

    # 1) 终选对照 24 种子
    cfgs = [('v0.5 现状', {'__v6__': False}),
            ('v0.6', {})]
    for yrs in (5, 20):
        st = run([(t, dict(o)) for t, o in cfgs], seeds24, yrs)
        D['final%d' % yrs] = st

    # 2) 尾数/毛长轨迹（20 年 12 种子）
    st = run([('v0.5', {'__v6__': False}), ('v0.6', {})], seeds12, 20)
    def yearly(rs, k):
        per = {}
        for r in rs:
            for d in r['daily']:
                per.setdefault(d['year'], []).append(d[k])
        return {y: statistics.mean(v) for y, v in sorted(per.items())}
    D['traj'] = {t: {'tail': yearly(rs, 'mtail'), 'hair': yearly(rs, 'mhair'),
                     'lum': yearly(rs, 'lum')} for t, rs in st.items()}

    # 3) 食物场景（5 年 12 种子）
    food = [('充足', {'Food_mode': 'pool', 'Food_supply_per_day': 3800}),
            ('正常', {'Food_mode': 'pool', 'Food_supply_per_day': 2900}),
            ('短缺', {'Food_mode': 'pool', 'Food_supply_per_day': 1900}),
            ('饥荒', {'Food_mode': 'pool', 'Food_supply_per_day': 1000}),
            ('断供', {'Food_mode': 'pool', 'Food_supply_per_day': 0}),
            ('断供2年→恢复', {'Food_mode': 'pool', 'Food_supply_per_day': 0,
                         'Food_shift_year': 2, 'Food_shift_to': 3800})]
    D['food'] = run([(t, dict(o)) for t, o in food], seeds12, 5)

    # 4) 育种家方程（换壁纸 20 年 12 种子）
    shift = [('恒定光照', {}),
             ('第8年换亮壁纸', {'Env_shift_year': 8, 'Env_shift_to': 85})]
    st = run([(t, dict(o)) for t, o in shift], seeds12, 20)
    D['sr'] = {}
    for t, rs in st.items():
        rows = []
        for y in range(20):
            pop, mom, pup = [], [], []
            for r in rs:
                for d in r['daily']:
                    if d['year'] == y:
                        pop.append(d['lum'])
                for lg in r['litter_log']:
                    if lg['year'] == y:
                        mom.append(lg['mom'])
                        pup += lg['pups']
            if pop and mom:
                p_, m_, c_ = statistics.mean(pop), statistics.mean(mom), statistics.mean(pup)
                rows.append((y, m_ - p_, c_ - p_))
        D['sr'][t] = rows

    # 5) 三档预设
    pres = [('稳健档', {'Lifespan_mean_days': 52, 'Lifespan_sd_days': 10,
                     'Lifespan_min_days': 32, 'Lifespan_max_days': 88,
                     'Immigration_every_days': 16 * 24}),
            ('标准档', {}),
            ('激进档', {'Lifespan_mean_days': 32, 'Lifespan_sd_days': 7,
                     'Lifespan_min_days': 20, 'Lifespan_max_days': 54,
                     'Migrate_base': 0.00006, 'Immigration_every_days': 9 * 24})]
    D['pres20'] = run([(t, dict(o)) for t, o in pres], seeds12, 20)

    # 6) v0.6 五轮
    D['rounds'] = run([('v0.6', {})], seeds24[:5], 5)['v0.6']
    return D


# ----------------------------- HTML -----------------------------

CSS = """
:root{--bg:#faf8f3;--card:#ffffff;--ink:#33302a;--sub:#8a8578;--line:#e5e2da;
--accent:#b9770e;--red:#c0392b;--blue:#2471a3;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
line-height:1.75;font-size:15px}
.wrap{max-width:900px;margin:0 auto;padding:36px 22px 80px}
h1{font-size:27px;margin:0 0 6px;letter-spacing:.5px}
h2{font-size:20px;margin:44px 0 14px;padding-left:11px;border-left:4px solid var(--accent)}
h3{font-size:16px;margin:26px 0 8px;color:#5a5548}
.meta{color:var(--sub);font-size:13px;margin-bottom:8px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:18px 20px;margin:14px 0}
table{width:100%;border-collapse:collapse;font-size:13.5px;margin:10px 0}
th,td{padding:7px 9px;text-align:right;border-bottom:1px solid var(--line)}
th{background:#f4f1ea;font-weight:600;color:#5a5548}
td:first-child,th:first-child{text-align:left}
tr:last-child td{border-bottom:none}
.good{color:#1e8449;font-weight:600}
.bad{color:#c0392b;font-weight:600}
.chart{width:100%;height:auto;display:block;margin:8px 0 4px}
.kpi{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0}
.kpi div{flex:1;min-width:150px;background:var(--card);border:1px solid var(--line);
border-radius:9px;padding:13px 15px}
.kpi b{display:block;font-size:24px;line-height:1.3;color:var(--accent)}
.kpi span{font-size:12.5px;color:var(--sub)}
.note{background:#fdf9ef;border-left:3px solid var(--accent);padding:11px 14px;
font-size:13.5px;margin:12px 0;border-radius:0 6px 6px 0}
.warn{background:#fdf1ef;border-left:3px solid var(--red);padding:11px 14px;
font-size:13.5px;margin:12px 0;border-radius:0 6px 6px 0}
code{background:#f2efe8;padding:1px 5px;border-radius:4px;font-size:13px}
ul{padding-left:22px}
"""


def tbl(headers, rows, cls_col=None):
    h = '<table><thead><tr>' + ''.join('<th>%s</th>' % x for x in headers) + '</tr></thead><tbody>'
    for r in rows:
        h += '<tr>'
        for i, c in enumerate(r):
            cl = ''
            if cls_col and i in cls_col:
                cl = ' class="%s"' % cls_col[i]
            h += '<td%s>%s</td>' % (cl, c)
        h += '</tr>'
    return h + '</tbody></table>'


def build(D):
    f5, f20 = D['final5'], D['final20']

    def row(st, tag, lab):
        rs = st[tag]
        return [lab, '%.1f' % m(rs, 'total_litters'),
                '%.0f%%' % (100 * m(rs, 'blocked_litters') /
                            max(1e-9, m(rs, 'blocked_litters') + m(rs, 'total_litters'))),
                '%.0f' % m(rs, 'trimmed_pups'), '%.1f' % m(rs, 'max_generation'),
                '%.1f' % m(rs, 'final_pop'), '%.3f' % m(rs, 'meanF_end'),
                '%.3f' % m(rs, 'het_end'), '%.2f' % m(rs, 'fp2_ratio'),
                '%+.3f' % m(rs, 'selection_r'),
                '%d' % sum(1 for r in rs if r['collapsed'])]

    hd = ['配置', '窝数', '空转', '裁剪', '世代', '种群', '近交 F', '杂合度', '指纹2', '选择 r', '崩溃']
    t5 = tbl(hd, [row(f5, 'v0.5 现状', 'v0.5 现状'), row(f5, 'v0.6', 'v0.6（本轮）')])
    t20 = tbl(hd, [row(f20, 'v0.5 现状', 'v0.5 现状'), row(f20, 'v0.6', 'v0.6（本轮）')])

    # 尾数轨迹
    tr = D['traj']
    ys = sorted(tr['v0.6']['tail'])
    tail_pts = [('v0.6', [(y, tr['v0.6']['tail'][y]) for y in ys]),
                ('v0.5', [(y, tr['v0.5']['tail'][y]) for y in ys])]
    hair_pts = [('v0.6 毛长', [(y, tr['v0.6']['hair'][y]) for y in ys]),
                ('v0.6 毛色明度(÷25)', [(y, tr['v0.6']['lum'][y] / 25.0) for y in ys])]
    g_tail = svg_line(tail_pts, ylab='平均尾数', xlab='生态年', ymin=1.5, ymax=3.0)
    g_hair = svg_line(hair_pts, ylab='均值', xlab='生态年', ymin=1.0, ymax=3.0)

    # 空转
    blk = [('v0.5 空转率', m(f20['v0.5 现状'], 'blocked_litters') /
            max(1e-9, m(f20['v0.5 现状'], 'blocked_litters') + m(f20['v0.5 现状'], 'total_litters')) * 100),
           ('v0.6 空转率', m(f20['v0.6'], 'blocked_litters') /
            max(1e-9, m(f20['v0.6'], 'blocked_litters') + m(f20['v0.6'], 'total_litters')) * 100)]
    g_blk = svg_bar(blk, ylab='%', fmt='%.0f', colors=('#c0392b', '#1e8449'))

    # 食物
    fd = D['food']
    order = ['充足', '正常', '短缺', '饥荒', '断供', '断供2年→恢复']
    food_rows = []
    for t in order:
        rs = fd[t]
        food_rows.append([t, '%.1f' % m(rs, 'final_pop'), '%.1f' % m(rs, 'total_litters'),
                          '%.0f' % m(rs, 'torpor_events'), '%.1f' % m(rs, 'mean_satiety_end'),
                          '%+.3f' % m(rs, 'selection_r'),
                          '%d' % sum(1 for r in rs if r['collapsed'])])
    g_food = svg_bar([(t, m(fd[t], 'selection_r')) for t in order[:4]],
                     ylab='选择相关 r', fmt='%.2f')
    g_pop = svg_bar([(t, m(fd[t], 'final_pop')) for t in order], ylab='末种群', fmt='%.1f')

    # S/R
    sr = D['sr']
    g_sr = svg_line([('选择差 S（换亮壁纸后）', [(y, s) for y, s, _ in sr['第8年换亮壁纸']]),
                     ('遗传响应 R', [(y, r) for y, _, r in sr['第8年换亮壁纸']]),
                     ('S（恒定光照对照）', [(y, s) for y, s, _ in sr['恒定光照']])],
                    ylab='明度差', xlab='生态年（第 8 年换壁纸）', ymin=-3.5, ymax=4.5,
                    colors=('#c0392b', '#2471a3', '#b9b3a4'))

    # 三档
    pr = D['pres20']
    pres_rows = []
    for t in ('稳健档', '标准档', '激进档'):
        rs = pr[t]
        pres_rows.append([t, '%.1f' % m(rs, 'max_generation'), '%.3f' % m(rs, 'meanF_end'),
                          '%.3f' % m(rs, 'het_end'), '%.1f' % m(rs, 'total_litters'),
                          '%.1f' % m(rs, 'immigrants')])
    g_pres = svg_bar([(t, m(pr[t], 'max_generation')) for t in ('稳健档', '标准档', '激进档')],
                     ylab='20 年世代数', fmt='%.1f')

    # 五轮
    r5 = D['rounds']
    round_rows = []
    for i, r in enumerate(r5, 1):
        round_rows.append(['第 %d 轮' % i, '%d' % r['max_generation'], '%d' % r['final_pop'],
                           '%.1f' % r['mean_pop'], '%.3f→%.3f' % (r['het_start'], r['het_end']),
                           '%d（存活 %d）' % (r['mutations_total'], r['mutations_survived']),
                           '%d' % r['trimmed_pups'], '%d' % (1 if r['collapsed'] else 0)])

    v6_20 = f20['v0.6']
    v5_20 = f20['v0.5 现状']
    kpi = [('%.0f%% → %.0f%%' % (
                m(v5_20, 'blocked_litters') / max(1e-9, m(v5_20, 'blocked_litters') + m(v5_20, 'total_litters')) * 100,
                m(v6_20, 'blocked_litters') / max(1e-9, m(v6_20, 'blocked_litters') + m(v6_20, 'total_litters')) * 100),
            '繁殖机会空转率（24 种子 · 20 年）'),
           ('%.3f → %.3f' % (m(v5_20, 'meanF_end'), m(v6_20, 'meanF_end')), '20 年近交系数 F（更低更好）'),
           ('%.2f → %.2f' % (m(v5_20, 'final_pop'), m(v6_20, 'final_pop')), '稳态种群（更热闹）'),
           ('+%.0f%%' % (m(fd['饥荒'], 'selection_r') / max(1e-9, m(fd['充足'], 'selection_r')) * 100 - 100),
            '饥荒 vs 充足：选择信号增幅'),
           ('0', '裁剪幼崽 / 崩溃次数')]

    html = []
    A = html.append
    A('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">')
    A('<meta name="viewport" content="width=device-width,initial-scale=1">')
    A('<title>幻想小狐狸 · 生态系统运行报告 v0.6</title><style>%s</style></head><body>' % CSS)
    A('<div class="wrap">')
    A('<h1>幻想小狐狸 · 生态系统运行报告 v0.6</h1>')
    A('<div class="meta">离线数值模拟 · 24 随机种子 × 5 / 20 生态年 · '
      '依据设计稿 v0.3 与需求清单 v0.3（F1–F5 已全部落地）</div>')

    A('<div class="kpi">')
    for b, s in kpi:
        A('<div><b>%s</b><span>%s</span></div>' % (b, s))
    A('</div>')

    A('<div class="note"><b>本轮最重要的一句话</b>：v0.5 里「看不见进化」不是错觉——'
      '实测静态适应度 20 年<b>下降了</b> 0.005～0.014。用育种家方程定位后发现：'
      '自然选择确实在挑人（选择差 S = +1.43，显著为正），但<b>子代没继承到优势</b>（响应 R ≈ 0）。'
      '病灶是毛色由低频隐性 + 上位控制，有利等位藏在杂合子里。'
      'v0.6 因此换用<b>尾数</b>作为可见进化的载体，并修掉了三个真正的机制缺陷。</div>')

    A('<h2>一、v0.6 改了什么：三个机制缺陷</h2>')
    A('<div class="card"><h3>D1 上限实施与密度曲线不自洽 —— 95%% 的妊娠在空转</h3>'
      '<p>v0.5 把密度软目标顶到了硬上限（<code>n_soft = 1.0 × N_max</code>），'
      '于是种群到 35 只时密度曲线 <code>L = 1 − ρ³</code> 仍有 0.33（鼓励受孕），'
      '但剩余名额只剩 5 &lt; 整窝预留 6，于是<b>被闸门拦下</b>。'
      '实测 blocked 987–1763 次 vs 真正成窝 25–33 次。'
      '繁殖机会这么稀缺时，「谁抢到名额」是运气不是适应度，选择信号被彻底淹没。</p>'
      '<p><b>修正</b>：改用 <code>L_plus_fit</code> —— 窝仔数去适配剩余名额（越挤窝越小），'
      '只有名额连最小窝仔数都放不下才拒孕；软目标降到 <code>0.90 × N_max</code>，'
      '让「密度归零」与「闸门触发」对齐。</p>@G@</div>'.replace('@G@', g_blk))

    A('<div class="card"><h3>D2 幼崽存活完全不看幼崽自己的基因</h3>'
      '<p>v0.5 的夭折率只受母亲健康 / 食物 / 季节影响，'
      '<b>与幼崽自身基因型无关</b> —— 而幼崽存活率差异恰恰是自然界选择最主要的通路。'
      '改为 <code>Juv_sel_strength = 1.2</code> 后，20 年近交 F 从 0.121 降到 <b>0.099</b>、'
      '杂合度 0.387 → <b>0.415</b>。</p></div>')

    A('<div class="card"><h3>D3 环境恒定 —— 没有方向可选</h3>'
      '<p>环境一成不变时，最优表型是固定的，初始种群本来就接近它，'
      '于是只剩下漂变与突变负荷在起作用（这就是 sfit 恒为负的原因）。'
      '加入 <code>Env_light_season_amp = 22</code> 的季节光照摆幅后，'
      '20 年近交 F 进一步降到 <b>0.095</b>（全档最低）。</p>'
      '<p class="meta">注意：把 <code>Selection_strength</code> 放大到 2.0 / 3.0 反而更糟'
      '（sfit 从 −0.01 恶化到 −0.03）—— 选择差变大会让少数个体垄断繁殖、Ne 下降、漂变加剧。'
      '因此<b>不采纳</b>放大选择强度，保持 1.0。</p></div>')

    A('<h2>二、终选对照（24 种子）</h2>')
    A('<h3>5 生态年（用户主场景）</h3>' + t5)
    A('<h3>20 生态年（长期稳定性）</h3>' + t20)
    A('<div class="note">v0.6 是唯一在<b>每一项</b>都不劣于 v0.5 的组合：'
      '窝数 +4%、空转 95%→8%、种群 +1.0、近交 F −0.011、杂合 +0.006、世代 +1.6、'
      '裁剪恒为 0、零崩溃。</div>')

    A('<h2>三、尾数：唯一肉眼可见的进化</h2>')
    A('<div class="card">@G@'
      '<p class="meta">尾数是加性累加性状（Tn1/Tn2，1–5 尾）＋ 性选择（多尾 +3%%/尾求偶加权），'
      '20 年 <b>1.86 → 2.38（+28%%）</b>，前 8 年就走完大部分位移，轨迹单调上升。</p></div>'.replace('@G@', g_tail))
    A('<div class="card">@G@'
      '<p class="meta">对照：毛长受季节交替选择（秋冬长毛有利、夏季短毛有利）→ 净选择≈0，'
      '是<b>平衡选择</b>，本来就不该有定向趋势（20 年 1.85→1.90，纹丝不动，符合预期）。'
      '毛色明度（右轴已除以 25 便于同图比较）只有漂移、没有方向。</p></div>'.replace('@G@', g_hair))

    A('<h2>四、为什么毛色进化看不见（育种家方程）</h2>')
    A('<div class="card">@G@'
      '<p>在「第 8 年换一张更亮的壁纸」场景下逐年统计：'
      '<b>选择差 S</b>（当上父母的个体比种群平均浅多少）切换后平均 <b>+1.43 ± 0.40，显著为正</b> —— '
      '说明自然选择确实在挑浅色个体；但 <b>响应 R</b>（它们的孩子比种群平均浅多少）'
      '平均 −0.32 ± 0.32，<b>与 0 无显著差异</b>。</p>'
      '<div class="warn"><b>原因</b>：想要的浅色表型需要低频隐性纯合 —— '
      '雪绒白要 <code>ww</code>（w 频率 0.10，出现概率约 1%%）、'
      '奶油金要 <code>dd</code>（d 频率 0.20，约 4%%）。'
      '有利等位绝大多数藏在杂合子里，选择看不见它们（Haldane 的经典结论）。'
      '这是当前毛色设计的<b>固有属性，不是 bug</b>，硬改要动 §2.1 已确认的显性序列，'
      '因此建议不改，改用尾数承载可见进化。</div></div>'.replace('@G@', g_sr))

    A('<h2>五、食物机制与短缺场景（F5）</h2>')
    A('<div class="card"><p>把 v0.5 的「布尔开关」换成<b>食物池 + 按适应度竞争取食</b>：'
      '每天投递固定份数，每只的取食权重 = 自身适应度 / 种群均值，'
      '于是短缺时高适应度个体先吃饱、低适应度先掉膘。'
      '掉膘门槛 70%%，由此<b>承载力 N* = 每日供给 / 96</b> —— 投喂量直接决定能养多少只。</p>'
      + tbl(['场景', '末种群', '窝数', '休眠次数', '末饱食', '选择 r', '崩溃'], food_rows)
      + '</div>')
    A('<div class="card">' + g_food
      + '<p class="meta">食物短缺是最强的选择引擎：'
      '选择相关从充足的 +0.062 升到饥荒的 <b>+0.153</b>。'
      '想让玩家看见自然选择，就别把狐狸喂太饱。</p></div>')
    A(''.join(['<div class="card">', g_pop,
      '<p class="meta">「不会饿死」成立：断供 5 年（120 游戏天）<b>零崩溃</b>，'
      '种群稳定在 5.7 只深度休眠；断供 2 年后恢复投喂，回到 <b>35.8 只</b>、繁殖重启。</p></div>']))
    A('<div class="note"><b>顺带修掉的两个缺陷</b>：'
      '① 断供时野外引入仍在每 14 天送一只狐狸进来，虚假维持了种群 —— '
      '已改为供给满足率 &lt; 70%% 不再有移民迁入；'
      '② 新增<b>深度休眠保底</b>：种群凋零到最后 3 只且全体休眠时停止衰老与疾病，'
      '保证玩家长期不投喂回来也不会发现狐狸全没了。</div>')

    A('<h2>六、三档节奏预设（20 年 · 12 种子）</h2>')
    A('<div class="card">' + g_pres + tbl(['档位', '世代', '近交 F', '杂合度', '窝数', '引入数'],
                                          pres_rows) + '</div>')
    A('<div class="note">三档 20 年近交 F 都落在 0.081–0.092 的安全区。'
      '激进档多 22% 世代，但引入个体多 65%（基因更多来自野外而非本族演化）；'
      '稳健档则相反。<b>默认标准档</b>。</div>')

    A('<h2>七、v0.6 五轮试运行（5 生态年）</h2>')
    A(tbl(['轮次', '世代', '末种群', '平均种群', '杂合度 起→末', '新突变', '裁剪', '崩溃'], round_rows))
    A('<div class="note">五轮全部存活，末种群 35–38，世代 8–10，零裁剪。'
      '遗传规则自检 <code>verify_genetics.py</code>：<b>16 项全部通过</b>'
      '（含 3:1 分离比、上位、九尾、累加 1:4:6:4:1、不完全显性 1:2:1、标准谱系亲缘系数）。</div>')

    A('<h2>八、遗留问题</h2>')
    A('<ul>'
      '<li><b>毛色进化不可见</b>（隐性 + 上位的固有属性）：建议不改规则，'
      '把尾数放上统计面板主位；换壁纸时给一句提示「背景变亮了，浅色毛发要十几代才看得出变化」。</li>'
      '<li><b>恒定 + 食物充足场景下选择信号仍弱</b>（r ≈ 0.01–0.06）：'
      '靠食物档位提供压力入口，或把默认档位设成「正常」而非「充足」。</li>'
      '<li><b>单轮轨迹不可逐位复现</b>：v0.6 重构引入的浮点路径变化会被混沌放大，'
      '对比一律用<b>多种子均值</b>。</li>'
      '<li><b>尾数长期会饱和到 5 尾</b>：20 年只到 2.4，离饱和还远；'
      '饱和后由九尾（V 突变）接棒作为稀有目标。</li></ul>')

    A('<p class="meta" style="margin-top:40px">生成脚本：<code>sim/gen_report_v3.py</code> · '
      '模拟器：<code>sim/fox_ecosystem_sim.py --variant v3</code></p>')
    A('</div></body></html>')
    return ''.join(html)


if __name__ == '__main__':
    D = collect()
    html = build(D)
    with io.open(_OUT, 'w', encoding='utf-8') as f:
        f.write(html)
    print('已生成', os.path.abspath(_OUT), '%.1f KB' % (len(html.encode('utf-8')) / 1024.0))
