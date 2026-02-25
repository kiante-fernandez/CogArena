(function () {
    var CONFIG = {
        n_rounds: 20,
        n_proposer: 10,
        n_responder: 10,
        endowment: 10,
        valid_keys: ["f", "j"],
        slider_min: 0,
        slider_max: 10,
        response_deadline: 15000,
        fixation_duration: 500,
        feedback_duration: 1500,
        iti_min: 300,
        iti_max: 600,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "ultimatum_game";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.n_proposer = Math.ceil(_nto / 2);
        CONFIG.n_responder = _nto - CONFIG.n_proposer;
        CONFIG.n_rounds = _nto;
    }

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    /* ---- Simulated responder thresholds (for proposer trials) ---- */
    // Each proposer round has a simulated responder with a minimum acceptable offer.
    // Thresholds vary across rounds: 2, 3, or 4 out of 10.
    var responderThresholds = [3, 2, 4, 3, 2, 4, 3, 2, 4, 3];

    /* ---- Simulated proposer offers (for responder trials) ---- */
    // Offers the simulated proposer makes: spread from 1-8 with some repeats
    var simulatedOffers = [1, 2, 3, 4, 5, 6, 7, 8, 2, 5];

    /* ---- Shuffle helper ---- */
    function shuffle(arr) {
        var shuffled = arr.slice();
        for (var i = shuffled.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var tmp = shuffled[i];
            shuffled[i] = shuffled[j];
            shuffled[j] = tmp;
        }
        return shuffled;
    }

    /* Shuffle the responder offers so order varies */
    var shuffledOffers = shuffle(simulatedOffers);
    var shuffledThresholds = shuffle(responderThresholds);

    /* ---- Timeline ---- */
    var timeline = [];

    /* Welcome */
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Ultimatum Game</h1>" +
            "<p>Welcome to the bargaining game.</p>" +
            "<p>Press any key to begin.</p>",
    });

    /* Instructions */
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>In this game, you will play <strong>" + CONFIG.n_rounds + " rounds</strong> " +
            "of the Ultimatum Game with different anonymous partners.</p>" +
            "<p>Each round, a pot of <strong>$" + CONFIG.endowment + "</strong> must be split between two players:</p>" +
            "<ul style='text-align:left;max-width:500px;margin:0 auto'>" +
            "<li>The <strong>Proposer</strong> decides how to split the money.</li>" +
            "<li>The <strong>Responder</strong> decides whether to accept or reject the split.</li>" +
            "</ul>",

            "<h2>Payoff Rules</h2>" +
            "<p>If the Responder <strong>accepts</strong>:</p>" +
            "<ul style='text-align:left;max-width:500px;margin:0 auto'>" +
            "<li>The Proposer keeps what they proposed to keep.</li>" +
            "<li>The Responder receives the offered amount.</li>" +
            "</ul>" +
            "<p>If the Responder <strong>rejects</strong>:</p>" +
            "<ul style='text-align:left;max-width:500px;margin:0 auto'>" +
            "<li><strong>Both players get $0.</strong></li>" +
            "</ul>",

            "<h2>Your Roles</h2>" +
            "<p>You will play <strong>" + CONFIG.n_proposer + " rounds as Proposer</strong> " +
            "and <strong>" + CONFIG.n_responder + " rounds as Responder</strong>.</p>" +
            "<p><strong>As Proposer:</strong> Use the slider to choose how much of $" + CONFIG.endowment + " to offer your partner.</p>" +
            "<p><strong>As Responder:</strong> You will see the Proposer's offer and decide:</p>" +
            "<p style='font-size:24px'><kbd>F</kbd> = <strong class='accept-key'>Accept</strong> &nbsp;&nbsp;&nbsp; " +
            "<kbd>J</kbd> = <strong class='reject-key'>Reject</strong></p>",

            "<h2>Ready?</h2>" +
            "<p>We will start with 2 practice rounds (one of each role).</p>" +
            "<p>Press Next to begin practice.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    /* ---- Build a proposer trial ---- */
    function buildProposerTrial(roundNum, totalRounds, threshold, isPractice) {
        var trials = [];
        var prefix = isPractice ? "Practice" : "Round";
        var label = prefix + " " + roundNum + " of " + totalRounds;

        /* Fixation */
        trials.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: '<div class="fixation">+</div>',
            choices: "NO_KEYS",
            trial_duration: CONFIG.fixation_duration,
            data: { trial_part: "fixation" },
        });

        /* Slider choice */
        trials.push({
            type: jsPsychHtmlSliderResponse,
            stimulus:
                '<div class="ultimatum-info">' +
                '<div class="round-header">' + label + '</div>' +
                '<div class="role-label">You are the <strong>PROPOSER</strong></div>' +
                '<div class="endowment-display">Pot: <span class="offer-amount">$' + CONFIG.endowment + '</span></div>' +
                '<div class="slider-label">How much do you offer your partner?</div>' +
                '</div>',
            min: CONFIG.slider_min,
            max: CONFIG.slider_max,
            step: 1,
            slider_start: Math.floor(CONFIG.endowment / 2),
            labels: ["$0 (keep all)", "$" + Math.floor(CONFIG.endowment / 2), "$" + CONFIG.endowment + " (give all)"],
            require_movement: true,
            button_label: "Submit Offer",
            trial_duration: CONFIG.response_deadline,
            data: {
                trial_part: isPractice ? "practice" : "stimulus",
                role: "proposer",
                endowment: CONFIG.endowment,
                responder_threshold: threshold,
            },
            on_finish: function (data) {
                var timedOut = data.response === null;
                data.timed_out = timedOut;

                var offerAmount = timedOut ? 0 : data.response;
                data.offer_amount = offerAmount;
                data.offer_proportion = offerAmount / CONFIG.endowment;

                /* Simulated responder accepts if offer >= threshold */
                data.accepted = offerAmount >= data.responder_threshold;

                if (data.accepted) {
                    data.player_payoff = CONFIG.endowment - offerAmount;
                    data.partner_payoff = offerAmount;
                } else {
                    data.player_payoff = 0;
                    data.partner_payoff = 0;
                }

                /* Derived fields for scoring */
                data.fair_offer = data.offer_proportion >= 0.3;
                data.low_offer = data.offer_proportion < 0.2;
                data.accepted_num = data.accepted ? 1 : 0;
            },
        });

        /* Feedback */
        trials.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                var last = jsPsych.data.get().last(1).values()[0];
                if (last.timed_out) {
                    return '<div class="feedback-container">' +
                        '<p style="color:#999">Time expired. Offer defaulted to $0.</p>' +
                        '<p class="feedback-reject">Partner rejected.</p>' +
                        '<p class="feedback-payoff">You earn: $0 &nbsp;|&nbsp; Partner earns: $0</p>' +
                        '</div>';
                }
                var acceptLabel = last.accepted
                    ? '<span class="feedback-accept">ACCEPTED</span>'
                    : '<span class="feedback-reject">REJECTED</span>';
                return '<div class="feedback-container">' +
                    '<p>You offered <strong>$' + last.offer_amount + '</strong> out of $' + CONFIG.endowment + '</p>' +
                    '<p>Partner ' + acceptLabel + ' your offer.</p>' +
                    '<p class="feedback-payoff">You earn: $' + last.player_payoff +
                    ' &nbsp;|&nbsp; Partner earns: $' + last.partner_payoff + '</p>' +
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

    /* ---- Build a responder trial ---- */
    function buildResponderTrial(roundNum, totalRounds, offerAmount, isPractice) {
        var trials = [];
        var prefix = isPractice ? "Practice" : "Round";
        var label = prefix + " " + roundNum + " of " + totalRounds;

        /* Fixation */
        trials.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: '<div class="fixation">+</div>',
            choices: "NO_KEYS",
            trial_duration: CONFIG.fixation_duration,
            data: { trial_part: "fixation" },
        });

        /* Accept/Reject choice */
        trials.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus:
                '<div class="ultimatum-info">' +
                '<div class="round-header">' + label + '</div>' +
                '<div class="role-label">You are the <strong>RESPONDER</strong></div>' +
                '<div class="endowment-display">Pot: $' + CONFIG.endowment + '</div>' +
                '<p>The Proposer offers you:</p>' +
                '<div class="offer-amount">$' + offerAmount + '</div>' +
                '<p>(Proposer keeps $' + (CONFIG.endowment - offerAmount) + ')</p>' +
                '<div class="response-keys">' +
                '<span class="accept-key"><kbd>F</kbd> Accept</span>' +
                ' &nbsp;&nbsp;&nbsp; ' +
                '<span class="reject-key"><kbd>J</kbd> Reject</span>' +
                '</div>' +
                '</div>',
            choices: CONFIG.valid_keys,
            trial_duration: CONFIG.response_deadline,
            data: {
                trial_part: isPractice ? "practice" : "stimulus",
                role: "responder",
                endowment: CONFIG.endowment,
                offer_amount: offerAmount,
            },
            on_finish: function (data) {
                var timedOut = data.response === null;
                data.timed_out = timedOut;

                data.offer_proportion = data.offer_amount / CONFIG.endowment;

                if (timedOut) {
                    /* Default to reject on timeout */
                    data.accepted = false;
                } else {
                    data.accepted = data.response === "f";
                }

                if (data.accepted) {
                    data.player_payoff = data.offer_amount;
                    data.partner_payoff = CONFIG.endowment - data.offer_amount;
                } else {
                    data.player_payoff = 0;
                    data.partner_payoff = 0;
                }

                /* Derived fields for scoring */
                data.fair_offer = data.offer_proportion >= 0.3;
                data.low_offer = data.offer_proportion < 0.2;
                data.accepted_num = data.accepted ? 1 : 0;
            },
        });

        /* Feedback */
        trials.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                var last = jsPsych.data.get().last(1).values()[0];
                if (last.timed_out) {
                    return '<div class="feedback-container">' +
                        '<p style="color:#999">Time expired. Offer automatically rejected.</p>' +
                        '<p class="feedback-payoff">You earn: $0 &nbsp;|&nbsp; Partner earns: $0</p>' +
                        '</div>';
                }
                var decisionLabel = last.accepted
                    ? '<span class="feedback-accept">ACCEPTED</span>'
                    : '<span class="feedback-reject">REJECTED</span>';
                return '<div class="feedback-container">' +
                    '<p>Offer of $' + last.offer_amount + ' out of $' + CONFIG.endowment + '</p>' +
                    '<p>You ' + decisionLabel + ' the offer.</p>' +
                    '<p class="feedback-payoff">You earn: $' + last.player_payoff +
                    ' &nbsp;|&nbsp; Partner earns: $' + last.partner_payoff + '</p>' +
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

    /* ---- Practice rounds (1 proposer, 1 responder) ---- */
    var practiceProposer = buildProposerTrial(1, 2, 3, true);
    practiceProposer.forEach(function (t) { timeline.push(t); });

    var practiceResponder = buildResponderTrial(2, 2, 4, true);
    practiceResponder.forEach(function (t) { timeline.push(t); });

    /* Transition to main rounds */
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>End of Practice</h2>" +
            "<p>The main game will now begin.</p>" +
            "<p>You will play <strong>" + CONFIG.n_rounds + " rounds</strong>:</p>" +
            "<p>" + CONFIG.n_proposer + " as Proposer, " + CONFIG.n_responder + " as Responder.</p>" +
            "<p>Press any key to start.</p>",
    });

    /* ---- Build main round schedule ---- */
    // Block structure: proposer rounds first, then responder rounds
    var trialCounter = 0;
    var roundCounter = 0;

    /* Proposer block */
    for (var p = 0; p < CONFIG.n_proposer; p++) {
        (function (proposerIdx) {
            roundCounter++;
            var roundNum = roundCounter;
            var threshold = shuffledThresholds[proposerIdx];
            var roundTrials = buildProposerTrial(roundNum, CONFIG.n_rounds, threshold, false);

            roundTrials.forEach(function (t) {
                if (t.data && t.data.trial_part === "stimulus") {
                    var origFinish = t.on_finish;
                    t.on_finish = function (data) {
                        origFinish(data);
                        trialCounter++;
                        data.trial_index = trialCounter;
                        data.round_number = roundNum;
                    };
                }
                timeline.push(t);
            });
        })(p);
    }

    /* Transition between blocks */
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Role Change</h2>" +
            "<p>You will now play as the <strong>Responder</strong> for the remaining rounds.</p>" +
            "<p>Press any key to continue.</p>",
    });

    /* Responder block */
    for (var r = 0; r < CONFIG.n_responder; r++) {
        (function (responderIdx) {
            roundCounter++;
            var roundNum = roundCounter;
            var offer = shuffledOffers[responderIdx];
            var roundTrials = buildResponderTrial(roundNum, CONFIG.n_rounds, offer, false);

            roundTrials.forEach(function (t) {
                if (t.data && t.data.trial_part === "stimulus") {
                    var origFinish = t.on_finish;
                    t.on_finish = function (data) {
                        origFinish(data);
                        trialCounter++;
                        data.trial_index = trialCounter;
                        data.round_number = roundNum;
                    };
                }
                timeline.push(t);
            });
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
        stimulus:
            "<h2>Task Complete</h2>" +
            "<p>Thank you for completing the Ultimatum Game.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
