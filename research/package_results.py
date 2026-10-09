"""Publish only reports with auditable source manifests and explicit limitations."""
import csv,hashlib,json,shutil,pickle
from pathlib import Path
import numpy as np
import pandas as pd
from research.experiment import resolve,summarize,episode_selection,millis,STEPS,features,calibrate_multi,calibrated
from xgboost import XGBClassifier

def native_comparison(root,summary):
    protocol=summary['protocol'];data=root/'data';result_root=root/'results'
    for report in summary['results']:
        if report['status']!='COMPLETE':continue
        s,tf=report['symbol'],report['timeframe'];folder=result_root/'native'/f'{s}_{tf}'
        decisions=folder/'kotlin_decisions.csv';accepted=folder/'kotlin_accepted.csv'
        if not decisions.exists() or not accepted.exists():continue
        native=pd.read_csv(decisions);allow=set(pd.read_csv(accepted)['signalCloseTime'].astype('int64'))
        a=np.load(data/f'{s}_{tf}.npy');fine=np.load(data/f'{s}_5m.npy',mmap_mode='r')
        lookup={int(row[6]):i for i,row in enumerate(a)};horizon=protocol['horizon_bars'][tf];step=STEPS[tf]
        web_path=result_root/'web'/f'{s}_{tf}.json';web=json.loads(web_path.read_text());events=[]
        xs,_,_,_=features(a)
        fit_x=[];fit_y=[];fit_t=[];native_predictions={};resolved={}
        for row in native.itertuples():
            t=int(row.signalCloseTime);i=lookup.get(t)
            if i is None or i+1>=len(a) or row.direction=='WAIT':continue
            side=-1 if 'SELL' in row.direction else 1
            z=[*xs.iloc[i].to_list(),side,float(row.confidence),float(row.adx),float(row.rsi),float(row.volumeRatio),float(row.mtfScore),float(row.comparableCases)]
            if not np.isfinite(z).all():continue
            fit_x.append(z);fit_t.append(t)
            if a[i+1,0]!=t+1:fit_y.append(-1);continue
            entry=float(a[i+1,1]);target=max(.004,float(row.atrPct)/100*float(row.entry)/entry)
            result=resolve(fine,t+1,entry,target,horizon*step,side);resolved[t]=(entry,target,result)
            fit_y.append(int(result['net']>0) if result['net'] is not None else -1)
        xx=np.array(fit_x);yy=np.array(fit_y);tt=np.array(fit_t)
        train=(yy>=0)&(tt>=millis(protocol['source_from']))&(tt+horizon*step<millis(protocol['train_label_end_exclusive']))
        cal=(yy>=0)&(tt>=millis(protocol['calibration_start']))&(tt+horizon*step<millis(protocol['calibration_label_end_exclusive']))
        filter_note=dict(scope='EXPLORATORY_ORIGINAL_SIGNAL_FILTER',train=int(train.sum()),calibration=int(cal.sum()))
        if train.sum()>=100 and cal.sum()>=100 and len(np.unique(yy[train]))==2 and len(np.unique(yy[cal]))==2:
            model=XGBClassifier(**protocol['estimator'],objective='binary:logistic');model.fit(xx[train],yy[train])
            calibrator=calibrate_multi(model,xx[cal],yy[cal]);probs=calibrated(model,calibrator,xx)[:,1]
            native_predictions=dict(zip(tt,probs))
            filter_note.update(earliest_training_decision=int(tt[train].min()),latest_training_label=int((tt[train]+horizon*step).max()),
                latest_calibration_label=int((tt[cal]+horizon*step).max()),threshold=.60)
            blob=pickle.dumps((model,calibrator));(result_root/'models'/f'{s}_{tf}_original_filter.pkl').write_bytes(blob)
            filter_note['model_sha256']=hashlib.sha256(blob).hexdigest()
        else:filter_note['reason']='Insufficient training/calibration samples or classes'
        report['original_filter']=filter_note
        for period,begin,end in [('validation',millis(protocol['validation_start']),millis(protocol['validation_label_end_exclusive'])),('holdout',millis(protocol['holdout_start']),millis(protocol['source_end_exclusive']))]:
            rows=native[(native.signalCloseTime>=begin)&(native.signalCloseTime+horizon*step<end)]
            for mode in ['original']+(['original_meta'] if native_predictions else []):
                available=-1;period_events=[]
                for row in rows.itertuples():
                    t=int(row.signalCloseTime);i=lookup.get(t);prob=native_predictions.get(t)
                    if i is None or t<available or t not in allow:continue
                    if mode=='original_meta' and (prob is None or prob<.60):continue
                    available=t+(horizon+1)*step
                    side=-1 if 'SELL' in row.direction else 1
                    if t in resolved:entry,target,result=resolved[t]
                    else:result=dict(status='MISSING',gross=None,net=None,mfe=None,mae=None,exit_time=None);entry=None;target=None
                    event=dict(time=t,side=side,entry=entry,target=target,probability=float(prob) if mode=='original_meta' else None,
                        status=result['status'],gross=result['gross'],net=result['net'],mfe=result['mfe'],mae=result['mae'],exit_time=result['exit_time'],
                        regime=str(row.regime),mode=mode,period=period)
                    period_events.append(event);events.append(event)
                report['periods'][period]['models'][mode]=summarize(period_events,len(rows))
            report['periods'][period]['models']['original']['note']='Kotlin research snapshot; ATR computed by Kotlin, candidate ATR by Python. Common barrier rule but indicator implementations differ. No integration evidence.'
        web['report']=report;web['events']=[e for e in web['events'] if e['mode'] not in ['original','original_meta']]+events
        web_path.write_text(json.dumps(web,allow_nan=False,separators=(',',':')))
    summary['original_app_comparison']='KOTLIN_RESEARCH_SNAPSHOT_COMMON_OUTCOME_RULE_NOT_PHYSICAL_APK'

def run(root):
    results=root/'results';summary=json.loads((results/'summary.json').read_text())
    native_comparison(root,summary)
    complete=[r for r in summary['results'] if r['status']=='COMPLETE']
    improvement=[]
    for r in complete:
        models=r['periods']['holdout']['models'];base=models.get('original',models['ema'])
        for mode in ['xgboost','meta']+(['original_meta'] if 'original_meta' in models else []):
            m=models[mode]
            improvement.append(dict(symbol=r['symbol'],timeframe=r['timeframe'],model=mode,
                signals=m['signals'],precision=m['barrier_precision'],baseline_precision=base['barrier_precision'],
                mean_net=m['mean_net'],baseline_mean_net=base['mean_net']))
    summary['integration_approved']=False
    summary['conclusion']=f'{len(complete)} combinaciones históricas evaluadas. Resultados exploratorios; no hay evidencia de mejora general ni 100 % de fiabilidad. Integración desactivada.'
    summary['candidate_comparisons']=improvement
    summary['not_evaluable_models']=[dict(symbol=r['symbol'],timeframe=r['timeframe'],model='original_meta',reason=r['original_filter']['reason'],train=r['original_filter']['train'],calibration=r['original_filter']['calibration']) for r in complete if r.get('original_filter',{}).get('reason')]
    (results/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False))
    dist=root/'dist'/'data';dist.mkdir(parents=True,exist_ok=True)
    for path in (results/'web').glob('*.json'):shutil.copyfile(path,dist/path.name)
    shutil.copyfile(results/'summary.json',dist/'summary.json');shutil.copyfile(root/'docs'/'protocol.json',dist/'protocol.json')
    # Offline fallback also works when opening index.html directly in Windows.
    bundle={p.stem:json.loads(p.read_text()) for p in dist.glob('*.json') if p.stem not in ['summary','protocol']}
    (root/'dist'/'offline-data.js').write_text('window.CRIPTO_OFFLINE='+json.dumps(dict(summary=summary,assets=bundle),allow_nan=False,separators=(',',':'))+';\n')
    rows=[]
    for r in complete:
        for period,p in r['periods'].items():
            for mode,m in p['models'].items():
                rows.append(dict(symbol=r['symbol'],timeframe=r['timeframe'],period=period,model=mode,**{k:m[k] for k in ['signals','valid','HIT','FAIL','NEUTRAL','AMBIGUOUS','MISSING','barrier_precision','positive_net_rate','mean_net','max_drawdown']}))
    with (results/'comparison.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['symbol']);w.writeheader();w.writerows(rows)
    shutil.copyfile(results/'comparison.csv',dist/'comparison.csv')
    def show(v):return 'sin dato' if v is None else f'{100*v:.3f} %'
    highlights=[]
    for symbol,tf,mode in [('ADA','1h','xgboost'),('SOL','1h','original_meta'),('ETH','4h','meta')]:
        rr=next((r for r in complete if r['symbol']==symbol and r['timeframe']==tf),None)
        if rr and mode in rr['periods']['holdout']['models']:
            mm=rr['periods']['holdout']['models'][mode]
            highlights.append(f'- {symbol} {tf} · {mode}: {mm["signals"]} señales, {show(mm["barrier_precision"])} de precisión de barrera y {show(mm["mean_net"])} de media neta por escenario. Revisar tamaño de muestra, neutras y costes antes de sacar conclusiones.')
    text=['# Resultados del laboratorio independiente','',
      'Estado: prueba histórica. Integración en CriptoAnálisis Multi desactivada.',
      'No se ha demostrado un 100 % de aciertos ni una mejora universal.','',
      '## Conclusiones',
      *highlights,
      '- Muchos candidatos no emitieron señales con el umbral fijado. Se conserva el rechazo; no se baja el umbral para mejorar artificialmente la cobertura.',
      f'- {len(complete)} combinaciones principales evaluadas y {len(summary["not_evaluable_models"])} variantes adicionales de filtro no evaluables: ver sus cantidades y motivos al final.',
      '- No se integra ningún cambio en la app actual.','',
      f"Velas de 2022 sólo inicializan indicadores. El modelo aprende únicamente en 2023; enero–junio 2024 calibra y julio–diciembre 2024 valida. Revisión histórica desde 2025 hasta {summary['protocol']['source_end_exclusive']} (exclusivo); el historial ya observado no es una confirmación prospectiva independiente.",
      'Modelos congelados, umbral 60 %, escenarios simétricos con coste total 0,20 %. No son operaciones spot ejecutadas.',
      'La precisión de barrera excluye neutras y ambiguas; la tasa de escenarios netos positivos incluye neutras. No debe confundirse ninguna con certeza futura.','',
      '| Moneda | Intervalo | Motor | Señales | Aciertos | Fallos | Neutras | No evaluables | Precisión | Media neta |',
      '|---|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        if r['period']!='holdout':continue
        def pct(v):return '—' if v is None else f'{100*v:.2f} %'
        text.append(f"| {r['symbol']} | {r['timeframe']} | {r['model']} | {r['signals']} | {r['HIT']} | {r['FAIL']} | {r['NEUTRAL']} | {r['AMBIGUOUS']+r['MISSING']} | {pct(r['barrier_precision'])} | {pct(r['mean_net'])} |")
    text+=['','## Límites de la comparación',
      '- La referencia EMA no es el motor Android. La comparación Kotlin adicional corresponde al snapshot de investigación identificado por hashes, con su excepción auditada para datos futuros ausentes.',
      '- Las implementaciones de ATR/indicadores Python y Kotlin no son idénticas. La comparación de señales es exploratoria: exige paridad adicional antes de integrar.',
      '- No hay noticias históricas, funding, profundidad de libro ni simulación de cartera spot. La tasa de acierto por sí sola no demuestra rentabilidad.',
      '- El examen histórico no sustituye un registro prospectivo. Las fechas previas ya pudieron influir indirectamente en decisiones de investigación anteriores.',
      '- Se repitió el examen tras corregir la falta de calentamiento de indicadores (2022). No se cambiaron umbrales ni parámetros según los resultados, pero el examen ya observado no es un registro prospectivo independiente.',
      '- No se ha probado físicamente la APK ni el navegador/PWA del móvil.','',
      '## Combinaciones no evaluables']
    text += [f"- {r['symbol']} {r['timeframe']}: {r.get('reason','')}" for r in summary['results'] if r['status']!='COMPLETE'] or ['Ninguna combinación excluida por completo. Los casos ambiguos y ausentes figuran en la tabla.']
    text+=['','## Modelos adicionales no evaluables']
    text += [f"- {r['symbol']} {r['timeframe']} · filtro sobre motor Kotlin: aprendizaje {r['train']}, calibración {r['calibration']}. {r['reason']}" for r in summary['not_evaluable_models']] or ['Ninguno.']
    (root/'docs'/'RESULTADOS.md').write_text('\n'.join(text)+'\n')
    return summary

if __name__=='__main__':run(Path(__file__).resolve().parents[1])
