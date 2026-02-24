(function () {
    var CONFIG = {
        n_back_level: 2,
        n_blocks: 5,
        trials_per_block: 24,
        target_proportion: 0.30,
        lure_proportion: 0.10,
        letters: ["B", "C", "D", "F", "G", "H", "J", "K", "L", "M"],
        valid_keys: ["f", "j"],
        match_key: "f",
        nonmatch_key: "j",
        stimulus_duration: 1500,
        isi_duration: 500,
        fixation_duration: 500,
        feedback_duration: 1000,
        n_practice: 12,
    };
    CONFIG.stimulus_duration = getTrialDuration(CONFIG.stimulus_duration);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "n_back";

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    function generateSequence(nTrials, targetProp, lureProp) {
        var nTargets = Math.round(nTrials * targetProp);
        var nLures = Math.round(nTrials * lureProp);
        var sequence = [];
        var isTarget = new Array(nTrials).fill(false);
        var isLure = new Array(nTrials).fill(false);

        for (var i = 0; i < CONFIG.n_back_level; i++) {
            sequence.push(CONFIG.letters[Math.floor(Math.random() * CONFIG.letters.length)]);
        }

        var targetPositions = [];
        var lurePositions = [];
        var availablePositions = [];
        for (var p = CONFIG.n_back_level; p < nTrials; p++) {
            availablePositions.push(p);
        }

        for (var s = availablePositions.length - 1; s > 0; s--) {
            var si = Math.floor(Math.random() * (s + 1));
            var tmp = availablePositions[s];
            availablePositions[s] = availablePositions[si];
            availablePositions[si] = tmp;
        }

        var tidx = 0;
        for (var t = 0; t < Math.min(nTargets, availablePositions.length); t++) {
            targetPositions.push(availablePositions[tidx]);
            isTarget[availablePositions[tidx]] = true;
            tidx++;
        }

        var luresAdded = 0;
        while (tidx < availablePositions.length && luresAdded < nLures) {
            var pos = availablePositions[tidx];
            if (!isTarget[pos]) {
                lurePositions.push(pos);
                isLure[pos] = true;
                luresAdded++;
            }
            tidx++;
        }

        for (var i = CONFIG.n_back_level; i < nTrials; i++) {
            if (isTarget[i]) {
                sequence.push(sequence[i - CONFIG.n_back_level]);
            } else if (isLure[i]) {
                var nBackLetter = sequence[i - CONFIG.n_back_level];
                var lureLetter;
                if (i >= 1 && Math.random() > 0.5) {
                    lureLetter = sequence[i - 1];
                } else if (i >= 3) {
                    lureLetter = sequence[i - 3];
                } else {
                    lureLetter = sequence[i - 1];
                }
                if (lureLetter === nBackLetter) {
                    var others = CONFIG.letters.filter(function (l) { return l !== nBackLetter; });
                    lureLetter = others[Math.floor(Math.random() * others.length)];
                }
                sequence.push(lureLetter);
            } else {
                var nBackLetter2 = sequence[i - CONFIG.n_back_level];
                var letter;
                do {
                    letter = CONFIG.letters[Math.floor(Math.random() * CONFIG.letters.length)];
                } while (letter === nBackLetter2);
                sequence.push(letter);
            }
        }

        var result = [];
        for (var i = 0; i < nTrials; i++) {
            result.push({
                stimulus: sequence[i],
                n_back_match: isTarget[i],
                is_lure: isLure[i],
            });
        }
        return result;
    }

    var timeline = [];

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>N-Back Task (2-Back)</h1>" +
            "<p>Welcome to the working memory task.</p>" +
            "<p>Press any key to begin.</p>",
    });

    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>You will see a series of letters appear one at a time.</p>" +
            "<p>Your job is to decide if the current letter is the <strong>same</strong> as " +
            "the letter shown <strong>2 trials ago</strong>.</p>" +
            "<p>This is called a <strong>2-back</strong> task.</p>",

            "<h2>Example</h2>" +
            '<div class="example-sequence">' +
            '<span class="example-normal">B</span> ' +
            '<span class="example-normal">D</span> ' +
            '<span class="example-match">B</span> ' +
            '<span class="example-normal">K</span> ' +
            '<span class="example-match">D</span> ' +
            '<span class="example-normal">F</span> ' +
            "</div>" +
            "<p>The 3rd letter (B) matches the 1st letter (B) — that's 2 back. <strong>Match!</strong></p>" +
            "<p>The 5th letter (D) matches the 3rd letter — wait, the 3rd is B. Actually D matches the 2nd letter (D) going 3 back... Let me redo:</p>" +
            '<div class="example-sequence">' +
            '<span class="example-normal">B</span> ' +
            '<span class="example-normal">D</span> ' +
            '<span class="example-match">B</span> ' +
            '<span class="example-normal">K</span> ' +
            '<span class="example-normal">F</span> ' +
            '<span class="example-match">K</span> ' +
            "</div>" +
            "<p>Position 3: B = position 1 (B). <strong>Match!</strong></p>" +
            "<p>Position 6: K = position 4 (K). <strong>Match!</strong></p>",

            "<h2>Response Keys</h2>" +
            "<p style='font-size:28px'><kbd>F</kbd> = <strong>Match</strong> (same as 2 back)</p>" +
            "<p style='font-size:28px'><kbd>J</kbd> = <strong>No Match</strong> (different)</p>" +
            "<p>Respond while the letter is on screen." + (CONFIG.stimulus_duration ? " You have " + (CONFIG.stimulus_duration / 1000) + " seconds." : "") + "</p>" +
            "<p>Press Next to start " + CONFIG.n_practice + " practice trials with feedback.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    var practiceSeq = generateSequence(CONFIG.n_practice, CONFIG.target_proportion, 0);

    practiceSeq.forEach(function (item, idx) {
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
                '<div class="nback-stimulus">' + item.stimulus + "</div>" +
                '<div class="nback-prompt">F = Match | J = No Match</div>',
            choices: CONFIG.valid_keys,
            trial_duration: CONFIG.stimulus_duration,
            data: {
                trial_part: "practice",
                stimulus: item.stimulus,
                n_back_match: item.n_back_match,
                is_lure: item.is_lure,
            },
            on_finish: function (data) {
                data.timed_out = data.response === null;
                if (data.timed_out) {
                    data.correct = false;
                } else if (data.n_back_match) {
                    data.correct = data.response === CONFIG.match_key;
                } else {
                    data.correct = data.response === CONFIG.nonmatch_key;
                }
            },
        });

        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                var last = jsPsych.data.get().last(1).values()[0];
                if (last.timed_out) {
                    return '<p class="feedback" style="color:orange;">Too slow!</p>';
                } else if (last.correct) {
                    return '<p class="feedback" style="color:green;">Correct!</p>';
                } else {
                    var expected = last.n_back_match ? "Match (F)" : "No Match (J)";
                    return '<p class="feedback" style="color:red;">Incorrect. Answer was: ' + expected + "</p>";
                }
            },
            choices: "NO_KEYS",
            trial_duration: CONFIG.feedback_duration,
            data: { trial_part: "feedback" },
        });

        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: "",
            choices: "NO_KEYS",
            trial_duration: CONFIG.isi_duration,
            data: { trial_part: "isi" },
        });
    });

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>End of Practice</h2>" +
            "<p>The main experiment will now begin.</p>" +
            "<p>There are " + CONFIG.n_blocks + " blocks of " + CONFIG.trials_per_block + " trials.</p>" +
            "<p>No more feedback will be given.</p>" +
            "<p>Press any key to start.</p>",
    });

    var trialCounter = 0;
    for (var block = 0; block < CONFIG.n_blocks; block++) {
        var blockSeq = generateSequence(CONFIG.trials_per_block, CONFIG.target_proportion, CONFIG.lure_proportion);

        (function (blockNum, seq) {
            seq.forEach(function (item) {
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
                        '<div class="nback-stimulus">' + item.stimulus + "</div>" +
                        '<div class="nback-prompt">F = Match | J = No Match</div>',
                    choices: CONFIG.valid_keys,
                    trial_duration: CONFIG.stimulus_duration,
                    data: {
                        trial_part: "stimulus",
                        block: blockNum,
                        stimulus: item.stimulus,
                        n_back_match: item.n_back_match,
                        is_lure: item.is_lure,
                    },
                    on_finish: function (data) {
                        trialCounter++;
                        data.trial_index = trialCounter;
                        data.timed_out = data.response === null;

                        if (data.timed_out) {
                            data.correct = false;
                            data.hit = false;
                            data.miss = data.n_back_match;
                            data.false_alarm = false;
                            data.correct_rejection = !data.n_back_match;
                        } else if (data.n_back_match) {
                            data.correct = data.response === CONFIG.match_key;
                            data.hit = data.correct;
                            data.miss = !data.correct;
                            data.false_alarm = false;
                            data.correct_rejection = false;
                        } else {
                            data.correct = data.response === CONFIG.nonmatch_key;
                            data.hit = false;
                            data.miss = false;
                            data.false_alarm = data.response === CONFIG.match_key;
                            data.correct_rejection = data.response === CONFIG.nonmatch_key;
                        }
                    },
                });

                timeline.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: "",
                    choices: "NO_KEYS",
                    trial_duration: CONFIG.isi_duration,
                    data: { trial_part: "isi" },
                });
            });
        })(block + 1, blockSeq);

        if (block < CONFIG.n_blocks - 1) {
            (function (b) {
                timeline.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus:
                        "<h2>Block " + (b + 1) + " of " + CONFIG.n_blocks + " complete</h2>" +
                        "<p>Take a short break if needed.</p>" +
                        "<p>Press any key to continue.</p>",
                });
            })(block);
        }
    }

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
            "<p>Thank you for completing the N-Back task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
