"""Frozen chronological experiment. No threshold is optimized on holdout data."""
import argparse, datetime as dt, hashlib, json, math, pickle
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

STEPS={'1h':3600000,'4h':14400000,'1d':86400000}

def millis(s): return int(pd.Timestamp(s).timestamp()*1000)

def features(a):
    f=pd.DataFrame(a,columns=['time','open','high','low','close','volume','end'])
    c,h,l,v=f.close,f.high,f.low,f.volume
    x=pd.DataFrame(index=f.index)
    for k in [1,3,6,12,24]: x[f'return_{k}']=np.log(c/c.shift(k))
    ema={k:c.ewm(span=k,adjust=False,min_periods=k).mean() for k in [20,50,200]}
    for k in [20,50,200]:
        x[f'ema_dist_{k}']=c/ema[k]-1
        x[f'ema_slope_{k}']=ema[k]/ema[k].shift(3)-1
    delta=c.diff(); gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    rsi=100-100/(1+gain/loss.replace(0,np.nan));rsi=rsi.where(loss!=0,100).where((gain!=0)|(loss!=0),50)
    x['rsi']=rsi/100; x['rsi_slope']=rsi.diff(3)/100
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    atr=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean();x['atr_pct']=atr/c
    up=h.diff();down=-l.diff();plus=up.where((up>down)&(up>0),0);minus=down.where((down>up)&(down>0),0)
    pdi=100*plus.ewm(alpha=1/14,adjust=False,min_periods=14).mean()/atr
    mdi=100*minus.ewm(alpha=1/14,adjust=False,min_periods=14).mean()/atr
    dx=100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)
    x['adx']=dx.ewm(alpha=1/14,adjust=False,min_periods=14).mean()/100
    x['dmi']=(pdi-mdi)/100
    x['vol_ratio']=v/v.shift().rolling(20).mean()
    x['volatility']=np.log(c/c.shift()).rolling(24).std()
    mean=c.rolling(20).mean();std=c.rolling(20).std()
    x['bb_position']=(c-mean)/(2*std);x['bb_width']=4*std/mean
    x['range_pct']=(h-l)/c;x['body_pct']=(c-f.open)/c
    x['distance_high']=c/h.shift().rolling(20).max()-1
    x['distance_low']=c/l.shift().rolling(20).min()-1
    x['hour_sin']=np.sin(2*np.pi*pd.to_datetime(f.end,unit='ms',utc=True).dt.hour/24)
    x['hour_cos']=np.cos(2*np.pi*pd.to_datetime(f.end,unit='ms',utc=True).dt.hour/24)
    side=np.where(ema[20]>=ema[50],1,-1)
    regime=np.where(x.adx<.20,'LATERAL',np.where(ema[20]>=ema[50],'ALCISTA','BAJISTA'))
    return x.replace([np.inf,-np.inf],np.nan),atr.to_numpy(),side,regime

def valid_windows(a,step,lookback=220):
    streak=np.ones(len(a),dtype=int)
    for i in range(1,len(a)): streak[i]=streak[i-1]+1 if a[i,0]==a[i-1,0]+step else 1
    return streak>=lookback

def resolve(fine,entry_time,entry,target,horizon_ms,side=1,cost=.002):
    """Resolve only complete 5m windows, conservatively flag intrabar ambiguity."""
    n=horizon_ms//300000;start=int(np.searchsorted(fine[:,0],entry_time));w=fine[start:start+n]
    if len(w)!=n or not np.array_equal(w[:,0],entry_time+np.arange(n)*300000):
        return dict(status='MISSING',gross=None,net=None,mfe=None,mae=None,exit_time=None)
    upper=entry*(1+target);lower=entry*(1-target)
    hu=w[:,2]>=upper;hl=w[:,3]<=lower;touched=np.flatnonzero(hu|hl)
    mfe=float(np.max((w[:,2]/entry-1) if side==1 else (1-w[:,3]/entry)))
    mae=float(np.min((w[:,3]/entry-1) if side==1 else (1-w[:,2]/entry)))
    status='NEUTRAL';price=float(w[-1,4]);when=int(w[-1,6])
    if len(touched):
        j=int(touched[0]);when=int(w[j,6]);op=float(w[j,1])
        # At a gap beyond a barrier, its order is known at the open.
        if op>=upper: hit_up=True;hit_down=False
        elif op<=lower: hit_up=False;hit_down=True
        else: hit_up=bool(hu[j]);hit_down=bool(hl[j])
        if hit_up and hit_down:
            return dict(status='AMBIGUOUS',gross=None,net=None,mfe=mfe,mae=mae,exit_time=when)
        favorable=hit_up if side==1 else hit_down
        status='HIT' if favorable else 'FAIL'
        price=(upper if hit_up else lower)
        # Stops may execute worse than the barrier on a gap. Targets get no bonus.
        if not favorable: price=min(lower,op) if side==1 else max(upper,op)
    gross=side*(price/entry-1)
    return dict(status=status,gross=float(gross),net=float(gross-cost),mfe=max(0,mfe),mae=min(0,mae),exit_time=when)

def build_labels(a,fine,atr,horizon_bars,step):
    out=[]
    for i in range(len(a)):
        if i+1>=len(a):out.append(None);continue
        entry_time=int(a[i,6]+1);entry=float(a[i+1,1])
        if a[i+1,0]!=entry_time or not np.isfinite(atr[i]):out.append(None);continue
        target=max(.004,float(atr[i]/entry))
        r=resolve(fine,entry_time,entry,target,horizon_bars*step)
        out.append(dict(**r,target=target,entry=entry,entry_time=entry_time,
                        maturity=entry_time+horizon_bars*step-1))
    return out

def calibrate_multi(model,xcal,ycal):
    raw=np.clip(model.predict_proba(xcal),1e-7,1)
    cal=LogisticRegression(C=1,max_iter=1000,random_state=17)
    cal.fit(np.log(raw),ycal)
    return cal

def calibrated(model,cal,x):
    raw=np.clip(model.predict_proba(x),1e-7,1)
    return cal.predict_proba(np.log(raw))

def wilson(wins,n):
    if not n:return [None,None]
    p=wins/n;z=1.96;den=1+z*z/n
    center=(p+z*z/(2*n))/den;radius=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [center-radius,center+radius]

def summarize(events,decisions,cost=.002):
    valid=[r for r in events if r['net'] is not None]
    wins=sum(r['status']=='HIT' for r in valid);losses=sum(r['status']=='FAIL' for r in valid)
    profitable=sum(r['gross']-cost>0 for r in valid)
    counts={s:sum(r['status']==s for r in events) for s in ['HIT','FAIL','NEUTRAL','AMBIGUOUS','MISSING']}
    # Research scenario returns, not a spot portfolio or profit guarantee.
    ret=np.array([r['gross']-cost for r in valid]);equity=np.cumprod(1+ret)
    full=np.r_[1,equity];dd=full/np.maximum.accumulate(full)-1
    gains=ret[ret>0].sum();losing=-ret[ret<0].sum()
    return dict(signals=len(events),valid=len(valid),**counts,
        coverage=len(events)/decisions if decisions else 0,
        barrier_precision=wins/(wins+losses) if wins+losses else None,
        precision_ci95=wilson(wins,wins+losses),positive_net_rate=profitable/len(valid) if valid else None,
        mean_net=float(ret.mean()) if valid else None,
        scenario_compound=float(equity[-1]-1) if valid else None,
        max_drawdown=float(dd.min()) if valid else None,
        profit_factor=float(gains/losing) if losing>0 else None,
        cost_sensitivity={str(b):float(np.mean([r['gross']-b/10000 for r in valid])) if valid else None for b in [10,20,40]},
        by_direction={d:dict(signals=sum(r['side']==s for r in events),
            valid=sum(r['side']==s for r in valid),
            mean_net=float(np.mean([r['gross']-cost for r in valid if r['side']==s])) if any(r['side']==s for r in valid) else None)
            for d,s in [('BUY',1),('SELL',-1)]})

def episode_selection(indices,accept,horizon,times=None,step=None):
    chosen=[];available=-1
    for i in indices:
        clock=i if times is None else times[i]
        if clock<available:continue
        if accept[i]:chosen.append(i);available=i+horizon+1 if times is None else clock+(horizon+1)*step
    return chosen

def asset_run(data,output,symbol,tf,protocol):
    step=STEPS[tf];horizon=protocol['horizon_bars'][tf]
    a=np.load(data/f'{symbol}_{tf}.npy');fine=np.load(data/f'{symbol}_5m.npy',mmap_mode='r')
    x,atr,base_side,regime=features(a)
    btc=np.load(data/f'BTC_{tf}.npy');bx,_,_,_=features(btc)
    # Exact closed candle timestamps only; no forward fills over missing BTC data.
    bmap=pd.DataFrame({'end':btc[:,6],'btc_return':bx.return_6,'btc_trend':bx.ema_dist_50,'btc_volatility':bx.volatility}).set_index('end')
    aligned=bmap.reindex(a[:,6]).reset_index(drop=True)
    x=pd.concat([x,aligned],axis=1);valid=valid_windows(a,step)&np.isfinite(x.to_numpy()).all(axis=1)
    labels=build_labels(a,fine,atr,horizon,step)
    y=np.full(len(a),-1,dtype=int);meta_y=np.full(len(a),-1,dtype=int)
    for i,r in enumerate(labels):
        if r and r['status'] in ['HIT','FAIL','NEUTRAL']:
            y[i]={'FAIL':0,'NEUTRAL':1,'HIT':2}[r['status']]
            # SELL labels resolved separately to handle asymmetric gap execution.
            rr=r if base_side[i]==1 else resolve(fine,r['entry_time'],r['entry'],r['target'],horizon*step,-1)
            if rr['net'] is not None:meta_y[i]=int(rr['net']>0)
    starts=a[:,6];maturities=starts+horizon*step
    train=valid&(y>=0)&(starts>=millis(protocol['source_from']))&(maturities<millis(protocol['train_label_end_exclusive']))
    cal=valid&(y>=0)&(starts>=millis(protocol['calibration_start']))&(maturities<millis(protocol['calibration_label_end_exclusive']))
    mtrain=train&(meta_y>=0);mcal=cal&(meta_y>=0)
    xmeta=x.copy();xmeta['base_side']=base_side
    needed=[(train,y,3),(cal,y,3),(mtrain,meta_y,2),(mcal,meta_y,2)]
    if any(mask.sum()<100 or len(np.unique(target[mask]))<classes for mask,target,classes in needed):
        return dict(symbol=symbol,timeframe=tf,status='NOT_EVALUABLE',reason='Insufficient training/calibration samples or classes',
                    training_samples=int(train.sum()),calibration_samples=int(cal.sum()),
                    train_class_counts={str(k):int(np.sum(y[train]==k)) for k in [0,1,2]},
                    calibration_class_counts={str(k):int(np.sum(y[cal]==k)) for k in [0,1,2]})
    model=XGBClassifier(**protocol['estimator'],objective='multi:softprob',num_class=3)
    model.fit(x[train],y[train]);calibrator=calibrate_multi(model,x[cal],y[cal])
    meta=XGBClassifier(**protocol['estimator'],objective='binary:logistic');meta.fit(xmeta[mtrain],meta_y[mtrain])
    mcalibrator=calibrate_multi(meta,xmeta[mcal],meta_y[mcal])
    p=np.zeros((len(a),3));mp=np.zeros(len(a));p[valid]=calibrated(model,calibrator,x[valid]);mp[valid]=calibrated(meta,mcalibrator,xmeta[valid])[:,1]
    side=np.where(p[:,2]>=p[:,0],1,-1);strength=np.maximum(p[:,0],p[:,2]);threshold=protocol['candidate_probability_threshold']
    # Extrapolation veto based exclusively on the TRAIN feature envelope.
    lo=x[train].quantile(.005);hi=x[train].quantile(.995)
    unusual=((x<lo)|(x>hi)).sum(axis=1).to_numpy()>6
    modes={'ema':(base_side,np.ones(len(a),dtype=bool),np.full(len(a),np.nan)),
           'xgboost':(side,(strength>=threshold)&~unusual,strength),
           'meta':(base_side,(mp>=threshold)&~unusual,mp)}
    report=dict(symbol=symbol,timeframe=tf,status='COMPLETE',horizon_bars=horizon,feature_names=list(x.columns),
        train=int(train.sum()),calibration=int(cal.sum()),meta_train=int(mtrain.sum()),meta_calibration=int(mcal.sum()),
        earliest_training_decision=int(starts[train].min()),latest_training_label=int(maturities[train].max()),latest_calibration_label=int(maturities[cal].max()),
        unknown_feature_veto=int(unusual.sum()),periods={})
    models_dir=output/'models';models_dir.mkdir(exist_ok=True)
    blob=pickle.dumps((model,calibrator,meta,mcalibrator,list(x.columns)));(models_dir/f'{symbol}_{tf}.pkl').write_bytes(blob)
    report['model_sha256']=hashlib.sha256(blob).hexdigest()
    ui_events=[]
    for period,begin,end in [('validation',millis(protocol['validation_start']),millis(protocol['validation_label_end_exclusive'])),
                              ('holdout',millis(protocol['holdout_start']),millis(protocol['source_end_exclusive']))]:
        eligible=valid&(starts>=begin)&(maturities<end)
        indices=np.flatnonzero(eligible);by_mode={};period_events={}
        for mode,(directions,accept,probabilities) in modes.items():
            chosen=episode_selection(indices,accept,horizon,starts,step);events=[]
            for i in chosen:
                r=labels[i]
                if r is None:
                    e=dict(time=int(starts[i]),side=int(directions[i]),entry=None,target=None,
                        status='MISSING',gross=None,net=None,probability=None,mfe=None,mae=None,
                        exit_time=None,regime=str(regime[i]),mode=mode,period=period)
                    events.append(e);ui_events.append(e);continue
                result=r if directions[i]==1 else resolve(fine,r['entry_time'],r['entry'],r['target'],horizon*step,-1)
                probability=float(probabilities[i]) if np.isfinite(probabilities[i]) else None
                e=dict(time=int(starts[i]),side=int(directions[i]),entry=r['entry'],target=r['target'],
                    status=result['status'],gross=result['gross'],net=result['net'],probability=probability,
                    mfe=result['mfe'],mae=result['mae'],exit_time=result['exit_time'],regime=str(regime[i]),mode=mode,period=period)
                events.append(e);ui_events.append(e)
            by_mode[mode]=summarize(events,len(indices));period_events[mode]=events
            by_mode[mode]['by_regime']={reg:summarize([r for r in events if r['regime']==reg],sum(regime[indices]==reg))
                for reg in ['ALCISTA','BAJISTA','LATERAL']}
        report['periods'][period]=dict(decisions=len(indices),models=by_mode)
        # Common calendar months, block bootstrap; exploratory, not integration evidence.
        month_keys=pd.date_range(pd.to_datetime(begin,unit='ms',utc=True),pd.to_datetime(end-1,unit='ms',utc=True),freq='MS').strftime('%Y-%m').tolist()
        monthly={}
        for mode,ev in period_events.items():
            monthly[mode]=[float(sum(r['net'] for r in ev if r['net'] is not None and pd.to_datetime(r['time'],unit='ms',utc=True).strftime('%Y-%m')==m)) for m in month_keys]
        rng=np.random.default_rng(17)
        comparisons={}
        for mode in ['xgboost','meta']:
            diff=np.array(monthly[mode])-np.array(monthly['ema']);boots=rng.choice(diff,(2000,len(diff)),replace=True).mean(axis=1) if len(diff) else []
            comparisons[mode]=dict(metric='monthly sum of scenario net returns; no capital simulation',
                mean_monthly_delta=float(diff.mean()) if len(diff) else None,
                exploratory_bootstrap_ci95=np.quantile(boots,[.025,.975]).tolist() if len(diff) else [None,None])
        report['periods'][period]['comparisons']=comparisons
    # Probability quality includes rejected decisions; never score only accepted winners.
    held=valid&(y>=0)&(starts>=millis(protocol['holdout_start']))&(maturities<millis(protocol['source_end_exclusive']))
    yy=np.eye(3)[y[held]];report['holdout_multiclass_brier']=float(np.mean(np.sum((p[held]-yy)**2,axis=1))) if held.any() else None
    mh=held&(meta_y>=0);report['holdout_meta_brier']=float(np.mean((mp[mh]-meta_y[mh])**2)) if mh.any() else None
    report['probability_bins']=[dict(low=j/10,high=(j+1)/10,count=int(mask.sum()),
        predicted=float(mp[mask].mean()) if mask.any() else None,observed=float(meta_y[mask].mean()) if mask.any() else None)
        for j in range(10) for mask in [mh&(mp>=j/10)&(mp<(j+1)/10 if j<9 else mp<=1)]]
    # Last closed historical candle, explicitly dated; not presented as a current quote.
    latest=np.flatnonzero(valid)[-1];report['last_historical_forecast']=dict(time=int(starts[latest]),
        price=float(a[latest,4]),direction='BUY' if side[latest]==1 else 'SELL',
        probability=float(strength[latest]),accepted=bool(modes['xgboost'][1][latest]),
        meta_accept_probability=float(mp[latest]),out_of_training_range=bool(unusual[latest]))
    chart=a[starts>=millis(protocol['validation_start'])][:,[6,1,2,3,4]].tolist()
    web=output/'web';web.mkdir(exist_ok=True)
    (web/f'{symbol}_{tf}.json').write_text(json.dumps(dict(report=report,candles=chart,events=ui_events),allow_nan=False,separators=(',',':')))
    return report

def run(data,output,protocol_path):
    output.mkdir(parents=True,exist_ok=True);protocol=json.loads(protocol_path.read_text())
    reports=[]
    for s in protocol['symbols']:
        for tf in protocol['timeframes']:
            print('Evaluando',s,tf,flush=True)
            try:
                manifest=json.loads((data/f'{s}_manifest.json').read_text())
                if any(x['status']=='MISMATCH' for x in manifest['native_hourly_checks']):raise ValueError('Native parity mismatch')
                if hashlib.sha256((data/f'{s}_5m.npy').read_bytes()).hexdigest()!=manifest['sha256_5m']:raise ValueError('Fine input hash mismatch')
                btc_manifest=json.loads((data/'BTC_manifest.json').read_text())
                if hashlib.sha256((data/f'BTC_{tf}.npy').read_bytes()).hexdigest()!=btc_manifest['derived'][tf]['sha256']:raise ValueError('BTC context hash mismatch')
                for interval in [tf]:
                    if hashlib.sha256((data/f'{s}_{interval}.npy').read_bytes()).hexdigest()!=manifest['derived'][interval]['sha256']:raise ValueError('Input hash mismatch')
                report=asset_run(data,output,s,tf,protocol)
            except Exception as e:
                report=dict(symbol=s,timeframe=tf,status='ERROR',reason=f'{type(e).__name__}: {e}')
            reports.append(report)
            (output/'summary.partial.json').write_text(json.dumps(reports,indent=2,allow_nan=False))
    result=dict(version=protocol['version'],generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        protocol=protocol,protocol_sha256=hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        status='HISTORICAL_EXPERIMENT_NOT_PROSPECTIVE',original_app_comparison='NOT_YET_EXECUTED',
        integration_approved=False,results=reports,
        data_manifest=json.loads((data/'manifest.json').read_text()))
    (output/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,default=Path('data'));p.add_argument('--output',type=Path,default=Path('results'))
    p.add_argument('--protocol',type=Path,default=Path('docs/protocol.json'));args=p.parse_args();run(args.data,args.output,args.protocol)
