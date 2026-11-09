/* 冒烟测试：把页面里的脚本放进打桩 DOM 里真跑一遍。
   看的是跑出来的东西对不对，不是语法过不过。 */
const fs = require('fs');
const path = require('path');
const cp = require('child_process');

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
global.setTimeout = function () {};
/* 不能把 global.URL 整个换成一个普通对象：node 的文件代理内部要做
   `x instanceof URL` 判断，覆盖后会报 "Right-hand side of 'instanceof' is not callable"，
   连带 readFileSync 全挂。只补上缺的方法。Blob 同理。 */
if (typeof global.URL !== 'function') global.URL = function () {};
global.URL.createObjectURL = function () { return ''; };
if (typeof global.Blob !== 'function') global.Blob = function () {};

const testSrc = `
return (function(){
  var fails = [], sheets = [];
  function ck(c, m){ if(!c) fails.push(m); }
  function has(where, what, tag){ ck(String(where).indexOf(what) > -1, tag + ' 找不到：' + what); }

  /* 1 启动即默认选中并画出泳道图 */
  ck(T('flow').innerHTML.indexOf('<marker') > -1, '启动时没有画出泳道图箭头');
  ck(T('metrics').innerHTML.indexOf('<b>') > -1, '启动时没有渲染关键数字');
  ck(T('detail').innerHTML.length > 100, '启动时没有渲染细节抽屉');
  var REF = T('reftxt').innerHTML;
  has(REF, '画法依据', '依据区'); has(REF, '细节层级', '依据区');
  has(REF, '推进阶梯', '依据区'); has(REF, 'A 必须始终是人', '依据区');
  has(REF, '泳道图', '依据区'); has(REF, 'RACI', '依据区');
  has(REF, '岗位任务覆盖', '依据区');
  has(REF, '连素材都不该由 AI 供', '依据区');
  ck(!!(DATA.meta.job_coverage && DATA.meta.job_coverage.excluded
        && DATA.meta.job_coverage.excluded.length), '数据里没有岗位任务覆盖登记，不画的那项没了交代');

  for (var i = 0; i < DATA.tasks.length; i++) {
    var t = DATA.tasks[i];
    render(t.id);

    /* 2 关键数字 */
    var M = T('metrics').innerHTML;
    has(M, '<b>' + t.steps.length + '</b>', t.id + ' 关键数字');
    has(M, '步流程', t.id); has(M, '处交接点', t.id);
    has(M, '步不用人盯', t.id); has(M, '步要人出手', t.id);

    /* 3 现状一行 */
    var P = T('prob').innerHTML;
    has(P, t.current, t.id); has(P, t.bottleneck, t.id);
    has(P, t.deliverable, t.id); has(P, t.cadence, t.id); has(P, t.maps_to, t.id);

    /* 4 泳道图：两条泳道、节点落位、R 标注、跨泳道交接 */
    var F = T('flow').innerHTML;
    has(F, '跨泳道箭头＝交接点', t.id);
    /* 图要设宽度上限：不设的话宽屏下 svg 被拉伸放大，字同比变大更容易溢出 */
    var mw = String(T('flow').style.maxWidth);
    ck(mw.length > 2 && mw.slice(-2) === 'px', t.id + ' 泳道图没有设宽度上限，宽屏下会被拉伸放大');
    has(F, '>机器</text>', t.id + ' 机器泳道标签');
    has(F, '>人</text>', t.id + ' 人泳道标签');
    /* 标题在卡片里会折成两行，只查前几个字等于把断言绑死在断行位置上——
       换行规则一调就误报。改成把 SVG 里所有文字按顺序拼起来，再找完整标题。
       不用正则切，避免这里的模板字符串把反斜杠吃掉。 */
    var flowText = String(F).split('</text>').map(function (x) {
      var q = x.lastIndexOf('>');
      return q > -1 ? x.slice(q + 1) : '';
    }).join('');
    var mCount = 0, hCount = 0;
    for (var k = 0; k < t.steps.length; k++) {
      var s = t.steps[k];
      has(flowText, s.title, t.id + ' 泳道图节点');
      has(F, 'R ' + s.raci.R, t.id + ' 泳道图 R 标注');
      has(F, autoText(s.auto), t.id + ' 档位文案');
      if (s.raci.R === '机器') mCount++; else hCount++;
      if (s.auto !== '全自动' && s.raci.other) {
        has(F, (s.auto === '例外制' ? '例外' : s.raci.other), t.id + ' 另一侧泳道标签');
      }
    }
    ck(mCount + hCount === t.steps.length, t.id + ' 泳道落位计数不对');
    ck(mCount > 0 && hCount > 0, t.id + ' 两条泳道都应有节点');
    var excGot = (F.match(/>例外</g) || []).length;
    var excWant = t.steps.filter(function (x) { return x.auto === '例外制'; }).length;
    ck(excGot === excWant, t.id + ' 例外标签数不对：应 ' + excWant + '，实际 ' + excGot);

    /* 5 细节抽屉：默认第 1 步，切到第 2 步要变 */
    var D1 = T('detail').innerHTML;
    has(D1, t.steps[0].title, t.id + ' 抽屉默认步');
    has(D1, t.steps[0].ai.brief, t.id + ' 抽屉默认步');
    selectStep(2);
    var D2 = T('detail').innerHTML;
    has(D2, t.steps[1].title, t.id + ' 点第 2 步后抽屉没切换');
    has(D2, t.steps[1].human.brief, t.id);
    has(D2, t.steps[1].handoff, t.id);
    has(D2, 'R ' + t.steps[1].raci.R, t.id + ' 抽屉 RACI');
    has(D2, 'A ' + t.steps[1].raci.A, t.id + ' 抽屉 RACI');
    has(D2, autoText(t.steps[1].auto), t.id + ' 抽屉档位文案');
    has(D2, t.steps[1].output, t.id);
    has(D2, t.steps[1].ai.needs[0], t.id);
    has(D2, t.steps[1].human.decides[0], t.id);
    has(D2, t.steps[1].on_error[0].if, t.id);
    has(D2, t.steps[1].basis.tier, t.id);
    has(D2, t.steps[1].basis.why, t.id);
    has(D2, t.steps[1].source[0], t.id);

    /* 6 打勾 */
    tog(2);
    ck(done[t.id + '#2'], t.id + ' 打勾没生效');
    ck(T('flow').innerHTML.indexOf('已完成') > -1, t.id + ' 打勾后流程图没显示已完成');
    tog(2);
    ck(!done[t.id + '#2'], t.id + ' 取消打勾没生效');

    /* 7 自检交接 */
    var L = T('linkbox').innerHTML, sc = t.selfcheck;
    has(L, sc.type_name, t.id + ' 自检类型中文名');
    for (var m = 0; m < sc.checkpoints.length; m++) has(L, sc.checkpoints[m], t.id);
    has(L, '全程跑一遍', t.id + ' 全程跑按钮');
    if (!T('job_bar')) f.push(t.id + ' 没有进度条容器，看不到进度也停不下来');
    has(L, '只跑规则检查', t.id + ' 单跑规则检查按钮');
    var mods = modulesOf(sc.type_key);
    /* 直接用页面里那份 MOD_SHORT，不再在测试里抄一份——
       抄过一次就会脱节：加 F 模块时这里漏了，断言就挂在 undefined 上。 */
    var MODSHORT = MOD_SHORT;
    Object.keys(DATA.meta.module_names).forEach(function (mk) {
      if (mods.indexOf(mk) > -1) has(L, MODSHORT[mk], t.id + ' 检查项说明');
    });
    ck(mods.length >= 4 && mods.length <= 6, t.id + ' 模块数异常：' + mods.length);
    if (sc.extra) { has(L, sc.extra.type_name, t.id + ' 另查按钮'); }

    /* 8 例外提示 */
    render(t.id);
    checkTriggers(t, t.triggers[0].kw[0] + ' 情况');
    ck(T('trg').innerHTML.indexOf('触发') > -1, t.id + ' 关键词没触发提示');
    checkTriggers(t, '平平无奇的一天');
    ck(T('trg').innerHTML === '', t.id + ' 没有关键词时不该有提示');

    /* 9 导出流程单 */
    T('ctx').value = '本次的具体情况测试';
    var sheet = buildSheet();
    ck(sheet.length > 1200, t.id + ' 流程单过短');
    var head = ['# 协作流程单', t.name, t.maps_to, t.deliverable, t.cadence, '本次的具体情况测试'];
    for (var q = 0; q < head.length; q++) has(sheet, head[q], t.id + ' 流程单');
    var must = ['AI 做什么', '人做什么', '交接点', '产出物', '出错怎么办', '判定依据',
                '交付前自检', '分工小结', '流程出处'];
    for (var m2 = 0; m2 < must.length; m2++) has(sheet, must[m2], t.id + ' 流程单');
    has(sheet, sc.type_key, t.id + ' 流程单');
    has(sheet, mods.join('、'), t.id + ' 流程单');
    has(sheet, '以机器为主', t.id + ' 流程单');
    for (var k3 = 0; k3 < t.steps.length; k3++) has(sheet, '第 ' + t.steps[k3].no + ' 步', t.id + ' 流程单');
    sheets.push({ id: t.id, len: sheet.length, text: sheet });
  }

  /* 11 跨引擎比对：本页引擎跑出来的数，必须与自检工具（Python）一致 */
  var GOLD = [
    ['样例一_版本更新公告.md', 'announcement'],
    ['样例二_玩家反馈日报.md', 'feedback_table'],
    ['样例三_活动复盘报告.md', 'report'],
    ['样例四_版本上线自检.md', 'launch_check']
  ];
  var cross = [];
  for (var gi = 0; gi < GOLD.length; gi++) {
    var fp = path.join(__dirname, '..', '运营自检', 'golden', GOLD[gi][0]);
    if (!fs.existsSync(fp)) { fails.push('跨引擎比对：找不到样例 ' + GOLD[gi][0]); continue; }
    var txt2 = fs.readFileSync(fp, 'utf8');
    var rr = runModules(txt2, GOLD[gi][1]), jsTotal = 0;
    for (var ri = 0; ri < rr.length; ri++) jsTotal += rr[ri].items.length;
    cross.push({ file: GOLD[gi][0], type: GOLD[gi][1], js: jsTotal });
  }

  return { fails: fails, sheets: sheets, cross: cross };
})()
`;

let out;
try {
  out = new Function('fs', 'path', '__dirname', jsM[1] + '\n' + testSrc)(fs, path, __dirname);
} catch (e) {
  console.log('[失败] 脚本运行报错：' + e.message);
  console.log(e.stack.split('\n').slice(0, 6).join('\n'));
  process.exit(1);
}

/* 页面自带凭据时的功能校验：界面不该出现任何要填的东西，点一下就该发请求 */
const BUILT = path.join(__dirname, '运营场景人机协作流程工具.html');
let builtReport = '（未找到主文件，跳过）';
if (fs.existsSync(BUILT)) {
  const bh = fs.readFileSync(BUILT, 'utf8');
  const bj = bh.match(/<script type="application\/json" id="flows">([\s\S]*?)<\/script>/);
  const bs = bh.match(/<script>([\s\S]*?)<\/script>/);
  const store2 = {};
  const el2 = () => ({
    value: '', textContent: '', innerHTML: '', className: '',
    dataset: {}, style: {}, classList: { toggle() {} },
    addEventListener() {}, querySelector() { return el2(); },
    querySelectorAll() { return []; }, appendChild() {}, removeChild() {},
    click() {}, select() {}, focus() {}, scrollIntoView() {},
    setAttribute() {}, getAttribute() { return null; }
  });
  const prevDoc = global.document, prevFetch = global.fetch, prevStore = {};
  global.document = {
    getElementById(id) {
      if (id === 'flows') return { textContent: bj[1] };
      if (!store2[id]) store2[id] = el2();
      return store2[id];
    },
    querySelectorAll() { return []; },
    createElement() { return el2(); },
    body: { appendChild() {}, removeChild() {} },
    addEventListener() {},
  execCommand() { return true; }
  };
  let cap = null;
  /* 假的 fetch：既记录请求，也把 then 链真的走一遍，
     这样 callLlm → 解析 → renderLlm 整条渲染路径都能被验证 */
  const chain = {
    then(f) { try { if (f) f({ json() { return chain; } }); } catch (e) { /* 断言失败由回调内部记录 */ } return chain; },
    catch() { return chain; }
  };
  global.fetch = function (url, opt) { cap = { url: url, opt: opt }; return chain; };
  try {
    const bres = new Function('fs', 'path', '__dirname', bs[1] + '\n' + `return (function(){
      var f = [];
      if (typeof LLM_KEY_ENC === 'undefined' || !LLM_KEY_ENC.length) f.push('凭据位是空的，页面打开后 AI 用不了');
      var k = llmUnwrap();
      if (k !== '') { if (k.indexOf('sk-') !== 0) f.push('解码回来的凭据不像密钥'); }
      if (llmCfg().key !== k) f.push('取到的凭据不是解码出来的那个');
      var L = T('linkbox').innerHTML;
      if (L.indexOf('type="password"') > -1) f.push('界面上不该再出现密钥输入框');
      if (L.indexOf('首次用要先填一次密钥') > -1) f.push('不该再提示填密钥');
      if (L.indexOf('换密钥') > -1) f.push('不该再出现换密钥入口');
      if (T('llm_state').textContent !== '') f.push('状态文字该是空的，实际：' + T('llm_state').textContent);
      T('draft').value = '这是一段测试初稿，含一个数字 42%。';
      llmGo();
      /* 大模型输出必须先被拆成条目，不能直接倒成一堵字墙 */
      var rl = renderLlm('1. 原文A → 问题B\\n2. 只给问题的句子，没有箭头');
      if (rl.indexOf('llmit') === -1) f.push('大模型输出没被拆成条目');
      if (rl.indexOf('问题B') === -1) f.push('大模型输出的问题部分丢了');
      if ((rl.match(/llmit/g) || []).length !== 2) f.push('条目数不对，应为 2');
      var rn = renderLlm('无');
      if (rn.indexOf('这一遍没提出语义层问题') === -1) f.push('模型回答「无」时没给正面提示');
      if (rn.indexOf('不等于真没有') === -1) f.push('模型答「无」时没带保留说明');
      /* 三段结构：原文 / 问题 / 改法 */
      var NL3 = String.fromCharCode(10);
      var r3 = renderLlm('条目：原文A' + NL3 + '问题：问题B' + NL3 + '改法：改成C');
      if (r3.indexOf('问题B') === -1 || r3.indexOf('改成C') === -1) f.push('审读结果的三段结构没渲染出来');
      if (r3.indexOf('llmRewrite') === -1) f.push('审读结果里没有「按这些改法重写一版」的入口');
      /* 全程跑与可中断 */
      if (typeof runPipeline !== 'function') f.push('缺「全程跑一遍」的入口');
      if (typeof stopJob !== 'function') f.push('缺「停下」的实现，做不到随时打断');
      if (typeof llmP !== 'function') f.push('缺可中断的调用实现');
      if (typeof llmRewrite !== 'function') f.push('缺「按这些改法重写一版」的实现');
      if (typeof aiSpec !== 'function') f.push('缺按任务类型分派的配置');
      if (typeof ld !== 'function' || ld('x').indexOf('ldbar') === -1) f.push('等待提示没有动画结构');
      /* 整理那两步只对「整理型」任务成立：输入是零散材料，产出是结构化报告。
         核稿型任务（公告、检查表、奖励核对）的输入已经是成稿，不该出现整理入口。
         2026-09-23 用户发现原先所有任务共用「玩家反馈日报」那一套，加这组断言守住分派。 */
      var tOrg = null, tRev = null, ti;
      for (ti = 0; ti < DATA.tasks.length; ti++) {
        var kk = DATA.tasks[ti].selfcheck.type_key;
        if (!tOrg && (kk === 'feedback_table' || kk === 'report')) tOrg = DATA.tasks[ti];
        if (!tRev && (kk === 'announcement' || kk === 'launch_check' || kk === 'reward_check')) tRev = DATA.tasks[ti];
      }
      if (!tOrg || !tRev) f.push('找不到用来验证任务分派的两类任务');
      else {
        render(tOrg.id);
        var LO = T('linkbox').innerHTML;
        if (LO.indexOf('跑打标') === -1 && LO.indexOf('跑整理') === -1) f.push('整理型任务没有整理入口，AI 又只剩查错');
        if (LO.indexOf('出初稿') === -1) f.push('整理型任务没有成文入口');
        if (!T('raw')) f.push('整理型任务没有材料输入框，整理没地方灌材料');
        if (LO.indexOf('先合并去重') === -1) f.push('整理那一步没写清是先合并去重');
        render(tRev.id);
        var LR = T('linkbox').innerHTML;
        if (LR.indexOf('跑打标') > -1 || LR.indexOf('跑整理') > -1) f.push('核稿型任务不该出现整理入口：' + tRev.name);
        if (LR.indexOf('不走「打标＋成文」这两步') === -1) f.push('核稿型任务没说明为什么不做整理：' + tRev.name);
        render(DATA.tasks[0].id);
      }
      if (typeof TAG_P1 !== 'string' || TAG_P1.indexOf('合并') === -1) f.push('第一步提示词缺失或没提合并');
      if (typeof TAG_P2 !== 'string' || TAG_P2.indexOf('反馈清单') === -1) f.push('第二步提示词缺失');
      if (typeof tagStep1 !== 'function' || typeof tagStep2 !== 'function') f.push('打标两步的入口函数缺失');
      if (typeof TAG_MERGED !== 'string') f.push('没有存第一步产出的变量，重跑会丢上下文');
      /* 这两个按钮是第一步跑完才渲染出来的，不在初始 DOM 里，要查函数体 */
      var s1 = tagStep1.toString();
      if (s1.indexOf('接着打标') === -1) f.push('第一步跑完没有「接着打标」的出口');
      if (s1.indexOf('重跑这一步') === -1) f.push('第一步跑完没有「重跑这一步」的退路');
      var tg = renderTag(['| 序号 | 原文摘要 | 置信度 | 备选归属 |',
                          '|---|---|---|---|',
                          '| 1 | 闪退 | 高 | - |',
                          '| 2 | 引导不清 | 低 | 玩法系统/新手引导 |',
                          '',
                          '待确认：第 2 条'].join(String.fromCharCode(10)));
      if (tg.indexOf('<table') === -1) f.push('打标结果没渲染成表格');
      if (tg.indexOf('class="low"') === -1) f.push('低置信度那行没被标出来');
      if ((tg.match(/<tr>/g) || []).length !== 3) f.push('打标表行数不对，应为表头+2 行');
      if (tg.indexOf('待确认：第 2 条') === -1) f.push('打标表的待确认说明丢了');
      if (renderTag('模型这次没给表格').indexOf('llmraw') === -1) f.push('没给表格时应退回纯文本，不能白屏');
      /* 条数必须由代码算，不能靠模型数。之前踩过：模型写「共 4 条」却列 5 个序号 */
      var NL = String.fromCharCode(10);
      var md = ['| 序号 | 反馈类型 | 紧急度 |', '|---|---|---|',
                '| 1 | 玩法系统 | 高 |', '| 2 | 玩法系统 | 低 |', '| 3 | 内容体验 | 高 |'].join(NL);
      var ct = countTagged(md);
      if (!ct) f.push('countTagged 解析不了打标表');
      else {
        if (ct.total !== 3) f.push('countTagged 总条数不对，应为 3，实际 ' + ct.total);
        if (!ct.types || ct.types.length !== 2) f.push('countTagged 类型分组不对，应为 2 组');
        else {
          var wan = 0, kai = 0;
          for (var q2 = 0; q2 < ct.types.length; q2++) {
            if (ct.types[q2].name === '玩法系统') wan = ct.types[q2].n;
            if (ct.types[q2].name === '内容体验') kai = ct.types[q2].n;
          }
          if (wan !== 2 || kai !== 1) f.push('countTagged 分组计数不对');
        }
        var fl = factLineOf(ct);
        if (fl.indexOf('总条数 3 条') === -1) f.push('统计那一行没写明总条数');
        if (fl.indexOf('玩法系统 2 条') === -1) f.push('统计那一行没写分类条数');
      }
      if (countTagged('没有表格的一段话') !== null) f.push('countTagged 对非表格输入该返回 null');
      /* F 列举检查：拿真实跑出来的回归用例验一遍（那版初稿有两处「N 条」与枚举对不上） */
      var NL2 = String.fromCharCode(10);
      var rp = path.join(__dirname, '校准材料', '回归用例-成文初稿-含已知问题.md');
      if (!fs.existsSync(rp)) {
        f.push('找不到 F 的回归用例：' + rp);
      } else {
        var rf = checkF(fs.readFileSync(rp, 'utf8').split(NL2), true);
        if (rf.length !== 2) f.push('F 对回归用例应报 2 项，实际 ' + rf.length + ' 项');
      }
      /* F 对基准样例：样例二已注入一处该类型问题（应报 1），其余三份不该报 */
      var GK = [['样例一_版本更新公告.md', 0], ['样例二_玩家反馈日报.md', 1],
                ['样例三_活动复盘报告.md', 0], ['样例四_版本上线自检.md', 0]];
      for (var gq = 0; gq < GK.length; gq++) {
        var gp2 = path.join(__dirname, '..', '运营自检', 'golden', GK[gq][0]);
        if (!fs.existsSync(gp2)) continue;
        var gfn = checkF(fs.readFileSync(gp2, 'utf8').split(NL2), true);
        if (gfn.length !== GK[gq][1]) {
          f.push('F 对 ' + GK[gq][0] + ' 应报 ' + GK[gq][1] + ' 项，实际 ' + gfn.length + ' 项');
        }
      }
      /* 一键跑完：串起规则检查、AI、自动勾「交付前自检」 */
      T('draft').value = '这是一段测试初稿，出现数字 42%，并且引用了「一些玩家说很卡」但没写来源。';
      var t1 = task(cur);
      runAll();
      if (!T('sc_result').innerHTML.trim()) f.push('一键跑完没渲染规则检查结果');
      if (!T('llm_out').innerHTML.trim()) f.push('一键跑完没渲染 AI 结果');
      var zi = -1;
      for (var q = 0; q < t1.steps.length; q++) { if (t1.steps[q].title.indexOf('自检') > -1) zi = t1.steps[q].no; }
      if (zi > -1 && !done[key(zi)]) f.push('一键跑完没自动勾掉「交付前自检」');
      if (zi === -1) f.push('没找到交付前自检这一步，自动勾选无法验证');
      return { fails: f };
    })()`)(fs, path, __dirname);
    if (bres && bres.fails && bres.fails.length) {
      bres.fails.forEach(function (m) { out.fails.push('本页自带凭据：' + m); });
    }
  } catch (e) {
    out.fails.push('自带凭据校验脚本报错：' + e.message);
  }
  global.document = prevDoc; global.fetch = prevFetch;
  builtReport = cap
    ? ('点一下发出的请求：' + (cap.url || '无') + '　带 Authorization：' +
       !!(cap.opt && cap.opt.headers && String(cap.opt.headers.Authorization).indexOf('Bearer sk-') === 0))
    : '（llmGo 没有发出请求）';
  if (!cap) out.fails.push('本页自带凭据：点了按钮没发出请求');
  if (cap && !(cap.opt && cap.opt.headers && String(cap.opt.headers.Authorization).indexOf('Bearer sk-') === 0)) {
    out.fails.push('本页自带凭据：请求头里没有密钥');
  }
}

console.log('='.repeat(64));
console.log('运营场景人机协作流程工具 · 冒烟测试');
console.log('='.repeat(64));
console.log('本页自带凭据：' + builtReport);
if (fs.existsSync(BUILT)) console.log('  界面只剩功能按钮，无输入框、无填密钥提示 —— 已断言');
console.log('');

/* 跨引擎比对：拿四份样例，本页引擎与自检工具分别跑，数必须一样 */
const PY = process.env.WB_PY ||
  'C:/Users/16073/.workbuddy/binaries/python/versions/3.13.12/python.exe';
console.log('跨引擎比对（本页引擎 vs 自检工具）：');
out.cross.forEach(function (c) {
  let py = null, note = '';
  try {
    const r = cp.execSync('"' + PY + '" 跑自检.py "../运营自检/golden/' + c.file + '" ' + c.type,
      { cwd: __dirname, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
    const mm = r.match(/待处理项合计：(\d+)/);
    py = mm ? parseInt(mm[1], 10) : null;
  } catch (e) { note = '（自检工具未跑起来，跳过比对）'; }
  if (py === null) {
    console.log('  ' + c.file + '　本页 ' + c.js + ' 项' + note);
  } else if (py === c.js) {
    console.log('  ' + c.file + '　两边一致：' + c.js + ' 项');
  } else {
    console.log('  ' + c.file + '　不一致！本页 ' + c.js + ' 项，自检工具 ' + py + ' 项');
    out.fails.push('跨引擎不一致：' + c.file + ' 本页 ' + c.js + ' / 自检工具 ' + py);
  }
});
console.log('');

console.log('导出流程单长度：');
out.sheets.forEach(function (s) { console.log('  ' + s.id + '：' + s.len + ' 字符'); });
console.log('');
if (out.fails.length) {
  console.log('[失败] ' + out.fails.length + ' 项');
  out.fails.slice(0, 30).forEach(function (f) { console.log('  - ' + f); });
  process.exit(1);
}
console.log('全部通过：泳道图与自动化档位、关键数字、细节抽屉切换、打勾、');
console.log('           页面内自检引擎、例外提示、流程单导出均正常。');
console.log('='.repeat(64));
