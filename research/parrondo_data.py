"""Download official hourly Binance spot ZIPs and derive 4h/1d candles.

Isolated Parrondo input preparation: does not alter the 5m production protocol.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from research.download import archive, aggregate, month_keys
from research.parrondo_backtest import SYMBOLS

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
            np.save(root/f'{symbol}_{tf}.npy',aggregate(a,step))
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
