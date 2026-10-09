// Execute the actual application against its actual JSON data with a DOM/canvas stub.
// This checks logic, selections and exports; it is not a browser visual or PWA test.
const fs=require('fs'),vm=require('vm'),path=require('path'),assert=require('assert');
const root=path.resolve(__dirname,'..'),dist=path.join(root,'dist'),els=new Map();
const html=fs.readFileSync(path.join(dist,'index.html'),'utf8');
for(const [,id]of html.matchAll(/id="([^"]+)"/g))els.set(id,{value:'',hidden:false,textContent:'',innerHTML:'',listeners:{},selectedOptions:[{text:'1 hora'}],replaceChildren(){this.innerHTML='';},addEventListener(t,f){this.listeners[t]=f;}});
Object.assign(els.get('asset'),{value:'BTC'});Object.assign(els.get('timeframe'),{value:'1h'});els.get('period').value='holdout';els.get('mode').value='ema';els.get('scroll').value='100';
Object.assign(els.get('chart'),{clientWidth:900,getContext(){return new Proxy({},{get(){return()=>{}},set(){return true}})}});
const emitted=[];const ctx={console,setTimeout,clearTimeout,Blob,URL,document:{getElementById:id=>{assert(els.has(id),'Missing HTML element '+id);return els.get(id)},createElement:()=>({click(){emitted.push(this.download)}})},location:{protocol:'https:'},navigator:{},window:{addEventListener(){},devicePixelRatio:1},fetch:async url=>{const p=path.join(dist,url);return{ok:fs.existsSync(p),json:async()=>JSON.parse(fs.readFileSync(p,'utf8'))}}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(dist,'app.js'),'utf8'),ctx);
const settle=()=>new Promise(resolve=>setTimeout(resolve,5));
(async()=>{await settle();assert.match(els.get('metrics').innerHTML,/Precisión de barrera/);assert.match(els.get('comparison').innerHTML,/EMA/);
 const sum=JSON.parse(fs.readFileSync(path.join(dist,'data/summary.json')));let count=0;
 for(const r of sum.results){els.get('asset').value=r.symbol;els.get('timeframe').value=r.timeframe;await els.get('asset').listeners.change();await settle();
  if(r.status!=='COMPLETE'){assert(!els.get('error').hidden);continue;}
  for(const period of ['holdout','validation'])for(const mode of Object.keys(r.periods[period].models)){els.get('period').value=period;els.get('mode').value=mode;els.get('mode').listeners.change();assert(els.get('error').hidden);assert.match(els.get('metrics').innerHTML,/Señales evaluables/);count++;}
 }
 const r=sum.results.find(r=>r.status==='COMPLETE');els.get('asset').value=r.symbol;els.get('timeframe').value=r.timeframe;els.get('mode').value='ema';await els.get('asset').listeners.change();await settle();els.get('export-csv').listeners.click();els.get('export-summary').listeners.click();assert.equal(emitted.length,2);
 console.log('PASS: '+count+' selecciones de motor/periodo, casos no evaluables y 2 exportaciones. No browser/PWA physical test.');
})().catch(e=>{console.error(e);process.exitCode=1});
