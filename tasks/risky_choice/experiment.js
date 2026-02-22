(function () {
    var CONFIG = {
        n_trials: 60,
        trials_per_domain: 20,
        domains: ["gain", "loss", "mixed"],
        probabilities: [0.1, 0.25, 0.5, 0.75, 0.9],
        n_practice: 4,
        valid_keys: ["f", "j"],
        response_deadline: 10000,
        fixation_duration: 500,
        iti_min: 300,
        iti_max: 600,
        feedback_duration: 1000,
    };

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "risky_choice";

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    function generateGambles() {
        var gambles = [];
        var stakes = [20, 30, 40, 50, 60, 80, 100];

        for (var d = 0; d < CONFIG.domains.length; d++) {
            var domain = CONFIG.domains[d];
            for (var t = 0; t < CONFIG.trials_per_domain; t++) {
                var prob = CONFIG.probabilities[t % CONFIG.probabilities.length];
                var stake = stakes[t % stakes.length];
                var risky_outcome, safe_outcome, risky_loss;

                if (domain === "gain") {
                    risky_outcome = stake;
                    risky_loss = 0;
                    safe_outcome = Math.round(stake * prob * (0.8 + Math.random() * 0.4));
                } else if (domain === "loss") {
                    risky_outcome = 0;
                    risky_loss = -stake;
                    safe_outcome = -Math.round(stake * (1 - prob) * (0.8 + Math.random() * 0.4));
                } else {
                    risky_outcome = stake;
                    risky_loss = -Math.round(stake * 0.5);
                    safe_outcome = Math.round((stake * prob + risky_loss * (1 - prob)) * (0.8 + Math.random() * 0.4));
                }

                var ev_risky;
                if (domain === "loss") {
                    ev_risky = risky_outcome * prob + risky_loss * (1 - prob);
                } else {
                    ev_risky = risky_outcome * prob + risky_loss * (1 - prob);
                }

                gambles.push({
                    domain: domain,
                    probability: prob,
                    risky_outcome: risky_outcome,
                    risky_loss: risky_loss,
                    safe_outcome: safe_outcome,
                    ev_risky: ev_risky,
                    ev_safe: safe_outcome,
                    risky_on_left: Math.random() > 0.5,
                });
            }
        }

        for (var i = gambles.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var tmp = gambles[i];
            gambles[i] = gambles[j];
            gambles[j] = tmp;
        }

        return gambles;
    }

    function formatAmount(amount) {
        if (amount >= 0) {
            return '<span class="gamble-amount positive">$' + amount + "</span>";
        } else {
            return '<span class="gamble-amount negative">-$' + Math.abs(amount) + "</span>";
        }
    }

    function formatGamble(gamble) {
        var riskyHtml, safeHtml;

        if (gamble.domain === "gain") {
            riskyHtml = formatAmount(gamble.risky_outcome) + " with " +
                Math.round(gamble.probability * 100) + "% chance<br>" +
                formatAmount(0) + " otherwise";
        } else if (gamble.domain === "loss") {
            riskyHtml = formatAmount(gamble.risky_loss) + " with " +
                Math.round((1 - gamble.probability) * 100) + "% chance<br>" +
                formatAmount(0) + " otherwise";
        } else {
            riskyHtml = formatAmount(gamble.risky_outcome) + " with " +
                Math.round(gamble.probability * 100) + "% chance<br>" +
                formatAmount(gamble.risky_loss) + " otherwise";
        }

        safeHtml = formatAmount(gamble.safe_outcome) + "<br>for sure";

        return { risky: riskyHtml, safe: safeHtml };
    }

    var allGambles = generateGambles();
    var timeline = [];

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Risky Choice Task</h1>" +
            "<p>Welcome to the decision-making task.</p>" +
            "<p>Press any key to begin.</p>",
    });

    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>In this task, you will make a series of choices between two options.</p>" +
            "<p>One option is always a <strong>sure thing</strong> (guaranteed amount).</p>" +
            "<p>The other option is a <strong>gamble</strong> with a chance of a better or worse outcome.</p>" +
            "<p>There are no right or wrong answers — just pick whichever you prefer.</p>",

            "<h2>Example</h2>" +
            '<div class="gamble-container">' +
            '<div class="gamble-option left">' +
            '<div class="gamble-label">Option A</div>' +
            '<span class="gamble-amount positive">$50</span> with 75% chance<br>' +
            '<span class="gamble-amount">$0</span> otherwise' +
            "</div>" +
            '<div class="gamble-option right">' +
            '<div class="gamble-label">Option B</div>' +
            '<span class="gamble-amount positive">$35</span><br>for sure' +
            "</div></div>" +
            "<p>The gamble offers more potential reward but with some risk.</p>" +
            "<p>Some trials involve gains, others involve losses or both.</p>",

            "<h2>Response Keys</h2>" +
            "<p style='font-size:28px'><kbd>F</kbd> = <strong>Left Option</strong></p>" +
            "<p style='font-size:28px'><kbd>J</kbd> = <strong>Right Option</strong></p>" +
            "<p>You have 10 seconds per choice. Press Next to start practice.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    var practiceGambles = [
        { domain: "gain", probability: 0.5, risky_outcome: 40, risky_loss: 0, safe_outcome: 18, ev_risky: 20, ev_safe: 18, risky_on_left: true },
        { domain: "loss", probability: 0.5, risky_outcome: 0, risky_loss: -40, safe_outcome: -18, ev_risky: -20, ev_safe: -18, risky_on_left: false },
        { domain: "gain", probability: 0.75, risky_outcome: 60, risky_loss: 0, safe_outcome: 40, ev_risky: 45, ev_safe: 40, risky_on_left: false },
        { domain: "mixed", probability: 0.5, risky_outcome: 50, risky_loss: -25, safe_outcome: 10, ev_risky: 12.5, ev_safe: 10, risky_on_left: true },
    ];

    practiceGambles.forEach(function (gamble, idx) {
        var formatted = formatGamble(gamble);
        var leftHtml = gamble.risky_on_left ? formatted.risky : formatted.safe;
        var rightHtml = gamble.risky_on_left ? formatted.safe : formatted.risky;
        var leftLabel = gamble.risky_on_left ? "Gamble" : "Sure Thing";
        var rightLabel = gamble.risky_on_left ? "Sure Thing" : "Gamble";

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
                '<div class="gamble-container">' +
                '<div class="gamble-option left"><div class="gamble-label">' + leftLabel + "</div>" + leftHtml + '<div class="key-hint">F</div></div>' +
                '<div class="gamble-option right"><div class="gamble-label">' + rightLabel + "</div>" + rightHtml + '<div class="key-hint">J</div></div>' +
                "</div>",
            choices: CONFIG.valid_keys,
            trial_duration: CONFIG.response_deadline,
            data: { trial_part: "practice" },
        });
    });

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>End of Practice</h2>" +
            "<p>The main experiment will now begin.</p>" +
            "<p>There are " + CONFIG.n_trials + " trials.</p>" +
            "<p>Press any key to start.</p>",
    });

    var trialCounter = 0;
    allGambles.forEach(function (gamble, idx) {
        var formatted = formatGamble(gamble);
        var leftHtml = gamble.risky_on_left ? formatted.risky : formatted.safe;
        var rightHtml = gamble.risky_on_left ? formatted.safe : formatted.risky;
        var leftLabel = gamble.risky_on_left ? "Gamble" : "Sure Thing";
        var rightLabel = gamble.risky_on_left ? "Sure Thing" : "Gamble";

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
                '<div class="gamble-container">' +
                '<div class="gamble-option left"><div class="gamble-label">' + leftLabel + "</div>" + leftHtml + '<div class="key-hint">F</div></div>' +
                '<div class="gamble-option right"><div class="gamble-label">' + rightLabel + "</div>" + rightHtml + '<div class="key-hint">J</div></div>' +
                "</div>",
            choices: CONFIG.valid_keys,
            trial_duration: CONFIG.response_deadline,
            data: {
                trial_part: "stimulus",
                domain: gamble.domain,
                probability: gamble.probability,
                risky_outcome: gamble.risky_outcome,
                risky_loss: gamble.risky_loss,
                safe_outcome: gamble.safe_outcome,
                ev_risky: gamble.ev_risky,
                ev_safe: gamble.ev_safe,
                risky_on_left: gamble.risky_on_left,
            },
            on_finish: function (data) {
                trialCounter++;
                data.trial_index = trialCounter;
                data.timed_out = data.response === null;

                if (!data.timed_out) {
                    var choseLeft = data.response === "f";
                    data.chose_risky = (choseLeft && data.risky_on_left) || (!choseLeft && !data.risky_on_left);
                    data.chose_safe = !data.chose_risky;
                } else {
                    data.chose_risky = false;
                    data.chose_safe = false;
                }

                data.ev_difference = data.ev_risky - data.ev_safe;
                data.chose_risky_num = data.chose_risky ? 1 : 0;
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
            "<p>Thank you for completing the risky choice task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
