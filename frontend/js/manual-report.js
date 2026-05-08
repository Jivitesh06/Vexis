/* ================================================================
   manual-report.js  —  CSV Upload → ML Predict → Firestore + PDF
   ================================================================ */

import { waitForUser } from './firebase.js';
import {
  auth, db, collection, addDoc, serverTimestamp
} from './firebase.js';
import { API_BASE } from './api.js';

const firebaseUser = await waitForUser();
if (!firebaseUser) {
  window.location.href = 'login.html';
  throw new Error('Not authenticated');
}

/* ── tiny toast ── */
function toast(msg, type = 'info') {
  const bg = type === 'success' ? '#22c55e' : type === 'error' ? '#ef4444' : '#00e5ff';
  const el = Object.assign(document.createElement('div'), { textContent: msg });
  el.style.cssText = `position:fixed;bottom:24px;right:24px;z-index:9999;
    background:${bg};color:#000;padding:12px 20px;border-radius:10px;
    font-size:13px;font-weight:600;box-shadow:0 4px 20px rgba(0,0,0,.4);
    animation:slideIn .3s ease;max-width:320px;`;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

/* ── base64 → PDF download ── */
function downloadBase64PDF(b64, filename) {
  const bytes  = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const blob   = new Blob([bytes], { type: 'application/pdf' });
  const url    = URL.createObjectURL(blob);
  const a      = Object.assign(document.createElement('a'), { href: url, download: filename });
  document.body.appendChild(a); a.click();
  document.body.removeChild(a); URL.revokeObjectURL(url);
}

/* ── save report to Firestore ── */
async function saveReportToFirestore(uid, payload) {
  try {
    await addDoc(collection(db, `users/${uid}/reports`), {
      source:        'csv_upload',
      vehicle_name:  payload.vehicle_name  || 'My Vehicle',
      vehicle_model: payload.vehicle_model || '',
      overall_score: payload.scores?.overall    || 0,
      engine_score:  payload.scores?.engine     || 0,
      fuel_score:    payload.scores?.fuel       || 0,
      driving_score: payload.scores?.driving    || 0,
      efficiency_score: payload.scores?.efficiency || 0,
      thermal_score: payload.scores?.thermal    || 0,
      status_label:  payload.status_label || '',
      failure_risk:  payload.failure_risk || false,
      issues:        payload.issues       || [],
      quality:       payload.quality      || '',
      rows_analysed: payload.rows_analysed || 0,
      backend_report_id: payload.report_id || null,
      // Store PDF so user can always re-download without hitting the backend
      pdf_base64:    payload.pdf_base64   || null,
      pdf_filename:  payload.filename     || `vexis_${payload.vehicle_name || 'report'}_report.pdf`,
      timestamp:     serverTimestamp(),
    });
    console.log('[Firestore] Report + PDF saved.');
  } catch (err) {
    console.warn('[Firestore] Could not save report:', err.message);
  }
}


/* ── HTML template ── */
function buildHTML() {
  return `
<style>
  .mr-field { width:100%;padding:11px 14px;background:rgba(255,255,255,.04);
    border:1px solid rgba(0,229,255,.18);border-radius:10px;color:#e2e8f0;
    font-size:13px;outline:none;transition:border .2s;box-sizing:border-box; }
  .mr-field:focus { border-color:#00e5ff;box-shadow:0 0 0 2px rgba(0,229,255,.12); }
  .mr-label { font-size:11px;color:#64748b;margin-bottom:5px;display:block;font-weight:600;letter-spacing:.5px; }
  .mr-row   { display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px; }

  .mr-zone { border:2px dashed rgba(0,229,255,.35);border-radius:16px;padding:40px 28px;
    text-align:center;cursor:pointer;transition:all .3s;background:rgba(0,229,255,.03); }
  .mr-zone:hover,.mr-zone.drag-over { border-color:#00e5ff;background:rgba(0,229,255,.07);
    transform:translateY(-2px);box-shadow:0 0 30px rgba(0,229,255,.12); }
  .mr-zone.file-ok { border-style:solid;border-color:#00e5ff;background:rgba(0,229,255,.08); }
  .mr-icon { width:60px;height:60px;margin:0 auto 12px;background:linear-gradient(135deg,rgba(0,229,255,.15),rgba(0,229,255,.04));
    border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:26px; }
  .mr-ztitle { font-family:var(--font-display,Orbitron);font-size:16px;font-weight:700;color:#e2e8f0;margin-bottom:5px; }
  .mr-zsub   { font-size:11px;color:#64748b; }

  .mr-btn { width:100%;padding:15px;margin-top:16px;font-size:14px;
    font-family:var(--font-display,Orbitron);font-weight:700;letter-spacing:1px;
    border:none;border-radius:12px;cursor:pointer;
    background:linear-gradient(135deg,#00e5ff,#0ea5e9);color:#000;
    transition:all .3s;display:flex;align-items:center;justify-content:center;gap:10px; }
  .mr-btn:hover:not(:disabled) { transform:translateY(-2px);box-shadow:0 8px 28px rgba(0,229,255,.35); }
  .mr-btn:disabled { opacity:.55;cursor:not-allowed;transform:none; }

  .mr-prog-wrap { background:rgba(255,255,255,.06);border-radius:999px;height:7px;
    overflow:hidden;margin-top:12px;display:none; }
  .mr-prog-fill { height:100%;background:linear-gradient(90deg,#00e5ff,#0ea5e9);
    border-radius:999px;width:0%;transition:width .4s; }

  .mr-status { display:none;padding:14px 18px;border-radius:12px;margin-top:14px;
    align-items:center;gap:12px; }
  .mr-status.show    { display:flex; }
  .mr-status.success { background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.3); }
  .mr-status.error   { background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3); }
  .mr-status.info    { background:rgba(0,229,255,.07);border:1px solid rgba(0,229,255,.2); }

  .mr-col-grid { display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px; }
  .mr-col-badge { background:rgba(0,229,255,.05);border:1px solid rgba(0,229,255,.14);
    border-radius:8px;padding:8px 10px;font-size:11px;font-family:monospace;color:#00e5ff; }
  .mr-col-badge span { display:block;color:#64748b;font-family:inherit;font-size:10px;margin-top:2px; }

  .mr-steps  { display:flex;flex-direction:column;gap:10px; }
  .mr-step   { display:flex;align-items:flex-start;gap:12px;padding:12px 14px;
    background:rgba(255,255,255,.03);border-radius:10px;border:1px solid rgba(255,255,255,.06); }
  .mr-step-num { width:28px;height:28px;flex-shrink:0;border-radius:50%;
    background:linear-gradient(135deg,rgba(0,229,255,.18),rgba(0,229,255,.04));
    border:1px solid rgba(0,229,255,.28);display:flex;align-items:center;justify-content:center;
    font-family:var(--font-display,Orbitron);font-size:11px;font-weight:700;color:#00e5ff; }
  .mr-step-body { font-size:11px;color:#64748b;line-height:1.5; }
  .mr-step-title { font-weight:600;color:#e2e8f0;margin-bottom:2px; }

  .mr-sample { font-family:monospace;font-size:10px;color:#64748b;background:rgba(0,0,0,.3);
    border-radius:8px;padding:10px;overflow-x:auto;white-space:nowrap;margin-top:8px;
    border:1px solid rgba(255,255,255,.05); }
  .mr-tpl-btn { background:none;border:1px solid rgba(255,255,255,.1);color:#64748b;
    padding:8px 16px;border-radius:8px;cursor:pointer;font-size:12px;
    transition:all .2s;margin-top:12px;width:100%; }
  .mr-tpl-btn:hover { border-color:rgba(0,229,255,.35);color:#00e5ff; }

  @keyframes slideIn { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
</style>

<div class="section-header reveal">
  <div>
    <h1 class="section-title">Manual Report</h1>
    <p class="section-subtitle">Enter vehicle details, upload OBD-II CSV → AI analyses → Download PDF + saved to Past Reports</p>
  </div>
</div>

<div style="display:grid;grid-template-columns:1.4fr 1fr;gap:22px;align-items:start">

  <!-- LEFT -->
  <div class="glass-card reveal" style="padding:26px">
    <div style="font-family:var(--font-display,Orbitron);font-size:15px;font-weight:700;color:#e2e8f0;margin-bottom:18px;display:flex;align-items:center;gap:8px">
      <span style="color:#00e5ff">📊</span> Upload Vehicle OBD Data
    </div>

    <!-- Vehicle Details -->
    <div style="margin-bottom:16px;padding:14px;background:rgba(0,229,255,.04);border:1px solid rgba(0,229,255,.12);border-radius:12px">
      <div style="font-size:11px;font-weight:700;color:#00e5ff;letter-spacing:.5px;margin-bottom:12px">VEHICLE DETAILS</div>
      <div class="mr-row">
        <div>
          <label class="mr-label">Vehicle Name *</label>
          <input class="mr-field" id="mr-veh-name" type="text" placeholder="e.g. Honda City" maxlength="60"/>
        </div>
        <div>
          <label class="mr-label">Model / Year (optional)</label>
          <input class="mr-field" id="mr-veh-model" type="text" placeholder="e.g. 2020 1.5L" maxlength="60"/>
        </div>
      </div>
    </div>

    <!-- Drop Zone -->
    <div class="mr-zone" id="mr-zone">
      <div class="mr-icon" id="mr-icon">📁</div>
      <div class="mr-ztitle" id="mr-title">Drop CSV here or click to browse</div>
      <div class="mr-zsub"   id="mr-sub">Supports .csv files — minimum 5 rows</div>
      <input type="file" id="mr-file-input" accept=".csv" style="display:none"/>
    </div>

    <!-- Progress -->
    <div class="mr-prog-wrap" id="mr-prog-wrap">
      <div class="mr-prog-fill" id="mr-prog-fill"></div>
    </div>

    <!-- Status -->
    <div class="mr-status" id="mr-status">
      <span id="mr-status-icon" style="font-size:20px">⏳</span>
      <div>
        <div id="mr-status-title" style="font-weight:600;color:#e2e8f0;font-size:13px"></div>
        <div id="mr-status-msg"   style="font-size:11px;color:#64748b;margin-top:2px"></div>
      </div>
    </div>

    <!-- Analyse Button -->
    <button class="mr-btn" id="mr-btn" disabled>
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
        <div class="mr-step"><div class="mr-step-num">1</div><div class="mr-step-body"><div class="mr-step-title">Enter vehicle details</div>Name and model so the report links to your vehicle</div></div>
        <div class="mr-step"><div class="mr-step-num">2</div><div class="mr-step-body"><div class="mr-step-title">Upload your CSV</div>Drag & drop or click browse — minimum 5 rows</div></div>
        <div class="mr-step"><div class="mr-step-num">3</div><div class="mr-step-body"><div class="mr-step-title">AI analyses data</div>ML scores Engine, Fuel, Efficiency, Driving & Thermal</div></div>
        <div class="mr-step"><div class="mr-step-num">4</div><div class="mr-step-body"><div class="mr-step-title">PDF downloads + saved</div>Report auto-downloads & appears instantly in Past Reports</div></div>
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

/* ── wire events ── */
function wireEvents() {
  const zone      = document.getElementById('mr-zone');
  const fileInput = document.getElementById('mr-file-input');
  const btn       = document.getElementById('mr-btn');
  const btnText   = document.getElementById('mr-btn-text');
  const progWrap  = document.getElementById('mr-prog-wrap');
  const progFill  = document.getElementById('mr-prog-fill');
  const status    = document.getElementById('mr-status');
  const stIcon    = document.getElementById('mr-status-icon');
  const stTitle   = document.getElementById('mr-status-title');
  const stMsg     = document.getElementById('mr-status-msg');
  const mrIcon    = document.getElementById('mr-icon');
  const mrTitle   = document.getElementById('mr-title');
  const mrSub     = document.getElementById('mr-sub');
  const tplBtn    = document.getElementById('mr-tpl-btn');
  const vehName   = document.getElementById('mr-veh-name');
  const vehModel  = document.getElementById('mr-veh-model');

  let selectedFile = null;

  const setStatus = (type, icon, title, msg) => {
    status.className = `mr-status ${type} show`;
    stIcon.textContent  = icon;
    stTitle.textContent = title;
    stMsg.textContent   = msg;
  };
  const clearStatus = () => { status.className = 'mr-status'; };
  const setProgress = pct => {
    progWrap.style.display = 'block';
    progFill.style.width   = pct + '%';
    if (pct >= 100) setTimeout(() => { progWrap.style.display = 'none'; }, 700);
  };

  function resetZone() {
    selectedFile = null; fileInput.value = '';
    zone.classList.remove('file-ok');
    mrIcon.textContent  = '📁';
    mrTitle.textContent = 'Drop CSV here or click to browse';
    mrSub.textContent   = 'Supports .csv files — minimum 5 rows';
    btn.disabled = true; btnText.textContent = 'Select a CSV file first';
    progFill.style.width = '0%'; clearStatus();
  }

  function onFile(file) {
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setStatus('error', '❌', 'Wrong file type', 'Please select a .csv file'); return;
    }
    selectedFile = file;
    zone.classList.add('file-ok');
    mrIcon.textContent  = '✅';
    mrTitle.textContent = file.name;
    mrSub.textContent   = `${(file.size/1024).toFixed(1)} KB — ready to analyse`;
    btn.disabled = false; btnText.textContent = '🔬 Analyse & Download Report';
    clearStatus();
  }

  zone.addEventListener('click',    () => fileInput.click());
  zone.addEventListener('dragover',  e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) onFile(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener('change', () => { if (fileInput.files[0]) onFile(fileInput.files[0]); });

  btn.addEventListener('click', async () => {
    if (!selectedFile) return;
    const vehicleName  = vehName.value.trim()  || 'My Vehicle';
    const vehicleModel = vehModel.value.trim();

    btn.disabled = true; btnText.textContent = '⏳ Analysing…';
    setProgress(20);
    setStatus('info', '⏳', 'Running ML Analysis', `Uploading CSV for "${vehicleName}"…`);

    try {
      const token = await firebaseUser.getIdToken(true);
      const form  = new FormData();
      form.append('file',          selectedFile);
      form.append('vehicle_name',  vehicleName);
      form.append('vehicle_model', vehicleModel);

      setProgress(45);

      const controller = new AbortController();
      const tid = setTimeout(() => controller.abort(), 180000); // 3 min timeout

      const res = await fetch(`${API_BASE}/predict/csv`, {
        method:  'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body:    form,
        signal:  controller.signal
      });
      clearTimeout(tid);
      setProgress(80);

      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.error || 'Analysis failed');

      setProgress(90);

      // 1. Save to Firestore — always works regardless of DB state
      await saveReportToFirestore(firebaseUser.uid, data);
      setProgress(95);

      // 2. Download PDF from base64
      downloadBase64PDF(data.pdf_base64, data.filename || `vexis_${vehicleName}_report.pdf`);
      setProgress(100);

      setStatus('success', '✅', 'Report Downloaded!',
        `PDF for "${vehicleName}" saved. Check Past Reports to view it.`);
      toast('PDF report downloaded & saved to Past Reports!', 'success');
      setTimeout(resetZone, 7000);

    } catch (err) {
      const msg = err.name === 'AbortError'
        ? 'Timed out (3 min). The backend may be cold-starting — try again in 30s.'
        : err.message || 'Something went wrong.';
      setStatus('error', '❌', 'Analysis Failed', msg);
      toast('Error: ' + msg, 'error');
      btn.disabled = false; btnText.textContent = '🔬 Analyse & Download Report';
      setProgress(0);
    }
  });

  tplBtn.addEventListener('click', () => {
    const rows = [
      'rpm,speed,load,coolant_temp,throttle_pos,intake_temp,maf,stft,ltft',
      '800,0,25,82,8,30,2.1,0.8,-0.5','1200,20,32,85,12,33,4.2,1.0,-0.8',
      '1800,45,42,87,22,35,8.5,1.2,-0.8','2100,60,55,89,28,36,11.2,0.8,-1.1',
      '2500,75,65,91,35,38,14.8,0.5,-1.5','3000,90,75,93,45,40,18.2,-0.2,-1.8',
      '1500,30,35,88,15,34,6.1,1.5,-0.3','900,5,28,84,9,31,2.8,1.1,-0.6',
      '2200,65,60,90,32,37,12.5,0.6,-1.3','1700,40,48,88,20,35,9.1,0.9,-0.9',
    ];
    const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
    const url  = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement('a'), { href: url, download: 'vexis_obd_template.csv' });
    document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(url);
    toast('Template downloaded!', 'success');
  });
}

window.loadManualReportSection = function(contentArea) {
  contentArea.innerHTML = buildHTML();
  wireEvents();
};
