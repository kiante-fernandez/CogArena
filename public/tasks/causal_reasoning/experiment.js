(function () {
    var CONFIG = {
        n_trials: 150,
        n_blocks: 3,
        trials_per_block: 50,
        valid_keys: ["f", "j"],
        response_deadline: 8000,
        fixation_duration: 500,
        feedback_duration: 1200,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "causal_reasoning";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.n_trials = _nto;
        CONFIG.trials_per_block = Math.ceil(_nto / CONFIG.n_blocks);
    }

    var jsPsych = initJsPsych({ experiment_width: 800, minimum_valid_rt: 100 });
    if (SESSION_ID === "debug") window._jsPsych = jsPsych;

    // Territory conditions (hidden agents)
    var CONDITIONS = [
        { name: "robber", agent: "Robber", description: "sometimes replaces gold with rocks in BOTH mines", intervention_rate: 0.3, both_affected: true, agent_outcome: "rocks" },
        { name: "millionaire", agent: "Millionaire", description: "sometimes puts gold in BOTH mines", intervention_rate: 0.3, both_affected: true, agent_outcome: "gold" },
        { name: "sheriff", agent: "Sheriff", description: "sometimes randomly swaps outcomes between mines", intervention_rate: 0.3, both_affected: false, agent_outcome: "random" },
    ];

    // Mine reward probabilities (base rates without agent intervention)
    var MINE_PROBS = [0.7, 0.3]; // Mine A better than Mine B

    function generateTrials() {
        var trials = [];
        // Shuffle condition order
        var condOrder = [0, 1, 2];
        for (var i = condOrder.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var tmp = condOrder[i]; condOrder[i] = condOrder[j]; condOrder[j] = tmp;
        }

        for (var b = 0; b < CONFIG.n_blocks; b++) {
            var cond = CONDITIONS[condOrder[b]];
            for (var t = 0; t < CONFIG.trials_per_block; t++) {
                var agentActive = Math.random() < cond.intervention_rate;

                // Base outcomes for each mine
                var mine_a_gold = Math.random() < MINE_PROBS[0];
                var mine_b_gold = Math.random() < MINE_PROBS[1];

                if (agentActive) {
                    if (cond.name === "robber") {
                        mine_a_gold = false;
                        mine_b_gold = false;
                    } else if (cond.name === "millionaire") {
                        mine_a_gold = true;
                        mine_b_gold = true;
                    } else {
                        // Sheriff swaps randomly
                        var temp = mine_a_gold;
                        mine_a_gold = mine_b_gold;
                        mine_b_gold = temp;
                    }
                }

                trials.push({
                    block: b,
                    condition: cond.name,
                    trial_in_block: t,
                    agent_active: agentActive,
                    mine_a_gold: mine_a_gold,
                    mine_b_gold: mine_b_gold,
                });
            }
        }
        return trials;
    }

    var allTrials = generateTrials();
    var timeline = [];

    timeline.push({ type: jsPsychHtmlKeyboardResponse, stimulus: "<h1>Mining Task</h1><p>Press any key to begin.</p>" });
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2><p>You are a miner exploring different territories.</p><p>Each territory has two mines. On each trial, you choose one mine to dig in.</p><p>You'll find either <strong style='color:#DAA520'>Gold</strong> or <strong style='color:#808080'>Rocks</strong>.</p>",
            "<h2>Hidden Agents</h2><p>Each territory has a hidden agent who sometimes intervenes:</p><ul style='text-align:left'><li>One agent replaces gold with rocks</li><li>Another puts gold in both mines</li><li>Another swaps outcomes randomly</li></ul><p>Try to learn which mine is better AND when the agent is active.</p>",
            "<h2>Response Keys</h2><p style='font-size:28px'><kbd>F</kbd> = <strong>Left Mine</strong></p><p style='font-size:28px'><kbd>J</kbd> = <strong>Right Mine</strong></p><p>Press Next to start.</p>",
        ],
        show_clickable_nav: true, button_label_next: "Next", button_label_previous: "Previous",
    });

    var trialCounter = 0;
    var prevBlock = -1;

    for (var ti = 0; ti < allTrials.length; ti++) {
        (function (trial) {
            if (trial.block !== prevBlock) {
                var cond = CONDITIONS.find(function (c) { return c.name === trial.condition; });
                timeline.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: '<h2>Territory ' + (trial.block + 1) + ' of ' + CONFIG.n_blocks + '</h2>' +
                        '<p>A new territory! There is a hidden agent here.</p>' +
                        '<p>Try to learn the mines and detect when the agent intervenes.</p>' +
                        '<p>Press any key to start.</p>',
                });
                prevBlock = trial.block;
            }

            timeline.push({ type: jsPsychHtmlKeyboardResponse, stimulus: '<div class="fixation">+</div>', choices: "NO_KEYS", trial_duration: CONFIG.fixation_duration, data: { trial_part: "fixation" } });

            // Mine choice
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: '<div class="trial-counter">Trial ' + (trialCounter + 1) + ' of ' + CONFIG.n_trials + '</div>' +
                    '<div class="territory-label">Territory ' + (trial.block + 1) + ' (' + trial.condition + ')</div>' +
                    '<div class="mine-container">' +
                    '<div class="mine-box"><div class="mine-label">\u26CF Mine A</div><div class="key-hint">F</div></div>' +
                    '<div class="mine-box"><div class="mine-label">\u26CF Mine B</div><div class="key-hint">J</div></div>' +
                    '</div>',
                choices: CONFIG.valid_keys,
                trial_duration: CONFIG.response_deadline,
                data: {
                    trial_part: "stimulus",
                    block: trial.block,
                    condition: trial.condition,
                    trial_in_block: trial.trial_in_block,
                    agent_active: trial.agent_active,
                    mine_a_gold: trial.mine_a_gold,
                    mine_b_gold: trial.mine_b_gold,
                },
                on_finish: function (data) {
                    trialCounter++;
                    data.trial_index = trialCounter;
                    data.timed_out = data.response === null;
                    if (!data.timed_out) {
                        data.choice = data.response === "f" ? "A" : "B";
                        data.feedback = data.choice === "A" ? data.mine_a_gold : data.mine_b_gold;
                        data.correct = data.feedback; // Finding gold = correct
                        // Better mine is A (0.7 base prob)
                        data.chose_better_mine = data.choice === "A";
                    } else {
                        data.choice = null;
                        data.feedback = false;
                        data.correct = false;
                        data.chose_better_mine = false;
                    }
                },
            });

            // Feedback: gold or rocks
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    var last = jsPsych.data.get().last(1).values()[0];
                    if (last.timed_out) return '<div class="feedback-incorrect">Too slow!</div>';
                    return last.feedback
                        ? '<div class="feedback-gold">\u2B50 Gold!</div>'
                        : '<div class="feedback-rocks">\u26AA Rocks</div>';
                },
                choices: "NO_KEYS", trial_duration: CONFIG.feedback_duration, data: { trial_part: "feedback" },
            });
        })(allTrials[ti]);
    }

    timeline.push({ type: jsPsychCallFunction, async: true, func: function (done) {
        var trial_data = jsPsych.data.get().filter({ trial_part: "stimulus" }).values();
        fetch("/api/data/" + SESSION_ID + "/" + TASK_ID, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ trial_data: trial_data, metadata: { task_id: TASK_ID, session_id: SESSION_ID, total_time_ms: jsPsych.getTotalTime(), n_trials: trial_data.length } }) })
            .then(function (r) { done(); }).catch(function (e) { console.error(e); done(); });
    }});

    timeline.push({ type: jsPsychHtmlKeyboardResponse, stimulus: "<h2>Task Complete</h2><p>Your data has been submitted.</p>", choices: "NO_KEYS", trial_duration: 3000 });
    jsPsych.run(timeline);
})();
