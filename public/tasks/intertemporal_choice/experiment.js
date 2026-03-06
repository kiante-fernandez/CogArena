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
    var TASK_ID = "intertemporal_choice";

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

    // Delay options with labels and day equivalents
    var SOONER_DELAYS = [
        { label: "today", days: 0 },
        { label: "1 week", days: 7 },
    ];

    var LATER_DELAYS = [
        { label: "1 month", days: 30 },
        { label: "3 months", days: 90 },
        { label: "6 months", days: 180 },
        { label: "1 year", days: 365 },
    ];

    // Kirby et al. (1999) style: fixed larger amounts with varying smaller amounts
    var LARGER_AMOUNTS = [20, 25, 30, 35, 40, 50, 55, 60, 75, 80, 85, 100];
    var AMOUNT_RATIOS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9];

    function generateTrials() {
        var trials = [];

        // Generate a balanced set of 60 trials across delay and amount combinations
        for (var i = 0; i < CONFIG.n_trials; i++) {
            var larger = LARGER_AMOUNTS[i % LARGER_AMOUNTS.length];
            var ratio = AMOUNT_RATIOS[i % AMOUNT_RATIOS.length];
            var smaller = Math.max(5, Math.round(larger * ratio));

            // Ensure smaller < larger
            if (smaller >= larger) {
                smaller = larger - 5;
            }
            if (smaller < 5) {
                smaller = 5;
            }

            var sooner = SOONER_DELAYS[i % SOONER_DELAYS.length];
            var later = LATER_DELAYS[i % LATER_DELAYS.length];

            trials.push({
                smaller_amount: smaller,
                larger_amount: larger,
                delay_sooner: sooner.days,
                delay_later: later.days,
                delay_sooner_label: sooner.label,
                delay_later_label: later.label,
                amount_ratio: Math.round((smaller / larger) * 1000) / 1000,
                delay_category: later.days <= 30 ? "short" : "long",
                sooner_on_left: Math.random() > 0.5,
            });
        }

        // Shuffle trials
        for (var i = trials.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var tmp = trials[i];
            trials[i] = trials[j];
            trials[j] = tmp;
        }

        return trials;
    }

    function formatOption(amount, delayLabel) {
        return (
            '<div class="choice-amount">$' + amount + "</div>" +
            '<div class="choice-delay">' + delayLabel + "</div>"
        );
    }

    function buildTrialStimulus(trial, trialNum, totalTrials, label) {
        var soonerHtml = formatOption(trial.smaller_amount, trial.delay_sooner_label);
        var laterHtml = formatOption(trial.larger_amount, trial.delay_later_label);

        var leftHtml = trial.sooner_on_left ? soonerHtml : laterHtml;
        var rightHtml = trial.sooner_on_left ? laterHtml : soonerHtml;
        var leftLabel = trial.sooner_on_left ? "Sooner" : "Later";
        var rightLabel = trial.sooner_on_left ? "Later" : "Sooner";

        return (
            '<div class="trial-counter">' + label + " " + trialNum + " of " + totalTrials + "</div>" +
            '<div class="choice-container">' +
            '<div class="choice-option"><div class="choice-label">' + leftLabel + "</div>" + leftHtml + '<div class="key-hint">F</div></div>' +
            '<div class="choice-option"><div class="choice-label">' + rightLabel + "</div>" + rightHtml + '<div class="key-hint">J</div></div>' +
            "</div>"
        );
    }

    var allTrials = generateTrials();
    var timeline = [];

    // Welcome screen
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Intertemporal Choice Task</h1>" +
            "<p>Welcome to the decision-making task.</p>" +
            "<p>Press any key to begin.</p>",
    });

    // Instructions
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>In this task, you will make a series of choices between two money options.</p>" +
            "<p>One option offers a <strong>smaller amount sooner</strong>.</p>" +
            "<p>The other option offers a <strong>larger amount later</strong>.</p>" +
            "<p>There are no right or wrong answers — just pick whichever you prefer.</p>",

            "<h2>Example</h2>" +
            '<div class="choice-container">' +
            '<div class="choice-option">' +
            '<div class="choice-label">Sooner</div>' +
            '<div class="choice-amount">$30</div>' +
            '<div class="choice-delay">today</div>' +
            "</div>" +
            '<div class="choice-option">' +
            '<div class="choice-label">Later</div>' +
            '<div class="choice-amount">$60</div>' +
            '<div class="choice-delay">6 months</div>' +
            "</div></div>" +
            "<p>Would you rather have $30 now, or $60 in 6 months?</p>" +
            "<p>The sooner and later options may appear on either side.</p>",

            "<h2>Response Keys</h2>" +
            "<p style='font-size:28px'><kbd>F</kbd> = <strong>Left Option</strong></p>" +
            "<p style='font-size:28px'><kbd>J</kbd> = <strong>Right Option</strong></p>" +
            "<p>You have 10 seconds per choice. Press Next to start practice.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    // Practice trials
    var practiceTrials = [
        { smaller_amount: 20, larger_amount: 50, delay_sooner: 0, delay_later: 90, delay_sooner_label: "today", delay_later_label: "3 months", amount_ratio: 0.4, delay_category: "long", sooner_on_left: true },
        { smaller_amount: 40, larger_amount: 60, delay_sooner: 7, delay_later: 180, delay_sooner_label: "1 week", delay_later_label: "6 months", amount_ratio: 0.667, delay_category: "long", sooner_on_left: false },
        { smaller_amount: 15, larger_amount: 30, delay_sooner: 0, delay_later: 30, delay_sooner_label: "today", delay_later_label: "1 month", amount_ratio: 0.5, delay_category: "short", sooner_on_left: true },
        { smaller_amount: 55, larger_amount: 80, delay_sooner: 7, delay_later: 365, delay_sooner_label: "1 week", delay_later_label: "1 year", amount_ratio: 0.688, delay_category: "long", sooner_on_left: false },
    ];

    practiceTrials.forEach(function (trial, idx) {
        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: '<div class="fixation">+</div>',
            choices: "NO_KEYS",
            trial_duration: CONFIG.fixation_duration,
            data: { trial_part: "fixation" },
        });

        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: buildTrialStimulus(trial, idx + 1, CONFIG.n_practice, "Practice"),
            choices: CONFIG.valid_keys,
            trial_duration: CONFIG.response_deadline,
            data: { trial_part: "practice" },
        });
    });

    // Transition to main experiment
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
    allTrials.forEach(function (trial, idx) {
        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: '<div class="fixation">+</div>',
            choices: "NO_KEYS",
            trial_duration: CONFIG.fixation_duration,
            data: { trial_part: "fixation" },
        });

        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: buildTrialStimulus(trial, idx + 1, CONFIG.n_trials, "Trial"),
            choices: CONFIG.valid_keys,
            trial_duration: CONFIG.response_deadline,
            data: {
                trial_part: "stimulus",
                smaller_amount: trial.smaller_amount,
                larger_amount: trial.larger_amount,
                delay_sooner: trial.delay_sooner,
                delay_later: trial.delay_later,
                delay_sooner_label: trial.delay_sooner_label,
                delay_later_label: trial.delay_later_label,
                amount_ratio: trial.amount_ratio,
                delay_category: trial.delay_category,
                sooner_on_left: trial.sooner_on_left,
            },
            on_finish: function (data) {
                trialCounter++;
                data.trial_index = trialCounter;
                data.timed_out = data.response === null;

                if (!data.timed_out) {
                    var choseLeft = data.response === "f";
                    data.chose_smaller = (choseLeft && data.sooner_on_left) || (!choseLeft && !data.sooner_on_left);
                    data.chose_larger = !data.chose_smaller;
                    data.chose_sooner = data.chose_smaller;
                } else {
                    data.chose_smaller = false;
                    data.chose_larger = false;
                    data.chose_sooner = false;
                }

                data.chose_larger_num = data.chose_larger ? 1 : 0;
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

    // Completion screen
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Task Complete</h2>" +
            "<p>Thank you for completing the intertemporal choice task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
