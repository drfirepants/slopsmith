// Tab Import plugin

let _tiTmpPath = null;

// ── Drop zone ───────────────────────────────────────────────────────────
(function() {
    // Wait for DOM to have the elements
    setTimeout(() => {
        const dropzone = document.getElementById('ti-dropzone');
        const fileInput = document.getElementById('ti-file-input');
        if (!dropzone || !fileInput) return;

        dropzone.addEventListener('click', () => fileInput.click());

        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('border-accent/60', 'bg-accent/5');
        });

        dropzone.addEventListener('dragleave', () => {
            dropzone.classList.remove('border-accent/60', 'bg-accent/5');
        });

        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('border-accent/60', 'bg-accent/5');
            const file = e.dataTransfer.files[0];
            if (file) tiHandleFile(file);
        });

        fileInput.addEventListener('change', () => {
            if (fileInput.files[0]) tiHandleFile(fileInput.files[0]);
        });
    }, 100);
})();

async function tiHandleFile(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['gp3', 'gp4', 'gp5'].includes(ext)) {
        alert('Only .gp3, .gp4, .gp5 files are supported.');
        return;
    }

    // Show loading state
    const dropzone = document.getElementById('ti-dropzone');
    dropzone.innerHTML = `<p class="text-gray-400 text-sm">Parsing ${esc(file.name)}...</p>`;

    // Read as base64
    const reader = new FileReader();
    reader.onload = async (e) => {
        const b64 = e.target.result.split(',')[1];
        try {
            const resp = await fetch('/api/plugins/tab_import/upload', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: file.name, data: b64 }),
            });
            const data = await resp.json();

            if (data.error) {
                dropzone.innerHTML = `<p class="text-red-400 text-sm">${data.error}</p>
                    <button onclick="tiReset()" class="mt-3 text-xs text-gray-500 hover:text-white">Try another file</button>`;
                return;
            }

            _tiTmpPath = data.tmp_path;
            tiShowParsed(data, file.name);
        } catch (err) {
            dropzone.innerHTML = `<p class="text-red-400 text-sm">Upload failed: ${err}</p>
                <button onclick="tiReset()" class="mt-3 text-xs text-gray-500 hover:text-white">Try again</button>`;
        }
    };
    reader.readAsDataURL(file);
}

function tiShowParsed(data, filename) {
    document.getElementById('ti-dropzone').classList.add('hidden');
    document.getElementById('ti-parsed').classList.remove('hidden');
    document.getElementById('ti-progress').classList.add('hidden');
    document.getElementById('ti-result').classList.add('hidden');

    document.getElementById('ti-title').value = data.title;
    document.getElementById('ti-artist').value = data.artist;
    document.getElementById('ti-album').value = data.album;

    const container = document.getElementById('ti-tracks');
    container.innerHTML = data.tracks.map(t => {
        const checked = t.is_guitar ? 'checked' : '';
        const arrOptions = ['Lead', 'Rhythm', 'Bass', 'Drums'].map(a =>
            `<option value="${a}" ${t.arrangement === a ? 'selected' : ''}>${a}</option>`
        ).join('');
        return `<div class="flex items-center gap-3 py-2 px-3 rounded-lg bg-dark-600/50">
            <input type="checkbox" data-track="${t.index}" ${checked}
                class="ti-track-check accent-accent">
            <span class="text-sm text-gray-300 flex-1">${esc(t.name)} <span class="text-gray-600">(${t.strings} strings)</span></span>
            <select data-track-arr="${t.index}" class="bg-dark-700 border border-gray-700 rounded-lg px-2 py-1 text-xs text-gray-300 outline-none">
                ${arrOptions}
            </select>
        </div>`;
    }).join('');
}

function tiUpdateYoutubeOptions() {
    const hasUrl = document.getElementById('ti-youtube').value.trim().length > 0;
    document.getElementById('ti-yt-options').classList.toggle('hidden', !hasUrl);
}

async function tiBuild() {
    if (!_tiTmpPath) return;

    const checks = document.querySelectorAll('.ti-track-check:checked');
    const trackIndices = [...checks].map(c => c.dataset.track);
    if (trackIndices.length === 0) {
        alert('Select at least one track.');
        return;
    }
    const arrangementNames = trackIndices.map(idx => {
        const sel = document.querySelector(`select[data-track-arr="${idx}"]`);
        return sel ? sel.value : 'Lead';
    });

    const title = document.getElementById('ti-title').value.trim();
    const artist = document.getElementById('ti-artist').value.trim();
    const album = document.getElementById('ti-album').value.trim();
    const youtube = document.getElementById('ti-youtube').value.trim();
    const ytStart = document.getElementById('ti-yt-start').value.trim();
    const ytEnd   = document.getElementById('ti-yt-end').value.trim();
    const alsoMidi = youtube && document.getElementById('ti-also-midi').checked;

    document.getElementById('ti-parsed').classList.add('hidden');
    document.getElementById('ti-progress').classList.remove('hidden');
    document.getElementById('ti-result').classList.add('hidden');

    const baseParams = { tmp_path: _tiTmpPath, title, artist, album,
        tracks: trackIndices.join(','), arrangement_names: arrangementNames.join(','),
        youtube_start: ytStart, youtube_end: ytEnd };

    const jobs = [{ ...baseParams, youtube_url: youtube }];
    if (alsoMidi) jobs.push({ ...baseParams, youtube_url: '' });

    const built = [];
    for (let i = 0; i < jobs.length; i++) {
        const label = jobs.length > 1 ? (i === 0 ? 'YouTube' : 'MIDI') : null;
        const ok = await tiRunBuild(jobs[i], label, i, jobs.length);
        if (!ok) return;
        built.push(ok);
    }

    document.getElementById('ti-progress').classList.add('hidden');
    document.getElementById('ti-result').classList.remove('hidden');
    document.getElementById('ti-result').innerHTML = `
        <div class="bg-green-900/20 border border-green-800/30 rounded-xl p-5 text-center">
            <p class="text-green-400 font-semibold mb-2">CDLC Created!</p>
            ${built.map(b => `<p class="text-sm text-gray-400">${esc(b.filename)}</p>
            <p class="text-xs text-gray-500 mb-2">Tracks: ${esc(b.tracks)}</p>`).join('')}
            <button onclick="tiReset()" class="mt-2 px-4 py-2 bg-dark-600 hover:bg-dark-500 rounded-xl text-sm text-gray-300 transition">Import Another</button>
        </div>`;
}

function tiRunBuild(params, label, jobIdx, totalJobs) {
    return new Promise((resolve) => {
        const progressBase = jobIdx / totalJobs * 100;
        const progressScale = 1 / totalJobs;

        const ws = new WebSocket(`ws://${location.host}/ws/plugins/tab_import/build?${new URLSearchParams(params)}`);
        ws.onmessage = (ev) => {
            const msg = JSON.parse(ev.data);
            if (msg.progress !== undefined) {
                const pct = progressBase + msg.progress * progressScale;
                document.getElementById('ti-bar').style.width = pct + '%';
            }
            if (msg.stage) {
                const prefix = label ? `[${label}] ` : '';
                document.getElementById('ti-stage').textContent = prefix + msg.stage;
            }
            if (msg.done) resolve({ filename: msg.filename, tracks: msg.tracks });
            if (msg.error) {
                document.getElementById('ti-progress').classList.add('hidden');
                document.getElementById('ti-result').classList.remove('hidden');
                document.getElementById('ti-result').innerHTML = `
                    <div class="bg-red-900/20 border border-red-800/30 rounded-xl p-5 text-center">
                        <p class="text-red-400 font-semibold mb-1">Build Failed${label ? ` (${label})` : ''}</p>
                        <p class="text-sm text-gray-400">${esc(msg.error)}</p>
                        <button onclick="tiReset()" class="mt-4 px-4 py-2 bg-dark-600 hover:bg-dark-500 rounded-xl text-sm text-gray-300 transition">Try Again</button>
                    </div>`;
                resolve(null);
            }
        };
        ws.onerror = () => {
            document.getElementById('ti-progress').classList.add('hidden');
            document.getElementById('ti-result').classList.remove('hidden');
            document.getElementById('ti-result').innerHTML = `<p class="text-red-400">Connection lost</p>
                <button onclick="tiReset()" class="mt-3 text-xs text-gray-500 hover:text-white">Try again</button>`;
            resolve(null);
        };
    });
}

function tiReset() {
    _tiTmpPath = null;
    const dropzone = document.getElementById('ti-dropzone');
    dropzone.classList.remove('hidden');
    dropzone.innerHTML = `
        <svg class="w-12 h-12 mx-auto mb-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/></svg>
        <p class="text-gray-400 text-sm mb-2">Drag and drop a Guitar Pro file here</p>
        <p class="text-gray-600 text-xs">or click to browse</p>`;
    document.getElementById('ti-file-input').value = '';
    document.getElementById('ti-youtube').value = '';
    document.getElementById('ti-yt-start').value = '';
    document.getElementById('ti-yt-end').value = '';
    document.getElementById('ti-yt-options').classList.add('hidden');
    document.getElementById('ti-parsed').classList.add('hidden');
    document.getElementById('ti-progress').classList.add('hidden');
    document.getElementById('ti-result').classList.add('hidden');
}
