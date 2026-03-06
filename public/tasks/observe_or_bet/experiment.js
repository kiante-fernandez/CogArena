(function () {
    var CONFIG = {
        n_blocks: 3,
        trials_per_block: [25, 50, 50],
        valid_keys: ["f", "j", "k"],
        response_deadline: 5000,
        fixation_duration: 500,
        feedback_duration: 1000,
        iti_min: 300,
        iti_max: 600,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "observe_or_bet";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        var perBlock = Math.ceil(_nto / CONFIG.n_blocks);
        CONFIG.trials_per_block = [perBlock, perBlock, perBlock];
    }

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    // Block probabilities: biased toward one color
    var BLOCK_PROBS = [
        { p_blue: 0.70 },  // Block 1 (practice)
        { p_blue: 0.30 },  // Block 2
        { p_blue: 0.80 },  // Block 3
    ];

    var timeline = [];
    var totalScore = 0;

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Observe or Bet</h1>" +
            "<p>Welcome to this prediction task.</p>" +
            "<p>Press any key to begin.</p>",
    });

    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>A light bulb will flash either <strong style='color:#1565c0'>BLUE</strong> or " +
            "<strong style='color:#c62828'>RED</strong> on each trial.</p>" +
            "<p>One color is more likely than the other, but you don't know which.</p>" +
            "<p>You have three choices on each trial:</p>",

            "<h2>Your Three Actions</h2>" +
            "<p><kbd>F</kbd> = <strong>Guess BLUE</strong> \u2014 Earn +1 if correct, lose \u22121 if wrong</p>" +
            "<p><kbd>J</kbd> = <strong>Guess RED</strong> \u2014 Earn +1 if correct, lose \u22121 if wrong</p>" +
            "<p><kbd>K</kbd> = <strong>OBSERVE</strong> \u2014 See the color for free (0 points)</p>" +
            "<p>Use observation to learn, then bet to earn points!</p>",

            "<h2>Blocks</h2>" +
            "<p>There are 3 blocks. The probability may change between blocks.</p>" +
            "<p>Block 1 is practice. Blocks 2-3 count for your score.</p>" +
            "<p>Press Next to start.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    var trialCounter = 0;

    for (var bi = 0; bi < CONFIG.n_blocks; bi++) {
        (function (blockIdx) {
            var blockProb = BLOCK_PROBS[blockIdx];
            var blockScore = 0;
            var isPractice = blockIdx === 0;

            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: "<h2>Block " + (blockIdx + 1) + " of " + CONFIG.n_blocks + "</h2>" +
                    (isPractice ? "<p><em>Practice block \u2014 points don't count</em></p>" :
                        "<p><strong>Points count!</strong></p>") +
                    "<p>" + CONFIG.trials_per_block[blockIdx] + " trials</p>" +
                    '<div class="score-display">Total score: ' + totalScore + '</div>' +
                    "<p>Press any key to start.</p>",
            });

            for (var t = 0; t < CONFIG.trials_per_block[blockIdx]; t++) {
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
                            return '<div class="trial-counter">Block ' + (blockIdx + 1) + ', Trial ' + (trialInBlock + 1) + '</div>' +
                                '<div class="bulb-display">\uD83D\uDCA1</div>' +
                                '<div style="font-size:20px;color:#555;">What color will the light be?</div>' +
                                '<div class="action-container">' +
                                '<div class="action-box" style="color:#1565c0">Guess<br>BLUE<div class="key-hint">F</div></div>' +
                                '<div class="action-box" style="color:#c62828">Guess<br>RED<div class="key-hint">J</div></div>' +
                                '<div class="action-box" style="color:#666">\uD83D\uDC41<br>Observe<div class="key-hint">K</div></div>' +
                                '</div>' +
                                '<div class="score-display">Score: ' + totalScore + '</div>';
                        },
                        choices: CONFIG.valid_keys,
                        trial_duration: CONFIG.response_deadline,
                        data: {
                            trial_part: "stimulus",
                            block: blockIdx,
                            trial_in_block: trialInBlock,
                            is_practice: isPractice,
                            p_blue: blockProb.p_blue,
                        },
                        on_finish: function (data) {
                            trialCounter++;
                            data.trial_index = trialCounter;
                            data.timed_out = data.response === null;

                            // Determine actual light color
                            var lightColor = Math.random() < blockProb.p_blue ? "blue" : "red";
                            data.light_color = lightColor;

                            if (data.timed_out) {
                                data.action = "timeout";
                                data.reward = 0;
                                data.correct = false;
                                return;
                            }

                            if (data.response === "k") {
                                data.action = "observe";
                                data.reward = 0;
                                data.correct = false;
                            } else if (data.response === "f") {
                                data.action = "guess_blue";
                                data.correct = lightColor === "blue";
                                data.reward = data.correct ? 1 : -1;
                            } else {
                                data.action = "guess_red";
                                data.correct = lightColor === "red";
                                data.reward = data.correct ? 1 : -1;
                            }

                            if (!isPractice) {
                                totalScore += data.reward;
                                blockScore += data.reward;
                            }
                        },
                    });

                    timeline.push({
                        type: jsPsychHtmlKeyboardResponse,
                        stimulus: function () {
                            var last = jsPsych.data.get().last(1).values()[0];
                            if (last.timed_out) {
                                return '<div class="feedback-incorrect">Too slow!</div>';
                            }
                            var colorEmoji = last.light_color === "blue" ?
                                '<span style="color:#1565c0;font-size:48px">\uD83D\uDD35 BLUE</span>' :
                                '<span style="color:#c62828;font-size:48px">\uD83D\uDD34 RED</span>';

                            if (last.action === "observe") {
                                return '<div class="feedback-observe">Observed: ' + colorEmoji + '</div>' +
                                    '<div style="font-size:20px;color:#666">0 points (observation)</div>';
                            }
                            if (last.correct) {
                                return '<div class="feedback-correct">\u2714 Correct! +1</div>' +
                                    '<div>Light was: ' + colorEmoji + '</div>';
                            }
                            return '<div class="feedback-incorrect">\u2718 Wrong! \u22121</div>' +
                                '<div>Light was: ' + colorEmoji + '</div>';
                        },
                        choices: "NO_KEYS",
                        trial_duration: CONFIG.feedback_duration,
                        data: { trial_part: "feedback" },
                    });
                })(t);
            }
        })(bi);
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
        stimulus: "<h2>Task Complete</h2><p>Final score: " + totalScore + "</p><p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
