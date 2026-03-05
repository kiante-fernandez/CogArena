(function () {
    var CONFIG = {
        n_trials: 100,
        n_rounds: 4,
        trials_per_round: 25,
        n_targets: 6,
        valid_keys: ["f", "j"],
        response_deadline: 10000,
        fixation_duration: 500,
        feedback_duration: 1000,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "insider_attack";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.n_trials = _nto;
        CONFIG.trials_per_round = Math.ceil(_nto / CONFIG.n_rounds);
    }

    var jsPsych = initJsPsych({ experiment_width: 800, minimum_valid_rt: 100 });
    if (SESSION_ID === "debug") window._jsPsych = jsPsych;

    // Target configurations per round (reward, penalty, monitoring probability)
    var TARGET_CONFIGS = [
        // Round 1
        [
            { reward: 3, penalty: -2, mprob: 0.15 },
            { reward: 8, penalty: -5, mprob: 0.50 },
            { reward: 5, penalty: -3, mprob: 0.30 },
            { reward: 2, penalty: -1, mprob: 0.10 },
            { reward: 9, penalty: -8, mprob: 0.55 },
            { reward: 4, penalty: -2, mprob: 0.20 },
        ],
        // Round 2
        [
            { reward: 6, penalty: -4, mprob: 0.35 },
            { reward: 3, penalty: -1, mprob: 0.10 },
            { reward: 7, penalty: -6, mprob: 0.45 },
            { reward: 9, penalty: -7, mprob: 0.60 },
            { reward: 4, penalty: -2, mprob: 0.15 },
            { reward: 5, penalty: -3, mprob: 0.25 },
        ],
        // Round 3
        [
            { reward: 8, penalty: -6, mprob: 0.50 },
            { reward: 5, penalty: -3, mprob: 0.25 },
            { reward: 2, penalty: -1, mprob: 0.05 },
            { reward: 6, penalty: -4, mprob: 0.30 },
            { reward: 3, penalty: -2, mprob: 0.10 },
            { reward: 7, penalty: -5, mprob: 0.40 },
        ],
        // Round 4
        [
            { reward: 4, penalty: -3, mprob: 0.20 },
            { reward: 9, penalty: -8, mprob: 0.55 },
            { reward: 6, penalty: -4, mprob: 0.35 },
            { reward: 3, penalty: -1, mprob: 0.08 },
            { reward: 7, penalty: -6, mprob: 0.45 },
            { reward: 5, penalty: -2, mprob: 0.18 },
        ],
    ];

    function computeEV(target) {
        return target.reward * (1 - target.mprob) + target.penalty * target.mprob;
    }

    function generateTrials() {
        var trials = [];
        for (var r = 0; r < CONFIG.n_rounds; r++) {
            var targets = TARGET_CONFIGS[r];
            // Pre-select which target is shown each trial (random pair)
            for (var t = 0; t < CONFIG.trials_per_round; t++) {
                // Pick two distinct targets to present
                var t1 = Math.floor(Math.random() * CONFIG.n_targets);
                var t2;
                do { t2 = Math.floor(Math.random() * CONFIG.n_targets); } while (t2 === t1);

                var left_target = targets[t1];
                var right_target = targets[t2];
                var left_ev = computeEV(left_target);
                var right_ev = computeEV(right_target);

                // Determine if warning appears (based on monitoring prob of chosen target - resolved at response time)
                trials.push({
                    round: r,
                    trial_in_round: t,
                    left_idx: t1,
                    right_idx: t2,
                    left_target: left_target,
                    right_target: right_target,
                    left_ev: left_ev,
                    right_ev: right_ev,
                });
            }
        }
        return trials;
    }

    function renderTargetInfo(target, label, key) {
        return '<div class="target-box">' +
            '<div style="font-weight:bold;font-size:20px">' + label + '</div>' +
            '<div class="reward">Reward: +' + target.reward + '</div>' +
            '<div class="penalty">Penalty: ' + target.penalty + '</div>' +
            '<div class="key-hint">' + key + '</div></div>';
    }

    var allTrials = generateTrials();
    var timeline = [];
    var totalScore = 0;

    timeline.push({ type: jsPsychHtmlKeyboardResponse, stimulus: "<h1>Insider Attack Game</h1><p>Press any key to begin.</p>" });
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2><p>You are trying to access computers on a network to steal information.</p><p>Each computer has a <strong style='color:#2e7d32'>reward</strong> if unmonitored and a <strong style='color:#c62828'>penalty</strong> if caught.</p>",
            "<h2>How It Works</h2><p>On each trial, you choose between two computers.</p><p>Sometimes you may see a <strong style='color:#c62828'>warning</strong> that a computer is being monitored.</p><p>After choosing, you find out whether you were caught or successful.</p>",
            "<h2>Strategy</h2><p>Some computers have high rewards but are more likely to be monitored.</p><p>Others have lower rewards but are safer.</p><p>Try to maximize your total score across all trials!</p>",
            "<h2>Response Keys</h2><p style='font-size:28px'><kbd>F</kbd> = <strong>Left Computer</strong></p><p style='font-size:28px'><kbd>J</kbd> = <strong>Right Computer</strong></p><p>Press Next to start.</p>",
        ],
        show_clickable_nav: true, button_label_next: "Next", button_label_previous: "Previous",
    });

    var trialCounter = 0;
    var prevRound = -1;

    for (var ti = 0; ti < allTrials.length; ti++) {
        (function (trial) {
            if (trial.round !== prevRound) {
                timeline.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: '<h2>Round ' + (trial.round + 1) + ' of ' + CONFIG.n_rounds + '</h2>' +
                        '<p>New round! Target payoffs have changed.</p>' +
                        '<p>Press any key to continue.</p>',
                });
                prevRound = trial.round;
            }

            timeline.push({ type: jsPsychHtmlKeyboardResponse, stimulus: '<div class="fixation">+</div>', choices: "NO_KEYS", trial_duration: CONFIG.fixation_duration, data: { trial_part: "fixation" } });

            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: '<div class="trial-counter">Trial ' + (trialCounter + 1) + ' of ' + CONFIG.n_trials + '</div>' +
                    '<div class="score-display">Score: ' + totalScore + '</div>' +
                    '<div class="mine-container">' +
                    renderTargetInfo(trial.left_target, "Computer " + (trial.left_idx + 1), "F") +
                    renderTargetInfo(trial.right_target, "Computer " + (trial.right_idx + 1), "J") +
                    '</div>',
                choices: CONFIG.valid_keys,
                trial_duration: CONFIG.response_deadline,
                data: {
                    trial_part: "stimulus",
                    round: trial.round,
                    trial_in_round: trial.trial_in_round,
                    left_idx: trial.left_idx,
                    right_idx: trial.right_idx,
                    left_reward: trial.left_target.reward,
                    right_reward: trial.right_target.reward,
                    left_penalty: trial.left_target.penalty,
                    right_penalty: trial.right_target.penalty,
                    left_mprob: trial.left_target.mprob,
                    right_mprob: trial.right_target.mprob,
                    left_ev: trial.left_ev,
                    right_ev: trial.right_ev,
                },
                on_finish: function (data) {
                    trialCounter++;
                    data.trial_index = trialCounter;
                    data.timed_out = data.response === null;

                    if (!data.timed_out) {
                        var choseLeft = data.response === "f";
                        var chosen = choseLeft
                            ? { reward: data.left_reward, penalty: data.left_penalty, mprob: data.left_mprob, ev: data.left_ev }
                            : { reward: data.right_reward, penalty: data.right_penalty, mprob: data.right_mprob, ev: data.right_ev };

                        data.target = choseLeft ? data.left_idx : data.right_idx;
                        data.monitored = Math.random() < chosen.mprob;
                        data.warning = data.monitored && Math.random() < 0.7; // 70% chance warning if monitored
                        data.reward = data.monitored ? chosen.penalty : chosen.reward;
                        data.correct = !data.monitored; // Success = not caught

                        // Did they choose the higher EV option?
                        data.chose_higher_ev = (choseLeft && data.left_ev >= data.right_ev) || (!choseLeft && data.right_ev >= data.left_ev);

                        totalScore += data.reward;
                    } else {
                        data.target = -1;
                        data.monitored = false;
                        data.warning = false;
                        data.reward = 0;
                        data.correct = false;
                        data.chose_higher_ev = false;
                    }
                    data.cumulative_score = totalScore;
                },
            });

            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    var last = jsPsych.data.get().last(1).values()[0];
                    if (last.timed_out) return '<div class="feedback-incorrect">Too slow!</div>';
                    if (last.monitored) {
                        return '<div class="feedback-incorrect">\u26A0 Caught! ' + last.reward + ' points</div>';
                    }
                    return '<div class="feedback-correct">\u2714 Success! +' + last.reward + ' points</div>';
                },
                choices: "NO_KEYS", trial_duration: CONFIG.feedback_duration, data: { trial_part: "feedback" },
            });
        })(allTrials[ti]);
    }

    timeline.push({ type: jsPsychCallFunction, async: true, func: function (done) {
        var trial_data = jsPsych.data.get().filter({ trial_part: "stimulus" }).values();
        fetch("/api/data/" + SESSION_ID + "/" + TASK_ID, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ trial_data: trial_data, metadata: { task_id: TASK_ID, session_id: SESSION_ID, total_time_ms: jsPsych.getTotalTime(), n_trials: trial_data.length } }) })
            .then(function (r) { done(); }).catch(function (e) { console.error(e); done(); });
    }});

    timeline.push({ type: jsPsychHtmlKeyboardResponse, stimulus: "<h2>Task Complete</h2><p>Final Score: " + totalScore + "</p><p>Your data has been submitted.</p>", choices: "NO_KEYS", trial_duration: 3000 });
    jsPsych.run(timeline);
})();
