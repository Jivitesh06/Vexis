/* ================================================================
   dashboard.js — Vexis Dashboard Content
   All 9 sections + sidebar section loaders
   ================================================================ */

import {
  apiGet, apiPost, apiPut, apiDelete, showToast,
  animateNumber, getBadgeClass,
  initRevealAnimations, getUser, setAuth,
  updateOBDStatusBanner,
  API_BASE
} from './api.js';

import {
  auth,
  updatePassword,
  EmailAuthProvider,
  reauthenticateWithCredential,
  updateProfile as firebaseUpdateProfile,
  db, collection, addDoc, getDocs, getDoc, setDoc, updateDoc, query, where, deleteDoc, doc, orderBy, serverTimestamp
} from './firebase.js';

import {
  isWebSerialSupported,
  connectOBDSerial,
  disconnectOBD    as serialDisconnect,
  startLiveStream,
  startAnalysis,
  cancelAnalysis,
  getStatus        as getSerialStatus
} from './obd_serial.js';


// ── Live polling state ─────────────────────────────────────────────
let metricsHistory = {};
let liveCharts     = {};
let pollingTimer   = null;
let currentReportId = null;

// ── Mock data (used when OBD disconnected) ─────────────────────────
function mockMetrics() {
  const rpm   = 800 + Math.random() * 2200;
  const speed = 0  + Math.random() * 80;
  return {
    rpm:           Math.round(rpm),
    speed:         Math.round(speed),
    load:          20 + Math.random() * 60,
    maf:           3  + Math.random() * 12,
    stft:          -5 + Math.random() * 10,
    ltft:          -3 + Math.random() * 6,
    oat:           18 + Math.random() * 15,
    coolant_temp:  80 + Math.random() * 30,
    throttle_pos:  5  + Math.random() * 70,
    intake_temp:   25 + Math.random() * 20
  };
}

function mockScores() {
  return {
    overall_score: 72 + Math.random() * 18,
    category:      'Good',
    component_scores: {
      engine:    68 + Math.random() * 22,
      fuel:      74 + Math.random() * 18,
      efficiency:70 + Math.random() * 20,
      driving:   80 + Math.random() * 15,
      thermal:   75 + Math.random() * 18
    },
    issues: [
      'Short-term fuel trim anomaly detected',
      'Engine load slightly elevated at idle'
    ],
    report_id: null
  };
}

// ── Score color helper ─────────────────────────────────────────────
function scoreColor(s) {
  if (s >= 90) return 'var(--success)';
  if (s >= 75) return 'var(--accent)';
  if (s >= 60) return 'var(--warning)';
  if (s >= 40) return 'var(--accent2)';
  return 'var(--danger)';
}
function scoreLabel(s) {
  if (s >= 90) return 'Excellent';
  if (s >= 75) return 'Good';
  if (s >= 60) return 'Fair';
  if (s >= 40) return 'Poor';
  return 'Critical';
}
function riskBadge(pct) {
  if (pct < 25) return '<span class="badge badge-good">LOW</span>';
  if (pct < 55) return '<span class="badge badge-fair">MEDIUM</span>';
  return '<span class="badge badge-critical">HIGH</span>';
}

// ══════════════════════════════════════════════════════════════════
//  SECTION 0 — OBD Connect Banner
// ══════════════════════════════════════════════════════════════════
function renderOBDConnect(status) {
  const connected = status?.connected;
  const port      = status?.port || '';
  return `
  <div class="glass-card obd-connect-card reveal" style="margin-bottom:20px">
    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px">
      <div style="display:flex;align-items:center;gap:12px">
        <div style="width:12px;height:12px;border-radius:50%;background:${connected ? 'var(--success)' : 'var(--danger)'};
             box-shadow:0 0 8px ${connected ? 'var(--success)' : 'var(--danger)'}${connected ? ';animation:dotPulse 1.5s infinite' : ''}"></div>
        <div>
          <div style="font-family:var(--font-display);font-size:15px;color:var(--text);font-weight:700">
            ${connected ? '✅ OBD Scanner Connected' : '🔌 No OBD Scanner Detected'}
          </div>
          <div style="font-size:12px;color:var(--muted);margin-top:2px">
            ${connected ? `Port: ${port} &nbsp;|&nbsp; Live data streaming` : 'Connect your USB ELM327 OBD-II scanner to begin'}
          </div>
        </div>
      </div>
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        ${connected ? `
          <button id="obd-run-btn" class="btn-primary" onclick="window._runFullAnalysis()">⚡ Run Full Analysis</button>
          <button class="btn-outline" style="padding:10px 18px" onclick="window._disconnectOBD()">Disconnect</button>
        ` : `
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
            <input id="obd-port-input" type="text" placeholder="COM port (auto)" style="
              background:rgba(255,255,255,0.05);border:1px solid var(--glass-border);
              border-radius:var(--radius-sm);padding:9px 14px;color:var(--text);
              font-family:var(--font-body);font-size:13px;width:150px"/>
            <button id="obd-connect-btn" class="btn-primary" onclick="window._connectOBD()">🔌 Connect OBD Scanner</button>
          </div>
        `}
      </div>
    </div>
  </div>`;
}

// ══════════════════════════════════════════════════════════════════
//  SECTION 1 — Vehicle Info
// ══════════════════════════════════════════════════════════════════
function renderVehicleInfo() {
  const now = new Date().toLocaleString();
  return `
  <div class="glass-card slide-top reveal" style="padding:28px;margin-bottom:20px">
    <div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap">
      <div style="color:var(--accent);flex-shrink:0">
        <svg viewBox="0 0 64 64" fill="none" width="64" height="64">
          <path d="M8 36H4a2 2 0 0 1-2-2V24a2 2 0 0 1 2-2h36l10 10v6a2 2 0 0 1-2 2h-4" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
          <circle cx="16" cy="40" r="6" stroke="currentColor" stroke-width="2.5"/>
          <circle cx="48" cy="40" r="6" stroke="currentColor" stroke-width="2.5"/>
          <path d="M10 22l6-12h24l6 12" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
        </svg>
      </div>
      <div style="flex:1">
        <div style="font-family:var(--font-display);font-size:18px;font-weight:700;color:var(--accent);margin-bottom:4px">Vehicle Scanner Active</div>
        <div style="font-size:13px;color:var(--muted)">VIN: OBD-AUTO-DETECT</div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:20px">
        ${['Last Scan','Data Points','Scanner'].map((k,i) => `
          <div style="text-align:center">
            <div style="font-size:11px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-bottom:4px">${k}</div>
            <div style="font-family:var(--font-display);font-size:13px;color:var(--text);font-weight:600">${[now,'Live Stream','ELM327 USB'][i]}</div>
          </div>`).join('')}
      </div>
    </div>
  </div>`;
}

// ══════════════════════════════════════════════════════════════════
//  SECTION 2 — Health Gauge
// ══════════════════════════════════════════════════════════════════
function renderHealthGauge(score, category) {
  const clr    = scoreColor(score);
  const angle  = -90 + (score / 100) * 180;
  const r      = 90;
  const cx = 150, cy = 155;
  const totalLen = Math.PI * r;
  const dash     = (score / 100) * totalLen;
  const descMap  = {
    Excellent: 'Peak performance — your vehicle is in top shape.',
    Good:      'Minor optimizations recommended.',
    Fair:      'Several areas need attention soon.',
    Poor:      'Significant issues detected — service recommended.',
    Critical:  'Immediate service required — critical faults found.'
  };
  return `
  <div class="glass-card reveal" style="padding:32px;text-align:center;margin-bottom:20px">
    <div style="font-family:var(--font-display);font-size:13px;color:var(--muted);letter-spacing:2px;text-transform:uppercase;margin-bottom:20px">Overall Vehicle Health</div>
    <div class="gauge-container">
      <svg viewBox="0 0 300 175" style="width:100%;max-width:340px;overflow:visible">
        <defs>
          <linearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#ff1744"/>
            <stop offset="40%" stop-color="#ffea00"/>
            <stop offset="70%" stop-color="#00e5ff"/>
            <stop offset="100%" stop-color="#00e676"/>
          </linearGradient>
        </defs>
        <!-- bg arc -->
        <path d="M30 155 A90 90 0 0 1 270 155" stroke="rgba(255,255,255,0.06)" stroke-width="18" fill="none" stroke-linecap="round"/>
        <!-- score arc -->
        <path id="gauge-arc" d="M30 155 A90 90 0 0 1 270 155"
          stroke="url(#gaugeGrad)" stroke-width="18" fill="none" stroke-linecap="round"
          stroke-dasharray="${totalLen}" stroke-dashoffset="${totalLen}"
          style="transition:stroke-dashoffset 1.6s cubic-bezier(0.34,1.2,0.64,1)"/>
        <!-- tick marks -->
        ${[0,25,50,75,100].map(v => {
          const a = (-90 + v * 1.8) * Math.PI / 180;
          const x1 = cx + (r-5)*Math.cos(a), y1 = cy + (r-5)*Math.sin(a);
          const x2 = cx + (r+8)*Math.cos(a), y2 = cy + (r+8)*Math.sin(a);
          return `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" stroke="rgba(255,255,255,0.25)" stroke-width="1.5"/>`;
        }).join('')}
        <!-- needle -->
        <line id="gauge-needle"
          x1="${cx}" y1="${cy}"
          x2="${cx}" y2="${cy - r + 12}"
          stroke="white" stroke-width="2.5" stroke-linecap="round"
          style="transform-origin:${cx}px ${cy}px;transform:rotate(-90deg);
                 transition:transform 1.6s cubic-bezier(0.34,1.2,0.64,1)"/>
        <!-- center dot -->
        <circle cx="${cx}" cy="${cy}" r="6" fill="${clr}" opacity="0.9"/>
        <circle cx="${cx}" cy="${cy}" r="3" fill="white"/>
        <!-- score text -->
        <text x="${cx}" y="${cy-20}" text-anchor="middle" font-family="Orbitron" font-size="36" font-weight="900" fill="${clr}" id="gauge-score-text">0</text>
        <text x="${cx}" y="${cy-4}" text-anchor="middle" font-family="Orbitron" font-size="13" fill="rgba(255,255,255,0.4)">/100</text>
      </svg>
    </div>
    <span class="badge ${getBadgeClass(category)}" style="font-size:14px;padding:8px 20px">${category}</span>
    <p style="color:var(--muted);font-size:14px;margin-top:12px">${descMap[category] || ''}</p>
  </div>`;
}

function animateGauge(score) {
  const arc    = document.getElementById('gauge-arc');
  const needle = document.getElementById('gauge-needle');
  const textEl = document.getElementById('gauge-score-text');
  if (!arc) return;
  const r = 90, total = Math.PI * r;
  setTimeout(() => {
    arc.style.strokeDashoffset = total - (score / 100) * total;
    if (needle) {
      const deg = -90 + (score / 100) * 180;
      needle.style.transform = `rotate(${deg}deg)`;
    }
    if (textEl) animateNumber(textEl, 0, score, 1600);
  }, 200);
}

// ══════════════════════════════════════════════════════════════════
//  SECTION 3 — Subsystem Scores
// ══════════════════════════════════════════════════════════════════
const ICONS = {
  engine:    `<path d="M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2z" stroke="currentColor" stroke-width="1.6"/><path d="M8 12h8M12 8v8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>`,
  fuel:      `<path d="M5 22V6l7-4 5 3v3l3 2v12H5z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M9 22v-6h6v6" stroke="currentColor" stroke-width="1.6"/>`,
  efficiency:`<path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>`,
  driving:   `<path d="M5 17H3a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h14l4 4v4a2 2 0 0 1-2 2h-2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><circle cx="7.5" cy="17.5" r="2.5" stroke="currentColor" stroke-width="1.6"/><circle cx="17.5" cy="17.5" r="2.5" stroke="currentColor" stroke-width="1.6"/>`,
  thermal:   `<path d="M12 2v12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M8 14a5 5 0 1 0 8 0" stroke="currentColor" stroke-width="1.6"/>`
};
const COMP_LABELS = { engine:'Engine Health', fuel:'Fuel System', efficiency:'Efficiency', driving:'Driving Behavior', thermal:'Thermal Health' };

function renderSubsystemScores(scores) {
  const cards = Object.entries(scores).map(([key, val]) => {
    const s   = Math.round(val);
    const clr = scoreColor(s);
    const lbl = scoreLabel(s);
    return `
    <div class="glass-card subsystem-card reveal" style="padding:22px;transition:transform 0.25s,border-color 0.25s">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
        <div style="color:${clr};width:22px;height:22px;flex-shrink:0">
          <svg viewBox="0 0 24 24" fill="none" width="22" height="22">${ICONS[key]||''}</svg>
        </div>
        <span style="font-size:13px;color:var(--muted);font-weight:600;letter-spacing:0.5px">${COMP_LABELS[key]||key}</span>
      </div>
      <div style="font-family:var(--font-display);font-size:32px;font-weight:900;color:${clr}" class="sub-score" data-val="${s}">0</div>
      <div style="height:6px;background:rgba(255,255,255,0.06);border-radius:3px;margin:12px 0;overflow:hidden">
        <div class="sub-bar" style="height:100%;width:0%;background:${clr};border-radius:3px;transition:width 1.2s cubic-bezier(0.34,1.2,0.64,1)" data-w="${s}"></div>
      </div>
      <div style="font-size:12px;color:${clr};font-weight:600">${lbl}</div>
    </div>`;
  }).join('');
  return `
  <div style="margin-bottom:20px">
    <div class="section-title">Subsystem Health</div>
    <div class="section-subtitle">AI-scored component analysis</div>
    <div class="subsystem-grid">${cards}</div>
  </div>`;
}

function animateSubsystems() {
  document.querySelectorAll('.sub-score').forEach(el => {
    animateNumber(el, 0, parseFloat(el.dataset.val), 1200);
  });
  setTimeout(() => {
    document.querySelectorAll('.sub-bar').forEach(el => {
      el.style.width = el.dataset.w + '%';
    });
  }, 100);
}

// ══════════════════════════════════════════════════════════════════
//  SECTION 4 — Live Metrics Tiles
// ══════════════════════════════════════════════════════════════════
const METRIC_DEFS = [
  { key:'rpm',          label:'RPM',          unit:'RPM',  icon:`<path d="M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2z" stroke="currentColor" stroke-width="1.5"/><path d="M12 8v4l3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>` },
  { key:'speed',        label:'Speed',         unit:'km/h', icon:`<path d="M5 17H3a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h14l4 4v4a2 2 0 0 1-2 2h-2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="7.5" cy="17.5" r="2.5" stroke="currentColor" stroke-width="1.5"/><circle cx="17.5" cy="17.5" r="2.5" stroke="currentColor" stroke-width="1.5"/>` },
  { key:'coolant_temp', label:'Coolant Temp',  unit:'°C',   icon:`<path d="M12 2v12M8 14a5 5 0 1 0 8 0" stroke="currentColor" stroke-width="1.5"/>` },
  { key:'load',         label:'Engine Load',   unit:'%',    icon:`<path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>` },
  { key:'throttle_pos', label:'Throttle',      unit:'%',    icon:`<circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.5"/><path d="M12 8v4l2 2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>` },
  { key:'stft',         label:'Fuel Trim',     unit:'%',    icon:`<path d="M5 22V6l7-4 5 3v3l3 2v12H5z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>` },
  { key:'intake_temp',  label:'Intake Temp',   unit:'°C',   icon:`<path d="M2 12h20M12 2v20" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>` }
];

function sparklinePath(vals) {
  if (!vals || vals.length < 2) return '';
  const min = Math.min(...vals), max = Math.max(...vals);
  const range = max - min || 1;
  const w = 60, h = 20;
  const pts = vals.map((v, i) => {
    const x = (i / (vals.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return `<svg viewBox="0 0 ${w} ${h}" style="width:60px;height:20px;display:block;margin:0 auto">
    <polyline points="${pts.join(' ')}" fill="none" stroke="var(--accent)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.7"/>
  </svg>`;
}

function renderLiveMetrics(metrics) {
  const tiles = METRIC_DEFS.map(d => {
    const val = metrics[d.key];
    const hist = metricsHistory[d.key] || [];
    const disp = val !== undefined ? parseFloat(val).toFixed(d.key === 'rpm' ? 0 : 1) : '--';
    return `
    <div class="metric-tile glass-card reveal">
      <div style="color:var(--muted);margin-bottom:6px">
        <svg viewBox="0 0 24 24" fill="none" width="18" height="18">${d.icon}</svg>
      </div>
      <div style="font-size:11px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-bottom:4px">${d.label}</div>
      <div class="metric-value" id="metric-${d.key}">${disp}</div>
      <div style="font-size:11px;color:var(--muted)">${d.unit}</div>
      <div style="margin-top:6px" id="spark-${d.key}">${sparklinePath(hist)}</div>
    </div>`;
  }).join('');
  return `
  <div style="margin-bottom:20px">
    <div class="section-title">Live Sensor Data</div>
    <div class="section-subtitle">Real-time OBD-II telemetry</div>
    <div class="metrics-grid">${tiles}</div>
  </div>`;
}

// ══════════════════════════════════════════════════════════════════
//  SECTION 5 — Charts
// ══════════════════════════════════════════════════════════════════
function makeChartData(base, range, count = 20) {
  return Array.from({length: count}, () => base + (Math.random() - 0.5) * range * 2);
}

function renderGraphs() {
  return `
  <div style="margin-bottom:20px">
    <div class="section-title">Performance Trends</div>
    <div class="section-subtitle">Historical sensor graphs — updating live</div>
    <div class="charts-grid">
      ${[
        {id:'chart-rpm',      label:'Engine RPM',       color:'#00e5ff'},
        {id:'chart-temp',     label:'Coolant Temp (°C)', color:'#ff6d00'},
        {id:'chart-load',     label:'Engine Load (%)',   color:'#7c4dff'},
        {id:'chart-throttle', label:'Throttle (%)',      color:'#00e676'}
      ].map(c => `
      <div class="chart-card glass-card reveal">
        <div style="font-size:12px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-bottom:12px">${c.label}</div>
        <canvas id="${c.id}" height="100"></canvas>
      </div>`).join('')}
    </div>
  </div>`;
}

function initCharts(metrics) {
  if (typeof Chart === 'undefined') return;
  const chartDefs = [
    {id:'chart-rpm',      base: metrics.rpm||900,        range:400,  color:'#00e5ff'},
    {id:'chart-temp',     base: metrics.coolant_temp||90,range:15,   color:'#ff6d00'},
    {id:'chart-load',     base: metrics.load||35,        range:20,   color:'#7c4dff'},
    {id:'chart-throttle', base: metrics.throttle_pos||30,range:20,   color:'#00e676'}
  ];
  const labels  = Array.from({length:20}, (_,i) => `-${19-i}s`);
  const gridClr = 'rgba(255,255,255,0.05)';
  const tickClr = '#6b7a99';

  chartDefs.forEach(c => {
    const canvas = document.getElementById(c.id);
    if (!canvas) return;
    if (liveCharts[c.id]) { liveCharts[c.id].destroy(); }
    liveCharts[c.id] = new Chart(canvas.getContext('2d'), {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data:          makeChartData(c.base, c.range),
          borderColor:   c.color,
          borderWidth:   2,
          pointRadius:   2,
          pointHoverRadius: 5,
          tension:       0.4,
          fill:          true,
          backgroundColor: c.color + '0d'
        }]
      },
      options: {
        animation: { duration: 800 },
        responsive: true,
        maintainAspectRatio: true,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: gridClr }, ticks: { color: tickClr, font: { size: 9 } } },
          y: { grid: { color: gridClr }, ticks: { color: tickClr, font: { size: 9 } } }
        }
      }
    });
  });
}

// ══════════════════════════════════════════════════════════════════
//  SECTION 6 — Alerts
// ══════════════════════════════════════════════════════════════════
function alertClass(txt) {
  const t = txt.toLowerCase();
  if (t.includes('critical'))                    return 'alert-critical';
  if (t.includes('high')||t.includes('stress'))  return 'alert-warning';
  if (t.includes('warning')||t.includes('trim')) return 'alert-warning';
  return 'alert-info';
}

function renderAlerts(issues) {
  const body = (!issues || issues.length === 0)
    ? `<div class="glass-card" style="padding:20px;border-left:4px solid var(--success);display:flex;align-items:center;gap:12px">
         <span style="font-size:24px">✅</span>
         <div><div style="color:var(--success);font-weight:600">No Issues Detected</div>
         <div style="font-size:13px;color:var(--muted)">Vehicle systems nominal.</div></div>
       </div>`
    : issues.map(txt => `
      <div class="alert-card glass-card ${alertClass(txt)}">
        <span style="font-size:20px">${alertClass(txt)==='alert-critical'?'🔴':alertClass(txt)==='alert-warning'?'⚠️':'ℹ️'}</span>
        <div style="flex:1">
          <div style="color:var(--text);font-size:14px;font-weight:500">${txt}</div>
        </div>
        <span class="badge ${alertClass(txt)==='alert-critical'?'badge-critical':alertClass(txt)==='alert-warning'?'badge-fair':'badge-good'}">
          ${alertClass(txt)==='alert-critical'?'CRITICAL':alertClass(txt)==='alert-warning'?'WARNING':'INFO'}
        </span>
      </div>`).join('');
  return `
  <div style="margin-bottom:20px">
    <div class="section-title">Detected Issues & Alerts</div>
    <div class="section-subtitle">Anomalies identified by AI diagnostics</div>
    ${body}
  </div>`;
}

// ══════════════════════════════════════════════════════════════════
//  SECTION 7 — Risk Predictions
// ══════════════════════════════════════════════════════════════════
function renderRiskPredictions(scores) {
  const risks = [
    { label:'Overheating Risk',       pct: Math.round(100 - (scores.thermal||75)),
      explain: (p) => p > 40 ? 'Thermal stress patterns suggest cooling system strain. Monitor coolant temperature.' : 'Thermal system operating within normal parameters.' },
    { label:'Engine Wear Risk',       pct: Math.round(100 - (scores.engine||75)),
      explain: (p) => p > 40 ? 'Elevated RPM variance and load patterns indicate potential engine wear.' : 'Engine operating within healthy parameters.' },
    { label:'Fuel Efficiency Loss',   pct: Math.round(100 - (scores.efficiency||75)),
      explain: (p) => p > 40 ? 'Fuel trim deviations and MAF irregularities suggest efficiency loss.' : 'Fuel system performing efficiently.' }
  ];
  const cards = risks.map(r => {
    const clr = r.pct < 25 ? 'var(--success)' : r.pct < 55 ? 'var(--warning)' : 'var(--danger)';
    return `
    <div class="glass-card reveal" style="padding:24px">
      <div style="font-size:12px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-bottom:12px">${r.label}</div>
      <div style="font-family:var(--font-display);font-size:40px;font-weight:900;color:${clr}">${r.pct}%</div>
      <div class="risk-bar"><div class="risk-fill" style="width:0%;background:${clr}" data-w="${r.pct}"></div></div>
      <p style="font-size:13px;color:var(--muted);font-style:italic;margin:8px 0">${r.explain(r.pct)}</p>
      ${riskBadge(r.pct)}
    </div>`;
  }).join('');
  return `
  <div style="margin-bottom:20px">
    <div class="section-title">Future Risk Predictions</div>
    <div class="section-subtitle">AI-powered failure probability</div>
    <div class="risk-grid">${cards}</div>
  </div>`;
}

// ══════════════════════════════════════════════════════════════════
//  SECTION 8 — Recommendations
// ══════════════════════════════════════════════════════════════════
function renderRecommendations(scores) {
  const recs = [];
  if ((scores.engine||100)    < 75) recs.push({icon:'🔧',title:'Engine Inspection Recommended',desc:'Schedule a comprehensive engine diagnostic with a certified mechanic.',priority:'HIGH',clr:'var(--danger)'});
  if ((scores.thermal||100)   < 75) recs.push({icon:'🌡️',title:'Cooling System Check',desc:'Coolant flush and thermostat inspection recommended.',priority:'HIGH',clr:'var(--danger)'});
  if ((scores.fuel||100)      < 75) recs.push({icon:'⛽',title:'Fuel System Service',desc:'Consider fuel injector cleaning and O2 sensor inspection.',priority:'MEDIUM',clr:'var(--warning)'});
  if ((scores.efficiency||100)< 75) recs.push({icon:'⚡',title:'Performance Optimization',desc:'Air filter replacement and MAF sensor cleaning may improve efficiency.',priority:'MEDIUM',clr:'var(--warning)'});
  if ((scores.driving||100)   < 75) recs.push({icon:'🚗',title:'Driving Behavior Advisory',desc:'Reducing aggressive acceleration can reduce engine wear by up to 30%.',priority:'LOW',clr:'var(--accent)'});

  const body = recs.length === 0
    ? `<div class="glass-card" style="padding:20px;border-left:4px solid var(--success);display:flex;gap:12px;align-items:center">
         <span style="font-size:24px">✅</span>
         <div><div style="color:var(--success);font-weight:600">No Immediate Service Required</div>
         <div style="font-size:13px;color:var(--muted)">Continue regular maintenance schedule.</div></div>
       </div>`
    : recs.map(r => `
      <div class="glass-card reveal" style="padding:20px;border-left:4px solid ${r.clr};margin-bottom:12px;display:flex;align-items:center;gap:16px;flex-wrap:wrap">
        <div style="font-size:28px">${r.icon}</div>
        <div style="flex:1">
          <div style="font-weight:700;color:var(--text);margin-bottom:4px">${r.title}</div>
          <div style="font-size:13px;color:var(--muted)">${r.desc}</div>
        </div>
        <span class="badge ${r.priority==='HIGH'?'badge-critical':r.priority==='MEDIUM'?'badge-fair':'badge-good'}">${r.priority}</span>
      </div>`).join('');
  return `
  <div style="margin-bottom:20px">
    <div class="section-title">Service Recommendations</div>
    <div class="section-subtitle">Based on your vehicle's current health data</div>
    ${body}
  </div>`;
}

// ══════════════════════════════════════════════════════════════════
//  SECTION 9 — Report Button
// ══════════════════════════════════════════════════════════════════
function renderReportButton(reportId) {
  return `
  <div class="glass-card reveal" style="padding:40px;text-align:center;margin-bottom:20px">
    <div style="color:var(--accent);margin-bottom:16px">
      <svg viewBox="0 0 24 24" fill="none" width="48" height="48">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z" stroke="currentColor" stroke-width="1.6"/>
        <path d="M14 2v6h6M12 17v-6M9 14l3 3 3-3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>
    <div style="font-family:var(--font-display);font-size:20px;font-weight:700;color:var(--text);margin-bottom:8px">Full Vehicle Health Report</div>
    <div style="font-size:14px;color:var(--muted);margin-bottom:28px">Complete diagnostic data, scores, issues and recommendations</div>
    <div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap">
      ${reportId
        ? `<button class="btn-primary" style="padding:14px 32px;font-size:15px"
               onclick="window.open('${API_BASE}/reports/download/${reportId}')">
             ⬇ Download PDF Report
           </button>
           <button class="btn-outline" style="padding:14px 24px"
               onclick="navigator.clipboard.writeText('${API_BASE}/reports/${reportId}').then(()=>window._showToast('Link copied!','success'))">
             🔗 Share Report
           </button>`
        : `<div style="color:var(--muted);font-size:14px">Run a full analysis to generate a report.</div>`}
    </div>
  </div>`;
}

// ══════════════════════════════════════════════════════════════════
//  OBD LIVE DASHBOARD — renderLiveDashboard()
//  Three-state analysis UI using Web Serial API
// ══════════════════════════════════════════════════════════════════
function renderLiveDashboard() {
  const supported = isWebSerialSupported();
  const circumference = 2 * Math.PI * 54; // 339.3

  return `
  <div style="margin-bottom:20px">
    <div class="section-title">Live OBD Dashboard</div>
    <div class="section-subtitle">Web Serial API — real data from your vehicle</div>
  </div>

  <!-- ─── OBD CONNECTION CARD ──────────────────────────────── -->
  <div class="glass-card reveal" id="obd-connection-card" style="padding:28px;margin-bottom:20px">
    ${!supported ? `
      <div style="display:flex;align-items:center;gap:16px;padding:16px;background:rgba(255,234,0,0.06);border:1px solid rgba(255,234,0,0.2);border-radius:var(--radius)">
        <span style="font-size:28px">⚠️</span>
        <div>
          <div style="color:var(--warning);font-weight:700;margin-bottom:4px">Browser Not Supported</div>
          <div style="font-size:13px;color:var(--muted)">Use Chrome or Edge browser for OBD connectivity via Web Serial API</div>
        </div>
      </div>
    ` : `
      <!-- Disconnected state -->
      <div id="obd-disconnected-view">
        <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
          <div style="flex-shrink:0;color:var(--muted)">
            <svg viewBox="0 0 24 24" fill="none" width="52" height="52">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" stroke="currentColor" stroke-width="1.4"/>
              <path d="M8 12h4m0 0l-2-2m2 2l-2 2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
              <path d="M15 9v6" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
            </svg>
          </div>
          <div style="flex:1">
            <div style="font-family:var(--font-display);font-size:17px;font-weight:700;color:var(--text);margin-bottom:6px">Connect OBD Scanner</div>
            <div style="font-size:13px;color:var(--muted);line-height:1.8">
              1. Plug USB ELM327 adapter into car OBD-II port<br>
              2. Click Connect below<br>
              3. Select COM port from the browser dialog
            </div>
          </div>
          <button id="connect-obd-btn" class="btn-primary" style="padding:13px 24px;font-size:14px;white-space:nowrap">
            🔌 Connect OBD Scanner
          </button>
        </div>
      </div>

      <!-- Connected state (hidden until connected) -->
      <div id="obd-connected-view" style="display:none">
        <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
          <div style="width:10px;height:10px;border-radius:50%;background:var(--success);box-shadow:0 0 8px var(--success);animation:dotPulse 1.5s infinite"></div>
          <div style="font-family:var(--font-display);font-size:15px;font-weight:700;color:var(--success)">OBD Scanner Connected</div>
          <button id="disconnect-obd-btn" class="btn-outline" style="padding:7px 16px;font-size:13px;margin-left:auto">
            🔌 Disconnect
          </button>
        </div>
      </div>
    `}
  </div>

  <!-- ─── LIVE METRICS (shown when connected) ───────────────── -->
  <div id="live-metrics-section" style="display:none;margin-bottom:20px">
    <div class="glass-card reveal" style="padding:24px">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;flex-wrap:wrap;gap:12px">
        <div class="live-indicator">
          <span class="live-dot"></span>
          LIVE OBD DATA
        </div>
        <span id="last-update-time" style="font-size:12px;color:var(--muted)">Waiting for data...</span>
      </div>
      <div class="metrics-grid">
        ${[
          { id:'val-rpm',      label:'RPM',         unit:'RPM',  icon:'M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2zM12 8v4l3 3' },
          { id:'val-speed',    label:'Speed',        unit:'km/h', icon:'M5 17H3a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h14l4 4v4a2 2 0 0 1-2 2h-2M7.5 17.5a2.5 2.5 0 1 0 5 0 2.5 2.5 0 0 0-5 0M14.5 17.5a2.5 2.5 0 1 0 5 0 2.5 2.5 0 0 0-5 0' },
          { id:'val-temp',     label:'Coolant',      unit:'°C',   icon:'M12 2v12M8 14a5 5 0 1 0 8 0' },
          { id:'val-load',     label:'Engine Load',  unit:'%',    icon:'M13 2L3 14h9l-1 8 10-12h-9l1-8z' },
          { id:'val-throttle', label:'Throttle',     unit:'%',    icon:'M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2zM12 8v4l2 2' },
          { id:'val-stft',     label:'Fuel Trim',    unit:'%',    icon:'M5 22V6l7-4 5 3v3l3 2v12H5z' },
          { id:'val-intake',   label:'Intake Temp',  unit:'°C',   icon:'M2 12h20M12 2v20' }
        ].map(m => `
          <div class="metric-tile glass-card">
            <div style="color:var(--muted);margin-bottom:6px">
              <svg viewBox="0 0 24 24" fill="none" width="18" height="18">
                <path d="${m.icon}" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
            <div style="font-size:11px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-bottom:4px">${m.label}</div>
            <div class="metric-value" id="${m.id}">--</div>
            <div style="font-size:11px;color:var(--muted)">${m.unit}</div>
          </div>
        `).join('')}
      </div>
    </div>
  </div>

  <!-- ─── HEALTH ANALYSIS CARD ──────────────────────────────── -->
  <div class="glass-card reveal" style="padding:32px;margin-bottom:20px">

    <!-- STATE 1: READY -->
    <div id="analysis-ready">
      <div style="text-align:center;margin-bottom:28px">
        <div style="font-size:52px;margin-bottom:12px">🔍</div>
        <div style="font-family:var(--font-display);font-size:20px;font-weight:700;color:var(--text);margin-bottom:8px">Vehicle Health Analysis</div>
        <div style="font-size:14px;color:var(--muted);max-width:460px;margin:0 auto">Collect real driving data for accurate ML-powered health scoring. Drive normally during collection.</div>
      </div>

      <!-- Duration Picker -->
      <div style="text-align:center;margin-bottom:20px">
        <div style="font-size:12px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-bottom:12px">Collection Duration</div>
        <div class="duration-picker">
          <button class="dur-btn" data-dur="60">1 min</button>
          <button class="dur-btn active" data-dur="120">2 min ⭐</button>
          <button class="dur-btn" data-dur="180">3 min</button>
        </div>
      </div>

      <!-- Tips box -->
      <div style="background:rgba(0,229,255,0.05);border:1px solid rgba(0,229,255,0.15);border-radius:var(--radius);padding:14px 18px;margin-bottom:24px;font-size:13px;color:var(--muted);text-align:center">
        💡 Best results: Drive at different speeds. Include some acceleration. City + highway mix is ideal.
      </div>

      <div style="text-align:center">
        <button id="start-analysis-btn" class="btn-primary" style="padding:14px 36px;font-size:15px" disabled>
          🔍 Start Health Analysis
        </button>
        <div style="font-size:12px;color:var(--muted);margin-top:10px" id="start-hint">Connect OBD scanner to enable</div>
      </div>
    </div>

    <!-- STATE 2: COLLECTING (hidden) -->
    <div id="analysis-collecting" style="display:none">
      <div style="text-align:center;margin-bottom:8px">
        <div style="font-family:var(--font-display);font-size:18px;font-weight:700;color:var(--accent)">Collecting Driving Data...</div>
        <div style="font-size:13px;color:var(--muted);margin-top:4px">Keep driving normally — the more varied, the better</div>
      </div>

      <!-- Circular progress -->
      <div class="circular-progress-wrap">
        <svg viewBox="0 0 120 120">
          <circle cx="60" cy="60" r="54" class="progress-bg"/>
          <circle cx="60" cy="60" r="54" class="progress-fill" id="progress-circle"
            style="stroke-dasharray:${circumference};stroke-dashoffset:${circumference}"/>
        </svg>
        <div class="progress-center">
          <div class="progress-time-text" id="progress-time">0s / 120s</div>
          <div style="font-size:11px;color:var(--muted);margin-top:2px">elapsed</div>
        </div>
      </div>

      <!-- Stats -->
      <div style="display:flex;justify-content:center;gap:32px;margin:16px 0;flex-wrap:wrap">
        <div style="text-align:center">
          <div style="font-size:11px;color:var(--muted);letter-spacing:1px;text-transform:uppercase">Readings</div>
          <div style="font-family:var(--font-display);font-size:22px;color:var(--accent);font-weight:700" id="progress-rows">0</div>
        </div>
      </div>

      <!-- Condition badges -->
      <div id="conditions-container" style="text-align:center;min-height:32px;margin:8px 0"></div>

      <!-- Rotating tip -->
      <div class="collection-tip" id="collection-tip" style="opacity:1">Drive normally for best results...</div>

      <div style="text-align:center;margin-top:20px">
        <button id="cancel-analysis-btn" class="btn-outline" style="padding:10px 24px">✕ Cancel Analysis</button>
      </div>
    </div>

    <!-- STATE 3: RESULTS (hidden) -->
    <div id="analysis-results" style="display:none">
      <div style="text-align:center;margin-bottom:24px">
        <div style="font-size:32px;margin-bottom:8px">✅</div>
        <div style="font-family:var(--font-display);font-size:20px;font-weight:700;color:var(--text)">Analysis Complete</div>
        <div style="font-size:13px;color:var(--muted);margin-top:4px" id="result-subtitle">Processing results...</div>
      </div>

      <!-- Overall gauge -->
      <div style="text-align:center;margin-bottom:28px">
        <div id="result-gauge" style="position:relative;display:inline-block">
          <svg viewBox="0 0 300 175" style="width:100%;max-width:300px;overflow:visible">
            <defs>
              <linearGradient id="resultGaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stop-color="#ff1744"/>
                <stop offset="40%" stop-color="#ffea00"/>
                <stop offset="70%" stop-color="#00e5ff"/>
                <stop offset="100%" stop-color="#00e676"/>
              </linearGradient>
            </defs>
            <path d="M30 155 A90 90 0 0 1 270 155" stroke="rgba(255,255,255,0.06)" stroke-width="18" fill="none" stroke-linecap="round"/>
            <path id="result-gauge-arc" d="M30 155 A90 90 0 0 1 270 155"
              stroke="url(#resultGaugeGrad)" stroke-width="18" fill="none" stroke-linecap="round"
              stroke-dasharray="${Math.PI * 90}" stroke-dashoffset="${Math.PI * 90}"
              style="transition:stroke-dashoffset 1.6s cubic-bezier(0.34,1.2,0.64,1)"/>
            <line id="result-gauge-needle" x1="150" y1="155" x2="150" y2="77"
              stroke="white" stroke-width="2.5" stroke-linecap="round"
              style="transform-origin:150px 155px;transform:rotate(-90deg);transition:transform 1.6s cubic-bezier(0.34,1.2,0.64,1)"/>
            <circle cx="150" cy="155" r="6" fill="var(--accent)" opacity="0.9"/>
            <circle cx="150" cy="155" r="3" fill="white"/>
            <text x="150" y="135" text-anchor="middle" font-family="Orbitron" font-size="36" font-weight="900" fill="var(--accent)" id="result-overall-score">0</text>
            <text x="150" y="151" text-anchor="middle" font-family="Orbitron" font-size="13" fill="rgba(255,255,255,0.4)">/100</text>
          </svg>
        </div>
        <div>
          <span class="badge badge-good" id="result-category">-</span>
        </div>
      </div>

      <!-- Component score grid -->
      <div class="result-component-grid">
        ${['engine','fuel','efficiency','driving','thermal'].map(c => `
          <div class="result-card glass-card">
            <div style="font-size:11px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-bottom:8px">${c.charAt(0).toUpperCase()+c.slice(1)}</div>
            <div class="result-score-num" id="score-${c}">0</div>
            <div class="result-bar-track"><div class="result-bar-fill" id="bar-${c}"></div></div>
            <div style="font-size:12px;color:var(--muted)" id="label-${c}">-</div>
          </div>
        `).join('')}
      </div>

      <!-- Issues -->
      <div style="margin-top:20px">
        <div style="font-size:12px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-bottom:10px">Detected Issues</div>
        <div id="result-issues"></div>
      </div>

      <!-- Conditions captured -->
      <div style="margin-top:16px">
        <div style="font-size:12px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-bottom:8px">Driving Conditions Captured</div>
        <div id="result-conditions"></div>
      </div>

      <!-- Action buttons -->
      <div class="action-buttons-row">
        <button id="download-pdf-btn" class="btn-primary" style="flex:1;padding:13px">
          📄 Download PDF
        </button>
        <button id="new-analysis-btn" class="btn-outline" style="flex:1;padding:13px">
          🔄 New Analysis
        </button>
      </div>
    </div>

  </div><!-- end analysis card -->`;
}

// ══════════════════════════════════════════════════════════════════
//  STATE MACHINE — showState
// ══════════════════════════════════════════════════════════════════
function showState(state) {
  ['analysis-ready','analysis-collecting','analysis-results'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
  });
  const target = document.getElementById('analysis-' + state);
  if (target) target.style.display = 'block';
}

// ══════════════════════════════════════════════════════════════════
//  CONNECTION UI
// ══════════════════════════════════════════════════════════════════
function updateConnectionUI(connected) {
  const disconnView  = document.getElementById('obd-disconnected-view');
  const connView     = document.getElementById('obd-connected-view');
  const metricsSection = document.getElementById('live-metrics-section');
  const startBtn     = document.getElementById('start-analysis-btn');
  const startHint    = document.getElementById('start-hint');

  if (connected) {
    if (disconnView)    disconnView.style.display    = 'none';
    if (connView)       connView.style.display       = 'flex';
    if (metricsSection) metricsSection.style.display = 'block';
    if (startBtn)  { startBtn.disabled = false; }
    if (startHint)   startHint.textContent = 'OBD connected — ready to analyze';
    updateOBDStatusBanner({ connected: true, port: 'USB' });
  } else {
    if (disconnView)    disconnView.style.display    = 'block';
    if (connView)       connView.style.display       = 'none';
    if (metricsSection) metricsSection.style.display = 'none';
    if (startBtn)  { startBtn.disabled = true; }
    if (startHint)   startHint.textContent = 'Connect OBD scanner to enable';
    updateOBDStatusBanner({ connected: false });
  }
}

// ══════════════════════════════════════════════════════════════════
//  LIVE METRICS UPDATE
// ══════════════════════════════════════════════════════════════════
function updateLiveMetrics(raw) {
  const map = {
    'val-rpm':      raw.rpm,
    'val-speed':    raw.speed,
    'val-temp':     raw.coolant_temp,
    'val-load':     raw.load,
    'val-throttle': raw.throttle_pos,
    'val-stft':     raw.stft,
    'val-intake':   raw.intake_temp
  };
  Object.entries(map).forEach(([id, val]) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = val !== null && val !== undefined
      ? (id === 'val-rpm' ? Math.round(val) : parseFloat(val).toFixed(1))
      : '--';
    el.classList.add('metric-flash');
    setTimeout(() => el.classList.remove('metric-flash'), 300);
  });
}

function updateLastUpdateTime() {
  const el = document.getElementById('last-update-time');
  if (el) el.textContent = 'Updated just now';
  setTimeout(() => {
    if (el) el.textContent = 'Updated 2s ago';
  }, 5000);
}

// ══════════════════════════════════════════════════════════════════
//  COLLECTING UI UPDATE
// ══════════════════════════════════════════════════════════════════
function updateCollectingUI(progress) {
  const circumference = 2 * Math.PI * 54; // 339.3
  const offset = circumference * (1 - progress.percentage / 100);

  const circle = document.getElementById('progress-circle');
  if (circle) circle.style.strokeDashoffset = offset;

  const timeEl = document.getElementById('progress-time');
  if (timeEl) timeEl.textContent = `${progress.elapsed}s / ${progress.total}s`;

  const rowsEl = document.getElementById('progress-rows');
  if (rowsEl) rowsEl.textContent = progress.rows;

  updateConditionBadges(progress.conditions);
}

function updateConditionBadges(conditions) {
  const container = document.getElementById('conditions-container');
  if (!container) return;
  conditions.forEach(c => {
    if (container.querySelector(`[data-cond="${c}"]`)) return;
    const badge = document.createElement('span');
    badge.className = 'condition-badge';
    badge.dataset.cond = c;
    badge.textContent = c.replace(/_/g, ' ');
    container.appendChild(badge);
  });
}

// ══════════════════════════════════════════════════════════════════
//  RESULT RENDERING
// ══════════════════════════════════════════════════════════════════
function animateResultGauge(score) {
  const arc    = document.getElementById('result-gauge-arc');
  const needle = document.getElementById('result-gauge-needle');
  const textEl = document.getElementById('result-overall-score');
  if (!arc) return;
  const total = Math.PI * 90;
  setTimeout(() => {
    arc.style.strokeDashoffset = total - (score / 100) * total;
    if (needle) needle.style.transform = `rotate(${-90 + (score / 100) * 180}deg)`;
    if (textEl) animateNumber(textEl, 0, score, 1600);
  }, 200);
}

function renderResults(result) {
  const scores = result.component_scores || {};

  // Overall gauge
  animateResultGauge(result.overall_score);

  // Category badge
  const catEl = document.getElementById('result-category');
  if (catEl) {
    catEl.className = 'badge ' + getBadgeClass(result.health_category);
    catEl.textContent = result.health_category;
  }

  // Subtitle
  const subEl = document.getElementById('result-subtitle');
  if (subEl) {
    const q = result.data_quality || {};
    subEl.textContent = `Based on ${q.rows_collected || '?'} readings · Quality: ${q.quality || '?'}`;
  }

  // Component scores
  ['engine','fuel','efficiency','driving','thermal'].forEach(comp => {
    const score = scores[comp] || 0;
    const scoreEl = document.getElementById('score-' + comp);
    const barEl   = document.getElementById('bar-' + comp);
    const lblEl   = document.getElementById('label-' + comp);

    if (scoreEl) animateNumber(scoreEl, 0, score, 1500);
    if (barEl)   setTimeout(() => { barEl.style.width = score + '%'; }, 100);
    if (lblEl)   lblEl.textContent = score >= 75 ? 'Good' : score >= 60 ? 'Fair' : score >= 40 ? 'Poor' : 'Critical';
  });

  // Issues
  const issuesEl = document.getElementById('result-issues');
  if (issuesEl) {
    if (!result.issues || result.issues.length === 0) {
      issuesEl.innerHTML = '<div class="no-issues">✅ No persistent issues detected</div>';
    } else {
      issuesEl.innerHTML = result.issues.map(issue =>
        `<div class="alert-card alert-warning" style="margin-bottom:8px">⚠️ ${issue}</div>`
      ).join('');
    }
  }

  // Conditions captured
  const condEl = document.getElementById('result-conditions');
  if (condEl) {
    const conditions = result.data_quality?.conditions || [];
    condEl.innerHTML = conditions.length > 0
      ? conditions.map(c => `<span class="condition-badge">${c.replace(/_/g,' ')}</span>`).join('')
      : '<span style="color:var(--muted);font-size:13px">No conditions recorded</span>';
  }

  // PDF download button
  const pdfBtn = document.getElementById('download-pdf-btn');
  if (pdfBtn && result.report_id) {
    pdfBtn.onclick = () => window.open(`${API_BASE}/reports/download/${result.report_id}`);
  } else if (pdfBtn) {
    pdfBtn.style.display = 'none';
  }
}

// ══════════════════════════════════════════════════════════════════
//  TIP ROTATION
// ══════════════════════════════════════════════════════════════════
let tipTimer = null;
function startTipRotation() {
  const tips = [
    'Drive normally for best results...',
    'Include some acceleration for complete analysis...',
    'Try varying your speed...',
    'City driving data captured...',
    'Almost there! Keep driving...'
  ];
  let i = 0;
  const el = document.getElementById('collection-tip');
  if (!el) return;
  if (tipTimer) clearInterval(tipTimer);
  tipTimer = setInterval(() => {
    el.style.opacity = '0';
    setTimeout(() => {
      i = (i + 1) % tips.length;
      el.textContent = tips[i];
      el.style.opacity = '1';
    }, 300);
  }, 10000);
}

// ══════════════════════════════════════════════════════════════════
//  WIRE UP OBD EVENT HANDLERS (called after renderLiveDashboard)
// ══════════════════════════════════════════════════════════════════
let selectedDuration = 120;

function wireOBDHandlers() {
  // Connect button
  const connectBtn = document.getElementById('connect-obd-btn');
  if (connectBtn) {
    connectBtn.addEventListener('click', async () => {
      connectBtn.textContent = 'Connecting...';
      connectBtn.disabled = true;

      const result = await connectOBDSerial();

      if (result.success) {
        showToast('OBD Connected! Live data starting...', 'success');
        updateConnectionUI(true);
        startLiveStream(raw => {
          updateLiveMetrics(raw);
          updateLastUpdateTime();
        });
      } else {
        showToast('Connection failed: ' + result.message, 'error');
        connectBtn.textContent = '🔌 Connect OBD Scanner';
        connectBtn.disabled = false;
      }
    });
  }

  // Disconnect button
  const disconnBtn = document.getElementById('disconnect-obd-btn');
  if (disconnBtn) {
    disconnBtn.addEventListener('click', async () => {
      await serialDisconnect();
      window.location.reload();
    });
  }

  // Duration picker
  document.querySelectorAll('.dur-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.dur-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedDuration = parseInt(btn.dataset.dur);
    });
  });

  // Start Analysis
  const startBtn = document.getElementById('start-analysis-btn');
  if (startBtn) {
    startBtn.addEventListener('click', () => {
      const status = getSerialStatus();
      if (!status.connected) {
        showToast('Connect OBD scanner first!', 'error');
        return;
      }
      showState('collecting');
      startTipRotation();

      startAnalysis(
        selectedDuration,
        // onProgress
        progress => updateCollectingUI(progress),
        // onComplete
        async (buffer, error) => {
          if (tipTimer) clearInterval(tipTimer);

          if (error) {
            showToast(error, 'error');
            showState('ready');
            return;
          }
          if (!buffer || buffer.length < 5) {
            showToast('Not enough data collected. Keep driving!', 'error');
            showState('ready');
            return;
          }

          showToast(`Analyzing ${buffer.length} readings...`, 'info');

          try {
            const result = await apiPost('/predict/batch', {
              rows:             buffer,
              duration_seconds: selectedDuration
            });
            showState('results');
            renderResults(result);
            showToast(`Analysis complete! Score: ${result.overall_score}/100`, 'success');
          } catch (err) {
            showToast('Analysis failed: ' + err.message, 'error');
            showState('ready');
          }
        }
      );
    });
  }

  // Cancel Analysis
  const cancelBtn = document.getElementById('cancel-analysis-btn');
  if (cancelBtn) {
    cancelBtn.addEventListener('click', () => {
      cancelAnalysis();
      if (tipTimer) clearInterval(tipTimer);
      showState('ready');
      showToast('Analysis cancelled', 'info');
    });
  }

  // New Analysis
  const newBtn = document.getElementById('new-analysis-btn');
  if (newBtn) {
    newBtn.addEventListener('click', () => showState('ready'));
  }
}

// ══════════════════════════════════════════════════════════════════
//  MAIN — renderDashboard
// ══════════════════════════════════════════════════════════════════
async function renderDashboard(container) {
  // Expose toast globally for inline onclick
  window._showToast = showToast;

  // Get OBD status
  let obdStatus = { connected: false };
  try { obdStatus = await apiGet('/obd/status'); } catch {}

  // Get metrics
  let metrics = mockMetrics();
  try {
    const live = await apiGet('/obd/data');
    if (live && live.rpm !== undefined) metrics = live;
  } catch {}

  // Get ML prediction
  let prediction = mockScores();
  try {
    const mockInput = {
      rpm: metrics.rpm, speed: metrics.speed, load: metrics.load,
      maf: metrics.maf, stft: metrics.stft, ltft: metrics.ltft,
      oat: metrics.oat, speed_limit: 60
    };
    const res = await apiPost('/predict', mockInput);
    if (res && res.overall_score !== undefined) prediction = res;
  } catch {}

  const score    = Math.round(prediction.overall_score || 72);
  const cat      = prediction.category || scoreLabel(score);
  const compScores = prediction.component_scores || prediction.scores || { engine:72,fuel:74,efficiency:70,driving:80,thermal:75 };
  const issues   = prediction.issues || [];
  const reportId = prediction.report_id || null;
  currentReportId = reportId;

  // Init history
  METRIC_DEFS.forEach(d => {
    if (!metricsHistory[d.key]) metricsHistory[d.key] = [];
    const v = metrics[d.key];
    if (v !== undefined) {
      metricsHistory[d.key].push(parseFloat(v));
      if (metricsHistory[d.key].length > 12) metricsHistory[d.key].shift();
    }
  });

  // Build HTML
  container.innerHTML = `
    <div class="section-header slide-top">
      <div>
        <h1 class="section-title">Dashboard</h1>
        <p class="section-subtitle">AI-powered vehicle health at a glance</p>
      </div>
    </div>

    ${renderLiveDashboard()}

    ${renderVehicleInfo()}

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px" class="gauge-row">
      ${renderHealthGauge(score, cat)}
      ${renderSubsystemScores(compScores)}
    </div>

    ${renderLiveMetrics(metrics)}
    ${renderGraphs()}
    ${renderAlerts(issues)}
    ${renderRiskPredictions(compScores)}
    ${renderRecommendations(compScores)}
    ${renderReportButton(reportId)}
  `;

  // Run animations after render
  requestAnimationFrame(() => {
    initRevealAnimations();
    animateGauge(score);
    animateSubsystems();
    setTimeout(() => {
      document.querySelectorAll('.risk-fill').forEach(el => {
        el.style.width = el.dataset.w + '%';
      });
    }, 300);
    setTimeout(() => initCharts(metrics), 400);
    startLivePolling();
    // Wire up OBD Web Serial API handlers
    wireOBDHandlers();
  });

  // Expose toast for inline onclick handlers
  window._showToast = showToast;
}

// ── Live polling ────────────────────────────────────────────────────
function startLivePolling() {
  if (pollingTimer) clearInterval(pollingTimer);
  pollingTimer = setInterval(async () => {
    let m = mockMetrics();
    try {
      const live = await apiGet('/obd/data');
      if (live && live.rpm !== undefined) m = live;
    } catch {}

    METRIC_DEFS.forEach(d => {
      const el = document.getElementById(`metric-${d.key}`);
      const v  = m[d.key];
      if (!el || v === undefined) return;
      const disp = parseFloat(v).toFixed(d.key==='rpm'?0:1);
      if (el.textContent !== disp) {
        el.textContent = disp;
        el.classList.add('metric-flash');
        setTimeout(() => el.classList.remove('metric-flash'), 400);
      }
      if (!metricsHistory[d.key]) metricsHistory[d.key] = [];
      metricsHistory[d.key].push(parseFloat(v));
      if (metricsHistory[d.key].length > 12) metricsHistory[d.key].shift();
      const sp = document.getElementById(`spark-${d.key}`);
      if (sp) sp.innerHTML = sparklinePath(metricsHistory[d.key]);
    });

    // Update charts
    const updateChartMap = {
      'chart-rpm':      m.rpm,
      'chart-temp':     m.coolant_temp,
      'chart-load':     m.load,
      'chart-throttle': m.throttle_pos
    };
    Object.entries(updateChartMap).forEach(([id, val]) => {
      const ch = liveCharts[id];
      if (!ch || val === undefined) return;
      ch.data.datasets[0].data.push(parseFloat(val));
      ch.data.datasets[0].data.shift();
      ch.data.labels.push('');
      ch.data.labels.shift();
      ch.update('none');
    });
  }, 3000);
}

// ══════════════════════════════════════════════════════════════════
//  SIDEBAR SECTIONS
// ══════════════════════════════════════════════════════════════════

async function loadVehiclesSection(container) {
  container.innerHTML = `
  <div class="section-header">
    <div>
      <h1 class="section-title">My Vehicles</h1>
      <p class="section-subtitle">Manage your registered vehicles</p>
    </div>
    <button class="btn-primary" onclick="document.getElementById('add-vehicle-modal').style.display='flex'">+ Add Vehicle</button>
  </div>
  
  <div id="vehicles-list-container">
    <div class="placeholder-section reveal">
      <p class="placeholder-title">Loading Vehicles...</p>
    </div>
  </div>

  <!-- Add Vehicle Modal -->
  <div id="add-vehicle-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.8);backdrop-filter:blur(5px);z-index:9999;align-items:center;justify-content:center;padding:20px;">
    <div class="glass-card reveal" style="width:100%;max-width:500px;padding:32px;position:relative">
      <button onclick="document.getElementById('add-vehicle-modal').style.display='none'" style="position:absolute;top:20px;right:20px;background:none;border:none;color:var(--text);font-size:24px;cursor:pointer">&times;</button>
      <h2 style="font-family:var(--font-display);font-size:24px;color:var(--accent);margin-bottom:8px">Add New Vehicle</h2>
      <p style="color:var(--muted);font-size:14px;margin-bottom:24px">Register a new car for OBD analysis.</p>
      
      <div id="vehicle-error" class="error-msg"></div>
      
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
        <div class="input-group">
          <label style="font-size:12px;color:var(--muted);display:block;margin-bottom:6px">Vehicle Nickname</label>
          <input type="text" id="veh-name" placeholder="e.g. My Daily Driver" style="background:rgba(255,255,255,0.05);border:1px solid var(--glass-border);border-radius:var(--radius-sm);padding:12px 16px;color:var(--text);width:100%;box-sizing:border-box" required/>
        </div>
        <div class="input-group">
          <label style="font-size:12px;color:var(--muted);display:block;margin-bottom:6px">Car Model</label>
          <input type="text" id="veh-model" placeholder="e.g. Honda Civic" style="background:rgba(255,255,255,0.05);border:1px solid var(--glass-border);border-radius:var(--radius-sm);padding:12px 16px;color:var(--text);width:100%;box-sizing:border-box" required/>
        </div>
      </div>
      
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
        <div class="input-group">
          <label style="font-size:12px;color:var(--muted);display:block;margin-bottom:6px">Plate Number</label>
          <input type="text" id="veh-plate" placeholder="e.g. ABC-1234" style="background:rgba(255,255,255,0.05);border:1px solid var(--glass-border);border-radius:var(--radius-sm);padding:12px 16px;color:var(--text);width:100%;box-sizing:border-box" required/>
        </div>
        <div class="input-group">
          <label style="font-size:12px;color:var(--muted);display:block;margin-bottom:6px">Purchase Year</label>
          <input type="text" id="veh-purchase" placeholder="e.g. 2020" style="background:rgba(255,255,255,0.05);border:1px solid var(--glass-border);border-radius:var(--radius-sm);padding:12px 16px;color:var(--text);width:100%;box-sizing:border-box" required/>
        </div>
      </div>
      
      <div class="input-group" style="margin-bottom:24px">
        <label style="font-size:12px;color:var(--muted);display:block;margin-bottom:6px">Owner Type</label>
        <select id="veh-owner" style="background:rgba(255,255,255,0.05);border:1px solid var(--glass-border);border-radius:var(--radius-sm);padding:12px 16px;color:var(--text);width:100%;box-sizing:border-box;font-family:var(--font-body)">
          <option value="1" style="background:#111">1st Owner</option>
          <option value="2" style="background:#111">2nd Owner</option>
          <option value="3" style="background:#111">3rd Owner (or more)</option>
        </select>
      </div>

      <button id="submit-vehicle-btn" class="btn-primary btn-full">Save Vehicle</button>
    </div>
  </div>`;
  
  const listContainer = document.getElementById('vehicles-list-container');
  
  async function fetchVehicles() {
    try {
      const user = auth.currentUser;
      if (!user) throw new Error("Not authenticated");
      
      const q = query(collection(db, "vehicles"), where("userId", "==", user.uid));
      const querySnapshot = await getDocs(q);
      
      let vehicles = [];
      querySnapshot.forEach((doc) => {
        vehicles.push({ id: doc.id, ...doc.data() });
      });
      
      vehicles.sort((a, b) => {
        const t1 = a.created_at ? a.created_at.toMillis() : 0;
        const t2 = b.created_at ? b.created_at.toMillis() : 0;
        return t2 - t1;
      });

      if (vehicles.length === 0) {
        listContainer.innerHTML = `
          <div class="placeholder-section reveal">
            <div class="placeholder-icon">
              <svg viewBox="0 0 24 24" fill="none" width="36" height="36">
                <path d="M5 17H3a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h14l4 4v4a2 2 0 0 1-2 2h-2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
                <circle cx="7.5" cy="17.5" r="2.5" stroke="currentColor" stroke-width="1.6"/>
                <circle cx="17.5" cy="17.5" r="2.5" stroke="currentColor" stroke-width="1.6"/>
              </svg>
            </div>
            <p class="placeholder-title">No Vehicles Added Yet</p>
            <p class="placeholder-sub">Click 'Add Vehicle' above to register your first car.</p>
          </div>`;
      } else {
        listContainer.innerHTML = `
          <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(300px, 1fr));gap:20px;">
            ${vehicles.map(v => `
              <div class="glass-card reveal" style="padding:24px;position:relative">
                <button class="delete-vehicle-btn" data-id="${v.id}" style="position:absolute;top:16px;right:16px;background:rgba(255,255,255,0.1);border:none;color:var(--muted);width:32px;height:32px;border-radius:50%;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background 0.2s" onmouseover="this.style.background='rgba(255,23,68,0.2)';this.style.color='#ff1744'" onmouseout="this.style.background='rgba(255,255,255,0.1)';this.style.color='var(--muted)'">
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
                </button>
                <div style="width:48px;height:48px;border-radius:12px;background:rgba(0,229,255,0.1);color:var(--accent);display:flex;align-items:center;justify-content:center;margin-bottom:16px">
                  <svg viewBox="0 0 24 24" fill="none" width="28" height="28">
                    <path d="M5 17H3a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h14l4 4v4a2 2 0 0 1-2 2h-2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                    <circle cx="7.5" cy="17.5" r="2.5" stroke="currentColor" stroke-width="1.8"/>
                    <circle cx="17.5" cy="17.5" r="2.5" stroke="currentColor" stroke-width="1.8"/>
                  </svg>
                </div>
                <h3 style="font-family:var(--font-display);font-size:18px;margin-bottom:4px;color:var(--text)">${v.name}</h3>
                <p style="color:var(--muted);font-size:13px;margin-bottom:16px">${v.model}</p>
                <div style="background:rgba(0,0,0,0.2);padding:12px;border-radius:8px;font-size:12px;display:grid;grid-template-columns:1fr 1fr;gap:10px">
                  <div><span style="color:var(--muted)">Plate:</span> <span style="color:var(--text-dim);font-family:monospace">${v.plate_number||'N/A'}</span></div>
                  <div><span style="color:var(--muted)">Year:</span> <span style="color:var(--text-dim)">${v.purchase_year||'N/A'}</span></div>
                  <div><span style="color:var(--muted)">Owner:</span> <span style="color:var(--text-dim)">${v.owner_number ? v.owner_number + (v.owner_number==1?'st':v.owner_number==2?'nd':v.owner_number==3?'rd':'th') : 'N/A'}</span></div>
                </div>
              </div>
            `).join('')}
          </div>
        `;
        // Attach delete listeners after render (avoids inline onclick quoting issues)
        listContainer.querySelectorAll('.delete-vehicle-btn').forEach(btn => {
          btn.addEventListener('click', async () => {
            const vehicleId = btn.dataset.id;
            if (!confirm('Are you sure you want to delete this vehicle?')) return;
            try {
              await deleteDoc(doc(db, 'vehicles', vehicleId));
              showToast('Vehicle deleted!', 'success');
              fetchVehicles();
            } catch(e) {
              showToast('Error deleting vehicle: ' + e.message, 'error');
            }
          });
        });
      }
      initRevealAnimations();
    } catch(e) {
      listContainer.innerHTML = `<p style="color:var(--danger)">Error loading vehicles: ${e.message}</p>`;
    }
  }

  window.deleteVehicle = async function(id) {
    if(!confirm('Are you sure you want to delete this vehicle?')) return;
    try {
      await deleteDoc(doc(db, "vehicles", id));
      showToast('Vehicle deleted successfully', 'success');
      fetchVehicles();
    } catch(e) {
      showToast('Error deleting vehicle', 'error');
    }
  };

  fetchVehicles();
  
  const submitBtn = document.getElementById('submit-vehicle-btn');
  if(submitBtn) {
    submitBtn.addEventListener('click', async () => {
      const name = document.getElementById('veh-name').value.trim();
      const model = document.getElementById('veh-model').value.trim();
      const plate = document.getElementById('veh-plate').value.trim();
      const purchase = document.getElementById('veh-purchase').value.trim();
      const owner = document.getElementById('veh-owner').value;
      const errorEl = document.getElementById('vehicle-error');
      
      errorEl.classList.remove('visible');
      if(!name || !model || !plate || !purchase) {
        errorEl.textContent = 'Please fill all fields.';
        errorEl.classList.add('visible');
        return;
      }
      
      submitBtn.textContent = 'Saving...';
      submitBtn.disabled = true;
      try {
        const user = auth.currentUser;
        if (!user) throw new Error("Not authenticated");
        
        await addDoc(collection(db, "vehicles"), {
          userId: user.uid,
          name: name,
          model: model,
          plate_number: plate,
          purchase_year: purchase,
          owner_number: owner,
          created_at: serverTimestamp()
        });
        document.getElementById('add-vehicle-modal').style.display='none';
        showToast('Vehicle added successfully!', 'success');
        
        // Reset form
        document.getElementById('veh-name').value='';
        document.getElementById('veh-model').value='';
        document.getElementById('veh-plate').value='';
        document.getElementById('veh-purchase').value='';
        
        fetchVehicles();
      } catch (e) {
        errorEl.textContent = e.message || 'Failed to add vehicle.';
        errorEl.classList.add('visible');
      } finally {
        submitBtn.textContent = 'Save Vehicle';
        submitBtn.disabled = false;
      }
    });
  }
}

async function loadReportsSection(container) {
  container.innerHTML = `
  <div class="section-header">
    <div>
      <h1 class="section-title">Past Reports</h1>
      <p class="section-subtitle">All historical vehicle scan reports</p>
    </div>
  </div>
  <div id="reports-body">
    <div class="placeholder-section reveal">
      <div class="placeholder-icon">
        <svg viewBox="0 0 24 24" fill="none" width="36" height="36">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z" stroke="currentColor" stroke-width="1.6"/>
          <path d="M14 2v6h6M16 13H8M16 17H8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
        </svg>
      </div>
      <p class="placeholder-title">Loading Reports...</p>
    </div>
  </div>`;

  try {
    const currentUser = auth.currentUser;
    if (!currentUser) throw new Error('Not authenticated');

    const q = query(collection(db, 'reports'), where('userId', '==', currentUser.uid));
    const snap = await getDocs(q);
    let reports = [];
    snap.forEach(d => reports.push({ id: d.id, ...d.data() }));
    reports.sort((a, b) => {
      const t1 = a.created_at ? a.created_at.toMillis() : 0;
      const t2 = b.created_at ? b.created_at.toMillis() : 0;
      return t2 - t1;
    });

    const body = document.getElementById('reports-body');
    if (!body) return;
    if (reports.length === 0) {
      body.innerHTML = `<div class="placeholder-section reveal">
        <p class="placeholder-title">No Reports Yet</p>
        <p class="placeholder-sub">Run your first vehicle scan to generate a report.</p>
      </div>`;
    } else {
      body.innerHTML = `
      <div class="glass-card" style="overflow:auto">
        <table style="width:100%;border-collapse:collapse;font-family:var(--font-body);font-size:13px">
          <thead>
            <tr style="border-bottom:1px solid var(--glass-border)">
              ${['Date','Score','Status','Engine','Fuel'].map(h=>`
                <th style="padding:14px 16px;text-align:left;color:var(--muted);font-weight:600;letter-spacing:1px;font-size:11px;text-transform:uppercase">${h}</th>`).join('')}
            </tr>
          </thead>
          <tbody>
            ${reports.map(r => {
              const ts = r.created_at ? new Date(r.created_at.toMillis()).toLocaleDateString() : 'N/A';
              return `
            <tr style="border-bottom:1px solid rgba(255,255,255,0.04);transition:background 0.2s" onmouseenter="this.style.background='rgba(0,229,255,0.03)'" onmouseleave="this.style.background=''">
              <td style="padding:14px 16px;color:var(--text-dim)">${ts}</td>
              <td style="padding:14px 16px"><span style="font-family:var(--font-display);color:${scoreColor(r.overall_score||0)};font-weight:700">${Math.round(r.overall_score||0)}</span></td>
              <td style="padding:14px 16px"><span class="badge ${getBadgeClass(r.category||scoreLabel(r.overall_score||0))}">${r.category||scoreLabel(r.overall_score||0)}</span></td>
              <td style="padding:14px 16px;color:${scoreColor(r.engine_score||0)}">${Math.round(r.engine_score||0)}</td>
              <td style="padding:14px 16px;color:${scoreColor(r.fuel_score||0)}">${Math.round(r.fuel_score||0)}</td>
            </tr>`;
            }).join('')}
          </tbody>
        </table>
      </div>`;
    }
  } catch(e) {
    const body = document.getElementById('reports-body');
    if (body) body.innerHTML = `<div class="placeholder-section reveal"><p class="placeholder-title">Could not load reports.</p><p class="placeholder-sub">${e.message}</p></div>`;
  }
  initRevealAnimations();
}

async function loadProfileSection(container) {
  const currentUser = auth.currentUser;
  let user = { name: '', email: currentUser?.email || '', alternate_contact: '', profile_photo_url: '' };
  
  // Fetch from Firestore
  try {
    if (currentUser) {
      const userDoc = await getDoc(doc(db, 'users', currentUser.uid));
      if (userDoc.exists()) {
        user = { ...user, ...userDoc.data() };
      } else {
        // Create initial doc
        await setDoc(doc(db, 'users', currentUser.uid), {
          name: currentUser.displayName || '',
          email: currentUser.email || '',
          alternate_contact: '',
          profile_photo_url: '',
          created_at: serverTimestamp()
        });
        user.name = currentUser.displayName || '';
      }
    }
  } catch (e) {
    console.warn('Could not fetch profile from Firestore', e);
  }

  const initials = (user.name||'VX').split(' ').map(w=>w[0]).join('').toUpperCase().slice(0,2);
  const photoUrl = user.profile_photo_url || currentUser?.photoURL || '';

  container.innerHTML = `
  <div class="section-header">
    <div><h1 class="section-title">My Profile</h1><p class="section-subtitle">Manage your account</p></div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
    
    <!-- Profile Info Update -->
    <div class="glass-card reveal" style="padding:28px">
      <div style="text-align:center;margin-bottom:24px">
        ${photoUrl 
          ? `<img src="${photoUrl}" style="width:72px;height:72px;border-radius:50%;object-fit:cover;margin:0 auto 12px;display:block;border:2px solid rgba(255,255,255,0.1)"/>`
          : `<div style="width:72px;height:72px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--accent3));display:flex;align-items:center;justify-content:center;font-family:var(--font-display);font-size:22px;font-weight:700;color:#000;margin:0 auto 12px">${initials}</div>`
        }
        <div style="font-family:var(--font-display);font-size:16px;font-weight:700;color:var(--text)">${user.name||'User'}</div>
        <div style="font-size:13px;color:var(--muted)">${user.email||''}</div>
      </div>
      
      <div class="input-group" style="margin-bottom:14px">
        <label style="font-size:12px;color:var(--muted);display:block;margin-bottom:6px">Full Name</label>
        <input type="text" id="profile-name" value="${user.name||''}" placeholder="Full name" style="background:rgba(255,255,255,0.05);border:1px solid var(--glass-border);border-radius:var(--radius-sm);padding:12px 16px;color:var(--text);width:100%;font-family:var(--font-body);box-sizing:border-box"/>
      </div>
      
      <div class="input-group" style="margin-bottom:14px">
        <label style="font-size:12px;color:var(--muted);display:block;margin-bottom:6px">Primary Email (Unchangeable)</label>
        <input type="email" value="${user.email||''}" disabled style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:var(--radius-sm);padding:12px 16px;color:var(--muted);width:100%;font-family:var(--font-body);box-sizing:border-box"/>
      </div>
      
      <div class="input-group" style="margin-bottom:14px">
        <label style="font-size:12px;color:var(--muted);display:block;margin-bottom:6px">Alternate Mobile or Email</label>
        <input type="text" id="profile-alt" value="${user.alternate_contact||''}" placeholder="Phone or email" style="background:rgba(255,255,255,0.05);border:1px solid var(--glass-border);border-radius:var(--radius-sm);padding:12px 16px;color:var(--text);width:100%;font-family:var(--font-body);box-sizing:border-box"/>
      </div>
      
      <div class="input-group" style="margin-bottom:20px">
        <label style="font-size:12px;color:var(--muted);display:block;margin-bottom:6px">Profile Photo</label>
        <input type="hidden" id="profile-photo" value="${user.profile_photo_url||''}"/>
        <div style="display:flex;align-items:center;gap:14px">
          <div id="photo-preview" style="width:52px;height:52px;border-radius:50%;overflow:hidden;border:2px solid var(--glass-border);flex-shrink:0;background:rgba(0,229,255,0.1);display:flex;align-items:center;justify-content:center">
            ${user.profile_photo_url 
              ? `<img src="${user.profile_photo_url}" style="width:100%;height:100%;object-fit:cover"/>`
              : `<span style="font-size:18px;color:var(--accent)">📷</span>`
            }
          </div>
          <div style="flex:1">
            <input type="file" id="photo-file-input" accept="image/*" style="display:none"/>
            <button id="upload-photo-btn" class="btn-outline" style="width:100%;padding:10px;font-size:13px">📤 Upload Photo</button>
            <div id="upload-status" style="font-size:11px;color:var(--muted);margin-top:6px"></div>
          </div>
        </div>
      </div>

      <button id="update-profile-btn" class="btn-primary btn-full">Update Profile</button>
    </div>
    
    <!-- Password Update -->
    <div class="glass-card reveal" style="padding:28px">
      <div style="font-family:var(--font-display);font-size:16px;font-weight:700;color:var(--text);margin-bottom:20px">Change Password</div>
      <div id="pw-error" class="error-msg"></div>
      
      <div style="margin-bottom:14px">
        <label style="font-size:12px;color:var(--muted);display:block;margin-bottom:6px">Current Password</label>
        <input type="password" id="current-pw" placeholder="••••••••" style="background:rgba(255,255,255,0.05);border:1px solid var(--glass-border);border-radius:var(--radius-sm);padding:12px 16px;color:var(--text);width:100%;font-family:var(--font-body);box-sizing:border-box"/>
      </div>
      <div style="margin-bottom:14px">
        <label style="font-size:12px;color:var(--muted);display:block;margin-bottom:6px">New Password</label>
        <input type="password" id="new-pw" placeholder="••••••••" style="background:rgba(255,255,255,0.05);border:1px solid var(--glass-border);border-radius:var(--radius-sm);padding:12px 16px;color:var(--text);width:100%;font-family:var(--font-body);box-sizing:border-box"/>
      </div>
      <div style="margin-bottom:20px">
        <label style="font-size:12px;color:var(--muted);display:block;margin-bottom:6px">Confirm Password</label>
        <input type="password" id="confirm-pw" placeholder="••••••••" style="background:rgba(255,255,255,0.05);border:1px solid var(--glass-border);border-radius:var(--radius-sm);padding:12px 16px;color:var(--text);width:100%;font-family:var(--font-body);box-sizing:border-box"/>
      </div>
      
      <button id="update-pw-btn" class="btn-primary btn-full">Update Password</button>
    </div>
  </div>`;
  
  // ── Cloudinary photo upload ─────────────────────────────────────
  const CLOUDINARY_CLOUD = 'dwhzpc4gn';
  const CLOUDINARY_PRESET = 'vexis-uploads';

  const uploadPhotoBtn = container.querySelector('#upload-photo-btn');
  const photoFileInput = container.querySelector('#photo-file-input');
  const uploadStatus  = container.querySelector('#upload-status');
  const photoHidden   = container.querySelector('#profile-photo');
  const photoPreview  = container.querySelector('#photo-preview');

  uploadPhotoBtn?.addEventListener('click', () => photoFileInput?.click());

  photoFileInput?.addEventListener('change', async () => {
    const file = photoFileInput.files[0];
    if (!file) return;
    uploadPhotoBtn.textContent = '⏳ Uploading...';
    uploadPhotoBtn.disabled = true;
    uploadStatus.textContent = 'Uploading to Cloudinary...';
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('upload_preset', CLOUDINARY_PRESET);
      const res = await fetch(`https://api.cloudinary.com/v1_1/${CLOUDINARY_CLOUD}/image/upload`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error?.message || 'Upload failed');
      const url = data.secure_url;
      // Store URL in hidden input
      photoHidden.value = url;
      // Update preview
      photoPreview.innerHTML = `<img src="${url}" style="width:100%;height:100%;object-fit:cover"/>`;
      // Immediately save to Firestore
      const currentUser = auth.currentUser;
      if (currentUser) {
        await setDoc(doc(db, 'users', currentUser.uid), { profile_photo_url: url, updated_at: serverTimestamp() }, { merge: true });
      }
      uploadStatus.textContent = '✅ Photo uploaded!';
      showToast('Profile photo updated!', 'success');
    } catch(e) {
      uploadStatus.textContent = '❌ ' + (e.message || 'Upload failed');
      showToast('Photo upload failed: ' + e.message, 'error');
    } finally {
      uploadPhotoBtn.textContent = '📤 Upload Photo';
      uploadPhotoBtn.disabled = false;
    }
  });

  // Attach event listeners after rendering
  const updateProfileBtn = container.querySelector('#update-profile-btn');
  const updatePwBtn = container.querySelector('#update-pw-btn');
  
  if (updateProfileBtn) {
    updateProfileBtn.addEventListener('click', async () => {
      const name = container.querySelector('#profile-name').value.trim();
      const alt = container.querySelector('#profile-alt').value.trim();
      const photo = container.querySelector('#profile-photo').value.trim();
      
      updateProfileBtn.textContent = 'Updating...';
      updateProfileBtn.disabled = true;
      
      try {
        const currentUser = auth.currentUser;
        if (!currentUser) throw new Error('Not logged in');
        
        // Update Firebase Auth display name
        if (name) {
          await firebaseUpdateProfile(currentUser, { displayName: name });
        }
        
        // Update/Create Firestore user doc
        await setDoc(doc(db, 'users', currentUser.uid), {
          name: name,
          email: currentUser.email,
          alternate_contact: alt,
          profile_photo_url: photo,
          updated_at: serverTimestamp()
        }, { merge: true });
        
        // Update header
        const headerName = document.getElementById('user-name');
        if (headerName) headerName.textContent = name || currentUser.email;
        const headerAvatar = document.getElementById('user-avatar');
        if (headerAvatar) headerAvatar.textContent = (name||'VX').split(' ').map(w=>w[0]).join('').toUpperCase().slice(0,2);
        
        showToast('Profile updated successfully!', 'success');
        setTimeout(() => loadProfileSection(container), 800);
      } catch (err) {
        showToast(err.message || 'Failed to update profile.', 'error');
      } finally {
        updateProfileBtn.textContent = 'Update Profile';
        updateProfileBtn.disabled = false;
      }
    });
  }

  if (updatePwBtn) {
    updatePwBtn.addEventListener('click', async () => {
      const cp = container.querySelector('#current-pw').value;
      const np = container.querySelector('#new-pw').value;
      const cfp = container.querySelector('#confirm-pw').value;
      const errEl = container.querySelector('#pw-error');
      
      errEl.classList.remove('visible');
      
      if (!cp || !np || !cfp) {
        errEl.textContent = 'Please fill all password fields.';
        errEl.classList.add('visible');
        return;
      }
      if (np.length < 8) {
        errEl.textContent = 'New password must be at least 8 characters.';
        errEl.classList.add('visible');
        return;
      }
      if (np !== cfp) {
        errEl.textContent = 'New passwords do not match.';
        errEl.classList.add('visible');
        return;
      }
      
      updatePwBtn.textContent = 'Updating...';
      updatePwBtn.disabled = true;
      
      try {
        const currentUser = auth.currentUser;
        if (!currentUser) throw new Error("Not logged in");
        
        // Re-authenticate first
        const credential = EmailAuthProvider.credential(currentUser.email, cp);
        await reauthenticateWithCredential(currentUser, credential);
        
        // Update password
        await updatePassword(currentUser, np);
        
        showToast('Password updated successfully!', 'success');
        container.querySelector('#current-pw').value = '';
        container.querySelector('#new-pw').value = '';
        container.querySelector('#confirm-pw').value = '';
      } catch (err) {
        let msg = 'Failed to update password.';
        if (err.code === 'auth/invalid-credential') msg = 'Current password is incorrect.';
        if (err.code === 'auth/weak-password') msg = 'New password is too weak.';
        
        errEl.textContent = msg;
        errEl.classList.add('visible');
      } finally {
        updatePwBtn.textContent = 'Update Password';
        updatePwBtn.disabled = false;
      }
    });
  }

  initRevealAnimations();
}

async function loadSettingsSection(container) {
  const currentUser = auth.currentUser;
  let s = {};
  // Load from Firestore first, fallback to localStorage
  try {
    if (currentUser) {
      const snap = await getDoc(doc(db, 'settings', currentUser.uid));
      if (snap.exists()) s = snap.data();
      else s = JSON.parse(localStorage.getItem('vexis_settings') || '{}');
    }
  } catch (e) {
    s = JSON.parse(localStorage.getItem('vexis_settings') || '{}');
  }

  container.innerHTML = `
  <div class="section-header">
    <div><h1 class="section-title">Settings</h1><p class="section-subtitle">Configure Vexis preferences</p></div>
  </div>
  <div style="display:grid;gap:16px;max-width:640px">
    ${[
      {id:'notif',    label:'Email Notifications',    sub:'Get email alerts for critical health scores', def: s.notif!==false},
      {id:'imperial', label:'Imperial Units',          sub:'Switch from metric to imperial (mph, °F)',   def: s.imperial===true},
      {id:'autoconn', label:'OBD Auto-Connect',        sub:'Automatically connect scanner on startup',  def: s.autoconn===true}
    ].map(t => `
    <div class="glass-card reveal" style="padding:22px;display:flex;align-items:center;justify-content:space-between;gap:16px">
      <div><div style="color:var(--text);font-weight:600;margin-bottom:4px">${t.label}</div>
      <div style="font-size:13px;color:var(--muted)">${t.sub}</div></div>
      <label style="position:relative;display:inline-block;width:44px;height:24px;flex-shrink:0">
        <input type="checkbox" id="toggle-${t.id}" ${t.def?'checked':''} style="opacity:0;width:0;height:0"/>
        <span onclick="this.previousElementSibling.checked=!this.previousElementSibling.checked;this.style.background=this.previousElementSibling.checked?'var(--accent)':'rgba(255,255,255,0.1)'"
          style="position:absolute;inset:0;border-radius:12px;background:${t.def?'var(--accent)':'rgba(255,255,255,0.1)'};
          cursor:pointer;transition:background 0.3s;display:flex;align-items:center;padding:2px">
          <span style="width:20px;height:20px;border-radius:50%;background:white;transition:transform 0.3s;${t.def?'margin-left:auto':''}"></span>
        </span>
      </label>
    </div>`).join('')}

    <div class="glass-card reveal" style="padding:22px">
      <div style="color:var(--text);font-weight:600;margin-bottom:4px">Data Refresh Rate</div>
      <div style="font-size:13px;color:var(--muted);margin-bottom:12px">How often live metrics update</div>
      <select id="refresh-rate" style="background:rgba(255,255,255,0.05);border:1px solid var(--glass-border);border-radius:var(--radius-sm);padding:10px 14px;color:var(--text);font-family:var(--font-body);width:100%">
        <option value="2000" ${(s.refresh||3000)==2000?'selected':''}>2 seconds</option>
        <option value="3000" ${(s.refresh||3000)==3000?'selected':''}>3 seconds (default)</option>
        <option value="5000" ${(s.refresh||3000)==5000?'selected':''}>5 seconds</option>
        <option value="10000" ${(s.refresh||3000)==10000?'selected':''}>10 seconds</option>
      </select>
    </div>

    <button id="save-settings-btn" class="btn-primary" style="width:100%;padding:14px">💾 Save Settings</button>
  </div>`;

  initRevealAnimations();

  document.getElementById('save-settings-btn')?.addEventListener('click', async () => {
    const cfg = {
      notif:    document.getElementById('toggle-notif').checked,
      imperial: document.getElementById('toggle-imperial').checked,
      autoconn: document.getElementById('toggle-autoconn').checked,
      refresh:  parseInt(document.getElementById('refresh-rate').value)
    };
    localStorage.setItem('vexis_settings', JSON.stringify(cfg));
    try {
      if (currentUser) {
        await setDoc(doc(db, 'settings', currentUser.uid), cfg, { merge: true });
      }
      showToast('Settings saved!', 'success');
    } catch (e) {
      showToast('Settings saved locally only.', 'info');
    }
  });
}

// ── Expose renderDashboard globally for sidebar.js ─────────────────
window.renderDashboard = renderDashboard;
window.loadVehiclesSection  = loadVehiclesSection;
window.loadReportsSection   = loadReportsSection;
window.loadProfileSection   = loadProfileSection;
window.loadSettingsSection  = loadSettingsSection;
