(function () {
    var CONFIG = {
        n_trials: 100,
        n_practice: 10,
        initial_mean: 50,
        drift_sd: 4,
        reward_sd: 8,
        mean_min: 10,
        mean_max: 90,
        valid_keys: ["f", "j"],
        response_deadline: 3000,
        fixation_duration: 500,
        feedback_duration: 1000,
        iti_min: 300,
        iti_max: 500,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "restless_bandit";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.n_trials = _nto;
    }

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    // --- Gaussian random number generator (Box-Muller) ---
    function randGaussian() {
        var u1 = Math.random();
        var u2 = Math.random();
        return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
    }

    // --- Bounded drift step for arm means ---
    function driftMean(currentMean) {
        var newMean = currentMean + randGaussian() * CONFIG.drift_sd;
        return Math.max(CONFIG.mean_min, Math.min(CONFIG.mean_max, newMean));
    }

    // --- Sample reward from arm ---
    function sampleReward(mean) {
        var reward = Math.round(mean + randGaussian() * CONFIG.reward_sd);
        return Math.max(0, Math.min(100, reward));
    }

    // --- Arm state ---
    var armMeans = {
        left: CONFIG.initial_mean,
        right: CONFIG.initial_mean,
    };

    var totalScore = 0;
    var timeline = [];

    // ===== Welcome =====
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Restless Bandit Task</h1>" +
            "<p>Welcome to the Restless Bandit (Drifting Rewards) task.</p>" +
            "<p>Press any key to begin.</p>",
    });

    // ===== Instructions =====
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>In this task, you will choose between two slot machines on each trial.</p>" +
            "<p>Each machine pays out a number of points that varies from trial to trial.</p>" +
            "<p>Your goal is to earn as many points as possible over the experiment.</p>",

            "<h2>Drifting Rewards</h2>" +
            "<p>The average payout of each machine <strong>changes slowly over time</strong>.</p>" +
            "<p>A machine that is good now may become worse later, and vice versa.</p>" +
            "<p>You need to keep track of how the machines are performing and switch when needed.</p>",

            "<h2>Response Keys</h2>" +
            "<p style='font-size:28px'><kbd>F</kbd> = <strong>Left Machine</strong></p>" +
            "<p style='font-size:28px'><kbd>J</kbd> = <strong>Right Machine</strong></p>" +
            "<p>You have 3 seconds to respond on each trial.</p>" +
            "<p>After choosing, you will see how many points you earned.</p>" +
            "<p>Press Next to start with some practice trials.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    // ===== Build trial timeline =====
    function buildTrials(nTrials, isPractice) {
        var trials = [];
        var trialCounter = 0;
        var prevReward = null;
        var prevChosenArm = null;

        // For practice, use separate arm means so main task starts fresh
        var localArmMeans;
        if (isPractice) {
            localArmMeans = { left: CONFIG.initial_mean, right: CONFIG.initial_mean };
        } else {
            localArmMeans = armMeans;
        }

        for (var t = 0; t < nTrials; t++) {
            (function (trialNum) {
                // Fixation
                trials.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: '<div class="fixation">+</div>',
                    choices: "NO_KEYS",
                    trial_duration: CONFIG.fixation_duration,
                    data: { trial_part: "fixation" },
                });

                // Stimulus
                trials.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: function () {
                        var header = isPractice
                            ? "Practice Trial " + (trialNum + 1) + " of " + nTrials
                            : "Trial " + (trialNum + 1) + " of " + nTrials;
                        return '<div class="game-header">' + header + "</div>" +
                            '<div class="slot-container">' +
                            '<div class="slot-machine">' +
                            '<div class="slot-label">Left</div>' +
                            '<div class="slot-window">?</div>' +
                            '<div class="key-hint">F</div>' +
                            "</div>" +
                            '<div class="slot-machine">' +
                            '<div class="slot-label">Right</div>' +
                            '<div class="slot-window">?</div>' +
                            '<div class="key-hint">J</div>' +
                            "</div>" +
                            "</div>" +
                            '<div class="score-display">Total Score: ' + totalScore + "</div>";
                    },
                    choices: CONFIG.valid_keys,
                    trial_duration: CONFIG.response_deadline,
                    data: {
                        trial_part: "stimulus",
                        is_practice: isPractice,
                    },
                    on_finish: function (data) {
                        trialCounter++;
                        data.trial_index = trialCounter;
                        data.timed_out = data.response === null;

                        // Current hidden means (before drift for this trial's reward)
                        data.arm_left_mean = Math.round(localArmMeans.left * 100) / 100;
                        data.arm_right_mean = Math.round(localArmMeans.right * 100) / 100;

                        // Determine optimal arm
                        if (localArmMeans.left >= localArmMeans.right) {
                            data.optimal_arm = "left";
                        } else {
                            data.optimal_arm = "right";
                        }

                        // Map response
                        if (data.response === "f") {
                            data.chosen_arm = "left";
                        } else if (data.response === "j") {
                            data.chosen_arm = "right";
                        } else {
                            data.chosen_arm = null;
                        }

                        // Chose optimal?
                        data.chose_optimal = data.chosen_arm === data.optimal_arm;

                        // Sample reward
                        if (data.chosen_arm) {
                            var chosenMean = localArmMeans[data.chosen_arm];
                            data.reward = sampleReward(chosenMean);
                            totalScore += data.reward;
                        } else {
                            data.reward = 0;
                        }
                        data.total_score = totalScore;

                        // Previous trial info
                        data.previous_reward = prevReward;
                        data.previous_chosen_arm = prevChosenArm;

                        // Stayed (chose same arm as previous trial)
                        if (prevChosenArm !== null && data.chosen_arm !== null) {
                            data.stayed = data.chosen_arm === prevChosenArm;
                            data.stayed_num = data.stayed ? 1 : 0;
                        } else {
                            data.stayed = null;
                            data.stayed_num = null;
                        }

                        // Previous reward above median (>50)
                        if (prevReward !== null) {
                            data.previous_reward_above_median = prevReward > 50;
                        } else {
                            data.previous_reward_above_median = null;
                        }

                        // Update previous trial tracking
                        prevReward = data.reward;
                        prevChosenArm = data.chosen_arm;

                        // Drift arm means for next trial
                        localArmMeans.left = driftMean(localArmMeans.left);
                        localArmMeans.right = driftMean(localArmMeans.right);
                    },
                });

                // Feedback
                trials.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: function () {
                        var last = jsPsych.data.get().last(1).values()[0];
                        if (last.timed_out) {
                            return '<div class="reward-display timeout">Too slow! +0 points</div>' +
                                '<div class="score-display">Total Score: ' + totalScore + "</div>";
                        }
                        return '<div class="reward-display">+' + last.reward + " points</div>" +
                            '<div class="score-display">Total Score: ' + totalScore + "</div>";
                    },
                    choices: "NO_KEYS",
                    trial_duration: CONFIG.feedback_duration,
                    data: { trial_part: "feedback" },
                });

                // ITI
                trials.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: "",
                    choices: "NO_KEYS",
                    trial_duration: function () {
                        return CONFIG.iti_min +
                            Math.floor(Math.random() * (CONFIG.iti_max - CONFIG.iti_min));
                    },
                    data: { trial_part: "iti" },
                });
            })(t);
        }

        return trials;
    }

    // ===== Practice trials =====
    var practiceTrials = buildTrials(CONFIG.n_practice, true);
    practiceTrials.forEach(function (t) { timeline.push(t); });

    // Transition to main task
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>End of Practice</h2>" +
            "<p>The main experiment will now begin.</p>" +
            "<p>There are " + CONFIG.n_trials + " trials total.</p>" +
            "<p>Remember: the machines' payouts drift over time. Keep tracking which is better!</p>" +
            "<p>Press any key to start.</p>",
    });

    // Reset score and arm means for the main task
    timeline.push({
        type: jsPsychCallFunction,
        func: function () {
            totalScore = 0;
            armMeans.left = CONFIG.initial_mean;
            armMeans.right = CONFIG.initial_mean;
        },
    });

    // ===== Main trials =====
    var mainTrials = buildTrials(CONFIG.n_trials, false);
    mainTrials.forEach(function (t) { timeline.push(t); });

    // ===== Data Submission =====
    timeline.push({
        type: jsPsychCallFunction,
        async: true,
        func: function (done) {
            var trial_data = jsPsych.data
                .get()
                .filter({ trial_part: "stimulus", is_practice: false })
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

    // ===== Completion =====
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus: function () {
            return "<h2>Task Complete</h2>" +
                "<p>Thank you for completing the Restless Bandit task.</p>" +
                "<p>Total points earned: " + totalScore + "</p>" +
                "<p>Your data has been submitted.</p>";
        },
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
