(function () {
    var CONFIG = {
        rounds_per_game: 15,
        games: ["pd", "bos"],
        valid_keys: ["f", "j"],
        response_deadline: 8000,
        outcome_display: 1500,
        // Payoff matrices: [player, opponent] given (player_action, opponent_action).
        // J = "cooperate" / equilibrium-1, F = "defect" / equilibrium-2 (Akata 2023 coding).
        payoffs: {
            pd:  { FF: [5, 5],  FJ: [10, 0], JF: [0, 10], JJ: [8, 8] },
            bos: { FF: [10, 7], FJ: [0, 0],  JF: [0, 0],  JJ: [7, 10] }
        },
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "repeated_games";

    // Optional URL override of n_trials (cap rounds per game proportionally).
    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.rounds_per_game = Math.max(2, Math.floor(_nto / CONFIG.games.length));
    }

    var jsPsych = initJsPsych({ experiment_width: 800, minimum_valid_rt: 50 });
    if (SESSION_ID === "debug") window._jsPsych = jsPsych;

    // ---- Game order ----
    function shuffledGames() {
        var games = CONFIG.games.slice();
        for (var i = games.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var t = games[i]; games[i] = games[j]; games[j] = t;
        }
        return games;
    }

    // ---- Bot strategies (canonical, well-known) ----
    function botMove(game, playerHist, opponentHist) {
        if (game === "pd") {
            // Tit-for-tat: cooperate (J) round 1, then mirror player's previous action.
            if (playerHist.length === 0) return "j";
            return playerHist[playerHist.length - 1];
        }
        if (game === "bos") {
            // Alternation: round 1 = F, round 2 = J, round 3 = F, ...
            return (opponentHist.length % 2 === 0) ? "f" : "j";
        }
        return "j";
    }

    function payoffsFor(game, playerAction, opponentAction) {
        var key = String(playerAction).toUpperCase() + String(opponentAction).toUpperCase();
        return CONFIG.payoffs[game][key];
    }

    // ---- Rendering helpers ----
    function cellClass(youPayoff, allYouPayoffs) {
        var maxP = Math.max.apply(null, allYouPayoffs);
        var minP = Math.min.apply(null, allYouPayoffs);
        if (youPayoff === maxP) return "cell-best";
        if (youPayoff === minP) return "cell-bad";
        if (youPayoff > (maxP + minP) / 2) return "cell-good";
        return "cell-mid";
    }
    function payoffMatrixHTML(game) {
        var p = CONFIG.payoffs[game];
        var allYou = [p.FF[0], p.FJ[0], p.JF[0], p.JJ[0]];
        function cell(pair) {
            return '<td class="' + cellClass(pair[0], allYou) + '">' +
                '<span class="you-pt">' + pair[0] + '</span>, ' +
                '<span class="opp-pt">' + pair[1] + '</span>' +
                '</td>';
        }
        return '<table class="payoff-table">' +
            "<tr><th></th><th>opp&nbsp;F</th><th>opp&nbsp;J</th></tr>" +
            "<tr><th>you&nbsp;F</th>" + cell(p.FF) + cell(p.FJ) + "</tr>" +
            "<tr><th>you&nbsp;J</th>" + cell(p.JF) + cell(p.JJ) + "</tr>" +
            "</table>";
    }

    function payoffCardHTML(game) {
        return '<div class="play-card">' +
                   '<div class="play-card-label">Payoffs (you · opp)</div>' +
                   payoffMatrixHTML(game) +
               '</div>';
    }

    function historyCardHTML(game, playerHist, opponentHist) {
        var inner;
        if (playerHist.length === 0) {
            inner = '<div class="history-empty">No rounds played yet.</div>';
        } else {
            var rows = "";
            for (var i = 0; i < playerHist.length; i++) {
                var pa = playerHist[i].toUpperCase();
                var oa = opponentHist[i].toUpperCase();
                var po = payoffsFor(game, pa, oa);
                rows += "<tr><td>" + (i + 1) +
                    "</td><td><span class='you-action'>" + pa + "</span>" +
                    "</td><td><span class='opp-action'>" + oa + "</span>" +
                    "</td><td>" + po[0] + "</td></tr>";
            }
            inner =
                '<div class="history-frame"><table class="history-table">' +
                "<tr><th>#</th><th>you</th><th>opp</th><th>pts</th></tr>" +
                rows +
                "</table></div>";
        }
        return '<div class="play-card">' +
                   '<div class="play-card-label">History</div>' +
                   inner +
               '</div>';
    }

    // Player-vs-opponent avatar bar + scoreboard.
    function playerBarHTML(playerTotal, opponentTotal) {
        return '<div class="player-bar">' +
            '<div class="player">' +
                '<div class="avatar you">🧑</div>' +
                '<div class="player-name">You</div>' +
                '<div class="player-score">' + playerTotal + '</div>' +
            '</div>' +
            '<div class="vs-badge">VS</div>' +
            '<div class="player">' +
                '<div class="avatar opp">🤖</div>' +
                '<div class="player-name">Opponent</div>' +
                '<div class="player-score">' + opponentTotal + '</div>' +
            '</div>' +
        '</div>';
    }

    function gameLabel(g) {
        return g === "pd" ? "Game A — Cooperate or Defect" : "Game B — Coordinate";
    }

    function gameSubtitle(g) {
        return g === "pd"
            ? "Both J = mutual cooperation (8, 8). One F + one J = (10, 0)."
            : "Match the opponent on F-F (you 10, opp 7) or J-J (you 7, opp 10). Mismatched = (0, 0).";
    }

    // ---- Per-game state (closure) ----
    function makeGameRunner(game, block_order) {
        var playerHist = [];
        var opponentHist = [];
        var playerTotal = 0;
        var opponentTotal = 0;
        var nodes = [];

        // Game intro screen.
        nodes.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                return "<div class='game-banner'>" + gameLabel(game) + "</div>" +
                       "<p style='text-align:center;color:#4b5563;margin:4px 0 12px'>" + gameSubtitle(game) + "</p>" +
                       "<p style='text-align:center'>You will play <strong>" + CONFIG.rounds_per_game +
                       "</strong> rounds against a fixed computer opponent.</p>" +
                       payoffMatrixHTML(game) +
                       "<div class='stim-prompt'>Press <span class='key-hint'>F</span> for action F · " +
                       "<span class='key-hint'>J</span> for action J.</div>" +
                       "<p style='text-align:center;color:#6b7280;margin-top:12px'>Press any key to begin.</p>";
            },
        });

        // Round trial (single keyboard-response per round).
        function makeRoundTrial(round_num) {
            return [
                {
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: function () {
                        return "<div class='game-banner'>" + gameLabel(game) + "</div>" +
                               "<div class='round-status'>Round " + round_num + " of " + CONFIG.rounds_per_game + "</div>" +
                               playerBarHTML(playerTotal, opponentTotal) +
                               "<table class='play-table'><tr>" +
                                   "<td>" + payoffCardHTML(game) + "</td>" +
                                   "<td>" + historyCardHTML(game, playerHist, opponentHist) + "</td>" +
                               "</tr></table>" +
                               "<div class='stim-prompt'>Your move: <span class='key-hint'>F</span> or <span class='key-hint'>J</span></div>";
                    },
                    choices: CONFIG.valid_keys,
                    trial_duration: CONFIG.response_deadline,
                    data: {
                        trial_part: "round",
                        game: game,
                        block_order: block_order,
                        round: round_num,
                    },
                    on_finish: function (data) {
                        var timed_out = data.response === null;
                        var pa;
                        if (timed_out) {
                            // Random fallback so the bot can compute a response.
                            pa = Math.random() < 0.5 ? "f" : "j";
                        } else {
                            pa = String(data.response).toLowerCase();
                        }
                        var oa = botMove(game, playerHist, opponentHist);
                        var po = payoffsFor(game, pa, oa);

                        // Reciprocity predictor: previous opponent's cooperate (J) vs defect (F),
                        // only meaningful for PD rounds 2+.
                        var prev_opp_coop_pd = null;
                        if (game === "pd" && opponentHist.length > 0) {
                            prev_opp_coop_pd = (opponentHist[opponentHist.length - 1] === "j");
                        }

                        Object.assign(data, {
                            player_action: pa,
                            opponent_action: oa,
                            player_cooperate: (game === "pd") ? (pa === "j") : null,
                            opponent_cooperate: (game === "pd") ? (oa === "j") : null,
                            prev_opp_coop_pd: prev_opp_coop_pd,
                            coordinated: (game === "bos") ? (pa === oa) : null,
                            player_payoff: po[0],
                            opponent_payoff: po[1],
                            timed_out: timed_out,
                        });

                        playerHist.push(pa);
                        opponentHist.push(oa);
                        playerTotal += po[0];
                        opponentTotal += po[1];
                    },
                },
                // Outcome display.
                {
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: function () {
                        var last = jsPsych.data.get().last(1).values()[0];
                        var pa = String(last.player_action).toUpperCase();
                        var oa = String(last.opponent_action).toUpperCase();
                        var pts = last.player_payoff;
                        var opp_pts = last.opponent_payoff;
                        var cls = pts > opp_pts ? "win" : (pts === opp_pts ? "tie" : "lose");
                        var msg = last.timed_out ? "<div class='outcome-line' style='font-size:13px;font-style:italic;opacity:0.75'>(no response — random move)</div>" : "";
                        return "<div class='game-banner'>" + gameLabel(game) + "</div>" +
                               "<div class='outcome-display " + cls + "'>" +
                                   "<div class='outcome-line'>You played <span class='pts'>" + pa + "</span> · opponent played <span class='pts'>" + oa + "</span></div>" +
                                   "<div class='outcome-line'>You earned <span class='pts'>+" + pts + "</span> &nbsp; (opponent +" + opp_pts + ")</div>" +
                                   msg +
                               "</div>" +
                               "<div class='total-display'>Round " + round_num + " of " + CONFIG.rounds_per_game + " · Total so far: " + playerTotal + "</div>";
                    },
                    choices: "NO_KEYS",
                    trial_duration: CONFIG.outcome_display,
                    data: { trial_part: "outcome", game: game, round: round_num },
                },
            ];
        }

        for (var r = 1; r <= CONFIG.rounds_per_game; r++) {
            var roundNodes = makeRoundTrial(r);
            for (var i = 0; i < roundNodes.length; i++) nodes.push(roundNodes[i]);
        }

        // Game-end summary.
        nodes.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                return "<div class='game-banner'>End of " + gameLabel(game) + "</div>" +
                       "<p style='text-align:center'>You earned <strong>" + playerTotal + "</strong> points across " +
                       CONFIG.rounds_per_game + " rounds.</p>" +
                       "<p style='text-align:center;color:#6b7280'>Press any key to continue.</p>";
            },
            trial_duration: 6000,
        });

        return nodes;
    }

    // ---- Build the timeline ----
    var timeline = [];
    var GAME_ORDER = shuffledGames();

    // Welcome.
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Repeated 2x2 Games</h1>" +
            "<p>You will play two short games against a computer opponent.</p>" +
            "<p>Press any key to begin.</p>",
    });

    // Instructions.
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>You will play two different 2x2 games. In each game you have <strong>two actions</strong>: " +
            "<span class='key-hint'>F</span> or <span class='key-hint'>J</span>.</p>" +
            "<p>The opponent will also pick F or J. Your payoff depends on both choices.</p>" +
            "<p>Each game lasts <strong>" + CONFIG.rounds_per_game + " rounds</strong> against the same opponent.</p>",

            "<h2>Game A — Cooperate or Defect</h2>" +
            "<p>Each round you and the opponent simultaneously pick F or J.</p>" +
            "<p>Payoffs (your points, opponent's points):</p>" +
            payoffMatrixHTML("pd") +
            "<p>If you both pick <strong>J</strong>, you each get 8. If one picks F while the other picks J, " +
            "the F-player gets 10 and the J-player gets 0. If you both pick F, you each get 5.</p>",

            "<h2>Game B — Coordinate</h2>" +
            "<p>Same setup: pick F or J each round.</p>" +
            "<p>Payoffs (your points, opponent's points):</p>" +
            payoffMatrixHTML("bos") +
            "<p>You only score when you both pick the same action. Both F gives you 10 (opp 7); both J gives you 7 (opp 10). Mismatched picks give 0.</p>",

            "<h2>Controls</h2>" +
            "<div class='stim-prompt'>Press <span class='key-hint'>F</span> for action F · " +
            "<span class='key-hint'>J</span> for action J.</div>" +
            "<p style='text-align:center'>You have " + Math.round(CONFIG.response_deadline / 1000) +
            " seconds per round. A no-response counts as a random move.</p>" +
            "<p style='text-align:center'>You will see a running history of past rounds during play. Press Next to start.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    // Append each game's node-list in random order.
    for (var gi = 0; gi < GAME_ORDER.length; gi++) {
        var g = GAME_ORDER[gi];
        var block_order = gi + 1;
        var nodes = makeGameRunner(g, block_order);
        for (var ni = 0; ni < nodes.length; ni++) timeline.push(nodes[ni]);
    }

    // Data submission. Renumber trial_index across all "round" trials at submit time.
    timeline.push({
        type: jsPsychCallFunction,
        async: true,
        func: function (done) {
            var trial_data = jsPsych.data.get().filter({ trial_part: "round" }).values();
            for (var i = 0; i < trial_data.length; i++) {
                trial_data[i].trial_index = i + 1;
            }

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
                .catch(function (error) { console.error("Data submission error:", error); done(); });
        },
    });

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Task Complete</h2>" +
            "<p>Thank you for completing the games.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
