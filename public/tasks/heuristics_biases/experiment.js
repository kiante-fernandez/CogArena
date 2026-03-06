(function () {
    var CONFIG = {
        n_trials: 40,
        n_tasks: 10,
        trials_per_task: 4,
        n_cues: 4,
        valid_keys: ["f", "j"],
        response_deadline: 10000,
        fixation_duration: 500,
        feedback_duration: 800,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "heuristics_biases";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) CONFIG.n_trials = _nto;

    CONFIG.n_tasks = Math.ceil(CONFIG.n_trials / CONFIG.trials_per_task);

    var jsPsych = initJsPsych({ experiment_width: 800, minimum_valid_rt: 100 });
    if (SESSION_ID === "debug") window._jsPsych = jsPsych;

    // Cue labels for display
    var CUE_LABELS = ["Speed", "Stamina", "Strength", "Agility"];
    var COMPETITOR_NAMES = ["Alpha", "Beta"];

    function generateCueWeights() {
        // Generate random cue weights for a task (planet)
        // Weights determine which cues are diagnostic
        var weights = [];
        for (var i = 0; i < CONFIG.n_cues; i++) {
            weights.push(Math.random() * 2 - 1); // range [-1, 1]
        }
        return weights;
    }

    function generateTrialStimuli(weights) {
        // Generate cue values for two competitors and determine correct answer
        var cues_a = [];
        var cues_b = [];
        for (var i = 0; i < CONFIG.n_cues; i++) {
            cues_a.push(Math.floor(Math.random() * 81) + 10); // 10-90
            cues_b.push(Math.floor(Math.random() * 81) + 10);
        }

        // Weighted sum determines winner
        var score_a = 0;
        var score_b = 0;
        for (var j = 0; j < CONFIG.n_cues; j++) {
            score_a += weights[j] * cues_a[j];
            score_b += weights[j] * cues_b[j];
        }

        // Add noise
        score_a += (Math.random() - 0.5) * 10;
        score_b += (Math.random() - 0.5) * 10;

        var correct_answer = score_a > score_b ? "f" : "j";
        var cue_diff = [];
        for (var k = 0; k < CONFIG.n_cues; k++) {
            cue_diff.push(cues_a[k] - cues_b[k]);
        }

        // Determine dominant cue (highest absolute weight)
        var best_cue_idx = 0;
        var best_weight = Math.abs(weights[0]);
        for (var m = 1; m < CONFIG.n_cues; m++) {
            if (Math.abs(weights[m]) > best_weight) {
                best_weight = Math.abs(weights[m]);
                best_cue_idx = m;
            }
        }

        // Would take-the-best (using dominant cue only) be correct?
        var ttb_choice = (weights[best_cue_idx] > 0)
            ? (cues_a[best_cue_idx] > cues_b[best_cue_idx] ? "f" : "j")
            : (cues_a[best_cue_idx] < cues_b[best_cue_idx] ? "f" : "j");
        var ttb_correct = ttb_choice === correct_answer;

        return {
            cues_a: cues_a,
            cues_b: cues_b,
            cue_diff: cue_diff,
            correct_answer: correct_answer,
            dominant_cue: best_cue_idx,
            ttb_correct: ttb_correct,
        };
    }

    function generateAllTrials() {
        var trials = [];
        for (var t = 0; t < CONFIG.n_tasks; t++) {
            var weights = generateCueWeights();
            for (var s = 0; s < CONFIG.trials_per_task; s++) {
                var stim = generateTrialStimuli(weights);
                trials.push({
                    block: t,
                    trial_in_block: s,
                    cues_a: stim.cues_a,
                    cues_b: stim.cues_b,
                    cue_diff: stim.cue_diff,
                    correct_answer: stim.correct_answer,
                    dominant_cue: stim.dominant_cue,
                    ttb_correct: stim.ttb_correct,
                    weights: weights,
                });
            }
        }
        return trials;
    }

    function renderCompetitor(name, cues, side) {
        var html = '<div class="competitor-box">';
        html += '<div class="competitor-label">' + name + '</div>';
        for (var i = 0; i < cues.length; i++) {
            var val = cues[i];
            var cls = val >= 50 ? "cue-positive" : "cue-negative";
            html += '<div>' + CUE_LABELS[i] + ': <span class="cue-value ' + cls + '">' + val + '</span></div>';
        }
        html += '<div class="key-hint">' + (side === "left" ? "F" : "J") + '</div>';
        html += '</div>';
        return html;
    }

    var allTrials = generateAllTrials();
    var timeline = [];

    timeline.push({ type: jsPsychHtmlKeyboardResponse, stimulus: "<h1>Cue Competition Task</h1><p>Press any key to begin.</p>" });
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2><p>You are visiting different planets where aliens compete in athletic events.</p><p>On each trial, you see two competitors with their attribute scores.</p><p>Your job is to <strong>predict which competitor will win</strong>.</p>",
            "<h2>Learning from Feedback</h2><p>After each prediction, you'll see whether you were correct.</p><p>Use the feedback to learn which attributes matter most on each planet.</p><p>The rules may change between planets!</p>",
            "<h2>Response Keys</h2><p style='font-size:28px'><kbd>F</kbd> = <strong>Left Competitor</strong></p><p style='font-size:28px'><kbd>J</kbd> = <strong>Right Competitor</strong></p><p>Try to be as accurate as possible. Press Next to start.</p>",
        ],
        show_clickable_nav: true, button_label_next: "Next", button_label_previous: "Previous",
    });

    var trialCounter = 0;
    var prevBlock = -1;

    for (var ti = 0; ti < allTrials.length; ti++) {
        (function (trial, idx) {
            // Block transition message
            if (trial.block !== prevBlock) {
                timeline.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: '<h2>Planet ' + (trial.block + 1) + ' of ' + CONFIG.n_tasks + '</h2><p>New planet! The rules may be different here.</p><p>Press any key to continue.</p>',
                });
                prevBlock = trial.block;
            }

            timeline.push({ type: jsPsychHtmlKeyboardResponse, stimulus: '<div class="fixation">+</div>', choices: "NO_KEYS", trial_duration: CONFIG.fixation_duration, data: { trial_part: "fixation" } });

            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: '<div class="trial-counter">Trial ' + (trialCounter + 1) + ' of ' + CONFIG.n_trials + '</div>' +
                    '<div class="block-label">Planet ' + (trial.block + 1) + '</div>' +
                    '<div class="cue-container">' +
                    renderCompetitor(COMPETITOR_NAMES[0], trial.cues_a, "left") +
                    renderCompetitor(COMPETITOR_NAMES[1], trial.cues_b, "right") +
                    '</div>',
                choices: CONFIG.valid_keys,
                trial_duration: CONFIG.response_deadline,
                data: {
                    trial_part: "stimulus",
                    block: trial.block,
                    trial_in_block: trial.trial_in_block,
                    cue_values: JSON.stringify(trial.cue_diff),
                    correct_answer: trial.correct_answer,
                    dominant_cue: trial.dominant_cue,
                    ttb_correct: trial.ttb_correct,
                },
                on_finish: function (data) {
                    trialCounter++;
                    data.trial_index = trialCounter;
                    data.timed_out = data.response === null;
                    if (!data.timed_out) {
                        data.correct = data.response === data.correct_answer;
                        // Did participant follow take-the-best heuristic?
                        data.used_ttb = (data.response === data.correct_answer) === data.ttb_correct;
                    } else {
                        data.correct = false;
                        data.used_ttb = false;
                    }
                },
            });

            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    var last = jsPsych.data.get().last(1).values()[0];
                    if (last.timed_out) return '<div class="feedback-incorrect">Too slow!</div>';
                    return last.correct ? '<div class="feedback-correct">\u2714 Correct!</div>' : '<div class="feedback-incorrect">\u2718 Wrong</div>';
                },
                choices: "NO_KEYS", trial_duration: CONFIG.feedback_duration, data: { trial_part: "feedback" },
            });
        })(allTrials[ti], ti);
    }

    timeline.push({ type: jsPsychCallFunction, async: true, func: function (done) {
        var trial_data = jsPsych.data.get().filter({ trial_part: "stimulus" }).values();
        fetch("/api/data/" + SESSION_ID + "/" + TASK_ID, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ trial_data: trial_data, metadata: { task_id: TASK_ID, session_id: SESSION_ID, total_time_ms: jsPsych.getTotalTime(), n_trials: trial_data.length } }) })
            .then(function (r) { done(); }).catch(function (e) { console.error(e); done(); });
    }});

    timeline.push({ type: jsPsychHtmlKeyboardResponse, stimulus: "<h2>Task Complete</h2><p>Your data has been submitted.</p>", choices: "NO_KEYS", trial_duration: 3000 });
    jsPsych.run(timeline);
})();
