// 3D Drum Highway — perspective lane-based drum visualization.
// Plugs into the slopsmith setRenderer contract (slopsmith#36).
// Each GM drum piece gets its own lane; notes scroll toward the hit line.

(function () {
    'use strict';

    /* ── Lane definitions ─────────────────────────────────────────────────
     * Left → right screen order. midi: MIDI note numbers that map here.
     * shape: 'cymbal' (flat disc-like), 'pad' (box), 'kick' (wide box).
     * Drum note encoding in slopsmith: midi = note.s * 24 + note.f
     */
    const LANES = [
        { midi: [49, 57, 55, 52], name: 'Crash',   color: 0xff8820, shape: 'cymbal' },
        { midi: [46],             name: 'HH Open', color: 0xffff40, shape: 'cymbal' },
        { midi: [42, 44],         name: 'HH',      color: 0xffe020, shape: 'cymbal' },
        { midi: [38, 40, 37],     name: 'Snare',   color: 0xff2828, shape: 'pad'    },
        { midi: [35, 36],         name: 'Kick',    color: 0xff5510, shape: 'kick'   },
        { midi: [45, 47, 48, 50], name: 'Tom 1',   color: 0x30d030, shape: 'pad'    },
        { midi: [43, 41],         name: 'Tom 2',   color: 0x2080ff, shape: 'pad'    },
        { midi: [51, 59, 53, 56], name: 'Ride',    color: 0x30d8d0, shape: 'cymbal' },
    ];

    const N = LANES.length;

    // MIDI → lane index lookup
    const MIDI_MAP = new Map();
    LANES.forEach((l, i) => l.midi.forEach(m => MIDI_MAP.set(m, i)));

    /* ── Layout ───────────────────────────────────────────────────────────*/
    const LANE_W  = 1.30;
    const LANE_G  = 0.10;
    const STRIDE  = LANE_W + LANE_G;
    const TOTAL_W = N * STRIDE - LANE_G;

    // Note box dimensions per shape
    const NW = { pad: LANE_W * 0.80, cymbal: LANE_W * 0.86, kick: LANE_W * 0.88 };
    const NH = { pad: 0.22,          cymbal: 0.07,           kick: 0.30           };
    const ND = 0.22; // depth along scroll axis

    /* ── Timing ───────────────────────────────────────────────────────────*/
    const AHEAD  = 2.4;  // seconds of notes visible ahead
    const BEHIND = 0.15; // seconds behind hit line still shown (fading)
    const WORLD  = 18.0; // world units over AHEAD seconds
    const SPEED  = WORLD / AHEAD; // world units per second

    /* ── Helpers ──────────────────────────────────────────────────────────*/
    const laneX  = i  => (i - (N - 1) / 2) * STRIDE;
    const getLane = (s, f) => MIDI_MAP.get(s * 24 + f) ?? -1;

    /* ── Three.js loader (module-level cache) ─────────────────────────────*/
    let _threeP = null;
    function loadThree() {
        if (!_threeP) {
            _threeP = import('/static/vendor/three/three.module.min.js').catch(
                () => import('https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.min.js')
            );
        }
        return _threeP;
    }

    /* ══════════════════════════════════════════════════════════════════════
     *  createInstance — one independent renderer per highway panel
     * ══════════════════════════════════════════════════════════════════════*/
    function createInstance() {
        let T = null;
        let ren = null, scene = null, cam = null, hw = null;
        let _ready = false, _lw = 0, _lh = 0;

        // Per-lane materials
        let _mNote = [], _mGlow = [], _mFlash = [];
        let _flashAmt = new Float32Array(N);

        // Object pools — pre-allocated meshes reused every frame
        let _notePool = [], _noteIdx = 0;
        let _beatPool = [], _beatIdx = 0;

        /* ── Teardown ─────────────────────────────────────────────────────*/
        function teardown() {
            _ready = false;
            _mNote.forEach(m => m.dispose()); _mNote = [];
            _mGlow.forEach(m => m.dispose()); _mGlow = [];
            _mFlash = [];
            if (ren) { ren.dispose(); ren = null; }
            scene = null; cam = null; hw = null;
            _notePool = []; _beatPool = [];
            _lw = _lh = 0;
        }

        /* ── Resize ───────────────────────────────────────────────────────*/
        function doResize() {
            if (!ren || !hw) return;
            const w = hw.offsetWidth || 800;
            const h = hw.offsetHeight || 600;
            if (w === _lw && h === _lh) return;
            _lw = w; _lh = h;
            ren.setSize(w, h, false);
            cam.aspect = w / h;
            cam.updateProjectionMatrix();
        }

        /* ── Label sprite ─────────────────────────────────────────────────*/
        function makeLabel(text, hexColor) {
            const cw = 128, ch = 48;
            const c = document.createElement('canvas');
            c.width = cw; c.height = ch;
            const ctx = c.getContext('2d');
            const col = '#' + new T.Color(hexColor).getHexString();
            ctx.font = 'bold 15px "Arial Black", Arial, sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.shadowColor = col; ctx.shadowBlur = 10;
            ctx.fillStyle = col;
            ctx.fillText(text, cw / 2, ch / 2);
            const tex = new T.CanvasTexture(c);
            const sp = new T.Sprite(new T.SpriteMaterial({
                map: tex, transparent: true, opacity: 0.92, depthTest: false,
            }));
            sp.renderOrder = 100;
            return sp;
        }

        /* ── Scene initialisation ─────────────────────────────────────────*/
        function initScene() {
            scene = new T.Scene();
            scene.background = new T.Color(0x060a10);
            scene.fog = new T.FogExp2(0x060a10, 0.028);

            // Camera: above and behind hit line, angled down the highway
            cam = new T.PerspectiveCamera(52, 1, 0.05, 150);
            cam.position.set(0, 4.2, 5.5);
            cam.lookAt(0, 0.25, -WORLD * 0.38);

            // Lights
            scene.add(new T.AmbientLight(0xffffff, 0.70));
            const dir = new T.DirectionalLight(0xffffff, 0.95);
            dir.position.set(1, 8, 4);
            scene.add(dir);

            const FL = WORLD + 14; // floor length
            const FZ = 5.5;        // floor starts here (behind camera origin)

            /* ── Floor ──────────────────────────────────────────────────*/
            const floorMat = new T.MeshStandardMaterial({ color: 0x0a1120, roughness: 1.0, metalness: 0.0 });
            const floorM = new T.Mesh(new T.PlaneGeometry(TOTAL_W + 5, FL), floorMat);
            floorM.rotation.x = -Math.PI / 2;
            floorM.position.set(0, 0, FZ - FL / 2);
            scene.add(floorM);

            /* ── Lane tints, dividers, flash quads ──────────────────────*/
            LANES.forEach((lane, i) => {
                const x = laneX(i);

                // Subtle color tint on the floor under each lane
                const tM = new T.Mesh(
                    new T.PlaneGeometry(LANE_W, FL),
                    new T.MeshBasicMaterial({ color: lane.color, transparent: true, opacity: 0.045 })
                );
                tM.rotation.x = -Math.PI / 2;
                tM.position.set(x, 0.001, FZ - FL / 2);
                scene.add(tM);

                // Left edge divider line
                const dCol = new T.Color(lane.color).multiplyScalar(0.30);
                const dx   = x - LANE_W / 2 - LANE_G / 2;
                scene.add(new T.Line(
                    new T.BufferGeometry().setFromPoints([
                        new T.Vector3(dx, 0.003, FZ),
                        new T.Vector3(dx, 0.003, -WORLD - 5),
                    ]),
                    new T.LineBasicMaterial({ color: dCol, transparent: true, opacity: 0.6 })
                ));

                // Hit-flash quad (at z=0, opacity driven per-frame)
                const fm = new T.MeshBasicMaterial({
                    color: lane.color, transparent: true, opacity: 0, depthWrite: false,
                });
                const fM = new T.Mesh(new T.PlaneGeometry(LANE_W * 0.88, ND * 4.5), fm);
                fM.rotation.x = -Math.PI / 2;
                fM.position.set(x, 0.014, 0);
                scene.add(fM);
                _mFlash.push(fm);
            });

            // Right edge divider
            {
                const dx = laneX(N - 1) + LANE_W / 2 + LANE_G / 2;
                scene.add(new T.Line(
                    new T.BufferGeometry().setFromPoints([
                        new T.Vector3(dx, 0.003, FZ),
                        new T.Vector3(dx, 0.003, -WORLD - 5),
                    ]),
                    new T.LineBasicMaterial({ color: 0x1a2840, transparent: true, opacity: 0.6 })
                ));
            }

            /* ── Hit line ───────────────────────────────────────────────*/
            {
                // Crisp white line
                const hl = new T.Mesh(
                    new T.PlaneGeometry(TOTAL_W + 0.5, 0.055),
                    new T.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.6 })
                );
                hl.rotation.x = -Math.PI / 2;
                hl.position.set(0, 0.013, 0);
                scene.add(hl);

                // Soft blue glow behind hit line
                const gl = new T.Mesh(
                    new T.PlaneGeometry(TOTAL_W + 1.5, 0.35),
                    new T.MeshBasicMaterial({ color: 0x2255cc, transparent: true, opacity: 0.14, depthWrite: false })
                );
                gl.rotation.x = -Math.PI / 2;
                gl.position.set(0, 0.011, 0);
                scene.add(gl);
            }

            /* ── Lane labels at hit line ────────────────────────────────*/
            LANES.forEach((lane, i) => {
                const sp = makeLabel(lane.name, lane.color);
                sp.scale.set(1.05, 0.50, 1);
                sp.position.set(laneX(i), 0.40, 1.0);
                scene.add(sp);
            });

            /* ── Note materials ─────────────────────────────────────────*/
            _mNote = LANES.map(l => {
                const c = new T.Color(l.color);
                return new T.MeshStandardMaterial({
                    color: c, emissive: c, emissiveIntensity: 0.22,
                    roughness: 0.32, metalness: 0.18,
                });
            });
            _mGlow = LANES.map(l => {
                const c = new T.Color(l.color);
                return new T.MeshStandardMaterial({
                    color: 0xffffff, emissive: c, emissiveIntensity: 4.0,
                    roughness: 0.12, metalness: 0.35,
                    transparent: true, opacity: 1.0,
                });
            });

            /* ── Note pool ──────────────────────────────────────────────*/
            const bGeo = new T.BoxGeometry(1, 1, 1);
            for (let i = 0; i < 256; i++) {
                const m = new T.Mesh(bGeo, _mNote[0]);
                m.visible = false;
                scene.add(m);
                _notePool.push(m);
            }
            _noteIdx = 0;

            /* ── Beat line pool ─────────────────────────────────────────*/
            const hw2 = TOTAL_W / 2 + 0.5;
            const beatPts = [new T.Vector3(-hw2, 0.004, 0), new T.Vector3(hw2, 0.004, 0)];
            const beatGeo = new T.BufferGeometry().setFromPoints(beatPts);
            const matBeat    = new T.LineBasicMaterial({ color: 0x182840, transparent: true, opacity: 0.75 });
            const matMeasure = new T.LineBasicMaterial({ color: 0x2a4060, transparent: true, opacity: 1.00 });
            for (let i = 0; i < 64; i++) {
                const line = new T.Line(beatGeo, matBeat);
                line.visible = false;
                scene.add(line);
                _beatPool.push({ line, matBeat, matMeasure });
            }
            _beatIdx = 0;
        }

        /* ── Per-frame update ─────────────────────────────────────────────*/
        function update(bundle) {
            const now = bundle.currentTime;

            // Reset pools
            _notePool.forEach(m => { m.visible = false; }); _noteIdx = 0;
            _beatPool.forEach(b => { b.line.visible = false; }); _beatIdx = 0;

            /* ── Beat lines ─────────────────────────────────────────────*/
            let prevMeasure = -1;
            for (const beat of (bundle.beats || [])) {
                const dt = beat.time - now;
                if (dt < -BEHIND || dt > AHEAD) continue;
                if (_beatIdx >= _beatPool.length) break;
                const bl = _beatPool[_beatIdx++];
                bl.line.position.z = -dt * SPEED;
                const isMeasure = (beat.measure !== prevMeasure);
                bl.line.material = isMeasure ? bl.matMeasure : bl.matBeat;
                if (isMeasure) prevMeasure = beat.measure;
                bl.line.visible = true;
            }

            /* ── Draw a single drum hit ──────────────────────────────────*/
            const drawHit = (dt, s, f) => {
                const li = getLane(s, f);
                if (li < 0 || _noteIdx >= _notePool.length) return;

                const lane = LANES[li];
                const z    = -dt * SPEED;

                // Fade out notes that are behind the hit line
                const fade = dt < 0 ? Math.max(0, 1 + dt / BEHIND) : 1;
                if (fade <= 0) return;

                const isNear = Math.abs(dt) < 0.09;
                const mesh   = _notePool[_noteIdx++];

                const shape = lane.shape;
                const nw = NW[shape], nh = NH[shape];
                mesh.scale.set(nw, nh, ND);
                mesh.position.set(laneX(li), nh / 2, z);

                const mat = isNear ? _mGlow[li] : _mNote[li];
                if (mesh.material !== mat) mesh.material = mat;
                if (mat.transparent) mat.opacity = fade;
                mesh.visible = true;

                // Accumulate flash brightness for this lane
                if (isNear && dt >= -0.07) {
                    _flashAmt[li] = Math.max(_flashAmt[li], 1 - Math.abs(dt) / 0.09);
                }
            };

            // Standalone notes
            for (const n of (bundle.notes || [])) {
                const dt = n.t - now;
                if (dt >= -BEHIND && dt <= AHEAD) drawHit(dt, n.s, n.f);
            }
            // Chord notes (simultaneous hits — common in drums)
            for (const ch of (bundle.chords || [])) {
                const dt = ch.t - now;
                if (dt < -BEHIND || dt > AHEAD) continue;
                for (const n of (ch.notes || [])) drawHit(dt, n.s, n.f);
            }

            /* ── Decay hit-flash ────────────────────────────────────────*/
            for (let i = 0; i < N; i++) {
                _flashAmt[i] *= 0.78;
                _mFlash[i].opacity = _flashAmt[i] * 0.70;
            }
        }

        /* ── setRenderer contract ─────────────────────────────────────────*/
        return {
            contextType: 'webgl2',

            async init(canvas, bundle) {
                teardown();
                hw = canvas;

                const mod = await loadThree();
                T = mod;

                ren = new T.WebGLRenderer({
                    canvas,
                    antialias: true,
                    powerPreference: 'high-performance',
                });
                ren.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

                initScene();
                doResize();
                _ready = true;
            },

            draw(bundle) {
                if (!_ready || !ren) return;
                if (hw.offsetWidth !== _lw || hw.offsetHeight !== _lh) doResize();
                update(bundle);
                ren.render(scene, cam);
            },

            resize() { if (_ready) doResize(); },
            destroy() { teardown(); },
        };
    }

    /* ── Register with slopsmith ──────────────────────────────────────────*/
    window.slopsmithViz_drums_3d = () => createInstance();
    window.slopsmithViz_drums_3d.contextType = 'webgl2';

    // Auto-select when a drum arrangement loads (slopsmith#36 Auto mode).
    // The existing 2D drum plugin (id: "drums") loads first alphabetically
    // and also matches — this plugin wins when the user explicitly picks it,
    // or if the 2D drums plugin is not loaded.
    window.slopsmithViz_drums_3d.matchesArrangement = si =>
        /drum/i.test((si && si.arrangement) || '');
})();
