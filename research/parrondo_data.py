"""Download official hourly Binance spot ZIPs and derive 4h/1d candles.

Isolated Parrondo input preparation: does not alter the 5m production protocol.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from research.download import archive, month_keys
from research.parrondo_backtest import SYMBOLS

def aggregate_hourly(a, step):
    # Hourly input: reject incomplete aggregation buckets.
    hours=step//3600000
    buckets=(a[:,0].astype('int64')//step)*step
    unique,starts,counts=np.unique(buckets,return_index=True,return_counts=True)
    out=[]
    for bucket,i,n in zip(unique,starts,counts):
        window=a[i:i+n]
        if (n!=hours or int(window[0,0])!=int(bucket) or
            int(window[-1,6])!=int(bucket+step-1) or
            np.any(np.diff(window[:,0])!=3600000)):
            continue
        out.append([bucket,window[0,1],np.max(window[:,2]),
                    np.min(window[:,3]),window[-1,4],np.sum(window[:,5]),bucket+step-1])
    return np.asarray(out,dtype=float).reshape(-1,7)

def run(root,start='2022-01',end='2026-09'):
    root.mkdir(parents=True,exist_ok=True)
    report={}
    for symbol in SYMBOLS:
        parts=[];issues=[]
        for month in month_keys(start,end):
            try:
                a,meta=archive(root,symbol,'1h',month)
                parts.append(a)
            except Exception as exc:
                issues.append(dict(month=month,error=str(exc)))
        if issues:
            report[symbol]=dict(status='NOT_EVALUABLE',issues=issues)
            continue
        a=np.concatenate(parts)
        if np.any(np.diff(a[:,0])<=0):
            report[symbol]=dict(status='NOT_EVALUABLE',issues=['Nonmonotonic hourly data'])
            continue
        np.save(root/f'{symbol}_1h.npy',a)
        for tf,step in [('4h',14400000),('1d',86400000)]:
            np.save(root/f'{symbol}_{tf}.npy',aggregate_hourly(a,step))
        report[symbol]=dict(status='COMPLETE',hourly_candles=len(a),
            hourly_gaps=int(np.sum(np.diff(a[:,0])!=3600000)))
    (root/'parrondo-source-manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    if any(x['status']!='COMPLETE' for x in report.values()):
        raise RuntimeError('Incomplete official hourly data; do not treat as successful run')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--data',type=Path,default=Path('data'))
    p.add_argument('--start',default='2022-01')
    p.add_argument('--end',default='2026-09')
    args=p.parse_args()
    print(json.dumps(run(args.data,args.start,args.end)))
