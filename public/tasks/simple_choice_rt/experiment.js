(function () {
    var CONFIG = {
        n_simple: 40,
        n_choice2: 20,
        n_choice4: 20,
        total_trials: 80,
        response_deadline: 2000,
        fixation_duration_min: 500,
        fixation_duration_max: 1500,
        feedback_duration: 500,
        iti_min: 200,
        iti_max: 400,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "simple_choice_rt";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        var _ratio = _nto / CONFIG.total_trials;
        CONFIG.n_simple = Math.max(2, Math.round(CONFIG.n_simple * _ratio));
        CONFIG.n_choice2 = Math.max(2, Math.round(CONFIG.n_choice2 * _ratio));
        CONFIG.n_choice4 = Math.max(2, Math.round(CONFIG.n_choice4 * _ratio));
        CONFIG.total_trials = CONFIG.n_simple + CONFIG.n_choice2 + CONFIG.n_choice4;
    }

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    // Stimulus definitions
    var SIMPLE_STIMULUS = {
        html: '<div class="rt-stimulus"><svg width="150" height="150">' +
            '<circle cx="75" cy="75" r="70" fill="green"/></svg></div>',
        label: "green circle",
    };

    var CHOICE2_STIMULI = [
        {
            direction: "left",
            correct_key: "f",
            html: '<div class="rt-stimulus arrow-stimulus">&larr;</div>',
            label: "left arrow",
        },
        {
            direction: "right",
            correct_key: "j",
            html: '<div class="rt-stimulus arrow-stimulus">&rarr;</div>',
            label: "right arrow",
        },
    ];

    var CHOICE4_STIMULI = [
        {
            color: "red",
            correct_key: "d",
            html: '<div class="rt-stimulus"><svg width="150" height="150">' +
                '<circle cx="75" cy="75" r="70" fill="red"/></svg></div>',
            label: "red circle",
        },
        {
            color: "blue",
            correct_key: "f",
            html: '<div class="rt-stimulus"><svg width="150" height="150">' +
                '<circle cx="75" cy="75" r="70" fill="blue"/></svg></div>',
            label: "blue circle",
        },
        {
            color: "green",
            correct_key: "j",
            html: '<div class="rt-stimulus"><svg width="150" height="150">' +
                '<circle cx="75" cy="75" r="70" fill="green"/></svg></div>',
            label: "green circle",
        },
        {
            color: "yellow",
            correct_key: "k",
            html: '<div class="rt-stimulus"><svg width="150" height="150">' +
                '<circle cx="75" cy="75" r="70" fill="gold" stroke="#999" stroke-width="2"/></svg></div>',
            label: "yellow circle",
        },
    ];

    // Generate trial list for a given condition
    function generateSimpleTrials(n) {
        var trials = [];
        for (var i = 0; i < n; i++) {
            trials.push({
                condition: "simple",
                n_alternatives: 1,
                log_n_alternatives: 0,
                stimulus_html: SIMPLE_STIMULUS.html,
                stimulus_label: SIMPLE_STIMULUS.label,
                correct_key: " ",
                valid_keys: [" "],
            });
        }
        return trials;
    }

    function generateChoice2Trials(n) {
        var trials = [];
        for (var i = 0; i < n; i++) {
            var stim = CHOICE2_STIMULI[i % CHOICE2_STIMULI.length];
            trials.push({
                condition: "choice2",
                n_alternatives: 2,
                log_n_alternatives: 1,
                stimulus_html: stim.html,
                stimulus_label: stim.label,
                correct_key: stim.correct_key,
                valid_keys: ["f", "j"],
            });
        }
        return trials;
    }

    function generateChoice4Trials(n) {
        var trials = [];
        for (var i = 0; i < n; i++) {
            var stim = CHOICE4_STIMULI[i % CHOICE4_STIMULI.length];
            trials.push({
                condition: "choice4",
                n_alternatives: 4,
                log_n_alternatives: 2,
                stimulus_html: stim.html,
                stimulus_label: stim.label,
                correct_key: stim.correct_key,
                valid_keys: ["d", "f", "j", "k"],
            });
        }
        return trials;
    }

    // Fisher-Yates shuffle
    function shuffle(arr) {
        for (var i = arr.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var temp = arr[i];
            arr[i] = arr[j];
            arr[j] = temp;
        }
        return arr;
    }

    // Random foreperiod to prevent anticipation
    function randomForeperiod() {
        return CONFIG.fixation_duration_min +
            Math.floor(Math.random() * (CONFIG.fixation_duration_max - CONFIG.fixation_duration_min));
    }

    var timeline = [];

    // Welcome
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Simple and Choice Reaction Time</h1>" +
            "<p>Welcome to the reaction time task.</p>" +
            "<p>Press any key to begin.</p>",
    });

    // Instructions
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Overview</h2>" +
            "<p>This experiment measures how quickly you can respond to visual stimuli.</p>" +
            "<p>There are <strong>three blocks</strong>, each with a different number of possible stimuli.</p>" +
            "<p>Try to respond as <strong>quickly</strong> and <strong>accurately</strong> as possible.</p>",

            "<h2>Block 1: Simple Reaction Time</h2>" +
            "<p>A green circle will appear on screen.</p>" +
            '<div style="text-align:center"><svg width="100" height="100">' +
            '<circle cx="50" cy="50" r="45" fill="green"/></svg></div>' +
            "<p>Press <kbd>SPACE</kbd> as fast as you can whenever it appears.</p>" +
            "<p>There is only one stimulus, so just react as quickly as possible.</p>" +
            "<p>(" + CONFIG.n_simple + " trials)</p>",

            "<h2>Block 2: Two-Choice Reaction Time</h2>" +
            "<p>An arrow will appear pointing either left or right.</p>" +
            '<div class="key-mapping">' +
            '<p><span style="font-size:40px">&larr;</span> Left arrow &rarr; press <kbd>F</kbd></p>' +
            '<p><span style="font-size:40px">&rarr;</span> Right arrow &rarr; press <kbd>J</kbd></p>' +
            "</div>" +
            "<p>(" + CONFIG.n_choice2 + " trials)</p>",

            "<h2>Block 3: Four-Choice Reaction Time</h2>" +
            "<p>A colored circle will appear. Press the key matching the color:</p>" +
            '<div class="key-mapping">' +
            '<p><svg width="30" height="30"><circle cx="15" cy="15" r="14" fill="red"/></svg>' +
            " Red &rarr; press <kbd>D</kbd></p>" +
            '<p><svg width="30" height="30"><circle cx="15" cy="15" r="14" fill="blue"/></svg>' +
            " Blue &rarr; press <kbd>F</kbd></p>" +
            '<p><svg width="30" height="30"><circle cx="15" cy="15" r="14" fill="green"/></svg>' +
            " Green &rarr; press <kbd>J</kbd></p>" +
            '<p><svg width="30" height="30"><circle cx="15" cy="15" r="14" fill="gold" stroke="#999" stroke-width="1"/></svg>' +
            " Yellow &rarr; press <kbd>K</kbd></p>" +
            "</div>" +
            "<p>(" + CONFIG.n_choice4 + " trials)</p>",

            "<h2>Ready?</h2>" +
            "<p>Remember:</p>" +
            "<ul style='text-align:left; max-width:500px; margin:0 auto;'>" +
            "<li>Block 1 (Simple): <kbd>SPACE</kbd> for the green circle</li>" +
            "<li>Block 2 (2-Choice): <kbd>F</kbd> = left, <kbd>J</kbd> = right</li>" +
            "<li>Block 3 (4-Choice): <kbd>D</kbd> = red, <kbd>F</kbd> = blue, <kbd>J</kbd> = green, <kbd>K</kbd> = yellow</li>" +
            "</ul>" +
            "<p>Click Next to begin Block 1 (Simple RT).</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    // --- Block builders ---

    var trialCounter = 0;

    function buildBlock(trialList, blockName) {
        trialList = shuffle(trialList);

        for (var t = 0; t < trialList.length; t++) {
            (function (trialData) {
                // Fixation with variable foreperiod
                timeline.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: '<div class="fixation">+</div>',
                    choices: "NO_KEYS",
                    trial_duration: function () {
                        return randomForeperiod();
                    },
                    data: { trial_part: "fixation" },
                });

                // Stimulus
                timeline.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: trialData.stimulus_html,
                    choices: trialData.valid_keys,
                    trial_duration: CONFIG.response_deadline,
                    data: {
                        trial_part: "stimulus",
                        block: blockName,
                        condition: trialData.condition,
                        n_alternatives: trialData.n_alternatives,
                        log_n_alternatives: trialData.log_n_alternatives,
                        stimulus: trialData.stimulus_label,
                        correct_key: trialData.correct_key,
                    },
                    on_finish: function (data) {
                        trialCounter++;
                        data.trial_index = trialCounter;
                        if (data.response === null) {
                            data.correct = false;
                            data.timed_out = true;
                        } else {
                            data.correct = jsPsych.pluginAPI.compareKeys(
                                data.response,
                                trialData.correct_key
                            );
                            data.timed_out = false;
                        }
                    },
                });

                // Brief accuracy feedback
                timeline.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: function () {
                        var last = jsPsych.data.get().last(1).values()[0];
                        if (last.timed_out) {
                            return '<p class="feedback" style="color:orange;">Too slow!</p>';
                        } else if (last.correct) {
                            return '<p class="feedback" style="color:green;">Correct!</p>';
                        } else {
                            return '<p class="feedback" style="color:red;">Incorrect</p>';
                        }
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
                        return CONFIG.iti_min +
                            Math.floor(Math.random() * (CONFIG.iti_max - CONFIG.iti_min));
                    },
                    data: { trial_part: "iti" },
                });
            })(trialList[t]);
        }
    }

    // === Block 1: Simple RT ===
    var simpleTrials = generateSimpleTrials(CONFIG.n_simple);
    buildBlock(simpleTrials, "simple");

    // Transition to 2-Choice
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Block 1 Complete</h2>" +
            "<p>Good job! Now we move to <strong>Block 2: Two-Choice RT</strong>.</p>" +
            "<p>An arrow will appear pointing left or right.</p>" +
            '<div class="key-mapping">' +
            '<p><span style="font-size:40px">&larr;</span> &rarr; press <kbd>F</kbd></p>' +
            '<p><span style="font-size:40px">&rarr;</span> &rarr; press <kbd>J</kbd></p>' +
            "</div>" +
            "<p>Press any key to begin Block 2.</p>",
    });

    // === Block 2: 2-Choice RT ===
    var choice2Trials = generateChoice2Trials(CONFIG.n_choice2);
    buildBlock(choice2Trials, "choice2");

    // Transition to 4-Choice
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Block 2 Complete</h2>" +
            "<p>Good job! Now we move to <strong>Block 3: Four-Choice RT</strong>.</p>" +
            "<p>A colored circle will appear. Press the matching key:</p>" +
            '<div class="key-mapping">' +
            '<p><svg width="24" height="24"><circle cx="12" cy="12" r="11" fill="red"/></svg>' +
            " Red = <kbd>D</kbd></p>" +
            '<p><svg width="24" height="24"><circle cx="12" cy="12" r="11" fill="blue"/></svg>' +
            " Blue = <kbd>F</kbd></p>" +
            '<p><svg width="24" height="24"><circle cx="12" cy="12" r="11" fill="green"/></svg>' +
            " Green = <kbd>J</kbd></p>" +
            '<p><svg width="24" height="24"><circle cx="12" cy="12" r="11" fill="gold" stroke="#999" stroke-width="1"/></svg>' +
            " Yellow = <kbd>K</kbd></p>" +
            "</div>" +
            "<p>Press any key to begin Block 3.</p>",
    });

    // === Block 3: 4-Choice RT ===
    var choice4Trials = generateChoice4Trials(CONFIG.n_choice4);
    buildBlock(choice4Trials, "choice4");

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

    // Completion
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Task Complete</h2>" +
            "<p>Thank you for completing the Simple and Choice Reaction Time task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
