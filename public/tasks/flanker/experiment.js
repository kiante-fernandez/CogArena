(function () {
    var CONFIG = {
        n_trials: 96,
        n_blocks: 4,
        trials_per_block: 24,
        proportion_congruent: 0.50,
        fixation_duration: 500,
        response_deadline: 3000,
        valid_keys: ["f", "j"],
        key_map: { left: "f", right: "j" },
        iti_min: 300,
        iti_max: 600,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "flanker";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.n_trials = _nto;
        CONFIG.n_blocks = 1;
        CONFIG.trials_per_block = _nto;
    }

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    // Stimulus definitions
    var STIMULI = {
        congruent_left: { display: "<<<<<", target: "left", flanker: "left", condition: "congruent" },
        congruent_right: { display: ">>>>>", target: "right", flanker: "right", condition: "congruent" },
        incongruent_left: { display: ">><>>", target: "left", flanker: "right", condition: "incongruent" },
        incongruent_right: { display: "<<><<", target: "right", flanker: "left", condition: "incongruent" },
    };

    function generateTrials() {
        var trials = [];
        for (var b = 0; b < CONFIG.n_blocks; b++) {
            var block_trials = [];
            var n_congruent = Math.round(CONFIG.trials_per_block * CONFIG.proportion_congruent);
            var n_incongruent = CONFIG.trials_per_block - n_congruent;

            // Half left, half right for each condition
            for (var i = 0; i < n_congruent; i++) {
                var stim = i < n_congruent / 2 ? STIMULI.congruent_left : STIMULI.congruent_right;
                block_trials.push({
                    display: stim.display,
                    target_direction: stim.target,
                    flanker_direction: stim.flanker,
                    condition: stim.condition,
                    block: b + 1,
                });
            }
            for (var i = 0; i < n_incongruent; i++) {
                var stim = i < n_incongruent / 2 ? STIMULI.incongruent_left : STIMULI.incongruent_right;
                block_trials.push({
                    display: stim.display,
                    target_direction: stim.target,
                    flanker_direction: stim.flanker,
                    condition: stim.condition,
                    block: b + 1,
                });
            }

            // Shuffle within block
            for (var i = block_trials.length - 1; i > 0; i--) {
                var j = Math.floor(Math.random() * (i + 1));
                var temp = block_trials[i];
                block_trials[i] = block_trials[j];
                block_trials[j] = temp;
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
            "<h2>Flanker Task</h2>" +
            "<p>In this task, you will see a row of five arrows.</p>" +
            "<p>Your job is to identify the direction of the <strong>CENTER</strong> arrow.</p>" +
            "<p>Ignore the surrounding (flanker) arrows.</p>",

            "<h2>Response Keys</h2>" +
            "<p>Press <kbd>F</kbd> if the center arrow points <strong>LEFT</strong> (&lt;)</p>" +
            "<p>Press <kbd>J</kbd> if the center arrow points <strong>RIGHT</strong> (&gt;)</p>" +
            "<p style='margin-top:20px'>Examples:</p>" +
            "<p style='font-family:monospace;font-size:36px;letter-spacing:12px'>&gt;&gt;&gt;&gt;&gt; → Press <kbd>J</kbd> (all point right)</p>" +
            "<p style='font-family:monospace;font-size:36px;letter-spacing:12px'>&lt;&lt;&gt;&lt;&lt; → Press <kbd>J</kbd> (center points right)</p>",

            "<h2>Ready?</h2>" +
            "<p>Respond as quickly and accurately as possible.</p>" +
            "<p>The task has " + CONFIG.n_blocks + " blocks of " + CONFIG.trials_per_block + " trials each.</p>" +
            "<p>Click Next to begin with a practice round.</p>"
        ],
        show_clickable_nav: true,
    });

    // Practice trials (8 trials)
    var practiceStims = [
        STIMULI.congruent_left, STIMULI.congruent_right,
        STIMULI.incongruent_left, STIMULI.incongruent_right,
        STIMULI.congruent_left, STIMULI.congruent_right,
        STIMULI.incongruent_left, STIMULI.incongruent_right,
    ];
    // Shuffle practice
    for (var i = practiceStims.length - 1; i > 0; i--) {
        var j = Math.floor(Math.random() * (i + 1));
        var temp = practiceStims[i];
        practiceStims[i] = practiceStims[j];
        practiceStims[j] = temp;
    }

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus: "<h2>Practice Round</h2><p>Let's practice with a few trials first.</p><p>Press any key to start.</p>",
    });

    practiceStims.forEach(function (stim) {
        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: '<div class="fixation">+</div>',
            choices: "NO_KEYS",
            trial_duration: CONFIG.fixation_duration,
        });

        var correctKey = CONFIG.key_map[stim.target];
        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: '<div class="flanker-stimulus">' + stim.display + '</div>',
            choices: CONFIG.valid_keys,
            trial_duration: CONFIG.response_deadline,
            data: { trial_part: "practice", condition: stim.condition },
            on_finish: function (data) {
                data.correct = data.response === correctKey;
            },
        });

        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                var last = jsPsych.data.get().last(1).values()[0];
                if (last.response === null) {
                    return '<div class="feedback" style="color:red">Too slow!</div>';
                } else if (last.correct) {
                    return '<div class="feedback" style="color:green">Correct!</div>';
                } else {
                    return '<div class="feedback" style="color:red">Incorrect!</div>';
                }
            },
            choices: "NO_KEYS",
            trial_duration: 500,
        });
    });

    // Main experiment
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Main Experiment</h2>" +
            "<p>Practice is over. The main task will now begin.</p>" +
            "<p>Remember: <kbd>F</kbd> = left, <kbd>J</kbd> = right (center arrow only)</p>" +
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

            var correctKey = CONFIG.key_map[trialData.target_direction];

            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: '<div class="flanker-stimulus">' + trialData.display + '</div>',
                choices: CONFIG.valid_keys,
                trial_duration: CONFIG.response_deadline,
                data: {
                    trial_part: "stimulus",
                    condition: trialData.condition,
                    target_direction: trialData.target_direction,
                    flanker_direction: trialData.flanker_direction,
                    correct_key: correctKey,
                    block: trialData.block,
                },
                on_finish: function (data) {
                    trialCounter++;
                    data.trial_index = trialCounter;
                    data.timed_out = data.response === null;
                    data.correct = data.response === correctKey;

                    // Previous trial info for sequential effects
                    if (trialCounter > 1) {
                        var prevTrials = jsPsych.data
                            .get()
                            .filter({ trial_part: "stimulus" })
                            .values();
                        if (prevTrials.length >= 2) {
                            var prev = prevTrials[prevTrials.length - 2];
                            data.prev_condition = prev.condition;
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
            "<p>Thank you for completing the Flanker task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
