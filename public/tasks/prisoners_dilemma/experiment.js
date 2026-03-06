(function () {
    var CONFIG = {
        n_rounds: 50,
        n_practice: 5,
        valid_keys: ["f", "j"],
        response_deadline: 10000,
        fixation_duration: 500,
        feedback_duration: 1500,
        iti_min: 300,
        iti_max: 600,
        noise_prob: 0.10,
        payoff_matrix: {
            CC: { player: 3, partner: 3 },
            CD: { player: 0, partner: 5 },
            DC: { player: 5, partner: 0 },
            DD: { player: 1, partner: 1 },
        },
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "prisoners_dilemma";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.n_rounds = _nto;
    }

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    /* ---- State tracking ---- */
    var cumulativePayoff = 0;
    var previousPlayerChoice = null;   // "cooperate" or "defect"
    var previousPartnerChoice = null;  // "cooperate" or "defect"
    var previousMutualDefection = false;

    /* ---- Tit-for-Tat with noise partner ---- */
    function getPartnerChoice(roundNumber) {
        // Round 1: partner cooperates
        if (roundNumber === 1) {
            return applyNoise("cooperate");
        }
        // Subsequent rounds: copy player's previous choice, with 10% flip
        return applyNoise(previousPlayerChoice);
    }

    function applyNoise(intendedChoice) {
        if (Math.random() < CONFIG.noise_prob) {
            return intendedChoice === "cooperate" ? "defect" : "cooperate";
        }
        return intendedChoice;
    }

    /* ---- Payoff lookup ---- */
    function getPayoffs(playerChoice, partnerChoice) {
        var key = (playerChoice === "cooperate" ? "C" : "D") +
                  (partnerChoice === "cooperate" ? "C" : "D");
        return CONFIG.payoff_matrix[key];
    }

    /* ---- Payoff matrix HTML ---- */
    function payoffMatrixHTML() {
        return '<table class="payoff-matrix">' +
            '<tr class="header-row">' +
                '<th></th><th></th>' +
                '<th class="partner-label" colspan="2">Partner</th>' +
            '</tr>' +
            '<tr>' +
                '<th></th><th></th>' +
                '<th>Cooperate</th><th>Defect</th>' +
            '</tr>' +
            '<tr>' +
                '<th class="you-label" rowspan="2">You</th>' +
                '<th>Cooperate</th>' +
                '<td class="payoff-cell"><span class="payoff-you">3</span>, <span class="payoff-partner">3</span></td>' +
                '<td class="payoff-cell"><span class="payoff-you">0</span>, <span class="payoff-partner">5</span></td>' +
            '</tr>' +
            '<tr>' +
                '<th>Defect</th>' +
                '<td class="payoff-cell"><span class="payoff-you">5</span>, <span class="payoff-partner">0</span></td>' +
                '<td class="payoff-cell"><span class="payoff-you">1</span>, <span class="payoff-partner">1</span></td>' +
            '</tr>' +
            '</table>';
    }

    /* ---- Timeline ---- */
    var timeline = [];

    /* Welcome */
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Repeated Prisoner's Dilemma</h1>" +
            "<p>Welcome to the cooperation game.</p>" +
            "<p>Press any key to begin.</p>",
    });

    /* Instructions */
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>In this game, you will play <strong>" + CONFIG.n_rounds + " rounds</strong> " +
            "with the <strong>same partner</strong>.</p>" +
            "<p>Each round, both you and your partner independently choose to " +
            "<strong>Cooperate</strong> or <strong>Defect</strong>.</p>" +
            "<p>Your payoff depends on both your choice and your partner's choice.</p>",

            "<h2>Payoff Matrix</h2>" +
            "<p>The numbers show payoffs as <span class='payoff-you'>You</span>, " +
            "<span class='payoff-partner'>Partner</span>:</p>" +
            payoffMatrixHTML() +
            "<p>If you both <strong>Cooperate</strong>, you each earn <strong>3</strong> points.</p>" +
            "<p>If you <strong>Defect</strong> while your partner <strong>Cooperates</strong>, " +
            "you earn <strong>5</strong> and they earn <strong>0</strong>.</p>" +
            "<p>If you both <strong>Defect</strong>, you each earn <strong>1</strong> point.</p>",

            "<h2>Response Keys</h2>" +
            "<p style='font-size:28px'><kbd>F</kbd> = <strong>Cooperate</strong></p>" +
            "<p style='font-size:28px'><kbd>J</kbd> = <strong>Defect</strong></p>" +
            "<p>You have 10 seconds to respond each round.</p>" +
            "<p>Remember: you play all " + CONFIG.n_rounds + " rounds with the <strong>same partner</strong>.</p>" +
            "<p>Try to earn as many points as possible!</p>" +
            "<p>Press Next to start with " + CONFIG.n_practice + " practice rounds.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    /* ---- Build a single round (practice or main) ---- */
    function buildRound(roundNumber, totalRounds, isPractice) {
        var trials = [];
        var prefix = isPractice ? "Practice" : "Round";
        var label = isPractice
            ? prefix + " " + roundNumber + " of " + totalRounds
            : prefix + " " + roundNumber + " of " + totalRounds;

        /* Fixation */
        trials.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: '<div class="fixation">+</div>',
            choices: "NO_KEYS",
            trial_duration: CONFIG.fixation_duration,
            data: { trial_part: "fixation" },
        });

        /* Choice screen */
        trials.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                var scoreHTML = isPractice ? "" :
                    '<div class="cumulative-score">Total Score: ' + cumulativePayoff + '</div>';
                return '<div class="round-header">' + label + '</div>' +
                    scoreHTML +
                    payoffMatrixHTML() +
                    '<div class="key-hint"><kbd>F</kbd> Cooperate &nbsp;&nbsp;&nbsp; <kbd>J</kbd> Defect</div>';
            },
            choices: CONFIG.valid_keys,
            trial_duration: CONFIG.response_deadline,
            data: {
                trial_part: isPractice ? "practice" : "stimulus",
                round_number: roundNumber,
                is_practice: isPractice,
            },
            on_finish: function (data) {
                var timedOut = data.response === null;
                data.timed_out = timedOut;

                /* Player choice */
                if (timedOut) {
                    data.player_choice = "cooperate"; // default to cooperate on timeout
                    data.player_cooperated = true;
                } else {
                    var playerCooperated = data.response === "f";
                    data.player_choice = playerCooperated ? "cooperate" : "defect";
                    data.player_cooperated = playerCooperated;
                }

                /* Partner choice (tit-for-tat with noise) */
                var partnerChoice = getPartnerChoice(roundNumber);
                data.partner_choice = partnerChoice;
                data.partner_cooperated = partnerChoice === "cooperate";

                /* Payoffs */
                var payoffs = getPayoffs(data.player_choice, data.partner_choice);
                data.player_payoff = payoffs.player;
                data.partner_payoff = payoffs.partner;

                /* Previous choices (for data record) */
                data.previous_player_choice = previousPlayerChoice;
                data.previous_partner_choice = previousPartnerChoice;

                /* Matched partner: player's current choice matches partner's PREVIOUS choice */
                if (roundNumber === 1 || previousPartnerChoice === null) {
                    data.matched_partner = null; // not applicable for round 1
                } else {
                    data.matched_partner = data.player_choice === previousPartnerChoice;
                }

                /* Mutual defection this round */
                data.mutual_defection = (data.player_choice === "defect" && data.partner_choice === "defect");

                /* Track previous_mutual_defection for forgiveness signature */
                data.previous_mutual_defection = previousMutualDefection;

                /* Forgave: cooperated after previous mutual defection */
                if (previousMutualDefection) {
                    data.forgave = data.player_cooperated;
                } else {
                    data.forgave = null; // not applicable
                }

                /* Cumulative score (main rounds only) */
                if (!isPractice) {
                    cumulativePayoff += data.player_payoff;
                }
                data.cumulative_payoff = cumulativePayoff;

                /* Update state for next round */
                previousPlayerChoice = data.player_choice;
                previousPartnerChoice = data.partner_choice;
                previousMutualDefection = data.mutual_defection;
            },
        });

        /* Feedback */
        trials.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                var lastTrial = jsPsych.data.get().last(1).values()[0];
                var playerClass = lastTrial.player_cooperated ? "cooperate" : "defect";
                var partnerClass = lastTrial.partner_cooperated ? "cooperate" : "defect";
                var playerLabel = lastTrial.player_cooperated ? "Cooperated" : "Defected";
                var partnerLabel = lastTrial.partner_cooperated ? "Cooperated" : "Defected";
                var scoreHTML = isPractice ? "" :
                    '<div class="feedback-cumulative">Cumulative Score: ' + lastTrial.cumulative_payoff + '</div>';

                return '<div class="feedback-container">' +
                    '<div class="feedback-choice ' + playerClass + '">You: <strong>' + playerLabel + '</strong></div>' +
                    '<div class="feedback-choice ' + partnerClass + '">Partner: <strong>' + partnerLabel + '</strong></div>' +
                    '<div class="feedback-payoff">You earned: ' + lastTrial.player_payoff + ' points</div>' +
                    scoreHTML +
                    '</div>';
            },
            choices: "NO_KEYS",
            trial_duration: CONFIG.feedback_duration,
            data: { trial_part: "feedback" },
        });

        /* ITI */
        trials.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: "",
            choices: "NO_KEYS",
            trial_duration: function () {
                return CONFIG.iti_min + Math.random() * (CONFIG.iti_max - CONFIG.iti_min);
            },
            data: { trial_part: "iti" },
        });

        return trials;
    }

    /* ---- Practice rounds ---- */
    // Reset state before practice (partner uses same TFT logic)
    previousPlayerChoice = null;
    previousPartnerChoice = null;
    previousMutualDefection = false;

    for (var p = 1; p <= CONFIG.n_practice; p++) {
        var practiceTrials = buildRound(p, CONFIG.n_practice, true);
        for (var pt = 0; pt < practiceTrials.length; pt++) {
            timeline.push(practiceTrials[pt]);
        }
    }

    /* Transition to main rounds */
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>End of Practice</h2>" +
            "<p>The main game will now begin.</p>" +
            "<p>You will play <strong>" + CONFIG.n_rounds + " rounds</strong> with your partner.</p>" +
            "<p>Press any key to start.</p>",
    });

    /* Reset state for main rounds */
    timeline.push({
        type: jsPsychCallFunction,
        func: function () {
            cumulativePayoff = 0;
            previousPlayerChoice = null;
            previousPartnerChoice = null;
            previousMutualDefection = false;
        },
    });

    /* ---- Main rounds ---- */
    var trialCounter = 0;
    for (var r = 1; r <= CONFIG.n_rounds; r++) {
        (function (roundNum) {
            var roundTrials = buildRound(roundNum, CONFIG.n_rounds, false);
            // Wrap the on_finish for the stimulus trial to add trial_index
            for (var rt = 0; rt < roundTrials.length; rt++) {
                if (roundTrials[rt].data && roundTrials[rt].data.trial_part === "stimulus") {
                    var origFinish = roundTrials[rt].on_finish;
                    roundTrials[rt].on_finish = function (data) {
                        origFinish(data);
                        trialCounter++;
                        data.trial_index = trialCounter;
                    };
                }
                timeline.push(roundTrials[rt]);
            }
        })(r);
    }

    /* ---- Data submission ---- */
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

    /* ---- Completion screen ---- */
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus: function () {
            return "<h2>Task Complete</h2>" +
                "<p>Thank you for completing the Prisoner's Dilemma game.</p>" +
                "<p>Your final score: <strong>" + cumulativePayoff + "</strong> points.</p>" +
                "<p>Your data has been submitted.</p>";
        },
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
