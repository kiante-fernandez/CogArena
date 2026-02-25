(function () {
    var CONFIG = {
        n_lists: 10,
        list_length: 12,
        presentation_duration: 1000,
        isi: 250,
        recall_timeout: 60000,
        valid_keys: [],
        response_type: "button",
    };
    CONFIG.recall_timeout = getTrialDuration(CONFIG.recall_timeout);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "serial_recall";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.n_lists = _nto;
    }

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    // Word pool: 120+ common concrete nouns
    var WORD_POOL = [
        "APPLE", "CHAIR", "RIVER", "CLOCK", "BREAD", "HOUSE", "TIGER", "BEACH",
        "KNIFE", "PIANO", "EAGLE", "BRIDGE", "CANDY", "DRESS", "FLAME", "GLOBE",
        "HORSE", "JUICE", "LEMON", "MOUSE", "NURSE", "OCEAN", "PEARL", "QUEEN",
        "ROBIN", "SNAKE", "TOWER", "UNCLE", "VIOLIN", "WHALE", "BRICK", "CLOUD",
        "DANCE", "FAIRY", "GRASS", "HEART", "IVORY", "JEWEL", "KNEEL", "LODGE",
        "MAPLE", "NOVEL", "OLIVE", "PLANE", "QUILT", "ROSES", "STORM", "TRUCK",
        "ANGEL", "BASIN", "CAMEL", "DELTA", "ELBOW", "FROST", "GRAIN", "HAVEN",
        "INBOX", "JELLY", "KITE", "LASER", "MEDAL", "NORTH", "ORBIT", "PATCH",
        "RANCH", "SHELF", "TABLE", "VAULT", "WAGON", "YACHT", "BADGE", "CORAL",
        "DIARY", "FENCE", "GRAPE", "HONEY", "IGLOO", "JUDGE", "KAYAK", "LLAMA",
        "MOOSE", "NERVE", "ONION", "PENNY", "RADAR", "SALAD", "THUMB", "URBAN",
        "WATER", "ZEBRA", "ARROW", "BOOTS", "CEDAR", "DONOR", "EPOCH", "FLASK",
        "GIANT", "HIKER", "IMAGE", "JOINT", "KNOTS", "LIVER", "MANGO", "NIGHT",
        "OPERA", "PIXEL", "RIDER", "SPOON", "TOOTH", "VALVE", "WOODS", "ALARM",
        "BLOOM", "CRANE", "DRIFT", "EMBER", "FORGE", "GRILL", "HATCH", "INDEX",
        "LINEN", "MARSH", "OASIS", "PRISM"
    ];

    // Shuffle helper (Fisher-Yates)
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

    // Draw words without replacement across all lists
    var totalWords = (CONFIG.n_lists + 1) * CONFIG.list_length; // +1 for practice
    var shuffledPool = shuffle(WORD_POOL);
    if (shuffledPool.length < totalWords) {
        // Double the pool if needed (should not happen with 132 words and 132 needed)
        shuffledPool = shuffle(WORD_POOL.concat(WORD_POOL));
    }
    var wordIndex = 0;

    function drawList() {
        var list = [];
        for (var i = 0; i < CONFIG.list_length; i++) {
            list.push(shuffledPool[wordIndex]);
            wordIndex++;
        }
        return list;
    }

    var timeline = [];

    // Welcome
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Serial Recall Task</h1>" +
            "<p>Welcome to the memory task.</p>" +
            "<p>Press any key to begin.</p>",
    });

    // Instructions
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>In this task, you will study lists of <strong>" + CONFIG.list_length + " words</strong>.</p>" +
            "<p>Each word will appear on screen one at a time.</p>" +
            "<p>Try to remember the words <strong>and the order</strong> in which they appeared.</p>",

            "<h2>Recall Phase</h2>" +
            "<p>After each list, all " + CONFIG.list_length + " words will appear as buttons in a shuffled order.</p>" +
            "<p>Click the words in the <strong>same order</strong> you saw them.</p>" +
            "<p>Selected words will be dimmed so you can see which ones you have already chosen.</p>" +
            "<p>Click the <strong>Done</strong> button when you are finished recalling.</p>",

            "<h2>Ready?</h2>" +
            "<p>First, you will do 1 practice list to get familiar with the task.</p>" +
            "<p>Then there will be " + CONFIG.n_lists + " main lists.</p>" +
            "<p>Click Next to start the practice.</p>"
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    // --- Helper: build encoding + recall trials for one list ---
    function buildListTrials(wordList, listNum, isPractice) {
        var trials = [];

        // "Get ready" screen
        trials.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus:
                '<div class="list-counter">' +
                (isPractice ? "Practice List" : "List " + listNum + " of " + CONFIG.n_lists) +
                '</div>' +
                '<p style="font-size:24px">Get ready...</p>',
            choices: "NO_KEYS",
            trial_duration: 2000,
            data: { trial_part: "get_ready" },
        });

        // Encoding phase: present each word one at a time
        for (var w = 0; w < wordList.length; w++) {
            (function (word, position) {
                // Word presentation
                trials.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: '<div class="word-display">' + word + '</div>',
                    choices: "NO_KEYS",
                    trial_duration: CONFIG.presentation_duration,
                    data: { trial_part: "encoding", word: word, serial_position: position + 1 },
                });

                // ISI (blank screen between words)
                trials.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: '<div class="fixation">+</div>',
                    choices: "NO_KEYS",
                    trial_duration: CONFIG.isi,
                    data: { trial_part: "isi" },
                });
            })(wordList[w], w);
        }

        // Recall phase: custom trial using call-function to build interactive recall
        var recallOrder = [];
        var recallStartTime = null;

        trials.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                recallOrder = [];
                recallStartTime = performance.now();
                var shuffledWords = shuffle(wordList);

                var html = '<div class="list-counter">' +
                    (isPractice ? "Practice List" : "List " + listNum + " of " + CONFIG.n_lists) +
                    '</div>';
                html += '<div class="recall-prompt">Click the words in the order you saw them:</div>';
                html += '<div class="recall-grid" id="recall-grid">';
                for (var i = 0; i < shuffledWords.length; i++) {
                    html += '<button class="recall-btn" data-word="' + shuffledWords[i] +
                        '" onclick="window._recallClick(this)">' + shuffledWords[i] + '</button>';
                }
                html += '</div>';
                html += '<div class="recall-order" id="recall-order-display">Your order: (click words above)</div>';
                html += '<button class="done-btn" onclick="window._recallDone()">Done</button>';

                return html;
            },
            choices: "NO_KEYS",
            trial_duration: CONFIG.recall_timeout,
            data: {
                trial_part: isPractice ? "practice_recall" : "stimulus",
                list_number: listNum,
                words_presented: JSON.stringify(wordList),
            },
            on_load: function () {
                // Set up global click handlers
                window._recallClick = function (btn) {
                    if (btn.classList.contains("selected")) return;
                    var word = btn.getAttribute("data-word");
                    recallOrder.push(word);
                    btn.classList.add("selected");

                    // Update display
                    var display = document.getElementById("recall-order-display");
                    if (display) {
                        display.textContent = "Your order: " + recallOrder.join(", ");
                    }
                };

                window._recallDone = function () {
                    // End the trial
                    var displayElem = document.querySelector(".jspsych-display-element");
                    if (displayElem) {
                        // Simulate finishing the trial by dispatching an event jsPsych will pick up
                        jsPsych.finishTrial();
                    }
                };
            },
            on_finish: function (data) {
                data.recall_order = recallOrder;
                data.words_presented = wordList;
                data.n_recalled = recallOrder.length;

                // Compute serial position accuracy
                var nCorrectPosition = 0;
                var serialPositionHits = [];
                for (var p = 0; p < CONFIG.list_length; p++) {
                    if (p < recallOrder.length && recallOrder[p] === wordList[p]) {
                        nCorrectPosition++;
                        serialPositionHits.push(true);
                    } else {
                        serialPositionHits.push(false);
                    }
                }
                data.n_correct_position = nCorrectPosition;
                data.serial_position_hits = serialPositionHits;

                // Primacy (positions 1-3, indices 0-2)
                var primacyHits = 0;
                for (var i = 0; i < 3; i++) {
                    if (serialPositionHits[i]) primacyHits++;
                }
                data.primacy_recalled = primacyHits / 3;

                // Recency (positions 10-12, indices 9-11)
                var recencyHits = 0;
                for (var i = 9; i < 12; i++) {
                    if (serialPositionHits[i]) recencyHits++;
                }
                data.recency_recalled = recencyHits / 3;

                // Middle (positions 4-9, indices 3-8)
                var middleHits = 0;
                for (var i = 3; i < 9; i++) {
                    if (serialPositionHits[i]) middleHits++;
                }
                data.middle_recalled = middleHits / 6;

                // Above chance: n_recalled / list_length > 1/12 (random baseline)
                data.above_chance_recall = (data.n_recalled / CONFIG.list_length) > 0.083;

                // Recall duration
                if (recallStartTime) {
                    data.recall_duration_ms = Math.round(performance.now() - recallStartTime);
                }

                // Clean up global handlers
                delete window._recallClick;
                delete window._recallDone;
            },
        });

        // Feedback for practice only
        if (isPractice) {
            trials.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    var last = jsPsych.data.get().last(1).values()[0];
                    return '<div style="font-size:20px">' +
                        '<p>You recalled <strong>' + last.n_recalled + '</strong> of ' + CONFIG.list_length + ' words.</p>' +
                        '<p><strong>' + last.n_correct_position + '</strong> were in the correct position.</p>' +
                        '<p>Press any key to continue to the main task.</p>' +
                        '</div>';
                },
            });
        }

        return trials;
    }

    // Practice list (1 list)
    var practiceWords = drawList();
    var practiceTrials = buildListTrials(practiceWords, 0, true);
    for (var i = 0; i < practiceTrials.length; i++) {
        timeline.push(practiceTrials[i]);
    }

    // Transition to main task
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Main Task</h2>" +
            "<p>The practice is over. The main task will now begin.</p>" +
            "<p>There are " + CONFIG.n_lists + " lists of " + CONFIG.list_length + " words each.</p>" +
            "<p>Press any key to start.</p>",
    });

    // Main lists
    var trialCounter = 0;
    for (var listIdx = 0; listIdx < CONFIG.n_lists; listIdx++) {
        (function (listNum) {
            var wordList = drawList();
            var listTrials = buildListTrials(wordList, listNum, false);
            for (var t = 0; t < listTrials.length; t++) {
                var trial = listTrials[t];
                // Attach trial_index counter to stimulus trials
                if (trial.data && trial.data.trial_part === "stimulus") {
                    var originalOnFinish = trial.on_finish;
                    trial.on_finish = (function (origFn, ln) {
                        return function (data) {
                            trialCounter++;
                            data.trial_index = trialCounter;
                            data.list_number = ln;
                            if (origFn) origFn(data);
                        };
                    })(originalOnFinish, listNum);
                }
                timeline.push(trial);
            }
        })(listIdx + 1);
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
        stimulus:
            "<h2>Task Complete</h2>" +
            "<p>Thank you for completing the Serial Recall task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
