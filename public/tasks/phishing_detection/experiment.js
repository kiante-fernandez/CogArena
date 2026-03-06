(function () {
    var CONFIG = {
        n_trials: 60,
        n_pre: 10,
        n_train: 40,
        n_post: 10,
        phishing_rate: 0.3,
        valid_keys: ["f", "j"],
        response_deadline: 15000,
        fixation_duration: 500,
        feedback_duration: 1000,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "phishing_detection";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.n_trials = _nto;
        CONFIG.n_pre = Math.round(_nto * 0.167);
        CONFIG.n_train = Math.round(_nto * 0.667);
        CONFIG.n_post = _nto - CONFIG.n_pre - CONFIG.n_train;
    }

    var jsPsych = initJsPsych({ experiment_width: 800, minimum_valid_rt: 100 });
    if (SESSION_ID === "debug") window._jsPsych = jsPsych;

    // Email templates
    var HAM_EMAILS = [
        { from: "HR Department <hr@company.com>", subject: "Q3 Team Building Event", body: "Hi team, we're planning a team-building event for Q3. Please fill out the survey on the company intranet to share your preferences. Thanks!" },
        { from: "IT Support <support@company.com>", subject: "Scheduled Maintenance Tonight", body: "Dear colleagues, we will perform routine server maintenance tonight from 11 PM to 3 AM. Some services may be briefly unavailable." },
        { from: "Project Manager <pm@company.com>", subject: "Sprint Review Meeting Tomorrow", body: "Reminder: Sprint review is tomorrow at 2 PM in Conference Room B. Please prepare your updates. Dial-in link is on the calendar invite." },
        { from: "Finance <finance@company.com>", subject: "Expense Report Deadline", body: "Please submit all Q2 expense reports by Friday. Use the standard form available on SharePoint. Contact Maria in Finance for questions." },
        { from: "CEO Office <ceo@company.com>", subject: "Company Town Hall Next Week", body: "Join us for the quarterly town hall next Tuesday at 10 AM. We'll share updates on company performance and upcoming initiatives." },
        { from: "Learning Team <learn@company.com>", subject: "New Training Courses Available", body: "Several new courses have been added to our learning platform. Topics include data analytics, project management, and communication skills." },
        { from: "Facilities <facilities@company.com>", subject: "Parking Lot Repaving Notice", body: "The north parking lot will be repaved next week. Please use the south lot or street parking. We apologize for the inconvenience." },
        { from: "Benefits <benefits@company.com>", subject: "Open Enrollment Reminder", body: "Open enrollment for health benefits runs through the end of this month. Review plan options on the benefits portal and make your selections." },
        { from: "Marketing <marketing@company.com>", subject: "Brand Guidelines Update", body: "We've updated our brand guidelines document. Please review the changes on the shared drive and use the new templates for all materials." },
        { from: "Safety Team <safety@company.com>", subject: "Fire Drill Scheduled", body: "A fire drill is scheduled for Thursday at 3 PM. Please familiarize yourself with your floor's evacuation route posted by the elevators." },
    ];

    var PHISHING_EMAILS = [
        { from: "IT Security <it-security@c0mpany.com>", subject: "URGENT: Password Expires Today!", body: "Your password will expire in 2 hours! Click here immediately to reset it or you will lose access to all systems. Act now!" },
        { from: "Payroll <payroll@company-hr.net>", subject: "Paycheck Error - Action Required", body: "We detected an error in your latest paycheck. To receive your corrected payment, please verify your bank details by clicking the link below." },
        { from: "CEO <ceo@c0mpany.com>", subject: "Confidential: Wire Transfer Needed", body: "I need you to process an urgent wire transfer. This is confidential - do not discuss with anyone. Reply with your authorization code." },
        { from: "Microsoft <no-reply@micros0ft-support.com>", subject: "Your Account Has Been Compromised", body: "Suspicious activity detected on your account. Verify your identity immediately by entering your credentials at the link below." },
        { from: "Dropbox <notifications@dr0pbox-share.com>", subject: "Shared Document: Invoice_2024.pdf", body: "Someone shared a document with you. Click to view the invoice. You must sign in to access the shared file." },
        { from: "Amazon <orders@amaz0n-delivery.com>", subject: "Your Order Cannot Be Delivered", body: "We were unable to deliver your package. Please update your shipping address and payment information to reschedule delivery." },
        { from: "Bank Security <alert@your-bank-secure.com>", subject: "Unusual Login Detected", body: "We noticed a login from an unrecognized device. If this wasn't you, secure your account immediately by clicking below." },
        { from: "Prize Committee <winner@sweepstakes-official.com>", subject: "Congratulations! You've Won $50,000!", body: "You've been selected as a winner! Claim your prize by providing your personal details and a small processing fee." },
        { from: "IRS <refund@irs-tax-gov.com>", subject: "Tax Refund Available", body: "You are eligible for a tax refund of $3,847. Submit your banking information to receive your refund within 24 hours." },
        { from: "Netflix <billing@netfl1x-account.com>", subject: "Payment Failed - Update Now", body: "Your payment method was declined. Update your billing information within 24 hours to avoid account suspension." },
    ];

    function generateTrials() {
        var trials = [];
        var phases = [
            { name: "pre", count: CONFIG.n_pre, feedback: false },
            { name: "train", count: CONFIG.n_train, feedback: true },
            { name: "post", count: CONFIG.n_post, feedback: false },
        ];

        for (var p = 0; p < phases.length; p++) {
            var phase = phases[p];
            for (var i = 0; i < phase.count; i++) {
                var isPhishing = Math.random() < CONFIG.phishing_rate;
                var emailList = isPhishing ? PHISHING_EMAILS : HAM_EMAILS;
                var email = emailList[Math.floor(Math.random() * emailList.length)];
                trials.push({
                    phase: phase.name,
                    show_feedback: phase.feedback,
                    email_type: isPhishing ? "phishing" : "ham",
                    from: email.from,
                    subject: email.subject,
                    body: email.body,
                });
            }
        }
        return trials;
    }

    var allTrials = generateTrials();
    var timeline = [];

    timeline.push({ type: jsPsychHtmlKeyboardResponse, stimulus: "<h1>Phishing Detection</h1><p>Press any key to begin.</p>" });
    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2><p>You will be shown a series of emails.</p><p>Your task is to classify each email as <strong>Legitimate</strong> (safe) or <strong>Phishing</strong> (suspicious/fraudulent).</p>",
            "<h2>What to Look For</h2><p>Phishing emails often contain:</p><ul style='text-align:left'><li>Misspelled sender addresses</li><li>Urgent language or threats</li><li>Requests for personal information</li><li>Suspicious links or offers</li></ul>",
            "<h2>Response Keys</h2><p style='font-size:28px'><kbd>F</kbd> = <strong>LEGITIMATE</strong> (safe email)</p><p style='font-size:28px'><kbd>J</kbd> = <strong>PHISHING</strong> (suspicious email)</p><p>During training, you'll receive feedback. Press Next to start.</p>",
        ],
        show_clickable_nav: true, button_label_next: "Next", button_label_previous: "Previous",
    });

    var trialCounter = 0;
    var currentPhase = "";

    for (var ti = 0; ti < allTrials.length; ti++) {
        (function (trial) {
            if (trial.phase !== currentPhase) {
                var phaseLabels = { pre: "Pre-Training (No Feedback)", train: "Training (With Feedback)", post: "Post-Training (No Feedback)" };
                timeline.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: '<h2>' + phaseLabels[trial.phase] + '</h2><p>Press any key to continue.</p>',
                });
                currentPhase = trial.phase;
            }

            timeline.push({ type: jsPsychHtmlKeyboardResponse, stimulus: '<div class="fixation">+</div>', choices: "NO_KEYS", trial_duration: CONFIG.fixation_duration, data: { trial_part: "fixation" } });

            timeline.push({
                type: jsPsychHtmlKeyboardResponse,
                stimulus: '<div class="trial-counter">Trial ' + (trialCounter + 1) + ' of ' + CONFIG.n_trials + '</div>' +
                    '<div class="phase-label">' + trial.phase.toUpperCase() + '</div>' +
                    '<div class="email-box">' +
                    '<div class="email-from">From: ' + trial.from + '</div>' +
                    '<div class="email-subject">' + trial.subject + '</div>' +
                    '<div class="email-body">' + trial.body + '</div>' +
                    '</div>' +
                    '<div class="response-options">' +
                    '<div class="response-box">LEGITIMATE<div class="key-hint">F</div></div>' +
                    '<div class="response-box">PHISHING<div class="key-hint">J</div></div></div>',
                choices: CONFIG.valid_keys,
                trial_duration: CONFIG.response_deadline,
                data: {
                    trial_part: "stimulus",
                    phase: trial.phase,
                    email_type: trial.email_type,
                    show_feedback: trial.show_feedback,
                },
                on_finish: function (data) {
                    trialCounter++;
                    data.trial_index = trialCounter;
                    data.timed_out = data.response === null;
                    if (!data.timed_out) {
                        var judgedPhishing = data.response === "j";
                        data.correct = (judgedPhishing && data.email_type === "phishing") || (!judgedPhishing && data.email_type === "ham");
                    } else {
                        data.correct = false;
                    }
                },
            });

            if (trial.show_feedback) {
                timeline.push({
                    type: jsPsychHtmlKeyboardResponse,
                    stimulus: function () {
                        var last = jsPsych.data.get().last(1).values()[0];
                        if (last.timed_out) return '<div class="feedback-incorrect">Too slow!</div>';
                        return last.correct ? '<div class="feedback-correct">\u2714 Correct!</div>' : '<div class="feedback-incorrect">\u2718 Wrong - it was ' + last.email_type.toUpperCase() + '</div>';
                    },
                    choices: "NO_KEYS", trial_duration: CONFIG.feedback_duration, data: { trial_part: "feedback" },
                });
            }
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
