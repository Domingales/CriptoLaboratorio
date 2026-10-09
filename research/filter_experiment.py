"""Exploratory fixed-rule filters on existing episodes; no holdout tuning."""
import csv, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
from research.experiment import features, summarize, millis

ROOT = Path(__file__).resolve().parents[1]

def rule_masks(x, side, bounds):
    trend = side * x.ema_dist_200.to_numpy() > 0
    adx = x.adx.to_numpy()
    volume = x.vol_ratio.to_numpy() >= 1.2
    return {'trend200': trend, 'adx20': adx >= .20, 'adx25': adx >= .25,
            'volume120': volume, 'trend200_adx20': trend & (adx >= .20),
            'trend200_adx20_volume120': trend & (adx >= .20) & volume,
            'normal_volatility': x.atr_pct.between(*bounds).to_numpy()}

def eligible(m, base, protocol):
    return (m['HIT'] + m['FAIL'] >= protocol['minimum_validation_resolved']
            and m['coverage'] >= protocol['minimum_validation_coverage']
            and m['barrier_precision'] is not None and base['barrier_precision'] is not None
            and m['barrier_precision'] >= base['barrier_precision'] + protocol['minimum_validation_precision_gain']
            and m['mean_net'] is not None and m['mean_net'] > 0)

def paired_months(events, keep):
    # Rejected scenarios earn zero; no capital redeployment assumed.
    months = pd.date_range('2025-01-01', '2026-09-01', freq='MS').strftime('%Y-%m')
    delta = {m: 0. for m in months}
    for e, accepted in zip(events, keep):
        if e['gross'] is not None and not accepted:
            m = pd.to_datetime(e['time'], unit='ms', utc=True).strftime('%Y-%m')
            delta[m] -= e['gross'] - .004
    values = np.array(list(delta.values()))
    boots = np.random.default_rng(17).choice(values, (5000, len(values)), replace=True).mean(axis=1)
    return {'monthly_sum_delta': float(values.mean()),
            'descriptive_ci95': np.quantile(boots, [.025, .975]).tolist(),
            'months': delta, 'multiple_testing_adjusted': False}

def run(root=ROOT):
    pp = root/'docs/filter-experiment-v2-protocol.json'
    protocol = json.loads(pp.read_text())
    rows=[]; selections=[]
    for path in sorted((root/'results/web').glob('*.json')):
        web=json.loads(path.read_text()); report=web['report']
        symbol, tf=report['symbol'],report['timeframe']
        a=np.load(root/'data'/f'{symbol}_{tf}.npy'); x,_,_,_=features(a)
        train=(a[:,6]>=millis('2023-01-01'))&(a[:,6]<millis('2024-01-01'))
        bounds=x.loc[train,'atr_pct'].quantile([.1,.9]).to_numpy()
        lookup={int(t):i for i,t in enumerate(a[:,6])}
        for mode in ['ema','original']:
            events={p:[e for e in web['events'] if e['mode']==mode and e['period']==p]
                    for p in ['validation','holdout']}
            masks={}
            for period, ev in events.items():
                ix=[lookup[e['time']] for e in ev]
                masks[period]=rule_masks(x.iloc[ix], np.array([e['side'] for e in ev]), bounds)
            baseline={p:summarize(ev,len(ev),cost=.004) for p,ev in events.items()}
            candidates=[]
            for name in protocol['filters']:
                metrics={p:summarize([e for e,k in zip(events[p],masks[p][name]) if k],len(events[p]),cost=.004)
                         for p in events}
                row={'symbol':symbol,'timeframe':tf,'engine':mode,'filter':name,
                     'eligible_on_validation':eligible(metrics['validation'],baseline['validation'],protocol),
                     'validation':metrics['validation'],'review':metrics['holdout'],
                     'baseline_validation':baseline['validation'],'baseline_review':baseline['holdout'],
                     'paired_review':paired_months(events['holdout'],masks['holdout'][name])}
                rows.append(row); candidates.append(row)
            admitted=[r for r in candidates if r['eligible_on_validation']]
            chosen=sorted(admitted,key=lambda r:(-r['validation']['mean_net'],r['filter']))[0] if admitted else None
            selections.append({'symbol':symbol,'timeframe':tf,'engine':mode,
                               'chosen_filter':chosen['filter'] if chosen else None,
                               'result':chosen,'reason':None if chosen else 'No candidate passed validation requirements'})
    output={'protocol':protocol,'protocol_sha256':hashlib.sha256(pp.read_bytes()).hexdigest(),
            'candidates':rows,'selections':selections,'integration':False}
    target=root/'results/filter-v2';target.mkdir(exist_ok=True)
    (target/'results.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    cols=['symbol','timeframe','engine','filter','eligible_on_validation','validation_n','validation_precision',
          'validation_mean_net_40bps','review_n','review_precision','review_mean_net_40bps','review_base_precision',
          'review_base_mean_net_40bps','review_coverage']
    with (target/'comparison.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=cols);writer.writeheader()
        for r in rows:
            v,h,b=r['validation'],r['review'],r['baseline_review']
            writer.writerow(dict(zip(cols,[r['symbol'],r['timeframe'],r['engine'],r['filter'],r['eligible_on_validation'],
                v['HIT']+v['FAIL'],v['barrier_precision'],v['mean_net'],h['HIT']+h['FAIL'],h['barrier_precision'],h['mean_net'],
                b['barrier_precision'],b['mean_net'],h['coverage']])))
    print(json.dumps({'candidates':len(rows),'selection_groups':len(selections),
                      'selected':[{k:r[k] for k in ['symbol','timeframe','engine','chosen_filter']} for r in selections if r['result']]}))
    return output

if __name__=='__main__': run()
