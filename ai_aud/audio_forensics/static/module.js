/**
 * PS-05 Audio Forensics Module UI
 * Standard Integration Contract: exposes initModule(containerElementId)
 * Local-only execution, zero external CDN dependencies.
 */

function initModule(containerElementId) {
  const container = document.getElementById(containerElementId);
  if (!container) {
    console.error(`[audio_forensics] Container element #${containerElementId} not found.`);
    return;
  }

  // Inject HTML template
  container.innerHTML = `
    <div class="audio_forensics-wrapper">
      <div class="audio_forensics-header">
        <div class="audio_forensics-title-group">
          <h2>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
              <line x1="12" y1="19" x2="12" y2="23"/>
              <line x1="8" y1="23" x2="16" y2="23"/>
            </svg>
            Audio Authenticity & Splice Verification
          </h2>
          <div class="audio_forensics-subtitle">PS-05 Digital Evidence Platform &bull; W2V2-AASIST Neural Deepfake & Splicing Detector</div>
        </div>
      </div>

      <!-- Setup Banner if model not installed -->
      <div id="af-model-banner" class="audio_forensics-banner" style="display: none;">
        <strong>Notice: Deepfake Detection Checkpoints Missing</strong>
        <p style="margin: 0.3rem 0 0 0;">The neural anti-spoofing model weights (<code>xlsr2_300m.pt</code> and <code>LA_model.pth</code>) were not detected in <code>audio_forensics/models/</code>.</p>
        <ol>
          <li>Run <code>run_platform.bat</code> from the project root to automatically download required weights, or</li>
          <li>Place <code>xlsr2_300m.pt</code> and <code>LA_model.pth</code> manually into <code>audio_forensics/models/</code>.</li>
        </ol>
      </div>

      <!-- Upload Zone -->
      <div id="af-dropzone" class="audio_forensics-dropzone">
        <input type="file" id="af-file-input" accept="audio/*,.wav,.mp3,.flac,.ogg,.m4a,.aac" style="display: none;" />
        <div class="audio_forensics-dropzone-icon">🎙️</div>
        <div class="audio_forensics-dropzone-text">Drop evidence audio file here or click to browse</div>
        <div class="audio_forensics-dropzone-subtext">Supports WAV, MP3, FLAC, OGG, M4A, AAC &bull; Up to 200 MB &bull; 100% Local Inference</div>
      </div>

      <!-- Progress Section -->
      <div id="af-progress" class="audio_forensics-progress-container">
        <div style="font-weight: 600; font-size: 1rem;" id="af-progress-title">Analyzing Evidence Audio...</div>
        <div class="audio_forensics-progress-bar-bg">
          <div id="af-progress-fill" class="audio_forensics-progress-bar-fill"></div>
        </div>
        <div id="af-progress-stage" class="audio_forensics-progress-label">Preparing pipeline...</div>
      </div>

      <!-- Results Section -->
      <div id="af-results" class="audio_forensics-results">
        
        <!-- Lossy Codec Notice Banner -->
        <div id="af-codec-banner" class="audio_forensics-codec-banner" style="display: none;">
          <!-- Dynamically populated if lossy input -->
        </div>

        <!-- Summary Cards Grid -->
        <div class="audio_forensics-summary-grid">
          
          <!-- Verdict Card -->
          <div class="audio_forensics-card">
            <div class="audio_forensics-card-title">Authenticity Verdict</div>
            <div>
              <span id="af-verdict-badge" class="audio_forensics-verdict-badge">INCONCLUSIVE</span>
            </div>
            <div style="margin-top: 0.75rem; font-size: 0.85rem; color: var(--audio_forensics-text-muted);">
              Confidence: <strong id="af-confidence-val" style="color: #fff;">0%</strong>
            </div>
          </div>

          <!-- Logit Gauge Card -->
          <div class="audio_forensics-card">
            <div class="audio_forensics-card-title">W2V2-AASIST Bona-Fide Score</div>
            <div style="font-size: 1.25rem; font-weight: 700;" id="af-logit-display">0.00</div>
            <div class="audio_forensics-gauge-container">
              <div class="audio_forensics-gauge-bar">
                <div class="audio_forensics-gauge-zone-synthetic" title="Synthetic speech zone (< -1.5)"></div>
                <div class="audio_forensics-gauge-zone-uncertain" title="Uncertain band (-1.5 to +1.5)"></div>
                <div class="audio_forensics-gauge-zone-authentic" title="Authentic speech zone (> +1.5)"></div>
                <div id="af-gauge-marker" class="audio_forensics-gauge-marker" style="left: 50%;"></div>
              </div>
              <div class="audio_forensics-gauge-labels">
                <span>&larr; Synthetic (-3.0)</span>
                <span>Uncertain Band</span>
                <span>Authentic (+3.0) &rarr;</span>
              </div>
            </div>
            <div style="font-size: 0.7rem; color: var(--audio_forensics-text-muted); margin-top: 0.4rem;">
              Raw logit metric (higher = more genuine). Not a probability percentage.
            </div>
          </div>

          <!-- File Evidence Info -->
          <div class="audio_forensics-card">
            <div class="audio_forensics-card-title">Evidence Chain of Custody</div>
            <div style="font-size: 0.825rem; color: #cbd5e1; word-break: break-all;">
              <div><strong>File:</strong> <span id="af-meta-name">-</span></div>
              <div><strong>Size:</strong> <span id="af-meta-size">-</span></div>
              <div><strong>Duration:</strong> <span id="af-meta-dur">-</span></div>
              <div style="margin-top: 0.3rem;"><strong>SHA-256:</strong></div>
              <div style="font-family: monospace; font-size: 0.725rem; color: #94a3b8;" id="af-meta-sha">-</div>
            </div>
          </div>

        </div>

        <!-- Embedded Audio Player Card -->
        <div class="audio_forensics-player-card">
          <div class="audio_forensics-card-title">Evidence Playback & Segment Navigation</div>
          <audio id="af-audio-player" controls preload="auto"></audio>
          <div id="af-suspicious-segments-bar" style="margin-top: 0.5rem; font-size: 0.8rem; color: var(--audio_forensics-text-muted);">
            <!-- Populated with quick-seek links if suspicious segments found -->
          </div>
          <div style="margin-top: 0.75rem; font-size: 0.8rem; font-weight: 600; color: #94a3b8; display: flex; justify-content: space-between;">
            <span>Analyzed Windows & Voice Activity:</span>
            <span style="font-weight: 400; font-size: 0.75rem;">Grey = &lt;50% speech (excluded)</span>
          </div>
          <div id="af-window-strip" class="audio_forensics-timeline-strip">
            <!-- Populated with window pills -->
          </div>
        </div>


        <!-- Visual Evidence Section -->
        <div class="audio_forensics-evidence-grid">
          
          <div class="audio_forensics-visual-box">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <div class="audio_forensics-card-title" style="margin: 0;">Waveform & Flagged Tampering Regions</div>
              <span style="font-size: 0.75rem; color: var(--audio_forensics-text-muted);">Red shading = AASIST score &lt; low_threshold</span>
            </div>
            <img id="af-img-waveform" alt="Waveform Analysis" />
          </div>

          <div class="audio_forensics-visual-box">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <div class="audio_forensics-card-title" style="margin: 0;">Spectral Energy & Discontinuity Markers</div>
              <span style="font-size: 0.75rem; color: var(--audio_forensics-text-muted);">Dashed lines = Detected acoustic / splice cut points</span>
            </div>
            <img id="af-img-spectrogram" alt="Spectrogram Analysis" />
          </div>

          <div class="audio_forensics-visual-box">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <div class="audio_forensics-card-title" style="margin: 0;">Per-Window Detection Score Timeline</div>
              <span style="font-size: 0.75rem; color: var(--audio_forensics-text-muted);">64,600-sample sliding windows &bull; Amber band = Uncertain</span>
            </div>
            <img id="af-img-timeline" alt="Logit Timeline Analysis" />
          </div>

        </div>

        <!-- Forensic Findings List -->
        <div class="audio_forensics-findings-container">
          <div class="audio_forensics-card-title" style="margin-bottom: 0.8rem;">Forensic Findings & Anomaly Indicators</div>
          <div id="af-findings-list">
            <!-- Dynamically populated -->
          </div>
        </div>

        <!-- Actions Footer -->
        <div class="audio_forensics-actions">
          <button id="af-btn-reset" class="audio_forensics-btn">Analyze Another File</button>
          <button id="af-btn-download" class="audio_forensics-btn audio_forensics-btn-primary">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            Download Result JSON
          </button>
        </div>

      </div>
    </div>
  `;

  // UI Element References
  const dropzone = container.querySelector("#af-dropzone");
  const fileInput = container.querySelector("#af-file-input");
  const progressBox = container.querySelector("#af-progress");
  const progressFill = container.querySelector("#af-progress-fill");
  const progressStage = container.querySelector("#af-progress-stage");
  const resultsBox = container.querySelector("#af-results");
  const modelBanner = container.querySelector("#af-model-banner");
  const audioPlayer = container.querySelector("#af-audio-player");
  const btnReset = container.querySelector("#af-btn-reset");
  const btnDownload = container.querySelector("#af-btn-download");

  let latestResult = null;

  // Drag and drop event listeners
  dropzone.addEventListener("click", () => fileInput.click());

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileUpload(e.target.files[0]);
    }
  });

  btnReset.addEventListener("click", () => {
    resultsBox.style.display = "none";
    dropzone.style.display = "block";
    fileInput.value = "";
    if (audioPlayer.src) {
      audioPlayer.pause();
      URL.revokeObjectURL(audioPlayer.src);
      audioPlayer.src = "";
    }
  });

  btnDownload.addEventListener("click", () => {
    if (!latestResult) return;
    const blob = new Blob([JSON.stringify(latestResult, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audio_forensics_${latestResult.evidence_file?.name || "result"}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  });

  // Upload and Analysis Handler
  function handleFileUpload(file) {
    dropzone.style.display = "none";
    progressBox.style.display = "block";
    resultsBox.style.display = "none";
    progressFill.style.width = "10%";
    progressStage.textContent = "Uploading evidence file...";

    // Set audio player source to local file blob
    try {
      const audioUrl = URL.createObjectURL(file);
      audioPlayer.src = audioUrl;
    } catch (err) {
      console.warn("Could not create object URL for player:", err);
    }

    const formData = new FormData();
    formData.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/audio_forensics/analyze", true);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const pct = Math.round((e.loaded / e.total) * 40);
        progressFill.style.width = `${pct}%`;
        progressStage.textContent = `Uploading: ${pct}%`;
      }
    };

    xhr.onload = () => {
      progressFill.style.width = "85%";
      progressStage.textContent = "Running W2V2-AASIST & heuristic checks...";

      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const result = JSON.parse(xhr.responseText);
          progressFill.style.width = "100%";
          setTimeout(() => {
            progressBox.style.display = "none";
            renderResults(result);
          }, 300);
        } catch (err) {
          showError("Failed to parse server response.");
        }
      } else {
        try {
          const errData = JSON.parse(xhr.responseText);
          showError(errData.detail || errData.errors?.join(", ") || "Analysis request failed.");
        } catch {
          showError(`HTTP Error ${xhr.status}: ${xhr.statusText}`);
        }
      }
    };

    xhr.onerror = () => {
      showError("Network connection error communicating with /api/audio_forensics/analyze");
    };

    xhr.send(formData);
  }

  function showError(msg) {
    progressBox.style.display = "none";
    dropzone.style.display = "block";
    alert(`Audio Forensics Error:\n${msg}`);
  }

  // Render Result Function
  function renderResults(res) {
    latestResult = res;
    resultsBox.style.display = "block";

    // Verdict Badge
    const verdict = (res.verdict || "inconclusive").toLowerCase();
    const verdictBadge = container.querySelector("#af-verdict-badge");
    verdictBadge.textContent = verdict.replace("_", " ");
    verdictBadge.className = `audio_forensics-verdict-badge audio_forensics-verdict-${verdict}`;

    // Confidence
    const confPct = Math.round((res.overall_confidence || 0) * 100);
    container.querySelector("#af-confidence-val").textContent = `${confPct}%`;

    // Evidence Metadata
    container.querySelector("#af-meta-name").textContent = res.evidence_file?.name || "audio";
    const bytes = res.evidence_file?.size_bytes || 0;
    container.querySelector("#af-meta-size").textContent = bytes > 1048576 ? `${(bytes / 1048576).toFixed(2)} MB` : `${(bytes / 1024).toFixed(1)} KB`;
    container.querySelector("#af-meta-dur").textContent = `${res.raw_metrics?.audio_info?.duration_sec || 0} s`;
    container.querySelector("#af-meta-sha").textContent = res.evidence_file?.sha256 || "N/A";

    // Logit Gauge
    const clipSummary = res.raw_metrics?.clip_summary || {};
    const medianLogit = typeof clipSummary.median_logit === "number" ? clipSummary.median_logit : null;
    const logitDisplay = container.querySelector("#af-logit-display");
    const gaugeMarker = container.querySelector("#af-gauge-marker");

    if (medianLogit !== null) {
      logitDisplay.textContent = `${medianLogit >= 0 ? "+" : ""}${medianLogit.toFixed(2)}`;
      logitDisplay.style.color = medianLogit >= 1.5 ? "var(--audio_forensics-ok)" : (medianLogit <= -1.5 ? "var(--audio_forensics-danger)" : "var(--audio_forensics-warn)");

      // Map logit range [-3.0, +3.0] to gauge [0%, 100%]
      const clamped = Math.max(-3.0, Math.min(3.0, medianLogit));
      const gaugePct = Math.round(((clamped + 3.0) / 6.0) * 100);
      gaugeMarker.style.left = `${gaugePct}%`;
      gaugeMarker.style.display = "block";
    } else {
      logitDisplay.textContent = "N/A";
      logitDisplay.style.color = "#94a3b8";
      gaugeMarker.style.display = "none";
    }

    // Codec Warning Banner
    const codecBanner = container.querySelector("#af-codec-banner");
    const lossyFinding = (res.findings || []).find(f => f.check === "lossy_codec_input");
    if (lossyFinding) {
      codecBanner.innerHTML = `
        <div style="display: flex; gap: 0.75rem; align-items: flex-start;">
          <span style="font-size: 1.25rem;">⚠️</span>
          <div>
            <strong>Lossy Compressed Input Detected</strong>
            <p style="margin: 0.25rem 0 0 0; color: #fde68a;">${lossyFinding.description}</p>
          </div>
        </div>
      `;
      codecBanner.style.display = "block";
    } else {
      codecBanner.style.display = "none";
    }

    // Check if model not installed finding exists
    const hasModelNotInstalled = (res.findings || []).some(f => f.check === "model_not_installed");
    modelBanner.style.display = hasModelNotInstalled ? "block" : "none";

    // Suspicious Segment Seek Bar
    const segBar = container.querySelector("#af-suspicious-segments-bar");
    segBar.innerHTML = "";
    const suspiciousSegments = (res.findings || []).filter(f => f.location && f.location.time_range_sec);

    if (suspiciousSegments.length > 0) {
      const spanTitle = document.createElement("span");
      spanTitle.textContent = "Jump to flagged segment: ";
      segBar.appendChild(spanTitle);

      suspiciousSegments.forEach(f => {
        const [start, end] = f.location.time_range_sec;
        const tag = document.createElement("span");
        tag.className = "audio_forensics-seek-tag";
        tag.textContent = `▶ ${start.toFixed(1)}s - ${end.toFixed(1)}s (${f.check})`;
        tag.addEventListener("click", () => {
          audioPlayer.currentTime = start;
          audioPlayer.play();
        });
        segBar.appendChild(tag);
      });
    }

    // Analyzed Windows Strip (VAD Speech vs Non-Speech)
    const windowStrip = container.querySelector("#af-window-strip");
    windowStrip.innerHTML = "";
    const perWindow = res.raw_metrics?.per_window_logits || [];
    const thresholdsUsed = res.raw_metrics?.thresholds_used || {};
    const lowThreshVal = typeof thresholdsUsed.low_threshold === "number" ? thresholdsUsed.low_threshold : -1.5;
    const highThreshVal = typeof thresholdsUsed.high_threshold === "number" ? thresholdsUsed.high_threshold : 1.5;

    if (perWindow.length === 0) {
      windowStrip.innerHTML = `<span style="font-size: 0.75rem; color: #64748b;">No window data available</span>`;
    } else {
      perWindow.forEach((w, idx) => {
        const pill = document.createElement("span");
        pill.className = "audio_forensics-win-pill";
        const logit = w.bona_fide_logit;
        const sTime = w.start_sec !== undefined ? w.start_sec.toFixed(1) : "?";
        const eTime = w.end_sec !== undefined ? w.end_sec.toFixed(1) : "?";

        // Check if non-speech (w.has_speech === false or logit is null)
        const isNonSpeech = w.has_speech === false || logit === null || logit === undefined;

        if (isNonSpeech) {
          pill.classList.add("audio_forensics-win-nospeech");
          pill.title = `Window ${idx+1} [${sTime}s - ${eTime}s]: Excluded (<50% speech)`;
          pill.textContent = `W${idx+1}: no speech`;
        } else if (logit <= lowThreshVal) {
          pill.classList.add("audio_forensics-win-low");
          pill.title = `Window ${idx+1} [${sTime}s - ${eTime}s]: ${logit.toFixed(2)} (Synthetic domain)`;
          pill.textContent = `W${idx+1}: ${logit >= 0 ? "+" : ""}${logit.toFixed(1)}`;
        } else if (logit >= highThreshVal) {
          pill.classList.add("audio_forensics-win-auth");
          pill.title = `Window ${idx+1} [${sTime}s - ${eTime}s]: ${logit.toFixed(2)} (Authentic domain)`;
          pill.textContent = `W${idx+1}: ${logit >= 0 ? "+" : ""}${logit.toFixed(1)}`;
        } else {
          pill.classList.add("audio_forensics-win-uncertain");
          pill.title = `Window ${idx+1} [${sTime}s - ${eTime}s]: ${logit.toFixed(2)} (Uncertain band)`;
          pill.textContent = `W${idx+1}: ${logit >= 0 ? "+" : ""}${logit.toFixed(1)}`;
        }

        pill.addEventListener("click", () => {
          if (w.start_sec !== undefined) {
            audioPlayer.currentTime = w.start_sec;
            audioPlayer.play();
          }
        });
        windowStrip.appendChild(pill);
      });
    }


    // Visual Artifacts
    const artMap = res.raw_metrics?.visual_artifacts || {};
    const imgWaveform = container.querySelector("#af-img-waveform");
    const imgSpectrogram = container.querySelector("#af-img-spectrogram");
    const imgTimeline = container.querySelector("#af-img-timeline");

    if (artMap.waveform) {
      imgWaveform.src = `/api/audio_forensics/artifacts/${artMap.waveform}`;
      imgWaveform.style.display = "block";
    } else {
      imgWaveform.style.display = "none";
    }

    if (artMap.spectrogram) {
      imgSpectrogram.src = `/api/audio_forensics/artifacts/${artMap.spectrogram}`;
      imgSpectrogram.style.display = "block";
    } else {
      imgSpectrogram.style.display = "none";
    }

    if (artMap.timeline) {
      imgTimeline.src = `/api/audio_forensics/artifacts/${artMap.timeline}`;
      imgTimeline.style.display = "block";
    } else {
      imgTimeline.style.display = "none";
    }

    // Forensic Findings List
    const findingsList = container.querySelector("#af-findings-list");
    findingsList.innerHTML = "";

    const findings = res.findings || [];
    if (findings.length === 0) {
      findingsList.innerHTML = `<div style="color: var(--audio_forensics-text-muted); font-size: 0.875rem;">No forensic anomalies or findings detected.</div>`;
    } else {
      findings.forEach(f => {
        const item = document.createElement("div");
        const sev = (f.severity || "info").toLowerCase();
        item.className = `audio_forensics-finding-item audio_forensics-finding-${sev}`;

        let locHtml = "";
        if (f.location && f.location.time_range_sec) {
          const [t0, t1] = f.location.time_range_sec;
          locHtml = `<span class="audio_forensics-seek-tag" style="margin-left: 0.5rem;" title="Click to seek audio">⏱ ${t0}s - ${t1}s</span>`;
        } else if (f.location && f.location.metadata_field) {
          locHtml = `<span style="font-size: 0.75rem; color: #94a3b8; margin-left: 0.5rem;">[tag: ${f.location.metadata_field}]</span>`;
        }

        item.innerHTML = `
          <div class="audio_forensics-finding-header">
            <span class="audio_forensics-check-name">${f.check || "Forensic Check"} ${locHtml}</span>
            <span class="audio_forensics-badge-pill audio_forensics-badge-${sev}">${sev} &bull; ${Math.round((f.confidence || 0) * 100)}%</span>
          </div>
          <p class="audio_forensics-finding-desc">${f.description || ""}</p>
        `;

        // Click to seek if time range exists
        if (f.location && f.location.time_range_sec) {
          const [t0] = f.location.time_range_sec;
          const seekBtn = item.querySelector(".audio_forensics-seek-tag");
          if (seekBtn) {
            seekBtn.addEventListener("click", () => {
              audioPlayer.currentTime = t0;
              audioPlayer.play();
            });
          }
        }

        findingsList.appendChild(item);
      });
    }
  }

  // Initial check of health & model status
  fetch("/api/audio_forensics/health")
    .then(r => r.json())
    .catch(() => {});
}

// Global exposure for standalone and embedded dashboard use
window.initModule = initModule;
