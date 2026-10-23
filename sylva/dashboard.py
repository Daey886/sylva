"""Sylva 唯讀看板：輕量單頁 Web UI，瀏覽核心記憶 / 年輪 / 斷點。

零前端框架、零新增依賴——單個自包含 HTML（內聯 CSS/JS），fetch 只讀
端點渲染。與三原語（Inject/Ingest/Ring）無關，純外圍查看，不寫資料庫。

i18n：內建簡中（zh-CN）/ 繁中（zh-TW）/ 英文（en）三語字典，前端
`I18N` 物件以 key 對照，新增語言只需加一個字典物件 + 語言選擇器
一個 `<option>`。選擇持久化於 localStorage（sylva_lang）。

端點（全部唯讀）：
    GET /            看板頁面（HTML）
    GET /rings       年輪列表
    GET /stats       統計概覽（計數 + db 大小）
    GET /checkpoint  最近斷點

安全：服務綁 0.0.0.0（用戶拍板），看板本身不新增任何寫入能力。
"""
from __future__ import annotations

from fastapi import FastAPI, Query, Response

from sylva.primitives import SylvaKernel

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sylva 記憶看板</title>
<style>
:root{--bg:#0f1512;--panel:#18211c;--border:#26332c;--text:#d7e3db;--muted:#8aa396;--accent:#4caf7d}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--text);padding:24px;max-width:960px;margin:0 auto;line-height:1.6}
#langbar{position:fixed;top:12px;right:16px;z-index:10}
#langbar select{background:var(--panel);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:6px 10px;font-family:inherit;font-size:13px;cursor:pointer}
header{margin-bottom:20px}
h1{font-size:20px;color:var(--accent);margin-bottom:16px}
.stats{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}
.stat{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:12px 16px;min-width:120px}
.stat b{display:block;font-size:22px;color:var(--accent)}
.stat span{color:var(--muted);font-size:13px}
.tabs{display:flex;gap:10px;margin-bottom:20px}
.tab{flex:1;background:var(--panel);border:1px solid var(--border);color:var(--muted);border-radius:8px;padding:12px 6px;font-size:14px;cursor:pointer;transition:all .15s;font-family:inherit}
.tab:hover{border-color:var(--accent);color:var(--text)}
.tab.active{background:var(--accent);border-color:var(--accent);color:#08140e;font-weight:600}
.panel{display:none}
.panel.active{display:block}
h2{font-size:15px;color:var(--accent);border-bottom:1px solid var(--border);padding-bottom:6px;margin-bottom:12px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:12px 16px;margin-bottom:10px}
.card .meta{color:var(--muted);font-size:12px;margin-bottom:4px}
.card .content{white-space:pre-wrap;word-break:break-word}
.tag{display:inline-block;font-size:11px;padding:2px 8px;border-radius:10px;margin-right:6px}
.tag.fact{background:#1e3a2a;color:#6fd49a}.tag.rule{background:#1e2c3a;color:#6fb3d4}
.tag.decision{background:#3a2a1e;color:#d4a96f}.tag.interaction{background:#2e2a3a;color:#b9a6d4}
.empty{color:var(--muted);font-style:italic}
.field{margin-bottom:14px}
.field label{display:block;color:var(--muted);font-size:12px;margin-bottom:5px}
.field input{width:100%;padding:10px;background:#0f1512;border:1px solid var(--border);border-radius:8px;color:var(--text);font-family:inherit;font-size:14px}
.field input:focus{outline:none;border-color:var(--accent)}
.btn-save{width:100%;padding:11px;background:var(--accent);border:none;border-radius:8px;color:#08140e;font-weight:600;cursor:pointer;font-family:inherit;font-size:14px;margin-top:6px}
.btn-save:hover{opacity:.9}
.set-status{color:var(--muted);font-size:13px;margin-top:10px}
.set-status.ok{color:#6fd49a}
.graph-tools{display:flex;gap:6px;margin-bottom:10px}
.graph-tools button{background:var(--panel);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:4px 12px;cursor:pointer;font-size:14px;font-family:inherit}
.graph-tools button:hover{border-color:var(--accent);color:var(--accent)}
</style>
</head>
<body>
<div id="langbar">
  <select id="lang" onchange="setLang(this.value)">
    <option value="zh-CN">简体中文</option>
    <option value="zh-TW">繁體中文</option>
    <option value="en">English</option>
  </select>
</div>
<div id="gate" style="display:none;max-width:360px;margin:80px auto;text-align:center">
  <h1 style="color:#4caf7d;font-size:20px;margin-bottom:8px" data-i18n="app_title">🌳 Sylva 記憶看板</h1>
  <p style="color:#8aa396;margin-bottom:16px" data-i18n="enter_key">請輸入訪問密鑰</p>
  <input id="keyinput" type="password" data-i18n="key_placeholder" placeholder="粘貼密鑰" style="width:100%;padding:10px;background:#18211c;border:1px solid #26332c;border-radius:8px;color:#d7e3db;margin-bottom:12px;font-family:inherit">
  <button id="keybtn" style="width:100%;padding:10px;background:#4caf7d;border:none;border-radius:8px;color:#08140e;font-weight:600;cursor:pointer;font-family:inherit" data-i18n="enter_btn">進入</button>
  <p id="keyerr" style="color:#d46f6f;margin-top:10px;font-size:13px;display:none" data-i18n="key_invalid">密鑰無效，請重新輸入</p>
</div>
<div id="app">
<header>
  <h1 data-i18n="app_title">🌳 Sylva 記憶看板</h1>
  <div class="stats" id="stats"></div>
</header>
<nav class="tabs">
  <button class="tab active" data-tab="cores" data-i18n="tab_cores">🌰 核心記憶</button>
  <button class="tab" data-tab="rings" data-i18n="tab_rings">🪵 年輪</button>
  <button class="tab" data-tab="checkpoint" data-i18n="tab_checkpoint">📌 斷點</button>
  <button class="tab" data-tab="relations" data-i18n="tab_relations">🕸️ 關係</button>
  <button class="tab" data-tab="settings" data-i18n="tab_settings">⚙️ 設置</button>
</nav>
<main>
  <section id="panel-cores" class="panel active"></section>
  <section id="panel-rings" class="panel"></section>
  <section id="panel-checkpoint" class="panel"></section>
  <section id="panel-relations" class="panel">
    <h2 data-i18n="relations_title">🕸️ 實體關係圖譜</h2>
    <div class="graph-tools">
      <button onclick="window.graphZoom&amp;&amp;window.graphZoom(1.3)" data-i18n-title="zoom_in">＋</button>
      <button onclick="window.graphZoom&amp;&amp;window.graphZoom(0.77)" data-i18n-title="zoom_out">－</button>
      <button onclick="window.graphReset&amp;&amp;window.graphReset()" data-i18n-title="zoom_reset">⤾</button>
      <button onclick="window.toggleHistory&amp;&amp;window.toggleHistory()" id="btn-history" data-i18n-title="show_history">🕰️</button>
    </div>
    <div class="card" id="graph-box"></div>
  </section>
  <section id="panel-settings" class="panel">
    <h2 data-i18n="settings_title">⚙️ 功能設置</h2>
    <div class="card">
      <div class="field"><label data-i18n="llm_base_url">LLM Base URL（OpenAI 兼容）</label><input id="set-base" placeholder="http://192.168.10.88:20127/v1"></div>
      <div class="field"><label data-i18n="llm_model">LLM 模型</label><input id="set-model" placeholder="cbai/deepseek-v4.1-flash"></div>
      <div class="field"><label data-i18n="api_key">API Key</label><input id="set-key" type="password" data-i18n="key_empty" placeholder="未配置，粘貼 API Key"></div>
      <button id="set-save" class="btn-save" data-i18n="save_btn">保存設置</button>
      <div id="set-status" class="set-status"></div>
    </div>
  </section>
</main>
</div>
<script>
var I18N={
'zh-TW':{
  app_title:'🌳 Sylva 記憶看板',enter_key:'請輸入訪問密鑰',key_placeholder:'粘貼密鑰',enter_btn:'進入',key_invalid:'密鑰無效，請重新輸入',
  tab_cores:'🌰 核心記憶',tab_rings:'🪵 年輪',tab_checkpoint:'📌 斷點',tab_relations:'🕸️ 關係',tab_settings:'⚙️ 設置',
  stat_rings:'年輪',stat_cores:'核心記憶',stat_checkpoints:'斷點',stat_db:'資料庫',
  cores_title_n:'🌰 核心記憶（{n}）',rings_title_n:'🪵 年輪（{n}）',checkpoint_title:'📌 斷點',
  relations_title:'🕸️ 實體關係圖譜',settings_title:'⚙️ 功能設置',
  empty_cores:'尚無核心記憶',empty_rings:'尚無年輪',empty_checkpoint:'尚無斷點',empty_relations:'尚無實體關係（注入記憶後自動抽取）',
  llm_base_url:'LLM Base URL（OpenAI 兼容）',llm_model:'LLM 模型',api_key:'API Key',
  key_empty:'未配置，粘貼 API Key',save_btn:'保存設置',
  key_configured_ph:'已配置 {masked}（留空保持不變）',llm_enabled_model:'✅ LLM 已啟用（{model}）',
  llm_disabled:'⚠️ 未配置 LLM，純本地模式（實體抽取 / 睡眠昇華自動跳過）',
  saved:'✅ 已保存',saved_llm:'✅ 已保存，LLM 已啟用',save_fail:'保存失敗，請檢查密鑰',zoom_in:'放大',zoom_out:'縮小',zoom_reset:'重置',show_history:'显示历史',history_tag:'已失效',show_history:'顯示歷史',history_tag:'已失效',
  load_fail:'載入失敗',stats_fail:'載入統計失敗',settings_fail:'載入設置失敗'
},
'zh-CN':{
  app_title:'🌳 Sylva 记忆看板',enter_key:'请输入访问密钥',key_placeholder:'粘贴密钥',enter_btn:'进入',key_invalid:'密钥无效，请重新输入',
  tab_cores:'🌰 核心记忆',tab_rings:'🪵 年轮',tab_checkpoint:'📌 断点',tab_relations:'🕸️ 关系',tab_settings:'⚙️ 设置',
  stat_rings:'年轮',stat_cores:'核心记忆',stat_checkpoints:'断点',stat_db:'数据库',
  cores_title_n:'🌰 核心记忆（{n}）',rings_title_n:'🪵 年轮（{n}）',checkpoint_title:'📌 断点',
  relations_title:'🕸️ 实体关系图谱',settings_title:'⚙️ 功能设置',
  empty_cores:'尚无核心记忆',empty_rings:'尚无年轮',empty_checkpoint:'尚无断点',empty_relations:'尚无实体关系（注入记忆后自动抽取）',
  llm_base_url:'LLM Base URL（OpenAI 兼容）',llm_model:'LLM 模型',api_key:'API Key',
  key_empty:'未配置，粘贴 API Key',save_btn:'保存设置',
  key_configured_ph:'已配置 {masked}（留空保持不变）',llm_enabled_model:'✅ LLM 已启用（{model}）',
  llm_disabled:'⚠️ 未配置 LLM，纯本地模式（实体抽取 / 睡眠升华自动跳过）',
  saved:'✅ 已保存',saved_llm:'✅ 已保存，LLM 已启用',save_fail:'保存失败，请检查密钥',zoom_in:'放大',zoom_out:'缩小',zoom_reset:'重置',
  load_fail:'加载失败',stats_fail:'加载统计失败',settings_fail:'加载设置失败'
},
'en':{
  app_title:'🌳 Sylva Memory Dashboard',enter_key:'Enter access key',key_placeholder:'Paste key',enter_btn:'Enter',key_invalid:'Invalid key, please retry',
  tab_cores:'🌰 Cores',tab_rings:'🪵 Rings',tab_checkpoint:'📌 Checkpoint',tab_relations:'🕸️ Relations',tab_settings:'⚙️ Settings',
  stat_rings:'Rings',stat_cores:'Cores',stat_checkpoints:'Checkpoints',stat_db:'Database',
  cores_title_n:'🌰 Core Memories ({n})',rings_title_n:'🪵 Rings ({n})',checkpoint_title:'📌 Checkpoint',
  relations_title:'🕸️ Entity Relation Graph',settings_title:'⚙️ Settings',
  empty_cores:'No core memories yet',empty_rings:'No rings yet',empty_checkpoint:'No checkpoint yet',empty_relations:'No relations yet (auto-extracted after ingestion)',
  llm_base_url:'LLM Base URL (OpenAI-compatible)',llm_model:'LLM Model',api_key:'API Key',
  key_empty:'Not configured, paste API key',save_btn:'Save',
  key_configured_ph:'Configured {masked} (leave empty to keep)',llm_enabled_model:'✅ LLM enabled ({model})',
  llm_disabled:'⚠️ LLM not configured, local-only mode (extraction / sleep skipped)',
  saved:'✅ Saved',saved_llm:'✅ Saved, LLM enabled',save_fail:'Save failed, check key',zoom_in:'Zoom in',zoom_out:'Zoom out',zoom_reset:'Reset',show_history:'Show history',history_tag:'Invalidated',
  load_fail:'Load failed',stats_fail:'Failed to load stats',settings_fail:'Failed to load settings'
}
};
var LANG=localStorage.getItem('sylva_lang')||'zh-TW';
var LOCALE={'zh-CN':'zh-CN','zh-TW':'zh-Hant','en':'en-US'}[LANG]||'zh-Hant';
function t(k){var d=I18N[LANG]||I18N['zh-TW'];return (d[k]!==undefined)?d[k]:(I18N['zh-TW'][k]||k);}
function tf(k,repl){var s=t(k);if(repl){for(var r in repl)s=s.split('{'+r+'}').join(repl[r]);}return s;}
function setLang(l){localStorage.setItem('sylva_lang',l);location.reload();}
function applyI18n(){
  document.querySelectorAll('[data-i18n]').forEach(function(el){
    var v=t(el.getAttribute('data-i18n'));
    if(el.tagName==='INPUT'){el.placeholder=v;}else{el.textContent=v;}
  });
  document.querySelectorAll('[data-i18n-title]').forEach(function(el){
    el.title=t(el.getAttribute('data-i18n-title'));
  });
  document.title=t('app_title');
  document.documentElement.lang=LANG;
}
function getKey(){
  var m=location.search.match(/[?&]key=([^&]+)/);
  if(m){var k=decodeURIComponent(m[1]);localStorage.setItem('sylva_key',k);history.replaceState(null,'',location.pathname);return k;}
  return localStorage.getItem('sylva_key')||'';
}
var KEY=getKey();
function showGate(err){
  document.getElementById('app').style.display='none';
  document.getElementById('gate').style.display='block';
  if(err)document.getElementById('keyerr').style.display='block';
}
function j(u){
  return fetch(u,{headers:KEY?{'Authorization':'Bearer '+KEY}:{}}).then(function(r){
    if(r.status===401){localStorage.removeItem('sylva_key');KEY='';showGate(true);throw 0;}
    if(!r.ok)throw 0;
    return r.json();
  });
}
function p(u,body){
  return fetch(u,{method:'POST',headers:Object.assign({'Content-Type':'application/json'},KEY?{'Authorization':'Bearer '+KEY}:{}),body:JSON.stringify(body)})
    .then(function(r){
      if(r.status===401){localStorage.removeItem('sylva_key');KEY='';showGate(true);throw 0;}
      if(!r.ok)throw 0;
      return r.json();
    });
}
if(!KEY){showGate(false);}else{document.getElementById('lang').value=LANG;applyI18n();}
document.getElementById('keybtn').onclick=function(){
  var v=document.getElementById('keyinput').value.trim();
  if(v){localStorage.setItem('sylva_key',v);location.reload();}
};
document.getElementById('keyinput').addEventListener('keydown',function(e){if(e.key==='Enter')document.getElementById('keybtn').click();});
function esc(s){return String(s??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c]));}
function fmtTime(t){return t?new Date(t*1000).toLocaleString(LOCALE):'';}

document.querySelectorAll('.tab').forEach(function(b){
  b.addEventListener('click',function(){
    document.querySelectorAll('.tab').forEach(function(x){x.classList.remove('active');});
    document.querySelectorAll('.panel').forEach(function(x){x.classList.remove('active');});
    b.classList.add('active');
    document.getElementById('panel-'+b.dataset.tab).classList.add('active');
  });
});

(function(){
  var order={fact:0,rule:1,decision:2,interaction:3};

  j('/stats').then(function(s){
    document.getElementById('stats').innerHTML=
      '<div class="stat"><b>'+s.rings+'</b><span>'+t('stat_rings')+'</span></div>'+
      '<div class="stat"><b>'+s.cores+'</b><span>'+t('stat_cores')+'</span></div>'+
      '<div class="stat"><b>'+s.checkpoints+'</b><span>'+t('stat_checkpoints')+'</span></div>'+
      '<div class="stat"><b>'+(s.db_bytes/1024).toFixed(1)+'KB</b><span>'+t('stat_db')+'</span></div>';
  }).catch(function(){document.getElementById('stats').textContent=t('stats_fail');});

  j('/core').then(function(c){
    var cores=c.cores||{};
    var ks=Object.keys(cores);
    document.getElementById('panel-cores').innerHTML='<h2>'+tf('cores_title_n',{n:ks.length})+'</h2>'+(ks.length?
      ks.map(function(k){return '<div class="card"><div class="meta">'+esc(k)+'</div><div class="content">'+esc(cores[k])+'</div></div>';}).join(''):
      '<div class="empty">'+t('empty_cores')+'</div>');
  }).catch(function(){document.getElementById('panel-cores').textContent=t('load_fail');});

  j('/rings?limit=500').then(function(r){
    var rings=r.rings||[];
    rings.sort(function(a,b){return (order[a.ring_type]??9)-(order[b.ring_type]??9)||b.created_at-a.created_at;});
    document.getElementById('panel-rings').innerHTML='<h2>'+tf('rings_title_n',{n:rings.length})+'</h2>'+(rings.length?
      rings.map(function(x){return '<div class="card"><div class="meta"><span class="tag '+esc(x.ring_type)+'">'+esc(x.ring_type)+'</span>imp='+Number(x.importance).toFixed(2)+' · '+fmtTime(x.created_at)+'</div><div class="content">'+esc(x.content)+'</div></div>';}).join(''):
      '<div class="empty">'+t('empty_rings')+'</div>');
  }).catch(function(){document.getElementById('panel-rings').textContent=t('load_fail');});

  j('/checkpoint').then(function(cp){
    document.getElementById('panel-checkpoint').innerHTML='<h2>'+t('checkpoint_title')+'</h2>'+(cp?
      '<div class="card"><div class="meta">'+esc(cp.session_id)+'</div><div class="content">'+esc(cp.context)+'</div></div>':
      '<div class="empty">'+t('empty_checkpoint')+'</div>');
  }).catch(function(){document.getElementById('panel-checkpoint').textContent=t('load_fail');});

  function renderGraph(rels){
    var nodes={},edges=[];
    (rels||[]).forEach(function(r){
      if(!nodes[r.subject])nodes[r.subject]={n:r.subject,d:0};
      if(!nodes[r.object])nodes[r.object]={n:r.object,d:0};
      nodes[r.subject].d++;nodes[r.object].d++;
      edges.push({s:r.subject,p:r.predicate,o:r.object,inv:r.invalid_at!=null});
    });
    var ns=Object.keys(nodes);
    if(!ns.length)return '<div class="empty">'+t('empty_relations')+'</div>';
    var cell=120;
    var span=Math.max(760,Math.sqrt(ns.length)*cell+140);
    var W=span,H=span,cx=W/2,cy=H/2;
    ns.forEach(function(n){nodes[n].x=cx+(Math.random()-0.5)*80;nodes[n].y=cy+(Math.random()-0.5)*80;nodes[n].vx=0;nodes[n].vy=0;});
    ns.forEach(function(n){nodes[n].r=5+Math.min(nodes[n].d,8)*1.6;});
    var ga=1,gamin=0.01;
    for(var git=0;git<2000&&ga>gamin;git++){
      var gi,gj,gA,gB,gdx,gdy,gd2,gd,gf,gp,gux,guy,gminD;
      for(gi=0;gi<ns.length;gi++){nodes[ns[gi]].vx=0;nodes[ns[gi]].vy=0;}
      for(gi=0;gi<ns.length;gi++)for(gj=gi+1;gj<ns.length;gj++){
        gA=nodes[ns[gi]];gB=nodes[ns[gj]];gdx=gA.x-gB.x;gdy=gA.y-gB.y;gd2=gdx*gdx+gdy*gdy;
        if(gd2<1)gd2=1;gd=Math.sqrt(gd2);gf=4000/gd2;
        gA.vx+=gdx/gd*gf;gA.vy+=gdy/gd*gf;gB.vx-=gdx/gd*gf;gB.vy-=gdy/gd*gf;
      }
      for(gi=0;gi<ns.length;gi++)for(gj=gi+1;gj<ns.length;gj++){
        gA=nodes[ns[gi]];gB=nodes[ns[gj]];gdx=gA.x-gB.x;gdy=gA.y-gB.y;gd=Math.sqrt(gdx*gdx+gdy*gdy)||0.1;
        gminD=gA.r+gB.r+22;
        if(gd<gminD){gp=(gminD-gd)*0.7;gux=gdx/gd;guy=gdy/gd;gA.vx+=gux*gp;gA.vy+=guy*gp;gB.vx-=gux*gp;gB.vy-=guy*gp;}
      }
      edges.forEach(function(ge){
        gA=nodes[ge.s];gB=nodes[ge.o];gdx=gB.x-gA.x;gdy=gB.y-gA.y;gd=Math.sqrt(gdx*gdx+gdy*gdy)||0.1;
        gf=(gd-130)*0.04;
        gA.vx+=gdx/gd*gf;gA.vy+=gdy/gd*gf;gB.vx-=gdx/gd*gf;gB.vy-=gdy/gd*gf;
      });
      for(gi=0;gi<ns.length;gi++){
        gA=nodes[ns[gi]];
        gA.vx+=(cx-gA.x)*0.03;gA.vy+=(cy-gA.y)*0.03;
      }
      for(gi=0;gi<ns.length;gi++){
        gA=nodes[ns[gi]];gA.x+=gA.vx*ga;gA.y+=gA.vy*ga;
      }
      ga*=0.985;
    }
    var gFinal={};
    ns.forEach(function(n){gFinal[n]={x:nodes[n].x,y:nodes[n].y};});
    ns.forEach(function(n){nodes[n].x=cx+(Math.random()-0.5)*80;nodes[n].y=cy+(Math.random()-0.5)*80;nodes[n].vx=0;nodes[n].vy=0;});
    window.__graphAnim={nodes:nodes,edges:edges,ns:ns,cx:cx,cy:cy,final:gFinal};
    function sl(s,m){return s.length>m?s.slice(0,m)+'…':s;}
    var svg='<svg id="gsvg" width="100%" height="520" viewBox="0 0 '+W+' '+H+'" style="display:block;cursor:grab;touch-action:none">';
    svg+='<g id="gg">';
    edges.forEach(function(e,i){
      var a=nodes[e.s],b=nodes[e.o];
      var st=e.inv?'#4a5a52':'#2f4538';
      var dash=e.inv?' stroke-dasharray="4,3"':'';
      var fl=e.inv?'#5a6b62':'#8aa899';
      svg+='<line id="ge'+i+'" x1="'+a.x+'" y1="'+a.y+'" x2="'+b.x+'" y2="'+b.y+'" stroke="'+st+'" stroke-width="1.5"'+dash+'/>';
      svg+='<text id="gep'+i+'" x="'+((a.x+b.x)/2)+'" y="'+((a.y+b.y)/2-4)+'" fill="'+fl+'" font-size="9" text-anchor="middle">'+esc(sl(e.p,10))+'<title>'+esc(e.p)+(e.inv?'（'+t('history_tag')+'）':'')+'</title></text>';
    });
    ns.forEach(function(n,i){
      var r=nodes[n].r;
      svg+='<circle id="gn'+i+'" cx="'+nodes[n].x+'" cy="'+nodes[n].y+'" r="'+r+'" fill="#6fd49a"/>';
      svg+='<text id="gnt'+i+'" x="'+nodes[n].x+'" y="'+(nodes[n].y+r+13)+'" fill="#dce6e0" font-size="11" text-anchor="middle">'+esc(sl(n,14))+'<title>'+esc(n)+'</title></text>';
    });
    svg+='</g></svg>';
    return svg;
  }
  var showHistory=false;
  function loadGraph(){
    var url=showHistory?'/relations?include_invalid=true':'/relations';
    j(url).then(function(d){
      document.getElementById('graph-box').innerHTML=renderGraph(d.relations);
      bindGraph();
    }).catch(function(){document.getElementById('graph-box').textContent=t('load_fail');});
  }
  window.toggleHistory=function(){
    showHistory=!showHistory;
    var b=document.getElementById('btn-history');
    if(b){b.style.borderColor=showHistory?'var(--accent)':'var(--border)';b.style.color=showHistory?'var(--accent)':'var(--text)';}
    loadGraph();
  };
  loadGraph();

  function bindGraph(){
    var svg=document.getElementById('gsvg');
    if(!svg)return;
    var g=document.getElementById('gg');
    var scale=1,tx=0,ty=0;
    function apply(){g.setAttribute('transform','translate('+tx+','+ty+') scale('+scale+')');}
    svg.addEventListener('wheel',function(e){
      e.preventDefault();
      var rect=svg.getBoundingClientRect();
      var mx=e.clientX-rect.left,my=e.clientY-rect.top;
      var ns=Math.min(8,Math.max(0.2,scale*(e.deltaY<0?1.12:0.89)));
      tx=mx-(mx-tx)*(ns/scale);ty=my-(my-ty)*(ns/scale);
      scale=ns;apply();
    },{passive:false});
    var dragging=false,sx=0,sy=0;
    svg.addEventListener('mousedown',function(e){dragging=true;sx=e.clientX-tx;sy=e.clientY-ty;svg.style.cursor='grabbing';});
    window.addEventListener('mousemove',function(e){if(dragging){tx=e.clientX-sx;ty=e.clientY-sy;apply();}});
    window.addEventListener('mouseup',function(){dragging=false;svg.style.cursor='grab';});
    svg.addEventListener('dblclick',function(){scale=1;tx=0;ty=0;apply();});
    window.graphZoom=function(f){var ns=Math.min(8,Math.max(0.2,scale*f));var rect=svg.getBoundingClientRect();var mx=rect.width/2,my=rect.height/2;tx=mx-(mx-tx)*(ns/scale);ty=my-(my-ty)*(ns/scale);scale=ns;apply();};
    window.graphReset=function(){scale=1;tx=0;ty=0;apply();};
    startGraphAnim();
  }

  function startGraphAnim(){
    var st=window.__graphAnim;
    if(!st)return;
    if(window.__animId)cancelAnimationFrame(window.__animId);
    var nodes=st.nodes,edges=st.edges,ns=st.ns;
    var circles=[],labels=[],lines=[],ptexts=[],i;
    for(i=0;i<ns.length;i++){circles.push(document.getElementById('gn'+i));labels.push(document.getElementById('gnt'+i));}
    for(i=0;i<edges.length;i++){lines.push(document.getElementById('ge'+i));ptexts.push(document.getElementById('gep'+i));}
    var startPos={};
    ns.forEach(function(n){startPos[n]={x:nodes[n].x,y:nodes[n].y};});
    function render(){
      var i,n,nd,c,t,e,a,b,l,pt;
      for(i=0;i<ns.length;i++){
        n=ns[i];nd=nodes[n];c=circles[i];t=labels[i];
        if(c){c.setAttribute('cx',nd.x);c.setAttribute('cy',nd.y);}
        if(t){t.setAttribute('x',nd.x);t.setAttribute('y',nd.y+nd.r+13);}
      }
      for(i=0;i<edges.length;i++){
        e=edges[i];a=nodes[e.s];b=nodes[e.o];l=lines[i];pt=ptexts[i];
        if(l){l.setAttribute('x1',a.x);l.setAttribute('y1',a.y);l.setAttribute('x2',b.x);l.setAttribute('y2',b.y);}
        if(pt){pt.setAttribute('x',(a.x+b.x)/2);pt.setAttribute('y',(a.y+b.y)/2-4);}
      }
    }
    function fitView(){
      var minX=1e9,minY=1e9,maxX=-1e9,maxY=-1e9,i,a;
      for(i=0;i<ns.length;i++){
        a=nodes[ns[i]];
        minX=Math.min(minX,a.x-a.r-34);maxX=Math.max(maxX,a.x+a.r+34);
        minY=Math.min(minY,a.y-a.r-34);maxY=Math.max(maxY,a.y+a.r+34);
      }
      var sv=document.getElementById('gsvg');
      if(sv)sv.setAttribute('viewBox',minX+' '+minY+' '+Math.max(maxX-minX,200)+' '+Math.max(maxY-minY,200));
    }
    if(typeof requestAnimationFrame!=='function'){
      var i0,n0;
      for(i0=0;i0<ns.length;i0++){n0=ns[i0];nodes[n0].x=st.final[n0].x;nodes[n0].y=st.final[n0].y;}
      render();fitView();return;
    }
    var t0=null,DUR=1800;
    function frame(ts){
      if(t0===null)t0=ts;
      var p=Math.min(1,(ts-t0)/DUR);
      var e=p<0.5?2*p*p:-1+(4-2*p)*p;
      var i,n,sp,fp;
      for(i=0;i<ns.length;i++){
        n=ns[i];sp=startPos[n];fp=st.final[n];
        nodes[n].x=sp.x+(fp.x-sp.x)*e;
        nodes[n].y=sp.y+(fp.y-sp.y)*e;
      }
      render();
      if(p<1){window.__animId=requestAnimationFrame(frame);}
      else{fitView();}
    }
    window.__animId=requestAnimationFrame(frame);
    setTimeout(function(){
      var i,n,fp;
      for(i=0;i<ns.length;i++){
        n=ns[i];fp=st.final[n];
        nodes[n].x=fp.x;nodes[n].y=fp.y;
      }
      render();fitView();
    },2600);
  }

  var setStatus=document.getElementById('set-status');
  function loadSettings(){
    j('/settings').then(function(s){
      document.getElementById('set-base').value=s.llm_base_url||'';
      document.getElementById('set-model').value=s.llm_model||'';
      document.getElementById('set-key').value='';
      document.getElementById('set-key').placeholder=s.has_key?tf('key_configured_ph',{masked:s.api_key_masked}):t('key_empty');
      setStatus.textContent=s.llm_available?tf('llm_enabled_model',{model:s.llm_model||''}):t('llm_disabled');
      setStatus.className='set-status'+(s.llm_available?' ok':'');
    }).catch(function(){setStatus.textContent=t('settings_fail');setStatus.className='set-status';});
  }
  loadSettings();
  document.getElementById('set-save').onclick=function(){
    var body={
      llm_base_url:document.getElementById('set-base').value.trim(),
      llm_model:document.getElementById('set-model').value.trim(),
      api_key:document.getElementById('set-key').value.trim()
    };
    p('/settings',body).then(function(r){
      setStatus.textContent=r.llm_available?t('saved_llm'):t('saved');
      setStatus.className='set-status ok';
      document.getElementById('set-key').value='';
      loadSettings();
    }).catch(function(){setStatus.textContent=t('save_fail');setStatus.className='set-status';});
  };
})();
</script>
</body>
</html>
"""


def mount_dashboard(app: FastAPI, kernel: SylvaKernel) -> None:
    """把唯讀看板端點掛到 FastAPI 應用上。"""

    @app.get("/", include_in_schema=False)
    def dashboard() -> Response:
        return Response(content=DASHBOARD_HTML, media_type="text/html; charset=utf-8")

    @app.get("/rings")
    def list_rings(limit: int = Query(default=500, ge=1, le=2000)) -> dict:
        return {"rings": kernel.store.list_rings(limit=limit)}

    @app.get("/stats")
    def stats() -> dict:
        return kernel.store.stats()

    @app.get("/checkpoint")
    def latest_checkpoint() -> dict | None:
        cp = kernel.store.get_latest_checkpoint()
        if cp is None:
            return None
        return {"session_id": cp[0], "context": cp[1]}
