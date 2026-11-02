# -*- coding: utf-8 -*-
import os, statistics
from multiprocessing import Pool
_HERE=os.path.dirname(os.path.abspath(__file__)); _M=None
def _init():
    global _M
    import importlib.util
    spec=importlib.util.spec_from_file_location('m', os.path.join(_HERE,'fox_ecosystem_sim.py'))
    _M=importlib.util.module_from_spec(spec); spec.loader.exec_module(_M)
def one(a):
    cap, seed, yrs = a
    P=dict(_M.TUNED_V2_PARAMS); P['N_max']=cap; P['Litter_reserve']=6
    return cap, _M.run_round(seed,P,yrs)
if __name__=='__main__':
    seeds=[20261031+i*7919 for i in range(10)]
    tasks=[(c,s,20) for c in (30,40,50,60) for s in seeds]
    with Pool(initializer=_init) as pool:
        raw=pool.map(one,tasks,chunksize=1)
    store={}
    for cap,r in raw: store.setdefault(cap,[]).append(r)
    print('%-8s %12s %14s %10s %10s %10s %10s %10s'%('上限','世代','近交 F','指纹2','毛色','窝/20年','出生/20年','引入数'))
    _ = None
    for cap in (30,40,50,60):
        rs=store[cap]
        def st(k):
            v=[r[k] for r in rs]; return statistics.mean(v), statistics.pstdev(v)/max(1,len(v)**0.5)
        G,Gs=st('max_generation'); F,Fs=st('meanF_end'); P2,_=st('fp2_ratio')
        C=statistics.mean([len(r['end_colors']) for r in rs]); L,_=st('total_litters'); B,_=st('total_births')
        IM,_=st('immigrants')
        print('%-8d %6.1f±%-5.1f %6.3f±%-5.3f %10.2f %10.2f %10.0f %10.1f'%(cap,G,Gs,F,Fs,P2,C,L,IM))
