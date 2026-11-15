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
    a=np.load(path,allow_pickle=False)
    # Include warmup before evaluation; decisions and outcomes must be inside period.
    # The evaluator's fixed warmup is 50 bars. One extra bar ensures next-bar exit.
    first=np.searchsorted(a[:,0],start)
    last=np.searchsorted(a[:,0],end)
    if first<50 or last-first<100:
        raise ValueError('Insufficient history or evaluation candles')
    # Evaluate entire history up to the end to preserve continuous indicators.
    bars=[Bar(int(r[0]),float(r[1]),float(r[2]),float(r[3]),float(r[4])) for r in a[:last]]
    # Discontinuities are not silently skipped; caller marks series not evaluable.
    from research.parrondo import policies
    decisions=policies(bars)
    filtered=[d for d in decisions if first<=d['t'] and d['t']+1<last]
    if not filtered: raise ValueError('No eligible decisions')
    out={}
    for key in ('A','B','C_aabb','C_state'):
        returns=[]
        for d in filtered:
            c=bars[d['t']+1]
            returns.append(d[key]*(c.close/c.open-1)-cost_bps/10000)
        wealth=1.;peak=1.;drawdown=0.
        for r in returns:
            wealth*=1+r;peak=max(peak,wealth);drawdown=min(drawdown,wealth/peak-1)
        out[key]=dict(n=len(returns),mean_net=sum(returns)/len(returns),
                      compound=wealth-1,max_drawdown=drawdown,
                      positive_net_rate=sum(x>0 for x in returns)/len(returns))
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
