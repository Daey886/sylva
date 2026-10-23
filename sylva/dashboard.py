"""Sylva 唯讀看板：輕量單頁 Web UI，瀏覽核心記憶 / 年輪 / 斷點。

零前端框架、零新增依賴——單個自包含 HTML（內聯 CSS/JS），fetch 只讀
端點渲染。與三原語（Inject/Ingest/Ring）無關，純外圍查看，不寫資料庫。

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
</style>
</head>
<body>
<header>
  <h1>🌳 Sylva 記憶看板</h1>
  <div class="stats" id="stats"></div>
</header>
<nav class="tabs">
  <button class="tab active" data-tab="cores">🌰 核心記憶</button>
  <button class="tab" data-tab="rings">🪵 年輪</button>
  <button class="tab" data-tab="checkpoint">📌 斷點</button>
</nav>
<main>
  <section id="panel-cores" class="panel active"></section>
  <section id="panel-rings" class="panel"></section>
  <section id="panel-checkpoint" class="panel"></section>
</main>
<script>
async function j(u){const r=await fetch(u);if(!r.ok)throw 0;return r.json();}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function fmtTime(t){return t?new Date(t*1000).toLocaleString('zh-Hant'):'';}

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
      '<div class="stat"><b>'+s.rings+'</b><span>年輪</span></div>'+
      '<div class="stat"><b>'+s.cores+'</b><span>核心記憶</span></div>'+
      '<div class="stat"><b>'+s.checkpoints+'</b><span>斷點</span></div>'+
      '<div class="stat"><b>'+(s.db_bytes/1024).toFixed(1)+'KB</b><span>資料庫</span></div>';
  }).catch(function(){document.getElementById('stats').textContent='載入統計失敗';});

  j('/core').then(function(c){
    var cores=c.cores||{};
    var ks=Object.keys(cores);
    document.getElementById('panel-cores').innerHTML='<h2>🌰 核心記憶（'+ks.length+'）</h2>'+(ks.length?
      ks.map(function(k){return '<div class="card"><div class="meta">'+esc(k)+'</div><div class="content">'+esc(cores[k])+'</div></div>';}).join(''):
      '<div class="empty">尚無核心記憶</div>');
  }).catch(function(){document.getElementById('panel-cores').textContent='載入失敗';});

  j('/rings?limit=500').then(function(r){
    var rings=r.rings||[];
    rings.sort(function(a,b){return (order[a.ring_type]??9)-(order[b.ring_type]??9)||b.created_at-a.created_at;});
    document.getElementById('panel-rings').innerHTML='<h2>🪵 年輪（'+rings.length+'）</h2>'+(rings.length?
      rings.map(function(x){return '<div class="card"><div class="meta"><span class="tag '+esc(x.ring_type)+'">'+esc(x.ring_type)+'</span>imp='+Number(x.importance).toFixed(2)+' · '+fmtTime(x.created_at)+'</div><div class="content">'+esc(x.content)+'</div></div>';}).join(''):
      '<div class="empty">尚無年輪</div>');
  }).catch(function(){document.getElementById('panel-rings').textContent='載入失敗';});

  j('/checkpoint').then(function(cp){
    document.getElementById('panel-checkpoint').innerHTML='<h2>📌 斷點</h2>'+(cp?
      '<div class="card"><div class="meta">'+esc(cp.session_id)+'</div><div class="content">'+esc(cp.context)+'</div></div>':
      '<div class="empty">尚無斷點</div>');
  }).catch(function(){document.getElementById('panel-checkpoint').textContent='載入失敗';});
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
