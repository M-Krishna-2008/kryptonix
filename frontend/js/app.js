/**
 * Main Application Controller
 * Coordinates API client, state, UI rendering, drag-and-drop, and health monitoring.
 */

import { ApiClient } from './api.js';
import { StateManager } from './state.js';
import { UIRenderer } from './ui.js';

class AppController {
  constructor() {
    this.api = new ApiClient();
    this.state = new StateManager();
    this.ui = null;
    this.healthInterval = null;
  }

  async init() {
    await this.state.init();

    // DOM Elements
    this.threadContainer = document.getElementById('threadContainer');
    this.emptyState = document.getElementById('emptyState');
    this.composerCard = document.getElementById('composerCard');
    this.fileInput = document.getElementById('fileInput');
    this.btnAttach = document.getElementById('btnAttach');
    this.btnSend = document.getElementById('btnSend');
    this.selectedFilePill = document.getElementById('selectedFilePill');
    this.selectedFileName = document.getElementById('selectedFileName');
    this.btnRemoveFile = document.getElementById('btnRemoveFile');
    this.moduleChipsRow = document.getElementById('moduleChipsRow');
    this.btnToggleSidebar = document.getElementById('btnToggleSidebar');
    this.sidebar = document.getElementById('sidebar');
    this.btnNewAnalysis = document.getElementById('btnNewAnalysis');
    this.btnThemeToggle = document.getElementById('btnThemeToggle');
    this.historyList = document.getElementById('historyList');

    this.ui = new UIRenderer(this.threadContainer, this.api);

    // Bind Event Listeners
    this.bindEvents();

    // Fetch config & initial health check
    await this.loadConfig();
    await this.refreshHealth();
    await this.loadHistory();

    // Health check poll every 8s
    this.healthInterval = setInterval(() => this.refreshHealth(), 8000);
  }

  async loadConfig() {
    try {
      const config = await this.api.getConfig();
      this.state.modulesConfig = config.modules || [];
      this.renderModuleChips();
      this.renderSidebarModules();
    } catch (e) {
      console.error('Failed to load configuration:', e);
    }
  }

  async refreshHealth() {
    try {
      const health = await this.api.getHealth();
      const mods = health.modules || {};
      for (const [modId, info] of Object.entries(mods)) {
        const dot = document.querySelector(`.status-dot[data-module="${modId}"]`);
        if (dot) {
          dot.className = `status-dot ${info.status}`;
          dot.title = `${info.display_name || modId}: ${info.status.toUpperCase()} (${info.latency_ms ? info.latency_ms + 'ms' : info.error || ''})`;
        }
      }
    } catch (e) {
      document.querySelectorAll('.status-dot').forEach(dot => {
        dot.className = 'status-dot down';
        dot.title = 'Gateway offline or unreachable';
      });
    }
  }

  async loadHistory() {
    if (!this.historyList) return;
    const history = await this.state.getRecentAnalyses(15);
    if (history.length === 0) {
      this.historyList.innerHTML = `<li style="padding: 10px 12px; font-size: 0.8rem; color: var(--text-muted);">No prior analyses yet.</li>`;
      return;
    }

    this.historyList.innerHTML = history.map(item => {
      const badgeText = item.moduleId === 'image_forgery' ? 'Photoshop Forgery' : (item.moduleId === 'ai_aud' ? 'Audio' : item.moduleId === 'ai_cctv' ? 'CCTV' : item.moduleId === 'ai_img' ? 'AI Image' : item.moduleId.replace('ai_', ''));
      return `
        <li class="history-item" data-id="${item.id}" title="${item.filename}">
          <span class="history-item-title">${item.filename}</span>
          <span class="history-item-badge">${badgeText}</span>
        </li>
      `;
    }).join('');

    this.historyList.querySelectorAll('.history-item').forEach(li => {
      li.addEventListener('click', () => {
        const item = history.find(h => h.id === li.dataset.id);
        if (item) {
          this.displayPastAnalysis(item);
        }
      });
    });
  }

  displayPastAnalysis(item) {
    if (this.emptyState) this.emptyState.style.display = 'none';
    this.ui.clearThread();

    const mockFile = { name: item.filename, size: item.fileSize, type: item.fileType || '' };
    this.ui.renderUserBubble(mockFile, null, item.moduleId);
    const card = this.ui.renderLoadingCard(item.moduleId);
    this.ui.renderForensicResult(card, item.result, mockFile, item.moduleId, null);
  }

  renderModuleChips() {
    if (!this.moduleChipsRow) return;
    this.moduleChipsRow.innerHTML = this.state.modulesConfig.map(m => {
      const label = m.id === 'image_forgery' ? 'Photoshop Forgery' : (m.short_name || m.display_name);
      return `
        <button class="module-chip ${m.id === this.state.selectedModuleId ? 'selected' : ''}" data-id="${m.id}">
          <svg width="14" height="14"><use href="#icon-${m.id === 'ai_aud' ? 'audio' : m.id === 'ai_cctv' ? 'cctv' : m.id === 'image_forgery' ? 'forgery' : 'image'}"></use></svg>
          <span>${label}</span>
        </button>
      `;
    }).join('');

    this.moduleChipsRow.querySelectorAll('.module-chip').forEach(btn => {
      btn.addEventListener('click', () => {
        this.selectModule(btn.dataset.id);
      });
    });
  }

  renderSidebarModules() {
    const list = document.getElementById('sidebarModuleList');
    if (!list) return;

    list.innerHTML = this.state.modulesConfig.map(m => {
      const label = m.id === 'image_forgery' ? 'Photoshop Forgery' : (m.short_name || m.display_name);
      return `
        <li class="module-item ${m.id === this.state.selectedModuleId ? 'active' : ''}" data-id="${m.id}">
          <div class="module-item-left">
            <svg class="module-icon"><use href="#icon-${m.id === 'ai_aud' ? 'audio' : m.id === 'ai_cctv' ? 'cctv' : m.id === 'image_forgery' ? 'forgery' : 'image'}"></use></svg>
            <span>${label}</span>
          </div>
          <span class="status-dot" data-module="${m.id}" title="Checking status..."></span>
        </li>
      `;
    }).join('');

    list.querySelectorAll('.module-item').forEach(item => {
      item.addEventListener('click', () => {
        this.selectModule(item.dataset.id);
      });
    });
  }

  selectModule(moduleId) {
    this.state.setSelectedModule(moduleId);
    document.querySelectorAll('.module-chip').forEach(c => {
      c.classList.toggle('selected', c.dataset.id === moduleId);
    });
    document.querySelectorAll('.module-item').forEach(m => {
      m.classList.toggle('active', m.dataset.id === moduleId);
    });

    // Update accepted extensions on file input
    const mod = this.state.modulesConfig.find(m => m.id === moduleId);
    if (mod && mod.allowed_extensions) {
      this.fileInput.accept = mod.allowed_extensions.join(',');
    }
  }

  bindEvents() {
    // Attach button click
    this.btnAttach.addEventListener('click', () => this.fileInput.click());

    // File selected via picker
    this.fileInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (file) this.handleFileSelection(file);
    });

    // Remove selected file
    this.btnRemoveFile.addEventListener('click', () => {
      this.clearSelectedFile();
    });

    // Send / Analyze button
    this.btnSend.addEventListener('click', () => this.startAnalysis());

    // New analysis reset button
    this.btnNewAnalysis.addEventListener('click', () => {
      this.ui.clearThread();
      if (this.emptyState) this.emptyState.style.display = 'flex';
      this.clearSelectedFile();
    });

    // Sidebar toggle
    this.btnToggleSidebar.addEventListener('click', () => {
      this.sidebar.classList.toggle('collapsed');
    });

    // Theme toggle
    this.btnThemeToggle.addEventListener('click', () => {
      this.state.toggleTheme();
    });

    // Quickstart card chips on empty state
    document.querySelectorAll('.quickstart-card').forEach(card => {
      card.addEventListener('click', () => {
        const targetMod = card.dataset.targetModule;
        if (targetMod) {
          this.selectModule(targetMod);
          this.fileInput.click();
        }
      });
    });

    // Drag and Drop over window & composer
    window.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.stopPropagation();
    });

    window.addEventListener('drop', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const files = e.dataTransfer.files;
      if (files && files.length > 0) {
        this.handleFileSelection(files[0]);
      }
    });

    // Keyboard shortcuts (Enter or Ctrl+Enter in composer triggers analysis)
    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        if (!this.btnSend.disabled) {
          this.startAnalysis();
        }
      }
    });
  }

  handleFileSelection(file) {
    this.state.setSelectedFile(file);
    this.selectedFileName.textContent = file.name;
    this.selectedFilePill.style.display = 'inline-flex';
    this.btnSend.disabled = false;

    // Auto-detect best module if obvious
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (['.wav', '.mp3', '.flac', '.ogg', '.m4a'].includes(ext)) {
      if (this.state.selectedModuleId !== 'ai_aud') this.selectModule('ai_aud');
    } else if (['.mp4', '.avi', '.mov', '.mkv'].includes(ext)) {
      if (this.state.selectedModuleId !== 'ai_cctv') this.selectModule('ai_cctv');
    }
  }

  clearSelectedFile() {
    this.state.setSelectedFile(null);
    this.fileInput.value = '';
    this.selectedFilePill.style.display = 'none';
    this.btnSend.disabled = true;
  }

  async startAnalysis() {
    const file = this.state.selectedFile;
    const moduleId = this.state.selectedModuleId;
    if (!file) return;

    // Hide empty state
    if (this.emptyState) this.emptyState.style.display = 'none';

    // Create object URL for local preview (thumbnail, waveform, or video)
    let previewUrl = null;
    try {
      previewUrl = URL.createObjectURL(file);
    } catch (e) {}

    // 1. Render User Bubble
    this.ui.renderUserBubble(file, previewUrl, moduleId);

    // 2. Render Loading Card
    const loadingCard = this.ui.renderLoadingCard(moduleId, 'Submitting file to forensic gateway...');
    this.clearSelectedFile();

    // 3. Submit async job to Gateway
    try {
      const jobInfo = await this.api.submitJob(file, moduleId);
      const jobId = jobInfo.job_id;

      // 4. Poll job status until completed
      let completed = false;
      let attempts = 0;
      const maxAttempts = 180; // Up to 3 minutes timeout

      while (!completed && attempts < maxAttempts) {
        attempts++;
        await new Promise(r => setTimeout(r, 1000));

        const jobStatus = await this.api.pollJob(jobId);
        this.ui.updateProgress(loadingCard, jobStatus.percent, jobStatus.stage);

        if (jobStatus.status === 'completed') {
          completed = true;
          const result = jobStatus.result;
          this.ui.renderForensicResult(loadingCard, result, file, moduleId, previewUrl);

          // Save to local IndexedDB history
          await this.state.saveAnalysis({
            id: jobId,
            timestamp: Date.now(),
            filename: file.name,
            fileSize: file.size,
            fileType: file.type,
            moduleId: moduleId,
            result: result,
          });
          await this.loadHistory();
          break;
        } else if (jobStatus.status === 'failed') {
          completed = true;
          this.ui.renderErrorCard(loadingCard, moduleId, jobStatus.error || 'Forensic analysis failed.', () => {
            this.handleFileSelection(file);
            this.startAnalysis();
          });
          break;
        }
      }

      if (!completed) {
        this.ui.renderErrorCard(loadingCard, moduleId, 'Analysis timed out after 3 minutes. The backend may still be processing.', () => {
          this.handleFileSelection(file);
          this.startAnalysis();
        });
      }

    } catch (err) {
      this.ui.renderErrorCard(loadingCard, moduleId, err.message || 'Network communication error.', () => {
        this.handleFileSelection(file);
        this.startAnalysis();
      });
    }
  }
}

// Bootstrap on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  const app = new AppController();
  app.init().catch(e => console.error('App initialization error:', e));
});
