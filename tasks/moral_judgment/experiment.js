(function () {
    var CONFIG = {
        n_trials: 26,
        valid_keys: ["f", "j"],
        response_deadline: 30000,
        fixation_duration: 500,
        iti_min: 500,
        iti_max: 1000,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "moral_judgment";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.n_trials = _nto;
    }

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 200,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    // Victim types used in the Moral Machine
    var VICTIM_TYPES = [
        "man", "woman", "elderly man", "elderly woman",
        "boy", "girl", "baby", "pregnant woman",
        "male doctor", "female doctor", "male executive", "female executive",
        "homeless person", "criminal", "dog", "cat",
    ];

    function pluralize(count, type) {
        if (count === 1) return "one " + type;
        return count + " " + type + "s";
    }

    function describeVictims(victims) {
        var parts = [];
        for (var i = 0; i < victims.length; i++) {
            parts.push(pluralize(victims[i].count, victims[i].type));
        }
        if (parts.length === 1) return parts[0];
        return parts.slice(0, -1).join(", ") + " and " + parts[parts.length - 1];
    }

    function generateScenarios() {
        var scenarios = [];
        var types = [
            "quantity", "age", "gender", "status",
            "species", "intervention",
        ];

        for (var i = 0; i < CONFIG.n_trials; i++) {
            var scenarioType = types[i % types.length];
            var intervention = Math.random() > 0.5; // true = swerve option is outcome A
            var victimsA, victimsB;

            if (scenarioType === "quantity") {
                // Fewer vs more deaths
                var nA = 1 + Math.floor(Math.random() * 2);
                var nB = nA + 1 + Math.floor(Math.random() * 3);
                victimsA = [{ type: "man", count: nA }];
                victimsB = [{ type: "woman", count: nB }];
            } else if (scenarioType === "age") {
                // Young vs old
                victimsA = [{ type: Math.random() > 0.5 ? "boy" : "girl", count: 2 }];
                victimsB = [{ type: Math.random() > 0.5 ? "elderly man" : "elderly woman", count: 2 }];
            } else if (scenarioType === "gender") {
                var n = 1 + Math.floor(Math.random() * 3);
                victimsA = [{ type: "man", count: n }];
                victimsB = [{ type: "woman", count: n }];
            } else if (scenarioType === "status") {
                victimsA = [{ type: "male doctor", count: 1 }];
                victimsB = [{ type: "homeless person", count: 1 }];
            } else if (scenarioType === "species") {
                victimsA = [{ type: Math.random() > 0.5 ? "dog" : "cat", count: 2 }];
                victimsB = [{ type: "man", count: 1 }];
            } else {
                // Intervention: passengers vs pedestrians
                var n2 = 1 + Math.floor(Math.random() * 2);
                victimsA = [{ type: "man", count: n2 }];
                victimsB = [{ type: "woman", count: n2 }];
            }

            var totalA = 0;
            for (var a = 0; a < victimsA.length; a++) totalA += victimsA[a].count;
            var totalB = 0;
            for (var b = 0; b < victimsB.length; b++) totalB += victimsB[b].count;

            scenarios.push({
                scenario_type: scenarioType,
                intervention: intervention,
                victims_a: victimsA,
                victims_b: victimsB,
                n_killed_a: totalA,
                n_killed_b: totalB,
                desc_a: describeVictims(victimsA),
                desc_b: describeVictims(victimsB),
                action_a: intervention ? "swerve" : "continue ahead",
                action_b: intervention ? "continue ahead" : "swerve",
            });
        }

        return scenarios;
    }

    var scenarios = generateScenarios();
    var timeline = [];

    // Welcome
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Moral Judgment Task</h1>" +
            "<p>Welcome to the moral dilemmas task.</p>" +
            "<p>Press any key to begin.</p>",
    });

    // Instructions
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>Imagine a self-driving car experiencing <strong>sudden brake failure</strong>.</p>" +
            "<p>On each trial, the car must choose between two outcomes.</p>" +
            "<p>Each outcome results in the death of different people.</p>" +
            "<p>Your task: <strong>Which outcome do you prefer?</strong></p>",

            "<h2>Example</h2>" +
            "<p><strong>Outcome A:</strong> The car swerves, killing 1 elderly man.</p>" +
            "<p><strong>Outcome B:</strong> The car continues ahead, killing 2 women.</p>" +
            "<p>There are no right or wrong answers — go with your moral intuition.</p>",

            "<h2>Response Keys</h2>" +
            "<p style='font-size:28px'><kbd>F</kbd> = <strong>Outcome A</strong> (left)</p>" +
            "<p style='font-size:28px'><kbd>J</kbd> = <strong>Outcome B</strong> (right)</p>" +
            "<p>You have 30 seconds per decision. Press Next to begin.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    // Trials
    var trialCounter = 0;
    scenarios.forEach(function (sc, idx) {
        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: '<div class="fixation">+</div>',
            choices: "NO_KEYS",
            trial_duration: CONFIG.fixation_duration,
            data: { trial_part: "fixation" },
        });

        var html = '<div class="trial-counter">Scenario ' + (idx + 1) + " of " + CONFIG.n_trials + "</div>";
        html += '<div class="scenario-intro">A self-driving car has sudden brake failure.</div>';
        html += '<div class="dilemma-container">';

        html += '<div class="outcome-box">';
        html += '<div class="outcome-label">Outcome A</div>';
        html += '<div class="action-desc">Car will ' + sc.action_a + "</div>";
        html += '<div class="casualties">Deaths: ' + sc.desc_a + "</div>";
        html += '<div class="key-hint">F</div>';
        html += "</div>";

        html += '<div class="outcome-box">';
        html += '<div class="outcome-label">Outcome B</div>';
        html += '<div class="action-desc">Car will ' + sc.action_b + "</div>";
        html += '<div class="casualties">Deaths: ' + sc.desc_b + "</div>";
        html += '<div class="key-hint">J</div>';
        html += "</div>";

        html += "</div>";

        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: html,
            choices: CONFIG.valid_keys,
            trial_duration: CONFIG.response_deadline,
            data: {
                trial_part: "stimulus",
                scenario_type: sc.scenario_type,
                intervention: sc.intervention,
                n_killed_a: sc.n_killed_a,
                n_killed_b: sc.n_killed_b,
                action_a: sc.action_a,
                action_b: sc.action_b,
            },
            on_finish: function (data) {
                trialCounter++;
                data.trial_index = trialCounter;
                data.timed_out = data.response === null;

                if (!data.timed_out) {
                    var choseA = data.response === "f";
                    data.n_saved_a = data.n_killed_b; // saving B's victims by choosing A
                    data.n_saved_b = data.n_killed_a; // saving A's victims by choosing B

                    // Did they choose the outcome with fewer deaths?
                    if (data.n_killed_a < data.n_killed_b) {
                        data.chose_fewer_deaths = choseA;
                    } else if (data.n_killed_b < data.n_killed_a) {
                        data.chose_fewer_deaths = !choseA;
                    } else {
                        data.chose_fewer_deaths = true; // Equal — count as utilitarian
                    }

                    data.chose_fewer_deaths_num = data.chose_fewer_deaths ? 1 : 0;
                    data.death_difference = Math.abs(data.n_killed_a - data.n_killed_b);

                    // Omission bias: did they choose the "continue ahead" (non-intervention) option?
                    data.chose_intervention = (choseA && data.action_a === "swerve") ||
                                               (!choseA && data.action_b === "swerve");
                    data.chose_inaction = !data.chose_intervention;
                } else {
                    data.n_saved_a = 0;
                    data.n_saved_b = 0;
                    data.chose_fewer_deaths = false;
                    data.chose_fewer_deaths_num = 0;
                    data.death_difference = Math.abs(data.n_killed_a - data.n_killed_b);
                    data.chose_intervention = false;
                    data.chose_inaction = false;
                }
            },
        });

        // ITI
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

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Task Complete</h2>" +
            "<p>Thank you for completing the moral judgment task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
