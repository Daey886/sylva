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
  saved:'✅ 已保存',saved_llm:'✅ 已保存，LLM 已啟用',save_fail:'保存失敗，請檢查密鑰',
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
  saved:'✅ 已保存',saved_llm:'✅ 已保存，LLM 已启用',save_fail:'保存失败，请检查密钥',
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
  saved:'✅ Saved',saved_llm:'✅ Saved, LLM enabled',save_fail:'Save failed, check key',
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
      edges.push({s:r.subject,p:r.predicate,o:r.object});
    });
    var ns=Object.keys(nodes);
    if(!ns.length)return '<div class="empty">'+t('empty_relations')+'</div>';
    var W=640,H=400,cx=W/2,cy=H/2,R=Math.min(W,H)/2-50;
    ns.forEach(function(n,i){var a=2*Math.PI*i/ns.length;nodes[n].x=cx+R*Math.cos(a);nodes[n].y=cy+R*Math.sin(a);});
    var disp={};ns.forEach(function(n){disp[n]={x:0,y:0};});
    for(var it=0;it<140;it++){
      ns.forEach(function(n){disp[n].x=0;disp[n].y=0;});
      for(var i=0;i<ns.length;i++)for(var j=i+1;j<ns.length;j++){
        var a=nodes[ns[i]],b=nodes[ns[j]],dx=a.x-b.x,dy=a.y-b.y,d=Math.sqrt(dx*dx+dy*dy)||1,f=900/(d*d);
        disp[ns[i]].x+=dx/d*f;disp[ns[i]].y+=dy/d*f;
        disp[ns[j]].x-=dx/d*f;disp[ns[j]].y-=dy/d*f;
      }
      edges.forEach(function(e){
        var a=nodes[e.s],b=nodes[e.o],dx=b.x-a.x,dy=b.y-a.y,d=Math.sqrt(dx*dx+dy*dy)||1,f=(d-90)*0.03;
        disp[e.s].x+=dx/d*f;disp[e.s].y+=dy/d*f;
        disp[e.o].x-=dx/d*f;disp[e.o].y-=dy/d*f;
      });
      ns.forEach(function(n){
        nodes[n].x+=disp[n].x*0.6;nodes[n].y+=disp[n].y*0.6;
        nodes[n].x=Math.max(18,Math.min(W-18,nodes[n].x));
        nodes[n].y=Math.max(18,Math.min(H-18,nodes[n].y));
      });
    }
    var svg='<svg width="100%" viewBox="0 0 '+W+' '+H+'" style="display:block">';
    edges.forEach(function(e){
      var a=nodes[e.s],b=nodes[e.o];
      svg+='<line x1="'+a.x+'" y1="'+a.y+'" x2="'+b.x+'" y2="'+b.y+'" stroke="#2f4538" stroke-width="1.5"/>';
      svg+='<text x="'+((a.x+b.x)/2)+'" y="'+((a.y+b.y)/2)+'" fill="#8aa899" font-size="10" text-anchor="middle">'+esc(e.p)+'</text>';
    });
    ns.forEach(function(n){
      svg+='<circle cx="'+nodes[n].x+'" cy="'+nodes[n].y+'" r="'+(4+nodes[n].d*2)+'" fill="#6fd49a"/>';
      svg+='<text x="'+nodes[n].x+'" y="'+(nodes[n].y+20)+'" fill="#dce6e0" font-size="11" text-anchor="middle">'+esc(n)+'</text>';
    });
    return svg+'</svg>';
  }
  j('/relations').then(function(d){
    document.getElementById('graph-box').innerHTML=renderGraph(d.relations);
  }).catch(function(){document.getElementById('graph-box').textContent=t('load_fail');});

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
