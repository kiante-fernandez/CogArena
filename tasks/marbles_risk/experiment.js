(function () {
    var CONFIG = {
        n_practice_trials: 4,
        n_repetitions: 4,
        safe_value: 5,
        probabilities: [0.125, 0.25, 0.375, 0.5, 0.675, 0.75],
        gamble_values: [8, 20, 50],
        excluded_combinations: [[0.25, 8], [0.75, 50]],
        valid_keys: ["f", "j"],
        response_deadline: 8000,
        fixation_duration: 500,
        iti_min: 400,
        iti_max: 800,
        urn_size: 8,             // marbles displayed in the urn schematic
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "marbles_risk";

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });
    if (SESSION_ID === "debug") window._jsPsych = jsPsych;

    // ---- Trial generation ----
    function isExcluded(prob, val) {
        for (var i = 0; i < CONFIG.excluded_combinations.length; i++) {
            var ex = CONFIG.excluded_combinations[i];
            if (Math.abs(ex[0] - prob) < 1e-9 && ex[1] === val) return true;
        }
        return false;
    }

    function buildTrials() {
        var combos = [];
        for (var pi = 0; pi < CONFIG.probabilities.length; pi++) {
            for (var vi = 0; vi < CONFIG.gamble_values.length; vi++) {
                var p = CONFIG.probabilities[pi];
                var v = CONFIG.gamble_values[vi];
                if (isExcluded(p, v)) continue;
                combos.push({ probability: p, gamble_value: v });
            }
        }
        var trials = [];
        var rep_max = CONFIG.n_repetitions;
        var _nto = parseInt(urlParams.get("n_trials"));
        if (!isNaN(_nto) && _nto > 0) {
            rep_max = Math.max(1, Math.ceil(_nto / combos.length));
        }
        for (var r = 0; r < rep_max; r++) {
            for (var c = 0; c < combos.length; c++) {
                var combo = combos[c];
                var safe_position = Math.random() < 0.5 ? "left" : "right";
                var ev_risky = combo.probability * combo.gamble_value;
                var ev_diff = ev_risky - CONFIG.safe_value;
                var key_higher_ev = null;
                if (Math.abs(ev_diff) >= 0.05) {
                    var risky_is_better = ev_diff > 0;
                    var risky_position = safe_position === "left" ? "right" : "left";
                    var winning_position = risky_is_better ? risky_position : safe_position;
                    key_higher_ev = winning_position === "left" ? "f" : "j";
                }
                trials.push({
                    probability: combo.probability,
                    gamble_value: combo.gamble_value,
                    safe_value: CONFIG.safe_value,
                    ev_risky: ev_risky,
                    ev_diff: ev_diff,
                    safe_position: safe_position,
                    correct_key_higher_ev: key_higher_ev,
                });
            }
        }
        // Shuffle.
        for (var i = trials.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var t = trials[i]; trials[i] = trials[j]; trials[j] = t;
        }
        if (!isNaN(_nto) && _nto > 0) trials = trials.slice(0, _nto);
        return trials;
    }

    // ---- Urn rendering: SVG urn with marbles inside ----
    function urnHtml(prob, n_marbles) {
        n_marbles = n_marbles || CONFIG.urn_size;
        var n_win = Math.round(prob * n_marbles);
        var W = 130, H = 110;
        var s = '<svg class="urn-svg" width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H + '" xmlns="http://www.w3.org/2000/svg">';
        // Defs: gradient for urn body
        s += '<defs>'
          + '<linearGradient id="urnGrad" x1="0" y1="0" x2="1" y2="0">'
          +   '<stop offset="0%" stop-color="#9ca3af"/>'
          +   '<stop offset="50%" stop-color="#e5e7eb"/>'
          +   '<stop offset="100%" stop-color="#6b7280"/>'
          + '</linearGradient>'
          + '<radialGradient id="winMarble" cx="0.35" cy="0.35" r="0.6">'
          +   '<stop offset="0%" stop-color="#60a5fa"/>'
          +   '<stop offset="100%" stop-color="#1e40af"/>'
          + '</radialGradient>'
          + '<radialGradient id="loseMarble" cx="0.35" cy="0.35" r="0.6">'
          +   '<stop offset="0%" stop-color="#fbbf24"/>'
          +   '<stop offset="100%" stop-color="#92400e"/>'
          + '</radialGradient>'
          + '</defs>';

        // Urn shape (vase-like outline)
        var urnPath = 'M 25 28 ' +                           // top-left rim
            'Q 25 22 30 22 ' +                                // rounded rim corner
            'L 100 22 ' +
            'Q 105 22 105 28 ' +
            'L 105 38 ' +
            'Q 120 50 120 70 ' +                              // outer right curve
            'Q 120 100 90 105 ' +                             // bottom right
            'L 40 105 ' +
            'Q 10 100 10 70 ' +                               // outer left curve
            'Q 10 50 25 38 Z';
        s += '<path d="' + urnPath + '" fill="url(#urnGrad)" stroke="#374151" stroke-width="2"/>';

        // Inner shadow at the top of urn
        s += '<rect x="28" y="24" width="74" height="6" rx="3" fill="#1f2937" opacity="0.35"/>';

        // Marbles inside the urn — arrange in rows.
        // Place ~2 rows of 4-5 marbles in the wider lower body.
        var positions = [
            [38, 60], [55, 60], [72, 60], [89, 60],
            [30, 78], [47, 78], [64, 78], [81, 78], [98, 78],
        ];
        // Shuffle deterministically by seed of prob to mix win/lose visually.
        var indices = positions.map(function (_, i) { return i; });
        // Place wins first; we'll randomize placement by simple mod.
        var win_set = new Set();
        for (var k = 0; k < n_win; k++) win_set.add(k);
        for (var i = 0; i < n_marbles && i < positions.length; i++) {
            var pos = positions[i];
            var isWin = win_set.has(i);
            var grad = isWin ? "url(#winMarble)" : "url(#loseMarble)";
            s += '<circle cx="' + pos[0] + '" cy="' + pos[1] + '" r="7" fill="' + grad + '" stroke="#1f2937" stroke-width="0.8"/>';
            // Highlight reflection
            s += '<circle cx="' + (pos[0] - 1.5) + '" cy="' + (pos[1] - 2) + '" r="1.6" fill="#ffffff" opacity="0.7"/>';
        }
        s += '</svg>';

        var pct = Math.round(prob * 1000) / 10;
        return s + '<div class="urn-caption"><span class="win-marble-key">●</span> ' +
            n_win + ' of ' + n_marbles + ' = <strong>' + pct + '%</strong> win chance</div>';
    }

    function safeCardHtml(safe_val) {
        return '<div class="option-label">SAFE</div>' +
            '<div class="option-content">' +
            '<div class="option-payoff"><span class="reward">' + safe_val + ' points</span> for sure</div>' +
            '</div>';
    }

    function riskyCardHtml(prob, val) {
        return '<div class="option-label">RISKY</div>' +
            '<div class="option-content">' +
            urnHtml(prob) +
            '<div class="option-payoff">' +
            '<span class="reward">' + val + ' points</span> if you win<br>' +
            '<span class="zero">0 points</span> if you lose</div>' +
            '</div>';
    }

    function trialStimulusHtml(trial) {
        var safe_html = safeCardHtml(trial.safe_value);
        var risky_html = riskyCardHtml(trial.probability, trial.gamble_value);
        var left_html = trial.safe_position === "left" ? safe_html : risky_html;
        var right_html = trial.safe_position === "left" ? risky_html : safe_html;
        return '<div class="stim-prompt">Choose one option. Press <kbd>F</kbd> for left, <kbd>J</kbd> for right.</div>' +
            '<table class="marble-table"><tr>' +
            '<td class="option-cell"><div class="option-card">' + left_html + '<div class="key-hint">F</div></div></td>' +
            '<td class="center-cell"><div class="center-cross">+</div></td>' +
            '<td class="option-cell"><div class="option-card">' + right_html + '<div class="key-hint">J</div></div></td>' +
            '</tr></table>';
    }

    var timeline = [];

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Marbles: Risky Choice</h1>" +
            "<p>Welcome. Press any key to begin.</p>",
    });

    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>On every trial you will see two options.</p>" +
            "<p>The <strong>SAFE</strong> option always pays " + CONFIG.safe_value + " points for sure.</p>" +
            "<p>The <strong>RISKY</strong> option pays a higher amount with some probability, otherwise 0.</p>",

            "<h2>Reading the urn</h2>" +
            "<p>The risky option is shown as an urn with " + CONFIG.urn_size + " marbles.</p>" +
            "<p>" + Math.round(0.5 * CONFIG.urn_size) + " marbles are <span style='color:#1f6fb2;font-weight:bold'>blue</span> means a 50% chance to win.</p>" +
            "<p>The exact percentage is also written below the urn.</p>",

            "<h2>Response Keys</h2>" +
            "<p>Press <kbd>F</kbd> to choose the option on the left.</p>" +
            "<p>Press <kbd>J</kbd> to choose the option on the right.</p>" +
            "<p>You have up to " + Math.round(CONFIG.response_deadline / 1000) + " seconds per trial.</p>" +
            "<p>Press Next to start a few practice trials.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    var fixation = {
        type: jsPsychHtmlKeyboardResponse,
        stimulus: '<div class="fixation">+</div>',
        choices: "NO_KEYS",
        trial_duration: CONFIG.fixation_duration,
        data: { trial_part: "fixation" },
    };

    var iti = {
        type: jsPsychHtmlKeyboardResponse,
        stimulus: "",
        choices: "NO_KEYS",
        trial_duration: function () {
            return CONFIG.iti_min + Math.random() * (CONFIG.iti_max - CONFIG.iti_min);
        },
        data: { trial_part: "iti" },
    };

    var trial_counter = 0;

    function makeStimulusTrial(is_practice) {
        return {
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                var trial = jsPsych.evaluateTimelineVariable("__trial");
                return trialStimulusHtml(trial);
            },
            choices: CONFIG.valid_keys,
            trial_duration: CONFIG.response_deadline,
            data: function () {
                var t = jsPsych.evaluateTimelineVariable("__trial");
                return {
                    trial_part: "stimulus",
                    practice: !!is_practice,
                    probability: t.probability,
                    gamble_value: t.gamble_value,
                    safe_value: t.safe_value,
                    ev_risky: t.ev_risky,
                    ev_diff: t.ev_diff,
                    safe_position: t.safe_position,
                    correct_key_higher_ev: t.correct_key_higher_ev,
                    has_clear_better: Math.abs(t.ev_diff) >= 0.05,
                    near_neutral_ev: Math.abs(t.ev_diff) <= 1.0,
                };
            },
            on_finish: function (data) {
                if (!is_practice) {
                    trial_counter++;
                    data.trial_index = trial_counter;
                } else {
                    data.trial_index = -1;
                }
                if (data.response === null) {
                    data.timed_out = true;
                    data.chose_risky = null;
                    data.chose_higher_ev = null;
                } else {
                    data.timed_out = false;
                    var picked_position = data.response === "f" ? "left" : "right";
                    data.chose_risky = (picked_position !== data.safe_position);
                    if (data.correct_key_higher_ev !== null) {
                        data.chose_higher_ev = (data.response === data.correct_key_higher_ev);
                    } else {
                        data.chose_higher_ev = null;
                    }
                }
            },
        };
    }

    var practice_trials = (function () {
        // 4 practice trials at extreme prob/value combos so the gradient is obvious.
        var t1 = { probability: 0.5, gamble_value: 20, safe_value: CONFIG.safe_value, ev_risky: 10, ev_diff: 5, safe_position: "left", correct_key_higher_ev: "j" };
        var t2 = { probability: 0.125, gamble_value: 8, safe_value: CONFIG.safe_value, ev_risky: 1.0, ev_diff: -4.0, safe_position: "right", correct_key_higher_ev: "j" };
        var t3 = { probability: 0.5, gamble_value: 8, safe_value: CONFIG.safe_value, ev_risky: 4.0, ev_diff: -1.0, safe_position: "left", correct_key_higher_ev: "f" };
        var t4 = { probability: 0.75, gamble_value: 20, safe_value: CONFIG.safe_value, ev_risky: 15, ev_diff: 10, safe_position: "right", correct_key_higher_ev: "f" };
        return [t1, t2, t3, t4].map(function (t) { return { __trial: t }; });
    })();

    timeline.push({
        timeline: [fixation, makeStimulusTrial(true), iti],
        timeline_variables: practice_trials,
        randomize_order: true,
    });

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>End of Practice</h2>" +
            "<p>The main task will now begin.</p>" +
            "<p>Press any key to start.</p>",
    });

    var trials = buildTrials();
    var trial_vars = trials.map(function (t) { return { __trial: t }; });

    timeline.push({
        timeline: [fixation, makeStimulusTrial(false), iti],
        timeline_variables: trial_vars,
        randomize_order: false,    // already shuffled
    });

    // Data submission
    timeline.push({
        type: jsPsychCallFunction,
        async: true,
        func: function (done) {
            var trial_data = jsPsych.data
                .get()
                .filter({ trial_part: "stimulus", practice: false })
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
            "<p>Thank you for completing the marbles task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
