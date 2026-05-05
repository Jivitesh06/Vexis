/* ================================================================
   obd_serial.js — Vexis OBD Web Serial API Integration
   Two-stream architecture: live stream + analysis buffer
   ================================================================ */

// ── Constants ─────────────────────────────────────────────────────
const OBD_BAUD_RATE = 38400;

const PID_COMMANDS = {
  rpm:          '010C',
  speed:        '010D',
  load:         '0104',
  coolant_temp: '0105',
  throttle_pos: '0111',
  intake_temp:  '010F',
  maf:          '0110',
  stft:         '0106',
  ltft:         '0107'
};

// ── Module state ──────────────────────────────────────────────────
let port              = null;
let reader            = null;
let writer            = null;
let isConnected       = false;
let readBuffer        = '';
let liveInterval      = null;
let isCollecting      = false;
let collectionBuffer  = [];
let collectionTimer   = null;
let onLiveCallback    = null;

// ── Helper ────────────────────────────────────────────────────────
function delay(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// Automatically reload page on physical hardware disconnect
if ('serial' in navigator) {
  navigator.serial.addEventListener('disconnect', () => {
    if (isConnected) {
      window.location.reload();
    }
  });
}

// ── FUNCTION 1 — isWebSerialSupported ─────────────────────────────
export function isWebSerialSupported() {
  return 'serial' in navigator;
}

// ── FUNCTION 2 — connectOBDSerial ─────────────────────────────────
export async function connectOBDSerial() {
  try {
    // Show browser port picker
    port = await navigator.serial.requestPort();

    // Open the port
    await port.open({
      baudRate: OBD_BAUD_RATE,
      dataBits: 8,
      stopBits: 1,
      parity: 'none'
    });

    // Setup writer (text encoder stream)
    const textEncoder = new TextEncoderStream();
    textEncoder.readable.pipeTo(port.writable);
    writer = textEncoder.writable.getWriter();

    // Setup reader (text decoder stream)
    const textDecoder = new TextDecoderStream();
    port.readable.pipeTo(textDecoder.writable);
    reader = textDecoder.readable.getReader();

    isConnected = true;

    // Start background read loop (non-blocking)
    startReadLoop();

    // Initialize ELM327 adapter
    await initELM327();

    return { success: true, message: 'OBD Scanner Connected!' };

  } catch (error) {
    isConnected = false;
    if (error.name === 'NotFoundError') {
      return { success: false, message: 'No port selected' };
    }
    return { success: false, message: error.message };
  }
}

// ── FUNCTION 3 — startReadLoop ────────────────────────────────────
async function startReadLoop() {
  while (isConnected) {
    try {
      const { value, done } = await reader.read();
      if (done) break;
      readBuffer += value;
    } catch (e) {
      break;
    }
  }
}

// ── FUNCTION 4 — sendCommand ──────────────────────────────────────
async function sendCommand(cmd, waitMs = 300) {
  readBuffer = '';
  await writer.write(cmd + '\r');
  await delay(waitMs);
  const response = readBuffer.trim();
  readBuffer = '';
  return response;
}

// ── FUNCTION 5 — initELM327 ──────────────────────────────────────
async function initELM327() {
  await sendCommand('ATZ',   1500);  // Reset — wait longer
  await sendCommand('ATE0',  300);   // Echo OFF
  await sendCommand('ATL0',  300);   // Linefeeds OFF
  await sendCommand('ATS0',  300);   // Spaces OFF
  await sendCommand('ATH0',  300);   // Headers OFF
  await sendCommand('ATSP0', 300);   // Auto protocol
  await sendCommand('0100',  500);   // Test PIDs available
  console.log('[OBD] ELM327 Ready');
}

// ── FUNCTION 6 — parseOBDResponse ────────────────────────────────
function parseOBDResponse(response) {
  if (!response ||
      response.includes('NO DATA') ||
      response.includes('ERROR') ||
      response.includes('?')) {
    return null;
  }

  // Clean response: remove spaces and prompt char
  let cleaned = response
    .replace(/\s/g, '')
    .replace(/>/g, '')
    .toUpperCase();

  // Remove echo (mode+pid prefix 4 chars after '41')
  if (cleaned.startsWith('41')) {
    cleaned = cleaned.substring(4);
  }

  // Split into byte pairs and parse as integers
  const bytes = [];
  for (let i = 0; i < cleaned.length; i += 2) {
    const hex = cleaned.substring(i, i + 2);
    if (hex.length === 2) {
      bytes.push(parseInt(hex, 16));
    }
  }

  return bytes.length > 0 ? bytes : null;
}

// ── FUNCTION 7 — readOBDData ──────────────────────────────────────
export async function readOBDData() {
  const data = {};

  // RPM — formula: ((A*256)+B)/4
  try {
    const resp  = await sendCommand('010C');
    const bytes = parseOBDResponse(resp);
    if (bytes && bytes.length >= 2) {
      data.rpm = ((bytes[0] * 256) + bytes[1]) / 4;
    }
  } catch { data.rpm = null; }

  // Speed km/h — formula: A
  try {
    const resp  = await sendCommand('010D');
    const bytes = parseOBDResponse(resp);
    if (bytes) data.speed = bytes[0];
  } catch { data.speed = null; }

  // Engine Load % — formula: A*100/255
  try {
    const resp  = await sendCommand('0104');
    const bytes = parseOBDResponse(resp);
    if (bytes) data.load = (bytes[0] * 100) / 255;
  } catch { data.load = null; }

  // Coolant Temp °C — formula: A-40
  try {
    const resp  = await sendCommand('0105');
    const bytes = parseOBDResponse(resp);
    if (bytes) data.coolant_temp = bytes[0] - 40;
  } catch { data.coolant_temp = null; }

  // Throttle Position % — formula: A*100/255
  try {
    const resp  = await sendCommand('0111');
    const bytes = parseOBDResponse(resp);
    if (bytes) data.throttle_pos = (bytes[0] * 100) / 255;
  } catch { data.throttle_pos = null; }

  // Intake Air Temp °C — formula: A-40
  try {
    const resp  = await sendCommand('010F');
    const bytes = parseOBDResponse(resp);
    if (bytes) data.intake_temp = bytes[0] - 40;
  } catch { data.intake_temp = null; }

  // MAF g/s — formula: ((A*256)+B)/100
  try {
    const resp  = await sendCommand('0110');
    const bytes = parseOBDResponse(resp);
    if (bytes && bytes.length >= 2) {
      data.maf = ((bytes[0] * 256) + bytes[1]) / 100;
    }
  } catch { data.maf = null; }

  // Short Fuel Trim % — formula: (A-128)*100/128
  try {
    const resp  = await sendCommand('0106');
    const bytes = parseOBDResponse(resp);
    if (bytes) data.stft = (bytes[0] - 128) * 100 / 128;
  } catch { data.stft = null; }

  // Long Fuel Trim % — formula: (A-128)*100/128
  try {
    const resp  = await sendCommand('0107');
    const bytes = parseOBDResponse(resp);
    if (bytes) data.ltft = (bytes[0] - 128) * 100 / 128;
  } catch { data.ltft = null; }

  // Round all numeric values to 2 decimal places
  Object.keys(data).forEach(k => {
    if (data[k] !== null && data[k] !== undefined) {
      data[k] = Math.round(data[k] * 100) / 100;
    }
  });

  return data;
}

// ── FUNCTION 8 — computeDerivedFeatures ──────────────────────────
export function computeDerivedFeatures(raw) {
  const rpm        = raw.rpm        || 0;
  const speed      = raw.speed      || 0;
  const load       = raw.load       || 0;
  const maf        = raw.maf        || 0;
  const stft       = raw.stft       || 0;
  const ltft       = raw.ltft       || 0;
  const oat        = raw.coolant_temp || 70;
  const speedLimit = 60;

  return {
    ...raw,
    oat,
    speed_limit: speedLimit,

    // Engine features
    maf_per_rpm:    rpm   > 0 ? Math.round(maf / rpm * 10000) / 10000 : 0,
    rpm_load_ratio: load  > 0 ? Math.round(rpm / load * 100) / 100    : 0,

    // Efficiency features
    maf_per_speed:      speed > 0 ? Math.round(maf / speed * 10000) / 10000 : 0,
    load_per_speed:     speed > 0 ? Math.round(load / speed * 100) / 100    : 0,
    maf_speed_deviation:speed > 0 ? Math.abs(maf / speed - maf / (rpm || 1)) : 0,

    // Fuel features
    fuel_trim_combined: Math.round((stft + ltft) * 100) / 100,
    fuel_trim_abs:      Math.round((Math.abs(stft) + Math.abs(ltft)) * 100) / 100,

    // Driving features
    speed_excess:     Math.max(0, speed - speedLimit),
    is_overspeeding:  speed > speedLimit ? 1 : 0,

    // Thermal features
    thermal_stress:      Math.round(oat * (load / 100) * 100) / 100,
    maf_temp_adjusted:   Math.round(maf * (1 + oat / 100) * 100) / 100,
    gradient_speed_stress: Math.round((rpm / 1000) * (speed / 100) * 100) / 100
  };
}

// ── FUNCTION 9 — detectConditions ────────────────────────────────
export function detectConditions(buffer) {
  if (buffer.length === 0) return [];

  const speeds = buffer.map(r => r.speed || 0);
  const loads  = buffer.map(r => r.load  || 0);
  const rpms   = buffer.map(r => r.rpm   || 0);

  const avg = arr => arr.reduce((a, b) => a + b, 0) / arr.length;
  const max = arr => Math.max(...arr);

  const avgSpeed = avg(speeds);
  const avgLoad  = avg(loads);
  const maxLoad  = max(loads);
  const avgRPM   = avg(rpms);

  const conditions = [];

  if (avgSpeed < 5)                        conditions.push('idle');
  if (avgSpeed >= 5  && avgSpeed < 40)     conditions.push('city');
  if (avgSpeed >= 40 && avgSpeed < 80)     conditions.push('mixed');
  if (avgSpeed >= 80)                      conditions.push('highway');
  if (maxLoad  > 70)                       conditions.push('acceleration');
  if (avgLoad  < 25)                       conditions.push('light_load');
  if (avgRPM   > 3000)                     conditions.push('high_rpm');

  return [...new Set(conditions)];
}

// ── FUNCTION 10 — startLiveStream ────────────────────────────────
export function startLiveStream(callback) {
  onLiveCallback = callback;

  liveInterval = setInterval(async () => {
    if (!isConnected) return;

    try {
      const raw  = await readOBDData();
      const full = computeDerivedFeatures(raw);

      // Always update live display
      if (onLiveCallback) onLiveCallback(raw);

      // If analysis is running → push to buffer
      if (isCollecting) {
        collectionBuffer.push(full);
      }

    } catch (e) {
      console.warn('[OBD] Read error:', e);
    }

  }, 2000);
}

// ── FUNCTION 11 — startAnalysis ──────────────────────────────────
export function startAnalysis(durationSeconds, onProgress, onComplete) {
  if (!isConnected) {
    onComplete(null, 'Connect OBD scanner first');
    return;
  }
  if (isCollecting) {
    onComplete(null, 'Analysis already in progress');
    return;
  }

  collectionBuffer = [];
  isCollecting     = true;
  let elapsed      = 0;

  collectionTimer = setInterval(() => {
    elapsed++;

    const pct        = Math.min((elapsed / durationSeconds) * 100, 100);
    const conditions = detectConditions(collectionBuffer);

    onProgress({
      elapsed,
      total:      durationSeconds,
      percentage: pct,
      rows:       collectionBuffer.length,
      conditions
    });

    if (elapsed >= durationSeconds) {
      clearInterval(collectionTimer);
      isCollecting = false;
      const data   = [...collectionBuffer];
      collectionBuffer = [];
      onComplete(data, null);
    }

  }, 1000);
}

// ── FUNCTION 12 — cancelAnalysis ─────────────────────────────────
export function cancelAnalysis() {
  clearInterval(collectionTimer);
  isCollecting     = false;
  collectionBuffer = [];
}

// ── FUNCTION 13 — disconnectOBD ──────────────────────────────────
export async function disconnectOBD() {
  cancelAnalysis();
  clearInterval(liveInterval);
  isConnected = false;

  try {
    if (reader) await reader.cancel();
    if (writer) await writer.close();
    if (port)   await port.close();
  } catch (e) {
    console.warn('[OBD] Disconnect error:', e);
  }

  port   = null;
  reader = null;
  writer = null;
}

// ── FUNCTION 14 — getStatus ──────────────────────────────────────
export function getStatus() {
  return {
    connected:  isConnected,
    supported:  isWebSerialSupported(),
    collecting: isCollecting,
    bufferSize: collectionBuffer.length
  };
}
