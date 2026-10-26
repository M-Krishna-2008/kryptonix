/**
 * Forensic Image Forgery Module Frontend
 * Single Deep Engine (TruFor) + Classical Forensic Checks.
 * Exposes a single entry point: initModule(containerElementId)
 * Strictly zero CDN dependencies, safe DOM textContent operations against XSS.
 */

function initModule(containerElementId) {
  const container = document.getElementById(containerElementId);
  if (!container) {
    console.error("Image Forgery module container not found:", containerElementId);
    return;
  }

  container.innerHTML = "";

  let selectedFile = null;
  let analysisResult = null;
  let timerInterval = null;
  let startTime = 0;
  let enginesStatus = {};
  let currentLayer = "annotated";
  let currentOpacity = 0.6;
  let selectedFindingId = null;

  const wrapper = document.createElement("div");
  wrapper.className = "image_forgery-wrapper";
  container.appendChild(wrapper);

  // Header
  const header = document.createElement("div");
  header.className = "image_forgery-header";
  const title = document.createElement("h2");
  title.className = "image_forgery-title";
  title.textContent = "Image Forgery & Tamper Localization";
  const badge = document.createElement("span");
  badge.className = "image_forgery-badge-pill";
  badge.textContent = "PS-05 Digital Evidence";
  title.appendChild(badge);

  const subtitle = document.createElement("p");
  subtitle.className = "image_forgery-subtitle";
  subtitle.textContent = "Offline forensic analysis: TruFor transformer + Metadata, Quantization, ELA, SIFT copy-move";
  header.appendChild(title);
  header.appendChild(subtitle);
  wrapper.appendChild(header);

  // Upload Card
  const uploadCard = document.createElement("div");
  uploadCard.className = "image_forgery-card";

  const dropzone = document.createElement("div");
  dropzone.className = "image_forgery-dropzone";
  dropzone.setAttribute("tabindex", "0");
  dropzone.setAttribute("role", "button");
  dropzone.setAttribute("aria-label", "Upload evidence image file");

  const dropIcon = document.createElement("span");
  dropIcon.className = "image_forgery-dropzone-icon";
  dropIcon.textContent = "🔍";

  const dropTitle = document.createElement("div");
  dropTitle.className = "image_forgery-dropzone-title";
  dropTitle.textContent = "Drag & Drop Evidence Image, or Click to Browse";

  const dropHint = document.createElement("div");
  dropHint.className = "image_forgery-dropzone-hint";
  dropHint.textContent = "Supported formats: JPEG, PNG, TIFF, WEBP, BMP (Max 50 MB)";

  dropzone.appendChild(dropIcon);
  dropzone.appendChild(dropTitle);
  dropzone.appendChild(dropHint);

  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.accept = "image/jpeg,image/png,image/tiff,image/webp,image/bmp,.jpg,.jpeg,.png,.tif,.tiff,.webp,.bmp";
  fileInput.style.display = "none";
  dropzone.appendChild(fileInput);

  const filePreview = document.createElement("div");
  filePreview.className = "image_forgery-file-preview";
  filePreview.style.display = "none";

  const fileNameSpan = document.createElement("span");
  fileNameSpan.style.fontWeight = "600";
  const fileSizeSpan = document.createElement("span");
  fileSizeSpan.style.color = "var(--text-muted)";
  filePreview.appendChild(fileNameSpan);
  filePreview.appendChild(fileSizeSpan);

  const optionsTitle = document.createElement("div");
  optionsTitle.style.fontWeight = "600";
  optionsTitle.style.marginTop = "1rem";
  optionsTitle.textContent = "Forensic Engines & Checks";

  const enginesGrid = document.createElement("div");
  enginesGrid.className = "image_forgery-options-grid";

  uploadCard.appendChild(dropzone);
  uploadCard.appendChild(filePreview);
  uploadCard.appendChild(optionsTitle);
  uploadCard.appendChild(enginesGrid);

  const btnRow = document.createElement("div");
  btnRow.style.marginTop = "1.25rem";
  btnRow.style.display = "flex";
  btnRow.style.gap = "0.75rem";

  const analyzeBtn = document.createElement("button");
  analyzeBtn.className = "image_forgery-button";
  analyzeBtn.textContent = "Run Forensic Analysis";
  analyzeBtn.disabled = true;

  btnRow.appendChild(analyzeBtn);
  uploadCard.appendChild(btnRow);
  wrapper.appendChild(uploadCard);

  // Progress Card
  const progressCard = document.createElement("div");
  progressCard.className = "image_forgery-card";
  progressCard.style.display = "none";

  const progressBarContainer = document.createElement("div");
  progressBarContainer.className = "image_forgery-progress-bar-container";
  const progressBar = document.createElement("div");
  progressBar.className = "image_forgery-progress-bar-indeterminate";
  progressBarContainer.appendChild(progressBar);

  const progressStatus = document.createElement("div");
  progressStatus.className = "image_forgery-progress-text";
  const progressMsg = document.createElement("span");
  progressMsg.textContent = "Running forensic engines - this can take a minute on a laptop GPU...";
  const progressTimer = document.createElement("span");
  progressTimer.textContent = "Elapsed: 0s";
  progressStatus.appendChild(progressMsg);
  progressStatus.appendChild(progressTimer);

  progressCard.appendChild(progressBarContainer);
  progressCard.appendChild(progressStatus);
  wrapper.appendChild(progressCard);

  // Results Section
  const resultsContainer = document.createElement("div");
  resultsContainer.className = "image_forgery-results";
  resultsContainer.style.display = "none";
  wrapper.appendChild(resultsContainer);

  fetch("/api/image_forgery/engines")
    .then((r) => r.json())
    .then((data) => {
      enginesStatus = data;
      renderEngineCheckboxes();
    })
    .catch((err) => {
      console.warn("Could not fetch engine statuses:", err);
      renderEngineCheckboxes();
    });

  function renderEngineCheckboxes() {
    enginesGrid.innerHTML = "";
    const engineConfigs = [
      { id: "trufor", label: "TruFor (Deep Cross-Modal Transformer)", defaultChecked: true },
      { id: "metadata", label: "Metadata & Provenance Forensics", defaultChecked: true },
      { id: "ela", label: "Error Level Analysis (ELA)", defaultChecked: true },
      { id: "copy_move", label: "Copy-Move Keypoint Matching (SIFT/ORB)", defaultChecked: false }
    ];

    engineConfigs.forEach((cfg) => {
      const item = document.createElement("label");
      item.className = "image_forgery-engine-item";

      const chk = document.createElement("input");
      chk.type = "checkbox";
      chk.value = cfg.id;
      chk.name = "engines";

      const statusInfo = enginesStatus[cfg.id];
      const isAvail = statusInfo ? statusInfo.available : true;
      chk.checked = isAvail && cfg.defaultChecked;

      if (!isAvail) {
        chk.disabled = true;
        item.classList.add("disabled");
      }

      const textWrap = document.createElement("div");
      const titleSpan = document.createElement("span");
      titleSpan.textContent = cfg.label;
      textWrap.appendChild(titleSpan);

      if (statusInfo && statusInfo.reason) {
        const hint = document.createElement("span");
        hint.className = "image_forgery-engine-tooltip";
        hint.textContent = isAvail ? "Ready" : statusInfo.reason;
        textWrap.appendChild(hint);
      }

      item.appendChild(chk);
      item.appendChild(textWrap);
      enginesGrid.appendChild(item);
    });
  }

  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") fileInput.click();
  });

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("image_forgery-dragover");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("image_forgery-dragover");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("image_forgery-dragover");
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  });

  function handleFileSelected(file) {
    selectedFile = file;
    fileNameSpan.textContent = file.name;
    const mb = (file.size / (1024 * 1024)).toFixed(2);
    fileSizeSpan.textContent = `${mb} MB`;
    filePreview.style.display = "flex";
    analyzeBtn.disabled = false;
  }

  analyzeBtn.addEventListener("click", () => {
    if (!selectedFile) return;

    const checkedEngines = [];
    const chks = enginesGrid.querySelectorAll("input[type=checkbox]:checked");
    chks.forEach((c) => checkedEngines.push(c.value));

    const options = {
      engines: checkedEngines,
      mask_threshold: 0.5,
      max_side: 1024,
      ela_quality: 90,
      min_region_area_frac: 0.005
    };

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("options", JSON.stringify(options));

    uploadCard.style.display = "none";
    progressCard.style.display = "block";
    resultsContainer.style.display = "none";

    startTime = Date.now();
    timerInterval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTime) / 1000);
      progressTimer.textContent = `Elapsed: ${elapsed}s`;
    }, 1000);

    fetch("/api/image_forgery/analyze", {
      method: "POST",
      body: formData
    })
      .then(async (response) => {
        clearInterval(timerInterval);
        progressCard.style.display = "none";

        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          throw new Error(errData.detail || `Server error: ${response.status}`);
        }
        return response.json();
      })
      .then((data) => {
        analysisResult = data;
        renderResults(data);
      })
      .catch((err) => {
        clearInterval(timerInterval);
        progressCard.style.display = "none";
        uploadCard.style.display = "block";
        alert(`Analysis Error: ${err.message}`);
      });
  });

  function renderResults(data) {
    resultsContainer.innerHTML = "";
    resultsContainer.style.display = "block";

    const disclaimer = document.createElement("div");
    disclaimer.className = "image_forgery-disclaimer";
    disclaimer.setAttribute("role", "note");
    disclaimer.textContent = "Notice: These results are decision-support indicators, not definitive legal proof of manipulation or authenticity.";
    resultsContainer.appendChild(disclaimer);

    const summaryGrid = document.createElement("div");
    summaryGrid.className = "image_forgery-summary-grid";

    // Verdict Box
    const verdictBox = document.createElement("div");
    verdictBox.className = "image_forgery-verdict-box";

    const vBadge = document.createElement("div");
    vBadge.className = `image_forgery-verdict-badge image_forgery-verdict-${data.verdict}`;
    vBadge.setAttribute("aria-label", `Verdict: ${data.verdict}`);

    const vIcon = document.createElement("span");
    let plainVerdict = "Inconclusive";
    if (data.verdict === "likely_tampered") {
      vIcon.textContent = "⚠️";
      plainVerdict = "Likely Manipulated";
    } else if (data.verdict === "suspicious") {
      vIcon.textContent = "⚡";
      plainVerdict = "Suspicious";
    } else if (data.verdict === "authentic") {
      vIcon.textContent = "✅";
      plainVerdict = "Likely Authentic";
    } else {
      vIcon.textContent = "❓";
      plainVerdict = "Inconclusive";
    }

    const vText = document.createElement("span");
    vText.textContent = plainVerdict;
    vBadge.appendChild(vIcon);
    vBadge.appendChild(vText);

    verdictBox.appendChild(vBadge);

    // Explicit TruFor score display
    const confBreakdown = data.confidence_breakdown || (data.raw_metrics && data.raw_metrics.confidence_breakdown);
    if (confBreakdown && confBreakdown.trufor_global_score !== undefined && confBreakdown.trufor_global_score !== null) {
      const scoreDiv = document.createElement("div");
      scoreDiv.style.marginTop = "0.5rem";
      scoreDiv.style.fontSize = "0.875rem";
      scoreDiv.style.fontWeight = "500";
      scoreDiv.style.color = "#94a3b8";
      const scoreVal = confBreakdown.trufor_global_score;
      scoreDiv.textContent = `TruFor Anomaly Score: ${(scoreVal * 100).toFixed(1)}% (${scoreVal.toFixed(3)})`;
      verdictBox.appendChild(scoreDiv);
    }

    const confMeter = document.createElement("div");
    confMeter.className = "image_forgery-conf-meter";
    const confVal = document.createElement("div");
    confVal.className = "image_forgery-conf-val";
    confVal.textContent = `${Math.round(data.overall_confidence * 100)}% Confidence`;

    const confBar = document.createElement("div");
    confBar.className = "image_forgery-conf-bar";
    const confFill = document.createElement("div");
    confFill.className = "image_forgery-conf-fill";
    confFill.style.width = `${Math.round(data.overall_confidence * 100)}%`;
    confBar.appendChild(confFill);

    confMeter.appendChild(confVal);
    confMeter.appendChild(confBar);

    verdictBox.appendChild(confMeter);
    summaryGrid.appendChild(verdictBox);

    // Chain of Custody
    const chainBox = document.createElement("div");
    chainBox.className = "image_forgery-chain-info";

    const rows = [
      { label: "File Name", val: data.evidence_file.name },
      { label: "SHA-256", val: data.evidence_file.sha256 },
      { label: "Size", val: `${(data.evidence_file.size_bytes / 1024).toFixed(1)} KB (${data.evidence_file.type})` },
      { label: "Timestamp", val: data.analyzed_at }
    ];

    rows.forEach((r) => {
      const rDiv = document.createElement("div");
      rDiv.className = "image_forgery-chain-row";
      const lbl = document.createElement("span");
      lbl.className = "image_forgery-chain-label";
      lbl.textContent = r.label;
      const val = document.createElement("span");
      val.textContent = r.val;
      rDiv.appendChild(lbl);
      rDiv.appendChild(val);
      chainBox.appendChild(rDiv);
    });

    summaryGrid.appendChild(chainBox);
    resultsContainer.appendChild(summaryGrid);

    renderViewer(resultsContainer, data);
    renderFindings(resultsContainer, data);

    // Actions
    const actionRow = document.createElement("div");
    actionRow.className = "image_forgery-actions-bar";

    const leftActions = document.createElement("div");
    leftActions.style.display = "flex";
    leftActions.style.gap = "0.75rem";

    const downloadBtn = document.createElement("button");
    downloadBtn.className = "image_forgery-button";
    downloadBtn.textContent = "Download JSON Result";
    downloadBtn.addEventListener("click", () => {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `forgery_report_${data.evidence_file.sha256.substring(0, 8)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    });

    const copyShaBtn = document.createElement("button");
    copyShaBtn.className = "image_forgery-button image_forgery-button-secondary";
    copyShaBtn.textContent = "Copy SHA-256";
    copyShaBtn.addEventListener("click", () => {
      navigator.clipboard.writeText(data.evidence_file.sha256).then(() => {
        copyShaBtn.textContent = "SHA-256 Copied!";
        setTimeout(() => (copyShaBtn.textContent = "Copy SHA-256"), 2000);
      });
    });

    leftActions.appendChild(downloadBtn);
    leftActions.appendChild(copyShaBtn);

    const newBtn = document.createElement("button");
    newBtn.className = "image_forgery-button image_forgery-button-secondary";
    newBtn.textContent = "Analyze Another Image";
    newBtn.addEventListener("click", () => {
      selectedFile = null;
      filePreview.style.display = "none";
      analyzeBtn.disabled = true;
      resultsContainer.style.display = "none";
      uploadCard.style.display = "block";
    });

    actionRow.appendChild(leftActions);
    actionRow.appendChild(newBtn);
    resultsContainer.appendChild(actionRow);
  }

  function renderViewer(parent, data) {
    const viewerCard = document.createElement("div");
    viewerCard.className = "image_forgery-viewer-container";

    const toolbar = document.createElement("div");
    toolbar.className = "image_forgery-viewer-toolbar";

    const layerBtns = document.createElement("div");
    layerBtns.className = "image_forgery-layer-buttons";

    const hashDir = data.evidence_file.sha256.substring(0, 12);
    const layers = [
      { id: "annotated", label: "Annotated Boxes", url: `/api/image_forgery/artifacts/${hashDir}/annotated.png` },
      { id: "original", label: "Original Only", url: null },
      { id: "trufor_overlay", label: "TruFor Overlay", url: `/api/image_forgery/artifacts/${hashDir}/trufor_overlay.png` },
      { id: "trufor_map", label: "TruFor Heatmap", url: `/api/image_forgery/artifacts/${hashDir}/trufor_map.png` },
      { id: "trufor_conf", label: "TruFor Confidence", url: `/api/image_forgery/artifacts/${hashDir}/trufor_confidence.png` },
      { id: "ela", label: "ELA Heatmap", url: `/api/image_forgery/artifacts/${hashDir}/ela.png` },
      { id: "copymove", label: "Copy-Move Matches", url: `/api/image_forgery/artifacts/${hashDir}/copy_move.png` }
    ];

    layers.forEach((lyr) => {
      const btn = document.createElement("button");
      btn.className = "image_forgery-layer-btn";
      if (lyr.id === currentLayer) btn.classList.add("active");
      btn.textContent = lyr.label;
      btn.addEventListener("click", () => {
        layerBtns.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        currentLayer = lyr.id;
        updateStageView(lyr.url);
      });
      layerBtns.appendChild(btn);
    });

    const controls = document.createElement("div");
    controls.className = "image_forgery-viewer-controls";

    const opLabel = document.createElement("label");
    opLabel.textContent = "Opacity: ";
    const opSlider = document.createElement("input");
    opSlider.type = "range";
    opSlider.min = "0";
    opSlider.max = "1";
    opSlider.step = "0.05";
    opSlider.value = String(currentOpacity);

    opSlider.addEventListener("input", (e) => {
      currentOpacity = parseFloat(e.target.value);
      if (overlayImg) overlayImg.style.opacity = currentOpacity;
    });

    controls.appendChild(opLabel);
    controls.appendChild(opSlider);

    toolbar.appendChild(layerBtns);
    toolbar.appendChild(controls);
    viewerCard.appendChild(toolbar);

    const stage = document.createElement("div");
    stage.className = "image_forgery-canvas-stage";

    const baseImg = document.createElement("img");
    baseImg.className = "image_forgery-stage-img-base";
    baseImg.alt = "Evidence preview";
    if (selectedFile) baseImg.src = URL.createObjectURL(selectedFile);

    const overlayImg = document.createElement("img");
    overlayImg.className = "image_forgery-stage-img-overlay";
    overlayImg.style.opacity = currentOpacity;
    overlayImg.alt = "Forensic overlay";

    const svgOverlay = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svgOverlay.setAttribute("class", "image_forgery-stage-svg");

    stage.appendChild(baseImg);
    stage.appendChild(overlayImg);
    stage.appendChild(svgOverlay);
    viewerCard.appendChild(stage);
    parent.appendChild(viewerCard);

    function updateStageView(overlayUrl) {
      if (!overlayUrl || currentLayer === "original") {
        overlayImg.style.display = "none";
        svgOverlay.style.display = "none";
      } else if (currentLayer === "annotated") {
        overlayImg.src = overlayUrl;
        overlayImg.style.display = "block";
        svgOverlay.style.display = "block";
        drawSvgBoxes();
      } else {
        overlayImg.src = overlayUrl;
        overlayImg.style.display = "block";
        svgOverlay.style.display = "none";
      }
    }

    function drawSvgBoxes() {
      svgOverlay.innerHTML = "";
      if (!baseImg.naturalWidth || !baseImg.naturalHeight) return;

      const scaleX = baseImg.clientWidth / baseImg.naturalWidth;
      const scaleY = baseImg.clientHeight / baseImg.naturalHeight;

      svgOverlay.setAttribute("viewBox", `0 0 ${baseImg.clientWidth} ${baseImg.clientHeight}`);

      data.findings.forEach((f) => {
        if (f.location && f.location.region) {
          const [rx, ry, rw, rh] = f.location.region;
          const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
          rect.setAttribute("x", rx * scaleX);
          rect.setAttribute("y", ry * scaleY);
          rect.setAttribute("width", rw * scaleX);
          rect.setAttribute("height", rh * scaleY);
          rect.setAttribute("class", "image_forgery-svg-box");
          rect.setAttribute("data-finding-id", f.id);

          if (selectedFindingId === f.id) rect.classList.add("active");

          rect.addEventListener("click", () => {
            highlightFinding(f.id);
          });

          svgOverlay.appendChild(rect);
        }
      });
    }

    baseImg.onload = () => {
      updateStageView(layers[0].url);
      window.addEventListener("resize", drawSvgBoxes);
    };
  }

  function renderFindings(parent, data) {
    const findingsHeader = document.createElement("div");
    findingsHeader.className = "image_forgery-findings-header";
    const fhTitle = document.createElement("h3");
    fhTitle.style.margin = "0";
    fhTitle.textContent = `Forensic Findings (${data.findings.length})`;
    findingsHeader.appendChild(fhTitle);
    parent.appendChild(findingsHeader);

    const findingsContainer = document.createElement("div");
    findingsContainer.id = "image_forgery-findings-container";

    if (data.findings.length === 0) {
      const emptyMsg = document.createElement("div");
      emptyMsg.style.color = "var(--text-muted)";
      emptyMsg.style.padding = "1rem";
      emptyMsg.textContent = "No forensic anomalies detected.";
      findingsContainer.appendChild(emptyMsg);
    } else {
      data.findings.forEach((f) => {
        const card = document.createElement("div");
        card.className = `image_forgery-finding-card sev-${f.severity}`;
        card.id = `finding-card-${f.id}`;

        const top = document.createElement("div");
        top.className = "image_forgery-finding-top";

        const badges = document.createElement("div");
        badges.className = "image_forgery-finding-badges";

        const idBadge = document.createElement("span");
        idBadge.style.fontWeight = "700";
        idBadge.style.fontSize = "0.85rem";
        idBadge.textContent = f.id;

        const sevChip = document.createElement("span");
        sevChip.className = `image_forgery-chip image_forgery-chip-${f.severity}`;
        sevChip.textContent = `${f.severity} severity`;

        const checkBadge = document.createElement("span");
        checkBadge.className = "image_forgery-badge-pill";
        checkBadge.textContent = f.check;

        badges.appendChild(idBadge);
        badges.appendChild(sevChip);
        badges.appendChild(checkBadge);

        const confSpan = document.createElement("span");
        confSpan.style.fontSize = "0.8125rem";
        confSpan.style.color = "var(--text-muted)";
        confSpan.textContent = `Confidence: ${Math.round(f.confidence * 100)}%`;

        top.appendChild(badges);
        top.appendChild(confSpan);

        const desc = document.createElement("p");
        desc.className = "image_forgery-finding-desc";
        desc.textContent = f.description;

        const meta = document.createElement("div");
        meta.className = "image_forgery-finding-meta";

        if (f.location) {
          if (f.location.region) {
            const [x, y, w, h] = f.location.region;
            const regSpan = document.createElement("span");
            regSpan.textContent = `Region: [x:${x}, y:${y}, w:${w}, h:${h}]`;
            meta.appendChild(regSpan);
          }
          if (f.location.metadata_field) {
            const mfSpan = document.createElement("span");
            mfSpan.textContent = `Metadata Field: ${f.location.metadata_field}`;
            meta.appendChild(mfSpan);
          }
        }

        card.appendChild(top);
        card.appendChild(desc);
        if (meta.children.length > 0) card.appendChild(meta);

        card.addEventListener("click", () => {
          highlightFinding(f.id);
        });

        findingsContainer.appendChild(card);
      });
    }

    parent.appendChild(findingsContainer);
  }

  function highlightFinding(findingId) {
    selectedFindingId = findingId;

    const cards = document.querySelectorAll(".image_forgery-finding-card");
    cards.forEach((c) => c.classList.remove("highlighted"));
    const targetCard = document.getElementById(`finding-card-${findingId}`);
    if (targetCard) {
      targetCard.classList.add("highlighted");
      targetCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    const boxes = document.querySelectorAll(".image_forgery-svg-box");
    boxes.forEach((b) => {
      if (b.getAttribute("data-finding-id") === findingId) {
        b.classList.add("active");
      } else {
        b.classList.remove("active");
      }
    });
  }
}
