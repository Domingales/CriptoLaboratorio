"""Compile the frozen Kotlin research adapter without an Android SDK.

Adapter source is preserved verbatim, including its documented future-gap fix.
This validates the mathematical domain, not APK/background services.
"""
import argparse, concurrent.futures, hashlib, json, os, subprocess
from pathlib import Path
import urllib.request
import numpy as np

ARTIFACTS=[('org.jetbrains.kotlin','kotlin-compiler-embeddable','2.0.21'),
 ('org.jetbrains.kotlin','kotlin-stdlib','2.0.21'),('org.jetbrains.kotlin','kotlin-script-runtime','2.0.21'),
 ('org.jetbrains.kotlin','kotlin-reflect','1.6.10'),('org.jetbrains.kotlin','kotlin-daemon-embeddable','2.0.21'),
 ('org.jetbrains.intellij.deps','trove4j','1.0.20200330'),
 ('org.jetbrains.kotlinx','kotlinx-coroutines-core-jvm','1.6.4'),('org.jetbrains','annotations','13.0')]

def setup(root):
    deps=root/'private'/'jvm';deps.mkdir(parents=True,exist_ok=True)
    def fetch(item):
        group,artifact,version=item;name=f'{artifact}-{version}.jar';path=deps/name
        if not path.exists():
            url=f'https://repo.maven.apache.org/maven2/{group.replace(".","/")}/{artifact}/{version}/{name}'
            with urllib.request.urlopen(url,timeout=120) as r:path.write_bytes(r.read())
        return path
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(fetch,ARTIFACTS))
    jars=[x for x in deps.glob('*.jar') if x.name!='reference.jar'];cp=os.pathsep.join(str(x) for x in jars)
    sources=sorted((root/'native').glob('*.kt'));jar=deps/'reference.jar'
    subprocess.run(['java','-Xmx2g','-cp',cp,'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler','-no-stdlib','-no-reflect',
        '-classpath',cp,'-jvm-target','17','-d',str(jar),*[str(x) for x in sources]],check=True)
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    (root/'docs'/'native-source-hashes.json').write_text(json.dumps(dict(
        repository='Domingales/Cripto-Analisis-Multi---MOTOR-PREDICTIVO',
        commit='6cd24603a15b49234a6de7c6c34efc680d25e0d7',
        adapter='ExpandedResearchEngine: cache optimization and previously audited future-availability cooldown repair',
        files=hashes),indent=2))
    return cp+os.pathsep+str(jar)

def run(root,data,output,symbols,timeframes):
    cp=setup(root);folder=root/'private'/'native-data';folder.mkdir(exist_ok=True)
    for s in symbols:
        for tf in ['5m','15m','1h','4h','1d']:
            a=np.load(data/f'{s}_{tf}.npy');p=folder/f'{s}USDT_{tf}.csv'
            np.savetxt(p,a,delimiter=',',header='openTime,open,high,low,close,volume,closeTime',comments='',
                fmt=['%.0f','%.17g','%.17g','%.17g','%.17g','%.17g','%.0f'])
    def task(job):
        s,tf=job;out=output/f'{s}_{tf}';out.mkdir(parents=True,exist_ok=True)
        env=os.environ.copy();env.update(EXPANDED_DATA_DIR=str(folder),EXPANDED_SYMBOL=s,EXPANDED_TF=tf,EXPANDED_KOTLIN_DIR=str(out))
        with (out/'run.log').open('w') as f:
            r=subprocess.run(['java','-Xmx2g','-cp',cp,'com.domingales.criptoanalisis.multi.evaluation.NativeRunnerKt'],env=env,stdout=f,stderr=subprocess.STDOUT)
        print('Native',s,tf,'exit',r.returncode,flush=True);return dict(symbol=s,timeframe=tf,exit=r.returncode)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(task,[(s,tf) for s in symbols for tf in timeframes]))
    (output/'runs.json').write_text(json.dumps(results,indent=2));return results

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--setup-only',action='store_true');args=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    if args.setup_only:setup(root)
    else:run(root,root/'data',root/'results'/'native',['BTC','ETH','ADA','SOL','XRP'],['1h','4h','1d'])
