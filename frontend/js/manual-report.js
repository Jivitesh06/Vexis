/* ================================================================
   manual-report.js  —  CSV Upload → ML Predict → PDF Download
   Registered as window.loadManualReportSection(contentArea)
   so sidebar.js can call it when the user navigates to 'manual'.
   ================================================================ */

import { waitForUser } from './firebase.js';
import { API_BASE }    from './api.js';

// ── Get authenticated user (waits for Firebase init) ──────────────
const firebaseUser = await waitForUser();
if (!firebaseUser) {
  window.location.href = 'login.html';
  throw new Error('Not authenticated');
}

// ── Simple toast (api.js does not export showToast) ───────────────
function toast(msg, type = 'info') {
  const el = document.createElement('div');
  const bg = type === 'success' ? '#22c55e'
           : type === 'error'   ? '#ef4444'
           :                      '#00e5ff';
  el.style.cssText = `
    position:fixed;bottom:24px;right:24px;z-index:9999;
    background:${bg};color:#000;padding:12px 20px;border-radius:10px;
    font-size:13px;font-weight:600;box-shadow:0 4px 20px rgba(0,0,0,0.4);
    animation:slideIn .3s ease;max-width:320px;`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// ── HTML template injected into #content-area ─────────────────────
function buildHTML() {
  return `
<style>
  .mr-upload-zone {
    border: 2px dashed rgba(0,229,255,0.35);
    border-radius: 16px;
    padding: 52px 32px;
    text-align: center;
    cursor: pointer;
    transition: all 0.3s ease;
    background: rgba(0,229,255,0.03);
  }
  .mr-upload-zone:hover, .mr-upload-zone.drag-over {
    border-color: #00e5ff;
    background: rgba(0,229,255,0.07);
    transform: translateY(-2px);
    box-shadow: 0 0 30px rgba(0,229,255,0.12);
  }
  .mr-upload-zone.file-ok {
    border-style: solid;
    border-color: #00e5ff;
    background: rgba(0,229,255,0.08);
  }
  .mr-upload-icon {
    width: 68px; height: 68px; margin: 0 auto 16px;
    background: linear-gradient(135deg,rgba(0,229,255,0.15),rgba(100,220,255,0.04));
    border-radius: 50%; display:flex; align-items:center; justify-content:center;
    font-size:30px;
  }
  .mr-upload-title { font-family:var(--font-display,Orbitron,sans-serif); font-size:18px; font-weight:700; color:var(--text,#e2e8f0); margin-bottom:6px; }
  .mr-upload-sub   { font-size:12px; color:var(--muted,#64748b); }

  .mr-analyze-btn {
    width:100%; padding:16px; margin-top:20px;
    font-size:15px; font-family:var(--font-display,Orbitron,sans-serif);
    font-weight:700; letter-spacing:1px;
    border:none; border-radius:12px; cursor:pointer;
    background:linear-gradient(135deg,#00e5ff,#0ea5e9); color:#000;
    transition:all .3s ease; display:flex; align-items:center; justify-content:center; gap:10px;
  }
  .mr-analyze-btn:hover:not(:disabled) { transform:translateY(-2px); box-shadow:0 8px 28px rgba(0,229,255,0.35); }
  .mr-analyze-btn:disabled { opacity:.55; cursor:not-allowed; transform:none; }

  .mr-progress-wrap { background:rgba(255,255,255,0.06); border-radius:999px; height:7px; overflow:hidden; margin-top:14px; display:none; }
  .mr-progress-fill { height:100%; background:linear-gradient(90deg,#00e5ff,#0ea5e9); border-radius:999px; width:0%; transition:width .4s ease; }

  .mr-status { display:none; padding:16px 20px; border-radius:12px; margin-top:16px; align-items:center; gap:14px; }
  .mr-status.show    { display:flex; }
  .mr-status.success { background:rgba(34,197,94,.1);  border:1px solid rgba(34,197,94,.3); }
  .mr-status.error   { background:rgba(239,68,68,.1);  border:1px solid rgba(239,68,68,.3); }
  .mr-status.info    { background:rgba(0,229,255,.07); border:1px solid rgba(0,229,255,.2); }

  .mr-col-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-top:12px; }
  .mr-col-badge {
    background:rgba(0,229,255,.05); border:1px solid rgba(0,229,255,.14);
    border-radius:8px; padding:9px 12px; font-size:12px; font-family:monospace; color:#00e5ff;
  }
  .mr-col-badge span { display:block; color:var(--muted,#64748b); font-family:inherit; font-size:10px; margin-top:3px; }

  .mr-steps { display:flex; flex-direction:column; gap:10px; }
  .mr-step  { display:flex; align-items:flex-start; gap:14px; padding:14px 16px;
               background:rgba(255,255,255,.03); border-radius:10px; border:1px solid rgba(255,255,255,.06); }
  .mr-step-num {
    width:30px; height:30px; flex-shrink:0; border-radius:50%;
    background:linear-gradient(135deg,rgba(0,229,255,.18),rgba(0,229,255,.04));
    border:1px solid rgba(0,229,255,.28); display:flex; align-items:center; justify-content:center;
    font-family:var(--font-display,Orbitron,sans-serif); font-size:12px; font-weight:700; color:#00e5ff;
  }
  .mr-step-body  { font-size:12px; color:var(--muted,#64748b); line-height:1.5; }
  .mr-step-title { font-weight:600; color:var(--text,#e2e8f0); margin-bottom:2px; }

  .mr-sample { font-family:monospace; font-size:10.5px; color:var(--muted,#64748b);
    background:rgba(0,0,0,.3); border-radius:8px; padding:10px; overflow-x:auto;
    white-space:nowrap; margin-top:10px; border:1px solid rgba(255,255,255,.05); }

  .mr-tpl-btn {
    background:none; border:1px solid rgba(255,255,255,.1); color:var(--muted,#64748b);
    padding:8px 18px; border-radius:8px; cursor:pointer; font-size:12px;
    transition:all .2s; margin-top:14px; width:100%;
  }
  .mr-tpl-btn:hover { border-color:rgba(0,229,255,.35); color:#00e5ff; }

  @keyframes slideIn { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } }
</style>

<div class="section-header reveal">
  <div>
    <h1 class="section-title">Manual Report</h1>
    <p class="section-subtitle">Upload OBD-II CSV data → AI analyses → Download PDF report instantly</p>
  </div>
</div>

<div style="display:grid;grid-template-columns:1.4fr 1fr;gap:22px;align-items:start">

  <!-- LEFT: Upload Card -->
  <div class="glass-card reveal" style="padding:26px">
    <div style="font-family:var(--font-display,Orbitron);font-size:15px;font-weight:700;color:var(--text,#e2e8f0);margin-bottom:18px;display:flex;align-items:center;gap:8px">
      <span style="color:#00e5ff">📊</span> Upload Vehicle OBD Data
    </div>

    <!-- Drop Zone -->
    <div class="mr-upload-zone" id="mr-zone">
      <div class="mr-upload-icon" id="mr-icon">📁</div>
      <div class="mr-upload-title" id="mr-title">Drop CSV here or click to browse</div>
      <div class="mr-upload-sub"   id="mr-sub">Supports .csv files with OBD-II sensor columns (min 5 rows)</div>
      <input type="file" id="mr-file-input" accept=".csv" style="display:none"/>
    </div>

    <!-- Progress Bar -->
    <div class="mr-progress-wrap" id="mr-prog-wrap">
      <div class="mr-progress-fill" id="mr-prog-fill"></div>
    </div>

    <!-- Status -->
    <div class="mr-status" id="mr-status">
      <span id="mr-status-icon" style="font-size:22px">⏳</span>
      <div>
        <div id="mr-status-title" style="font-weight:600;color:var(--text,#e2e8f0);font-size:13px">Processing...</div>
        <div id="mr-status-msg"   style="font-size:11px;color:var(--muted,#64748b);margin-top:2px">Running ML analysis on your data</div>
      </div>
    </div>

    <!-- Analyse Button -->
    <button class="mr-analyze-btn" id="mr-analyze-btn" disabled>
      <svg viewBox="0 0 24 24" fill="none" width="18" height="18">
        <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"
          stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <span id="mr-btn-text">Select a CSV file first</span>
    </button>

    <!-- Template Download -->
    <button class="mr-tpl-btn" id="mr-tpl-btn">⬇ Download Sample CSV Template</button>
  </div>

  <!-- RIGHT: Guide -->
  <div style="display:flex;flex-direction:column;gap:18px">

    <!-- How it works -->
    <div class="glass-card reveal" style="padding:22px">
      <div style="font-family:var(--font-display,Orbitron);font-size:13px;font-weight:700;color:var(--text,#e2e8f0);margin-bottom:14px">How It Works</div>
      <div class="mr-steps">
        <div class="mr-step"><div class="mr-step-num">1</div><div class="mr-step-body"><div class="mr-step-title">Prepare your CSV</div>Download the template or export OBD data from your scanner app</div></div>
        <div class="mr-step"><div class="mr-step-num">2</div><div class="mr-step-body"><div class="mr-step-title">Upload the file</div>Drag & drop or click browse — minimum 5 rows required</div></div>
        <div class="mr-step"><div class="mr-step-num">3</div><div class="mr-step-body"><div class="mr-step-title">AI analyses data</div>ML model scores Engine, Fuel, Efficiency, Driving & Thermal</div></div>
        <div class="mr-step"><div class="mr-step-num">4</div><div class="mr-step-body"><div class="mr-step-title">Download PDF</div>Full report with scores, issues & recommendations auto-downloads</div></div>
      </div>
    </div>

    <!-- Required Columns -->
    <div class="glass-card reveal" style="padding:22px">
      <div style="font-family:var(--font-display,Orbitron);font-size:13px;font-weight:700;color:var(--text,#e2e8f0);margin-bottom:4px">Required CSV Columns</div>
      <div style="font-size:11px;color:var(--muted,#64748b);margin-bottom:12px">All 9 columns must be present with numeric values</div>
      <div class="mr-col-grid">
        <div class="mr-col-badge">rpm<span>Engine RPM</span></div>
        <div class="mr-col-badge">speed<span>Speed km/h</span></div>
        <div class="mr-col-badge">load<span>Engine Load %</span></div>
        <div class="mr-col-badge">coolant_temp<span>Coolant °C</span></div>
        <div class="mr-col-badge">throttle_pos<span>Throttle %</span></div>
        <div class="mr-col-badge">intake_temp<span>Intake Air °C</span></div>
        <div class="mr-col-badge">maf<span>MAF g/s</span></div>
        <div class="mr-col-badge">stft<span>Short Fuel Trim</span></div>
        <div class="mr-col-badge">ltft<span>Long Fuel Trim</span></div>
      </div>
      <div class="mr-sample">rpm,speed,load,coolant_temp,throttle_pos,intake_temp,maf,stft,ltft
1800,45,42,87,22,35,8.5,1.2,-0.8
2100,60,55,89,28,36,11.2,0.8,-1.1</div>
    </div>

  </div>
</div>`;
}

// ── Wire up all events after HTML is injected ─────────────────────
function wireEvents() {
  const zone       = document.getElementById('mr-zone');
  const fileInput  = document.getElementById('mr-file-input');
  const analyzeBtn = document.getElementById('mr-analyze-btn');
  const btnText    = document.getElementById('mr-btn-text');
  const progWrap   = document.getElementById('mr-prog-wrap');
  const progFill   = document.getElementById('mr-prog-fill');
  const status     = document.getElementById('mr-status');
  const statusIcon = document.getElementById('mr-status-icon');
  const statusTtl  = document.getElementById('mr-status-title');
  const statusMsg  = document.getElementById('mr-status-msg');
  const mrIcon     = document.getElementById('mr-icon');
  const mrTitle    = document.getElementById('mr-title');
  const mrSub      = document.getElementById('mr-sub');
  const tplBtn     = document.getElementById('mr-tpl-btn');

  let selectedFile = null;

  // ── Helpers ──────────────────────────────────────────────────────
  function setStatus(type, icon, title, msg) {
    status.className = `mr-status ${type} show`;
    statusIcon.textContent = icon;
    statusTtl.textContent  = title;
    statusMsg.textContent  = msg;
  }
  function clearStatus() { status.className = 'mr-status'; }

  function setProgress(pct) {
    progWrap.style.display = 'block';
    progFill.style.width   = pct + '%';
    if (pct >= 100) setTimeout(() => { progWrap.style.display = 'none'; }, 700);
  }

  function resetZone() {
    selectedFile = null;
    fileInput.value = '';
    zone.classList.remove('file-ok');
    mrIcon.textContent  = '📁';
    mrTitle.textContent = 'Drop CSV here or click to browse';
    mrSub.textContent   = 'Supports .csv files with OBD-II sensor columns (min 5 rows)';
    analyzeBtn.disabled = true;
    btnText.textContent = 'Select a CSV file first';
    progFill.style.width = '0%';
    clearStatus();
  }

  function onFileSelected(file) {
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setStatus('error', '❌', 'Wrong file type', 'Please select a .csv file');
      return;
    }
    selectedFile = file;
    zone.classList.add('file-ok');
    mrIcon.textContent  = '✅';
    mrTitle.textContent = file.name;
    mrSub.textContent   = `${(file.size / 1024).toFixed(1)} KB — ready to analyse`;
    analyzeBtn.disabled = false;
    btnText.textContent = '🔬 Analyse & Download Report';
    clearStatus();
  }

  // ── Drag & Drop ──────────────────────────────────────────────────
  zone.addEventListener('click', () => fileInput.click());
  zone.addEventListener('dragover',  e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) onFileSelected(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) onFileSelected(fileInput.files[0]);
  });

  // ── Analyse ──────────────────────────────────────────────────────
  analyzeBtn.addEventListener('click', async () => {
    if (!selectedFile) return;

    analyzeBtn.disabled = true;
    btnText.textContent = '⏳ Analysing…';
    setProgress(20);
    setStatus('info', '⏳', 'Running ML Analysis', 'Uploading CSV and running prediction models…');

    try {
      const token = await firebaseUser.getIdToken(true);
      const form  = new FormData();
      form.append('file', selectedFile);

      setProgress(50);

      const res = await fetch(`${API_BASE}/predict/csv`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: form
      });

      setProgress(85);

      if (!res.ok) {
        let errMsg = 'Analysis failed';
        try { errMsg = (await res.json()).error || errMsg; } catch (_) {}
        throw new Error(errMsg);
      }

      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = `vexis_report_${new Date().toISOString().slice(0,10)}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      setProgress(100);
      setStatus('success', '✅', 'Report Downloaded!', 'Your PDF vehicle health report has been saved.');
      toast('PDF report downloaded!', 'success');
      setTimeout(resetZone, 5000);

    } catch (err) {
      setStatus('error', '❌', 'Analysis Failed', err.message || 'Something went wrong. Try again.');
      toast('Error: ' + err.message, 'error');
      analyzeBtn.disabled = false;
      btnText.textContent = '🔬 Analyse & Download Report';
      setProgress(0);
    }
  });

  // ── Template Download ─────────────────────────────────────────────
  tplBtn.addEventListener('click', () => {
    const rows = [
      'rpm,speed,load,coolant_temp,throttle_pos,intake_temp,maf,stft,ltft',
      '800,0,25,82,8,30,2.1,0.8,-0.5',
      '1200,20,32,85,12,33,4.2,1.0,-0.8',
      '1800,45,42,87,22,35,8.5,1.2,-0.8',
      '2100,60,55,89,28,36,11.2,0.8,-1.1',
      '2500,75,65,91,35,38,14.8,0.5,-1.5',
      '3000,90,75,93,45,40,18.2,-0.2,-1.8',
      '1500,30,35,88,15,34,6.1,1.5,-0.3',
      '900,5,28,84,9,31,2.8,1.1,-0.6',
      '2200,65,60,90,32,37,12.5,0.6,-1.3',
      '1700,40,48,88,20,35,9.1,0.9,-0.9',
    ];
    const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = 'vexis_obd_template.csv';
    document.body.appendChild(a); a.click();
    document.body.removeChild(a); URL.revokeObjectURL(url);
    toast('Template downloaded!', 'success');
  });
}

// ── Entry point called by sidebar.js ─────────────────────────────
window.loadManualReportSection = function(contentArea) {
  contentArea.innerHTML = buildHTML();
  wireEvents();
};
