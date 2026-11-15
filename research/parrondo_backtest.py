"""Evaluate frozen Parrondo baselines on audited local official candle arrays.

Run only after research.download created data/<SYMBOL>_<TF>.npy.
This script NEVER downloads, changes models, or trades.
"""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from research.parrondo import Bar, evaluate

SYMBOLS=('BTC','ETH','ADA','SOL','XRP')
TIMEFRAMES=('1h','4h','1d')
PERIODS={
    'validation':('2024-07-01','2025-01-01'),
    'holdout':('2025-01-01','2026-10-01'),
}
def timestamp(s):
    return int(np.datetime64(s,'ms').astype('int64'))

def evaluate_file(path, start, end, cost_bps):
    if not np.isfinite(cost_bps) or cost_bps < 0:
        raise ValueError('Invalid transaction costs')
    a=np.load(path,allow_pickle=False)
    if a.ndim!=2 or a.shape[1]<5 or len(a)<52:
        raise ValueError('Invalid candle array')
    times=a[:,0].astype('int64')
    if np.any(np.diff(times)<=0):
        raise ValueError('Nonmonotonic or duplicated timestamps')
    step=int(times[1]-times[0])
    if step not in (3600000,14400000,86400000):
        raise ValueError('Unsupported candle timeframe')
    first=int(np.searchsorted(times,start))
    last=int(np.searchsorted(times,end))
    if first<50 or last-first<100:
        raise ValueError('Insufficient history or evaluation candles')
    # Never fill missing candles. Each gap splits the series into independent
    # continuous segments. A fresh 50-candle warmup is required after each gap.
    boundaries=np.r_[0,np.flatnonzero(np.diff(times)!=step)+1,len(a)]
    from research.parrondo import policies
    keys=('A','B','C_aabb','C_state')
    returns={k:[] for k in keys}
    skipped_gaps=int(len(boundaries)-2)
    eligible=0
    for left,right in zip(boundaries[:-1],boundaries[1:]):
        if right-left<52 or right<=first or left>=last:
            continue
        bars=[Bar(int(r[0]),float(r[1]),float(r[2]),float(r[3]),float(r[4]))
              for r in a[left:min(right,last)]]
        if len(bars)<52:
            continue
        for decision in policies(bars):
            global_t=left+decision['t']
            if not (first<=global_t and global_t+1<last):
                continue
            candle=bars[decision['t']+1]
            eligible+=1
            for key in keys:
                returns[key].append(decision[key]*(candle.close/candle.open-1)-cost_bps/10000)
    if eligible<100:
        raise ValueError('Insufficient consecutive eligible episodes after gap exclusions')
    out={}
    for key,values in returns.items():
        wealth=1.;peak=1.;drawdown=0.
        for r in values:
            wealth*=1+r;peak=max(peak,wealth);drawdown=min(drawdown,wealth/peak-1)
        out[key]=dict(n=len(values),mean_net=sum(values)/len(values),
                      compound=wealth-1,max_drawdown=drawdown,
                      positive_net_rate=sum(x>0 for x in values)/len(values))
    # Metadata does not enter scoring. No synthetic candles or bridging trades.
    out['_integrity']=dict(gaps=skipped_gaps,eligible_episodes=eligible,
                           excluded_period_candles=int(last-first-eligible))
    return out

def run(data,output,cost_bps):
    rows=[]
    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            path=data/f'{symbol}_{tf}.npy'
            for period,(start,end) in PERIODS.items():
                row=dict(symbol=symbol,timeframe=tf,period=period)
                try:
                    if not path.exists(): raise FileNotFoundError(str(path))
                    metrics=evaluate_file(path,timestamp(start),timestamp(end),cost_bps)
                    row.update(status='COMPLETE',metrics=metrics,
                        parrondo_candidate={k:(metrics['A']['mean_net']<0 and
                            metrics['B']['mean_net']<0 and metrics[k]['mean_net']>0)
                            for k in ('C_aabb','C_state')})
                except (ValueError,FileNotFoundError,IndexError) as e:
                    row.update(status='NOT_EVALUABLE',reason=str(e))
                rows.append(row)
    output.mkdir(parents=True,exist_ok=True)
    (output/'results.json').write_text(json.dumps(dict(cost_bps=cost_bps,results=rows,
        integration=False,interpretation='Exploratory fixed policies; holdout not prospectively unseen after design'),indent=2)+'\n')
    with (output/'comparison.csv').open('w',newline='') as f:
        writer=csv.writer(f)
        writer.writerow(['symbol','timeframe','period','status','strategy','n','mean_net','compound','max_drawdown','positive_net_rate','parrondo_candidate','reason'])
        for row in rows:
            if row['status']!='COMPLETE':
                writer.writerow([row['symbol'],row['timeframe'],row['period'],row['status'],'','','','','','','',row['reason']])
                continue
            for key,m in row['metrics'].items():
                if key.startswith('_'): continue
                writer.writerow([row['symbol'],row['timeframe'],row['period'],'COMPLETE',key,m['n'],m['mean_net'],m['compound'],m['max_drawdown'],m['positive_net_rate'],row['parrondo_candidate'].get(key,'')])
    print(json.dumps({'complete':sum(r['status']=='COMPLETE' for r in rows),
                      'not_evaluable':sum(r['status']!='COMPLETE' for r in rows),
                      'output':str(output)}))
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--data',type=Path,default=Path('data'))
    p.add_argument('--output',type=Path,default=Path('results/parrondo'))
    p.add_argument('--cost-bps',type=float,default=20)
    args=p.parse_args()
    run(args.data,args.output,args.cost_bps)
