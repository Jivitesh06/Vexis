/* ================================================================
   VEXIS — API Communication Layer
   All functions are named exports for use across pages.
   ================================================================ */

const IS_LOCAL =
  window.location.hostname === 'localhost' ||
  window.location.hostname === '127.0.0.1';

const API_BASE = IS_LOCAL
  ? 'http://localhost:5000/api'
  : 'https://your-app.onrender.com/api';

const SOCKET_URL = IS_LOCAL
  ? 'http://localhost:5000'
  : 'https://your-app.onrender.com';

export { API_BASE, SOCKET_URL };

// ── 1. getToken ────────────────────────────────────────────────────
export function getToken() {
  return localStorage.getItem('vexis_token');
}

// ── 2. getUser ─────────────────────────────────────────────────────
export function getUser() {
  const u = localStorage.getItem('vexis_user');
  return u ? JSON.parse(u) : null;
}

// ── 3. setAuth ─────────────────────────────────────────────────────
export function setAuth(token, user) {
  localStorage.setItem('vexis_token', token);
  localStorage.setItem('vexis_user', JSON.stringify(user));
}

// ── 4. clearAuth ───────────────────────────────────────────────────
export function clearAuth() {
  localStorage.removeItem('vexis_token');
  localStorage.removeItem('vexis_user');
}

// ── 5. authHeaders ─────────────────────────────────────────────────
export function authHeaders() {
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${getToken()}`
  };
}

// ── 6. apiGet ──────────────────────────────────────────────────────
export async function apiGet(endpoint) {
  const res  = await fetch(API_BASE + endpoint, {
    method:  'GET',
    headers: authHeaders()
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}

// ── 7. apiPost ─────────────────────────────────────────────────────
export async function apiPost(endpoint, body, skipAuth = false) {
  const headers = skipAuth
    ? { 'Content-Type': 'application/json' }
    : authHeaders();
  const res  = await fetch(API_BASE + endpoint, {
    method:  'POST',
    headers,
    body:    JSON.stringify(body)
  });
  const data = await res.json();
  // For 403 we return the data object alongside the error so callers can inspect it
  if (!res.ok) {
    const err = new Error(data.error || 'Request failed');
    err.status = res.status;
    err.data   = data;
    throw err;
  }
  return data;
}

// ── 8. checkAuth ───────────────────────────────────────────────────
export async function checkAuth() {
  const token = getToken();
  if (!token) {
    window.location.href = 'login.html';
    return false;
  }
  try {
    await apiGet('/auth/me');
    return true;
  } catch {
    clearAuth();
    window.location.href = 'login.html';
    return false;
  }
}

// ── 9. logout ──────────────────────────────────────────────────────
export function logout() {
  clearAuth();
  showToast('Logged out successfully', 'success');
  setTimeout(() => { window.location.href = 'login.html'; }, 800);
}

// ── 10. showToast ──────────────────────────────────────────────────
export function showToast(message, type = 'info', duration = 3000) {
  // Create or reuse container
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  // Icon per type
  const icons = { success: '✓', error: '✗', info: 'ℹ' };
  const icon  = icons[type] || icons.info;

  // Build toast element
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span style="font-size:16px;font-weight:700">${icon}</span><span>${message}</span>`;
  container.appendChild(toast);

  // Dismiss after duration
  setTimeout(() => {
    toast.style.animation = 'toastOut 0.3s ease forwards';
    setTimeout(() => toast.remove(), 350);
  }, duration);

  // Hard-remove safety net
  setTimeout(() => { if (toast.parentNode) toast.remove(); }, duration + 400);
}

// ── 11. formatScore ────────────────────────────────────────────────
export function formatScore(score) {
  return `${parseFloat(score).toFixed(1)}/100`;
}

// ── 12. getBadgeClass ──────────────────────────────────────────────
export function getBadgeClass(category) {
  const map = {
    'Excellent': 'badge-excellent',
    'Good':      'badge-good',
    'Fair':      'badge-fair',
    'Poor':      'badge-poor',
    'Critical':  'badge-critical'
  };
  return map[category] || 'badge-good';
}

// ── 13. animateNumber ──────────────────────────────────────────────
export function animateNumber(element, start, end, duration = 1500) {
  // easeOutQuart easing
  const easeOutQuart = t => 1 - Math.pow(1 - t, 4);

  let startTime = null;

  function step(timestamp) {
    if (!startTime) startTime = timestamp;
    const elapsed  = timestamp - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased    = easeOutQuart(progress);
    const current  = start + (end - start) * eased;

    element.textContent = current.toFixed(1);

    if (progress < 1) {
      requestAnimationFrame(step);
    } else {
      element.textContent = end.toFixed(1);
    }
  }

  requestAnimationFrame(step);
}

// ── 14. initRevealAnimations ───────────────────────────────────────
export function initRevealAnimations() {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target); // animate once
        }
      });
    },
    { threshold: 0.1 }
  );

  document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
}

// ── 15. initSocketIO ───────────────────────────────────────────────
export function initSocketIO() {
  return new Promise((resolve) => {
    // Load Socket.IO client from CDN if not already present
    if (window.io) {
      _connectSocket(resolve);
      return;
    }
    const script = document.createElement('script');
    script.src = 'https://cdn.socket.io/4.7.2/socket.io.min.js';
    script.onload = () => _connectSocket(resolve);
    document.head.appendChild(script);
  });
}

function _connectSocket(resolve) {
  const socket = window.io(SOCKET_URL);
  window.vexisSocket = socket;

  socket.on('obd_status', (data) => {
    updateOBDStatusBanner(data);
  });

  socket.on('obd_data', (data) => {
    if (data.success && typeof window.onOBDData === 'function') {
      window.onOBDData(data.data);
    }
  });

  resolve(socket);
}

// ── 16. updateOBDStatusBanner ──────────────────────────────────────
export function updateOBDStatusBanner(status) {
  const banner = document.getElementById('obd-banner');
  if (!banner) return;

  if (status.connected) {
    banner.classList.add('connected');
    banner.classList.remove('disconnected');
    const port      = status.port || 'AUTO';
    const simBadge  = status.simulated
      ? '<span style="opacity:.7;font-size:11px"> (Simulated)</span>'
      : '';
    banner.innerHTML = `
      <span style="color:#00e676;font-size:18px">●</span>
      <span>OBD Scanner Connected${simBadge} &mdash; Port: <b>${port}</b></span>
      <span style="margin-left:12px;color:#00e676;font-size:12px">● Live Data Active</span>
      <button onclick="this.parentElement.style.display='none'"
              style="margin-left:auto;background:none;border:none;color:inherit;cursor:pointer;font-size:16px">✕</button>
    `;
  } else {
    banner.classList.add('disconnected');
    banner.classList.remove('connected');
    banner.innerHTML = `
      <span style="color:#ff1744;font-size:18px">●</span>
      <span>${status.message || 'No OBD Scanner Detected'}</span>
    `;
  }
}

// ── 17. connectOBD ─────────────────────────────────────────────────
export async function connectOBD(port = null) {
  return await apiPost('/obd/connect', { port });
}

// ── 18. disconnectOBD ──────────────────────────────────────────────
export async function disconnectOBD() {
  return await apiPost('/obd/disconnect', {});
}

// ── 19. getOBDStatus ───────────────────────────────────────────────
export async function getOBDStatus() {
  return await apiGet('/obd/status');
}
