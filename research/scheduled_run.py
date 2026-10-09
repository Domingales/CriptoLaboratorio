"""Bound scheduled runs to completed official archive months, never tune models."""
import argparse, datetime as dt, hashlib, json, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def prepare(root=ROOT, today=None):
    today = today or dt.datetime.now(dt.timezone.utc).date()
    end = today.replace(day=1)
    last = end - dt.timedelta(days=1)
    path = root/'docs/protocol.json'
    original = path.read_bytes(); protocol = json.loads(original)
    protocol['source_end_exclusive'] = end.isoformat()+'T00:00:00Z'
    (root/'docs/scheduled-base-protocol.json').write_bytes(original)
    path.write_text(json.dumps(protocol,indent=2)+'\n')
    config = {'registered_at': dt.datetime.now(dt.timezone.utc).isoformat(),
              'download_end': last.strftime('%Y-%m'), 'base_protocol_sha256':hashlib.sha256(original).hexdigest(),
              'run_id':os.environ.get('GITHUB_RUN_ID'), 'commit':os.environ.get('GITHUB_SHA'),
              'schedule':'Sundays 03:17 UTC; GitHub may delay scheduled runs',
              'scope':'Repeat frozen historical models and fixed exploratory filters. No parameter search or production integration.',
              'new_data':'Only completed monthly official archives; current incomplete month excluded.',
              'integration':False}
    (root/'docs/scheduled-run.json').write_text(json.dumps(config,indent=2)+'\n')
    print(json.dumps(config))
    return config

def download(root=ROOT):
    from research.download import run
    config=json.loads((root/'docs/scheduled-run.json').read_text())
    assets=run(root/'data',['BTC','ETH','ADA','SOL','XRP'],'2022-01',config['download_end'])
    if len(assets)!=5 or any(a['issues'] for a in assets):
        raise RuntimeError('Missing monthly archives: do not accept partial scheduled results')
    if any(c['status']!='MATCH' for a in assets for c in a['native_hourly_checks']):
        raise RuntimeError('Independent hourly source check unavailable or mismatched')

def verify(root=ROOT):
    summary=json.loads((root/'results/summary.json').read_text())
    statuses=[r['status'] for r in summary['results']]
    if len(statuses)!=15 or any(s!='COMPLETE' for s in statuses):
        raise RuntimeError('Not all 15 combinations completed; inspect partial artifacts')
    config=json.loads((root/'docs/scheduled-run.json').read_text())
    # Training and calibration cutoffs are still the registered historical cutoffs.
    original=json.loads((root/'docs/scheduled-base-protocol.json').read_text())
    expected=dict(original,source_end_exclusive=summary['protocol']['source_end_exclusive'])
    assert summary['protocol']==expected
    assert not config['integration'] and not summary['integration_approved']
    native=json.loads((root/'results/native/runs.json').read_text())
    assert len(native)==15 and all(r['exit']==0 for r in native)
    print('PASS: 15 complete combinations, only source end extended; integration disabled')

def summary(root=ROOT):
    path=root/'results/summary.json'
    lines=['## CriptoLaboratorio — ejecución automática','',
           'Modelos históricos congelados; filtros exploratorios. Sin integración en producción.']
    if path.exists():
        s=json.loads(path.read_text())
        lines += ['',f"Corte de datos: {s['protocol']['source_end_exclusive']} (exclusivo)", '',
                  '| Moneda | Intervalo | Estado |','|---|---|---|']
        lines += [f"| {r['symbol']} | {r['timeframe']} | {r['status']} |" for r in s['results']]
    else: lines += ['','No se generó el informe: revisar los pasos fallidos y los artefactos parciales.']
    text='\n'.join(lines)+'\n'
    (root/'docs/AUTOMATIC_RUN.md').write_text(text)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as file:file.write(text)
    print(text)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','download','verify','summary'])
    globals()[p.parse_args().action]()
