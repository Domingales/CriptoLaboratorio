'use strict';
const $=id=>document.getElementById(id),labels={ema:'Referencia EMA20/50',xgboost:'XGBoost · dirección',meta:'EMA + filtro aprendido',original:'Motor Kotlin · investigación',original_meta:'Motor Kotlin + filtro aprendido'};
let summary=null,payload=null,cache=new Map(),generation=0,installPrompt=null;
const pct=v=>v==null?'—':(100*v).toFixed(2)+' %';
const date=t=>new Date(t).toISOString().replace('T',' ').slice(0,16);
const safe=t=>String(t).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const chosenEvents=()=>payload?payload.events.filter(r=>r.mode===$('mode').value&&r.period===$('period').value):[];
function download(name,content,mime){const u=URL.createObjectURL(new Blob([content],{type:mime})),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}
async function change(){const mine=++generation,key=$('asset').value+'_'+$('timeframe').value;$('error').hidden=true;
 try{if(!cache.has(key)){if(location.protocol==='file:'&&window.CRIPTO_OFFLINE?.assets[key])cache.set(key,window.CRIPTO_OFFLINE.assets[key]);else{const r=await fetch('data/'+key+'.json');if(!r.ok)throw Error('No hay resultados evaluables para esta combinación.');cache.set(key,await r.json());}}if(mine!==generation)return;payload=cache.get(key);render();}
 catch(e){if(mine!==generation)return;const report=summary?.results.find(r=>r.symbol===$('asset').value&&r.timeframe===$('timeframe').value);$('error').textContent=report?.status==='NOT_EVALUABLE'?'No evaluable: '+report.reason+' · Aprendizaje: '+report.training_samples+' · Calibración: '+report.calibration_samples+'.':e.message;$('error').hidden=false;payload=null;$('forecast-panel').hidden=true;$('metrics').replaceChildren();$('comparison').replaceChildren();$('events').replaceChildren();$('diagnostics').replaceChildren();draw();}
}
function render(){const report=payload.report,period=report.periods[$('period').value],mode=$('mode').value,m=period.models[mode];
 $('forecast-panel').hidden=false;
 const forecast=report.last_historical_forecast;
 $('forecast-title').textContent=(forecast.accepted?(forecast.direction==='BUY'?'Posible compra':'Posible venta'):'No operar')+' · '+report.symbol+' · '+date(forecast.time)+' UTC';
 $('forecast-detail').textContent='Precio al cierre: '+forecast.price.toPrecision(7)+' USDT. Estimación del escenario direccional: '+pct(forecast.probability)+'. '+(forecast.out_of_training_range?'Situación alejada del rango de aprendizaje. ':'')+'Es una predicción histórica; no es una recomendación para operar ahora.';
 $('error').hidden=true;
 if(!m){$('error').textContent='Esta comparación todavía no dispone de resultados comprobados.';$('error').hidden=false;$('metrics').replaceChildren();$('events').replaceChildren();$('comparison').replaceChildren();$('diagnostics').replaceChildren();draw();return;}
 const sampleNote=m.valid<30?'Muestra pequeña · '+m.valid+' casos. ':'';
 const cards=[['Precisión de barrera',pct(m.barrier_precision),sampleNote+'IC 95 %: '+m.precision_ci95.map(pct).join(' – ')],['Señales evaluables',m.valid.toLocaleString('es-ES'),m.signals+' registradas · '+(m.AMBIGUOUS+m.MISSING)+' no evaluables'],['Resultado neto medio',pct(m.mean_net),'Por escenario · costes totales 0,20 %'],['Escenarios netos positivos',pct(m.positive_net_rate),'Incluye neutras · no son operaciones reales']];
 $('metrics').innerHTML=cards.map(([l,v,n])=>`<article class="metric"><span class="label">${safe(l)}</span><strong>${safe(v)}</strong><small>${safe(n)}</small></article>`).join('');
 $('comparison').innerHTML=Object.entries(period.models).map(([key,v])=>`<tr class="${key===mode?'selected':''}"><td>${safe(labels[key]||key)}</td><td>${v.signals}</td><td>${v.HIT} / ${v.FAIL}</td><td>${v.NEUTRAL}</td><td>${v.AMBIGUOUS+v.MISSING}</td><td>${pct(v.barrier_precision)}</td><td class="${v.mean_net>0?'green':'red'}">${pct(v.mean_net)}</td><td>${pct(v.max_drawdown)}</td></tr>`).join('');
 const manifest=summary.data_manifest.assets.find(a=>a.symbol===report.symbol),checks=manifest.native_hourly_checks.filter(r=>r.status==='MATCH').length;
 const diag=[['Aprendizaje / calibración',report.train+' / '+report.calibration+' casos'],['Examen · decisiones disponibles',period.decisions.toLocaleString('es-ES')],['Cobertura del motor',pct(m.coverage)],['Resolución del resultado','Velas oficiales 5m'],['Última vela publicada',date(Date.parse(manifest.through_utc))+' UTC'],['Contrastes con velas 1h nativas',checks+' correctos / '+manifest.native_hourly_checks.length],['Discontinuidades en datos 5m',manifest.gaps_5m],['Probabilidades · Brier del filtro',report.holdout_meta_brier?.toFixed(4)??'—'],['Integración en nuestra app','DESACTIVADA']];
 $('diagnostics').innerHTML=diag.map(([k,v])=>`<div><dt>${safe(k)}</dt><dd>${safe(v)}</dd></div>`).join('');
 const events=chosenEvents(),rows=events.slice(-100).reverse();
 $('events').innerHTML=rows.map(r=>`<tr><td>${date(r.time)}</td><td class="${r.side===1?'green':'red'}">${r.side===1?'COMPRA':'VENTA'}</td><td>${r.entry==null?'—':r.entry.toPrecision(7)}</td><td>${pct(r.probability)}</td><td>${safe({HIT:'ACIERTO',FAIL:'FALLO',NEUTRAL:'NEUTRAL',AMBIGUOUS:'AMBIGUA',MISSING:'DATOS AUSENTES'}[r.status]||r.status)}</td><td class="${r.net>0?'green':'red'}">${pct(r.net)}</td><td>${safe(r.regime)}</td></tr>`).join('');
 $('events-note').textContent='Se muestran las últimas '+rows.length+' de '+events.length+' señales. El CSV contiene el registro completo del motor y periodo seleccionados.';
 $('chart-title').textContent=report.symbol+' / USDT · '+$('timeframe').selectedOptions[0].text;draw();
}
function draw(){const canvas=$('chart'),width=canvas.clientWidth||700,height=330,dpr=window.devicePixelRatio||1;canvas.width=width*dpr;canvas.height=height*dpr;const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);ctx.clearRect(0,0,width,height);if(!payload)return;
 const begin=$('period').value==='holdout'?Date.UTC(2025,0,1):Date.UTC(2024,6,1),end=$('period').value==='holdout'?Infinity:Date.UTC(2025,0,1);
 const full=payload.candles.filter(c=>c[0]>=begin&&c[0]<end),n=Math.min(160,full.length),offset=Math.round(Math.max(0,full.length-n)*Number($('scroll').value)/100),a=full.slice(offset,offset+n);if(!a.length)return;
 const left=12,right=75,top=15,bottom=30,plotW=width-left-right,plotH=height-top-bottom;
 let low=Math.min(...a.map(c=>c[3])),high=Math.max(...a.map(c=>c[2])),pad=(high-low)*.1||high*.01;low-=pad;high+=pad;
 const y=p=>top+(high-p)/(high-low)*plotH,dx=plotW/a.length,x=i=>left+(i+.5)*dx;
 ctx.font='10px system-ui';ctx.textAlign='left';for(let j=0;j<=4;j++){let price=low+(high-low)*j/4,yy=y(price);ctx.strokeStyle='#242b36';ctx.beginPath();ctx.moveTo(left,yy);ctx.lineTo(width-right,yy);ctx.stroke();ctx.fillStyle='#8995a6';ctx.fillText(price.toPrecision(5),width-right+9,yy+3);}
 a.forEach((c,i)=>{ctx.strokeStyle=c[4]>=c[1]?'#68d9b0':'#fa8890';ctx.fillStyle=ctx.strokeStyle;ctx.beginPath();ctx.moveTo(x(i),y(c[2]));ctx.lineTo(x(i),y(c[3]));ctx.stroke();ctx.fillRect(x(i)-Math.max(1,dx*.26),Math.min(y(c[1]),y(c[4])),Math.max(1,dx*.52),Math.max(1,Math.abs(y(c[1])-y(c[4]))));});
 const map=new Map(a.map((c,i)=>[c[0],i]));chosenEvents().forEach(e=>{const i=map.get(e.time);if(i===undefined)return;const yy=e.side===1?y(a[i][3])+9:y(a[i][2])-9;ctx.fillStyle=e.side===1?'#68d9b0':'#fa8890';ctx.beginPath();ctx.moveTo(x(i),yy+(e.side===1?-4:4));ctx.lineTo(x(i)-4,yy+(e.side===1?4:-4));ctx.lineTo(x(i)+4,yy+(e.side===1?4:-4));ctx.closePath();ctx.fill();});
 ctx.fillStyle='#8995a6';ctx.fillText(date(a[0][0]).slice(0,10),left,height-7);ctx.textAlign='right';ctx.fillText(date(a[a.length-1][0]).slice(0,10),width-right,height-7);
 $('chart-range').textContent=date(a[0][0])+' → '+date(a[a.length-1][0])+' UTC';
}
for(const id of ['asset','timeframe'])$(id).addEventListener('change',change);
for(const id of ['mode','period'])$(id).addEventListener('change',()=>{if(payload)render();});
$('scroll').addEventListener('input',draw);window.addEventListener('resize',draw);
$('export-summary').addEventListener('click',()=>{if(summary)download('CriptoLaboratorio_informe.json',JSON.stringify(summary,null,2),'application/json');});
$('export-csv').addEventListener('click',()=>{const ev=chosenEvents();if(!ev.length)return;const keys=['time','side','entry','probability','status','gross','net','target','mfe','mae','exit_time','regime','mode','period'];const csv=[keys.join(','),...ev.map(e=>keys.map(k=>JSON.stringify(e[k]??'')).join(','))].join('\n');download('CriptoLaboratorio_'+$('asset').value+'_'+$('timeframe').value+'_'+$('mode').value+'.csv',csv,'text/csv;charset=utf-8');});
window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();installPrompt=e;$('install').hidden=false;});$('install').addEventListener('click',async()=>{if(installPrompt){await installPrompt.prompt();installPrompt=null;$('install').hidden=true;}});
(async()=>{try{if(location.protocol==='file:'&&window.CRIPTO_OFFLINE)summary=window.CRIPTO_OFFLINE.summary;else{const r=await fetch('data/summary.json');if(!r.ok)throw Error('No se ha generado el informe. Ejecuta el experimento antes de publicar.');summary=await r.json();}const completed=summary.results.filter(r=>r.status==='COMPLETE').length;$('experiment-status').textContent=completed+' / '+summary.results.length+' combinaciones comprobadas';$('conclusion').textContent=summary.conclusion||'Resultados históricos disponibles. Integración desactivada: una mejora frente a EMA no demuestra mejora frente a nuestra app.';await change();}catch(e){$('experiment-status').textContent='Resultados no disponibles';$('error').textContent=e.message;$('error').hidden=false;}})();
if('serviceWorker'in navigator&&location.protocol.startsWith('http'))navigator.serviceWorker.register('sw.js').catch(()=>{});
