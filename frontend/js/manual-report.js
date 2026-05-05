/* ================================================================
   manual-report.js — CSV Upload → ML → PDF Download
   ================================================================ */

import { auth }    from './firebase.js';
import { waitForUser } from './firebase.js';
import { API_BASE, showToast } from './api.js';

// ── Auth guard ────────────────────────────────────────────────────
const firebaseUser = await waitForUser();
if (!firebaseUser) { window.location.href = 'login.html'; throw new Error(); }

// ── Elements ──────────────────────────────────────────────────────
const zone        = document.getElementById('upload-zone');
const fileInput   = document.getElementById('csv-file-input');
const analyzeBtn  = document.getElementById('analyze-btn');
const btnText     = document.getElementById('analyze-btn-text');
const progressWrap= document.getElementById('progress-wrap');
const progressFill= document.getElementById('progress-fill');
const statusCard  = document.getElementById('status-card');
const statusIcon  = document.getElementById('status-icon');
const statusTitle = document.getElementById('status-title');
const statusMsg   = document.getElementById('status-msg');
const uploadIcon  = document.getElementById('upload-icon');
const uploadTitle = document.getElementById('upload-title');
const uploadSub   = document.getElementById('upload-sub');
const templateBtn = document.getElementById('download-template-btn');

let selectedFile = null;

// ── Drag & Drop ───────────────────────────────────────────────────
zone.addEventListener('click', () => fileInput.click());

zone.addEventListener('dragover', e => {
  e.preventDefault();
  zone.classList.add('drag-over');
});
zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
zone.addEventListener('drop', e => {
  e.preventDefault();
  zone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleFileSelect(file);
});

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) handleFileSelect(fileInput.files[0]);
});

function handleFileSelect(file) {
  if (!file.name.endsWith('.csv')) {
    showStatus('error', '❌', 'Invalid file type', 'Please upload a .csv file only');
    return;
  }
  selectedFile = file;

  // Update zone UI
  zone.classList.add('file-selected');
  uploadIcon.textContent = '✅';
  uploadTitle.textContent = file.name;
  uploadSub.textContent   = `${(file.size / 1024).toFixed(1)} KB • Ready to analyse`;

  // Enable button
  analyzeBtn.disabled = false;
  btnText.textContent  = '🔬 Analyse & Download Report';

  hideStatus();
}

// ── Analyse button ────────────────────────────────────────────────
analyzeBtn.addEventListener('click', async () => {
  if (!selectedFile) return;

  analyzeBtn.disabled = true;
  btnText.textContent = '⏳ Analysing...';
  showProgress(30);
  showStatus('info', '⏳', 'Running ML Analysis', 'Sending data to Vexis AI engine...');

  try {
    const token = await firebaseUser.getIdToken(true);

    const formData = new FormData();
    formData.append('file', selectedFile);

    showProgress(60);

    const res = await fetch(`${API_BASE}/predict/csv`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });

    showProgress(90);

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || 'Analysis failed');
    }

    // Trigger PDF download
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `vexis_report_${new Date().toISOString().slice(0,10)}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showProgress(100);
    showStatus('success', '✅', 'Report Downloaded!', 'Your PDF health report has been saved to your device.');
    showToast('PDF report downloaded successfully!', 'success');

    // Reset after 4s
    setTimeout(resetZone, 4000);

  } catch (err) {
    showStatus('error', '❌', 'Analysis Failed', err.message || 'Something went wrong. Please try again.');
    showToast('Analysis failed: ' + err.message, 'error');
    analyzeBtn.disabled = false;
    btnText.textContent = '🔬 Analyse & Download Report';
    showProgress(0);
  }
});

// ── Sample template download ──────────────────────────────────────
templateBtn.addEventListener('click', () => {
  const header = 'rpm,speed,load,coolant_temp,throttle_pos,intake_temp,maf,stft,ltft';
  const rows   = [
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
  const csv  = [header, ...rows].join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = 'vexis_obd_template.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast('Template downloaded!', 'success');
});

// ── Helpers ───────────────────────────────────────────────────────
function showStatus(type, icon, title, msg) {
  statusCard.className = `status-card ${type} show`;
  statusIcon.textContent  = icon;
  statusTitle.textContent = title;
  statusMsg.textContent   = msg;
}
function hideStatus() {
  statusCard.className = 'status-card';
}
function showProgress(pct) {
  progressWrap.style.display = 'block';
  progressFill.style.width   = pct + '%';
  if (pct >= 100) {
    setTimeout(() => { progressWrap.style.display = 'none'; }, 600);
  }
}
function resetZone() {
  selectedFile = null;
  fileInput.value = '';
  zone.classList.remove('file-selected');
  uploadIcon.textContent  = '📁';
  uploadTitle.textContent = 'Drop CSV here or click to browse';
  uploadSub.textContent   = 'Supports .csv files with OBD-II sensor columns';
  analyzeBtn.disabled     = true;
  btnText.textContent     = 'Select a CSV file first';
  hideStatus();
  progressFill.style.width = '0%';
}
