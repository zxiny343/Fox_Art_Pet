// 临时校验脚本：在 Node 里跑一遍狐狸渲染逻辑，检查坐标与数值是否健全
const fs = require('fs');
const path = require('path').join(__dirname, 'fantasy-fox-design-v0.1.html');
const html = fs.readFileSync(path, 'utf8');
const i = html.rindex ? html.rindex('<script>') : html.lastIndexOf('<script>');
const j = html.lastIndexOf('</script>');
let js = html.slice(i + 8, j);

// 只保留到 FOXES 定义结束（去掉所有 DOM 渲染代码）
const cut = js.indexOf('/* ============ 渲染到页面 ============ */');
js = js.slice(0, cut);

const sandbox = {};
new Function('globalThis.__out = {}; ' + js + '; globalThis.__fox = foxSVG; globalThis.__foxes = FOXES;')();

const foxSVG = globalThis.__fox;
const FOXES = globalThis.__foxes;

const POSES = [undefined, 'stand', 'sit', 'sleep', 'walk', 'run', 'eat', 'display', 'young'];
let issues = 0, total = 0;

function check(name, svg) {
  total++;
  if (/NaN|undefined|Infinity/.test(svg)) {
    console.log('  [NaN/undefined] ' + name);
    issues++;
  }
  // 检查 viewBox 尺寸
  const vb = /viewBox="0 0 (\d+) (\d+)"/.exec(svg);
  const W = +vb[1], H = +vb[2];
  // 收集显式中心点坐标
  const centers = [];
  const reEll = /<ellipse cx="([-\d.]+)" cy="([-\d.]+)" rx="([-\d.]+)" ry="([-\d.]+)"/g;
  let m;
  while ((m = reEll.exec(svg))) {
    centers.push({ x: +m[1], y: +m[2], rx: +m[3], ry: +m[4] });
  }
  const reCir = /<circle cx="([-\d.]+)" cy="([-\d.]+)" r="([-\d.]+)"/g;
  while ((m = reCir.exec(svg))) {
    centers.push({ x: +m[1], y: +m[2], rx: +m[3], ry: +m[3] });
  }
  let minX = 1e9, maxX = -1e9, minY = 1e9, maxY = -1e9;
  centers.forEach(c => {
    minX = Math.min(minX, c.x - c.rx); maxX = Math.max(maxX, c.x + c.rx);
    minY = Math.min(minY, c.y - c.ry); maxY = Math.max(maxY, c.y + c.ry);
  });
  // 检查 path 上的坐标（跳过 rotate 等 transform 里的自定义例外）
  const rePath = /<path d="([^"]+)"/g;
  let p;
  while ((p = rePath.exec(svg))) {
    const d = p[1];
    // 相对命令（小写）无法用「绝对值交替配对」解析，跳过（只有嘴部的小 q 曲线）
    if (/[mlqctshvz]/.test(d)) continue;
    const nums = (d.match(/-?\d+(\.\d+)?/g) || []).map(Number);
    for (let n = 0; n + 1 < nums.length; n += 2) {
      minX = Math.min(minX, nums[n]); maxX = Math.max(maxX, nums[n]);
      minY = Math.min(minY, nums[n + 1]); maxY = Math.max(maxY, nums[n + 1]);
    }
  }

  // 允许 4px 描边余量；超出即视为被裁切
  const pad = 3;
  if (minX < -pad || maxX > W + pad || minY < -pad || maxY > H + pad) {
    console.log('  [越界] ' + name + '  X:' + minX.toFixed(1) + '~' + maxX.toFixed(1) +
      '  Y:' + minY.toFixed(1) + '~' + maxY.toFixed(1) + '  (画布 ' + W + 'x' + H + ')');
    issues++;
  }
}

console.log('== 逐个体验证 ==');
Object.keys(FOXES).forEach(k => {
  check(k + '/默认', foxSVG(FOXES[k], 150));
});

console.log('== 全姿态 × 全是被遇上 lung examination ==');
Object.keys(FOXES).forEach(k => {
  POSES.forEach(po => {
    const sp = JSON.parse(JSON.stringify(FOXES[k]));
    sp.pose = po;
    check(k + '/' + (po || 'default'), foxSVG(sp, 150));
  });
});

console.log('== 极端组合 ==');
const extremes = [
  { name: '最大耳+垂耳+长毛+九尾+显示', v: { coat: 'black', ears: { shape: 'flop', size: 1.25, tip: 'dark', inner: 'dark' }, tails: { count: 9, len: 'long', fluff: 'fluffy', tip: 'white' }, fur: { len: 4, curl: 2 }, eyes: { color: 'violet', shape: 'round', hetero: true, heteroTo: 'gold' }, pattern: { type: 'tabby' }, stars: true, halo: true, glow: true, sparkle: true, pose: 'display' } },
  { name: '最小耳+单短尾+短毛+睡眠', v: { coat: 'white', ears: { shape: 'round', size: 0.8, tip: 'none', inner: 'light' }, tails: { count: 1, len: 'short', fluff: 'thin', tip: 'same' }, fur: { len: 0, curl: 0 }, eyes: { color: 'blue', shape: 'narrow' }, pattern: { type: 'none' }, pose: 'sleep' } },
  { name: '幼崽+奔跑+三尾', v: { coat: 'orange', ears: { shape: 'pointy', size: 1, tip: 'white', inner: 'light' }, tails: { count: 3, len: 'long', fluff: 'fluffy', tip: 'ember' }, fur: { len: 2, curl: 1 }, eyes: { color: 'gold', shape: 'almond' }, pattern: { type: 'spots' }, pose: 'young' } },
  { name: '无特化默认值', v: { coat: 'silver' } }
];
extremes.forEach(e => check('极端:' + e.name, foxSVG(e.v, 150)));

console.log('\n渲染总数 ' + total + '，问题数 ' + issues);
const sample = foxSVG(FOXES.jiuyao, 150);
console.log('九曜示例元素数：' + (sample.match(/<(path|ellipse|circle|g)\b/g) || []).length);
console.log('九曜 SVG 长度：' + sample.length + ' 字节');
