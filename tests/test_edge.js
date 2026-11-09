/* 边界与错误路径测试。
   冒烟测试证明「没崩、主路径能跑」，这一套专门测它测不到的那一半：
   任务分派对不对、坏输入会不会静默失败、错误提示给不给、状态机会不会卡死。
   两者都通过，才算这个工具可交付。 */
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '运营场景人机协作流程工具.html'), 'utf8');
const jsonM = html.match(/<script type="application\/json" id="flows">([\s\S]*?)<\/script>/);
const jsM = html.match(/<script>([\s\S]*?)<\/script>/);
if (!jsonM || !jsM) { console.log('[失败] 找不到数据块或脚本块'); process.exit(1); }

const store = {};
function El() {
  return {
    value: '', textContent: '', innerHTML: '', className: '',
    dataset: {}, style: {}, classList: { toggle() {} },
    addEventListener() {}, querySelector() { return El(); },
    querySelectorAll() { return []; },
    appendChild() {}, removeChild() {}, click() {}, select() {}, focus() {},
    scrollIntoView() {}, setAttribute() {}, getAttribute() { return null; }
  };
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
/* 不能把 global.URL 整个换成一个普通对象：node 的文件代理内部要做
   `x instanceof URL` 判断，覆盖后会报 "Right-hand side of 'instanceof' is not callable"，
   连带 readFileSync 全挂。只补上缺的方法。Blob 同理。 */
if (typeof global.URL !== 'function') global.URL = function () {};
global.URL.createObjectURL = function () { return ''; };
if (typeof global.Blob !== 'function') global.Blob = function () {};

/* fetch 桩：按模式返回不同结果，用来测错误路径 */
let MODE = 'ok';
let LAST = null;
let REPLY = 'ok';
let ABORTED = false;
global.fetch = function (url, opt) {
  LAST = { url: url, opt: opt, body: opt && opt.body ? JSON.parse(opt.body) : null };
  if (opt && opt.signal) {
    opt.signal.addEventListener('abort', function () { ABORTED = true; });
  }
  if (MODE === 'error') return Promise.resolve({ json: () => Promise.resolve({ error: { message: '模拟接口错误' } }) });
  if (MODE === 'empty') return Promise.resolve({ json: () => Promise.resolve({ choices: [{ message: { content: '   ' } }] }) });
  if (MODE === 'throw') return Promise.reject(new Error('模拟网络中断'));
  return Promise.resolve({ json: () => Promise.resolve({ choices: [{ message: { content: REPLY } }] }) });
};

const testSrc = `
return (function(){
  var fails = [], groups = [];
  function ck(c, m){ if (!c) fails.push(m); }
  function has(where, what, tag){ ck(String(where).indexOf(what) > -1, tag + ' 找不到：' + what); }
  function no(where, what, tag){ ck(String(where).indexOf(what) === -1, tag + ' 不该出现：' + what); }
  function G(name){ groups.push(name); }
  var NL = String.fromCharCode(10);

  /* ============ A 结构完整性 ============ */
  G('A 结构完整性');
  ck(typeof MOD_SHORT === 'object' && MOD_SHORT.A === '数字出处', 'A1 MOD_SHORT 缺失或不全');
  ck(typeof T('linkbox') !== 'undefined', 'A2 linkbox 容器缺失');
  var k = '';
  try { k = llmUnwrap(); } catch (e) { k = ''; }
  ck(k.indexOf('sk-') === 0, 'A3 凭据解不出来');
  ck(k.length > 30, 'A4 凭据长度异常：' + k.length);
  ck(typeof llmCfg === 'function' && llmCfg().key === k, 'A5 llmCfg 取到的凭据与解码不一致');

  /* ============ B 任务分派（逐个任务验） ============ */
  G('B 任务分派');
  var seen = { organize: 0, review: 0 };
  for (var bi = 0; bi < DATA.tasks.length; bi++) {
    var bt = DATA.tasks[bi];
    var bw = aiSpec(bt);
    var bkey = bt.selfcheck.type_key;
    render(bt.id);
    var BL = T('linkbox').innerHTML;
    var organize = (bkey === 'feedback_table' || bkey === 'report');
    ck(bw.mode === (organize ? 'organize' : 'review'), 'B1 ' + bt.id + ' 分派错了：' + bw.mode);
    seen[bw.mode]++;
    if (organize) {
      ck(BL.indexOf('id="raw"') > -1, 'B2 ' + bt.id + ' 整理型却没有材料输入框');
      ck(BL.indexOf('跑打标') > -1 || BL.indexOf('跑整理') > -1, 'B3 ' + bt.id + ' 整理型却没有整理按钮');
      ck(BL.indexOf('出初稿') > -1, 'B4 ' + bt.id + ' 整理型却没有成文按钮');
    } else {
      ck(BL.indexOf('id="raw"') === -1, 'B5 ' + bt.id + ' 核稿型不该有材料输入框');
      ck(BL.indexOf('跑打标') === -1 && BL.indexOf('跑整理') === -1, 'B6 ' + bt.id + ' 核稿型不该有整理按钮');
      ck(BL.indexOf('不走「打标＋成文」这两步') > -1, 'B7 ' + bt.id + ' 没说明为什么不做整理');
    }
    /* 最关键的一条：别的任务不能串味成「玩家反馈日报」 */
    if (bkey !== 'feedback_table') {
      no(BL, '出日报初稿', 'B8 ' + bt.id);
      no(BL, '原始反馈', 'B9 ' + bt.id);
    }
    ck(BL.indexOf('全程跑一遍') > -1, 'B10 ' + bt.id + ' 缺全程跑按钮');
    ck(!!T('job_bar'), 'B11 ' + bt.id + ' 缺进度条容器');
  }
  ck(seen.organize > 0 && seen.review > 0, 'B12 两类任务没有都覆盖到');

  /* ============ C 三段解析与渲染 ============ */
  G('C 三段解析');
  var c1 = parseLlm('条目：原句甲' + NL + '问题：问题乙' + NL + '改法：改成丙');
  ck(c1.length === 1 && c1[0].q === '原句甲' && c1[0].p === '问题乙' && c1[0].f === '改成丙', 'C1 标准三段解析错');
  var c2 = parseLlm('条目：原句甲' + NL + '问题：问题乙');
  ck(c2.length === 1 && c2[0].f === '', 'C2 缺改法时该留空而不是崩');
  var c3 = parseLlm('原句甲 → 问题乙');
  ck(c3.length === 1 && c3[0].p.indexOf('问题乙') > -1, 'C3 老格式「→」没兼容');
  var c4 = parseLlm('条目：A' + NL + '问题：B' + NL + '改法：C' + NL + '条目：D' + NL + '问题：E' + NL + '改法：F');
  ck(c4.length === 2 && c4[1].q === 'D', 'C4 多条解析错，得到 ' + c4.length);
  var c5 = parseLlm('让我看看这个问题。' + NL + '原文里写的是共 4 条。');
  ck(c5.length >= 1, 'C5 乱格式应该兜底成问题，不能丢内容');
  var r1 = renderLlm('条目：原句甲' + NL + '问题：问题乙' + NL + '改法：改成丙');
  has(r1, '问题乙', 'C6 渲染'); has(r1, '改成丙', 'C7 渲染'); has(r1, 'llmRewrite', 'C8 渲染');
  var r2 = renderLlm('无');
  has(r2, '这一遍没提出语义层问题', 'C9 答无'); has(r2, '不等于真没有', 'C10 答无');
  ck(renderLlm('').indexOf('没有返回内容') > -1, 'C11 空返回没有提示');
  var r4 = renderLlm('条目：' + new Array(60).join('长') + '甲' + NL + '问题：乙' + NL + '改法：丙');
  has(r4, 'qfull', 'C12 长原文没有可展开结构');
  has(r4, 'qshort', 'C13 长原文没有收起态');

  /* ============ D 边界与错误路径 ============ */
  G('D 边界与错误路径');
  render(DATA.tasks[0].id);
  /* D1 材料为空跑合并 */
  if (T('raw')) T('raw').value = '';
  TAG_MERGED = '';
  var d1out = T('tag_out');
  stepMerge();
  has(d1out.innerHTML, '原始材料是空的', 'D2 空材料的提示');
  /* D3 没有合并结果就打标 */
  TAG_MERGED = '';
  var d3out = T('tag_out');
  stepTag();
  has(d3out.innerHTML, '没有合并结果', 'D4 缺合并结果的提示');
  /* D5 没有整理结果就成文 */
  if (T('tag_out')) T('tag_out').textContent = '';
  var d5out = T('draft_out');
  stepDraft();
  has(T('tag_out').innerHTML, '没有打标结果', 'D6 缺整理结果的提示');
  /* D7 初稿为空跑 AI 审读 */
  if (T('draft')) T('draft').value = '';
  var d7out = T('llm_out');
  stepRead();
  has(T('llm_out').innerHTML, '初稿框是空的', 'D8 空初稿的提示');
  /* D9 没有改法就点重写 */
  LLM_ITEMS = [];
  if (T('draft')) T('draft').value = '有初稿';
  var d9 = T('rw_state');
  llmRewrite();
  has(d9.textContent, '先让 AI 读一遍', 'D10 无改法时的提示');
  /* D11 初稿为空点重写 */
  LLM_ITEMS = [{ q: '甲', p: '乙', f: '丙' }];
  if (T('draft')) T('draft').value = '';
  llmRewrite();
  has(d9.textContent, '初稿框是空的', 'D12 空初稿重写的提示');
  /* D13 有改法但模型没给改法字段 */
  LLM_ITEMS = [{ q: '甲', p: '乙', f: '' }];
  if (T('draft')) T('draft').value = '有初稿';
  llmRewrite();
  has(d9.textContent, '没给出具体改法', 'D14 改法为空时的提示');

  /* ============ E 全程跑状态机 ============ */
  G('E 全程跑状态机');
  var eOrg = null, eRev = null, ei;
  for (ei = 0; ei < DATA.tasks.length; ei++) {
    var ek = DATA.tasks[ei].selfcheck.type_key;
    if (!eOrg && (ek === 'feedback_table' || ek === 'report')) eOrg = DATA.tasks[ei];
    if (!eRev && (ek === 'announcement' || ek === 'launch_check' || ek === 'reward_check')) eRev = DATA.tasks[ei];
  }
  /* E1 整理型起步数 6 */
  if (T('raw')) T('raw').value = '一条原始材料';
  JOB.on = false;
  render(eOrg.id);
  if (T('raw')) T('raw').value = '一条原始材料';
  runPipeline();
  ck(JOB.total === 6, 'E2 整理型步数应为 6，实际 ' + JOB.total);
  ck(JOB.on === true && JOB.i === 0, 'E3 起步状态不对：on=' + JOB.on + ' i=' + JOB.i);
  ck(String(T('job_bar').innerHTML).indexOf('全程跑') > -1, 'E4 进度条没渲染');
  has(T('job_bar').innerHTML, '1 / 6', 'E5 进度条步数');
  /* E6 停下 */
  stopJob();
  ck(JOB.on === false, 'E7 停下之后 JOB.on 还是 true');
  ck(T('job_bar').innerHTML === '', 'E8 停下之后进度条没清掉');
  /* E9 核稿型起步数 2 */
  render(eRev.id);
  runPipeline();
  ck(JOB.total === 2, 'E10 核稿型步数应为 2，实际 ' + JOB.total);
  stopJob();
  /* E11 复核点出口 */
  render(eOrg.id);
  if (T('raw')) T('raw').value = '一条原始材料';
  runPipeline();
  JOB.i = 1;                       // 走到复核点
  if (T('tag_out')) T('tag_out').innerHTML = '<div>合并结果</div>';
  stepReview();
  has(T('tag_out').innerHTML, '跳过复核', 'E12 复核点没有跳过出口');
  has(T('tag_out').innerHTML, '继续', 'E13 复核点没有继续出口');
  ck((T('tag_out').innerHTML + T('job_bar').innerHTML).indexOf('job stop') > -1, 'E14 复核点没有高亮态');
  JOB.skip = true; jobGo(true);
  ck(JOB.i === 2, 'E15 跳过复核后步数没推进：' + JOB.i);
  stopJob();

  /* ============ F 中断 ============ */
  G('F 中断');
  ck(typeof llmP === 'function', 'F1 缺 llmP');
  ck(typeof stopJob === 'function', 'F2 缺 stopJob');
  ck(typeof AbortController === 'function', 'F3 本环境没有 AbortController，中断会降级');
  var fp = llmP('测试', 0);
  ck(fp && typeof fp.then === 'function', 'F4 llmP 没返回 Promise');
  ck(ABORT !== null, 'F5 发起请求后没有挂中断器');
  fp.catch(function(){});
  stopJob();
  ck(ABORT === null, 'F6 停下之后中断器没清掉');

  /* ============ G 空值与兜底 ============ */
  G('G 空值与兜底');
  var g1 = aiSpec({ selfcheck: { type_key: '不存在的类型' }, deliverable: '' });
  ck(g1.mode === 'review', 'G1 未知类型没有兜底成核稿型');
  ck(typeof g1.prod === 'string' && g1.prod.length > 0, 'G2 交付物名为空时没给默认值');
  var g2 = aiSpec({ selfcheck: {}, deliverable: '分析报告 + 附录' });
  ck(g2.prod.indexOf('+') === -1, 'G3 交付物名没有切开加号：' + g2.prod);
  ck(countTagged('这不是表格') === null, 'G4 countTagged 对非表格应返回 null');
  ck(typeof modulesOf('feedback_table') === 'object', 'G5 modulesOf 异常');
  ck(renderLink({ selfcheck: null }) === undefined, 'G6 无自检配置时 renderLink 应安全返回');

  /* ============ H 规则引擎回归 ============ */
  G('H 规则引擎回归');
  var h1 = runModules('本期共 3 条，包括：甲（序号 1）、乙（序号 2）、丙（序号 3）', 'feedback_table');
  var hf = h1.filter(function(m){ return m.k === 'F'; })[0];
  ck(hf && hf.items.length === 0, 'H1 数量与枚举一致时 F 该不报');
  var h2 = runModules('本期共 2 条，包括：甲（序号 1）、乙（序号 2）、丙（序号 3）', 'feedback_table');
  var hf2 = h2.filter(function(m){ return m.k === 'F'; })[0];
  ck(hf2 && hf2.items.length === 1, 'H2 数量与枚举不一致时 F 该报 1 项，实际 ' + (hf2 ? hf2.items.length : '无'));
  ck(runModules('随便一句话', 'feedback_table').length === 6, 'H3 模块数应为 6');

  return { fails: fails, groups: groups };
})();
`;

let res;
try {
  /* 与冒烟测试同一种执行方式：页面脚本 ＋ 测试脚本拼在一起，同一个作用域。 */
  res = new Function('fs', 'path', '__dirname', jsM[1] + '\n' + testSrc)(fs, path, __dirname);
} catch (e) {
  console.log('[失败] 脚本运行报错：' + e.message);
  console.log(e.stack.split('\n').slice(0, 4).join('\n'));
  process.exit(1);
}

console.log('='.repeat(66));
console.log('边界与错误路径测试');
console.log('='.repeat(66));
console.log('覆盖分组：' + res.groups.join('｜'));
console.log('');
if (res.fails.length) {
  console.log('[失败] ' + res.fails.length + ' 项');
  res.fails.forEach(function (m) { console.log('  - ' + m); });
  process.exit(1);
} else {
  console.log('全部通过：任务分派、三段解析、边界与错误提示、全程跑状态机、中断、空值兜底、规则引擎回归。');
}
console.log('='.repeat(66));
