/**
 * VexBot — AI Vehicle Chatbot with user context
 * Integrates with /api/chatbot/message (Gemini 1.5 Flash + RAG)
 */
import { getToken, API_BASE, showToast } from './api.js';
import { waitForUser } from './firebase.js';

const SUGGESTIONS = [
  '🔍 How is my engine doing?',
  '⛽ Any fuel issues?',
  '🌡️ Check my thermal score',
  '📅 When should I service?',
  '⚠️ What issues were detected?',
  '📊 Explain my health score',
];

let chatHistory   = [];   // [{role:'user'|'bot', text:'...'}]
let isTyping      = false;
let currentUser   = null;
let hasContext    = false;

// ── Init ─────────────────────────────────────────────────────────────────────
export async function initVexBot() {
  currentUser = await waitForUser();
  if (!currentUser) return;   // not logged in

  injectHTML();
  wireEvents();

  // Show welcome message after brief delay
  setTimeout(() => {
    appendBotMessage(
      '👋 Hey! I\'m **VexBot** — your personal vehicle health assistant.\n\n' +
      'I have access to your Vexis vehicle data and reports. Ask me anything about your car\'s health, OBD readings, or maintenance!\n\n' +
      '_Try one of the suggestions below_ 👇'
    );
    showBadge();
  }, 1200);
}

// ── Inject HTML widget ───────────────────────────────────────────────────────
function injectHTML() {
  const wrap = document.createElement('div');
  wrap.innerHTML = `
    <!-- Floating trigger -->
    <button id="vexbot-trigger" aria-label="Open VexBot chat" title="Ask VexBot">
      💬
      <span id="vexbot-badge"></span>
    </button>

    <!-- Chat window -->
    <div id="vexbot-window" role="dialog" aria-label="VexBot Chat">
      <div class="vexbot-header">
        <div class="vexbot-avatar">🤖</div>
        <div class="vexbot-info">
          <div class="vexbot-name">VexBot</div>
          <div class="vexbot-status">Vehicle AI Online</div>
        </div>
        <button class="vexbot-close" id="vexbot-close" title="Close chat">×</button>
      </div>

      <div class="vexbot-context-bar" id="vexbot-ctx-bar" style="display:none">
        ✅ Your vehicle data loaded — personalized answers enabled
      </div>

      <div class="vexbot-messages" id="vexbot-messages"></div>

      <div class="vexbot-suggestions" id="vexbot-suggestions">
        ${SUGGESTIONS.map(s => `<button class="vexbot-suggestion">${s}</button>`).join('')}
      </div>

      <div class="vexbot-input-area">
        <textarea
          id="vexbot-input"
          placeholder="Ask about your car... (English / Hindi / Hinglish)"
          rows="1"
          maxlength="1000"
        ></textarea>
        <button id="vexbot-send" aria-label="Send">➤</button>
      </div>
    </div>
  `;
  document.body.appendChild(wrap);
}

// ── Wire events ──────────────────────────────────────────────────────────────
function wireEvents() {
  const trigger     = document.getElementById('vexbot-trigger');
  const window_     = document.getElementById('vexbot-window');
  const input       = document.getElementById('vexbot-input');
  const sendBtn     = document.getElementById('vexbot-send');
  const closeBtn    = document.getElementById('vexbot-close');
  const suggestions = document.getElementById('vexbot-suggestions');

  // Toggle open/close
  trigger.addEventListener('click', () => {
    const isOpen = window_.classList.toggle('open');
    trigger.classList.toggle('open', isOpen);
    hideBadge();
    if (isOpen) {
      input.focus();
      scrollToBottom();
    }
  });

  // Send on button click
  sendBtn.addEventListener('click', sendMessage);

  // Send on Enter (Shift+Enter = newline)
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // Auto-resize textarea
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 100) + 'px';
  });

  // Close chat
  closeBtn.addEventListener('click', () => {
    window_.classList.remove('open');
    trigger.classList.remove('open');
  });

  // Quick suggestions
  suggestions.addEventListener('click', e => {
    const btn = e.target.closest('.vexbot-suggestion');
    if (!btn) return;
    input.value = btn.textContent.replace(/^[^\w\u0900-\u097F]+/, '').trim();
    // Remove emoji prefix from text before sending
    const cleanText = btn.textContent.replace(/^[\u{1F300}-\u{1FFFF}\u{2600}-\u{26FF}⚠️✅📅📊⛽🌡️🔍]\s*/u, '').trim();
    input.value = cleanText;
    sendMessage();
  });

  // Close when clicking outside
  document.addEventListener('click', e => {
    if (!window_.contains(e.target) && e.target !== trigger && !trigger.contains(e.target)) {
      window_.classList.remove('open');
      trigger.classList.remove('open');
    }
  });
}

// ── Send message ─────────────────────────────────────────────────────────────
async function sendMessage() {
  const input   = document.getElementById('vexbot-input');
  const sendBtn = document.getElementById('vexbot-send');
  const text    = input.value.trim();

  if (!text || isTyping) return;

  input.value = '';
  input.style.height = 'auto';
  hideSuggestions();

  // Append user message
  appendUserMessage(text);
  chatHistory.push({ role: 'user', text });

  // Show typing
  isTyping = true;
  sendBtn.disabled = true;
  const typingEl = appendTypingIndicator();

  try {
    const token = await getToken();
    const res   = await fetch(`${API_BASE}/chatbot/message`, {
      method:  'POST',
      headers: {
        'Content-Type':  'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        message: text,
        history: chatHistory.slice(-8),  // last 8 for context
      }),
    });

    const data = await res.json();
    typingEl.remove();

    const reply = data.reply || 'Sorry, something went wrong. Please try again.';
    appendBotMessage(reply);
    chatHistory.push({ role: 'bot', text: reply });

    // Show context bar once we get a response (meaning context loaded)
    if (!hasContext) {
      hasContext = true;
      const ctxBar = document.getElementById('vexbot-ctx-bar');
      if (ctxBar) ctxBar.style.display = 'flex';
    }

    // Show badge if chat is closed
    const win = document.getElementById('vexbot-window');
    if (!win.classList.contains('open')) showBadge();

  } catch (err) {
    typingEl.remove();
    appendBotMessage('🔧 I\'m having trouble connecting right now. Please try again in a moment.');
    console.error('[VexBot]', err);
  } finally {
    isTyping = false;
    sendBtn.disabled = false;
    document.getElementById('vexbot-input').focus();
  }
}

// ── DOM helpers ──────────────────────────────────────────────────────────────
function appendUserMessage(text) {
  const msgs = document.getElementById('vexbot-messages');
  const el   = document.createElement('div');
  el.className = 'vexbot-msg user';
  el.innerHTML = `
    <div class="vexbot-msg-avatar">👤</div>
    <div class="vexbot-bubble">${escapeHtml(text)}</div>
  `;
  msgs.appendChild(el);
  scrollToBottom();
}

function appendBotMessage(text) {
  const msgs = document.getElementById('vexbot-messages');
  if (!msgs) return;
  const el   = document.createElement('div');
  el.className = 'vexbot-msg bot';
  // Convert simple markdown: **bold**, *italic*, newlines
  const formatted = markdownToHtml(text);
  el.innerHTML = `
    <div class="vexbot-msg-avatar">🤖</div>
    <div class="vexbot-bubble">${formatted}</div>
  `;
  msgs.appendChild(el);
  scrollToBottom();
}

function appendTypingIndicator() {
  const msgs = document.getElementById('vexbot-messages');
  const el   = document.createElement('div');
  el.className = 'vexbot-msg bot';
  el.innerHTML = `
    <div class="vexbot-msg-avatar">🤖</div>
    <div class="vexbot-bubble">
      <div class="vexbot-typing">
        <span></span><span></span><span></span>
      </div>
    </div>
  `;
  msgs.appendChild(el);
  scrollToBottom();
  return el;
}

function scrollToBottom() {
  const msgs = document.getElementById('vexbot-messages');
  if (msgs) msgs.scrollTop = msgs.scrollHeight;
}

function hideSuggestions() {
  const s = document.getElementById('vexbot-suggestions');
  if (s && chatHistory.length > 0) s.style.display = 'none';
}

function showBadge() {
  const b = document.getElementById('vexbot-badge');
  if (b) b.classList.add('visible');
}
function hideBadge() {
  const b = document.getElementById('vexbot-badge');
  if (b) b.classList.remove('visible');
}

// ── Utilities ────────────────────────────────────────────────────────────────
function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function markdownToHtml(text) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    // Bold **text**
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Italic *text*
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Inline code
    .replace(/`(.+?)`/g, '<code style="background:rgba(255,255,255,0.1);padding:1px 5px;border-radius:4px;font-size:0.8em">$1</code>')
    // Bullet lists
    .replace(/^[-•]\s+(.+)/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/gs, '<ul style="margin:4px 0 4px 16px;padding:0">$1</ul>')
    // Newlines
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>');
}
