// Base Game Song Extractor plugin

(function() {
    // Idempotency: if screen.js is re-evaluated (loader cache miss, hot reload,
    // older core builds without the load-side guard), don't re-wrap showScreen —
    // each re-wrap captures the previous wrapper, growing the chain and
    // leaking closures.
    const HOOK_KEY = '__slopsmithDiscExtractHooksInstalled';
    if (window[HOOK_KEY]) return;
    window[HOOK_KEY] = true;

    const origShowScreen = window.showScreen;
    window.showScreen = function(id) {
        origShowScreen(id);
        if (id === 'plugin-disc_extract') discLoadStatus();
    };
})();

async function discLoadStatus() {
    const status = document.getElementById('disc-status');
    const songs = document.getElementById('disc-songs');
    document.getElementById('disc-progress').classList.add('hidden');
    document.getElementById('disc-result').classList.add('hidden');

    status.innerHTML = '<p class="text-gray-500 text-sm">Loading...</p>';

    try {
        const resp = await fetch('/api/plugins/disc_extract/status');
        const data = await resp.json();

        if (data.error) {
            status.innerHTML = `<p class="text-red-400 text-sm">${data.error}</p>`;
            return;
        }

        if (!data.has_songs_psarc) {
            status.innerHTML = `
                <div class="bg-yellow-900/20 border border-yellow-800/30 rounded-xl p-4 text-sm">
                    <p class="text-yellow-400 font-semibold">songs.psarc not found</p>
                    <p class="text-gray-400 mt-1">The Rocksmith install directory needs to be accessible. Make sure the Rocksmith2014 folder is mounted at /rocksmith in Docker.</p>
                </div>`;
            songs.innerHTML = '';
            return;
        }

        const extractedCount = data.extracted_count || 0;
        const totalCount = data.song_count || 0;
        const remaining = totalCount - extractedCount;

        status.innerHTML = `
            <div class="bg-dark-700/50 border border-gray-800/50 rounded-xl p-3 text-xs text-gray-500 flex items-center justify-between">
                <span>Rocksmith found at: ${esc(data.rs_dir)}</span>
                <span>${extractedCount}/${totalCount} songs extracted</span>
            </div>`;

        if (!data.songs || data.songs.length === 0) {
            songs.innerHTML = '<p class="text-gray-500 text-sm">No songs found in songs.psarc.</p>';
            return;
        }

        songs.innerHTML = `
            <div class="bg-dark-700 border border-gray-800 rounded-xl p-5">
                <div class="flex items-center justify-between mb-4">
                    <div>
                        <h3 class="text-lg font-semibold text-white">Base Game Songs</h3>
                        <p class="text-xs text-gray-500">${totalCount} songs &middot; songs.psarc</p>
                    </div>
                    ${remaining > 0 ? `
                        <button onclick="discExtract()"
                            class="bg-accent hover:bg-accent-light px-5 py-2 rounded-xl text-sm font-semibold text-white transition">
                            Extract ${remaining === totalCount ? 'All' : remaining + ' Remaining'}
                        </button>
                    ` : `
                        <span class="text-green-400 text-sm font-semibold">All Extracted</span>
                    `}
                </div>
                <div class="max-h-80 overflow-y-auto space-y-1">
                    ${data.songs.map(s => `
                        <div class="flex items-center justify-between py-1.5 px-3 rounded-lg hover:bg-dark-600/50 text-sm">
                            <div class="min-w-0">
                                <span class="text-white">${esc(s.title)}</span>
                                <span class="text-gray-500 ml-2">${esc(s.artist)}</span>
                            </div>
                            <div class="flex items-center gap-3 flex-shrink-0">
                                <span class="text-xs text-gray-600">${s.arrangements.join(', ')}</span>
                                ${s.extracted ? '<span class="text-xs text-green-600">extracted</span>' : ''}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>`;
    } catch (e) {
        status.innerHTML = `<p class="text-red-400 text-sm">Failed to load: ${e}</p>`;
    }
}

function discExtract() {
    document.getElementById('disc-songs').classList.add('hidden');
    document.getElementById('disc-progress').classList.remove('hidden');
    document.getElementById('disc-result').classList.add('hidden');
    document.getElementById('disc-bar').style.width = '0%';
    document.getElementById('disc-stage').textContent = 'Connecting...';

    const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws/plugins/disc_extract/extract`);
    ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.progress !== undefined)
            document.getElementById('disc-bar').style.width = msg.progress + '%';
        if (msg.stage)
            document.getElementById('disc-stage').textContent = msg.stage;
        if (msg.done) {
            document.getElementById('disc-progress').classList.add('hidden');
            document.getElementById('disc-result').classList.remove('hidden');
            document.getElementById('disc-result').innerHTML = `
                <div class="bg-green-900/20 border border-green-800/30 rounded-xl p-5 text-center">
                    <p class="text-green-400 font-semibold text-lg mb-1">Extraction Complete!</p>
                    <p class="text-gray-400">${msg.total} songs extracted to your DLC folder</p>
                    <button onclick="discLoadStatus()" class="mt-4 px-4 py-2 bg-dark-600 hover:bg-dark-500 rounded-xl text-sm text-gray-300 transition">Back</button>
                </div>`;
        }
        if (msg.error) {
            document.getElementById('disc-progress').classList.add('hidden');
            document.getElementById('disc-result').classList.remove('hidden');
            document.getElementById('disc-result').innerHTML = `
                <div class="bg-red-900/20 border border-red-800/30 rounded-xl p-5 text-center">
                    <p class="text-red-400 font-semibold mb-1">Extraction Failed</p>
                    <p class="text-gray-400 text-sm">${msg.error}</p>
                    <button onclick="discLoadStatus()" class="mt-4 px-4 py-2 bg-dark-600 hover:bg-dark-500 rounded-xl text-sm text-gray-300 transition">Back</button>
                </div>`;
        }
    };
    ws.onerror = () => {
        document.getElementById('disc-stage').textContent = 'Connection lost';
    };
}
