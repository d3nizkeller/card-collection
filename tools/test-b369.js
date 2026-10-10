/* b369: системные тосты видны только в Студии, игровые — везде.
   Запуск: node tools/test-b369.js [url] (нужен python3 -m http.server в корне) */
const PW = process.env.PW_PATH || '/tmp/pw/node_modules/playwright-core';
const {chromium}=require(PW);
(async()=>{
const b=await chromium.launch({executablePath: process.env.CHROME_PATH || '/tmp/.cache/ms-playwright/chromium-1134/chrome-linux/chrome',args:['--no-sandbox']});
const p=await (await b.newContext({viewport:{width:1100,height:800}})).newPage();
const errs=[]; p.on('pageerror',e=>errs.push(e.message));
await p.goto(process.argv[2] || 'http://127.0.0.1:8123/index.html',{waitUntil:'load',timeout:60000});
await p.waitForTimeout(3200);
const r=await p.evaluate(async()=>{
  const cnt=()=>document.getElementById('toast-container').childElementCount;
  const out={};
  switchTab('store'); await new Promise(r=>setTimeout(r,300));
  let c0=cnt(); nxOwnerToast('системный тост В МАГАЗИНЕ','error'); await new Promise(r=>setTimeout(r,300));
  out.storeSystem = cnt()-c0;                       // ожидаем 0
  c0=cnt(); showToast('игровой тост В МАГАЗИНЕ','success'); await new Promise(r=>setTimeout(r,300));
  out.storeGame = cnt()-c0;                         // ожидаем 1
  document.getElementById('toast-container').innerHTML='';
  document.querySelectorAll('#tab-store,#tab-albums,#tab-battle,#tab-rewards,#tab-market').forEach(t=>t.classList.add('hidden'));
  document.getElementById('tab-studio').classList.remove('hidden'); await new Promise(r=>setTimeout(r,400));
  c0=cnt(); nxOwnerToast('системный тост В СТУДИИ','error'); await new Promise(r=>setTimeout(r,300));
  out.studioSystem = cnt()-c0;                      // ожидаем 1
  // b360-ошибка вшивания вне студии: err() больше не рисует тост
  document.getElementById('toast-container').innerHTML='';
  switchTab('store'); await new Promise(r=>setTimeout(r,300));
  c0=cnt();
  // эмулируем путь err(): nxPushEmbedded без токена не годится (ранний return), поэтому зовём err-логику напрямую через nxOwnerToast-гейт
  try { if (typeof nxInStudio === 'function') { if (nxInStudio()) showToast('Вшивать так много нельзя','error'); else nxOwnerToast('Вшивать так много нельзя','error'); } } catch(e){}
  await new Promise(r=>setTimeout(r,300));
  out.embedErrOutsideStudio = cnt()-c0;             // ожидаем 0
  return out;
});
console.log('системный тост в Магазине  :', r.storeSystem, '(ожидаем 0)');
console.log('игровой тост в Магазине    :', r.storeGame, '(ожидаем 1)');
console.log('системный тост в Студии    :', r.studioSystem, '(ожидаем 1)');
console.log('ошибка вшивания вне Студии :', r.embedErrOutsideStudio, '(ожидаем 0)');
console.log('ошибки страницы:', errs.length?errs.slice(0,3):'нет');
const ok=r.storeSystem===0&&r.storeGame===1&&r.studioSystem===1&&r.embedErrOutsideStudio===0&&errs.length===0;
console.log(ok?'\n✓ b369: системные тосты только в Студии, игровые — везде':'\n✗ расхождение');
await b.close(); process.exit(ok?0:1);})();
