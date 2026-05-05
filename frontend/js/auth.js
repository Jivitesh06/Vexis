/* ================================================================
   auth.js — Vexis Login & Signup (Firebase Auth)
   ================================================================ */

import { showToast } from './api.js';
import {
  auth,
  googleProvider,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendPasswordResetEmail,
  sendEmailVerification,
  signInWithPopup,
  updateProfile,
  waitForUser,
  syncWithBackend
} from './firebase.js';

// ── Guard: redirect if already logged in (verified only) ──────────
waitForUser().then(user => {
  if (user && user.emailVerified) window.location.href = 'dashboard.html';
});

// ── Elements ──────────────────────────────────────────────────────
const tabLogin   = document.getElementById('tab-login');
const tabSignup  = document.getElementById('tab-signup');
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

document.getElementById('go-signup')?.addEventListener('click',    showSignupTab);
document.getElementById('go-login')?.addEventListener('click',     showLoginTab);
document.getElementById('back-to-login')?.addEventListener('click', showLoginTab);

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
  const len    = pw.length;
  const hasNum = /[0-9]/.test(pw);
  const hasSpc = /[^a-zA-Z0-9]/.test(pw);
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
  el.style.animation = 'none';
  requestAnimationFrame(() => { el.style.animation = ''; });
}
function hideError(id) {
  const el = document.getElementById(id);
  el.classList.remove('visible');
  el.textContent = '';
}
function setLoading(btnId, loading) {
  const btn = document.getElementById(btnId);
  btn.classList.toggle('loading', loading);
  btn.querySelector('.btn-text').style.display    = loading ? 'none' : '';
  btn.querySelector('.btn-spinner').style.display = loading ? 'flex'  : 'none';
}
function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

// ── Map Firebase error codes to friendly messages ─────────────────
function friendlyError(code) {
  console.error('[VEXIS] Firebase error code:', code);   // ← always log real code
  const map = {
    'auth/user-not-found':            'No account found with this email.',
    'auth/wrong-password':            'Incorrect password. Please try again.',
    'auth/invalid-credential':        'Invalid email or password.',
    'auth/email-already-in-use':      'This email is already registered. Try logging in.',
    'auth/weak-password':             'Password must be at least 6 characters.',
    'auth/invalid-email':             'Please enter a valid email address.',
    'auth/too-many-requests':         'Too many attempts. Please wait and try again.',
    'auth/network-request-failed':    'Network error. Check your internet connection.',
    'auth/popup-closed-by-user':      'Google sign-in was cancelled.',
    'auth/popup-blocked':             'Popup was blocked. Please allow popups for this site.',
    'auth/operation-not-allowed':     'Email/Password sign-in is not enabled. Please contact support.',
    'auth/configuration-not-found':   'Firebase is not configured correctly. Check project settings.',
    'auth/invalid-api-key':           'Invalid Firebase API key. Check configuration.',
    'auth/app-not-authorized':        'This app is not authorized. Check Firebase settings.',
    'auth/user-disabled':             'This account has been disabled.',
    'auth/requires-recent-login':     'Please log in again to continue.',
  };
  return map[code] || `Something went wrong (${code || 'unknown'}). Try again.`;
}

// ── LOGIN (Email/Password) ────────────────────────────────────────
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
    const cred = await signInWithEmailAndPassword(auth, email, pw);

    // ── Block unverified users ──────────────────────────────────────
    if (!cred.user.emailVerified) {
      // Sign out immediately — do NOT let them access the app
      await auth.signOut();
      setLoading('login-btn', false);
      showError('login-error', '📧 Please verify your email before logging in.');

      // Inject resend banner
      const existingBanner = loginForm.querySelector('.unverified-banner');
      if (existingBanner) existingBanner.remove();
      const banner = document.createElement('div');
      banner.className = 'unverified-banner';
      banner.innerHTML = `
        <span>Check your inbox for the verification link.</span>
        <button class="resend-inline-btn" id="login-resend-btn" type="button">Resend Email</button>
      `;
      document.getElementById('login-error').after(banner);
      document.getElementById('login-resend-btn').addEventListener('click', async () => {
        try {
          // Temporarily sign in to get user object, send email, sign out again
          const tmp = await signInWithEmailAndPassword(auth, email, pw);
          await sendEmailVerification(tmp.user);
          await auth.signOut();
          showToast('Verification email resent! Check your inbox.', 'success', 4000);
        } catch {
          showToast('Could not resend. Try again later.', 'error');
        }
      });
      return;
    }

    // ── Verified — create DB entry and proceed ──────────────────────
    await syncWithBackend(cred.user);
    showToast(`Welcome back! 🚗`, 'success');
    setTimeout(() => { window.location.href = 'dashboard.html'; }, 700);

  } catch (err) {
    setLoading('login-btn', false);
    showError('login-error', friendlyError(err.code));
  }
});

// ── GOOGLE SIGN-IN ────────────────────────────────────────────────
document.getElementById('google-signin-btn')?.addEventListener('click', async () => {
  try {
    const result = await signInWithPopup(auth, googleProvider);
    await syncWithBackend(result.user);
    showToast(`Welcome, ${result.user.displayName}! 🚗`, 'success');
    setTimeout(() => { window.location.href = 'dashboard.html'; }, 700);
  } catch (err) {
    if (err.code !== 'auth/popup-closed-by-user') {
      showToast(friendlyError(err.code), 'error');
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
    // 1. Create Firebase user
    const cred = await createUserWithEmailAndPassword(auth, email, pw);

    // 2. Set display name in Firebase
    await updateProfile(cred.user, { displayName: name });

    // 3. Send verification email (DB entry created only AFTER they verify + login)
    await sendEmailVerification(cred.user);

    // 4. Sign them out — they must verify before accessing the app
    await auth.signOut();

    // 5. Show success state
    document.getElementById('signup-fields').style.display        = 'none';
    document.getElementById('signup-success-state').style.display = 'block';
    document.getElementById('success-email-display').textContent  = email;

  } catch (err) {
    setLoading('signup-btn', false);
    showError('signup-error', friendlyError(err.code));
  }
});

// ── RESEND VERIFICATION EMAIL ─────────────────────────────────────
const resendBtn = document.getElementById('resend-btn');
if (resendBtn) {
  resendBtn.addEventListener('click', async () => {
    const user = auth.currentUser;
    if (!user) {
      showToast('No account session found. Please sign up again.', 'error');
      return;
    }
    resendBtn.disabled = true;
    resendBtn.textContent = 'Sending...';
    try {
      await sendEmailVerification(user);
      showToast('Verification email sent! Check your inbox.', 'success', 4000);
    } catch (err) {
      // auth/too-many-requests means Firebase rate-limited resend
      if (err.code === 'auth/too-many-requests') {
        showToast('Please wait a few minutes before resending.', 'error');
      } else {
        showToast('Could not resend. Please try again.', 'error');
      }
    } finally {
      resendBtn.disabled = false;
      resendBtn.textContent = 'Resend Email';
    }
  });
}
document.getElementById('google-signup-btn')?.addEventListener('click', async () => {
  try {
    const result = await signInWithPopup(auth, googleProvider);
    await syncWithBackend(result.user);
    showToast(`Welcome, ${result.user.displayName}! 🚗`, 'success');
    setTimeout(() => { window.location.href = 'dashboard.html'; }, 700);
  } catch (err) {
    if (err.code !== 'auth/popup-closed-by-user') {
      showToast(friendlyError(err.code), 'error');
    }
  }
});

// ── FORGOT PASSWORD ───────────────────────────────────────────────
const forgotLink     = document.getElementById('forgot-link');
const loginFields    = document.getElementById('login-fields');
const forgotFormEl   = document.getElementById('forgot-form');
const backToLoginBtn = document.getElementById('back-to-login-btn');
const forgotBtn      = document.getElementById('forgot-btn');

function showForgotForm() {
  loginFields.style.display  = 'none';
  forgotFormEl.style.display = 'block';
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

forgotLink?.addEventListener('click', e => { e.preventDefault(); showForgotForm(); });
backToLoginBtn?.addEventListener('click', hideForgotForm);

forgotBtn?.addEventListener('click', async () => {
  hideError('forgot-error');
  const email = document.getElementById('forgot-email').value.trim();

  if (!email || !isValidEmail(email)) {
    showError('forgot-error', 'Please enter a valid email address.');
    return;
  }

  forgotBtn.querySelector('.btn-text').style.display    = 'none';
  forgotBtn.querySelector('.btn-spinner').style.display = 'flex';
  forgotBtn.disabled = true;

  try {
    await sendPasswordResetEmail(auth, email);
    document.getElementById('forgot-fields').style.display = 'none';
    const el = document.getElementById('forgot-success');
    el.textContent = '✉️ Password reset email sent! Check your inbox.';
    el.classList.add('visible');
  } catch (err) {
    showError('forgot-error', friendlyError(err.code));
  } finally {
    forgotBtn.querySelector('.btn-text').style.display    = '';
    forgotBtn.querySelector('.btn-spinner').style.display = 'none';
    forgotBtn.disabled = false;
  }
});
