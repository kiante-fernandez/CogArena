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

    function getStimulusTrials(jsPsychRef) {
        return jsPsychRef.data.get().filter({ trial_part: "stimulus" }).values();
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
            .then(function () { _saveInFlight = false; })
            .catch(function () { _saveInFlight = false; });
    }

    window.initJsPsych = function (opts) {
        opts = opts || {};
        var userOnDataUpdate = opts.on_data_update;
        var _jsPsychRef = null;

        opts.on_data_update = function (data) {
            if (userOnDataUpdate) userOnDataUpdate(data);
            if (data.trial_part !== "stimulus" || !_jsPsychRef) return;
            if (_saveInFlight) return;

            var allStimuli = getStimulusTrials(_jsPsychRef);
            var newTrials = allStimuli.length - _lastSavedCount;
            var elapsed = Date.now() - _lastSaveTime;

            if (newTrials >= SAVE_EVERY_N || elapsed >= SAVE_EVERY_MS) {
                _lastSavedCount = allStimuli.length;
                _lastSaveTime = Date.now();
                doSave(allStimuli);
            }
        };

        _jsPsychRef = _originalInitJsPsych(opts);

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
