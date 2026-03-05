(function () {
    var CONFIG = {
        n_trials: 120,
        valid_keys: ["f", "j"],
        response_deadline: 3000,
        fixation_duration: 500,
        feedback_duration: 800,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "lexical_decision";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) CONFIG.n_trials = _nto;

    var jsPsych = initJsPsych({ experiment_width: 800, minimum_valid_rt: 100 });
    if (SESSION_ID === "debug") window._jsPsych = jsPsych;

    // Word lists
    var HIGH_FREQ_WORDS = ["table", "house", "water", "money", "light", "world", "place", "think", "state", "after",
        "child", "point", "story", "night", "group", "study", "power", "music", "small", "young",
        "heart", "field", "paper", "human", "south", "order", "woman", "class", "party", "plant"];
    var LOW_FREQ_WORDS = ["plumb", "glyph", "trove", "fjord", "knoll", "qualm", "girth", "demur", "guise", "shawl",
        "arbor", "cleft", "droit", "haven", "plait", "stoic", "feint", "wraith", "caulk", "psalm",
        "epoch", "prism", "tithe", "rogue", "brine", "dirge", "swath", "inert", "abode", "creed"];
    var NONWORDS = ["flirp", "glomb", "snarp", "brive", "clunt", "drafe", "spalk", "trund", "pleck", "grish",
        "bloft", "crend", "dwine", "frult", "glape", "knorp", "preft", "slank", "twibe", "vrand",
        "brisk", "clund", "drelm", "flonk", "grelt", "hwerp", "jilpt", "kwend", "mroft", "nulth"];

    function generateTrials() {
        var trials = [];
        var half = Math.floor(CONFIG.n_trials / 2);
        var wordTrials = Math.ceil(half / 2);

        for (var i = 0; i < wordTrials && trials.length < half; i++) {
            trials.push({ stimulus: HIGH_FREQ_WORDS[i % HIGH_FREQ_WORDS.length], stimulus_type: "word", word_frequency: "high" });
        }
        for (var j = 0; j < wordTrials && trials.length < half; j++) {
            trials.push({ stimulus: LOW_FREQ_WORDS[j % LOW_FREQ_WORDS.length], stimulus_type: "word", word_frequency: "low" });
        }
        for (var k = 0; k < CONFIG.n_trials - half; k++) {
            trials.push({ stimulus: NONWORDS[k % NONWORDS.length], stimulus_type: "nonword", word_frequency: "none" });
        }

        for (var m = trials.length - 1; m > 0; m--) {
            var n = Math.floor(Math.random() * (m + 1));
            var tmp = trials[m]; trials[m] = trials[n]; trials[n] = tmp;
        }
        return trials;
    }

    var allTrials = generateTrials();
    var timeline = [];

    timeline.push({ type: jsPsychHtmlKeyboardResponse, stimulus: "<h1>Lexical Decision</h1><p>Press any key to begin.</p>" });
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2><p>You will see a string of letters on each trial.</p><p>Decide as quickly as possible whether it is a <strong>real English word</strong> or a <strong>nonword</strong>.</p>",
            "<h2>Response Keys</h2><p style='font-size:28px'><kbd>F</kbd> = <strong>WORD</strong> (real English word)</p><p style='font-size:28px'><kbd>J</kbd> = <strong>NONWORD</strong> (not a real word)</p><p>Be fast and accurate!</p><p>Press Next to start.</p>",
        ],
        show_clickable_nav: true, button_label_next: "Next", button_label_previous: "Previous",
    });

    var trialCounter = 0;
    for (var ti = 0; ti < allTrials.length; ti++) {
        (function (trial) {
            timeline.push({ type: jsPsychHtmlKeyboardResponse, stimulus: '<div class="fixation">+</div>', choices: "NO_KEYS", trial_duration: CONFIG.fixation_duration, data: { trial_part: "fixation" } });

            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: '<div class="trial-counter">Trial ' + (trialCounter + 1) + ' of ' + CONFIG.n_trials + '</div>' +
                    '<div class="word-display">' + trial.stimulus.toUpperCase() + '</div>' +
                    '<div class="response-options">' +
                    '<div class="response-box">WORD<div class="key-hint">F</div></div>' +
                    '<div class="response-box">NONWORD<div class="key-hint">J</div></div></div>',
                choices: CONFIG.valid_keys,
                trial_duration: CONFIG.response_deadline,
                data: { trial_part: "stimulus", stimulus: trial.stimulus, stimulus_type: trial.stimulus_type, word_frequency: trial.word_frequency },
                on_finish: function (data) {
                    trialCounter++;
                    data.trial_index = trialCounter;
                    data.timed_out = data.response === null;
                    if (!data.timed_out) {
                        var judgedWord = data.response === "f";
                        data.correct = (judgedWord && trial.stimulus_type === "word") || (!judgedWord && trial.stimulus_type === "nonword");
                    } else {
                        data.correct = false;
                    }
                },
            });

            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    var last = jsPsych.data.get().last(1).values()[0];
                    if (last.timed_out) return '<div class="feedback-incorrect">Too slow!</div>';
                    return last.correct ? '<div class="feedback-correct">\u2714 Correct!</div>' : '<div class="feedback-incorrect">\u2718 Wrong</div>';
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
