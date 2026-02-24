(function () {
    var CONFIG = {
        n_practice_trials: 8,
        n_blocks: 4,
        trials_per_block: 24,
        colors: ["red", "blue", "green", "yellow"],
        words: ["RED", "BLUE", "GREEN", "YELLOW"],
        neutral_word: "XXXX",
        key_mapping: { red: "d", blue: "f", green: "j", yellow: "k" },
        valid_keys: ["d", "f", "j", "k"],
        fixation_duration: 500,
        response_deadline: 5000,
        iti_min: 500,
        iti_max: 1000,
        feedback_duration: 1500,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "stroop";

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    function generateStimulusList(n_per_condition) {
        var stimuli = [];
        var i, colorIdx, wordIdx, color;

        for (i = 0; i < n_per_condition; i++) {
            colorIdx = i % CONFIG.colors.length;
            color = CONFIG.colors[colorIdx];
            stimuli.push({
                word: color.toUpperCase(),
                color: color,
                condition: "congruent",
                correct_key: CONFIG.key_mapping[color],
            });
        }

        for (i = 0; i < n_per_condition; i++) {
            colorIdx = i % CONFIG.colors.length;
            wordIdx = (colorIdx + 1 + (i % (CONFIG.colors.length - 1))) % CONFIG.colors.length;
            color = CONFIG.colors[colorIdx];
            stimuli.push({
                word: CONFIG.words[wordIdx],
                color: color,
                condition: "incongruent",
                correct_key: CONFIG.key_mapping[color],
            });
        }

        for (i = 0; i < n_per_condition; i++) {
            colorIdx = i % CONFIG.colors.length;
            color = CONFIG.colors[colorIdx];
            stimuli.push({
                word: CONFIG.neutral_word,
                color: color,
                condition: "neutral",
                correct_key: CONFIG.key_mapping[color],
            });
        }

        return stimuli;
    }

    var timeline = [];

    // Welcome
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Stroop Color-Word Task</h1>" +
            "<p>Welcome to the Stroop task.</p>" +
            "<p>Press any key to begin.</p>",
    });

    // Instructions
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>In this experiment, you will see colored words appear on screen.</p>" +
            "<p>Your job is to identify the <strong>INK COLOR</strong> of the word, " +
            "ignoring what the word says.</p>" +
            "<p>For example, if you see the word GREEN printed in <span style='color:red; font-weight:bold'>red</span> ink, " +
            "you should respond with the key for <span style='color:red; font-weight:bold'>red</span>.</p>",

            "<h2>Response Keys</h2>" +
            '<div class="key-mapping">' +
            "<p><span style='color:red; font-weight:bold; font-size:28px'>RED</span> &rarr; press <kbd>D</kbd></p>" +
            "<p><span style='color:blue; font-weight:bold; font-size:28px'>BLUE</span> &rarr; press <kbd>F</kbd></p>" +
            "<p><span style='color:green; font-weight:bold; font-size:28px'>GREEN</span> &rarr; press <kbd>J</kbd></p>" +
            "<p><span style='color:yellow; font-weight:bold; font-size:28px; text-shadow:0 0 2px #000'>YELLOW</span> &rarr; press <kbd>K</kbd></p>" +
            "</div>" +
            "<p>Try to respond as quickly and accurately as possible.</p>",

            "<h2>Practice</h2>" +
            "<p>We will start with " + CONFIG.n_practice_trials + " practice trials with feedback.</p>" +
            "<p>Press Next to begin practice.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    // Fixation
    var fixation = {
        type: jsPsychHtmlKeyboardResponse,
        stimulus: '<div class="fixation">+</div>',
        choices: "NO_KEYS",
        trial_duration: CONFIG.fixation_duration,
        data: { trial_part: "fixation" },
    };

    // Stimulus trial
    var stimulus_trial = {
        type: jsPsychHtmlKeyboardResponse,
        stimulus: function () {
            var word = jsPsych.evaluateTimelineVariable("word");
            var color = jsPsych.evaluateTimelineVariable("color");
            var style = "color:" + color + ";";
            if (color === "yellow") {
                style += "text-shadow:0 0 2px #000;";
            }
            return '<div class="stroop-stimulus" style="' + style + '">' + word + "</div>";
        },
        choices: CONFIG.valid_keys,
        trial_duration: CONFIG.response_deadline,
        data: {
            trial_part: "stimulus",
            condition: jsPsych.timelineVariable("condition"),
            stimulus_word: jsPsych.timelineVariable("word"),
            stimulus_color: jsPsych.timelineVariable("color"),
            correct_key: jsPsych.timelineVariable("correct_key"),
        },
        on_finish: function (data) {
            if (data.response === null) {
                data.correct = false;
                data.timed_out = true;
            } else {
                data.correct = jsPsych.pluginAPI.compareKeys(data.response, data.correct_key);
                data.timed_out = false;
            }
        },
    };

    // Feedback (practice only)
    var feedback = {
        type: jsPsychHtmlKeyboardResponse,
        stimulus: function () {
            var last = jsPsych.data.get().last(1).values()[0];
            if (last.timed_out) {
                return '<p class="feedback" style="color:orange;">Too slow! Please respond faster.</p>';
            } else if (last.correct) {
                return '<p class="feedback" style="color:green;">Correct!</p>';
            } else {
                return '<p class="feedback" style="color:red;">Incorrect. Respond to the INK COLOR.</p>';
            }
        },
        choices: "NO_KEYS",
        trial_duration: CONFIG.feedback_duration,
        data: { trial_part: "feedback" },
    };

    // ITI
    var iti = {
        type: jsPsychHtmlKeyboardResponse,
        stimulus: "",
        choices: "NO_KEYS",
        trial_duration: function () {
            return CONFIG.iti_min + Math.random() * (CONFIG.iti_max - CONFIG.iti_min);
        },
        data: { trial_part: "iti" },
    };

    // Practice block
    var practice_stimuli = generateStimulusList(Math.ceil(CONFIG.n_practice_trials / 3));
    practice_stimuli = jsPsych.randomization.shuffle(practice_stimuli).slice(0, CONFIG.n_practice_trials);

    timeline.push({
        timeline: [fixation, stimulus_trial, feedback, iti],
        timeline_variables: practice_stimuli,
        randomize_order: true,
    });

    // Transition
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>End of Practice</h2>" +
            "<p>The main experiment will now begin.</p>" +
            "<p>There are " + CONFIG.n_blocks + " blocks of " + CONFIG.trials_per_block + " trials each.</p>" +
            "<p>Remember: respond to the <strong>INK COLOR</strong>, not the word.</p>" +
            "<p>Press any key to start.</p>",
    });

    // Experimental blocks
    var trial_counter = 0;
    for (var block = 0; block < CONFIG.n_blocks; block++) {
        var n_per_cond = CONFIG.trials_per_block / 3;
        var block_stimuli = generateStimulusList(n_per_cond);

        var block_stimulus = {
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                var word = jsPsych.evaluateTimelineVariable("word");
                var color = jsPsych.evaluateTimelineVariable("color");
                var style = "color:" + color + ";";
                if (color === "yellow") {
                    style += "text-shadow:0 0 2px #000;";
                }
                return '<div class="stroop-stimulus" style="' + style + '">' + word + "</div>";
            },
            choices: CONFIG.valid_keys,
            trial_duration: CONFIG.response_deadline,
            data: {
                trial_part: "stimulus",
                block: block + 1,
                condition: jsPsych.timelineVariable("condition"),
                stimulus_word: jsPsych.timelineVariable("word"),
                stimulus_color: jsPsych.timelineVariable("color"),
                correct_key: jsPsych.timelineVariable("correct_key"),
            },
            on_finish: function (data) {
                trial_counter++;
                data.trial_index = trial_counter;
                if (data.response === null) {
                    data.correct = false;
                    data.timed_out = true;
                } else {
                    data.correct = jsPsych.pluginAPI.compareKeys(data.response, data.correct_key);
                    data.timed_out = false;
                }
            },
        };

        timeline.push({
            timeline: [fixation, block_stimulus, iti],
            timeline_variables: block_stimuli,
            randomize_order: true,
        });

        if (block < CONFIG.n_blocks - 1) {
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus:
                    "<h2>Block " + (block + 1) + " of " + CONFIG.n_blocks + " complete</h2>" +
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

    // Thank you
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Task Complete</h2>" +
            "<p>Thank you for completing the Stroop task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
