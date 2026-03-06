(function () {
    var CONFIG = {
        n_trials: 100,
        n_practice: 10,
        valid_keys: ["f", "j"],
        response_deadline: 3000,
        fixation_duration: 500,
        feedback_duration: 1000,
        iti_min: 300,
        iti_max: 600,
        common_transition_prob: 0.70,
        drift_sd: 0.025,
        drift_min: 0.25,
        drift_max: 0.75,
        drift_start: 0.50,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "two_step";

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

    // --- Reward probability drift (Gaussian random walk) ---
    // Four stage-2 options: state A has options [0, 1], state B has options [2, 3]
    var rewardProbs = [CONFIG.drift_start, CONFIG.drift_start, CONFIG.drift_start, CONFIG.drift_start];

    function gaussianRandom() {
        var u1 = Math.random();
        var u2 = Math.random();
        return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
    }

    function driftRewardProbs() {
        for (var i = 0; i < rewardProbs.length; i++) {
            rewardProbs[i] += gaussianRandom() * CONFIG.drift_sd;
            if (rewardProbs[i] < CONFIG.drift_min) { rewardProbs[i] = CONFIG.drift_min; }
            if (rewardProbs[i] > CONFIG.drift_max) { rewardProbs[i] = CONFIG.drift_max; }
        }
    }

    // --- Stage display helpers ---
    function stage1HTML(trialLabel) {
        return '<div class="stage-label">' + trialLabel + '</div>' +
            '<div class="stage-label">Stage 1: Choose a spaceship</div>' +
            '<div class="stage-container">' +
            '<div>' +
            '<div class="stage-box stage1-left">&#9650;</div>' +
            '<div class="key-hint" style="text-align:center;color:#666">F</div>' +
            '</div>' +
            '<div>' +
            '<div class="stage-box stage1-right">&#9660;</div>' +
            '<div class="key-hint" style="text-align:center;color:#666">J</div>' +
            '</div>' +
            '</div>';
    }

    function stage2HTML(state, trialLabel) {
        var leftClass, rightClass, leftSymbol, rightSymbol, stateLabel;
        if (state === "A") {
            leftClass = "stage2a-left";
            rightClass = "stage2a-right";
            leftSymbol = "&#9733;";   // star
            rightSymbol = "&#9830;";  // diamond
            stateLabel = "Planet A (teal/green)";
        } else {
            leftClass = "stage2b-left";
            rightClass = "stage2b-right";
            leftSymbol = "&#9829;";   // heart
            rightSymbol = "&#9824;";  // spade
            stateLabel = "Planet B (orange/red)";
        }
        return '<div class="stage-label">' + trialLabel + '</div>' +
            '<div class="stage-label">Stage 2: ' + stateLabel + '</div>' +
            '<div class="stage-container">' +
            '<div>' +
            '<div class="stage-box ' + leftClass + '">' + leftSymbol + '</div>' +
            '<div class="key-hint" style="text-align:center;color:#666">F</div>' +
            '</div>' +
            '<div>' +
            '<div class="stage-box ' + rightClass + '">' + rightSymbol + '</div>' +
            '<div class="key-hint" style="text-align:center;color:#666">J</div>' +
            '</div>' +
            '</div>';
    }

    function feedbackHTML(rewarded) {
        if (rewarded) {
            return '<div class="reward-display reward-coin">&#9733; +1 point!</div>';
        } else {
            return '<div class="reward-display reward-none">&#10008; No reward</div>';
        }
    }

    // --- State tracking for "stayed" and previous trial info ---
    var previousStage1Choice = null;
    var previousRewarded = null;
    var previousTransition = null;
    var totalReward = 0;
    var trialCounter = 0;

    // --- Build a single two-step trial ---
    function buildTwoStepTrial(trialNum, totalTrials, isPractice) {
        var trialNodes = [];
        var trialLabel = isPractice ?
            "Practice " + (trialNum + 1) + " / " + totalTrials :
            "Trial " + (trialNum + 1) + " / " + totalTrials;

        // Variables to carry between stage 1 and stage 2 within this trial
        var trialState = {
            stage1_choice: null,
            stage1_rt: null,
            transition_type: null,
            stage2_state: null,
            stage2_choice: null,
            stage2_rt: null,
            rewarded: null,
            reward_amount: 0,
            timed_out_stage1: false,
            timed_out_stage2: false,
        };

        // Fixation
        trialNodes.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: '<div class="fixation">+</div>',
            choices: "NO_KEYS",
            trial_duration: CONFIG.fixation_duration,
            data: { trial_part: "fixation" },
        });

        // Stage 1: Choose between two options
        trialNodes.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: stage1HTML(trialLabel),
            choices: CONFIG.valid_keys,
            trial_duration: CONFIG.response_deadline,
            data: { trial_part: "stage1" },
            on_finish: function (data) {
                if (data.response === null) {
                    // Timed out: random stage1 choice
                    trialState.stage1_choice = Math.random() < 0.5 ? "left" : "right";
                    trialState.timed_out_stage1 = true;
                } else {
                    trialState.stage1_choice = data.response === "f" ? "left" : "right";
                }
                trialState.stage1_rt = data.rt;

                // Determine transition
                var isCommon = Math.random() < CONFIG.common_transition_prob;
                trialState.transition_type = isCommon ? "common" : "rare";

                if (trialState.stage1_choice === "left") {
                    trialState.stage2_state = isCommon ? "A" : "B";
                } else {
                    trialState.stage2_state = isCommon ? "B" : "A";
                }
            },
        });

        // Transition indicator (brief)
        trialNodes.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                var arrow = trialState.stage2_state === "A" ?
                    "&#8594; Planet A" : "&#8594; Planet B";
                return '<div class="transition-indicator">' + arrow + '</div>';
            },
            choices: "NO_KEYS",
            trial_duration: 400,
            data: { trial_part: "transition" },
        });

        // Stage 2: Choose between two options in the arrived-at state
        trialNodes.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                return stage2HTML(trialState.stage2_state, trialLabel);
            },
            choices: CONFIG.valid_keys,
            trial_duration: CONFIG.response_deadline,
            data: { trial_part: "stage2" },
            on_finish: function (data) {
                if (data.response === null) {
                    trialState.stage2_choice = Math.random() < 0.5 ? "left" : "right";
                    trialState.timed_out_stage2 = true;
                } else {
                    trialState.stage2_choice = data.response === "f" ? "left" : "right";
                }
                trialState.stage2_rt = data.rt;

                // Map stage2 state + choice to reward probability index
                // State A: left=index 0, right=index 1
                // State B: left=index 2, right=index 3
                var probIndex;
                if (trialState.stage2_state === "A") {
                    probIndex = trialState.stage2_choice === "left" ? 0 : 1;
                } else {
                    probIndex = trialState.stage2_choice === "left" ? 2 : 3;
                }

                trialState.rewarded = Math.random() < rewardProbs[probIndex];
                trialState.reward_amount = trialState.rewarded ? 1 : 0;
                totalReward += trialState.reward_amount;
            },
        });

        // Feedback
        trialNodes.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                return feedbackHTML(trialState.rewarded);
            },
            choices: "NO_KEYS",
            trial_duration: CONFIG.feedback_duration,
            data: { trial_part: "feedback" },
        });

        // Data recording node (call-function to write the combined trial record)
        if (!isPractice) {
            trialNodes.push({
                type: jsPsychCallFunction,
                func: function () {
                    trialCounter++;

                    // Compute stayed
                    var stayed = null;
                    var stayedNum = null;
                    if (previousStage1Choice !== null) {
                        stayed = trialState.stage1_choice === previousStage1Choice;
                        stayedNum = stayed ? 1 : 0;
                    }

                    // Previous trial info for interaction analysis
                    var prevRewardedStr = null;
                    var prevTransition = null;
                    if (previousRewarded !== null) {
                        prevRewardedStr = previousRewarded ? "rewarded" : "unrewarded";
                        prevTransition = previousTransition;
                    }

                    // Record the full trial data as a stimulus trial
                    jsPsych.data.get().push([{
                        trial_part: "stimulus",
                        trial_index: trialCounter,
                        stage1_choice: trialState.stage1_choice,
                        stage1_rt: trialState.stage1_rt,
                        transition_type: trialState.transition_type,
                        stage2_state: trialState.stage2_state,
                        stage2_choice: trialState.stage2_choice,
                        stage2_rt: trialState.stage2_rt,
                        rewarded: trialState.rewarded,
                        reward_amount: trialState.reward_amount,
                        stayed: stayed,
                        stayed_num: stayedNum,
                        previous_rewarded: previousRewarded,
                        previous_rewarded_str: prevRewardedStr,
                        previous_transition: prevTransition,
                        timed_out_stage1: trialState.timed_out_stage1,
                        timed_out_stage2: trialState.timed_out_stage2,
                        reward_probs: rewardProbs.slice(),
                        total_reward: totalReward,
                    }]);

                    // Update previous trial state for next trial
                    previousStage1Choice = trialState.stage1_choice;
                    previousRewarded = trialState.rewarded;
                    previousTransition = trialState.transition_type;

                    // Drift reward probabilities for next trial
                    driftRewardProbs();
                },
            });
        } else {
            // During practice, still drift and update previous choice tracking
            trialNodes.push({
                type: jsPsychCallFunction,
                func: function () {
                    previousStage1Choice = trialState.stage1_choice;
                    previousRewarded = trialState.rewarded;
                    previousTransition = trialState.transition_type;
                    driftRewardProbs();
                },
            });
        }

        // ITI
        trialNodes.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: "",
            choices: "NO_KEYS",
            trial_duration: function () {
                return CONFIG.iti_min +
                    Math.floor(Math.random() * (CONFIG.iti_max - CONFIG.iti_min));
            },
            data: { trial_part: "iti" },
        });

        return trialNodes;
    }

    // --- Build full timeline ---
    var timeline = [];

    // Welcome
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Two-Step Task</h1>" +
            "<p>Welcome to the two-step decision task.</p>" +
            "<p>Press any key to begin.</p>",
    });

    // Instructions
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>In this task, each trial has <strong>two stages</strong>.</p>" +
            "<p><strong>Stage 1:</strong> Choose one of two spaceships.</p>" +
            "<p>Your spaceship will fly to one of two planets.</p>" +
            "<p><strong>Stage 2:</strong> On the planet, choose one of two aliens to ask for treasure.</p>",

            "<h2>Transitions</h2>" +
            '<div class="stage-container">' +
            '<div class="stage-box stage1-left" style="width:80px;height:80px;font-size:24px">&#9650;</div>' +
            '<div style="font-size:24px;color:#555">&#8594; usually &#8594;</div>' +
            '<div class="stage-box stage2a-left" style="width:80px;height:80px;font-size:24px">A</div>' +
            '</div>' +
            '<div class="stage-container">' +
            '<div class="stage-box stage1-right" style="width:80px;height:80px;font-size:24px">&#9660;</div>' +
            '<div style="font-size:24px;color:#555">&#8594; usually &#8594;</div>' +
            '<div class="stage-box stage2b-left" style="width:80px;height:80px;font-size:24px">B</div>' +
            '</div>' +
            "<p>Each spaceship <strong>usually</strong> goes to one planet (70% of the time),</p>" +
            "<p>but sometimes goes to the other planet (30% of the time).</p>",

            "<h2>Rewards</h2>" +
            "<p>Each alien has a different chance of giving you treasure.</p>" +
            "<p>These chances <strong>slowly change</strong> over time.</p>" +
            "<p>Pay attention to which aliens are currently generous!</p>" +
            '<p><span style="font-size:36px;color:#ffc107">&#9733;</span> = +1 point &nbsp;&nbsp;&nbsp; ' +
            '<span style="font-size:36px;color:#b71c1c">&#10008;</span> = no reward</p>',

            "<h2>Controls</h2>" +
            "<p style='font-size:24px'><kbd>F</kbd> = <strong>Left option</strong></p>" +
            "<p style='font-size:24px'><kbd>J</kbd> = <strong>Right option</strong></p>" +
            "<p>Use the same keys for both stages.</p>" +
            "<p>Try to respond quickly. You have 3 seconds per choice.</p>" +
            "<p>We will start with 10 practice trials.</p>" +
            "<p>Click Next to begin practice.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    // --- Practice trials ---
    // Reset drift to starting values for practice
    rewardProbs = [CONFIG.drift_start, CONFIG.drift_start, CONFIG.drift_start, CONFIG.drift_start];
    previousStage1Choice = null;
    previousRewarded = null;
    previousTransition = null;

    for (var p = 0; p < CONFIG.n_practice; p++) {
        var practiceNodes = buildTwoStepTrial(p, CONFIG.n_practice, true);
        for (var pi = 0; pi < practiceNodes.length; pi++) {
            timeline.push(practiceNodes[pi]);
        }
    }

    // Transition to main experiment
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>End of Practice</h2>" +
            "<p>Great! You have completed the practice trials.</p>" +
            "<p>The main experiment has <strong>" + CONFIG.n_trials + " trials</strong>.</p>" +
            "<p>Remember:</p>" +
            "<ul style='text-align:left;display:inline-block'>" +
            "<li>Each spaceship usually goes to one planet (70%)</li>" +
            "<li>Alien reward chances change slowly over time</li>" +
            "<li>Try to earn as many points as possible</li>" +
            "</ul>" +
            "<p>Press any key to start.</p>",
    });

    // --- Reset state for main experiment ---
    // We push a call-function to reset state at runtime
    timeline.push({
        type: jsPsychCallFunction,
        func: function () {
            rewardProbs = [CONFIG.drift_start, CONFIG.drift_start, CONFIG.drift_start, CONFIG.drift_start];
            previousStage1Choice = null;
            previousRewarded = null;
            previousTransition = null;
            totalReward = 0;
            trialCounter = 0;
        },
    });

    // --- Main trials ---
    for (var t = 0; t < CONFIG.n_trials; t++) {
        var trialNodes = buildTwoStepTrial(t, CONFIG.n_trials, false);
        for (var ti = 0; ti < trialNodes.length; ti++) {
            timeline.push(trialNodes[ti]);
        }

        // Periodic break every 25 trials
        if ((t + 1) % 25 === 0 && t < CONFIG.n_trials - 1) {
            (function (trialNum) {
                timeline.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: function () {
                        return "<h2>Break</h2>" +
                            "<p>You have completed " + (trialNum + 1) + " of " + CONFIG.n_trials + " trials.</p>" +
                            "<p>Total points: " + totalReward + "</p>" +
                            "<p>Take a short break if needed.</p>" +
                            "<p>Press any key to continue.</p>";
                    },
                });
            })(t);
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

    // Completion screen
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus: function () {
            return "<h2>Task Complete</h2>" +
                "<p>Thank you for completing the Two-Step Task.</p>" +
                "<p>Total points earned: " + totalReward + "</p>" +
                "<p>Your data has been submitted.</p>";
        },
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
