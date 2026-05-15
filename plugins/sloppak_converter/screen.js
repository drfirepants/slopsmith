(function () {
    'use strict';

    /* ======================================================================
     *  Sloppak Converter Plugin — frontend
     *  Injects a "Convert" button on each PSARC library entry — both grid
     *  cards and tree-view song rows, on the main Library and the
     *  Favorites screens. Clicking it enqueues a background job on the
     *  server that runs the PSARC → sloppak pipeline (+ optional Demucs
     *  stem split), streams progress back over a WebSocket, and reloads
     *  the library when jobs finish so the new sloppak appears
     *  immediately.
     * ====================================================================== */

    const API = '/api/plugins/sloppak_converter';
    const WS_URL = (location.protocol === 'https:' ? 'wss://' : 'ws://') +
                   location.host + '/ws/plugins/sloppak_converter/events';

    // filename -> latest job state ({id, state, progress, stage, message, ...})
    const jobsByFilename = new Map();
    let demucsAvailable = false;
    let ws = null;

    // ── Button rendering ──────────────────────────────────────────────────────

    function buttonLabel(job) {
        if (!job) return 'Convert';
        switch (job.state) {
            case 'queued':    return 'Queued';
            case 'running':   return `${Math.round((job.progress || 0) * 100)}% ${job.stage || ''}`.trim();
            case 'done':      return '✓ Converted';
            case 'error':     return '! Error';
            case 'cancelled': return 'Cancelled';
            default:          return 'Convert';
        }
    }

    // Each variant gets its own base classes — cards want a full-width
    // pill under the metadata, rows want a compact pill that fits on a
    // single horizontal line. State-driven color classes are shared.
    const BUTTON_BASE_CARD = 'sloppak-convert-btn mt-2 w-full px-2 py-1.5 rounded-lg text-xs font-medium transition truncate';
    const BUTTON_BASE_ROW = 'sloppak-convert-btn ml-1 px-2 py-0.5 rounded text-[11px] font-medium transition whitespace-nowrap';

    function buttonStateClasses(job) {
        if (!job) return ' bg-purple-500/10 hover:bg-purple-500/20 border border-purple-400/30 text-purple-300';
        switch (job.state) {
            case 'running':
            case 'queued':
                return ' bg-purple-500/20 border border-purple-400/40 text-purple-200 cursor-wait';
            case 'done':
                return ' bg-green-500/15 border border-green-400/30 text-green-300';
            case 'error':
                return ' bg-red-500/15 border border-red-400/30 text-red-300';
            default:
                return ' bg-purple-500/10 hover:bg-purple-500/20 border border-purple-400/30 text-purple-300';
        }
    }

    function buttonClassesFor(job, variant) {
        const base = variant === 'row' ? BUTTON_BASE_ROW : BUTTON_BASE_CARD;
        return base + buttonStateClasses(job);
    }

    function makeButton(filename, variant) {
        const job = jobsByFilename.get(filename);
        const btn = document.createElement('button');
        btn.className = buttonClassesFor(job, variant);
        btn.dataset.sloppakFilename = filename;
        // Preserve the variant so refreshButton can rebuild the right
        // class set on every state change without re-deriving it from
        // the DOM context.
        btn.dataset.sloppakVariant = variant || 'card';
        btn.textContent = buttonLabel(job);
        btn.title = job && job.message ? job.message : 'Convert this PSARC to a .sloppak';
        btn.disabled = job && (job.state === 'queued' || job.state === 'running');
        btn.onclick = (e) => {
            e.stopPropagation();
            enqueue(filename);
        };
        return btn;
    }

    function refreshButton(btn) {
        const filename = btn.dataset.sloppakFilename;
        if (!filename) return;
        const job = jobsByFilename.get(filename);
        btn.className = buttonClassesFor(job, btn.dataset.sloppakVariant || 'card');
        btn.textContent = buttonLabel(job);
        btn.title = job && job.message ? job.message : 'Convert this PSARC to a .sloppak';
        btn.disabled = job && (job.state === 'queued' || job.state === 'running');
    }

    function refreshAllButtons() {
        document.querySelectorAll('button.sloppak-convert-btn').forEach(refreshButton);
    }

    // ── Injection into library cards + tree rows ─────────────────────────────

    function entryFilename(el) {
        try { return decodeURIComponent(el.dataset.play || ''); }
        catch (_) { return el.dataset.play || ''; }
    }

    function isPsarc(filename) {
        return filename.toLowerCase().endsWith('.psarc');
    }

    /** Strip common PSARC suffixes (_p, _m) and the .psarc extension to
     *  produce a human-readable song name suitable for accessible labels. */
    function songNameFromFilename(fn) {
        return fn.replace(/_(p|m)\.psarc$|\.psarc$/i, '');
    }

    /** Set a per-song accessible label on a bulk-selection checkbox. */
    function setCheckboxAriaLabel(cb, fn) {
        cb.setAttribute('aria-label', `Select ${songNameFromFilename(fn)} for bulk conversion`);
    }

    function injectIntoCard(card) {
        if (card.querySelector('button.sloppak-convert-btn')) return;
        const fn = entryFilename(card);
        if (!fn || !isPsarc(fn)) return;
        // Find the card body padding div (same one editBtn sits under).
        const body = card.querySelector('.p-4');
        if (!body) return;
        body.appendChild(makeButton(fn, 'card'));
    }

    function injectIntoRow(row) {
        if (row.querySelector('button.sloppak-convert-btn')) return;
        const fn = entryFilename(row);
        if (!fn || !isPsarc(fn)) return;
        // Tree rows are flex containers. The metadata badges (arrange-
        // ments, tuning, lyrics, duration) sit in a trailing
        // `flex items-center gap-1.5 flex-shrink-0 text-xs` div — we
        // append our compact button there so it sits inline at the
        // end without breaking the row layout. Falls back to row
        // append if the badge container ever changes shape.
        const tail = row.querySelector(':scope > .flex.items-center.flex-shrink-0') ||
                     row.querySelector(':scope > div:last-child') ||
                     row;
        tail.appendChild(makeButton(fn, 'row'));
    }

    function injectAll() {
        // Includes both the main Library and the Favorites trees and
        // grids — same `.song-card` / `.song-row[data-play]` markup,
        // same convert semantics. The `[data-play]` filter on rows
        // skips the one-off `.song-row` instances inside the search
        // results screen which don't carry the attribute.
        document.querySelectorAll('.song-card').forEach(injectIntoCard);
        document.querySelectorAll('.song-row[data-play]').forEach(injectIntoRow);
        // The bulk-mode injections below are no-ops outside bulk mode
        // (just bail) so they're safe to call from every render pass.
        injectBulkToggle();
        injectBulkBar();
        injectAllCheckboxes();
        refreshBulkBar();
    }

    // ── Bulk selection mode (slopsmith#107) ──────────────────────────────────
    //
    // Selection state is in-memory + sessionStorage-mirrored so a reload
    // mid-workflow doesn't lose the user's curation. NOT localStorage —
    // a day-old selection produces stale references when the user adds
    // or removes DLC, which is worse UX than a fresh start.
    const SEL_KEY = 'sloppak_converter.selection';
    const MODE_KEY = 'sloppak_converter.bulkMode';
    const selected = new Set();
    let bulkMode = false;
    let reconvertOpt = false;
    // Tracks whether the Favorites screen is currently active so
    // doConvertMissing can forward favorites=1 to the server.
    let _onFavoritesScreen = false;
    try {
        const raw = sessionStorage.getItem(SEL_KEY);
        if (raw) JSON.parse(raw).forEach(f => selected.add(f));
        bulkMode = sessionStorage.getItem(MODE_KEY) === '1';
    } catch (_) { /* private mode / quota */ }

    function persistSelection() {
        try { sessionStorage.setItem(SEL_KEY, JSON.stringify([...selected])); }
        catch (_) {}
    }
    function persistMode() {
        try { sessionStorage.setItem(MODE_KEY, bulkMode ? '1' : '0'); }
        catch (_) {}
    }

    // Inject the bulk-mode CSS exactly once.
    let bulkStyleInjected = false;
    function ensureBulkStyles() {
        if (bulkStyleInjected) return;
        bulkStyleInjected = true;
        const style = document.createElement('style');
        style.textContent = `
            body.sloppak-bulk-mode .sloppak-convert-btn { display: none !important; }
            .sloppak-card-checkbox {
                position: absolute; top: 8px; left: 8px; z-index: 10;
                width: 22px; height: 22px; cursor: pointer;
                accent-color: #c4b5fd;
            }
            .sloppak-row-checkbox {
                margin-right: 6px; cursor: pointer;
                accent-color: #c4b5fd;
            }
            .song-card.sloppak-checked {
                outline: 2px solid rgba(160, 120, 255, 0.6);
                outline-offset: -2px;
            }
            .song-row.sloppak-checked {
                background: rgba(160, 120, 255, 0.08);
            }
            #sloppak-bulk-bar {
                position: fixed; top: 0; left: 0; right: 0; z-index: 200;
                background: linear-gradient(180deg, rgba(13,13,24,0.97), rgba(13,13,24,0.92));
                border-bottom: 1px solid rgba(160, 120, 255, 0.25);
                padding: 12px 16px;
                display: none;
                gap: 8px; flex-wrap: wrap; align-items: center;
            }
            body.sloppak-bulk-mode.sloppak-on-bulk-screen #sloppak-bulk-bar { display: flex; }
            #sloppak-bulk-bar .sb-btn {
                background: rgba(160, 120, 255, 0.15);
                color: #e9d5ff;
                border: 1px solid rgba(160, 120, 255, 0.3);
                padding: 6px 12px; border-radius: 8px;
                font-size: 13px; font-weight: 500;
                cursor: pointer; transition: background 0.15s;
            }
            #sloppak-bulk-bar .sb-btn:hover { background: rgba(160, 120, 255, 0.25); }
            #sloppak-bulk-bar .sb-btn:disabled { opacity: 0.5; cursor: not-allowed; }
            #sloppak-bulk-bar .sb-btn-primary {
                background: rgba(160, 120, 255, 0.4);
                border-color: rgba(160, 120, 255, 0.6);
            }
            #sloppak-bulk-bar .sb-btn-link {
                background: transparent; border: none; color: #cbd5e1;
                text-decoration: underline; padding: 4px 6px;
            }
            #sloppak-bulk-toggle {
                background: rgba(160, 120, 255, 0.12);
                border: 1px solid rgba(160, 120, 255, 0.3);
                color: #e9d5ff;
                padding: 8px 12px; border-radius: 12px;
                font-size: 13px; cursor: pointer;
                transition: background 0.15s;
            }
            #sloppak-bulk-toggle:hover { background: rgba(160, 120, 255, 0.22); }
            #sloppak-bulk-toggle.active {
                background: rgba(160, 120, 255, 0.4);
                border-color: rgba(160, 120, 255, 0.6);
            }
        `;
        document.head.appendChild(style);
    }

    function injectBulkToggle() {
        if (document.getElementById('sloppak-bulk-toggle')) return;
        // Land next to the Filters button — most stable horizontal slot
        // in the library controls row, lives across both Library and
        // Favorites screens via the existing `flex` container at
        // index.html:72-117.
        const filtersBtn = document.getElementById('btn-lib-filters');
        if (!filtersBtn || !filtersBtn.parentNode) return;
        ensureBulkStyles();
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.id = 'sloppak-bulk-toggle';
        btn.textContent = bulkMode ? 'Selecting' : 'Select';
        btn.classList.toggle('active', bulkMode);
        btn.title = 'Bulk-select PSARCs to convert to .sloppak';
        btn.onclick = () => setBulkMode(!bulkMode);
        // Place after the Filters button.
        filtersBtn.parentNode.insertBefore(btn, filtersBtn.nextSibling);
        // Apply the body class so existing checked items render
        // correctly on first paint after reload.
        document.body.classList.toggle('sloppak-bulk-mode', bulkMode);
    }

    function setBulkMode(on) {
        bulkMode = !!on;
        persistMode();
        document.body.classList.toggle('sloppak-bulk-mode', bulkMode);
        const btn = document.getElementById('sloppak-bulk-toggle');
        if (btn) {
            btn.textContent = bulkMode ? 'Selecting' : 'Select';
            btn.classList.toggle('active', bulkMode);
        }
        // Re-run injection so checkboxes appear/disappear immediately.
        injectAllCheckboxes();
        refreshBulkBar();
    }

    function injectAllCheckboxes() {
        if (!bulkMode) {
            // Tear down any previously-injected checkboxes when leaving
            // bulk mode so the row layout reflows cleanly.
            document.querySelectorAll('.sloppak-card-checkbox, .sloppak-row-checkbox')
                .forEach(el => el.remove());
            // Drop the .sloppak-checked visual without losing the
            // selection set — re-entering bulk mode restores it.
            document.querySelectorAll('.song-card.sloppak-checked, .song-row.sloppak-checked')
                .forEach(el => el.classList.remove('sloppak-checked'));
            return;
        }
        document.querySelectorAll('.song-card').forEach(injectCheckboxIntoCard);
        document.querySelectorAll('.song-row[data-play]').forEach(injectCheckboxIntoRow);
    }

    function injectCheckboxIntoCard(card) {
        if (card.querySelector('.sloppak-card-checkbox')) return;
        const fn = entryFilename(card);
        if (!fn || !isPsarc(fn)) return;
        ensureBulkStyles();
        // Card-art is the natural mounting point — already
        // position:relative and ours can absolutely-position over the
        // album art.
        const art = card.querySelector('.card-art');
        if (!art) return;
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'sloppak-card-checkbox';
        cb.dataset.sloppakBulkFilename = fn;
        cb.checked = selected.has(fn);
        setCheckboxAriaLabel(cb, fn);
        cb.title = 'Select for bulk conversion';
        cb.onclick = (ev) => { ev.stopPropagation(); toggleSelected(fn, cb.checked); };
        // Don't let the click bubble to the card's playSong handler.
        cb.onmousedown = (ev) => ev.stopPropagation();
        art.appendChild(cb);
        if (selected.has(fn)) card.classList.add('sloppak-checked');
    }

    function injectCheckboxIntoRow(row) {
        if (row.querySelector('.sloppak-row-checkbox')) return;
        const fn = entryFilename(row);
        if (!fn || !isPsarc(fn)) return;
        ensureBulkStyles();
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'sloppak-row-checkbox';
        cb.dataset.sloppakBulkFilename = fn;
        cb.checked = selected.has(fn);
        setCheckboxAriaLabel(cb, fn);
        cb.title = 'Select for bulk conversion';
        cb.onclick = (ev) => { ev.stopPropagation(); toggleSelected(fn, cb.checked); };
        cb.onmousedown = (ev) => ev.stopPropagation();
        row.insertBefore(cb, row.firstChild);
        if (selected.has(fn)) row.classList.add('sloppak-checked');
    }

    function toggleSelected(filename, on) {
        if (on) selected.add(filename);
        else selected.delete(filename);
        persistSelection();
        // Sync the .sloppak-checked class on every visible instance —
        // a single PSARC could appear in both grid and tree if both
        // happen to be in the DOM (e.g. transition between views).
        document.querySelectorAll(`[data-sloppak-bulk-filename="${cssEscape(filename)}"]`)
            .forEach(cb => {
                cb.checked = on;
                const host = cb.closest('.song-card, .song-row');
                if (host) host.classList.toggle('sloppak-checked', on);
            });
        refreshBulkBar();
    }

    function cssEscape(s) {
        return (window.CSS && CSS.escape) ? CSS.escape(s) : s.replace(/"/g, '\\"');
    }

    function injectBulkBar() {
        if (document.getElementById('sloppak-bulk-bar')) return;
        ensureBulkStyles();
        // Mount directly on body as a position:fixed overlay so it is
        // visible on every screen (Library, Favorites, etc.) without
        // needing to track which section container is currently active.
        const bar = document.createElement('div');
        bar.id = 'sloppak-bulk-bar';
        bar.innerHTML = `
            <span id="sloppak-bulk-count" class="text-sm text-purple-200 font-medium"></span>
            <span id="sloppak-bulk-hidden" class="text-xs text-gray-400"></span>
            <button type="button" class="sb-btn sb-btn-primary" data-action="convert-selected">Convert selected</button>
            <button type="button" class="sb-btn" data-action="convert-missing">Convert all PSARCs missing a sloppak</button>
            <label class="text-xs text-gray-400 inline-flex items-center gap-1 ml-2">
                <input type="checkbox" id="sloppak-bulk-reconvert">
                Reconvert (re-convert files that already have a sloppak)
            </label>
            <span class="flex-1"></span>
            <button type="button" class="sb-btn-link" data-action="clear">Clear selection</button>
            <button type="button" class="sb-btn-link" data-action="exit">Exit</button>
        `;
        document.body.appendChild(bar);
        bar.addEventListener('click', (ev) => {
            const btn = ev.target.closest('[data-action]');
            if (!btn) return;
            const action = btn.dataset.action;
            if (action === 'convert-selected') doConvertSelected();
            else if (action === 'convert-missing') doConvertMissing();
            else if (action === 'clear') { clearSelection(); }
            else if (action === 'exit') { setBulkMode(false); }
        });
        bar.querySelector('#sloppak-bulk-reconvert').onchange = (ev) => {
            reconvertOpt = !!ev.target.checked;
        };
    }

    function refreshBulkBar() {
        const countEl = document.getElementById('sloppak-bulk-count');
        const hiddenEl = document.getElementById('sloppak-bulk-hidden');
        if (!countEl || !hiddenEl) return;
        countEl.textContent = `${selected.size} selected`;
        // Compute "not in current view" by counting selected filenames
        // that don't match any *visible* card/row.  Only include checkboxes
        // whose offsetParent is non-null so that cards in hidden tabs or
        // sections (display:none ancestors) are excluded from the tally.
        const visible = new Set();
        document.querySelectorAll('[data-sloppak-bulk-filename]')
            .forEach(cb => { if (cb.offsetParent !== null) visible.add(cb.dataset.sloppakBulkFilename); });
        let hidden = 0;
        for (const fn of selected) if (!visible.has(fn)) hidden++;
        if (hidden > 0) {
            hiddenEl.innerHTML = `· ${hidden} not in current view ` +
                `<button type="button" class="sb-btn-link" data-action="clear-hidden">Clear hidden</button>`;
            hiddenEl.querySelector('button').onclick = () => clearHiddenSelection(visible);
        } else {
            hiddenEl.textContent = '';
        }
        const convertBtn = document.querySelector('[data-action="convert-selected"]');
        if (convertBtn) {
            convertBtn.disabled = selected.size === 0;
            convertBtn.textContent = `Convert ${selected.size || ''} selected`.trim();
        }
    }

    function clearSelection() {
        selected.clear();
        persistSelection();
        document.querySelectorAll('[data-sloppak-bulk-filename]').forEach(cb => { cb.checked = false; });
        document.querySelectorAll('.song-card.sloppak-checked, .song-row.sloppak-checked')
            .forEach(el => el.classList.remove('sloppak-checked'));
        refreshBulkBar();
    }

    function clearHiddenSelection(visibleSet) {
        for (const fn of [...selected]) if (!visibleSet.has(fn)) selected.delete(fn);
        persistSelection();
        refreshBulkBar();
    }

    async function doConvertSelected() {
        if (!selected.size) return;
        const filenames = [...selected];
        try {
            const r = await fetch(`${API}/enqueue_bulk`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filenames, split: demucsAvailable, reconvert: reconvertOpt }),
            });
            if (!r.ok) {
                console.warn(`[sloppak_converter] enqueue_bulk HTTP ${r.status}`);
                alert(`Failed to enqueue: ${r.status} ${r.statusText}`);
                return;
            }
            const data = await r.json();
            announceBulkResult(data);
            // Drop only the entries we successfully enqueued — keep skipped
            // (e.g. already-converted) entries selected so the user sees
            // what's left if they hit Reconvert and retry.
            for (const e of (data.enqueued || [])) selected.delete(e.filename);
            persistSelection();
            // Sync UI checkboxes.
            for (const e of (data.enqueued || [])) {
                document.querySelectorAll(`[data-sloppak-bulk-filename="${cssEscape(e.filename)}"]`)
                    .forEach(cb => {
                        cb.checked = false;
                        const host = cb.closest('.song-card, .song-row');
                        if (host) host.classList.remove('sloppak-checked');
                    });
            }
        } catch (err) {
            console.warn('[sloppak_converter] doConvertSelected error:', err);
            alert(`Failed to enqueue: ${err.message}`);
        }
        refreshBulkBar();
    }

    async function doConvertMissing() {
        // Mirror the user's current library filters (search box + format
        // dropdown + filter-drawer state) so "missing in current view"
        // matches what they're looking at. The query-string builder
        // lives in core; we replicate the read here rather than
        // depending on a private app.js export.
        try {
            const params = new URLSearchParams();
            const q = (document.getElementById('lib-filter') || {}).value || '';
            const sort = (document.getElementById('lib-sort') || {}).value || '';
            const format = (document.getElementById('lib-format') || {}).value || '';
            const direction = (document.getElementById('lib-direction') || {}).value || '';
            if (q.trim()) params.set('q', q.trim());
            if (sort) params.set('sort', sort);
            if (direction) params.set('direction', direction);
            if (format) params.set('format', format);
            // When the user is browsing their Favorites, scope the missing-sloppak
            // query to favorites only so the queued set matches what they see.
            if (_onFavoritesScreen) params.set('favorites', '1');
            // Filter-drawer state lives in core's `_libFilters`. Forward it
            // verbatim if the helper is available.
            if (typeof window._applyLibFiltersToParams === 'function') {
                window._applyLibFiltersToParams(params);
            }
            const r = await fetch(`${API}/missing_sloppak?${params.toString()}`);
            if (!r.ok) {
                alert(`Error checking for missing sloppaks: ${r.status} ${r.statusText}`);
                return;
            }
            const data = await r.json();
            if (data.error) {
                alert(`Error: ${data.error}`);
                return;
            }
            const filenames = data.filenames || [];
            if (!filenames.length) {
                alert('No PSARCs missing a sloppak in the current view.');
                return;
            }
            if (!confirm(`Enqueue ${filenames.length} PSARCs for conversion?`)) return;
            const er = await fetch(`${API}/enqueue_bulk`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filenames, split: demucsAvailable, reconvert: reconvertOpt }),
            });
            if (!er.ok) {
                alert(`Failed to enqueue: ${er.status} ${er.statusText}`);
                return;
            }
            announceBulkResult(await er.json());
        } catch (err) {
            console.warn('[sloppak_converter] doConvertMissing error:', err);
            alert(`Failed to convert missing: ${err.message}`);
        }
    }

    function announceBulkResult(data) {
        const ok = (data.enqueued || []).length;
        const skip = (data.skipped || []).length;
        const reasons = {};
        for (const s of (data.skipped || [])) reasons[s.reason] = (reasons[s.reason] || 0) + 1;
        const skipDetail = Object.entries(reasons).map(([k, v]) => `${v} ${k.replace(/_/g, ' ')}`).join(', ');
        const msg = `${ok} enqueued${skip ? ` · ${skip} skipped (${skipDetail})` : ''}`;
        // Soft toast via the existing progress panel container —
        // floating bottom-right anyway. Falls back to console if the
        // panel isn't ready yet.
        // Only force the panel visible when there are actually new jobs;
        // if everything was skipped we append the banner without
        // overriding the user's dismiss intent.
        try {
            const p = ensurePanel();
            const banner = document.createElement('div');
            banner.style.cssText = 'color:#a78bfa; font-weight:500; padding:6px 0;';
            banner.textContent = msg;
            if (ok > 0) {
                panelDismissed = false;
            }
            // Always show the panel so skipped-only results ("all already
            // converted") are visible rather than silently disappearing.
            p.style.display = 'block';
            p.appendChild(banner);
            setTimeout(() => banner.remove(), 4000);
        } catch (_) { console.info('[sloppak_converter]', msg); }
    }
    // Expose for the queue dashboard's "Open queue" deeplink to also
    // be able to trigger Convert if needed.
    window.sloppakConverterBulk = {
        getSelected: () => [...selected],
        setBulkMode,
        clearSelection,
    };

    // Watch for library re-renders. We only re-inject on childList changes;
    // refreshing button text is done via WS events, not on every mutation,
    // otherwise each textContent update would retrigger the observer.
    let injectPending = false;
    function startObserver() {
        // Observe at the document level so we pick up both the
        // Library (`#lib-grid` / `#lib-tree`) and Favorites
        // (`#fav-grid` / `#fav-tree`) re-renders without needing to
        // attach an observer to each one individually. The RAF
        // coalesce keeps the cost negligible — we run injectAll at
        // most once per frame regardless of mutation burst size.
        const obs = new MutationObserver((mutations) => {
            // Ignore mutations that are purely attribute/text changes on our own buttons.
            let structural = false;
            for (const m of mutations) {
                if (m.type === 'childList' && (m.addedNodes.length || m.removedNodes.length)) {
                    structural = true;
                    break;
                }
            }
            if (!structural || injectPending) return;
            injectPending = true;
            requestAnimationFrame(() => {
                injectPending = false;
                injectAll();
                checkConvDashboardMount();
            });
        });
        obs.observe(document.body, { childList: true, subtree: true });
        injectAll();
    }

    // ── API calls ─────────────────────────────────────────────────────────────

    async function enqueue(filename) {
        try {
            const r = await fetch(`${API}/enqueue`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename, split: demucsAvailable }),
            });
            const data = await r.json();
            if (data.error) {
                console.warn('[sloppak_converter] enqueue failed:', data.error);
            }
        } catch (e) {
            console.warn('[sloppak_converter] enqueue error:', e);
        }
    }

    // ── Progress panel ────────────────────────────────────────────────────────

    let panel = null;
    // Dismiss the floating progress panel for the current job set. Reset
    // automatically when a new job lands so the user gets feedback for
    // fresh work without losing the dismiss for the current batch.
    let panelDismissed = false;

    function ensurePanel() {
        if (panel) return panel;
        panel = document.createElement('div');
        panel.id = 'sloppak-converter-panel';
        panel.style.cssText = `
            position: fixed; right: 16px; bottom: 16px; z-index: 9999;
            min-width: 260px; max-width: 340px;
            max-height: calc(100vh - 32px);
            background: linear-gradient(145deg, #13132a 0%, #0d0d18 100%);
            border: 1px solid rgba(160, 120, 255, 0.25);
            border-radius: 12px; padding: 10px 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
            font-size: 12px; color: #cbd5e1;
            display: none; flex-direction: column;
        `;
        document.body.appendChild(panel);
        panel.addEventListener('click', (ev) => {
            const open = ev.target.closest('[data-sloppak-panel-open]');
            if (open) {
                ev.preventDefault();
                if (typeof window.showScreen === 'function') {
                    window.showScreen('plugin-sloppak_converter');
                }
                return;
            }
            if (ev.target.closest('[data-sloppak-panel-dismiss]')) {
                panelDismissed = true;
                renderPanel();
            }
        });
        return panel;
    }

    const RECENT_TTL_MS = 6000;

    function renderPanel() {
        const now = Date.now() / 1000;
        const active = [...jobsByFilename.values()].filter(j =>
            j.state === 'queued' || j.state === 'running'
        );
        // Only keep recently-finished jobs visible for a few seconds.
        const recent = [...jobsByFilename.values()].filter(j =>
            (j.state === 'done' || j.state === 'error') &&
            j.finished_at && (now - j.finished_at) * 1000 < RECENT_TTL_MS
        ).slice(-3);

        const p = ensurePanel();
        if (active.length === 0 && recent.length === 0) {
            p.style.display = 'none';
            return;
        }
        if (panelDismissed) {
            p.style.display = 'none';
            return;
        }
        p.style.display = 'flex';

        const header = `<div style="display:flex;align-items:center;justify-content:space-between;gap:6px;margin-bottom:6px;flex:0 0 auto;">
                       <span style="font-weight:600;color:#c4b5fd;">Sloppak converter</span>
                       <span style="display:flex;align-items:center;gap:8px;">
                           <a href="#" data-sloppak-panel-open="1"
                              title="Open the full Conversions queue"
                              style="color:#a78bfa;text-decoration:underline;font-size:11px;">Open queue →</a>
                           <button type="button" data-sloppak-panel-dismiss="1"
                                   aria-label="Dismiss queue panel"
                                   title="Dismiss (open Conversions tab to view full queue)"
                                   style="background:transparent;border:none;color:#6b7280;cursor:pointer;font-size:16px;line-height:1;padding:0 4px;">×</button>
                       </span>
                   </div>`;
        const rows = [];
        for (const j of active) {
            const pct = Math.round((j.progress || 0) * 100);
            const name = j.filename.length > 34 ? j.filename.slice(0, 32) + '…' : j.filename;
            rows.push(`
                <div style="margin-bottom:8px;">
                    <div style="display:flex;justify-content:space-between;gap:6px;">
                        <span style="color:#e2e8f0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(name)}</span>
                        <span style="color:#a78bfa;">${pct}%</span>
                    </div>
                    <div style="height:4px;background:#1e1b33;border-radius:2px;overflow:hidden;margin-top:4px;">
                        <div style="height:100%;width:${pct}%;background:linear-gradient(90deg,#8b5cf6,#a78bfa);transition:width 0.2s;"></div>
                    </div>
                    <div style="color:#6b7280;margin-top:2px;">${escapeHtml(j.stage || '')}${j.message ? ' — ' + escapeHtml(j.message) : ''}</div>
                </div>`);
        }
        for (const j of recent) {
            const color = j.state === 'done' ? '#86efac' : '#fca5a5';
            const icon = j.state === 'done' ? '✓' : '!';
            const name = j.filename.length > 34 ? j.filename.slice(0, 32) + '…' : j.filename;
            rows.push(`
                <div style="margin-bottom:4px;color:${color};">
                    ${icon} ${escapeHtml(name)}${j.state === 'error' ? ' — ' + escapeHtml(j.message || '') : ''}
                </div>`);
        }
        p.innerHTML = header + `<div style="overflow-y:auto;flex:1 1 auto;min-height:0;">${rows.join('')}</div>`;
    }

    function escapeHtml(s) {
        return (s || '').replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
    }

    // ── WebSocket event handling ──────────────────────────────────────────────

    function connect() {
        try {
            ws = new WebSocket(WS_URL);
        } catch (e) {
            console.warn('[sloppak_converter] ws connect failed:', e);
            return;
        }
        ws.onmessage = (ev) => {
            let data;
            try { data = JSON.parse(ev.data); } catch (_) { return; }
            if (data.type === 'snapshot') {
                // Any job ID in this snapshot that the client hasn't seen
                // before counts as a "new job": reset the dismiss state so
                // work that arrived while the socket was offline still shows
                // in the floating panel (mirrors the job_update behaviour).
                const hasNewJob = (data.jobs || []).some(j => !convJobsById.has(j.id));
                demucsAvailable = !!data.demucs_available;
                convPaused = !!data.paused;
                jobsByFilename.clear();
                convJobsById.clear();
                for (const j of (data.jobs || [])) {
                    jobsByFilename.set(j.filename, j);
                    convJobsById.set(j.id, j);
                }
                if (hasNewJob) panelDismissed = false;
                refreshAllButtons();
                renderPanel();
                renderConvQueue();
            } else if (data.type === 'queue_state') {
                convPaused = !!data.paused;
                renderConvQueue();
            } else if (data.type === 'job_update' && data.job) {
                const prev = jobsByFilename.get(data.job.filename);
                const isNewJob = !convJobsById.has(data.job.id);
                jobsByFilename.set(data.job.filename, data.job);
                convJobsById.set(data.job.id, data.job);
                // New job arrival re-shows the floating panel even if the
                // user dismissed a previous batch, so they get feedback
                // for fresh work without losing the dismiss intent.
                if (isNewJob) panelDismissed = false;
                refreshAllButtons();
                renderPanel();
                renderConvQueue();
                // On completion, schedule a re-render so the "recent" TTL
                // drops the bubble automatically, and reload the library so
                // the new sloppak shows up.
                const justDone = (data.job.state === 'done' || data.job.state === 'error') &&
                                 (!prev || prev.state !== data.job.state);
                if (justDone) {
                    setTimeout(renderPanel, RECENT_TTL_MS + 100);
                    if (data.job.state === 'done' && typeof window.loadLibrary === 'function') {
                        setTimeout(() => { try { window.loadLibrary(); } catch (_) {} }, 400);
                    }
                }
            }
        };
        ws.onclose = () => {
            // Auto-reconnect with backoff.
            setTimeout(connect, 2000);
        };
        ws.onerror = () => { try { ws.close(); } catch (_) {} };
    }

    // ── Bootstrap ─────────────────────────────────────────────────────────────

    // ── Conversion Queue dashboard (slopsmith#107) ─────────────────────────
    //
    // The dashboard's markup lives in queue.html (mounted by core at
    // `#plugin-sloppak_converter`). All behavior lives here because
    // core's plugin loader sets `screenDiv.innerHTML = …` without
    // re-creating <script> nodes — inline scripts inside queue.html
    // would be inert. The MutationObserver below picks up the
    // dashboard DOM the first time the screen is mounted (initial
    // plugin load) and again after any remount, then drives all live
    // updates from the existing `jobsByFilename` cache the WS already
    // populates.

    const STATES = ['all', 'queued', 'running', 'done', 'error', 'cancelled'];
    const STATE_BADGE = {
        queued:    'bg-purple-500/15 text-purple-300 border-purple-400/30',
        running:   'bg-blue-500/15 text-blue-300 border-blue-400/30',
        done:      'bg-green-500/15 text-green-300 border-green-400/30',
        error:     'bg-red-500/15 text-red-300 border-red-400/30',
        cancelled: 'bg-gray-500/15 text-gray-400 border-gray-500/30',
    };
    let convStateFilter = 'all';
    let convPaused = false;
    // Index by `id` for the dashboard so multiple jobs against the
    // same filename (retry-failed creates a fresh id) all show. The
    // existing `jobsByFilename` Map is keyed by filename and good
    // for the per-card buttons (they only care about the latest
    // attempt) but would collapse the retry history here.
    const convJobsById = new Map();

    function convSummaryLine() {
        const counts = { queued: 0, running: 0, done: 0, error: 0, cancelled: 0 };
        for (const j of convJobsById.values()) counts[j.state] = (counts[j.state] || 0) + 1;
        const total = convJobsById.size;
        const head = convPaused ? '⏸ Paused — ' : '';
        if (!total) return head + 'No jobs yet.';
        const parts = [];
        if (counts.done) parts.push(`${counts.done} of ${total} done`);
        if (counts.running) parts.push(`${counts.running} running`);
        if (counts.queued) parts.push(`${counts.queued} queued`);
        if (counts.error) parts.push(`${counts.error} error`);
        if (counts.cancelled) parts.push(`${counts.cancelled} cancelled`);
        return head + parts.join(' · ');
    }

    function refreshPauseBtn() {
        const btn = document.getElementById('conv-pause-btn');
        if (!btn) return;
        btn.textContent = convPaused ? 'Resume' : 'Pause';
        btn.classList.toggle('bg-purple-500/30', convPaused);
        btn.classList.toggle('text-purple-200', convPaused);
    }

    function renderConvFilters() {
        const el = document.getElementById('conv-filters');
        if (!el) return;
        const counts = { all: convJobsById.size, queued: 0, running: 0, done: 0, error: 0, cancelled: 0 };
        for (const j of convJobsById.values()) counts[j.state] = (counts[j.state] || 0) + 1;
        el.innerHTML = STATES.map(s => {
            const active = convStateFilter === s;
            const cls = active
                ? 'bg-accent text-white'
                : 'bg-dark-700 text-gray-400 hover:text-white';
            return `<button type="button" data-conv-filter="${s}" aria-pressed="${active}" class="px-3 py-1 rounded text-xs transition ${cls}">${s} <span class="opacity-60">${counts[s] || 0}</span></button>`;
        }).join('');
    }

    function escAttr(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        }[c]));
    }

    function fmtDuration(secs) {
        const s = Math.max(0, Math.round(secs || 0));
        const m = Math.floor(s / 60);
        const r = s % 60;
        return `${m}:${r.toString().padStart(2, '0')}`;
    }

    function fmtBytes(n) {
        n = Number(n) || 0;
        if (n < 1024) return `${n} B`;
        if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
        if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
        return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
    }

    function elapsedSecs(j) {
        if (j.started_at && j.finished_at) return j.finished_at - j.started_at;
        return 0;
    }

    function convJobRow(j) {
        const pct = Math.round((j.progress || 0) * 100);
        const badge = STATE_BADGE[j.state] || STATE_BADGE.queued;
        const action = j.state === 'queued'
            ? `<button type="button" data-conv-cancel="${escAttr(j.id)}" class="text-xs text-gray-400 hover:text-red-300 transition">Cancel</button>`
            : j.state === 'error'
                ? `<button type="button" data-conv-retry="${escAttr(j.filename)}" data-conv-retry-split="${j.split ? '1' : '0'}" class="text-xs text-gray-400 hover:text-accent-light transition">Retry</button>`
                : '';
        const message = j.message ? `<div class="text-xs text-gray-600 truncate mt-0.5">${escAttr(j.message)}</div>` : '';

        // Prefer enriched title/artist when meta_db has the row; fall back
        // to the bare filename so jobs against missing-from-DB files still
        // render legibly.
        const title = j.title || '';
        const artist = j.artist || '';
        const heading = title
            ? (artist ? `${escAttr(artist)} — ${escAttr(title)}` : escAttr(title))
            : escAttr(j.filename);
        const sub = title ? `<div class="text-xs text-gray-500 truncate">${escAttr(j.filename)}</div>` : '';

        const meta = [];
        if (j.album) meta.push(escAttr(j.album));
        if (j.duration) meta.push(fmtDuration(j.duration));
        if (j.tuning_name) meta.push(escAttr(j.tuning_name));
        const arrCount = Array.isArray(j.arrangements) ? j.arrangements.length : 0;
        if (arrCount) meta.push(`${arrCount} arrangement${arrCount === 1 ? '' : 's'}`);
        // For done jobs, surface what Demucs actually produced — stem ids
        // (so the user sees whether vocals/drums/bass/etc were split out),
        // output size, and how long the job took. Reads `result_*` fields
        // populated server-side after a successful convert+split.
        let resultLine = '';
        if (j.state === 'done') {
            const resultBits = [];
            const stems = Array.isArray(j.result_stems) ? j.result_stems : [];
            if (stems.length) {
                resultBits.push(`stems: ${stems.map(s => escAttr(s)).join(', ')}`);
            } else if (j.demucs_skipped) {
                resultBits.push('stem split skipped');
            }
            if (j.result_size) resultBits.push(fmtBytes(j.result_size));
            const took = elapsedSecs(j);
            if (took > 0) resultBits.push(`${fmtDuration(took)} elapsed`);
            if (resultBits.length) {
                resultLine = `<div class="text-xs text-green-400/80 truncate mt-0.5">✓ ${resultBits.join(' · ')}</div>`;
            }
        }

        const arrList = arrCount
            ? `<div class="flex flex-wrap gap-1 mt-1">${j.arrangements.slice(0, 6).map(a => {
                  const n = (a && typeof a === 'object') ? (a.name || '') : String(a || '');
                  return `<span class="text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded bg-dark-800 text-gray-400 border border-gray-700">${escAttr(n)}</span>`;
              }).join('')}</div>`
            : '';
        const metaLine = meta.length
            ? `<div class="text-xs text-gray-500 truncate mt-0.5">${meta.join(' · ')}</div>`
            : '';

        return `
            <div class="bg-dark-700 border border-gray-800 rounded-lg p-3">
                <div class="flex items-center gap-3">
                    <span class="text-xs font-medium uppercase tracking-wider px-2 py-0.5 rounded border ${badge} flex-shrink-0">${escAttr(j.state)}</span>
                    <div class="flex-1 min-w-0">
                        <div class="text-sm text-gray-200 truncate">${heading}</div>
                        ${sub}
                        ${metaLine}
                        ${arrList}
                        ${resultLine}
                        ${message}
                    </div>
                    <div class="flex-shrink-0 text-right">
                        <div class="text-xs text-gray-500">${escAttr(j.stage || '')}</div>
                        ${j.state === 'running' || j.state === 'queued' ? `<div class="text-xs text-gray-400">${pct}%</div>` : ''}
                    </div>
                    ${action}
                </div>
                ${j.state === 'running' ? `
                    <div class="h-1 mt-2 bg-dark-800 rounded-full overflow-hidden" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100" aria-label="Conversion progress">
                        <div class="h-full bg-gradient-to-r from-purple-500 to-purple-300" style="width: ${pct}%; transition: width 0.2s;"></div>
                    </div>` : ''}
            </div>
        `;
    }

    function renderConvQueue() {
        const summaryEl = document.getElementById('conv-summary');
        if (!summaryEl) return;  // Dashboard not mounted yet.
        summaryEl.textContent = convSummaryLine();
        refreshPauseBtn();
        renderConvFilters();
        const table = document.getElementById('conv-table');
        const empty = document.getElementById('conv-empty');
        if (!table) return;
        // Sort: running first, then queued (FIFO by created_at), then
        // recently finished. Keeps active work at the top.
        const order = { running: 0, queued: 1, done: 2, cancelled: 3, error: 4 };
        const list = [...convJobsById.values()]
            .filter(j => convStateFilter === 'all' || j.state === convStateFilter)
            .sort((a, b) => {
                const oa = order[a.state] ?? 99, ob = order[b.state] ?? 99;
                if (oa !== ob) return oa - ob;
                return (a.created_at || 0) - (b.created_at || 0);
            });
        table.innerHTML = list.map(convJobRow).join('');
        empty.classList.toggle('hidden', list.length > 0);
    }

    // Single click delegate on the dashboard root so we don't have to
    // re-bind on every render. Dispatches by data-attribute set in
    // queue.html and convJobRow().
    let convClickDelegateRoot = null;
    let convDashboardMounted = false;
    const convClickDelegateHandler = (ev) => {
        const filter = ev.target.closest('[data-conv-filter]');
        if (filter) {
            convStateFilter = filter.dataset.convFilter;
            renderConvQueue();
            return;
        }
        const cancelOne = ev.target.closest('[data-conv-cancel]');
        if (cancelOne) {
            fetch(`${API}/jobs/${encodeURIComponent(cancelOne.dataset.convCancel)}`,
                  { method: 'DELETE' }).catch(() => {});
            return;
        }
        const retryOne = ev.target.closest('[data-conv-retry]');
        if (retryOne) {
            const retryFn = retryOne.dataset.convRetry;
            // Use the most-recent job's split flag for this filename rather
            // than the stale dataset attribute on the specific row.  When the
            // dashboard shows multiple error entries for the same file, an
            // older row's split value can be out of date; jobsByFilename
            // always holds the latest state for each filename.
            const latestJob = jobsByFilename.get(retryFn);
            const retrySplit = latestJob ? !!latestJob.split : demucsAvailable;
            fetch(`${API}/enqueue_bulk`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    filenames: [retryFn],
                    split: retrySplit,
                    reconvert: true,
                }),
            }).catch(() => {});
            return;
        }
        const headerAction = ev.target.closest('[data-conv-action]');
        if (!headerAction) return;
        const action = headerAction.dataset.convAction;
        if (action === 'toggle-pause') {
            const path = convPaused ? 'resume' : 'pause';
            fetch(`${API}/${path}`, { method: 'POST' })
                .then(r => r.json())
                .then(d => { convPaused = !!d.paused; renderConvQueue(); })
                .catch(() => {});
        } else if (action === 'cancel-all') {
            if (!confirm('Cancel every queued job? Running jobs will continue.')) return;
            fetch(`${API}/cancel_queued`, { method: 'POST' }).catch(() => {});
        } else if (action === 'retry-failed') {
            fetch(`${API}/retry_failed`, { method: 'POST' }).catch(() => {});
        } else if (action === 'clear-finished') {
            if (!confirm('Clear all finished (done / error / cancelled) jobs from the queue?')) return;
            fetch(`${API}/clear_finished`, { method: 'POST' }).catch(() => {});
        }
    };
    function ensureConvClickDelegate() {
        const root = document.getElementById('plugin-sloppak_converter');
        if (!root) return;
        if (convClickDelegateRoot === root) return;
        if (convClickDelegateRoot) {
            convClickDelegateRoot.removeEventListener('click', convClickDelegateHandler);
        }
        convClickDelegateRoot = root;
        convClickDelegateRoot.addEventListener('click', convClickDelegateHandler);
    }

    // Watch for the dashboard DOM appearing (it's mounted lazily when
    // core injects the plugin's screen.html). Once the summary
    // element exists we install the click delegate and seed the table.
    // The mount flag prevents renderConvQueue() being called on every
    // subsequent DOM mutation (which would create a self-sustaining
    // render loop: renderConvQueue writes to the DOM → observer fires
    // → checkConvDashboardMount → renderConvQueue → …).
    function checkConvDashboardMount() {
        if (!document.getElementById('conv-summary')) {
            if (convDashboardMounted) {
                // Dashboard was just removed; remove the click delegate and
                // clear mount flags so the next mount gets a clean initial
                // render and a fresh delegate without stacking up listeners.
                convDashboardMounted = false;
                if (convClickDelegateRoot) {
                    convClickDelegateRoot.removeEventListener('click', convClickDelegateHandler);
                    convClickDelegateRoot = null;
                }
            }
            return;
        }
        ensureConvClickDelegate();
        if (!convDashboardMounted) {
            convDashboardMounted = true;
            renderConvQueue();
        }
    }

    // Persist the dashboard as the "last screen" so refresh stays here
     // instead of bouncing back to Library. Core's showScreen doesn't
     // remember the active screen, so each plugin that wants
     // reload-stickiness opts in itself. Other plugins doing the same
     // would race to be the last writer — fine, last screen wins.
    const LAST_SCREEN_KEY = 'sloppak_converter.lastScreen';
    const OUR_SCREEN_ID = 'plugin-sloppak_converter';
    function _wireScreenPersistence() {
        if (window.slopsmith && typeof window.slopsmith.on === 'function') {
            window.slopsmith.on('screen:changed', (ev) => {
                // slopsmith.emit dispatches CustomEvent; payload lives in .detail
                const id = ev && ev.detail && ev.detail.id;
                if (!id) return;
                // Track the favorites screen so doConvertMissing can filter
                // to the user's current favorites-only view.
                _onFavoritesScreen = (id === 'favorites');
                // The bulk bar (Convert selected / Convert missing) only makes
                // sense on the library workflow screens.  Hide it everywhere
                // else — including the Conversions dashboard and any other
                // plugin or app screen the user might visit.
                // Core's library screen id is 'home' (not 'library' — that's
                // the route name, not the DOM id). The favorites screen id
                // matches its route.
                document.body.classList.toggle('sloppak-on-bulk-screen',
                                               id === 'home' || id === 'favorites');
                if (id === OUR_SCREEN_ID) {
                    try { localStorage.setItem(LAST_SCREEN_KEY, id); } catch (_) {}
                } else {
                    // User left the dashboard — clear so we don't yank
                    // them back next reload.
                    try { localStorage.removeItem(LAST_SCREEN_KEY); } catch (_) {}
                }
            });
        }
        // Sync screen-dependent state immediately at boot so that a hard
        // refresh while on Favorites (or any other screen) starts with the
        // correct state without waiting for the first screen:changed event.
        // Slopsmith uses hash routing; the hash holds the current screen id.
        (function _syncInitialScreenState() {
            // Slopsmith doesn't actually use hash routing; the visible
            // screen is whichever .screen has the `active` class. Default
            // is `#home` (set in index.html). Read that directly so a hard
            // refresh on Favorites starts with the bar showing.
            const active = document.querySelector('.screen.active');
            const screenId = (active && active.id) || 'home';
            _onFavoritesScreen = (screenId === 'favorites');
            document.body.classList.toggle('sloppak-on-bulk-screen',
                screenId === 'home' || screenId === 'favorites');
        })();
        // On boot, if the last screen was ours and the container exists,
        // navigate. Wait a tick so other plugins / core finish their own
        // boot navigation first.
        try {
            const last = localStorage.getItem(LAST_SCREEN_KEY);
            if (last === OUR_SCREEN_ID && typeof window.showScreen === 'function') {
                setTimeout(() => {
                    if (document.getElementById(OUR_SCREEN_ID)) {
                        window.showScreen(OUR_SCREEN_ID);
                    }
                }, 50);
            }
        } catch (_) {}
    }

    function init() {
        // Fetch current state up front (so buttons reflect it before WS lands).
        fetch(`${API}/jobs`).then(r => r.json()).then(data => {
            demucsAvailable = !!data.demucs_available;
            convPaused = !!data.paused;
            for (const j of (data.jobs || [])) {
                jobsByFilename.set(j.filename, j);
                convJobsById.set(j.id, j);
            }
            refreshAllButtons();
            renderPanel();
            checkConvDashboardMount();
        }).catch(() => {});

        connect();
        startObserver();
        checkConvDashboardMount();
        _wireScreenPersistence();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
