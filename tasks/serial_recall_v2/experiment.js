(function () {
    var CONFIG = {
        n_study_pairs: 16,
        pairs_per_similarity_level: 4,
        similarity_levels: [0.2, 0.4, 0.6, 0.8],
        study_pair_duration: 3000,
        study_pair_isi: 500,
        filler_break: 5000,
        recall_cue_deadline: 8000,
        response_match_chars: 3,
    };
    CONFIG.recall_cue_deadline = getTrialDuration(CONFIG.recall_cue_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "serial_recall_v2";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        // n_trials is total study + recall trials. Halve to get pairs.
        var n_pairs = Math.max(2, Math.floor(_nto / 2));
        CONFIG.n_study_pairs = n_pairs;
        CONFIG.pairs_per_similarity_level = Math.max(1, Math.floor(n_pairs / CONFIG.similarity_levels.length));
    }

    var jsPsych = initJsPsych({ experiment_width: 800, minimum_valid_rt: 50 });
    if (SESSION_ID === "debug") window._jsPsych = jsPsych;

    // ---- Word-pair pool, sampled subsets of Haridi & Schulz's PairsMaxSim* lists. ----
    var POOL = {
        0.2: [
            ["bear", "grass"], ["domino", "statue"], ["fudge", "rifle"],
            ["medal", "torso"], ["blower", "faucet"], ["game", "pepper"],
            ["globe", "coal"], ["cloak", "chalk"], ["clay", "tick"],
            ["hanger", "lime"], ["suit", "sheet"], ["radio", "dress"],
            ["leash", "drink"], ["lion", "fossil"], ["sponge", "watch"],
            ["blimp", "taco"], ["cannon", "garlic"], ["bikini", "bison"],
            ["ankle", "dagger"], ["chest", "dial"]
        ],
        0.4: [
            ["rope", "skunk"], ["closet", "camper"], ["earwig", "walnut"],
            ["shelf", "gauze"], ["slime", "possum"], ["poppy", "crayon"],
            ["ramp", "noose"], ["kayak", "block"], ["raft", "shorts"],
            ["daisy", "riser"], ["barrel", "crane"], ["blind", "switch"],
            ["leek", "roll"], ["pipe", "paper"], ["bowtie", "wolf"],
            ["cape", "chime"], ["target", "clasp"], ["crutch", "camel"],
            ["cactus", "moose"], ["money", "wand"]
        ],
        0.6: [
            ["tomato", "dough"], ["cookie", "cereal"], ["desk", "toilet"],
            ["branch", "train"], ["cart", "buggy"], ["cigar", "flask"],
            ["rosary", "altar"], ["heater", "tripod"], ["napkin", "tinsel"],
            ["fungus", "moth"], ["radish", "melon"], ["powder", "floss"],
            ["chisel", "spool"], ["mast", "frame"], ["tape", "wire"],
            ["seed", "leaf"], ["makeup", "paint"], ["stem", "stump"],
            ["chip", "tablet"], ["bonsai", "tulip"]
        ],
        0.8: [
            ["sauce", "fondue"], ["knee", "wrist"], ["chick", "girl"],
            ["kiwi", "apple"], ["flag", "banner"], ["file", "folder"],
            ["squid", "fish"], ["goose", "duck"], ["horse", "pony"],
            ["kilt", "tiara"], ["candle", "lamp"], ["sundae", "sushi"],
            ["yarn", "alpaca"], ["juice", "soda"], ["jersey", "shirt"],
            ["snake", "koala"], ["hotdog", "bacon"], ["chili", "clove"],
            ["chin", "neck"], ["puddle", "sand"]
        ],
    };

    function shuffle(arr) {
        var a = arr.slice();
        for (var i = a.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var t = a[i]; a[i] = a[j]; a[j] = t;
        }
        return a;
    }

    function pickStudyPairs() {
        var pairs = [];
        for (var s = 0; s < CONFIG.similarity_levels.length; s++) {
            var sim = CONFIG.similarity_levels[s];
            var subset = shuffle(POOL[sim]).slice(0, CONFIG.pairs_per_similarity_level);
            for (var i = 0; i < subset.length; i++) {
                pairs.push({ word1: subset[i][0], word2: subset[i][1], similarity_level: sim });
            }
        }
        // For recall, we'll cue word1 → ask for word2.
        return shuffle(pairs);
    }

    var STUDY_PAIRS = pickStudyPairs();
    var trial_counter = 0;

    function pairCardHTML(p) {
        return '<div class="pair-card"><div class="pair-words">' +
                   p.word1 + '<span class="pair-divider">—</span>' + p.word2 +
               '</div></div>';
    }

    function blankFrame() {
        return '<div style="height: 80px"></div>';
    }

    var timeline = [];

    // ---- Welcome ----
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Cued Paired-Associate Recall</h1>" +
            "<p>You will study a list of word pairs and then try to recall each partner.</p>" +
            "<p>Press any key to begin.</p>",
    });

    // ---- Instructions ----
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>This task has three parts:</p>" +
            "<ol style='text-align:left;display:inline-block'>" +
            "<li><strong>Study</strong>: " + CONFIG.n_study_pairs + " word pairs are shown one at a time.</li>" +
            "<li><strong>Brief pause</strong>: a 5-second countdown.</li>" +
            "<li><strong>Recall</strong>: for each cue word, type the first <strong>" +
            CONFIG.response_match_chars + " letters</strong> of its partner.</li>" +
            "</ol>",

            "<h2>Study phase</h2>" +
            "<p>Each word pair will appear for " + (CONFIG.study_pair_duration / 1000) +
            " seconds. Try to remember which two words went together.</p>" +
            "<p>Word pairs vary in how related the two words feel — some are clearly related, others are unrelated.</p>",

            "<h2>Recall phase</h2>" +
            "<p>For each cue word, type the first <strong>" + CONFIG.response_match_chars +
            " letters</strong> of the partner you saw paired with it.</p>" +
            "<p>You can also type the whole word — only the first " + CONFIG.response_match_chars +
            " letters are scored.</p>" +
            "<p>If you don't remember, leave the field blank or type any letters.</p>" +
            "<p>You have " + Math.round(CONFIG.recall_cue_deadline / 1000) + " seconds per cue.</p>" +
            "<p>Press <span class='key-hint'>Enter</span> to submit, or click the Submit button.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    // ---- Study phase ----
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus: "<div class='stage-label'>Study phase</div>" +
                  "<p>Watch each word pair carefully.</p>" +
                  "<p>Press any key to begin studying.</p>",
    });

    for (var s = 0; s < STUDY_PAIRS.length; s++) {
        (function (pair, position) {
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: "<div class='stage-label'>Studying pair " + (position + 1) + " of " + STUDY_PAIRS.length + "</div>" +
                          pairCardHTML(pair),
                choices: "NO_KEYS",
                trial_duration: CONFIG.study_pair_duration,
                data: {
                    trial_part: "study",
                    study_position: position + 1,
                    cue_word: pair.word1,
                    target_word: pair.word2,
                    similarity_level: pair.similarity_level,
                },
            });
            // ISI
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: blankFrame(),
                choices: "NO_KEYS",
                trial_duration: CONFIG.study_pair_isi,
                data: { trial_part: "isi" },
            });
        })(STUDY_PAIRS[s], s);
    }

    // ---- Filler break ----
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus: function () {
            return "<div class='stage-label'>Brief pause</div>" +
                   "<div class='countdown' id='countdown'>" + Math.round(CONFIG.filler_break / 1000) + "</div>" +
                   "<p style='text-align:center;color:#6b7280'>Recall phase starts shortly.</p>";
        },
        choices: "NO_KEYS",
        trial_duration: CONFIG.filler_break,
        on_load: function () {
            var remaining = Math.round(CONFIG.filler_break / 1000);
            var iv = setInterval(function () {
                remaining -= 1;
                var el = document.getElementById("countdown");
                if (el) el.textContent = String(Math.max(0, remaining));
                if (remaining <= 0) clearInterval(iv);
            }, 1000);
        },
        data: { trial_part: "filler" },
    });

    // ---- Recall phase intro ----
    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus: "<div class='stage-label'>Recall phase</div>" +
                  "<p>For each cue word, type the first <strong>" + CONFIG.response_match_chars +
                  " letters</strong> of its partner and press Enter.</p>" +
                  "<p>Press any key to start the recall trials.</p>",
    });

    // ---- Recall trials (one per study pair, shuffled order) ----
    var RECALL_ORDER = shuffle(STUDY_PAIRS.map(function (_, i) { return i; }));

    for (var ri = 0; ri < RECALL_ORDER.length; ri++) {
        (function (pair, recall_position, study_position) {
            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: function () {
                    return "<div class='stage-label'>Recall " + (recall_position + 1) + " of " + STUDY_PAIRS.length + "</div>" +
                           "<div class='cue-card'>" +
                               "<div class='cue-word'>" + pair.word1 + " — ?</div>" +
                               "<input type='text' id='recall-input' class='recall-input' " +
                                   "autocomplete='off' autocorrect='off' autocapitalize='off' spellcheck='false' " +
                                   "maxlength='20' />" +
                               "<button id='recall-submit' class='recall-submit' type='button'>Submit</button>" +
                           "</div>" +
                           "<div class='stim-prompt'>Type the first <strong>" + CONFIG.response_match_chars +
                           "</strong> letters of the partner. Press <span class='key-hint'>Enter</span> or click Submit.</div>";
                },
                choices: "NO_KEYS",
                trial_duration: CONFIG.recall_cue_deadline,
                data: {
                    trial_part: "recall",
                    study_position: study_position + 1,
                    cue_word: pair.word1,
                    target_word: pair.word2,
                    similarity_level: pair.similarity_level,
                },
                on_load: function () {
                    var input = document.getElementById("recall-input");
                    var submit = document.getElementById("recall-submit");
                    if (!input || !submit) return;
                    input.focus();
                    var startTime = performance.now();

                    function finish() {
                        var rt = performance.now() - startTime;
                        var raw = (input.value || "").trim().toLowerCase();
                        var truncated = raw.slice(0, CONFIG.response_match_chars);
                        var target_truncated = String(pair.word2).slice(0, CONFIG.response_match_chars).toLowerCase();
                        trial_counter++;
                        jsPsych.finishTrial({
                            trial_part: "recall",
                            trial_index: trial_counter,
                            study_position: study_position + 1,
                            cue_word: pair.word1,
                            target_word: pair.word2,
                            similarity_level: pair.similarity_level,
                            response: raw,
                            response_truncated: truncated,
                            target_truncated: target_truncated,
                            correct: truncated === target_truncated && truncated.length > 0,
                            rt: rt,
                            timed_out: false,
                        });
                    }

                    submit.addEventListener("click", finish);
                    input.addEventListener("keydown", function (e) {
                        if (e.key === "Enter") {
                            e.preventDefault();
                            finish();
                        }
                    });
                },
                on_finish: function (data) {
                    if (data.trial_part !== "recall" || data.response === undefined) {
                        // Trial timed out without a submit.
                        trial_counter++;
                        var target_truncated = String(pair.word2).slice(0, CONFIG.response_match_chars).toLowerCase();
                        Object.assign(data, {
                            trial_part: "recall",
                            trial_index: trial_counter,
                            study_position: study_position + 1,
                            cue_word: pair.word1,
                            target_word: pair.word2,
                            similarity_level: pair.similarity_level,
                            response: "",
                            response_truncated: "",
                            target_truncated: target_truncated,
                            correct: false,
                            timed_out: true,
                        });
                    }
                },
            });
        })(STUDY_PAIRS[RECALL_ORDER[ri]], ri, RECALL_ORDER[ri]);
    }

    // ---- Data submission ----
    timeline.push({
        type: jsPsychCallFunction,
        async: true,
        func: function (done) {
            var trial_data = jsPsych.data.get().filter({ trial_part: "recall" }).values();
            for (var i = 0; i < trial_data.length; i++) trial_data[i].trial_index = i + 1;
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
            "<p>Thank you for completing the recall task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
