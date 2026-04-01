/* ================================================================
   sidebar.js — Dashboard Shell Logic
   Manages auth, navigation, clock, user info, OBD status
   ================================================================ */

import {
  checkAuth, logout, getUser,
  showToast, initSocketIO,
  updateOBDStatusBanner, getOBDStatus,
  initRevealAnimations
} from './api.js';

// ── Auth guard ─────────────────────────────────────────────────────
const authed = await checkAuth().catch(() => false);
if (!authed) {
  window.location.href = 'login.html';
  throw new Error('Not authenticated');
}

// ── DOM refs ───────────────────────────────────────────────────────
const contentArea   = document.getElementById('content-area');
const obdBanner     = document.getElementById('obd-banner');
const obdDot        = document.getElementById('obd-dot');
const obdLabel      = document.getElementById('obd-label');
const navItems      = document.querySelectorAll('.nav-item[data-section]');
const mobileItems   = document.querySelectorAll('.mobile-nav-item[data-section]');

// ── Populate user info ─────────────────────────────────────────────
(function populateUser() {
  const user = getUser();
  if (!user) return;

  const nameEl   = document.getElementById('user-name');
  const avatarEl = document.getElementById('user-avatar');

  if (nameEl)   nameEl.textContent   = user.name || user.email || 'User';
  if (avatarEl) {
    const words    = (user.name || user.email || 'VX').split(' ');
    const initials = words.length >= 2
      ? words[0][0] + words[1][0]
      : words[0].slice(0, 2);
    avatarEl.textContent = initials.toUpperCase();
  }
})();

// ── Live clock ─────────────────────────────────────────────────────
(function startClock() {
  const clockEl = document.getElementById('live-clock');
  if (!clockEl) return;

  const DAYS   = ['SUN','MON','TUE','WED','THU','FRI','SAT'];
  const MONTHS = ['JAN','FEB','MAR','APR','MAY','JUN',
                  'JUL','AUG','SEP','OCT','NOV','DEC'];

  function tick() {
    const now = new Date();
    const day = DAYS[now.getDay()];
    const d   = String(now.getDate()).padStart(2, '0');
    const mon = MONTHS[now.getMonth()];
    const yr  = now.getFullYear();
    const hh  = String(now.getHours()).padStart(2, '0');
    const mm  = String(now.getMinutes()).padStart(2, '0');
    const ss  = String(now.getSeconds()).padStart(2, '0');
    clockEl.textContent = `${day}, ${d} ${mon} ${yr}  ${hh}:${mm}:${ss}`;
  }

  tick();
  setInterval(tick, 1000);
})();

// ── Sidebar + mobile nav click ─────────────────────────────────────
function setActiveSection(name) {
  navItems.forEach(el => el.classList.toggle('active', el.dataset.section === name));
  mobileItems.forEach(el => el.classList.toggle('active', el.dataset.section === name));
}

navItems.forEach(item => {
  item.addEventListener('click', () => {
    const section = item.dataset.section;
    setActiveSection(section);
    loadSection(section);
  });
});
mobileItems.forEach(item => {
  item.addEventListener('click', () => {
    const section = item.dataset.section;
    setActiveSection(section);
    loadSection(section);
  });
});

// ── Logout ─────────────────────────────────────────────────────────
document.getElementById('logout-btn')?.addEventListener('click', () => logout());

// ── OBD Banner dismiss ─────────────────────────────────────────────
document.getElementById('banner-dismiss')?.addEventListener('click', () => {
  obdBanner?.classList.add('hidden');
});

// ── OBD header chip updater ──────────────────────────────────────
function updateHeaderOBD(status) {
  if (!obdDot || !obdLabel) return;
  if (status?.connected) {
    obdDot.className   = 'obd-dot connected';
    obdLabel.textContent = status.simulated ? 'OBD Simulated' : 'OBD Connected';
  } else {
    obdDot.className   = 'obd-dot disconnected';
    obdLabel.textContent = 'OBD Disconnected';
  }
}

// ── Socket.IO ──────────────────────────────────────────────────────
try {
  await initSocketIO();
  // api.js emits obd_status → updateOBDStatusBanner (banner),
  // but we also need to update the header chip.
  if (window.vexisSocket) {
    window.vexisSocket.on('obd_status', (status) => {
      updateOBDStatusBanner(status); // banner
      updateHeaderOBD(status);       // header chip
    });
    window.vexisSocket.on('obd_data', (data) => {
      if (data.success && typeof window.onOBDData === 'function') {
        window.onOBDData(data.data);
      }
    });
  }
} catch { /* Socket.IO optional — page still works */ }

// ── Check OBD on load ──────────────────────────────────────────────
try {
  const status = await getOBDStatus();
  updateOBDStatusBanner(status);
  updateHeaderOBD(status);
} catch { /* ignore — not connected */ }

// ── Section loader ─────────────────────────────────────────────────
export function skeletonHTML() {
  return `
    <div class="content-skeleton">
      <div class="skeleton skel-header"></div>
      <div class="skel-row">
        <div class="skeleton skel-card"></div>
        <div class="skeleton skel-card"></div>
        <div class="skeleton skel-card"></div>
      </div>
      <div class="skeleton skel-wide"></div>
    </div>`;
}

export async function loadSection(name) {
  contentArea.innerHTML = skeletonHTML();

  // Small artificial delay so skeleton is visible on fast loads
  await new Promise(r => setTimeout(r, 200));

  switch (name) {
    case 'dashboard':
      await loadDashboardContent();
      break;
    case 'vehicles':
      if (typeof window.loadVehiclesSection === 'function') {
        await window.loadVehiclesSection(contentArea);
      } else {
        loadPlaceholder('vehicles', 'My Vehicles', 'Manage your registered vehicles.', `<svg viewBox="0 0 24 24" fill="none" width="36" height="36"><path d="M5 17H3a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h14l4 4v4a2 2 0 0 1-2 2h-2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><circle cx="7.5" cy="17.5" r="2.5" stroke="currentColor" stroke-width="1.6"/><circle cx="17.5" cy="17.5" r="2.5" stroke="currentColor" stroke-width="1.6"/></svg>`);
      }
      break;
    case 'reports':
      if (typeof window.loadReportsSection === 'function') {
        await window.loadReportsSection(contentArea);
      } else {
        loadPlaceholder('reports', 'Past Reports', 'View historical scan reports.', `<svg viewBox="0 0 24 24" fill="none" width="36" height="36"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z" stroke="currentColor" stroke-width="1.6"/><path d="M14 2v6h6M16 13H8M16 17H8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>`);
      }
      break;
    case 'profile':
      if (typeof window.loadProfileSection === 'function') {
        await window.loadProfileSection(contentArea);
      } else {
        loadPlaceholder('profile', 'My Profile', 'Update your account details.', `<svg viewBox="0 0 24 24" fill="none" width="36" height="36"><circle cx="12" cy="8" r="4" stroke="currentColor" stroke-width="1.6"/><path d="M4 20c0-4 3.582-7 8-7s8 3 8 7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>`);
      }
      break;
    case 'settings':
      if (typeof window.loadSettingsSection === 'function') {
        window.loadSettingsSection(contentArea);
      } else {
        loadPlaceholder('settings', 'Settings', 'Configure OBD scanner and preferences.', `<svg viewBox="0 0 24 24" fill="none" width="36" height="36"><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.6"/></svg>`);
      }
      break;
    default:
      await loadDashboardContent();
  }

  initRevealAnimations();
}

function loadPlaceholder(section, title, sub, iconSVG) {
  contentArea.innerHTML = `
    <div class="placeholder-section reveal">
      <div class="placeholder-icon">${iconSVG}</div>
      <h2 class="placeholder-title">${title}</h2>
      <p class="placeholder-sub">${sub}</p>
      <p style="font-size:12px;color:var(--muted);margin-top:8px">
        This section will be implemented in the next sprint.
      </p>
    </div>`;
}

// Delegate to dashboard.js (loaded as separate module)
async function loadDashboardContent() {
  if (typeof window.renderDashboard === 'function') {
    await window.renderDashboard(contentArea);
  } else {
    // If dashboard.js not yet ready, show a minimal stub
    contentArea.innerHTML = `
      <div class="section-header">
        <div>
          <h1 class="section-title">Dashboard</h1>
          <p class="section-subtitle">Your vehicle health at a glance</p>
        </div>
      </div>
      <div class="placeholder-section">
        <div class="placeholder-icon">
          <svg viewBox="0 0 24 24" fill="none" width="36" height="36">
            <rect x="3" y="3" width="7" height="7" rx="1" stroke="currentColor" stroke-width="1.6"/>
            <rect x="14" y="3" width="7" height="7" rx="1" stroke="currentColor" stroke-width="1.6"/>
            <rect x="3" y="14" width="7" height="7" rx="1" stroke="currentColor" stroke-width="1.6"/>
            <rect x="14" y="14" width="7" height="7" rx="1" stroke="currentColor" stroke-width="1.6"/>
          </svg>
        </div>
        <p class="placeholder-title">Dashboard Loading...</p>
        <p class="placeholder-sub">Connect your OBD scanner to get started.</p>
      </div>`;
  }
}

// ── Default load ───────────────────────────────────────────────────
loadSection('dashboard');

// ── Expose for cross-module use ────────────────────────────────────
window.loadSection   = loadSection;
window.skeletonHTML  = skeletonHTML;
