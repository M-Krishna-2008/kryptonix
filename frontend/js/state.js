/**
 * Application State & Offline Storage Management (IndexedDB + localStorage)
 */

const DB_NAME = 'ForensicsPlatformDB';
const DB_VERSION = 1;
const STORE_NAME = 'analyses_history';

export class StateManager {
  constructor() {
    this.db = null;
    this.selectedModuleId = 'ai_aud';
    this.selectedFile = null;
    this.modulesConfig = [];
    this.theme = localStorage.getItem('theme') || 'light';
    this.listeners = new Set();
  }

  async init() {
    this.applyTheme(this.theme);
    await this._initDB();
  }

  applyTheme(theme) {
    this.theme = theme;
    localStorage.setItem('theme', theme);
    document.documentElement.setAttribute('data-theme', theme);
    this.notify();
  }

  toggleTheme() {
    const next = this.theme === 'light' ? 'dark' : 'light';
    this.applyTheme(next);
  }

  setSelectedModule(moduleId) {
    this.selectedModuleId = moduleId;
    this.notify();
  }

  setSelectedFile(file) {
    this.selectedFile = file;
    this.notify();
  }

  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  notify() {
    for (const listener of this.listeners) {
      listener(this);
    }
  }

  // -------------------------------------------------------------------------
  // IndexedDB Persistence for Recent Forensic Analyses History
  // -------------------------------------------------------------------------
  _initDB() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = (e) => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' });
          store.createIndex('timestamp', 'timestamp', { unique: false });
        }
      };
      request.onsuccess = (e) => {
        this.db = e.target.result;
        resolve();
      };
      request.onerror = (e) => {
        console.warn('IndexedDB failed, falling back to in-memory history:', e);
        resolve();
      };
    });
  }

  async saveAnalysis(entry) {
    if (!this.db) return;
    return new Promise((resolve) => {
      try {
        const tx = this.db.transaction(STORE_NAME, 'readwrite');
        const store = tx.objectStore(STORE_NAME);
        store.put(entry);
        tx.oncomplete = () => resolve();
        tx.onerror = () => resolve();
      } catch (e) {
        resolve();
      }
    });
  }

  async getRecentAnalyses(limit = 20) {
    if (!this.db) return [];
    return new Promise((resolve) => {
      try {
        const tx = this.db.transaction(STORE_NAME, 'readonly');
        const store = tx.objectStore(STORE_NAME);
        const index = store.index('timestamp');
        const req = index.openCursor(null, 'prev');
        const results = [];
        req.onsuccess = (e) => {
          const cursor = e.target.result;
          if (cursor && results.length < limit) {
            results.push(cursor.value);
            cursor.continue();
          } else {
            resolve(results);
          }
        };
        req.onerror = () => resolve([]);
      } catch (e) {
        resolve([]);
      }
    });
  }

  async clearHistory() {
    if (!this.db) return;
    return new Promise((resolve) => {
      try {
        const tx = this.db.transaction(STORE_NAME, 'readwrite');
        const store = tx.objectStore(STORE_NAME);
        store.clear();
        tx.oncomplete = () => resolve();
      } catch (e) {
        resolve();
      }
    });
  }
}
