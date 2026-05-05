/* ================================================================
   firebase.js — Firebase App & Auth Initialization
   Shared across all pages via ES module import.
   ================================================================ */

import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js';
import {
  getAuth,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut,
  onAuthStateChanged,
  sendPasswordResetEmail,
  sendEmailVerification,
  GoogleAuthProvider,
  signInWithPopup,
  updateProfile,
  updatePassword,
  EmailAuthProvider,
  reauthenticateWithCredential
} from 'https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js';
import { 
  getFirestore, 
  collection, 
  addDoc, 
  getDocs, 
  getDoc,
  setDoc,
  updateDoc,
  onSnapshot,
  query, 
  where,
  deleteDoc,
  doc,
  orderBy,
  serverTimestamp
} from 'https://www.gstatic.com/firebasejs/10.12.0/firebase-firestore.js';

// ── Firebase Project Config ────────────────────────────────────────
const firebaseConfig = {
  apiKey:            "AIzaSyBIsm5h4YOxLb4HBhavmWj1U8WLt3D-tG4",
  authDomain:        "vexis-527f2.firebaseapp.com",
  projectId:         "vexis-527f2",
  storageBucket:     "vexis-527f2.firebasestorage.app",
  messagingSenderId: "999347430615",
  appId:             "1:999347430615:web:82fa5dabd5e10bfa25fc92"
};

// ── Initialize ─────────────────────────────────────────────────────
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const googleProvider = new GoogleAuthProvider();
const db = getFirestore(app);

// ── Exports ────────────────────────────────────────────────────────
export {
  auth,
  googleProvider,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut,
  onAuthStateChanged,
  sendPasswordResetEmail,
  sendEmailVerification,
  signInWithPopup,
  updateProfile,
  updatePassword,
  EmailAuthProvider,
  reauthenticateWithCredential,
  db,
  collection, addDoc, getDocs, getDoc, setDoc, updateDoc, onSnapshot, query, where, deleteDoc, doc, orderBy, serverTimestamp
};

/**
 * getFirebaseToken()
 * Returns the current user's fresh Firebase ID token,
 * or null if not logged in.
 */
export async function getFirebaseToken() {
  const user = auth.currentUser;
  if (!user) return null;
  try {
    return await user.getIdToken(/* forceRefresh = */ false);
  } catch {
    return null;
  }
}

/**
 * waitForUser()
 * Returns a promise that resolves with the current Firebase user
 * (or null) after Firebase finishes its auth state check.
 * Prevents race conditions on page load.
 */
export function waitForUser() {
  return new Promise((resolve) => {
    const unsub = onAuthStateChanged(auth, (user) => {
      unsub();
      resolve(user);
    });
  });
}

/**
 * syncWithBackend(user)
 * Sends the Firebase ID token to /api/auth/verify-token
 * so the backend can upsert the user in PostgreSQL.
 */
export async function syncWithBackend(user) {
  try {
    const token = await user.getIdToken();
    const IS_LOCAL =
      window.location.hostname === 'localhost' ||
      window.location.hostname === '127.0.0.1';
    const API_BASE = IS_LOCAL
      ? 'http://localhost:5000/api'
      : 'https://vexis-backend-kklg.onrender.com/api';

    const res = await fetch(`${API_BASE}/auth/verify-token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token })
    });
    const data = await res.json();
    if (data.success) {
      // Cache user info locally for display (non-sensitive)
      localStorage.setItem('vexis_user', JSON.stringify({
        uid: data.user.uid,
        name: data.user.name || user.displayName || 'User',
        email: data.user.email || user.email
      }));
    }
    return data;
  } catch (e) {
    console.warn('[VEXIS] Backend sync failed:', e);
    return null;
  }
}
