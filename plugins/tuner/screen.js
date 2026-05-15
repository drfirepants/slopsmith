// Guitar/Bass Tuner Plugin for Slopsmith
(function() {
    const _TUNER_MIN_YIN_SAMPLES = 4096;
    const _TUNER_FRAME_SIZE = 2048;
    const _TUNER_MIN_DETECTABLE_HZ = 30;

    let enabled = false;
    let audioCtx = null;
    let sourceNode = null;
    let stream = null;
    let processor = null;
    let gainNode = null;
    let accumBuffer = new Float32Array(0);
    let pendingBuffer = null;
    let detectInterval = null;
    let refreshInterval = null;
    let lastPlayerActive = false;
    let lastSongId = null;
    let processingFrame = false;

    let uiContainer = null;
    let freqDisplay = null;
    let noteDisplay = null;
    let centsDisplay = null;
    let gaugeEl = null;
    let gaugeNeedle = null;
    let tuningSelect = null;
    let stringNoteContainer = null;
    let manualTargetFreq = null;

    let defaultTunings = {};
    let tunings = {};
    
    let selectedTuning = null;
    let selectedTuningName = "Guitar Standard";
    let showFloatingButton = true;

    let selectedDeviceId = '';
    let selectedChannel = 'mono';
    const _TUNER_STORAGE_KEY = 'slopsmith_tuner_settings';

    function loadSettings() {
        try {
            const saved = localStorage.getItem(_TUNER_STORAGE_KEY);
            if (saved) {
                const s = JSON.parse(saved);
                if (s.deviceId !== undefined) selectedDeviceId = s.deviceId;
                if (['mono', 'left', 'right'].includes(s.channel)) selectedChannel = s.channel;
            }
        } catch (e) { /* unavailable */ }
    }

    function saveSettings() {
        try {
            localStorage.setItem(_TUNER_STORAGE_KEY, JSON.stringify({
                deviceId: selectedDeviceId,
                channel: selectedChannel,
            }));
        } catch (e) { /* unavailable */ }
    }

    async function loadConfig() {
        try {
            const resp = await fetch('/api/plugins/tuner/config');
            const config = await resp.json();
            
            defaultTunings = config.defaultTunings || {};
            showFloatingButton = config.showFloatingButton !== false;

            // Rebuild tunings list
            tunings = {};
            // Add visible defaults
            Object.keys(defaultTunings).forEach(groupName => {
                const group = defaultTunings[groupName];
                Object.keys(group).forEach(name => {
                    if (!config.disabledTunings || !config.disabledTunings.includes(name)) {
                        tunings[name] = group[name];
                    }
                });
            });
            // Add custom
            if (config.customTunings) {
                Object.assign(tunings, config.customTunings);
            }

            if (config.lastTuning && tunings[config.lastTuning]) {
                selectedTuningName = config.lastTuning;
                selectedTuning = tunings[selectedTuningName];
            } else {
                // Fallback to first available if last is gone/disabled
                const first = Object.keys(tunings)[0];
                if (first) {
                    selectedTuningName = first;
                    selectedTuning = tunings[selectedTuningName];
                }
            }

        if (tuningSelect) {
            renderTuningOptions();
        }
        if (uiContainer && !uiContainer.classList.contains('hidden')) {
            renderStringNotes();
        }
            updateFloatingButtonVisibility();
        } catch (e) {
            console.error('Tuner: Failed to load config', e);
        }
    }

    function renderTuningOptions() {
        if (!tuningSelect) return;
        tuningSelect.innerHTML = '';

        // Add "Current Song" if in player
        const isPlayer = document.getElementById('player')?.classList.contains('active');
        if (isPlayer && window.highway && typeof window.highway.getSongInfo === 'function') {
            const info = window.highway.getSongInfo();
            if (info && info.tuning) {
                const sc = info.stringCount || info.tuning.length;
                const realTuning = info.tuning.slice(0, sc);
                const isBass = (info.arrangement || '').toLowerCase().includes('bass');
                const freqs = offsetsToFreqs(realTuning, isBass);
                const tName = getTuningName(realTuning);

                const name = `Current Song [${tName}]`;
                const opt = document.createElement('option');
                opt.value = '_current';
                opt.textContent = name;
                tuningSelect.appendChild(opt);

                // If this is currently selected, map it
                if (selectedTuningName === '_current') {
                    selectedTuning = freqs;
                }
            } else {
                // If song info is missing but we're in player, 
                // we might want to clear selectedTuning if it was '_current'
                if (selectedTuningName === '_current') {
                    selectedTuning = null;
                }
            }
        } else if (selectedTuningName === '_current') {
            selectedTuning = null;
        }

        for (const name in tunings) {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            tuningSelect.appendChild(opt);
        }

        if (selectedTuningName) {
            tuningSelect.value = selectedTuningName;
        }
    }

    window._tunerReloadConfig = loadConfig;

    async function saveConfig() {
        try {
            await fetch('/api/plugins/tuner/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lastTuning: selectedTuningName })
            });
        } catch (e) {
            console.error('Tuner: Failed to save config', e);
        }
    }

    function initUI() {
        if (uiContainer) return;

        loadSettings();

        uiContainer = document.createElement('div');
        uiContainer.id = 'tuner-plugin-ui';
        uiContainer.className = 'fixed bottom-20 right-5 w-72 bg-dark-800/95 border border-gray-800 rounded-xl p-4 text-white z-[1000] hidden flex-col items-center shadow-2xl backdrop-blur-md';

        const header = document.createElement('div');
        header.className = 'flex justify-center items-center w-full mb-3 relative';
        
        const title = document.createElement('div');
        title.className = 'font-bold text-xs text-gray-500 uppercase tracking-wider';
        title.textContent = 'TUNER';
        header.appendChild(title);

        const settingsBtn = document.createElement('button');
        settingsBtn.className = 'absolute right-0 text-gray-500 hover:text-white transition-colors';
        settingsBtn.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
        `;
        settingsBtn.onclick = showSettings;
        header.appendChild(settingsBtn);

        uiContainer.appendChild(header);

        tuningSelect = document.createElement('select');
        tuningSelect.className = 'w-full bg-dark-700 text-sm text-gray-200 border border-gray-800 mb-4 p-2 rounded-lg outline-none focus:border-accent transition';
        renderTuningOptions();
        tuningSelect.onchange = (e) => {
            selectedTuningName = e.target.value;
            if (selectedTuningName === '_current') {
                const info = window.highway?.getSongInfo();
                if (info) {
                    const sc = info.stringCount || info.tuning.length;
                    const realTuning = info.tuning.slice(0, sc);
                    const isBass = (info.arrangement || '').toLowerCase().includes('bass');
                    selectedTuning = offsetsToFreqs(realTuning, isBass);
                } else {
                    selectedTuning = null;
                }
            } else {
                selectedTuning = tunings[selectedTuningName];
            }
            manualTargetFreq = null;
            renderStringNotes();
            if (selectedTuningName !== '_current') saveConfig();
        };
        uiContainer.appendChild(tuningSelect);

        stringNoteContainer = document.createElement('div');
        stringNoteContainer.className = 'flex justify-between w-full mb-4 gap-1';
        uiContainer.appendChild(stringNoteContainer);
        renderStringNotes();

        noteDisplay = document.createElement('div');
        noteDisplay.className = 'text-5xl font-black my-2 h-16 flex items-center justify-center';
        noteDisplay.textContent = '--';
        uiContainer.appendChild(noteDisplay);

        freqDisplay = document.createElement('div');
        freqDisplay.className = 'text-xs text-gray-500 mb-3 font-mono';
        freqDisplay.textContent = '0.0 Hz';
        uiContainer.appendChild(freqDisplay);

        // Gauge
        gaugeEl = document.createElement('div');
        gaugeEl.className = 'w-full h-2.5 bg-dark-900 border border-gray-800 rounded-full relative overflow-hidden mb-1.5';
        
        const centerMarker = document.createElement('div');
        centerMarker.className = 'absolute left-1/2 top-0 bottom-0 w-0.5 bg-accent z-10';
        gaugeEl.appendChild(centerMarker);

        gaugeNeedle = document.createElement('div');
        gaugeNeedle.className = 'absolute left-1/2 top-0 bottom-0 w-1 bg-white transition-all duration-100 ease-out -translate-x-1/2 z-20 shadow-[0_0_8px_rgba(255,255,255,0.5)]';
        gaugeEl.appendChild(gaugeNeedle);
        
        uiContainer.appendChild(gaugeEl);

        centsDisplay = document.createElement('div');
        centsDisplay.className = 'text-sm font-bold tracking-tight';
        centsDisplay.textContent = '0 cents';
        uiContainer.appendChild(centsDisplay);

        const closeBtn = document.createElement('button');
        closeBtn.className = 'mt-5 w-full bg-dark-700 hover:bg-dark-600 border border-gray-800 text-gray-300 text-xs py-2 rounded-lg transition-colors uppercase font-semibold tracking-wide';
        closeBtn.textContent = 'Close';
        closeBtn.onclick = disable;
        uiContainer.appendChild(closeBtn);

        document.body.appendChild(uiContainer);
    }

    // ── Settings ──────────────────────────────────────────────────────
    function showSettings() {
        let panel = uiContainer.querySelector('.tuner-settings-panel');
        if (panel) { panel.remove(); return; }

        panel = document.createElement('div');
        panel.className = 'tuner-settings-panel w-full bg-dark-700/50 border border-gray-800 rounded-lg p-3 mb-4 text-xs';
        panel.innerHTML = `
            <div class="flex justify-between items-center mb-2">
                <span class="text-gray-400 font-semibold uppercase tracking-tighter">Audio Settings</span>
                <button class="tuner-settings-close text-gray-500 hover:text-white">&times;</button>
            </div>

            <label class="block text-gray-500 mb-1">Microphone</label>
            <select class="tuner-device-select w-full bg-dark-800 border border-gray-700 rounded px-2 py-1 text-gray-200 mb-2 outline-none focus:border-accent">
                <option value="">Default</option>
            </select>

            <label class="block text-gray-500 mb-1">Input Channel</label>
            <select class="tuner-channel-select w-full bg-dark-800 border border-gray-700 rounded px-2 py-1 text-gray-200 outline-none focus:border-accent">
                <option value="mono" ${selectedChannel === 'mono' ? 'selected' : ''}>Mono (mix both)</option>
                <option value="left" ${selectedChannel === 'left' ? 'selected' : ''}>Left (Channel 1)</option>
                <option value="right" ${selectedChannel === 'right' ? 'selected' : ''}>Right (Channel 2)</option>
            </select>
        `;

        // Insert above tuningSelect
        uiContainer.insertBefore(panel, tuningSelect);

        panel.querySelector('.tuner-settings-close').onclick = () => panel.remove();
        panel.querySelector('.tuner-device-select').onchange = (e) => {
            selectedDeviceId = e.target.value;
            saveSettings();
            if (enabled) restartAudio();
        };
        panel.querySelector('.tuner-channel-select').onchange = (e) => {
            selectedChannel = e.target.value;
            saveSettings();
            if (enabled) restartAudio();
        };

        populateDevices(panel);
    }

    async function populateDevices(panel) {
        try {
            const devices = await navigator.mediaDevices.enumerateDevices();
            const sel = panel.querySelector('.tuner-device-select');
            if (!sel) return;
            sel.innerHTML = '<option value="">Default</option>';
            for (const d of devices) {
                if (d.kind !== 'audioinput') continue;
                const opt = document.createElement('option');
                opt.value = d.deviceId;
                opt.textContent = d.label || `Input ${d.deviceId.slice(0, 8)}`;
                if (d.deviceId === selectedDeviceId) opt.selected = true;
                sel.appendChild(opt);
            }
        } catch (e) { /* permission not yet granted */ }
    }

    async function restartAudio() {
        const wasEnabled = enabled;
        disable();
        if (wasEnabled) await enable();
    }

    async function enable() {
        if (enabled) return;
        await loadConfig();
        
        // Refresh options in case we entered/exited player since last load
        lastPlayerActive = !!document.getElementById('player')?.classList.contains('active');
        lastSongId = window.highway?.getSongInfo()?.filename || null;

        // Auto-select "Current Song" if in player
        if (lastPlayerActive) {
            selectedTuningName = '_current';
        }

        renderTuningOptions();
        // If we were on 'Current Song' but it's gone now, fallback
        if (selectedTuningName === '_current' && (!tuningSelect || !tuningSelect.querySelector('option[value="_current"]'))) {
             selectedTuningName = Object.keys(tunings)[0];
             selectedTuning = tunings[selectedTuningName];
             if (tuningSelect) renderTuningOptions();
        }

        initUI();
        if (selectedTuning) renderStringNotes();
        uiContainer.classList.remove('hidden');
        uiContainer.classList.add('flex');

        if (!refreshInterval) {
            refreshInterval = setInterval(() => {
                const isPlayer = !!document.getElementById('player')?.classList.contains('active');
                const songInfo = window.highway?.getSongInfo();
                const songId = songInfo?.filename || null;

                if (isPlayer !== lastPlayerActive || songId !== lastSongId) {
                    const wasPlayer = lastPlayerActive;
                    lastPlayerActive = isPlayer;
                    lastSongId = songId;
                    
                    const wasCurrent = selectedTuningName === '_current';

                    // Auto-select current if we just entered player
                    if (isPlayer && !wasPlayer) {
                        selectedTuningName = '_current';
                    }

                    renderTuningOptions();
                    
                if (wasCurrent) {
                    if (tuningSelect.querySelector('option[value="_current"]')) {
                        // Still available, update tuning ref (might have changed arrangement/song)
                        const sc = songInfo.stringCount || songInfo.tuning.length;
                        const realTuning = songInfo.tuning.slice(0, sc);
                        const isBass = (songInfo.arrangement || '').toLowerCase().includes('bass');
                        selectedTuning = offsetsToFreqs(realTuning, isBass);
                    } else {
                        // Gone, fallback
                        selectedTuningName = Object.keys(tunings)[0];
                        selectedTuning = tunings[selectedTuningName];
                        tuningSelect.value = selectedTuningName;
                    }
                    renderStringNotes();
                }
                }
            }, 1000);
        }

        try {
            const constraints = {
                audio: {
                    echoCancellation: false,
                    noiseSuppression: false,
                    autoGainControl: false,
                    channelCount: 2,
                }
            };
            if (selectedDeviceId) {
                constraints.audio.deviceId = { exact: selectedDeviceId };
            }

            stream = await navigator.mediaDevices.getUserMedia(constraints);

            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            sourceNode = audioCtx.createMediaStreamSource(stream);
            const streamChannels = sourceNode.channelCount;

            gainNode = audioCtx.createGain();
            gainNode.gain.value = 1.0;

            if (streamChannels >= 2 && selectedChannel !== 'mono') {
                const splitterNode = audioCtx.createChannelSplitter(2);
                sourceNode.connect(splitterNode);
                const mergerNode = audioCtx.createChannelMerger(1);
                const chIdx = selectedChannel === 'left' ? 0 : 1;
                splitterNode.connect(mergerNode, chIdx, 0);
                mergerNode.connect(gainNode);
            } else {
                sourceNode.connect(gainNode);
            }

            processor = audioCtx.createScriptProcessor(_TUNER_FRAME_SIZE, 1, 1);
            processor.onaudioprocess = (e) => {
                const input = e.inputBuffer.getChannelData(0);
                const combined = new Float32Array(accumBuffer.length + input.length);
                combined.set(accumBuffer);
                combined.set(input, accumBuffer.length);
                
                if (combined.length >= _TUNER_MIN_YIN_SAMPLES) {
                    pendingBuffer = combined.slice(combined.length - _TUNER_MIN_YIN_SAMPLES);
                    accumBuffer = new Float32Array(0);
                } else {
                    accumBuffer = combined;
                }
            };

            gainNode.connect(processor);
            processor.connect(audioCtx.destination);

            detectInterval = setInterval(() => {
                if (processingFrame || !pendingBuffer) return;
                const buf = pendingBuffer;
                pendingBuffer = null;
                processingFrame = true;
                
                const result = _tunerYinDetect(buf, audioCtx.sampleRate);
                updateUI(result);
                processingFrame = false;
            }, 50);

            enabled = true;
            if (window.tuner && window.tuner.updateButtons) window.tuner.updateButtons();
        } catch (e) {
            console.error('Tuner: Failed to start audio', e);
            alert('Tuner: Could not access microphone.');
            disable();
        }
    }

    function disable() {
        enabled = false;
        if (uiContainer) {
            uiContainer.classList.add('hidden');
            uiContainer.classList.remove('flex');
        }
        if (detectInterval) { clearInterval(detectInterval); detectInterval = null; }
        if (refreshInterval) { clearInterval(refreshInterval); refreshInterval = null; }
        if (processor) { processor.disconnect(); processor = null; }
        if (gainNode) { gainNode.disconnect(); gainNode = null; }
        if (sourceNode) { sourceNode.disconnect(); sourceNode = null; }
        if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
        if (audioCtx) { audioCtx.close(); audioCtx = null; }
        if (window.tuner && window.tuner.updateButtons) window.tuner.updateButtons();
    }

    function _tunerYinDetect(buffer, sampleRate) {
        const threshold = 0.15;
        const halfLen = Math.floor(buffer.length / 2);
        const yinBuffer = new Float32Array(halfLen);

        let runningSum = 0;
        yinBuffer[0] = 1;
        for (let tau = 1; tau < halfLen; tau++) {
            let sum = 0;
            for (let i = 0; i < halfLen; i++) {
                const delta = buffer[i] - buffer[i + tau];
                sum += delta * delta;
            }
            yinBuffer[tau] = sum;
            runningSum += sum;
            yinBuffer[tau] *= tau / runningSum;
        }

        let tau = 2;
        while (tau < halfLen) {
            if (yinBuffer[tau] < threshold) {
                while (tau + 1 < halfLen && yinBuffer[tau + 1] < yinBuffer[tau]) tau++;
                break;
            }
            tau++;
        }
        if (tau === halfLen) return null;

        const s0 = yinBuffer[tau - 1];
        const s1 = yinBuffer[tau];
        const s2 = tau + 1 < halfLen ? yinBuffer[tau + 1] : yinBuffer[tau];
        const betterTau = tau + (s0 - s2) / (2 * (s0 - 2 * s1 + s2));

        const freq = sampleRate / betterTau;
        const confidence = 1 - yinBuffer[tau];
        return { freq, confidence };
    }

    function freqToMidi(f) {
        return 69 + 12 * Math.log2(f / 440);
    }

    const noteNames = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
    function midiToNote(m) {
        const rounded = Math.round(m);
        return noteNames[rounded % 12];
    }

    function midiToFreq(m) {
        return Math.pow(2, (m - 69) / 12) * 440;
    }

    function offsetsToFreqs(offsets, isBass) {
        // E Standard base (MIDI notes)
        // Guitar: E2, A2, D3, G3, B3, E4
        const guitarBase = [40, 45, 50, 55, 59, 64];
        // Bass: E1, A1, D2, G2
        const bassBase = [28, 33, 38, 43];

        const base = isBass ? bassBase : guitarBase;
        return offsets.map((offset, i) => {
            if (i >= base.length) return midiToFreq(base[base.length - 1] + offset);
            return midiToFreq(base[i] + offset);
        });
    }

    function getTuningName(offsets) {
        if (!offsets || offsets.length === 0) return 'Unknown';

        // All pattern checks are gated on len == 6 (Guitar) or len == 4 (Bass).
        const len = offsets.length;
        if (len !== 6 && len !== 4) return offsets.join(' ');

        // Standard tunings (all strings same offset)
        const standard = {
            0: "E Standard", "-1": "Eb Standard", "-2": "D Standard",
            "-3": "C# Standard", "-4": "C Standard", "-5": "B Standard",
            "-6": "Bb Standard", "-7": "A Standard",
            "1": "F Standard", "2": "F# Standard",
        };

        if (offsets.every(o => o === offsets[0])) {
            return standard[offsets[0]] || offsets.join(' ');
        }

        // Drop tunings (low string 2 semitones below the rest)
        if (offsets[0] === offsets[1] - 2 && offsets.slice(1).every(o => o === offsets[1])) {
            const noteNames = ["E", "F", "F#", "G", "Ab", "A", "Bb", "B", "C", "C#", "D", "Eb"];
            let idx = (offsets[0] + (len === 4 ? 4 : 0)) % 12; // Bass E is offsets[0] relative to E1
            if (idx < 0) idx += 12;
            return `Drop ${noteNames[idx]}`;
        }

        // Common named tunings (6-string only)
        if (len === 6) {
            const named = {
                "-2,0,0,0,0,0": "Drop D",
                "-4,-2,-2,-2,-2,-2": "Drop C",
                "-2,-2,0,0,0,0": "Double Drop D",
                "0,0,0,-1,0,0": "Open G",
                "-2,-2,0,0,-2,-2": "Open D",
                "-2,0,0,0,-2,0": "DADGAD",
                "0,2,2,1,0,0": "Open E",
                "-2,0,0,2,3,2": "Open D (alt)",
            };
            const key = offsets.join(',');
            if (named[key]) return named[key];
        }

        return offsets.join(' ');
    }

    function renderStringNotes() {
        if (!stringNoteContainer) return;
        stringNoteContainer.innerHTML = '';
        if (!selectedTuning) return;
        selectedTuning.forEach(f => {
            const btn = document.createElement('button');
            btn.dataset.freq = f;
            btn.className = 'flex-1 py-1.5 text-xs font-bold rounded bg-dark-700 text-gray-400 border border-gray-800 hover:border-gray-600 transition-colors';
            btn.textContent = midiToNote(freqToMidi(f));
            btn.onclick = () => {
                if (manualTargetFreq === f) {
                    manualTargetFreq = null; // Toggle off if clicked again
                } else {
                    manualTargetFreq = f;
                }
                // Visual feedback immediately
                Array.from(stringNoteContainer.children).forEach(b => {
                    const bFreq = parseFloat(b.dataset.freq);
                    if (Math.abs(bFreq - manualTargetFreq) < 0.1) {
                        b.className = 'flex-1 py-1.5 text-xs font-bold rounded bg-accent text-white border border-accent transition-colors';
                    } else {
                        b.className = 'flex-1 py-1.5 text-xs font-bold rounded bg-dark-700 text-gray-400 border border-gray-800 hover:border-gray-600 transition-colors';
                    }
                });
            };
            stringNoteContainer.appendChild(btn);
        });
    }

    function updateUI(result) {
        if (!result || result.confidence < 0.8 || result.freq < _TUNER_MIN_DETECTABLE_HZ) {
            // No strong signal
            return;
        }

        const freq = result.freq;
        freqDisplay.textContent = freq.toFixed(1) + ' Hz';

        let targetFreq;
        let isManual = false;
        if (manualTargetFreq) {
            targetFreq = manualTargetFreq;
            isManual = true;
        } else {
            // Find closest string in selected tuning
            targetFreq = selectedTuning[0];
            let minDiff = Math.abs(freq - targetFreq);
            for (let i = 1; i < selectedTuning.length; i++) {
                const diff = Math.abs(freq - selectedTuning[i]);
                if (diff < minDiff) {
                    minDiff = diff;
                    targetFreq = selectedTuning[i];
                }
            }
        }

        const targetMidi = freqToMidi(targetFreq);
        const actualMidi = freqToMidi(freq);
        const cents = (actualMidi - targetMidi) * 100;

        noteDisplay.textContent = midiToNote(targetMidi);
        centsDisplay.textContent = (cents > 0 ? '+' : '') + cents.toFixed(0) + ' cents';
        
        // Update string note highlighting
        Array.from(stringNoteContainer.children).forEach(btn => {
            const btnFreq = parseFloat(btn.dataset.freq);
            if (Math.abs(btnFreq - targetFreq) < 0.1) {
                if (isManual) {
                    // Full highlight for manual selection
                    btn.className = 'flex-1 py-1.5 text-xs font-bold rounded bg-accent text-white border border-accent transition-colors';
                } else {
                    // Border only for estimated
                    btn.className = 'flex-1 py-1.5 text-xs font-bold rounded bg-dark-700 text-accent border border-accent transition-colors';
                }
            } else {
                btn.className = 'flex-1 py-1.5 text-xs font-bold rounded bg-dark-700 text-gray-400 border border-gray-800 hover:border-gray-600 transition-colors';
            }
        });

        // Update gauge
        const gaugeRange = 50; // cents
        const percent = 50 + (cents / gaugeRange) * 50;
        const constrained = Math.max(0, Math.min(100, percent));
        gaugeNeedle.style.left = constrained + '%';

        if (Math.abs(cents) < 5) {
            noteDisplay.className = 'text-5xl font-black my-2 h-16 flex items-center justify-center text-green-400';
            gaugeNeedle.className = 'absolute left-1/2 top-0 bottom-0 w-1 bg-green-400 transition-all duration-100 ease-out -translate-x-1/2 z-20 shadow-[0_0_8px_rgba(74,222,128,0.5)]';
        } else {
            noteDisplay.className = 'text-5xl font-black my-2 h-16 flex items-center justify-center text-white';
            gaugeNeedle.className = 'absolute left-1/2 top-0 bottom-0 w-1 bg-white transition-all duration-100 ease-out -translate-x-1/2 z-20 shadow-[0_0_8px_rgba(255,255,255,0.5)]';
        }
    }

    // Add to slopsmith menu or shortcut
    // For now, we'll just expose it to window so it can be called
    window.tuner = {
        enable,
        disable,
        toggle: () => enabled ? disable() : enable(),
        updateButtons: () => {
            updateFloatingButton();
            updatePlayerButton();
            updateFloatingButtonVisibility();
        }
    };

    function updateFloatingButtonVisibility() {
        const btn = document.getElementById('tuner-toggle-btn');
        if (!btn) return;
        
        const isPlayer = document.querySelector('.screen.active')?.id === 'player';
        const isPlaying = window.slopsmith?.isPlaying;

        if (!showFloatingButton || isPlayer || isPlaying) {
            btn.classList.add('hidden');
        } else {
            btn.classList.remove('hidden');
        }
    }

    function updateFloatingButton() {
        const btn = document.getElementById('tuner-toggle-btn');
        if (!btn) return;
        const baseClasses = enabled
            ? 'fixed bottom-5 right-5 px-4 py-2.5 bg-green-700/40 hover:bg-green-700/60 border border-green-500/50 text-green-300 rounded-xl text-sm transition-all duration-200 active:scale-95 shadow-2xl z-[1001]'
            : 'fixed bottom-5 right-5 px-4 py-2.5 bg-dark-700 hover:bg-dark-600 border border-gray-800 text-gray-300 hover:text-white rounded-xl text-sm transition-all duration-200 active:scale-95 shadow-2xl z-[1001]';
        
        // Preserve hidden state
        const isHidden = btn.classList.contains('hidden');
        btn.className = baseClasses;
        if (isHidden) btn.classList.add('hidden');
        updateFloatingButtonVisibility();
    }

    function updatePlayerButton() {
        const btn = document.getElementById('btn-tuner-player');
        if (!btn) return;
        btn.className = enabled
            ? 'px-3 py-1.5 bg-green-700/40 hover:bg-green-700/60 rounded-lg text-xs text-green-300 transition'
            : 'px-3 py-1.5 bg-dark-600 hover:bg-dark-500 rounded-lg text-xs text-gray-400 transition';
    }

    console.log('Tuner plugin loaded. Use window.tuner.toggle() to open.');
    
    // Add a floating button to the UI
    function addButton() {
        if (document.getElementById('tuner-toggle-btn')) return;

        const btn = document.createElement('button');
        btn.id = 'tuner-toggle-btn';
        btn.textContent = 'Tuner';
        btn.title = 'Open Tuner';
        btn.onclick = window.tuner.toggle;
        document.body.appendChild(btn);
        updateFloatingButton();
        updateFloatingButtonVisibility();

        const handlePlay = () => {
            updateFloatingButtonVisibility();
            if (enabled) {
                // If tuner is open, we should probably close it to free the mic
                // and keep the UI clean during playback.
                disable();
            }
        };
        const handleStop = () => {
            updateFloatingButtonVisibility();
        };

        if (window.slopsmith) {
            window.slopsmith.on('song:play', () => handlePlay());
            window.slopsmith.on('song:pause', () => handleStop());
            window.slopsmith.on('song:ended', () => handleStop());
            window.slopsmith.on('screen:changed', (e) => {
                if (e.detail.id === 'player') {
                    handlePlay();
                    injectPlayerButton();
                } else {
                    handleStop();
                }
            });

            // Initial state check
            if (window.slopsmith.isPlaying || document.querySelector('.screen.active')?.id === 'player') {
                handlePlay();
                if (document.querySelector('.screen.active')?.id === 'player') injectPlayerButton();
            } else {
                updateFloatingButtonVisibility();
            }
        }
    }

    function injectPlayerButton() {
        const controls = document.getElementById('player-controls');
        if (!controls || document.getElementById('btn-tuner-player')) return;

        const closeBtn = controls.querySelector('button:last-child');
        const btn = document.createElement('button');
        btn.id = 'btn-tuner-player';
        btn.textContent = 'Tuner';
        btn.title = 'Open Tuner';
        btn.onclick = window.tuner.toggle;
        if (closeBtn) controls.insertBefore(btn, closeBtn);
        else controls.appendChild(btn);
        updatePlayerButton();
    }

    addButton();

})();
