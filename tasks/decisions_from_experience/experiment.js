(function () {
    var CONFIG = {
        n_problems: 20,
        valid_keys: ["f", "j"],
        sampling_key: " ",
        response_deadline: 10000,
        fixation_duration: 500,
        feedback_duration: 800,
        iti_min: 300,
        iti_max: 500,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "decisions_from_experience";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.n_problems = _nto;
    }

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    // ---- Problem generation ----
    // Each problem: two options (A=left, B=right)
    // option_a: win option_a_high with prob_a_high, win option_a_low otherwise
    // option_b: win option_b_high with prob_b_high, win option_b_low otherwise
    // rare_event_present: true if any probability <= 0.15
    function generateProblems() {
        var problems = [
            // -- Gain domain: rare high-value events --
            // Problem 1: A has rare big gain (description-experience gap expected)
            { option_a_high: 32, option_a_low: 0, prob_a_high: 0.10, option_b_high: 3, option_b_low: 3, prob_b_high: 1.0, domain: "gain" },
            // Problem 2: B has rare big gain
            { option_a_high: 4, option_a_low: 4, prob_a_high: 1.0, option_b_high: 40, option_b_low: 0, prob_b_high: 0.10, domain: "gain" },
            // Problem 3: Classic Hertwig et al. H-problem
            { option_a_high: 4, option_a_low: 0, prob_a_high: 0.80, option_b_high: 3, option_b_low: 3, prob_b_high: 1.0, domain: "gain" },
            // Problem 4: Rare moderate gain vs safe
            { option_a_high: 50, option_a_low: 0, prob_a_high: 0.10, option_b_high: 5, option_b_low: 5, prob_b_high: 1.0, domain: "gain" },
            // Problem 5: Medium probability gain
            { option_a_high: 20, option_a_low: 0, prob_a_high: 0.50, option_b_high: 10, option_b_low: 10, prob_b_high: 1.0, domain: "gain" },
            // Problem 6: High probability gain vs sure thing
            { option_a_high: 12, option_a_low: 0, prob_a_high: 0.90, option_b_high: 10, option_b_low: 10, prob_b_high: 1.0, domain: "gain" },
            // Problem 7: Rare big vs common small
            { option_a_high: 100, option_a_low: 0, prob_a_high: 0.05, option_b_high: 5, option_b_low: 5, prob_b_high: 1.0, domain: "gain" },

            // -- Loss domain: rare high-loss events --
            // Problem 8: A has rare big loss
            { option_a_high: 0, option_a_low: -32, prob_a_high: 0.90, option_b_high: -3, option_b_low: -3, prob_b_high: 1.0, domain: "loss" },
            // Problem 9: B has rare big loss
            { option_a_high: -4, option_a_low: -4, prob_a_high: 1.0, option_b_high: 0, option_b_low: -40, prob_b_high: 0.90, domain: "loss" },
            // Problem 10: Classic loss version
            { option_a_high: 0, option_a_low: -4, prob_a_high: 0.20, option_b_high: -3, option_b_low: -3, prob_b_high: 1.0, domain: "loss" },
            // Problem 11: Rare catastrophic loss
            { option_a_high: 0, option_a_low: -50, prob_a_high: 0.90, option_b_high: -5, option_b_low: -5, prob_b_high: 1.0, domain: "loss" },
            // Problem 12: Medium probability loss
            { option_a_high: 0, option_a_low: -20, prob_a_high: 0.50, option_b_high: -10, option_b_low: -10, prob_b_high: 1.0, domain: "loss" },
            // Problem 13: Mostly-loss vs sure loss
            { option_a_high: 0, option_a_low: -12, prob_a_high: 0.10, option_b_high: -10, option_b_low: -10, prob_b_high: 1.0, domain: "loss" },

            // -- Mixed domain --
            // Problem 14: Mixed with rare gain
            { option_a_high: 60, option_a_low: -5, prob_a_high: 0.10, option_b_high: 2, option_b_low: -2, prob_b_high: 0.50, domain: "mixed" },
            // Problem 15: Mixed balanced
            { option_a_high: 20, option_a_low: -10, prob_a_high: 0.50, option_b_high: 5, option_b_low: 5, prob_b_high: 1.0, domain: "mixed" },
            // Problem 16: Mixed with rare loss
            { option_a_high: 6, option_a_low: -60, prob_a_high: 0.90, option_b_high: 0, option_b_low: 0, prob_b_high: 1.0, domain: "mixed" },
            // Problem 17: Near-equal EVs, rare event in A
            { option_a_high: 30, option_a_low: -2, prob_a_high: 0.20, option_b_high: 4, option_b_low: 4, prob_b_high: 1.0, domain: "mixed" },

            // -- More gain domain with varied probabilities --
            // Problem 18: Two risky options
            { option_a_high: 25, option_a_low: 0, prob_a_high: 0.20, option_b_high: 10, option_b_low: 0, prob_b_high: 0.50, domain: "gain" },
            // Problem 19: High-prob moderate vs low-prob high
            { option_a_high: 8, option_a_low: 0, prob_a_high: 0.80, option_b_high: 32, option_b_low: 0, prob_b_high: 0.20, domain: "gain" },
            // Problem 20: Sure thing vs risky with same EV
            { option_a_high: 10, option_a_low: 10, prob_a_high: 1.0, option_b_high: 50, option_b_low: 0, prob_b_high: 0.20, domain: "gain" },
        ];

        // Compute EVs and rare_event_present for each problem
        for (var i = 0; i < problems.length; i++) {
            var p = problems[i];
            p.ev_a = Math.round((p.option_a_high * p.prob_a_high + p.option_a_low * (1 - p.prob_a_high)) * 100) / 100;
            p.ev_b = Math.round((p.option_b_high * p.prob_b_high + p.option_b_low * (1 - p.prob_b_high)) * 100) / 100;
            // Rare event present if any outcome probability <= 0.15
            p.rare_event_present =
                p.prob_a_high <= 0.15 ||
                (1 - p.prob_a_high) <= 0.15 ||
                p.prob_b_high <= 0.15 ||
                (1 - p.prob_b_high) <= 0.15;
            p.problem_number = i + 1;
        }

        // Shuffle
        for (var i = problems.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var tmp = problems[i];
            problems[i] = problems[j];
            problems[j] = tmp;
        }

        return problems;
    }

    // Sample from a distribution: returns high with prob p, low otherwise
    function sampleOutcome(high, low, probHigh) {
        return Math.random() < probHigh ? high : low;
    }

    function formatOutcome(amount) {
        if (amount > 0) {
            return '<span class="sample-outcome positive">+$' + amount + '</span>';
        } else if (amount < 0) {
            return '<span class="sample-outcome negative">-$' + Math.abs(amount) + '</span>';
        } else {
            return '<span class="sample-outcome zero">$0</span>';
        }
    }

    var allProblems = generateProblems();
    allProblems = allProblems.slice(0, CONFIG.n_problems);
    var timeline = [];

    // ---- Welcome ----
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Decisions from Experience</h1>" +
            "<p>Welcome to the decision-making task.</p>" +
            "<p>Press any key to begin.</p>",
    });

    // ---- Instructions ----
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>In this task, you will face a series of choice problems.</p>" +
            "<p>Each problem has two options: a <strong>Left Deck</strong> and a <strong>Right Deck</strong>.</p>" +
            "<p>Each deck gives different monetary outcomes with different probabilities.</p>" +
            "<p>You do <strong>not</strong> know the outcomes or probabilities in advance.</p>",

            "<h2>Sampling Phase</h2>" +
            "<p>Before making your final choice, you can <strong>sample</strong> from either deck " +
            "to learn what outcomes they produce.</p>" +
            '<div class="deck-container">' +
            '<div class="deck-box left"><div class="deck-label">Left Deck</div>?<div class="deck-key">F</div></div>' +
            '<div class="deck-box right"><div class="deck-label">Right Deck</div>?<div class="deck-key">J</div></div>' +
            '</div>' +
            "<p>Press <kbd>F</kbd> to draw a sample from the Left Deck.</p>" +
            "<p>Press <kbd>J</kbd> to draw a sample from the Right Deck.</p>" +
            "<p>Each sample shows you one possible outcome from that deck.</p>" +
            "<p>You can sample as many times as you like from either deck.</p>" +
            "<p>Sampling outcomes do <strong>not</strong> count toward your earnings.</p>",

            "<h2>Choice Phase</h2>" +
            "<p>When you are ready to decide, press <kbd>SPACE</kbd> to stop sampling.</p>" +
            "<p>You will then make your <strong>final choice</strong>:</p>" +
            "<p style='font-size:24px'><kbd>F</kbd> = Choose <strong>Left Deck</strong></p>" +
            "<p style='font-size:24px'><kbd>J</kbd> = Choose <strong>Right Deck</strong></p>" +
            "<p>The outcome of your final choice <strong>does</strong> count toward your earnings.</p>" +
            "<p>Try to maximize your total earnings across all problems.</p>",

            "<h2>Summary</h2>" +
            "<p>1. <strong>Sample</strong> from decks by pressing <kbd>F</kbd> (left) or <kbd>J</kbd> (right).</p>" +
            "<p>2. Press <kbd>SPACE</kbd> when you are ready to make your final choice.</p>" +
            "<p>3. <strong>Choose</strong> your preferred deck with <kbd>F</kbd> (left) or <kbd>J</kbd> (right).</p>" +
            "<p>There are " + CONFIG.n_problems + " problems. Press Next to begin.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    // ---- Build trials for each problem ----
    var trialCounter = 0;

    for (var pi = 0; pi < allProblems.length; pi++) {
        (function (problemIdx) {
            var problem = allProblems[problemIdx];

            // State for this problem's sampling phase
            var samplingState = {
                samples_a: 0,
                samples_b: 0,
                total_samples: 0,
                sample_history: [], // {deck, outcome, sample_number}
                last_sampled_deck: null,
                last_outcome: null,
                done_sampling: false,
            };

            // Fixation
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: '<div class="fixation">+</div>',
                choices: "NO_KEYS",
                trial_duration: CONFIG.fixation_duration,
                data: { trial_part: "fixation" },
            });

            // Problem start screen
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus:
                    '<div class="trial-counter">Problem ' + (problemIdx + 1) + ' of ' + CONFIG.n_problems + '</div>' +
                    '<div class="phase-label">Sampling Phase</div>' +
                    '<p>Press <kbd>F</kbd> or <kbd>J</kbd> to sample. Press <kbd>SPACE</kbd> when ready to choose.</p>' +
                    '<div class="deck-container">' +
                    '<div class="deck-box left"><div class="deck-label">Left Deck</div>?<div class="deck-key">F</div></div>' +
                    '<div class="deck-box right"><div class="deck-label">Right Deck</div>?<div class="deck-key">J</div></div>' +
                    '</div>',
                choices: ["f", "j", " "],
                data: { trial_part: "sample_start" },
                on_finish: function (data) {
                    if (data.response === " ") {
                        // Immediately stop sampling (0 samples)
                        samplingState.done_sampling = true;
                    } else if (data.response === "f") {
                        var outcome = sampleOutcome(problem.option_a_high, problem.option_a_low, problem.prob_a_high);
                        samplingState.samples_a++;
                        samplingState.total_samples++;
                        samplingState.last_sampled_deck = "a";
                        samplingState.last_outcome = outcome;
                        samplingState.sample_history.push({
                            deck: "a",
                            outcome: outcome,
                            sample_number: samplingState.total_samples,
                        });
                    } else if (data.response === "j") {
                        var outcome = sampleOutcome(problem.option_b_high, problem.option_b_low, problem.prob_b_high);
                        samplingState.samples_b++;
                        samplingState.total_samples++;
                        samplingState.last_sampled_deck = "b";
                        samplingState.last_outcome = outcome;
                        samplingState.sample_history.push({
                            deck: "b",
                            outcome: outcome,
                            sample_number: samplingState.total_samples,
                        });
                    }
                },
            });

            // Sample feedback (shows outcome, loops back)
            var sampleFeedback = {
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    if (samplingState.last_outcome === null) {
                        return "";
                    }
                    var deckName = samplingState.last_sampled_deck === "a" ? "Left" : "Right";
                    return '<div class="trial-counter">Problem ' + (problemIdx + 1) + ' of ' + CONFIG.n_problems + '</div>' +
                        '<div class="phase-label">Sample from ' + deckName + ' Deck</div>' +
                        '<div>' + formatOutcome(samplingState.last_outcome) + '</div>' +
                        '<div class="sample-counter">Samples: Left=' + samplingState.samples_a + ' Right=' + samplingState.samples_b + '</div>';
                },
                choices: "NO_KEYS",
                trial_duration: function () {
                    if (samplingState.done_sampling) return 0;
                    return CONFIG.feedback_duration;
                },
                data: { trial_part: "sample_feedback" },
                on_finish: function (data) {
                    // Record sample data
                    if (samplingState.last_sampled_deck !== null && !samplingState.done_sampling) {
                        var lastSample = samplingState.sample_history[samplingState.sample_history.length - 1];
                        data.trial_part = "sample";
                        data.problem_number = problem.problem_number;
                        data.sampled_deck = samplingState.last_sampled_deck;
                        data.outcome_seen = lastSample.outcome;
                        data.sample_number = lastSample.sample_number;
                    }
                },
            };

            // Next sample prompt (press F/J to sample more, SPACE to choose)
            var samplePrompt = {
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    if (samplingState.done_sampling) return "";
                    return '<div class="trial-counter">Problem ' + (problemIdx + 1) + ' of ' + CONFIG.n_problems + '</div>' +
                        '<div class="phase-label">Sampling Phase</div>' +
                        '<p>Press <kbd>F</kbd> or <kbd>J</kbd> to sample. Press <kbd>SPACE</kbd> to choose.</p>' +
                        '<div class="deck-container">' +
                        '<div class="deck-box left"><div class="deck-label">Left Deck</div>' +
                        (samplingState.samples_a > 0 ? '<div style="font-size:16px;color:#888;">' + samplingState.samples_a + ' samples</div>' : '?') +
                        '<div class="deck-key">F</div></div>' +
                        '<div class="deck-box right"><div class="deck-label">Right Deck</div>' +
                        (samplingState.samples_b > 0 ? '<div style="font-size:16px;color:#888;">' + samplingState.samples_b + ' samples</div>' : '?') +
                        '<div class="deck-key">J</div></div>' +
                        '</div>' +
                        '<div class="sample-counter">Total samples: ' + samplingState.total_samples + '</div>';
                },
                choices: ["f", "j", " "],
                trial_duration: function () {
                    if (samplingState.done_sampling) return 0;
                    return null; // No deadline during sampling
                },
                data: { trial_part: "sample_prompt" },
                on_finish: function (data) {
                    if (data.response === " ") {
                        samplingState.done_sampling = true;
                    } else if (data.response === "f") {
                        var outcome = sampleOutcome(problem.option_a_high, problem.option_a_low, problem.prob_a_high);
                        samplingState.samples_a++;
                        samplingState.total_samples++;
                        samplingState.last_sampled_deck = "a";
                        samplingState.last_outcome = outcome;
                        samplingState.sample_history.push({
                            deck: "a",
                            outcome: outcome,
                            sample_number: samplingState.total_samples,
                        });
                    } else if (data.response === "j") {
                        var outcome = sampleOutcome(problem.option_b_high, problem.option_b_low, problem.prob_b_high);
                        samplingState.samples_b++;
                        samplingState.total_samples++;
                        samplingState.last_sampled_deck = "b";
                        samplingState.last_outcome = outcome;
                        samplingState.sample_history.push({
                            deck: "b",
                            outcome: outcome,
                            sample_number: samplingState.total_samples,
                        });
                    }
                },
            };

            // Sampling loop: feedback then prompt, loop until done
            var samplingLoop = {
                timeline: [sampleFeedback, samplePrompt],
                loop_function: function () {
                    return !samplingState.done_sampling;
                },
            };

            timeline.push(samplingLoop);

            // ---- Choice phase ----
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    return '<div class="trial-counter">Problem ' + (problemIdx + 1) + ' of ' + CONFIG.n_problems + '</div>' +
                        '<div class="phase-label">Final Choice</div>' +
                        '<p>Which deck do you choose for your <strong>final</strong> decision?</p>' +
                        '<div class="deck-container">' +
                        '<div class="deck-box left"><div class="deck-label">Left Deck</div>' +
                        '<div style="font-size:16px;color:#888;">' + samplingState.samples_a + ' samples</div>' +
                        '<div class="deck-key">F</div></div>' +
                        '<div class="deck-box right"><div class="deck-label">Right Deck</div>' +
                        '<div style="font-size:16px;color:#888;">' + samplingState.samples_b + ' samples</div>' +
                        '<div class="deck-key">J</div></div>' +
                        '</div>' +
                        '<div class="choice-prompt"><kbd>F</kbd> = Left &nbsp;&nbsp;&nbsp; <kbd>J</kbd> = Right</div>';
                },
                choices: CONFIG.valid_keys,
                trial_duration: CONFIG.response_deadline,
                data: {
                    trial_part: "stimulus",
                    problem_number: problem.problem_number,
                    option_a_high: problem.option_a_high,
                    option_a_low: problem.option_a_low,
                    prob_a_high: problem.prob_a_high,
                    option_b_high: problem.option_b_high,
                    option_b_low: problem.option_b_low,
                    prob_b_high: problem.prob_b_high,
                    ev_a: problem.ev_a,
                    ev_b: problem.ev_b,
                    domain: problem.domain,
                    rare_event_present: problem.rare_event_present,
                },
                on_finish: function (data) {
                    trialCounter++;
                    data.trial_index = trialCounter;
                    data.timed_out = data.response === null;

                    data.samples_a = samplingState.samples_a;
                    data.samples_b = samplingState.samples_b;
                    data.total_samples = samplingState.total_samples;

                    if (!data.timed_out) {
                        var choseLeft = data.response === "f";
                        data.chose_a = choseLeft;
                        data.chose_b = !choseLeft;

                        // Did they choose the higher EV option?
                        if (data.ev_a > data.ev_b) {
                            data.chose_higher_ev = choseLeft;
                        } else if (data.ev_b > data.ev_a) {
                            data.chose_higher_ev = !choseLeft;
                        } else {
                            // Equal EVs: either is correct
                            data.chose_higher_ev = true;
                        }
                    } else {
                        data.chose_a = false;
                        data.chose_b = false;
                        data.chose_higher_ev = false;
                    }

                    data.chose_higher_ev_num = data.chose_higher_ev ? 1 : 0;

                    // Frugal sampling: total_samples < 15
                    data.frugal_sampling = data.total_samples < 15;

                    // Recency: did the last sample come from the chosen deck?
                    if (samplingState.sample_history.length > 0 && !data.timed_out) {
                        var lastSample = samplingState.sample_history[samplingState.sample_history.length - 1];
                        var chosenDeck = data.chose_a ? "a" : "b";
                        data.last_sample_match = lastSample.deck === chosenDeck ? 1 : 0;
                    } else {
                        data.last_sample_match = 0;
                    }
                },
            });

            // Choice feedback
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    var lastTrial = jsPsych.data.get().last(1).values()[0];
                    if (lastTrial.timed_out) {
                        return '<div class="sample-outcome negative">Too slow! No choice recorded.</div>';
                    }
                    var chosenDeck = lastTrial.chose_a ? "Left" : "Right";
                    // Draw from chosen distribution
                    var outcome;
                    if (lastTrial.chose_a) {
                        outcome = sampleOutcome(problem.option_a_high, problem.option_a_low, problem.prob_a_high);
                    } else {
                        outcome = sampleOutcome(problem.option_b_high, problem.option_b_low, problem.prob_b_high);
                    }
                    return '<div class="phase-label">You chose: ' + chosenDeck + ' Deck</div>' +
                        '<div>Outcome: ' + formatOutcome(outcome) + '</div>';
                },
                choices: "NO_KEYS",
                trial_duration: CONFIG.feedback_duration,
                data: { trial_part: "choice_feedback" },
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

        })(pi);
    }

    // ---- Data submission ----
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

    // ---- End screen ----
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Task Complete</h2>" +
            "<p>Thank you for completing the Decisions from Experience task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
