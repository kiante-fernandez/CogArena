(function () {
    var CONFIG = {
        n_trials: 120,
        base_count: 50,
        ratios: [1.1, 1.2, 1.3, 1.5, 1.8, 2.0],
        valid_keys: ["f", "j"],
        response_deadline: 3000,
        fixation_duration: 500,
        feedback_duration: 800,
        stimulus_duration: 1500,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "random_dot_motion";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) CONFIG.n_trials = _nto;

    var jsPsych = initJsPsych({ experiment_width: 800, minimum_valid_rt: 100 });
    if (SESSION_ID === "debug") window._jsPsych = jsPsych;

    function generateDots(count) {
        var dots = "";
        for (var i = 0; i < count; i++) dots += "\u25CF";
        // Wrap dots in grid
        var html = '<div style="display:flex;flex-wrap:wrap;justify-content:center;gap:2px;max-width:180px">';
        for (var j = 0; j < count; j++) {
            html += '<span style="font-size:8px;color:#333">\u25CF</span>';
        }
        html += '</div>';
        return html;
    }

    function generateTrials() {
        var trials = [];
        var trialsPerRatio = Math.ceil(CONFIG.n_trials / CONFIG.ratios.length);
        for (var r = 0; r < CONFIG.ratios.length; r++) {
            for (var t = 0; t < trialsPerRatio && trials.length < CONFIG.n_trials; t++) {
                var ratio = CONFIG.ratios[r];
                var base = CONFIG.base_count + Math.floor(Math.random() * 20 - 10);
                var more = Math.round(base * ratio);
                var moreOnLeft = Math.random() > 0.5;
                trials.push({
                    n_left: moreOnLeft ? more : base,
                    n_right: moreOnLeft ? base : more,
                    ratio: ratio,
                    correct_side: moreOnLeft ? "left" : "right",
                    condition: ratio <= 1.2 ? "hard" : ratio <= 1.5 ? "medium" : "easy",
                });
            }
        }
        for (var i = trials.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var tmp = trials[i]; trials[i] = trials[j]; trials[j] = tmp;
        }
        return trials;
    }

    var allTrials = generateTrials();
    var timeline = [];

    timeline.push({ type: jsPsychHtmlKeyboardResponse, stimulus: "<h1>Dot Discrimination</h1><p>Press any key to begin.</p>" });
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2><p>You will see two groups of dots on each trial.</p><p>Your task is to identify which group has <strong>MORE</strong> dots.</p>",
            "<h2>Response Keys</h2><p style='font-size:28px'><kbd>F</kbd> = <strong>Left has more</strong></p><p style='font-size:28px'><kbd>J</kbd> = <strong>Right has more</strong></p><p>Respond as quickly and accurately as possible.</p><p>Press Next to start.</p>",
        ],
        show_clickable_nav: true, button_label_next: "Next", button_label_previous: "Previous",
    });

    var trialCounter = 0;
    for (var ti = 0; ti < allTrials.length; ti++) {
        (function (trial) {
            timeline.push({ type: jsPsychHtmlKeyboardResponse, stimulus: '<div class="fixation">+</div>', choices: "NO_KEYS", trial_duration: CONFIG.fixation_duration, data: { trial_part: "fixation" } });

            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: '<div class="trial-counter">Trial ' + (trialCounter + 1) + ' of ' + CONFIG.n_trials + '</div>' +
                    '<div class="dot-container">' +
                    '<div class="dot-array">' + generateDots(trial.n_left) + '<div class="key-hint">F</div></div>' +
                    '<div class="dot-array">' + generateDots(trial.n_right) + '<div class="key-hint">J</div></div></div>',
                choices: CONFIG.valid_keys,
                trial_duration: CONFIG.response_deadline,
                data: { trial_part: "stimulus", condition: trial.condition, n_left: trial.n_left, n_right: trial.n_right, ratio: trial.ratio, correct_side: trial.correct_side },
                on_finish: function (data) {
                    trialCounter++;
                    data.trial_index = trialCounter;
                    data.timed_out = data.response === null;
                    if (!data.timed_out) {
                        var chose = data.response === "f" ? "left" : "right";
                        data.correct = chose === trial.correct_side;
                    } else {
                        data.correct = false;
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
        })(allTrials[ti]);
    }

    timeline.push({ type: jsPsychCallFunction, async: true, func: function (done) {
        var trial_data = jsPsych.data.get().filter({ trial_part: "stimulus" }).values();
        fetch("/api/data/" + SESSION_ID + "/" + TASK_ID, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ trial_data: trial_data, metadata: { task_id: TASK_ID, session_id: SESSION_ID, total_time_ms: jsPsych.getTotalTime(), n_trials: trial_data.length } }) })
            .then(function (r) { done(); }).catch(function (e) { console.error(e); done(); });
    }});

    timeline.push({ type: jsPsychHtmlKeyboardResponse, stimulus: "<h2>Task Complete</h2><p>Your data has been submitted.</p>", choices: "NO_KEYS", trial_duration: 3000 });
    jsPsych.run(timeline);
})();
