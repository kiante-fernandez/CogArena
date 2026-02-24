/**
 * CogArena Timing Helper
 *
 * Reads URL parameters to override trial durations:
 *   ?no_deadline=true      → null (jsPsych waits forever)
 *   ?trial_duration=60000  → custom ms value
 *   (no param)             → returns the default
 *
 * jsPsych always records actual RT regardless of trial_duration.
 */
function getTrialDuration(defaultMs) {
    var params = new URLSearchParams(window.location.search);
    if (params.get("no_deadline") === "true") {
        return null;
    }
    var override = params.get("trial_duration");
    if (override) {
        var parsed = parseInt(override, 10);
        if (!isNaN(parsed) && parsed > 0) {
            return parsed;
        }
    }
    return defaultMs;
}
