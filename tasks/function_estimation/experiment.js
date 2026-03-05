(function () {
    var CONFIG = {
        n_trials: 40,
        n_blocks: 8,
        trials_per_block: 5,
        n_train_points: 6,
        response_deadline: 15000,
        fixation_duration: 500,
        feedback_duration: 1000,
        canvas_width: 400,
        canvas_height: 300,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "function_estimation";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.n_trials = _nto;
        CONFIG.n_blocks = Math.ceil(_nto / CONFIG.trials_per_block);
    }

    var jsPsych = initJsPsych({ experiment_width: 800, minimum_valid_rt: 100 });
    if (SESSION_ID === "debug") window._jsPsych = jsPsych;

    // Function types
    var FUNCTIONS = [
        { name: "linear", fn: function (x, a, b) { return a * x + b; } },
        { name: "quadratic", fn: function (x, a, b) { return a * x * x + b; } },
        { name: "sinusoidal", fn: function (x, a, b) { return a * Math.sin(3 * x) + b; } },
        { name: "exponential", fn: function (x, a, b) { return a * (Math.exp(x) - 1) + b; } },
    ];

    function generateBlock(blockIdx) {
        var funcType = FUNCTIONS[blockIdx % FUNCTIONS.length];
        var a = (Math.random() * 1.5 + 0.5) * (Math.random() < 0.5 ? 1 : -1);
        var b = Math.random() * 0.4 - 0.2;
        var noise_sd = 0.1;

        // Generate training points
        var train_points = [];
        for (var i = 0; i < CONFIG.n_train_points; i++) {
            var x = -1 + (2 * i) / (CONFIG.n_train_points - 1);
            var y = funcType.fn(x, a, b) + (Math.random() - 0.5) * noise_sd * 2;
            y = Math.max(-1, Math.min(1, y));
            train_points.push({ x: x, y: y });
        }

        // Generate test x-values
        var test_trials = [];
        for (var j = 0; j < CONFIG.trials_per_block; j++) {
            var tx = -0.9 + (1.8 * j) / (CONFIG.trials_per_block - 1);
            // Avoid exact training point locations
            tx += (Math.random() - 0.5) * 0.1;
            tx = Math.max(-1, Math.min(1, tx));
            var correct_y = funcType.fn(tx, a, b);
            correct_y = Math.max(-1, Math.min(1, correct_y));

            test_trials.push({
                x_value: Math.round(tx * 100) / 100,
                correct_y: Math.round(correct_y * 100) / 100,
                func_type: funcType.name,
            });
        }

        return { train_points: train_points, test_trials: test_trials, func_type: funcType.name };
    }

    function drawScatterplot(train_points, test_x, canvasId) {
        // Return HTML with canvas and inline script to draw
        var w = CONFIG.canvas_width;
        var h = CONFIG.canvas_height;
        var pointsStr = JSON.stringify(train_points);

        return '<canvas id="' + canvasId + '" class="scatter-canvas" width="' + w + '" height="' + h + '"></canvas>' +
            '<script>' +
            '(function() {' +
            'var c = document.getElementById("' + canvasId + '");' +
            'if (!c) return;' +
            'var ctx = c.getContext("2d");' +
            'var W=' + w + ', H=' + h + ', pad=40;' +
            // Draw axes
            'ctx.strokeStyle="#999"; ctx.lineWidth=1;' +
            'ctx.beginPath(); ctx.moveTo(pad, H-pad); ctx.lineTo(W-pad, H-pad); ctx.stroke();' +
            'ctx.beginPath(); ctx.moveTo(pad, pad); ctx.lineTo(pad, H-pad); ctx.stroke();' +
            // Axis labels
            'ctx.fillStyle="#666"; ctx.font="12px sans-serif";' +
            'ctx.fillText("-1", pad-5, H-pad+15); ctx.fillText("1", W-pad-5, H-pad+15);' +
            'ctx.fillText("1", pad-15, pad+5); ctx.fillText("-1", pad-20, H-pad);' +
            // Map data coords to canvas coords
            'function mapX(x) { return pad + (x+1)/2 * (W-2*pad); }' +
            'function mapY(y) { return H - pad - (y+1)/2 * (H-2*pad); }' +
            // Draw training points
            'var pts = ' + pointsStr + ';' +
            'ctx.fillStyle="#1565c0";' +
            'for (var i=0; i<pts.length; i++) {' +
            '  ctx.beginPath(); ctx.arc(mapX(pts[i].x), mapY(pts[i].y), 5, 0, 2*Math.PI); ctx.fill();' +
            '}' +
            // Draw test x indicator
            'var tx = ' + test_x + ';' +
            'ctx.strokeStyle="#c62828"; ctx.lineWidth=2; ctx.setLineDash([5,5]);' +
            'ctx.beginPath(); ctx.moveTo(mapX(tx), pad); ctx.lineTo(mapX(tx), H-pad); ctx.stroke();' +
            'ctx.setLineDash([]);' +
            '})();</' + 'script>';
    }

    var blocks = [];
    for (var bi = 0; bi < CONFIG.n_blocks; bi++) {
        blocks.push(generateBlock(bi));
    }

    var timeline = [];

    timeline.push({ type: jsPsychHtmlKeyboardResponse, stimulus: "<h1>Function Estimation</h1><p>Press any key to begin.</p>" });
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2><p>You will see scatterplots with data points (blue dots).</p><p>The data follows an underlying pattern or function.</p>",
            "<h2>Your Task</h2><p>A red vertical line shows an X position.</p><p>Use the slider to predict the Y value at that position based on the pattern you see.</p><p>Try to estimate the underlying function, not just connect dots.</p>",
            "<h2>Controls</h2><p>Move the slider to set your Y prediction, then click Submit.</p><p>Press Next to start.</p>",
        ],
        show_clickable_nav: true, button_label_next: "Next", button_label_previous: "Previous",
    });

    var trialCounter = 0;

    for (var bk = 0; bk < blocks.length; bk++) {
        (function (block, blockIdx) {
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: '<h2>Pattern ' + (blockIdx + 1) + ' of ' + CONFIG.n_blocks + '</h2><p>New data pattern. Press any key to continue.</p>',
            });

            for (var tt = 0; tt < block.test_trials.length; tt++) {
                (function (test, trialInBlock) {
                    var canvasId = "canvas_" + blockIdx + "_" + trialInBlock;

                    timeline.push({
                        type: jsPsychHtmlSliderResponse,
                        stimulus: '<div class="trial-counter">Trial ' + (trialCounter + 1) + ' of ' + CONFIG.n_trials + '</div>' +
                            '<div class="block-label">Pattern ' + (blockIdx + 1) + ' (' + block.func_type + ')</div>' +
                            '<div class="scatter-display">' +
                            drawScatterplot(block.train_points, test.x_value, canvasId) +
                            '</div>' +
                            '<div class="x-indicator">Predict Y at X = ' + test.x_value + '</div>',
                        min: -100,
                        max: 100,
                        start: 0,
                        step: 1,
                        labels: ["-1.0", "0", "1.0"],
                        slider_width: 400,
                        require_movement: true,
                        trial_duration: CONFIG.response_deadline,
                        data: {
                            trial_part: "stimulus",
                            block: blockIdx,
                            trial_in_block: trialInBlock,
                            x_value: test.x_value,
                            correct_y: test.correct_y,
                            func_type: test.func_type,
                        },
                        on_finish: function (data) {
                            trialCounter++;
                            data.trial_index = trialCounter;
                            data.timed_out = data.response === null;
                            if (!data.timed_out) {
                                // Convert slider (−100 to 100) to function coords (−1 to 1)
                                data.response = data.response / 100;
                                data.estimation_error = Math.abs(data.response - data.correct_y);
                                data.correct = data.estimation_error < 0.3;
                            } else {
                                data.estimation_error = 1.0;
                                data.correct = false;
                            }
                        },
                    });

                    timeline.push({
                        type: jsPsychHtmlKeyboardResponse,
                        stimulus: function () {
                            var last = jsPsych.data.get().last(1).values()[0];
                            if (last.timed_out) return '<div class="feedback-text" style="color:#c62828">Too slow!</div>';
                            var err = last.estimation_error.toFixed(2);
                            var color = last.correct ? "#2e7d32" : "#c62828";
                            return '<div class="feedback-text" style="color:' + color + '">Error: ' + err + '</div>';
                        },
                        choices: "NO_KEYS", trial_duration: CONFIG.feedback_duration, data: { trial_part: "feedback" },
                    });
                })(block.test_trials[tt], tt);
            }
        })(blocks[bk], bk);
    }

    timeline.push({ type: jsPsychCallFunction, async: true, func: function (done) {
        var trial_data = jsPsych.data.get().filter({ trial_part: "stimulus" }).values();
        fetch("/api/data/" + SESSION_ID + "/" + TASK_ID, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ trial_data: trial_data, metadata: { task_id: TASK_ID, session_id: SESSION_ID, total_time_ms: jsPsych.getTotalTime(), n_trials: trial_data.length } }) })
            .then(function (r) { done(); }).catch(function (e) { console.error(e); done(); });
    }});

    timeline.push({ type: jsPsychHtmlKeyboardResponse, stimulus: "<h2>Task Complete</h2><p>Your data has been submitted.</p>", choices: "NO_KEYS", trial_duration: 3000 });
    jsPsych.run(timeline);
})();
