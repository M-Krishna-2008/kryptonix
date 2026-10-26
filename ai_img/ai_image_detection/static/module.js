/**
 * ai_image_detection Frontend Controller
 * Exposes initModule(containerElementId)
 * Zero CDN dependencies, uses pure Vanilla JS & relative API endpoints.
 */

(function (root, factory) {
  if (typeof define === "function" && define.amd) {
    define([], factory);
  } else if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.initModule = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {

  return function initModule(containerElementId) {
    const container = document.getElementById(containerElementId);
    if (!container) {
      console.error(`[ai_image_detection] Container element #${containerElementId} not found.`);
      return;
    }

    let currentAnalysisResult = null;

    // Render component markup inside container
    container.innerHTML = `
      <div class="ai_image_detection-root">
        <!-- Header -->
        <header class="ai_image_detection-header">
          <div class="ai_image_detection-title-group">
            <h2>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <circle cx="8.5" cy="8.5" r="1.5"></circle>
                <polyline points="21 15 16 10 5 21"></polyline>
              </svg>
              AI Image Detection
            </h2>
            <p class="ai_image_detection-subtitle">Universal Fake Detect (UnivFD) CLIP ViT-L/14 Forensic Analyzer</p>
          </div>
          <span class="ai_image_detection-badge-spec">PS-05 Local Forensic</span>
        </header>

        <!-- Upload Dropzone -->
        <div class="ai_image_detection-upload-area" id="aid-upload-zone">
          <svg class="ai_image_detection-upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="17 8 12 3 7 8"></polyline>
            <line x1="12" y1="3" x2="12" y2="15"></line>
          </svg>
          <div class="ai_image_detection-upload-text">Drag & drop evidence image, or click to browse</div>
          <div class="ai_image_detection-upload-subtext">Supports JPEG, PNG, WebP, HEIC (Max 50MB, processed 100% locally)</div>
          <input type="file" id="aid-file-input" class="ai_image_detection-file-input" accept="image/*" />
        </div>

        <!-- Scanning / Loading State -->
        <div class="ai_image_detection-loading-state" id="aid-loading-indicator">
          <div class="ai_image_detection-spinner"></div>
          <div class="ai_image_detection-loading-text">Analyzing Evidence Integrity...</div>
          <div class="ai_image_detection-loading-stage" id="aid-loading-stage">Extracting 3x3 multi-crop high-frequency CLIP features</div>
        </div>

        <!-- Results View -->
        <div class="ai_image_detection-results-container" id="aid-results-panel">
          
          <!-- Inconclusive Alert Banner -->
          <div class="ai_image_detection-warning-banner" id="aid-warning-banner">
            <div class="ai_image_detection-warning-title">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                <line x1="12" y1="9" x2="12" y2="13"></line>
                <line x1="12" y1="17" x2="12.01" y2="17"></line>
              </svg>
              Inconclusive Forensic Threshold
            </div>
            <span>This image yielded ambiguous or insufficient quality indicators. It is strongly advised to cross-examine this file using the other PS-05 forensic modules: Error Level Analysis (ELA), EXIF Metadata Consistency, and PRNU Sensor Noise Analysis.</span>
          </div>

          <!-- Top Verdict Card -->
          <div class="ai_image_detection-verdict-card">
            <div class="ai_image_detection-verdict-badge" id="aid-verdict-badge">AUTHENTIC</div>
            
            <div class="ai_image_detection-verdict-details">
              <h3 id="aid-verdict-heading">Authentic Camera Capture</h3>
              <div class="ai_image_detection-meta-chips" id="aid-meta-chips"></div>
            </div>

            <div class="ai_image_detection-gauge-container">
              <div class="ai_image_detection-gauge-label">
                <span>Fake Probability</span>
                <span class="ai_image_detection-gauge-value" id="aid-gauge-val">0.0%</span>
              </div>
              <div class="ai_image_detection-gauge-track">
                <div class="ai_image_detection-gauge-fill" id="aid-gauge-fill" style="width: 0%;"></div>
              </div>
              <div class="ai_image_detection-gauge-zones">
                <span>Real (&le;20%)</span>
                <span>Uncertain</span>
                <span>Fake (&ge;80%)</span>
              </div>
            </div>
          </div>

          <!-- Main Layout: Evidence Artifacts + Findings List -->
          <div class="ai_image_detection-content-layout">
            
            <!-- Left: Crop Heatmap Artifact -->
            <div class="ai_image_detection-panel">
              <div class="ai_image_detection-panel-title">
                <span>Multi-Crop Forensic Heatmap</span>
                <span id="aid-crop-count-label" style="font-size: 0.75rem; color: var(--aid-text-muted);">9 crops</span>
              </div>
              
              <div class="ai_image_detection-heatmap-wrapper">
                <img id="aid-heatmap-img" class="ai_image_detection-heatmap-img" alt="Forensic Heatmap" />
              </div>

              <div class="ai_image_detection-heatmap-legend">
                <div class="ai_image_detection-legend-item">
                  <div class="ai_image_detection-legend-box" style="background: rgba(16, 185, 129, 0.8);"></div>
                  <span>Real Texture</span>
                </div>
                <div class="ai_image_detection-legend-item">
                  <div class="ai_image_detection-legend-box" style="background: rgba(245, 158, 11, 0.8);"></div>
                  <span>Uncertain</span>
                </div>
                <div class="ai_image_detection-legend-item">
                  <div class="ai_image_detection-legend-box" style="background: rgba(239, 68, 68, 0.8);"></div>
                  <span>Synthetic Artifacts</span>
                </div>
              </div>
            </div>

            <!-- Right: Granular Findings -->
            <div class="ai_image_detection-panel">
              <div class="ai_image_detection-panel-title">
                <span>Forensic Findings</span>
                <span id="aid-findings-count" style="font-size: 0.75rem; color: var(--aid-text-muted);">0 checks</span>
              </div>
              <div class="ai_image_detection-findings-list" id="aid-findings-container"></div>
            </div>

          </div>

          <!-- Bottom Action Bar -->
          <div class="ai_image_detection-action-bar">
            <div>
              <button type="button" class="ai_image_detection-raw-toggle" id="aid-toggle-raw">
                Inspect Raw Forensic Metrics (JSON)
              </button>
            </div>
            <div style="display: flex; gap: 0.75rem;">
              <button type="button" class="ai_image_detection-btn ai_image_detection-btn-secondary" id="aid-btn-reset">
                Analyze Another Image
              </button>
              <button type="button" class="ai_image_detection-btn" id="aid-btn-download">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="7 10 12 15 17 10"></polyline>
                  <line x1="12" y1="15" x2="12" y2="3"></line>
                </svg>
                Download JSON Report
              </button>
            </div>
          </div>

          <pre class="ai_image_detection-raw-json" id="aid-raw-json-block"></pre>

        </div>
      </div>
    `;

    // DOM References
    const uploadZone = container.querySelector("#aid-upload-zone");
    const fileInput = container.querySelector("#aid-file-input");
    const loadingIndicator = container.querySelector("#aid-loading-indicator");
    const resultsPanel = container.querySelector("#aid-results-panel");
    const warningBanner = container.querySelector("#aid-warning-banner");
    const verdictBadge = container.querySelector("#aid-verdict-badge");
    const verdictHeading = container.querySelector("#aid-verdict-heading");
    const metaChips = container.querySelector("#aid-meta-chips");
    const gaugeVal = container.querySelector("#aid-gauge-val");
    const gaugeFill = container.querySelector("#aid-gauge-fill");
    const heatmapImg = container.querySelector("#aid-heatmap-img");
    const cropCountLabel = container.querySelector("#aid-crop-count-label");
    const findingsContainer = container.querySelector("#aid-findings-container");
    const findingsCount = container.querySelector("#aid-findings-count");
    const toggleRawBtn = container.querySelector("#aid-toggle-raw");
    const rawJsonBlock = container.querySelector("#aid-raw-json-block");
    const btnReset = container.querySelector("#aid-btn-reset");
    const btnDownload = container.querySelector("#aid-btn-download");

    // Event Listeners for Upload Area
    uploadZone.addEventListener("click", () => fileInput.click());

    ["dragenter", "dragover"].forEach(eventName => {
      uploadZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadZone.classList.add("is-dragover");
      });
    });

    ["dragleave", "drop"].forEach(eventName => {
      uploadZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadZone.classList.remove("is-dragover");
      });
    });

    uploadZone.addEventListener("drop", (e) => {
      const files = e.dataTransfer.files;
      if (files && files.length > 0) {
        handleFileUpload(files[0]);
      }
    });

    fileInput.addEventListener("change", (e) => {
      if (fileInput.files && fileInput.files.length > 0) {
        handleFileUpload(fileInput.files[0]);
      }
    });

    btnReset.addEventListener("click", () => {
      currentAnalysisResult = null;
      resultsPanel.style.display = "none";
      uploadZone.style.display = "block";
      fileInput.value = "";
    });

    toggleRawBtn.addEventListener("click", () => {
      if (rawJsonBlock.style.display === "block") {
        rawJsonBlock.style.display = "none";
        toggleRawBtn.textContent = "Inspect Raw Forensic Metrics (JSON)";
      } else {
        rawJsonBlock.style.display = "block";
        toggleRawBtn.textContent = "Hide Raw Forensic Metrics (JSON)";
      }
    });

    btnDownload.addEventListener("click", () => {
      if (!currentAnalysisResult) return;
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(currentAnalysisResult, null, 2));
      const downloadAnchor = document.createElement("a");
      const sha = currentAnalysisResult.evidence_file?.sha256?.substring(0, 8) || "report";
      downloadAnchor.setAttribute("href", dataStr);
      downloadAnchor.setAttribute("download", `ai_image_detection_${sha}.json`);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
    });

    // Upload Handler via relative API
    async function handleFileUpload(file) {
      uploadZone.style.display = "none";
      loadingIndicator.style.display = "block";
      resultsPanel.style.display = "none";

      const formData = new FormData();
      formData.append("file", file);

      try {
        const response = await fetch("/api/ai_image_detection/analyze", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          throw new Error(`Server returned HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        currentAnalysisResult = data;
        renderResults(data);
      } catch (err) {
        alert("Forensic Analysis Error: " + err.message);
        uploadZone.style.display = "block";
      } finally {
        loadingIndicator.style.display = "none";
      }
    }

    // Render Results Logic
    function renderResults(data) {
      resultsPanel.style.display = "block";

      const verdict = data.verdict || "inconclusive";
      const conf = Math.round((data.overall_confidence || 0) * 100);
      const metrics = data.raw_metrics || {};
      const fakeProb = metrics.calibrated_probability !== undefined 
        ? Math.round(metrics.calibrated_probability * 1000) / 10 
        : 50.0;

      // Verdict Badge
      verdictBadge.className = `ai_image_detection-verdict-badge verdict-${verdict}`;
      verdictBadge.textContent = verdict.replace("_", " ");

      // Verdict Heading
      const headings = {
        authentic: "Camera-Captured Authentic Image",
        likely_tampered: "AI-Generated / Synthesized Image Detected",
        suspicious: "Suspicious Artifacts (Potential Manipulation)",
        inconclusive: "Inconclusive / Insufficient Evidence"
      };
      verdictHeading.textContent = headings[verdict] || "Analysis Complete";

      // Inconclusive Banner
      if (verdict === "inconclusive" || verdict === "suspicious") {
        warningBanner.style.display = "block";
      } else {
        warningBanner.style.display = "none";
      }

      // Meta Chips
      metaChips.innerHTML = "";
      const chips = [
        { label: "Type", val: (metrics.photo_type || "unknown").replace("_", " "), accent: true },
        { label: "SHA-256", val: (data.evidence_file?.sha256 || "").substring(0, 10) + "..." },
        { label: "File Size", val: formatBytes(data.evidence_file?.size_bytes || 0) },
        { label: "Inference", val: (metrics.inference_ms || 0) + "ms" },
      ];
      if (metrics.jpeg_quality_estimate) {
        chips.push({ label: "JPEG Quality", val: metrics.jpeg_quality_estimate + "/100" });
      }
      chips.forEach(c => {
        const span = document.createElement("span");
        span.className = `ai_image_detection-chip ${c.accent ? "ai_image_detection-chip-accent" : ""}`;
        span.innerHTML = `<strong>${c.label}:</strong> ${c.val}`;
        metaChips.appendChild(span);
      });

      // Gauge
      gaugeVal.textContent = `${fakeProb}%`;
      gaugeFill.style.width = `${Math.min(100, Math.max(0, fakeProb))}%`;

      // Heatmap Artifact
      let artifactRel = null;
      if (data.findings && data.findings.length > 0) {
        for (const f of data.findings) {
          if (f.evidence_artifacts && f.evidence_artifacts.length > 0) {
            artifactRel = f.evidence_artifacts[0];
            break;
          }
        }
      }

      if (artifactRel) {
        // Strip prefix if needed
        const cleanName = artifactRel.split("/").pop();
        heatmapImg.src = `/api/ai_image_detection/artifacts/${cleanName}`;
        heatmapImg.style.display = "block";
      } else {
        heatmapImg.style.display = "none";
      }

      cropCountLabel.textContent = `${metrics.num_crops || 1} crops sampled`;

      // Findings List
      findingsContainer.innerHTML = "";
      const findings = data.findings || [];
      findingsCount.textContent = `${findings.length} findings`;

      findings.forEach(f => {
        const item = document.createElement("div");
        item.className = `ai_image_detection-finding-item sev-${f.severity || "info"}`;
        
        item.innerHTML = `
          <div class="ai_image_detection-finding-head">
            <span class="ai_image_detection-check-name">${formatCheckName(f.check)}</span>
            <span class="ai_image_detection-sev-pill sev-${f.severity}">${f.severity}</span>
          </div>
          <p class="ai_image_detection-finding-desc">${escapeHtml(f.description)}</p>
        `;
        findingsContainer.appendChild(item);
      });

      // Raw JSON
      rawJsonBlock.textContent = JSON.stringify(data, null, 2);
    }

    function formatBytes(bytes) {
      if (!bytes) return "0 B";
      const k = 1024;
      const sizes = ["B", "KB", "MB", "GB"];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
    }

    function formatCheckName(check) {
      if (!check) return "Check";
      return check.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    }

    function escapeHtml(text) {
      if (!text) return "";
      const div = document.createElement("div");
      div.textContent = text;
      return div.innerHTML;
    }
  };
});
