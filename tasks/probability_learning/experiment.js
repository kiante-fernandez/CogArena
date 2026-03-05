(function () {
    var CONFIG = {
        n_trials: 100,
        p_left: 0.70,
        p_right: 0.30,
        valid_keys: ["f", "j"],
        response_deadline: 5000,
        fixation_duration: 500,
        feedback_duration: 1000,
        iti_min: 300,
        iti_max: 600,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "probability_learning";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.n_trials = _nto;
    }

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    // Pre-generate outcomes for reproducibility within session
    function generateOutcomes() {
        var outcomes = { left: [], right: [] };
        for (var i = 0; i < CONFIG.n_trials; i++) {
            outcomes.left.push(Math.random() < CONFIG.p_left ? 1 : 0);
            outcomes.right.push(Math.random() < CONFIG.p_right ? 1 : 0);
        }
        return outcomes;
    }

    var outcomes = generateOutcomes();
    var timeline = [];

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Probability Learning</h1>" +
            "<p>Welcome to this prediction task.</p>" +
            "<p>Press any key to begin.</p>",
    });

    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>In this task, an animal is hiding behind one of two houses on each trial.</p>" +
            "<p>Your goal is to predict which house the animal is behind.</p>" +
            "<p>One house is more likely to have the animal than the other.</p>" +
            "<p>Try to find the animal as many times as possible!</p>",

            "<h2>Feedback</h2>" +
            "<p>After each choice, you will see whether the animal was behind each house.</p>" +
            "<p><span style='color:#2e7d32; font-weight:bold'>\u2714</span> = Animal was here</p>" +
            "<p><span style='color:#c62828; font-weight:bold'>\u2718</span> = No animal here</p>" +
            "<p>Use this feedback to learn which house is better.</p>",

            "<h2>Response Keys</h2>" +
            "<p style='font-size:28px'><kbd>F</kbd> = <strong>Left House</strong> \uD83C\uDFE0</p>" +
            "<p style='font-size:28px'><kbd>J</kbd> = <strong>Right House</strong> \uD83C\uDFE0</p>" +
            "<p>You have 5 seconds to respond.</p>" +
            "<p>Press Next to start.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    var trialCounter = 0;
    var optimalSide = CONFIG.p_left >= CONFIG.p_right ? "left" : "right";

    for (var ti = 0; ti < CONFIG.n_trials; ti++) {
        (function (trialIdx) {
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
                    return '<div class="trial-counter">Trial ' + (trialCounter + 1) + ' of ' + CONFIG.n_trials + '</div>' +
                        '<div class="house-container">' +
                        '<div class="house">\uD83C\uDFE0<div class="key-hint">F</div></div>' +
                        '<div class="house">\uD83C\uDFE0<div class="key-hint">J</div></div>' +
                        '</div>' +
                        '<div style="margin-top:20px;font-size:20px;color:#555;">Which house is the animal behind?</div>';
                },
                choices: CONFIG.valid_keys,
                trial_duration: CONFIG.response_deadline,
                data: {
                    trial_part: "stimulus",
                    optimal_side: optimalSide,
                    p_left: CONFIG.p_left,
                    p_right: CONFIG.p_right,
                },
                on_finish: function (data) {
                    trialCounter++;
                    data.trial_index = trialCounter;
                    data.timed_out = data.response === null;

                    var leftOutcome = outcomes.left[trialIdx];
                    var rightOutcome = outcomes.right[trialIdx];
                    data.left_outcome = leftOutcome;
                    data.right_outcome = rightOutcome;

                    if (!data.timed_out) {
                        var choice = data.response === "f" ? "left" : "right";
                        data.choice = choice;
                        // Reward = 1 if chosen house has animal, 0 otherwise
                        data.reward = choice === "left" ? leftOutcome : rightOutcome;
                        data.correct = data.reward === 1;
                        data.chose_optimal = choice === optimalSide;

                        // Win-stay / lose-shift
                        var prevTrials = jsPsych.data.get().filter({ trial_part: "stimulus" }).values();
                        if (prevTrials.length >= 2) {
                            var prev = prevTrials[prevTrials.length - 2];
                            data.stayed = data.choice === prev.choice;
                            data.prev_reward = prev.reward;
                        }
                    } else {
                        data.choice = null;
                        data.reward = 0;
                        data.correct = false;
                        data.chose_optimal = false;
                    }
                },
            });

            // Feedback: show both houses
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    var last = jsPsych.data.get().last(1).values()[0];
                    if (last.timed_out) {
                        return '<div class="feedback-incorrect">Too slow!</div>';
                    }
                    var leftIcon = last.left_outcome ? '<span style="color:#2e7d32;font-size:36px">\u2714 Found!</span>' :
                                                       '<span style="color:#c62828;font-size:36px">\u2718 Empty</span>';
                    var rightIcon = last.right_outcome ? '<span style="color:#2e7d32;font-size:36px">\u2714 Found!</span>' :
                                                         '<span style="color:#c62828;font-size:36px">\u2718 Empty</span>';
                    var leftBorder = last.choice === "left" ? "border: 4px solid #1565c0;" : "";
                    var rightBorder = last.choice === "right" ? "border: 4px solid #1565c0;" : "";
                    var resultClass = last.correct ? "feedback-correct" : "feedback-incorrect";
                    var resultText = last.correct ? "Found the animal!" : "Wrong house!";

                    return '<div class="' + resultClass + '">' + resultText + '</div>' +
                        '<div class="house-container" style="margin-top:20px;">' +
                        '<div class="house" style="' + leftBorder + '">\uD83C\uDFE0<br>' + leftIcon + '</div>' +
                        '<div class="house" style="' + rightBorder + '">\uD83C\uDFE0<br>' + rightIcon + '</div>' +
                        '</div>';
                },
                choices: "NO_KEYS",
                trial_duration: CONFIG.feedback_duration,
                data: { trial_part: "feedback" },
            });

        })(ti);
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
            "<p>Thank you for completing the probability learning task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
