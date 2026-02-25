(function () {
    var CONFIG = {
        n_games: 40,
        games_per_horizon: 20,
        n_forced: 4,
        reward_mean: 50,
        reward_sd: 10,
        mean_sep_min: 4,
        mean_sep_max: 12,
        valid_keys: ["f", "j"],
        response_deadline: 5000,
        fixation_duration: 500,
        feedback_duration: 1500,
        iti_min: 300,
        iti_max: 600,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "two_armed_bandit";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.n_games = _nto;
        CONFIG.games_per_horizon = Math.ceil(_nto / 2);
    }

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 100,
    });

    if (SESSION_ID === "debug") {
        window._jsPsych = jsPsych;
    }

    function seededRandom(seed) {
        var x = Math.sin(seed) * 10000;
        return x - Math.floor(x);
    }

    function generateGames() {
        var games = [];
        var seed = 12345;

        for (var h = 0; h < 2; h++) {
            var horizon = h === 0 ? 1 : 6;
            for (var g = 0; g < CONFIG.games_per_horizon; g++) {
                seed++;
                var sep = CONFIG.mean_sep_min + seededRandom(seed) * (CONFIG.mean_sep_max - CONFIG.mean_sep_min);
                sep = Math.round(sep);

                seed++;
                var base = CONFIG.reward_mean + (seededRandom(seed) - 0.5) * CONFIG.reward_sd;

                seed++;
                var leftHigher = seededRandom(seed) > 0.5;
                var mean_left, mean_right;
                if (leftHigher) {
                    mean_left = Math.round(base + sep / 2);
                    mean_right = Math.round(base - sep / 2);
                } else {
                    mean_left = Math.round(base - sep / 2);
                    mean_right = Math.round(base + sep / 2);
                }

                seed++;
                var moreInfoLeft = seededRandom(seed) > 0.5;
                var forced_sequence = [];
                if (moreInfoLeft) {
                    forced_sequence = ["left", "left", "left", "right"];
                } else {
                    forced_sequence = ["right", "right", "right", "left"];
                }

                seed++;
                for (var s = forced_sequence.length - 1; s > 0; s--) {
                    var si = Math.floor(seededRandom(seed + s) * (s + 1));
                    var temp = forced_sequence[s];
                    forced_sequence[s] = forced_sequence[si];
                    forced_sequence[si] = temp;
                }

                games.push({
                    horizon: horizon,
                    mean_left: mean_left,
                    mean_right: mean_right,
                    info_condition: "unequal",
                    more_info_arm: moreInfoLeft ? "left" : "right",
                    forced_sequence: forced_sequence,
                });
            }
        }

        seed++;
        for (var i = games.length - 1; i > 0; i--) {
            var j = Math.floor(seededRandom(seed + i) * (i + 1));
            var tmp = games[i];
            games[i] = games[j];
            games[j] = tmp;
        }

        return games;
    }

    function sampleReward(mean, sd, seed) {
        var u1 = seededRandom(seed);
        var u2 = seededRandom(seed + 1);
        var z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
        return Math.round(mean + sd * z);
    }

    var allGames = generateGames();
    var timeline = [];

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>2-Armed Bandit Task</h1>" +
            "<p>Welcome to the bandit task.</p>" +
            "<p>Press any key to begin.</p>",
    });

    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>In this task, you will play a series of games.</p>" +
            "<p>Each game has two slot machines (arms): <strong>Left</strong> and <strong>Right</strong>.</p>" +
            "<p>Each arm gives rewards that vary around a hidden average value.</p>" +
            "<p>Your goal is to earn as many points as possible.</p>",

            "<h2>How Each Game Works</h2>" +
            "<p>Each game has two phases:</p>" +
            "<p><strong>1. Forced Phase:</strong> You will be shown which arm to pick for 4 trials. " +
            "Watch the rewards to learn about each arm.</p>" +
            "<p><strong>2. Free Phase:</strong> You choose which arm to play. " +
            "Some games have 1 free choice, others have 6.</p>" +
            "<p>The arm averages change between games, so learn from the forced trials.</p>",

            "<h2>Response Keys</h2>" +
            "<p style='font-size:28px'><kbd>F</kbd> = <strong>Left Arm</strong></p>" +
            "<p style='font-size:28px'><kbd>J</kbd> = <strong>Right Arm</strong></p>" +
            "<p>Try to respond quickly. You have 5 seconds per choice.</p>" +
            "<p>Press Next to start a practice game.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    function buildGameTimeline(game, gameIndex, isPractice) {
        var gameTrials = [];
        var rewardSeed = gameIndex * 1000;
        var leftHistory = [];
        var rightHistory = [];

        for (var f = 0; f < CONFIG.n_forced; f++) {
            (function (forcedIdx, forcedArm) {
                gameTrials.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: function () {
                        var leftStyle = forcedArm === "left" ? "border-color:#2196F3;border-width:5px;" : "opacity:0.4;";
                        var rightStyle = forcedArm === "right" ? "border-color:#2196F3;border-width:5px;" : "opacity:0.4;";
                        return '<div class="game-header">Game ' + (gameIndex + 1) + " of " + CONFIG.n_games +
                            " | Forced Trial " + (forcedIdx + 1) + " of " + CONFIG.n_forced + "</div>" +
                            '<div class="forced-label">You must pick the highlighted arm</div>' +
                            '<div class="bandit-container">' +
                            '<div class="bandit-arm left" style="' + leftStyle + '">' +
                            "Left<br><span class='key-hint'>F</span></div>" +
                            '<div class="bandit-arm right" style="' + rightStyle + '">' +
                            "Right<br><span class='key-hint'>J</span></div>" +
                            "</div>" +
                            '<div class="history-display">Left rewards: [' + leftHistory.join(", ") +
                            "] | Right rewards: [" + rightHistory.join(", ") + "]</div>";
                    },
                    choices: [forcedArm === "left" ? "f" : "j"],
                    trial_duration: CONFIG.response_deadline,
                    data: {
                        trial_part: "forced",
                        game_index: gameIndex,
                        horizon: game.horizon,
                        trial_in_game: forcedIdx + 1,
                        trial_type: "forced",
                        forced_arm: forcedArm,
                        arm_left_mean: game.mean_left,
                        arm_right_mean: game.mean_right,
                        info_condition: game.info_condition,
                    },
                    on_finish: function (data) {
                        var arm = forcedArm;
                        var mean = arm === "left" ? game.mean_left : game.mean_right;
                        rewardSeed++;
                        var reward = sampleReward(mean, 8, rewardSeed);
                        data.arm_chosen = arm;
                        data.reward = reward;
                        data.correct = (game.mean_left >= game.mean_right && arm === "left") ||
                                      (game.mean_right > game.mean_left && arm === "right");
                        data.timed_out = data.response === null;
                        if (arm === "left") { leftHistory.push(reward); }
                        else { rightHistory.push(reward); }
                    },
                });

                gameTrials.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: function () {
                        var lastTrial = jsPsych.data.get().last(1).values()[0];
                        return '<div class="reward-display">' + lastTrial.arm_chosen.toUpperCase() +
                            " arm: +" + lastTrial.reward + " points</div>";
                    },
                    choices: "NO_KEYS",
                    trial_duration: CONFIG.feedback_duration,
                    data: { trial_part: "feedback" },
                });
            })(f, game.forced_sequence[f]);
        }

        var n_free = game.horizon;
        var freeTrialCounter = 0;

        for (var c = 0; c < n_free; c++) {
            (function (choiceIdx) {
                gameTrials.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: function () {
                        return '<div class="game-header">Game ' + (gameIndex + 1) + " of " + CONFIG.n_games +
                            " | Free Choice " + (choiceIdx + 1) + " of " + n_free + "</div>" +
                            '<div class="bandit-container">' +
                            '<div class="bandit-arm left">Left<br><span class="key-hint">F</span></div>' +
                            '<div class="bandit-arm right">Right<br><span class="key-hint">J</span></div>' +
                            "</div>" +
                            '<div class="history-display">Left rewards: [' + leftHistory.join(", ") +
                            "] | Right rewards: [" + rightHistory.join(", ") + "]</div>";
                    },
                    choices: CONFIG.valid_keys,
                    trial_duration: CONFIG.response_deadline,
                    data: {
                        trial_part: "stimulus",
                        game_index: gameIndex,
                        horizon: game.horizon,
                        trial_in_game: CONFIG.n_forced + choiceIdx + 1,
                        trial_type: "free",
                        arm_left_mean: game.mean_left,
                        arm_right_mean: game.mean_right,
                        info_condition: game.info_condition,
                        more_info_arm: game.more_info_arm,
                    },
                    on_finish: function (data) {
                        freeTrialCounter++;
                        var arm = data.response === "f" ? "left" : data.response === "j" ? "right" : null;
                        data.arm_chosen = arm;
                        data.timed_out = data.response === null;

                        if (arm) {
                            var mean = arm === "left" ? game.mean_left : game.mean_right;
                            rewardSeed++;
                            var reward = sampleReward(mean, 8, rewardSeed);
                            data.reward = reward;
                            data.correct = (game.mean_left >= game.mean_right && arm === "left") ||
                                          (game.mean_right > game.mean_left && arm === "right");
                            data.explore_choice = !data.correct;
                            data.chose_less_sampled = arm !== game.more_info_arm;
                            if (arm === "left") { leftHistory.push(reward); }
                            else { rightHistory.push(reward); }
                        } else {
                            data.reward = 0;
                            data.correct = false;
                            data.explore_choice = false;
                            data.chose_less_sampled = false;
                        }
                    },
                });

                gameTrials.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: function () {
                        var lastTrial = jsPsych.data.get().last(1).values()[0];
                        if (lastTrial.timed_out) {
                            return '<div class="reward-display" style="color:#e65100;">Too slow!</div>';
                        }
                        return '<div class="reward-display">' + lastTrial.arm_chosen.toUpperCase() +
                            " arm: +" + lastTrial.reward + " points</div>";
                    },
                    choices: "NO_KEYS",
                    trial_duration: CONFIG.feedback_duration,
                    data: { trial_part: "feedback" },
                });
            })(c);
        }

        return gameTrials;
    }

    var practiceGame = {
        horizon: 3,
        mean_left: 55,
        mean_right: 45,
        info_condition: "unequal",
        more_info_arm: "left",
        forced_sequence: ["left", "left", "right", "left"],
    };
    var practiceTrials = buildGameTimeline(practiceGame, -1, true);
    practiceTrials.forEach(function (t) { timeline.push(t); });

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>End of Practice</h2>" +
            "<p>The main experiment will now begin.</p>" +
            "<p>There are " + CONFIG.n_games + " games total.</p>" +
            "<p>Some games have 1 free choice, others have 6.</p>" +
            "<p>Press any key to start.</p>",
    });

    var trialCounter = 0;
    for (var gi = 0; gi < allGames.length; gi++) {
        (function (gameIdx) {
            var gameTimeline = buildGameTimeline(allGames[gameIdx], gameIdx, false);
            gameTimeline.forEach(function (t) {
                if (t.data && t.data.trial_part === "stimulus") {
                    var origFinish = t.on_finish;
                    t.on_finish = function (data) {
                        origFinish(data);
                        trialCounter++;
                        data.trial_index = trialCounter;

                        if (trialCounter > 1) {
                            var prevFree = jsPsych.data.get().filter({ trial_part: "stimulus" });
                            var prevTrials = prevFree.values();
                            if (prevTrials.length >= 2) {
                                var prev = prevTrials[prevTrials.length - 2];
                                data.prev_win = prev.reward > prev.arm_left_mean && prev.reward > prev.arm_right_mean ? false :
                                    prev.correct;
                                data.stayed = data.arm_chosen === prev.arm_chosen;
                            }
                        }
                    };
                }
                timeline.push(t);
            });

            if (gameIdx < allGames.length - 1 && (gameIdx + 1) % 10 === 0) {
                timeline.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus:
                        "<h2>" + (gameIdx + 1) + " of " + CONFIG.n_games + " games complete</h2>" +
                        "<p>Take a short break if needed.</p>" +
                        "<p>Press any key to continue.</p>",
                });
            }
        })(gi);
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
            "<p>Thank you for completing the bandit task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
