(function () {
    var CONFIG = {
        n_trials: 80,
        n_blocks: 4,
        trials_per_block: 20,
        valid_keys: ["f", "j"],
        key_map: { H: "f", S: "j" },
        response_deadline: 3000,
        fixation_duration: 500,
        feedback_duration: 0,
        iti_min: 300,
        iti_max: 500,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "navon";

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

    // --- Navon figure rendering ---
    // Each large letter is defined as a 7-row x 7-column grid of 0s and 1s.
    // 1 = place the local letter, 0 = place spaces.
    var LETTER_PATTERNS = {
        H: [
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 1, 1, 1, 1],
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
        ],
        S: [
            [0, 1, 1, 1, 1],
            [1, 0, 0, 0, 0],
            [1, 0, 0, 0, 0],
            [0, 1, 1, 1, 0],
            [0, 0, 0, 0, 1],
            [0, 0, 0, 0, 1],
            [1, 1, 1, 1, 0],
        ],
    };

    /**
     * Render a Navon figure as an HTML string.
     * @param {string} globalLetter - The large letter shape ("H" or "S")
     * @param {string} localLetter  - The small letter used to fill ("H" or "S")
     * @returns {string} HTML for the Navon figure
     */
    function renderNavonFigure(globalLetter, localLetter) {
        var pattern = LETTER_PATTERNS[globalLetter];
        var rows = [];
        for (var r = 0; r < pattern.length; r++) {
            var row = [];
            for (var c = 0; c < pattern[r].length; c++) {
                if (pattern[r][c] === 1) {
                    row.push(localLetter);
                } else {
                    row.push(" ");
                }
            }
            rows.push(row.join(" "));
        }
        return '<div class="navon-stimulus">' + rows.join("\n") + "</div>";
    }

    // Target level alternates by block: blocks 1,3 = global; blocks 2,4 = local
    function getTargetLevel(block) {
        return block % 2 === 1 ? "global" : "local";
    }

    // Generate all trial specifications
    function generateTrials() {
        var trials = [];
        var globalLetters = ["H", "S"];
        var localLetters = ["H", "S"];

        for (var b = 0; b < CONFIG.n_blocks; b++) {
            var blockNum = b + 1;
            var targetLevel = getTargetLevel(blockNum);
            var blockTrials = [];

            // 20 trials per block: 5 of each combination (H-H, H-S, S-H, S-S)
            for (var gi = 0; gi < globalLetters.length; gi++) {
                for (var li = 0; li < localLetters.length; li++) {
                    var gl = globalLetters[gi];
                    var ll = localLetters[li];
                    var congruency = gl === ll ? "congruent" : "incongruent";
                    var correctResponse = targetLevel === "global" ? gl : ll;
                    var correctKey = CONFIG.key_map[correctResponse];
                    var nReps = 5;

                    for (var rep = 0; rep < nReps; rep++) {
                        blockTrials.push({
                            block: blockNum,
                            target_level: targetLevel,
                            global_letter: gl,
                            local_letter: ll,
                            congruency: congruency,
                            correct_response: correctResponse,
                            correct_key: correctKey,
                        });
                    }
                }
            }

            // Shuffle within block
            for (var i = blockTrials.length - 1; i > 0; i--) {
                var j = Math.floor(Math.random() * (i + 1));
                var temp = blockTrials[i];
                blockTrials[i] = blockTrials[j];
                blockTrials[j] = temp;
            }

            trials = trials.concat(blockTrials);
        }
        return trials;
    }

    var allTrials = generateTrials();
    var timeline = [];

    // --- Welcome ---
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Navon Global/Local Task</h1>" +
            "<p>Welcome to the Navon task.</p>" +
            "<p>Press any key to begin.</p>",
    });

    // --- Instructions ---
    var exampleGlobalH_localS = renderNavonFigure("H", "S");
    var exampleGlobalS_localH = renderNavonFigure("S", "H");
    var exampleGlobalH_localH = renderNavonFigure("H", "H");
    var exampleGlobalS_localS = renderNavonFigure("S", "S");

    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>In this task, you will see large letters made up of smaller letters.</p>" +
            "<p>These are called <strong>Navon figures</strong>. Here is an example:</p>" +
            "<div style='margin:20px 0'>" + exampleGlobalH_localS + "</div>" +
            "<p>The large (global) letter above is <strong>H</strong>, and it is made of small (local) <strong>S</strong> letters.</p>",

            "<h2>More Examples</h2>" +
            "<div style='display:flex; justify-content:center; gap:60px; margin:20px 0'>" +
            "<div><p>Global <strong>S</strong>, Local <strong>H</strong></p>" + exampleGlobalS_localH + "</div>" +
            "<div><p>Global <strong>H</strong>, Local <strong>H</strong></p>" + exampleGlobalH_localH + "</div>" +
            "<div><p>Global <strong>S</strong>, Local <strong>S</strong></p>" + exampleGlobalS_localS + "</div>" +
            "</div>" +
            "<p>Sometimes the large and small letters match (congruent), and sometimes they differ (incongruent).</p>",

            "<h2>Your Task</h2>" +
            "<p>On each block, you will be asked to identify either the <strong>LARGE (global)</strong> letter or the <strong>SMALL (local)</strong> letter.</p>" +
            "<p>A message before each block will tell you which level to attend to.</p>" +
            "<p><strong>Response keys:</strong></p>" +
            "<p>Press <kbd>F</kbd> if the target letter is <strong>H</strong></p>" +
            "<p>Press <kbd>J</kbd> if the target letter is <strong>S</strong></p>",

            "<h2>Ready?</h2>" +
            "<p>Respond as quickly and accurately as possible.</p>" +
            "<p>The task has " + CONFIG.n_blocks + " blocks of " + CONFIG.trials_per_block + " trials each.</p>" +
            "<p>Click Next to begin with a short practice round.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    // --- Practice trials (4 trials: one of each stimulus type, global level) ---
    var practiceStims = [
        { global_letter: "H", local_letter: "H", congruency: "congruent", target_level: "global", correct_response: "H", correct_key: "f" },
        { global_letter: "S", local_letter: "S", congruency: "congruent", target_level: "global", correct_response: "S", correct_key: "j" },
        { global_letter: "H", local_letter: "S", congruency: "incongruent", target_level: "global", correct_response: "H", correct_key: "f" },
        { global_letter: "S", local_letter: "H", congruency: "incongruent", target_level: "global", correct_response: "S", correct_key: "j" },
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
        stimulus:
            "<h2>Practice Round</h2>" +
            "<p>Identify the <strong>LARGE (global)</strong> letter.</p>" +
            "<p><kbd>F</kbd> = H &nbsp;&nbsp;&nbsp; <kbd>J</kbd> = S</p>" +
            "<p>Press any key to start practice.</p>",
    });

    practiceStims.forEach(function (stim) {
        // Fixation
        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: '<div class="fixation">+</div>',
            choices: "NO_KEYS",
            trial_duration: CONFIG.fixation_duration,
        });

        // Stimulus
        var correctKey = stim.correct_key;
        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: renderNavonFigure(stim.global_letter, stim.local_letter),
            choices: CONFIG.valid_keys,
            trial_duration: CONFIG.response_deadline,
            data: { trial_part: "practice", congruency: stim.congruency },
            on_finish: function (data) {
                data.correct = data.response === correctKey;
            },
        });

        // Feedback
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

    // --- Main experiment ---
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Main Experiment</h2>" +
            "<p>Practice is over. The main task will now begin.</p>" +
            "<p>Remember: <kbd>F</kbd> = H, <kbd>J</kbd> = S</p>" +
            "<p>Press any key to start.</p>",
    });

    var trialCounter = 0;

    for (var t = 0; t < allTrials.length; t++) {
        // Block instruction at the start of each block
        if (t % CONFIG.trials_per_block === 0) {
            var blockNum = Math.floor(t / CONFIG.trials_per_block) + 1;
            var level = getTargetLevel(blockNum);
            var levelLabel = level === "global" ? "LARGE (global)" : "SMALL (local)";
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus:
                    '<div class="block-instruction">' +
                    "<h2>Block " + blockNum + " of " + CONFIG.n_blocks + "</h2>" +
                    "<p>In this block, identify the <strong>" + levelLabel + "</strong> letter.</p>" +
                    "<p><kbd>F</kbd> = H &nbsp;&nbsp;&nbsp; <kbd>J</kbd> = S</p>" +
                    "<p>Press any key to start.</p>" +
                    "</div>",
            });
        }

        (function (trialData) {
            // Fixation
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: '<div class="fixation">+</div>',
                choices: "NO_KEYS",
                trial_duration: CONFIG.fixation_duration,
            });

            var correctKey = trialData.correct_key;

            // Stimulus
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: renderNavonFigure(trialData.global_letter, trialData.local_letter),
                choices: CONFIG.valid_keys,
                trial_duration: CONFIG.response_deadline,
                data: {
                    trial_part: "stimulus",
                    block: trialData.block,
                    target_level: trialData.target_level,
                    global_letter: trialData.global_letter,
                    local_letter: trialData.local_letter,
                    congruency: trialData.congruency,
                    correct_response: trialData.correct_response,
                    correct_key: correctKey,
                },
                on_finish: function (data) {
                    trialCounter++;
                    data.trial_index = trialCounter;
                    data.timed_out = data.response === null;
                    if (data.timed_out) {
                        data.correct = false;
                        data.player_response = null;
                    } else {
                        data.correct = data.response === correctKey;
                        // Map key back to letter
                        if (data.response === "f") {
                            data.player_response = "H";
                        } else if (data.response === "j") {
                            data.player_response = "S";
                        } else {
                            data.player_response = null;
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

        // Block break (between blocks, not after last trial)
        if ((t + 1) % CONFIG.trials_per_block === 0 && t < allTrials.length - 1) {
            var completedBlock = Math.floor(t / CONFIG.trials_per_block) + 1;
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus:
                    "<h2>Block " + completedBlock + " of " + CONFIG.n_blocks + " complete</h2>" +
                    "<p>Take a short break if needed.</p>" +
                    "<p>Press any key to continue.</p>",
            });
        }
    }

    // --- Data submission ---
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

    // --- Completion ---
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Task Complete</h2>" +
            "<p>Thank you for completing the Navon Global/Local task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
