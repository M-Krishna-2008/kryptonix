/**
 * Hand-drawn Canvas and Interactive Visualizers
 * Pure HTML5 Canvas & DOM; zero external charting libraries or CDN dependencies.
 */

/**
 * 1. Audio Waveform with Highlighted Speech Windows
 */
export function renderAudioWaveform(canvas, perWindowLogits = [], durationSec = 10.0) {
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);

  const width = rect.width;
  const height = rect.height;
  const midY = height / 2;

  ctx.clearRect(0, 0, width, height);

  // Background grid lines
  ctx.strokeStyle = getComputedStyle(canvas).getPropertyValue('--border-light').trim() || '#E8E6DC';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, midY);
  ctx.lineTo(width, midY);
  ctx.stroke();

  // Generate stylized acoustic bars
  const numBars = Math.floor(width / 5);
  const barWidth = 3;
  const barGap = 2;

  // Find active speech windows for coloring
  const speechIntervals = [];
  for (const win of perWindowLogits) {
    if (win.has_speech) {
      speechIntervals.push({
        start: (win.start_sec / (durationSec || 10.0)) * width,
        end: (win.end_sec / (durationSec || 10.0)) * width,
        logit: win.bona_fide_logit,
      });
    }
  }

  // Draw simulated speech waveform envelope
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const accentColor = getComputedStyle(canvas).getPropertyValue('--accent-primary').trim() || '#C96442';
  const baseColor = isDark ? '#4A4843' : '#D5D1C5';

  for (let i = 0; i < numBars; i++) {
    const x = i * (barWidth + barGap);
    // Envelope simulation with harmonic variations
    const normX = i / numBars;
    const sin1 = Math.sin(normX * Math.PI * 8);
    const sin2 = Math.cos(normX * Math.PI * 18);
    const amp = Math.max(0.12, Math.abs(sin1 * 0.6 + sin2 * 0.4)) * (height * 0.42);

    // Check if x falls into any analyzed speech window
    let inSpeech = false;
    for (const interval of speechIntervals) {
      if (x >= interval.start && x <= interval.end) {
        inSpeech = true;
        break;
      }
    }

    ctx.fillStyle = inSpeech ? accentColor : baseColor;
    ctx.fillRect(x, midY - amp, barWidth, amp * 2);
  }

  // Draw time axis labels
  ctx.fillStyle = isDark ? '#85827A' : '#87847C';
  ctx.font = '10px ui-monospace, Consolas, monospace';
  ctx.fillText('0.0s', 6, height - 6);
  ctx.fillText(`${(durationSec || 10.0).toFixed(1)}s`, width - 36, height - 6);
}

/**
 * 2. AI Image Calibrated Probability Gauge
 */
export function renderImageGauge(container, calibratedProb) {
  if (!container) return;
  const pct = Math.max(0, Math.min(100, (calibratedProb ?? 0) * 100));

  container.innerHTML = `
    <div class="gauge-wrapper">
      <div class="metric-title">
        <span>Calibrated AI Fake Probability P(fake)</span>
        <span class="has-tooltip" data-tooltip="Calibrated probability from Universal Fake Detect (UnivFD CLIP ViT-L/14 linear probe).">&#9432;</span>
      </div>
      <div style="display: flex; align-items: baseline; gap: 8px;">
        <span class="metric-number">${pct.toFixed(1)}%</span>
        <span class="metric-subnote">${pct < 20 ? '(Real-domain)' : pct > 80 ? '(Synthetic-domain)' : '(Ambiguous / Uncertain)'}</span>
      </div>
      <div class="gauge-bar-track">
        <div class="gauge-marker" style="left: ${pct}%;"></div>
      </div>
      <div class="gauge-labels-row">
        <span>0% Real</span>
        <span>20% (Cutoff)</span>
        <span>50% Uncertain</span>
        <span>80% (Cutoff)</span>
        <span>100% Fake</span>
      </div>
    </div>
  `;
}

/**
 * 3. Image Forgery Overlay with Opacity Slider & Side-by-Side Mode
 */
export function setupForgeryViewer(container, originalUrl, heatmapUrl, elaUrl) {
  if (!container) return;

  container.innerHTML = `
    <div class="forgery-controls-bar">
      <div class="view-mode-toggle">
        <button class="btn-mode-tab active" data-mode="overlay">Overlay</button>
        <button class="btn-mode-tab" data-mode="side">Side-by-Side</button>
        ${elaUrl ? '<button class="btn-mode-tab" data-mode="ela">ELA</button>' : ''}
      </div>
      <div class="opacity-slider-box" id="opacityCtrl">
        <span>Heatmap Opacity:</span>
        <input type="range" class="opacity-slider" id="heatmapOpacity" min="0" max="100" value="65">
        <span id="opacityVal">65%</span>
      </div>
      ${heatmapUrl ? `<a href="${heatmapUrl}" download="tamper_heatmap.png" class="btn-secondary" style="padding: 4px 10px; font-size: 0.76rem;">Download Heatmap</a>` : ''}
    </div>

    <div class="forgery-display-stage" id="forgeryStage">
      <!-- Injected mode content -->
    </div>
  `;

  const stage = container.querySelector('#forgeryStage');
  const opacityCtrl = container.querySelector('#opacityCtrl');
  const slider = container.querySelector('#heatmapOpacity');
  const opacityVal = container.querySelector('#opacityVal');
  const modeTabs = container.querySelectorAll('.btn-mode-tab');

  function renderMode(mode) {
    if (mode === 'overlay') {
      opacityCtrl.style.display = 'flex';
      stage.innerHTML = `
        <div class="overlay-container">
          <img src="${originalUrl}" class="overlay-img-base" alt="Evidence Original">
          ${heatmapUrl ? `<img src="${heatmapUrl}" id="heatmapImg" class="overlay-img-heatmap" style="opacity: ${slider.value / 100};" alt="TruFor Tamper Heatmap">` : ''}
        </div>
      `;
    } else if (mode === 'side') {
      opacityCtrl.style.display = 'none';
      stage.innerHTML = `
        <div class="side-by-side-grid">
          <div class="side-item">
            <span class="side-label">Original Image</span>
            <img src="${originalUrl}" class="side-img" alt="Original">
          </div>
          <div class="side-item">
            <span class="side-label">TruFor Heatmap Overlay</span>
            <img src="${heatmapUrl || originalUrl}" class="side-img" alt="Heatmap">
          </div>
        </div>
      `;
    } else if (mode === 'ela') {
      opacityCtrl.style.display = 'none';
      stage.innerHTML = `
        <div class="side-by-side-grid">
          <div class="side-item">
            <span class="side-label">Original Image</span>
            <img src="${originalUrl}" class="side-img" alt="Original">
          </div>
          <div class="side-item">
            <span class="side-label">Error Level Analysis (ELA)</span>
            <img src="${elaUrl}" class="side-img" alt="ELA Compression Discrepancies">
          </div>
        </div>
      `;
    }
  }

  // Handle mode tabs
  modeTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      modeTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      renderMode(tab.dataset.mode);
    });
  });

  // Handle opacity slider
  slider.addEventListener('input', (e) => {
    const val = e.target.value;
    opacityVal.textContent = `${val}%`;
    const hm = stage.querySelector('#heatmapImg');
    if (hm) hm.style.opacity = val / 100;
  });

  // Default mode
  renderMode('overlay');
}

/**
 * 4. CCTV Video Score-Over-Time Timeline Chart with Video Seek
 */
export function renderCCTVTimeline(canvas, videoPlayer, frameScores = [], durationSec = 1.0) {
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();

  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);

  const width = rect.width;
  const height = rect.height;
  const padBottom = 22;
  const padTop = 14;
  const padLeft = 32;
  const padRight = 16;
  const plotW = width - padLeft - padRight;
  const plotH = height - padTop - padBottom;

  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const textColor = isDark ? '#A3A099' : '#87847C';
  const gridColor = isDark ? '#3A3935' : '#E8E6DC';
  const accentColor = getComputedStyle(canvas).getPropertyValue('--accent-primary').trim() || '#C96442';

  ctx.clearRect(0, 0, width, height);

  // Draw Y-axis guide lines (0.0, 0.5, 0.7 threshold, 1.0)
  ctx.strokeStyle = gridColor;
  ctx.lineWidth = 1;
  ctx.font = '10px ui-monospace, Consolas, monospace';
  ctx.fillStyle = textColor;

  [0.0, 0.5, 1.0].forEach(val => {
    const y = padTop + plotH * (1.0 - val);
    ctx.beginPath();
    ctx.moveTo(padLeft, y);
    ctx.lineTo(width - padRight, y);
    ctx.stroke();
    ctx.fillText(val.toFixed(1), 6, y + 3);
  });

  // 0.70 AI Threshold line (dashed amber/red)
  const threshY = padTop + plotH * (1.0 - 0.70);
  ctx.save();
  ctx.strokeStyle = isDark ? '#F1BE6B' : '#D97706';
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(padLeft, threshY);
  ctx.lineTo(width - padRight, threshY);
  ctx.stroke();
  ctx.fillText('0.70 Threshold', width - padRight - 80, threshY - 4);
  ctx.restore();

  // If no frame scores, exit
  if (!frameScores || frameScores.length === 0) {
    ctx.fillText('No per-frame timeline data available', width / 2 - 80, height / 2);
    return;
  }

  // Calculate coordinates
  const maxTime = Math.max(durationSec || 1.0, frameScores[frameScores.length - 1].timestamp || 1.0);
  const points = frameScores.map(f => {
    const t = f.timestamp ?? 0;
    const s = Math.max(0, Math.min(1, f.score ?? 0));
    return {
      x: padLeft + (t / maxTime) * plotW,
      y: padTop + plotH * (1.0 - s),
      time: t,
      score: s,
    };
  });

  // Draw curve
  ctx.beginPath();
  ctx.strokeStyle = accentColor;
  ctx.lineWidth = 2.5;
  points.forEach((pt, i) => {
    if (i === 0) ctx.moveTo(pt.x, pt.y);
    else ctx.lineTo(pt.x, pt.y);
  });
  ctx.stroke();

  // Draw points
  points.forEach(pt => {
    ctx.beginPath();
    ctx.fillStyle = pt.score >= 0.70 ? '#C53030' : (isDark ? '#ECEBE4' : '#1F1E1D');
    ctx.arc(pt.x, pt.y, pt.score >= 0.70 ? 4.5 : 3, 0, Math.PI * 2);
    ctx.fill();
  });

  // Click handler to seek video player
  canvas.onclick = (e) => {
    if (!videoPlayer) return;
    const cRect = canvas.getBoundingClientRect();
    const clickX = e.clientX - cRect.left;
    if (clickX >= padLeft && clickX <= width - padRight) {
      const clickTime = ((clickX - padLeft) / plotW) * maxTime;
      videoPlayer.currentTime = clickTime;
      videoPlayer.play().catch(() => {});
    }
  };
}
