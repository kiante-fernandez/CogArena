(function () {
    var CONFIG = {
        n_learning_pairs: 4,
        trials_per_pair: 24,
        n_transfer_trials: 24,
        valid_keys: ["f", "j"],
        response_deadline: 5000,
        fixation_duration: 500,
        feedback_duration: 1500,
        iti_min: 300,
        iti_max: 600,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "magnitude_rl";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.trials_per_pair = Math.ceil((_nto - CONFIG.n_transfer_trials) / CONFIG.n_learning_pairs);
        if (CONFIG.trials_per_pair < 4) CONFIG.trials_per_pair = 4;
    }

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    // Learning pairs: 2 high-magnitude + 2 low-magnitude
    // Each pair has one 75% and one 25% reward probability
    // High magnitude: +10 / -10; Low magnitude: +1 / -1
    var PAIRS = [
        { id: 0, reward_magnitude: "high", mag_value: 10, p_left: 0.75, p_right: 0.25, symbols: ["\u25B2", "\u25BC"] },
        { id: 1, reward_magnitude: "high", mag_value: 10, p_left: 0.25, p_right: 0.75, symbols: ["\u25C6", "\u25CF"] },
        { id: 2, reward_magnitude: "low",  mag_value: 1,  p_left: 0.75, p_right: 0.25, symbols: ["\u2605", "\u2736"] },
        { id: 3, reward_magnitude: "low",  mag_value: 1,  p_left: 0.25, p_right: 0.75, symbols: ["\u2666", "\u2663"] },
    ];

    function generateLearningTrials() {
        var trials = [];
        for (var p = 0; p < PAIRS.length; p++) {
            for (var t = 0; t < CONFIG.trials_per_pair; t++) {
                trials.push({ pair: PAIRS[p], trial_in_pair: t });
            }
        }
        // Shuffle
        for (var i = trials.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var tmp = trials[i]; trials[i] = trials[j]; trials[j] = tmp;
        }
        return trials;
    }

    function generateTransferTrials() {
        // Transfer: pit best symbols from each pair against each other
        // Test if high-magnitude best symbol preferred over low-magnitude best symbol
        var bestSymbols = PAIRS.map(function (p) {
            var bestSide = p.p_left >= p.p_right ? "left" : "right";
            return {
                symbol: bestSide === "left" ? p.symbols[0] : p.symbols[1],
                pair_id: p.id,
                magnitude: p.reward_magnitude,
                mag_value: p.mag_value,
                original_p: Math.max(p.p_left, p.p_right),
            };
        });

        var trials = [];
        // All unique pairings of best symbols
        for (var i = 0; i < bestSymbols.length; i++) {
            for (var j = i + 1; j < bestSymbols.length; j++) {
                // 4 repetitions of each pairing
                for (var r = 0; r < 4; r++) {
                    // Randomize left/right
                    if (Math.random() > 0.5) {
                        trials.push({ left: bestSymbols[i], right: bestSymbols[j] });
                    } else {
                        trials.push({ left: bestSymbols[j], right: bestSymbols[i] });
                    }
                }
            }
        }
        // Shuffle
        for (var k = trials.length - 1; k > 0; k--) {
            var m = Math.floor(Math.random() * (k + 1));
            var tmp = trials[k]; trials[k] = trials[m]; trials[m] = tmp;
        }
        return trials;
    }

    var learningTrials = generateLearningTrials();
    var transferTrials = generateTransferTrials();
    var timeline = [];

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Magnitude RL</h1>" +
            "<p>Welcome to this learning task.</p>" +
            "<p>Press any key to begin.</p>",
    });

    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>In this task, you will see pairs of symbols on each trial.</p>" +
            "<p>Each symbol has a hidden probability of giving a <strong>reward</strong> or <strong>penalty</strong>.</p>" +
            "<p>Some symbols give <strong>large</strong> rewards/penalties, others give <strong>small</strong> ones.</p>" +
            "<p>Your goal is to learn which symbol is better in each pair.</p>",

            "<h2>Two Phases</h2>" +
            "<p><strong>Learning Phase:</strong> You will see symbol pairs and receive feedback after each choice.</p>" +
            "<p><strong>Transfer Phase:</strong> You will see new combinations of previously learned symbols. " +
            "Choose the symbol you think is better. No feedback will be given.</p>",

            "<h2>Response Keys</h2>" +
            "<p style='font-size:28px'><kbd>F</kbd> = <strong>Left Symbol</strong></p>" +
            "<p style='font-size:28px'><kbd>J</kbd> = <strong>Right Symbol</strong></p>" +
            "<p>You have 5 seconds to respond on each trial.</p>" +
            "<p>Press Next to start.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    // ---- Learning Phase ----
    var trialCounter = 0;

    for (var li = 0; li < learningTrials.length; li++) {
        (function (trialInfo) {
            var pair = trialInfo.pair;

            // Fixation
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: '<div class="fixation">+</div>',
                choices: "NO_KEYS",
                trial_duration: CONFIG.fixation_duration,
                data: { trial_part: "fixation" },
            });

            // Stimulus
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    var magLabel = pair.reward_magnitude === "high" ? "\u00B110" : "\u00B11";
                    return '<div class="trial-counter">Learning: Trial ' + (trialCounter + 1) + ' of ' + learningTrials.length + '</div>' +
                        '<div class="phase-label">Learning Phase \u2014 Magnitude: ' + magLabel + '</div>' +
                        '<div class="bandit-container">' +
                        '<div class="bandit-option"><div style="font-size:64px">' + pair.symbols[0] + '</div>' +
                        '<div class="key-hint">F</div></div>' +
                        '<div class="bandit-option"><div style="font-size:64px">' + pair.symbols[1] + '</div>' +
                        '<div class="key-hint">J</div></div>' +
                        '</div>';
                },
                choices: CONFIG.valid_keys,
                trial_duration: CONFIG.response_deadline,
                data: {
                    trial_part: "stimulus",
                    phase: "learning",
                    context: pair.id,
                    reward_magnitude: pair.reward_magnitude,
                    mag_value: pair.mag_value,
                    p_left: pair.p_left,
                    p_right: pair.p_right,
                },
                on_finish: function (data) {
                    trialCounter++;
                    data.trial_index = trialCounter;
                    data.timed_out = data.response === null;

                    if (!data.timed_out) {
                        var arm = data.response === "f" ? "left" : "right";
                        data.arm_chosen = arm;
                        var p_chosen = arm === "left" ? pair.p_left : pair.p_right;
                        var win = Math.random() < p_chosen;
                        data.reward = win ? pair.mag_value : -pair.mag_value;
                        data.correct = (pair.p_left >= pair.p_right && arm === "left") ||
                                       (pair.p_right > pair.p_left && arm === "right");

                        // Win-stay tracking
                        var prevTrials = jsPsych.data.get().filter({ trial_part: "stimulus", context: pair.id }).values();
                        if (prevTrials.length >= 2) {
                            var prev = prevTrials[prevTrials.length - 2];
                            data.stayed = data.arm_chosen === prev.arm_chosen;
                            data.prev_reward = prev.reward;
                        }
                    } else {
                        data.arm_chosen = null;
                        data.reward = 0;
                        data.correct = false;
                    }
                },
            });

            // Feedback
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    var last = jsPsych.data.get().last(1).values()[0];
                    if (last.timed_out) {
                        return '<div class="feedback-neg">Too slow!</div>';
                    }
                    var cls = last.reward > 0 ? "feedback-pos" : "feedback-neg";
                    var sign = last.reward > 0 ? "+" : "";
                    return '<div class="' + cls + '">' + sign + last.reward + ' points</div>';
                },
                choices: "NO_KEYS",
                trial_duration: CONFIG.feedback_duration,
                data: { trial_part: "feedback" },
            });

        })(learningTrials[li]);
    }

    // Transition screen
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Learning Phase Complete</h2>" +
            "<p>Now you will enter the <strong>Transfer Phase</strong>.</p>" +
            "<p>You will see new combinations of the symbols you learned.</p>" +
            "<p>Choose which symbol you think is better. No feedback will be shown.</p>" +
            "<p>Press any key to continue.</p>",
    });

    // ---- Transfer Phase ----
    for (var xi = 0; xi < transferTrials.length; xi++) {
        (function (tInfo) {
            // Fixation
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: '<div class="fixation">+</div>',
                choices: "NO_KEYS",
                trial_duration: CONFIG.fixation_duration,
                data: { trial_part: "fixation" },
            });

            // Stimulus
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    return '<div class="trial-counter">Transfer: Trial ' + (trialCounter - learningTrials.length + 1) + ' of ' + transferTrials.length + '</div>' +
                        '<div class="phase-label">Transfer Phase \u2014 No Feedback</div>' +
                        '<div class="bandit-container">' +
                        '<div class="bandit-option"><div style="font-size:64px">' + tInfo.left.symbol + '</div>' +
                        '<div class="key-hint">F</div></div>' +
                        '<div class="bandit-option"><div style="font-size:64px">' + tInfo.right.symbol + '</div>' +
                        '<div class="key-hint">J</div></div>' +
                        '</div>';
                },
                choices: CONFIG.valid_keys,
                trial_duration: CONFIG.response_deadline,
                data: {
                    trial_part: "stimulus",
                    phase: "transfer",
                    context: "transfer",
                    reward_magnitude: "mixed",
                    left_pair_id: tInfo.left.pair_id,
                    right_pair_id: tInfo.right.pair_id,
                    left_magnitude: tInfo.left.magnitude,
                    right_magnitude: tInfo.right.magnitude,
                },
                on_finish: function (data) {
                    trialCounter++;
                    data.trial_index = trialCounter;
                    data.timed_out = data.response === null;

                    if (!data.timed_out) {
                        var arm = data.response === "f" ? "left" : "right";
                        data.arm_chosen = arm;
                        // In transfer, "correct" = chose the symbol with higher original probability
                        var chosenInfo = arm === "left" ? tInfo.left : tInfo.right;
                        var otherInfo = arm === "left" ? tInfo.right : tInfo.left;
                        data.correct = chosenInfo.original_p >= otherInfo.original_p;
                        // Did they prefer high magnitude?
                        data.chose_high_magnitude = chosenInfo.magnitude === "high";
                        data.reward = 0; // no feedback
                        data.mag_value = 0;
                    } else {
                        data.arm_chosen = null;
                        data.correct = false;
                        data.chose_high_magnitude = false;
                        data.reward = 0;
                        data.mag_value = 0;
                    }
                },
            });

        })(transferTrials[xi]);
    }

    // Data submission
    timeline.push({
        type: jsPsychCallFunction,
        async: true,
        func: function (done) {
            var trial_data = jsPsych.data
                .get()
                .filter({ trial_part: "stimulus" })
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
            "<p>Thank you for completing the magnitude learning task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
