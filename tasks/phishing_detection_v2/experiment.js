(function () {
    var CONFIG = {
        n_pre_training: 10,
        n_training: 40,
        n_post_training: 10,
        phishing_rate: 0.5,
        valid_keys: ["f", "j"],
        key_legitimate: "f",
        key_phishing: "j",
        response_deadline: 30000,
        feedback_duration: 2000,
        iti_min: 500,
        iti_max: 1000,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "phishing_detection_v2";

    // Allow shrinking from URL: --n-trials sets total; we keep training:non-training ~4:1.
    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        var n = Math.max(3, _nto);
        CONFIG.n_training = Math.max(1, Math.round(n * 0.66));
        var rest = n - CONFIG.n_training;
        CONFIG.n_pre_training = Math.max(1, Math.floor(rest / 2));
        CONFIG.n_post_training = Math.max(1, rest - CONFIG.n_pre_training);
    }

    var jsPsych = initJsPsych({
        experiment_width: 800,
        minimum_valid_rt: 200,
    });
    if (SESSION_ID === "debug") window._jsPsych = jsPsych;

    // ---- Email corpus (loaded async) ----
    var EMAILS = null;
    var EMAILS_LOAD_PROMISE = fetch("/tasks/phishing_detection_v2/assets/emails.json", { cache: "force-cache" })
        .then(function (r) { return r.json(); })
        .then(function (data) { EMAILS = data.emails; })
        .catch(function (err) { console.error("Failed to load emails:", err); EMAILS = []; });

    function shuffle(arr) {
        for (var i = arr.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var t = arr[i]; arr[i] = arr[j]; arr[j] = t;
        }
        return arr;
    }

    function pickEmails(n_trials, phishing_rate) {
        var phish = EMAILS.filter(function (e) { return e.is_phishing; }).slice();
        var ham = EMAILS.filter(function (e) { return !e.is_phishing; }).slice();
        shuffle(phish);
        shuffle(ham);
        var n_phish = Math.round(n_trials * phishing_rate);
        var n_ham = n_trials - n_phish;
        // If we don't have enough ham (53), oversample.
        var picked_phish = [];
        for (var i = 0; i < n_phish; i++) picked_phish.push(phish[i % phish.length]);
        var picked_ham = [];
        for (var j = 0; j < n_ham; j++) picked_ham.push(ham[j % ham.length]);
        var combined = picked_phish.concat(picked_ham);
        return shuffle(combined);
    }

    // ---- Email rendering ----
    function senderInitial(sender) {
        var s = (sender || "").trim();
        var atIdx = s.indexOf("@");
        var local = atIdx > 0 ? s.slice(0, atIdx) : s;
        return (local.charAt(0) || "?").toUpperCase();
    }
    function senderDisplayName(sender) {
        var s = (sender || "").trim();
        var atIdx = s.indexOf("@");
        if (atIdx <= 0) return s;
        // Title-case the local part with a space or two for readability.
        var local = s.slice(0, atIdx).replace(/[._-]/g, " ");
        local = local.charAt(0).toUpperCase() + local.slice(1);
        return local;
    }
    function fakeDate() {
        // Stable per-trial pseudo-date (shown for realism only; not used in scoring).
        return "Mon, Jan 23, 2017, 9:42 AM";
    }

    function emailHtml(email, trialNum, totalNum) {
        return '' +
            '<div class="trial-counter">Trial ' + trialNum + ' of ' + totalNum + '</div>' +
            '<div class="email-window">' +
                '<div class="email-toolbar">' +
                    '<span>Inbox</span>' +
                    '<span class="icons">' +
                        '<span>↩</span><span>↪</span><span>📎</span>' +
                    '</span>' +
                '</div>' +
                '<div class="email-header">' +
                    '<div class="email-subject">' + escapeHtml(email.subject || "(no subject)") + '</div>' +
                    '<div class="email-meta">' +
                        '<div class="email-from">' +
                            '<span class="email-avatar">' + senderInitial(email.sender) + '</span>' +
                            '<div>' +
                                '<div class="email-from-name">' + escapeHtml(senderDisplayName(email.sender)) + '</div>' +
                                '<div class="email-from-addr">&lt;' + escapeHtml(email.sender || "unknown") + '&gt;</div>' +
                            '</div>' +
                        '</div>' +
                        '<div class="email-date">' + fakeDate() + '</div>' +
                    '</div>' +
                '</div>' +
                '<div class="email-body">' + (email.body_html || "") + '</div>' +
            '</div>' +
            '<div class="response-prompt">' +
                'Press <kbd>F</kbd> for <strong>LEGITIMATE</strong> &nbsp;or&nbsp; <kbd>J</kbd> for <strong>PHISHING</strong>' +
            '</div>';
    }

    function escapeHtml(s) {
        if (s === undefined || s === null) return "";
        return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    var trialCounter = 0;

    var timeline = [];

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Phishing Detection</h1>" +
            "<p>Welcome. Press any key to begin.</p>",
    });

    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>You will see a series of emails as they would appear in your inbox.</p>" +
            "<p>For each email, decide whether it is <strong>LEGITIMATE</strong> (a real, harmless email) or <strong>PHISHING</strong> (a suspicious or fraudulent email designed to steal information).</p>",

            "<h2>What to look for</h2>" +
            "<p>Phishing emails often include:</p>" +
            "<ul style='text-align:left; max-width:560px; margin:0 auto'>" +
            "<li>Misspelled or look-alike sender domains (e.g.\\ <em>paypa1.com</em>)</li>" +
            "<li>Urgent language or threats (\"act now or lose access\")</li>" +
            "<li>Requests for passwords, payment info, or personal data</li>" +
            "<li>Suspicious links to unfamiliar sites</li>" +
            "<li>Generic greetings (\"Dear customer\")</li>" +
            "</ul>" +
            "<p>Legitimate emails come from real services and don't ask you to enter sensitive info via a link.</p>",

            "<h2>Phases</h2>" +
            "<p>The task has three phases:</p>" +
            "<p><strong>Pre-training</strong> (" + CONFIG.n_pre_training + " emails, no feedback)</p>" +
            "<p><strong>Training</strong> (" + CONFIG.n_training + " emails, with correct/incorrect feedback after each)</p>" +
            "<p><strong>Post-training</strong> (" + CONFIG.n_post_training + " emails, no feedback)</p>" +
            "<p>Press Next to start.</p>",

            "<h2>Response keys</h2>" +
            "<p style='font-size:24px'><kbd>F</kbd> = LEGITIMATE</p>" +
            "<p style='font-size:24px'><kbd>J</kbd> = PHISHING</p>" +
            "<p>You have up to " + Math.round(CONFIG.response_deadline / 1000) + " seconds per email.</p>" +
            "<p>Press Next to begin the pre-training phase.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    // Per-phase email assignment, populated once EMAILS finishes loading.
    var PHASE_EMAILS = { pre: [], training: [], post: [] };

    // Wait for emails to load AND build the per-phase queues.
    timeline.push({
        type: jsPsychCallFunction,
        async: true,
        func: function (done) {
            EMAILS_LOAD_PROMISE.then(function () {
                PHASE_EMAILS.pre = pickEmails(CONFIG.n_pre_training, CONFIG.phishing_rate);
                PHASE_EMAILS.training = pickEmails(CONFIG.n_training, CONFIG.phishing_rate);
                PHASE_EMAILS.post = pickEmails(CONFIG.n_post_training, CONFIG.phishing_rate);
                done();
            });
        },
    });

    function buildPhase(phase, n_trials, give_feedback, totalSoFar, total) {
        var nodes = [];
        // Phase intro
        var phaseLabels = { pre: "Pre-training", training: "Training (with feedback)", post: "Post-training" };
        nodes.push({
            type: jsPsychHtmlKeyboardResponse,
            stimulus:
                "<h2>" + phaseLabels[phase] + " — " + n_trials + " emails</h2>" +
                (give_feedback
                    ? "<p>You will see feedback after each response.</p>"
                    : "<p>No feedback will be given. Just respond as best you can.</p>") +
                "<p>Press any key to start.</p>",
        });

        var localTotalSoFar = { value: totalSoFar };

        for (var i = 0; i < n_trials; i++) {
            (function (trial_in_phase) {
                nodes.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: function () {
                        var email = PHASE_EMAILS[phase][trial_in_phase - 1];
                        return emailHtml(email, localTotalSoFar.value + trial_in_phase, total);
                    },
                    choices: CONFIG.valid_keys,
                    trial_duration: CONFIG.response_deadline,
                    data: function () {
                        var email = PHASE_EMAILS[phase][trial_in_phase - 1];
                        return {
                            trial_part: "stimulus",
                            phase: phase,
                            trial_in_phase: trial_in_phase,
                            email_id: email.id,
                            is_phishing: email.is_phishing,
                        };
                    },
                    on_finish: function (data) {
                        trialCounter++;
                        data.trial_index = trialCounter;
                        if (data.response === null) {
                            data.timed_out = true;
                            data.responded_phishing = null;
                            data.is_hit = false;
                            data.is_false_alarm = false;
                            data.is_miss = data.is_phishing;
                            data.is_correct_rejection = !data.is_phishing;
                            data.correct = false;
                        } else {
                            data.timed_out = false;
                            data.responded_phishing = (data.response === CONFIG.key_phishing);
                            data.is_hit = data.is_phishing && data.responded_phishing;
                            data.is_false_alarm = !data.is_phishing && data.responded_phishing;
                            data.is_miss = data.is_phishing && !data.responded_phishing;
                            data.is_correct_rejection = !data.is_phishing && !data.responded_phishing;
                            data.correct = data.is_hit || data.is_correct_rejection;
                        }
                    },
                });

                if (give_feedback) {
                    nodes.push({
                        type: jsPsychHtmlKeyboardResponse,
                        stimulus: function () {
                            var last = jsPsych.data.get().last(1).values()[0];
                            if (last.timed_out) {
                                return '<div class="feedback timed_out">Too slow.<small>The email was ' +
                                    (last.is_phishing ? "phishing" : "legitimate") + '.</small></div>';
                            }
                            if (last.correct) {
                                return '<div class="feedback correct">✔ Correct<small>The email was ' +
                                    (last.is_phishing ? "phishing" : "legitimate") + '.</small></div>';
                            }
                            return '<div class="feedback wrong">✘ Incorrect<small>The email was ' +
                                (last.is_phishing ? "phishing" : "legitimate") + '.</small></div>';
                        },
                        choices: "NO_KEYS",
                        trial_duration: CONFIG.feedback_duration,
                        data: { trial_part: "feedback" },
                    });
                }

                nodes.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: '<div class="fixation">+</div>',
                    choices: "NO_KEYS",
                    trial_duration: function () {
                        return CONFIG.iti_min + Math.random() * (CONFIG.iti_max - CONFIG.iti_min);
                    },
                    data: { trial_part: "iti" },
                });
            })(i + 1);
        }
        return nodes;
    }

    var totalTrials = CONFIG.n_pre_training + CONFIG.n_training + CONFIG.n_post_training;
    timeline = timeline.concat(buildPhase("pre", CONFIG.n_pre_training, false, 1, totalTrials));
    timeline = timeline.concat(buildPhase("training", CONFIG.n_training, true, CONFIG.n_pre_training + 1, totalTrials));
    timeline = timeline.concat(buildPhase("post", CONFIG.n_post_training, false, CONFIG.n_pre_training + CONFIG.n_training + 1, totalTrials));

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
            "<p>Thank you for completing the phishing detection task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
