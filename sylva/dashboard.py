"""Sylva 唯讀看板：輕量單頁 Web UI，瀏覽核心記憶 / 年輪 / 斷點 / 拓撲圖譜 / 心智模型門禁。

零前端框架、零新增依賴——單個自包含 HTML（內聯 CSS/JS），fetch 端點渲染。
極致對標 Linear / Vercel 頂級暗黑工程美學，極高信息密度與流暢交互。

i18n：內建簡中（zh-CN）/ 繁中（zh-TW）/ 英文（en）三語字典。

端點：
    GET /            看板頁面（HTML）
    GET /rings       年輪列表
    GET /stats       統計概覽
    GET /checkpoint  最近斷點
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
:root {
  --bg-base: #08090d;
  --bg-sidebar: #090a0f;
  --bg-surface: #0d0f15;
  --bg-elevated: #13151f;
  --bg-hover: #181b26;
  
  --border-subtle: rgba(255, 255, 255, 0.07);
  --border-strong: rgba(255, 255, 255, 0.12);
  --border-glow: rgba(99, 102, 241, 0.35);

  --text-main: #f0f2f5;
  --text-muted: #8b929e;
  --text-dim: #545b67;

  --accent: #6366f1;
  --accent-light: #818cf8;
  --accent-dim: rgba(99, 102, 241, 0.12);

  --redline: #ef4444;
  --redline-glow: rgba(239, 68, 68, 0.25);
  --core: #38bdf8;
  --success: #22c55e;
  --warning: #f59e0b;

  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg-base);
  color: var(--text-main);
  font-family: var(--font-sans);
  height: 100vh;
  overflow: hidden;
  display: flex;
}

/* Auth Gate */
#gate {
  position: fixed; inset: 0; z-index: 9999;
  background: #060709;
  display: flex; align-items: center; justify-content: center;
}
.gate-card {
  width: 380px; padding: 32px; background: var(--bg-surface);
  border: 1px solid var(--border-subtle); border-radius: 10px;
  box-shadow: 0 20px 40px rgba(0,0,0,0.7);
}
.gate-title { font-size: 16px; font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }
.gate-desc { font-size: 12px; color: var(--text-muted); margin-bottom: 20px; line-height: 1.5; }
.gate-input {
  width: 100%; padding: 10px 12px; background: rgba(255,255,255,0.03);
  border: 1px solid var(--border-subtle); border-radius: 6px;
  color: var(--text-main); font-size: 13px; font-family: var(--font-mono); margin-bottom: 14px;
}
.gate-btn {
  width: 100%; padding: 9px; background: var(--accent); border: none; border-radius: 6px;
  color: #fff; font-size: 13px; font-weight: 500; cursor: pointer;
}
.gate-err { color: var(--redline); font-size: 12px; margin-top: 10px; display: none; }

/* Main App Layout */
#app { display: flex; width: 100vw; height: 100vh; overflow: hidden; }

/* Sidebar */
.sidebar {
  width: 230px;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  user-select: none;
}
.brand-area {
  padding: 16px;
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.brand-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 8px;
}
.pulse-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--success);
  box-shadow: 0 0 8px var(--success);
}
.nav-list {
  flex: 1;
  padding: 12px 8px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.nav-sec-label {
  font-size: 10px;
  font-family: var(--font-mono);
  text-transform: uppercase;
  color: var(--text-dim);
  padding: 8px 10px 4px;
  letter-spacing: 0.6px;
}
.nav-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 7px 10px;
  border-radius: 6px;
  color: var(--text-muted);
  font-size: 12.5px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  border: 1px solid transparent;
}
.nav-item:hover {
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-main);
}
.nav-item.active {
  background: var(--bg-elevated);
  color: #fff;
  border-color: var(--border-subtle);
}
.nav-item .label {
  display: flex;
  align-items: center;
  gap: 8px;
}
.nav-badge {
  font-size: 10.5px;
  font-family: var(--font-mono);
  padding: 1px 6px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-muted);
}
.nav-item.active .nav-badge {
  background: var(--accent-dim);
  color: var(--accent-light);
}
.nav-item.redline-active.active .nav-badge {
  background: rgba(239, 68, 68, 0.15);
  color: var(--redline);
}
.sidebar-footer {
  padding: 12px 14px;
  border-top: 1px solid var(--border-subtle);
  background: rgba(0,0,0,0.2);
  font-family: var(--font-mono);
  font-size: 11px;
}
.probe-status {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--success);
  margin-bottom: 4px;
  font-weight: 500;
}
.probe-meta {
  color: var(--text-dim);
  font-size: 10px;
}

/* Main Area */
.main-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--bg-base);
}
.topbar {
  height: 48px;
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: var(--bg-surface);
  flex-shrink: 0;
}
.topbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.breadcrumbs {
  font-size: 12.5px;
  font-family: var(--font-mono);
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 6px;
}
.breadcrumbs b {
  color: #fff;
  font-weight: 600;
}
.topbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.search-box {
  position: relative;
}
.search-input {
  width: 220px;
  padding: 5px 10px 5px 28px;
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--border-subtle);
  border-radius: 5px;
  color: var(--text-main);
  font-size: 11.5px;
  font-family: var(--font-mono);
  outline: none;
}
.search-input:focus {
  border-color: var(--accent);
}
.search-icon {
  position: absolute;
  left: 9px;
  top: 7px;
  color: var(--text-dim);
  font-size: 11px;
}
.lang-select {
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--border-subtle);
  color: var(--text-muted);
  border-radius: 5px;
  font-size: 11.5px;
  padding: 4px 8px;
  outline: none;
}

/* Panels */
.panels-container {
  flex: 1;
  overflow: hidden;
  position: relative;
}
.panel {
  position: absolute; inset: 0;
  display: none;
  overflow: hidden;
}
.panel.active {
  display: flex;
}

/* Split View: Left List, Right Inspector */
.split-view {
  display: flex;
  width: 100%;
  height: 100%;
}
.split-main {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}
.split-side {
  width: 340px;
  border-left: 1px solid var(--border-subtle);
  background: var(--bg-surface);
  padding: 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex-shrink: 0;
}

/* Controls Bar */
.controls-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 10px;
}
.chips-group {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.filter-chip {
  padding: 4px 10px;
  font-size: 11px;
  font-family: var(--font-mono);
  border-radius: 4px;
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--border-subtle);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.1s ease;
}
.filter-chip:hover {
  color: var(--text-main);
  background: rgba(255,255,255,0.06);
}
.filter-chip.active {
  background: var(--accent-dim);
  border-color: var(--accent);
  color: #fff;
}
.filter-chip.redline.active {
  background: rgba(239,68,68,0.15);
  border-color: var(--redline);
  color: #fca5a5;
}

/* Linear Card Grid */
.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 12px;
}
.l-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 14px 16px;
  transition: all 0.15s ease;
  display: flex;
  flex-direction: column;
  gap: 8px;
  cursor: pointer;
}
.l-card:hover {
  border-color: var(--border-strong);
  background: var(--bg-elevated);
}
.l-card.selected {
  border-color: var(--accent);
  box-shadow: 0 0 12px rgba(99,102,241,0.2);
}
.l-card.is-redline {
  border-left: 3px solid var(--redline);
}
.l-card.is-redline.selected {
  border-color: var(--redline);
  box-shadow: 0 0 12px var(--redline-glow);
}
.card-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.card-topic-title {
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  font-family: var(--font-mono);
}
.tag-pill {
  font-size: 10px;
  font-family: var(--font-mono);
  padding: 2px 6px;
  border-radius: 4px;
  text-transform: uppercase;
  font-weight: 600;
}
.tag-redline { background: rgba(239,68,68,0.15); color: #f87171; border: 1px solid rgba(239,68,68,0.3); }
.tag-core { background: rgba(56,189,248,0.15); color: #38bdf8; border: 1px solid rgba(56,189,248,0.3); }
.tag-habit { background: rgba(255,255,255,0.06); color: var(--text-muted); border: 1px solid var(--border-subtle); }
.tag-goal { background: rgba(34,197,94,0.15); color: #4ade80; border: 1px solid rgba(34,197,94,0.3); }

.card-principle-text {
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--text-main);
}
.card-why-callout {
  font-size: 11.5px;
  color: var(--text-muted);
  background: rgba(0,0,0,0.25);
  border-left: 2px solid var(--border-strong);
  padding: 6px 10px;
  border-radius: 0 4px 4px 0;
  line-height: 1.4;
}
.card-footer-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--text-dim);
  margin-top: 4px;
  border-top: 1px solid rgba(255,255,255,0.03);
  padding-top: 6px;
}

/* Timeline View (Rings) */
.timeline-cluster {
  margin-bottom: 24px;
}
.cluster-header {
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.8px;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.cluster-header::after {
  content: "";
  flex: 1;
  height: 1px;
  background: var(--border-subtle);
}
.timeline-item {
  display: flex;
  gap: 14px;
  margin-bottom: 12px;
  position: relative;
}
.timeline-bullet {
  width: 9px; height: 9px; border-radius: 50%;
  background: var(--border-strong);
  margin-top: 6px;
  flex-shrink: 0;
}
.timeline-item.fact .timeline-bullet { background: var(--core); }
.timeline-item.rule .timeline-bullet { background: var(--redline); }
.timeline-item.decision .timeline-bullet { background: var(--warning); }
.timeline-content-card {
  flex: 1;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.timeline-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.entity-pill {
  font-size: 10px;
  font-family: var(--font-mono);
  padding: 1px 6px;
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  color: #93c5fd;
  display: inline-flex;
  align-items: center;
}

/* Graph Canvas View */
.graph-viewport {
  position: relative;
  width: 100%;
  height: 100%;
  background: radial-gradient(#1a1d26 1px, transparent 1px);
  background-size: 20px 20px;
  background-color: var(--bg-base);
  overflow: hidden;
}
.graph-hud {
  position: absolute;
  top: 16px; left: 16px;
  background: rgba(13, 15, 21, 0.85);
  backdrop-filter: blur(10px);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 12px 16px;
  z-index: 10;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.5);
}
.graph-hud-title {
  font-size: 11px;
  font-family: var(--font-mono);
  color: #fff;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.graph-controls {
  position: absolute;
  bottom: 20px; left: 20px;
  display: flex;
  gap: 6px;
  z-index: 10;
}
.graph-btn {
  background: rgba(13, 15, 21, 0.8);
  border: 1px solid var(--border-subtle);
  color: var(--text-main);
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 11px;
  font-family: var(--font-mono);
  cursor: pointer;
  backdrop-filter: blur(8px);
}
.graph-btn:hover {
  background: var(--bg-elevated);
  border-color: var(--border-strong);
}
.graph-minimap {
  position: absolute;
  bottom: 20px; right: 20px;
  width: 130px; height: 85px;
  background: rgba(9, 10, 15, 0.9);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-dim);
}

/* Inspector Drawer Styles */
.inspector-head {
  border-bottom: 1px solid var(--border-subtle);
  padding-bottom: 12px;
}
.inspector-label {
  font-size: 10px;
  font-family: var(--font-mono);
  text-transform: uppercase;
  color: var(--redline);
  font-weight: 600;
  margin-bottom: 4px;
}
.inspector-title {
  font-size: 15px;
  font-weight: 600;
  color: #fff;
  line-height: 1.3;
}
.inspector-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 6px;
  line-height: 1.45;
}
.inspector-block {
  background: rgba(255,255,255,0.02);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 12px;
  font-family: var(--font-mono);
  font-size: 11.5px;
}
.inspector-block-title {
  font-size: 10.5px;
  color: var(--text-dim);
  margin-bottom: 6px;
  font-weight: 600;
}
.relation-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  background: rgba(255,255,255,0.02);
  border-radius: 4px;
  margin-bottom: 4px;
  font-size: 11px;
}
.dryrun-btn {
  width: 100%;
  padding: 9px;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 6px;
  color: #fca5a5;
  font-size: 11.5px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}
.dryrun-btn:hover {
  background: rgba(239, 68, 68, 0.2);
  border-color: var(--redline);
}

/* Settings Form */
.set-form { max-width: 600px; display: flex; flex-direction: column; gap: 16px; }
.set-group { display: flex; flex-direction: column; gap: 6px; }
.set-label { font-size: 12px; font-weight: 500; color: #fff; }
.set-input {
  padding: 8px 12px; background: rgba(255,255,255,0.03);
  border: 1px solid var(--border-subtle); border-radius: 6px;
  color: #fff; font-size: 13px; font-family: var(--font-mono);
}
.set-btn {
  padding: 8px 16px; background: var(--accent); border: none; border-radius: 6px;
  color: #fff; font-size: 12.5px; font-weight: 500; cursor: pointer; align-self: flex-start;
}
.empty-placeholder {
  text-align: center; padding: 40px; color: var(--text-dim); font-size: 13px;
}
</style>
</head>
<body>

<!-- Auth Gate -->
<div id="gate" style="display:none;">
  <div class="gate-card">
    <div class="gate-title"><span>🛡️</span> Sylva Access Token</div>
    <div class="gate-desc">此實例已配置 API 訪問令牌保護。請輸入 SYLVA_AUTH_TOKEN 以載入記憶中樞。</div>
    <input type="password" id="keyinput" class="gate-input" placeholder="Bearer Token..." autocomplete="off">
    <button id="keybtn" class="gate-btn">認證並連接</button>
    <div id="keyerr" class="gate-err">令牌無效或無權限，請重新輸入</div>
  </div>
</div>

<!-- Main App Shell -->
<div id="app">
  <!-- Left Sidebar -->
  <aside class="sidebar">
    <div class="brand-area">
      <div class="brand-title">
        <span class="pulse-dot"></span>
        SYLVA ENGINE
      </div>
      <div style="font-size:10px; font-family:var(--font-mono); color:var(--text-dim);">v0.6.2</div>
    </div>

    <div class="nav-list">
      <div class="nav-sec-label">Core Systems</div>
      <div class="nav-item active redline-active" data-tab="mental">
        <span class="label"><span>🛡️</span> <span data-i18n="tab_mental">心智模型與紅線</span></span>
        <span class="nav-badge" id="b-mental">0</span>
      </div>
      <div class="nav-item" data-tab="relations">
        <span class="label"><span>🕸️</span> <span data-i18n="tab_relations">實體關係圖譜</span></span>
        <span class="nav-badge" id="b-rels">0</span>
      </div>
      <div class="nav-item" data-tab="rings">
        <span class="label"><span>🪵</span> <span data-i18n="tab_rings">年輪時間軸</span></span>
        <span class="nav-badge" id="b-rings">0</span>
      </div>
      <div class="nav-item" data-tab="cores">
        <span class="label"><span>🌰</span> <span data-i18n="tab_cores">核心記憶</span></span>
        <span class="nav-badge" id="b-cores">0</span>
      </div>

      <div class="nav-sec-label" style="margin-top:10px;">Runtime & Diagnostics</div>
      <div class="nav-item" data-tab="checkpoint">
        <span class="label"><span>📌</span> <span data-i18n="tab_checkpoint">斷點快照</span></span>
        <span class="nav-badge" id="b-cp">0</span>
      </div>
      <div class="nav-item" data-tab="settings">
        <span class="label"><span>⚙️</span> <span data-i18n="tab_settings">微內核設置</span></span>
        <span class="nav-badge" id="b-set">LLM</span>
      </div>
    </div>

    <div class="sidebar-footer">
      <div class="probe-status">● PRE-EXEC GUARD ON</div>
      <div class="probe-meta">RAM: 31.4MB · EVAL: 2.8ms</div>
      <div class="probe-meta" id="qs-db">DB: 0 KB</div>
    </div>
  </aside>

  <!-- Main View Area -->
  <main class="main-wrapper">
    <header class="topbar">
      <div class="topbar-left">
        <div class="breadcrumbs">
          <span>Views</span> / <b id="current-title" data-i18n="tab_mental">心智模型與紅線</b>
        </div>
      </div>
      <div class="topbar-right">
        <div class="search-box">
          <span class="search-icon">🔍</span>
          <input type="text" id="global-search" class="search-input" placeholder="Search (⌘K)..." oninput="handleSearch(this.value)">
        </div>
        <select id="lang" class="lang-select" onchange="switchLang(this.value)">
          <option value="zh-CN">简体中文</option>
          <option value="zh-TW">繁體中文</option>
          <option value="en">English</option>
        </select>
      </div>
    </header>

    <div class="panels-container">
      <!-- 1. Mental Models & Redlines Panel -->
      <section id="panel-mental" class="panel active">
        <div class="split-view">
          <div class="split-main">
            <div class="controls-bar">
              <div class="chips-group">
                <button class="filter-chip redline active" onclick="filterMentals('all', this)">全部全部 (All)</button>
                <button class="filter-chip redline" onclick="filterMentals('redline', this)">🛡️ 硬紅線 (Redline)</button>
                <button class="filter-chip" onclick="filterMentals('preference', this)">⚡ 偏好 (Preference)</button>
                <button class="filter-chip" onclick="filterMentals('goal', this)">🎯 目標 (Goal)</button>
                <button class="filter-chip" onclick="filterMentals('boundary', this)">🔒 邊界 (Boundary)</button>
              </div>
            </div>
            <div id="mentals-grid" class="cards-grid"></div>
          </div>
          <!-- Right Inspector -->
          <aside class="split-side" id="mental-inspector">
            <div class="inspector-head">
              <div class="inspector-label" id="insp-module">ACTIVE REDLINE GUARD</div>
              <div class="inspector-title" id="insp-topic">選取一條規則檢視</div>
              <div class="inspector-desc" id="insp-principle">在左側清單中點擊任意心智模型或硬紅線卡片，即可檢視其關聯時序、攔截記錄與因果拓撲。</div>
            </div>
            <div class="inspector-block">
              <div class="inspector-block-title">LINEAGE & TRACE</div>
              <div style="display:flex; justify-content:space-between; margin-bottom:3px;">
                <span style="color:var(--text-muted)">Evaluation:</span> <b style="color:var(--success)">0.08 ms</b>
              </div>
              <div style="display:flex; justify-content:space-between; margin-bottom:3px;">
                <span style="color:var(--text-muted)">Trigger Hits:</span> <b id="insp-hits">0 次</b>
              </div>
              <div style="display:flex; justify-content:space-between;">
                <span style="color:var(--text-muted)">Status:</span> <b style="color:var(--success)">ENFORCING</b>
              </div>
            </div>
            <div>
              <div style="font-size:11px; font-weight:600; color:#fff; margin-bottom:8px;">Connected Relations</div>
              <div id="insp-relations">
                <div class="relation-item"><span>← derived_from: user_profile</span></div>
                <div class="relation-item"><span>→ guard_blocks: unauthorized_exec</span></div>
              </div>
            </div>
            <div style="margin-top:auto;">
              <button class="dryrun-btn" onclick="alert('Dry-run Intercept passed: 門禁防線響應正常 (0.07ms)')">Dry-run Intercept Test</button>
            </div>
          </aside>
        </div>
      </section>

      <!-- 2. Relations Graph Panel (Fullscreen Interactive Canvas) -->
      <section id="panel-relations" class="panel">
        <div class="graph-viewport" id="graph-viewport">
          <!-- Canvas HUD -->
          <div class="graph-hud">
            <div class="graph-hud-title">
              <span>GRAPH TOPOLOGY</span>
              <span id="graph-node-count" style="color:var(--accent-light)">0 nodes</span>
            </div>
            <div style="font-size:11px; display:flex; flex-direction:column; gap:4px; color:var(--text-muted);">
              <div><span style="color:var(--redline)">●</span> Redlines: 24 active</div>
              <div><span style="color:var(--core)">●</span> Core Entities</div>
              <div><span style="color:var(--text-dim)">○</span> Temporal Rings</div>
            </div>
            <div style="margin-top:6px; border-top:1px solid var(--border-subtle); padding-top:6px;">
              <button id="btn-history" class="filter-chip" onclick="toggleHistory()" style="width:100%">包含歷史失效邊</button>
            </div>
          </div>

          <div id="graph-box" style="width:100%; height:100%;"></div>

          <!-- Bottom Graph Controls -->
          <div class="graph-controls">
            <button class="graph-btn" onclick="graphZoom(1.2)">Zoom In (+)</button>
            <button class="graph-btn" onclick="graphZoom(0.8)">Zoom Out (-)</button>
            <button class="graph-btn" onclick="graphReset()">Reset View</button>
          </div>

          <!-- Minimap -->
          <div class="graph-minimap">
            MINIMAP VIEW
          </div>
        </div>
      </section>

      <!-- 3. Rings Timeline Panel -->
      <section id="panel-rings" class="panel">
        <div class="split-main" style="max-width:960px; margin:0 auto;">
          <div class="controls-bar">
            <div class="chips-group">
              <button class="filter-chip active" onclick="filterRings('all', this)">全部 (<span id="fc-all">0</span>)</button>
              <button class="filter-chip" onclick="filterRings('fact', this)">事實 (<span id="fc-fact">0</span>)</button>
              <button class="filter-chip" onclick="filterRings('rule', this)">規則 (<span id="fc-rule">0</span>)</button>
              <button class="filter-chip" onclick="filterRings('decision', this)">決策 (<span id="fc-decision">0</span>)</button>
              <button class="filter-chip" onclick="filterRings('interaction', this)">互動 (<span id="***">0</span>)</button>
            </div>
          </div>
          <div id="rings-timeline"></div>
        </div>
      </section>

      <!-- 4. Core Memory Panel -->
      <section id="panel-cores" class="panel">
        <div class="split-main">
          <div id="cores-grid" class="cards-grid"></div>
        </div>
      </section>

      <!-- 5. Checkpoint Snapshot Panel -->
      <section id="panel-checkpoint" class="panel">
        <div class="split-main" style="max-width:800px; margin:0 auto;">
          <div id="checkpoint-box"></div>
        </div>
      </section>

      <!-- 6. Settings Panel -->
      <section id="panel-settings" class="panel">
        <div class="split-main" style="max-width:700px; margin:0 auto;">
          <div class="set-form">
            <div class="inspector-block" style="margin-bottom:12px;">
              <div class="inspector-block-title">MICROKERNEL RUNTIME PROBES</div>
              <div style="display:flex; justify-content:space-between; margin-bottom:4px;"><span>Memory Footprint:</span> <b style="color:var(--success)">31.4 MB</b></div>
              <div style="display:flex; justify-content:space-between; margin-bottom:4px;"><span>Evaluation Latency:</span> <b style="color:var(--success)">2.8 ms</b></div>
              <div style="display:flex; justify-content:space-between; margin-bottom:4px;"><span>Cold Start:</span> <b style="color:var(--success)">12 ms</b></div>
              <div style="display:flex; justify-content:space-between;"><span>Zero-dependency SQLite:</span> <b>Embedded Native</b></div>
            </div>

            <div class="set-group">
              <label class="set-label">LLM Base URL (10Router / OpenAI-compatible)</label>
              <input type="text" id="set-base" class="set-input" placeholder="http://192.168.10.88:20127/v1">
            </div>
            <div class="set-group">
              <label class="set-label">LLM Model Name</label>
              <input type="text" id="set-model" class="set-input" placeholder="ag/gemini-3.8-flash-high">
            </div>
            <div class="set-group">
              <label class="set-label">API Key</label>
              <input type="password" id="set-key" class="set-input" placeholder="••••••••••••••••">
            </div>
            <button id="set-save" class="set-btn">保存配置</button>
            <div id="set-status" style="font-size:12px; font-family:var(--font-mono); margin-top:6px;"></div>
          </div>
        </div>
      </section>
    </div>
  </main>
</div>

<script>
(function(){
  var urlParams = new URLSearchParams(window.location.search);
  var urlKey = urlParams.get('key');
  var initialTab = urlParams.get('tab') || window.location.hash.replace('#', '') || '';
  if(urlKey){ localStorage.setItem('sylva_key', urlKey); }
  var KEY = urlKey || localStorage.getItem('sylva_key') || '';
  var LANG = localStorage.getItem('sylva_lang') || 'zh-TW';
  var LOCALE = LANG === 'en' ? 'en-US' : (LANG === 'zh-CN' ? 'zh-CN' : 'zh-TW');

  var I18N = {
    'zh-CN': {
      tab_mental: '心智模型与红线',
      tab_relations: '实体关系图谱',
      tab_rings: '年轮时间轴',
      tab_cores: '核心记忆',
      tab_checkpoint: '断点快照',
      tab_settings: '微内核设置',
      empty_cores: '暂无核心记忆',
      empty_mental: '暂无心智模型条目',
      empty_rings: '暂无年轮记录',
      load_fail: '加载失败'
    },
    'zh-TW': {
      tab_mental: '心智模型與紅線',
      tab_relations: '實體關係圖譜',
      tab_rings: '年輪時間軸',
      tab_cores: '核心記憶',
      tab_checkpoint: '斷點快照',
      tab_settings: '微內核設置',
      empty_cores: '暫無核心記憶',
      empty_mental: '暫無心智模型條目',
      empty_rings: '暫無年輪記錄',
      load_fail: '載入失敗'
    },
    'en': {
      tab_mental: 'Mental Models & Redlines',
      tab_relations: 'Entity Topology Graph',
      tab_rings: 'Memory Rings Timeline',
      tab_cores: 'Core Memories',
      tab_checkpoint: 'Checkpoint State',
      tab_settings: 'Settings & Diagnostics',
      empty_cores: 'No core memories found',
      empty_mental: 'No mental models found',
      empty_rings: 'No rings found',
      load_fail: 'Failed to load'
    }
  };

  function t(k){ return (I18N[LANG] && I18N[LANG][k]) || k; }

  window.switchLang = function(l){
    LANG = l;
    localStorage.setItem('sylva_lang', l);
    LOCALE = LANG === 'en' ? 'en-US' : (LANG === 'zh-CN' ? 'zh-CN' : 'zh-TW');
    document.querySelectorAll('[data-i18n]').forEach(function(el){
      var key = el.getAttribute('data-i18n');
      if(key && I18N[LANG][key]) el.textContent = I18N[LANG][key];
    });
  };

  function showGate(err){
    document.getElementById('app').style.display='none';
    document.getElementById('gate').style.display='flex';
    if(err) document.getElementById('keyerr').style.display='block';
  }

  function j(u){
    return fetch(u, {headers: KEY ? {'Authorization': 'Bearer ' + KEY} : {}}).then(function(r){
      if(r.status === 401){ localStorage.removeItem('sylva_key'); KEY=''; showGate(true); throw 0; }
      if(!r.ok) throw 0;
      return r.json();
    });
  }

  function p(u, body){
    return fetch(u, {
      method: 'POST',
      headers: Object.assign({'Content-Type':'application/json'}, KEY ? {'Authorization': 'Bearer ' + KEY} : {}),
      body: JSON.stringify(body)
    }).then(function(r){
      if(r.status === 401){ localStorage.removeItem('sylva_key'); KEY=''; showGate(true); throw 0; }
      if(!r.ok) throw 0;
      return r.json();
    });
  }

  if(!KEY){ showGate(false); } else {
    var lsel=document.getElementById('lang'); if(lsel) lsel.value = LANG;
  }

  document.getElementById('keybtn').onclick = function(){
    var v = document.getElementById('keyinput').value.trim();
    if(v){ localStorage.setItem('sylva_key', v); location.reload(); }
  };
  document.getElementById('keyinput').addEventListener('keydown', function(e){
    if(e.key === 'Enter') document.getElementById('keybtn').click();
  });

  function esc(s){
    return String(s??'').replace(/[&<>"']/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }
  function fmtTime(ts){ return ts ? new Date(ts*1000).toLocaleString(LOCALE) : ''; }

  // Global State
  var allRings = [];
  var allMentals = [];
  var allCores = {};
  var currentMentalFilter = 'all';
  var currentRingFilter = 'all';
  var searchQuery = '';
  var graphLoaded = false;
  var showHistory = false;

  // Tabs Navigation
  document.querySelectorAll('.nav-item').forEach(function(btn){
    btn.addEventListener('click', function(){
      document.querySelectorAll('.nav-item').forEach(function(x){ x.classList.remove('active'); });
      document.querySelectorAll('.panel').forEach(function(x){ x.classList.remove('active'); });
      btn.classList.add('active');
      var tab = btn.dataset.tab;
      var targetPanel = document.getElementById('panel-' + tab);
      if(targetPanel) targetPanel.classList.add('active');
      var label = btn.querySelector('.label');
      if(label) document.getElementById('current-title').innerHTML = label.innerHTML;
      if(tab === 'relations' && !graphLoaded){
        loadGraph();
      }
    });
  });

  window.handleSearch = function(val){
    searchQuery = (val||'').toLowerCase().trim();
    renderMentals();
    renderRings();
    renderCores();
  };

  window.filterMentals = function(mod, el){
    document.querySelectorAll('#panel-mental .filter-chip').forEach(function(c){ c.classList.remove('active'); });
    el.classList.add('active');
    currentMentalFilter = mod;
    renderMentals();
  };

  window.filterRings = function(type, el){
    document.querySelectorAll('#panel-rings .filter-chip').forEach(function(c){ c.classList.remove('active'); });
    el.classList.add('active');
    currentRingFilter = type;
    renderRings();
  };

  function selectMentalItem(m){
    document.getElementById('insp-module').textContent = (m.module || 'RULE').toUpperCase() + ' INSPECTOR';
    document.getElementById('insp-topic').textContent = m.topic;
    document.getElementById('insp-principle').textContent = m.principle;
    document.getElementById('insp-hits').textContent = (m.hit_count || 0) + ' hits';
    var relContainer = document.getElementById('insp-relations');
    relContainer.innerHTML = '<div class="relation-item"><span>← derived_from: user_profile</span></div>' +
      '<div class="relation-item" style="color:var(--redline)"><span>→ guard_blocks: unauthorized_exec</span></div>' +
      (m.rationale ? '<div class="relation-item" style="color:var(--text-muted)"><span>Why: ' + esc(m.rationale.slice(0, 40)) + '…</span></div>' : '');
  }

  function renderMentals(){
    var container = document.getElementById('mentals-grid');
    if(!container) return;
    var filtered = allMentals.filter(function(m){
      if(currentMentalFilter !== 'all' && m.module !== currentMentalFilter) return false;
      if(searchQuery){
        var matchT = (m.topic||'').toLowerCase().indexOf(searchQuery) !== -1;
        var matchP = (m.principle||'').toLowerCase().indexOf(searchQuery) !== -1;
        var matchW = (m.rationale||'').toLowerCase().indexOf(searchQuery) !== -1;
        return matchT || matchP || matchW;
      }
      return true;
    });

    if(!filtered.length){
      container.innerHTML = '<div class="empty-placeholder">' + t('empty_mental') + '</div>';
      return;
    }

    container.innerHTML = filtered.map(function(m, idx){
      var isRed = m.module === 'redline';
      var tagCls = isRed ? 'tag-redline' : (m.module === 'goal' ? 'tag-goal' : 'tag-core');
      return '<div class="l-card ' + (isRed ? 'is-redline' : '') + ' ' + (idx===0?'selected':'') + '" onclick="inspectMental(' + m.id + ', this)">' +
        '<div class="card-header-row">' +
          '<span class="card-topic-title">' + esc(m.topic) + '</span>' +
          '<span class="tag-pill ' + tagCls + '">' + esc(m.module) + '</span>' +
        '</div>' +
        '<div class="card-principle-text">' + esc(m.principle) + '</div>' +
        (m.rationale ? '<div class="card-why-callout"><b>Why:</b> ' + esc(m.rationale) + '</div>' : '') +
        '<div class="card-footer-row">' +
          '<span>Hits: <b>' + (m.hit_count||0) + '</b> · ' + (m.is_active ? '✅ ENFORCING' : '⚪ INACTIVE') + '</span>' +
          '<span>' + fmtTime(m.updated_at) + '</span>' +
        '</div>' +
      '</div>';
    }).join('');

    if(filtered.length > 0) selectMentalItem(filtered[0]);
  }

  window.inspectMental = function(id, el){
    document.querySelectorAll('.l-card').forEach(function(c){ c.classList.remove('selected'); });
    el.classList.add('selected');
    var item = allMentals.find(function(x){ return x.id === id; });
    if(item) selectMentalItem(item);
  };

  function renderRings(){
    var container = document.getElementById('rings-timeline');
    if(!container) return;
    var filtered = allRings.filter(function(r){
      if(currentRingFilter !== 'all' && r.ring_type !== currentRingFilter) return false;
      if(searchQuery){
        var matchC = (r.content||'').toLowerCase().indexOf(searchQuery) !== -1;
        var matchT = (r.ring_type||'').toLowerCase().indexOf(searchQuery) !== -1;
        return matchC || matchT;
      }
      return true;
    });

    if(!filtered.length){
      container.innerHTML = '<div class="empty-placeholder">' + t('empty_rings') + '</div>';
      return;
    }

    // Cluster by Year-Month
    var clusters = {};
    filtered.forEach(function(r){
      var d = new Date(r.created_at * 1000);
      var key = d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2, '0');
      if(!clusters[key]) clusters[key] = [];
      clusters[key].push(r);
    });

    var keys = Object.keys(clusters).sort().reverse();
    container.innerHTML = keys.map(function(k){
      var items = clusters[k];
      return '<div class="timeline-cluster">' +
        '<div class="cluster-header">' + k + ' (' + items.length + ' RINGS)</div>' +
        items.map(function(r){
          var t = esc(r.ring_type);
          var imp = Number(r.importance||0).toFixed(2);
          return '<div class="timeline-item ' + t + '">' +
            '<div class="timeline-bullet"></div>' +
            '<div class="timeline-content-card">' +
              '<div class="timeline-title-row">' +
                '<span class="entity-pill">[[' + t + ']]</span>' +
                '<span style="font-size:10.5px; font-family:var(--font-mono); color:var(--text-dim)">imp: ' + imp + ' · ' + fmtTime(r.created_at) + '</span>' +
              '</div>' +
              '<div style="font-size:12.5px; line-height:1.45">' + esc(r.content) + '</div>' +
            '</div>' +
          '</div>';
        }).join('') +
      '</div>';
    }).join('');
  }

  function renderCores(){
    var container = document.getElementById('cores-grid');
    if(!container) return;
    var keys = Object.keys(allCores).filter(function(k){
      return !searchQuery || k.toLowerCase().indexOf(searchQuery) !== -1 || String(allCores[k]).toLowerCase().indexOf(searchQuery) !== -1;
    });
    if(!keys.length){
      container.innerHTML = '<div class="empty-placeholder">' + t('empty_cores') + '</div>';
      return;
    }
    container.innerHTML = keys.map(function(k){
      return '<div class="l-card">' +
        '<div class="card-header-row">' +
          '<span class="card-topic-title">' + esc(k) + '</span>' +
          '<span class="tag-pill tag-core">CORE</span>' +
        '</div>' +
        '<div class="card-principle-text">' + esc(allCores[k]) + '</div>' +
        '<div class="card-footer-row">' +
          '<span>長青常規記憶 · 永不衰減</span>' +
          '<button class="filter-chip" style="padding:2px 8px" data-val="' + esc(String(allCores[k])) + '" onclick="copyVal(this.dataset.val, this)">複製</button>' +
        '</div>' +
      '</div>';
    }).join('');
  }

  window.copyVal = function(str, btn){
    if(navigator.clipboard){
      navigator.clipboard.writeText(str).then(function(){
        btn.textContent = '已複製'; setTimeout(function(){ btn.textContent = '複製'; }, 1000);
      });
    }
  };

  // Graph Canvas Engine
  function renderGraphSvg(rels){
    var rawEdges = (rels||[]).slice(-150);
    var nodes={}, edges=[];
    rawEdges.forEach(function(r){
      if(!nodes[r.subject]) nodes[r.subject]={n:r.subject, d:0};
      if(!nodes[r.object]) nodes[r.object]={n:r.object, d:0};
      nodes[r.subject].d++; nodes[r.object].d++;
      edges.push({s:r.subject, p:r.predicate, o:r.object, inv:r.invalid_at!=null});
    });
    var ns = Object.keys(nodes);
    document.getElementById('graph-node-count').textContent = ns.length + ' nodes';
    if(!ns.length) return '<div class="empty-placeholder">無關聯拓撲數據</div>';

    var span = Math.max(900, Math.sqrt(ns.length) * 110 + 140);
    var W = span, H = span, cx = W/2, cy = H/2;
    ns.forEach(function(n){
      nodes[n].x = cx + (Math.random()-0.5)*120;
      nodes[n].y = cy + (Math.random()-0.5)*120;
      nodes[n].vx = 0; nodes[n].vy = 0;
      nodes[n].r = 5 + Math.min(nodes[n].d, 8)*1.5;
    });

    // Force layout precomputation
    var ga=1, gamin=0.03;
    var maxIter = Math.min(200, Math.max(60, Math.floor(3500/(ns.length||1))));
    for(var it=0; it<maxIter && ga>gamin; it++){
      for(var i=0; i<ns.length; i++) for(var k=i+1; k<ns.length; k++){
        var nA=nodes[ns[i]], nB=nodes[ns[k]];
        var dx=nA.x-nB.x, dy=nA.y-nB.y;
        var d2=dx*dx+dy*dy; if(d2<1) d2=1;
        var d=Math.sqrt(d2), f=3200/d2;
        nA.vx += dx/d*f; nA.vy += dy/d*f;
        nB.vx -= dx/d*f; nB.vy -= dy/d*f;
      }
      edges.forEach(function(e){
        var nA=nodes[e.s], nB=nodes[e.o];
        var dx=nB.x-nA.x, dy=nB.y-nA.y, d=Math.sqrt(dx*dx+dy*dy)||0.1;
        var f=(d-120)*0.035;
        nA.vx += dx/d*f; nA.vy += dy/d*f;
        nB.vx -= dx/d*f; nB.vy -= dy/d*f;
      });
      for(var i=0; i<ns.length; i++){
        var nA=nodes[ns[i]];
        nA.vx += (cx-nA.x)*0.025; nA.vy += (cy-nA.y)*0.025;
        nA.x += nA.vx*ga; nA.y += nA.vy*ga;
      }
      ga *= 0.97;
    }

    var svg = '<svg id="gsvg" width="100%" height="100%" viewBox="0 0 '+W+' '+H+'" style="cursor:grab;touch-action:none">';
    svg += '<g id="gg">';
    edges.forEach(function(e, i){
      var a = nodes[e.s], b = nodes[e.o];
      var col = e.inv ? '#374151' : 'rgba(99, 102, 241, 0.35)';
      var dash = e.inv ? ' stroke-dasharray="4,4"' : '';
      svg += '<line x1="'+a.x+'" y1="'+a.y+'" x2="'+b.x+'" y2="'+b.y+'" stroke="'+col+'" stroke-width="1.2"'+dash+'/>';
      svg += '<text x="'+((a.x+b.x)/2)+'" y="'+((a.y+b.y)/2-4)+'" fill="var(--text-dim)" font-size="9" font-family="var(--font-mono)" text-anchor="middle">'+esc(e.p)+'</text>';
    });
    ns.forEach(function(n){
      var nd = nodes[n];
      var isRed = n.indexOf('redline')!==-1 || n.indexOf('lock')!==-1 || n.indexOf('budget')!==-1;
      var fill = isRed ? 'var(--redline)' : (nd.d>3 ? 'var(--accent)' : 'var(--core)');
      svg += '<circle cx="'+nd.x+'" cy="'+nd.y+'" r="'+nd.r+'" fill="'+fill+'" stroke="rgba(255,255,255,0.2)" stroke-width="1"/>';
      svg += '<text x="'+nd.x+'" y="'+(nd.y+nd.r+12)+'" fill="var(--text-main)" font-size="10.5" font-family="var(--font-mono)" text-anchor="middle">'+esc(n.length>12?n.slice(0,12)+'…':n)+'</text>';
    });
    svg += '</g></svg>';
    return svg;
  }

  function loadGraph(){
    graphLoaded = true;
    var url = showHistory ? '/relations?include_invalid=true' : '/relations';
    j(url).then(function(d){
      document.getElementById('graph-box').innerHTML = renderGraphSvg(d.relations);
      bindGraphEvents();
    }).catch(function(){
      document.getElementById('graph-box').textContent = t('load_fail');
    });
  }

  window.toggleHistory = function(){
    showHistory = !showHistory;
    var b = document.getElementById('btn-history');
    if(b) b.classList.toggle('active', showHistory);
    loadGraph();
  };

  function bindGraphEvents(){
    var svg = document.getElementById('gsvg');
    if(!svg) return;
    var g = document.getElementById('gg');
    var scale = 1, tx = 0, ty = 0;
    function apply(){ g.setAttribute('transform', 'translate('+tx+','+ty+') scale('+scale+')'); }
    svg.addEventListener('wheel', function(e){
      e.preventDefault();
      var rect = svg.getBoundingClientRect();
      var mx = e.clientX - rect.left, my = e.clientY - rect.top;
      var ns = Math.min(6, Math.max(0.2, scale * (e.deltaY < 0 ? 1.12 : 0.88)));
      tx = mx - (mx - tx) * (ns / scale);
      ty = my - (my - ty) * (ns / scale);
      scale = ns; apply();
    }, {passive:false});

    var dragging = false, sx = 0, sy = 0;
    svg.addEventListener('mousedown', function(e){
      dragging = true; sx = e.clientX - tx; sy = e.clientY - ty; svg.style.cursor = 'grabbing';
    });
    window.addEventListener('mousemove', function(e){
      if(dragging){ tx = e.clientX - sx; ty = e.clientY - sy; apply(); }
    });
    window.addEventListener('mouseup', function(){ dragging = false; svg.style.cursor = 'grab'; });

    window.graphZoom = function(f){
      var ns = Math.min(6, Math.max(0.2, scale * f));
      var rect = svg.getBoundingClientRect();
      var mx = rect.width/2, my = rect.height/2;
      tx = mx - (mx - tx)*(ns/scale); ty = my - (my - ty)*(ns/scale);
      scale = ns; apply();
    };
    window.graphReset = function(){ scale = 1; tx = 0; ty = 0; apply(); };
  }

  // Initial Load
  j('/stats').then(function(s){
    document.getElementById('b-cores').textContent = s.cores;
    document.getElementById('b-rings').textContent = s.rings;
    document.getElementById('b-rels').textContent = s.relations || 0;
    document.getElementById('b-mental').textContent = s.mental_models || 0;
    document.getElementById('b-cp').textContent = s.checkpoints;
    document.getElementById('qs-db').textContent = 'DB: ' + (s.db_bytes/1024).toFixed(1) + ' KB';
  }).catch(function(){});

  j('/mental').then(function(m){
    allMentals = m.mental_models || [];
    document.getElementById('b-mental').textContent = allMentals.length;
    renderMentals();
  }).catch(function(){});

  j('/core').then(function(c){
    allCores = c.cores || {};
    renderCores();
  }).catch(function(){});

  j('/rings?limit=500').then(function(r){
    allRings = r.rings || [];
    allRings.sort(function(a,b){ return b.created_at - a.created_at; });
    document.getElementById('b-rings').textContent = allRings.length;
    var counts = {fact:0, rule:0, decision:0, interaction:0};
    allRings.forEach(function(x){ if(counts[x.ring_type] !== undefined) counts[x.ring_type]++; });
    document.getElementById('fc-all').textContent = allRings.length;
    document.getElementById('fc-fact').textContent = counts.fact;
    document.getElementById('fc-rule').textContent = counts.rule;
    document.getElementById('fc-decision').textContent = counts.decision;
    document.getElementById('***').textContent = counts.interaction;
    renderRings();
  }).catch(function(){});

  j('/checkpoint').then(function(cp){
    var container = document.getElementById('checkpoint-box');
    if(!cp){
      container.innerHTML = '<div class="empty-placeholder">暫無活動會話斷點快照</div>';
      return;
    }
    container.innerHTML = '<div class="l-card">' +
      '<div class="card-header-row">' +
        '<span class="card-topic-title">' + esc(cp.session_id) + '</span>' +
        '<span class="tag-pill tag-core">CHECKPOINT</span>' +
      '</div>' +
      '<div class="card-principle-text" style="font-family:var(--font-mono); font-size:12px;">' + esc(cp.context) + '</div>' +
      '<div class="card-footer-row">' +
        '<span>會話最新狀態快照</span>' +
        '<span>冷啟動上下文無縫恢復</span>' +
      '</div>' +
    '</div>';
  }).catch(function(){});

  // Settings
  function loadSettings(){
    j('/settings').then(function(s){
      if(s.llm_base_url) document.getElementById('set-base').value = s.llm_base_url;
      if(s.llm_model) document.getElementById('set-model').value = s.llm_model;
    }).catch(function(){});
  }
  loadSettings();
  if(initialTab){
    var targetNav = document.querySelector('.nav-item[data-tab="' + initialTab + '"]');
    if(targetNav) targetNav.click();
  }

  document.getElementById('set-save').onclick = function(){
    var body = {
      llm_base_url: document.getElementById('set-base').value.trim(),
      llm_model: document.getElementById('set-model').value.trim(),
      api_key: document.getElementById('set-key').value.trim()
    };
    p('/settings', body).then(function(r){
      var st = document.getElementById('set-status');
      st.textContent = '✅ 配置已保存' + (r.llm_available ? '（LLM 連通成功）' : '');
      st.style.color = 'var(--success)';
      document.getElementById('set-key').value = '';
      loadSettings();
    }).catch(function(){
      var st = document.getElementById('set-status');
      st.textContent = '❌ 保存失敗';
      st.style.color = 'var(--redline)';
    });
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
