(function () {
    var CONFIG = {
        n_trials: 120,
        reward_prob: 0.80,
        reversal_min: 15,
        reversal_max: 25,
        valid_keys: ["f", "j"],
        response_deadline: 3000,
        fixation_duration: 500,
        feedback_duration: 1000,
        iti_min: 300,
        iti_max: 600,
    };

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "reversal_learning";

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    // Stimuli: blue square (left) vs orange circle (right)
    var STIM_LEFT = '<svg width="120" height="120"><rect x="10" y="10" width="100" height="100" rx="10" fill="#2563eb"/></svg>';
    var STIM_RIGHT = '<svg width="120" height="120"><circle cx="60" cy="60" r="50" fill="#ea580c"/></svg>';

    // Determine reversal schedule
    function generateReversalSchedule() {
        var schedule = [];
        var trialsSoFar = 0;
        var correctStim = "left"; // Start: left is correct

        while (trialsSoFar < CONFIG.n_trials) {
            var phaseLen = CONFIG.reversal_min +
                Math.floor(Math.random() * (CONFIG.reversal_max - CONFIG.reversal_min + 1));
            phaseLen = Math.min(phaseLen, CONFIG.n_trials - trialsSoFar);

            for (var i = 0; i < phaseLen; i++) {
                schedule.push({
                    correct_stimulus: correctStim,
                    trials_since_reversal: i,
                    reversal_count: schedule.length > 0 ?
                        schedule[schedule.length - 1].reversal_count + (i === 0 && schedule.length > 0 ? 1 : 0) :
                        0,
                });
            }

            trialsSoFar += phaseLen;
            correctStim = correctStim === "left" ? "right" : "left";
        }

        // Fix reversal counts
        var revCount = 0;
        for (var i = 0; i < schedule.length; i++) {
            if (i > 0 && schedule[i].trials_since_reversal === 0) {
                revCount++;
            }
            schedule[i].reversal_count = revCount;
        }

        return schedule;
    }

    var reversalSchedule = generateReversalSchedule();
    var timeline = [];

    // Instructions
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Reversal Learning Task</h2>" +
            "<p>In this task, you will see two shapes on each trial:</p>" +
            '<div class="reversal-stimulus">' +
            '<div>' + STIM_LEFT + '<p style="text-align:center;margin-top:8px">Blue Square</p></div>' +
            '<div>' + STIM_RIGHT + '<p style="text-align:center;margin-top:8px">Orange Circle</p></div>' +
            '</div>' +
            "<p>One shape is the 'correct' choice and will usually give you a reward.</p>" +
            "<p>The other shape will usually give no reward.</p>",

            "<h2>The Catch</h2>" +
            "<p>The correct shape will <strong>change</strong> during the task!</p>" +
            "<p>When you notice rewards shifting, adapt your choices accordingly.</p>" +
            "<p>Note: Even the correct shape doesn't reward you every time (about 80% of the time).</p>",

            "<h2>Controls</h2>" +
            "<p>Press <kbd>F</kbd> to choose the <strong>left shape</strong> (Blue Square)</p>" +
            "<p>Press <kbd>J</kbd> to choose the <strong>right shape</strong> (Orange Circle)</p>" +
            "<p>Try to earn as many rewards as possible.</p>" +
            "<p>Click Next to begin.</p>"
        ],
        show_clickable_nav: true,
    });

    var trialCounter = 0;
    var totalReward = 0;

    for (var t = 0; t < CONFIG.n_trials; t++) {
        (function (trialNum, scheduleInfo) {
            // Fixation
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: '<div class="fixation">+</div>',
                choices: "NO_KEYS",
                trial_duration: CONFIG.fixation_duration,
            });

            // Stimulus
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus:
                    '<div class="reversal-stimulus">' +
                    '<div class="reversal-shape">' + STIM_LEFT + '</div>' +
                    '<div class="reversal-shape">' + STIM_RIGHT + '</div>' +
                    '</div>' +
                    '<p style="text-align:center;color:#999;font-size:14px">' +
                    '<kbd>F</kbd> = Left &nbsp;&nbsp;&nbsp; <kbd>J</kbd> = Right</p>',
                choices: CONFIG.valid_keys,
                trial_duration: CONFIG.response_deadline,
                data: {
                    trial_part: "stimulus",
                    correct_stimulus: scheduleInfo.correct_stimulus,
                    trials_since_reversal: scheduleInfo.trials_since_reversal,
                    reversal_count: scheduleInfo.reversal_count,
                },
                on_finish: function (data) {
                    trialCounter++;
                    data.trial_index = trialCounter;
                    data.timed_out = data.response === null;

                    // Map response to choice
                    if (data.response === "f") {
                        data.stimulus_chosen = "left";
                    } else if (data.response === "j") {
                        data.stimulus_chosen = "right";
                    } else {
                        data.stimulus_chosen = null;
                    }

                    // Determine if choice was correct (chose the currently rewarded stimulus)
                    data.correct = data.stimulus_chosen === data.correct_stimulus;

                    // Probabilistic reward: 80% for correct, 20% for incorrect
                    if (data.correct) {
                        data.rewarded = Math.random() < CONFIG.reward_prob;
                    } else {
                        data.rewarded = Math.random() < (1 - CONFIG.reward_prob);
                    }

                    data.reward_value = data.rewarded ? 1 : 0;
                    totalReward += data.reward_value;
                    data.total_reward = totalReward;

                    // Phase labeling
                    if (data.trials_since_reversal < 5) {
                        data.phase = "post_reversal";
                    } else {
                        data.phase = "pre_reversal";
                    }

                    // Perseveration: after reversal, still choosing old stimulus
                    if (data.trials_since_reversal < 5 && !data.correct) {
                        data.perseveration = true;
                    } else {
                        data.perseveration = false;
                    }
                },
            });

            // Feedback
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    var last = jsPsych.data.get().last(1).values()[0];
                    if (last.timed_out) {
                        return '<div class="feedback" style="color:#999">Too slow! No reward.</div>';
                    }
                    if (last.rewarded) {
                        return '<div class="feedback" style="color:green">+1 Reward!</div>';
                    } else {
                        return '<div class="feedback" style="color:red">No reward.</div>';
                    }
                },
                choices: "NO_KEYS",
                trial_duration: CONFIG.feedback_duration,
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
        })(t, reversalSchedule[t]);

        // Periodic break
        if ((t + 1) % 40 === 0 && t < CONFIG.n_trials - 1) {
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    return "<h2>Break</h2>" +
                        "<p>You've completed " + (t + 1) + " of " + CONFIG.n_trials + " trials.</p>" +
                        "<p>Total rewards: " + totalReward + "</p>" +
                        "<p>Press any key to continue.</p>";
                },
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

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus: function () {
            return "<h2>Task Complete</h2>" +
                "<p>Thank you for completing the Reversal Learning task.</p>" +
                "<p>Total rewards earned: " + totalReward + "</p>" +
                "<p>Your data has been submitted.</p>";
        },
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
