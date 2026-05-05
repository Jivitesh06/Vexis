/* ================================================================
   manual-report.js — CSV Upload → ML Batch → PDF Download
   Exposes window.loadManualReportSection(container) for sidebar.js
   ================================================================ */

import { API_BASE } from './api.js';
import { waitForUser } from './firebase.js';

// ── Section renderer — called by sidebar.js loadSection('manual') ─
window.loadManualReportSection = async function (container) {

  const firebaseUser = await waitForUser();
  if (!firebaseUser) return;

  container.innerHTML = `
  <style>
    .mr-grid { display:grid; grid-template-columns:1.4fr 1fr; gap:24px; align-items:start; }
    @media(max-width:900px){ .mr-grid{ grid-template-columns:1fr; } }

    .upload-zone {
      border: 2px dashed rgba(0,229,255,0.3);
      border-radius: 16px; padding:50px 30px;
      text-align:center; cursor:pointer;
      transition:all 0.3s ease;
      background:rgba(0,229,255,0.02);
    }
    .upload-zone:hover, .upload-zone.drag-over {
      border-color:var(--accent);
      background:rgba(0,229,255,0.07);
      transform:translateY(-2px);
      box-shadow:0 0 28px rgba(0,229,255,0.1);
    }
    .upload-zone.file-ok {
      border-color:var(--accent); border-style:solid;
      background:rgba(0,229,255,0.06);
    }
    .uz-icon { font-size:44px; margin-bottom:14px; }
    .uz-title { font-family:var(--font-display); font-size:18px; font-weight:700; color:var(--text); margin-bottom:6px; }
    .uz-sub   { font-size:13px; color:var(--muted); }

    .prog-wrap { background:rgba(255,255,255,0.06); border-radius:999px; height:7px; overflow:hidden; margin-top:16px; display:none; }
    .prog-fill  { height:100%; background:linear-gradient(90deg,#00e5ff,#0ea5e9); border-radius:999px; width:0%; transition:width 0.4s ease; }

    .status-box { display:none; padding:16px 20px; border-radius:10px; margin-top:16px; align-items:center; gap:14px; }
    .status-box.show { display:flex; }
    .status-box.info    { background:rgba(0,229,255,0.08); border:1px solid rgba(0,229,255,0.2); }
    .status-box.success { background:rgba(34,197,94,0.08); border:1px solid rgba(34,197,94,0.25); }
    .status-box.error   { background:rgba(239,68,68,0.08); border:1px solid rgba(239,68,68,0.25); }
    .status-icon { font-size:22px; flex-shrink:0; }
    .status-title{ font-weight:600; font-size:14px; color:var(--text); }
    .status-msg  { font-size:12px; color:var(--muted); margin-top:2px; }

    .analyse-btn {
      width:100%; padding:16px; margin-top:20px;
      font-family:var(--font-display); font-size:15px; font-weight:700; letter-spacing:1px;
      border:none; border-radius:12px; cursor:pointer;
      background:linear-gradient(135deg,#00e5ff,#0ea5e9); color:#000;
      display:flex; align-items:center; justify-content:center; gap:10px;
      transition:all 0.3s ease;
    }
    .analyse-btn:hover:not(:disabled){ transform:translateY(-2px); box-shadow:0 8px 28px rgba(0,229,255,0.35); }
    .analyse-btn:disabled{ opacity:0.55; cursor:not-allowed; transform:none; }

    .tmpl-btn {
      width:100%; margin-top:12px; padding:10px;
      background:none; border:1px solid rgba(255,255,255,0.1);
      border-radius:8px; color:var(--muted); font-size:12px;
      cursor:pointer; transition:all 0.2s ease;
    }
    .tmpl-btn:hover{ border-color:rgba(0,229,255,0.3); color:var(--accent); }

    .col-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-top:14px; }
    .col-chip {
      background:rgba(0,229,255,0.05); border:1px solid rgba(0,229,255,0.13);
      border-radius:8px; padding:9px 12px;
      font-family:monospace; font-size:12px; color:var(--accent);
    }
    .col-chip span { display:block; font-family:var(--font-body); font-size:10px; color:var(--muted); margin-top:2px; }

    .sample-csv {
      font-family:monospace; font-size:10px; color:var(--muted);
      background:rgba(0,0,0,0.3); border:1px solid rgba(255,255,255,0.06);
      border-radius:8px; padding:10px; overflow-x:auto; white-space:nowrap; margin-top:12px;
    }

    .step-list { display:flex; flex-direction:column; gap:10px; }
    .step-row  { display:flex; align-items:flex-start; gap:14px; padding:14px 16px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06); border-radius:10px; }
    .step-num  { width:30px; height:30px; flex-shrink:0; border-radius:50%; background:rgba(0,229,255,0.1); border:1px solid rgba(0,229,255,0.3); display:flex; align-items:center; justify-content:center; font-family:var(--font-display); font-size:12px; font-weight:700; color:var(--accent); }
    .step-body .step-hd  { font-weight:600; font-size:13px; color:var(--text); margin-bottom:2px; }
    .step-body .step-sub { font-size:12px; color:var(--muted); line-height:1.5; }
  </style>

  <div class="section-header reveal">
    <div>
      <h1 class="section-title">Manual Report</h1>
      <p class="section-subtitle">Upload OBD-II CSV → AI analyses → Download PDF report instantly</p>
    </div>
  </div>

  <div class="mr-grid">

    <!-- LEFT: Upload -->
    <div class="glass-card reveal" style="padding:26px">
      <div style="font-family:var(--font-display);font-size:15px;font-weight:700;color:var(--text);margin-bottom:18px;display:flex;align-items:center;gap:8px">
        <span style="color:var(--accent)">📊</span> Upload Vehicle CSV Data
      </div>

      <div class="upload-zone" id="mr-zone">
        <div class="uz-icon" id="mr-icon">📁</div>
        <div class="uz-title" id="mr-title">Drop CSV here or click to browse</div>
        <div class="uz-sub" id="mr-sub">Supports .csv files · Min 5 rows required</div>
        <input type="file" id="mr-file-input" accept=".csv" style="display:none"/>
      </div>

      <div class="prog-wrap" id="mr-prog-wrap">
        <div class="prog-fill" id="mr-prog-fill"></div>
      </div>

      <div class="status-box" id="mr-status">
        <div class="status-icon" id="mr-status-icon">⏳</div>
        <div>
          <div class="status-title" id="mr-status-title">Processing...</div>
          <div class="status-msg"   id="mr-status-msg">Running ML analysis</div>
        </div>
      </div>

      <button class="analyse-btn" id="mr-analyse-btn" disabled>
        <svg viewBox="0 0 24 24" fill="none" width="18" height="18">
          <circle cx="11" cy="11" r="8" stroke="currentColor" stroke-width="1.8"/>
          <path d="m21 21-4.35-4.35" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
        </svg>
        <span id="mr-btn-text">Select a CSV file first</span>
      </button>

      <button class="tmpl-btn" id="mr-tmpl-btn">⬇ Download Sample CSV Template</button>
    </div>

    <!-- RIGHT: Info -->
    <div style="display:flex;flex-direction:column;gap:20px">

      <!-- How it works -->
      <div class="glass-card reveal" style="padding:22px">
        <div style="font-family:var(--font-display);font-size:13px;font-weight:700;color:var(--text);margin-bottom:14px">How It Works</div>
        <div class="step-list">
          <div class="step-row"><div class="step-num">1</div><div class="step-body"><div class="step-hd">Prepare your CSV</div><div class="step-sub">Download the template or export from your OBD scanner app</div></div></div>
          <div class="step-row"><div class="step-num">2</div><div class="step-body"><div class="step-hd">Upload the file</div><div class="step-sub">Drag & drop or click to select · Minimum 5 data rows</div></div></div>
          <div class="step-row"><div class="step-num">3</div><div class="step-body"><div class="step-hd">AI analyses your data</div><div class="step-sub">ML models score engine, fuel, efficiency, driving & thermal</div></div></div>
          <div class="step-row"><div class="step-num">4</div><div class="step-body"><div class="step-hd">Download PDF report</div><div class="step-sub">Full report with scores, issues & recommendations</div></div></div>
        </div>
      </div>

      <!-- Required columns -->
      <div class="glass-card reveal" style="padding:22px">
        <div style="font-family:var(--font-display);font-size:13px;font-weight:700;color:var(--text);margin-bottom:4px">Required CSV Columns</div>
        <div style="font-size:11px;color:var(--muted);margin-bottom:12px">All 9 columns must be present (numeric values)</div>
        <div class="col-grid">
          <div class="col-chip">rpm<span>Engine RPM</span></div>
          <div class="col-chip">speed<span>Speed km/h</span></div>
          <div class="col-chip">load<span>Engine Load %</span></div>
          <div class="col-chip">coolant_temp<span>Coolant °C</span></div>
          <div class="col-chip">throttle_pos<span>Throttle %</span></div>
          <div class="col-chip">intake_temp<span>Intake Air °C</span></div>
          <div class="col-chip">maf<span>MAF g/s</span></div>
          <div class="col-chip">stft<span>Short Fuel Trim</span></div>
          <div class="col-chip">ltft<span>Long Fuel Trim</span></div>
        </div>
        <div class="sample-csv">rpm,speed,load,coolant_temp,throttle_pos,intake_temp,maf,stft,ltft<br>1800,45,42,87,22,35,8.5,1.2,-0.8<br>2100,60,55,89,28,36,11.2,0.8,-1.1</div>
      </div>

    </div>
  </div>`;

  // ── Wire up UI after injecting ──────────────────────────────────
  _initManualReportUI(container, firebaseUser);
};

function _initManualReportUI(container, firebaseUser) {
  const zone      = container.querySelector('#mr-zone');
  const fileInput = container.querySelector('#mr-file-input');
  const analyseBtn= container.querySelector('#mr-analyse-btn');
  const btnText   = container.querySelector('#mr-btn-text');
  const progWrap  = container.querySelector('#mr-prog-wrap');
  const progFill  = container.querySelector('#mr-prog-fill');
  const statusBox = container.querySelector('#mr-status');
  const statusIcon= container.querySelector('#mr-status-icon');
  const statusTtl = container.querySelector('#mr-status-title');
  const statusMsg = container.querySelector('#mr-status-msg');
  const mrIcon    = container.querySelector('#mr-icon');
  const mrTitle   = container.querySelector('#mr-title');
  const mrSub     = container.querySelector('#mr-sub');
  const tmplBtn   = container.querySelector('#mr-tmpl-btn');

  let selectedFile = null;

  // Drag & drop
  zone.addEventListener('click', () => fileInput.click());
  zone.addEventListener('dragover',  e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) handleFile(fileInput.files[0]);
  });

  function handleFile(f) {
    if (!f.name.endsWith('.csv')) {
      showStatus('error', '❌', 'Wrong file type', 'Please upload a .csv file');
      return;
    }
    selectedFile = f;
    zone.classList.add('file-ok');
    mrIcon.textContent  = '✅';
    mrTitle.textContent = f.name;
    mrSub.textContent   = `${(f.size/1024).toFixed(1)} KB · Ready to analyse`;
    analyseBtn.disabled = false;
    btnText.textContent = '🔬 Analyse & Download Report';
    hideStatus();
  }

  // Analyse
  analyseBtn.addEventListener('click', async () => {
    if (!selectedFile) return;
    analyseBtn.disabled = true;
    btnText.textContent = '⏳ Analysing...';
    setProgress(30);
    showStatus('info', '⏳', 'Running ML Analysis', 'Sending data to Vexis AI engine…');

    try {
      const token    = await firebaseUser.getIdToken(true);
      const formData = new FormData();
      formData.append('file', selectedFile);

      setProgress(60);

      const res = await fetch(`${API_BASE}/predict/csv`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      });

      setProgress(90);

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(err.error || 'Analysis failed');
      }

      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = Object.assign(document.createElement('a'), {
        href: url,
        download: `vexis_report_${new Date().toISOString().slice(0,10)}.pdf`
      });
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      setProgress(100);
      showStatus('success', '✅', 'Report Downloaded!', 'PDF health report saved to your device.');
      if (typeof window.showToast === 'function') window.showToast('PDF report downloaded!', 'success');

      setTimeout(resetZone, 4000);
    } catch (err) {
      showStatus('error', '❌', 'Analysis Failed', err.message || 'Something went wrong. Try again.');
      if (typeof window.showToast === 'function') window.showToast('Failed: ' + err.message, 'error');
      analyseBtn.disabled = false;
      btnText.textContent = '🔬 Analyse & Download Report';
      setProgress(0);
    }
  });

  // Sample template download
  tmplBtn.addEventListener('click', () => {
    const csv = [
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
      '1700,40,48,88,20,35,9.1,0.9,-0.9'
    ].join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    const a   = Object.assign(document.createElement('a'), { href: url, download: 'vexis_obd_template.csv' });
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
    if (typeof window.showToast === 'function') window.showToast('Template downloaded!', 'success');
  });

  // Helpers
  function showStatus(type, icon, title, msg) {
    statusBox.className    = `status-box ${type} show`;
    statusIcon.textContent = icon;
    statusTtl.textContent  = title;
    statusMsg.textContent  = msg;
  }
  function hideStatus() { statusBox.className = 'status-box'; }
  function setProgress(pct) {
    progWrap.style.display = 'block';
    progFill.style.width   = pct + '%';
    if (pct >= 100) setTimeout(() => { progWrap.style.display = 'none'; }, 700);
  }
  function resetZone() {
    selectedFile = null; fileInput.value = '';
    zone.classList.remove('file-ok');
    mrIcon.textContent  = '📁';
    mrTitle.textContent = 'Drop CSV here or click to browse';
    mrSub.textContent   = 'Supports .csv files · Min 5 rows required';
    analyseBtn.disabled = true;
    btnText.textContent = 'Select a CSV file first';
    hideStatus(); progFill.style.width = '0%';
  }
}
