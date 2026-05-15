/* ================================================================
   sidebar.js — Dashboard Shell Logic
   Manages auth, navigation, clock, user info, OBD status
   ================================================================ */

import {
  logout, getUser,
  showToast, initSocketIO,
  updateOBDStatusBanner, getOBDStatus,
  initRevealAnimations, getUserNotifications
} from './api.js';
import { waitForUser, syncWithBackend, auth, db, doc, onSnapshot } from './firebase.js';

// ── Auth guard ───────────────────────────────────────────────────
const firebaseUser = await waitForUser();
if (!firebaseUser) {
  window.location.href = 'login.html';
  throw new Error('Not authenticated');
}
// Block users who haven't verified their email
if (!firebaseUser.emailVerified) {
  const { signOut } = await import('./firebase.js');
  await signOut(auth).catch(() => {});
  window.location.href = 'login.html';
  throw new Error('Email not verified');
}
// Verified — sync with backend DB in the background (no await — never blocks render)
syncWithBackend(firebaseUser).catch(() => {});

// ── DOM refs ───────────────────────────────────────────────────────
const contentArea   = document.getElementById('content-area');
const obdBanner     = document.getElementById('obd-banner');
const obdDot        = document.getElementById('obd-dot');
const obdLabel      = document.getElementById('obd-label');
const navItems      = document.querySelectorAll('.nav-item[data-section]');
const mobileItems   = document.querySelectorAll('.mobile-nav-item[data-section]');

// ── Apply user data to header ─────────────────────────────────────
function applyUserToHeader(data) {
  const displayName = data?.name || firebaseUser.displayName || 'User';
  const photoUrl    = data?.profile_photo_url || firebaseUser.photoURL || '';
  const email       = data?.email || firebaseUser.email || '';

  const nameEl   = document.getElementById('user-name');
  const avatarEl = document.getElementById('user-avatar');
  const emailEl  = document.getElementById('user-email');
  const photoEl  = document.getElementById('user-photo');

  if (nameEl)  nameEl.textContent  = displayName;
  if (emailEl) emailEl.textContent = email;

  if (photoEl && photoUrl) {
    photoEl.src           = photoUrl;
    photoEl.style.display = '';
    photoEl.style.width   = '36px';
    photoEl.style.height  = '36px';
    photoEl.style.borderRadius = '50%';
    photoEl.style.objectFit = 'cover';
    if (avatarEl) avatarEl.style.display = 'none';
  } else if (avatarEl) {
    if (photoEl) photoEl.style.display = 'none';
    avatarEl.style.display = '';
    const words    = displayName.trim().split(' ');
    const initials = words.length >= 2
      ? words[0][0] + words[words.length-1][0]
      : words[0].slice(0, 2);
    avatarEl.textContent = initials.toUpperCase();
  }
}

// ── Populate user info (initial load from cache) ──────────────────
window.populateUser = function() {
  const cachedUser = getUser();
  applyUserToHeader({
    name:              cachedUser?.name || firebaseUser.displayName,
    email:             cachedUser?.email || firebaseUser.email,
    profile_photo_url: cachedUser?.profile_photo_url || firebaseUser.photoURL
  });
};
window.populateUser();

// ── Real-time Firestore listener for profile updates ──────────────
if (firebaseUser?.uid) {
  onSnapshot(doc(db, 'users', firebaseUser.uid), (snap) => {
    if (snap.exists()) {
      applyUserToHeader(snap.data());
    }
  });
}


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

// section name → filename mapping (add overrides here)
const SECTION_FILE = {
  'dashboard':   'dashboard.html',
  'manual':      'manual-report.html',
};
function sectionToUrl(section) {
  return SECTION_FILE[section] || `${section}.html`;
}

navItems.forEach(item => {
  item.addEventListener('click', () => {
    window.location.href = sectionToUrl(item.dataset.section);
  });
});
mobileItems.forEach(item => {
  item.addEventListener('click', () => {
    window.location.href = sectionToUrl(item.dataset.section);
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
    case 'manual':
      if (typeof window.loadManualReportSection === 'function') {
        await window.loadManualReportSection(contentArea);
      } else {
        loadPlaceholder('manual', 'Manual Report', 'Upload OBD data for manual analysis.', `<svg viewBox="0 0 24 24" fill="none" width="36" height="36"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><polyline points="17 8 12 3 7 8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><line x1="12" y1="3" x2="12" y2="15" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>`);
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

// ── Routing / Default load ─────────────────────────────────────────
function handleRoute() {
  const path = window.location.pathname;
  let section = 'dashboard';
  if (path.includes('vehicles.html'))           section = 'vehicles';
  else if (path.includes('reports.html'))       section = 'reports';
  else if (path.includes('profile.html'))       section = 'profile';
  else if (path.includes('settings.html'))      section = 'settings';
  else if (path.includes('manual-report.html')) section = 'manual';

  setActiveSection(section);
  loadSection(section);
}

handleRoute();

// ── Notifications Logic ────────────────────────────────────────────
const notifBtn = document.getElementById('notif-btn');
const notifDropdown = document.getElementById('notif-dropdown');
const notifBadge = document.getElementById('notif-badge');
const notifList = document.getElementById('notif-list');

if (notifBtn && notifDropdown) {
  // Toggle dropdown
  notifBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    notifDropdown.classList.toggle('open');
  });

  // Close when clicking outside
  document.addEventListener('click', (e) => {
    if (!notifDropdown.contains(e.target) && !notifBtn.contains(e.target)) {
      notifDropdown.classList.remove('open');
    }
  });

  // Fetch and render notifications
  async function loadNotifications() {
    try {
      const res = await getUserNotifications();
      if (!res.success) return;

      const notifs = res.notifications || [];
      if (notifs.length === 0) {
        notifBadge.style.display = 'none';
        notifList.innerHTML = `<div class="notif-empty">No new notifications</div>`;
        return;
      }

      // Show badge
      notifBadge.style.display = 'flex';
      notifBadge.textContent = notifs.length > 9 ? '9+' : notifs.length;

      // Render list
      let html = '';
      notifs.forEach(n => {
        let iconSvg = '';
        if (n.type === 'critical') iconSvg = '⚠️';
        else if (n.type === 'warning') iconSvg = '⚡';
        else iconSvg = '💡';

        // Format relative time (e.g., "2h ago")
        const date = new Date(n.timestamp);
        let timeStr = date.toLocaleDateString();
        const diffMs = Date.now() - date.getTime();
        if (diffMs < 86400000 && diffMs > 0) {
          const hrs = Math.floor(diffMs / 3600000);
          timeStr = hrs > 0 ? `${hrs}h ago` : 'Just now';
        }

        html += `
          <div class="notif-item">
            <div class="notif-icon ${n.type}">${iconSvg}</div>
            <div class="notif-content">
              <div class="notif-title">
                <span>${n.title}</span>
                <span class="notif-time">${timeStr}</span>
              </div>
              <p class="notif-message">${n.message}</p>
              <span class="notif-vehicle">${n.vehicle_name}</span>
            </div>
          </div>
        `;
      });
      notifList.innerHTML = html;
    } catch (err) {
      console.error("Failed to load notifications:", err);
      notifList.innerHTML = `<div class="notif-empty">Failed to load notifications</div>`;
    }
  }

  // Load after a small delay to let page render
  setTimeout(loadNotifications, 1000);
}


// ── Expose for cross-module use ────────────────────────────────────
window.loadSection   = loadSection;
window.skeletonHTML  = skeletonHTML;
