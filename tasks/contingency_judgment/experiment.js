(function () {
    var CONFIG = {
        n_blocks: 4,
        trials_per_block: 20,
        n_total: 80,
        slider_min: 0,
        slider_max: 100,
        observation_duration: 1500,
        iti: 500,
        rating_deadline: 15000,
        fixation_duration: 500,
    };
    CONFIG.rating_deadline = getTrialDuration(CONFIG.rating_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "contingency_judgment";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.trials_per_block = Math.max(4, Math.ceil(_nto / CONFIG.n_blocks));
    }

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 200,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    // --- Block designs ---
    // Each block has a different contingency (delta P) level
    // delta_p = P(E|C) - P(E|~C)
    var BLOCK_DESIGNS = [
        { block: 1, delta_p: 0.75,  p_e_given_c: 0.875, p_e_given_not_c: 0.125, label: "strong positive cause" },
        { block: 2, delta_p: 0.25,  p_e_given_c: 0.625, p_e_given_not_c: 0.375, label: "weak positive cause" },
        { block: 3, delta_p: 0.0,   p_e_given_c: 0.50,  p_e_given_not_c: 0.50,  label: "no relationship" },
        { block: 4, delta_p: -0.25, p_e_given_c: 0.375, p_e_given_not_c: 0.625, label: "weak preventive cause" },
    ];

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

    // --- Generate observation trials for one block ---
    function generateBlockTrials(blockDesign) {
        var trials = [];
        // 10 cause-present, 10 cause-absent per block
        var causePresent = [];
        for (var i = 0; i < CONFIG.trials_per_block / 2; i++) {
            causePresent.push(true);
        }
        for (var j = 0; j < CONFIG.trials_per_block / 2; j++) {
            causePresent.push(false);
        }
        causePresent = shuffle(causePresent);

        for (var t = 0; t < CONFIG.trials_per_block; t++) {
            var cp = causePresent[t];
            var pEffect = cp ? blockDesign.p_e_given_c : blockDesign.p_e_given_not_c;
            var ep = Math.random() < pEffect;

            var cellType;
            if (cp && ep) cellType = "a";       // C+E+
            else if (cp && !ep) cellType = "b";  // C+E-
            else if (!cp && ep) cellType = "c";  // C-E+
            else cellType = "d";                  // C-E-

            trials.push({
                block: blockDesign.block,
                block_delta_p: blockDesign.delta_p,
                cause_present: cp,
                effect_present: ep,
                cell_type: cellType,
            });
        }
        return trials;
    }

    // --- Render observation display ---
    function renderObservation(cause_present, effect_present) {
        var causeHtml;
        if (cause_present) {
            causeHtml =
                '<div class="cause-display">' +
                '<span class="pill-icon" style="color:#4caf50;">&#x1F48A;</span> ' +
                'Patient <strong>took</strong> medicine' +
                '</div>';
        } else {
            causeHtml =
                '<div class="cause-display">' +
                'Patient did <strong>NOT</strong> take medicine' +
                '</div>';
        }

        var effectHtml;
        if (effect_present) {
            effectHtml =
                '<div class="effect-display effect-present">' +
                '&#x2705; Patient <strong>recovered</strong>' +
                '</div>';
        } else {
            effectHtml =
                '<div class="effect-display effect-absent">' +
                '&#x274C; Patient did <strong>NOT</strong> recover' +
                '</div>';
        }

        return '<div class="observation-container">' + causeHtml + effectHtml + '</div>';
    }

    // --- Build timeline ---
    var timeline = [];
    var trialCounter = 0;
    var ratingCounter = 0;

    // Welcome
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Contingency Judgment Task</h1>" +
            "<p>Welcome to the causal reasoning experiment.</p>" +
            "<p>Press any key to begin.</p>",
    });

    // Instructions
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>In this experiment, you will observe a series of patients.</p>" +
            "<p>For each patient, you will see whether they <strong>took a medicine</strong> or not, " +
            "and whether they <strong>recovered</strong> from their illness or not.</p>" +
            "<p>Your task is to judge how strongly the medicine <strong>causes</strong> (or prevents) recovery.</p>",

            "<h2>What You Will See</h2>" +
            '<div class="observation-container" style="min-height:auto; margin:20px 0;">' +
            '<div class="cause-display">' +
            '<span class="pill-icon" style="color:#4caf50;">&#x1F48A;</span> ' +
            'Patient <strong>took</strong> medicine' +
            '</div>' +
            '<div class="effect-display effect-present">' +
            '&#x2705; Patient <strong>recovered</strong>' +
            '</div>' +
            '</div>' +
            "<p>Each observation shows one patient's outcome.</p>" +
            "<p>Watch carefully whether recovery is more common when the medicine is taken.</p>",

            "<h2>Rating the Medicine</h2>" +
            "<p>After observing a group of patients, you will rate the medicine's effectiveness.</p>" +
            "<p>Use a slider from <strong>0</strong> to <strong>100</strong>:</p>" +
            "<ul style='text-align:left; max-width:500px; margin:0 auto; font-size:18px; line-height:1.8'>" +
            "<li><strong>0</strong> = Medicine <em>prevents</em> recovery</li>" +
            "<li><strong>50</strong> = Medicine has <em>no effect</em></li>" +
            "<li><strong>100</strong> = Medicine <em>strongly causes</em> recovery</li>" +
            "</ul>" +
            "<p>There are 4 groups of patients to observe.</p>" +
            "<p>Click Next to begin.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    // --- Build blocks ---
    for (var b = 0; b < BLOCK_DESIGNS.length; b++) {
        var blockDesign = BLOCK_DESIGNS[b];
        var blockTrials = generateBlockTrials(blockDesign);

        // Block intro
        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus:
                "<h2>Group " + blockDesign.block + " of " + CONFIG.n_blocks + "</h2>" +
                "<p>You will now observe <strong>" + CONFIG.trials_per_block + " patients</strong>.</p>" +
                "<p>Watch whether the medicine affects recovery.</p>" +
                "<p>Press any key to begin observations.</p>",
        });

        // Observation trials
        for (var t = 0; t < blockTrials.length; t++) {
            (function (trial, obsIndex, blockNum) {
                // Fixation
                timeline.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: '<div class="fixation">+</div>',
                    choices: "NO_KEYS",
                    trial_duration: CONFIG.fixation_duration,
                    data: { trial_part: "fixation" },
                });

                // Observation
                timeline.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus:
                        '<div class="observation-counter">Group ' + blockNum + ' &mdash; Observation ' +
                        (obsIndex + 1) + ' of ' + CONFIG.trials_per_block + '</div>' +
                        renderObservation(trial.cause_present, trial.effect_present),
                    choices: "NO_KEYS",
                    trial_duration: CONFIG.observation_duration,
                    data: {
                        trial_part: "observation",
                        block: trial.block,
                        block_delta_p: trial.block_delta_p,
                        cause_present: trial.cause_present,
                        effect_present: trial.effect_present,
                        cell_type: trial.cell_type,
                    },
                    on_finish: function (data) {
                        trialCounter++;
                        data.trial_index = trialCounter;
                    },
                });

                // ITI
                timeline.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: "",
                    choices: "NO_KEYS",
                    trial_duration: CONFIG.iti,
                    data: { trial_part: "iti" },
                });
            })(blockTrials[t], t, blockDesign.block);
        }

        // Rating after block
        (function (bd) {
            timeline.push({
                type: jsPsychHtmlSliderResponse,
                stimulus:
                    '<div class="rating-prompt">' +
                    '<h2>Rate the Medicine (Group ' + bd.block + ')</h2>' +
                    '<p>Based on the ' + CONFIG.trials_per_block + ' patients you just observed:</p>' +
                    '<p><strong>How strongly does the medicine cause recovery?</strong></p>' +
                    '</div>',
                min: CONFIG.slider_min,
                max: CONFIG.slider_max,
                step: 1,
                slider_start: 50,
                labels: ["0<br>Prevents<br>recovery", "50<br>No<br>effect", "100<br>Strongly causes<br>recovery"],
                require_movement: true,
                trial_duration: CONFIG.rating_deadline,
                data: {
                    trial_part: "stimulus",
                    block: bd.block,
                    block_delta_p: bd.delta_p,
                },
                on_finish: function (data) {
                    ratingCounter++;
                    data.trial_index = ratingCounter;
                    data.timed_out = data.response === null;

                    if (!data.timed_out) {
                        data.rating = data.response;
                    } else {
                        data.rating = 50; // default to neutral on timeout
                    }

                    data.rating_normalized = data.rating / 100;
                    data.actual_delta_p = data.block_delta_p;

                    // expected_rating maps delta_p from [-1,1] to [0,1]
                    var expected_rating = (data.actual_delta_p + 1) / 2;
                    data.rating_accuracy = 1 - Math.abs(data.rating_normalized - expected_rating);
                    data.rating_error = Math.abs(data.rating_normalized - expected_rating);
                    data.high_rating = data.rating_normalized > 0.5;
                    data.overestimated = data.rating_normalized > 0.55;
                },
            });
        })(blockDesign);
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
            "<p>Thank you for completing the Contingency Judgment task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
