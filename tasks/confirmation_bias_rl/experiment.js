(function () {
    var CONFIG = {
        n_contexts: 4,
        trials_per_context: 24,
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
    var TASK_ID = "confirmation_bias_rl";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.trials_per_context = Math.ceil(_nto / CONFIG.n_contexts);
    }

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    // Contexts: 4 symbol pairs, each with different reward probabilities
    // 2 partial feedback (see chosen only) + 2 complete feedback (see both)
    var CONTEXTS = [
        { id: 0, feedback_type: "partial",  p_left: 0.75, p_right: 0.25, symbols: ["\u25B2", "\u25BC"] },
        { id: 1, feedback_type: "partial",  p_left: 0.25, p_right: 0.75, symbols: ["\u25C6", "\u25CF"] },
        { id: 2, feedback_type: "complete", p_left: 0.75, p_right: 0.25, symbols: ["\u2605", "\u2736"] },
        { id: 3, feedback_type: "complete", p_left: 0.25, p_right: 0.75, symbols: ["\u2666", "\u2663"] },
    ];

    function generateTrials() {
        var trials = [];
        for (var c = 0; c < CONTEXTS.length; c++) {
            for (var t = 0; t < CONFIG.trials_per_context; t++) {
                trials.push({
                    context: CONTEXTS[c],
                    trial_in_context: t,
                });
            }
        }
        // Shuffle: interleave contexts
        for (var i = trials.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var tmp = trials[i];
            trials[i] = trials[j];
            trials[j] = tmp;
        }
        return trials;
    }

    var allTrials = generateTrials();
    var timeline = [];

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Confirmation Bias RL</h1>" +
            "<p>Welcome to this learning task.</p>" +
            "<p>Press any key to begin.</p>",
    });

    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>In this task, you will see pairs of symbols on each trial.</p>" +
            "<p>Each symbol has a hidden probability of giving you a <strong>reward (+1)</strong> or a <strong>penalty (\u22121)</strong>.</p>" +
            "<p>Your goal is to learn which symbol is better in each pair and earn as many points as possible.</p>",

            "<h2>Feedback Types</h2>" +
            "<p>For some symbol pairs, you will only see the outcome of <strong>your chosen</strong> symbol (partial feedback).</p>" +
            "<p>For other pairs, you will see the outcomes of <strong>both</strong> symbols \u2014 the one you chose and the one you didn\u2019t (complete feedback).</p>" +
            "<p>Use all available feedback to learn which symbols are better.</p>",

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

    var trialCounter = 0;
    var contextCounters = {};
    CONTEXTS.forEach(function (c) { contextCounters[c.id] = 0; });

    for (var ti = 0; ti < allTrials.length; ti++) {
        (function (trialInfo) {
            var ctx = trialInfo.context;

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
                    var ctxNum = contextCounters[ctx.id] + 1;
                    var totalTrials = CONFIG.trials_per_context;
                    var feedbackLabel = ctx.feedback_type === "complete" ? "Complete Feedback" : "Partial Feedback";
                    return '<div class="trial-counter">Trial ' + (trialCounter + 1) + ' of ' + allTrials.length + '</div>' +
                        '<div class="context-label">' + feedbackLabel + '</div>' +
                        '<div class="bandit-container">' +
                        '<div class="bandit-option"><div style="font-size:64px">' + ctx.symbols[0] + '</div>' +
                        '<div class="bandit-label">Left</div>' +
                        '<div class="key-hint">F</div></div>' +
                        '<div class="bandit-option"><div style="font-size:64px">' + ctx.symbols[1] + '</div>' +
                        '<div class="bandit-label">Right</div>' +
                        '<div class="key-hint">J</div></div>' +
                        '</div>';
                },
                choices: CONFIG.valid_keys,
                trial_duration: CONFIG.response_deadline,
                data: {
                    trial_part: "stimulus",
                    context: ctx.id,
                    feedback_type: ctx.feedback_type,
                    p_left: ctx.p_left,
                    p_right: ctx.p_right,
                    symbol_left: ctx.symbols[0],
                    symbol_right: ctx.symbols[1],
                },
                on_finish: function (data) {
                    trialCounter++;
                    contextCounters[ctx.id]++;
                    data.trial_index = trialCounter;
                    data.timed_out = data.response === null;

                    if (!data.timed_out) {
                        var arm = data.response === "f" ? "left" : "right";
                        data.arm_chosen = arm;
                        var p_chosen = arm === "left" ? ctx.p_left : ctx.p_right;
                        var p_unchosen = arm === "left" ? ctx.p_right : ctx.p_left;
                        data.reward = Math.random() < p_chosen ? 1 : -1;
                        data.unchosen_reward = Math.random() < p_unchosen ? 1 : -1;
                        data.correct = (ctx.p_left >= ctx.p_right && arm === "left") ||
                                       (ctx.p_right > ctx.p_left && arm === "right");

                        // Win-stay / lose-shift
                        var prevTrials = jsPsych.data.get().filter({ trial_part: "stimulus", context: ctx.id }).values();
                        if (prevTrials.length >= 2) {
                            var prev = prevTrials[prevTrials.length - 2];
                            data.stayed = data.arm_chosen === prev.arm_chosen;
                            data.prev_reward = prev.reward;
                        }
                    } else {
                        data.arm_chosen = null;
                        data.reward = 0;
                        data.unchosen_reward = 0;
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
                        return '<div class="feedback-neg">Too slow! (0 points)</div>';
                    }
                    var chosenLabel = last.arm_chosen === "left" ? ctx.symbols[0] : ctx.symbols[1];
                    var unchosenLabel = last.arm_chosen === "left" ? ctx.symbols[1] : ctx.symbols[0];
                    var chosenClass = last.reward > 0 ? "feedback-win" : "feedback-lose";
                    var chosenText = last.reward > 0 ? "+1" : "\u22121";
                    var html = '<div class="bandit-container">';
                    html += '<div class="bandit-option"><div style="font-size:48px">' + chosenLabel + '</div>';
                    html += '<div class="' + chosenClass + '">Chosen: ' + chosenText + '</div></div>';

                    if (ctx.feedback_type === "complete") {
                        var unchosenClass = last.unchosen_reward > 0 ? "feedback-win" : "feedback-lose";
                        var unchosenText = last.unchosen_reward > 0 ? "+1" : "\u22121";
                        html += '<div class="bandit-option"><div style="font-size:48px">' + unchosenLabel + '</div>';
                        html += '<div class="feedback-unchosen">Unchosen: ' + unchosenText + '</div></div>';
                    } else {
                        html += '<div class="bandit-option"><div style="font-size:48px">' + unchosenLabel + '</div>';
                        html += '<div class="feedback-unchosen">???</div></div>';
                    }

                    html += '</div>';
                    return html;
                },
                choices: "NO_KEYS",
                trial_duration: CONFIG.feedback_duration,
                data: { trial_part: "feedback" },
            });

        })(allTrials[ti]);
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
            "<p>Thank you for completing the learning task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
