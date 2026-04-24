(function () {
    var CONFIG = {
        n_study: 50,
        n_lures: 50,             // n_test = n_study + n_lures
        study_duration: 2500,
        study_iti: 500,
        distractor_duration: 30000,
        test_response_deadline: 4000,
        test_iti: 500,
        valid_keys: ["f", "j"],
        key_old: "f",
        key_new: "j",
        canvas_size: 280,
    };
    CONFIG.test_response_deadline = getTrialDuration(CONFIG.test_response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "visual_recognition";

    // Allow shrinking from URL: --n-trials becomes the test count; study scales proportionally.
    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        var n_test = Math.max(2, _nto);
        CONFIG.n_study = Math.max(1, Math.floor(n_test / 2));
        CONFIG.n_lures = n_test - CONFIG.n_study;
    }

    var jsPsych = initJsPsych({
        experiment_width: 600,
        minimum_valid_rt: 100,
    });
    if (SESSION_ID === "debug") window._jsPsych = jsPsych;

    // ---- Procedural stimulus generation ----
    var SHAPES = ["circle", "square", "triangle", "hexagon", "pentagon", "diamond"];
    var COLORS = [
        { name: "red", fill: "#dc2626" },
        { name: "blue", fill: "#1f6fb2" },
        { name: "green", fill: "#15803d" },
        { name: "yellow", fill: "#ca8a04" },
        { name: "purple", fill: "#6d28d9" },
        { name: "orange", fill: "#ea580c" },
        { name: "teal", fill: "#0d9488" },
        { name: "pink", fill: "#db2777" },
    ];
    var PATTERNS = ["solid", "stripe", "dot", "ring"];
    var ORIENTATIONS = [0, 45, 90, 135];

    function makeStimulusPool() {
        // 6 × 8 × 4 × 4 = 768 unique combinations.
        var pool = [];
        for (var s = 0; s < SHAPES.length; s++) {
            for (var c = 0; c < COLORS.length; c++) {
                for (var p = 0; p < PATTERNS.length; p++) {
                    for (var o = 0; o < ORIENTATIONS.length; o++) {
                        pool.push({
                            id: SHAPES[s] + "_" + COLORS[c].name + "_" + PATTERNS[p] + "_" + ORIENTATIONS[o],
                            shape: SHAPES[s],
                            color: COLORS[c],
                            pattern: PATTERNS[p],
                            orientation: ORIENTATIONS[o],
                        });
                    }
                }
            }
        }
        return pool;
    }

    function shuffle(arr) {
        for (var i = arr.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var t = arr[i]; arr[i] = arr[j]; arr[j] = t;
        }
        return arr;
    }

    function pickStimuli(pool, n) {
        return shuffle(pool.slice()).slice(0, n);
    }

    // ---- SVG renderer ----
    function svgFor(stim) {
        var size = CONFIG.canvas_size;
        var cx = size / 2, cy = size / 2, r = size * 0.30;
        var fill = stim.color.fill;
        var stroke = "#222";
        var strokeWidth = 3;
        var patternId = "pattern_" + stim.pattern + "_" + stim.color.name;
        var defs = "";
        var fillAttr = "fill='" + fill + "'";
        if (stim.pattern === "stripe") {
            defs = '<defs><pattern id="' + patternId + '" patternUnits="userSpaceOnUse" width="10" height="10" patternTransform="rotate(45)">' +
                '<rect width="10" height="10" fill="' + fill + '"/>' +
                '<line x1="0" y1="0" x2="0" y2="10" stroke="#fff" stroke-width="3"/></pattern></defs>';
            fillAttr = "fill='url(#" + patternId + ")'";
        } else if (stim.pattern === "dot") {
            defs = '<defs><pattern id="' + patternId + '" patternUnits="userSpaceOnUse" width="12" height="12">' +
                '<rect width="12" height="12" fill="' + fill + '"/>' +
                '<circle cx="6" cy="6" r="2" fill="#fff"/></pattern></defs>';
            fillAttr = "fill='url(#" + patternId + ")'";
        } else if (stim.pattern === "ring") {
            // For "ring" we'll use solid fill but add a thick outer ring stroke
            strokeWidth = 8;
            stroke = "#fff";
        }
        var shapeSvg = "";
        if (stim.shape === "circle") {
            shapeSvg = '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" ' + fillAttr +
                ' stroke="' + stroke + '" stroke-width="' + strokeWidth + '" />';
        } else if (stim.shape === "square") {
            shapeSvg = '<rect x="' + (cx - r) + '" y="' + (cy - r) + '" width="' + (2 * r) + '" height="' + (2 * r) + '" ' + fillAttr +
                ' stroke="' + stroke + '" stroke-width="' + strokeWidth + '" />';
        } else if (stim.shape === "triangle") {
            var pts = [
                cx + "," + (cy - r),
                (cx - r) + "," + (cy + r),
                (cx + r) + "," + (cy + r),
            ].join(" ");
            shapeSvg = '<polygon points="' + pts + '" ' + fillAttr +
                ' stroke="' + stroke + '" stroke-width="' + strokeWidth + '" />';
        } else if (stim.shape === "hexagon" || stim.shape === "pentagon") {
            var n_sides = stim.shape === "hexagon" ? 6 : 5;
            var pts2 = [];
            for (var i = 0; i < n_sides; i++) {
                var a = -Math.PI / 2 + (2 * Math.PI * i) / n_sides;
                pts2.push((cx + r * Math.cos(a)) + "," + (cy + r * Math.sin(a)));
            }
            shapeSvg = '<polygon points="' + pts2.join(" ") + '" ' + fillAttr +
                ' stroke="' + stroke + '" stroke-width="' + strokeWidth + '" />';
        } else if (stim.shape === "diamond") {
            var pts3 = [
                cx + "," + (cy - r),
                (cx + r) + "," + cy,
                cx + "," + (cy + r),
                (cx - r) + "," + cy,
            ].join(" ");
            shapeSvg = '<polygon points="' + pts3 + '" ' + fillAttr +
                ' stroke="' + stroke + '" stroke-width="' + strokeWidth + '" />';
        }
        var rotated = '<g transform="rotate(' + stim.orientation + ' ' + cx + ' ' + cy + ')">' + shapeSvg + "</g>";
        return '<svg class="stim-canvas" width="' + size + '" height="' + size + '" xmlns="http://www.w3.org/2000/svg" data-stim-id="' + stim.id + '">' +
            defs + rotated + "</svg>";
    }

    // ---- Build study + test sets ----
    var pool = makeStimulusPool();
    var combined = pickStimuli(pool, CONFIG.n_study + CONFIG.n_lures); // n_study old + n_lures new
    var studySet = combined.slice(0, CONFIG.n_study);
    var lureSet = combined.slice(CONFIG.n_study);
    var testSet = [];
    studySet.forEach(function (s) { testSet.push({ stim: s, is_old: true }); });
    lureSet.forEach(function (s) { testSet.push({ stim: s, is_old: false }); });
    shuffle(testSet);

    var trial_counter = 0;

    var timeline = [];

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Visual Recognition Memory</h1>" +
            "<p>Welcome. Press any key to begin.</p>",
    });

    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions — Study Phase</h2>" +
            "<p>You will see a series of " + CONFIG.n_study + " unique colored shapes.</p>" +
            "<p>Each one is shown for " + (CONFIG.study_duration / 1000) + " seconds.</p>" +
            "<p>Try to remember each shape. You will be tested later.</p>",

            "<h2>Distractor Phase</h2>" +
            "<p>After the study phase, you will solve simple arithmetic problems for " +
            (CONFIG.distractor_duration / 1000) + " seconds.</p>" +
            "<p>This is to prevent you from rehearsing the shapes.</p>",

            "<h2>Test Phase</h2>" +
            "<p>You will then see " + (CONFIG.n_study + CONFIG.n_lures) + " shapes one at a time.</p>" +
            "<p>For each shape, decide whether it was in the study list:</p>" +
            "<div class='key-mapping'>" +
            "<p>Press <kbd>F</kbd> if the shape was studied (OLD).</p>" +
            "<p>Press <kbd>J</kbd> if the shape is new (NEW).</p>" +
            "</div>" +
            "<p>You have " + (CONFIG.test_response_deadline / 1000) + " seconds per response.</p>" +
            "<p>Press Next to start the study phase.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    // ---- Study phase ----
    studySet.forEach(function (stim, idx) {
        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: svgFor(stim),
            choices: "NO_KEYS",
            trial_duration: CONFIG.study_duration,
            data: {
                trial_part: "study",
                phase: "study",
                stimulus_id: stim.id,
                presentation_order: idx + 1,
                is_old: true,
            },
            on_finish: function (data) {
                trial_counter++;
                data.trial_index = trial_counter;
                data.timed_out = false;
                data.response = null;
                data.responded_old = null;
                data.is_hit = false;
                data.is_false_alarm = false;
                data.is_miss = false;
                data.is_correct_rejection = false;
                data.correct = null;
            },
        });
        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: '<div class="fixation">+</div>',
            choices: "NO_KEYS",
            trial_duration: CONFIG.study_iti,
            data: { trial_part: "study_iti" },
        });
    });

    // ---- Distractor phase ----
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Distractor</h2>" +
            "<p>Solve as many arithmetic problems as you can in " + (CONFIG.distractor_duration / 1000) + " seconds.</p>" +
            "<p>Press any key to start.</p>",
    });
    timeline.push({
        type: jsPsychCallFunction,
        async: true,
        func: function (done) {
            var content = document.querySelector("#jspsych-content");
            if (!content) { done(); return; }
            var startT = performance.now();
            var n_correct = 0;
            var n_solved = 0;

            function makeProblem() {
                var a = Math.floor(Math.random() * 50) + 10;
                var b = Math.floor(Math.random() * 50) + 10;
                return { a: a, b: b, ans: a + b };
            }
            var current = makeProblem();

            function render() {
                var elapsed = performance.now() - startT;
                var remaining = Math.max(0, Math.round((CONFIG.distractor_duration - elapsed) / 1000));
                content.innerHTML =
                    '<div class="distractor-prompt">' + current.a + " + " + current.b + " = ?</div>" +
                    '<input type="text" class="distractor-input" id="distractor-input" autocomplete="off" inputmode="numeric" />' +
                    '<div class="distractor-counter">Time left: ' + remaining + 's &middot; solved: ' + n_solved + " (" + n_correct + " correct)</div>";
                var input = document.getElementById("distractor-input");
                if (input) {
                    input.focus();
                    input.addEventListener("keydown", function (e) {
                        if (e.key === "Enter" || e.key === " ") {
                            var val = parseInt(input.value);
                            n_solved++;
                            if (val === current.ans) n_correct++;
                            current = makeProblem();
                            render();
                        }
                    });
                }
            }
            render();
            var deadlineTimer = setTimeout(function () {
                clearInterval(tickTimer);
                done();
            }, CONFIG.distractor_duration);
            var tickTimer = setInterval(render, 1000);
        },
    });

    // ---- Test phase ----
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Test Phase</h2>" +
            "<p>For each shape, press <kbd>F</kbd> if it was in the study list (OLD), or <kbd>J</kbd> if it is new (NEW).</p>" +
            "<p>Press any key to start.</p>",
    });

    testSet.forEach(function (item) {
        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: svgFor(item.stim) +
                '<div class="key-mapping">' +
                '<kbd>F</kbd> = OLD &nbsp;&nbsp; <kbd>J</kbd> = NEW' +
                '</div>',
            choices: CONFIG.valid_keys,
            trial_duration: CONFIG.test_response_deadline,
            data: {
                trial_part: "test",
                phase: "test",
                stimulus_id: item.stim.id,
                is_old: item.is_old,
            },
            on_finish: function (data) {
                trial_counter++;
                data.trial_index = trial_counter;
                if (data.response === null) {
                    data.timed_out = true;
                    data.responded_old = null;
                    data.is_hit = false;
                    data.is_false_alarm = false;
                    data.is_miss = data.is_old;
                    data.is_correct_rejection = !data.is_old;
                    data.correct = false;
                } else {
                    data.timed_out = false;
                    data.responded_old = (data.response === CONFIG.key_old);
                    data.is_hit = data.is_old && data.responded_old;
                    data.is_false_alarm = !data.is_old && data.responded_old;
                    data.is_miss = data.is_old && !data.responded_old;
                    data.is_correct_rejection = !data.is_old && !data.responded_old;
                    data.correct = data.is_hit || data.is_correct_rejection;
                }
            },
        });
        timeline.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: '<div class="fixation">+</div>',
            choices: "NO_KEYS",
            trial_duration: CONFIG.test_iti,
            data: { trial_part: "test_iti" },
        });
    });

    // Data submission
    timeline.push({
        type: jsPsychCallFunction,
        async: true,
        func: function (done) {
            var trial_data = jsPsych.data
                .get()
                .filter({ trial_part: "test" })
                .values();
            var payload = {
                trial_data: trial_data,
                metadata: {
                    task_id: TASK_ID,
                    session_id: SESSION_ID,
                    total_time_ms: jsPsych.getTotalTime(),
                    n_trials: trial_data.length,
                    n_study: CONFIG.n_study,
                    n_lures: CONFIG.n_lures,
                },
            };
            fetch("/api/data/" + SESSION_ID + "/" + TASK_ID, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            })
                .then(function (response) {
                    if (!response.ok) console.error("Data submission failed:", response.status);
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
            "<p>Thank you for completing the recognition memory task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
