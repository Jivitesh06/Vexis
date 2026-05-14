/**
 * Vexis Payment Module — Razorpay Integration
 * Handles subscription checks, pricing modal, and payment flow.
 */
import { getToken } from './api.js';

const API = 'https://vexis-backend-kklg.onrender.com/api';
const RAZORPAY_KEY = 'rzp_test_Sp78k3JIxzjZH1';

// ─── Plans config (mirrors backend) ────────────────────────────────────────
const PLANS = [
  {
    id:          'single',
    name:        'Single Report',
    price:       49,
    icon:        '📄',
    duration:    '1 Use',
    feature:     '1 AI Analysis or PDF Report',
    color:       '#34d399',
    badge:       null,
  },
  {
    id:          'explorer',
    name:        'Explorer',
    price:       99,
    icon:        '🔍',
    duration:    '7 Days',
    feature:     'Unlimited Analyses & PDF Reports',
    color:       '#60a5fa',
    badge:       null,
  },
  {
    id:          'pro',
    name:        'Pro',
    price:       199,
    icon:        '⚡',
    duration:    '30 Days',
    feature:     'Unlimited Analyses & PDF Reports',
    color:       '#a78bfa',
    badge:       null,
  },
  {
    id:          'elite',
    name:        'Elite',
    price:       499,
    icon:        '👑',
    duration:    '1 Year',
    feature:     'Unlimited Everything — Best Value',
    color:       '#f59e0b',
    badge:       'BEST VALUE',
  },
];

// ─── State ──────────────────────────────────────────────────────────────────
let _cachedStatus    = null;
let _cacheExpiry     = 0;
let _pendingCallback = null;     // Called after successful payment

// ─── Check subscription status (cached 60s) ─────────────────────────────────
export async function checkSubscription(force = false) {
  const now = Date.now();
  if (!force && _cachedStatus && now < _cacheExpiry) {
    return _cachedStatus;
  }
  try {
    const token = await getToken();
    const res   = await fetch(`${API}/payments/status`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await res.json();
    _cachedStatus = data;
    _cacheExpiry  = now + 60_000;   // Cache for 60 seconds
    return data;
  } catch (e) {
    console.error('[Payments] checkSubscription error:', e);
    return { active: false, plan: 'free' };
  }
}

// ─── Invalidate cache (call after payment) ──────────────────────────────────
export function invalidateSubCache() {
  _cachedStatus = null;
  _cacheExpiry  = 0;
}

// ─── Gate a feature: checks sub, shows modal if not active ──────────────────
/**
 * Call before any paid feature.
 * @param {Function} onAllowed - Called immediately if subscription is active,
 *                                or after successful payment.
 */
export async function requireSubscription(onAllowed) {
  const status = await checkSubscription();
  if (status.active) {
    onAllowed();
    return;
  }
  // Not subscribed — show pricing modal
  _pendingCallback = onAllowed;
  showPricingModal();
}

// ─── Build & show the pricing modal ─────────────────────────────────────────
export function showPricingModal() {
  // Remove any existing modal
  document.getElementById('vexis-payment-modal')?.remove();

  const overlay = document.createElement('div');
  overlay.id        = 'vexis-payment-modal';
  overlay.className = 'payment-overlay';
  overlay.innerHTML = `
    <div class="payment-modal" role="dialog" aria-modal="true" aria-label="Choose a plan">

      <div class="payment-modal-header">
        <button class="payment-modal-close" id="pay-modal-close" aria-label="Close">✕</button>
        <div class="payment-modal-icon">🔐</div>
        <h2 class="payment-modal-title">Unlock AI Intelligence</h2>
        <p class="payment-modal-subtitle">Choose a plan to access AI Health Analysis & PDF Reports</p>
      </div>

      <!-- Plans grid -->
      <div class="plans-grid" id="plans-grid">
        ${PLANS.map(p => `
          <div class="plan-card" data-plan="${p.id}" id="plan-card-${p.id}" tabindex="0" role="button" aria-label="Select ${p.name} plan">
            ${p.badge ? `<div class="plan-badge">${p.badge}</div>` : ''}
            <div class="plan-icon">${p.icon}</div>
            <div class="plan-name">${p.name}</div>
            <div class="plan-price">
              <span class="currency">₹</span>
              <span class="amount">${p.price}</span>
            </div>
            <div class="plan-duration">${p.duration}</div>
            <div class="plan-feature">${p.feature}</div>
            <button class="plan-cta" data-plan="${p.id}">Get ${p.name}</button>
          </div>
        `).join('')}
      </div>

      <!-- Processing state -->
      <div class="payment-processing" id="pay-processing">
        <div class="payment-spinner"></div>
        <p style="color:rgba(255,255,255,0.6); margin:0;">Processing payment securely…</p>
      </div>

      <!-- Success state -->
      <div class="payment-success" id="pay-success">
        <div class="payment-success-icon">✅</div>
        <h3>Payment Successful!</h3>
        <p>Your subscription is now active. Loading your analysis…</p>
      </div>

      <div class="payment-footer">
        <span>🔒 Secured by</span>
        <span style="font-weight:600;color:rgba(255,255,255,0.5)">Razorpay</span>
        <span>· Test Mode Active</span>
      </div>

    </div>
  `;

  document.body.appendChild(overlay);

  // Animate in
  requestAnimationFrame(() => overlay.classList.add('active'));

  // Close on overlay click or close button
  document.getElementById('pay-modal-close').addEventListener('click', closeModal);
  overlay.addEventListener('click', e => { if (e.target === overlay) closeModal(); });
  // Close on Escape
  const escHandler = e => { if (e.key === 'Escape') closeModal(); };
  document.addEventListener('keydown', escHandler);
  overlay._escHandler = escHandler;

  // Plan CTA clicks
  overlay.querySelectorAll('.plan-cta').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      initiatePayment(btn.dataset.plan);
    });
  });
  // Also allow clicking the card itself
  overlay.querySelectorAll('.plan-card').forEach(card => {
    card.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') initiatePayment(card.dataset.plan);
    });
  });
}

function closeModal() {
  const overlay = document.getElementById('vexis-payment-modal');
  if (!overlay) return;
  if (overlay._escHandler) document.removeEventListener('keydown', overlay._escHandler);
  overlay.classList.remove('active');
  setTimeout(() => overlay.remove(), 350);
  _pendingCallback = null;
}

function showProcessing() {
  document.getElementById('plans-grid').style.display      = 'none';
  document.getElementById('pay-processing').classList.add('active');
  document.getElementById('pay-success').classList.remove('active');
}

function showSuccess() {
  document.getElementById('pay-processing').classList.remove('active');
  document.getElementById('pay-success').classList.add('active');
}

// ─── Initiate Razorpay checkout ──────────────────────────────────────────────
async function initiatePayment(planId) {
  showProcessing();
  try {
    const token = await getToken();

    // 1. Create order on backend
    const orderRes = await fetch(`${API}/payments/create-order`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body:    JSON.stringify({ plan_id: planId }),
    });
    const order = await orderRes.json();

    if (!orderRes.ok || !order.order_id) {
      throw new Error(order.error || 'Failed to create order');
    }

    // 2. Hide processing, open Razorpay checkout
    document.getElementById('pay-processing').classList.remove('active');
    document.getElementById('plans-grid').style.display = 'grid';

    const options = {
      key:         order.key_id,        // ← use the SAME key the backend used to create the order
      amount:      order.amount,
      currency:    order.currency,
      name:        'Vexis AI',
      description: order.plan_name,
      image:       '',
      order_id:    order.order_id,
      prefill: {},
      theme:       { color: '#818cf8' },
      modal: {
        ondismiss: () => {
          // User closed checkout — reset modal back to plans
          document.getElementById('plans-grid').style.display = 'grid';
          document.getElementById('pay-processing').classList.remove('active');
        },
      },
      handler: async (response) => {
        await handlePaymentSuccess(response, planId);
      },
    };

    // Load Razorpay SDK lazily if not already loaded
    await loadRazorpaySdk();
    const rzp = new window.Razorpay(options);
    rzp.open();

  } catch (err) {
    console.error('[Payments] initiatePayment error:', err);
    document.getElementById('plans-grid').style.display = 'grid';
    document.getElementById('pay-processing').classList.remove('active');
    showToast(`Payment error: ${err.message}`, 'error');
  }
}

// ─── Handle successful payment ───────────────────────────────────────────────
async function handlePaymentSuccess(response, planId) {
  showProcessing();
  try {
    const token = await getToken();
    const res   = await fetch(`${API}/payments/verify`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body:    JSON.stringify({
        razorpay_payment_id: response.razorpay_payment_id,
        razorpay_order_id:   response.razorpay_order_id,
        razorpay_signature:  response.razorpay_signature,
        plan_id:             planId,
      }),
    });
    const result = await res.json();

    if (!res.ok || !result.success) {
      throw new Error(result.error || 'Verification failed');
    }

    // Invalidate cache so next check fetches fresh status
    invalidateSubCache();

    showSuccess();

    // After 1.8s — close modal and trigger the pending action
    setTimeout(() => {
      closeModal();
      if (typeof _pendingCallback === 'function') {
        const cb = _pendingCallback;
        _pendingCallback = null;
        cb();
      }
    }, 1800);

  } catch (err) {
    console.error('[Payments] handlePaymentSuccess error:', err);
    showToast(`Verification error: ${err.message}`, 'error');
    document.getElementById('pay-processing').classList.remove('active');
    document.getElementById('plans-grid').style.display = 'grid';
  }
}

// ─── Lazily load Razorpay SDK ────────────────────────────────────────────────
function loadRazorpaySdk() {
  return new Promise((resolve, reject) => {
    if (window.Razorpay) { resolve(); return; }
    const s  = document.createElement('script');
    s.src    = 'https://checkout.razorpay.com/v1/checkout.js';
    s.onload = resolve;
    s.onerror = () => reject(new Error('Failed to load Razorpay SDK'));
    document.head.appendChild(s);
  });
}

// ─── Small toast helper (uses existing toast if available) ───────────────────
function showToast(msg, type = 'info') {
  if (typeof window.showToast === 'function') {
    window.showToast(msg, type);
    return;
  }
  const t = document.createElement('div');
  t.textContent = msg;
  Object.assign(t.style, {
    position: 'fixed', bottom: '1.5rem', right: '1.5rem',
    background: type === 'error' ? '#ef4444' : '#818cf8',
    color: '#fff', padding: '0.75rem 1.25rem', borderRadius: '10px',
    fontFamily: 'Rajdhani, sans-serif', fontSize: '0.9rem',
    zIndex: '99999', boxShadow: '0 8px 30px rgba(0,0,0,0.4)',
    transition: 'opacity 0.3s', pointerEvents: 'none',
  });
  document.body.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 3000);
}
