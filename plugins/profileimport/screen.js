// Profile Import plugin

let _piProfileId = null;

// ── Navigation hook ────────────────────────────────────────────────────
(function() {
    // Idempotency: if screen.js is re-evaluated (loader cache miss, hot reload,
    // older core builds without the load-side guard), don't re-wrap showScreen —
    // each re-wrap captures the previous wrapper, growing the chain and
    // leaking closures.
    const HOOK_KEY = '__slopsmithProfileImportHooksInstalled';
    if (window[HOOK_KEY]) return;
    window[HOOK_KEY] = true;

    const origShowScreen = window.showScreen;
    window.showScreen = function(id) {
        origShowScreen(id);
        if (id === 'plugin-profileimport') _piInit();
    };
})();

// ── Initialization ─────────────────────────────────────────────────────

function _piInit() {
    _piLoadHistory();
    _piCheckMapping();
    _piSetupDragDrop();
}

function _piSetupDragDrop() {
    const dropzone = document.getElementById('pi-dropzone');
    if (!dropzone || dropzone._piInitialized) return;
    dropzone._piInitialized = true;

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('border-accent');
    });
    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('border-accent');
    });
    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('border-accent');
        const file = e.dataTransfer.files[0];
        if (file) _piUploadFile(file);
    });

    document.getElementById('pi-file-input').addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) _piUploadFile(file);
    });
}

// ── Upload ─────────────────────────────────────────────────────────────

async function _piUploadFile(file) {
    const errorEl = document.getElementById('pi-upload-error');
    errorEl.classList.add('hidden');

    try {
        const buf = await file.arrayBuffer();
        const resp = await fetch('/api/plugins/profileimport/upload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/octet-stream', 'X-Filename': file.name },
            body: buf,
        });
        const data = await resp.json();

        if (data.error) {
            errorEl.textContent = data.error;
            errorEl.classList.remove('hidden');
            return;
        }

        _piProfileId = data.header.profile_id;
        _piShowPreview(data);
    } catch (e) {
        errorEl.textContent = 'Upload failed: ' + e.message;
        errorEl.classList.remove('hidden');
    }
}

function _piShowPreview(data) {
    document.getElementById('pi-upload-section').classList.add('hidden');
    document.getElementById('pi-preview-section').classList.remove('hidden');

    document.getElementById('pi-profile-name').textContent = data.filename || 'Profile';
    document.getElementById('pi-profile-id').textContent = 'Profile ID: ' + data.header.profile_id;

    document.getElementById('pi-stat-played').textContent = data.arrangements_played;
    document.getElementById('pi-stat-mastered').textContent = data.arrangements_mastered;
    document.getElementById('pi-stat-favorites').textContent = data.favorites_count;
    document.getElementById('pi-stat-sa').textContent = data.score_attack_played;

    const extras = [];
    if (data.total_play_count) extras.push(data.total_play_count + ' total plays');
    if (data.total_sessions) extras.push(data.total_sessions + ' sessions');
    if (data.total_session_time) extras.push(_piFormatDuration(data.total_session_time) + ' total play time');
    if (data.song_lists_count) extras.push(data.song_lists_count + ' song lists');
    document.getElementById('pi-extra-stats').textContent = extras.join(' · ');

    _piCheckMapping();
}

// ── Mapping ────────────────────────────────────────────────────────────

async function _piCheckMapping() {
    try {
        const resp = await fetch('/api/plugins/profileimport/mapping-status');
        const data = await resp.json();
        const statusEl = document.getElementById('pi-mapping-status');
        const btn = document.getElementById('pi-build-mapping-btn');
        const importBtn = document.getElementById('pi-import-btn');

        if (data.cached_mappings > 0) {
            statusEl.textContent = data.cached_mappings + ' arrangements mapped';
            btn.textContent = 'Rebuild';
            if (_piProfileId) importBtn.disabled = false;
        } else {
            statusEl.textContent = 'Not built yet — required before import';
            btn.textContent = 'Build Mapping';
            importBtn.disabled = true;
        }
    } catch (e) {
        console.error('Mapping status check failed:', e);
    }
}

function _piBuildMapping() {
    const progressEl = document.getElementById('pi-mapping-progress');
    const barEl = document.getElementById('pi-mapping-bar');
    const labelEl = document.getElementById('pi-mapping-label');
    const btn = document.getElementById('pi-build-mapping-btn');

    progressEl.classList.remove('hidden');
    btn.disabled = true;
    btn.textContent = 'Scanning...';

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(proto + '//' + location.host + '/ws/plugins/profileimport/build-mapping');

    ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);

        if (msg.error) {
            labelEl.textContent = 'Error: ' + msg.error;
            btn.disabled = false;
            btn.textContent = 'Retry';
            return;
        }

        if (msg.stage === 'scanning') {
            const pct = msg.total > 0 ? Math.round((msg.progress / msg.total) * 100) : 0;
            barEl.style.width = pct + '%';
            labelEl.textContent = msg.progress + ' / ' + msg.total + ' PSARCs scanned' +
                (msg.errors ? ' (' + msg.errors + ' errors)' : '');
        }

        if (msg.stage === 'done') {
            barEl.style.width = '100%';
            labelEl.textContent = 'Done — ' + msg.mappings + ' arrangements mapped';
            btn.disabled = false;
            btn.textContent = 'Rebuild';
            document.getElementById('pi-mapping-status').textContent = msg.mappings + ' arrangements mapped';
            if (_piProfileId) document.getElementById('pi-import-btn').disabled = false;
        }
    };

    ws.onerror = () => {
        labelEl.textContent = 'WebSocket connection failed';
        btn.disabled = false;
        btn.textContent = 'Retry';
    };
}

// ── Import ─────────────────────────────────────────────────────────────

function _piStartImport() {
    if (!_piProfileId) return;

    document.getElementById('pi-preview-section').classList.add('hidden');
    document.getElementById('pi-progress-section').classList.remove('hidden');

    const log = document.getElementById('pi-progress-log');
    log.innerHTML = '';

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(proto + '//' + location.host + '/ws/plugins/profileimport/import');

    ws.onopen = () => {
        ws.send(JSON.stringify({
            profile_id: _piProfileId,
            import_favorites: document.getElementById('pi-opt-favorites').checked,
            import_play_counts: document.getElementById('pi-opt-playcounts').checked,
            import_scores: document.getElementById('pi-opt-scores').checked,
        }));
    };

    ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);

        if (msg.error) {
            _piAddLogEntry(log, msg.error, 'error');
            return;
        }

        if (msg.stage === 'favorites') {
            _piUpdateStage(log, 'favorites', 'Favorites', msg);
        } else if (msg.stage === 'playcounts') {
            _piUpdateStage(log, 'playcounts', 'Play Counts', msg);
        } else if (msg.stage === 'scores') {
            _piUpdateStage(log, 'scores', 'Score Attack', msg);
        } else if (msg.stage === 'complete') {
            _piShowDone(msg.stats);
        }
    };

    ws.onerror = () => {
        _piAddLogEntry(log, 'Connection lost', 'error');
    };
}

function _piUpdateStage(log, stageId, label, msg) {
    let el = document.getElementById('pi-stage-' + stageId);
    if (!el) {
        el = document.createElement('div');
        el.id = 'pi-stage-' + stageId;
        el.className = 'bg-dark-600 rounded-lg p-4';
        log.appendChild(el);
    }

    if (msg.done) {
        el.innerHTML = '<div class="flex items-center gap-2">' +
            '<svg class="w-5 h-5 text-green-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>' +
            '<span class="text-sm text-gray-300">' + esc(msg.message) + '</span></div>';
    } else if (msg.total) {
        const pct = Math.round((msg.progress / msg.total) * 100);
        el.innerHTML = '<p class="text-sm text-gray-300 mb-2">' + label + '</p>' +
            '<div class="w-full bg-dark-500 rounded-full h-1.5">' +
            '<div class="bg-accent h-1.5 rounded-full" style="width:' + pct + '%"></div></div>' +
            '<p class="text-xs text-gray-500 mt-1">' + msg.progress + ' / ' + msg.total +
            (msg.matched !== undefined ? ' (' + msg.matched + ' matched)' : '') + '</p>';
    } else {
        el.innerHTML = '<div class="flex items-center gap-2">' +
            '<div class="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin"></div>' +
            '<span class="text-sm text-gray-400">' + esc(msg.message) + '</span></div>';
    }
}

function _piAddLogEntry(log, message, type) {
    const el = document.createElement('div');
    el.className = 'bg-dark-600 rounded-lg p-4';
    const color = type === 'error' ? 'text-red-400' : 'text-gray-300';
    el.innerHTML = '<span class="text-sm ' + color + '">' + esc(message) + '</span>';
    log.appendChild(el);
}

function _piShowDone(stats) {
    document.getElementById('pi-progress-section').classList.add('hidden');
    document.getElementById('pi-done-section').classList.remove('hidden');

    const parts = [];
    if (stats.favorites_imported > 0) parts.push(stats.favorites_imported + ' favorites');
    if (stats.play_counts_imported > 0) parts.push(stats.play_counts_imported + ' play records');
    if (stats.songs_matched > 0) parts.push(stats.songs_matched + ' matched to library');

    document.getElementById('pi-done-stats').textContent = parts.length > 0
        ? 'Imported: ' + parts.join(', ')
        : 'No data was imported.';

    _piLoadHistory();
}

// ── Reset ──────────────────────────────────────────────────────────────

function _piReset() {
    _piProfileId = null;
    document.getElementById('pi-upload-section').classList.remove('hidden');
    document.getElementById('pi-preview-section').classList.add('hidden');
    document.getElementById('pi-progress-section').classList.add('hidden');
    document.getElementById('pi-done-section').classList.add('hidden');
    document.getElementById('pi-file-input').value = '';
    document.getElementById('pi-upload-error').classList.add('hidden');
}

// ── History ────────────────────────────────────────────────────────────

async function _piLoadHistory() {
    try {
        const resp = await fetch('/api/plugins/profileimport/history');
        const data = await resp.json();
        const list = document.getElementById('pi-history-list');

        if (data.length === 0) {
            list.innerHTML = '<p class="text-gray-600 text-sm">No imports yet.</p>';
            return;
        }

        list.innerHTML = data.map(h => {
            const date = new Date(h.imported_at + 'Z');
            const dateStr = date.toLocaleDateString('en', { month: 'short', day: 'numeric', year: 'numeric' })
                + ' ' + date.toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' });
            const parts = [];
            if (h.favorites_imported > 0) parts.push(h.favorites_imported + ' favs');
            if (h.play_counts_imported > 0) parts.push(h.play_counts_imported + ' plays');
            if (h.songs_matched > 0) parts.push(h.songs_matched + ' matched');
            return '<div class="flex items-center justify-between py-2 px-3 bg-dark-700/30 rounded-lg">' +
                '<span class="text-xs text-gray-400">' + dateStr + '</span>' +
                '<span class="text-xs text-gray-500">' + (parts.join(', ') || 'Empty import') + '</span>' +
            '</div>';
        }).join('');
    } catch (e) {
        console.error('History load failed:', e);
    }
}

// ── Helpers ────────────────────────────────────────────────────────────

function _piFormatDuration(seconds) {
    if (seconds < 60) return Math.round(seconds) + 's';
    if (seconds < 3600) return Math.floor(seconds / 60) + 'm';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return m > 0 ? h + 'h ' + m + 'm' : h + 'h';
}
