(function () {
    var CONFIG = {
        n_trials: 100,
        n_blocks: 5,
        trials_per_block: 20,
        decks: ["A", "B", "C", "D"],
        valid_keys: ["d", "f", "j", "k"],
        key_map: { A: "d", B: "f", C: "j", D: "k" },
        response_deadline: 5000,
        fixation_duration: 500,
        feedback_duration: 2000,
        iti_min: 300,
        iti_max: 600,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    // Deck payoff schedules (classic Bechara et al., 1994)
    // Decks A & B: High reward ($100), high penalty — net negative (bad decks)
    // Decks C & D: Low reward ($50), low penalty — net positive (good decks)
    var DECK_SCHEDULES = {
        A: {
            reward: 100,
            // 50% chance of loss, losses range 150-350
            loss_prob: 0.50,
            loss_min: 150,
            loss_max: 350,
            // Net EV per trial: 100 - 0.5*250 = -25
            type: "disadvantageous"
        },
        B: {
            reward: 100,
            // 10% chance of large loss (1250)
            loss_prob: 0.10,
            loss_min: 1150,
            loss_max: 1350,
            // Net EV per trial: 100 - 0.1*1250 = -25
            type: "disadvantageous"
        },
        C: {
            reward: 50,
            // 50% chance of loss, losses range 25-75
            loss_prob: 0.50,
            loss_min: 25,
            loss_max: 75,
            // Net EV per trial: 50 - 0.5*50 = +25
            type: "advantageous"
        },
        D: {
            reward: 50,
            // 10% chance of large loss (250)
            loss_prob: 0.10,
            loss_min: 200,
            loss_max: 300,
            // Net EV per trial: 50 - 0.1*250 = +25
            type: "advantageous"
        }
    };

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "iowa_gambling";

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    function sampleLoss(deckInfo) {
        if (Math.random() < deckInfo.loss_prob) {
            return Math.round(deckInfo.loss_min + Math.random() * (deckInfo.loss_max - deckInfo.loss_min));
        }
        return 0;
    }

    var timeline = [];
    var totalScore = 2000; // Starting bankroll

    // Instructions
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Iowa Gambling Task</h2>" +
            "<p>In this task, you will choose cards from four decks: <strong>A, B, C, D</strong>.</p>" +
            "<p>Each card gives you a reward and sometimes a penalty.</p>" +
            "<p>Your goal is to <strong>maximize your total earnings</strong> over 100 card picks.</p>",

            "<h2>The Decks</h2>" +
            '<div class="igt-decks">' +
            '<div class="igt-deck" style="background:#e8d5b7">A</div>' +
            '<div class="igt-deck" style="background:#b7d5e8">B</div>' +
            '<div class="igt-deck" style="background:#b7e8c4">C</div>' +
            '<div class="igt-deck" style="background:#e8b7d5">D</div>' +
            '</div>' +
            "<p>Some decks are better than others in the long run.</p>" +
            "<p>You need to figure out which decks are profitable.</p>",

            "<h2>Controls</h2>" +
            "<p><kbd>D</kbd> = Deck A &nbsp;&nbsp; <kbd>F</kbd> = Deck B &nbsp;&nbsp; <kbd>J</kbd> = Deck C &nbsp;&nbsp; <kbd>K</kbd> = Deck D</p>" +
            "<p>You start with <strong>$2,000</strong>.</p>" +
            "<p>Click Next to begin.</p>"
        ],
        show_clickable_nav: true,
    });

    var trialCounter = 0;

    for (var t = 0; t < CONFIG.n_trials; t++) {
        (function (trialNum) {
            // Fixation
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: '<div class="fixation">+</div>',
                choices: "NO_KEYS",
                trial_duration: CONFIG.fixation_duration,
            });

            var blockNum = Math.floor(trialNum / CONFIG.trials_per_block) + 1;

            // Deck choice
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    return '<div class="igt-decks">' +
                        '<div class="igt-deck" style="background:#e8d5b7">A<br><small>D</small></div>' +
                        '<div class="igt-deck" style="background:#b7d5e8">B<br><small>F</small></div>' +
                        '<div class="igt-deck" style="background:#b7e8c4">C<br><small>J</small></div>' +
                        '<div class="igt-deck" style="background:#e8b7d5">D<br><small>K</small></div>' +
                        '</div>' +
                        '<div class="igt-score">Trial ' + (trialNum + 1) + '/' + CONFIG.n_trials +
                        ' &nbsp;|&nbsp; Total: $' + totalScore + '</div>';
                },
                choices: CONFIG.valid_keys,
                trial_duration: CONFIG.response_deadline,
                data: {
                    trial_part: "stimulus",
                    block: blockNum,
                },
                on_finish: function (data) {
                    trialCounter++;
                    data.trial_index = trialCounter;
                    data.timed_out = data.response === null;

                    // Map key to deck
                    var keyToDeck = { d: "A", f: "B", j: "C", k: "D" };
                    if (data.response !== null) {
                        data.deck_chosen = keyToDeck[data.response];
                    } else {
                        // Random deck on timeout
                        data.deck_chosen = CONFIG.decks[Math.floor(Math.random() * 4)];
                    }

                    var deckInfo = DECK_SCHEDULES[data.deck_chosen];
                    data.deck_type = deckInfo.type;
                    data.win = deckInfo.reward;
                    data.loss = sampleLoss(deckInfo);
                    data.net_outcome = data.win - data.loss;

                    totalScore += data.net_outcome;
                    data.total_score = totalScore;

                    // Advantageous = chose C or D
                    data.chose_advantageous = data.deck_chosen === "C" || data.deck_chosen === "D";
                    data.correct = data.chose_advantageous;
                },
            });

            // Feedback
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    var last = jsPsych.data.get().last(1).values()[0];
                    var feedbackHTML = '<div class="igt-feedback">';
                    feedbackHTML += '<p>Deck <strong>' + last.deck_chosen + '</strong></p>';
                    feedbackHTML += '<p style="color:green">Win: +$' + last.win + '</p>';
                    if (last.loss > 0) {
                        feedbackHTML += '<p style="color:red">Loss: -$' + last.loss + '</p>';
                    }
                    feedbackHTML += '<p><strong>Net: ' + (last.net_outcome >= 0 ? '+' : '') + '$' + last.net_outcome + '</strong></p>';
                    feedbackHTML += '<p class="igt-score">Total: $' + last.total_score + '</p>';
                    feedbackHTML += '</div>';
                    return feedbackHTML;
                },
                choices: "NO_KEYS",
                trial_duration: CONFIG.feedback_duration,
            });
        })(t);

        // Block break
        if ((t + 1) % CONFIG.trials_per_block === 0 && t < CONFIG.n_trials - 1) {
            var blockNum = Math.floor(t / CONFIG.trials_per_block) + 1;
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    return "<h2>Block " + blockNum + " of " + CONFIG.n_blocks + " complete</h2>" +
                        "<p>Current total: $" + totalScore + "</p>" +
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
            return "<h2>Task Complete</h2>" +
                "<p>Thank you for completing the Iowa Gambling Task.</p>" +
                "<p>Final total: $" + totalScore + "</p>" +
                "<p>Your data has been submitted.</p>";
        },
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
