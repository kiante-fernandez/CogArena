(function () {
    var CONFIG = {
        n_trials: 90,
        n_training: 30,
        n_test_per_effect: 20,
        n_practice: 3,
        valid_keys: ["d", "f", "j"],
        response_deadline: 10000,
        fixation_duration: 500,
        feedback_duration: 1500,
        iti_min: 300,
        iti_max: 600,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "context_effects";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.n_trials = _nto;
        CONFIG.n_training = Math.round(_nto / 3);
        CONFIG.n_test_per_effect = Math.round(_nto / 3 / 2);
    }

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    // Option reward distributions: mean rewards for each option
    // Target (T) and Competitor (C) are roughly equal in quality
    // Decoy (D) varies by effect type
    function generateTrials() {
        var trials = [];

        // Training phase: 2-option forced choice to learn option values
        var targetMean = 70;
        var competitorMean = 65;

        for (var i = 0; i < CONFIG.n_training; i++) {
            var tReward = Math.round(targetMean + (Math.random() - 0.5) * 20);
            var cReward = Math.round(competitorMean + (Math.random() - 0.5) * 20);
            trials.push({
                phase: "training",
                effect_type: "none",
                block: 1,
                rewards: [tReward, cReward, null],
                labels: ["A", "B", null],
                n_options: 2,
                target_idx: 0,
            });
        }

        // Test phase: 3-option choice with decoy
        var effects = ["attraction", "compromise"];
        for (var e = 0; e < effects.length; e++) {
            var effect = effects[e];
            for (var t = 0; t < CONFIG.n_test_per_effect; t++) {
                var tR = Math.round(targetMean + (Math.random() - 0.5) * 20);
                var cR = Math.round(competitorMean + (Math.random() - 0.5) * 20);
                var dR;

                if (effect === "attraction") {
                    // Decoy is dominated by target (slightly worse in all dimensions)
                    dR = Math.round(tR * 0.75 + (Math.random() - 0.5) * 5);
                } else {
                    // Compromise: target is middle, decoy is extreme
                    dR = Math.round(targetMean * 1.3 + (Math.random() - 0.5) * 10);
                }

                trials.push({
                    phase: "test",
                    effect_type: effect,
                    block: e + 2,
                    rewards: [tR, cR, dR],
                    labels: ["A", "B", "C"],
                    n_options: 3,
                    target_idx: 0,
                });
            }
        }

        // Shuffle test trials
        var training = trials.slice(0, CONFIG.n_training);
        var test = trials.slice(CONFIG.n_training);
        for (var s = test.length - 1; s > 0; s--) {
            var j = Math.floor(Math.random() * (s + 1));
            var tmp = test[s];
            test[s] = test[j];
            test[j] = tmp;
        }

        return training.concat(test);
    }

    var allTrials = generateTrials();
    var timeline = [];

    // Welcome
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Multi-Option Choice Task</h1>" +
            "<p>Welcome to the decision-making experiment.</p>" +
            "<p>Press any key to begin.</p>",
    });

    // Instructions
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>On each trial, you will choose between options that give different point rewards.</p>" +
            "<p>After choosing, you'll see the rewards for <strong>all</strong> options.</p>" +
            "<p>Your goal is to <strong>maximize your total points</strong>.</p>",

            "<h2>Response Keys</h2>" +
            "<p>When there are <strong>2 options</strong>:</p>" +
            "<p style='font-size:28px'><kbd>F</kbd> = Left &nbsp;&nbsp; <kbd>J</kbd> = Right</p>" +
            "<p>When there are <strong>3 options</strong>:</p>" +
            "<p style='font-size:28px'><kbd>D</kbd> = Left &nbsp;&nbsp; <kbd>F</kbd> = Middle &nbsp;&nbsp; <kbd>J</kbd> = Right</p>" +
            "<p>You have 10 seconds per choice. Press Next to begin.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    // Main trials
    var trialCounter = 0;
    allTrials.forEach(function (trial, idx) {
        var nOpt = trial.n_options;
        var keys = nOpt === 2 ? ["f", "j"] : ["d", "f", "j"];

        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: '<div class="fixation">+</div>',
            choices: "NO_KEYS",
            trial_duration: CONFIG.fixation_duration,
            data: { trial_part: "fixation" },
        });

        var optionsHtml = '<div class="trial-counter">Trial ' + (idx + 1) + " of " + CONFIG.n_trials + "</div>";
        optionsHtml += '<div class="options-container">';

        for (var o = 0; o < nOpt; o++) {
            var keyLabel = keys[o].toUpperCase();
            optionsHtml += '<div class="option-box">';
            optionsHtml += '<div class="option-label">Option ' + trial.labels[o] + "</div>";
            optionsHtml += '<div class="option-reward">?</div>';
            optionsHtml += '<div class="key-hint">' + keyLabel + "</div>";
            optionsHtml += "</div>";
        }
        optionsHtml += "</div>";

        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: optionsHtml,
            choices: keys,
            trial_duration: CONFIG.response_deadline,
            data: {
                trial_part: "stimulus",
                phase: trial.phase,
                effect_type: trial.effect_type,
                block: trial.block,
                n_options: nOpt,
                reward_0: trial.rewards[0],
                reward_1: trial.rewards[1],
                reward_2: trial.rewards[2],
                target_idx: trial.target_idx,
            },
            on_finish: function (data) {
                trialCounter++;
                data.trial_index = trialCounter;
                data.trial_in_block = trialCounter;
                data.timed_out = data.response === null;

                if (!data.timed_out) {
                    var keyIdx;
                    if (data.n_options === 2) {
                        keyIdx = data.response === "f" ? 0 : 1;
                    } else {
                        keyIdx = data.response === "d" ? 0 : data.response === "f" ? 1 : 2;
                    }
                    data.option_chosen = keyIdx;
                    data.reward_chosen = [data.reward_0, data.reward_1, data.reward_2][keyIdx];
                    data.is_target = keyIdx === data.target_idx;
                } else {
                    data.option_chosen = null;
                    data.reward_chosen = 0;
                    data.is_target = false;
                }
            },
        });

        // Feedback: show all rewards
        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                var last = jsPsych.data.get().last(1).values()[0];
                var html = '<div class="options-container">';
                var rewards = [last.reward_0, last.reward_1, last.reward_2];
                var labels = ["A", "B", "C"];
                var chosen = last.option_chosen;
                for (var o = 0; o < last.n_options; o++) {
                    var cls = o === chosen ? "feedback-chosen" : "feedback-other";
                    html += '<div class="option-box">';
                    html += '<div class="option-label">Option ' + labels[o] + "</div>";
                    html += '<div class="option-reward ' + cls + '">' + rewards[o] + " pts</div>";
                    html += "</div>";
                }
                html += "</div>";
                if (chosen !== null) {
                    html += '<div class="feedback">You earned <strong>' + rewards[chosen] + "</strong> points</div>";
                } else {
                    html += '<div class="feedback">Too slow! No points earned.</div>';
                }
                return html;
            },
            choices: "NO_KEYS",
            trial_duration: CONFIG.feedback_duration,
            data: { trial_part: "feedback" },
        });

        // ITI
        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: "",
            choices: "NO_KEYS",
            trial_duration: function () {
                return CONFIG.iti_min + Math.random() * (CONFIG.iti_max - CONFIG.iti_min);
            },
            data: { trial_part: "iti" },
        });
    });

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
                    if (!response.ok) {
                        console.error("Data submission failed:", response.status);
                    }
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
            "<p>Thank you for completing the decision-making task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
