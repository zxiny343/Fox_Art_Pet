/**
 * 面板原型校验（Node，无需浏览器）
 *
 * 1. 提取内联 <script> 做语法检查
 * 2. 在 mock DOM 下真实执行该 script，取出 JS 侧的遗传引擎
 * 3. 逐条对比 JS 结果 vs 导出时 Python 内核的预计算结果
 * 4. 校验 HTML 结构完整性（标签闭合、无占位符残留、无乱码）
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML = path.join(__dirname, '..', 'docs', 'gene-panel-v0.4.html');
const html = fs.readFileSync(HTML, 'utf8');

let pass = 0, fail = 0;
const ck = (cond, msg, extra = '') => {
  if (cond) { pass++; console.log('  [OK]   ' + msg); }
  else { fail++; console.log('  [FAIL] ' + msg + '   ' + extra); }
};

console.log('='.repeat(78));
console.log('基因与性状面板原型校验');
console.log('='.repeat(78));

// ---------------------------------------------------------------- 1 结构
console.log('\n1. HTML 结构');
const cnt = (re) => (html.match(re) || []).length;
ck(cnt(/<div[ >]/g) === cnt(/<\/div>/g),
   `div 标签闭合 (${cnt(/<div[ >]/g)} 开 / ${cnt(/<\/div>/g)} 闭)`);
ck(cnt(/<script/g) === cnt(/<\/script>/g), `script 标签闭合 (${cnt(/<script/g)})`);
ck(!html.includes('__PANEL_DATA__'), '无占位符残留');
ck(!/[锟]|\uFFFD/.test(html), '无乱码');
ck(cnt(/<table/g) === cnt(/<\/table>/g), `table 闭合 (${cnt(/<table/g)})`);

// ---------------------------------------------------------------- 2 取数据 + 执行 JS
console.log('\n2. 在 mock DOM 下执行页面 JS');
const mPd = html.match(/<script id="pd" type="application\/json">([\s\S]*?)<\/script>/);
ck(!!mPd, '找到内嵌数据块');
let DATA;
try { DATA = JSON.parse(mPd[1]); ck(true, `数据可解析（${DATA.foxes.length} 只狐狸）`); }
catch (e) { ck(false, '数据可解析', e.message); process.exit(1); }

const scripts = [...html.matchAll(/<script(?![^>]*id="pd")[^>]*>([\s\S]*?)<\/script>/g)];
ck(scripts.length >= 1, `找到 ${scripts.length} 段可执行脚本`);
const code = scripts.map(s => s[1]).join('\n');

const mkEl = () => ({
  innerHTML: '', textContent: '', value: '', checked: false,
  dataset: {}, style: {}, classList: { add() {}, remove() {}, contains() { return false; } },
  onclick: null, onchange: null,
  click() { if (typeof this.onclick === 'function') this.onclick(); },
});
const els = {};
// 真实浏览器里 <select> 默认选中第一项；mock 需要显式给出，否则脚本读到空 value
const firstF = DATA.foxes.find(f => f.sex === 'F');
const firstM = DATA.foxes.find(f => f.sex === 'M');
els.selDam = Object.assign(mkEl(), { value: String(firstF ? firstF.id : '') });
els.selSire = Object.assign(mkEl(), { value: String(firstM ? firstM.id : '') });
els.selTarget = mkEl();
const sandbox = {
  console,
  document: {
    getElementById(id) {
      if (id === 'pd') return { textContent: mPd[1] };
      if (!els[id]) els[id] = mkEl();
      return els[id];
    },
    querySelectorAll() { return []; },
  },
  window: {},
  JSON,
  Math,
};
sandbox.globalThis = sandbox;

let runErr = null;
try { vm.createContext(sandbox); vm.runInContext(code, sandbox); }
catch (e) { runErr = e; }
ck(!runErr, '页面 JS 无运行时错误', runErr ? runErr.message : '');
if (runErr) { console.log(runErr.stack.split('\n').slice(0, 4).join('\n')); process.exit(1); }

const { predictTarget, kinship, phenotype, predictTrait, BYID, TRAITS } = sandbox;
ck(typeof predictTarget === 'function', '导出 predictTarget()');
ck(typeof kinship === 'function', '导出 kinship()');
ck(typeof phenotype === 'function', '导出 phenotype()');

// ---------------------------------------------------------------- 3 表型一致性
console.log('\n3. JS 表型函数 vs 导出时 Python 的 pheno 字段');
let phenoBad = 0, phenoBadMsg = '';
DATA.foxes.forEach(f => {
  const ph = phenotype(f.geno);
  ['color', 'pattern', 'tails', 'hair_len', 'ear', 'eye', 'curl', 'hetero',
   'glow', 'star', 'halo', 'flame'].forEach(k => {
    if (ph[k] !== f.pheno[k]) {
      phenoBad++;
      if (!phenoBadMsg) phenoBadMsg = `FX-${f.id} ${k}: JS=${ph[k]} Py=${f.pheno[k]}`;
    }
  });
});
ck(phenoBad === 0, `全部 ${DATA.foxes.length} 只狐狸 × 12 个性状的表型一致`, phenoBadMsg);

// ---------------------------------------------------------------- 4 概率一致性
console.log('\n4. JS 配对概率 vs Python 预计算');
let probBad = 0, worst = 0, probMsg = '';
let n = 0;
Object.keys(DATA.targets).forEach(k => {
  const [key, val] = k.split('|');
  DATA.targets[k].forEach(x => {
    n++;
    const jsP = predictTarget(BYID[x.dam].geno, BYID[x.sire].geno, key, val);
    const d = Math.abs(jsP - x.prob);
    worst = Math.max(worst, d);
    if (d > 1e-3) {
      probBad++;
      if (!probMsg) probMsg = `${key}→${val} FX-${x.dam}×FX-${x.sire}: JS=${jsP.toFixed(4)} Py=${x.prob}`;
    }
  });
});
ck(probBad === 0, `${n} 组配对概率全部一致（最大偏差 ${worst.toExponential(2)}）`, probMsg);

// ---------------------------------------------------------------- 5 亲缘系数
console.log('\n5. JS 亲缘系数 vs Python 预计算');
let kBad = 0, kWorst = 0, kMsg = '';
let kn = 0;
Object.keys(DATA.targets).forEach(k => {
  DATA.targets[k].forEach(x => {
    kn++;
    const jsR = kinship(x.dam, x.sire);
    const d = Math.abs(jsR - x.r);
    kWorst = Math.max(kWorst, d);
    if (d > 1e-3) {
      kBad++;
      if (!kMsg) kMsg = `FX-${x.dam}×FX-${x.sire}: JS=${jsR} Py=${x.r}`;
    }
  });
});
ck(kBad === 0, `${kn} 组亲缘系数全部一致（最大偏差 ${kWorst.toExponential(2)}）`, kMsg);

// ---------------------------------------------------------------- 6 概率归一
console.log('\n6. 概率分布归一性');
let normBad = 0, normMsg = '';
const seen = new Set();
DATA.foxes.slice(0, 6).forEach(a => {
  DATA.foxes.slice(0, 6).forEach(b => {
    if (a.sex === b.sex) return;
    const key = a.id + '-' + b.id;
    if (seen.has(key)) return;
    seen.add(key);
    TRAITS.forEach(t => {
      const items = predictTrait(a.geno, b.geno, t);
      const s = items.reduce((acc, it) => acc + it.prob, 0);
      if (Math.abs(s - 1) > 1e-9) {
        normBad++;
        if (!normMsg) normMsg = `${t.name}: 和=${s}`;
      }
    });
  });
});
ck(normBad === 0, '抽样配对的全部性状概率和 = 1', normMsg);

// ---------------------------------------------------------------- 7 濒危数据
console.log('\n7. 濒危等位数据自洽');
let eBad = 0, eMsg = '';
DATA.endangered.forEach(e => {
  const real = DATA.foxes.filter(f => f.geno[e.locus].includes(
    DATA.population.find(p => p.locus === e.locus && p.cn === e.cn).allele)).map(f => f.id);
  if (real.length !== e.carriers) { eBad++; eMsg = `${e.name}/${e.cn}: 记载 ${e.carriers} 只，实算 ${real.length} 只`; }
  if (e.holders.length !== e.carriers) { eBad++; eMsg = `${e.name}/${e.cn}: holders ${e.holders.length} != carriers ${e.carriers}`; }
});
ck(eBad === 0, `${DATA.endangered.length} 个濒危等位的携带者名单自洽`, eMsg);

console.log('\n' + '='.repeat(78));
console.log(`结果：${pass} 通过 / ${fail} 失败`);
console.log('='.repeat(78));
process.exit(fail ? 1 : 0);
