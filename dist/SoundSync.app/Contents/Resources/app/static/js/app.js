/**
 * SoundSync Multi-Out - Pro Studio Frontend Controller
 * Hardware-grade Audio Spectrum Visualizer, DAW Channel Strips, Solo Routing, and Keyboard Shortcuts.
 */

document.addEventListener('DOMContentLoaded', () => {
  // DOM References
  const btnToggleBroadcast = document.getElementById('btn-toggle-broadcast');
  const broadcastBtnLabel = document.getElementById('broadcast-btn-label');
  const broadcastPill = document.getElementById('broadcast-pill');
  const statusPillText = document.getElementById('status-pill-text');
  
  const btnRefresh = document.getElementById('btn-refresh');
  const btnTestAll = document.getElementById('btn-test-all');
  const btnShortcuts = document.getElementById('btn-shortcuts');
  const btnHelp = document.getElementById('btn-help');
  
  const guideModal = document.getElementById('guide-modal');
  const btnCloseGuide = document.getElementById('btn-close-guide');
  const btnGuideConfirm = document.getElementById('btn-guide-confirm');
  
  const shortcutsModal = document.getElementById('shortcuts-modal');
  const btnCloseShortcuts = document.getElementById('btn-close-shortcuts');

  const masterVolumeSlider = document.getElementById('master-volume-slider');
  const masterGainNum = document.getElementById('master-gain-num');
  const btnMasterMute = document.getElementById('btn-master-mute');
  
  const meterLeftFill = document.getElementById('meter-left-fill');
  const meterRightFill = document.getElementById('meter-right-fill');
  const meterLeftPeak = document.getElementById('meter-left-peak');
  const meterRightPeak = document.getElementById('meter-right-peak');
  
  const spectrumCanvas = document.getElementById('spectrum-canvas');
  const ctx = spectrumCanvas ? spectrumCanvas.getContext('2d') : null;

  const sourceSelect = document.getElementById('source-select');
  const deviceCountPill = document.getElementById('device-count-pill');
  const soloAlertBanner = document.getElementById('solo-alert-banner');
  const btnClearSolo = document.getElementById('btn-clear-solo');
  const channelsContainer = document.getElementById('channels-container');
  const studioToast = document.getElementById('studio-toast');
  const toastMessage = document.getElementById('toast-message');

  // Application State
  let appState = {
    is_broadcasting: false,
    master_volume: 1.0,
    master_muted: false,
    mirror_mode: 'mirror',
    devices: [],
    soloed_device_id: null
  };

  // Visualizer & Metering Physics State
  const SPECTRUM_BANDS = 20;
  let currentBands = new Array(SPECTRUM_BANDS).fill(0);
  let targetBands = new Array(SPECTRUM_BANDS).fill(0);
  let peakBands = new Array(SPECTRUM_BANDS).fill(0);
  let peakBandDecay = new Array(SPECTRUM_BANDS).fill(0);

  let leftPeakHold = 0;
  let rightPeakHold = 0;

  let eventSource = null;
  let fallbackInterval = null;

  initApp();

  function initApp() {
    setupEventListeners();
    setupKeyboardShortcuts();
    fetchStatus();
    startMeterStream();
    startCanvasVisualizerLoop();
  }

  // =========================================================================
  // Event Listeners & Keyboard Shortcuts
  // =========================================================================

  function setupEventListeners() {
    btnToggleBroadcast.addEventListener('click', toggleBroadcast);
    btnRefresh.addEventListener('click', handleRefreshDevices);
    btnTestAll.addEventListener('click', () => triggerTestTone(null));

    // Modals
    btnHelp.addEventListener('click', () => guideModal.classList.remove('hidden'));
    btnCloseGuide.addEventListener('click', () => guideModal.classList.add('hidden'));
    btnGuideConfirm.addEventListener('click', () => guideModal.classList.add('hidden'));
    guideModal.querySelector('.modal-backdrop').addEventListener('click', () => guideModal.classList.add('hidden'));

    btnShortcuts.addEventListener('click', () => shortcutsModal.classList.remove('hidden'));
    btnCloseShortcuts.addEventListener('click', () => shortcutsModal.classList.add('hidden'));
    shortcutsModal.querySelector('.modal-backdrop').addEventListener('click', () => shortcutsModal.classList.add('hidden'));

    // Master Volume Slider
    masterVolumeSlider.addEventListener('input', (e) => {
      const val = parseInt(e.target.value, 10);
      masterGainNum.textContent = `${val}%`;
      updateMaster({ volume: val / 100.0 });
      syncGainPresetHighlight(val);
    });

    // Master Mute
    btnMasterMute.addEventListener('click', () => {
      const newMuted = !appState.master_muted;
      updateMaster({ muted: newMuted });
    });

    // Quick Gain Taps
    document.querySelectorAll('.gain-tap').forEach(btn => {
      btn.addEventListener('click', () => {
        const vol = parseInt(btn.dataset.vol, 10);
        masterVolumeSlider.value = vol;
        masterGainNum.textContent = `${vol}%`;
        updateMaster({ volume: vol / 100.0 });
        syncGainPresetHighlight(vol);
      });
    });

    // Mode Selector (Smart Mirror vs Multi-Direct)
    document.querySelectorAll('.mode-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.mode-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const mode = tab.dataset.mode;
        updateMaster({ mode: mode });
        showToast(`Routing Mode: ${mode === 'mirror' ? 'Smart Mirror' : 'Multi-Direct'}`);
      });
    });

    // Audio Capture Source Line Dropdown
    if (sourceSelect) {
      sourceSelect.addEventListener('change', async (e) => {
        const val = e.target.value;
        const srcId = val === 'auto' ? null : parseInt(val, 10);
        showToast(val === 'auto' ? 'Capture source: Windows Default' : `Capture source: Switching line...`);
        try {
          const res = await fetch('/api/source/select', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source_device_index: srcId })
          });
          const data = await res.json();
          if (data.success) {
            updateUIState(data.status);
            showToast('Capture source line updated!');
          }
        } catch (err) {
          showToast('Could not switch capture source');
        }
      });
    }

    // Presets Bar (Tri-Party, Cinema Sync, Balanced)
    document.querySelectorAll('.preset-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.preset-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        const preset = chip.dataset.preset;
        applyPreset(preset);
      });
    });

    // Clear Solo Banner
    btnClearSolo.addEventListener('click', () => {
      if (appState.soloed_device_id !== null) {
        toggleSolo(appState.soloed_device_id);
      }
    });
  }

  function setupKeyboardShortcuts() {
    window.addEventListener('keydown', (e) => {
      // Ignore if user is inside an input field
      if (e.target.tagName === 'INPUT' && e.target.type === 'text') return;

      if (e.code === 'Space') {
        e.preventDefault();
        toggleBroadcast();
      } else if (e.key === 'm' || e.key === 'M') {
        e.preventDefault();
        updateMaster({ muted: !appState.master_muted });
      } else if (e.key === 'r' || e.key === 'R') {
        e.preventDefault();
        handleRefreshDevices();
      } else if (e.key === 't' || e.key === 'T') {
        e.preventDefault();
        triggerTestTone(null);
      } else if (e.key === 'Escape') {
        guideModal.classList.add('hidden');
        shortcutsModal.classList.add('hidden');
        if (appState.soloed_device_id !== null) {
          toggleSolo(appState.soloed_device_id);
        }
      } else if (e.key >= '1' && e.key <= '9') {
        const idx = parseInt(e.key, 10) - 1;
        if (appState.devices && appState.devices[idx]) {
          const dev = appState.devices[idx];
          updateDeviceConfig(dev.index, { enabled: !dev.enabled });
          const chk = document.getElementById(`switch-${dev.index}`);
          if (chk) chk.checked = !dev.enabled;
        }
      }
    });
  }

  function syncGainPresetHighlight(vol) {
    document.querySelectorAll('.gain-tap').forEach(btn => {
      btn.classList.toggle('active', parseInt(btn.dataset.vol, 10) === vol);
    });
  }

  // =========================================================================
  // API Calls
  // =========================================================================

  async function fetchStatus() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      if (data.success) {
        updateUIState(data.data);
      }
    } catch (err) {
      console.error('Error fetching status:', err);
      showToast('Connecting to audio engine...');
    }
  }

  async function handleRefreshDevices() {
    btnRefresh.classList.add('loading');
    showToast('Scanning Windows Bluetooth & Audio Endpoints...');
    try {
      const res = await fetch('/api/devices/refresh', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        updateUIState(data.status);
        showToast(`Discovered ${data.devices.length} audio devices!`);
      }
    } catch (err) {
      showToast('Scan error');
    } finally {
      btnRefresh.classList.remove('loading');
    }
  }

  async function toggleBroadcast() {
    const isRunning = appState.is_broadcasting;
    const endpoint = isRunning ? '/api/broadcast/stop' : '/api/broadcast/start';

    try {
      btnToggleBroadcast.disabled = true;
      const res = await fetch(endpoint, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        updateUIState(data.status);
        if (data.is_broadcasting) {
          showToast('🟢 Live Broadcasting to all active outputs!');
        } else {
          showToast('Broadcasting stopped');
        }
      } else {
        showToast('Error: ' + (data.error || 'Check audio device'));
      }
    } catch (err) {
      showToast('Failed to toggle broadcast');
    } finally {
      btnToggleBroadcast.disabled = false;
    }
  }

  async function updateMaster(payload) {
    try {
      const res = await fetch('/api/master', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        appState.master_volume = data.status.master_volume;
        appState.master_muted = data.status.master_muted;
        appState.mirror_mode = data.status.mirror_mode;
        syncMasterControls();
      }
    } catch (err) {}
  }

  async function updateDeviceConfig(devIndex, payload) {
    try {
      const res = await fetch(`/api/device/${devIndex}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        const card = document.getElementById(`channel-card-${devIndex}`);
        if (card && payload.enabled !== undefined) {
          card.classList.toggle('is-disabled', !payload.enabled);
        }
      }
    } catch (err) {}
  }

  async function toggleSolo(devIndex) {
    try {
      const res = await fetch(`/api/device/${devIndex}/solo`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        appState.soloed_device_id = data.soloed_device_id;
        syncSoloUI();
        if (appState.soloed_device_id !== null) {
          showToast(`⚡ Solo Active: Isolated channel ${devIndex}`);
        } else {
          showToast('Solo cleared');
        }
      }
    } catch (err) {}
  }

  async function applyPreset(presetName) {
    showToast(`Applying "${presetName.toUpperCase()}" Preset...`);
    try {
      const res = await fetch(`/api/preset/${presetName}`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        updateUIState(data.status);
        showToast(`Preset "${presetName.toUpperCase()}" activated!`);
      }
    } catch (err) {}
  }

  async function triggerTestTone(devIndex) {
    showToast(devIndex !== null ? 'Playing harmonic chime...' : 'Testing all active outputs...');
    try {
      await fetch('/api/test_tone', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_index: devIndex })
      });
    } catch (err) {}
  }

  // =========================================================================
  // UI Rendering & Synchronization
  // =========================================================================

  function updateUIState(state) {
    appState = state;

    // Master Broadcast Button & Status
    if (state.is_broadcasting) {
      btnToggleBroadcast.className = 'master-power-btn is-broadcasting';
      broadcastBtnLabel.textContent = 'STOP BROADCAST';
      broadcastPill.className = 'status-indicator-pill live';
      statusPillText.textContent = 'BROADCASTING LIVE';
    } else {
      btnToggleBroadcast.className = 'master-power-btn';
      broadcastBtnLabel.textContent = 'START BROADCAST';
      broadcastPill.className = 'status-indicator-pill';
      statusPillText.textContent = 'STANDBY';
    }

    // Source Info & Dropdown
    if (sourceSelect && state.devices) {
      const currentSelected = (state.selected_source_index !== null && state.selected_source_index !== undefined)
        ? String(state.selected_source_index)
        : 'auto';

      if (document.activeElement !== sourceSelect) {
        const desiredValues = ['auto', ...state.devices.map(d => String(d.index))];
        const existingValues = Array.from(sourceSelect.options).map(o => o.value);
        const match = desiredValues.length === existingValues.length && desiredValues.every((v, i) => v === existingValues[i]);
        if (!match) {
          let optionsHtml = `<option value="auto">Auto: Windows Default (${state.default_output || 'Default'})</option>`;
          state.devices.forEach(d => {
            optionsHtml += `<option value="${d.index}">${d.name} (${d.category.toUpperCase()})</option>`;
          });
          sourceSelect.innerHTML = optionsHtml;
        }
        sourceSelect.value = currentSelected;
      }
    }

    // Devices Count
    const btCount = state.devices.filter(d => d.category === 'bluetooth').length;
    deviceCountPill.textContent = `${state.devices.length} Outputs (${btCount} Bluetooth)`;

    // Sync Master Controls
    syncMasterControls();

    // Render Channels
    renderChannelStrips(state.devices);

    // Sync Solo
    syncSoloUI();
  }

  function syncMasterControls() {
    const volPercent = Math.round(appState.master_volume * 100);
    masterVolumeSlider.value = volPercent;
    masterGainNum.textContent = `${volPercent}%`;
    btnMasterMute.classList.toggle('active', appState.master_muted);

    document.querySelectorAll('.mode-tab').forEach(t => {
      t.classList.toggle('active', t.dataset.mode === appState.mirror_mode);
    });

    syncGainPresetHighlight(volPercent);
  }

  function syncSoloUI() {
    const soloId = appState.soloed_device_id;
    soloAlertBanner.classList.toggle('hidden', soloId === null);

    document.querySelectorAll('.channel-strip-card').forEach(card => {
      const devId = parseInt(card.dataset.devId, 10);
      const isSoloed = (soloId !== null && devId === soloId);
      card.classList.toggle('is-soloed', isSoloed);

      const soloBtn = card.querySelector('.btn-solo');
      if (soloBtn) soloBtn.classList.toggle('active', isSoloed);
    });
  }

  function renderChannelStrips(devices) {
    if (!devices || devices.length === 0) {
      channelsContainer.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 48px; color: var(--text-muted);">
          <p>No audio outputs detected. Connect your Bluetooth headphones/speakers and click <strong>Refresh</strong>.</p>
        </div>
      `;
      return;
    }

    channelsContainer.innerHTML = '';
    devices.forEach((dev, idx) => {
      const card = createChannelStripCard(dev, idx + 1);
      channelsContainer.appendChild(card);
    });
  }

  function createChannelStripCard(dev, chNum) {
    const card = document.createElement('div');
    const isSoloed = (appState.soloed_device_id === dev.index);
    card.className = `channel-strip-card ${dev.is_worker_active ? 'active-stream' : ''} ${isSoloed ? 'is-soloed' : ''} ${!dev.enabled ? 'is-disabled' : ''}`;
    card.id = `channel-card-${dev.index}`;
    card.dataset.devId = dev.index;

    const isBt = dev.category === 'bluetooth';
    const catIcon = isBt ? 'ᛒ' : (dev.category === 'speaker' ? '🔊' : '🎛️');

    card.innerHTML = `
      <!-- Card Header -->
      <div class="channel-card-top">
        <div class="channel-id-row">
          <div class="channel-avatar ${dev.category}" title="${dev.category.toUpperCase()}">${catIcon}</div>
          <div class="channel-name-info">
            <span class="channel-num-tag">CH 0${chNum}</span>
            <h4 class="channel-title" title="${dev.name}">${dev.name}</h4>
            <div class="channel-badges-row">
              ${dev.is_default ? '<span class="ch-badge default-badge">Default</span>' : ''}
              ${isBt ? '<span class="ch-badge bt-badge">Bluetooth</span>' : ''}
              <span class="ch-badge">${dev.sample_rate}Hz</span>
            </div>
          </div>
        </div>

        <label class="channel-switch" title="Toggle output stream [Shortcut: ${chNum}]">
          <input type="checkbox" id="switch-${dev.index}" ${dev.enabled ? 'checked' : ''}>
          <span class="switch-slider"></span>
        </label>
      </div>

      <!-- Real-Time LED Level Bar -->
      <div class="channel-meter-strip">
        <div class="meter-track">
          <div class="meter-bar-fill" id="meter-bar-${dev.index}"></div>
        </div>
      </div>

      <!-- Mixer Rack -->
      <div class="mixer-controls-rack">
        
        <!-- Fader & Mute / Solo -->
        <div class="control-module">
          <div class="module-header">
            <span>Fader Output Gain</span>
            <span class="module-val" id="vol-readout-${dev.index}">${Math.round(dev.volume * 100)}%</span>
          </div>
          <div class="fader-with-toggles">
            <input type="range" class="pro-fader" id="vol-fader-${dev.index}" min="0" max="150" value="${Math.round(dev.volume * 100)}">
            <button class="ch-btn btn-mute ${dev.muted ? 'active' : ''}" id="mute-btn-${dev.index}" title="Mute Channel">M</button>
            <button class="ch-btn btn-solo ${isSoloed ? 'active' : ''}" id="solo-btn-${dev.index}" title="Solo Channel (Isolate Sound)">S</button>
          </div>
        </div>

        <!-- Bluetooth Latency Delay Sync -->
        <div class="control-module">
          <div class="module-header">
            <span title="Micro-delay line to synchronize wireless Bluetooth audio">Bluetooth Latency Sync</span>
            <span class="module-val" id="delay-readout-${dev.index}">${dev.delay_ms} ms</span>
          </div>
          <input type="range" class="pro-fader" id="delay-fader-${dev.index}" min="0" max="500" step="5" value="${dev.delay_ms}">
          
          <div class="delay-quick-chips">
            <button class="sync-chip ${dev.delay_ms === 0 ? 'active' : ''}" data-ms="0">0ms</button>
            <button class="sync-chip ${dev.delay_ms === 40 ? 'active' : ''}" data-ms="40">40ms</button>
            <button class="sync-chip ${dev.delay_ms === 120 ? 'active' : ''}" data-ms="120">120ms</button>
            <button class="sync-chip ${dev.delay_ms === 180 ? 'active' : ''}" data-ms="180">180ms</button>
          </div>
        </div>

        <!-- Stereo Pan Balance -->
        <div class="control-module">
          <div class="module-header">
            <span>Pan Balance</span>
            <span class="module-val" id="pan-readout-${dev.index}">${dev.pan === 0 ? 'Center' : (dev.pan < 0 ? 'L ' + Math.abs(Math.round(dev.pan * 100)) + '%' : 'R ' + Math.round(dev.pan * 100) + '%')}</span>
          </div>
          <div class="pan-track-wrap">
            <div class="pan-center-mark"></div>
            <input type="range" class="pro-fader" id="pan-fader-${dev.index}" min="-100" max="100" step="5" value="${Math.round(dev.pan * 100)}">
          </div>
        </div>

      </div>

      <!-- Card Footer -->
      <div class="channel-footer">
        <button class="ch-test-btn" id="test-btn-${dev.index}" title="Play test chime on this output">
          <svg class="svg-icon" viewBox="0 0 24 24"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/></svg>
          Test Tone
        </button>
        <span class="ch-meta-text">${dev.channels}ch • WASAPI</span>
      </div>
    `;

    // Attach Card Event Handlers
    const chk = card.querySelector(`#switch-${dev.index}`);
    chk.addEventListener('change', (e) => {
      updateDeviceConfig(dev.index, { enabled: e.target.checked });
    });

    const volFader = card.querySelector(`#vol-fader-${dev.index}`);
    const volReadout = card.querySelector(`#vol-readout-${dev.index}`);
    volFader.addEventListener('input', (e) => {
      const v = parseInt(e.target.value, 10);
      volReadout.textContent = `${v}%`;
      updateDeviceConfig(dev.index, { volume: v / 100.0 });
    });

    const muteBtn = card.querySelector(`#mute-btn-${dev.index}`);
    muteBtn.addEventListener('click', () => {
      dev.muted = !dev.muted;
      muteBtn.classList.toggle('active', dev.muted);
      updateDeviceConfig(dev.index, { muted: dev.muted });
    });

    const soloBtn = card.querySelector(`#solo-btn-${dev.index}`);
    soloBtn.addEventListener('click', () => {
      toggleSolo(dev.index);
    });

    const delayFader = card.querySelector(`#delay-fader-${dev.index}`);
    const delayReadout = card.querySelector(`#delay-readout-${dev.index}`);
    delayFader.addEventListener('input', (e) => {
      const ms = parseInt(e.target.value, 10);
      delayReadout.textContent = `${ms} ms`;
      updateDeviceConfig(dev.index, { delay_ms: ms });
      syncDelayChips(card, ms);
    });

    card.querySelectorAll('.sync-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const ms = parseInt(chip.dataset.ms, 10);
        delayFader.value = ms;
        delayReadout.textContent = `${ms} ms`;
        updateDeviceConfig(dev.index, { delay_ms: ms });
        syncDelayChips(card, ms);
      });
    });

    const panFader = card.querySelector(`#pan-fader-${dev.index}`);
    const panReadout = card.querySelector(`#pan-readout-${dev.index}`);
    panFader.addEventListener('input', (e) => {
      const p = parseInt(e.target.value, 10);
      panReadout.textContent = (p === 0 ? 'Center' : (p < 0 ? `L ${Math.abs(p)}%` : `R ${p}%`));
      updateDeviceConfig(dev.index, { pan: p / 100.0 });
    });

    const testBtn = card.querySelector(`#test-btn-${dev.index}`);
    testBtn.addEventListener('click', () => {
      triggerTestTone(dev.index);
    });

    return card;
  }

  function syncDelayChips(card, currentMs) {
    card.querySelectorAll('.sync-chip').forEach(c => {
      c.classList.toggle('active', parseInt(c.dataset.ms, 10) === currentMs);
    });
  }

  // =========================================================================
  // Canvas Spectrum & Stereo VU Visualizer Loop
  // =========================================================================

  function startMeterStream() {
    if (window.EventSource) {
      try {
        eventSource = new EventSource('/api/meter_stream');
        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            handleIncomingMeters(data);
          } catch (e) {}
        };
        eventSource.onerror = () => {
          eventSource.close();
          fallbackPolling();
        };
      } catch (err) {
        fallbackPolling();
      }
    } else {
      fallbackPolling();
    }
  }

  function fallbackPolling() {
    if (fallbackInterval) return;
    fallbackInterval = setInterval(async () => {
      try {
        const res = await fetch('/api/meters');
        const data = await res.json();
        handleIncomingMeters(data);
      } catch (e) {}
    }, 60);
  }

  function handleIncomingMeters(data) {
    if (!data) return;

    // Master Stereo Peak Meters
    const mLvl = data.master_level || 0.0;
    const leftVal = Math.min(100, Math.round(mLvl * 100));
    const rightVal = Math.min(100, Math.round(mLvl * 96)); // slight stereo variance

    meterLeftFill.style.height = `${leftVal}%`;
    meterRightFill.style.height = `${rightVal}%`;

    // Peak Hold markers
    if (leftVal > leftPeakHold) leftPeakHold = leftVal;
    else leftPeakHold = Math.max(0, leftPeakHold - 1.5);

    if (rightVal > rightPeakHold) rightPeakHold = rightVal;
    else rightPeakHold = Math.max(0, rightPeakHold - 1.5);

    meterLeftPeak.style.bottom = `${leftPeakHold}%`;
    meterRightPeak.style.bottom = `${rightPeakHold}%`;

    // Spectrum Bands from FFT
    if (data.spectrum && data.spectrum.length === SPECTRUM_BANDS) {
      targetBands = data.spectrum;
    } else {
      // Fallback synthetic wave driven by RMS
      for (let i = 0; i < SPECTRUM_BANDS; i++) {
        const phase = Math.sin(Date.now() * 0.008 + i * 0.4);
        targetBands[i] = Math.max(0, Math.min(1.0, mLvl * (0.8 + 0.4 * phase)));
      }
    }

    // Per-Device Level Meters
    const devLevels = data.device_levels || {};
    for (const [devId, lvl] of Object.entries(devLevels)) {
      const bar = document.getElementById(`meter-bar-${devId}`);
      if (bar) {
        const p = Math.min(100, Math.round((lvl || 0) * 100));
        bar.style.width = `${p}%`;
      }
    }
  }

  function startCanvasVisualizerLoop() {
    if (!ctx || !spectrumCanvas) return;

    function renderFrame() {
      const width = spectrumCanvas.width;
      const height = spectrumCanvas.height;

      ctx.clearRect(0, 0, width, height);

      const totalBars = SPECTRUM_BANDS;
      const barSpacing = 4;
      const barWidth = (width - (totalBars - 1) * barSpacing) / totalBars;

      for (let i = 0; i < totalBars; i++) {
        // Smoothly interpolate current to target
        currentBands[i] += (targetBands[i] - currentBands[i]) * 0.28;
        const val = currentBands[i];
        const barHeight = Math.max(3, val * (height - 10));

        // Peak cap physics
        if (barHeight > peakBands[i]) {
          peakBands[i] = barHeight;
          peakBandDecay[i] = 0;
        } else {
          peakBandDecay[i] += 0.15;
          peakBands[i] = Math.max(3, peakBands[i] - peakBandDecay[i]);
        }

        const x = i * (barWidth + barSpacing);
        const y = height - barHeight;

        // Gradient bar (Cyan -> Purple -> Pink)
        const grad = ctx.createLinearGradient(0, height, 0, 0);
        grad.addColorStop(0, '#00f2fe');
        grad.addColorStop(0.6, '#38bdf8');
        grad.addColorStop(0.85, '#a855f7');
        grad.addColorStop(1.0, '#ec4899');

        ctx.fillStyle = grad;
        // Rounded bar
        ctx.beginPath();
        ctx.roundRect(x, y, barWidth, barHeight, [3, 3, 0, 0]);
        ctx.fill();

        // Draw Peak Cap Line
        const capY = Math.max(0, height - peakBands[i]);
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(x, capY, barWidth, 2);
      }

      requestAnimationFrame(renderFrame);
    }

    requestAnimationFrame(renderFrame);
  }

  // =========================================================================
  // Toast Notifications
  // =========================================================================

  function showToast(msg) {
    toastMessage.textContent = msg;
    studioToast.classList.remove('hidden');
    clearTimeout(studioToast._timer);
    studioToast._timer = setTimeout(() => {
      studioToast.classList.add('hidden');
    }, 2800);
  }
});
