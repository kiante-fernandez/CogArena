(function () {
    var CONFIG = {
        n_blocks: 2,
        trials_per_block: 40,
        block_conditions: ["low_cost", "high_cost"],
        travel_cost_seconds: { low_cost: 4, high_cost: 8 },
        start_reward_mean: 70,
        start_reward_sd: 6,
        decay_rate_mean: 0.88,
        decay_rate_sd: 0.04,
        valid_keys: ["f", "j"],
        key_mapping: { stay: "f", leave: "j" },
        response_deadline: 5000,
        harvest_animation: 900,  // visual feedback window; does not affect scoring
        travel_animation: 600,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "effort_foraging";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.trials_per_block = Math.max(2, Math.floor(_nto / CONFIG.n_blocks));
    }

    var jsPsych = initJsPsych({ experiment_width: 800, minimum_valid_rt: 50 });
    if (SESSION_ID === "debug") window._jsPsych = jsPsych;

    function gaussian(mean, sd) {
        var u1 = Math.random() || 1e-12;
        var u2 = Math.random();
        return mean + sd * Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
    }
    function clip(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
    function shuffle(a) {
        a = a.slice();
        for (var i = a.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var t = a[i]; a[i] = a[j]; a[j] = t;
        }
        return a;
    }

    function blockBanner(condition) {
        var lab = condition === "low_cost" ? "Low-cost travel" : "High-cost travel";
        var cls = condition === "low_cost" ? "low" : "high";
        var secs = CONFIG.travel_cost_seconds[condition];
        return "<div class='block-banner " + cls + "'><span class='dot'></span>" + lab +
               " · travel = " + secs + "s</div>";
    }

    // --- Tree SVG with depletion states ---
    // ratio = current_reward / patch_start_reward (falls from 1.0 toward 0)
    // We pass both absolute reward (for apple count) and ratio (for canopy scale).
    function svgTree(reward, ratio, small) {
        var W = small ? 100 : 280;
        var H = small ? 110 : 240;
        var trunkW = small ? 10 : 24;
        var trunkH = small ? 28 : 64;
        var trunkX = W / 2 - trunkW / 2, trunkY = H - trunkH - 6;

        // Canopy scale: shrinks 100% -> 60% as ratio falls from 1.0 -> 0.
        var canopyScale = 0.6 + 0.4 * clip(ratio, 0, 1);
        var baseR = small ? 34 : 70;
        var canopyR = baseR * canopyScale;
        var canopyCx = W / 2, canopyCy = H - trunkH - canopyR + 26;

        var maxApples = small ? 6 : 14;
        var apples = Math.min(maxApples, Math.max(0, Math.round(reward / 6)));

        // Deterministic apple slots on canopy
        var slots = [
            [-50, 5], [-32, -25], [-12, -42], [12, -42], [34, -28], [52, 0],
            [-40, 22], [-18, 8], [8, 12], [30, 22], [-22, -10], [22, -8],
            [0, -22], [-46, -12],
        ];

        var s = '<svg class="tree-svg" width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H + '" xmlns="http://www.w3.org/2000/svg">';
        s += '<defs>'
          + '<radialGradient id="canopyGrad" cx="0.4" cy="0.4" r="0.7">'
          +   '<stop offset="0%" stop-color="#86efac"/>'
          +   '<stop offset="100%" stop-color="#15803d"/>'
          + '</radialGradient>'
          + '<linearGradient id="trunkGrad" x1="0" y1="0" x2="1" y2="0">'
          +   '<stop offset="0%" stop-color="#92400e"/>'
          +   '<stop offset="100%" stop-color="#78350f"/>'
          + '</linearGradient>'
          + '</defs>';

        // Shadow under tree
        s += '<ellipse cx="' + (W / 2) + '" cy="' + (H - 4) + '" rx="' + (trunkW * 1.8) + '" ry="4" fill="rgba(0,0,0,0.15)"/>';
        // Trunk
        s += '<rect x="' + trunkX + '" y="' + trunkY + '" width="' + trunkW + '" height="' + trunkH + '" rx="3" fill="url(#trunkGrad)"/>';

        if (apples === 0 && ratio < 0.25) {
            // Bare/dead tree: branches + muted canopy hint
            s += '<g stroke="#6b4226" stroke-width="' + (small ? 1.4 : 2.2) + '" fill="none" stroke-linecap="round">';
            s += '<line x1="' + canopyCx + '" y1="' + (canopyCy + 10) + '" x2="' + (canopyCx - 24) + '" y2="' + (canopyCy - 18) + '"/>';
            s += '<line x1="' + canopyCx + '" y1="' + (canopyCy + 10) + '" x2="' + (canopyCx + 26) + '" y2="' + (canopyCy - 20) + '"/>';
            s += '<line x1="' + canopyCx + '" y1="' + (canopyCy + 4) + '" x2="' + canopyCx + '" y2="' + (canopyCy - 28) + '"/>';
            s += '</g>';
            if (!small) {
                s += '<text x="' + (W / 2) + '" y="' + (canopyCy + 4) + '" font-size="11" fill="#6b7280" text-anchor="middle" font-family="system-ui">depleted</text>';
            }
        } else {
            // Canopy (3 overlapping circles, scale-adjusted)
            s += '<circle cx="' + (canopyCx - canopyR * 0.38) + '" cy="' + canopyCy + '" r="' + (canopyR - canopyR * 0.12) + '" fill="url(#canopyGrad)"/>';
            s += '<circle cx="' + (canopyCx + canopyR * 0.38) + '" cy="' + canopyCy + '" r="' + (canopyR - canopyR * 0.15) + '" fill="url(#canopyGrad)"/>';
            s += '<circle cx="' + canopyCx + '" cy="' + (canopyCy - canopyR * 0.2) + '" r="' + (canopyR - canopyR * 0.08) + '" fill="url(#canopyGrad)"/>';

            for (var i = 0; i < apples; i++) {
                var sx = canopyCx + slots[i][0] * canopyScale;
                var sy = canopyCy + slots[i][1] * canopyScale;
                var ar = small ? 4 : 6;
                s += '<circle cx="' + sx + '" cy="' + sy + '" r="' + ar + '" fill="#dc2626" stroke="#7f1d1d" stroke-width="1"/>';
                s += '<circle cx="' + (sx - 1.5) + '" cy="' + (sy - 2) + '" r="' + (small ? 0.9 : 1.5) + '" fill="#fca5a5"/>';
                if (!small) s += '<line x1="' + sx + '" y1="' + (sy - 6) + '" x2="' + (sx + 1) + '" y2="' + (sy - 9) + '" stroke="#15803d" stroke-width="1.5"/>';
            }
        }
        s += '</svg>';
        return s;
    }

    function basketHTML(total) {
        // Cap pile apples at 14 visible regardless of total
        var pileApples = Math.min(14, Math.max(0, Math.round(total / 10)));
        var slots = [
            [10,16], [30,10], [50,14], [70,10], [90,16],
            [20,4], [40,2], [60,4], [80,2],
            [15,22], [55,22], [95,20], [35,20], [75,22],
        ];
        var pile = "";
        for (var i = 0; i < pileApples; i++) {
            pile += '<div class="pile-apple" style="left:' + slots[i][0] + 'px;bottom:' + slots[i][1] + 'px;"></div>';
        }
        return '<div class="basket-anchor" id="basket">' +
                   '<div class="basket-count" id="basket-count">' + total + ' apples</div>' +
                   '<div class="basket-pile">' + pile + '</div>' +
                   '<div class="basket-rim"></div>' +
                   '<div class="basket-body"></div>' +
               '</div>';
    }

    function sceneStageHTML(state, mode) {
        // mode: "decision" | "harvest" | "travel"
        var ratio = state.patch_start_reward > 0 ? state.current_reward / state.patch_start_reward : 0;
        var treeWilt = ratio < 0.5 ? "wilt" : "";
        var reward = state.current_reward;

        var horizon =
            '<div class="horizon-tree t1">' + svgTree(60, 1.0, true) + '</div>' +
            '<div class="horizon-tree t2">' + svgTree(60, 1.0, true) + '</div>' +
            '<div class="horizon-tree t3">' + svgTree(60, 1.0, true) + '</div>';

        var sky =
            '<div class="sun"></div>' +
            '<div class="cloud c1"></div>' +
            '<div class="cloud c2"></div>';

        var tree =
            '<div class="tree-slot ' + treeWilt + '" id="tree-slot">' +
                svgTree(reward, ratio, false) +
            '</div>';

        var travel = "";
        if (mode === "travel") {
            travel =
                '<div class="outcome-banner travel">leaving patch · walking to new tree</div>' +
                '<div class="travel-progress"><div class="bar" id="travel-bar"></div></div>' +
                '<div class="travel-label" id="travel-label">travelling...</div>' +
                '<div class="walker" id="walker"><span class="bob">🚶</span></div>';
        }

        var harvestBanner = "";
        if (mode === "harvest") {
            harvestBanner = '<div class="outcome-banner harvest" id="outcome-banner">+<span id="harvest-amt">0</span> apples harvested</div>';
        }

        return '<div class="scene-stage" id="scene-stage">' +
                   sky +
                   '<div class="ground-path"></div>' +
                   '<div class="trail"></div>' +
                   (mode === "travel" ? "" : tree) +
                   (mode === "travel" ? "" : horizon) +
                   (mode === "travel" ? "" : basketHTML(state.block_total)) +
                   travel +
                   harvestBanner +
               '</div>';
    }

    function hudHTML(state) {
        var pct = Math.round(100 * state.trial_in_block / CONFIG.trials_per_block);
        return '<div class="hud">' +
                   '<div>Tree ' + state.patch_id + ' · harvest #' + (state.harvest_in_patch + 1) + '</div>' +
                   '<div class="progress-track"><div class="progress-fill" style="width:' + pct + '%"></div></div>' +
                   '<div>Trial <span class="running">' + (state.trial_in_block + 1) + '</span> / ' + CONFIG.trials_per_block + '</div>' +
               '</div>';
    }

    function decisionSceneHTML(state) {
        return blockBanner(state.condition) +
               "<div class='scene-card'>" +
                   hudHTML(state) +
                   sceneStageHTML(state, "decision") +
                   "<div class='reward-offer'>" + Math.round(state.current_reward) +
                       "<span class='unit'>apples if you STAY</span></div>" +
                   "<div class='patch-meta'>Leaving costs " + CONFIG.travel_cost_seconds[state.condition] +
                       "s of travel · Avg per decision so far: <strong>" + state.running_avg.toFixed(1) + "</strong></div>" +
                   "<div class='key-row'>" +
                       "<div class='choice-stay'><span class='key-hint'>F</span> STAY (harvest)</div>" +
                       "<div class='choice-leave'><span class='key-hint'>J</span> LEAVE (travel)</div>" +
                   "</div>" +
               "</div>";
    }

    function outcomeSceneHTML(state, mode) {
        return blockBanner(state.condition) +
               "<div class='scene-card'>" +
                   hudHTML(state) +
                   sceneStageHTML(state, mode) +
                   (mode === "harvest"
                       ? "<div class='reward-offer' style='color:#15803d'>+<span id='outcome-delta'>0</span><span class='unit'>apples in the basket</span></div>"
                       : "<div class='reward-offer' style='color:#92400e'>Walking to the next tree</div>") +
                   "<div class='patch-meta'>&nbsp;</div>" +
               "</div>";
    }

    // --- Animations ---
    function animateHarvestFlight(amount, finalBasketTotal) {
        var stage = document.getElementById("scene-stage");
        var basket = document.getElementById("basket");
        var count = document.getElementById("basket-count");
        var deltaEl = document.getElementById("outcome-delta");
        var bannerAmt = document.getElementById("harvest-amt");
        if (!stage || !basket || !count) return;

        if (bannerAmt) bannerAmt.textContent = amount;

        // Animate the "+N in the basket" digit counter from 0 -> amount
        if (deltaEl) {
            var start = performance.now();
            var dur = 500;
            function tickDelta(now) {
                var p = Math.min(1, (now - start) / dur);
                deltaEl.textContent = Math.round(amount * p);
                if (p < 1) requestAnimationFrame(tickDelta);
            }
            requestAnimationFrame(tickDelta);
        }

        // Fly 3 apples from the canopy to the basket in quick succession
        var stageRect = stage.getBoundingClientRect();
        var basketRect = basket.getBoundingClientRect();
        var targetX = basketRect.left - stageRect.left + 40;
        var targetY = basketRect.top - stageRect.top + 20;

        var treeCanopyX = stageRect.width * 0.32;
        var treeCanopyY = stageRect.height * 0.38;

        var n = Math.max(1, Math.min(3, Math.round(amount / 20) + 1));
        for (var k = 0; k < n; k++) {
            (function (idx) {
                setTimeout(function () {
                    var apple = document.createElement("div");
                    apple.className = "flying-apple";
                    var jitterX = (Math.random() - 0.5) * 40;
                    var jitterY = (Math.random() - 0.5) * 20;
                    apple.style.left = (treeCanopyX + jitterX) + "px";
                    apple.style.top = (treeCanopyY + jitterY) + "px";
                    apple.innerHTML = '<span class="leaf"></span>';
                    stage.appendChild(apple);

                    // Force reflow then animate
                    apple.getBoundingClientRect();
                    apple.style.transition = "left 480ms cubic-bezier(.4,.2,.6,1), top 480ms cubic-bezier(.5,-.2,.7,1.4)";
                    apple.style.left = (targetX + (Math.random() - 0.5) * 16) + "px";
                    apple.style.top = (targetY + (Math.random() - 0.5) * 6) + "px";

                    setTimeout(function () {
                        apple.remove();
                        if (count) {
                            count.textContent = finalBasketTotal + " apples";
                            count.classList.add("bump");
                            setTimeout(function () { count.classList.remove("bump"); }, 200);
                        }
                    }, 500);
                }, idx * 120);
            })(k);
        }

        // Shake the tree on impact
        var treeSlot = document.getElementById("tree-slot");
        if (treeSlot) {
            treeSlot.classList.add("shake");
            setTimeout(function () { treeSlot.classList.remove("shake"); }, 450);
        }
    }

    function animateTravel(durationMs) {
        var bar = document.getElementById("travel-bar");
        var walker = document.getElementById("walker");
        var label = document.getElementById("travel-label");
        if (!bar || !walker) return;
        var start = performance.now();
        function tick(now) {
            var elapsed = now - start;
            var p = Math.min(1, elapsed / durationMs);
            bar.style.width = (p * 100) + "%";
            // Walker goes from 6% -> 86% of stage width
            walker.style.left = (6 + p * 80) + "%";
            if (label) {
                var remain = Math.max(0, (durationMs - elapsed) / 1000);
                label.textContent = remain.toFixed(1) + "s to next tree";
            }
            if (p < 1) requestAnimationFrame(tick);
            else if (label) label.textContent = "arrived";
        }
        requestAnimationFrame(tick);
    }

    // --- Block runner ---
    function makeBlockRunner(block_idx, condition) {
        var nodes = [];
        var state = {
            block_idx: block_idx,
            condition: condition,
            trial_in_block: 0,
            patch_id: 0,
            harvest_in_patch: 0,
            current_reward: 0,
            patch_start_reward: 0,
            patch_decay_rate: 0,
            block_total: 0,
            block_decisions: 0,
            harvests_so_far_in_patch: 0,
            running_avg: 0,
        };

        function startNewPatch() {
            state.patch_id += 1;
            state.harvest_in_patch = 0;
            state.harvests_so_far_in_patch = 0;
            state.patch_decay_rate = clip(gaussian(CONFIG.decay_rate_mean, CONFIG.decay_rate_sd), 0.5, 0.99);
            var r0 = clip(gaussian(CONFIG.start_reward_mean, CONFIG.start_reward_sd), 10, 120);
            state.current_reward = r0;
            state.patch_start_reward = r0;
        }
        startNewPatch();

        // Block intro
        nodes.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                return blockBanner(state.condition) +
                       "<div class='intro-card'>" +
                           "<h2>Starting block " + block_idx + " of " + CONFIG.n_blocks + "</h2>" +
                           "<p>This block contains <strong>" + CONFIG.trials_per_block + "</strong> stay/leave decisions.</p>" +
                           "<ul>" +
                               "<li><strong style='color:#15803d'>STAY</strong> — harvest the current tree. The apple count shrinks with each harvest.</li>" +
                               "<li><strong style='color:#b91c1c'>LEAVE</strong> — walk to a fresh tree. Travel takes <strong>" +
                                   CONFIG.travel_cost_seconds[state.condition] +
                                   " seconds</strong> that you cannot harvest in.</li>" +
                           "</ul>" +
                           "<p style='color:#6b7280'>Press any key to begin.</p>" +
                       "</div>";
            },
        });

        function makeDecisionTrial() {
            return {
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    state.running_avg = state.block_decisions > 0 ? state.block_total / state.block_decisions : 0;
                    return decisionSceneHTML(state);
                },
                choices: CONFIG.valid_keys,
                trial_duration: CONFIG.response_deadline,
                data: { trial_part: "decision", block: block_idx, block_condition: state.condition },
                on_finish: function (data) {
                    var timed_out = data.response === null;
                    var pre_avg = state.block_decisions > 0 ? state.block_total / state.block_decisions : 0;
                    var pre_current_reward = state.current_reward;
                    var pre_harvest_in_patch = state.harvest_in_patch;
                    var pre_patch_id = state.patch_id;

                    var mvt_stay = pre_current_reward >= pre_avg;
                    var mvt_optimal_action = mvt_stay ? "stay" : "leave";

                    var action;
                    if (timed_out) {
                        action = "leave";
                    } else if (data.response === CONFIG.key_mapping.stay) {
                        action = "stay";
                    } else if (data.response === CONFIG.key_mapping.leave) {
                        action = "leave";
                    } else {
                        action = "leave";
                    }

                    var harvest_reward = 0;
                    var harvests_stayed_in_patch = state.harvests_so_far_in_patch;
                    if (action === "stay") {
                        harvest_reward = Math.round(pre_current_reward);
                        state.block_total += harvest_reward;
                        state.current_reward = pre_current_reward * state.patch_decay_rate;
                        state.harvest_in_patch += 1;
                        state.harvests_so_far_in_patch += 1;
                    } else {
                        startNewPatch();
                    }

                    state.trial_in_block += 1;
                    state.block_decisions += 1;

                    Object.assign(data, {
                        trial_part: "decision",
                        block: block_idx,
                        block_condition: state.condition,
                        travel_cost_seconds: CONFIG.travel_cost_seconds[state.condition],
                        patch_id: pre_patch_id,
                        harvest_in_patch: pre_harvest_in_patch + 1,
                        current_reward_offered: Math.round(pre_current_reward),
                        running_block_avg_per_decision: Number(pre_avg.toFixed(2)),
                        action: action,
                        is_stay: action === "stay",
                        harvest_reward: harvest_reward,
                        harvest_reward_above_chance: harvest_reward > 25,
                        harvests_stayed_in_patch: action === "leave" ? harvests_stayed_in_patch : null,
                        mvt_optimal_action: mvt_optimal_action,
                        mvt_optimal_match: action === mvt_optimal_action,
                        timed_out: timed_out,
                    });
                },
            };
        }

        function makeOutcomeTrial() {
            return {
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    var last = jsPsych.data.get().last(1).values()[0];
                    if (!last) return "";
                    var mode = last.action === "stay" ? "harvest" : "travel";
                    return outcomeSceneHTML(state, mode);
                },
                choices: "NO_KEYS",
                trial_duration: function () {
                    var last = jsPsych.data.get().last(1).values()[0];
                    if (last && last.action === "leave") {
                        return CONFIG.travel_cost_seconds[state.condition] * 1000;
                    }
                    return CONFIG.harvest_animation;
                },
                on_load: function () {
                    var last = jsPsych.data.get().last(1).values()[0];
                    if (!last) return;
                    if (last.action === "stay") {
                        animateHarvestFlight(last.harvest_reward, state.block_total);
                    } else {
                        animateTravel(CONFIG.travel_cost_seconds[state.condition] * 1000);
                    }
                },
                data: { trial_part: "outcome", block: block_idx },
            };
        }

        for (var t = 0; t < CONFIG.trials_per_block; t++) {
            nodes.push(makeDecisionTrial());
            nodes.push(makeOutcomeTrial());
        }

        // Block summary
        nodes.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                var avg = state.block_decisions > 0 ? (state.block_total / state.block_decisions).toFixed(1) : "0";
                return blockBanner(state.condition) +
                       "<div class='summary-card'>" +
                           "<h2>Block " + block_idx + " complete</h2>" +
                           "<p>You harvested <strong>" + state.block_total + "</strong> apples across " +
                           state.block_decisions + " decisions (avg " + avg + " per decision).</p>" +
                           "<p style='color:#6b7280'>Press any key to continue.</p>" +
                       "</div>";
            },
            trial_duration: 8000,
        });

        return nodes;
    }

    // --- Build the timeline ---
    var timeline = [];
    var BLOCK_ORDER = shuffle(CONFIG.block_conditions.slice());

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<div class='intro-card'>" +
                "<h1 style='text-align:center'>Effort Foraging — Apple Patches</h1>" +
                "<p style='text-align:center;color:#6b7280'>Press any key to begin.</p>" +
            "</div>",
    });

    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<div class='intro-card'>" +
            "<h2>Instructions</h2>" +
            "<p>You are foraging for apples in an orchard.</p>" +
            "<p>On every trial you see <strong>one tree</strong> and the number of apples you would get by harvesting it.</p>" +
            "<p>Each time you harvest the same tree, the canopy thins and the count shrinks — the tree is depleting.</p>" +
            "</div>",

            "<div class='intro-card'>" +
            "<h2>Two choices each trial</h2>" +
            "<p><strong style='color:#15803d'>STAY</strong> (press <span class='key-hint'>F</span>): harvest the current tree. You collect the apples shown, but the next harvest from this tree will give fewer.</p>" +
            "<p><strong style='color:#b91c1c'>LEAVE</strong> (press <span class='key-hint'>J</span>): walk to a fresh tree. The new tree starts with a full canopy, but travelling takes time you cannot harvest in.</p>" +
            "<p>Each tree's starting reward is drawn independently — the new tree isn't necessarily richer than the one you left.</p>" +
            "</div>",

            "<div class='intro-card'>" +
            "<h2>Two blocks</h2>" +
            "<p>You will play two blocks in random order.</p>" +
            "<p><span class='block-banner low'><span class='dot'></span>Low-cost travel</span> — walking to a new tree takes " + CONFIG.travel_cost_seconds.low_cost + " seconds.</p>" +
            "<p><span class='block-banner high'><span class='dot'></span>High-cost travel</span> — walking to a new tree takes " + CONFIG.travel_cost_seconds.high_cost + " seconds.</p>" +
            "<p>Each block contains <strong>" + CONFIG.trials_per_block + "</strong> stay/leave decisions.</p>" +
            "</div>",

            "<div class='intro-card'>" +
            "<h2>Goal</h2>" +
            "<p>Maximize the total apples you collect across both blocks.</p>" +
            "<p>Ecological theory (the marginal value theorem) predicts you should stay longer in each patch when travel is expensive, and leave sooner when travel is cheap.</p>" +
            "<p style='text-align:center;margin-top:20px'><span class='key-hint'>F</span> to STAY · <span class='key-hint'>J</span> to LEAVE</p>" +
            "<p style='text-align:center;color:#6b7280'>You have " + Math.round(CONFIG.response_deadline / 1000) +
            " seconds per decision.</p>" +
            "</div>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    for (var b = 0; b < BLOCK_ORDER.length; b++) {
        var nodes = makeBlockRunner(b + 1, BLOCK_ORDER[b]);
        for (var n = 0; n < nodes.length; n++) timeline.push(nodes[n]);
    }

    // --- Data submission ---
    timeline.push({
        type: jsPsychCallFunction,
        async: true,
        func: function (done) {
            var trial_data = jsPsych.data.get().filter({ trial_part: "decision" }).values();
            for (var i = 0; i < trial_data.length; i++) trial_data[i].trial_index = i + 1;
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
                .catch(function (error) { console.error("Data submission error:", error); done(); });
        },
    });

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<div class='summary-card' style='text-align:center'>" +
                "<h2>Task Complete</h2>" +
                "<p>Thank you for foraging.</p>" +
                "<p style='color:#6b7280'>Your data has been submitted.</p>" +
            "</div>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
