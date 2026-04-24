(function () {
    var CONFIG = {
        n_blocks: 11,
        clicks_per_block: 10,
        grid_rows: 11,
        grid_cols: 11,
        kraken_threshold: 50,
        reward_noise_sd: 1.0,
        n_safe_blocks: 6,
        n_risky_blocks: 5,
        click_deadline: 30000,
        feedback_duration: 600,
    };
    CONFIG.click_deadline = getTrialDuration(CONFIG.click_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "grid_bandit";

    // Allow shrinking the task from the URL (--n-trials in the runner) — n_trials is total clicks.
    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        // Reduce to as few blocks as we need at 10 clicks each, minimum 2 blocks (1 safe, 1 risky).
        var n_blocks = Math.max(2, Math.ceil(_nto / CONFIG.clicks_per_block));
        CONFIG.n_blocks = n_blocks;
        // Re-balance: alternate safe/risky.
        CONFIG.n_safe_blocks = Math.ceil(n_blocks / 2);
        CONFIG.n_risky_blocks = Math.floor(n_blocks / 2);
        // Cap clicks_per_block so the total never exceeds the requested n_trials.
        CONFIG.clicks_per_block = Math.max(1, Math.floor(_nto / n_blocks));
    }

    var jsPsych = initJsPsych({
        experiment_width: 700,
        minimum_valid_rt: 50,
    });
    if (SESSION_ID === "debug") window._jsPsych = jsPsych;

    // ---- Reward grids (loaded async) ----
    var GRIDS = null;
    var GRID_LOAD_PROMISE = fetch("/tasks/grid_bandit/assets/sample_grid.json", { cache: "force-cache" })
        .then(function (r) { return r.json(); })
        .then(function (json) { GRIDS = json; })
        .catch(function (err) { console.error("Failed to load grids:", err); GRIDS = null; });

    function gridValue(env_idx, x, y) {
        // env keys are stringified ints; rows/cols same.
        var env = GRIDS[String(env_idx)];
        if (!env) return 50; // fallback to mean
        var row = env[String(y)];
        if (!row) return 50;
        var v = row[String(x)];
        return (v === undefined || v === null) ? 50 : v;
    }

    function gaussianNoise(sd) {
        // Box-Muller
        var u1 = Math.random() || 1e-12;
        var u2 = Math.random();
        return sd * Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
    }

    function buildBlockOrder() {
        var blocks = [];
        for (var i = 0; i < CONFIG.n_safe_blocks; i++) blocks.push("safe");
        for (var i = 0; i < CONFIG.n_risky_blocks; i++) blocks.push("risky");
        // Fisher-Yates shuffle.
        for (var i = blocks.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var t = blocks[i]; blocks[i] = blocks[j]; blocks[j] = t;
        }
        return blocks;
    }

    function pickEnvIndices(n) {
        var pool = [];
        for (var i = 0; i < 30; i++) pool.push(i);
        for (var i = pool.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var t = pool[i]; pool[i] = pool[j]; pool[j] = t;
        }
        return pool.slice(0, n);
    }

    var BLOCK_ORDER = null;     // initialized after grid load
    var BLOCK_ENVS = null;
    var trial_counter = 0;

    // ---- Grid rendering ----
    function renderGrid(blockState, lastClick) {
        var html = "";
        // Header banner
        var bannerClass = blockState.condition === "risky" ? "risky" : "safe";
        var bannerText = blockState.condition === "risky"
            ? "🐙 RISKY waters — a Kraken hunts here. Hauls of " + CONFIG.kraken_threshold + " or fewer fish summon it and ZERO your block."
            : "⛵ SAFE waters — no Kraken. Maximize your fish haul.";
        html += '<div style="text-align:center;margin-bottom:6px"><span class="grid-banner ' + bannerClass + '">' + bannerText + "</span></div>";
        html += '<div style="text-align:center;margin-bottom:8px"><span class="grid-status">Block <strong>' + blockState.block_num + "</strong> of " + CONFIG.n_blocks +
                " · Cast <strong>" + (blockState.click_idx + 1) + "</strong> of " + CONFIG.clicks_per_block +
                " · Catch so far: <strong>" + blockState.block_running_reward + " 🐟</strong></span></div>";
        html += '<div class="boat">⛵</div>';
        html += '<div class="grid-wrap"><table class="grid-table">';
        for (var r = 0; r < CONFIG.grid_rows; r++) {
            html += "<tr>";
            for (var c = 0; c < CONFIG.grid_cols; c++) {
                var key = c + "," + r;
                var hist = blockState.history[key];
                var cls = "";
                var label = "";
                if (hist) {
                    cls = "clicked";
                    if (hist.kraken) {
                        cls += " kraken";
                        label = "🐙";
                    } else {
                        label = hist.last_z;
                    }
                }
                if (lastClick && lastClick.x === c && lastClick.y === r) {
                    cls += " last-click";
                }
                html += '<td data-x="' + c + '" data-y="' + r + '" class="' + cls + '">' + label + "</td>";
            }
            html += "</tr>";
        }
        html += "</table></div>";
        return html;
    }

    // ---- Click handler attached on_load ----
    function attachClickHandler(blockState) {
        var cells = document.querySelectorAll(".grid-table td");
        cells.forEach(function (cell) {
            cell.addEventListener("click", function () {
                var x = parseInt(cell.getAttribute("data-x"));
                var y = parseInt(cell.getAttribute("data-y"));
                if (isNaN(x) || isNaN(y)) return;

                // Compute reward.
                var z_true = gridValue(blockState.env_idx, x, y);
                var z = Math.max(0, Math.min(100, Math.round(z_true + gaussianNoise(CONFIG.reward_noise_sd))));

                // Distance from last click.
                var dist = null;
                if (blockState.last_click) {
                    var dx = x - blockState.last_click.x;
                    var dy = y - blockState.last_click.y;
                    dist = Math.sqrt(dx * dx + dy * dy);
                }
                var prev_z = blockState.last_click ? blockState.last_click.z : null;
                var key = x + "," + y;
                var was_clicked = !!blockState.history[key];
                var kraken_caught = (blockState.condition === "risky" && z_true <= CONFIG.kraken_threshold);

                // Update running reward.
                if (kraken_caught) {
                    blockState.block_running_reward = 0;
                } else {
                    blockState.block_running_reward += z;
                }

                // Update history.
                blockState.history[key] = { last_z: z, kraken: kraken_caught };
                blockState.last_click = { x: x, y: y, z: z };

                trial_counter++;
                var clickRecord = {
                    trial_part: "click",
                    trial_index: trial_counter,
                    block: blockState.block_num,
                    click_in_block: blockState.click_idx + 1,
                    block_condition: blockState.condition,
                    env_idx: blockState.env_idx,
                    x: x, y: y, z: z, z_true: z_true,
                    z_above_50: z > 50,
                    previous_z: prev_z,
                    distance_from_last: dist,
                    is_repeat_tile: was_clicked,
                    kraken_caught: kraken_caught,
                    timed_out: false,
                    rt: performance.now() - blockState._click_start,
                };

                jsPsych.finishTrial(clickRecord);
            });
        });
    }

    // ---- Block state factory (one per block) ----
    function makeBlockState(block_num) {
        return {
            block_num: block_num,
            condition: BLOCK_ORDER[block_num - 1],
            env_idx: BLOCK_ENVS[block_num - 1],
            click_idx: 0,
            history: {},
            last_click: null,
            block_running_reward: 0,
            _click_start: 0,
        };
    }

    // ---- Build the timeline ----
    var timeline = [];

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Spatial Bandit (Grid Foraging)</h1>" +
            "<p>Welcome. Press any key to begin.</p>",
    });

    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>You will see an 11×11 grid of tiles. Each tile hides a fish count between 0 and 100.</p>" +
            "<p>Click a tile to fish there. The number you collect appears on the tile. Nearby tiles tend to give similar values.</p>" +
            "<p>The experiment has " + CONFIG.n_blocks + " blocks of " + CONFIG.clicks_per_block + " clicks each, on " + CONFIG.n_blocks + " different grids.</p>",

            "<h2>Two block types</h2>" +
            "<p><span style='color:#15803d;font-weight:bold'>SAFE blocks</span>: harvest as much as you can. No risk.</p>" +
            "<p><span style='color:#b91c1c;font-weight:bold'>RISKY blocks</span>: a Kraken patrols. Any click with a value ≤ " + CONFIG.kraken_threshold + " catches the Kraken and ZEROES your earnings for that block. Try to find values above " + CONFIG.kraken_threshold + ".</p>" +
            "<p>The block type is shown in a banner above the grid on every click.</p>",

            "<h2>Get ready</h2>" +
            "<p>You have up to " + Math.round(CONFIG.click_deadline / 1000) + " seconds per click.</p>" +
            "<p>Press Next to start the first block.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    // Block initializer: choose order + envs once grids have loaded.
    timeline.push({
        type: jsPsychCallFunction,
        async: true,
        func: function (done) {
            GRID_LOAD_PROMISE.then(function () {
                BLOCK_ORDER = buildBlockOrder();
                BLOCK_ENVS = pickEnvIndices(CONFIG.n_blocks);
                done();
            });
        },
    });

    function makeBlockTimeline(block_num) {
        // Per-block closure that owns the BlockState.
        var blockState = null;
        var clicks_this_block = 0;
        var nodes = [];

        // Block intro screen.
        nodes.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                var cond = BLOCK_ORDER[block_num - 1];
                var bannerClass = cond === "risky" ? "risky" : "safe";
                return "<div class='grid-banner " + bannerClass + "'>" +
                       "Block " + block_num + " of " + CONFIG.n_blocks + " · " +
                       (cond === "risky" ? "RISKY" : "SAFE") + "</div>" +
                       "<p>Press any key to begin this block.</p>";
            },
            on_finish: function () {
                blockState = makeBlockState(block_num);
            },
        });

        // Repeated click trial: a single trial node that the timeline will run
        // `clicks_per_block` times via `repetitions`.
        nodes.push({
            timeline: [{
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () { return renderGrid(blockState, blockState.last_click); },
                choices: "NO_KEYS",
                trial_duration: CONFIG.click_deadline,
                on_load: function () {
                    blockState._click_start = performance.now();
                    attachClickHandler(blockState);
                },
                on_finish: function (data) {
                    if (data.trial_part !== "click") {
                        // Trial ended via timeout (no click).
                        trial_counter++;
                        Object.assign(data, {
                            trial_part: "click",
                            trial_index: trial_counter,
                            block: blockState.block_num,
                            click_in_block: blockState.click_idx + 1,
                            block_condition: blockState.condition,
                            env_idx: blockState.env_idx,
                            x: null, y: null, z: null, z_true: null,
                            previous_z: blockState.last_click ? blockState.last_click.z : null,
                            distance_from_last: null,
                            is_repeat_tile: false,
                            kraken_caught: false,
                            timed_out: true,
                        });
                    }
                    blockState.click_idx++;
                    clicks_this_block++;
                },
            }],
            repetitions: CONFIG.clicks_per_block,
        });

        // Block summary screen.
        nodes.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                return "<div class='feedback-block'>" +
                       "End of block " + block_num + ".<br>" +
                       "You harvested <strong>" + blockState.block_running_reward + "</strong> fish in this block." +
                       "</div>" +
                       "<p>Press any key to continue.</p>";
            },
            trial_duration: 8000,
        });
        return { timeline: nodes };
    }

    for (var b = 1; b <= CONFIG.n_blocks; b++) {
        timeline.push(makeBlockTimeline(b));
    }

    // Data submission.
    timeline.push({
        type: jsPsychCallFunction,
        async: true,
        func: function (done) {
            var trial_data = jsPsych.data
                .get()
                .filter({ trial_part: "click" })
                .values();

            var payload = {
                trial_data: trial_data,
                metadata: {
                    task_id: TASK_ID,
                    session_id: SESSION_ID,
                    total_time_ms: jsPsych.getTotalTime(),
                    n_trials: trial_data.length,
                },
            };

            fetch("/api/data/" + SESSION_ID + "/" + TASK_ID, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            })
                .then(function (response) {
                    if (!response.ok) console.error("Data submission failed:", response.status);
                    done();
                })
                .catch(function (error) {
                    console.error("Data submission error:", error);
                    done();
                });
        },
    });

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Task Complete</h2>" +
            "<p>Thank you for completing the spatial bandit task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
