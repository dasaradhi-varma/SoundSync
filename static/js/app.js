/**
 * SoundSync Multi-Out - Frontend Application Controller
 * Handles real-time device matrix, VU meter animations, volume & delay sync controls.
 */

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const btnToggleBroadcast = document.getElementById('btn-toggle-broadcast');
  const broadcastBtnText = document.getElementById('broadcast-btn-text');
  const broadcastStatusBadge = document.getElementById('broadcast-status-badge');
  const btnRefresh = document.getElementById('btn-refresh');
  const btnTestAll = document.getElementById('btn-test-all');
  const btnHelp = document.getElementById('btn-help');
  const guideModal = document.getElementById('guide-modal');
  const btnCloseModal = document.getElementById('btn-close-modal');
  const btnModalGotIt = document.getElementById('btn-modal-gotit');
  
  const masterVolumeSlider = document.getElementById('master-volume-slider');
  const masterVolVal = document.getElementById('master-vol-val');
  const masterMuteBtn = document.getElementById('master-mute-btn');
  const masterVuFill = document.getElementById('master-vu-fill');
  const masterMeterVal = document.getElementById('master-meter-val');
  
  const srcDefaultName = document.getElementById('src-default-name');
  const srcMetaInfo = document.getElementById('src-meta-info');
  const devicesCount = document.getElementById('devices-count');
  const devicesContainer = document.getElementById('devices-container');
  const routingModeRadios = document.querySelectorAll('input[name="routing_mode"]');
  const toast = document.getElementById('toast');

  let appState = {
    is_broadcasting: false,
    master_volume: 1.0,
    master_muted: false,
    mirror_mode: 'mirror',
    devices: []
  };

  let eventSource = null;
  let meterPollInterval = null;

  // Initialize
  initApp();

  function initApp() {
    setupEventListeners();
    fetchStatus();
    startMeterStream();
  }

  function setupEventListeners() {
    btnToggleBroadcast.addEventListener('click', toggleBroadcast);
    btnRefresh.addEventListener('click', handleRefreshDevices);
    btnTestAll.addEventListener('click', () => triggerTestTone(null));
    
    // Help Modal
    btnHelp.addEventListener('click', () => guideModal.classList.remove('hidden'));
    btnCloseModal.addEventListener('click', () => guideModal.classList.add('hidden'));
    btnModalGotIt.addEventListener('click', () => guideModal.classList.add('hidden'));
    guideModal.addEventListener('click', (e) => {
      if (e.target === guideModal) guideModal.classList.add('hidden');
    });

    // Master Volume
    masterVolumeSlider.addEventListener('input', (e) => {
      const val = parseInt(e.target.value, 10);
      masterVolVal.textContent = `${val}%`;
      updateMaster({ volume: val / 100.0 });
    });

    // Master Mute
    masterMuteBtn.addEventListener('click', () => {
      const newMuted = !appState.master_muted;
      updateMaster({ muted: newMuted });
    });

    // Volume Presets
    document.querySelectorAll('.preset-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const vol = parseInt(btn.dataset.vol, 10);
        masterVolumeSlider.value = vol;
        masterVolVal.textContent = `${vol}%`;
        updateMaster({ volume: vol / 100.0 });
      });
    });

    // Routing Mode
    routingModeRadios.forEach(radio => {
      radio.addEventListener('change', (e) => {
        updateMaster({ mode: e.target.value });
      });
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
      showToast('Could not connect to audio engine');
    }
  }

  async function handleRefreshDevices() {
    btnRefresh.disabled = true;
    showToast('Scanning for newly connected Bluetooth & sound devices...');
    try {
      const res = await fetch('/api/devices/refresh', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        updateUIState(data.status);
        showToast(`Discovered ${data.devices.length} audio endpoints!`);
      }
    } catch (err) {
      showToast('Device scan failed');
    } finally {
      btnRefresh.disabled = false;
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
          showToast('Broadcasting live to all active devices!');
        } else {
          showToast('Broadcasting stopped');
        }
      } else {
        showToast('Error starting broadcast: ' + (data.error || 'Check audio device'));
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
    } catch (err) {
      console.error('Error updating master:', err);
    }
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
        const devCard = document.getElementById(`device-card-${devIndex}`);
        if (devCard && payload.enabled !== undefined) {
          devCard.classList.toggle('is-disabled', !payload.enabled);
        }
      }
    } catch (err) {
      console.error(`Error updating device ${devIndex}:`, err);
    }
  }

  async function triggerTestTone(devIndex) {
    showToast(devIndex !== null ? 'Playing test chime...' : 'Testing all active devices...');
    try {
      await fetch('/api/test_tone', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_index: devIndex })
      });
    } catch (err) {
      showToast('Test tone failed');
    }
  }

  // =========================================================================
  // UI Rendering & Synchronization
  // =========================================================================

  function updateUIState(state) {
    appState = state;

    // Master Broadcast Button & Badges
    if (state.is_broadcasting) {
      btnToggleBroadcast.className = 'btn-broadcast stop';
      broadcastBtnText.textContent = 'STOP BROADCASTING';
      broadcastStatusBadge.className = 'badge broadcasting';
      broadcastStatusBadge.textContent = 'BROADCASTING LIVE';
    } else {
      btnToggleBroadcast.className = 'btn-broadcast start';
      broadcastBtnText.textContent = 'START BROADCASTING';
      broadcastStatusBadge.className = 'badge';
      broadcastStatusBadge.textContent = 'STANDBY';
    }

    // Capture Source info
    if (state.default_output) {
      srcDefaultName.textContent = state.default_output;
      srcMetaInfo.textContent = `WASAPI Loopback • ${state.sample_rate} Hz Stereo 32-bit Float`;
    }

    // Devices Count
    const btCount = state.devices.filter(d => d.category === 'bluetooth').length;
    devicesCount.textContent = `${state.devices.length} Total (${btCount} Bluetooth)`;

    // Sync Master Volume
    syncMasterControls();

    // Render Device Cards
    renderDeviceCards(state.devices);
  }

  function syncMasterControls() {
    masterVolumeSlider.value = Math.round(appState.master_volume * 100);
    masterVolVal.textContent = `${Math.round(appState.master_volume * 100)}%`;
    masterMuteBtn.classList.toggle('muted', appState.master_muted);

    routingModeRadios.forEach(r => {
      r.checked = (r.value === appState.mirror_mode);
    });
  }

  function renderDeviceCards(devices) {
    if (!devices || devices.length === 0) {
      devicesContainer.innerHTML = `
        <div class="loading-state">
          <p>No audio output endpoints detected. Connect your Bluetooth headphones/speakers and click "Refresh Devices".</p>
        </div>
      `;
      return;
    }

    devicesContainer.innerHTML = '';
    devices.forEach(dev => {
      const card = createDeviceCard(dev);
      devicesContainer.appendChild(card);
    });
  }

  function createDeviceCard(dev) {
    const card = document.createElement('div');
    card.className = `device-card ${dev.is_worker_active ? 'is-active-stream' : ''} ${!dev.enabled ? 'is-disabled' : ''}`;
    card.id = `device-card-${dev.index}`;

    const catIcon = dev.category === 'bluetooth' ? 'ᛒ' : (dev.category === 'speaker' ? '🔊' : '🎛️');
    const isBt = dev.category === 'bluetooth';

    card.innerHTML = `
      <div class="device-card-header">
        <div class="device-identity">
          <div class="device-avatar ${dev.category}">${catIcon}</div>
          <div class="device-info-text">
            <h4 class="device-name" title="${dev.name}">${dev.name}</h4>
            <div class="device-badges">
              ${dev.is_default ? '<span class="mini-badge default-badge">Default Device</span>' : ''}
              ${isBt ? '<span class="mini-badge bt-badge">Bluetooth</span>' : ''}
              <span class="mini-badge">${dev.sample_rate}Hz</span>
            </div>
          </div>
        </div>

        <label class="toggle-switch" title="Enable/Disable multi-output to this device">
          <input type="checkbox" id="toggle-${dev.index}" ${dev.enabled ? 'checked' : ''}>
          <span class="slider-switch"></span>
        </label>
      </div>

      <!-- Live VU Meter -->
      <div class="device-meter-wrap">
        <div class="device-meter-bar">
          <div class="device-meter-fill" id="meter-fill-${dev.index}"></div>
        </div>
      </div>

      <!-- Controls -->
      <div class="device-controls">
        <!-- Volume Slider -->
        <div class="control-field">
          <div class="field-header">
            <span>Device Output Volume</span>
            <span class="field-value" id="vol-val-${dev.index}">${Math.round(dev.volume * 100)}%</span>
          </div>
          <div class="slider-row">
            <input type="range" class="range-slider" id="vol-slider-${dev.index}" min="0" max="150" value="${Math.round(dev.volume * 100)}">
            <button class="btn btn-icon ${dev.muted ? 'muted' : ''}" id="mute-btn-${dev.index}" title="Mute Device">
              <svg class="icon" viewBox="0 0 24 24"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/></svg>
            </button>
          </div>
        </div>

        <!-- Latency / Delay Sync Slider (Essential for Multi-Bluetooth!) -->
        <div class="control-field">
          <div class="field-header">
            <span title="Adjust to eliminate echo between different Bluetooth headphones">Bluetooth Latency Sync (Delay)</span>
            <span class="field-value" id="delay-val-${dev.index}">${dev.delay_ms} ms</span>
          </div>
          <input type="range" class="range-slider" id="delay-slider-${dev.index}" min="0" max="500" step="5" value="${dev.delay_ms}">
        </div>

        <!-- Stereo Balance (Pan) -->
        <div class="control-field">
          <div class="field-header">
            <span>Balance (L - R)</span>
            <span class="field-value" id="pan-val-${dev.index}">${dev.pan === 0 ? 'Center' : (dev.pan < 0 ? 'L ' + Math.abs(Math.round(dev.pan * 100)) + '%' : 'R ' + Math.round(dev.pan * 100) + '%')}</span>
          </div>
          <input type="range" class="range-slider" id="pan-slider-${dev.index}" min="-100" max="100" step="5" value="${Math.round(dev.pan * 100)}">
        </div>
      </div>

      <!-- Footer Action -->
      <div class="device-footer-actions">
        <button class="btn btn-secondary btn-sm" id="test-btn-${dev.index}" title="Play test chime on this device">
          <svg class="icon" viewBox="0 0 24 24"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/></svg>
          Test Audio
        </button>
        <span class="source-meta">${dev.channels} Channels</span>
      </div>
    `;

    // Attach card event listeners
    const toggle = card.querySelector(`#toggle-${dev.index}`);
    toggle.addEventListener('change', (e) => {
      updateDeviceConfig(dev.index, { enabled: e.target.checked });
    });

    const volSlider = card.querySelector(`#vol-slider-${dev.index}`);
    const volVal = card.querySelector(`#vol-val-${dev.index}`);
    volSlider.addEventListener('input', (e) => {
      const v = parseInt(e.target.value, 10);
      volVal.textContent = `${v}%`;
      updateDeviceConfig(dev.index, { volume: v / 100.0 });
    });

    const muteBtn = card.querySelector(`#mute-btn-${dev.index}`);
    muteBtn.addEventListener('click', () => {
      dev.muted = !dev.muted;
      muteBtn.classList.toggle('muted', dev.muted);
      updateDeviceConfig(dev.index, { muted: dev.muted });
    });

    const delaySlider = card.querySelector(`#delay-slider-${dev.index}`);
    const delayVal = card.querySelector(`#delay-val-${dev.index}`);
    delaySlider.addEventListener('input', (e) => {
      const ms = parseInt(e.target.value, 10);
      delayVal.textContent = `${ms} ms`;
      updateDeviceConfig(dev.index, { delay_ms: ms });
    });

    const panSlider = card.querySelector(`#pan-slider-${dev.index}`);
    const panVal = card.querySelector(`#pan-val-${dev.index}`);
    panSlider.addEventListener('input', (e) => {
      const p = parseInt(e.target.value, 10);
      panVal.textContent = p === 0 ? 'Center' : (p < 0 ? `L ${Math.abs(p)}%` : `R ${p}%`);
      updateDeviceConfig(dev.index, { pan: p / 100.0 });
    });

    const testBtn = card.querySelector(`#test-btn-${dev.index}`);
    testBtn.addEventListener('click', () => {
      triggerTestTone(dev.index);
    });

    return card;
  }

  // =========================================================================
  // Real-time VU Meter Visualizer
  // =========================================================================

  function startMeterStream() {
    if (window.EventSource) {
      try {
        eventSource = new EventSource('/api/meter_stream');
        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            updateMeters(data);
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
    if (meterPollInterval) return;
    meterPollInterval = setInterval(async () => {
      try {
        const res = await fetch('/api/meters');
        const data = await res.json();
        updateMeters(data);
      } catch (e) {}
    }, 100);
  }

  function updateMeters(data) {
    if (!data) return;

    // Master Meter
    const mLevel = data.master_level || 0.0;
    const mPercent = Math.min(100, Math.round(mLevel * 100));
    masterVuFill.style.width = `${mPercent}%`;

    if (mLevel > 0.005) {
      const db = (20 * Math.log10(Math.max(0.001, mLevel))).toFixed(1);
      masterMeterVal.textContent = `${db} dB`;
    } else {
      masterMeterVal.textContent = '-inf dB';
    }

    // Per-device meters
    const devLevels = data.device_levels || {};
    for (const [devId, level] of Object.entries(devLevels)) {
      const fillEl = document.getElementById(`meter-fill-${devId}`);
      if (fillEl) {
        const p = Math.min(100, Math.round((level || 0) * 100));
        fillEl.style.width = `${p}%`;
      }
    }
  }

  // Toast Notification
  function showToast(message) {
    toast.textContent = message;
    toast.classList.remove('hidden');
    clearTimeout(toast._timeout);
    toast._timeout = setTimeout(() => {
      toast.classList.add('hidden');
    }, 3200);
  }
});
