(function () {
    var CONFIG = {
        n_rounds: 20,
        endowment: 10,
        response_deadline: 15000,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "dictator_game";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.n_rounds = _nto;
    }

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 200,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    var timeline = [];

    // Instructions
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Dictator Game</h2>" +
            "<p>In this task, you will play " + CONFIG.n_rounds + " rounds of a giving game.</p>" +
            "<p>Each round, you are paired with a different anonymous partner.</p>" +
            "<p>You receive <strong>$" + CONFIG.endowment + "</strong> and can give any amount ($0 - $" + CONFIG.endowment + ") to your partner.</p>",

            "<h2>How It Works</h2>" +
            "<p>Use the slider to choose how much to give.</p>" +
            "<p>You keep whatever you don't give away.</p>" +
            "<p>Your partner has no say in the decision — you are the 'dictator'.</p>" +
            "<p>Each partner is different and will not know your choices from other rounds.</p>",

            "<h2>Ready?</h2>" +
            "<p>There are no right or wrong answers.</p>" +
            "<p>Just decide what feels appropriate to you.</p>" +
            "<p>Click Next to begin.</p>"
        ],
        show_clickable_nav: true,
    });

    var trialCounter = 0;

    for (var r = 0; r < CONFIG.n_rounds; r++) {
        (function (roundNum) {
            var partnerLabel = "Partner " + (roundNum + 1);

            timeline.push({
                type: jsPsychHtmlSliderResponse,
                stimulus:
                    '<div class="dictator-info">' +
                    '<p class="partner-label">Round ' + (roundNum + 1) + ' of ' + CONFIG.n_rounds + ' &mdash; ' + partnerLabel + '</p>' +
                    '<p>You have <span class="dictator-amount">$' + CONFIG.endowment + '</span></p>' +
                    '<p>How much would you like to give to ' + partnerLabel + '?</p>' +
                    '</div>',
                min: 0,
                max: CONFIG.endowment,
                step: 1,
                slider_start: Math.floor(CONFIG.endowment / 2),
                labels: ["$0 (keep all)", "$" + Math.floor(CONFIG.endowment / 2), "$" + CONFIG.endowment + " (give all)"],
                require_movement: true,
                trial_duration: CONFIG.response_deadline,
                data: {
                    trial_part: "stimulus",
                    round: roundNum + 1,
                    endowment: CONFIG.endowment,
                },
                on_finish: function (data) {
                    trialCounter++;
                    data.trial_index = trialCounter;

                    var given = data.response !== null ? data.response : 0;
                    data.amount_given = given;
                    data.amount_given_proportion = given / CONFIG.endowment;
                    data.gave_nonzero = given > 0;
                    data.gave_half = given >= CONFIG.endowment / 2;
                    data.amount_kept = CONFIG.endowment - given;
                    data.timed_out = data.response === null;
                },
            });

            // Brief confirmation
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    var last = jsPsych.data.get().last(1).values()[0];
                    if (last.timed_out) {
                        return '<div style="font-size:20px;color:#999">Time expired. Moving to next round...</div>';
                    }
                    return '<div style="font-size:20px">' +
                        'You gave <strong>$' + last.amount_given + '</strong> to ' + partnerLabel +
                        ' and kept <strong>$' + last.amount_kept + '</strong>.</div>';
                },
                choices: "NO_KEYS",
                trial_duration: 1500,
            });
        })(r);
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
        stimulus:
            "<h2>Task Complete</h2>" +
            "<p>Thank you for completing the Dictator Game.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
