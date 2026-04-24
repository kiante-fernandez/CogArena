(function () {
    var CONFIG = {
        n_practice_trials: 6,
        n_blocks: 5,
        trials_per_block: 24,
        coherence_levels: [0.05, 0.10, 0.20, 0.40, 0.80],
        directions: ["left", "right"],
        key_mapping: { left: "f", right: "j" },
        valid_keys: ["f", "j"],
        stimulus_duration: 2000,
        response_deadline: 2000,
        fixation_duration: 500,
        feedback_duration: 800,
        iti_min: 400,
        iti_max: 800,
        n_dots: 200,
        dot_speed: 3,           // pixels per frame
        dot_radius: 2,
        aperture_radius: 150,   // pixels
        canvas_size: 320,       // px (must be > 2*aperture_radius)
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);
    CONFIG.stimulus_duration = CONFIG.response_deadline; // synchronize stimulus to response window

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "random_dot_motion_v2";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.n_blocks = 1;
        CONFIG.trials_per_block = _nto;
    }

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });
    if (SESSION_ID === "debug") window._jsPsych = jsPsych;

    // ---- Trial generation ----
    function generateBlockTrials(block_idx) {
        // Balanced: trials_per_block / (5 coherences * 2 directions) per cell
        var per_cell = Math.max(1, Math.floor(CONFIG.trials_per_block / (CONFIG.coherence_levels.length * CONFIG.directions.length)));
        var trials = [];
        for (var c = 0; c < CONFIG.coherence_levels.length; c++) {
            for (var d = 0; d < CONFIG.directions.length; d++) {
                for (var k = 0; k < per_cell; k++) {
                    var coh = CONFIG.coherence_levels[c];
                    var dir = CONFIG.directions[d];
                    trials.push({
                        block: block_idx + 1,
                        coherence: coh,
                        direction: dir,
                        correct_key: CONFIG.key_mapping[dir],
                        condition:
                            coh <= 0.10 ? "low" :
                            coh <= 0.20 ? "medium" : "high",
                    });
                }
            }
        }
        // Shuffle
        for (var i = trials.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var t = trials[i]; trials[i] = trials[j]; trials[j] = t;
        }
        return trials;
    }

    // ---- Canvas RDM rendering ----
    function startRdmAnimation(canvas, coherence, direction) {
        var ctx = canvas.getContext("2d");
        var cx = canvas.width / 2;
        var cy = canvas.height / 2;
        var r_ap = CONFIG.aperture_radius;
        var n_dots = CONFIG.n_dots;
        var speed = CONFIG.dot_speed;
        var coherent_dx = (direction === "right" ? 1 : -1) * speed;

        // Initialize dots uniformly in aperture (rejection sampling)
        var dots = new Array(n_dots);
        for (var i = 0; i < n_dots; i++) {
            var x, y;
            do {
                x = (Math.random() - 0.5) * 2 * r_ap;
                y = (Math.random() - 0.5) * 2 * r_ap;
            } while (x * x + y * y > r_ap * r_ap);
            dots[i] = { x: x, y: y };
        }

        var rafId = null;
        var stopped = false;

        function frame() {
            if (stopped) return;
            ctx.fillStyle = "#000";
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            // Aperture mask: draw circle outline
            ctx.strokeStyle = "#222";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.arc(cx, cy, r_ap, 0, Math.PI * 2);
            ctx.stroke();

            // Update + draw dots
            ctx.fillStyle = "#fff";
            for (var i = 0; i < n_dots; i++) {
                var d = dots[i];
                var dx, dy;
                if (Math.random() < coherence) {
                    dx = coherent_dx;
                    dy = 0;
                } else {
                    var theta = Math.random() * 2 * Math.PI;
                    dx = Math.cos(theta) * speed;
                    dy = Math.sin(theta) * speed;
                }
                d.x += dx; d.y += dy;
                // Wrap if out of aperture
                if (d.x * d.x + d.y * d.y > r_ap * r_ap) {
                    var nx, ny;
                    do {
                        nx = (Math.random() - 0.5) * 2 * r_ap;
                        ny = (Math.random() - 0.5) * 2 * r_ap;
                    } while (nx * nx + ny * ny > r_ap * r_ap);
                    d.x = nx; d.y = ny;
                }
                ctx.beginPath();
                ctx.arc(cx + d.x, cy + d.y, CONFIG.dot_radius, 0, Math.PI * 2);
                ctx.fill();
            }
            rafId = requestAnimationFrame(frame);
        }
        rafId = requestAnimationFrame(frame);

        return function stop() {
            stopped = true;
            if (rafId !== null) cancelAnimationFrame(rafId);
        };
    }

    var timeline = [];

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1 style='color:#ddd'>Random Dot Motion</h1>" +
            "<p style='color:#ddd'>Welcome. Press any key to begin.</p>",
    });

    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2 style='color:#ddd'>Instructions</h2>" +
            "<p style='color:#ddd'>You will see a cloud of moving dots inside a circle.</p>" +
            "<p style='color:#ddd'>Most dots move randomly, but a fraction of them all move together to the <strong>left</strong> or to the <strong>right</strong>.</p>" +
            "<p style='color:#ddd'>Your task is to identify the <strong>overall direction</strong> of motion.</p>",

            "<h2 style='color:#ddd'>Response Keys</h2>" +
            "<div class='key-mapping'>" +
            "<p>Dots move <strong>LEFT</strong> &rarr; press <kbd>F</kbd></p>" +
            "<p>Dots move <strong>RIGHT</strong> &rarr; press <kbd>J</kbd></p>" +
            "</div>" +
            "<p style='color:#ddd'>Respond as quickly and accurately as possible.</p>",

            "<h2 style='color:#ddd'>Practice</h2>" +
            "<p style='color:#ddd'>We will start with " + CONFIG.n_practice_trials + " practice trials with feedback.</p>" +
            "<p style='color:#ddd'>Press Next to begin.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    var fixation = {
        type: jsPsychHtmlKeyboardResponse,
        stimulus: '<div class="fixation">+</div>',
        choices: "NO_KEYS",
        trial_duration: CONFIG.fixation_duration,
        data: { trial_part: "fixation" },
    };

    var iti = {
        type: jsPsychHtmlKeyboardResponse,
        stimulus: "",
        choices: "NO_KEYS",
        trial_duration: function () {
            return Math.floor(CONFIG.iti_min + Math.random() * (CONFIG.iti_max - CONFIG.iti_min));
        },
        data: { trial_part: "iti" },
    };

    var trial_counter = 0;

    function makeStimulusTrial(is_practice) {
        return {
            type: jsPsychHtmlKeyboardResponse,
            stimulus: '<canvas id="rdm-canvas" class="rdm-canvas" width="' + CONFIG.canvas_size + '" height="' + CONFIG.canvas_size + '"></canvas>',
            choices: CONFIG.valid_keys,
            trial_duration: CONFIG.stimulus_duration,
            data: {
                trial_part: "stimulus",
                practice: !!is_practice,
                block: jsPsych.timelineVariable("block"),
                condition: jsPsych.timelineVariable("condition"),
                coherence: jsPsych.timelineVariable("coherence"),
                direction: jsPsych.timelineVariable("direction"),
                correct_key: jsPsych.timelineVariable("correct_key"),
            },
            on_load: function () {
                var canvas = document.getElementById("rdm-canvas");
                if (!canvas) return;
                var coh = jsPsych.evaluateTimelineVariable("coherence");
                var dir = jsPsych.evaluateTimelineVariable("direction");
                this._stop = startRdmAnimation(canvas, coh, dir);
            },
            on_finish: function (data) {
                if (this._stop) this._stop();
                if (!is_practice) {
                    trial_counter++;
                    data.trial_index = trial_counter;
                } else {
                    data.trial_index = -1;
                }
                if (data.response === null) {
                    data.correct = false;
                    data.timed_out = true;
                } else {
                    data.correct = jsPsych.pluginAPI.compareKeys(data.response, data.correct_key);
                    data.timed_out = false;
                }
            },
        };
    }

    var feedback = {
        type: jsPsychHtmlKeyboardResponse,
        stimulus: function () {
            var last = jsPsych.data.get().last(1).values()[0];
            if (last.timed_out) {
                return '<div class="feedback" style="color:orange;">Too slow!</div>';
            } else if (last.correct) {
                return '<div class="feedback" style="color:#4ade80;">✔ Correct</div>';
            } else {
                return '<div class="feedback" style="color:#f87171;">✘ Wrong</div>';
            }
        },
        choices: "NO_KEYS",
        trial_duration: CONFIG.feedback_duration,
        data: { trial_part: "feedback" },
    };

    // Practice
    var practice_stimuli = [];
    var pcoh = [0.40, 0.80];
    for (var pi = 0; pi < CONFIG.n_practice_trials; pi++) {
        var pdir = pi % 2 === 0 ? "left" : "right";
        var pc = pcoh[pi % pcoh.length];
        practice_stimuli.push({
            block: 0,
            coherence: pc,
            direction: pdir,
            correct_key: CONFIG.key_mapping[pdir],
            condition: "high",
        });
    }
    timeline.push({
        timeline: [fixation, makeStimulusTrial(true), feedback, iti],
        timeline_variables: practice_stimuli,
        randomize_order: true,
    });

    // Transition
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2 style='color:#ddd'>End of Practice</h2>" +
            "<p style='color:#ddd'>The main experiment will now begin.</p>" +
            "<p style='color:#ddd'>There are " + CONFIG.n_blocks + " blocks of " + CONFIG.trials_per_block + " trials each.</p>" +
            "<p style='color:#ddd'>No feedback will be shown during the main experiment.</p>" +
            "<p style='color:#ddd'>Press any key to start.</p>",
    });

    // Experimental blocks (no feedback)
    for (var b = 0; b < CONFIG.n_blocks; b++) {
        var block_stimuli = generateBlockTrials(b);

        timeline.push({
            timeline: [fixation, makeStimulusTrial(false), iti],
            timeline_variables: block_stimuli,
            randomize_order: true,
        });

        if (b < CONFIG.n_blocks - 1) {
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus:
                    "<h2 style='color:#ddd'>Block " + (b + 1) + " of " + CONFIG.n_blocks + " complete</h2>" +
                    "<p style='color:#ddd'>Take a short break if needed.</p>" +
                    "<p style='color:#ddd'>Press any key to continue.</p>",
            });
        }
    }

    // Data submission
    timeline.push({
        type: jsPsychCallFunction,
        async: true,
        func: function (done) {
            var trial_data = jsPsych.data
                .get()
                .filter({ trial_part: "stimulus", practice: false })
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
            "<h2 style='color:#ddd'>Task Complete</h2>" +
            "<p style='color:#ddd'>Thank you for completing the task.</p>" +
            "<p style='color:#ddd'>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
