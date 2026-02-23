(function () {
    var CONFIG = {
        n_trials: 100,
        n_blocks: 5,
        trials_per_block: 20,
        go_proportion: 0.75,
        stimulus_duration: 500,
        response_deadline: 1000,
        fixation_duration: 500,
        feedback_duration: 500,
        valid_keys: ["f"],
        iti_min: 300,
        iti_max: 600,
    };

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "go_nogo";

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    // Generate trial sequence with controlled go/no-go proportions
    function generateTrials() {
        var trials = [];
        for (var b = 0; b < CONFIG.n_blocks; b++) {
            var block_trials = [];
            var n_go = Math.round(CONFIG.trials_per_block * CONFIG.go_proportion);
            var n_nogo = CONFIG.trials_per_block - n_go;

            for (var i = 0; i < n_go; i++) {
                block_trials.push({ stimulus_type: "go", block: b + 1 });
            }
            for (var i = 0; i < n_nogo; i++) {
                block_trials.push({ stimulus_type: "nogo", block: b + 1 });
            }

            // Shuffle within block (Fisher-Yates)
            for (var i = block_trials.length - 1; i > 0; i--) {
                var j = Math.floor(Math.random() * (i + 1));
                var temp = block_trials[i];
                block_trials[i] = block_trials[j];
                block_trials[j] = temp;
            }

            // Avoid consecutive no-go trials (swap if found)
            for (var i = 1; i < block_trials.length; i++) {
                if (block_trials[i].stimulus_type === "nogo" &&
                    block_trials[i - 1].stimulus_type === "nogo") {
                    // Find next go trial and swap
                    for (var j = i + 1; j < block_trials.length; j++) {
                        if (block_trials[j].stimulus_type === "go") {
                            var temp = block_trials[i];
                            block_trials[i] = block_trials[j];
                            block_trials[j] = temp;
                            break;
                        }
                    }
                }
            }

            trials = trials.concat(block_trials);
        }
        return trials;
    }

    var allTrials = generateTrials();
    var timeline = [];

    // Instructions
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Go/No-Go Task</h2>" +
            "<p>In this task, you will see colored circles on the screen.</p>" +
            "<p>Press <kbd>F</kbd> as fast as you can when you see a <span style='color:green;font-weight:bold'>GREEN</span> circle.</p>" +
            "<p>Do <strong>NOT</strong> press anything when you see a <span style='color:red;font-weight:bold'>RED</span> circle.</p>",

            "<h2>Important</h2>" +
            "<p><span style='color:green;font-weight:bold'>GREEN circle</span> = Press <kbd>F</kbd> quickly</p>" +
            "<p><span style='color:red;font-weight:bold'>RED circle</span> = Do NOT press any key</p>" +
            "<p>Try to be both fast AND accurate.</p>" +
            "<p>The task has " + CONFIG.n_blocks + " blocks of " + CONFIG.trials_per_block + " trials each.</p>" +
            "<p>Click Next to begin.</p>"
        ],
        show_clickable_nav: true,
    });

    // Practice trials (8 trials)
    var practiceTrials = [];
    for (var i = 0; i < 6; i++) practiceTrials.push({ stimulus_type: "go", block: 0 });
    for (var i = 0; i < 2; i++) practiceTrials.push({ stimulus_type: "nogo", block: 0 });
    // Simple shuffle
    for (var i = practiceTrials.length - 1; i > 0; i--) {
        var j = Math.floor(Math.random() * (i + 1));
        var temp = practiceTrials[i];
        practiceTrials[i] = practiceTrials[j];
        practiceTrials[j] = temp;
    }

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus: "<h2>Practice Round</h2><p>Let's practice with a few trials first.</p><p>Press any key to start.</p>",
    });

    practiceTrials.forEach(function (pt) {
        // Fixation
        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: '<div class="fixation">+</div>',
            choices: "NO_KEYS",
            trial_duration: CONFIG.fixation_duration,
        });

        var isGo = pt.stimulus_type === "go";
        var circleColor = isGo ? "green" : "red";
        var circleHTML = '<div class="gonogo-stimulus"><svg width="150" height="150">' +
            '<circle cx="75" cy="75" r="70" fill="' + circleColor + '"/></svg></div>';

        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: circleHTML,
            choices: ["f"],
            trial_duration: CONFIG.response_deadline,
            data: { trial_part: "practice", stimulus_type: pt.stimulus_type },
            on_finish: function (data) {
                var responded = data.response !== null;
                if (isGo) {
                    data.correct = responded;
                } else {
                    data.correct = !responded;
                }
            },
        });

        // Feedback for practice
        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                var last = jsPsych.data.get().last(1).values()[0];
                if (last.correct) {
                    return '<div class="feedback" style="color:green">Correct!</div>';
                } else {
                    if (last.stimulus_type === "go") {
                        return '<div class="feedback" style="color:red">Too slow! Press F for green circles.</div>';
                    } else {
                        return '<div class="feedback" style="color:red">Don\'t press for red circles!</div>';
                    }
                }
            },
            choices: "NO_KEYS",
            trial_duration: CONFIG.feedback_duration,
        });
    });

    // Main experiment
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Main Experiment</h2>" +
            "<p>Practice is over. The main task will now begin.</p>" +
            "<p>Remember: Press <kbd>F</kbd> for GREEN, do nothing for RED.</p>" +
            "<p>Press any key to start.</p>",
    });

    var trialCounter = 0;

    for (var t = 0; t < allTrials.length; t++) {
        (function (trialData) {
            // Fixation
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: '<div class="fixation">+</div>',
                choices: "NO_KEYS",
                trial_duration: CONFIG.fixation_duration,
            });

            var isGo = trialData.stimulus_type === "go";
            var circleColor = isGo ? "green" : "red";
            var circleHTML = '<div class="gonogo-stimulus"><svg width="150" height="150">' +
                '<circle cx="75" cy="75" r="70" fill="' + circleColor + '"/></svg></div>';

            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: circleHTML,
                choices: ["f"],
                stimulus_duration: CONFIG.stimulus_duration,
                trial_duration: CONFIG.response_deadline,
                data: {
                    trial_part: "stimulus",
                    stimulus_type: trialData.stimulus_type,
                    block: trialData.block,
                },
                on_finish: function (data) {
                    trialCounter++;
                    data.trial_index = trialCounter;

                    var responded = data.response !== null;
                    data.timed_out = !responded;

                    if (data.stimulus_type === "go") {
                        data.correct = responded;
                        data.hit = responded;
                        data.miss = !responded;
                        data.false_alarm = false;
                        data.correct_rejection = false;
                    } else {
                        data.correct = !responded;
                        data.hit = false;
                        data.miss = false;
                        data.false_alarm = responded;
                        data.correct_rejection = !responded;
                    }

                    // Previous trial info for post-error slowing
                    if (trialCounter > 1) {
                        var prevTrials = jsPsych.data
                            .get()
                            .filter({ trial_part: "stimulus" })
                            .values();
                        if (prevTrials.length >= 2) {
                            var prev = prevTrials[prevTrials.length - 2];
                            data.prev_correct = prev.correct;
                        }
                    }
                },
            });

            // ITI
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: "",
                choices: "NO_KEYS",
                trial_duration: function () {
                    return CONFIG.iti_min +
                        Math.floor(Math.random() * (CONFIG.iti_max - CONFIG.iti_min));
                },
            });
        })(allTrials[t]);

        // Block break
        if ((t + 1) % CONFIG.trials_per_block === 0 && t < allTrials.length - 1) {
            var blockNum = Math.floor(t / CONFIG.trials_per_block) + 1;
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus:
                    "<h2>Block " + blockNum + " of " + CONFIG.n_blocks + " complete</h2>" +
                    "<p>Take a short break if needed.</p>" +
                    "<p>Press any key to continue.</p>",
            });
        }
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
            "<p>Thank you for completing the Go/No-Go task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
