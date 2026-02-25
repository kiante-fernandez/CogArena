(function () {
    var CONFIG = {
        n_training: 96,
        n_transfer: 24,
        n_blocks: 8,
        trials_per_block: 12,
        valid_keys: ["f", "j"],
        response_deadline: 5000,
        fixation_duration: 500,
        feedback_duration: 1000,
        iti_min: 300,
        iti_max: 500,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "category_learning";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.n_blocks = Math.max(1, Math.ceil(_nto / CONFIG.trials_per_block));
    }

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    // --- Stimulus definitions ---
    // 8 objects defined by 3 binary dimensions: shape, color, size
    // Dimension values: shape (circle=0, square=1), color (red=0, blue=1), size (large=0, small=1)
    var DIMENSIONS = {
        shape: ["circle", "square"],
        color: ["red", "blue"],
        size: ["large", "small"],
    };

    var STIMULI = [];
    for (var s = 0; s < 2; s++) {
        for (var c = 0; c < 2; c++) {
            for (var z = 0; z < 2; z++) {
                STIMULI.push({
                    stimulus_id: STIMULI.length,
                    shape: DIMENSIONS.shape[s],
                    color: DIMENSIONS.color[c],
                    size: DIMENSIONS.size[z],
                });
            }
        }
    }

    // --- Category rule: Type I (single dimension) ---
    // Color determines category: red = Category A, blue = Category B
    function getCategory(stimulus) {
        return stimulus.color === "red" ? "A" : "B";
    }

    // Assign correct categories to all stimuli
    for (var i = 0; i < STIMULI.length; i++) {
        STIMULI[i].correct_category = getCategory(STIMULI[i]);
    }

    // --- Stimulus rendering ---
    function renderStimulus(stimulus) {
        var sizeClass = stimulus.size;
        var shapeClass = stimulus.shape;
        var colorClass = stimulus.color;
        return (
            '<div class="stimulus-container">' +
            '<div class="stimulus-shape ' + shapeClass + " " + colorClass + " " + sizeClass + '"></div>' +
            "</div>"
        );
    }

    // --- Shuffle helper ---
    function shuffle(arr) {
        var a = arr.slice();
        for (var i = a.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var tmp = a[i];
            a[i] = a[j];
            a[j] = tmp;
        }
        return a;
    }

    // --- Generate training trials (8 blocks x 12 trials) ---
    // Each block: each of the 8 stimuli appears once, plus 4 randomly repeated
    function generateTrainingTrials() {
        var trials = [];
        for (var block = 1; block <= CONFIG.n_blocks; block++) {
            var blockTrials = STIMULI.slice(); // all 8 stimuli
            // Add 4 more randomly selected stimuli to reach 12 per block
            var extras = shuffle(STIMULI).slice(0, CONFIG.trials_per_block - STIMULI.length);
            blockTrials = blockTrials.concat(extras);
            blockTrials = shuffle(blockTrials);
            for (var t = 0; t < blockTrials.length; t++) {
                trials.push({
                    stimulus_id: blockTrials[t].stimulus_id,
                    shape: blockTrials[t].shape,
                    color: blockTrials[t].color,
                    size: blockTrials[t].size,
                    correct_category: blockTrials[t].correct_category,
                    block: block,
                    phase: "training",
                });
            }
        }
        return trials;
    }

    // --- Generate transfer trials (each stimulus 3 times, no feedback) ---
    function generateTransferTrials() {
        var trials = [];
        for (var rep = 0; rep < 3; rep++) {
            for (var i = 0; i < STIMULI.length; i++) {
                trials.push({
                    stimulus_id: STIMULI[i].stimulus_id,
                    shape: STIMULI[i].shape,
                    color: STIMULI[i].color,
                    size: STIMULI[i].size,
                    correct_category: STIMULI[i].correct_category,
                    block: CONFIG.n_blocks + 1,
                    phase: "transfer",
                });
            }
        }
        return shuffle(trials);
    }

    var trainingTrials = generateTrainingTrials();
    var transferTrials = generateTransferTrials();

    var timeline = [];

    // --- Welcome ---
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Category Learning Task</h1>" +
            "<p>Welcome to the category learning experiment.</p>" +
            "<p>Press any key to begin.</p>",
    });

    // --- Instructions ---
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>In this task, you will see shapes on the screen one at a time.</p>" +
            "<p>Each shape belongs to either <strong>Category A</strong> or <strong>Category B</strong>.</p>" +
            "<p>Your job is to learn which shapes belong to which category.</p>",

            "<h2>The Shapes</h2>" +
            "<p>The shapes vary in three ways:</p>" +
            "<ul style='text-align:left; max-width:500px; margin:0 auto; font-size:20px; line-height:1.8'>" +
            "<li><strong>Shape:</strong> " +
            '<span class="instruction-shape circle" style="width:20px;height:20px;background:#888;display:inline-block;"></span> circle or ' +
            '<span class="instruction-shape square" style="width:20px;height:20px;background:#888;display:inline-block;"></span> square</li>' +
            "<li><strong>Color:</strong> " +
            '<span class="instruction-shape" style="width:20px;height:20px;background:#d32f2f;display:inline-block;border-radius:4px;"></span> red or ' +
            '<span class="instruction-shape" style="width:20px;height:20px;background:#1976d2;display:inline-block;border-radius:4px;"></span> blue</li>' +
            "<li><strong>Size:</strong> large or small</li>" +
            "</ul>" +
            "<p>Try to figure out the rule that determines each shape's category.</p>",

            "<h2>How to Respond</h2>" +
            "<p style='font-size:28px'><kbd>F</kbd> = <strong>Category A</strong></p>" +
            "<p style='font-size:28px'><kbd>J</kbd> = <strong>Category B</strong></p>" +
            "<p>After each response during training, you will see whether you were correct.</p>" +
            "<p>Use this feedback to learn the rule.</p>" +
            "<p>You have 5 seconds to respond on each trial.</p>" +
            "<p>Press Next to begin the training phase.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    // --- Training trials ---
    var trialCounter = 0;

    trainingTrials.forEach(function (trial, idx) {
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
            stimulus:
                '<div class="trial-counter">Training — Block ' + trial.block + " of " + CONFIG.n_blocks +
                " (Trial " + (idx + 1) + " of " + CONFIG.n_training + ")</div>" +
                renderStimulus(trial) +
                '<div class="key-mapping">' +
                '<div class="key-option"><kbd>F</kbd><br>Category A</div>' +
                '<div class="key-option"><kbd>J</kbd><br>Category B</div>' +
                "</div>",
            choices: CONFIG.valid_keys,
            trial_duration: CONFIG.response_deadline,
            data: {
                trial_part: "stimulus",
                phase: trial.phase,
                block: trial.block,
                stimulus_id: trial.stimulus_id,
                shape: trial.shape,
                color: trial.color,
                size: trial.size,
                correct_category: trial.correct_category,
            },
            on_finish: function (data) {
                trialCounter++;
                data.trial_index = trialCounter;
                data.timed_out = data.response === null;

                if (!data.timed_out) {
                    data.player_response = data.response === "f" ? "A" : "B";
                    data.correct = data.player_response === data.correct_category;
                } else {
                    data.player_response = null;
                    data.correct = false;
                }
            },
        });

        // Feedback (training only)
        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                var lastData = jsPsych.data.get().last(1).values()[0];
                if (lastData.timed_out) {
                    return '<div class="feedback incorrect">Too slow! It was Category ' + lastData.correct_category + "</div>";
                } else if (lastData.correct) {
                    return '<div class="feedback correct">Correct!</div>';
                } else {
                    return '<div class="feedback incorrect">Incorrect &mdash; it was Category ' + lastData.correct_category + "</div>";
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
                return CONFIG.iti_min + Math.random() * (CONFIG.iti_max - CONFIG.iti_min);
            },
            data: { trial_part: "iti" },
        });
    });

    // --- Transition screen ---
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Training Complete</h2>" +
            "<p>You have finished the training phase.</p>" +
            "<p>Now you will see more shapes. This time you will <strong>not</strong> receive feedback.</p>" +
            "<p>Continue to classify each shape as Category A or Category B.</p>" +
            "<p>Press any key to begin the transfer phase.</p>",
    });

    // --- Transfer trials ---
    transferTrials.forEach(function (trial, idx) {
        // Fixation
        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: '<div class="fixation">+</div>',
            choices: "NO_KEYS",
            trial_duration: CONFIG.fixation_duration,
            data: { trial_part: "fixation" },
        });

        // Stimulus (no feedback)
        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus:
                '<div class="trial-counter">Transfer — Trial ' + (idx + 1) + " of " + CONFIG.n_transfer + "</div>" +
                renderStimulus(trial) +
                '<div class="key-mapping">' +
                '<div class="key-option"><kbd>F</kbd><br>Category A</div>' +
                '<div class="key-option"><kbd>J</kbd><br>Category B</div>' +
                "</div>",
            choices: CONFIG.valid_keys,
            trial_duration: CONFIG.response_deadline,
            data: {
                trial_part: "stimulus",
                phase: trial.phase,
                block: trial.block,
                stimulus_id: trial.stimulus_id,
                shape: trial.shape,
                color: trial.color,
                size: trial.size,
                correct_category: trial.correct_category,
            },
            on_finish: function (data) {
                trialCounter++;
                data.trial_index = trialCounter;
                data.timed_out = data.response === null;

                if (!data.timed_out) {
                    data.player_response = data.response === "f" ? "A" : "B";
                    data.correct = data.player_response === data.correct_category;
                } else {
                    data.player_response = null;
                    data.correct = false;
                }
            },
        });

        // ITI (no feedback for transfer)
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
            "<p>Thank you for completing the category learning task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
