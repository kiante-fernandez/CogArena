(function () {
    var CONFIG = {
        n_balloons: 30,
        n_practice: 3,
        max_pumps: 128,
        pop_threshold_max: 64,
        valid_keys: ["f", "j"],
        pump_value: 0.05,
        response_deadline: 5000,
        feedback_duration: 1500,
        iti_min: 500,
        iti_max: 800,
        balloon_start_size: 40,
        balloon_grow_per_pump: 3,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "bart";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.n_balloons = _nto;
    }

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    // Generate random pop thresholds for each balloon
    function generatePopThresholds(n) {
        var thresholds = [];
        for (var i = 0; i < n; i++) {
            // Random integer from 1 to pop_threshold_max (inclusive)
            thresholds.push(Math.floor(Math.random() * CONFIG.pop_threshold_max) + 1);
        }
        return thresholds;
    }

    var practiceThresholds = generatePopThresholds(CONFIG.n_practice);
    var mainThresholds = generatePopThresholds(CONFIG.n_balloons);

    var totalEarnings = 0;
    var timeline = [];

    // Balloon colors for visual variety
    var balloonColors = [
        "radial-gradient(circle at 35% 35%, #ff6b6b, #e63946)",
        "radial-gradient(circle at 35% 35%, #6bb5ff, #3978e6)",
        "radial-gradient(circle at 35% 35%, #6bff8e, #39e65c)",
        "radial-gradient(circle at 35% 35%, #ffdb6b, #e6b439)",
        "radial-gradient(circle at 35% 35%, #d06bff, #9b39e6)",
    ];

    function getBalloonColor(balloonIndex) {
        return balloonColors[balloonIndex % balloonColors.length];
    }

    function formatMoney(val) {
        return "$" + val.toFixed(2);
    }

    // Welcome
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Balloon Analog Risk Task</h1>" +
            "<p>Welcome to the balloon pumping task.</p>" +
            "<p>Press any key to begin.</p>",
    });

    // Instructions
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>In this task, you will see a series of balloons on the screen.</p>" +
            "<p>You can pump each balloon to earn money, or cash out to collect your earnings.</p>" +
            "<p>Each pump adds <strong>" + formatMoney(CONFIG.pump_value) + "</strong> to the balloon's value.</p>",

            "<h2>The Risk</h2>" +
            "<p>Each balloon has a hidden limit. If you pump it too many times, " +
            "the balloon will <strong>POP</strong> and you lose all earnings for that balloon.</p>" +
            "<p>The pop point varies for each balloon, so there is always some risk.</p>" +
            "<p>You must decide: <strong>pump for more money</strong> or <strong>cash out to keep your earnings</strong>?</p>",

            "<h2>Controls</h2>" +
            "<p style='font-size:24px'><kbd>F</kbd> = <strong>Pump</strong> (inflate balloon)</p>" +
            "<p style='font-size:24px'><kbd>J</kbd> = <strong>Cash Out</strong> (collect earnings)</p>" +
            "<p>You have 5 seconds to decide on each pump.</p>" +
            "<p>We will start with 3 practice balloons, then 30 main balloons.</p>" +
            "<p>Press Next to begin the practice.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    // Build a single balloon sequence
    function buildBalloonTimeline(balloonIndex, popThreshold, isPractice, balloonLabel) {
        var balloonTrials = [];
        var pumpCount = 0;
        var pumpRTs = [];
        var balloonDone = false;
        var balloonPopped = false;
        var balloonColor = getBalloonColor(balloonIndex);

        // ITI before balloon
        var itiDuration = CONFIG.iti_min + Math.random() * (CONFIG.iti_max - CONFIG.iti_min);
        balloonTrials.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: '<div class="fixation">+</div>',
            choices: "NO_KEYS",
            trial_duration: itiDuration,
        });

        // We build a loop using jsPsych timeline variables with a loop_function
        // Each iteration is one pump decision
        var pumpNode = {
            timeline: [
                {
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: function () {
                        var size = CONFIG.balloon_start_size + pumpCount * CONFIG.balloon_grow_per_pump;
                        var currentValue = pumpCount * CONFIG.pump_value;
                        var prefix = isPractice ? "Practice " : "";
                        return '<div class="bart-container">' +
                            '<div class="bart-header">' + prefix + 'Balloon ' + balloonLabel +
                            (isPractice ? "" : " | Total Earnings: " + formatMoney(totalEarnings)) + '</div>' +
                            '<div class="balloon-wrapper">' +
                            '<div class="balloon" style="width:' + size + 'px;height:' + size +
                            'px;background:' + balloonColor + ';">' +
                            '<span class="balloon-value">' + formatMoney(currentValue) + '</span>' +
                            '<div class="balloon-string"></div>' +
                            '</div>' +
                            '</div>' +
                            '<div class="bart-info">Pumps: ' + pumpCount + '</div>' +
                            '<div class="bart-controls"><kbd>F</kbd> Pump &nbsp;&nbsp;&nbsp; <kbd>J</kbd> Cash Out</div>' +
                            '</div>';
                    },
                    choices: CONFIG.valid_keys,
                    trial_duration: CONFIG.response_deadline,
                    data: {
                        trial_part: "pump_decision",
                        balloon_index: balloonIndex,
                        is_practice: isPractice,
                    },
                    on_finish: function (data) {
                        data.pump_number = pumpCount + 1;
                        data.pop_threshold = popThreshold;

                        if (data.response === null) {
                            // Timed out — treat as cash out
                            balloonDone = true;
                            data.action = "timeout_cashout";
                        } else if (data.response === "j") {
                            // Cash out
                            balloonDone = true;
                            data.action = "cashout";
                        } else if (data.response === "f") {
                            // Pump
                            pumpCount++;
                            pumpRTs.push(data.rt);
                            data.action = "pump";

                            // Check if popped
                            if (pumpCount >= popThreshold) {
                                balloonPopped = true;
                                balloonDone = true;
                                data.action = "pump_pop";
                            }
                        }
                    },
                },
            ],
            loop_function: function () {
                return !balloonDone;
            },
        };

        balloonTrials.push(pumpNode);

        // Feedback trial
        balloonTrials.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                if (balloonPopped) {
                    return '<div class="bart-container">' +
                        '<div class="pop-display">POP!</div>' +
                        '<div class="bart-info" style="color:#e63946;">You lost ' +
                        formatMoney(pumpCount * CONFIG.pump_value) + ' for this balloon.</div>' +
                        '<div class="bart-earnings">Total Earnings: ' + formatMoney(totalEarnings) + '</div>' +
                        '</div>';
                } else {
                    var earned = pumpCount * CONFIG.pump_value;
                    return '<div class="bart-container">' +
                        '<div class="cashout-display">Cashed out! +' + formatMoney(earned) + '</div>' +
                        '<div class="bart-earnings">Total Earnings: ' + formatMoney(totalEarnings) + '</div>' +
                        '</div>';
                }
            },
            choices: "NO_KEYS",
            trial_duration: CONFIG.feedback_duration,
            data: { trial_part: "feedback" },
            on_start: function () {
                // Update total earnings before feedback displays
                if (!balloonPopped) {
                    var earned = pumpCount * CONFIG.pump_value;
                    if (!isPractice) {
                        totalEarnings += earned;
                    }
                }
            },
        });

        // Summary trial for data recording (only for main balloons)
        if (!isPractice) {
            balloonTrials.push({
                type: jsPsychCallFunction,
                func: function () {
                    // This trial records the balloon summary
                },
                data: {
                    trial_part: "stimulus",
                    balloon_index: balloonIndex,
                },
                on_finish: function (data) {
                    var bEarnings = balloonPopped ? 0 : pumpCount * CONFIG.pump_value;
                    var meanRT = pumpRTs.length > 0
                        ? Math.round(pumpRTs.reduce(function (a, b) { return a + b; }, 0) / pumpRTs.length)
                        : null;

                    data.trial_index = balloonIndex + 1;
                    data.balloon_number = balloonIndex + 1;
                    data.n_pumps = pumpCount;
                    data.popped = balloonPopped;
                    data.cashed_out = !balloonPopped;
                    data.balloon_earnings = parseFloat(bEarnings.toFixed(2));
                    data.total_earnings = parseFloat(totalEarnings.toFixed(2));
                    data.pop_threshold = popThreshold;
                    data.adjusted_pumps = balloonPopped ? null : pumpCount;
                    data.mean_pump_rt = meanRT;

                    // Compute previous_popped by checking prior balloon summaries
                    var priorSummaries = jsPsych.data.get().filter({ trial_part: "stimulus" }).values();
                    // The current trial is already in the data, so previous is second-to-last
                    if (priorSummaries.length >= 2) {
                        var prevBalloon = priorSummaries[priorSummaries.length - 2];
                        data.previous_popped = prevBalloon.popped;
                    } else {
                        data.previous_popped = false;
                    }

                    // Derived fields for scoring signatures
                    data.above_floor_pumps = (data.adjusted_pumps !== null && data.adjusted_pumps > 5);
                    data.high_pumps = data.n_pumps > 15;
                },
            });
        }

        return balloonTrials;
    }

    // Practice balloons
    for (var p = 0; p < CONFIG.n_practice; p++) {
        var practiceTrials = buildBalloonTimeline(p, practiceThresholds[p], true, (p + 1) + "/" + CONFIG.n_practice);
        practiceTrials.forEach(function (t) { timeline.push(t); });
    }

    // End of practice
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>End of Practice</h2>" +
            "<p>The main experiment will now begin.</p>" +
            "<p>You will inflate <strong>" + CONFIG.n_balloons + "</strong> balloons.</p>" +
            "<p>Your goal is to maximize your total earnings.</p>" +
            "<p>Press any key to start.</p>",
    });

    // Main balloons
    for (var b = 0; b < CONFIG.n_balloons; b++) {
        var bTrials = buildBalloonTimeline(b, mainThresholds[b], false, (b + 1) + "/" + CONFIG.n_balloons);
        bTrials.forEach(function (t) { timeline.push(t); });
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

    // Completion screen
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus: function () {
            return "<h2>Task Complete</h2>" +
                "<p>Thank you for completing the Balloon Analog Risk Task.</p>" +
                "<p>Final earnings: <strong>" + formatMoney(totalEarnings) + "</strong></p>" +
                "<p>Your data has been submitted.</p>";
        },
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
