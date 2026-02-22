(function () {
    var CONFIG = {
        n_rounds: 15,
        endowment: 10,
        multiplier: 3,
        n_practice: 2,
        trustee_types: [
            { type: "cooperative", return_min: 0.40, return_max: 0.60, count: 5 },
            { type: "neutral", return_min: 0.25, return_max: 0.35, count: 5 },
            { type: "defecting", return_min: 0.05, return_max: 0.15, count: 5 },
        ],
        response_deadline: 15000,
        outcome_duration: 3000,
        iti_duration: 500,
    };

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "trust_game";

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    function generateRoundOrder() {
        var rounds = [];
        var trusteeId = 0;
        CONFIG.trustee_types.forEach(function (tt) {
            for (var i = 0; i < tt.count; i++) {
                rounds.push({
                    trustee_id: trusteeId,
                    trustee_type: tt.type,
                    return_min: tt.return_min,
                    return_max: tt.return_max,
                });
                trusteeId++;
            }
        });

        for (var i = rounds.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var tmp = rounds[i];
            rounds[i] = rounds[j];
            rounds[j] = tmp;
        }

        return rounds;
    }

    function computeReturn(tripled, returnMin, returnMax) {
        var rate = returnMin + Math.random() * (returnMax - returnMin);
        var amount = Math.round(tripled * rate * 100) / 100;
        return Math.max(0, Math.min(tripled, Math.round(amount)));
    }

    var allRounds = generateRoundOrder();
    var timeline = [];

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Trust Game</h1>" +
            "<p>Welcome to the trust game.</p>" +
            "<p>Press any key to begin.</p>",
    });

    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>In this game, you will play " + CONFIG.n_rounds + " rounds with different partners.</p>" +
            "<p>Each round, you receive <strong>$" + CONFIG.endowment + "</strong>.</p>" +
            "<p>You decide how much to send to your partner (from $0 to $" + CONFIG.endowment + ").</p>" +
            "<p>Use the slider to choose your investment amount.</p>",

            "<h2>The Multiplier</h2>" +
            "<p>Whatever you send is <strong>tripled</strong> (multiplied by " + CONFIG.multiplier + ").</p>" +
            "<p>For example, if you send $5, your partner receives $15.</p>" +
            "<p>Your partner then decides how much to return to you.</p>" +
            "<p>Your profit = what you kept + what partner returns.</p>" +
            "<p>Different partners may behave differently!</p>",

            "<h2>Ready?</h2>" +
            "<p>We will start with " + CONFIG.n_practice + " practice rounds.</p>" +
            "<p>Press Next to begin practice.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    function buildRoundTimeline(roundData, roundNum, isPractice) {
        var trials = [];
        var prefix = isPractice ? "Practice Round" : "Round";

        trials.push({
            type: jsPsychHtmlSliderResponse,
            stimulus:
                '<div class="round-header">' + prefix + " " + roundNum + (isPractice ? "" : " of " + CONFIG.n_rounds) + "</div>" +
                '<div class="partner-label">Partner #' + (roundData.trustee_id + 1) + "</div>" +
                '<div class="endowment-display">Your endowment: $' + CONFIG.endowment + "</div>" +
                '<div class="multiplier-note">Amount sent will be tripled (&times;' + CONFIG.multiplier + ")</div>" +
                '<div class="slider-label">How much do you want to send?</div>',
            min: 0,
            max: CONFIG.endowment,
            start: Math.floor(CONFIG.endowment / 2),
            step: 1,
            labels: ["$0", "$" + CONFIG.endowment],
            slider_width: 500,
            require_movement: false,
            button_label: "Send",
            trial_duration: CONFIG.response_deadline,
            data: {
                trial_part: isPractice ? "practice" : "stimulus",
                round: roundNum,
                trustee_id: roundData.trustee_id,
                trustee_type: roundData.trustee_type,
                endowment: CONFIG.endowment,
            },
            on_finish: function (data) {
                if (data.response === null) {
                    data.amount_sent = 0;
                    data.timed_out = true;
                } else {
                    data.amount_sent = data.response;
                    data.timed_out = false;
                }

                data.amount_sent_proportion = data.amount_sent / CONFIG.endowment;
                data.sent_nonzero = data.amount_sent > 0;
                data.tripled_amount = data.amount_sent * CONFIG.multiplier;
                data.amount_returned = computeReturn(data.tripled_amount, roundData.return_min, roundData.return_max);
                data.amount_returned_proportion = data.tripled_amount > 0 ? data.amount_returned / data.tripled_amount : 0;
                data.net_payoff = (CONFIG.endowment - data.amount_sent) + data.amount_returned;
            },
        });

        trials.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                var lastTrial = jsPsych.data.get().last(1).values()[0];
                var kept = CONFIG.endowment - lastTrial.amount_sent;
                var profitClass = lastTrial.net_payoff >= CONFIG.endowment ? "positive" : "negative";
                return '<div class="outcome-display">' +
                    '<div class="outcome-sent">You sent: $' + lastTrial.amount_sent +
                    " (tripled to $" + lastTrial.tripled_amount + ")</div>" +
                    '<div class="outcome-returned">Partner returned: $' + lastTrial.amount_returned + "</div>" +
                    "<hr>" +
                    '<div class="outcome-profit ' + profitClass + '">You kept $' + kept +
                    " + received $" + lastTrial.amount_returned +
                    " = $" + lastTrial.net_payoff + "</div>" +
                    "</div>";
            },
            choices: "NO_KEYS",
            trial_duration: CONFIG.outcome_duration,
            data: { trial_part: "outcome" },
        });

        trials.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: "",
            choices: "NO_KEYS",
            trial_duration: CONFIG.iti_duration,
            data: { trial_part: "iti" },
        });

        return trials;
    }

    var practiceRounds = [
        { trustee_id: 100, trustee_type: "cooperative", return_min: 0.45, return_max: 0.55 },
        { trustee_id: 101, trustee_type: "defecting", return_min: 0.05, return_max: 0.15 },
    ];

    practiceRounds.forEach(function (rd, idx) {
        var trials = buildRoundTimeline(rd, idx + 1, true);
        trials.forEach(function (t) { timeline.push(t); });
    });

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>End of Practice</h2>" +
            "<p>The main game will now begin.</p>" +
            "<p>There are " + CONFIG.n_rounds + " rounds with different partners.</p>" +
            "<p>Press any key to start.</p>",
    });

    var trialCounter = 0;
    allRounds.forEach(function (rd, idx) {
        var trials = buildRoundTimeline(rd, idx + 1, false);
        trials.forEach(function (t) {
            if (t.data && t.data.trial_part === "stimulus") {
                var origFinish = t.on_finish;
                t.on_finish = function (data) {
                    origFinish(data);
                    trialCounter++;
                    data.trial_index = trialCounter;

                    var prevStimuli = jsPsych.data.get().filter({ trial_part: "stimulus" }).values();
                    if (prevStimuli.length >= 2) {
                        var prev = prevStimuli[prevStimuli.length - 2];
                        data.prev_return_proportion = prev.amount_returned_proportion;
                    }
                };
            }
            timeline.push(t);
        });
    });

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
            "<p>Thank you for completing the trust game.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
