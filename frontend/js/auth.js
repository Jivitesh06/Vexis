/* ================================================================
   auth.js — Vexis Login & Signup Logic
   ================================================================ */

import {
  apiPost, setAuth, getToken, showToast, clearAuth
} from './api.js';

// ── State ─────────────────────────────────────────────────────────
let lastSignupEmail = '';

// ── Guard: redirect if already logged in ──────────────────────────
if (getToken()) {
  window.location.href = 'dashboard.html';
}

// ── Verified redirect toast ────────────────────────────────────────
const params = new URLSearchParams(window.location.search);
if (params.get('verified') === 'true') {
  // short delay so page renders first
  setTimeout(() => {
    showToast('✅ Email verified! You can now login.', 'success', 4000);
  }, 300);
  // Clean URL
  history.replaceState({}, '', window.location.pathname);
}

// ── Elements ──────────────────────────────────────────────────────
const tabLogin  = document.getElementById('tab-login');
const tabSignup = document.getElementById('tab-signup');
const loginForm  = document.getElementById('login-form');
const signupForm = document.getElementById('signup-form');

// ── Tab switching ─────────────────────────────────────────────────
function showLoginTab() {
  tabLogin.classList.add('active');
  tabSignup.classList.remove('active');
  signupForm.style.display = 'none';
  loginForm.style.display  = 'block';
  loginForm.style.animation = 'formIn 0.3s ease';
}

function showSignupTab() {
  tabSignup.classList.add('active');
  tabLogin.classList.remove('active');
  loginForm.style.display  = 'none';
  signupForm.style.display = 'block';
  signupForm.style.animation = 'formIn 0.3s ease';
}

tabLogin.addEventListener('click',  showLoginTab);
tabSignup.addEventListener('click', showSignupTab);

document.getElementById('go-signup').addEventListener('click', showSignupTab);
document.getElementById('go-login').addEventListener('click',  showLoginTab);
document.getElementById('back-to-login').addEventListener('click', showLoginTab);

// ── Password show/hide ────────────────────────────────────────────
document.querySelectorAll('.eye-toggle').forEach(btn => {
  btn.addEventListener('click', () => {
    const target = document.getElementById(btn.dataset.target);
    if (!target) return;
    const isPassword = target.type === 'password';
    target.type = isPassword ? 'text' : 'password';
    btn.querySelector('.eye-show').style.display = isPassword ? 'none' : '';
    btn.querySelector('.eye-hide').style.display = isPassword ? '' : 'none';
  });
});

// ── Password strength ─────────────────────────────────────────────
const strengthFill = document.getElementById('strength-fill');
const strengthText = document.getElementById('strength-text');

function evalStrength(pw) {
  const len     = pw.length;
  const hasNum  = /[0-9]/.test(pw);
  const hasSpc  = /[^a-zA-Z0-9]/.test(pw);
  if (len === 0) return null;
  if (len < 6)                       return { level: 'Weak',   pct: 25,  color: '#ff1744' };
  if (len < 8)                       return { level: 'Fair',   pct: 50,  color: '#ff6d00' };
  if (len >= 8 && hasNum && hasSpc)  return { level: 'Strong', pct: 100, color: '#00e676' };
  if (len >= 8)                      return { level: 'Good',   pct: 75,  color: '#ffea00' };
  return null;
}

document.getElementById('signup-password').addEventListener('input', e => {
  const s = evalStrength(e.target.value);
  if (!s) {
    strengthFill.style.width = '0%';
    strengthText.textContent  = '';
    return;
  }
  strengthFill.style.width      = s.pct + '%';
  strengthFill.style.background = s.color;
  strengthText.textContent       = s.level;
  strengthText.style.color       = s.color;
  // also recheck confirm match
  checkMatch();
});

// ── Confirm password match ────────────────────────────────────────
const matchIndicator = document.getElementById('match-indicator');

function checkMatch() {
  const pw  = document.getElementById('signup-password').value;
  const cfw = document.getElementById('signup-confirm').value;
  if (!cfw) { matchIndicator.textContent = ''; return; }
  if (pw === cfw) {
    matchIndicator.textContent = '✓';
    matchIndicator.style.color = 'var(--success)';
  } else {
    matchIndicator.textContent = '✗';
    matchIndicator.style.color = 'var(--danger)';
  }
}
document.getElementById('signup-confirm').addEventListener('input', checkMatch);

// ── Helpers ───────────────────────────────────────────────────────
function showError(id, msg) {
  const el = document.getElementById(id);
  el.textContent = msg;
  el.classList.add('visible');
  // force re-animation
  el.style.animation = 'none';
  requestAnimationFrame(() => { el.style.animation = ''; });
}
function hideError(id) {
  const el = document.getElementById(id);
  el.classList.remove('visible');
  el.textContent = '';
}
function showSuccess(id, msg) {
  const el = document.getElementById(id);
  el.textContent = msg;
  el.classList.add('visible');
}
function setLoading(btnId, loading) {
  const btn = document.getElementById(btnId);
  btn.classList.toggle('loading', loading);
  btn.querySelector('.btn-text').style.display   = loading ? 'none' : '';
  btn.querySelector('.btn-spinner').style.display = loading ? 'flex' : 'none';
}
function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

// ── LOGIN ─────────────────────────────────────────────────────────
document.getElementById('login-btn').addEventListener('click', async () => {
  hideError('login-error');

  const email = document.getElementById('login-email').value.trim();
  const pw    = document.getElementById('login-password').value;

  if (!email || !pw) {
    showError('login-error', 'Please enter your email and password.');
    return;
  }
  if (!isValidEmail(email)) {
    showError('login-error', 'Please enter a valid email address.');
    return;
  }

  setLoading('login-btn', true);

  try {
    const data = await apiPost('/auth/login', { email, password: pw }, true);
    setAuth(data.token, data.user);
    showToast(`Welcome back, ${data.user.name}! 🚗`, 'success');
    setTimeout(() => { window.location.href = 'dashboard.html'; }, 800);

  } catch (err) {
    setLoading('login-btn', false);

    if (err.status === 403) {
      // Unverified account — show resend option
      showError('login-error', 'Your email is not verified yet.');
      // Inject resend banner if not already there
      const existingBanner = loginForm.querySelector('.unverified-banner');
      if (existingBanner) existingBanner.remove();
      const banner = document.createElement('div');
      banner.className = 'unverified-banner';
      banner.innerHTML = `
        <span>Check your inbox for the verification link.</span>
        <button class="resend-inline-btn" id="login-resend-btn" type="button">Resend Email</button>
      `;
      document.getElementById('login-error').after(banner);
      document.getElementById('login-resend-btn').addEventListener('click', () => {
        resendVerification(email);
      });
    } else {
      showError('login-error', err.message || 'Login failed. Please try again.');
    }
  }
});

// ── SIGNUP ────────────────────────────────────────────────────────
document.getElementById('signup-btn').addEventListener('click', async () => {
  hideError('signup-error');

  const name  = document.getElementById('signup-name').value.trim();
  const email = document.getElementById('signup-email').value.trim();
  const pw    = document.getElementById('signup-password').value;
  const cfw   = document.getElementById('signup-confirm').value;

  // Validate
  if (!name) {
    showError('signup-error', 'Please enter your full name.');
    document.getElementById('signup-name').focus();
    return;
  }
  if (!email || !isValidEmail(email)) {
    showError('signup-error', 'Please enter a valid email address.');
    document.getElementById('signup-email').focus();
    return;
  }
  if (pw.length < 8) {
    showError('signup-error', 'Password must be at least 8 characters.');
    document.getElementById('signup-password').focus();
    return;
  }
  if (pw !== cfw) {
    showError('signup-error', 'Passwords do not match.');
    document.getElementById('signup-confirm').focus();
    return;
  }

  setLoading('signup-btn', true);

  try {
    await apiPost('/auth/signup', {
      name,
      email,
      password:         pw,
      confirm_password: cfw
    }, true);

    // Show success state
    lastSignupEmail = email;
    document.getElementById('signup-fields').style.display = 'none';
    document.getElementById('signup-success-state').style.display = 'block';
    document.getElementById('success-email-display').textContent = email;

  } catch (err) {
    setLoading('signup-btn', false);
    showError('signup-error', err.message || 'Signup failed. Please try again.');
  }
});

// ── RESEND VERIFICATION ────────────────────────────────────────────
async function resendVerification(email) {
  try {
    await apiPost('/auth/resend-verification', { email }, true);
    showToast('Verification email resent! Check your inbox.', 'success', 4000);
  } catch {
    showToast('Could not resend email. Please try again.', 'error');
  }
}

const resendBtn = document.getElementById('resend-btn');
if (resendBtn) {
  resendBtn.addEventListener('click', () => {
    if (lastSignupEmail) resendVerification(lastSignupEmail);
  });
}

// ── FORGOT PASSWORD ───────────────────────────────────────────────
const forgotLink      = document.getElementById('forgot-link');
const loginFields     = document.getElementById('login-fields');
const forgotFormEl    = document.getElementById('forgot-form');
const backToLoginBtn  = document.getElementById('back-to-login-btn');
const forgotBtn       = document.getElementById('forgot-btn');

function showForgotForm() {
  loginFields.style.display  = 'none';
  forgotFormEl.style.display = 'block';
  // Clear previous state
  hideError('forgot-error');
  document.getElementById('forgot-success').classList.remove('visible');
  document.getElementById('forgot-success').textContent = '';
  document.getElementById('forgot-email').value = '';
  document.getElementById('forgot-fields').style.display = '';
}

function hideForgotForm() {
  loginFields.style.display  = '';
  forgotFormEl.style.display = 'none';
  hideError('login-error');
}

forgotLink?.addEventListener('click', e => {
  e.preventDefault();
  showForgotForm();
});

backToLoginBtn?.addEventListener('click', hideForgotForm);

forgotBtn?.addEventListener('click', async () => {
  hideError('forgot-error');
  const email = document.getElementById('forgot-email').value.trim();

  if (!email || !isValidEmail(email)) {
    showError('forgot-error', 'Please enter a valid email address.');
    return;
  }

  // Loading state
  forgotBtn.querySelector('.btn-text').style.display    = 'none';
  forgotBtn.querySelector('.btn-spinner').style.display = 'flex';
  forgotBtn.disabled = true;

  try {
    await apiPost('/auth/forgot-password', { email }, true);

    // Hide fields, show success
    document.getElementById('forgot-fields').style.display = 'none';
    showSuccess('forgot-success', '✉️ Check your email for reset instructions. The link expires in 1 hour.');

  } catch (err) {
    showError('forgot-error', err.message || 'Failed to send reset email. Try again.');
  } finally {
    forgotBtn.querySelector('.btn-text').style.display    = '';
    forgotBtn.querySelector('.btn-spinner').style.display = 'none';
    forgotBtn.disabled = false;
  }
});
