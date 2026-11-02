const fs=require('fs');
const target=process.argv[2]||'fantasy-fox-design-v0.2.html';
console.log('校验目标:',target);
let html=fs.readFileSync(target,'utf8');
const blocks=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
console.log('script 块数:', blocks.length);
let js=blocks.join('\n');
const pathMod=require('path');
const store={};
function mkEl(){ return {innerHTML:'',children:[], insertBefore(){}, appendChild(){},
  insertAdjacentHTML(a,h){ this.innerHTML+=h; } }; }
globalThis.document={ querySelector:function(s){ if(!store[s]) store[s]=mkEl(); return store[s]; },
  createElement:function(){ return mkEl(); } };
try{ new Function(js)(); }catch(e){ console.log('RUN ERROR:', e.message); process.exit(1); }
const keys=Object.keys(store);
let empty=0,nan=0;
keys.forEach(k=>{
  const v=store[k].innerHTML||'';
  const n=(v.match(/NaN|undefined|Infinity/g)||[]).length;
  nan+=n; if(n) console.log('  NaN/undefined in '+k+': '+n);
  if(!v.trim()){ console.log('  EMPTY: '+k); empty++; }
});
console.log('');
console.log('容器数:', keys.length, '| 空:', empty, '| NaN/undefined:', nan);
let oob=0;
keys.forEach(k=>{
  const v=store[k].innerHTML||'';
  const re=/<(circle|ellipse|rect|line|text)\b[^>]*>/g; let m;
  while((m=re.exec(v))){
    (m[0].match(/(?:^|\s)(?:cx|x1|x2|x)="(-?[\d.]+)"/g)||[]).forEach(s=>{
      const nx=parseFloat(s.split('"')[1]);
      if(nx<-2||nx>1000){ oob++; if(oob<8) console.log('  X越界 '+k+': '+nx+' :: '+m[0].slice(0,80)); }
    });
  }
});
console.log('疑似 X 越界:', oob);
