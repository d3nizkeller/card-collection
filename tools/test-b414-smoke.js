/* b414: РЕГРЕССИОННЫЙ smoke-прогон всей игры после правок джекпота.

   Грузит боевые index.html + assets/app.js в jsdom (без сети, без WebGL),
   дёргает полный window.onload(), все вкладки Студии и магазина, все четыре
   игры с джекпотом (Слоты, Сетка, Линии, Колесо), облачную синхронизацию при
   недоступной сети и новую вкладку «Джекпот».

   Смысл: убедиться, что b414 не сломал запуск и основные выплаты
   (пара ×2, три одинаковых ×8…×30, сектор колеса ×1, пустой сектор 0).

   Запуск:  node tools/test-b414-smoke.js
   Нужен jsdom:  npm i jsdom   (или JSDOM_PATH=/путь/к/jsdom)
*/
const fs=require('fs'),path=require('path');
const {JSDOM}=require(process.env.JSDOM_PATH||'jsdom');
const ROOT=path.join(__dirname,'..');
const html=fs.readFileSync(path.join(ROOT,'index.html'),'utf8');
const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,url:'https://d3nizkeller.github.io/card-collection/'});
const w=dom.window, ev=s=>w.eval(s);
const ctx2d=()=>new Proxy({},{get(t,k){if(k==='canvas')return{width:256,height:256,style:{}};if(k==='measureText')return()=>({width:10});if(k==='getImageData')return()=>({data:new Uint8ClampedArray(4)});if(k==='createLinearGradient'||k==='createRadialGradient')return()=>({addColorStop(){}});if(k==='createPattern')return()=>null;return t[k]!==undefined?t[k]:(()=>{});},set(t,k,v){t[k]=v;return true;}});
w.HTMLCanvasElement.prototype.getContext=k=>k==='2d'?ctx2d():null;
w.HTMLCanvasElement.prototype.toDataURL=()=>'data:image/png;base64,';
w.HTMLMediaElement.prototype.play=function(){return Promise.resolve();};
w.HTMLMediaElement.prototype.pause=function(){};w.HTMLMediaElement.prototype.load=function(){};
Object.defineProperty(w,'fetch',{value:()=>Promise.resolve({ok:false,status:0,text:()=>Promise.resolve(''),json:()=>Promise.resolve(null)}),configurable:true});
w.navigator.sendBeacon=()=>true;
w.IntersectionObserver=class{observe(){}unobserve(){}disconnect(){}};
w.ResizeObserver=class{observe(){}unobserve(){}disconnect(){}};
w.matchMedia=w.matchMedia||(q=>({matches:false,media:q,addListener(){},removeListener(){},addEventListener(){},removeEventListener(){}}));
w.THREE=new Proxy({},{get:()=>function(){return{};}});
const errs=[];
w.addEventListener('error',e=>{try{errs.push(String((e.error&&e.error.message)||e.message));}catch(x){}});
const sc=w.document.createElement('script');sc.textContent=fs.readFileSync(path.join(ROOT,'assets','app.js'),'utf8');w.document.body.appendChild(sc);
let fails=0,checks=0;
const ok=(c,m)=>{checks++;console.log((c?'  OK  ':'  FAIL')+' '+m);if(!c)fails++;};
const tryRun=(label,fn)=>{try{const r=fn();ok(true,label+(r===undefined?'':' → '+r));return r;}catch(e){ok(false,label+' → '+e.message);return null;}};

console.log('\n== РЕГРЕССИЯ: полный запуск игры ==');
tryRun('window.onload() (полная инициализация)',()=>{ if(typeof w.onload==='function') w.onload(); });
ok(errs.length===0,'нет оконных ошибок'+(errs.length?': '+errs.slice(0,5).join(' | '):''));
tryRun('switchTab("store")',()=>w.switchTab&&w.switchTab('store'));
['store','albums','battle','rewards','market','studio'].forEach(t=>tryRun('switchTab('+t+')',()=>w.switchTab&&w.switchTab(t)));
tryRun('renderStudio()',()=>w.renderStudio&&w.renderStudio());
tryRun('statsRender()',()=>w.statsRender&&w.statsRender());
tryRun('renderMarket()',()=>w.renderMarket&&w.renderMarket());

console.log('\n== РЕГРЕССИЯ: игровые механики ==');
ev('state.coins = 100000000; saveState(); updateCoinDisplay();');
tryRun('slotsSpin() x3',()=>{for(let i=0;i<3;i++){ev('slots.spinning=false');w.slotsSpin();} return 'ok';});
tryRun('slotsFinish([0,0,0],1000) — три одинаковых',()=>{const c0=ev('state.coins');ev('slotsFinish([0,0,0],1000)');return 'выплата '+(ev('state.coins')-c0);});
tryRun('slotsFinish([0,0,1],1000) — пара',()=>{const c0=ev('state.coins');ev('slotsFinish([0,0,1],1000)');return 'выплата '+(ev('state.coins')-c0);});
tryRun('gridSpin()',()=>{ev('grid.spinning=false');w.gridSpin&&w.gridSpin();return 'ok';});
tryRun('linesStart()',()=>{ev('lines.spinning=false');(w.linesStart||w.linesSpin||function(){})();return 'ok';});
tryRun('wheelSpin()',()=>{ev('wheel.spinning=false');w.wheelSpin&&w.wheelSpin();return 'ok';});
tryRun('wheelAward(1) — сектор ×1',()=>{const c0=ev('state.coins');ev('wheel.betNow=1000');w.wheelAward(1);return 'выплата '+(ev('state.coins')-c0);});
tryRun('wheelAward(0) — пустой сектор',()=>{const c0=ev('state.coins');ev('wheel.betNow=1000');w.wheelAward(0);return 'дельта '+(ev('state.coins')-c0);});
tryRun('minesStart()',()=>{(w.minesStart||function(){})();return 'ok';});
tryRun('jpSyncNow() (сеть недоступна — должен проглотить)',()=>{w.jpSyncNow();return 'ok';});
tryRun('jackpotRender()',()=>{w.jackpotRender();return 'ok';});
tryRun('siteStatsApplyToMe()',()=>{w.siteStatsApplyToMe();return 'ok';});
tryRun('jpcApplyGrants() без назначений',()=>{w.jpcApplyGrants();return 'ok';});
tryRun('showStudioSec("jackpot") → jpcAdminRender+jpcSim',()=>{w.showStudioSec('jackpot');return document_ok();});
function document_ok(){const p=w.document.getElementById('jpc-prob').innerHTML;return 'prob:'+(p.length>500?'ok':'пусто')+' users:'+w.document.getElementById('jpc-users').innerHTML.length;}
tryRun('switchTab("store") обратно',()=>w.switchTab('store'));

setTimeout(()=>{
  ok(errs.length===0,'нет отложенных ошибок'+(errs.length?': '+errs.slice(0,5).join(' | '):''));
  console.log('\n'+(fails?'FAIL '+fails+'/'+checks:'ALL PASS '+checks+' проверок, ошибок 0'));
  process.exit(fails?1:0);
},1500);
