(function () {
    var CONFIG = {
        n_blocks: 10,
        trials_per_block: 15,
        n_options: 6,
        novel_reward_bonus: 0.1,
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
    var TASK_ID = "novelty_exploration";

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

    var SYMBOLS = ["\u25A0", "\u25B2", "\u25CF", "\u2605", "\u25C6", "\u2666",
                   "\u2660", "\u2663", "\u2665", "\u25D0", "\u25CB", "\u2736"];
    var COLORS = ["#e53935", "#1e88e5", "#43a047", "#f9a825", "#8e24aa", "#00897b",
                  "#d81b60", "#5e35b1", "#00acc1", "#6d4c41", "#546e7a", "#ff6f00"];

    function generateBlocks() {
        var blocks = [];
        var seenOptions = {};

        for (var b = 0; b < CONFIG.n_blocks; b++) {
            var blockOptions = [];
            for (var o = 0; o < CONFIG.n_options; o++) {
                var optIdx = b * CONFIG.n_options + o;
                var sym = SYMBOLS[optIdx % SYMBOLS.length];
                var col = COLORS[optIdx % COLORS.length];
                var id = "opt_" + b + "_" + o;
                blockOptions.push({
                    id: id,
                    symbol: sym,
                    color: col,
                    reward_prob: 0.3 + Math.random() * 0.4,
                });
            }

            var trials = [];
            for (var t = 0; t < CONFIG.trials_per_block; t++) {
                var idx1 = Math.floor(Math.random() * CONFIG.n_options);
                var idx2 = (idx1 + 1 + Math.floor(Math.random() * (CONFIG.n_options - 1))) % CONFIG.n_options;
                var opt1 = blockOptions[idx1];
                var opt2 = blockOptions[idx2];

                var leftIsFirst = Math.random() > 0.5;
                trials.push({
                    left: leftIsFirst ? opt1 : opt2,
                    right: leftIsFirst ? opt2 : opt1,
                    block: b,
                    trial_in_block: t,
                });
            }
            blocks.push({ trials: trials, options: blockOptions });
        }
        return blocks;
    }

    var allBlocks = generateBlocks();
    var timeline = [];
    var totalScore = 0;
    var optionEncounters = {};

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Novelty Exploration</h1>" +
            "<p>Welcome to this exploration task.</p>" +
            "<p>Press any key to begin.</p>",
    });

    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>In this task, you will explore different options across multiple rounds.</p>" +
            "<p>Each option has a hidden probability of giving you a <strong>coin</strong>.</p>" +
            "<p>Your goal is to collect as many coins as possible.</p>",

            "<h2>Novel vs Familiar</h2>" +
            "<p>Some options will be <strong>new</strong> (you haven't seen them before) " +
            "while others will be <strong>familiar</strong> (you've chosen them in previous trials).</p>" +
            "<p>New options might be better or worse than familiar ones \u2014 it's up to you to explore!</p>",

            "<h2>Response Keys</h2>" +
            "<p style='font-size:28px'><kbd>F</kbd> = <strong>Left Option</strong></p>" +
            "<p style='font-size:28px'><kbd>J</kbd> = <strong>Right Option</strong></p>" +
            "<p>You have 5 seconds to respond.</p>" +
            "<p>Press Next to start.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    var trialCounter = 0;

    for (var bi = 0; bi < allBlocks.length; bi++) {
        if (bi > 0) {
            (function (blockNum) {
                timeline.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: "<h2>Round " + (blockNum + 1) + " of " + CONFIG.n_blocks + "</h2>" +
                        "<p>New round with new options!</p>" +
                        '<div class="score-display">Total coins: ' + totalScore + '</div>' +
                        "<p>Press any key to continue.</p>",
                });
            })(bi);
        }

        var blockTrials = allBlocks[bi].trials;
        for (var ti = 0; ti < blockTrials.length; ti++) {
            (function (trial) {
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
                        var leftNovel = !optionEncounters[trial.left.id];
                        var rightNovel = !optionEncounters[trial.right.id];
                        var leftClass = leftNovel ? "option-box option-novel" : "option-box option-familiar";
                        var rightClass = rightNovel ? "option-box option-novel" : "option-box option-familiar";
                        var leftLabel = leftNovel ? "NEW" : "Seen " + (optionEncounters[trial.left.id] || 0) + "x";
                        var rightLabel = rightNovel ? "NEW" : "Seen " + (optionEncounters[trial.right.id] || 0) + "x";

                        return '<div class="trial-counter">Trial ' + (trialCounter + 1) + '</div>' +
                            '<div class="block-label">Round ' + (trial.block + 1) + ' of ' + CONFIG.n_blocks + '</div>' +
                            '<div class="option-container">' +
                            '<div class="' + leftClass + '">' +
                            '<span style="color:' + trial.left.color + '">' + trial.left.symbol + '</span>' +
                            '<div style="font-size:14px;color:#888">' + leftLabel + '</div>' +
                            '<div class="key-hint">F</div></div>' +
                            '<div class="' + rightClass + '">' +
                            '<span style="color:' + trial.right.color + '">' + trial.right.symbol + '</span>' +
                            '<div style="font-size:14px;color:#888">' + rightLabel + '</div>' +
                            '<div class="key-hint">J</div></div>' +
                            '</div>' +
                            '<div class="score-display">Coins: ' + totalScore + '</div>';
                    },
                    choices: CONFIG.valid_keys,
                    trial_duration: CONFIG.response_deadline,
                    data: {
                        trial_part: "stimulus",
                        block: trial.block,
                        trial_in_block: trial.trial_in_block,
                        left_id: trial.left.id,
                        right_id: trial.right.id,
                        left_reward_prob: trial.left.reward_prob,
                        right_reward_prob: trial.right.reward_prob,
                    },
                    on_finish: function (data) {
                        trialCounter++;
                        data.trial_index = trialCounter;
                        data.timed_out = data.response === null;

                        if (!data.timed_out) {
                            var chosen = data.response === "f" ? trial.left : trial.right;
                            var unchosen = data.response === "f" ? trial.right : trial.left;
                            data.chosen_option = chosen.id;
                            data.chosen_novelty = !optionEncounters[chosen.id] ? "novel" : "familiar";
                            data.unchosen_novelty = !optionEncounters[unchosen.id] ? "novel" : "familiar";

                            var reward = Math.random() < chosen.reward_prob ? 1 : 0;
                            data.reward = reward;
                            data.correct = reward === 1;
                            totalScore += reward;

                            optionEncounters[chosen.id] = (optionEncounters[chosen.id] || 0) + 1;
                        } else {
                            data.chosen_option = null;
                            data.chosen_novelty = null;
                            data.unchosen_novelty = null;
                            data.reward = 0;
                            data.correct = false;
                        }
                    },
                });

                timeline.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: function () {
                        var last = jsPsych.data.get().last(1).values()[0];
                        if (last.timed_out) {
                            return '<div class="feedback-empty">Too slow!</div>';
                        }
                        if (last.reward === 1) {
                            return '<div class="feedback-found">\uD83E\uDE99 Coin found! (+1)</div>';
                        }
                        return '<div class="feedback-empty">No coin this time</div>';
                    },
                    choices: "NO_KEYS",
                    trial_duration: CONFIG.feedback_duration,
                    data: { trial_part: "feedback" },
                });
            })(blockTrials[ti]);
        }
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
        stimulus: "<h2>Task Complete</h2><p>You collected " + totalScore + " coins!</p><p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
