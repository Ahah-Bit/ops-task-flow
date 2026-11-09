/* 渲染 11 个任务的泳道图，各写成一个可测量的 HTML（内嵌用真实包围盒判定的脚本）。
   只做渲染，不派生任何进程——这台机器上 node 被禁止 spawn 子进程，
   调浏览器的事交给 test_layout.py。
   用法：node render_flows.js */
const fs = require('fs');
const path = require('path');

const HERE = __dirname;
const html = fs.readFileSync(path.join(HERE, '运营场景人机协作流程工具.html'), 'utf8');
const jsonM = html.match(/<script type="application\/json" id="flows">([\s\S]*?)<\/script>/);
const jsM = html.match(/<script>([\s\S]*?)<\/script>/);
if (!jsonM || !jsM) { console.log('[失败] 找不到数据块或脚本块'); process.exit(1); }

const store = {};
function El() {
  const o = {
    value: '', textContent: '', innerHTML: '', className: '', dataset: {},
    style: {}, attrs: {},
    classList: { toggle() {}, add() {}, remove() {} },
    addEventListener() {}, querySelector() { return El(); }, querySelectorAll() { return []; },
    appendChild() {}, removeChild() {}, click() {}, select() {}, focus() {},
    scrollIntoView() {}, getAttribute() { return null; },
    setAttribute(k, v) { o.attrs[k] = v; }
  };
  return o;
}
global.document = {
  getElementById(id) {
    if (id === 'flows') return { textContent: jsonM[1] };
    if (!store[id]) store[id] = El();
    return store[id];
  },
  querySelectorAll() { return []; },
  createElement() { return El(); },
  body: { appendChild() {}, removeChild() {} },
  addEventListener() {},
  execCommand() { return true; }
};
global.navigator = {};
global.setTimeout = function () {};
/* 绝不能整个覆盖 URL：node 的文件代理内部要做 instanceof 判断，覆盖后 readFileSync 会挂 */
if (typeof global.URL !== 'function') global.URL = function () {};
global.URL.createObjectURL = function () { return ''; };
if (typeof global.Blob !== 'function') global.Blob = function () {};

let API;
try {
  const src = jsM[1].replace(/^[\s\S]*?(?=var DATA)/, '') +
    'return { tasks: DATA.tasks, run: function(id){ render(id); } };';
  API = new Function('DATA_IN', 'var DATA = DATA_IN;' + src)(JSON.parse(jsonM[1]));
} catch (e) {
  console.log('[失败] 主脚本执行出错：' + e.message);
  process.exit(1);
}

/* 测量脚本：用浏览器里真实的文字包围盒判定，不靠估字数 */
const MEASURE = `
var out = [];
try {
  var stage = document.getElementById('stage');
  var rects = stage.querySelectorAll('rect'), texts = stage.querySelectorAll('text');
  var cards = [], lanes = [];
  for (var r = 0; r < rects.length; r++) {
    var rx = rects[r].getAttribute('rx'), b = rects[r].getBBox();
    if (rx === '9') cards.push(b);
    else if (rx === '10') lanes.push(b);
  }
  for (var c = 0; c < cards.length; c++) {
    var ok = false;
    for (var l = 0; l < lanes.length; l++) {
      if (cards[c].y >= lanes[l].y - 1 && cards[c].y + cards[c].height <= lanes[l].y + lanes[l].height + 1) { ok = true; break; }
    }
    if (!ok) out.push('卡片跑出泳道 y=' + cards[c].y.toFixed(0) + '~' + (cards[c].y + cards[c].height).toFixed(0));
  }
  for (var q = 0; q < texts.length; q++) {
    var el = texts[q], tb = el.getBBox();
    var anc = el.getAttribute('text-anchor') || 'start';
    var txt = (el.textContent || '').trim();
    if (!txt || anc === 'middle') continue;          /* 介入标签另有宽度上限，不按卡片算 */
    if (tb.x < 78) continue;                          /* 左侧泳道标签，本就在卡片外 */
    if (txt.indexOf('跨泳道箭头') === 0) continue;     /* 图下方的说明 */
    var inside = null;
    for (var k = 0; k < cards.length; k++) {
      var cd = cards[k];
      if (tb.x >= cd.x + 3 && (tb.x + tb.width) <= (cd.x + cd.width - 3) &&
          tb.y >= cd.y + 1 && (tb.y + tb.height) <= (cd.y + cd.height - 1)) { inside = cd; break; }
    }
    if (!inside) out.push('文字没有完整落在卡片内：「' + txt + '」');
  }
  for (var m2 = 0; m2 < cards.length; m2++) {
    var cd2 = cards[m2], inb = [];
    for (var t2 = 0; t2 < texts.length; t2++) {
      var e2 = texts[t2], b2 = e2.getBBox();
      if ((e2.getAttribute('text-anchor') || 'start') !== 'start') continue;
      /* x 与 y 都要落在同一张卡片里才算这张卡片的行 */
      if (b2.x < cd2.x || b2.x > cd2.x + cd2.width) continue;
      if (b2.y < cd2.y - 2 || b2.y + b2.hh > cd2.y + cd2.height + 2) continue;
      inb.push({ y: b2.y, hh: b2.height, s: (e2.textContent || '').trim() });
    }
    inb.sort(function (x, y) { return x.y - y.y; });
    for (var g = 1; g < inb.length; g++) {
      var gap = inb[g].y - (inb[g - 1].y + inb[g - 1].hh);
      /* 用 !(x >= 阈值)：字段名写错时 gap 是 NaN，这样会当场报出来而不是静默通过 */
      if (!(gap >= 1.5)) out.push('两行文字相叠：「' + inb[g - 1].s + '」与「' + inb[g].s + '」间隙 ' + gap + 'px');
    }
  }
  var chips = [];
  for (var r2 = 0; r2 < rects.length; r2++) {
    if (rects[r2].getAttribute('rx') === '11') chips.push(rects[r2].getBBox());
  }
  chips.sort(function (x, y) { return x.x - y.x; });
  for (var c2 = 1; c2 < chips.length; c2++) {
    var gp = chips[c2].x - (chips[c2 - 1].x + chips[c2 - 1].width);
    if (!(gp >= 2)) out.push('介入标签横向压到一起，间隙 ' + gp + 'px');
  }
  document.getElementById('out').textContent = out.length ? out.join(' ;; ') : 'OK';
} catch (e) {
  document.getElementById('out').textContent = 'JS_ERROR ' + e.message;
}
`;

const OUT = path.join(HERE, '_shots', '_run');
if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });

const PAGE = (title, svgHtml, vb, w) => `<!doctype html><meta charset="utf-8">
<style>
  body{margin:0;background:#f2efe9;padding:14px;font-family:"Microsoft YaHei",system-ui,sans-serif}
  h3{font:600 13px/1.4 "Microsoft YaHei",system-ui;margin:0 0 8px;color:#3d3a34}
  .box{background:#fff;border:1px solid #ded9d0;border-radius:12px;padding:12px 8px 8px;
       overflow-x:auto;max-width:${w + 16}px}
  svg.flow{display:block;width:100%;height:auto;max-width:${w}px}
  #out{display:block;font:12px/1.5 monospace;margin-top:8px;color:#8a1f1f;white-space:pre-wrap}
</style>
<h3>${title}</h3>
<div class="box"><svg class="flow" id="stage" xmlns="http://www.w3.org/2000/svg" viewBox="${vb}">${svgHtml}</svg></div>
<pre id="out">RUNNING</pre>
<script>${MEASURE}</script>`;

const rows = [];
API.tasks.forEach(function (t, i) {
  store['flow'] = El();
  API.run(t.id);
  const svg = store['flow'];
  const vb = svg.attrs['viewBox'] || '';
  const w = parseInt(vb.split(' ')[2], 10) || 860;
  const no = String(i + 1).padStart(2, '0');
  fs.writeFileSync(path.join(OUT, 'task-' + no + '.html'),
    PAGE(t.id + '　' + t.name + '　（' + t.steps.length + ' 步）', svg.innerHTML, vb, w), 'utf8');
  rows.push([no, t.name, t.steps.length, w]);
});

console.log('已生成 ' + rows.length + ' 个可测量页面：');
rows.forEach(function (r) {
  console.log('  task-' + r[0] + '\t' + r[1] + '\t' + r[2] + ' 步\t图宽 ' + r[3]);
});
