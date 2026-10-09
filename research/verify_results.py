"""Fail if published results violate the frozen temporal or accounting protocol."""
import hashlib,json
from pathlib import Path
from research.experiment import millis,STEPS

def run(root):
    s=json.loads((root/'results'/'summary.json').read_text());p=s['protocol']
    assert s['protocol_sha256']==hashlib.sha256((root/'docs'/'protocol.json').read_bytes()).hexdigest()
    assert not s['integration_approved']
    assert len(s['results'])==len(p['symbols'])*len(p['timeframes'])
    events=0;complete=0;excluded=[]
    for r in s['results']:
        if r['status']!='COMPLETE':
            assert r.get('reason');excluded.append(r['symbol']+' '+r['timeframe']);continue
        complete+=1
        assert r['earliest_training_decision']>=millis(p['source_from'])
        assert r['latest_training_label']<millis(p['train_label_end_exclusive'])
        assert r['latest_calibration_label']<millis(p['calibration_label_end_exclusive'])
        if 'latest_training_label' in r.get('original_filter',{}):
            assert r['original_filter']['earliest_training_decision']>=millis(p['source_from'])
            assert r['original_filter']['latest_training_label']<millis(p['train_label_end_exclusive'])
            assert r['original_filter']['latest_calibration_label']<millis(p['calibration_label_end_exclusive'])
        web=json.loads((root/'dist'/'data'/f'{r["symbol"]}_{r["timeframe"]}.json').read_text())
        assert web['report']==r
        for period,pp in r['periods'].items():
            for mode,m in pp['models'].items():
                ev=[e for e in web['events'] if e['mode']==mode and e['period']==period];events+=len(ev)
                assert len(ev)==m['signals']
                assert sum(m[k] for k in ['HIT','FAIL','NEUTRAL','AMBIGUOUS','MISSING'])==m['signals']
                assert m['valid']==m['HIT']+m['FAIL']+m['NEUTRAL']
                assert len({e['time'] for e in ev})==len(ev)
                for a,b in zip(ev,ev[1:]):assert b['time']-a['time']>=(r['horizon_bars']+1)*STEPS[r['timeframe']]
                for e in ev:
                    if e['net'] is not None:
                        assert abs(e['net']-(e['gross']-.002))<1e-10
                        assert e['exit_time']>e['time']
                    if e['status'] in ['AMBIGUOUS','MISSING']:assert e['net'] is None
                    if e['probability'] is not None:assert 0<=e['probability']<=1
    out=dict(status='PASS',completed=complete,not_evaluable=excluded,published_events=events,
             temporal_boundaries='PASS',non_overlapping_episodes='PASS',accounting='PASS',integration='DISABLED')
    (root/'docs'/'verification.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
    return out

if __name__=='__main__':run(Path(__file__).resolve().parents[1])
