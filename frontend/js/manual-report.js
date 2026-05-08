/* ================================================================
   manual-report.js  —  CSV Upload → ML Predict → PDF Download
   Registered as window.loadManualReportSection(contentArea)
   ================================================================ */

import { waitForUser } from './firebase.js';
import { API_BASE }    from './api.js';

const firebaseUser = await waitForUser();
if (!firebaseUser) {
  window.location.href = 'login.html';
  throw new Error('Not authenticated');
}

function toast(msg, type = 'info') {
  const el = document.createElement('div');
  const bg = type === 'success' ? '#22c55e' : type === 'error' ? '#ef4444' : '#00e5ff';
  el.style.cssText = `position:fixed;bottom:24px;right:24px;z-index:9999;
    background:${bg};color:#000;padding:12px 20px;border-radius:10px;
    font-size:13px;font-weight:600;box-shadow:0 4px 20px rgba(0,0,0,0.4);
    animation:slideIn .3s ease;max-width:320px;`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

function buildHTML() {
  return `
<style>
  .mr-field { width:100%; padding:11px 14px; background:rgba(255,255,255,0.04);
    border:1px solid rgba(0,229,255,0.18); border-radius:10px; color:#e2e8f0;
    font-size:13px; outline:none; transition:border .2s; box-sizing:border-box; }
  .mr-field:focus { border-color:#00e5ff; box-shadow:0 0 0 2px rgba(0,229,255,0.12); }
  .mr-field-label { font-size:11px; color:#64748b; margin-bottom:5px; display:block; font-weight:600; letter-spacing:.5px; }
  .mr-field-row { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:14px; }

  .mr-upload-zone { border:2px dashed rgba(0,229,255,0.35); border-radius:16px;
    padding:40px 28px; text-align:center; cursor:pointer; transition:all 0.3s;
    background:rgba(0,229,255,0.03); }
  .mr-upload-zone:hover,.mr-upload-zone.drag-over { border-color:#00e5ff;
    background:rgba(0,229,255,0.07); transform:translateY(-2px); box-shadow:0 0 30px rgba(0,229,255,0.12); }
  .mr-upload-zone.file-ok { border-style:solid; border-color:#00e5ff; background:rgba(0,229,255,0.08); }
  .mr-upload-icon { width:60px;height:60px;margin:0 auto 12px;background:linear-gradient(135deg,rgba(0,229,255,0.15),rgba(100,220,255,0.04));
    border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:26px; }
  .mr-upload-title { font-family:var(--font-display,Orbitron,sans-serif);font-size:16px;font-weight:700;color:#e2e8f0;margin-bottom:5px; }
  .mr-upload-sub   { font-size:11px;color:#64748b; }

  .mr-analyze-btn { width:100%;padding:15px;margin-top:16px;font-size:14px;
    font-family:var(--font-display,Orbitron,sans-serif);font-weight:700;letter-spacing:1px;
    border:none;border-radius:12px;cursor:pointer;
    background:linear-gradient(135deg,#00e5ff,#0ea5e9);color:#000;
    transition:all .3s;display:flex;align-items:center;justify-content:center;gap:10px; }
  .mr-analyze-btn:hover:not(:disabled) { transform:translateY(-2px);box-shadow:0 8px 28px rgba(0,229,255,0.35); }
  .mr-analyze-btn:disabled { opacity:.55;cursor:not-allowed;transform:none; }

  .mr-progress-wrap { background:rgba(255,255,255,0.06);border-radius:999px;height:7px;overflow:hidden;margin-top:12px;display:none; }
  .mr-progress-fill { height:100%;background:linear-gradient(90deg,#00e5ff,#0ea5e9);border-radius:999px;width:0%;transition:width .4s; }

  .mr-status { display:none;padding:14px 18px;border-radius:12px;margin-top:14px;align-items:center;gap:12px; }
  .mr-status.show    { display:flex; }
  .mr-status.success { background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.3); }
  .mr-status.error   { background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3); }
  .mr-status.info    { background:rgba(0,229,255,.07);border:1px solid rgba(0,229,255,.2); }

  .mr-col-grid { display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px; }
  .mr-col-badge { background:rgba(0,229,255,.05);border:1px solid rgba(0,229,255,.14);
    border-radius:8px;padding:8px 10px;font-size:11px;font-family:monospace;color:#00e5ff; }
  .mr-col-badge span { display:block;color:#64748b;font-family:inherit;font-size:10px;margin-top:2px; }

  .mr-steps { display:flex;flex-direction:column;gap:10px; }
  .mr-step  { display:flex;align-items:flex-start;gap:12px;padding:12px 14px;
    background:rgba(255,255,255,.03);border-radius:10px;border:1px solid rgba(255,255,255,.06); }
  .mr-step-num { width:28px;height:28px;flex-shrink:0;border-radius:50%;
    background:linear-gradient(135deg,rgba(0,229,255,.18),rgba(0,229,255,.04));
    border:1px solid rgba(0,229,255,.28);display:flex;align-items:center;justify-content:center;
    font-family:var(--font-display,Orbitron,sans-serif);font-size:11px;font-weight:700;color:#00e5ff; }
  .mr-step-body { font-size:11px;color:#64748b;line-height:1.5; }
  .mr-step-title { font-weight:600;color:#e2e8f0;margin-bottom:2px; }

  .mr-sample { font-family:monospace;font-size:10px;color:#64748b;background:rgba(0,0,0,.3);
    border-radius:8px;padding:10px;overflow-x:auto;white-space:nowrap;margin-top:8px;
    border:1px solid rgba(255,255,255,.05); }
  .mr-tpl-btn { background:none;border:1px solid rgba(255,255,255,.1);color:#64748b;
    padding:8px 16px;border-radius:8px;cursor:pointer;font-size:12px;transition:all .2s;
    margin-top:12px;width:100%; }
  .mr-tpl-btn:hover { border-color:rgba(0,229,255,.35);color:#00e5ff; }
  @keyframes slideIn { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
</style>

<div class="section-header reveal">
  <div>
    <h1 class="section-title">Manual Report</h1>
    <p class="section-subtitle">Enter vehicle details, upload OBD-II CSV → AI analyses → Download PDF</p>
  </div>
</div>

<div style="display:grid;grid-template-columns:1.4fr 1fr;gap:22px;align-items:start">

  <!-- LEFT: Upload Card -->
  <div class="glass-card reveal" style="padding:26px">
    <div style="font-family:var(--font-display,Orbitron);font-size:15px;font-weight:700;color:#e2e8f0;margin-bottom:18px;display:flex;align-items:center;gap:8px">
      <span style="color:#00e5ff">📊</span> Upload Vehicle OBD Data
    </div>

    <!-- Vehicle Details -->
    <div style="margin-bottom:16px;padding:14px;background:rgba(0,229,255,0.04);border:1px solid rgba(0,229,255,0.12);border-radius:12px">
      <div style="font-size:11px;font-weight:700;color:#00e5ff;letter-spacing:.5px;margin-bottom:12px">VEHICLE DETAILS</div>
      <div class="mr-field-row">
        <div>
          <label class="mr-field-label">Vehicle Name *</label>
          <input class="mr-field" id="mr-veh-name" type="text" placeholder="e.g. Honda City" maxlength="60"/>
        </div>
        <div>
          <label class="mr-field-label">Model / Year (optional)</label>
          <input class="mr-field" id="mr-veh-model" type="text" placeholder="e.g. 2020 1.5L" maxlength="60"/>
        </div>
      </div>
    </div>

    <!-- Drop Zone -->
    <div class="mr-upload-zone" id="mr-zone">
      <div class="mr-upload-icon" id="mr-icon">📁</div>
      <div class="mr-upload-title" id="mr-title">Drop CSV here or click to browse</div>
      <div class="mr-upload-sub"   id="mr-sub">Supports .csv files — minimum 5 rows</div>
      <input type="file" id="mr-file-input" accept=".csv" style="display:none"/>
    </div>

    <!-- Progress -->
    <div class="mr-progress-wrap" id="mr-prog-wrap">
      <div class="mr-progress-fill" id="mr-prog-fill"></div>
    </div>

    <!-- Status -->
    <div class="mr-status" id="mr-status">
      <span id="mr-status-icon" style="font-size:20px">⏳</span>
      <div>
        <div id="mr-status-title" style="font-weight:600;color:#e2e8f0;font-size:13px">Processing...</div>
        <div id="mr-status-msg"   style="font-size:11px;color:#64748b;margin-top:2px"></div>
      </div>
    </div>

    <!-- Analyse Button -->
    <button class="mr-analyze-btn" id="mr-analyze-btn" disabled>
      <svg viewBox="0 0 24 24" fill="none" width="16" height="16">
        <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"
          stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <span id="mr-btn-text">Select a CSV file first</span>
    </button>

    <button class="mr-tpl-btn" id="mr-tpl-btn">⬇ Download Sample CSV Template</button>
  </div>

  <!-- RIGHT: Guide -->
  <div style="display:flex;flex-direction:column;gap:18px">
    <div class="glass-card reveal" style="padding:22px">
      <div style="font-family:var(--font-display,Orbitron);font-size:13px;font-weight:700;color:#e2e8f0;margin-bottom:14px">How It Works</div>
      <div class="mr-steps">
        <div class="mr-step"><div class="mr-step-num">1</div><div class="mr-step-body"><div class="mr-step-title">Enter vehicle details</div>Name and model so the report is linked to your vehicle</div></div>
        <div class="mr-step"><div class="mr-step-num">2</div><div class="mr-step-body"><div class="mr-step-title">Upload your CSV</div>Drag & drop or click browse — minimum 5 rows required</div></div>
        <div class="mr-step"><div class="mr-step-num">3</div><div class="mr-step-body"><div class="mr-step-title">AI analyses data</div>ML model scores Engine, Fuel, Efficiency, Driving & Thermal</div></div>
        <div class="mr-step"><div class="mr-step-num">4</div><div class="mr-step-body"><div class="mr-step-title">PDF downloads + saved</div>Report auto-downloads & appears in Past Reports</div></div>
      </div>
    </div>

    <div class="glass-card reveal" style="padding:22px">
      <div style="font-family:var(--font-display,Orbitron);font-size:13px;font-weight:700;color:#e2e8f0;margin-bottom:4px">Required CSV Columns</div>
      <div style="font-size:11px;color:#64748b;margin-bottom:10px">All 9 columns with numeric values</div>
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
  const vehName    = document.getElementById('mr-veh-name');
  const vehModel   = document.getElementById('mr-veh-model');

  let selectedFile = null;

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

  function checkReady() {
    if (selectedFile) {
      analyzeBtn.disabled = false;
      btnText.textContent = '🔬 Analyse & Download Report';
    }
  }

  function resetZone() {
    selectedFile = null;
    fileInput.value = '';
    zone.classList.remove('file-ok');
    mrIcon.textContent  = '📁';
    mrTitle.textContent = 'Drop CSV here or click to browse';
    mrSub.textContent   = 'Supports .csv files — minimum 5 rows';
    analyzeBtn.disabled = true;
    btnText.textContent = 'Select a CSV file first';
    progFill.style.width = '0%';
    clearStatus();
  }

  function onFileSelected(file) {
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setStatus('error', '❌', 'Wrong file type', 'Please select a .csv file'); return;
    }
    selectedFile = file;
    zone.classList.add('file-ok');
    mrIcon.textContent  = '✅';
    mrTitle.textContent = file.name;
    mrSub.textContent   = `${(file.size / 1024).toFixed(1)} KB — ready to analyse`;
    checkReady();
    clearStatus();
  }

  zone.addEventListener('click',    () => fileInput.click());
  zone.addEventListener('dragover',  e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) onFileSelected(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener('change', () => { if (fileInput.files[0]) onFileSelected(fileInput.files[0]); });

  analyzeBtn.addEventListener('click', async () => {
    if (!selectedFile) return;

    const vehicleName  = vehName.value.trim()  || 'My Vehicle';
    const vehicleModel = vehModel.value.trim();

    analyzeBtn.disabled = true;
    btnText.textContent = '⏳ Analysing…';
    setProgress(20);
    setStatus('info', '⏳', 'Running ML Analysis',
      `Uploading CSV for ${vehicleName} and running prediction models…`);

    try {
      const token = await firebaseUser.getIdToken(true);
      const form  = new FormData();
      form.append('file',          selectedFile);
      form.append('vehicle_name',  vehicleName);
      form.append('vehicle_model', vehicleModel);

      setProgress(50);

      // 120s timeout for CSV analysis
      const controller = new AbortController();
      const tid = setTimeout(() => controller.abort(), 120000);

      const res = await fetch(`${API_BASE}/predict/csv`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: form,
        signal: controller.signal
      });
      clearTimeout(tid);

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
      a.download = `vexis_${vehicleName.replace(/\s+/g,'_')}_${new Date().toISOString().slice(0,10)}.pdf`;
      document.body.appendChild(a); a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      setProgress(100);
      setStatus('success', '✅', 'Report Downloaded!',
        `PDF for ${vehicleName} saved. Check Past Reports to view it again.`);
      toast('PDF report downloaded!', 'success');
      setTimeout(resetZone, 6000);

    } catch (err) {
      const msg = err.name === 'AbortError'
        ? 'Request timed out (120s). Backend may be cold-starting — try again in 30s.'
        : err.message || 'Something went wrong.';
      setStatus('error', '❌', 'Analysis Failed', msg);
      toast('Error: ' + msg, 'error');
      analyzeBtn.disabled = false;
      btnText.textContent = '🔬 Analyse & Download Report';
      setProgress(0);
    }
  });

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

window.loadManualReportSection = function(contentArea) {
  contentArea.innerHTML = buildHTML();
  wireEvents();
};
