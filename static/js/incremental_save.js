/**
 * CogArena Incremental Save
 *
 * Wraps initJsPsych to automatically save partial trial data
 * periodically via PATCH. Loaded BEFORE experiment.js in each index.html.
 *
 * Config via URL params:
 *   ?save_interval=10       - save every N stimulus trials (default: 10)
 *   ?save_interval_ms=30000 - save every N ms (default: 30000)
 *   ?no_incremental=true    - disable incremental saving
 */
(function () {
    var params = new URLSearchParams(window.location.search);

    if (params.get("no_incremental") === "true") return;

    var SESSION_ID = params.get("session_id") || "debug";
    if (SESSION_ID === "debug") return;

    var SAVE_EVERY_N = parseInt(params.get("save_interval")) || 10;
    var SAVE_EVERY_MS = parseInt(params.get("save_interval_ms")) || 30000;

    var pathMatch = window.location.pathname.match(/\/tasks\/([^/]+)/);
    var TASK_ID = pathMatch ? pathMatch[1] : null;
    if (!TASK_ID) return;

    var _originalInitJsPsych = window.initJsPsych;
    var _lastSavedCount = 0;
    var _lastSaveTime = Date.now();
    var _saveInFlight = false;
    var _statusEl = null;

    // Tasks use varying trial_part values for the "main" trial: "stimulus",
    // "scenario" (moral_machine), "click" (grid_bandit), "pump_decision"
    // (bart), "decision"/"outcome" (effort_foraging), etc. We count ANY
    // trial that has a trial_part marker AND isn't a transient screen
    // (fixation, iti, feedback, practice). This is also what we ship to the
    // server for incremental saves so the data lands regardless of task
    // convention without polluting scores with practice trials.
    var _TRANSIENT_PARTS = {
        fixation: 1, iti: 1, feedback: 1,
        practice: 1, study_iti: 1, test_iti: 1,
    };
    function getStimulusTrials(jsPsychRef) {
        return jsPsychRef.data.get().filter(function (t) {
            if (!t.trial_part || _TRANSIENT_PARTS[t.trial_part]) return false;
            // Some tasks tag practice trials with practice:true rather than
            // a separate trial_part — exclude those too.
            if (t.practice === true) return false;
            return true;
        }).values();
    }

    // Always-on progress indicator. DOM-scanning agents (Browser-Use, etc.)
    // panic and try to reload the page if they see no interactive elements
    // during inter-trial intervals — that destroys jsPsych state. Keeping a
    // visible "Trials saved" element keeps the page non-blank at all times.
    function _ensureStatusEl() {
        if (_statusEl) return _statusEl;
        if (!document || !document.body) return null;
        var el = document.createElement("div");
        el.id = "cogarena-status";
        el.setAttribute("data-testid", "cogarena-status");
        el.style.cssText =
            "position:fixed;bottom:8px;right:8px;z-index:99999;" +
            "padding:4px 8px;font:12px system-ui,sans-serif;" +
            "color:#aaa;background:rgba(0,0,0,0.4);border-radius:4px;" +
            "pointer-events:none;user-select:none;";
        el.textContent = "CogArena: 0 trials completed";
        document.body.appendChild(el);
        _statusEl = el;
        return el;
    }

    function _updateStatusEl(nTrials) {
        var el = _ensureStatusEl();
        if (el) el.textContent = "CogArena: " + nTrials + " trials completed";
    }

    function doSave(trialData) {
        _saveInFlight = true;
        fetch("/api/data/" + SESSION_ID + "/" + TASK_ID, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                trial_data: trialData,
                is_complete: false,
            }),
        })
            .then(function () { _saveInFlight = false; _updateStatusEl(trialData.length); })
            .catch(function () { _saveInFlight = false; });
    }

    window.initJsPsych = function (opts) {
        opts = opts || {};
        var userOnDataUpdate = opts.on_data_update;
        var _jsPsychRef = null;

        opts.on_data_update = function (data) {
            if (userOnDataUpdate) userOnDataUpdate(data);
            if (!_jsPsychRef) return;
            // Only react to "main" trials, not transient ITI/fixation/feedback
            // or practice trials.
            if (!data.trial_part || _TRANSIENT_PARTS[data.trial_part]) return;
            if (data.practice === true) return;

            var allStimuli = getStimulusTrials(_jsPsychRef);
            // Always update the visible counter on every stimulus trial so
            // the agent sees forward progress even between saves.
            _updateStatusEl(allStimuli.length);

            if (_saveInFlight) return;
            var newTrials = allStimuli.length - _lastSavedCount;
            var elapsed = Date.now() - _lastSaveTime;

            if (newTrials >= SAVE_EVERY_N || elapsed >= SAVE_EVERY_MS) {
                _lastSavedCount = allStimuli.length;
                _lastSaveTime = Date.now();
                doSave(allStimuli);
            }
        };

        _jsPsychRef = _originalInitJsPsych(opts);
        // Mount the indicator as soon as the body exists.
        if (document.body) _ensureStatusEl();
        else document.addEventListener("DOMContentLoaded", _ensureStatusEl);

        // Last-resort save on page unload (keepalive allows fetch during unload)
        window.addEventListener("beforeunload", function () {
            if (!_jsPsychRef) return;
            var allStimuli = getStimulusTrials(_jsPsychRef);
            if (allStimuli.length > _lastSavedCount) {
                fetch("/api/data/" + SESSION_ID + "/" + TASK_ID, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ trial_data: allStimuli, is_complete: false }),
                    keepalive: true,
                });
            }
        });

        return _jsPsychRef;
    };
})();
