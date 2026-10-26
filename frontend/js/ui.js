/**
 * UI Renderer: Conversation Thread, User Bubbles, Assistant Forensic Cards
 */

import {
  renderAudioWaveform,
  renderImageGauge,
  setupForgeryViewer,
  renderCCTVTimeline,
} from './visualizers.js';

export class UIRenderer {
  constructor(threadContainer, api) {
    this.threadContainer = threadContainer;
    this.api = api;
  }

  clearThread() {
    this.threadContainer.innerHTML = '';
  }

  /**
   * Render User File Upload Bubble
   */
  renderUserBubble(file, previewUrl, moduleId) {
    const row = document.createElement('div');
    row.className = 'message-row user';

    const sizeStr = file.size > 1024 * 1024
      ? `${(file.size / (1024 * 1024)).toFixed(1)} MB`
      : `${(file.size / 1024).toFixed(0)} KB`;

    let thumbHtml = `
      <svg width="22" height="22">
        <use href="#icon-${moduleId === 'ai_aud' ? 'audio' : moduleId === 'ai_cctv' ? 'cctv' : moduleId === 'image_forgery' ? 'forgery' : 'image'}"></use>
      </svg>
    `;

    if (previewUrl && file.type.startsWith('image/')) {
      thumbHtml = `<img src="${previewUrl}" alt="Thumbnail">`;
    }

    row.innerHTML = `
      <div class="user-bubble">
        <div class="user-file-thumb">${thumbHtml}</div>
        <div class="user-file-info">
          <div class="user-file-name" title="${file.name}">${file.name}</div>
          <div class="user-file-meta">
            <span>${sizeStr}</span>
            <span>&bull;</span>
            <span>${moduleId === 'image_forgery' ? 'PHOTOSHOP FORGERY' : moduleId.toUpperCase()}</span>
          </div>
        </div>
      </div>
    `;

    this.threadContainer.appendChild(row);
    this.scrollToBottom();
    return row;
  }

  /**
   * Render Loading Skeleton Card with Progress
   */
  renderLoadingCard(moduleId, initialStage = 'Initializing analysis...') {
    const row = document.createElement('div');
    row.className = 'message-row assistant';

    row.innerHTML = `
      <div class="assistant-card" id="activeAssistantCard">
        <div class="card-header">
          <div class="card-module-tag">
            <svg width="16" height="16"><use href="#icon-${moduleId === 'ai_aud' ? 'audio' : moduleId === 'ai_cctv' ? 'cctv' : moduleId === 'image_forgery' ? 'forgery' : 'image'}"></use></svg>
            <span>${moduleId === 'image_forgery' ? 'Photoshop Forgery' : moduleId.replace('_', ' ')}</span>
          </div>
          <div class="card-timestamp">${new Date().toLocaleTimeString()}</div>
        </div>
        <div class="loading-box">
          <div class="progress-info">
            <span class="loading-stage">${initialStage}</span>
            <span class="loading-percent">5%</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill" style="width: 5%;"></div>
          </div>
        </div>
      </div>
    `;

    this.threadContainer.appendChild(row);
    this.scrollToBottom();
    return row.querySelector('#activeAssistantCard');
  }

  /**
   * Update Progress on Active Loading Card
   */
  updateProgress(cardElement, percent, stage) {
    if (!cardElement) return;
    const fill = cardElement.querySelector('.progress-fill');
    const pctText = cardElement.querySelector('.loading-percent');
    const stageText = cardElement.querySelector('.loading-stage');

    if (fill) fill.style.width = `${percent}%`;
    if (pctText) pctText.textContent = `${percent}%`;
    if (stageText && stage) stageText.textContent = stage;
  }

  /**
   * Replace Loading Card with Full Forensic Result Card
   */
  renderForensicResult(cardElement, result, file, moduleId, previewUrl) {
    if (!cardElement) return;

    const verdict = result.verdict || 'inconclusive';
    const confidence = result.overall_confidence;
    const confidenceText = (confidence === null || confidence === undefined)
      ? 'Confidence: not available'
      : `Confidence: ${(confidence * 100).toFixed(0)}%`;
    const rawMetrics = result.raw_metrics || {};
    const findings = result.findings || [];
    const sha256 = result.evidence_file?.sha256 || 'not available';
    const analyzedAt = result.analyzed_at || new Date().toISOString();

    // Map verdict to banner class and label
    const verdictMap = {
      authentic: { class: 'authentic', label: 'Authentic / Genuine' },
      likely_real: { class: 'authentic', label: 'Likely Real' },
      suspicious: { class: 'suspicious', label: 'Suspicious / Inconclusive' },
      inconclusive: { class: 'inconclusive', label: 'Inconclusive - Human Review Recommended' },
      likely_fake: { class: 'tampered', label: 'Likely AI-Generated' },
      likely_tampered: { class: 'tampered', label: 'Likely Tampered / Spliced' },
      tampered: { class: 'tampered', label: 'Tampered / Spoof Detected' },
    };

    const vInfo = verdictMap[verdict.toLowerCase()] || { class: 'inconclusive', label: verdict };

    // Build specialized forensic section based on module
    let moduleSpecificHtml = '';

    if (moduleId === 'ai_aud') {
      // Audio: bona-fide logit (NEVER percentage!)
      const logitVal = rawMetrics.clip_summary?.median_logit ?? rawMetrics.bona_fide_logit;
      const hasNumericScore = typeof logitVal === 'number' && !isNaN(logitVal);
      const formattedLogit = hasNumericScore ? (logitVal > 0 ? `+${logitVal.toFixed(3)}` : logitVal.toFixed(3)) : 'N/A';
      const scoreReason = result.score_unavailable_reason || rawMetrics.score_unavailable_reason || (hasNumericScore ? '' : 'Score unavailable for this recording');
      const validWindows = rawMetrics.valid_windows ?? rawMetrics.windows_analyzed ?? 0;
      const totalWindows = rawMetrics.total_windows ?? rawMetrics.windows_analyzed ?? 0;
      const speechWindows = rawMetrics.speech_windows ?? (rawMetrics.windows ? rawMetrics.windows.filter(w => w.speech_fraction >= 0.5).length : 0);

      moduleSpecificHtml = `
        <div class="audio-metric-container">
          <div class="metric-value-box">
            <div class="metric-title">
              <span>Bona-Fide Score</span>
              <span class="has-tooltip" data-tooltip="Raw acoustic logit from AASIST backend. Higher positive values indicate genuine human speech. It is NOT a percentage or probability.">&#9432;</span>
            </div>
            <div class="metric-number">${formattedLogit}</div>
            ${!hasNumericScore ? `<div class="metric-subnote" style="color: #f59e0b; font-weight: 500;">${scoreReason}</div>` : ''}
            <div class="metric-subnote">Thresholds: Authenticity cutoff &gt; +1.5 &bull; Spoof cutoff &lt; -3.7</div>
          </div>
          <div style="text-align: right; font-size: 0.8rem; color: var(--text-muted); line-height: 1.4;">
            <div>Windows analysed: <strong>${validWindows} / ${totalWindows}</strong></div>
            <div>Speech windows: <strong>${speechWindows}</strong></div>
            <div>Sample Rate: <strong>${rawMetrics.audio_info?.orig_sr ? rawMetrics.audio_info.orig_sr + ' Hz' : '16 kHz'}</strong></div>
          </div>
        </div>

        ${previewUrl ? `
          <div class="audio-player-wrapper">
            <audio controls src="${previewUrl}"></audio>
          </div>
        ` : ''}

        <div style="margin-top: 6px;">
          <div class="crops-title" style="margin-bottom: 4px;">Acoustic Waveform & Analyzed 4.04s Windows</div>
          <div class="waveform-canvas-box">
            <canvas class="waveform-canvas" id="audioWaveformCanvas"></canvas>
          </div>
          <div class="speech-window-legend">
            <div class="legend-item"><div class="legend-color-dot analyzed"></div><span>Analyzed Speech Windows</span></div>
            <div class="legend-item"><div class="legend-color-dot baseline"></div><span>Non-speech / Background</span></div>
          </div>
        </div>
      `;
    } else if (moduleId === 'ai_img') {
      // AI Image: calibrated P(fake), photo type, quality check
      const prob = rawMetrics.calibrated_probability ?? 0;
      const photoType = rawMetrics.photo_type || 'Unknown';
      const crops = rawMetrics.per_crop_scores || [];

      moduleSpecificHtml = `
        <div id="gaugeContainer"></div>

        <div style="display: flex; gap: 16px; margin-top: 10px; flex-wrap: wrap;">
          <div style="flex: 1; min-width: 200px;" class="crops-grid-container">
            <div class="crops-title">9-Crop Spatial Variation</div>
            <div class="crops-grid">
              ${crops.length === 9 ? crops.map((c, i) => `<div class="crop-cell">C${i+1}: ${(c*100).toFixed(0)}%</div>`).join('') : '<div style="color:var(--text-muted);font-size:0.8rem;">Uniform crop analysis applied</div>'}
            </div>
          </div>

          <div style="flex: 1; min-width: 200px;" class="crops-grid-container">
            <div class="crops-title">Classification & Quality Assessment</div>
            <div style="background:var(--bg-surface);padding:10px 14px;border-radius:var(--radius-md);font-size:0.82rem;line-height:1.5;">
              <div>Photo Type: <strong>${photoType.replace('_', ' ')}</strong></div>
              <div>Estimated JPEG Quality: <strong>${rawMetrics.jpeg_quality_estimate ?? 'N/A'}</strong></div>
              <div>Laplacian Variance: <strong>${rawMetrics.photo_type_details?.laplacian_variance ?? 'N/A'}</strong></div>
              <div>Resolution: <strong>${rawMetrics.photo_type_details?.resolution || (rawMetrics.image_dimensions ? rawMetrics.image_dimensions.join('x') : 'N/A')}</strong></div>
            </div>
          </div>
        </div>
      `;
    } else if (moduleId === 'image_forgery') {
      // Forgery: TruFor overlay with opacity slider & side-by-side
      const truforScore = rawMetrics.engines?.trufor?.global_score ?? 'N/A';
      const formattedScore = typeof truforScore === 'number' ? truforScore.toFixed(3) : truforScore;
      
      // Find heatmap artifact and ELA artifact
      let heatmapUrl = null;
      let elaUrl = null;
      for (const f of findings) {
        if (f.evidence_artifacts) {
          for (const art of f.evidence_artifacts) {
            if (art.includes('trufor_overlay') || art.includes('heatmap')) {
              heatmapUrl = this.api.getArtifactUrl(moduleId, art);
            }
            if (art.includes('ela')) {
              elaUrl = this.api.getArtifactUrl(moduleId, art);
            }
          }
        }
      }

      moduleSpecificHtml = `
        <div class="audio-metric-container" style="margin-bottom: 12px;">
          <div class="metric-value-box">
            <div class="metric-title">
              <span>TruFor Integrity Score</span>
              <span class="has-tooltip" data-tooltip="TruFor Transformer image-level integrity score (0.0 = authentic, 1.0 = tampered). Shown separately from ELA/metadata heuristics.">&#9432;</span>
            </div>
            <div class="metric-number">${formattedScore}</div>
            <div class="metric-subnote">Thresholds: Authentic &lt; 0.35 &bull; Tampered &gt; 0.60</div>
          </div>
          <div style="text-align: right; font-size: 0.8rem; color: var(--text-muted);">
            <div>Primary Model: <strong>TruFor (RGB + Noise)</strong></div>
            <div>Classical Heuristic: <strong>ELA & Metadata</strong></div>
          </div>
        </div>

        <div id="forgeryViewerBox"></div>
      `;
    } else if (moduleId === 'ai_cctv') {
      // CCTV: video player + timeline chart + quality gate
      const medianP = rawMetrics.median_p ?? 'N/A';
      const formattedP = typeof medianP === 'number' ? `${(medianP * 100).toFixed(1)}%` : medianP;
      const frameScores = rawMetrics.frame_scores || [];
      const durationSec = rawMetrics.video_metadata?.duration || 1.0;

      // Extract flagged time intervals
      const flaggedScores = frameScores.filter(f => (f.score ?? 0) >= 0.70);

      moduleSpecificHtml = `
        <div class="audio-metric-container" style="margin-bottom: 12px;">
          <div class="metric-value-box">
            <div class="metric-title">
              <span>CCTV Median AI Probability</span>
              <span class="has-tooltip" data-tooltip="Aggregated clip median AI synthesis probability from fine-tuned YOLO11-cls across quality-screened tiles.">&#9432;</span>
            </div>
            <div class="metric-number">${formattedP}</div>
            <div class="metric-subnote">Cutoff: 0.70 AI Threshold &bull; Aggregated from ${rawMetrics.kept_count || frameScores.length} frames</div>
          </div>
          <div style="text-align: right; font-size: 0.8rem; color: var(--text-muted);">
            <div>Architecture: <strong>YOLO11-cls (Fine-Tuned)</strong></div>
            <div>Frames Inspected: <strong>${rawMetrics.total_sampled ?? frameScores.length}</strong></div>
          </div>
        </div>

        ${previewUrl ? `
          <div class="video-preview-wrapper">
            <video id="cctvVideoPlayer" class="video-player" controls src="${previewUrl}"></video>
          </div>
        ` : ''}

        <div style="margin-top: 6px;">
          <div class="crops-title" style="margin-bottom: 4px;">Per-Frame AI Score Timeline (Click to seek video)</div>
          <div class="timeline-canvas-box">
            <canvas class="timeline-canvas" id="cctvTimelineCanvas"></canvas>
          </div>
        </div>

        ${flaggedScores.length > 0 ? `
          <div class="flagged-ranges-container">
            <div class="flagged-ranges-title">Suspicious Intervals Exceeding 0.70 Threshold:</div>
            <div class="flagged-pill-list">
              ${flaggedScores.map(f => `
                <button class="seek-pill" data-time="${f.timestamp}">
                  <svg width="10" height="10"><use href="#icon-play"></use></svg>
                  <span>${f.timestamp.toFixed(2)}s (${(f.score * 100).toFixed(0)}%)</span>
                </button>
              `).join('')}
            </div>
          </div>
        ` : ''}

        <div style="margin-top: 10px;">
          <div class="crops-title">Quality Gate Statistics</div>
          <table class="quality-gate-table">
            <tr><td>Total Sampled Frames</td><td>${rawMetrics.total_sampled ?? 'N/A'}</td></tr>
            <tr><td>Retained for Inference</td><td>${rawMetrics.kept_count ?? 'N/A'} (Quality Pass)</td></tr>
            <tr><td>Dropped (Blur / Low-Res / Artifacts)</td><td>${rawMetrics.dropped_count ?? 0}</td></tr>
          </table>
        </div>
      `;
    }

    // Build Findings section
    let findingsHtml = '';
    if (findings.length > 0) {
      findingsHtml = `
        <div class="findings-container">
          <div class="findings-title">Key Forensic Findings & Observations</div>
          ${findings.map(f => `
            <div class="finding-item">
              <div class="finding-header">
                <span class="finding-check-name">${f.check || f.id}</span>
                <span class="finding-severity ${f.severity || 'info'}">${f.severity || 'info'}</span>
              </div>
              <div class="finding-desc">${f.description || 'No description provided.'}</div>
            </div>
          `).join('')}
        </div>
      `;
    }

    // Construct full card DOM
    cardElement.innerHTML = `
      <div class="card-header">
        <div class="card-module-tag">
          <svg width="16" height="16"><use href="#icon-${moduleId === 'ai_aud' ? 'audio' : moduleId === 'ai_cctv' ? 'cctv' : moduleId === 'image_forgery' ? 'forgery' : 'image'}"></use></svg>
          <span>${moduleId === 'image_forgery' ? 'Photoshop Forgery' : moduleId.replace('_', ' ')} Forensic Assessment</span>
        </div>
        <div class="card-timestamp">${new Date(analyzedAt).toLocaleTimeString()}</div>
      </div>

      <div class="verdict-banner ${vInfo.class}">
        <div class="verdict-badge">
          <svg width="18" height="18"><use href="#icon-${vInfo.class === 'authentic' ? 'check' : vInfo.class === 'tampered' ? 'alert' : 'info'}"></use></svg>
          <span>${vInfo.label}</span>
        </div>
        <div class="verdict-confidence">${confidenceText}</div>
      </div>

      ${moduleSpecificHtml}

      ${findingsHtml}

      <!-- Persistent Caution Line -->
      <div class="forensic-caution-banner">
        <svg width="16" height="16" style="flex-shrink: 0;"><use href="#icon-info"></use></svg>
        <span class="forensic-caution-text">This is a forensic signal, not proof. Always corroborate with DVR logs, chain of custody, and metadata.</span>
      </div>

      <!-- Expandable Details & Chain of Custody -->
      <details class="details-drawer">
        <summary class="details-summary">
          <span>Details & Chain of Custody</span>
          <svg width="12" height="12"><use href="#icon-sidebar"></use></svg>
        </summary>
        <div class="details-content">
          <div class="details-row"><span class="details-label">Evidence File:</span><span class="details-value">${file.name}</span></div>
          <div class="details-row"><span class="details-label">SHA-256 Hash:</span><span class="details-value">${sha256}</span></div>
          <div class="details-row"><span class="details-label">File Size:</span><span class="details-value">${file.size} bytes</span></div>
          <div class="details-row"><span class="details-label">Module Version:</span><span class="details-value">${result.version || '1.0'}</span></div>
          <div class="details-row"><span class="details-label">Analyzed At:</span><span class="details-value">${analyzedAt}</span></div>
          <div class="details-row"><span class="details-label">Processing Time:</span><span class="details-value">${rawMetrics.inference_ms ? rawMetrics.inference_ms.toFixed(0) + ' ms' : (rawMetrics.total_runtime_sec ? (rawMetrics.total_runtime_sec * 1000).toFixed(0) + ' ms' : 'not available')}</span></div>
        </div>
      </details>

      <!-- Collapsible Raw JSON Debug Panel -->
      <details class="details-drawer" style="margin-top: 8px;">
        <summary class="details-summary">
          <span>Raw JSON Response</span>
          <svg width="12" height="12"><use href="#icon-sidebar"></use></svg>
        </summary>
        <div class="details-content" style="padding: 10px;">
          <pre style="background: var(--bg-surface); padding: 10px; border-radius: var(--radius-sm); font-size: 0.72rem; overflow-x: auto; max-height: 320px; color: var(--text-main); font-family: monospace; white-space: pre-wrap; word-break: break-all;">${JSON.stringify(result, null, 2)}</pre>
        </div>
      </details>

      <!-- Card Action Buttons -->
      <div class="card-actions-row">
        <button class="btn-secondary btn-copy-json" title="Copy raw JSON payload">
          <svg width="14" height="14"><use href="#icon-copy"></use></svg>
          <span>Copy JSON</span>
        </button>
        <button class="btn-secondary btn-download-report" title="Generate printable HTML forensic report">
          <svg width="14" height="14"><use href="#icon-download"></use></svg>
          <span>Download Report</span>
        </button>
      </div>
    `;

    // Hook up visualizers now that DOM is attached
    if (moduleId === 'ai_aud') {
      const canvas = cardElement.querySelector('#audioWaveformCanvas');
      renderAudioWaveform(canvas, rawMetrics.per_window_logits, rawMetrics.audio_info?.duration_sec);
    } else if (moduleId === 'ai_img') {
      const gCont = cardElement.querySelector('#gaugeContainer');
      renderImageGauge(gCont, rawMetrics.calibrated_probability);
    } else if (moduleId === 'image_forgery') {
      const vBox = cardElement.querySelector('#forgeryViewerBox');
      let heatmapUrl = null;
      let elaUrl = null;
      for (const f of findings) {
        if (f.evidence_artifacts) {
          for (const art of f.evidence_artifacts) {
            if (art.includes('trufor_overlay') || art.includes('heatmap')) {
              heatmapUrl = this.api.getArtifactUrl(moduleId, art);
            }
            if (art.includes('ela')) {
              elaUrl = this.api.getArtifactUrl(moduleId, art);
            }
          }
        }
      }
      setupForgeryViewer(vBox, previewUrl, heatmapUrl, elaUrl);
    } else if (moduleId === 'ai_cctv') {
      const vPlayer = cardElement.querySelector('#cctvVideoPlayer');
      const cCanvas = cardElement.querySelector('#cctvTimelineCanvas');
      renderCCTVTimeline(cCanvas, vPlayer, rawMetrics.frame_scores, rawMetrics.video_metadata?.duration);

      // Hook up seek pills
      cardElement.querySelectorAll('.seek-pill').forEach(pill => {
        pill.addEventListener('click', () => {
          const t = parseFloat(pill.dataset.time);
          if (vPlayer && !isNaN(t)) {
            vPlayer.currentTime = t;
            vPlayer.play().catch(() => {});
          }
        });
      });
    }

    // Hook up "Copy JSON" button
    const copyBtn = cardElement.querySelector('.btn-copy-json');
    if (copyBtn) {
      copyBtn.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(JSON.stringify(result, null, 2));
          copyBtn.innerHTML = `
            <svg width="14" height="14"><use href="#icon-check"></use></svg>
            <span>Copied!</span>
          `;
          setTimeout(() => {
            copyBtn.innerHTML = `
              <svg width="14" height="14"><use href="#icon-copy"></use></svg>
              <span>Copy JSON</span>
            `;
          }, 2000);
        } catch (e) {
          alert('Failed to copy to clipboard.');
        }
      });
    }

    // Hook up "Download Report" button (Printable HTML Forensic Dossier)
    const reportBtn = cardElement.querySelector('.btn-download-report');
    if (reportBtn) {
      reportBtn.addEventListener('click', () => {
        this.generatePrintableReport(result, file, moduleId, vInfo);
      });
    }

    this.scrollToBottom();
  }

  /**
   * Render Friendly Error Card with Retry Button
   */
  renderErrorCard(cardElement, moduleId, errorMessage, onRetry) {
    if (!cardElement) return;

    cardElement.className = 'assistant-card error-card';
    cardElement.innerHTML = `
      <div class="error-title">
        <svg width="18" height="18"><use href="#icon-alert"></use></svg>
        <span>Forensic Analysis Failed</span>
      </div>
      <div class="error-message">${errorMessage}</div>
      <div class="card-actions-row">
        ${onRetry ? `
          <button class="btn-secondary btn-retry" style="border-color: var(--verdict-tampered-border);">
            <svg width="14" height="14"><use href="#icon-refresh"></use></svg>
            <span>Retry Analysis</span>
          </button>
        ` : ''}
      </div>
    `;

    const retryBtn = cardElement.querySelector('.btn-retry');
    if (retryBtn && onRetry) {
      retryBtn.addEventListener('click', onRetry);
    }
  }

  /**
   * Generates a printable HTML forensic report dossier
   */
  generatePrintableReport(result, file, moduleId, vInfo) {
    const reportWindow = window.open('', '_blank');
    if (!reportWindow) {
      alert('Popup blocked. Please allow popups to view the printable forensic report.');
      return;
    }

    const sha256 = result.evidence_file?.sha256 || 'N/A';
    const analyzedAt = result.analyzed_at || new Date().toISOString();
    const findings = result.findings || [];

    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
        <title>Forensic Evidence Dossier - ${file.name}</title>
        <style>
          body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #1F1E1D; line-height: 1.5; margin: 40px auto; max-width: 800px; padding: 0 20px; }
          h1 { font-family: Charter, Cambria, Georgia, serif; font-size: 24px; border-bottom: 2px solid #C96442; padding-bottom: 8px; margin-bottom: 20px; }
          .banner { padding: 12px 16px; border-radius: 6px; font-weight: bold; margin-bottom: 20px; background: #F5F3EC; border: 1px solid #E8E6DC; }
          table { width: 100%; border-collapse: collapse; margin-bottom: 24px; font-size: 14px; }
          th, td { text-align: left; padding: 8px 12px; border-bottom: 1px solid #E8E6DC; }
          th { background: #FAF9F5; width: 30%; color: #57554F; }
          .finding { background: #FAF9F5; border-left: 3px solid #C96442; padding: 10px 14px; margin-bottom: 10px; border-radius: 0 4px 4px 0; }
          .caution { background: #FFFBEB; border: 1px solid #FDE68A; color: #92400E; padding: 12px; border-radius: 6px; font-size: 13px; margin-top: 24px; font-weight: 500; }
          @media print { .no-print { display: none; } }
        </style>
      </head>
      <body>
        <div class="no-print" style="margin-bottom: 20px; text-align: right;">
          <button onclick="window.print()" style="padding: 8px 16px; background: #C96442; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">Print / Save PDF</button>
        </div>
        <h1>AI Forensic Evidence Report</h1>
        <div class="banner">Verdict: ${vInfo.label} (Confidence: ${((result.overall_confidence || 0) * 100).toFixed(0)}%)</div>
        <table>
          <tr><th>Evidence Filename</th><td>${file.name}</td></tr>
          <tr><th>File Size</th><td>${file.size} bytes</td></tr>
          <tr><th>SHA-256 Hash</th><td><code style="word-break: break-all;">${sha256}</code></td></tr>
          <tr><th>Target Module</th><td>${moduleId === 'image_forgery' ? 'PHOTOSHOP FORGERY' : moduleId.toUpperCase()}</td></tr>
          <tr><th>Analysis Timestamp</th><td>${analyzedAt}</td></tr>
          <tr><th>Module Version</th><td>${result.version || '1.0'}</td></tr>
        </table>

        <h3>Forensic Observations & Findings</h3>
        ${findings.map(f => `
          <div class="finding">
            <strong>${f.check || f.id} (${(f.severity || 'info').toUpperCase()})</strong>
            <div>${f.description}</div>
          </div>
        `).join('')}

        <div class="caution">
          <strong>LEGAL CAUTION:</strong> This assessment represents an automated forensic computational signal, not conclusive proof. Accuracy varies across unseen generative models, encoding pipelines, and acoustic/visual noise. This report must be corroborated with original device records and human expert review.
        </div>
      </body>
      </html>
    `;

    reportWindow.document.write(html);
    reportWindow.document.close();
  }

  scrollToBottom() {
    requestAnimationFrame(() => {
      this.threadContainer.scrollTop = this.threadContainer.scrollHeight;
    });
  }
}
