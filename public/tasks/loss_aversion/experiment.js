(function () {
    var CONFIG = {
        n_trials: 60,
        n_practice: 4,
        valid_keys: ["f", "j"],
        response_deadline: 10000,
        fixation_duration: 500,
        iti_min: 300,
        iti_max: 600,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "loss_aversion";

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

    // Generate mixed gambles with varying gain and loss amounts.
    // All gambles are 50-50: win G or lose L.
    // Loss aversion predicts rejection when L/G < ~2 even if EV > 0.
    function generateGambles() {
        var gains = [5, 10, 15, 20, 25, 30, 35, 40];
        var losses = [5, 10, 15, 20, 25, 30, 35, 40];
        var gambles = [];

        // Create all gain-loss combinations, then sample n_trials
        var allPairs = [];
        for (var g = 0; g < gains.length; g++) {
            for (var l = 0; l < losses.length; l++) {
                allPairs.push({ gain: gains[g], loss: losses[l] });
            }
        }

        // Shuffle and take n_trials
        for (var i = allPairs.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var tmp = allPairs[i];
            allPairs[i] = allPairs[j];
            allPairs[j] = tmp;
        }

        var selected = allPairs.slice(0, CONFIG.n_trials);

        for (var t = 0; t < selected.length; t++) {
            var gain = selected[t].gain;
            var loss = selected[t].loss;
            var ev = (gain - loss) / 2; // 50% chance of each
            gambles.push({
                gain: gain,
                loss: loss,
                ev_gamble: ev,
                ev_positive: ev > 0,
                loss_gain_ratio: loss / gain,
                ev_abs: Math.abs(ev),
            });
        }

        return gambles;
    }

    var allGambles = generateGambles();
    var timeline = [];

    // Welcome
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Loss Aversion Task</h1>" +
            "<p>Welcome to the mixed gambles task.</p>" +
            "<p>Press any key to begin.</p>",
    });

    // Instructions
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>On each trial, you will see a gamble with two possible outcomes:</p>" +
            "<ul style='text-align:left; max-width:500px; margin:0 auto;'>" +
            "<li>A <strong style='color:#2e7d32'>gain</strong> (50% chance)</li>" +
            "<li>A <strong style='color:#c62828'>loss</strong> (50% chance)</li>" +
            "</ul>" +
            "<p>You must decide whether to <strong>accept</strong> or <strong>reject</strong> the gamble.</p>" +
            "<p>If you reject, you get $0 (no change).</p>",

            "<h2>Example</h2>" +
            '<div class="gamble-box">' +
            '<span class="amount-positive">Win $20</span> or <span class="amount-negative">Lose $15</span>' +
            "<br>(each 50% chance)" +
            "</div>" +
            "<p>Would you accept this gamble?</p>" +
            "<p>There are no right or wrong answers — go with your gut feeling.</p>",

            "<h2>Response Keys</h2>" +
            "<p style='font-size:28px'><kbd>F</kbd> = <strong>Accept</strong> the gamble</p>" +
            "<p style='font-size:28px'><kbd>J</kbd> = <strong>Reject</strong> the gamble</p>" +
            "<p>You have 10 seconds per decision. Press Next to start practice.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    // Practice trials
    var practiceGambles = [
        { gain: 20, loss: 10, ev_gamble: 5 },
        { gain: 15, loss: 25, ev_gamble: -5 },
        { gain: 30, loss: 30, ev_gamble: 0 },
        { gain: 40, loss: 15, ev_gamble: 12.5 },
    ];

    practiceGambles.forEach(function (g, idx) {
        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: '<div class="fixation">+</div>',
            choices: "NO_KEYS",
            trial_duration: CONFIG.fixation_duration,
            data: { trial_part: "fixation" },
        });

        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus:
                '<div class="trial-counter">Practice ' + (idx + 1) + " of " + CONFIG.n_practice + "</div>" +
                '<div class="gamble-box">' +
                '<span class="amount-positive">Win $' + g.gain + "</span>" +
                " or " +
                '<span class="amount-negative">Lose $' + g.loss + "</span>" +
                "<br>(each 50% chance)" +
                "</div>" +
                '<div class="response-hint"><kbd>F</kbd> Accept &nbsp;&nbsp; <kbd>J</kbd> Reject</div>',
            choices: CONFIG.valid_keys,
            trial_duration: CONFIG.response_deadline,
            data: { trial_part: "practice" },
        });
    });

    // Transition to main trials
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>End of Practice</h2>" +
            "<p>The main experiment will now begin.</p>" +
            "<p>There are " + CONFIG.n_trials + " trials.</p>" +
            "<p>Press any key to start.</p>",
    });

    // Main trials
    var trialCounter = 0;
    allGambles.forEach(function (gamble, idx) {
        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: '<div class="fixation">+</div>',
            choices: "NO_KEYS",
            trial_duration: CONFIG.fixation_duration,
            data: { trial_part: "fixation" },
        });

        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus:
                '<div class="trial-counter">Trial ' + (idx + 1) + " of " + CONFIG.n_trials + "</div>" +
                '<div class="gamble-box">' +
                '<span class="amount-positive">Win $' + gamble.gain + "</span>" +
                " or " +
                '<span class="amount-negative">Lose $' + gamble.loss + "</span>" +
                "<br>(each 50% chance)" +
                "</div>" +
                '<div class="response-hint"><kbd>F</kbd> Accept &nbsp;&nbsp; <kbd>J</kbd> Reject</div>',
            choices: CONFIG.valid_keys,
            trial_duration: CONFIG.response_deadline,
            data: {
                trial_part: "stimulus",
                gain: gamble.gain,
                loss: gamble.loss,
                ev_gamble: gamble.ev_gamble,
                ev_positive: gamble.ev_positive,
                loss_gain_ratio: gamble.loss_gain_ratio,
                ev_abs: gamble.ev_abs,
            },
            on_finish: function (data) {
                trialCounter++;
                data.trial_index = trialCounter;
                data.timed_out = data.response === null;

                if (!data.timed_out) {
                    data.accept = data.response === "f";
                    data.reject = data.response === "j";
                } else {
                    data.accept = false;
                    data.reject = false;
                }

                data.accept_num = data.accept ? 1 : 0;
            },
        });

        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: "",
            choices: "NO_KEYS",
            trial_duration: function () {
                return CONFIG.iti_min + Math.random() * (CONFIG.iti_max - CONFIG.iti_min);
            },
            data: { trial_part: "iti" },
        });
    });

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

    // Thank you
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Task Complete</h2>" +
            "<p>Thank you for completing the loss aversion task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
