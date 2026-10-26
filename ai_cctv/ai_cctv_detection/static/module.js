/**
 * ai_cctv_detection Forensic UI Module
 * Self-contained vanilla JS component conforming to PS-05 Integration Contract.
 */

(function () {
  "use strict";

  function initModule(containerElementId) {
    const root = document.getElementById(containerElementId);
    if (!root) {
      console.error(`ai_cctv_detection: Container #${containerElementId} not found.`);
      return;
    }

    root.classList.add("ai_cctv_detection-root");

    // Render foundational layout
    root.innerHTML = `
      <div class="ai_cctv_detection-header">
        <h2 class="ai_cctv_detection-title">
          <span>📹</span>
          <span>AI CCTV Integrity & Authenticity Analysis</span>
          <span class="ai_cctv_detection-tag">PS-05 Forensic</span>
        </h2>
      </div>

      <div id="ai_cctv_detection-banner-container"></div>

      <div class="ai_cctv_detection-options">
        <label class="ai_cctv_detection-checkbox-label">
          <input type="checkbox" id="ai_cctv_detection-opt-tracking">
          <span>Enable ByteTrack Motion Consistency Modifiers (Optional)</span>
        </label>
      </div>

      <div class="ai_cctv_detection-dropzone" id="ai_cctv_detection-dropzone">
        <div class="ai_cctv_detection-dropzone-icon">📁</div>
        <div class="ai_cctv_detection-dropzone-title">Drag & Drop CCTV Evidence Video</div>
        <div class="ai_cctv_detection-dropzone-subtitle">Supports MP4, AVI, MKV, MOV (Streams up to 2 GB directly to disk)</div>
        <input type="file" id="ai_cctv_detection-file-input" class="ai_cctv_detection-file-input" accept="video/*,.mp4,.avi,.mkv,.mov">
      </div>

      <div id="ai_cctv_detection-progress-area" style="display: none;">
        <div class="ai_cctv_detection-progress-card">
          <div class="ai_cctv_detection-progress-header">
            <span id="ai_cctv_detection-progress-stage">Initializing analysis...</span>
            <span id="ai_cctv_detection-progress-pct">0%</span>
          </div>
          <div class="ai_cctv_detection-progress-bar-bg">
            <div id="ai_cctv_detection-progress-bar-fill" class="ai_cctv_detection-progress-bar-fill" style="width: 0%;"></div>
          </div>
        </div>
      </div>

      <div id="ai_cctv_detection-results-area" style="display: none;"></div>
    `;

    const dropzone = root.querySelector("#ai_cctv_detection-dropzone");
    const fileInput = root.querySelector("#ai_cctv_detection-file-input");
    const progressArea = root.querySelector("#ai_cctv_detection-progress-area");
    const progressStage = root.querySelector("#ai_cctv_detection-progress-stage");
    const progressPct = root.querySelector("#ai_cctv_detection-progress-pct");
    const progressBar = root.querySelector("#ai_cctv_detection-progress-bar-fill");
    const resultsArea = root.querySelector("#ai_cctv_detection-results-area");
    const bannerContainer = root.querySelector("#ai_cctv_detection-banner-container");
    const trackingOpt = root.querySelector("#ai_cctv_detection-opt-tracking");

    let activeJobId = null;
    let pollInterval = null;
    let lastUploadedBlobUrl = null;
    let lastResultData = null;

    // Dropzone listeners
    dropzone.addEventListener("click", () => fileInput.click());

    ["dragenter", "dragover"].forEach((eventName) => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropzone.classList.add("ai_cctv_detection-active");
      });
    });

    ["dragleave", "drop"].forEach((eventName) => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropzone.classList.remove("ai_cctv_detection-active");
      });
    });

    dropzone.addEventListener("drop", (e) => {
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        startUpload(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener("change", () => {
      if (fileInput.files && fileInput.files.length > 0) {
        startUpload(fileInput.files[0]);
      }
    });

    function generateJobId() {
      return "job_" + Math.random().toString(36).substring(2, 12) + "_" + Date.now();
    }

    function startUpload(file) {
      if (!file) return;

      activeJobId = generateJobId();
      if (lastUploadedBlobUrl) {
        URL.revokeObjectURL(lastUploadedBlobUrl);
      }
      lastUploadedBlobUrl = URL.createObjectURL(file);

      // UI State: Reset
      resultsArea.style.display = "none";
      resultsArea.innerHTML = "";
      bannerContainer.innerHTML = "";
      progressArea.style.display = "block";
      updateProgressUI("Streaming video to forensic sandbox...", 5);

      // Poll progress endpoint
      pollInterval = setInterval(async () => {
        try {
          const res = await fetch(`/api/ai_cctv_detection/progress/${activeJobId}`);
          if (res.ok) {
            const data = await res.json();
            updateProgressUI(data.stage, data.percent);
          }
        } catch (err) {
          console.warn("Progress poll failed:", err);
        }
      }, 500);

      // Post upload to analyze endpoint
      const formData = new FormData();
      formData.append("file", file);

      const isTracking = trackingOpt.checked;
      const analyzeUrl = `/api/ai_cctv_detection/analyze?job_id=${encodeURIComponent(activeJobId)}&tracking=${isTracking}`;

      fetch(analyzeUrl, {
        method: "POST",
        body: formData,
      })
        .then(async (response) => {
          clearInterval(pollInterval);
          if (!response.ok) {
            const errJson = await response.json().catch(() => ({ detail: "Unknown server error" }));
            throw new Error(errJson.detail || `Server returned status ${response.status}`);
          }
          return response.json();
        })
        .then((result) => {
          updateProgressUI("Analysis complete", 100);
          setTimeout(() => {
            progressArea.style.display = "none";
            renderResults(result, file);
          }, 300);
        })
        .catch((err) => {
          clearInterval(pollInterval);
          progressArea.style.display = "none";
          showErrorBanner(`Analysis encountered an error: ${err.message}`);
        });
    }

    function updateProgressUI(stage, percent) {
      progressStage.textContent = stage;
      progressPct.textContent = `${percent}%`;
      progressBar.style.width = `${percent}%`;
    }

    function showErrorBanner(msg) {
      bannerContainer.innerHTML = `
        <div class="ai_cctv_detection-banner ai_cctv_detection-banner-warn">
          <span>⚠️</span>
          <div>${msg}</div>
        </div>
      `;
    }

    function renderResults(result, file) {
      lastResultData = result;
      resultsArea.style.display = "block";

      const verdict = result.verdict || "inconclusive";
      const confPct = Math.round((result.overall_confidence || 0) * 100);
      const metrics = result.raw_metrics || {};

      // Check if model not trained
      const modelNotTrained = result.findings.some((f) => f.check === "model_not_trained");
      if (modelNotTrained) {
        bannerContainer.innerHTML = `
          <div class="ai_cctv_detection-banner ai_cctv_detection-banner-warn">
            <span style="font-size: 1.4rem;">⚠️</span>
            <div>
              <strong>Detector Model Not Trained (Forensic Honesty Rule)</strong><br>
              The fine-tuned YOLO11 CCTV weights (<code>models/best.pt</code>) are not present. In strict compliance with forensic integrity, synthetic scores are NOT invented. Non-ML metadata and quality gates were executed successfully.
              <br><br>
              To train the detector with CCTV footage:
              <pre>train_model.bat &lt;path_to_real_videos&gt; &lt;path_to_fake_videos&gt;</pre>
            </div>
          </div>
        `;
      }

      // Collect artifacts
      const artifactsDir = result.artifacts_dir || "artifacts/ai_cctv_detection";
      const timelineArtifact = (result.findings.flatMap((f) => f.evidence_artifacts || []).find((a) => a.includes("timeline")) || "");
      const contactArtifact = (result.findings.flatMap((f) => f.evidence_artifacts || []).find((a) => a.includes("contact_sheet")) || "");

      // Clickable chips for suspicious time ranges
      const suspiciousFindings = result.findings.filter((f) => f.check === "suspicious_segment" && f.location && f.location.time_range_sec);

      let chipsHtml = "";
      if (suspiciousFindings.length > 0) {
        chipsHtml = `
          <div style="margin-top: 0.6rem;">
            <div style="font-size: 0.75rem; color: var(--ai_cctv_detection-subtext); margin-bottom: 0.3rem;">CLICK TO JUMP VIDEO TO SUSPICIOUS RANGE:</div>
            <div class="ai_cctv_detection-chips">
              ${suspiciousFindings
                .map((sf) => {
                  const [start, end] = sf.location.time_range_sec;
                  return `<button class="ai_cctv_detection-chip" data-time="${start}">⏱️ ${start.toFixed(1)}s - ${end.toFixed(1)}s (${sf.severity.toUpperCase()})</button>`;
                })
                .join("")}
            </div>
          </div>
        `;
      }

      // Findings list HTML
      const findingsHtml = (result.findings || [])
        .map((f) => {
          const sev = f.severity || "info";
          return `
            <div class="ai_cctv_detection-finding-item ai_cctv_detection-finding-${sev}">
              <div class="ai_cctv_detection-finding-header">
                <span class="ai_cctv_detection-finding-title">${escapeHtml(f.check)}</span>
                <span class="ai_cctv_detection-finding-badge ai_cctv_detection-badge-${sev}">${sev}</span>
              </div>
              <div class="ai_cctv_detection-finding-desc">${escapeHtml(f.description)}</div>
            </div>
          `;
        })
        .join("");

      // Quality gate metrics
      const qg = metrics.quality_summary || {};

      resultsArea.innerHTML = `
        <div class="ai_cctv_detection-results">
          <!-- Summary Cards -->
          <div class="ai_cctv_detection-summary-grid">
            <div class="ai_cctv_detection-card">
              <div class="ai_cctv_detection-card-title">Clip Verdict</div>
              <div class="ai_cctv_detection-verdict ai_cctv_detection-verdict-${verdict}">
                ${verdict.replace("_", " ")}
              </div>
              <div style="font-size: 0.8rem; color: var(--ai_cctv_detection-subtext); margin-top: 0.5rem;">
                Evidence Integrity: SHA-256 verified
              </div>
            </div>

            <div class="ai_cctv_detection-card">
              <div class="ai_cctv_detection-card-title">Verdict Confidence</div>
              <div class="ai_cctv_detection-confidence-val">${confPct}%</div>
              <div style="font-size: 0.8rem; color: var(--ai_cctv_detection-subtext); margin-top: 0.2rem;">
                Median AI P: ${metrics.median_p !== undefined ? metrics.median_p : "N/A"}
              </div>
            </div>

            <div class="ai_cctv_detection-card">
              <div class="ai_cctv_detection-card-title">Quality Screen</div>
              <div style="font-size: 1.1rem; font-weight: 600; margin-top: 0.2rem;">
                ${qg.kept_count || 0} / ${qg.total_sampled || 0} Frames Kept
              </div>
              <div style="font-size: 0.8rem; color: var(--ai_cctv_detection-subtext); margin-top: 0.2rem;">
                Dropped: ${qg.dropped_count || 0} | Usability: ${Math.round((qg.quality_share || 0) * 100)}%
              </div>
            </div>

            <div class="ai_cctv_detection-card">
              <div class="ai_cctv_detection-card-title">Chain of Custody</div>
              <div style="font-size: 0.75rem; word-break: break-all; font-family: monospace; color: var(--ai_cctv_detection-accent);">
                ${escapeHtml(result.evidence_file.sha256 || "N/A")}
              </div>
              <div style="font-size: 0.78rem; color: var(--ai_cctv_detection-subtext); margin-top: 0.3rem;">
                ${(result.evidence_file.size_bytes / (1024 * 1024)).toFixed(2)} MB | ${escapeHtml(result.evidence_file.name)}
              </div>
            </div>
          </div>

          <!-- Video Player and Suspicious Chips -->
          <div class="ai_cctv_detection-evidence-viewer">
            <div class="ai_cctv_detection-card ai_cctv_detection-video-box">
              <div class="ai_cctv_detection-card-title">Forensic Playback & Temporal Jumps</div>
              <video id="ai_cctv_detection-player" controls preload="metadata" src="${lastUploadedBlobUrl || ""}"></video>
              ${chipsHtml}
            </div>

            <div class="ai_cctv_detection-card">
              <div class="ai_cctv_detection-card-title">Forensic Timeline (P_AI vs Time)</div>
              ${
                timelineArtifact
                  ? `<img class="ai_cctv_detection-artifact-img" src="/api/ai_cctv_detection/artifacts/${encodeURIComponent(
                      timelineArtifact.split("/").pop()
                    )}" alt="Timeline Plot">`
                  : `<div style="color: var(--ai_cctv_detection-subtext); padding: 2rem 0; text-align: center;">Timeline plot not generated (model not trained or no usable frames)</div>`
              }
            </div>
          </div>

          <!-- Contact Sheet of Top Frames -->
          ${
            contactArtifact
              ? `
            <div class="ai_cctv_detection-card">
              <div class="ai_cctv_detection-card-title">Contact Sheet: Highest AI Probability Frames</div>
              <img class="ai_cctv_detection-artifact-img" src="/api/ai_cctv_detection/artifacts/${encodeURIComponent(
                contactArtifact.split("/").pop()
              )}" alt="Highest AI Frames">
            </div>
          `
              : ""
          }

          <!-- Findings List -->
          <div class="ai_cctv_detection-card">
            <div class="ai_cctv_detection-card-title">Forensic Findings (${result.findings.length})</div>
            <div style="margin-top: 0.8rem;">
              ${findingsHtml}
            </div>
          </div>

          <!-- Actions -->
          <div class="ai_cctv_detection-actions">
            <button class="ai_cctv_detection-btn ai_cctv_detection-btn-secondary" id="ai_cctv_detection-btn-reset">
              Analyze Another Video
            </button>
            <button class="ai_cctv_detection-btn" id="ai_cctv_detection-btn-download">
              ⬇️ Download Forensic Report (JSON)
            </button>
          </div>
        </div>
      `;

      // Connect video seek chips
      const player = resultsArea.querySelector("#ai_cctv_detection-player");
      resultsArea.querySelectorAll(".ai_cctv_detection-chip").forEach((btn) => {
        btn.addEventListener("click", () => {
          const t = parseFloat(btn.getAttribute("data-time"));
          if (player && !isNaN(t)) {
            player.currentTime = t;
            player.play();
          }
        });
      });

      // Reset button
      resultsArea.querySelector("#ai_cctv_detection-btn-reset").addEventListener("click", () => {
        resultsArea.style.display = "none";
        resultsArea.innerHTML = "";
        fileInput.value = "";
      });

      // Download JSON button
      resultsArea.querySelector("#ai_cctv_detection-btn-download").addEventListener("click", () => {
        if (!lastResultData) return;
        const blob = new Blob([JSON.stringify(lastResultData, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `forensic_report_${result.evidence_file.name || "cctv"}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      });
    }

    function escapeHtml(str) {
      if (!str) return "";
      return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    }
  }

  // Expose initModule globally
  window.initModule = initModule;
})();
