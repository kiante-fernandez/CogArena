(function () {
    var CONFIG = {
        n_blocks: 10,
        trials_per_block: 10,
        n_options: 4,
        valid_keys: ["f", "j"],
        response_deadline: 5000,
        fixation_duration: 500,
        feedback_duration: 1500,
        iti_min: 300,
        iti_max: 600,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "safe_exploration";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.trials_per_block = Math.ceil(_nto / CONFIG.n_blocks);
    }

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    // Each block: 2 options with hidden reward means
    // Safe blocks: no kraken risk. Risky blocks: low-reward option may trigger kraken
    function generateBlocks() {
        var blocks = [];
        for (var b = 0; b < CONFIG.n_blocks; b++) {
            var isRisky = b % 2 === 1; // alternate safe/risky
            var highMean = 60 + Math.random() * 20; // 60-80
            var lowMean = 20 + Math.random() * 20;  // 20-40
            var leftHigh = Math.random() > 0.5;

            blocks.push({
                block: b,
                risk_condition: isRisky ? "risky" : "safe",
                left_mean: leftHigh ? highMean : lowMean,
                right_mean: leftHigh ? lowMean : highMean,
                kraken_threshold: 40, // reward below this => kraken risk in risky blocks
            });
        }
        return blocks;
    }

    var allBlocks = generateBlocks();
    var timeline = [];
    var totalScore = 0;

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Safe Exploration</h1>" +
            "<p>Welcome to this fishing exploration task.</p>" +
            "<p>Press any key to begin.</p>",
    });

    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>You are a sailor catching fish from different locations.</p>" +
            "<p>Each round, choose between two fishing spots. Each spot yields a different amount of fish.</p>" +
            "<p>Your goal is to catch as many fish as possible.</p>",

            "<h2>Safe vs Risky Rounds</h2>" +
            "<p>In <strong style='color:#2e7d32'>SAFE rounds</strong>, you can explore freely.</p>" +
            "<p>In <strong style='color:#c62828'>RISKY rounds</strong>, a kraken lurks near low-yield spots!</p>" +
            "<p>If you catch very few fish (&lt;40), the kraken may steal ALL your fish from that round.</p>" +
            "<p>The round indicator will tell you if the kraken is present.</p>",

            "<h2>Response Keys</h2>" +
            "<p style='font-size:28px'><kbd>F</kbd> = <strong>Left Spot</strong></p>" +
            "<p style='font-size:28px'><kbd>J</kbd> = <strong>Right Spot</strong></p>" +
            "<p>You have 5 seconds to respond.</p>" +
            "<p>Press Next to start.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    var trialCounter = 0;

    for (var bi = 0; bi < allBlocks.length; bi++) {
        (function (block) {
            var roundScore = 0;
            var krakenCaught = false;

            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    var riskLabel = block.risk_condition === "risky" ?
                        '<span class="risk-label risk-danger">\u26A0 RISKY ROUND \u2014 Kraken Present!</span>' :
                        '<span class="risk-label risk-safe">\u2714 SAFE ROUND \u2014 No Kraken</span>';
                    return "<h2>Round " + (block.block + 1) + " of " + CONFIG.n_blocks + "</h2>" +
                        "<div>" + riskLabel + "</div>" +
                        '<div class="score-display">Total fish: ' + totalScore + '</div>' +
                        "<p>Press any key to start fishing.</p>";
                },
            });

            for (var t = 0; t < CONFIG.trials_per_block; t++) {
                (function (trialInBlock) {
                    timeline.push({
                        type: jsPsychHtmlKeyboardResponse,
                        stimulus: '<div class="fixation">+</div>',
                        choices: "NO_KEYS",
                        trial_duration: CONFIG.fixation_duration,
                        data: { trial_part: "fixation" },
                    });

                    timeline.push({
                        type: jsPsychHtmlKeyboardResponse,
                        stimulus: function () {
                            if (krakenCaught) {
                                return '<div class="feedback-kraken">Kraken caught! Round over.</div>';
                            }
                            var riskIcon = block.risk_condition === "risky" ? " \u26A0" : " \u2714";
                            return '<div class="trial-counter">Round ' + (block.block + 1) + ', Trial ' + (trialInBlock + 1) + '</div>' +
                                '<div class="risk-label ' + (block.risk_condition === "risky" ? "risk-danger" : "risk-safe") + '">' +
                                block.risk_condition.toUpperCase() + riskIcon + '</div>' +
                                '<div class="option-container">' +
                                '<div class="option-box">\uD83C\uDFA3<br>Spot A<div class="key-hint">F</div></div>' +
                                '<div class="option-box">\uD83C\uDFA3<br>Spot B<div class="key-hint">J</div></div>' +
                                '</div>' +
                                '<div class="score-display">Round fish: ' + roundScore + ' | Total: ' + totalScore + '</div>';
                        },
                        choices: function () {
                            return krakenCaught ? "NO_KEYS" : CONFIG.valid_keys;
                        },
                        trial_duration: function () {
                            return krakenCaught ? 1000 : CONFIG.response_deadline;
                        },
                        data: {
                            trial_part: "stimulus",
                            block: block.block,
                            trial_in_block: trialInBlock,
                            risk_condition: block.risk_condition,
                            left_mean: block.left_mean,
                            right_mean: block.right_mean,
                        },
                        on_finish: function (data) {
                            trialCounter++;
                            data.trial_index = trialCounter;
                            data.timed_out = data.response === null;
                            data.kraken_caught = false;

                            if (krakenCaught || data.timed_out) {
                                data.chosen_option = null;
                                data.reward = 0;
                                data.correct = false;
                                data.kraken_caught = krakenCaught;
                                return;
                            }

                            var side = data.response === "f" ? "left" : "right";
                            data.chosen_option = side;
                            var mean = side === "left" ? block.left_mean : block.right_mean;
                            var reward = Math.round(Math.max(0, mean + (Math.random() - 0.5) * 20));
                            data.reward = reward;
                            data.correct = (block.left_mean >= block.right_mean && side === "left") ||
                                           (block.right_mean > block.left_mean && side === "right");

                            // Kraken check in risky rounds
                            if (block.risk_condition === "risky" && reward < block.kraken_threshold) {
                                if (Math.random() < 0.5) {
                                    krakenCaught = true;
                                    data.kraken_caught = true;
                                    roundScore = 0;
                                    return;
                                }
                            }
                            roundScore += reward;
                        },
                    });

                    timeline.push({
                        type: jsPsychHtmlKeyboardResponse,
                        stimulus: function () {
                            var last = jsPsych.data.get().last(1).values()[0];
                            if (last.kraken_caught) {
                                return '<div class="feedback-kraken">\uD83E\uDD91 KRAKEN! All round fish lost!</div>';
                            }
                            if (last.timed_out) {
                                return '<div class="feedback-kraken">Too slow!</div>';
                            }
                            return '<div class="feedback-reward">\uD83D\uDC1F +' + last.reward + ' fish</div>';
                        },
                        choices: "NO_KEYS",
                        trial_duration: CONFIG.feedback_duration,
                        data: { trial_part: "feedback" },
                    });
                })(t);
            }

            // End of round: add round score to total
            timeline.push({
                type: jsPsychCallFunction,
                func: function () {
                    totalScore += roundScore;
                },
            });
        })(allBlocks[bi]);
    }

    timeline.push({
        type: jsPsychCallFunction,
        async: true,
        func: function (done) {
            var trial_data = jsPsych.data.get().filter({ trial_part: "stimulus" }).values();
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
                .then(function (r) { if (!r.ok) console.error("Submit failed:", r.status); done(); })
                .catch(function (e) { console.error("Submit error:", e); done(); });
        },
    });

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus: "<h2>Task Complete</h2><p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
