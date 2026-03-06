(function () {
    var CONFIG = {
        n_trials: 100,
        n_blocks: 5,
        trials_per_block: 20,
        n_practice: 10,
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
    var TASK_ID = "probabilistic_classification";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.n_trials = _nto;
        CONFIG.n_blocks = Math.max(1, Math.ceil(_nto / CONFIG.trials_per_block));
    }

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    // Cue predictive validities: P(sun | cue present)
    // Cue 1: strong sun predictor, Cue 4: strong rain predictor
    var CUE_PROBS = [0.80, 0.60, 0.40, 0.20];

    // Card display labels and colors
    var CARD_LABELS = ["1", "2", "3", "4"];

    // Generate a cue pattern: 1-3 cues present per trial
    function generateCuePattern() {
        // Decide how many cues are present (1, 2, or 3 with equal probability)
        var nPresent = 1 + Math.floor(Math.random() * 3); // 1, 2, or 3

        // Create array of cue indices, shuffle, pick first nPresent
        var indices = [0, 1, 2, 3];
        for (var i = indices.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var temp = indices[i];
            indices[i] = indices[j];
            indices[j] = temp;
        }

        var present = [false, false, false, false];
        for (var i = 0; i < nPresent; i++) {
            present[indices[i]] = true;
        }

        return present;
    }

    // Determine outcome probabilistically using additive log-odds model
    // Each present cue contributes its log-odds toward sun
    // Base rate is 50/50 (log-odds = 0)
    function determineOutcome(cuePattern) {
        var logOdds = 0;
        for (var i = 0; i < 4; i++) {
            if (cuePattern[i]) {
                // Convert P(sun|cue) to log-odds contribution
                var p = CUE_PROBS[i];
                logOdds += Math.log(p / (1 - p));
            }
        }
        // Convert combined log-odds back to probability
        var pSun = 1 / (1 + Math.exp(-logOdds));

        // Determine actual outcome probabilistically
        return Math.random() < pSun ? "sun" : "rain";
    }

    // Determine optimal response based on expected probability
    function getOptimalResponse(cuePattern) {
        var logOdds = 0;
        for (var i = 0; i < 4; i++) {
            if (cuePattern[i]) {
                var p = CUE_PROBS[i];
                logOdds += Math.log(p / (1 - p));
            }
        }
        var pSun = 1 / (1 + Math.exp(-logOdds));
        return pSun >= 0.5 ? "sun" : "rain";
    }

    // Build card display HTML
    function buildCardHTML(cuePattern) {
        var html = '<div class="wpt-cards">';
        for (var i = 0; i < 4; i++) {
            var presentClass = cuePattern[i] ? "wpt-card-present" : "wpt-card-absent";
            html += '<div>';
            html += '<div class="wpt-card wpt-card-' + (i + 1) + ' ' + presentClass + '">';
            html += CARD_LABELS[i];
            html += '</div>';
            html += '<div class="wpt-label">' + (cuePattern[i] ? "Present" : "Absent") + '</div>';
            html += '</div>';
        }
        html += '</div>';
        html += '<div class="wpt-prompt">' +
            '<kbd>F</kbd> = Sun &nbsp;&nbsp;&nbsp; <kbd>J</kbd> = Rain</div>';
        return html;
    }

    // Pre-generate all trial cue patterns
    var practicePatterns = [];
    for (var i = 0; i < CONFIG.n_practice; i++) {
        practicePatterns.push(generateCuePattern());
    }

    var mainPatterns = [];
    for (var i = 0; i < CONFIG.n_trials; i++) {
        mainPatterns.push(generateCuePattern());
    }

    var timeline = [];

    // Welcome
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Weather Prediction Task</h2>" +
            "<p>In this task, you are a weather forecaster.</p>" +
            "<p>On each trial, you will see a combination of cards.</p>" +
            "<p>Based on the cards shown, you must predict the weather: <strong>Sun</strong> or <strong>Rain</strong>.</p>",

            "<h2>The Cards</h2>" +
            '<div class="wpt-cards">' +
            '<div><div class="wpt-card wpt-card-1 wpt-card-present">1</div><div class="wpt-label">Card 1</div></div>' +
            '<div><div class="wpt-card wpt-card-2 wpt-card-present">2</div><div class="wpt-label">Card 2</div></div>' +
            '<div><div class="wpt-card wpt-card-3 wpt-card-present">3</div><div class="wpt-label">Card 3</div></div>' +
            '<div><div class="wpt-card wpt-card-4 wpt-card-present">4</div><div class="wpt-label">Card 4</div></div>' +
            '</div>' +
            "<p>On each trial, 1 to 3 of these cards will be present (highlighted).</p>" +
            "<p>The remaining cards will be dimmed.</p>" +
            "<p>Each card provides a clue about the weather, but the relationship is <strong>probabilistic</strong> " +
            "- the same cards won't always lead to the same outcome.</p>",

            "<h2>Your Task</h2>" +
            "<p>Press <kbd>F</kbd> to predict <strong>Sun</strong></p>" +
            "<p>Press <kbd>J</kbd> to predict <strong>Rain</strong></p>" +
            "<p>After each prediction, you will see the actual outcome and whether you were correct.</p>" +
            "<p>Try to learn which card combinations predict sun and which predict rain.</p>" +
            "<p>We'll start with some practice trials.</p>" +
            "<p>Click Next to begin practice.</p>"
        ],
        show_clickable_nav: true,
    });

    // Practice round header
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Practice Round</h2>" +
            "<p>Let's practice with " + CONFIG.n_practice + " trials.</p>" +
            "<p>You'll receive feedback after each prediction.</p>" +
            "<p>Press any key to start.</p>",
    });

    // Practice trials
    for (var p = 0; p < CONFIG.n_practice; p++) {
        (function (practiceNum, cuePattern) {
            var actualOutcome = determineOutcome(cuePattern);
            var optimalResp = getOptimalResponse(cuePattern);

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
                stimulus: buildCardHTML(cuePattern),
                choices: CONFIG.valid_keys,
                trial_duration: CONFIG.response_deadline,
                data: {
                    trial_part: "practice",
                    cue1_present: cuePattern[0],
                    cue2_present: cuePattern[1],
                    cue3_present: cuePattern[2],
                    cue4_present: cuePattern[3],
                    actual_outcome: actualOutcome,
                    optimal_response: optimalResp,
                },
                on_finish: function (data) {
                    data.timed_out = data.response === null;

                    if (data.response === "f") {
                        data.player_response = "sun";
                    } else if (data.response === "j") {
                        data.player_response = "rain";
                    } else {
                        data.player_response = null;
                    }

                    data.correct = data.player_response === data.actual_outcome;
                },
            });

            // Feedback
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    var last = jsPsych.data.get().last(1).values()[0];
                    if (last.timed_out) {
                        return '<div class="feedback" style="color:#999">Too slow! The weather was ' +
                            (last.actual_outcome === "sun" ? "Sun &#9728;&#65039;" : "Rain &#127783;&#65039;") + '</div>';
                    }
                    if (last.correct) {
                        return '<div class="feedback" style="color:green">Correct! It was ' +
                            (last.actual_outcome === "sun" ? "Sun &#9728;&#65039;" : "Rain &#127783;&#65039;") + '</div>';
                    } else {
                        return '<div class="feedback" style="color:red">Incorrect. It was ' +
                            (last.actual_outcome === "sun" ? "Sun &#9728;&#65039;" : "Rain &#127783;&#65039;") + '</div>';
                    }
                },
                choices: "NO_KEYS",
                trial_duration: CONFIG.feedback_duration,
            });
        })(p, practicePatterns[p]);
    }

    // Transition to main experiment
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Main Experiment</h2>" +
            "<p>Practice is over. The main task will now begin.</p>" +
            "<p>There are " + CONFIG.n_trials + " trials in " + CONFIG.n_blocks + " blocks.</p>" +
            "<p>Remember: <kbd>F</kbd> = Sun, <kbd>J</kbd> = Rain</p>" +
            "<p>Press any key to start.</p>",
    });

    // Main trials
    var trialCounter = 0;
    var totalCorrect = 0;

    for (var t = 0; t < CONFIG.n_trials; t++) {
        (function (trialNum, cuePattern) {
            var blockNum = Math.floor(trialNum / CONFIG.trials_per_block) + 1;
            var actualOutcome = determineOutcome(cuePattern);
            var optimalResp = getOptimalResponse(cuePattern);
            var nPresent = 0;
            for (var c = 0; c < 4; c++) {
                if (cuePattern[c]) nPresent++;
            }
            var strongCuePresent = cuePattern[0] || cuePattern[3];

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
                stimulus: buildCardHTML(cuePattern),
                choices: CONFIG.valid_keys,
                trial_duration: CONFIG.response_deadline,
                data: {
                    trial_part: "stimulus",
                    block: blockNum,
                    cue1_present: cuePattern[0],
                    cue2_present: cuePattern[1],
                    cue3_present: cuePattern[2],
                    cue4_present: cuePattern[3],
                    n_cues_present: nPresent,
                    strong_cue_present: strongCuePresent,
                    actual_outcome: actualOutcome,
                    optimal_response: optimalResp,
                },
                on_finish: function (data) {
                    trialCounter++;
                    data.trial_index = trialCounter;
                    data.timed_out = data.response === null;

                    if (data.response === "f") {
                        data.player_response = "sun";
                    } else if (data.response === "j") {
                        data.player_response = "rain";
                    } else {
                        data.player_response = null;
                    }

                    data.correct = data.player_response === data.actual_outcome;
                    if (data.correct) {
                        totalCorrect++;
                    }
                },
            });

            // Feedback
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    var last = jsPsych.data.get().last(1).values()[0];
                    if (last.timed_out) {
                        return '<div class="feedback" style="color:#999">Too slow! The weather was ' +
                            (last.actual_outcome === "sun" ? "Sun &#9728;&#65039;" : "Rain &#127783;&#65039;") + '</div>';
                    }
                    if (last.correct) {
                        return '<div class="feedback" style="color:green">Correct! It was ' +
                            (last.actual_outcome === "sun" ? "Sun &#9728;&#65039;" : "Rain &#127783;&#65039;") + '</div>';
                    } else {
                        return '<div class="feedback" style="color:red">Incorrect. It was ' +
                            (last.actual_outcome === "sun" ? "Sun &#9728;&#65039;" : "Rain &#127783;&#65039;") + '</div>';
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
        })(t, mainPatterns[t]);

        // Block break
        if ((t + 1) % CONFIG.trials_per_block === 0 && t < CONFIG.n_trials - 1) {
            var blockNum = Math.floor(t / CONFIG.trials_per_block) + 1;
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    var pct = Math.round((totalCorrect / trialCounter) * 100);
                    return "<h2>Block " + blockNum + " of " + CONFIG.n_blocks + " complete</h2>" +
                        "<p>Accuracy so far: " + pct + "%</p>" +
                        "<p>Take a short break if needed.</p>" +
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
            var pct = Math.round((totalCorrect / trialCounter) * 100);
            return "<h2>Task Complete</h2>" +
                "<p>Thank you for completing the Weather Prediction task.</p>" +
                "<p>Final accuracy: " + pct + "%</p>" +
                "<p>Your data has been submitted.</p>";
        },
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
