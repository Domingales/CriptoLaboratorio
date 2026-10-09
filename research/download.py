"""Download official closed Binance candles; cache ZIPs and verify CHECKSUMs."""
import argparse, concurrent.futures, datetime as dt, hashlib, io, json, time
from pathlib import Path
import urllib.request, urllib.error, zipfile
import numpy as np
import pandas as pd

SYMBOLS = ['BTC', 'ETH', 'ADA', 'SOL', 'XRP']
START = '2022-01'  # Indicator warmup only. Model labels begin in 2023.
END = '2026-09'
STEP = 300_000

def get(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404 or attempt == 2: raise
        except (OSError, TimeoutError):
            if attempt == 2: raise
        time.sleep(attempt + 1)

def month_keys(start, end):
    return [p.strftime('%Y-%m') for p in pd.period_range(start, end, freq='M')]

def archive(root, symbol, interval, month):
    name = f'{symbol}USDT-{interval}-{month}.zip'
    path = root / 'archives' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    url = f'https://data.binance.vision/data/spot/monthly/klines/{symbol}USDT/{interval}/{name}'
    checksum_path = path.with_suffix('.zip.CHECKSUM')
    if not path.exists():
        blob = get(url)
        checksum = get(url+'.CHECKSUM').decode().split()[0]
        if hashlib.sha256(blob).hexdigest() != checksum: raise ValueError('Archive checksum mismatch')
        path.write_bytes(blob); checksum_path.write_text(checksum)
    blob = path.read_bytes()
    if not checksum_path.exists(): checksum_path.write_text(get(url+'.CHECKSUM').decode().split()[0])
    sha = hashlib.sha256(blob).hexdigest()
    if sha != checksum_path.read_text().strip(): raise ValueError('Cached checksum mismatch')
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        frame = pd.read_csv(z.open(z.namelist()[0]), header=None, usecols=range(7))
    a = frame.to_numpy(dtype=float)
    for col in (0,6): a[:,col] = np.where(a[:,col] > 1e14, a[:,col]//1000, a[:,col])
    step = {'5m':300000,'1h':3600000}[interval]
    invalid_time=(a[:,0] % step != 0)|(a[:,6] != a[:,0]+step-1)
    excluded=a[invalid_time].tolist()
    a=a[~invalid_time]
    if (not np.isfinite(a).all() or np.any(a[:,1:5] <= 0) or
        np.any(a[:,5] < 0) or np.any(a[:,3] > np.minimum(a[:,1],a[:,4])) or
        np.any(a[:,2] < np.maximum(a[:,1],a[:,4])) or np.any(np.diff(a[:,0]) <= 0)):
        raise ValueError('Invalid OHLCV '+name)
    return a, dict(url=url,sha256=sha,count=len(a),first_open=int(a[0,0]),last_close=int(a[-1,6]),
                  excluded_nonstandard_time=len(excluded),excluded_examples=excluded[:5])

def aggregate(a, step):
    f = pd.DataFrame(a,columns=['time','open','high','low','close','volume','end'])
    f['bucket'] = (f.time // step * step).astype('int64')
    grouped = f.groupby('bucket',sort=True)
    out = grouped.agg(open=('open','first'),high=('high','max'),low=('low','min'),
                      close=('close','last'),volume=('volume','sum'),n=('time','size'),
                      first=('time','first'),last=('end','last'))
    expected = step//STEP
    good = (out.n==expected)&(out['first']==out.index)&(out['last']==out.index+step-1)
    out = out[good]
    return np.column_stack([out.index,out.open,out.high,out.low,out.close,out.volume,out.index+step-1]).astype(float)

def run(root, symbols=SYMBOLS, start=START, end=END):
    root.mkdir(parents=True,exist_ok=True)
    jobs = [(s,m) for s in symbols for m in month_keys(start,end)]
    results = {s:[] for s in symbols}; issues=[]
    def task(job):
        s,m=job
        try: return s,m,archive(root,s,'5m',m),None
        except Exception as e: return s,m,None,f'{type(e).__name__}: {e}'
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for i,(s,m,result,error) in enumerate(pool.map(task,jobs),1):
            if error: issues.append(dict(symbol=s,month=m,error=error))
            else: results[s].append((m,*result))
            if i%15==0: print(f'Archivos comprobados {i}/{len(jobs)}',flush=True)
    manifests=[]
    for s,parts in results.items():
        if not parts: continue
        a=np.concatenate([x[1] for x in sorted(parts)])
        if np.any(np.diff(a[:,0])<=0): raise ValueError('Duplicate/nonmonotonic times')
        np.save(root/f'{s}_5m.npy',a)
        derived={}
        for tf,step in [('15m',900000),('1h',3600000),('4h',14400000),('1d',86400000)]:
            b=aggregate(a,step); np.save(root/f'{s}_{tf}.npy',b)
            derived[tf]=dict(count=len(b),sha256=hashlib.sha256((root/f'{s}_{tf}.npy').read_bytes()).hexdigest(),
                            gaps=int(np.sum(np.diff(b[:,0])!=step)))
        # Independently compare native 1h archives at start and end of each calendar year.
        checks=[]
        b=np.load(root/f'{s}_1h.npy')
        def check_native(m):
            try:
                native,source=archive(root,s,'1h',m)
                mask=(b[:,0]>=native[0,0])&(b[:,0]<=native[-1,0]); d=b[mask]
                match=len(d)==len(native) and np.allclose(d,native,rtol=1e-10,atol=1e-7)
                return dict(month=m,status='MATCH' if match else 'MISMATCH',source=source)
            except Exception as e:return dict(month=m,status='UNAVAILABLE',error=str(e))
        check_months=sorted({x[0] for x in parts if x[0].endswith(('-01','-09','-12'))})
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:checks=list(pool.map(check_native,check_months))
        manifest=dict(symbol=s,source='Binance official spot monthly ZIP + SHA256 CHECKSUM',
            from_utc=pd.to_datetime(a[0,0],unit='ms',utc=True).isoformat(),
            through_utc=pd.to_datetime(a[-1,6],unit='ms',utc=True).isoformat(),count_5m=len(a),
            gaps_5m=int(np.sum(np.diff(a[:,0])!=STEP)),sha256_5m=hashlib.sha256((root/f'{s}_5m.npy').read_bytes()).hexdigest(),archives=[x[2] for x in sorted(parts)],
            derived=derived,native_hourly_checks=checks,issues=[x for x in issues if x['symbol']==s])
        (root/f'{s}_manifest.json').write_text(json.dumps(manifest,indent=2)); manifests.append(manifest)
        print(f'{s}: {len(a)} velas 5m; {manifest["gaps_5m"]} discontinuidades',flush=True)
    (root/'manifest.json').write_text(json.dumps(dict(start=start,end=end,assets=manifests,issues=issues),indent=2))
    return manifests

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--data',type=Path,default=Path('data'))
    p.add_argument('--symbols',nargs='+',default=SYMBOLS); p.add_argument('--start',default=START);p.add_argument('--end',default=END)
    args=p.parse_args();run(args.data,args.symbols,args.start,args.end)
