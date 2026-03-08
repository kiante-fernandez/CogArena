(function () {
    var CONFIG = {
        n_rounds: 10,
        endowment: 20,
        multiplier: 1.6,
        n_players: 4,
        slider_min: 0,
        slider_max: 20,
        n_practice: 2,
        response_deadline: 15000,
        fixation_duration: 500,
        feedback_duration: 2000,
        iti_min: 300,
        iti_max: 600,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "public_goods";

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

    // --- Simulated co-player contributions ---
    // Conditional cooperation pattern: starts around 8-12, declines ~1 per round, noise +/-2
    function simulateOtherContributions(roundNum) {
        var contributions = [];
        for (var p = 0; p < CONFIG.n_players - 1; p++) {
            var baseMean = 10 - (roundNum - 1) * 1.0;
            var noise = (Math.random() * 4) - 2;
            var contribution = Math.round(baseMean + noise);
            contribution = Math.max(0, Math.min(CONFIG.endowment, contribution));
            contributions.push(contribution);
        }
        return contributions;
    }

    function meanArray(arr) {
        var sum = 0;
        for (var i = 0; i < arr.length; i++) {
            sum += arr[i];
        }
        return arr.length > 0 ? sum / arr.length : 0;
    }

    function randomITI() {
        return CONFIG.iti_min + Math.floor(Math.random() * (CONFIG.iti_max - CONFIG.iti_min + 1));
    }

    var timeline = [];
    var trialCounter = 0;
    var cumulativePayoff = 0;

    // --- Welcome ---
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Public Goods Game</h1>" +
            "<p>Welcome to the Public Goods Game.</p>" +
            "<p>Press any key to begin.</p>",
    });

    // --- Instructions ---
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>In this game, you are in a group of <strong>" + CONFIG.n_players + " players</strong>.</p>" +
            "<p>Each round, every player receives an endowment of <strong>" + CONFIG.endowment + " tokens</strong>.</p>" +
            "<p>You decide how many tokens (0 to " + CONFIG.endowment + ") to contribute to a shared <strong>public pool</strong>.</p>" +
            "<p>You keep any tokens you do not contribute.</p>",

            "<h2>The Public Pool</h2>" +
            "<p>All contributions are added together, then <strong>multiplied by " + CONFIG.multiplier + "</strong>.</p>" +
            "<p>The multiplied pool is then <strong>split equally</strong> among all " + CONFIG.n_players + " players.</p>" +
            "<p>Your round payoff = (tokens kept) + (your share of the pool).</p>" +
            "<p>For example, if everyone contributes 10 tokens:</p>" +
            "<p>Pool = 4 &times; 10 &times; 1.6 = 64 &rarr; each player gets 16 back, plus 10 kept = 26 tokens.</p>",

            "<h2>Your Group</h2>" +
            "<p>You are matched with 3 other players.</p>" +
            "<p>The other players make their own contribution decisions each round.</p>" +
            "<p>After each round, you will see everyone's contributions and your payoff.</p>",

            "<h2>Ready?</h2>" +
            "<p>We will start with " + CONFIG.n_practice + " practice rounds to help you understand the game.</p>" +
            "<p>Practice rounds do not count toward your score.</p>" +
            "<p>Press Next to begin practice.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    // --- Build a single round ---
    function buildRoundTimeline(roundNum, isPractice) {
        var trials = [];
        var prefix = isPractice ? "Practice Round" : "Round";
        var totalLabel = isPractice ? "" : " of " + CONFIG.n_rounds;

        // Fixation
        trials.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: '<div class="fixation">+</div>',
            choices: "NO_KEYS",
            trial_duration: CONFIG.fixation_duration,
            data: { trial_part: "fixation" },
        });

        // Contribution slider
        trials.push({
            type: jsPsychHtmlSliderResponse,
            stimulus:
                '<div class="round-header">' + prefix + " " + roundNum + totalLabel + "</div>" +
                '<div class="endowment-display">Your endowment: ' + CONFIG.endowment + ' tokens</div>' +
                '<div class="group-note">Group of ' + CONFIG.n_players + ' players &bull; Pool multiplied by ' + CONFIG.multiplier + '</div>' +
                '<div class="slider-label">How many tokens do you contribute to the public pool?</div>',
            min: CONFIG.slider_min,
            max: CONFIG.slider_max,
            start: Math.floor(Math.random() * (CONFIG.slider_max - CONFIG.slider_min + 1)) + CONFIG.slider_min,
            step: 1,
            labels: ["0 (keep all)", "" + Math.floor(CONFIG.endowment / 2), "" + CONFIG.endowment + " (give all)"],
            slider_width: 500,
            require_movement: true,
            button_label: "Contribute",
            trial_duration: CONFIG.response_deadline,
            data: {
                trial_part: isPractice ? "practice" : "stimulus",
                round_number: roundNum,
                endowment: CONFIG.endowment,
            },
            on_finish: function (data) {
                var playerContribution = data.response !== null ? data.response : 0;
                data.timed_out = data.response === null;
                data.player_contribution = playerContribution;
                data.player_contribution_proportion = playerContribution / CONFIG.endowment;

                // Simulate other players
                var otherContributions = simulateOtherContributions(data.round_number);
                data.other_contributions = otherContributions;
                data.other_mean_contribution = Math.round(meanArray(otherContributions) * 100) / 100;

                // Calculate pool and payoffs
                var totalContributions = playerContribution;
                for (var i = 0; i < otherContributions.length; i++) {
                    totalContributions += otherContributions[i];
                }
                data.total_contributions = totalContributions;
                data.public_return = Math.round((totalContributions * CONFIG.multiplier / CONFIG.n_players) * 100) / 100;
                data.player_payoff = Math.round(((CONFIG.endowment - playerContribution) + data.public_return) * 100) / 100;

                // Positive contribution flag (for proportion test)
                data.positive_contribution = playerContribution > 0;

                if (!isPractice) {
                    trialCounter++;
                    data.trial_index = trialCounter;
                    cumulativePayoff = Math.round((cumulativePayoff + data.player_payoff) * 100) / 100;
                    data.cumulative_payoff = cumulativePayoff;

                    // Previous round data
                    var prevStimuli = jsPsych.data.get().filter({ trial_part: "stimulus" }).values();
                    if (prevStimuli.length >= 2) {
                        var prev = prevStimuli[prevStimuli.length - 2];
                        data.previous_player_contribution = prev.player_contribution;
                        data.previous_other_mean = prev.other_mean_contribution;
                        data.contribution_declined = playerContribution < prev.player_contribution;
                    } else {
                        data.previous_player_contribution = null;
                        data.previous_other_mean = null;
                        data.contribution_declined = null;
                    }
                }
            },
        });

        // Feedback screen
        trials.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                var last = jsPsych.data.get().last(1).values()[0];
                if (last.timed_out) {
                    return '<div style="font-size:20px;color:#999">Time expired. You contributed 0 tokens this round.</div>';
                }

                var otherContribs = last.other_contributions;
                var html = '<div class="feedback-display">';
                html += '<div class="section-label">Contributions:</div>';
                html += '<div class="contribution-row contribution-you"><span>You:</span><span>' + last.player_contribution + ' tokens</span></div>';
                for (var i = 0; i < otherContribs.length; i++) {
                    html += '<div class="contribution-row contribution-other"><span>Player ' + (i + 2) + ':</span><span>' + otherContribs[i] + ' tokens</span></div>';
                }

                html += '<div class="pool-total">Total pool: ' + last.total_contributions + ' &times; ' + CONFIG.multiplier + ' = ' + Math.round(last.total_contributions * CONFIG.multiplier * 100) / 100 + ' tokens</div>';
                html += '<div style="text-align:center; font-size:18px; color:#666;">Your share: ' + last.public_return + ' tokens</div>';

                var payoffClass = last.player_payoff >= CONFIG.endowment ? "positive" : "negative";
                html += '<div class="payoff-display ' + payoffClass + '">Round payoff: ' + last.player_payoff + ' tokens</div>';

                if (!last.timed_out && last.trial_part === "stimulus") {
                    html += '<div style="text-align:center; font-size:16px; color:#888;">(Kept ' + (CONFIG.endowment - last.player_contribution) + ' + received ' + last.public_return + ')</div>';
                }

                html += '</div>';
                return html;
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
            trial_duration: randomITI(),
            data: { trial_part: "iti" },
        });

        return trials;
    }

    // --- Practice rounds ---
    for (var p = 0; p < CONFIG.n_practice; p++) {
        var practiceTrials = buildRoundTimeline(p + 1, true);
        practiceTrials.forEach(function (t) { timeline.push(t); });
    }

    // End of practice
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>End of Practice</h2>" +
            "<p>The main game will now begin.</p>" +
            "<p>There are " + CONFIG.n_rounds + " rounds. Your contributions and payoffs will be recorded.</p>" +
            "<p>Press any key to start.</p>",
    });

    // --- Main rounds ---
    for (var r = 0; r < CONFIG.n_rounds; r++) {
        var roundTrials = buildRoundTimeline(r + 1, false);
        roundTrials.forEach(function (t) { timeline.push(t); });
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

    // --- Completion screen ---
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Task Complete</h2>" +
            "<p>Thank you for completing the Public Goods Game.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
