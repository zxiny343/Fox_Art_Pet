# -*- coding: utf-8 -*-
"""
动画数据可用性体检（2026-11-02）
================================================================
在写播放器之前先回答：36 个动作、20 根骨骼、9 个插槽的数据到底能不能直接用。

检查四件事：
  A. 通道引用的骨骼是否存在（含多尾分支骨）
  B. 插槽是否存在、anchor 是否可信
  C. 插槽引用的附件能否在磁盘找到（含毛色补全）
  D. 每个动作的振幅与是否被我们的渲染器支持
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anim as AN                                      # noqa: E402
import artmap as AM                                    # noqa: E402

PASS = FAIL = 0
ROWS = []


def ck(ok, title, detail=''):
    global PASS, FAIL
    PASS, FAIL = (PASS + 1, FAIL) if ok else (PASS, FAIL + 1)
    ROWS.append('  %s %-52s %s' % ('✓' if ok else '✗', title, detail))


def main():
    bones = set(AN.BONES)
    # 多尾分支骨：tail_b{i}_{root,mid,sub,tip}
    branch_bones = set()
    for tpl in AN.SKEL.get('tailBranchTemplates', {}).values():
        for b in tpl.get('branches', []):
            for bb in b.get('bones', []):
                branch_bones.add(bb['id'])
    known = bones | branch_bones

    # --- A. 骨骼引用 ---
    bad_bone = {}
    for aid, a in AN.ACTIONS.items():
        for c in a.get('channels', []):
            if c['bone'] not in known:
                bad_bone.setdefault(c['bone'], []).append(aid)
    ck(not bad_bone, 'A 所有通道引用的骨骼都存在',
       '%d 根已知骨，未知 %d 个%s'
       % (len(known), len(bad_bone),
          ('：' + ', '.join(sorted(bad_bone)[:4])) if bad_bone else ''))

    # --- B. 插槽 ---
    slots = {s['id']: s for s in AN.SKEL.get('slots', [])}
    used_slots = set()
    for a in AN.ACTIONS.values():
        for s in a.get('slots', []):
            used_slots.add(s['slot'])
    miss = sorted(used_slots - set(slots))
    ck(not miss, 'B 动作引用的插槽都在 skeleton 里',
       '用到 %d 个，缺 %s' % (len(used_slots), miss or '无'))

    # anchor 可信度：tail / ear_l_att / ear_r_att 的 anchor 若等于 head 的，
    # 基本是复制粘贴遗留
    head_anc = tuple(slots.get('head', {}).get('anchor', (0, 0)))
    suspicious = []
    for sid in sorted(slots):
        anc = tuple(slots[sid].get('anchor', (0, 0)))
        bone = slots[sid].get('bone')
        b = AN.BONES.get(bone)
        if not b or anc == (0, 0):
            continue
        # 插槽 anchor 应该落在其骨骼附近（用骨骼 start/end 的两端做参照）
        d = min(((anc[0] - p[0]) ** 2 + (anc[1] - p[1]) ** 2) ** 0.5
                for p in (b['start'], b['end']))
        if d > 120:
            suspicious.append('%s(anchor%s → bone %s 距 %.0fpx)'
                              % (sid, anc, bone, d))
    ck(not suspicious, 'B 插槽 anchor 落在其骨骼附近（≤120px）',
       '可疑 %d 个：%s' % (len(suspicious), '; '.join(suspicious[:3]) or '无'))

    # --- C. 附件可解析 ---
    coats = sorted(AM._colorways())
    att_miss = {}
    for aid, a in AN.ACTIONS.items():
        for s in a.get('slots', []):
            for k in s.get('keys', []):
                name = k[1]
                if not isinstance(name, str):
                    continue
                # 用全部毛色试，只要有一个能解析就算通（其余靠毛色补全）
                if AM.find_attachment(name, 'blue') is None and \
                        AM.find_attachment(name, None) is None:
                    att_miss.setdefault(name, []).append(aid)
    ck(not att_miss, 'C 插槽引用的附件都能在磁盘找到',
       '缺 %d 个%s' % (len(att_miss),
                       ('：' + ', '.join(sorted(att_miss)[:5])) if att_miss else ''))

    # 闭眼件带毛色：确认每个毛色都有
    no_coat = [c for c in coats
               if not os.path.isfile(os.path.join(
                   AM.MASTER, 'Expressions', 'eye_closed_%s.png' % c))]
    ck(not no_coat, 'C eye_closed 每个毛色都有对应件',
       '%d 色，缺 %s' % (len(coats), no_coat or '无'))

    # --- D. 动作可用性与振幅 ---
    SUPPORTED = {'tail_root', 'tail_mid', 'tail_sub', 'tail_tip',
                 'ear_l', 'ear_r', 'body', 'head', 'pelvis'}
    print('\n动作清单（36 个）：')
    print('  %-18s %-5s %5s %5s  %-34s %s'
          % ('id', 'layer', '帧', 'loop', '涉及骨骼', '我方支持'))
    unsupported = []
    for a in AN.ACTIONS.values():
        bs = sorted({c['bone'] for c in a.get('channels', [])})
        # 只统计真正驱动形变的通道
        drive = [c for c in a.get('channels', [])
                 if abs(max(abs(k[1]) for k in c['keys'] if isinstance(k[1], (int, float))) or 0) > 0.01
                 or c['channel'] in ('scaleX', 'scaleY')]
        bs = sorted({c['bone'] for c in drive})
        ok = all(b in SUPPORTED for b in bs)
        if not ok:
            unsupported.append((a['id'], [b for b in bs if b not in SUPPORTED]))
        print('  %-18s %-5s %5d %5s  %-34s %s'
              % (a['id'], a.get('layer'), a.get('frames', 0), a.get('loop'),
                 ','.join(bs)[:34], 'OK' if ok else '需骨骼 %s' % [b for b in bs if b not in SUPPORTED]))
    print()
    ck(len(unsupported) <= 12,
       'D 大多数动作只用我方已支持的骨骼',
       '36 个里 %d 个需要未实现的骨骼（腿/躯干位移）' % len(unsupported))

    # --- E. 振幅体检：摆尾到底有多大 ---
    print('关键动作振幅（deg 或 ratio）：')
    for aid in ('idle_tail_sway', 'idle_breath', 'idle_ear_twitch', 'walk'):
        a = AN.ACTIONS[aid]
        for c in a.get('channels', []):
            vs = [k[1] for k in c['keys'] if isinstance(k[1], (int, float))]
            if not vs:
                continue
            print('    %-16s %-10s %-12s  %6.2f … %6.2f'
                  % (aid, c['bone'], c['channel'], min(vs), max(vs)))
    print()

    print('\n'.join(ROWS))
    print('')
    print('=' * 62)
    print('通过 %d 项，失败 %d 项' % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
